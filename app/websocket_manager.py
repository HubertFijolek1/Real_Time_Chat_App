from fastapi import WebSocket
from typing import List, Dict

class ConnectionManager:
    """
    Manages active WebSocket connections and facilitates message broadcasting.
    """

    def __init__(self):
        self.active_connections: Dict[WebSocket, str] = {}

    async def connect(self, websocket: WebSocket, username: str):
        self.active_connections[websocket] = username

    def disconnect(self, websocket: WebSocket):
        self.active_connections.pop(websocket, None)

    async def broadcast(self, message: str):
        """
        Send a message to all active WebSocket connections.

        Args:
            message (str): The message to broadcast.
        """
        to_remove = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                # Log the error and mark the connection for removal
                print(f"Error sending message: {e}")
                to_remove.append(connection)
        # Remove any connections that encountered errors
        for connection in to_remove:
            self.disconnect(connection)

# Instantiate a single ConnectionManager to be used across the application
manager = ConnectionManager()