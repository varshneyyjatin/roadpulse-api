from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, String, Text, 
    func, Index, UniqueConstraint, DECIMAL, SmallInteger, Integer
)
from sqlalchemy.orm import relationship
from ...base import Base, get_table_args, get_fk_name


# class MstComputeDevice(Base):
#     """
#     Compute device specifications inside a Compute Box.
#     Detailed hardware inventory and performance monitoring for edge devices.
#     """
#     __tablename__ = "mst_compute_device"
#     __table_args__ = (
#         Index("ix_device_box", "box_id"),
#     )
    
#     id = Column(Integer, primary_key=True, autoincrement=True)
#     box_id = Column(Integer, ForeignKey("mst_compute_box.box_id", ondelete="RESTRICT"),             #string to integer
#                    nullable=False, index=True)
#     device_name = Column(String(200))
#     device_type = Column(String(50))
#     product_id = Column(String(100))
#     os_name = Column(String(50))
#     os_version = Column(String(50))
#     total_space_gb = Column(Integer)
#     is_active = Column(Boolean, default=True, nullable=False, index=True)
#     created_by = Column(String(50), nullable=False)
#     updated_by = Column(String(50), nullable=False)
#     created_at = Column(DateTime, server_default=func.now(), nullable=False)
#     updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

#     compute_box = relationship("MstComputeBox", back_populates="compute_devices")
class TrnDeviceHealth(Base):
    """
    Health check records for both compute boxes and cameras.
    Tracks status, heartbeat, and performance metrics over time.
    """
    __tablename__ = "trn_device_health"
    __table_args__ = get_table_args()
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    camera_id = Column(Integer, ForeignKey(get_fk_name("mst_camera", "camera_id"), ondelete="RESTRICT"), nullable=True, index=True)
    compute_box_id = Column(Integer, ForeignKey(get_fk_name("mst_compute_box", "box_id"), ondelete="RESTRICT"), nullable=True, index=True)

    is_online = Column(Boolean, default=False, nullable=False, index=True)
    status = Column(String(50), nullable=False, default="Unknown")  
    cpu_usage = Column(DECIMAL(5, 2), nullable=True)                
    memory_usage = Column(DECIMAL(5, 2), nullable=True)            
    disk_usage = Column(DECIMAL(5, 2), nullable=True)             
    error_message = Column(String(255), nullable=True)

    checked_at = Column(DateTime, server_default=func.now(), nullable=False)
    created_by = Column(String(50), nullable=False)
    updated_by = Column(String(50), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    compute_box = relationship("MstComputeBox", back_populates="device_health") 
    cameras = relationship("MstCamera", back_populates="device_health")
