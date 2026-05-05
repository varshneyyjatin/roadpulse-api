"""
API routes for dashboard.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status, Body, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy import desc, cast, Integer, text
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone, date
from application.database.session import get_db
from application.auth.utils import get_current_user
from application.dashboard import crud, utils, schemas
from application.database.models.vehicle import MstVehicle
from application.database.models.transactions.access_control import TrnAccessControl
from application.database.models.transactions.vehicle_log import TrnVehicleLog
from application.database.models.checkpoint import MstCheckpoint
from application.database.models.location import MstLocation
from application.helpers.logger import get_logger
from application.helpers.storage import get_storage
import io
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.drawing.image import Image as XLImage
from PIL import Image as PILImage
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from rapidfuzz import fuzz

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
    
    # Compact request log
    logger.info(f"Vehicle Logs API :: User:{user_id}({current_user.username}) :: Co:{current_user.company_id} :: Role:{current_user.role} :: Scope:{request.scope} :: ReqLocs:{request.location_ids} :: ReqCPs:{request.checkpoint_ids} :: Dates:{request.start_date}-{request.end_date} :: BL:{request.is_blacklisted} :: WL:{request.is_whitelisted} :: Plate:{request.plate_number} :: Page:{request.page}/{request.page_size} :: Excel:{request.excel_report}")
    
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
    # Pass db, company_id, and role for company filtering
    access_info = utils.extract_accessible_locations_checkpoints(
        access_entries, 
        db=db, 
        company_id=current_user.company_id, 
        role=current_user.role
    )
    user_location_ids = access_info["location_ids"]
    user_checkpoint_ids = access_info["checkpoint_ids"]
    
    logger.info(f"Access Control :: UserLocs:{user_location_ids} :: UserCPs:{user_checkpoint_ids}")
    
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
        
        logger.info(f"Dashboard Scope :: FinalLocs:{location_ids} :: FinalCPs:{checkpoint_ids} :: Dates:{start_date}-{end_date}")
    else:
        # Report scope: use requested locations/checkpoints (filtered by user access)
        if request.location_ids:
            # Filter requested locations by user's accessible locations
            if user_location_ids is None:
                # None means user has access to ALL locations
                location_ids = request.location_ids
            elif len(user_location_ids) == 0:
                # Empty list means no access
                location_ids = []
            else:
                # Filter requested by accessible
                location_ids = [lid for lid in request.location_ids if lid in user_location_ids]
        else:
            # If no locations specified, use all accessible locations
            location_ids = user_location_ids
        
        # IMPORTANT: If location is selected, ALWAYS filter checkpoints by those locations
        if location_ids is not None and len(location_ids) > 0:
            # Fetch checkpoints that belong to selected locations
            location_checkpoints = db.query(MstCheckpoint.checkpoint_id).filter(
                MstCheckpoint.location_id.in_(location_ids),
                MstCheckpoint.disabled == False,
                MstCheckpoint.is_deleted == False
            ).all()
            location_checkpoint_ids = [cp[0] for cp in location_checkpoints]
            
            # If user also specified checkpoint_ids, intersect them
            if request.checkpoint_ids:
                # Only use checkpoints that are both: in selected locations AND requested by user
                checkpoint_ids = [cid for cid in request.checkpoint_ids if cid in location_checkpoint_ids]
            else:
                # Use all checkpoints from selected locations
                checkpoint_ids = location_checkpoint_ids
            
            logger.info(f"Checkpoint Filter :: LocationCheckpoints:{checkpoint_ids}")
        else:
            # No location filter, use checkpoint filter as-is
            if request.checkpoint_ids:
                # Filter requested checkpoints by user's accessible checkpoints
                if user_checkpoint_ids is None:
                    checkpoint_ids = request.checkpoint_ids
                elif len(user_checkpoint_ids) == 0:
                    checkpoint_ids = []
                else:
                    checkpoint_ids = [cid for cid in request.checkpoint_ids if cid in user_checkpoint_ids]
            else:
                # Use all accessible checkpoints
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
        
        logger.info(f"Report Scope :: ReqLocs:{request.location_ids} :: UserLocs:{user_location_ids} :: FinalLocs:{location_ids} :: FinalCPs:{checkpoint_ids} :: Dates:{start_date}-{end_date}")
    
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
    
    # Check if we need to use expanded pagination (for plate_number search)
    use_expanded_pagination = request.plate_number and request.scope == schemas.ScopeEnum.report
    
    logger.info(f"Query Params :: Locs:{location_ids} :: CPs:{checkpoint_ids} :: Dates:{start_date}-{end_date} :: Expanded:{use_expanded_pagination}")
    
    # Get total count of matching records
    total_records = crud.get_vehicle_logs_count(
        db,
        company_id=current_user.company_id,
        location_ids=location_ids,
        checkpoint_ids=checkpoint_ids,
        start_date=start_date,
        end_date=end_date,
        is_blacklisted=request.is_blacklisted,
        is_whitelisted=request.is_whitelisted,
        plate_number=request.plate_number if use_expanded_pagination else None
    )
    
    # Calculate pagination metadata
    total_pages = (total_records + request.page_size - 1) // request.page_size if total_records > 0 else 0
    
    if use_expanded_pagination:
        # Get vehicle logs with history_data expanded and paginated
        expanded_entries = crud.get_vehicle_logs_with_blacklist_expanded(
            db,
            company_id=current_user.company_id,
            location_ids=location_ids,
            checkpoint_ids=checkpoint_ids,
            start_date=start_date,
            end_date=end_date,
            is_blacklisted=request.is_blacklisted,
            is_whitelisted=request.is_whitelisted,
            plate_number=request.plate_number,
            page=request.page,
            page_size=request.page_size
        )
    else:
        # Get vehicle logs with blacklist status in single query (paginated)
        logs = crud.get_vehicle_logs_with_blacklist(
            db,
            company_id=current_user.company_id,
            location_ids=location_ids,
            checkpoint_ids=checkpoint_ids,
            start_date=start_date,
            end_date=end_date,
            is_blacklisted=request.is_blacklisted,
            is_whitelisted=request.is_whitelisted,
            plate_number=None,  # Don't filter by plate_number in normal mode
            page=request.page,
            page_size=request.page_size
        )
    
    # Format response based on mode
    result = []
    image_paths = set()  # Collect images while building result
    
    if use_expanded_pagination:
        # EXPANDED MODE: Process pre-expanded entries
        all_checkpoint_ids = {
            entry["history_entry"].get("checkpoint_id")
            for entry in expanded_entries
            if entry["history_entry"].get("checkpoint_id")
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
            
            checkpoint_cache = {
                cp.checkpoint_id: {
                    "checkpoint_name": cp.name,
                    "location_id": cp.location_id,
                    "location_name": cp.location_name
                }
                for cp in checkpoints
            }
        
        # Build result from expanded entries
        for entry_data in expanded_entries:
            log = entry_data["log"]
            history_entry = entry_data["history_entry"]
            detection_number = entry_data["detection_number"]
            
            # Determine plate number to display
            display_plate_number = log.plate_number
            if log.is_revised and log.revised_data:
                display_plate_number = log.revised_data.get("new_number", log.plate_number)
            
            checkpoint_id = history_entry.get("checkpoint_id")
            picture_data = history_entry.get("Picture", {})
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
                "detection_number": detection_number,
                "location_id": checkpoint_info.get("location_id"),
                "location_name": checkpoint_info.get("location_name"),
                "checkpoint_id": checkpoint_id,
                "checkpoint_name": checkpoint_info.get("checkpoint_name"),
                "timestamp": snap_time,
                "plate_number": display_plate_number,
                "is_blacklisted": bool(log.is_blacklisted),
                "is_whitelisted": bool(log.is_whitelisted),
                "latest_data_vehicle_image": vehicle_image,
                "latest_data_number_plate_image": plate_image,
                "is_multiple_times": entry_data["total_detections"] > 1,
                "is_revised": bool(log.is_revised),
                "timeline": []
            })
    else:
        # NORMAL MODE: Process logs with timeline
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
            
            checkpoint_cache = {
                cp.checkpoint_id: {
                    "checkpoint_name": cp.name,
                    "location_id": cp.location_id,
                    "location_name": cp.location_name
                }
                for cp in checkpoints
            }
        
        for log in logs:
            # Determine plate number to display
            display_plate_number = log.plate_number
            if log.is_revised and log.revised_data:
                display_plate_number = log.revised_data.get("new_number", log.plate_number)
            
            is_blacklisted = bool(log.is_blacklisted)
            is_whitelisted = bool(log.is_whitelisted)
            is_revised = bool(log.is_revised)
            
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
    
    logger.info(f"Response :: TotalVehicles:{summary['total_vehicles']} :: Page:{request.page}/{total_pages} :: Records:{len(result)}/{total_records} :: URLs:{len(presigned_urls)}")
    
    # Check if Excel report is requested
    if request.excel_report and request.scope == schemas.ScopeEnum.report:
        logger.info(f"Excel Report Start :: TotalRecords:{total_records}")
        
        # Fetch ALL data for Excel (no pagination limit)
        if use_expanded_pagination:
            # Get all expanded entries - use large page_size to get everything
            all_expanded_entries = crud.get_vehicle_logs_with_blacklist_expanded(
                db,
                company_id=current_user.company_id,
                location_ids=location_ids,
                checkpoint_ids=checkpoint_ids,
                start_date=start_date,
                end_date=end_date,
                is_blacklisted=request.is_blacklisted,
                is_whitelisted=request.is_whitelisted,
                plate_number=request.plate_number,
                page=1,
                page_size=100000  # Large number to get all records
            )
            
            # Fetch checkpoint info for Excel
            excel_checkpoint_ids = {
                entry["history_entry"].get("checkpoint_id")
                for entry in all_expanded_entries
                if entry["history_entry"].get("checkpoint_id")
            }
            
            excel_checkpoint_cache = {}
            if excel_checkpoint_ids:
                checkpoints = db.query(
                    MstCheckpoint.checkpoint_id,
                    MstCheckpoint.name,
                    MstCheckpoint.location_id,
                    MstLocation.location_name
                ).outerjoin(
                    MstLocation, MstCheckpoint.location_id == MstLocation.location_id
                ).filter(
                    MstCheckpoint.checkpoint_id.in_(excel_checkpoint_ids)
                ).all()
                
                excel_checkpoint_cache = {
                    cp.checkpoint_id: {
                        "checkpoint_name": cp.name,
                        "location_id": cp.location_id,
                        "location_name": cp.location_name
                    }
                    for cp in checkpoints
                }
            
            # Collect all image paths for Excel
            excel_image_paths = set()
            for entry_data in all_expanded_entries:
                history_entry = entry_data["history_entry"]
                picture_data = history_entry.get("Picture", {})
                vehicle_image = picture_data.get("VehiclePic", {}).get("Content")
                plate_image = picture_data.get("CutoutPic", {}).get("Content")
                if vehicle_image:
                    excel_image_paths.add(vehicle_image)
                if plate_image:
                    excel_image_paths.add(plate_image)
            
            # Generate presigned URLs for ALL Excel images
            excel_presigned_urls = storage.generate_presigned_urls_batch(list(excel_image_paths), expiration=3600)
            
            # Build Excel data from expanded entries
            excel_data = []
            for entry_data in all_expanded_entries:
                log = entry_data["log"]
                history_entry = entry_data["history_entry"]
                
                display_plate_number = log.plate_number
                if log.is_revised and log.revised_data:
                    display_plate_number = log.revised_data.get("new_number", log.plate_number)
                
                checkpoint_id = history_entry.get("checkpoint_id")
                picture_data = history_entry.get("Picture", {})
                snap_info = picture_data.get("SnapInfo", {})
                snap_time_str = snap_info.get("SnapTime", "")
                
                # Parse date and time
                try:
                    snap_datetime = datetime.strptime(snap_time_str, "%Y-%m-%d %H:%M:%S")
                    snap_date = snap_datetime.strftime("%Y-%m-%d")
                    snap_time = snap_datetime.strftime("%H:%M:%S")
                except:
                    snap_date = snap_time_str.split(" ")[0] if " " in snap_time_str else snap_time_str
                    snap_time = snap_time_str.split(" ")[1] if " " in snap_time_str else ""
                
                vehicle_image = picture_data.get("VehiclePic", {}).get("Content")
                plate_image = picture_data.get("CutoutPic", {}).get("Content")
                
                # Get checkpoint info
                checkpoint_info = excel_checkpoint_cache.get(checkpoint_id, {})
                
                excel_data.append({
                    "location_name": checkpoint_info.get("location_name", ""),
                    "checkpoint_name": checkpoint_info.get("checkpoint_name", ""),
                    "date": snap_date,
                    "time": snap_time,
                    "plate_number": display_plate_number,
                    "plate_image": excel_presigned_urls.get(plate_image) if plate_image else "",
                    "vehicle_image": excel_presigned_urls.get(vehicle_image) if vehicle_image else "",
                    "blacklist": "Yes" if log.is_blacklisted else "No",
                    "whitelist": "Yes" if log.is_whitelisted else "No"
                })
        else:
            # Get all normal logs - use large page_size to get everything
            all_logs = crud.get_vehicle_logs_with_blacklist(
                db,
                company_id=current_user.company_id,
                location_ids=location_ids,
                checkpoint_ids=checkpoint_ids,
                start_date=start_date,
                end_date=end_date,
                is_blacklisted=request.is_blacklisted,
                is_whitelisted=request.is_whitelisted,
                plate_number=None,
                page=1,
                page_size=100000  # Large number to get all records
            )
            
            # Collect all image paths for Excel
            excel_image_paths = set()
            for log in all_logs:
                picture_data = log.latest_data.get("Picture", {}) if log.latest_data else {}
                vehicle_image = picture_data.get("VehiclePic", {}).get("Content")
                plate_image = picture_data.get("CutoutPic", {}).get("Content")
                if vehicle_image:
                    excel_image_paths.add(vehicle_image)
                if plate_image:
                    excel_image_paths.add(plate_image)
            
            # Generate presigned URLs for ALL Excel images
            excel_presigned_urls = storage.generate_presigned_urls_batch(list(excel_image_paths), expiration=3600)
            
            # Build Excel data from normal logs
            excel_data = []
            for log in all_logs:
                display_plate_number = log.plate_number
                if log.is_revised and log.revised_data:
                    display_plate_number = log.revised_data.get("new_number", log.plate_number)
                
                picture_data = log.latest_data.get("Picture", {}) if log.latest_data else {}
                snap_info = picture_data.get("SnapInfo", {})
                snap_time_str = snap_info.get("SnapTime", "")
                
                # Parse date and time
                try:
                    snap_datetime = datetime.strptime(snap_time_str, "%Y-%m-%d %H:%M:%S")
                    snap_date = snap_datetime.strftime("%Y-%m-%d")
                    snap_time = snap_datetime.strftime("%H:%M:%S")
                except:
                    snap_date = snap_time_str.split(" ")[0] if " " in snap_time_str else snap_time_str
                    snap_time = snap_time_str.split(" ")[1] if " " in snap_time_str else ""
                
                vehicle_image = picture_data.get("VehiclePic", {}).get("Content")
                plate_image = picture_data.get("CutoutPic", {}).get("Content")
                
                # Get presigned URLs for Excel
                vehicle_image_url = excel_presigned_urls.get(vehicle_image) if vehicle_image else ""
                plate_image_url = excel_presigned_urls.get(plate_image) if plate_image else ""
                
                excel_data.append({
                    "location_name": log.location_name or "",
                    "checkpoint_name": log.checkpoint_name or "",
                    "date": snap_date,
                    "time": snap_time,
                    "plate_number": display_plate_number,
                    "plate_image": plate_image_url,
                    "vehicle_image": vehicle_image_url,
                    "blacklist": "Yes" if log.is_blacklisted else "No",
                    "whitelist": "Yes" if log.is_whitelisted else "No"
                })
        
        # Generate Excel file
        excel_buffer = generate_excel_report(excel_data, start_date, end_date)
        
        # Generate filename
        filename = f"vehicle_logs_{start_date}_{end_date}.xlsx"
        
        logger.info(f"Excel Report Done :: Records:{len(excel_data)} :: Filename:{filename}")
        
        # Return Excel file as download
        return StreamingResponse(
            excel_buffer,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    
    return {
        "total_vehicles": summary["total_vehicles"],
        "total_locations": summary["total_locations"],
        "total_cameras": summary["total_cameras"],
        "blacklisted_vehicle_count": summary["blacklisted_vehicle_count"],
        "multiple_detections_count": summary["multiple_detections_count"],
        "pagination": {
            "page": request.page,
            "page_size": request.page_size,
            "total_records": total_records,
            "total_pages": total_pages,
            "has_next": request.page < total_pages,
            "has_previous": request.page > 1
        },
        "summary_data": result
    }

def download_and_resize_image(url: str, max_size=(80, 40)) -> io.BytesIO:
    """
    Download and resize image in parallel - OPTIMIZED.
    
    Args:
        url: Image URL
        max_size: Maximum size tuple (width, height)
        
    Returns:
        BytesIO buffer with resized image or None if failed
    """
    try:
        response = requests.get(url, timeout=2, stream=True)  # Faster timeout + streaming
        if response.status_code == 200:
            img_data = io.BytesIO(response.content)
            pil_img = PILImage.open(img_data)
            
            # Convert to RGB if necessary
            if pil_img.mode in ('RGBA', 'LA', 'P'):
                pil_img = pil_img.convert('RGB')
            
            # Resize image (smaller = faster)
            pil_img.thumbnail(max_size, PILImage.Resampling.LANCZOS)
            
            # Save to BytesIO with compression
            img_buffer = io.BytesIO()
            pil_img.save(img_buffer, format='JPEG', quality=75, optimize=True)  # JPEG faster than PNG
            img_buffer.seek(0)
            return img_buffer
    except Exception as e:
        pass  # Silent fail for speed
    return None


def generate_excel_report(data: list, start_date: date = None, end_date: date = None) -> io.BytesIO:
    """
    Generate Excel report from vehicle logs data with embedded images.
    
    Args:
        data: List of vehicle log dictionaries
        start_date: Report start date (optional)
        end_date: Report end date (optional)
        
    Returns:
        BytesIO buffer containing Excel file
    """
    # Create workbook and worksheet
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Vehicle Logs"
    
    # ===== PROFESSIONAL TITLE SECTION =====
    ws.merge_cells('A1:H1')
    title_cell = ws['A1']
    title_cell.value = "ROADPULSE - Vehicle Detection Report"
    title_cell.font = Font(name='Arial', bold=True, size=18, color="FFFFFF")
    title_cell.fill = PatternFill(start_color="2C3E50", end_color="2C3E50", fill_type="solid")
    title_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 40
    
    # ===== DATE RANGE & INFO SECTION =====
    ws.merge_cells('A2:H2')
    date_cell = ws['A2']
    
    # Handle None dates
    if start_date and end_date:
        date_range = f"Report Period: {start_date.strftime('%d %B %Y')} to {end_date.strftime('%d %B %Y')}"
    elif start_date:
        date_range = f"Report Period: From {start_date.strftime('%d %B %Y')}"
    elif end_date:
        date_range = f"Report Period: Until {end_date.strftime('%d %B %Y')}"
    else:
        date_range = f"Report Period: All Time"
    
    date_cell.value = date_range
    date_cell.font = Font(name='Arial', bold=True, size=11, color="2C3E50")
    date_cell.fill = PatternFill(start_color="ECF0F1", end_color="ECF0F1", fill_type="solid")
    date_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[2].height = 25
    
    # ===== HEADERS =====
    headers = [
        "Location Name",
        "Checkpoint Name", 
        "Date",
        "Time",
        "Plate Number",
        "Plate Image",
        "Blacklist",
        "Whitelist"
    ]
    
    # Professional header styling
    header_fill = PatternFill(start_color="34495E", end_color="34495E", fill_type="solid")
    header_font = Font(name='Arial', bold=True, color="FFFFFF", size=11)
    header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    
    # Professional borders
    border_thick = Border(
        left=Side(style='medium', color='2C3E50'),
        right=Side(style='medium', color='2C3E50'),
        top=Side(style='medium', color='2C3E50'),
        bottom=Side(style='medium', color='2C3E50')
    )
    border = Border(
        left=Side(style='thin', color='BDC3C7'),
        right=Side(style='thin', color='BDC3C7'),
        top=Side(style='thin', color='BDC3C7'),
        bottom=Side(style='thin', color='BDC3C7')
    )
    
    # Write headers in row 3
    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=3, column=col_num)
        cell.value = header
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = header_alignment
        cell.border = border_thick
    
    ws.row_dimensions[3].height = 30
    
    # Optimized column widths
    ws.column_dimensions['A'].width = 22  # Location Name
    ws.column_dimensions['B'].width = 22  # Checkpoint Name
    ws.column_dimensions['C'].width = 12  # Date
    ws.column_dimensions['D'].width = 10  # Time
    ws.column_dimensions['E'].width = 15  # Plate Number
    ws.column_dimensions['F'].width = 15  # Plate Image (smaller)
    ws.column_dimensions['G'].width = 11  # Blacklist
    ws.column_dimensions['H'].width = 11  # Whitelist
    
    # ===== OPTIMIZED PARALLEL DOWNLOAD =====
    # Collect plate image URLs only
    plate_image_tasks = []
    for idx, record in enumerate(data):
        plate_url = record.get("plate_image", "")
        if plate_url and plate_url.startswith('http'):
            plate_image_tasks.append((idx, plate_url))
    
    # Download plate images in parallel (max 30 concurrent for maximum speed)
    plate_image_cache = {}
    with ThreadPoolExecutor(max_workers=30) as executor:
        future_to_task = {
            executor.submit(download_and_resize_image, task[1], (80, 40)): task  # Smaller images
            for task in plate_image_tasks
        }
        
        for future in as_completed(future_to_task):
            task = future_to_task[future]
            idx, url = task
            try:
                img_buffer = future.result()
                if img_buffer:
                    plate_image_cache[idx] = img_buffer
            except:
                pass  # Silent fail for speed
    
    # ===== DATA ROWS WITH PLATE IMAGES + VEHICLE LINKS =====
    current_row = 4
    
    for idx, record in enumerate(data):
        # Set row height for smaller images
        ws.row_dimensions[current_row].height = 50
        
        # Write text data with professional font
        ws.cell(row=current_row, column=1).value = record.get("location_name", "")
        ws.cell(row=current_row, column=2).value = record.get("checkpoint_name", "")
        ws.cell(row=current_row, column=3).value = record.get("date", "")
        ws.cell(row=current_row, column=4).value = record.get("time", "")
        
        # Plate number with bold font
        plate_cell = ws.cell(row=current_row, column=5)
        plate_cell.value = record.get("plate_number", "")
        plate_cell.font = Font(name='Arial', bold=True, size=10, color="2C3E50")
        
        # Embed plate image from cache
        if idx in plate_image_cache:
            try:
                xl_img = XLImage(plate_image_cache[idx])
                cell_ref = f'F{current_row}'
                ws.add_image(xl_img, cell_ref)
            except:
                ws.cell(row=current_row, column=6).value = "N/A"
                ws.cell(row=current_row, column=6).font = Font(name='Arial', size=9, color="95A5A6")
        else:
            ws.cell(row=current_row, column=6).value = "N/A"
            ws.cell(row=current_row, column=6).font = Font(name='Arial', size=9, color="95A5A6")
        
        # Blacklist with professional styling
        blacklist_cell = ws.cell(row=current_row, column=7)
        if record.get("blacklist") == "Yes":
            blacklist_cell.value = "YES"
            blacklist_cell.font = Font(name='Arial', bold=True, size=10, color="E74C3C")
            blacklist_cell.fill = PatternFill(start_color="FADBD8", end_color="FADBD8", fill_type="solid")
        else:
            blacklist_cell.value = "No"
            blacklist_cell.font = Font(name='Arial', size=10, color="27AE60")
        
        # Whitelist with professional styling
        whitelist_cell = ws.cell(row=current_row, column=8)
        if record.get("whitelist") == "Yes":
            whitelist_cell.value = "YES"
            whitelist_cell.font = Font(name='Arial', bold=True, size=10, color="3498DB")
            whitelist_cell.fill = PatternFill(start_color="D6EAF8", end_color="D6EAF8", fill_type="solid")
        else:
            whitelist_cell.value = "No"
            whitelist_cell.font = Font(name='Arial', size=10, color="7F8C8D")
        
        # Apply professional styling to all cells
        for col in range(1, 9):
            cell = ws.cell(row=current_row, column=col)
            
            # Set font only if not already set (for columns 5, 7, 8)
            if col not in [5, 7, 8]:
                cell.font = Font(name='Arial', size=10)
            
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=False)
            cell.border = border
            
            # Elegant alternate row colors (don't override blacklist/whitelist)
            if col not in [7, 8]:
                if current_row % 2 == 0:
                    cell.fill = PatternFill(start_color="F7F9F9", end_color="F7F9F9", fill_type="solid")
                else:
                    cell.fill = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")
        
        current_row += 1
    
    # ===== PROFESSIONAL FOOTER =====
    ws.merge_cells(f'A{current_row}:H{current_row}')
    footer_cell = ws.cell(row=current_row, column=1)
    footer_cell.value = f"Total Records: {len(data)} | Generated: {datetime.now().strftime('%d %B %Y at %H:%M:%S')} | Powered by Transline Technologies"
    footer_cell.font = Font(name='Arial', italic=True, size=9, color="7F8C8D")
    footer_cell.alignment = Alignment(horizontal="center", vertical="center")
    footer_cell.fill = PatternFill(start_color="ECF0F1", end_color="ECF0F1", fill_type="solid")
    footer_cell.border = border_thick
    ws.row_dimensions[current_row].height = 25
    
    # Freeze header rows (title, date, headers)
    ws.freeze_panes = "A4"
    
    # Save to BytesIO buffer
    excel_buffer = io.BytesIO()
    wb.save(excel_buffer)
    excel_buffer.seek(0)
    
    return excel_buffer

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
    

@router.get("/similar-vehicles")
def get_similar_vehicles(
    plate: str,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user_id = current_user.user_id

    logger.info(
        f"Similar Vehicles API :: User:{user_id}({current_user.username}) :: "
        f"Co:{current_user.company_id} :: Role:{current_user.role} :: Plate:{plate}"
    )

    access_entries = db.query(TrnAccessControl).filter(
        TrnAccessControl.user_id == user_id,
        TrnAccessControl.disabled == False,
        TrnAccessControl.is_deleted == False
    ).all()

    if not access_entries:
        logger.warning(
            f"Similar Vehicles Request :: UserID -> {user_id} :: "
            "Reason -> No access control entries found"
        )
        return {
            100: [],
            75: [],
            50: [],
            25: []
        }

    access_info = utils.extract_accessible_locations_checkpoints(
        access_entries,
        db=db,
        company_id=current_user.company_id,
        role=current_user.role
    )
    location_ids = access_info["location_ids"]
    checkpoint_ids = access_info["checkpoint_ids"]

    logger.info(f"Similar Vehicles Access Control :: UserLocs:{location_ids} :: UserCPs:{checkpoint_ids}")

    buckets = {
        100: [],
        75: [],
        50: [],
        25: []
    }

    log_query = db.query(
        TrnVehicleLog,
        MstVehicle,
        MstLocation,
        MstCheckpoint
    ).join(
        MstVehicle,
        MstVehicle.vehicle_id == TrnVehicleLog.vehicle_id
    ).outerjoin(
        MstLocation,
        MstLocation.location_id == TrnVehicleLog.location_id
    ).outerjoin(
        MstCheckpoint,
        MstCheckpoint.checkpoint_id == cast(TrnVehicleLog.latest_data.op('->>')(text("'checkpoint_id'")), Integer)
    ).filter(
        MstVehicle.is_deleted == False,
        MstVehicle.disabled == False,
        TrnVehicleLog.last_seen != None
    )

    if location_ids is not None:
        if len(location_ids) == 0:
            return buckets
        log_query = log_query.filter(TrnVehicleLog.location_id.in_(location_ids))

    if checkpoint_ids is not None:
        if len(checkpoint_ids) == 0:
            return buckets
        log_query = log_query.filter(MstCheckpoint.checkpoint_id.in_(checkpoint_ids))

    authorized_logs = log_query.order_by(
        TrnVehicleLog.vehicle_id.asc(),
        desc(TrnVehicleLog.last_seen)
    ).all()

    latest_logs_by_vehicle = {}
    for log, vehicle, location, checkpoint in authorized_logs:
        if vehicle.vehicle_id not in latest_logs_by_vehicle:
            latest_logs_by_vehicle[vehicle.vehicle_id] = (log, vehicle, location, checkpoint)

    normalized_plate = plate.strip().upper()

    for log, vehicle, location, checkpoint in latest_logs_by_vehicle.values():
        raw_similarity = fuzz.ratio(normalized_plate, vehicle.plate_number)

        vehicle_data = {
            "plate_number": vehicle.plate_number,
            "similarity": raw_similarity,
            "vehicle_type": vehicle.vehicle_type,
            "location": location.location_name if location else None,
            "checkpoint": checkpoint.name if checkpoint else None,
            "last_seen": log.last_seen.isoformat() if log.last_seen else None
        }

        if raw_similarity >= 90:
            buckets[100].append(vehicle_data)
            buckets[75].append(vehicle_data)
            buckets[50].append(vehicle_data)
            buckets[25].append(vehicle_data)

        elif raw_similarity >= 75:
            buckets[75].append(vehicle_data)
            buckets[50].append(vehicle_data)
            buckets[25].append(vehicle_data)

        elif raw_similarity >= 50:
            buckets[50].append(vehicle_data)
            buckets[25].append(vehicle_data)

        elif raw_similarity >= 25:
            buckets[25].append(vehicle_data)

    for key in buckets:
        buckets[key].sort(key=lambda x: x["similarity"], reverse=True)

    return buckets
