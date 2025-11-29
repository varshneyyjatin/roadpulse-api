from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, String, Text, 
    func, Index, UniqueConstraint, DECIMAL, SmallInteger, Integer
)
from sqlalchemy.orm import relationship
from ..base import Base, get_table_args, get_fk_name


class MstDriver(Base):
    """
    Driver master table.
    Stores driver information for vehicle-driver association and compliance tracking.
    """
    __tablename__ = "mst_drivers"
    __table_args__ = get_table_args()
    
    
    driver_id = Column(Integer, primary_key=True, autoincrement=True)                          
    company_id = Column(Integer, ForeignKey(get_fk_name("mst_company", "id"), ondelete="RESTRICT"), 
                         nullable=False, index=True)
    name = Column(String(200), nullable=False, index=True)
    license_number = Column(String(30), unique=True, nullable=True, index=True)
    phone = Column(String(15), nullable=True, index=True)                      
    address = Column(String(255), nullable=True)
    image = Column(String(255), nullable=True)                            
    created_by = Column(String(50), nullable=False)
    updated_by = Column(String(50), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    disabled = Column(Boolean, default=False, nullable=False, index=True)
    
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)
    deleted_at = Column(DateTime, nullable=True)
    deleted_by = Column(String(50), nullable=True) 

    # Relationships
    company = relationship("MstCompany", back_populates="drivers")
    logs = relationship("TrnVehicleLog", back_populates="driver")              
