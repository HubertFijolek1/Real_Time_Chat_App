import os
import logging
import asyncio
import json
from typing import List
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
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from starlette.datastructures import State

from fastapi.security import OAuth2PasswordRequestForm
from . import models, schemas
from .database import SessionLocal, engine
from .auth import authenticate_user, create_access_token, get_current_user_from_token, get_current_user
import redis.asyncio as redis

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Set logging level to DEBUG to capture all logs
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

# Create the FastAPI app
app = FastAPI()
app.state: State = State()

# Mount static directories
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Serve the index HTML file
@app.get("/", response_class=HTMLResponse)
async def read_index():
    logger.debug("Serving index.html")
    return FileResponse("frontend/index.html")

# Application startup event
@app.on_event("startup")
async def startup():
    # Initialize Redis client
    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = int(os.getenv("REDIS_PORT", 6379))
    logger.debug(f"Connecting to Redis at {redis_host}:{redis_port}")
    app.state.redis_client = redis.Redis(
        host=redis_host,
        port=redis_port,
        db=0,
        encoding='utf-8',
        decode_responses=True,
    )
    try:
        await app.state.redis_client.ping()
        logger.info("Successfully connected to Redis")
    except Exception as e:
        logger.error(f"Error connecting to Redis: {str(e)}")

    # Create database tables and ensure the 'General' chat room exists
    logger.debug("Creating database tables if they do not exist")
    models.Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        general_chat_room = db.query(models.ChatRoom).filter(models.ChatRoom.name == 'General').first()
        if not general_chat_room:
            logger.debug("General chat room not found, creating it")
            general_chat_room = models.ChatRoom(name='General', is_private=False)
            db.add(general_chat_room)
            db.commit()
            db.refresh(general_chat_room)
        # Log the ID of the 'General' chat room
        logger.info(f"General chat room ID: {general_chat_room.id}")
    except Exception as e:
        logger.error(f"Error during startup database operations: {e}", exc_info=True)
    finally:
        db.close()

# Application shutdown event
@app.on_event("shutdown")
async def shutdown():
    if app.state.redis_client:
        logger.debug("Closing Redis connection")
        await app.state.redis_client.close()

# Dependency to get DB session
def get_db():
    logger.debug("Creating new database session")
    db = SessionLocal()
    try:
        yield db
    finally:
        logger.debug("Closing database session")
        db.close()

