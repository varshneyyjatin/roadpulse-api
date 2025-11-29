"""
API routes for checkpoint management.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from application.database.session import get_db
from application.auth.utils import get_current_user
from application.checkpoint import crud, utils
from application.checkpoint.schemas import CheckpointUpdate, CheckpointFullUpdate
from typing import Union
from application.database.models.checkpoint import MstCheckpoint
from application.database.models.location import MstLocation
from application.database.models.company import MstCompany
from application.helpers.logger import get_logger

logger = get_logger("checkpoint")
router = APIRouter(prefix="/checkpoints", tags=["Checkpoints"])

@router.get("/configurations")
def get_checkpoints_configurations(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get checkpoints configurations.
    - Manager: Can view only their company's checkpoints (limited fields)
    - Creator: Can view all companies' checkpoints (all fields)
    """
    # Check if user has manager or creator role
    if current_user.role not in ["manager", "creator"]:
        logger.warning(f"Access Denied :: UserID -> {current_user.user_id} :: Username -> {current_user.username} :: Role -> {current_user.role} :: Reason -> Not a manager or creator")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Only managers and creators can view checkpoints."
        )
    
    # Creator can see all companies, Manager only their company
    if current_user.role == "creator":
        # Get all checkpoints for creator
        checkpoints = db.query(
            MstCheckpoint.checkpoint_id,
            MstCheckpoint.name.label("checkpoint_name"),
            MstCheckpoint.description,
            MstCheckpoint.sequence_order,
            MstCheckpoint.checkpoint_type,
            MstCheckpoint.direction,
            MstCheckpoint.latitude,
            MstCheckpoint.longitude,
            MstCheckpoint.disabled,
            MstLocation.location_id,
            MstLocation.location_name,
            MstCompany.id.label("company_id"),
            MstCompany.name.label("company_name")
        ).join(
            MstLocation, MstCheckpoint.location_id == MstLocation.location_id
        ).join(
            MstCompany, MstLocation.company_id == MstCompany.id
        ).filter(
            MstCheckpoint.is_deleted == False,
            MstLocation.is_deleted == False
        ).order_by(
            MstCompany.name,
            MstLocation.location_name,
            MstCheckpoint.sequence_order
        ).all()
        
        # Group by company and location for creator
        from collections import defaultdict
        company_map = defaultdict(lambda: defaultdict(list))
        
        for cp in checkpoints:
            company_map[cp.company_name][cp.location_name].append({
                "checkpoint_id": cp.checkpoint_id,
                "checkpoint_name": cp.checkpoint_name,
                "description": cp.description,
                "sequence_order": cp.sequence_order,
                "checkpoint_type": cp.checkpoint_type,
                "direction": cp.direction,
                "latitude": float(cp.latitude) if cp.latitude else None,
                "longitude": float(cp.longitude) if cp.longitude else None,
                "disabled": cp.disabled,
                "location_id": cp.location_id
            })
        
        result = []
        for company_name, locations in company_map.items():
            company_locations = []
            for location_name, checkpoints_list in locations.items():
                company_locations.append({
                    "location_name": location_name,
                    "checkpoint_count": len(checkpoints_list),
                    "checkpoints": checkpoints_list
                })
            result.append({
                "company_name": company_name,
                "locations": company_locations
            })
        
        total_checkpoints = sum(
            loc["checkpoint_count"] 
            for company in result 
            for loc in company["locations"]
        )
        
        logger.info(f"All Checkpoints Fetched :: UserID -> {current_user.user_id} :: Username -> {current_user.username} :: Role -> creator :: Companies -> {len(result)} :: Total Checkpoints -> {total_checkpoints}")
        
        return {
            "role": "creator",
            "total_companies": len(result),
            "total_checkpoints": total_checkpoints,
            "companies": result
        }
    
    else:  # Manager
        company_id = current_user.company_id
        
        # Get checkpoints from database
        checkpoints = crud.get_company_checkpoints(db, company_id)
        
        # Group checkpoints by location
        result = utils.group_checkpoints_by_location(checkpoints)
        total_checkpoints = sum(loc["checkpoint_count"] for loc in result)
        
        logger.info(f"Company Checkpoints Fetched :: UserID -> {current_user.user_id} :: Username -> {current_user.username} :: CompanyID -> {company_id} :: Locations -> {len(result)} :: Total Checkpoints -> {total_checkpoints}")
        
        return {
            "role": "manager",
            "company_id": company_id,
            "total_locations": len(result),
            "total_checkpoints": total_checkpoints,
            "locations": result
        }

