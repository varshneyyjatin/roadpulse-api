from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, String, Text, 
    func, Index, UniqueConstraint, DECIMAL, SmallInteger, Integer
)
from sqlalchemy.orm import relationship
from ..base import Base, get_table_args

class MstVehicle(Base):
    """
    Vehicle master table with enhanced tracking.
    Central registry for all vehicles detected by the ANPR system.
    """
    __tablename__ = "mst_vehicles"  
    __table_args__ = get_table_args()                                
    
    vehicle_id = Column(Integer, primary_key=True, autoincrement=True)
    plate_number = Column(String(20), unique=True, nullable=False, index=True)                        
    vehicle_type = Column(String(50), nullable=True, index=True)                                
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    disabled = Column(Boolean, default=False, nullable=False, index=True)
    
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)
    deleted_at = Column(DateTime, nullable=True)
    deleted_by = Column(String(50), nullable=True) 

    # Relationships
    logs = relationship("TrnVehicleLog", back_populates="vehicle")
    alerts = relationship("MstAlert", back_populates="vehicle")
    watchlist = relationship("MstWatchlist", back_populates="vehicle")