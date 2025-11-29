"""API routes for notifications."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from application.database.session import get_db
from application.auth.utils import get_current_user
from application.notification import crud, schemas
from application.helpers.logger import get_logger

logger = get_logger("notification")
router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.post("/", response_model=schemas.NotificationResponse)
def create_notification(
    request: schemas.CreateNotificationRequest = Body(...),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new notification.
    
    - Can be targeted (user_id specified) or broadcast (user_id = null)
    - Automatically creates tracker entries for targeted notifications
    """
    user_id = current_user.user_id
    username = current_user.username
    
    logger.info(
        f"Create Notification Request :: UserID -> {user_id} :: "
        f"Type -> {request.notification_type} :: Priority -> {request.priority}"
    )
    
    try:
        # Create notification
        notification = crud.create_notification(
            db=db,
            user_id=request.user_id,
            company_id=request.company_id or current_user.company_id,
            location_id=request.location_id,
            notification_type=request.notification_type,
            title=request.title,
            message=request.message,
            priority=request.priority,
            context_data=request.context_data,
            expires_at=request.expires_at,
            created_by=username
        )
        
        # If targeted notification, create tracker entry
        if request.user_id:
            crud.create_notification_tracker(
                db=db,
                notification_id=notification.notification_id,
                user_id=request.user_id
            )
        
        logger.info(
            f"Create Notification Success :: NotificationID -> {notification.notification_id} :: "
            f"Type -> {request.notification_type}"
        )
        
        return schemas.NotificationResponse(
            notification_id=notification.notification_id,
            user_id=notification.user_id,
            company_id=notification.company_id,
            location_id=notification.location_id,
            notification_type=notification.notification_type,
            title=notification.title,
            message=notification.message,
            priority=notification.priority,
            context_data=notification.context_data,
            is_read=False,
            read_at=None,
            created_at=notification.created_at,
            expires_at=notification.expires_at
        )
        
    except Exception as e:
        db.rollback()
        logger.error(f"Create Notification Failed :: UserID -> {user_id} :: Error -> {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create notification: {str(e)}"
        )


