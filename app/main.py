from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from . import redis_client

app = FastAPI()

app.mount("/static", StaticFiles(directory="../frontend"), name="static")

@app.get("/", response_class=HTMLResponse)
def read_root():
    with open("../frontend/index.html") as f:
        return f.read()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    # Send last 50 messages
    messages = redis_client.lrange("chat_messages", -50, -1)
    for message in messages:
        await websocket.send_text(message)
    while True:
        data = await websocket.receive_text()
        redis_client.rpush("chat_messages", data)
        redis_client.ltrim("chat_messages", -50, -1)
        await websocket.send_text(data)