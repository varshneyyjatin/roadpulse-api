from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, String, Text, 
    func, Index, UniqueConstraint, DECIMAL, SmallInteger, Integer, JSON
)
from sqlalchemy.orm import relationship
from ..base import Base, get_table_args, get_fk_name


class MstWatchlist(Base):
    """
    Blacklisted vehicle audit table with reason tracking.
    Maintains history of vehicles flagged for security or compliance violations.
    """
    __tablename__ = "mst_watchlist"
    __table_args__ = get_table_args()
    
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    vehicle_id = Column(Integer, ForeignKey(get_fk_name("mst_vehicles", "vehicle_id"), ondelete="RESTRICT"), nullable=False, index=True)
    company_id = Column(Integer, nullable=False, index=True)
    reason = Column(String(500), nullable=False)                                               
    disabled = Column(Boolean, default=False, nullable=False, index=True)                      
    is_blacklisted = Column(Boolean, default=False, nullable=True, index = True)
    is_whitelisted = Column(Boolean, default=True, nullable=True, index = True)
    operation_data = Column(JSON, nullable=True)
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)
    deleted_at = Column(DateTime, nullable=True)
    deleted_by = Column(String(50), nullable=True)

    # Relationships
    vehicle = relationship("MstVehicle", back_populates="watchlist")
