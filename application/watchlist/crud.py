"""CRUD operations for watchlist."""
from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from application.database.models.watchlist import MstWatchlist
from application.database.models.vehicle import MstVehicle
from application.database.models.transactions.vehicle_log import TrnVehicleLog


def get_watchlist_by_access(
    db: Session,
    company_id: int,
    location_ids: Optional[List[int]] = None,
    checkpoint_ids: Optional[List[int]] = None
):
    """
    Get watchlist entries for a company.
    
    Args:
        db: Database session
        company_id: Company ID to filter watchlist
        location_ids: List of accessible location IDs (not used for filtering, kept for future)
        checkpoint_ids: List of accessible checkpoint IDs (not used for filtering, kept for future)
        
    Returns:
        List of watchlist entries with vehicle details for the company
    """
    # Get all watchlist entries for the company with updated schema
    query = db.query(
        MstWatchlist.id,
        MstWatchlist.vehicle_id,
        MstWatchlist.company_id,
        MstWatchlist.reason,
        MstWatchlist.is_blacklisted,
        MstWatchlist.is_whitelisted,
        MstWatchlist.disabled,
        MstWatchlist.is_deleted,
        MstWatchlist.operation_data,
        MstVehicle.plate_number
    ).join(
        MstVehicle, MstWatchlist.vehicle_id == MstVehicle.vehicle_id
    ).filter(
        MstWatchlist.is_deleted == False,
        MstWatchlist.company_id == company_id
    ).order_by(
        MstWatchlist.id.desc()
    )
    
    return query.all()


def add_watchlist_entry(
    db: Session,
    vehicle_id: int,
    company_id: int,
    reason: str,
    is_blacklisted: bool,
    is_whitelisted: bool,
    added_by: str
):
    """
    Add a new watchlist entry - DEPRECATED, use POST /watchlist/add instead.
    
    This function is kept for backward compatibility but the new endpoint
    handles operation_data tracking properly.
    """
    new_entry = MstWatchlist(
        vehicle_id=vehicle_id,
        company_id=company_id,
        reason=reason,
        is_blacklisted=is_blacklisted,
        is_whitelisted=is_whitelisted,
        disabled=False,
        is_deleted=False
    )
    
    db.add(new_entry)
    db.commit()
    db.refresh(new_entry)
    
    return new_entry


def check_vehicle_exists(db: Session, vehicle_id: int) -> bool:
    """Check if vehicle exists in database."""
    return db.query(MstVehicle).filter(MstVehicle.vehicle_id == vehicle_id).first() is not None


def get_vehicle_by_plate_number(db: Session, plate_number: str):
    """Get vehicle by plate number."""
    return db.query(MstVehicle).filter(
        MstVehicle.plate_number == plate_number,
        MstVehicle.is_deleted == False
    ).first()


def create_vehicle(db: Session, plate_number: str, vehicle_type: Optional[str], created_by: str):
    """Create a new vehicle entry."""
    new_vehicle = MstVehicle(
        plate_number=plate_number,
        vehicle_type=vehicle_type,
        disabled=False,
        is_deleted=False
    )
    
    db.add(new_vehicle)
    db.commit()
    db.refresh(new_vehicle)
    
    return new_vehicle


def check_duplicate_watchlist(db: Session, vehicle_id: int, company_id: int) -> bool:
    """Check if vehicle already exists in watchlist for this company."""
    return db.query(MstWatchlist).filter(
        MstWatchlist.vehicle_id == vehicle_id,
        MstWatchlist.company_id == company_id,
        MstWatchlist.is_deleted == False
    ).first() is not None
