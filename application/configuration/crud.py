"""CRUD operations for configuration."""
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_
from application.database.models.transactions.access_control import TrnAccessControl
from application.database.models.camera import MstCamera
from application.database.models.checkpoint import MstCheckpoint
from application.database.models.location import MstLocation


def get_user_assigned_locations(db: Session, user_id: int, company_id: int, role: str) -> List[int]:
    """
    Get all location IDs assigned to a user from access control.
    
    Args:
        db: Database session
        user_id: User ID
        company_id: User's company ID
        role: User's role
        
    Returns:
        List of location IDs (empty list if no access, or all locations if NULL access_data)
    """
    import json
    
    # Get location access control entries
    location_accesses = db.query(TrnAccessControl).filter(
        and_(
            TrnAccessControl.user_id == user_id,
            TrnAccessControl.access_type == 'location',
            TrnAccessControl.disabled == False,
            TrnAccessControl.is_deleted == False
        )
    ).all()
    
    if not location_accesses:
        return []
    
    # Check if user has access to ALL locations (NULL access_data)
    for access in location_accesses:
        if access.access_data is None:
            # NULL means ALL locations - but filter by company for non-creator roles
            query = db.query(MstLocation.location_id).filter(
                and_(
                    MstLocation.disabled == False,
                    MstLocation.is_deleted == False
                )
            )
            
            # Non-creator roles see only their company's locations
            if role != 'creator':
                query = query.filter(MstLocation.company_id == company_id)
            
            all_locations = query.all()
            return [loc[0] for loc in all_locations]
    
    # Extract specific location IDs from JSON
    location_ids = []
    for access in location_accesses:
        if access.access_data:
            try:
                data = json.loads(access.access_data)
                ids = data.get('access_ids', [])
                location_ids.extend(ids)
            except:
                continue
    
    # Filter location IDs by company for non-creator roles
    if location_ids and role != 'creator':
        valid_locations = db.query(MstLocation.location_id).filter(
            and_(
                MstLocation.location_id.in_(location_ids),
                MstLocation.company_id == company_id,
                MstLocation.disabled == False,
                MstLocation.is_deleted == False
            )
        ).all()
        location_ids = [loc[0] for loc in valid_locations]
    
    return list(set(location_ids))  # Remove duplicates


def get_checkpoints_by_locations(db: Session, location_ids: List[int]) -> List[tuple]:
    """
    Get all checkpoints for given locations with location details.
    
    Args:
        db: Database session
        location_ids: List of location IDs
        
    Returns:
        List of (checkpoint, location) tuples
    """
    checkpoints = db.query(
        MstCheckpoint,
        MstLocation
    ).join(
        MstLocation, MstCheckpoint.location_id == MstLocation.location_id
    ).filter(
        and_(
            MstCheckpoint.location_id.in_(location_ids),
            MstCheckpoint.is_deleted == False
        )
    ).order_by(
        MstLocation.location_name,
        MstCheckpoint.sequence_order,
        MstCheckpoint.name
    ).all()
    
    return checkpoints


def get_cameras_by_locations(db: Session, location_ids: List[int]) -> List[tuple]:
    """
    Get all cameras for given locations with checkpoint and location details.
    
    Args:
        db: Database session
        location_ids: List of location IDs
        
    Returns:
        List of (camera, checkpoint, location) tuples
    """
    cameras = db.query(
        MstCamera,
        MstCheckpoint,
        MstLocation
    ).outerjoin(
        MstCheckpoint, MstCamera.checkpoint_id == MstCheckpoint.checkpoint_id
    ).join(
        MstLocation, MstCamera.location_id == MstLocation.location_id
    ).filter(
        and_(
            MstCamera.location_id.in_(location_ids),
            MstCamera.is_deleted == False
        )
    ).order_by(
        MstLocation.location_name,
        MstCheckpoint.name,
        MstCamera.camera_name
    ).all()
    
    return cameras


def upsert_camera(db: Session, camera_data: Dict[str, Any], username: str) -> MstCamera:
    """
    Create or update a camera.
    Either device_id or box_id must be provided (mutually exclusive).
    
    Args:
        db: Database session
        camera_data: Camera data dictionary
        username: Username performing the operation
        
    Returns:
        Created or updated camera object
    """
    camera_id = camera_data.get('camera_id')
    device_id = camera_data.get('device_id')
    box_id = camera_data.get('box_id')
    
    # Set deployment_type based on device_id or box_id
    if box_id:
        camera_data['deployment_type'] = 'Box Solution'
        # Generate device_id from box_id
        device_id = f"box_{box_id}"
        camera_data['device_id'] = device_id
    elif device_id:
        camera_data['deployment_type'] = 'Camera Solution'
    
    if camera_id:
        # Update existing camera
        camera = db.query(MstCamera).filter(
            and_(
                MstCamera.camera_id == camera_id,
                MstCamera.is_deleted == False
            )
        ).first()
        
        if not camera:
            raise ValueError(f"Camera with ID {camera_id} not found")
        
        # Check if device_id is being changed and if new device_id already exists
        if device_id and device_id != camera.device_id:
            existing_device = db.query(MstCamera).filter(
                and_(
                    MstCamera.device_id == device_id,
                    MstCamera.camera_id != camera_id,
                    MstCamera.is_deleted == False
                )
            ).first()
            
            if existing_device:
                raise ValueError(f"Camera with device_id {device_id} already exists")
        
        # Update fields
        for key, value in camera_data.items():
            if key == 'camera_id':
                continue
            if key == 'password' and value:
                # Store password as plain text in password_hash field
                camera.password_hash = value
            elif hasattr(camera, key):
                setattr(camera, key, value)
        
        camera.updated_by = username
        
    else:
        # Create new camera
        # Check if device_id already exists
        existing = db.query(MstCamera).filter(
            and_(
                MstCamera.device_id == device_id,
                MstCamera.is_deleted == False
            )
        ).first()
        
        if existing:
            raise ValueError(f"Camera with device_id {device_id} already exists")
        
        # Store password as plain text
        password_hash = camera_data.get('password')
        
        camera = MstCamera(
            device_id=device_id,
            camera_name=camera_data.get('camera_name'),
            checkpoint_id=camera_data.get('checkpoint_id'),
            location_id=camera_data['location_id'],
            box_id=box_id,
            camera_type=camera_data.get('camera_type'),
            camera_model=camera_data.get('camera_model'),
            fps=camera_data.get('fps'),
            ip_address=camera_data.get('ip_address'),
            username=camera_data.get('username'),
            password_hash=password_hash,
            roi=camera_data.get('roi'),
            loi=camera_data.get('loi'),
            deployment_type=camera_data['deployment_type'],
            disabled=camera_data.get('disabled', False),
            remarks=camera_data.get('remarks'),
            created_by=username,
            updated_by=username
        )
        db.add(camera)
    
    db.commit()
    db.refresh(camera)
    return camera
