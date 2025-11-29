from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, String, Text, 
    func, JSON, SmallInteger, Integer
)
from sqlalchemy.orm import relationship
from ..base import Base, get_table_args, get_fk_name

class MstCamera(Base):
    """
    Cameras installed at checkpoints, managed by compute box.
    Physical camera inventory and configuration for ANPR detection.
    For cloud, box_id can be NULL, rtsp_url points to cloud stream.
    """
    __tablename__ = "mst_camera"
    __table_args__ = get_table_args()

    
    camera_id = Column(Integer, primary_key=True, autoincrement=True)                 
    checkpoint_id = Column(Integer, ForeignKey(get_fk_name("mst_checkpoints", "checkpoint_id"), ondelete="SET NULL"), 
                          nullable=True, index=True)
    location_id = Column(Integer, ForeignKey(get_fk_name("mst_locations", "location_id"), ondelete="SET NULL"), 
                          nullable=False, index=True)
    box_id = Column(Integer, ForeignKey(get_fk_name("mst_compute_box", "box_id"), ondelete="SET NULL"), 
                   nullable=True, index=True)
    device_id = Column(String(50), nullable= False, unique = True, index=True)
    camera_name = Column(String(200), nullable=True)
    camera_type = Column(String(50), index=True, nullable=True)
    camera_model = Column(String(100), nullable=True)
    fps = Column(SmallInteger, nullable=True)
    ip_address = Column(String(45), index=True, nullable=True)
    username = Column(String(100), nullable=True)   
    password_hash = Column(String(255), nullable=True)
    roi = Column(JSON, nullable=True) 
    loi = Column(JSON, nullable=True)  
    installed_on = Column(DateTime, nullable=True)
    disabled = Column(Boolean, default=False, nullable=False, index=True)
    remarks = Column(Text, nullable=True)
    created_by = Column(String(50), nullable=False)
    updated_by = Column(String(50), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)
    deleted_at = Column(DateTime, nullable=True)
    deleted_by = Column(String(50), nullable=True) 
    deployment_type = Column(String(50),nullable=False,index=True)

    # Relationships
    checkpoint = relationship("MstCheckpoint", back_populates="cameras") 
    location = relationship("MstLocation", back_populates="cameras") 
    compute_box = relationship("MstComputeBox", back_populates="cameras") 
    device_health = relationship("TrnDeviceHealth", back_populates= "cameras")
