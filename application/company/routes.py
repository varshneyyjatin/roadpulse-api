"""Company onboarding routes"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy.orm import Session
from application.database.session import get_db
from application.company.schemas import CompanyOnboardingRequest, CompanyOnboardingResponse
from application.company.onboarding_service import CompanyOnboardingService
import secrets

router = APIRouter(prefix="/company", tags=["Company Onboarding"])
security = HTTPBasic()

# Basic Auth credentials
ONBOARDING_USERNAME = "johnthedon"
ONBOARDING_PASSWORD = "johnthedon"


def verify_onboarding_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    """Verify basic auth credentials for onboarding"""
    correct_username = secrets.compare_digest(credentials.username, ONBOARDING_USERNAME)
    correct_password = secrets.compare_digest(credentials.password, ONBOARDING_PASSWORD)
    
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

@router.post("/onboard", response_model=CompanyOnboardingResponse, status_code=status.HTTP_201_CREATED)
async def onboard_company(
    request: CompanyOnboardingRequest,
    db: Session = Depends(get_db),
    username: str = Depends(verify_onboarding_credentials)
):
    """
    🚀 Simplified Company Onboarding - Auto-generates everything!
    
    User provides:
    - Company code, name, email
    - Number of locations
    - (Optional) Checkpoints per location
    - (Optional) Cameras per checkpoint
    
    System auto-generates:
    - Location names, codes, addresses
    - Checkpoint names, types, coordinates
    - Camera names, IPs, device IDs
    
    Example 1 - Minimal (1 location, 1 checkpoint, 1 camera):
    ```json
    {
        "company_code": "ABC",
        "company_name": "ABC Company",
        "company_email": "admin@abc.com",
        "locations": {
            "count": 1
        }
    }
    ```
    
    Example 2 - Custom checkpoints (2 locations, custom checkpoints):
    ```json
    {
        "company_code": "XYZ",
        "company_name": "XYZ Corp",
        "company_email": "admin@xyz.com",
        "locations": {
            "count": 2,
            "checkpoints_per_location": [3, 2]
        }
    }
    ```
    
    Example 3 - Full custom (2 locations, custom checkpoints & cameras):
    ```json
    {
        "company_code": "TTL",
        "company_name": "Transline Technologies",
        "company_email": "transline@gmail.com",
        "company_phone": "9876543210",
        "company_address": "Transline Office, India",
        "data_retention_days": 90,
        "locations": {
            "count": 2,
            "checkpoints_per_location": [3, 1],
            "cameras_per_checkpoint": [
                [2, 1, 1],
                [1]
            ]
        }
    }
    ```
    """
    try:
        service = CompanyOnboardingService(db)
        result = service.onboard_company(request, created_by="api_onboarding")
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )