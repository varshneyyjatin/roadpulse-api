"""Utility functions for watchlist."""
from typing import List, Dict
import json
from application.helpers.logger import get_logger

logger = get_logger("watchlist_utils")


def extract_accessible_locations_checkpoints(access_entries: List, db=None, company_id: int = None, role: str = None) -> Dict:
    """
    Extract accessible location and checkpoint IDs from access control entries.
    
    Args:
        access_entries: List of access control entries
        db: Database session (optional, needed for company filtering)
        company_id: User's company ID (optional, needed for non-creator roles)
        role: User's role (optional, needed to determine if creator)
        
    Returns:
        Dict with location_ids and checkpoint_ids lists (None means ALL access for that company)
    """
    location_ids = []
    checkpoint_ids = []
    has_all_locations = False
    has_all_checkpoints = False
    
    for entry in access_entries:
        if entry.access_type == 'location':
            if entry.access_data is None:
                has_all_locations = True
            else:
                try:
                    data = json.loads(entry.access_data)
                    location_ids.extend(data.get('access_ids', []))
                except:
                    pass
        
        elif entry.access_type == 'checkpoint':
            if entry.access_data is None:
                has_all_checkpoints = True
            else:
                try:
                    data = json.loads(entry.access_data)
                    checkpoint_ids.extend(data.get('access_ids', []))
                except:
                    pass
    
    # If has_all_locations and non-creator role, get all locations for that company
    if has_all_locations and db and company_id and role != 'creator':
        from application.database.models.location import MstLocation
        company_locations = db.query(MstLocation.location_id).filter(
            MstLocation.company_id == company_id,
            MstLocation.disabled == False,
            MstLocation.is_deleted == False
        ).all()
        location_ids = [loc[0] for loc in company_locations]
        has_all_locations = False  # Now we have specific IDs
    
    # If has_all_checkpoints and non-creator role, get all checkpoints for accessible locations
    if has_all_checkpoints and db and company_id and role != 'creator':
        from application.database.models.checkpoint import MstCheckpoint
        from application.database.models.location import MstLocation
        
        # Get checkpoints from user's company locations
        company_checkpoints = db.query(MstCheckpoint.checkpoint_id).join(
            MstLocation, MstCheckpoint.location_id == MstLocation.location_id
        ).filter(
            MstLocation.company_id == company_id,
            MstCheckpoint.disabled == False,
            MstCheckpoint.is_deleted == False,
            MstLocation.disabled == False,
            MstLocation.is_deleted == False
        ).all()
        checkpoint_ids = [cp[0] for cp in company_checkpoints]
        has_all_checkpoints = False  # Now we have specific IDs
    
    # Filter location_ids by company for non-creator roles
    if location_ids and db and company_id and role != 'creator':
        from application.database.models.location import MstLocation
        valid_locations = db.query(MstLocation.location_id).filter(
            MstLocation.location_id.in_(location_ids),
            MstLocation.company_id == company_id,
            MstLocation.disabled == False,
            MstLocation.is_deleted == False
        ).all()
        location_ids = [loc[0] for loc in valid_locations]
    
    # Filter checkpoint_ids by company for non-creator roles
    if checkpoint_ids and db and company_id and role != 'creator':
        from application.database.models.checkpoint import MstCheckpoint
        from application.database.models.location import MstLocation
        valid_checkpoints = db.query(MstCheckpoint.checkpoint_id).join(
            MstLocation, MstCheckpoint.location_id == MstLocation.location_id
        ).filter(
            MstCheckpoint.checkpoint_id.in_(checkpoint_ids),
            MstLocation.company_id == company_id,
            MstCheckpoint.disabled == False,
            MstCheckpoint.is_deleted == False,
            MstLocation.disabled == False,
            MstLocation.is_deleted == False
        ).all()
        checkpoint_ids = [cp[0] for cp in valid_checkpoints]
    
    return {
        "location_ids": None if has_all_locations else list(set(location_ids)) if location_ids else [],
        "checkpoint_ids": None if has_all_checkpoints else list(set(checkpoint_ids)) if checkpoint_ids else []
    }
