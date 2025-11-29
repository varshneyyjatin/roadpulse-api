from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, String, Text, 
    func, Index, UniqueConstraint, Integer, Enum
)
from sqlalchemy.orm import relationship
from ...base import Base, get_table_args, get_fk_name

class TrnAccessControl(Base):
    """
    Unified user access control table.
    Manages hierarchical access: Tabs → Components, Locations → Checkpoints
    
    Hierarchy:
    - Tab access: User can see the tab
    - Component access: User can access specific components (component already has tab_id)
    - Location access: User can access specific locations
    - Checkpoint access: User can access specific checkpoints (checkpoint already has location_id)
    
    Supports time-bound component launches and granular permissions.
    """
    __tablename__ = "trn_access_control"
    __table_args__ = get_table_args(
        Index('idx_user_access_type', 'user_id', 'access_type'),
        Index('idx_disabled', 'disabled'),
        Index('idx_tab_access', 'user_id', 'access_type', 'disabled'),
        UniqueConstraint('user_id', 'access_type',
                        name='uq_user_access_type')
    )
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey(get_fk_name("mst_users", "id"), ondelete="CASCADE"), nullable=False, index=True)
    access_type = Column(String(20), nullable=False, index=True) # Values: 'tab', 'component', 'location', 'checkpoint'
    
    # Access data stored as JSON
    # - NULL = ALL (wildcard access to all resources of this type)
    # - JSON array = Specific IDs: {"access_ids": [1, 2, 3]}
    # Examples:
    #   access_type='tab', access_data='{"access_ids": [1, 2, 3]}' → Tabs 1, 2, 3
    #   access_type='tab', access_data=NULL → All tabs
    #   access_type='component', access_data='{"access_ids": [5, 6]}' → Components 5, 6
    access_data = Column(Text, nullable=True)
    
    can_view = Column(Boolean, default=True, nullable=False)
    can_create = Column(Boolean, default=False, nullable=False)
    can_update = Column(Boolean, default=False, nullable=False)
    can_delete = Column(Boolean, default=False, nullable=False)

    disabled = Column(Boolean, default=False, nullable=False, index=True)
    context_data = Column(Text, nullable=True)  # Reserved for future use
    created_by = Column(String(50), nullable=False)
    updated_by = Column(String(50), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)
    deleted_at = Column(DateTime, nullable=True)
    deleted_by = Column(String(50), nullable=True)
    
    # Relationships
    user = relationship("MstUser", foreign_keys=[user_id], back_populates="user_accesses")