"""
API routes for dashboard.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone, date
from application.database.session import get_db
from application.auth.utils import get_current_user
from application.dashboard import crud, utils, schemas
from application.database.models.transactions.access_control import TrnAccessControl
from application.database.models.transactions.vehicle_log import TrnVehicleLog
from application.database.models.checkpoint import MstCheckpoint
from application.helpers.logger import get_logger
from application.helpers.storage import get_storage

logger = get_logger("dashboard")
router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

@router.post("/vehicle-logs")
def get_vehicle_logs(
    request: schemas.VehicleLogsRequest = Body(...),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get vehicle logs based on scope.
    
    - scope=dashboard: Returns today's data based on user's access control
    - scope=report: Returns data for specified locations, checkpoints, and date range
    """
    user_id = current_user.user_id
    logger.info(f"Vehicle Logs Request :: UserID -> {user_id} :: Username -> {current_user.username} :: Scope -> {request.scope}")
    
    # Get user's access control entries
    access_entries = db.query(TrnAccessControl).filter(
        TrnAccessControl.user_id == user_id,
        TrnAccessControl.disabled == False,
        TrnAccessControl.is_deleted == False
    ).all()
    
    if not access_entries:
        logger.warning(f"Vehicle Logs Request :: UserID -> {user_id} :: Reason -> No access control entries found")
        return {
            "total_logs": 0,
            "logs": []
        }
    
    # Extract accessible locations and checkpoints from access control
    access_info = utils.extract_accessible_locations_checkpoints(access_entries)
    user_location_ids = access_info["location_ids"]
    user_checkpoint_ids = access_info["checkpoint_ids"]
    
    # Determine final location and checkpoint IDs based on scope
    if request.scope == schemas.ScopeEnum.dashboard:
        # Dashboard scope: use user's access control
        location_ids = user_location_ids
        checkpoint_ids = user_checkpoint_ids
        
        # Use provided dates or default to today
        if request.start_date or request.end_date:
            start_date = request.start_date
            end_date = request.end_date
        else:
            today = date.today()
            start_date = today
            end_date = today
        
        # Validate: Dashboard scope allows maximum 30 days
        if start_date and end_date:
            date_diff = (end_date - start_date).days
            if date_diff > 30:
                logger.warning(f"Dashboard Scope Failed :: UserID -> {user_id} :: Reason -> Date range exceeds 30 days limit")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Dashboard scope allows maximum 30 days date range"
                )
        
        logger.info(f"Dashboard Scope :: UserID -> {user_id} :: LocationIDs -> {location_ids} :: CheckpointIDs -> {checkpoint_ids} :: StartDate -> {start_date} :: EndDate -> {end_date}")
    else:
        # Report scope: use requested locations/checkpoints (filtered by user access)
        if request.location_ids:
            # Filter requested locations by user's accessible locations
            location_ids = [lid for lid in request.location_ids if lid in user_location_ids] if user_location_ids else request.location_ids
        else:
            # If no locations specified, use all accessible locations
            location_ids = user_location_ids
        
        if request.checkpoint_ids:
            # Filter requested checkpoints by user's accessible checkpoints
            checkpoint_ids = [cid for cid in request.checkpoint_ids if cid in user_checkpoint_ids] if user_checkpoint_ids else request.checkpoint_ids
        else:
            # If no checkpoints specified, use all accessible checkpoints
            checkpoint_ids = user_checkpoint_ids
        
        start_date = request.start_date
        end_date = request.end_date
        
        # Validate: Report scope allows maximum 90 days
        if start_date and end_date:
            date_diff = (end_date - start_date).days
            if date_diff > 90:
                logger.warning(f"Report Scope Failed :: UserID -> {user_id} :: Reason -> Date range exceeds 90 days limit")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Report scope allows maximum 90 days date range"
                )
        
        logger.info(f"Report Scope :: UserID -> {user_id} :: LocationIDs -> {location_ids} :: CheckpointIDs -> {checkpoint_ids} :: StartDate -> {start_date} :: EndDate -> {end_date}")
    
    # Determine if today_only flag for summary counts
    today = date.today()
    today_only = (request.scope == schemas.ScopeEnum.dashboard and start_date == today and end_date == today)
    
    # Get summary counts
    summary = crud.get_summary_counts(
        db,
        company_id=current_user.company_id,
        location_ids=location_ids,
        checkpoint_ids=checkpoint_ids,
        start_date=start_date,
        end_date=end_date,
        today_only=today_only
    )
    
    # Get vehicle logs with blacklist status in single query
    logs = crud.get_vehicle_logs_with_blacklist(
        db,
        company_id=current_user.company_id,
        location_ids=location_ids,
        checkpoint_ids=checkpoint_ids,
        start_date=start_date,
        end_date=end_date,
        is_blacklisted=request.is_blacklisted,
        is_whitelisted=request.is_whitelisted,
        plate_number=request.plate_number if request.scope == schemas.ScopeEnum.report else None
    )
    
    # OPTIMIZATION: Pre-fetch all checkpoint IDs from history_data in one query
    from application.database.models.location import MstLocation
    
    # OPTIMIZED: Extract checkpoint IDs using set comprehension
    all_checkpoint_ids = {
        entry.get("checkpoint_id")
        for log in logs if log.history_data
        for entry in log.history_data
        if entry.get("checkpoint_id")
    }
    
    # Single query to fetch all checkpoints with locations
    checkpoint_cache = {}
    if all_checkpoint_ids:
        checkpoints = db.query(
            MstCheckpoint.checkpoint_id,
            MstCheckpoint.name,
            MstCheckpoint.location_id,
            MstLocation.location_name
        ).outerjoin(
            MstLocation, MstCheckpoint.location_id == MstLocation.location_id
        ).filter(
            MstCheckpoint.checkpoint_id.in_(all_checkpoint_ids)
        ).all()
        
        # OPTIMIZED: Build cache using dict comprehension
        checkpoint_cache = {
            cp.checkpoint_id: {
                "checkpoint_name": cp.name,
                "location_id": cp.location_id,
                "location_name": cp.location_name
            }
            for cp in checkpoints
        }
    
    # Format response - OPTIMIZED
    result = []
    image_paths = set()  # Collect images while building result
    
    for log in logs:
        # Determine plate number to display
        display_plate_number = log.plate_number
        if log.is_revised and log.revised_data:
            display_plate_number = log.revised_data.get("new_number", log.plate_number)
        
        is_blacklisted = bool(log.is_blacklisted)
        is_whitelisted = bool(log.is_whitelisted)
        is_revised = bool(log.is_revised)
        
        # If searching by plate_number, expand history_data into separate rows
        if request.plate_number and log.history_data:
            # Sort history_data by timestamp in ascending order
            sorted_history = sorted(
                log.history_data,
                key=lambda x: x.get("Picture", {}).get("SnapInfo", {}).get("SnapTime", "")
            )
            
            for idx, entry in enumerate(sorted_history):
                checkpoint_id = entry.get("checkpoint_id")
                picture_data = entry.get("Picture", {})
                snap_time = picture_data.get("SnapInfo", {}).get("SnapTime", "")
                vehicle_image = picture_data.get("VehiclePic", {}).get("Content")
                plate_image = picture_data.get("CutoutPic", {}).get("Content")
                
                # Collect images
                if vehicle_image:
                    image_paths.add(vehicle_image)
                if plate_image:
                    image_paths.add(plate_image)
                
                checkpoint_info = checkpoint_cache.get(checkpoint_id, {})
                
                result.append({
                    "log_id": log.log_id,
                    "vehicle_id": log.vehicle_id,
                    "detection_number": idx + 1,
                    "location_id": checkpoint_info.get("location_id"),
                    "location_name": checkpoint_info.get("location_name"),
                    "checkpoint_id": checkpoint_id,
                    "checkpoint_name": checkpoint_info.get("checkpoint_name"),
                    "timestamp": snap_time,
                    "plate_number": display_plate_number,
                    "is_blacklisted": is_blacklisted,
                    "is_whitelisted": is_whitelisted,
                    "latest_data_vehicle_image": vehicle_image,
                    "latest_data_number_plate_image": plate_image,
                    "is_multiple_times": len(log.history_data) > 1,
                    "is_revised": is_revised,
                    "timeline": []
                })
        else:
            # Normal behavior: one row per log with timeline
            picture_data = log.latest_data.get("Picture", {}) if log.latest_data else {}
            latest_vehicle_image = picture_data.get("VehiclePic", {}).get("Content")
            latest_plate_image = picture_data.get("CutoutPic", {}).get("Content")
            latest_timestamp = picture_data.get("SnapInfo", {}).get("SnapTime")
            
            # Collect images
            if latest_vehicle_image:
                image_paths.add(latest_vehicle_image)
            if latest_plate_image:
                image_paths.add(latest_plate_image)
            
            # Build timeline from history_data
            timeline = []
            if log.history_data:
                for entry in log.history_data:
                    checkpoint_id = entry.get("checkpoint_id")
                    picture_data = entry.get("Picture", {})
                    snap_time = picture_data.get("SnapInfo", {}).get("SnapTime", "")
                    vehicle_image = picture_data.get("VehiclePic", {}).get("Content")
                    plate_image = picture_data.get("CutoutPic", {}).get("Content")
                    
                    # Collect images
                    if vehicle_image:
                        image_paths.add(vehicle_image)
                    if plate_image:
                        image_paths.add(plate_image)
                    
                    checkpoint_info = checkpoint_cache.get(checkpoint_id, {})
                    timeline.append({
                        "location_name": checkpoint_info.get("location_name"),
                        "checkpoint_name": checkpoint_info.get("checkpoint_name"),
                        "time": snap_time,
                        "vehicle_image": vehicle_image,
                        "number_plate_image": plate_image
                    })
            
            result_obj = {
                "log_id": log.log_id,
                "vehicle_id": log.vehicle_id,
                "location_id": log.location_id,
                "location_name": log.location_name,
                "checkpoint_id": log.checkpoint_id,
                "checkpoint_name": log.checkpoint_name,
                "timestamp": latest_timestamp,
                "plate_number": display_plate_number,
                "is_blacklisted": is_blacklisted,
                "is_whitelisted": is_whitelisted,
                "latest_data_vehicle_image": latest_vehicle_image,
                "latest_data_number_plate_image": latest_plate_image,
                "is_multiple_times": len(log.history_data) > 1 if log.history_data else False,
                "is_revised": is_revised,
                "timeline": timeline
            }
            
            # Add revised_data only if is_revised is True
            if is_revised and log.revised_data:
                result_obj["revised_data"] = log.revised_data
            
            result.append(result_obj)
    
    # Generate presigned URLs for all images - OPTIMIZED
    storage = get_storage()
    presigned_urls = storage.generate_presigned_urls_batch(list(image_paths), expiration=3600)
    
    # Replace image paths with presigned URLs - OPTIMIZED
    for item in result:
        vehicle_img = item.get("latest_data_vehicle_image")
        plate_img = item.get("latest_data_number_plate_image")
        
        if vehicle_img:
            item["latest_data_vehicle_image"] = presigned_urls.get(vehicle_img)
        if plate_img:
            item["latest_data_number_plate_image"] = presigned_urls.get(plate_img)
        
        # Timeline images
        for timeline_entry in item.get("timeline", []):
            v_img = timeline_entry.get("vehicle_image")
            p_img = timeline_entry.get("number_plate_image")
            
            if v_img:
                timeline_entry["vehicle_image"] = presigned_urls.get(v_img)
            if p_img:
                timeline_entry["number_plate_image"] = presigned_urls.get(p_img)
    
    logger.info(f"Vehicle Logs Response :: UserID -> {user_id} :: Scope -> {request.scope} :: TotalVehicles -> {summary['total_vehicles']} :: TotalLogs -> {len(result)} :: PresignedURLs -> {len(presigned_urls)}")
    
    return {
        "total_vehicles": summary["total_vehicles"],
        "total_locations": summary["total_locations"],
        "total_cameras": summary["total_cameras"],
        "blacklisted_vehicle_count": summary["blacklisted_vehicle_count"],
        "multiple_detections_count": summary["multiple_detections_count"],
        "summary_data": result
    }

