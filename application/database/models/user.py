from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, String, Text, 
    func, Index, UniqueConstraint, DECIMAL, SmallInteger, Integer
)
from sqlalchemy.orm import relationship
from ..base import Base, get_table_args, get_fk_name


class MstUser(Base):
    """
    User master table with role-based hierarchy.
    Manages system access and permissions for location-based operations.
    """
    __tablename__ = "mst_users"       
    __table_args__ = get_table_args()                       
    
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey(get_fk_name("mst_company", "id"), ondelete="RESTRICT"), 
                         nullable=False, index=True)
    name = Column(String(255), nullable=False)
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(254), unique=True, index=True)                                                                           
    phone = Column(String(15), nullable=True)                                                     
    role = Column(String(30), nullable=False)
    last_login = Column(DateTime,  server_default=func.now(), nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    disabled = Column(Boolean, default=False, nullable=False, index=True)
    
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)
    deleted_at = Column(DateTime, nullable=True)
    deleted_by = Column(String(50), nullable=True)                                                     
    created_by = Column(String(50), nullable=False)
    updated_by = Column(String(50), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    company = relationship("MstCompany", back_populates="users")
    user_accesses = relationship("TrnAccessControl", foreign_keys="[TrnAccessControl.user_id]", back_populates="user")
    notifications = relationship("MstNotification", back_populates="user")
    notification_read_statuses = relationship("TrnNotificationTracker", back_populates="user")