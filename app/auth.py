import os
import logging
from datetime import datetime, timedelta
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from . import models
from .database import SessionLocal

logger = logging.getLogger(__name__)

SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60  # Increased expiration time for testing

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")

def authenticate_user(db: Session, username: str, password: str):
    logger.debug(f"Authenticating user: {username}")
    user = db.query(models.User).filter(models.User.username == username).first()
    if user and user.verify_password(password):
        logger.debug(f"Authentication successful for user: {username}")
        return user
    logger.warning(f"Authentication failed for user: {username}")
    return None

def create_access_token(data: dict, expires_delta: timedelta = None):
    logger.debug(f"Creating access token for data: {data}")
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    logger.debug(f"Access token created: {token}")
    return token

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(SessionLocal)):
    credentials_exception = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    try:
        logger.debug(f"Decoding token: {token}")
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        logger.debug(f"Extracted username from token: {username}")
        if username is None:
            logger.error("Username not found in token")
            raise credentials_exception
    except JWTError as e:
        logger.error(f"JWTError during token decoding: {e}")
        raise credentials_exception
    user = db.query(models.User).filter(models.User.username == username).first()
    if user is None:
        logger.error(f"User not found: {username}")
        raise credentials_exception
    logger.debug(f"User retrieved from token: {user.username}")
    return user

def get_current_user_from_token(token: str, db: Session):
    credentials_exception = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    try:
        logger.debug(f"Decoding token for WebSocket: {token}")
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        logger.debug(f"Extracted username from token for WebSocket: {username}")
        if username is None:
            logger.error("Username not found in token for WebSocket")
            raise credentials_exception
    except JWTError as e:
        logger.error(f"JWTError during token decoding for WebSocket: {e}")
        raise credentials_exception
    user = db.query(models.User).filter(models.User.username == username).first()
    if user is None:
        logger.error(f"User not found from token in WebSocket: {username}")
        raise credentials_exception
    logger.debug(f"User retrieved from token for WebSocket: {user.username}")
    return user