# User registration endpoint
@app.post("/users/", response_model=schemas.User)
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    logger.debug(f"Attempting to register user: {user.username}")
    db_user = db.query(models.User).filter(models.User.username == user.username).first()
    if db_user:
        logger.warning(f"Username already registered: {user.username}")
        raise HTTPException(status_code=400, detail="Username already registered")
    new_user = models.User(username=user.username)
    new_user.set_password(user.password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    logger.info(f"User registered successfully: {new_user.username}")
    return new_user

# User login endpoint
@app.post("/token", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    logger.debug(f"User login attempt: {form_data.username}")
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        logger.warning(f"Login failed for user: {form_data.username}")
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    access_token = create_access_token(data={"sub": user.username})
    logger.info(f"User logged in successfully: {user.username}")
    return {"access_token": access_token, "token_type": "bearer"}

# Endpoint to create chat rooms
@app.post("/chat_rooms/", response_model=schemas.ChatRoom)
def create_chat_room(
    chat_room: schemas.ChatRoomCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    logger.debug(f"User {current_user.username} is creating a chat room: {chat_room.name}")
    db_chat_room = db.query(models.ChatRoom).filter(models.ChatRoom.name == chat_room.name).first()
    if db_chat_room:
        logger.warning(f"Chat room already exists: {chat_room.name}")
        raise HTTPException(status_code=400, detail="Chat room already exists")
    new_chat_room = models.ChatRoom(name=chat_room.name, is_private=chat_room.is_private)
    db.add(new_chat_room)
    db.commit()
    db.refresh(new_chat_room)
    # Add current user as a member
    membership = models.Membership(user_id=current_user.id, chat_room_id=new_chat_room.id)
    db.add(membership)
    db.commit()
    logger.info(f"Chat room created successfully: {new_chat_room.name}")
    return new_chat_room

# Endpoint to join chat rooms
@app.post("/chat_rooms/{chat_room_id}/join")
def join_chat_room(
    chat_room_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    logger.debug(f"User {current_user.username} is attempting to join chat room {chat_room_id}")
    chat_room = db.query(models.ChatRoom).filter(models.ChatRoom.id == chat_room_id).first()
    if not chat_room:
        logger.error(f"Chat room not found: ID {chat_room_id}")
        raise HTTPException(status_code=404, detail="Chat room not found")
    membership = (
        db.query(models.Membership)
        .filter_by(user_id=current_user.id, chat_room_id=chat_room_id)
        .first()
    )
    if membership:
        logger.warning(f"User {current_user.username} is already a member of chat room {chat_room_id}")
        raise HTTPException(status_code=400, detail="Already a member of this chat room")
    new_membership = models.Membership(user_id=current_user.id, chat_room_id=chat_room_id)
    db.add(new_membership)
    db.commit()
    logger.info(f"User {current_user.username} joined chat room {chat_room_id} successfully")
    return {"message": "Joined chat room successfully"}

# Endpoint to list chat rooms
@app.get("/chat_rooms/", response_model=List[schemas.ChatRoom])
def list_chat_rooms(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    logger.debug(f"User {current_user.username} is listing chat rooms")
    chat_rooms = db.query(models.ChatRoom).all()
    logger.debug(f"Found {len(chat_rooms)} chat rooms")
    return chat_rooms

# Endpoint to search messages
@app.get("/chat_rooms/{chat_room_id}/search", response_model=List[schemas.Message])
def search_messages(
    chat_room_id: int,
    query: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    logger.debug(f"User {current_user.username} is searching messages in chat room {chat_room_id} with query '{query}'")
    messages = (
        db.query(models.Message)
        .filter(
            models.Message.chat_room_id == chat_room_id,
            models.Message.content.contains(query),
        )
        .all()
    )
    logger.debug(f"Found {len(messages)} messages matching query")
    return messages

# Endpoint to delete a message
@app.delete("/messages/{message_id}")
def delete_message(
    message_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    logger.debug(f"User {current_user.username} is attempting to delete message {message_id}")
    message = db.query(models.Message).filter(models.Message.id == message_id).first()
    if not message:
        logger.error(f"Message not found: ID {message_id}")
        raise HTTPException(status_code=404, detail="Message not found")
    if message.user_id != current_user.id:
        logger.warning(f"User {current_user.username} is not authorized to delete message {message_id}")
        raise HTTPException(status_code=403, detail="Not authorized to delete this message")
    db.delete(message)
    db.commit()
    logger.info(f"Message {message_id} deleted successfully by user {current_user.username}")
    return {"message": "Message deleted successfully"}

# File upload endpoint
@app.post("/upload/")
async def upload_file(
        file: UploadFile = File(...),
        current_user: models.User = Depends(get_current_user),
):
    logger.debug(f"User {current_user.username} is uploading a file")
    try:
        # Validate file type
        if file.content_type not in ["image/png", "image/jpeg", "application/pdf"]:
            logger.warning(f"Unsupported file type: {file.content_type}")
            raise HTTPException(status_code=400, detail="Unsupported file type")

        # Set maximum file size (e.g., 10 MB)
        max_file_size = 10 * 1024 * 1024  # 10 MB in bytes

        # Read the file in chunks to avoid loading the entire file into memory
        file_size = 0
        contents = bytearray()
        while True:
            chunk = await file.read(1024)  # Read in 1 KB chunks
            if not chunk:
                break
            file_size += len(chunk)
            if file_size > max_file_size:
                logger.warning(f"File too large: {file_size} bytes")
                raise HTTPException(status_code=400, detail="File too large")
            contents.extend(chunk)

        # Save the file
        filename = os.path.basename(file.filename)
        file_location = f"uploads/{filename}"
        os.makedirs(os.path.dirname(file_location), exist_ok=True)
        with open(file_location, "wb") as buffer:
            buffer.write(contents)

        logger.info(f"File uploaded successfully: {filename}")
        return {"file_url": f"/{file_location}"}
    except Exception as e:
        logger.error(f"File upload error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")

# WebSocket endpoint
@app.websocket("/ws/{chat_room_id}")
async def websocket_endpoint(websocket: WebSocket, chat_room_id: int, token: str = Query(...)):
    logger.debug(f"WebSocket connection attempt to chat room {chat_room_id} with token {token}")
    await websocket.accept()
    db = SessionLocal()
    try:
        # Authenticate user from token
        current_user = get_current_user_from_token(token, db)
        logger.info(f"User {current_user.username} connected to chat room {chat_room_id}")

        # Check if user is a member of the chat room
        membership = (
            db.query(models.Membership)
            .filter_by(user_id=current_user.id, chat_room_id=chat_room_id)
            .first()
        )
        if not membership:
            logger.warning(f"User {current_user.username} is not a member of chat room {chat_room_id}")
            await websocket.close(code=1008, reason="Not a member of the chat room")
            return

        # Use Redis client from app.state
        redis_client = app.state.redis_client

        # Subscribe to Redis channel
        redis_channel = f"chat_room_{chat_room_id}"
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(redis_channel)
        logger.debug(f"Subscribed to Redis channel: {redis_channel}")

        async def send_messages():
            try:
                while True:
                    message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                    if message:
                        data = json.loads(message['data'])
                        logger.debug(f"Received message from Redis: {data}")
                        await websocket.send_json(data)
                    await asyncio.sleep(0.01)  # Prevent tight loop
            except Exception as e:
                logger.error(f"Error in send_messages task: {e}", exc_info=True)

        send_task = asyncio.create_task(send_messages())

        try:
            while True:
                data = await websocket.receive_json()
                logger.debug(f"Received data from client: {data}")
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
                    logger.info(f"Message saved to database: {message.id}")
                    msg = {
                        "type": "chat",
                        "content": content,
                        "username": current_user.username,
                        "is_attachment": is_attachment,
                        "message_id": message.id,
                    }
                    # Publish the message to Redis
                    await redis_client.publish(redis_channel, json.dumps(msg))
                    logger.debug(f"Published message to Redis channel {redis_channel}: {msg}")
                    # Send the message back to the sender
                    await websocket.send_json(msg)
                elif message_type == "typing":
                    # Broadcast typing indicator
                    msg = {"type": "typing", "username": current_user.username}
                    await redis_client.publish(redis_channel, json.dumps(msg))
                    logger.debug(f"Published typing indicator to Redis channel {redis_channel}: {msg}")
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
                    logger.debug(f"Published reaction to Redis channel {redis_channel}: {msg}")
                elif message_type == "read_receipt":
                    # Handle read receipts
                    message_id = data.get("message_id")
                    read_status = models.MessageReadStatus(
                        user_id=current_user.id, message_id=message_id
                    )
                    db.merge(read_status)
                    db.commit()
                    logger.debug(f"Read receipt saved for message {message_id} by user {current_user.username}")
                    # Optionally notify the sender
                # Add handling for other message types if needed
        except WebSocketDisconnect:
            logger.info(f"Client {current_user.username} disconnected from chat room {chat_room_id}")
            send_task.cancel()
            await pubsub.unsubscribe(redis_channel)
        except Exception as e:
            logger.error(f"Error during WebSocket communication: {e}", exc_info=True)
            send_task.cancel()
            await pubsub.unsubscribe(redis_channel)
            await websocket.close()
        finally:
            logger.debug(f"WebSocket connection closed for user {current_user.username}")
    except HTTPException as e:
        logger.error(f"Authentication failed: {e.detail}")
        await websocket.close(code=1008, reason=e.detail)
    except Exception as e:
        logger.error(f"Error during WebSocket connection setup: {e}", exc_info=True)
        await websocket.close()
    finally:
        db.close()
        logger.debug("Database session closed")
