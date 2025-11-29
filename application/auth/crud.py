"""
CRUD operations for authentication.
"""
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional
from application.database.models.user import MstUser

def get_user_by_email(db: Session, email: str) -> Optional[MstUser]:
    """Retrieve user by email address."""
    return db.query(MstUser).filter(MstUser.email == email).first()

def get_user_by_username(db: Session, username: str) -> Optional[MstUser]:
    """Retrieve user by username."""
    return db.query(MstUser).filter(MstUser.username == username).first()

def get_user_by_email_or_username(db: Session, identifier: str) -> Optional[MstUser]:
    """Retrieve user by email or username."""
    return db.query(MstUser).filter(
        or_(MstUser.email == identifier, MstUser.username == identifier)
    ).first()

def get_user_by_id(db: Session, user_id: int) -> Optional[MstUser]:
    """Retrieve user by primary key."""
    return db.query(MstUser).filter(MstUser.id == user_id).first()