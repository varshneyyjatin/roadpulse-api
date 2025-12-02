"""CRUD operations for notifications."""
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, cast, Integer, Text
from application.database.models.notification import MstNotification
from application.database.models.transactions.notification_tracker import TrnNotificationTracker
from application.database.models.transactions.access_control import TrnAccessControl
from application.database.models.user import MstUser


def get_users_with_location_access(
    db: Session,
    company_id: int,
    location_id: int
) -> List[int]:
    """
    Get all user IDs who have access to a specific location.
    
    Args:
        db: Session
        company_id: Company ID
        location_id: Location ID
        
    Returns:
        List of user IDs with access to the location
    """
    import json
    from sqlalchemy import text
    
    # Query users with location access
    # access_data format: {"access_ids": [1, 2, 3]} or NULL (all locations)
    
    # Get all access control entries for location type
    access_entries = db.query(
        TrnAccessControl.user_id,
        TrnAccessControl.access_data
    ).join(
        MstUser, TrnAccessControl.user_id == MstUser.id
    ).filter(
        and_(
            TrnAccessControl.access_type == 'location',
            TrnAccessControl.disabled == False,
            TrnAccessControl.is_deleted == False,
            MstUser.company_id == company_id,
            MstUser.disabled == False,
            MstUser.is_deleted == False
        )
    ).all()
    
    # Filter users who have access to this location
    user_ids = []
    for user_id, access_data in access_entries:
        # NULL means access to all locations
        if access_data is None:
            user_ids.append(user_id)
            continue
        
        # Parse JSON and check if location_id is in access_ids array
        try:
            data = json.loads(access_data) if isinstance(access_data, str) else access_data
            access_ids = data.get('access_ids', []) if isinstance(data, dict) else []
            if location_id in access_ids:
                user_ids.append(user_id)
        except (json.JSONDecodeError, AttributeError, TypeError):
            continue
    
    return list(set(user_ids))  # Remove duplicates


def create_notification(
    db: Session,
    user_id: Optional[int],
    company_id: Optional[int],
    location_id: Optional[int],
    notification_type: str,
    title: str,
    message: str,
    priority: str,
    context_data: Optional[Dict[str, Any]],
    expires_at: Optional[datetime],
    created_by: str
) -> MstNotification:
    """
    Create a new notification.
    
    Args:
        db: Database session
        user_id: Target user ID (None for broadcast)
        company_id: Company ID
        location_id: Location ID
        notification_type: Type of notification
        title: Notification title
        message: Notification message
        priority: Priority level
        context_data: Additional context data
        expires_at: Expiration timestamp
        created_by: Username who created
        
    Returns:
        Created notification object
    """
    notification = MstNotification(
        user_id=user_id,
        company_id=company_id,
        location_id=location_id,
        notification_type=notification_type,
        title=title,
        message=message,
        priority=priority,
        context_data=context_data,
        expires_at=expires_at,
        created_by=created_by,
        updated_by=created_by
    )
    
    db.add(notification)
    db.commit()
    db.refresh(notification)
    
    return notification


def create_notification_tracker(
    db: Session,
    notification_id: int,
    user_id: int
) -> TrnNotificationTracker:
    """
    Create a notification tracker entry for a user.
    
    Args:
        db: Database session
        notification_id: Notification ID
        user_id: User ID
        
    Returns:
        Created tracker object
    """
    tracker = TrnNotificationTracker(
        notification_id=notification_id,
        user_id=user_id,
        is_read=False
    )
    
    db.add(tracker)
    db.commit()
    db.refresh(tracker)
    
    return tracker


def get_user_notifications(
    db: Session,
    user_id: int,
    company_id: Optional[int] = None,
    is_read: Optional[bool] = None,
    notification_type: Optional[str] = None,
    limit: int = 50
) -> List[tuple]:
    """
    Get notifications for a user with read status.
    
    Args:
        db: Database session
        user_id: User ID
        company_id: Company ID (None for all companies - creator only)
        is_read: Filter by read status (None for all)
        notification_type: Filter by notification type
        limit: Maximum number of results
        
    Returns:
        List of (notification, tracker) tuples
    """
    # Build base filters
    filters = [
        MstNotification.disabled == False,
        MstNotification.is_deleted == False,
        or_(
            MstNotification.expires_at.is_(None),
            MstNotification.expires_at > datetime.utcnow()
        ),
        or_(
            MstNotification.user_id == user_id,
            MstNotification.user_id.is_(None)
        )
    ]
    
    # Add company filter if specified (non-creator roles)
    if company_id is not None:
        filters.append(MstNotification.company_id == company_id)
    
    query = db.query(
        MstNotification,
        TrnNotificationTracker
    ).outerjoin(
        TrnNotificationTracker,
        and_(
            MstNotification.notification_id == TrnNotificationTracker.notification_id,
            TrnNotificationTracker.user_id == user_id
        )
    ).filter(and_(*filters))
    
    # Filter by read status
    if is_read is not None:
        if is_read:
            query = query.filter(TrnNotificationTracker.is_read == True)
        else:
            query = query.filter(
                or_(
                    TrnNotificationTracker.is_read == False,
                    TrnNotificationTracker.is_read.is_(None)
                )
            )
    
    # Filter by notification type
    if notification_type:
        query = query.filter(MstNotification.notification_type == notification_type)
    
    # Order by priority and created_at
    query = query.order_by(
        MstNotification.priority.desc(),
        MstNotification.created_at.desc()
    ).limit(limit)
    
    return query.all()


