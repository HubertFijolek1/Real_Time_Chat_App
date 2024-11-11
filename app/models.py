from .database import Base
from passlib.context import CryptContext
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, func, Boolean
from sqlalchemy.orm import relationship

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)

    # Relationships (to be defined later)
    messages = relationship("Message", back_populates="user")
    memberships = relationship("Membership", back_populates="user")


    def set_password(self, password):
        self.password_hash = pwd_context.hash(password)

    def verify_password(self, password):
        return pwd_context.verify(password, self.password_hash)


class Message(Base):
    __tablename__ = 'messages'

    id = Column(Integer, primary_key=True, index=True)
    content = Column(String, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    user_id = Column(Integer, ForeignKey('users.id'))
    chat_room_id = Column(Integer, ForeignKey('chat_rooms.id'))

    user = relationship("User", back_populates="messages")
    chat_room = relationship("ChatRoom", back_populates="messages")

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