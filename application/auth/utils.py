"""
Authentication utilities for internal APIs and JWT token management.
"""
from datetime import datetime, timedelta
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials, HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
import secrets
import bcrypt
import jwt
from config import EDGE_API_USERNAME, EDGE_API_PASSWORD, JWT_SECRET_KEY, JWT_ALGORITHM, JWT_ACCESS_TOKEN_EXPIRE_MINUTES
from application.helpers.logger import get_logger
from application.database.session import get_db
from application.auth import crud
from application.auth.schemas import TokenData

logger = get_logger("auth")
security = HTTPBasic()
bearer_scheme = HTTPBearer()

def verify_basic_auth(credentials: HTTPBasicCredentials = Depends(security)) -> str:
    """Verify basic authentication credentials for internal APIs."""
    correct_username = secrets.compare_digest(credentials.username, EDGE_API_USERNAME)
    correct_password = secrets.compare_digest(credentials.password, EDGE_API_PASSWORD)
    
    if not (correct_username and correct_password):
        logger.error(f"Auth Failed :: Username -> {credentials.username} :: Invalid credentials")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    
    return credentials.username

def hash_password(password: str) -> str:
    """Hash password using bcrypt."""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against bcrypt hash."""
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token."""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "iat": datetime.utcnow()})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    
    return encoded_jwt

def decode_access_token(token: str) -> Optional[dict]:
    """Decode and verify JWT token."""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("Token Verification Failed :: Token expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired. Please login again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        logger.warning("Token Verification Failed :: Invalid token")
        return None

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db)
) -> TokenData:
    """Get current authenticated user from JWT token - dependency for protected routes."""
    token = credentials.credentials
    
    try:
        payload = decode_access_token(token)
    except HTTPException:
        # Re-raise the exception from decode_access_token (session expired)
        raise
    
    if payload is None:
        logger.error("Auth Failed :: Invalid token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token. Please login again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id: int = payload.get("user_id")
    if user_id is None:
        logger.error("Auth Failed :: Token missing user_id")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = crud.get_user_by_id(db, user_id)
    if user is None:
        logger.error(f"Auth Failed :: User not found :: UserID -> {user_id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if user.disabled:
        logger.error(f"Auth Failed :: User disabled :: UserID -> {user_id} :: Email -> {user.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is disabled",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return TokenData(
        user_id=user.id,
        username=user.username,
        name=user.name,
        email=user.email,
        role=user.role,
        company_id=user.company_id
    )
