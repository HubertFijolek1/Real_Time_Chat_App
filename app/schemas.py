from pydantic import BaseModel
from datetime import datetime

class UserBase(BaseModel):
    username: str

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: int

    class Config:
        orm_mode = True

class Token(BaseModel):
    access_token: str
    token_type: str

class ChatRoomBase(BaseModel):
    name: str
    is_private: bool = False

class ChatRoomCreate(ChatRoomBase):
    pass

class ChatRoom(ChatRoomBase):
    id: int

    class Config:
        orm_mode = True

class MessageBase(BaseModel):
    content: str
    is_attachment: bool = False

class MessageCreate(MessageBase):
    pass

class Message(MessageBase):
    id: int
    timestamp: datetime
    user_id: int
    chat_room_id: int

    class Config:
        orm_mode = True

class ReactionBase(BaseModel):
    reaction_type: str

class ReactionCreate(ReactionBase):
    message_id: int

class Reaction(ReactionBase):
    user_id: int
    message_id: int

    class Config:
        orm_mode = True

class MessageReadStatusBase(BaseModel):
    read_at: datetime

class MessageReadStatusCreate(BaseModel):
    message_id: int

class MessageReadStatus(MessageReadStatusBase):
    user_id: int
    message_id: int

    class Config:
        orm_mode = True