from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, String, Text, 
    func, Index, UniqueConstraint, DECIMAL, SmallInteger, Integer
)
from sqlalchemy.orm import relationship
from ..base import Base, get_table_args, get_fk_name

class MstAlert(Base):
    """
    Alert management for security events and violations.
    Tracks security incidents, blacklist violations, and system notifications.
    """
    __tablename__ = "mst_alert"
    __table_args__ = get_table_args(
        Index("ix_alert_vehicle_timestamp", "vehicle_id", "timestamp"),
        Index("ix_alert_checkpoint_status", "checkpoint_id", "status"),
        Index("ix_alert_type_priority", "alert_type", "priority"),
        Index("ix_alert_location_timestamp", "location_id", "timestamp"),
        Index("ix_alert_status_timestamp", "status", "timestamp")
    )
    
    alert_id = Column(Integer, primary_key=True, autoincrement=True)
    vehicle_id = Column(Integer, ForeignKey(get_fk_name("mst_vehicles", "vehicle_id"), ondelete="RESTRICT"), nullable=False)
    checkpoint_id = Column(Integer, ForeignKey(get_fk_name("mst_checkpoints", "checkpoint_id"), ondelete="RESTRICT"), nullable=False, index=True)
    location_id = Column(Integer, nullable=False)
    alert_type = Column(String(50), nullable=False, index=True)
    alert_category = Column(String(30), nullable=False, index=True)
    message = Column(String(500), nullable=True)                                                   
    status = Column(String(20), default="ACTIVE", nullable=False)                    
    priority = Column(String(10), default="MEDIUM", nullable=False)
    timestamp = Column(DateTime, default=func.now(), nullable=False)
    acknowledged_at = Column(DateTime, nullable=True)
    acknowledged_by = Column(String(50),  nullable=True)
    resolved_at = Column(DateTime)
    resolved_by = Column(String(50))
    resolution_notes = Column(String(500), nullable=True) 
    auto_resolved = Column(Boolean, default=False)
    created_by = Column(String(50), nullable=False)
    updated_by = Column(String(50), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)
    deleted_at = Column(DateTime, nullable=True)
    deleted_by = Column(String(50), nullable=True) 

    # Relationships
    vehicle = relationship("MstVehicle", back_populates="alerts")
    checkpoint = relationship("MstCheckpoint", back_populates="alerts")