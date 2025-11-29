"""Utility functions for notifications."""
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from application.notification import crud
from application.helpers.logger import get_logger

logger = get_logger("notification_utils")


def send_watchlist_alert(
    db: Session,
    company_id: int,
    location_id: int,
    vehicle_id: int,
    plate_number: str,
    is_blacklisted: bool,
    is_whitelisted: bool,
    checkpoint_name: Optional[str] = None,
    timestamp: Optional[str] = None,
    vehicle_image: Optional[str] = None,
    plate_image: Optional[str] = None,
    vehicle_data: Optional[Dict[str, Any]] = None
) -> int:
    """
    Send watchlist alert notification to users with access to the location.
    
    Args:
        db: Database session
        company_id: Company ID
        location_id: Location ID where vehicle was detected
        vehicle_id: Vehicle ID
        plate_number: Vehicle plate number
        is_blacklisted: Whether vehicle is blacklisted
        is_whitelisted: Whether vehicle is whitelisted
        checkpoint_name: Checkpoint name (optional)
        timestamp: Detection timestamp (optional)
        vehicle_image: Vehicle snapshot image path (optional)
        plate_image: Number plate image path (optional)
        vehicle_data: Additional vehicle detection data (optional)
        
    Returns:
        Number of notifications created
    """
    # Get users with access to this location
    user_ids = crud.get_users_with_location_access(
        db=db,
        company_id=company_id,
        location_id=location_id
    )
    
    if not user_ids:
        logger.warning(
            f"Watchlist Alert Skipped :: LocationID -> {location_id} :: "
            f"Reason -> No users with access"
        )
        return 0
    
    # Determine notification type and priority
    notification_type = "watchlist_alert"
    
    if is_blacklisted:
        priority = "high"
        status_emoji = "🚨"
        status_text = "Blacklisted"
        action_text = "Please take immediate action"
    elif is_whitelisted:
        priority = "medium"
        status_emoji = "✅"
        status_text = "Whitelisted"
        action_text = "Authorized vehicle entry"
    else:
        return 0
    
    # Build formatted message
    title = f"{status_emoji} {status_text} Vehicle Alert"
    
    # Message with better formatting
    message_parts = [f"{status_text} vehicle {plate_number} has been detected"]
    
    if checkpoint_name:
        message_parts.append(f"at {checkpoint_name}")
    
    if timestamp:
        # Format timestamp nicely
        try:
            from datetime import datetime
            dt = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
            formatted_time = dt.strftime("%I:%M %p on %B %d, %Y")
            message_parts.append(f"on {formatted_time}")
        except:
            message_parts.append(f"at {timestamp}")
    
    message = " ".join(message_parts) + f". {action_text}."
    
    # Context data with vehicle images and details
    context_data = {
        "vehicle_id": vehicle_id,
        "plate_number": plate_number,
        "location_id": location_id,
        "checkpoint_name": checkpoint_name,
        "timestamp": timestamp,
        "is_blacklisted": is_blacklisted,
        "is_whitelisted": is_whitelisted,
        "vehicle_image": vehicle_image,
        "plate_image": plate_image
    }
    
    # Add vehicle data if provided
    if vehicle_data:
        context_data["vehicle_data"] = vehicle_data
    
    logger.info(
        f"Context Data :: VehicleImage -> {vehicle_image} :: "
        f"PlateImage -> {plate_image} :: HasVehicleData -> {vehicle_data is not None}"
    )
    
    # Set expiration (24 hours from now)
    expires_at = datetime.utcnow() + timedelta(hours=24)
    
    # Create ONE broadcast notification
    try:
        notification = crud.create_notification(
            db=db,
            user_id=None,  # Broadcast notification
            company_id=company_id,
            location_id=location_id,
            notification_type=notification_type,
            title=title,
            message=message,
            priority=priority,
            context_data=context_data,
            expires_at=expires_at,
            created_by="system"
        )
        
        # Create tracker entries for all users with access
        notification_count = 0
        for user_id in user_ids:
            try:
                crud.create_notification_tracker(
                    db=db,
                    notification_id=notification.notification_id,
                    user_id=user_id
                )
                notification_count += 1
            except Exception as e:
                logger.error(
                    f"Tracker Creation Failed :: UserID -> {user_id} :: "
                    f"NotificationID -> {notification.notification_id} :: Error -> {str(e)}"
                )
                continue
        
        logger.info(
            f"Watchlist Alert Sent :: PlateNumber -> {plate_number} :: "
            f"LocationID -> {location_id} :: UserCount -> {notification_count}"
        )
        
        return notification_count
        
    except Exception as e:
        logger.error(
            f"Watchlist Alert Failed :: PlateNumber -> {plate_number} :: "
            f"LocationID -> {location_id} :: Error -> {str(e)}"
        )
        return 0
