"""Schemas for watchlist API."""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class WatchlistResponse(BaseModel):
    id: int
    vehicle_id: int
    plate_number: str
    company_id: int
    reason: str
    date_added: datetime
    date_removed: Optional[datetime]
    added_by: str
    removed_by: Optional[str]
    is_blacklisted: Optional[bool]
    is_whitelisted: Optional[bool]
    disabled: bool
    
    class Config:
        from_attributes = True

class AddWatchlistRequest(BaseModel):
    vehicle_id: Optional[int] = Field(default=None, description="Vehicle ID (provide either vehicle_id or plate_number)")
    plate_number: Optional[str] = Field(default=None, min_length=1, max_length=20, description="Vehicle plate number (provide either vehicle_id or plate_number)")
    reason: str = Field(..., min_length=1, max_length=500, description="Reason for adding to watchlist")
    is_blacklisted: bool = Field(default=False, description="Mark as blacklisted")
    is_whitelisted: bool = Field(default=False, description="Mark as whitelisted")