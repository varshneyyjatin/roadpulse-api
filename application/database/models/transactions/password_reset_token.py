from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Integer, func
from sqlalchemy.orm import relationship
from ...base import Base, get_table_args, get_fk_name

class TrnPasswordResetToken(Base):
    """
    Password reset token table for forgot password functionality.
    Stores one-time use tokens with expiry for secure password resets.
    """
    __tablename__ = "trn_password_reset_tokens"
    __table_args__ = get_table_args()
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey(get_fk_name("mst_users", "id"), ondelete="CASCADE"), 
                     nullable=False, index=True)
    token = Column(String(255), unique=True, nullable=False, index=True)
    is_used = Column(Boolean, default=False, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    
    # Relationship
    user = relationship("MstUser")
