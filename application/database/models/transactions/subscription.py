from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, String, Text, 
    func, Index, UniqueConstraint, DECIMAL, Integer, Date
)
from sqlalchemy.orm import relationship
from ...base import Base, get_table_args, get_fk_name

class TrnSubscription(Base):
    """
    Active subscription management for companies and locations.
    Manages subscription plans, billing, and component access.
    
    Subscription can be at:
    - Company level: All locations under company get access
    - Location level: Only specific location gets access
    """
    __tablename__ = "trn_subscriptions"
    __table_args__ = get_table_args(
        Index('idx_subscription_entity', 'subscription_type', 'entity_id', 'disabled'),
        Index('idx_subscription_dates', 'start_date', 'end_date', 'disabled'),
        Index('idx_payment_status', 'payment_status')
    )
    
    subscription_id = Column(Integer, primary_key=True, autoincrement=True)
    subscription_type = Column(String(20), nullable=False, index=True)
    entity_id = Column(Integer, nullable=False, index=True)
    plan_name = Column(String(100), nullable=False, index=True)
    plan_type = Column(String(20), nullable=False)
    # Values: 'trial', 'monthly', 'quarterly', 'yearly', 'lifetime'
    start_date = Column(Date, nullable=False, index=True)
    end_date = Column(Date, nullable=False, index=True)
    disabled = Column(Boolean, default=False, nullable=False, index=True)
    auto_renew = Column(Boolean, default=False, nullable=False)
    final_amount = Column(DECIMAL(10, 2), nullable=False)
    payment_status = Column(String(20), nullable=False, default='pending', index=True)
    # Values: 'pending', 'paid', 'failed', 'refunded', 'cancelled'
    
    payment_date = Column(DateTime, nullable=True)  
    is_trial = Column(Boolean, default=False, nullable=False)
    trial_days = Column(Integer, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)
    cancelled_by = Column(String(50), nullable=True)
    cancellation_reason = Column(Text, nullable=True)
    context_data = Column(Text, nullable=True)
    created_by = Column(String(50), nullable=False)
    updated_by = Column(String(50), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    
    history = relationship("TrnSubscriptionHistory", back_populates="subscription", 
                          order_by="desc(TrnSubscriptionHistory.changed_at)")


class TrnSubscriptionHistory(Base):
    """
    Subscription history and audit trail.
    Tracks all changes to subscriptions: creation, renewal, upgrades, downgrades, cancellations.
    """
    __tablename__ = "trn_subscription_history"
    __table_args__ = get_table_args(
        Index('idx_subscription_history', 'subscription_id', 'changed_at'),
        Index('idx_history_action', 'action', 'changed_at')
    )
    
    history_id = Column(Integer, primary_key=True, autoincrement=True)
    subscription_id = Column(Integer, ForeignKey(get_fk_name("trn_subscriptions", "subscription_id"), ondelete="CASCADE"),
                            nullable=False, index=True)
    
    action = Column(String(20), nullable=False, index=True)
    # Values: 'created', 'renewed', 'upgraded', 'downgraded', 'cancelled', 
    #         'expired', 'payment_success', 'payment_failed', 'refunded'
    action_description = Column(Text, nullable=True)
    old_end_date = Column(Date, nullable=True)
    new_end_date = Column(Date, nullable=True)
    old_billing_amount = Column(DECIMAL(10, 2), nullable=True)
    new_billing_amount = Column(DECIMAL(10, 2), nullable=True)
    context_data = Column(Text, nullable=True)
    changed_by = Column(String(50), nullable=False)
    changed_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)
    
    subscription = relationship("TrnSubscription", back_populates="history")