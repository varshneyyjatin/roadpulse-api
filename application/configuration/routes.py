"""API routes for configuration."""
from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from application.database.session import get_db
from application.auth.utils import get_current_user
from application.configuration import crud, schemas
from application.helpers.logger import get_logger

logger = get_logger("configuration")
router = APIRouter(prefix="/configuration", tags=["Configuration"])

@router.post("/camera")
def upsert_camera(
    request: schemas.CameraUpsertRequest = Body(...),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create or update a camera.
    
    - If camera_id is provided: Updates existing camera
    - If camera_id is null: Creates new camera
    """
    user_id = current_user.user_id
    username = current_user.username
    
    operation = "Update" if request.camera_id else "Create"
    
    logger.info(
        f"Camera {operation} Request :: UserID -> {user_id} :: "
        f"Username -> {username} :: DeviceID -> {request.device_id}"
    )
    
    try:
        camera_data = request.model_dump()
        camera = crud.upsert_camera(db, camera_data, username)
        
        logger.info(
            f"Camera {operation} Success :: UserID -> {user_id} :: "
            f"CameraID -> {camera.camera_id} :: DeviceID -> {camera.device_id}"
        )
        
        return {
            "success": True,
            "message": f"Camera {operation.lower()}d successfully",
            "camera_id": camera.camera_id,
            "device_id": camera.device_id
        }
        
    except ValueError as e:
        logger.warning(
            f"Camera {operation} Failed :: UserID -> {user_id} :: "
            f"Reason -> {str(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(
            f"Camera {operation} Failed :: UserID -> {user_id} :: "
            f"Error -> {str(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to {operation.lower()} camera: {str(e)}"
        )

@router.post("/assigned-resources")
def get_assigned_resources(
    request: schemas.GetAssignedResourcesRequest = Body(...),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get assigned resources (cameras or checkpoints) based on user's access control.
    
    - scope=camera: Returns all cameras from user's assigned locations
    - scope=checkpoints: Returns all checkpoints from user's assigned locations
    """
    user_id = current_user.user_id
    username = current_user.username
    
    logger.info(
        f"Assigned Resources Request :: UserID -> {user_id} :: "
        f"Username -> {username} :: Scope -> {request.scope}"
    )
    
    try:
        # Get user's assigned locations from access control
        location_ids = crud.get_user_assigned_locations(db, user_id)
        
        if not location_ids:
            logger.warning(
                f"Assigned Resources :: UserID -> {user_id} :: "
                f"Reason -> No locations assigned"
            )
            return {
                "scope": request.scope,
                "total_locations": 0,
                "total_count": 0,
                "data": []
            }
        
        if request.scope == schemas.ScopeEnum.checkpoints:
            # Get checkpoints for assigned locations
            checkpoints = crud.get_checkpoints_by_locations(db, location_ids)
            
            result = []
            for checkpoint, location in checkpoints:
                result.append({
                    "checkpoint_id": checkpoint.checkpoint_id,
                    "checkpoint_name": checkpoint.name,
                    "location_id": location.location_id,
                    "location_name": location.location_name,
                    "checkpoint_type": checkpoint.checkpoint_type,
                    "direction": checkpoint.direction,
                    "sequence_order": checkpoint.sequence_order,
                    "latitude": float(checkpoint.latitude) if checkpoint.latitude else None,
                    "longitude": float(checkpoint.longitude) if checkpoint.longitude else None,
                    "disabled": checkpoint.disabled
                })
            
            logger.info(
                f"Assigned Resources Success :: UserID -> {user_id} :: "
                f"Scope -> checkpoints :: Locations -> {len(location_ids)} :: "
                f"Checkpoints -> {len(result)}"
            )
            
            return {
                "scope": request.scope,
                "total_locations": len(location_ids),
                "total_count": len(result),
                "data": result
            }
        
        elif request.scope == schemas.ScopeEnum.camera:
            # Get cameras for assigned locations
            cameras = crud.get_cameras_by_locations(db, location_ids)
            
            result = []
            for camera, checkpoint, location in cameras:
                result.append({
                    "camera_id": camera.camera_id,
                    "camera_name": camera.camera_name,
                    "device_id": camera.device_id,
                    "checkpoint_id": checkpoint.checkpoint_id if checkpoint else None,
                    "checkpoint_name": checkpoint.name if checkpoint else None,
                    "location_id": location.location_id,
                    "location_name": location.location_name,
                    "camera_type": camera.camera_type,
                    "camera_model": camera.camera_model,
                    "ip_address": camera.ip_address,
                    "username": camera.username,
                    "fps": camera.fps,
                    "deployment_type": camera.deployment_type,
                    "roi": camera.roi,
                    "loi": camera.loi,
                    "disabled": camera.disabled
                })
            
            logger.info(
                f"Assigned Resources Success :: UserID -> {user_id} :: "
                f"Scope -> camera :: Locations -> {len(location_ids)} :: "
                f"Cameras -> {len(result)}"
            )
            
            return {
                "scope": request.scope,
                "total_locations": len(location_ids),
                "total_count": len(result),
                "data": result
            }
        
    except Exception as e:
        logger.error(
            f"Assigned Resources Failed :: UserID -> {user_id} :: "
            f"Scope -> {request.scope} :: Error -> {str(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch assigned resources: {str(e)}"
        )