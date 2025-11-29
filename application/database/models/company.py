from sqlalchemy import (Boolean, Column, DateTime, ForeignKey, String, Text, func, Index, UniqueConstraint, DECIMAL, SmallInteger, Integer)
from sqlalchemy.orm import relationship
from ..base import Base, get_table_args

class MstCompany(Base):
    """
    Company master table - Root entity for multi-tenancy.
    Stores primary company information for system access and billing.
    """
    __tablename__ = "mst_company"
    __table_args__ = get_table_args()

    id = Column(Integer, primary_key=True, autoincrement=True)    
    company_code = Column(String, unique=True, nullable=True, index=True)                          
    name = Column(String(255), nullable=False, index=True)
    logo = Column(String(255), nullable=True)           
    email= Column(String(254), index=True)
    phone = Column(String(15), nullable=True)
    address = Column(String(255), nullable=True)
    data_retention_days = Column(Integer, default=90, nullable=False)
    disabled = Column(Boolean, default=False, nullable=False, index=True)
    created_by = Column(String(50), nullable=False)
    updated_by = Column(String(50), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)
    deleted_at = Column(DateTime, nullable=True)
    deleted_by = Column(String(50), nullable=True)
    
    # Relationships
    locations = relationship("MstLocation", back_populates="company")
    users = relationship("MstUser", back_populates="company")
    drivers = relationship("MstDriver", back_populates="company")
    notifications = relationship("MstNotification", back_populates="company")