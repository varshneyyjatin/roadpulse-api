from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, String, Text, 
    func, Index, Integer, JSON
)
from sqlalchemy.orm import relationship
from ..base import Base, get_table_args, get_fk_name


class MstNotification(Base):
    """
    Notification master table for system-wide and user-specific notifications.
    Tracks feature launches, watchlist changes, alerts, and other important events.
    
    Read Status Tracking:
    - Individual user read status is tracked in TrnNotificationTracker table
    - This allows multiple users to have different read states for the same notification
    """
    __tablename__ = "mst_notifications"
    __table_args__ = get_table_args(
        Index('idx_notification_user_created', 'user_id', 'created_at'),
        Index('idx_notification_type_created', 'notification_type', 'created_at'),
        Index('idx_notification_company', 'company_id', 'created_at'),
        Index('idx_notification_priority', 'priority', 'created_at')
    )
    
    notification_id = Column(Integer, primary_key=True, autoincrement=True)
    
    user_id = Column(Integer, ForeignKey(get_fk_name("mst_users", "id"), ondelete="CASCADE"), 
nullable=True, index=True)
    company_id = Column(Integer, ForeignKey(get_fk_name("mst_company", "id"), ondelete="CASCADE"), 
nullable=True, index=True)
    location_id = Column(Integer, ForeignKey(get_fk_name("mst_locations", "location_id"), ondelete="SET NULL"), nullable=True, index=True)   
    notification_type = Column(String(50), nullable=False, index=True)
    
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    
    priority = Column(String(20), default='medium', nullable=False, index=True)
    context_data = Column(JSON, nullable=True)
    
    expires_at = Column(DateTime, nullable=True, index=True)

    disabled = Column(Boolean, default=False, nullable=False, index=True)
    created_by = Column(String(50), nullable=False)
    updated_by = Column(String(50), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)
    deleted_at = Column(DateTime, nullable=True)
    deleted_by = Column(String(50), nullable=True)
    
    user = relationship("MstUser", foreign_keys=[user_id], back_populates="notifications")
    company = relationship("MstCompany", foreign_keys=[company_id], back_populates="notifications")
    location = relationship("MstLocation", foreign_keys=[location_id], back_populates="notifications")
    read_statuses = relationship("TrnNotificationTracker", back_populates="notification", cascade="all, delete-orphan")