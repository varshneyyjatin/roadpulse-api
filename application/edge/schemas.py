"""
Pydantic schemas for Edge Box configuration API.
"""
from typing import List, Optional, Dict
from pydantic import BaseModel
from datetime import datetime

class CameraConfigSchema(BaseModel):
    """Camera configuration with network details, RTSP connection, and ROI settings."""
    camera_id: int
    compute_box_id: int
    camera_ip_add: str
    box_ip_add: str
    roi: Optional[Dict] = None
    rtsp_url: Optional[str] = None
    camera_name: str
    user_name: Optional[str] = None
    password: Optional[str] = None

class CheckpointSchema(BaseModel):
    """Checkpoint representing a monitoring point with associated cameras."""
    direction: Optional[str] = None
    checkpoint_name: str
    checkpoint_id: int
    camera_config: List[CameraConfigSchema]

class LocationSchema(BaseModel):
    """Complete site configuration for edge box operation."""
    company_id: int
    location_name: str
    location_id: int
    company_name: str
    checkpoints: List[CheckpointSchema]
    latest_updated_at: Optional[datetime]

class VehicleLookupRequest(BaseModel):
    """Request schema for vehicle blacklist lookup."""
    plate_number: str
    vehicle_type: Optional[str] = None

class EdgeBoxBlacklistInfoSchemaResponse(BaseModel):
    """Response schema for vehicle blacklist information."""
    plate_number: str
    vehicle_id: int
    vehicle_type: Optional[str] = None
    is_blacklisted: Optional[bool] = None
    is_whitelisted: Optional[bool] = None
    watchlist_id: Optional[int] = None

class VehicleDetectionRequest(BaseModel):
    """Combined request schema for vehicle detection with logging."""
    plate_number: str
    vehicle_type: Optional[str] = None
    timestamp: str
    location_id: int
    data: Dict
    checkpoint_id: Optional[int] = None
    driver_id: Optional[int] = None

class VehicleDetectionResponse(BaseModel):
    """Combined response schema for vehicle detection."""
    vehicle_id: int
    plate_number: str
    vehicle_type: Optional[str] = None
    is_blacklisted: bool
    is_whitelisted: bool
    watchlist_id: Optional[int] = None
    log_status: str
    log_id: int
    notification_sent: bool
    notification_count: Optional[int] = None