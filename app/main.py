import os
import logging
from fastapi import (
    FastAPI,
    WebSocket,
    WebSocketDisconnect,
    Query,
    Depends,
    HTTPException,
    status,
    UploadFile,
    File,
)
from sqlalchemy.orm import Session
from typing import List
import asyncio

from . import models, schemas
from .database import SessionLocal, engine
from .auth import authenticate_user, create_access_token, get_current_user
from . import redis, init_redis_pool

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create the FastAPI app
app = FastAPI()

# Startup and shutdown events
@app.on_event("startup")
async def startup():
    await init_redis_pool()
    models.Base.metadata.create_all(bind=engine)

@app.on_event("shutdown")
async def shutdown():
    redis.close()
    await redis.wait_closed()

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# User registration endpoint
@app.post("/users/", response_model=schemas.User)
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    new_user = models.User(username=user.username)
    new_user.set_password(user.password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

# User login endpoint
@app.post("/token", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

# Endpoint to create chat rooms
@app.post("/chat_rooms/", response_model=schemas.ChatRoom)
def create_chat_room(
    chat_room: schemas.ChatRoomCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    db_chat_room = db.query(models.ChatRoom).filter(models.ChatRoom.name == chat_room.name).first()
    if db_chat_room:
        raise HTTPException(status_code=400, detail="Chat room already exists")
    new_chat_room = models.ChatRoom(name=chat_room.name, is_private=chat_room.is_private)
    db.add(new_chat_room)
    db.commit()
    db.refresh(new_chat_room)
    # Add current user as a member
    membership = models.Membership(user_id=current_user.id, chat_room_id=new_chat_room.id)
    db.add(membership)
    db.commit()
    return new_chat_room

# Endpoint to join chat rooms
@app.post("/chat_rooms/{chat_room_id}/join")
def join_chat_room(
    chat_room_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    chat_room = db.query(models.ChatRoom).filter(models.ChatRoom.id == chat_room_id).first()
    if not chat_room:
        raise HTTPException(status_code=404, detail="Chat room not found")
    membership = (
        db.query(models.Membership)
        .filter_by(user_id=current_user.id, chat_room_id=chat_room_id)
        .first()
    )
    if membership:
        raise HTTPException(status_code=400, detail="Already a member of this chat room")
    new_membership = models.Membership(user_id=current_user.id, chat_room_id=chat_room_id)
    db.add(new_membership)
    db.commit()
    return {"message": "Joined chat room successfully"}

# Endpoint to search messages
@app.get("/chat_rooms/{chat_room_id}/search", response_model=List[schemas.Message])
def search_messages(
    chat_room_id: int,
    query: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    messages = (
        db.query(models.Message)
        .filter(
            models.Message.chat_room_id == chat_room_id,
            models.Message.content.contains(query),
        )
        .all()
    )
    return messages

# Endpoint to delete a message
@app.delete("/messages/{message_id}")
def delete_message(
    message_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    message = db.query(models.Message).filter(models.Message.id == message_id).first()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    if message.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this message")
    db.delete(message)
    db.commit()
    return {"message": "Message deleted successfully"}

# File upload endpoint
@app.post("/upload/")
async def upload_file(
    file: UploadFile = File(...), current_user: models.User = Depends(get_current_user)
):
    file_location = f"uploads/{file.filename}"
    os.makedirs(os.path.dirname(file_location), exist_ok=True)
    with open(file_location, "wb") as buffer:
        buffer.write(await file.read())
    return {"file_url": f"/{file_location}"}

# WebSocket endpoint
@app.websocket("/ws/{chat_room_id}")
async def websocket_endpoint(websocket: WebSocket, chat_room_id: int, token: str = Query(...)):
    await websocket.accept()
    try:
        db = SessionLocal()
        current_user = await get_current_user(token=token, db=db)
        # Check if user is a member of the chat room
        membership = (
            db.query(models.Membership)
            .filter_by(user_id=current_user.id, chat_room_id=chat_room_id)
            .first()
        )
        if not membership:
            await websocket.close(code=1008, reason="Not a member of the chat room")
            return

        # Subscribe to Redis channel
        redis_channel = f"chat_room_{chat_room_id}"
        pubsub = await redis.subscribe(redis_channel)
        channel = pubsub[0]

        async def send_messages():
            while True:
                try:
                    message = await channel.get_json()
                    if message:
                        await websocket.send_json(message)
                except Exception as e:
                    print(f"Error sending message: {e}")
                    break

        send_task = asyncio.create_task(send_messages())

        while True:
            data = await websocket.receive_json()
            message_type = data.get("type")
            if message_type == "chat":
                is_attachment = data.get("is_attachment", False)
                content = data.get("content")
                message = models.Message(
                    content=content,
                    user_id=current_user.id,
                    chat_room_id=chat_room_id,
                    is_attachment=is_attachment,
                )
                db.add(message)
                db.commit()
                msg = {
                    "type": "chat",
                    "content": content,
                    "username": current_user.username,
                    "is_attachment": is_attachment,
                    "message_id": message.id,
                }
                # Publish the message to Redis
                await redis.publish_json(redis_channel, msg)
            elif message_type == "typing":
                # Broadcast typing indicator
                msg = {"type": "typing", "username": current_user.username}
                await redis.publish_json(redis_channel, msg)
            elif message_type == "reaction":
                # Handle reactions
                reaction_type = data.get("reaction_type")
                message_id = data.get("message_id")
                reaction = models.Reaction(
                    user_id=current_user.id, message_id=message_id, reaction_type=reaction_type
                )
                db.merge(reaction)  # Use merge to handle upserts
                db.commit()
                msg = {
                    "type": "reaction",
                    "message_id": message_id,
                    "reaction_type": reaction_type,
                    "username": current_user.username,
                }
                await redis.publish_json(redis_channel, msg)
            elif message_type == "read_receipt":
                # Handle read receipts
                message_id = data.get("message_id")
                read_status = models.MessageReadStatus(
                    user_id=current_user.id, message_id=message_id
                )
                db.merge(read_status)
                db.commit()
                # Optionally notify the sender
            # Add handling for other message types if needed
    except WebSocketDisconnect:
        send_task.cancel()
        await redis.unsubscribe(redis_channel)
        print(f"Client disconnected")
    except Exception as e:
        logger.error(f"Error: {e}")
        await websocket.close()
    finally:
        db.close()