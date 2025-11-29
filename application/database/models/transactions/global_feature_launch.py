from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, String, Text, 
    func, Index, Integer
)
from sqlalchemy.orm import relationship
from ...base import Base, get_table_args, get_fk_name

class TrnGlobalLaunch(Base):
    """
    Global component launch configuration.
    Allows launching new components to all users for a specific time period.
    After the period ends, component access is locked/removed automatically.
    """
    __tablename__ = "trn_global_launch"
    __table_args__ = get_table_args(
        Index('idx_component_launch_dates', 'component_id', 'launch_from', 'launch_until')
    )
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # ========== LAUNCH SCOPE ==========
    launch_scope = Column(String(20), nullable=False, index=True)
    # Values: 'tab', 'component'
    
    tab_id = Column(Integer, ForeignKey(get_fk_name("mst_tabs", "tab_id"), ondelete="CASCADE"), nullable=True, index=True)
    # If launch_scope='tab', launch entire tab
    
    component_id = Column(Integer, ForeignKey(get_fk_name("mst_components", "component_id"), ondelete="CASCADE"), nullable=True, index=True)
    # If launch_scope='component', launch specific component
    
    launch_name = Column(String(200), nullable=False) # Example: "Q1 2024 AI Analytics Beta Launch"
    launch_description = Column(Text, nullable=True) # Detailed description of the launch
    launch_message = Column(Text, nullable=True) # Message to show users: "🎉 New AI Analytics feature is now available!"
    launch_from = Column(DateTime, nullable=False, index=True)# Feature becomes available from this date
    launch_until = Column(DateTime, nullable=True, index=True) # Feature locks/expires after this date (null = permanent)
    target_scope = Column(String(20), nullable=False, default='all') # Values: 'all', 'company', 'location', 'role'
    target_scope_ids = Column(Text, nullable=True) # JSON array of IDs: "[1,2,3]" for company_ids, location_ids, etc. # null if target_scope='all'
    post_launch_action = Column(String(20), nullable=False, default='lock') # Values: 'lock' (disable access), 'keep' (keep access), 'ask' (ask users to subscribe)
    disabled = Column(Boolean, default=False, nullable=False, index=True)
    launch_status = Column(String(20), nullable=False, default='scheduled', index=True)# Values: 'scheduled', 'active', 'completed', 'cancelled'
    context_data = Column(Text, nullable=True)

    created_by = Column(String(50), nullable=False)
    updated_by = Column(String(50), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    tab = relationship("MstTab", foreign_keys=[tab_id])
    component = relationship("MstComponent", foreign_keys=[component_id], back_populates="global_launches")