from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    DateTime,
    Boolean,
    func,
)
from sqlalchemy.orm import relationship
from passlib.context import CryptContext
from .database import Base

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)

    messages = relationship("Message", back_populates="user")
    memberships = relationship("Membership", back_populates="user")
    reactions = relationship("Reaction", back_populates="user")
    read_statuses = relationship("MessageReadStatus", back_populates="user")

    def set_password(self, password):
        self.password_hash = pwd_context.hash(password)

    def verify_password(self, password):
        return pwd_context.verify(password, self.password_hash)

class ChatRoom(Base):
    __tablename__ = 'chat_rooms'

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    is_private = Column(Boolean, default=False)

    messages = relationship("Message", back_populates="chat_room")
    memberships = relationship("Membership", back_populates="chat_room")

class Membership(Base):
    __tablename__ = 'memberships'

    user_id = Column(Integer, ForeignKey('users.id'), primary_key=True)
    chat_room_id = Column(Integer, ForeignKey('chat_rooms.id'), primary_key=True)
    joined_at = Column(DateTime, default=func.now())

    user = relationship("User", back_populates="memberships")
    chat_room = relationship("ChatRoom", back_populates="memberships")

class Message(Base):
    __tablename__ = 'messages'

    id = Column(Integer, primary_key=True, index=True)
    content = Column(String, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    user_id = Column(Integer, ForeignKey('users.id'))
    chat_room_id = Column(Integer, ForeignKey('chat_rooms.id'))
    is_attachment = Column(Boolean, default=False)

    user = relationship("User", back_populates="messages")
    chat_room = relationship("ChatRoom", back_populates="messages")
    reactions = relationship("Reaction", back_populates="message")
    read_statuses = relationship("MessageReadStatus", back_populates="message")

class Reaction(Base):
    __tablename__ = 'reactions'

    user_id = Column(Integer, ForeignKey('users.id'), primary_key=True)
    message_id = Column(Integer, ForeignKey('messages.id'), primary_key=True)
    reaction_type = Column(String, nullable=False)

    user = relationship("User", back_populates="reactions")
    message = relationship("Message", back_populates="reactions")

class MessageReadStatus(Base):
    __tablename__ = 'message_read_status'

    user_id = Column(Integer, ForeignKey('users.id'), primary_key=True)
    message_id = Column(Integer, ForeignKey('messages.id'), primary_key=True)
    read_at = Column(DateTime, default=func.now())

    user = relationship("User", back_populates="read_statuses")
    message = relationship("Message", back_populates="read_statuses")