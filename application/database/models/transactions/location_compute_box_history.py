from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, String, Integer, func, Index
)
from sqlalchemy.orm import relationship
from ...base import Base, get_table_args, get_fk_name


class TrnComputeBoxLocationHistory(Base):
    """
    History table to track compute box assignments and movements across locations.
    Maintains full audit trail for device deployment and relocation.
    """
    __tablename__ = "trn_compute_box_location_history"
    __table_args__ = get_table_args()

    id = Column(Integer, primary_key=True, autoincrement=True)
    
    box_id = Column(Integer, ForeignKey(get_fk_name("mst_compute_box", "box_id"), ondelete="RESTRICT"), nullable=False, index=True)
    old_location_id = Column(Integer, ForeignKey(get_fk_name("mst_locations", "location_id"), ondelete="RESTRICT"), nullable=True, index= True)
    new_location_id = Column(Integer, ForeignKey(get_fk_name("mst_locations", "location_id"), ondelete="RESTRICT"), nullable=False, index= True)    
    active_from = Column(DateTime, default=func.now(), nullable=False)
    active_till = Column(DateTime, nullable=True)
    disabled = Column(Boolean, default=False, nullable=False, index=True)
    created_by = Column(String(50), nullable=False)
    updated_by = Column(String(50), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)
    deleted_at = Column(DateTime, nullable=True)
    deleted_by = Column(String(50), nullable=True)


    # Relationships
    compute_box = relationship("MstComputeBox", back_populates="location_history")
