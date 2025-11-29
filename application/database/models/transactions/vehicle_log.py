from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, String, Text, 
    func, Index, UniqueConstraint, DECIMAL, SmallInteger, Integer, JSON
)
from sqlalchemy.orm import relationship
from sqlalchemy.ext.mutable import MutableList
from ...base import Base, get_table_args, get_fk_name

class TrnVehicleLog(Base):
    """
    Vehicle detection event logs - Core transaction table.
    Records every vehicle detection event with timestamp, confidence, and associated metadata.
    """
    __tablename__ = "trn_vehicle_log"
    __table_args__ = get_table_args(
        Index("ix_log_vehicle_timestamp", "vehicle_id", "timestamp"),
        Index("ix_log_location_timestamp", "location_id", "timestamp")
    )
    
    log_id = Column(Integer, primary_key=True, autoincrement=True)
    vehicle_id = Column(Integer, ForeignKey(get_fk_name("mst_vehicles", "vehicle_id"), ondelete="RESTRICT"), nullable=False, index=True)
    driver_id = Column(Integer, ForeignKey(get_fk_name("mst_drivers", "driver_id"), ondelete="SET NULL"), nullable=True, index=True)
    location_id = Column(Integer, nullable=False, index=True)
    timestamp = Column(DateTime, default=func.now(), nullable=False, index=True)
    first_seen = Column(DateTime, nullable=True, server_default=func.now())
    last_seen = Column(DateTime, nullable=True, server_default=func.now())
    history_data = Column(MutableList.as_mutable(JSON), nullable=False, server_default='[]')
    latest_data = Column(JSON, nullable=False, server_default='{}')
    is_revised = Column(Boolean, default=False, nullable=False, index=True)
    revised_data = Column(JSON, nullable=True)
    created_by = Column(String(50), nullable=False)
    updated_by = Column(String(50), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    vehicle = relationship("MstVehicle", back_populates="logs")
    driver = relationship("MstDriver", back_populates="logs")