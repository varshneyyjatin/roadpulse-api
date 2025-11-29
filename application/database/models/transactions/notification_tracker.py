from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, func, Index, UniqueConstraint
)
from sqlalchemy.orm import relationship
from ...base import Base, get_table_args, get_fk_name

class TrnNotificationTracker(Base):
    """
    Tracks which users have read which notifications.
    Supports both targeted and broadcast notifications.
    
    For targeted notifications (user_id is set in MstNotification):
    - One row per notification
    
    For broadcast notifications (user_id is NULL in MstNotification):
    - One row per user who has read the notification
    """
    __tablename__ = "trn_notification_tracker"
    __table_args__ = get_table_args(
        UniqueConstraint('notification_id', 'user_id', name='uq_notification_user'),
        Index('idx_read_status_user', 'user_id', 'is_read'),
        Index('idx_read_status_notification', 'notification_id', 'is_read')
    )
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    notification_id = Column(Integer, ForeignKey(get_fk_name("mst_notifications", "notification_id"), ondelete="CASCADE"), 
                            nullable=False, index=True)
    user_id = Column(Integer, ForeignKey(get_fk_name("mst_users", "id"), ondelete="CASCADE"), 
                     nullable=False, index=True)
    is_read = Column(Boolean, default=False, nullable=False, index=True)
    read_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    notification = relationship("MstNotification", back_populates="read_statuses")
    user = relationship("MstUser", back_populates="notification_read_statuses")