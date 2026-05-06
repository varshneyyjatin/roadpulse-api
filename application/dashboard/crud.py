"""
CRUD operations for dashboard.
"""
from typing import List, Optional, Dict
from datetime import date, datetime, timedelta
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
    start_date = None,
    end_date = None
):
    """
    Get vehicle logs filtered by locations, checkpoints, and date/datetime range.
    
    Args:
        db: Database session
        location_ids: List of location IDs (None means all)
        checkpoint_ids: List of checkpoint IDs (None means all)
        start_date: Start date or datetime for filtering (None means no start limit)
        end_date: End date or datetime for filtering (None means no end limit)
        
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
    
    # Filter by date/datetime range if provided
    if start_date:
        if isinstance(start_date, date) and not isinstance(start_date, datetime):
            start_datetime = datetime.combine(start_date, datetime.min.time())
        else:
            start_datetime = start_date
        query = query.filter(TrnVehicleLog.timestamp >= start_datetime)
    
    if end_date:
        if isinstance(end_date, date) and not isinstance(end_date, datetime):
            # Add 1 day and use < instead of <= to include all of end_date
            end_datetime = datetime.combine(end_date + timedelta(days=1), datetime.min.time())
            query = query.filter(TrnVehicleLog.timestamp < end_datetime)
        else:
            # For datetime objects, use < (routes.py already added 1 day for date inputs)
            query = query.filter(TrnVehicleLog.timestamp < end_date)
    
    # Order by most recent first
    query = query.order_by(TrnVehicleLog.last_seen.desc())
    
    return query.all()


def get_vehicle_logs_with_blacklist(
    db: Session,
    company_id: int,
    location_ids: List[int] = None,
    checkpoint_ids: List[int] = None,
    start_date = None,
    end_date = None,
    is_blacklisted: Optional[bool] = None,
    is_whitelisted: Optional[bool] = None,
    plate_number: Optional[str] = None,
    page: int = 1,
    page_size: int = 50
):
    """
    HIGHLY OPTIMIZED: Get vehicle logs with blacklist status in single query.
    
    Args:
        db: Database session
        company_id: Company ID for blacklist check
        location_ids: List of location IDs (None means all)
        checkpoint_ids: List of checkpoint IDs (None means all)
        start_date: Start date or datetime for filtering (None means no start limit)
        end_date: End date or datetime for filtering (None means no end limit)
        is_blacklisted: Filter by blacklisted status (None means all)
        is_whitelisted: Filter by whitelisted status (None means all)
        plate_number: Filter by vehicle plate number (None means all)
        page: Page number (starts from 1)
        page_size: Number of records per page
        
    Returns:
        List of vehicle logs with blacklist status
    """
    from sqlalchemy import and_
    
    # Build filter conditions
    filters = []
    
    # NOTE: We will filter by checkpoint's location (from latest_data), not TrnVehicleLog.location_id
    # TrnVehicleLog.location_id is the first detection location, not the latest
    # Location filtering will be done via checkpoint_ids parameter
    
    if start_date:
        if isinstance(start_date, date) and not isinstance(start_date, datetime):
            start_datetime = datetime.combine(start_date, datetime.min.time())
        else:
            start_datetime = start_date
        filters.append(TrnVehicleLog.timestamp >= start_datetime)
    if end_date:
        if isinstance(end_date, date) and not isinstance(end_date, datetime):
            # Add 1 day and use < instead of <= to include all of end_date
            end_datetime = datetime.combine(end_date + timedelta(days=1), datetime.min.time())
            filters.append(TrnVehicleLog.timestamp < end_datetime)
        else:
            # For datetime objects, use < (routes.py already added 1 day for date inputs)
            filters.append(TrnVehicleLog.timestamp < end_date)
    
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
    
    # IMPORTANT: Filter by checkpoint (which filters by latest location, not first location)
    if checkpoint_ids is not None:
        if len(checkpoint_ids) == 0:
            # Empty list means no access - return empty list
            return []
        # Filter by checkpoint_id from latest_data (via MstCheckpoint join)
        query = query.filter(MstCheckpoint.checkpoint_id.in_(checkpoint_ids))
    
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
    
    # Calculate offset for pagination
    offset = (page - 1) * page_size
    
    # Order by indexed column and apply pagination
    query = query.order_by(TrnVehicleLog.timestamp.desc()).offset(offset).limit(page_size)
    
    return query.all()


def get_summary_counts(
    db: Session,
    company_id: int,
    location_ids: List[int] = None,
    checkpoint_ids: List[int] = None,
    start_date = None,
    end_date = None,
    today_only: bool = True
):
    """
    Get summary counts for dashboard or reports - HIGHLY OPTIMIZED.
    
    Args:
        db: Database session
        company_id: Company ID for blacklist count
        location_ids: List of location IDs assigned to user (None means all)
        checkpoint_ids: List of checkpoint IDs assigned to user (None means all)
        start_date: Start date or datetime for filtering vehicle logs
        end_date: End date or datetime for filtering vehicle logs
        today_only: Not used anymore, kept for compatibility
        
    Returns:
        Dict with:
        - total_vehicles: Unique vehicles in date range
        - total_locations: Total accessible locations (static)
        - total_cameras: Total accessible cameras (static)
        - blacklisted_vehicle_count: Blacklisted vehicles in date range
        - multiple_detections_count: Vehicles with multiple detections in date range
    """
    from sqlalchemy import func, select, and_, case
    
    # ===== BUILD FILTERS FOR DATE RANGE =====
    filters = []
    
    # Date/datetime filters
    if start_date:
        if isinstance(start_date, date) and not isinstance(start_date, datetime):
            start_datetime = datetime.combine(start_date, datetime.min.time())
        else:
            start_datetime = start_date
        filters.append(TrnVehicleLog.timestamp >= start_datetime)
    if end_date:
        if isinstance(end_date, date) and not isinstance(end_date, datetime):
            # Add 1 day and use < instead of <= to include all of end_date
            end_datetime = datetime.combine(end_date + timedelta(days=1), datetime.min.time())
            filters.append(TrnVehicleLog.timestamp < end_datetime)
        else:
            # For datetime objects, use < (routes.py already added 1 day for date inputs)
            filters.append(TrnVehicleLog.timestamp < end_date)
    
    # Location filter
    if location_ids is not None:
        filters.append(TrnVehicleLog.location_id.in_(location_ids))
    
    # ===== TOTAL VEHICLES & BLACKLISTED COUNT (WITH DATE FILTER) =====
    # Get unique vehicles in date range
    vehicle_subquery = select(TrnVehicleLog.vehicle_id).distinct()
    if filters:
        vehicle_subquery = vehicle_subquery.where(and_(*filters))
    vehicle_subquery = vehicle_subquery.subquery()
    
    # Single query to get both total and blacklisted counts
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
    
    # ===== MULTIPLE DETECTIONS COUNT (WITH DATE FILTER) =====
    # Count vehicles with multiple detections in date range
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


def get_vehicle_logs_count(
    db: Session,
    company_id: int,
    location_ids: List[int] = None,
    checkpoint_ids: List[int] = None,
    start_date = None,
    end_date = None,
    is_blacklisted: Optional[bool] = None,
    is_whitelisted: Optional[bool] = None,
    plate_number: Optional[str] = None
) -> int:
    """
    Get total count of vehicle logs matching the filters.
    When plate_number is provided, counts history_data entries instead of log records.
    
    Args:
        db: Database session
        company_id: Company ID for blacklist check
        location_ids: List of location IDs (None means all)
        checkpoint_ids: List of checkpoint IDs (None means all)
        start_date: Start date or datetime for filtering (None means no start limit)
        end_date: End date or datetime for filtering (None means no end limit)
        is_blacklisted: Filter by blacklisted status (None means all)
        is_whitelisted: Filter by whitelisted status (None means all)
        plate_number: Filter by vehicle plate number (None means all)
        
    Returns:
        Total count of matching records (history_data entries if plate_number provided, else log records)
    """
    from sqlalchemy import and_, func, cast, Integer, text
    
    # Build filter conditions
    filters = []
    
    # Handle location_ids: None means all, empty list means no access
    if location_ids is not None:
        if len(location_ids) == 0:
            # Empty list means no access - return 0
            return 0
        filters.append(TrnVehicleLog.location_id.in_(location_ids))
    
    if start_date:
        if isinstance(start_date, date) and not isinstance(start_date, datetime):
            start_datetime = datetime.combine(start_date, datetime.min.time())
        else:
            start_datetime = start_date
        filters.append(TrnVehicleLog.timestamp >= start_datetime)
    if end_date:
        if isinstance(end_date, date) and not isinstance(end_date, datetime):
            # Add 1 day and use < instead of <= to include all of end_date
            end_datetime = datetime.combine(end_date + timedelta(days=1), datetime.min.time())
            filters.append(TrnVehicleLog.timestamp < end_datetime)
        else:
            # For datetime objects, use < (routes.py already added 1 day for date inputs)
            filters.append(TrnVehicleLog.timestamp < end_date)
    
    # Build count query with same filters as main query
    query = db.query(TrnVehicleLog).join(
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
            query = query.filter(MstWatchlist.is_blacklisted == True)
        else:
            query = query.filter(
                (MstWatchlist.is_blacklisted == False) | (MstWatchlist.is_blacklisted.is_(None))
            )
    
    if is_whitelisted is not None:
        if is_whitelisted:
            query = query.filter(MstWatchlist.is_whitelisted == True)
        else:
            query = query.filter(
                (MstWatchlist.is_whitelisted == False) | (MstWatchlist.is_whitelisted.is_(None))
            )
    
    # If plate_number is provided, count history_data entries instead of log records
    if plate_number:
        logs = query.all()
        total_count = 0
        for log in logs:
            if log.history_data and len(log.history_data) > 0:
                # Count each history_data entry
                total_count += len(log.history_data)
            else:
                # If no history_data, count the log itself as 1 entry
                total_count += 1
        return total_count
    else:
        # Normal count of log records
        return query.count()


def get_vehicle_logs_with_blacklist_expanded(
    db: Session,
    company_id: int,
    location_ids: List[int] = None,
    checkpoint_ids: List[int] = None,
    start_date = None,
    end_date = None,
    is_blacklisted: Optional[bool] = None,
    is_whitelisted: Optional[bool] = None,
    plate_number: Optional[str] = None,
    page: int = 1,
    page_size: int = 50
):
    """
    Get vehicle logs with history_data expanded into separate rows (for plate number search).
    Applies pagination AFTER expanding history_data entries.
    
    OPTIMIZED: Fetches all matching logs in one query, then expands and paginates in memory.
    This is necessary because pagination must happen AFTER expansion when searching by plate_number.
    
    Args:
        db: Database session
        company_id: Company ID for blacklist check
        location_ids: List of location IDs (None means all)
        checkpoint_ids: List of checkpoint IDs (None means all)
        start_date: Start date or datetime for filtering (None means no start limit)
        end_date: End date or datetime for filtering (None means no end limit)
        is_blacklisted: Filter by blacklisted status (None means all)
        is_whitelisted: Filter by whitelisted status (None means all)
        plate_number: Filter by vehicle plate number (None means all)
        page: Page number (starts from 1)
        page_size: Number of records per page
        
    Returns:
        List of expanded history entries with pagination applied
    """
    from sqlalchemy import and_, cast, Integer, text
    
    # Build filter conditions
    filters = []
    
    # IMPORTANT: Filter by location_id based on latest_data (not history_data)
    # This ensures only logs from selected locations are returned
    if location_ids is not None:
        if len(location_ids) == 0:
            # Empty list means no access - return empty list
            return []
        filters.append(TrnVehicleLog.location_id.in_(location_ids))
    
    if start_date:
        if isinstance(start_date, date) and not isinstance(start_date, datetime):
            start_datetime = datetime.combine(start_date, datetime.min.time())
        else:
            start_datetime = start_date
        filters.append(TrnVehicleLog.timestamp >= start_datetime)
    if end_date:
        if isinstance(end_date, date) and not isinstance(end_date, datetime):
            # Add 1 day and use < instead of <= to include all of end_date
            end_datetime = datetime.combine(end_date + timedelta(days=1), datetime.min.time())
            filters.append(TrnVehicleLog.timestamp < end_datetime)
        else:
            # For datetime objects, use < (routes.py already added 1 day for date inputs)
            filters.append(TrnVehicleLog.timestamp < end_date)
    
    # Build query with all joins - fetch ALL matching logs
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
    
    # IMPORTANT: Filter by checkpoint (which filters by latest location, not first location)
    if checkpoint_ids is not None:
        if len(checkpoint_ids) == 0:
            # Empty list means no access - return empty list
            return []
        # Filter by checkpoint_id from latest_data (via MstCheckpoint join)
        query = query.filter(MstCheckpoint.checkpoint_id.in_(checkpoint_ids))
    
    # Apply watchlist filters if provided
    if is_blacklisted is not None:
        if is_blacklisted:
            query = query.filter(MstWatchlist.is_blacklisted == True)
        else:
            query = query.filter(
                (MstWatchlist.is_blacklisted == False) | (MstWatchlist.is_blacklisted.is_(None))
            )
    
    if is_whitelisted is not None:
        if is_whitelisted:
            query = query.filter(MstWatchlist.is_whitelisted == True)
        else:
            query = query.filter(
                (MstWatchlist.is_whitelisted == False) | (MstWatchlist.is_whitelisted.is_(None))
            )
    
    # Order by timestamp and fetch ALL matching logs
    query = query.order_by(TrnVehicleLog.timestamp.desc())
    logs = query.all()
    
    # Expand history_data into separate entries
    expanded_entries = []
    for log in logs:
        if log.history_data and len(log.history_data) > 0:
            # Sort history_data by timestamp in descending order (latest first)
            sorted_history = sorted(
                log.history_data,
                key=lambda x: x.get("Picture", {}).get("SnapInfo", {}).get("SnapTime", ""),
                reverse=True
            )
            
            for idx, entry in enumerate(sorted_history):
                expanded_entries.append({
                    "log": log,
                    "history_entry": entry,
                    "detection_number": idx + 1,
                    "total_detections": len(sorted_history)
                })
        else:
            # If no history_data, use latest_data as single entry
            expanded_entries.append({
                "log": log,
                "history_entry": log.latest_data if log.latest_data else {},
                "detection_number": 1,
                "total_detections": 1
            })
    
    # Apply pagination to expanded entries
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paginated_entries = expanded_entries[start_idx:end_idx]
    
    return paginated_entries


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