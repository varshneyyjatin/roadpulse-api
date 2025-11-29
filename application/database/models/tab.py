from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, String, Text, 
    func, Index, UniqueConstraint, Integer
)
from sqlalchemy.orm import relationship
from ..base import Base, get_table_args


class MstTab(Base):
    """
    Master table for application tabs/modules.
    Defines main navigation tabs in the application.
    """
    __tablename__ = "mst_tabs"
    __table_args__ = get_table_args()
    
    tab_id = Column(Integer, primary_key=True, autoincrement=True)
    tab_name = Column(String(100), nullable=False, index=True)
    tab_description = Column(String(255), nullable=True)
    display_order = Column(Integer, default=0, nullable=False)
    disabled = Column(Boolean, default=False, nullable=False, index=True)
    created_by = Column(String(50), nullable=False)
    updated_by = Column(String(50), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)
    deleted_at = Column(DateTime, nullable=True)
    deleted_by = Column(String(50), nullable=True)
    
    # Relationships
    components = relationship("MstComponent", back_populates="tab")