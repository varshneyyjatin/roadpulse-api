from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, String, Text, 
    func, Index, UniqueConstraint, DECIMAL, SmallInteger, Integer
)
from sqlalchemy.orm import relationship
from ..base import Base, get_table_args, get_fk_name


class MstCheckpoint(Base):
    """
    Checkpoint master: Entry/Exit gates and intermediate checkpoints.
    Defines physical locations where vehicle detection occurs within a facility.
    """
    __tablename__ = "mst_checkpoints"                       
    __table_args__ = get_table_args(
        Index("ix_checkpoint_location_type", "location_id", "checkpoint_type"),
        Index("ix_checkpoint_disabled", "disabled")
    )
    
    checkpoint_id = Column(Integer, primary_key=True, autoincrement=True)
    location_id = Column(Integer, ForeignKey(get_fk_name("mst_locations", "location_id"), ondelete="RESTRICT"), 
                          nullable=False, index=True)
    latitude = Column(DECIMAL(10, 8), nullable=True)
    longitude = Column(DECIMAL(11, 8), nullable=True)
    name = Column(String(200), nullable=False)
    checkpoint_type = Column(String(20), nullable=False)                  
    direction = Column(String(10))
    sequence_order = Column(SmallInteger)                                                 
    disabled = Column(Boolean, default=False, nullable=False, index=True)                
    created_by = Column(String(50), nullable=False)
    updated_by = Column(String(50), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)
    deleted_at = Column(DateTime, nullable=True)
    deleted_by = Column(String(50), nullable=True) 

    # Relationships
    location = relationship("MstLocation", back_populates="checkpoint")
    cameras = relationship("MstCamera", back_populates="checkpoint")
    alerts = relationship("MstAlert", back_populates="checkpoint")

