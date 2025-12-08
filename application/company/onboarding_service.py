"""Company Onboarding Service - Auto-generates company, locations, checkpoints, cameras only"""
import json
from sqlalchemy.orm import Session
from application.database.models.company import MstCompany
from application.database.models.location import MstLocation
from application.database.models.checkpoint import MstCheckpoint
from application.database.models.camera import MstCamera
from application.database.models.user import MstUser
from application.database.models.transactions.access_control import TrnAccessControl
from application.auth.utils import hash_password
from application.company.schemas import CompanyOnboardingRequest


class CompanyOnboardingService:
    """Service to handle simplified company onboarding with auto-generation"""
    
    # Default location names pattern
    LOCATION_NAMES = [
        "Main Office", "Branch Office 1", "Branch Office 2", "Branch Office 3",
        "Branch Office 4", "Branch Office 5", "Branch Office 6", "Branch Office 7",
        "Branch Office 8", "Branch Office 9", "Branch Office 10"
    ]
    
    # Default checkpoint names pattern
    CHECKPOINT_NAMES = [
        "Main Entrance", "Parking Area", "Basement", "Reception", "Loading Bay",
        "Side Entrance", "Emergency Exit", "Rooftop", "Warehouse", "Gate 1"
    ]
    
    def __init__(self, db: Session):
        self.db = db
        
    def onboard_company(self, request: CompanyOnboardingRequest, created_by: str = "system"):
        """
        Simplified company onboarding with auto-generation
        User provides: company details + location/checkpoint/camera counts
        System generates: Company, Locations, Checkpoints, Cameras only
        """
        try:
            # 1. Create Company
            company = self._create_company(request, created_by)
            
            # 2. Auto-generate Locations
            locations = self._auto_generate_locations(request, company.id, created_by)
            
            # 3. Auto-generate Checkpoints
            checkpoints = self._auto_generate_checkpoints(request, locations, created_by)
            
            # 4. Auto-generate Cameras
            cameras = self._auto_generate_cameras(request, checkpoints, locations, created_by)
            
            # 5. Auto-generate Default Superadmin User
            user = self._auto_generate_default_user(request, company.id, created_by)
            
            # 6. Create Full Access Control for Default User
            access_controls = self._create_full_access_control(user.id, created_by)
            
            self.db.commit()
            
            return {
                "success": True,
                "message": "Company onboarded successfully",
                "company_id": company.id,
                "company_code": company.company_code,
                "company_name": company.name,
                "locations_created": len(locations),
                "checkpoints_created": len(checkpoints),
                "cameras_created": len(cameras),
                "default_user": {
                    "username": f"sa-{request.company_code.lower()}",
                    "password": f"sa-{request.company_code.lower()}",
                    "role": "manager",
                    "email": request.company_email
                }
            }
            
        except Exception as e:
            self.db.rollback()
            raise Exception(f"Onboarding failed: {str(e)}")
    
    def _create_company(self, request: CompanyOnboardingRequest, created_by: str):
        """Create company"""
        company = MstCompany(
            company_code=request.company_code,
            name=request.company_name,
            email=request.company_email,
            phone=request.company_phone or "0000000000",
            address=request.company_address or f"{request.company_name} Office",
            data_retention_days=request.data_retention_days,
            disabled=False,
            created_by=created_by,
            updated_by=created_by
        )
        self.db.add(company)
        self.db.flush()
        return company
    
    def _auto_generate_locations(self, request: CompanyOnboardingRequest, company_id: int, created_by: str):
        """Auto-generate locations based on count with company code pattern"""
        locations = []
        location_count = request.locations.count
        company_code_lower = request.company_code.lower()
        
        for i in range(location_count):
            # Location code: test001, test002, test003...
            location_code = f"{company_code_lower}{i+1:03d}"
            
            # Location name: Testing Location 1, Testing Location 2...
            location_name = f"{request.company_name} Location {i+1}"
            
            location = MstLocation(
                company_id=company_id,
                location_name=location_name,
                location_code=location_code,
                location_type="Office",
                location_address=f"{location_name}, {request.company_name}",
                contact_person_name="Site Manager",
                contact_person_phone=f"98765432{10+i:02d}",
                disabled=False,
                created_by=created_by,
                updated_by=created_by
            )
            self.db.add(location)
            locations.append(location)
        
        self.db.flush()
        return locations
    
    def _auto_generate_checkpoints(self, request: CompanyOnboardingRequest, locations, created_by: str):
        """Auto-generate checkpoints based on configuration with location name pattern"""
        checkpoints = []
        checkpoints_config = request.locations.checkpoints_per_location
        
        for loc_idx, location in enumerate(locations):
            # Determine checkpoint count for this location
            if checkpoints_config and loc_idx < len(checkpoints_config):
                checkpoint_count = checkpoints_config[loc_idx]
            else:
                checkpoint_count = 1  # Default: 1 checkpoint per location
            
            # Generate checkpoints for this location
            for cp_idx in range(checkpoint_count):
                # Checkpoint name: Testing Location 1 - Checkpoint 1
                checkpoint_name = f"{location.location_name} - Checkpoint {cp_idx+1}"
                
                checkpoint = MstCheckpoint(
                    location_id=location.location_id,
                    name=checkpoint_name,
                    checkpoint_type="Entry" if cp_idx == 0 else "Internal",
                    latitude=28.6692 + (loc_idx * 0.01),  # Dummy coordinates
                    longitude=77.1510 + (loc_idx * 0.01),
                    disabled=False,
                    created_by=created_by,
                    updated_by=created_by
                )
                self.db.add(checkpoint)
                checkpoints.append(checkpoint)
        
        self.db.flush()
        return checkpoints
    
    def _auto_generate_cameras(self, request: CompanyOnboardingRequest, checkpoints, locations, created_by: str):
        """Auto-generate cameras based on configuration"""
        cameras = []
        cameras_config = request.locations.cameras_per_checkpoint
        camera_counter = 1
        
        # Group checkpoints by location
        location_checkpoints = {}
        for checkpoint in checkpoints:
            loc_id = checkpoint.location_id
            if loc_id not in location_checkpoints:
                location_checkpoints[loc_id] = []
            location_checkpoints[loc_id].append(checkpoint)
        
        # Generate cameras
        for loc_idx, location in enumerate(locations):
            loc_checkpoints = location_checkpoints.get(location.location_id, [])
            
            for cp_idx, checkpoint in enumerate(loc_checkpoints):
                # Determine camera count for this checkpoint
                if cameras_config and loc_idx < len(cameras_config) and cp_idx < len(cameras_config[loc_idx]):
                    camera_count = cameras_config[loc_idx][cp_idx]
                else:
                    camera_count = 1  # Default: 1 camera per checkpoint
                
                # Generate cameras for this checkpoint
                for cam_idx in range(camera_count):
                    device_id = f"CAM-{camera_counter:03d}"
                    # Camera name: Testing Location 1 - Checkpoint 1 - Camera 1
                    camera_name = f"{checkpoint.name} - Camera {cam_idx+1}"
                    
                    camera = MstCamera(
                        checkpoint_id=checkpoint.checkpoint_id,
                        location_id=location.location_id,
                        box_id=None,
                        device_id=device_id,
                        camera_name=camera_name,
                        camera_type="IP",
                        camera_model="Hikvision DS-2CD2T47G2-L",
                        fps=25,
                        ip_address=f"192.168.1.{100 + camera_counter}",
                        username="admin",
                        password_hash="admin123",
                        disabled=False,
                        deployment_type="Edge",
                        created_by=created_by,
                        updated_by=created_by
                    )
                    self.db.add(camera)
                    cameras.append(camera)
                    camera_counter += 1
        
        self.db.flush()
        return cameras

    def _auto_generate_default_user(self, request: CompanyOnboardingRequest, company_id: int, created_by: str):
        """Auto-generate default superadmin user: sa-{company_code}"""
        username = f"sa-{request.company_code.lower()}"
        password = f"sa-{request.company_code.lower()}"
        
        user = MstUser(
            company_id=company_id,
            name=f"Super Admin - {request.company_name}",
            username=username,
            email=request.company_email,
            phone=request.company_phone or "0000000000",
            role="manager",
            password_hash=hash_password(password),
            disabled=False,
            created_by=created_by,
            updated_by=created_by
        )
        self.db.add(user)
        self.db.flush()
        return user
    
    def _create_full_access_control(self, user_id: int, created_by: str):
        """Create full access control (all NULL = full access)"""
        access_controls = [
            TrnAccessControl(
                user_id=user_id,
                access_type='tab',
                access_data=None,  # NULL = All tabs
                can_view=True,
                can_create=True,
                can_update=True,
                can_delete=True,
                disabled=False,
                created_by=created_by,
                updated_by=created_by
            ),
            TrnAccessControl(
                user_id=user_id,
                access_type='component',
                access_data=None,  # NULL = All components
                can_view=True,
                can_create=True,
                can_update=True,
                can_delete=True,
                disabled=False,
                created_by=created_by,
                updated_by=created_by
            ),
            TrnAccessControl(
                user_id=user_id,
                access_type='location',
                access_data=None,  # NULL = All locations
                can_view=True,
                can_create=True,
                can_update=True,
                can_delete=True,
                disabled=False,
                created_by=created_by,
                updated_by=created_by
            ),
            TrnAccessControl(
                user_id=user_id,
                access_type='checkpoint',
                access_data=None,  # NULL = All checkpoints
                can_view=True,
                can_create=True,
                can_update=True,
                can_delete=True,
                disabled=False,
                created_by=created_by,
                updated_by=created_by
            )
        ]
        
        for ac in access_controls:
            self.db.add(ac)
        
        self.db.flush()
        return access_controls