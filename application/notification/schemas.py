"""Schemas for notification API."""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class NotificationTypeEnum(str, Enum):
    blacklist_alert = "blacklist_alert"
    whitelist_alert = "whitelist_alert"
    feature_launch = "feature_launch"
    system_alert = "system_alert"
    watchlist_change = "watchlist_change"


class PriorityEnum(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class CreateNotificationRequest(BaseModel):
    user_id: Optional[int] = Field(default=None, description="Specific user ID (null for broadcast)")
    company_id: Optional[int] = Field(default=None, description="Company ID")
    location_id: Optional[int] = Field(default=None, description="Location ID")
    notification_type: NotificationTypeEnum = Field(..., description="Type of notification")
    title: str = Field(..., min_length=1, max_length=200, description="Notification title")
    message: str = Field(..., min_length=1, description="Notification message")
    priority: PriorityEnum = Field(default=PriorityEnum.medium, description="Priority level")
    context_data: Optional[Dict[str, Any]] = Field(default=None, description="Additional context data")
    expires_at: Optional[datetime] = Field(default=None, description="Expiration timestamp")


class NotificationResponse(BaseModel):
    notification_id: int
    user_id: Optional[int]
    company_id: Optional[int]
    location_id: Optional[int]
    notification_type: str
    title: str
    message: str
    priority: str
    context_data: Optional[Dict[str, Any]]
    is_read: bool
    read_at: Optional[datetime]
    created_at: datetime
    expires_at: Optional[datetime]

    class Config:
        from_attributes = True


class MarkAsReadRequest(BaseModel):
    notification_ids: List[int] = Field(..., description="List of notification IDs to mark as read")


class GetNotificationsRequest(BaseModel):
    is_read: Optional[bool] = Field(default=None, description="Filter by read status (null for all)")
    notification_type: Optional[NotificationTypeEnum] = Field(default=None, description="Filter by type")
    limit: int = Field(default=50, ge=1, le=100, description="Maximum number of notifications")
