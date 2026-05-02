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

# Password Reset Token Operations
from application.database.models.transactions.password_reset_token import TrnPasswordResetToken
from datetime import datetime, timedelta
import secrets

def create_password_reset_token(db: Session, user_id: int, expiry_hours: int = 1) -> TrnPasswordResetToken:
    """Create a new password reset token for user."""
    token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(hours=expiry_hours)
    
    db_token = TrnPasswordResetToken(
        user_id=user_id,
        token=token,
        expires_at=expires_at
    )
    db.add(db_token)
    db.commit()
    db.refresh(db_token)
    return db_token

def get_valid_reset_token(db: Session, token: str) -> Optional[TrnPasswordResetToken]:
    """Get valid (not used, not expired) reset token."""
    return db.query(TrnPasswordResetToken).filter(
        TrnPasswordResetToken.token == token,
        TrnPasswordResetToken.is_used == False,
        TrnPasswordResetToken.expires_at > datetime.utcnow()
    ).first()

def mark_token_as_used(db: Session, token_id: int):
    """Mark reset token as used."""
    db.query(TrnPasswordResetToken).filter(
        TrnPasswordResetToken.id == token_id
    ).update({"is_used": True})
    db.commit()

def delete_user_old_tokens(db: Session, user_id: int):
    """Delete all old tokens for a user (cleanup before creating new)."""
    db.query(TrnPasswordResetToken).filter(
        TrnPasswordResetToken.user_id == user_id
    ).delete()
    db.commit()
