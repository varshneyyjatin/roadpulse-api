"""Utility functions for watchlist."""
from typing import List, Dict
import json
from application.helpers.logger import get_logger

logger = get_logger("watchlist_utils")


def extract_accessible_locations_checkpoints(access_entries: List) -> Dict:
    """
    Extract accessible location and checkpoint IDs from access control entries.
    
    Args:
        access_entries: List of access control entries
        
    Returns:
        Dict with location_ids and checkpoint_ids lists (None means ALL access)
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
    
    return {
        "location_ids": None if has_all_locations else list(set(location_ids)),
        "checkpoint_ids": None if has_all_checkpoints else list(set(checkpoint_ids))
    }
