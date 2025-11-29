from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, String, Text, 
    func, Index, UniqueConstraint, DECIMAL, SmallInteger, Integer
)
from sqlalchemy.orm import relationship
from ..base import Base, get_table_args, get_fk_name


class MstLocation(Base):
    """
    Location master table - Warehouses, stores, facilities.
    Defines physical sites where ANPR systems are deployed.
    """
    __tablename__ = "mst_locations"          
    __table_args__ = get_table_args()                   

    location_id = Column(Integer, primary_key=True, autoincrement=True)                               
    company_id = Column(Integer, ForeignKey(get_fk_name("mst_company", "id"), ondelete="RESTRICT"),   index=True, nullable=False)
    location_name = Column(String(200), nullable=False, index=True)
    location_code = Column(String, unique=True, nullable=True, index=True)                          
    location_type = Column(String(50), nullable=False, index=True)
    location_address = Column(String(255),nullable=True)                                       
    contact_person_name = Column(String(100), nullable=True)                                                
    contact_person_phone = Column(String(15), nullable=True)                                            
    disabled = Column(Boolean, default=False, nullable=False, index=True)
    
    created_by = Column(String(50), nullable=False)
    updated_by = Column(String(50), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)
    deleted_at = Column(DateTime, nullable=True)
    deleted_by = Column(String(50), nullable=True)

    # Relationships
    company = relationship("MstCompany", back_populates="locations")
    checkpoint = relationship("MstCheckpoint", back_populates="location")
    cameras = relationship("MstCamera", back_populates="location")
    compute_boxes = relationship("MstComputeBox", back_populates="location")
    notifications = relationship("MstNotification", back_populates="location")