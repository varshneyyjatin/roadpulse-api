"""Schemas for dashboard API."""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date
from enum import Enum

class ScopeEnum(str, Enum):
    dashboard = "dashboard"
    report = "report"

class VehicleLogsRequest(BaseModel):
    scope: ScopeEnum = Field(default=ScopeEnum.dashboard, description="Scope: dashboard or report")
    location_ids: Optional[List[int]] = Field(default=None, description="List of location IDs (for report scope)")
    checkpoint_ids: Optional[List[int]] = Field(default=None, description="List of checkpoint IDs (for report scope)")
    start_date: Optional[date] = Field(default=None, description="Start date (for report scope)")
    end_date: Optional[date] = Field(default=None, description="End date (for report scope)")
    is_blacklisted: Optional[bool] = Field(default=None, description="Filter by blacklisted vehicles (true/false/null for all)")
    is_whitelisted: Optional[bool] = Field(default=None, description="Filter by whitelisted vehicles (true/false/null for all)")
    plate_number: Optional[str] = Field(default=None, min_length=1, max_length=20, description="Search by vehicle plate number (for report scope)")

class FixVehicleNumberRequest(BaseModel):
    record_id: int = Field(..., description="Vehicle log record ID")
    old_value: str = Field(..., description="Old plate number")
    new_value: str = Field(..., description="New plate number")
    change_reason: str = Field(..., description="Reason for change")