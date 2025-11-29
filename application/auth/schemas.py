"""
Pydantic schemas for authentication.
"""
from pydantic import BaseModel
from typing import Optional

class UserLogin(BaseModel):
    """User login request schema - supports email or username."""
    username: Optional[str] = None
    email: Optional[str] = None
    password: str

class TokenResponse(BaseModel):
    """JWT token response schema."""
    access_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    """Token payload data."""
    user_id: int
    username: str
    name: str
    email: Optional[str]
    role: str
    company_id: int
