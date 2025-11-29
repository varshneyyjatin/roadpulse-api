"""
CRUD operations for dashboard.
"""
from typing import List, Optional, Dict
from datetime import date, datetime
from sqlalchemy.orm import Session
from application.database.models.transactions.vehicle_log import TrnVehicleLog
from application.database.models.vehicle import MstVehicle
from application.database.models.checkpoint import MstCheckpoint
from application.database.models.location import MstLocation
from application.database.models.watchlist import MstWatchlist
from application.database.models.camera import MstCamera

def get_vehicle_logs_by_locations_checkpoints(
    db: Session,
    location_ids: List[int] = None,
    checkpoint_ids: List[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None
):
    """
    Get vehicle logs filtered by locations, checkpoints, and date range.
    
    Args:
        db: Database session
        location_ids: List of location IDs (None means all)
        checkpoint_ids: List of checkpoint IDs (None means all)
        start_date: Start date for filtering (None means no start limit)
        end_date: End date for filtering (None means no end limit)
        
    Returns:
        List of vehicle logs with related data
    """
    query = db.query(
        TrnVehicleLog.log_id,
        TrnVehicleLog.vehicle_id,
        TrnVehicleLog.location_id,
        TrnVehicleLog.timestamp,
        TrnVehicleLog.first_seen,
        TrnVehicleLog.last_seen,
        TrnVehicleLog.latest_data,
        TrnVehicleLog.history_data,
        MstVehicle.plate_number,
        MstLocation.location_name
    ).join(
        MstVehicle, TrnVehicleLog.vehicle_id == MstVehicle.vehicle_id
    ).outerjoin(
        MstLocation, TrnVehicleLog.location_id == MstLocation.location_id
    )
    
    # Filter by locations if provided
    if location_ids is not None:
        query = query.filter(TrnVehicleLog.location_id.in_(location_ids))
    
    # Filter by date range if provided
    if start_date:
        start_datetime = datetime.combine(start_date, datetime.min.time())
        query = query.filter(TrnVehicleLog.timestamp >= start_datetime)
    
    if end_date:
        end_datetime = datetime.combine(end_date, datetime.max.time())
        query = query.filter(TrnVehicleLog.timestamp <= end_datetime)
    
    # Order by most recent first
    query = query.order_by(TrnVehicleLog.last_seen.desc())
    
    return query.all()


def get_vehicle_logs_with_blacklist(
    db: Session,
    company_id: int,
    location_ids: List[int] = None,
    checkpoint_ids: List[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    is_blacklisted: Optional[bool] = None,
    is_whitelisted: Optional[bool] = None,
    plate_number: Optional[str] = None,
    limit: int = 1000
):
    """
    HIGHLY OPTIMIZED: Get vehicle logs with blacklist status in single query.
    
    Args:
        db: Database session
        company_id: Company ID for blacklist check
        location_ids: List of location IDs (None means all)
        checkpoint_ids: List of checkpoint IDs (None means all)
        start_date: Start date for filtering (None means no start limit)
        end_date: End date for filtering (None means no end limit)
        is_blacklisted: Filter by blacklisted status (None means all)
        is_whitelisted: Filter by whitelisted status (None means all)
        plate_number: Filter by vehicle plate number (None means all)
        limit: Maximum number of records to return (default 1000)
        
    Returns:
        List of vehicle logs with blacklist status
    """
    from sqlalchemy import and_
    
    # Build filter conditions
    filters = []
    if location_ids is not None:
        filters.append(TrnVehicleLog.location_id.in_(location_ids))
    if start_date:
        start_datetime = datetime.combine(start_date, datetime.min.time())
        filters.append(TrnVehicleLog.timestamp >= start_datetime)
    if end_date:
        end_datetime = datetime.combine(end_date, datetime.max.time())
        filters.append(TrnVehicleLog.timestamp <= end_datetime)
    
    # Single optimized query with all joins
    from sqlalchemy import cast, Integer, text
    
    query = db.query(
        TrnVehicleLog.log_id,
        TrnVehicleLog.vehicle_id,
        TrnVehicleLog.location_id,
        TrnVehicleLog.timestamp,
        TrnVehicleLog.first_seen,
        TrnVehicleLog.last_seen,
        TrnVehicleLog.latest_data,
        TrnVehicleLog.history_data,
        TrnVehicleLog.is_revised,
        TrnVehicleLog.revised_data,
        MstVehicle.plate_number,
        MstLocation.location_name,
        MstCheckpoint.checkpoint_id,
        MstCheckpoint.name.label("checkpoint_name"),
        MstWatchlist.is_blacklisted,
        MstWatchlist.is_whitelisted
    ).join(
        MstVehicle, TrnVehicleLog.vehicle_id == MstVehicle.vehicle_id
    ).outerjoin(
        MstCheckpoint,
        MstCheckpoint.checkpoint_id == cast(TrnVehicleLog.latest_data.op('->>')(text("'checkpoint_id'")), Integer)
    ).outerjoin(
        MstLocation, MstCheckpoint.location_id == MstLocation.location_id
    ).outerjoin(
        MstWatchlist,
        and_(
            TrnVehicleLog.vehicle_id == MstWatchlist.vehicle_id,
            MstWatchlist.company_id == company_id,
            MstWatchlist.is_deleted == False,
            MstWatchlist.disabled == False
        )
    )
    
    # Apply plate number filter if provided
    if plate_number:
        plate_number_upper = plate_number.strip().upper()
        filters.append(MstVehicle.plate_number == plate_number_upper)
    
    # Apply all filters at once
    if filters:
        query = query.filter(and_(*filters))
    
    # Apply watchlist filters if provided
    if is_blacklisted is not None:
        if is_blacklisted:
            # Show only blacklisted vehicles
            query = query.filter(MstWatchlist.is_blacklisted == True)
        else:
            # Show only non-blacklisted vehicles (including those not in watchlist)
            query = query.filter(
                (MstWatchlist.is_blacklisted == False) | (MstWatchlist.is_blacklisted.is_(None))
            )
    
    if is_whitelisted is not None:
        if is_whitelisted:
            # Show only whitelisted vehicles
            query = query.filter(MstWatchlist.is_whitelisted == True)
        else:
            # Show only non-whitelisted vehicles (including those not in watchlist)
            query = query.filter(
                (MstWatchlist.is_whitelisted == False) | (MstWatchlist.is_whitelisted.is_(None))
            )
    
    # Order by indexed column and limit results
    query = query.order_by(TrnVehicleLog.timestamp.desc()).limit(limit)
    
    return query.all()


def get_summary_counts(
    db: Session,
    company_id: int,
    location_ids: List[int] = None,
    checkpoint_ids: List[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    today_only: bool = True
):
    """
    Get summary counts for dashboard or reports - HIGHLY OPTIMIZED.
    
    Args:
        db: Database session
        company_id: Company ID for blacklist count
        location_ids: List of location IDs assigned to user (None means all)
        checkpoint_ids: List of checkpoint IDs assigned to user (None means all)
        start_date: Start date for filtering vehicle logs
        end_date: End date for filtering vehicle logs
        today_only: Not used anymore, kept for compatibility
        
    Returns:
        Dict with total vehicles (from date range), total locations (assigned), total cameras (assigned), blacklisted vehicles (from date range), multiple detections count
    """
    from sqlalchemy import func, select, and_, case
    
    # Build filter conditions once
    filters = []
    if start_date:
        start_datetime = datetime.combine(start_date, datetime.min.time())
        filters.append(TrnVehicleLog.timestamp >= start_datetime)
    
    if end_date:
        end_datetime = datetime.combine(end_date, datetime.max.time())
        filters.append(TrnVehicleLog.timestamp <= end_datetime)
    
    if location_ids is not None:
        filters.append(TrnVehicleLog.location_id.in_(location_ids))
    
    # SUPER OPTIMIZED: Single CTE query for both counts
    # Create subquery for distinct vehicle IDs
    vehicle_subquery = select(TrnVehicleLog.vehicle_id).distinct()
    if filters:
        vehicle_subquery = vehicle_subquery.where(and_(*filters))
    vehicle_subquery = vehicle_subquery.subquery()
    
    # Single query to get both counts using the subquery
    counts = db.query(
        func.count(vehicle_subquery.c.vehicle_id).label('total_vehicles'),
        func.count(MstWatchlist.vehicle_id).label('blacklisted_count')
    ).outerjoin(
        MstWatchlist,
        and_(
            vehicle_subquery.c.vehicle_id == MstWatchlist.vehicle_id,
            MstWatchlist.company_id == company_id,
            MstWatchlist.is_blacklisted == True,
            MstWatchlist.is_deleted == False,
            MstWatchlist.disabled == False
        )
    ).first()
    
    total_vehicles = counts.total_vehicles if counts else 0
    blacklisted_count = counts.blacklisted_count if counts else 0
    
    # Count vehicles with multiple detections (history_data length > 1)
    multiple_detections_query = db.query(
        func.count().label('multiple_count')
    ).select_from(TrnVehicleLog)
    
    if filters:
        multiple_detections_query = multiple_detections_query.filter(and_(*filters))
    
    multiple_detections_query = multiple_detections_query.filter(
        func.json_array_length(TrnVehicleLog.history_data) > 1
    )
    
    multiple_detections_count = multiple_detections_query.scalar() or 0
    
    # Total Locations - Simple count from list (no DB query)
    if location_ids is not None and len(location_ids) > 0:
        total_locations = len(location_ids)
    else:
        # Cache this or make it faster
        total_locations = db.query(func.count(MstLocation.location_id)).filter(
            MstLocation.is_deleted == False,
            MstLocation.disabled == False
        ).scalar() or 0
    
    # Total Cameras - Single optimized count
    if location_ids is not None:
        camera_filters = [MstCamera.is_deleted == False, MstCamera.disabled == False]
        camera_filters.append(MstCamera.location_id.in_(location_ids))
        total_cameras = db.query(func.count(MstCamera.camera_id)).filter(and_(*camera_filters)).scalar() or 0
    else:
        total_cameras = db.query(func.count(MstCamera.camera_id)).filter(
            MstCamera.is_deleted == False,
            MstCamera.disabled == False
        ).scalar() or 0
    
    return {
        "total_vehicles": total_vehicles,
        "total_locations": total_locations,
        "total_cameras": total_cameras,
        "blacklisted_vehicle_count": blacklisted_count,
        "multiple_detections_count": multiple_detections_count
    }


def get_blacklisted_vehicles(db: Session, company_id: int) -> Dict[int, bool]:
    """
    Get blacklisted vehicles for a company.
    
    Args:
        db: Database session
        company_id: Company ID
        
    Returns:
        Dict mapping vehicle_id to is_blacklisted status
    """
    blacklist_entries = db.query(
        MstWatchlist.vehicle_id,
        MstWatchlist.is_blacklisted
    ).filter(
        MstWatchlist.company_id == company_id,
        MstWatchlist.is_deleted == False,
        MstWatchlist.disabled == False
    ).all()
    
    # Create a dict: vehicle_id -> is_blacklisted
    blacklist_map = {}
    for entry in blacklist_entries:
        blacklist_map[entry.vehicle_id] = entry.is_blacklisted if entry.is_blacklisted is not None else False
    
    return blacklist_map


