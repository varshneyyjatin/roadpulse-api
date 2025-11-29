from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, String, Text, 
    func, Index, UniqueConstraint, DECIMAL, SmallInteger, Integer
)
from sqlalchemy.orm import relationship
from ..base import Base, get_table_args, get_fk_name


class MstComputeBox(Base):
    """
    Compute box / edge device at location for distributed processing.
    Manages on-premise hardware devices that run ANPR processing.
    For cloud/hybrid, can represent virtual instances (e.g., AWS EC2 ID in box_id).
    """
    __tablename__ = "mst_compute_box"
    __table_args__ = get_table_args()
    

    box_id = Column(Integer, primary_key=True)    
    location_id = Column(Integer, ForeignKey(get_fk_name("mst_locations", "location_id"), ondelete="SET NULL"), nullable=True, index=True)                                
    box_name = Column(String(200))
    box_type = Column(String(20), nullable=False)
    hardware_model = Column(String(100))
    ip_address = Column(String(45))
    mac_address = Column(String(17))
    installed_on = Column(DateTime, nullable =False)
    last_heartbeat = Column(DateTime , nullable =True)
    disabled = Column(Boolean, default=False, nullable=False, index=True)
    is_online = Column(Boolean, default=False, nullable=False, index=True)
    created_by = Column(String(50), nullable=False)
    updated_by = Column(String(50), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)
    deleted_at = Column(DateTime, nullable=True)
    deleted_by = Column(String(50), nullable=True)

    # Relationships
    location = relationship("MstLocation", back_populates="compute_boxes")
    device_health = relationship("TrnDeviceHealth", back_populates="compute_box")
    cameras = relationship("MstCamera", back_populates="compute_box")
    location_history = relationship("TrnComputeBoxLocationHistory", back_populates="compute_box")
