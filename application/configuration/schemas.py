"""Schemas for configuration API."""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class ScopeEnum(str, Enum):
    camera = "camera"
    checkpoints = "checkpoints"


class GetAssignedResourcesRequest(BaseModel):
    scope: ScopeEnum = Field(..., description="Scope: camera or checkpoints")


class CheckpointResponse(BaseModel):
    checkpoint_id: int
    checkpoint_name: str
    location_id: int
    location_name: str
    checkpoint_type: str
    direction: Optional[str]
    sequence_order: Optional[int]
    latitude: Optional[float]
    longitude: Optional[float]
    disabled: bool

    class Config:
        from_attributes = True


class CameraResponse(BaseModel):
    camera_id: int
    camera_name: Optional[str]
    device_id: str
    checkpoint_id: Optional[int]
    checkpoint_name: Optional[str]
    location_id: int
    location_name: str
    camera_type: Optional[str]
    camera_model: Optional[str]
    ip_address: Optional[str]
    rtsp_url: Optional[str]
    fps: Optional[int]
    deployment_type: str
    disabled: bool

    class Config:
        from_attributes = True


class CameraUpsertRequest(BaseModel):
    camera_id: Optional[int] = Field(None, description="Camera ID for update, null for create")
    device_id: Optional[str] = Field(None, description="Unique device identifier (for Camera Solution)")
    camera_name: Optional[str] = None
    checkpoint_id: Optional[int] = None
    location_id: int = Field(..., description="Location ID (required)")
    box_id: Optional[int] = Field(None, description="Box ID (for Box Solution)")
    camera_type: Optional[str] = None
    camera_model: Optional[str] = None
    fps: Optional[int] = None
    ip_address: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    roi: Optional[Dict[str, Any]] = None
    loi: Optional[Dict[str, Any]] = None
    disabled: bool = False
    remarks: Optional[str] = None
    
    @classmethod
    def model_validate(cls, value):
        obj = super().model_validate(value)
        
        # Validate that exactly one of device_id or box_id is provided
        has_device_id = obj.device_id is not None
        has_box_id = obj.box_id is not None
        
        if not has_device_id and not has_box_id:
            raise ValueError("Either device_id or box_id must be provided")
        
        if has_device_id and has_box_id:
            raise ValueError("Only one of device_id or box_id should be provided, not both")
        
        return obj
