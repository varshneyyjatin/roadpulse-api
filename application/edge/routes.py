"""
API routes for Edge Box configuration.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from datetime import datetime, timezone
from application.database.session import get_db
from application.edge.schemas import LocationSchema, CameraConfigSchema, CheckpointSchema, VehicleLookupRequest, EdgeBoxBlacklistInfoSchemaResponse, VehicleDetectionRequest, VehicleDetectionResponse
from application.edge import crud
from application.helpers.logger import get_logger
from application.auth.utils import verify_basic_auth

logger = get_logger("edge")
router = APIRouter(prefix="/edge", tags=["EdgeBox"])

@router.get("/box-config", response_model=List[LocationSchema])
def get_company_details_by_mac(
    mac_address: str, 
    db: Session = Depends(get_db),
    username: str = Depends(verify_basic_auth)
):
    """
    Retrieve complete edge box configuration by MAC address.
    
    Returns company details, location information, checkpoints, and camera configurations
    required for edge box initialization and operation.
    """
    try:
        logger.info(f"Box Config Request :: MAC -> {mac_address} :: User -> {username}")
        
        # Validate compute box exists
        compute_box = crud.get_compute_box_by_mac(db, mac_address)
        if not compute_box:
            logger.error(f"Box Config Failed :: MAC -> {mac_address} :: Error -> Compute box not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="Compute box not found"
            )

        # Validate associated location
        location = crud.get_location_by_id(db, compute_box.location_id)
        if not location:
            logger.error(f"Box Config Failed :: MAC -> {mac_address} :: BoxID -> {compute_box.box_id} :: Error -> Location not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="Location not found"
            )

        # Validate company ownership
        company = crud.get_company_by_id(db, location.company_id)
        if not company:
            logger.error(f"Box Config Failed :: MAC -> {mac_address} :: LocationID -> {location.location_id} :: Error -> Company not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="Company not found"
            )

        # Fetch checkpoints with associated cameras
        checkpoints = crud.get_checkpoints_with_cameras(
            db, 
            location.location_id, 
            compute_box.box_id
        )
        
        if not checkpoints:
            logger.error(f"Box Config Failed :: MAC -> {mac_address} :: LocationID -> {location.location_id} :: Error -> No checkpoints found")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
                detail="Default checkpoint not found for this location"
            )

        # Build response structure
        checkpoints_list = []
        all_timestamps = [
            compute_box.updated_at,
            location.updated_at,
            company.updated_at
        ]

        # Process each checkpoint and its cameras
        for checkpoint in checkpoints:
            cameras = [
                camera for camera in checkpoint.cameras 
                if camera.box_id == compute_box.box_id
            ]
            
            all_timestamps.append(checkpoint.updated_at)
            
            # Build camera configuration list
            camera_list = [
                CameraConfigSchema(
                    camera_id=camera.camera_id,
                    compute_box_id=camera.box_id,
                    camera_ip_add=camera.ip_address,
                    box_ip_add=compute_box.ip_address,
                    roi=camera.roi,
                    rtsp_url=camera.rtsp_url,
                    camera_name=camera.camera_name,
                    user_name=camera.username,
                    password=camera.password_hash
                )
                for camera in cameras
            ]
            
            # Collect camera timestamps
            all_timestamps.extend(camera.updated_at for camera in cameras)

            # Include only checkpoints with active cameras
            if camera_list:
                checkpoints_list.append(
                    CheckpointSchema(
                        checkpoint_name=checkpoint.name,
                        direction=checkpoint.direction,
                        checkpoint_id=checkpoint.checkpoint_id,
                        camera_config=camera_list
                    )
                )

        # Determine most recent update timestamp
        valid_timestamps = (ts for ts in all_timestamps if ts is not None)
        latest_updated_at = max(
            valid_timestamps,
            default=datetime.now(timezone.utc)
        )

        # Construct final response
        response = LocationSchema(
            company_id=company.id,
            location_id=location.location_id,
            location_name=location.location_name,
            company_name=company.name,
            checkpoints=checkpoints_list,
            latest_updated_at=latest_updated_at
        )
        
        logger.info(
            f"Box Config Success :: MAC -> {mac_address} :: "
            f"Company -> {company.name} :: Location -> {location.location_name} :: "
            f"Checkpoints -> {len(checkpoints_list)} :: Cameras -> {sum(len(cp.camera_config) for cp in checkpoints_list)}"
        )
        
        return [response]
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Box Config Failed :: MAC -> {mac_address} :: Error -> {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred"
        )

@router.post("/location/{device_id}")
def get_location_id(device_id: str, db: Session = Depends(get_db)):
    """
    Retrieve location and checkpoint information for a camera device.
    """
    from application.database.models.camera import MstCamera
    
    logger.info(f"Location Request :: DeviceID -> {device_id}")
    
    camera = db.query(MstCamera).filter(MstCamera.device_id == device_id).first()
    
    if not camera:
        logger.warning(f"Location Request Failed :: DeviceID -> {device_id} :: Reason -> Camera not found")
        raise HTTPException(status_code=404, detail="Camera not found")
    
    company_id = camera.location.company_id if camera.location else None
    
    logger.info(f"Location Request Success :: DeviceID -> {device_id} :: LocationID -> {camera.location_id} :: CheckpointID -> {camera.checkpoint_id} :: CompanyID -> {company_id}")
    
    return {
        "device_id": device_id,
        "location_id": camera.location_id,
        "checkpoint_id": camera.checkpoint_id,
        "company_id": company_id
    }

@router.post("/vehicle-detection", response_model=VehicleDetectionResponse)
async def vehicle_detection(payload: VehicleDetectionRequest, db: Session = Depends(get_db)):
    """
    Combined API for vehicle detection that handles:
    1. Vehicle creation/lookup
    2. Watchlist status check
    3. Vehicle log creation/update
    4. Notification sending (if blacklisted/whitelisted)

    """
    from application.database.models.vehicle import MstVehicle
    from application.database.models.watchlist import MstWatchlist
    from application.database.models.transactions.vehicle_log import TrnVehicleLog
    from application.database.models.checkpoint import MstCheckpoint
    from application.database.models.location import MstLocation
    from application.notification.utils import send_watchlist_alert
    from sqlalchemy.exc import SQLAlchemyError
    
    logger.info(f"Vehicle Detection :: PlateNumber -> {payload.plate_number} :: Timestamp -> {payload.timestamp}")
    
    try:
        # Step 1: Get or create vehicle
        plate_number = payload.plate_number.strip().upper()
        vehicle = db.query(MstVehicle).filter(MstVehicle.plate_number == plate_number).first()
        
        if not vehicle:
            vehicle = MstVehicle(
                plate_number=plate_number,
                vehicle_type=payload.vehicle_type,
                disabled=False
            )
            db.add(vehicle)
            db.commit()
            db.refresh(vehicle)
            logger.info(f"Vehicle Created :: PlateNumber -> {plate_number} :: VehicleID -> {vehicle.vehicle_id}")
        
        # Step 2: Check watchlist status
        watchlist_entry = db.query(MstWatchlist).filter(
            MstWatchlist.vehicle_id == vehicle.vehicle_id,
            MstWatchlist.is_deleted == False,
            MstWatchlist.disabled == False
        ).first()
        
        is_blacklisted = watchlist_entry.is_blacklisted if watchlist_entry else False
        is_whitelisted = watchlist_entry.is_whitelisted if watchlist_entry else False
        watchlist_id = watchlist_entry.id if watchlist_entry else None
        
        logger.info(f"Watchlist Check :: VehicleID -> {vehicle.vehicle_id} :: Blacklisted -> {is_blacklisted} :: Whitelisted -> {is_whitelisted}")
        
        # Step 3: Create or update vehicle log
        log_date = payload.timestamp.split(" ")[0]
        existing_log = (
            db.query(TrnVehicleLog)
            .filter(
                TrnVehicleLog.vehicle_id == vehicle.vehicle_id,
                func.date(TrnVehicleLog.first_seen) == log_date
            )
            .first()
        )
        
        # Add checkpoint_id to data if provided
        data_with_checkpoint = payload.data.copy()
        if payload.checkpoint_id:
            data_with_checkpoint["checkpoint_id"] = payload.checkpoint_id
        
        if existing_log:
            # Update existing log
            existing_log.history_data.append(data_with_checkpoint)
            existing_log.latest_data = data_with_checkpoint
            existing_log.last_seen = payload.timestamp
            existing_log.updated_by = "system_generated"
            existing_log.updated_at = datetime.utcnow()
            
            db.commit()
            db.refresh(existing_log)
            
            logger.info(f"Vehicle Log Updated :: VehicleID -> {vehicle.vehicle_id} :: LogID -> {existing_log.log_id}")
            log_id = existing_log.log_id
            log_status = "updated"
        else:
            # Create new log
            new_log = TrnVehicleLog(
                vehicle_id=vehicle.vehicle_id,
                driver_id=payload.driver_id,
                location_id=payload.location_id,
                timestamp=payload.timestamp,
                first_seen=payload.timestamp,
                last_seen=payload.timestamp,
                history_data=[data_with_checkpoint],
                latest_data=data_with_checkpoint,
                created_by="system_generated",
                updated_by="system_generated"
            )
            db.add(new_log)
            db.commit()
            db.refresh(new_log)
            
            logger.info(f"Vehicle Log Created :: VehicleID -> {vehicle.vehicle_id} :: LogID -> {new_log.log_id}")
            log_id = new_log.log_id
            log_status = "created"
        
        # Step 4: Send notification (only for new logs with watchlist entries)
        notification_sent = False
        notification_count = None
        
        if log_status == "created" and watchlist_entry and (is_blacklisted or is_whitelisted):
            # Get checkpoint and location details
            checkpoint_name = None
            company_id = None
            
            if payload.checkpoint_id:
                checkpoint = db.query(MstCheckpoint).filter(
                    MstCheckpoint.checkpoint_id == payload.checkpoint_id
                ).first()
                if checkpoint:
                    checkpoint_name = checkpoint.name
            
            location = db.query(MstLocation).filter(
                MstLocation.location_id == payload.location_id
            ).first()
            if location:
                company_id = location.company_id
            
            if company_id:
                try:
                    # Extract vehicle and plate images from data
                    picture_data = data_with_checkpoint.get("Picture", {})
                    vehicle_image = picture_data.get("VehiclePic", {}).get("Content")
                    plate_image = picture_data.get("CutoutPic", {}).get("Content")
                    
                    logger.info(
                        f"Image Extraction :: VehicleID -> {vehicle.vehicle_id} :: "
                        f"VehicleImage -> {vehicle_image} :: PlateImage -> {plate_image}"
                    )
                    
                    notification_count = send_watchlist_alert(
                        db=db,
                        company_id=company_id,
                        location_id=payload.location_id,
                        vehicle_id=vehicle.vehicle_id,
                        plate_number=vehicle.plate_number,
                        is_blacklisted=is_blacklisted,
                        is_whitelisted=is_whitelisted,
                        checkpoint_name=checkpoint_name,
                        timestamp=payload.timestamp,
                        vehicle_image=vehicle_image,
                        plate_image=plate_image,
                        vehicle_data=data_with_checkpoint
                    )
                    notification_sent = True
                    logger.info(
                        f"Notification Sent :: VehicleID -> {vehicle.vehicle_id} :: "
                        f"Count -> {notification_count}"
                    )
                except Exception as e:
                    logger.error(f"Notification Failed :: VehicleID -> {vehicle.vehicle_id} :: Error -> {str(e)}")
        
        # Return combined response
        return VehicleDetectionResponse(
            vehicle_id=vehicle.vehicle_id,
            plate_number=vehicle.plate_number,
            vehicle_type=vehicle.vehicle_type,
            is_blacklisted=is_blacklisted,
            is_whitelisted=is_whitelisted,
            watchlist_id=watchlist_id,
            log_status=log_status,
            log_id=log_id,
            notification_sent=notification_sent,
            notification_count=notification_count
        )
        
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Vehicle Detection Failed :: PlateNumber -> {payload.plate_number} :: Error -> {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except Exception as e:
        db.rollback()
        logger.error(f"Vehicle Detection Failed :: PlateNumber -> {payload.plate_number} :: Error -> {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")