@router.post("/fix-vehicle-number")
def fix_vehicle_number(
    request: schemas.FixVehicleNumberRequest = Body(...),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Fix vehicle number by updating TrnVehicleLog.
    
    Updates the vehicle log with revised data and marks is_revised as True.
    Only works for records that haven't been revised yet (is_revised = False).
    """
    user_id = current_user.user_id
    username = current_user.username
    
    logger.info(f"Fix Vehicle Number Request :: UserID -> {user_id} :: Username -> {username} :: RecordID -> {request.record_id} :: OldValue -> {request.old_value} :: NewValue -> {request.new_value}")
    
    # Validate that old and new values are different
    if request.old_value.strip() == request.new_value.strip():
        logger.warning(f"Fix Vehicle Number Failed :: UserID -> {user_id} :: RecordID -> {request.record_id} :: Reason -> Old and new values are the same")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Old value and new value cannot be the same"
        )
    
    # Get the vehicle log record
    vehicle_log = db.query(TrnVehicleLog).filter(TrnVehicleLog.log_id == request.record_id).first()
    
    if not vehicle_log:
        logger.warning(f"Fix Vehicle Number Failed :: UserID -> {user_id} :: RecordID -> {request.record_id} :: Reason -> Vehicle log not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vehicle log record not found"
        )
    
    # Check if already revised
    if vehicle_log.is_revised:
        logger.warning(f"Fix Vehicle Number Failed :: UserID -> {user_id} :: RecordID -> {request.record_id} :: Reason -> Record already revised")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This record has already been revised and cannot be changed again"
        )
    
    try:
        # Get Indian Standard Time (IST = UTC + 5:30)
        ist = timezone(timedelta(hours=5, minutes=30))
        current_time_ist = datetime.now(ist)
        
        # Update vehicle log with revised data
        vehicle_log.revised_data = {
            "old_number": request.old_value,
            "new_number": request.new_value,
            "changed_by": username,
            "changed_at": current_time_ist.strftime("%Y-%m-%d %H:%M:%S"),
            "change_reason": request.change_reason
        }
        vehicle_log.is_revised = True
        vehicle_log.updated_by = username
        vehicle_log.updated_at = current_time_ist.replace(tzinfo=None)
        
        db.commit()
        db.refresh(vehicle_log)
        
        logger.info(f"Fix Vehicle Number Success :: UserID -> {user_id} :: RecordID -> {request.record_id} :: OldValue -> {request.old_value} :: NewValue -> {request.new_value}")
        
        return {
            "success": True,
            "message": "Vehicle number fixed successfully",
            "record_id": request.record_id,
            "old_value": request.old_value,
            "new_value": request.new_value,
            "revised_data": vehicle_log.revised_data
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Fix Vehicle Number Failed :: UserID -> {user_id} :: RecordID -> {request.record_id} :: Error -> {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fix vehicle number: {str(e)}"
        )