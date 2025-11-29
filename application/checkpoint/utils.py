"""
Utility functions for checkpoint management.
"""
from collections import defaultdict
from typing import List, Dict
from fastapi import HTTPException, status
from application.helpers.logger import get_logger

logger = get_logger("checkpoint_utils")

def validate_sequence_uniqueness(checkpoint_location_map: Dict[int, int], updates: List) -> None:
    """
    Validate that sequence numbers are unique within each location.
    
    Args:
        checkpoint_location_map: Mapping of checkpoint_id to location_id
        updates: List of CheckpointSequenceUpdate objects
        
    Raises:
        HTTPException: If duplicate sequences found in same location
    """
    location_sequences = defaultdict(list)
    
    for update in updates:
        location_id = checkpoint_location_map[update.checkpoint_id]
        location_sequences[location_id].append(update.sequence_order)
    
    # Check for duplicate sequences within each location
    for location_id, sequences in location_sequences.items():
        if len(sequences) != len(set(sequences)):
            logger.warning(f"Validation Failed :: LocationID -> {location_id} :: Reason -> Duplicate sequence numbers")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Duplicate sequence numbers found for location {location_id}. Each checkpoint in a location must have a unique sequence number."
            )

def validate_sequence_continuity(checkpoint_location_map: Dict[int, int], updates: List) -> None:
    """
    Validate that sequence numbers are continuous (1, 2, 3, ...) within each location.
    
    Args:
        checkpoint_location_map: Mapping of checkpoint_id to location_id
        updates: List of CheckpointSequenceUpdate objects
        
    Raises:
        HTTPException: If sequences are not continuous
    """
    location_sequences = defaultdict(list)
    
    for update in updates:
        location_id = checkpoint_location_map[update.checkpoint_id]
        location_sequences[location_id].append(update.sequence_order)
    
    # Check if sequences are continuous (1, 2, 3, ...)
    for location_id, sequences in location_sequences.items():
        sorted_sequences = sorted(sequences)
        expected_sequences = list(range(1, len(sequences) + 1))
        if sorted_sequences != expected_sequences:
            logger.warning(f"Validation Failed :: LocationID -> {location_id} :: Reason -> Sequences not continuous")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Sequence numbers for location {location_id} must be continuous (1, 2, 3, ...). Got: {sorted_sequences}"
            )

def group_checkpoints_by_location(checkpoints: List) -> List[Dict]:
    """
    Group checkpoints by location name.
    
    Args:
        checkpoints: List of checkpoint query results
        
    Returns:
        List of dictionaries with location info and grouped checkpoints
    """
    location_map = defaultdict(list)
    
    for cp in checkpoints:
        location_map[cp.location_name].append({
            "checkpoint_id": cp.checkpoint_id,
            "checkpoint_name": cp.checkpoint_name,
            "description": cp.description,
            "sequence_order": cp.sequence_order
        })
    
    result = [
        {
            "location_name": location_name,
            "checkpoint_count": len(checkpoints_list),
            "checkpoints": checkpoints_list
        }
        for location_name, checkpoints_list in location_map.items()
    ]
    
    return result