@router.put("/configurations/{checkpoint_id}")
def update_checkpoint_config(
    checkpoint_id: int,
    payload: Union[CheckpointUpdate, CheckpointFullUpdate],
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update checkpoint details.
    - Manager: Can update only their company's checkpoints (name, description, sequence)
    - Creator: Can update all checkpoints (all fields)
    """
    # Check if user has manager or creator role
    if current_user.role not in ["manager", "creator"]:
        logger.warning(f"Access Denied :: UserID -> {current_user.user_id} :: Username -> {current_user.username} :: Role -> {current_user.role} :: Reason -> Not a manager or creator")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Only managers and creators can update checkpoints."
        )
    
    # Fetch checkpoint with location info
    checkpoint_info = crud.get_checkpoint_with_location(db, checkpoint_id)
    
    if not checkpoint_info:
        logger.warning(f"Update Failed :: UserID -> {current_user.user_id} :: CheckpointID -> {checkpoint_id} :: Reason -> Checkpoint not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Checkpoint not found"
        )
    
    # Manager can only update their company's checkpoints
    if current_user.role == "manager":
        company_id = current_user.company_id
        if checkpoint_info.company_id != company_id:
            logger.warning(f"Access Denied :: UserID -> {current_user.user_id} :: CheckpointID -> {checkpoint_id} :: Reason -> Checkpoint belongs to different company")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Checkpoint does not belong to your company"
            )
    
    # Validate sequence order if provided
    if payload.sequence_order is not None:
        # Get total checkpoint count in location
        total_checkpoints = crud.get_location_checkpoint_count(db, checkpoint_info.location_id)
        
        # Check if sequence is within valid range
        if payload.sequence_order > total_checkpoints:
            logger.warning(f"Update Failed :: UserID -> {current_user.user_id} :: CheckpointID -> {checkpoint_id} :: LocationID -> {checkpoint_info.location_id} :: Sequence -> {payload.sequence_order} :: TotalCheckpoints -> {total_checkpoints} :: Reason -> Sequence exceeds checkpoint count")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Sequence order cannot be {payload.sequence_order}. This location has only {total_checkpoints} checkpoints. Valid range: 1-{total_checkpoints}"
            )
        
        # Check if sequence already exists
        sequence_exists = crud.check_sequence_exists(
            db, 
            checkpoint_info.location_id, 
            payload.sequence_order,
            exclude_checkpoint_id=checkpoint_id
        )
        
        if sequence_exists:
            logger.warning(f"Update Failed :: UserID -> {current_user.user_id} :: CheckpointID -> {checkpoint_id} :: LocationID -> {checkpoint_info.location_id} :: Sequence -> {payload.sequence_order} :: Reason -> Sequence already exists")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Sequence order {payload.sequence_order} already exists for another checkpoint in this location"
            )
    
    # Update checkpoint based on role
    if current_user.role == "creator":
        # Creator can update all fields
        updated_checkpoint = crud.update_checkpoint_full(
            db,
            checkpoint_id=checkpoint_id,
            location_id=getattr(payload, 'location_id', None),
            latitude=getattr(payload, 'latitude', None),
            longitude=getattr(payload, 'longitude', None),
            checkpoint_name=getattr(payload, 'checkpoint_name', None),
            description=getattr(payload, 'description', None),
            checkpoint_type=getattr(payload, 'checkpoint_type', None),
            direction=getattr(payload, 'direction', None),
            sequence_order=getattr(payload, 'sequence_order', None),
            disabled=getattr(payload, 'disabled', None),
            updated_by=current_user.username
        )
    else:  # Manager
        # Manager can only update limited fields
        updated_checkpoint = crud.update_checkpoint(
            db,
            checkpoint_id=checkpoint_id,
            checkpoint_name=payload.checkpoint_name,
            description=payload.description,
            sequence_order=payload.sequence_order,
            updated_by=current_user.username
        )
    
    if not updated_checkpoint:
        logger.error(f"Update Failed :: UserID -> {current_user.user_id} :: CheckpointID -> {checkpoint_id} :: Reason -> Update operation failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update checkpoint"
        )
    
    db.commit()
    
    logger.info(f"Checkpoint Updated :: UserID -> {current_user.user_id} :: Username -> {current_user.username} :: Role -> {current_user.role} :: CheckpointID -> {checkpoint_id}")
    
    return {
        "message": "Checkpoint updated successfully",
        "checkpoint_id": checkpoint_id,
        "role": current_user.role
    }