@router.post("/list")
def get_notifications(
    request: schemas.GetNotificationsRequest = Body(...),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get notifications for the current user.
    
    - Returns both targeted and broadcast notifications
    - Can filter by read status and notification type
    """
    user_id = current_user.user_id
    company_id = current_user.company_id
    
    logger.info(
        f"Get Notifications Request :: UserID -> {user_id} :: "
        f"IsRead -> {request.is_read} :: Type -> {request.notification_type}"
    )
    
    try:
        notifications = crud.get_user_notifications(
            db=db,
            user_id=user_id,
            company_id=company_id,
            is_read=request.is_read,
            notification_type=request.notification_type,
            limit=request.limit
        )
        
        result = []
        for notification, tracker in notifications:
            notification_obj = {
                "notification_id": notification.notification_id,
                "user_id": notification.user_id,
                "company_id": notification.company_id,
                "location_id": notification.location_id,
                "notification_type": notification.notification_type,
                "title": notification.title,
                "message": notification.message,
                "priority": notification.priority,
                "context_data": notification.context_data,
                "is_read": tracker.is_read if tracker else False,
                "read_at": tracker.read_at if tracker else None,
                "created_at": notification.created_at,
                "expires_at": notification.expires_at
            }
            
            # Extract images from context_data for easier access
            if notification.context_data:
                notification_obj["vehicle_image"] = notification.context_data.get("vehicle_image")
                notification_obj["plate_image"] = notification.context_data.get("plate_image")
            else:
                notification_obj["vehicle_image"] = None
                notification_obj["plate_image"] = None
            
            result.append(notification_obj)
        
        logger.info(
            f"Get Notifications Success :: UserID -> {user_id} :: "
            f"Count -> {len(result)}"
        )
        
        return {
            "total": len(result),
            "notifications": result
        }
        
    except Exception as e:
        logger.error(f"Get Notifications Failed :: UserID -> {user_id} :: Error -> {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch notifications: {str(e)}"
        )

@router.post("/mark-as-read")
def mark_as_read(
    request: schemas.MarkAsReadRequest = Body(...),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Mark notifications as read for the current user.
    """
    user_id = current_user.user_id
    
    logger.info(
        f"Mark As Read Request :: UserID -> {user_id} :: "
        f"NotificationIDs -> {request.notification_ids}"
    )
    
    try:
        count = crud.mark_notifications_as_read(
            db=db,
            notification_ids=request.notification_ids,
            user_id=user_id
        )
        
        logger.info(
            f"Mark As Read Success :: UserID -> {user_id} :: "
            f"MarkedCount -> {count}"
        )
        
        return {
            "success": True,
            "marked_count": count,
            "message": f"{count} notification(s) marked as read"
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Mark As Read Failed :: UserID -> {user_id} :: Error -> {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to mark notifications as read: {str(e)}"
        )

@router.get("/unread-count")
def get_unread_count(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get count of unread notifications for the current user.
    """
    user_id = current_user.user_id
    company_id = current_user.company_id
    
    try:
        count = crud.get_unread_count(
            db=db,
            user_id=user_id,
            company_id=company_id
        )
        
        logger.info(f"Unread Count :: UserID -> {user_id} :: Count -> {count}")
        
        return {
            "unread_count": count
        }
        
    except Exception as e:
        logger.error(f"Unread Count Failed :: UserID -> {user_id} :: Error -> {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get unread count: {str(e)}"
        )


@router.get("/my-notifications")
def get_my_notifications(
    is_read: Optional[bool] = None,
    notification_type: Optional[str] = None,
    limit: int = 50,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get notifications for current user based on access control.
    
    Query Parameters:
    - is_read: Filter by read status (optional)
    - notification_type: Filter by notification type (optional)
    - limit: Maximum number of results (default: 50)
    
    Returns:
    - User-specific notifications (user_id = current_user.id)
    - Broadcast notifications for user's accessible locations (user_id = null, location_id in accessible locations)
    - Filtered by access matrix (location-based access control)
    """
    from application.database.models.transactions.access_control import TrnAccessControl
    import json
    
    user_id = current_user.user_id
    company_id = current_user.company_id
    
    logger.info(
        f"My Notifications Request :: UserID -> {user_id} :: "
        f"IsRead -> {is_read} :: Type -> {notification_type}"
    )
    
    try:
        # Get user's accessible location IDs from access control
        access_entries = db.query(TrnAccessControl).filter(
            TrnAccessControl.user_id == user_id,
            TrnAccessControl.access_type == 'location',
            TrnAccessControl.disabled == False,
            TrnAccessControl.is_deleted == False
        ).all()
        
        accessible_location_ids = []
        has_all_locations_access = False
        
        for entry in access_entries:
            # NULL access_data means access to all locations
            if entry.access_data is None:
                has_all_locations_access = True
                break
            
            # Parse JSON and extract location IDs
            try:
                data = json.loads(entry.access_data) if isinstance(entry.access_data, str) else entry.access_data
                access_ids = data.get('access_ids', []) if isinstance(data, dict) else []
                accessible_location_ids.extend(access_ids)
            except (json.JSONDecodeError, AttributeError, TypeError):
                continue
        
        # Remove duplicates
        accessible_location_ids = list(set(accessible_location_ids))
        
        logger.info(
            f"Access Control Check :: UserID -> {user_id} :: "
            f"AllLocations -> {has_all_locations_access} :: "
            f"AccessibleLocations -> {accessible_location_ids}"
        )
        
        # Get notifications with location-based filtering
        notifications = crud.get_user_notifications_with_access(
            db=db,
            user_id=user_id,
            company_id=company_id,
            accessible_location_ids=accessible_location_ids,
            has_all_locations_access=has_all_locations_access,
            is_read=is_read,
            notification_type=notification_type,
            limit=limit
        )
        
        result = []
        for notification, tracker in notifications:
            notification_obj = {
                "notification_id": notification.notification_id,
                "user_id": notification.user_id,
                "company_id": notification.company_id,
                "location_id": notification.location_id,
                "notification_type": notification.notification_type,
                "title": notification.title,
                "message": notification.message,
                "priority": notification.priority,
                "context_data": notification.context_data,
                "is_read": tracker.is_read if tracker else False,
                "read_at": tracker.read_at if tracker else None,
                "created_at": notification.created_at,
                "expires_at": notification.expires_at
            }
            
            # Extract images from context_data for easier access
            if notification.context_data:
                notification_obj["vehicle_image"] = notification.context_data.get("vehicle_image")
                notification_obj["plate_image"] = notification.context_data.get("plate_image")
            else:
                notification_obj["vehicle_image"] = None
                notification_obj["plate_image"] = None
            
            result.append(notification_obj)
        
        logger.info(
            f"My Notifications Success :: UserID -> {user_id} :: "
            f"Count -> {len(result)}"
        )
        
        return {
            "total": len(result),
            "notifications": result
        }
        
    except Exception as e:
        logger.error(f"My Notifications Failed :: UserID -> {user_id} :: Error -> {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch notifications: {str(e)}"
        )
