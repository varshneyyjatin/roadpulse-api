"""API routes for watchlist."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from application.database.session import get_db
from application.auth.utils import get_current_user
from application.watchlist import crud, utils, schemas
from application.database.models.transactions.access_control import TrnAccessControl
from application.helpers.logger import get_logger

logger = get_logger("watchlist")
router = APIRouter(prefix="/watchlist", tags=["Watchlist"])

@router.get("/")
def get_watchlist(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get watchlist entries based on user's access control.
    
    Returns watchlist for vehicles seen in locations and checkpoints that the user has access to.
    """
    user_id = current_user.user_id
    logger.info(f"Watchlist Request :: UserID -> {user_id} :: Username -> {current_user.username}")
    
    # Get user's access control entries
    access_entries = db.query(TrnAccessControl).filter(
        TrnAccessControl.user_id == user_id,
        TrnAccessControl.disabled == False,
        TrnAccessControl.is_deleted == False
    ).all()
    
    if not access_entries:
        logger.warning(f"Watchlist Request :: UserID -> {user_id} :: Reason -> No access control entries found")
        return {
            "message": "No Data Available",
            "data": []
        }
    
    # Extract accessible locations and checkpoints
    # Pass db, company_id, and role for company filtering
    access_info = utils.extract_accessible_locations_checkpoints(
        access_entries,
        db=db,
        company_id=current_user.company_id,
        role=current_user.role
    )
    location_ids = access_info["location_ids"]
    checkpoint_ids = access_info["checkpoint_ids"]
    
    logger.info(f"Watchlist Access :: UserID -> {user_id} :: CompanyID -> {current_user.company_id} :: LocationIDs -> {location_ids} :: CheckpointIDs -> {checkpoint_ids}")
    
    # Get watchlist entries - filter by company for non-creator roles
    if current_user.role == 'creator':
        # Creator can see all companies
        watchlist_entries = crud.get_watchlist_by_access(
            db,
            company_id=None,  # All companies
            location_ids=location_ids,
            checkpoint_ids=checkpoint_ids
        )
    else:
        # Other roles see only their company
        watchlist_entries = crud.get_watchlist_by_access(
            db,
            company_id=current_user.company_id,
            location_ids=location_ids,
            checkpoint_ids=checkpoint_ids
        )
    
    # Format response
    result = []
    for entry in watchlist_entries:
        result.append({
            "id": entry.id,
            "vehicle_id": entry.vehicle_id,
            "plate_number": entry.plate_number,
            "company_id": entry.company_id,
            "reason": entry.reason,
            "is_blacklisted": entry.is_blacklisted if entry.is_blacklisted else False,
            "is_whitelisted": entry.is_whitelisted if entry.is_whitelisted else False,
            "disabled": entry.disabled if entry.disabled else False,
            "is_deleted": entry.is_deleted if entry.is_deleted else False,
            "operation_data": entry.operation_data if entry.operation_data else []
        })
    
    logger.info(f"Watchlist Response :: UserID -> {user_id} :: TotalEntries -> {len(result)}")
    
    if not result:
        return {
            "message": "No Data Available",
            "data": []
        }
    
    return {
        "message": "Success",
        "data": result
    }

