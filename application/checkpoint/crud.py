"""
CRUD operations for checkpoint management.
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from application.database.models.checkpoint import MstCheckpoint
from application.database.models.location import MstLocation

def get_company_checkpoints(db: Session, company_id: int):
    """
    Get all checkpoints for a company with location information.
    
    Args:
        db: Database session
        company_id: Company ID
        
    Returns:
        List of checkpoint query results with location info
    """
    checkpoints = db.query(
        MstCheckpoint.checkpoint_id,
        MstCheckpoint.name.label("checkpoint_name"),
        MstCheckpoint.checkpoint_type,
        MstCheckpoint.direction,
        MstCheckpoint.sequence_order,
        MstLocation.location_name
    ).join(
        MstLocation, MstCheckpoint.location_id == MstLocation.location_id
    ).filter(
        MstLocation.company_id == company_id,
        MstCheckpoint.disabled == False,
        MstCheckpoint.is_deleted == False,
        MstLocation.disabled == False,
        MstLocation.is_deleted == False
    ).order_by(
        MstLocation.location_name,
        MstCheckpoint.sequence_order
    ).all()
    
    return checkpoints

def get_checkpoints_by_ids(db: Session, checkpoint_ids: List[int]):
    """
    Get checkpoints by their IDs with location and company info.
    
    Args:
        db: Database session
        checkpoint_ids: List of checkpoint IDs
        
    Returns:
        List of checkpoint query results
    """
    checkpoints = db.query(
        MstCheckpoint.checkpoint_id,
        MstCheckpoint.location_id,
        MstLocation.company_id
    ).join(
        MstLocation, MstCheckpoint.location_id == MstLocation.location_id
    ).filter(
        MstCheckpoint.checkpoint_id.in_(checkpoint_ids),
        MstCheckpoint.disabled == False,
        MstCheckpoint.is_deleted == False
    ).all()
    
    return checkpoints

def update_checkpoint(
    db: Session, 
    checkpoint_id: int, 
    checkpoint_name: Optional[str] = None,
    checkpoint_type: Optional[str] = None,
    direction: Optional[str] = None,
    sequence_order: Optional[int] = None,
    updated_by: str = None
) -> Optional[MstCheckpoint]:
    """
    Update checkpoint details (name, type, direction, sequence order) - Manager access.
    
    Args:
        db: Database session
        checkpoint_id: Checkpoint ID
        checkpoint_name: New checkpoint name (optional)
        checkpoint_type: New checkpoint type (optional)
        direction: New direction (optional)
        sequence_order: New sequence order (optional)
        updated_by: Username of user making the update
        
    Returns:
        Updated checkpoint object or None
    """
    checkpoint = db.query(MstCheckpoint).filter(
        MstCheckpoint.checkpoint_id == checkpoint_id
    ).first()
    
    if checkpoint:
        if checkpoint_name is not None:
            checkpoint.name = checkpoint_name
        if checkpoint_type is not None:
            checkpoint.checkpoint_type = checkpoint_type
        if direction is not None:
            checkpoint.direction = direction
        if sequence_order is not None:
            checkpoint.sequence_order = sequence_order
        if updated_by is not None:
            checkpoint.updated_by = updated_by
        return checkpoint
    
    return None

def update_checkpoint_full(
    db: Session,
    checkpoint_id: int,
    location_id: Optional[int] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    checkpoint_name: Optional[str] = None,
    checkpoint_type: Optional[str] = None,
    direction: Optional[str] = None,
    sequence_order: Optional[int] = None,
    disabled: Optional[bool] = None,
    updated_by: str = None
) -> Optional[MstCheckpoint]:
    """
    Full update checkpoint details - Creator access.
    
    Args:
        db: Database session
        checkpoint_id: Checkpoint ID
        location_id: New location ID (optional)
        latitude: New latitude (optional)
        longitude: New longitude (optional)
        checkpoint_name: New checkpoint name (optional)
        checkpoint_type: New checkpoint type (optional)
        direction: New direction (optional)
        sequence_order: New sequence order (optional)
        disabled: New disabled status (optional)
        updated_by: Username of user making the update
        
    Returns:
        Updated checkpoint object or None
    """
    checkpoint = db.query(MstCheckpoint).filter(
        MstCheckpoint.checkpoint_id == checkpoint_id
    ).first()
    
    if checkpoint:
        if location_id is not None:
            checkpoint.location_id = location_id
        if latitude is not None:
            checkpoint.latitude = latitude
        if longitude is not None:
            checkpoint.longitude = longitude
        if checkpoint_name is not None:
            checkpoint.name = checkpoint_name
        if checkpoint_type is not None:
            checkpoint.checkpoint_type = checkpoint_type
        if direction is not None:
            checkpoint.direction = direction
        if sequence_order is not None:
            checkpoint.sequence_order = sequence_order
        if disabled is not None:
            checkpoint.disabled = disabled
        if updated_by is not None:
            checkpoint.updated_by = updated_by
        return checkpoint
    
    return None


def check_sequence_exists(db: Session, location_id: int, sequence_order: int, exclude_checkpoint_id: int = None) -> bool:
    """
    Check if a sequence order already exists for a location.
    
    Args:
        db: Database session
        location_id: Location ID
        sequence_order: Sequence order to check
        exclude_checkpoint_id: Checkpoint ID to exclude from check (for updates)
        
    Returns:
        True if sequence exists, False otherwise
    """
    query = db.query(MstCheckpoint).filter(
        MstCheckpoint.location_id == location_id,
        MstCheckpoint.sequence_order == sequence_order,
        MstCheckpoint.disabled == False,
        MstCheckpoint.is_deleted == False
    )
    
    if exclude_checkpoint_id:
        query = query.filter(MstCheckpoint.checkpoint_id != exclude_checkpoint_id)
    
    return query.first() is not None

def get_checkpoint_with_location(db: Session, checkpoint_id: int):
    """
    Get checkpoint with location and company info.
    
    Args:
        db: Database session
        checkpoint_id: Checkpoint ID
        
    Returns:
        Checkpoint query result with location info
    """
    checkpoint = db.query(
        MstCheckpoint.checkpoint_id,
        MstCheckpoint.location_id,
        MstLocation.company_id
    ).join(
        MstLocation, MstCheckpoint.location_id == MstLocation.location_id
    ).filter(
        MstCheckpoint.checkpoint_id == checkpoint_id,
        MstCheckpoint.disabled == False,
        MstCheckpoint.is_deleted == False,
        MstLocation.disabled == False,
        MstLocation.is_deleted == False
    ).first()
    
    return checkpoint


def get_location_checkpoint_count(db: Session, location_id: int) -> int:
    """
    Get total count of active checkpoints in a location.
    
    Args:
        db: Database session
        location_id: Location ID
        
    Returns:
        Count of checkpoints
    """
    count = db.query(MstCheckpoint).filter(
        MstCheckpoint.location_id == location_id,
        MstCheckpoint.disabled == False,
        MstCheckpoint.is_deleted == False
    ).count()
    
    return count
