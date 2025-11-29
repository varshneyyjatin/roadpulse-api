"""
Pydantic schemas for checkpoint management.
"""
from pydantic import BaseModel, validator
from typing import List, Optional

class CheckpointUpdate(BaseModel):
    """Schema for updating checkpoint details (Manager - limited fields)"""
    checkpoint_name: Optional[str] = None
    description: Optional[str] = None
    sequence_order: Optional[int] = None
    
    @validator('sequence_order')
    def validate_sequence(cls, v):
        if v is not None and v < 1:
            raise ValueError('Sequence order must be greater than 0')
        return v
    
    @validator('checkpoint_name')
    def validate_name(cls, v):
        if v is not None and len(v.strip()) == 0:
            raise ValueError('Checkpoint name cannot be empty')
        return v

class CheckpointFullUpdate(BaseModel):
    """Schema for full checkpoint update (Creator - all fields)"""
    location_id: Optional[int] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    checkpoint_name: Optional[str] = None
    description: Optional[str] = None
    checkpoint_type: Optional[str] = None
    direction: Optional[str] = None
    sequence_order: Optional[int] = None
    disabled: Optional[bool] = None
    
    @validator('sequence_order')
    def validate_sequence(cls, v):
        if v is not None and v < 1:
            raise ValueError('Sequence order must be greater than 0')
        return v
    
    @validator('checkpoint_name')
    def validate_name(cls, v):
        if v is not None and len(v.strip()) == 0:
            raise ValueError('Checkpoint name cannot be empty')
        return v

class CheckpointResponse(BaseModel):
    """Schema for checkpoint response"""
    checkpoint_id: int
    checkpoint_name: str
    description: Optional[str]
    sequence_order: Optional[int]

class LocationCheckpointsResponse(BaseModel):
    """Schema for location with checkpoints"""
    location_name: str
    checkpoint_count: int
    checkpoints: List[CheckpointResponse]