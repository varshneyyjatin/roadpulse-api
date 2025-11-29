from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, String, Text, 
    func, Index, UniqueConstraint, DECIMAL, SmallInteger, Integer
)
from sqlalchemy.orm import relationship
from ..base import Base, get_table_args, get_fk_name

class MstComponent(Base):
    """
    Component master table for UI components/features.
    Defines available ANPR system capabilities and premium features.
    Components are the smallest unit of access control (buttons, widgets, sections).
    Each component belongs to a specific tab.
    """
    __tablename__ = "mst_components"      
    __table_args__ = get_table_args(
        Index('idx_tab_component', 'tab_id', 'component_id')
    )
    
    component_id = Column(Integer, primary_key=True, autoincrement=True)
    tab_id = Column(Integer, ForeignKey(get_fk_name("mst_tabs", "tab_id"), ondelete="CASCADE"), nullable=False, index=True)# Which tab does this component belong to
    component_name = Column(String(200), nullable=False, index=True)
    component_code = Column(String(50), unique=True, nullable=False) # Example: "LIVE_VIEW", "VEHICLE_COUNT_WIDGET", "EXPORT_BUTTON"
    component_description = Column(String(255), nullable=True)
    component_type = Column(String(50), nullable=True)
    # Example: "widget", "button", "section", "page"
    
    created_by = Column(String(50), nullable=False)
    updated_by = Column(String(50), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    disabled = Column(Boolean, default=False, nullable=False, index=True)
    
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)
    deleted_at = Column(DateTime, nullable=True)
    deleted_by = Column(String(50), nullable=True)

    # Relationships
    tab = relationship("MstTab", back_populates="components")
    global_launches = relationship("TrnGlobalLaunch", back_populates="component")
