import os
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect,Depends, HTTPException, status,Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.security import OAuth2PasswordRequestForm
from .auth import authenticate_user, create_access_token, get_current_user
from . import redis_client, models,schemas
from .websocket_manager import manager
from .database import engine,SessionLocal
from sqlalchemy.orm import Session

models.Base.metadata.create_all(bind=engine)

# Configure logging to track events and errors
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Construct absolute path to the frontend directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "..", "frontend")
FRONTEND_DIR = os.path.abspath(FRONTEND_DIR)  # Ensure it's an absolute path

# Mount the frontend static files to serve them via FastAPI
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

@app.get("/", response_class=HTMLResponse)
def read_root():
    """
    Serve the main HTML page of the chat application.

    Returns:
        HTMLResponse: The content of index.html.
    """
    index_file = os.path.join(FRONTEND_DIR, "index.html")
    try:
        with open(index_file, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        logger.error(f"Index file not found at {index_file}")
        return HTMLResponse(content="Index file not found.", status_code=404)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(...)):
    await websocket.accept()
    try:
        db = SessionLocal()
        current_user = await get_current_user(token=token, db=db)
        await manager.connect(websocket, current_user.username)
        while True:
            data = await websocket.receive_json()
            content = data.get("content")
            chat_room_id = data.get("chat_room_id")
            message = models.Message(content=content, user_id=current_user.id, chat_room_id=chat_room_id)
            db.add(message)
            db.commit()
            await manager.broadcast(message.content, chat_room_id)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        await websocket.close()
    finally:
        db.close()


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

@app.post("/token", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/chat_rooms/", response_model=schemas.ChatRoom)
def create_chat_room(chat_room: schemas.ChatRoomCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
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