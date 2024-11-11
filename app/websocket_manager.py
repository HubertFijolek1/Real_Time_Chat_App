# app/websocket_manager.py

from fastapi import WebSocket
from typing import Dict, Set, DefaultDict
from collections import defaultdict

class ConnectionManager:
    """
    Manages active WebSocket connections and facilitates message broadcasting.
    """

    def __init__(self):
        """
        Initialize the ConnectionManager with active connections and chat rooms.
        """
        self.active_connections: Dict[WebSocket, str] = {}
        self.chat_rooms: DefaultDict[int, Set[WebSocket]] = defaultdict(set)

    async def connect(self, websocket: WebSocket, username: str, chat_room_id: int):
        """
        Accept and register a new WebSocket connection.
        """
        self.active_connections[websocket] = username
        self.chat_rooms[chat_room_id].add(websocket)

    def disconnect(self, websocket: WebSocket):
        """
        Remove a WebSocket connection from the active connections and chat rooms.
        """
        username = self.active_connections.pop(websocket, None)
        for chat_room in self.chat_rooms.values():
            chat_room.discard(websocket)

    async def broadcast(self, message: dict, chat_room_id: int):
        """
        Send a message to all active WebSocket connections in a chat room.
        """
        for connection in self.chat_rooms[chat_room_id]:
            try:
                await connection.send_json(message)
            except Exception as e:
                print(f"Error sending message: {e}")
                self.disconnect(connection)