def mark_notifications_as_read(
    db: Session,
    notification_ids: List[int],
    user_id: int
) -> int:
    """
    Mark notifications as read for a user.
    
    Args:
        db: Database session
        notification_ids: List of notification IDs
        user_id: User ID
        
    Returns:
        Number of notifications marked as read
    """
    ist = timezone(timedelta(hours=5, minutes=30))
    current_time_ist = datetime.now(ist).replace(tzinfo=None)
    
    count = 0
    for notification_id in notification_ids:
        # Check if tracker exists
        tracker = db.query(TrnNotificationTracker).filter(
            and_(
                TrnNotificationTracker.notification_id == notification_id,
                TrnNotificationTracker.user_id == user_id
            )
        ).first()
        
        if tracker:
            # Update existing tracker
            if not tracker.is_read:
                tracker.is_read = True
                tracker.read_at = current_time_ist
                count += 1
        else:
            # Create new tracker for broadcast notification
            tracker = TrnNotificationTracker(
                notification_id=notification_id,
                user_id=user_id,
                is_read=True,
                read_at=current_time_ist
            )
            db.add(tracker)
            count += 1
    
    db.commit()
    return count


def get_unread_count(db: Session, user_id: int, company_id: Optional[int] = None) -> int:
    """
    Get count of unread notifications for a user.
    
    Args:
        db: Database session
        user_id: User ID
        company_id: Company ID (None for all companies - creator only)
        
    Returns:
        Count of unread notifications
    """
    # Build base filters
    filters = [
        MstNotification.disabled == False,
        MstNotification.is_deleted == False,
        or_(
            MstNotification.expires_at.is_(None),
            MstNotification.expires_at > datetime.utcnow()
        ),
        or_(
            MstNotification.user_id == user_id,
            MstNotification.user_id.is_(None)
        ),
        or_(
            TrnNotificationTracker.is_read == False,
            TrnNotificationTracker.is_read.is_(None)
        )
    ]
    
    # Add company filter if specified (non-creator roles)
    if company_id is not None:
        filters.append(MstNotification.company_id == company_id)
    
    count = db.query(func.count(MstNotification.notification_id)).outerjoin(
        TrnNotificationTracker,
        and_(
            MstNotification.notification_id == TrnNotificationTracker.notification_id,
            TrnNotificationTracker.user_id == user_id
        )
    ).filter(and_(*filters)).scalar()
    
    return count or 0


def get_user_notifications_with_access(
    db: Session,
    user_id: int,
    company_id: Optional[int] = None,
    accessible_location_ids: List[int] = None,
    has_all_locations_access: bool = False,
    is_read: Optional[bool] = None,
    notification_type: Optional[str] = None,
    limit: int = 50
) -> List[tuple]:
    """
    Get notifications for a user filtered by access control.
    
    Returns:
    - User-specific notifications (user_id = user_id)
    - Broadcast notifications for accessible locations (user_id = null, location_id in accessible_location_ids)
    
    Args:
        db: Database session
        user_id: User ID
        company_id: Company ID (None for all companies - creator only)
        accessible_location_ids: List of location IDs user has access to
        has_all_locations_access: Whether user has access to all locations
        is_read: Filter by read status (None for all)
        notification_type: Filter by notification type
        limit: Maximum number of results
        
    Returns:
        List of (notification, tracker) tuples
    """
    # Build base filters
    filters = [
        MstNotification.disabled == False,
        MstNotification.is_deleted == False,
        or_(
            MstNotification.expires_at.is_(None),
            MstNotification.expires_at > datetime.utcnow()
        )
    ]
    
    # Add company filter if specified (non-creator roles)
    if company_id is not None:
        filters.append(MstNotification.company_id == company_id)
    
    query = db.query(
        MstNotification,
        TrnNotificationTracker
    ).outerjoin(
        TrnNotificationTracker,
        and_(
            MstNotification.notification_id == TrnNotificationTracker.notification_id,
            TrnNotificationTracker.user_id == user_id
        )
    ).filter(and_(*filters))
    
    # Filter by user access:
    # 1. User-specific notifications (user_id = user_id)
    # 2. Broadcast notifications for accessible locations
    if has_all_locations_access:
        # User has access to all locations - show all broadcast notifications
        query = query.filter(
            or_(
                MstNotification.user_id == user_id,
                MstNotification.user_id.is_(None)
            )
        )
    else:
        # User has limited location access
        if accessible_location_ids:
            query = query.filter(
                or_(
                    MstNotification.user_id == user_id,
                    and_(
                        MstNotification.user_id.is_(None),
                        MstNotification.location_id.in_(accessible_location_ids)
                    )
                )
            )
        else:
            # No location access - only show user-specific notifications
            query = query.filter(MstNotification.user_id == user_id)
    
    # Filter by read status
    if is_read is not None:
        if is_read:
            query = query.filter(TrnNotificationTracker.is_read == True)
        else:
            query = query.filter(
                or_(
                    TrnNotificationTracker.is_read == False,
                    TrnNotificationTracker.is_read.is_(None)
                )
            )
    
    # Filter by notification type
    if notification_type:
        query = query.filter(MstNotification.notification_type == notification_type)
    
    # Order by priority and created_at
    query = query.order_by(
        MstNotification.priority.desc(),
        MstNotification.created_at.desc()
    ).limit(limit)
    
    return query.all()
