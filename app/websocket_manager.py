from fastapi import WebSocket
from typing import List

class ConnectionManager:
    """
    Manages active WebSocket connections and facilitates message broadcasting.
    """

    def __init__(self):
        """
        Initialize the ConnectionManager with an empty list of active connections.
        """
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        """
        Accept and register a new WebSocket connection.

        Args:
            websocket (WebSocket): The WebSocket connection to accept and add.
        """
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        """
        Remove a WebSocket connection from the active connections list.

        Args:
            websocket (WebSocket): The WebSocket connection to remove.
        """
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

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