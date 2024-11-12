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
from fastapi.responses import FileResponse , HTMLResponse
from fastapi.staticfiles import StaticFiles  # Import StaticFiles
from sqlalchemy.orm import Session
from typing import List
import asyncio
import json

from fastapi.security import OAuth2PasswordRequestForm
from . import models, schemas
from .database import SessionLocal, engine
from .auth import authenticate_user, create_access_token, get_current_user
import redis.asyncio as redis



# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create the FastAPI app
app = FastAPI()

app.mount("/static", StaticFiles(directory="frontend/static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def read_index():
    return FileResponse("frontend/index.html")


# app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")


@app.on_event("startup")
async def startup():
    # Initialize Redis client
    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = int(os.getenv("REDIS_PORT", 6379))
    app.state.redis_client = redis.Redis(
        host=redis_host,
        port=redis_port,
        db=0,
        encoding='utf-8',
        decode_responses=True,
    )
    models.Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        general_chat_room = db.query(models.ChatRoom).filter(models.ChatRoom.name == 'General').first()
        if not general_chat_room:
            general_chat_room = models.ChatRoom(name='General', is_private=False)
            db.add(general_chat_room)
            db.commit()
    finally:
        db.close()

@app.on_event("shutdown")
async def shutdown():
    if app.state.redis_client:
        await app.state.redis_client.close()


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

@app.get("/chat_rooms/", response_model=List[schemas.ChatRoom])
def list_chat_rooms(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return db.query(models.ChatRoom).all()

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
    # Validate file size and type
    if file.content_type not in ["image/png", "image/jpeg", "application/pdf"]:
        raise HTTPException(status_code=400, detail="Unsupported file type")
    if file.spool_max_size > 10 * 1024 * 1024:  # Limit to 10MB
        raise HTTPException(status_code=400, detail="File too large")
    # Sanitize file name
    filename = os.path.basename(file.filename)
    file_location = f"uploads/{filename}"
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

        # Use Redis client from app.state
        redis_client = app.state.redis_client

        # Subscribe to Redis channel
        redis_channel = f"chat_room_{chat_room_id}"
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(redis_channel)

        async def send_messages():
            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message:
                    data = json.loads(message['data'])
                    await websocket.send_json(data)
                await asyncio.sleep(0.01)  # Prevent tight loop

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
                await redis_client.publish(redis_channel, json.dumps(msg))
                # Send the message back to the sender
                await websocket.send_json(msg)
            elif message_type == "typing":
                # Broadcast typing indicator
                msg = {"type": "typing", "username": current_user.username}
                await redis_client.publish(redis_channel, json.dumps(msg))
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
                await redis_client.publish(redis_channel, json.dumps(msg))
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
        await pubsub.unsubscribe(redis_channel)
        logger.info(f"Client disconnected: {current_user.username}")
    except Exception as e:
        logger.error(f"Error in WebSocket connection: {e}", exc_info=True)
        await websocket.close()

    finally:
        db.close()