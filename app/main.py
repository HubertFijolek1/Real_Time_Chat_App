import os
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect,Depends, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
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
async def websocket_endpoint(websocket: WebSocket):
    """
    Handle WebSocket connections for real-time chat.

    Args:
        websocket (WebSocket): The WebSocket connection instance.

    Handles:
        - Connection acceptance
        - Sending last 50 messages from Redis
        - Receiving and broadcasting new messages
        - Graceful disconnection handling
    """
    await manager.connect(websocket)
    logger.info("Client connected")
    try:
        # Retrieve and send the last 50 chat messages from Redis
        messages = redis_client.lrange("chat_messages", -50, -1)
        for message in messages:
            await websocket.send_text(message)

        while True:
            # Receive a new message from the client
            data = await websocket.receive_text()
            if not data.strip():
                # Inform the client about empty messages
                await websocket.send_text("Error: Empty messages are not allowed.")
                continue

            logger.info(f"Received message: {data}")
            # Store the message in Redis
            redis_client.rpush("chat_messages", data)
            # Trim the list to the last 50 messages
            redis_client.ltrim("chat_messages", -50, -1)
            # Broadcast the message to all connected clients
            await manager.broadcast(data)
    except WebSocketDisconnect:
        # Handle client disconnection
        manager.disconnect(websocket)
        logger.info("Client disconnected")
        await manager.broadcast("A user has left the chat.")
    except Exception as e:
        # Handle unexpected exceptions
        logger.error(f"Unexpected error: {e}")
        manager.disconnect(websocket)


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