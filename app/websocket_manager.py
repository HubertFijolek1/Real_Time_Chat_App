from fastapi import WebSocket
from typing import List, Dict
from collections import defaultdict

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[WebSocket, str] = {}
        self.chat_rooms: defaultdict = defaultdict(set)

    async def connect(self, websocket: WebSocket, username: str, chat_room_id: int):
        self.active_connections[websocket] = username
        self.chat_rooms[chat_room_id].add(websocket)

    def disconnect(self, websocket: WebSocket):
        username = self.active_connections.pop(websocket, None)
        for chat_room in self.chat_rooms.values():
            chat_room.discard(websocket)

    async def broadcast(self, message: str, chat_room_id: int):
        for connection in self.chat_rooms[chat_room_id]:
            await connection.send_text(message)

# Instantiate a single ConnectionManager to be used across the application
manager = ConnectionManager()