@router.post("/")
def add_to_watchlist(
    request: schemas.AddWatchlistRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Add a vehicle to watchlist with complete operation history tracking.
    
    Tracks all operations in operation_data JSON field:
    - Who added the vehicle
    - When it was added
    - Reason for adding
    - Status changes (blacklist/whitelist)
    """
    from application.database.models.watchlist import MstWatchlist
    from application.database.models.vehicle import MstVehicle
    from datetime import datetime, timedelta, timezone
    
    user_id = current_user.user_id
    username = current_user.username
    company_id = current_user.company_id
    
    # Validate: Either vehicle_id or plate_number must be provided
    if not request.vehicle_id and not request.plate_number:
        logger.warning(f"Add Watchlist Failed :: UserID -> {user_id} :: Reason -> Neither vehicle_id nor plate_number provided")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either vehicle_id or plate_number must be provided"
        )
    
    logger.info(f"Add Watchlist Request :: UserID -> {user_id} :: Username -> {username} :: VehicleID -> {request.vehicle_id} :: PlateNumber -> {request.plate_number} :: Reason -> {request.reason}")
    
    # Determine vehicle_id
    vehicle = None
    vehicle_created = False
    
    if request.vehicle_id:
        # Vehicle ID provided - get vehicle
        vehicle = db.query(MstVehicle).filter(MstVehicle.vehicle_id == request.vehicle_id).first()
        if not vehicle:
            logger.warning(f"Add Watchlist Failed :: UserID -> {user_id} :: Reason -> Vehicle not found :: VehicleID -> {request.vehicle_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Vehicle not found"
            )
    
    elif request.plate_number:
        # Plate number provided - check if vehicle exists
        plate_number_upper = request.plate_number.strip().upper()
        vehicle = db.query(MstVehicle).filter(MstVehicle.plate_number == plate_number_upper).first()
        
        if not vehicle:
            # Vehicle doesn't exist - create new vehicle with type "Blacklisted"
            try:
                vehicle = MstVehicle(
                    plate_number=plate_number_upper,
                    vehicle_type="Blacklisted",
                    disabled=False
                )
                db.add(vehicle)
                db.flush()  # Get vehicle_id without committing
                vehicle_created = True
                logger.info(f"Vehicle Created :: PlateNumber -> {plate_number_upper} :: VehicleID -> {vehicle.vehicle_id} :: VehicleType -> Blacklisted")
            except Exception as e:
                db.rollback()
                logger.error(f"Vehicle Creation Failed :: UserID -> {user_id} :: PlateNumber -> {plate_number_upper} :: Error -> {str(e)}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to create vehicle: {str(e)}"
                )
        else:
            logger.info(f"Vehicle Found :: PlateNumber -> {plate_number_upper} :: VehicleID -> {vehicle.vehicle_id}")
    
    # Check if vehicle already in watchlist for this company (active entry)
    existing_entry = db.query(MstWatchlist).filter(
        MstWatchlist.vehicle_id == vehicle.vehicle_id,
        MstWatchlist.company_id == company_id,
        MstWatchlist.is_deleted == False
    ).first()
    
    # Get Indian Standard Time
    ist = timezone(timedelta(hours=5, minutes=30))
    current_time_ist = datetime.now(ist).strftime("%Y-%m-%d %H:%M:%S")
    
    if existing_entry:
        # Vehicle already exists - update operation_data
        logger.info(f"Watchlist Entry Exists :: WatchlistID -> {existing_entry.id} :: Updating operation_data")
        
        # Get existing operation_data or initialize
        operation_data = existing_entry.operation_data if existing_entry.operation_data else []
        
        # Add new operation
        operation_number = len(operation_data) + 1
        operation_data.append({
            "operation_number": operation_number,
            "action": "updated",
            "added_by": username,
            "added_date": current_time_ist,
            "reason": request.reason,
            "is_blacklisted": request.is_blacklisted,
            "is_whitelisted": request.is_whitelisted,
            "removed_date": None,
            "removed_by": None
        })
        
        # Update entry
        existing_entry.reason = request.reason
        existing_entry.is_blacklisted = request.is_blacklisted
        existing_entry.is_whitelisted = request.is_whitelisted
        existing_entry.operation_data = operation_data
        
        # Mark as modified to trigger SQLAlchemy update
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(existing_entry, "operation_data")
        
        db.commit()
        db.refresh(existing_entry)
        
        logger.info(f"Watchlist Updated :: WatchlistID -> {existing_entry.id} :: VehicleID -> {request.vehicle_id} :: OperationNumber -> {operation_number}")
        
        return {
            "success": True,
            "message": "Watchlist entry updated successfully",
            "vehicle_created": vehicle_created,
            "data": {
                "id": existing_entry.id,
                "vehicle_id": existing_entry.vehicle_id,
                "plate_number": vehicle.plate_number,
                "company_id": existing_entry.company_id,
                "reason": existing_entry.reason,
                "is_blacklisted": existing_entry.is_blacklisted,
                "is_whitelisted": existing_entry.is_whitelisted,
                "operation_data": existing_entry.operation_data
            }
        }
    
    else:
        # Create new watchlist entry
        operation_data = [{
            "operation_number": 1,
            "action": "added",
            "added_by": username,
            "added_date": current_time_ist,
            "reason": request.reason,
            "is_blacklisted": request.is_blacklisted,
            "is_whitelisted": request.is_whitelisted,
            "removed_date": None,
            "removed_by": None
        }]
        
        new_entry = MstWatchlist(
            vehicle_id=vehicle.vehicle_id,
            company_id=company_id,
            reason=request.reason,
            is_blacklisted=request.is_blacklisted,
            is_whitelisted=request.is_whitelisted,
            operation_data=operation_data,
            disabled=False,
            is_deleted=False
        )
        
        db.add(new_entry)
        db.commit()
        db.refresh(new_entry)
        
        logger.info(f"Watchlist Created :: WatchlistID -> {new_entry.id} :: VehicleID -> {vehicle.vehicle_id} :: AddedBy -> {username}")
        
        return {
            "success": True,
            "message": "Vehicle added to watchlist successfully",
            "vehicle_created": vehicle_created,
            "data": {
                "id": new_entry.id,
                "vehicle_id": new_entry.vehicle_id,
                "plate_number": vehicle.plate_number,
                "company_id": new_entry.company_id,
                "reason": new_entry.reason,
                "is_blacklisted": new_entry.is_blacklisted,
                "is_whitelisted": new_entry.is_whitelisted,
                "operation_data": new_entry.operation_data
            }
        }