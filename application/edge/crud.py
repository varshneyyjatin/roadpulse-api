"""
CRUD operations for Edge Box configuration.
"""
from sqlalchemy.orm import Session, joinedload
from typing import Optional, List
from application.database.models.compute_box import MstComputeBox
from application.database.models.location import MstLocation
from application.database.models.company import MstCompany
from application.database.models.checkpoint import MstCheckpoint
from application.database.models.camera import MstCamera

def get_compute_box_by_mac(db: Session, mac_address: str) -> Optional[MstComputeBox]:
    """Retrieve compute box by MAC address."""
    return (
        db.query(MstComputeBox)
        .filter(MstComputeBox.mac_address == mac_address)
        .first()
    )

def get_location_by_id(db: Session, location_id: int) -> Optional[MstLocation]:
    """Retrieve location by primary key."""
    return (
        db.query(MstLocation)
        .filter(MstLocation.location_id == location_id)
        .first()
    )

def get_company_by_id(db: Session, company_id: int) -> Optional[MstCompany]:
    """Retrieve company by primary key."""
    return (
        db.query(MstCompany)
        .filter(MstCompany.id == company_id)
        .first()
    )

def get_checkpoints_with_cameras(
    db: Session, 
    location_id: int, 
    box_id: int
) -> List[MstCheckpoint]:
    """
    Retrieve all checkpoints for a location with associated cameras.
    
    Uses eager loading to fetch related cameras in a single query,
    preventing N+1 query issues. Only loads required camera fields.
    """
    return (
        db.query(MstCheckpoint)
        .filter(MstCheckpoint.location_id == location_id)
        .options(
            joinedload(MstCheckpoint.cameras).load_only(
                MstCamera.camera_id,
                MstCamera.box_id,
                MstCamera.ip_address,
                MstCamera.roi,
                MstCamera.camera_name,
                MstCamera.username,
                MstCamera.password_hash,
                MstCamera.updated_at
            )
        )
        .all()
    )

def get_cameras_by_checkpoint_and_box(
    db: Session, 
    checkpoint_id: int, 
    box_id: int
) -> List[MstCamera]:
    """Retrieve cameras for a specific checkpoint and compute box."""
    return (
        db.query(MstCamera)
        .filter(
            MstCamera.checkpoint_id == checkpoint_id,
            MstCamera.box_id == box_id
        )
        .all()
    )
