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
        # Creator can see all companies, others only their company
        filter_company_id = None if current_user.role == 'creator' else company_id
        
        notifications = crud.get_user_notifications(
            db=db,
            user_id=user_id,
            company_id=filter_company_id,
            is_read=request.is_read,
            notification_type=request.notification_type,
            limit=request.limit
        )
        
        result = []
        image_paths = set()  # Collect all image paths
        
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
                vehicle_image = notification.context_data.get("vehicle_image")
                plate_image = notification.context_data.get("plate_image")
                
                notification_obj["vehicle_image"] = vehicle_image
                notification_obj["plate_image"] = plate_image
                
                # Collect image paths for batch URL generation
                if vehicle_image:
                    image_paths.add(vehicle_image)
                if plate_image:
                    image_paths.add(plate_image)
            else:
                notification_obj["vehicle_image"] = None
                notification_obj["plate_image"] = None
            
            result.append(notification_obj)
        
        # Generate presigned URLs for all images in batch
        from application.helpers.storage import get_storage
        storage = get_storage()
        presigned_urls = storage.generate_presigned_urls_batch(list(image_paths), expiration=3600)
        
        # Replace image paths with presigned URLs
        for notification_obj in result:
            vehicle_img = notification_obj.get("vehicle_image")
            plate_img = notification_obj.get("plate_image")
            
            if vehicle_img:
                notification_obj["vehicle_image"] = presigned_urls.get(vehicle_img)
            if plate_img:
                notification_obj["plate_image"] = presigned_urls.get(plate_img)
        
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
        # Creator can see all companies, others only their company
        filter_company_id = None if current_user.role == 'creator' else company_id
        
        count = crud.get_unread_count(
            db=db,
            user_id=user_id,
            company_id=filter_company_id
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
    nav_notification: bool = False,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all notifications for current user (simplified - no access control for now).
    
    Query Parameters:
    - is_read: Filter by read status (optional)
    - notification_type: Filter by notification type (optional)
    - limit: Maximum number of results (default: 50)
    - nav_notification: If true, returns minimal data (notification_type, title, message only)
    
    Returns all notifications from MstNotification table for the user.
    """
    user_id = current_user.user_id
    company_id = current_user.company_id
    
    logger.info(f"My Notifications :: UserID:{user_id} :: IsRead:{is_read} :: Type:{notification_type} :: Limit:{limit} :: NavMode:{nav_notification}")
    
    try:
        # If nav_notification is true, get only latest 3 UNREAD notifications
        if nav_notification:
            # Force is_read=False for nav mode to get only unread
            notifications = crud.get_user_notifications(
                db=db,
                user_id=user_id,
                company_id=company_id,
                is_read=False,  # Only unread notifications
                notification_type=notification_type,
                limit=3  # Only 3 latest
            )
            
            result = []
            for notification, tracker in notifications:
                result.append({
                    "notification_type": notification.notification_type,
                    "title": notification.title,
                    "message": notification.message
                })
            
            # Get unread count for nav mode
            filter_company_id = None if current_user.role == 'creator' else company_id
            unread_count = crud.get_unread_count(
                db=db,
                user_id=user_id,
                company_id=filter_company_id
            )
            
            logger.info(f"My Notifications Success (Nav) :: UserID:{user_id} :: Count:{len(result)} :: Unread:{unread_count}")
            
            return {
                "total": len(result),
                "unread_count": unread_count,
                "notifications": result
            }
        
        # Regular mode - get notifications based on filters
        notifications = crud.get_user_notifications(
            db=db,
            user_id=user_id,
            company_id=company_id,
            is_read=is_read,
            notification_type=notification_type,
            limit=limit
        )
        
        result = []
        
        # Full notification data with images
        image_paths = set()  # Collect all image paths
        
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
                vehicle_image = notification.context_data.get("vehicle_image")
                plate_image = notification.context_data.get("plate_image")
                
                notification_obj["vehicle_image"] = vehicle_image
                notification_obj["plate_image"] = plate_image
                
                # Collect image paths for batch URL generation
                if vehicle_image:
                    image_paths.add(vehicle_image)
                if plate_image:
                    image_paths.add(plate_image)
            else:
                notification_obj["vehicle_image"] = None
                notification_obj["plate_image"] = None
            
            result.append(notification_obj)
        
        # Generate presigned URLs for all images in batch
        from application.helpers.storage import get_storage
        storage = get_storage()
        presigned_urls = storage.generate_presigned_urls_batch(list(image_paths), expiration=3600)
        
        # Replace image paths with presigned URLs
        for notification_obj in result:
            vehicle_img = notification_obj.get("vehicle_image")
            plate_img = notification_obj.get("plate_image")
            
            if vehicle_img:
                notification_obj["vehicle_image"] = presigned_urls.get(vehicle_img)
            if plate_img:
                notification_obj["plate_image"] = presigned_urls.get(plate_img)
        
        logger.info(f"My Notifications Success :: UserID:{user_id} :: Count:{len(result)}")
        
        return {
            "total": len(result),
            "notifications": result
        }
        
    except Exception as e:
        logger.error(f"My Notifications Failed :: UserID:{user_id} :: Error:{str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch notifications: {str(e)}"
        )