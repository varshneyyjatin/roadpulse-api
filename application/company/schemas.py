"""Company onboarding schemas"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List


class SimpleLocationCreate(BaseModel):
    """Simplified location - user sirf location count dega"""
    count: int = Field(..., ge=1, description="Number of locations to create")
    checkpoints_per_location: Optional[List[int]] = Field(
        None, 
        description="Checkpoints count for each location. If not provided, 1 checkpoint per location"
    )
    cameras_per_checkpoint: Optional[List[List[int]]] = Field(
        None,
        description="Cameras count for each checkpoint in each location. If not provided, 1 camera per checkpoint"
    )


class CompanyOnboardingRequest(BaseModel):
    """Simplified company onboarding request"""
    # Company details (required)
    company_code: str = Field(..., min_length=2, max_length=50)
    company_name: str = Field(..., min_length=1, max_length=255)
    company_email: EmailStr
    
    # Location configuration (required)
    locations: SimpleLocationCreate
    
    # Optional fields
    company_phone: Optional[str] = Field(None, min_length=10, max_length=15)
    company_address: Optional[str] = None
    data_retention_days: int = Field(default=90)


class DefaultUserInfo(BaseModel):
    """Default user credentials"""
    username: str
    password: str
    role: str
    email: str


class CompanyOnboardingResponse(BaseModel):
    """Response after successful onboarding"""
    success: bool
    message: str
    company_id: int
    company_code: str
    company_name: str
    locations_created: int
    checkpoints_created: int
    cameras_created: int
    default_user: DefaultUserInfo
