"""
API routes for user authentication.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from application.database.session import get_db
from application.auth.schemas import UserLogin, TokenResponse
from application.auth import crud
from application.auth.utils import verify_password, create_access_token, get_current_user
from application.helpers.logger import get_logger
from application.database.models.transactions.access_control import TrnAccessControl
from application.database.models.tab import MstTab
from application.database.models.component import MstComponent
from application.database.models.location import MstLocation

logger = get_logger("auth")
router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/login", response_model=TokenResponse)
def login_user(user: UserLogin, db: Session = Depends(get_db)):
    """User authentication - validates credentials and generates JWT access token (supports email or username)."""
    
    # Log login attempt with provided credentials
    login_method = "Email" if user.email else "Username" if user.username else "None"
    identifier = user.email if user.email else user.username if user.username else "N/A"
    
    # Validate input
    if not user.email and not user.username:
        logger.warning(f"Login Failed :: Method -> {login_method} :: Identifier -> {identifier} :: Reason -> No email or username provided")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email or username is required"
        )
    
    # Fetch user by email or username
    db_user = crud.get_user_by_email_or_username(db, identifier)
    
    if not db_user:
        logger.warning(f"Login Failed :: Method -> {login_method} :: Identifier -> {identifier} :: Reason -> User not found in database")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect credentials"
        )
    
    # Log found user details
    logger.info(f"Login Attempt :: Method -> {login_method} :: Identifier -> {identifier} :: Found -> Username: {db_user.username}, UserID: {db_user.id}")
    
    # Verify password
    if not verify_password(user.password, db_user.password_hash):
        logger.warning(f"Login Failed :: Method -> {login_method} :: Identifier -> {identifier} :: Username -> {db_user.username} :: UserID -> {db_user.id} :: Reason -> Incorrect password")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect credentials"
        )
    
    # Check if user is disabled
    if db_user.disabled:
        logger.warning(f"Login Failed :: Method -> {login_method} :: Identifier -> {identifier} :: Username -> {db_user.username} :: UserID -> {db_user.id} :: Reason -> Account disabled")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is disabled. Please contact support."
        )
    
    # Create JWT token
    token_data = {
        "user_id": db_user.id,
        "username": db_user.username,
        "name": db_user.name,
        "email": db_user.email,
        "role": db_user.role,
        "company_id": db_user.company_id
    }
    access_token = create_access_token(data=token_data)
    
    logger.info(f"Login Success :: Method -> {login_method} :: Identifier -> {identifier} :: Username -> {db_user.username} :: Email -> {db_user.email or 'N/A'} :: UserID -> {db_user.id} :: Role -> {db_user.role} :: CompanyID -> {db_user.company_id}")
    return TokenResponse(access_token=access_token, token_type="bearer")

@router.get("/me/access-control")
def get_user_access_control(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get complete access control information for the authenticated user.
    Returns tabs, components, and locations with full details.
    """
    user_id = current_user.user_id
    
    # Get user details from database
    from application.database.models.user import MstUser
    from application.database.models.company import MstCompany
    user = db.query(MstUser).filter(MstUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get company details
    company = db.query(MstCompany).filter(MstCompany.id == current_user.company_id).first()
    company_name = company.name if company else None
    
    # Get all access control entries for user
    import json
    access_entries = db.query(TrnAccessControl).filter(
        TrnAccessControl.user_id == user_id,
        TrnAccessControl.disabled == False,
        TrnAccessControl.is_deleted == False
    ).all()
    
    # Helper function to extract access IDs from entry
    def get_access_ids(entry):
        """Extract access IDs from entry - NULL means ALL access"""
        if entry.access_data:
            try:
                data = json.loads(entry.access_data)
                return data.get('access_ids', [])
            except:
                return []
        else:
            return None  # NULL means ALL access
    
    # Separate by type
    tab_accesses = [a for a in access_entries if a.access_type == 'tab']
    component_accesses = [a for a in access_entries if a.access_type == 'component']
    location_accesses = [a for a in access_entries if a.access_type == 'location']
    
    # Get accessible tabs
    tab_ids_list = []
    has_all_tabs = False
    for entry in tab_accesses:
        ids = get_access_ids(entry)
        if ids is None:
            has_all_tabs = True
            break
        tab_ids_list.extend(ids)
    
    if has_all_tabs:
        accessible_tabs = db.query(MstTab).filter(
            MstTab.disabled == False,
            MstTab.is_deleted == False
        ).order_by(MstTab.display_order).all()
    else:
        accessible_tabs = db.query(MstTab).filter(
            MstTab.tab_id.in_(tab_ids_list),
            MstTab.disabled == False,
            MstTab.is_deleted == False
        ).order_by(MstTab.display_order).all()
    
    # Get accessible components
    component_ids_list = []
    has_all_components = False
    component_permission_map = {}
    
    for entry in component_accesses:
        ids = get_access_ids(entry)
        if ids is None:
            has_all_components = True
            break
        component_ids_list.extend(ids)
        # Store permissions for each component ID
        for comp_id in ids:
            component_permission_map[comp_id] = {
                "can_view": entry.can_view,
                "can_create": entry.can_create,
                "can_update": entry.can_update,
                "can_delete": entry.can_delete
            }
    
    if has_all_components:
        accessible_components = db.query(MstComponent).filter(
            MstComponent.disabled == False,
            MstComponent.is_deleted == False
        ).all()
        component_permission_map = {c.component_id: {"can_view": True, "can_create": True, "can_update": True, "can_delete": True} for c in accessible_components}
    else:
        accessible_components = db.query(MstComponent).filter(
            MstComponent.component_id.in_(component_ids_list),
            MstComponent.disabled == False,
            MstComponent.is_deleted == False
        ).all()
    
    # Build tabs with nested components
    tabs = []
    for tab in accessible_tabs:
        tab_components = [c for c in accessible_components if c.tab_id == tab.tab_id]
        tabs.append({
            "tab_id": tab.tab_id,
            "tab_name": tab.tab_name,
            "tab_description": tab.tab_description,
            "display_order": tab.display_order,
            "components": [
                {
                    "component_id": c.component_id,
                    "component_name": c.component_name,
                    "component_code": c.component_code,
                    "component_type": c.component_type,
                    "component_description": c.component_description,
                    "permissions": component_permission_map.get(c.component_id, {})
                }
                for c in tab_components
            ]
        })
    
    # Separate checkpoint accesses
    checkpoint_accesses = [a for a in access_entries if a.access_type == 'checkpoint']
    
    # Get accessible locations
    location_ids_list = []
    has_all_locations = False
    for entry in location_accesses:
        ids = get_access_ids(entry)
        if ids is None:
            has_all_locations = True
            break
        location_ids_list.extend(ids)
    
    if has_all_locations:
        accessible_locations = db.query(MstLocation).filter(
            MstLocation.disabled == False,
            MstLocation.is_deleted == False
        ).all()
    else:
        accessible_locations = db.query(MstLocation).filter(
            MstLocation.location_id.in_(location_ids_list),
            MstLocation.disabled == False,
            MstLocation.is_deleted == False
        ).all()
    
    # Get accessible checkpoints
    from application.database.models.checkpoint import MstCheckpoint
    checkpoint_ids_list = []
    has_all_checkpoints = False
    for entry in checkpoint_accesses:
        ids = get_access_ids(entry)
        if ids is None:
            has_all_checkpoints = True
            break
        checkpoint_ids_list.extend(ids)
    
    if has_all_checkpoints:
        accessible_checkpoints = db.query(MstCheckpoint).filter(
            MstCheckpoint.disabled == False,
            MstCheckpoint.is_deleted == False
        ).all()
    elif checkpoint_ids_list:
        accessible_checkpoints = db.query(MstCheckpoint).filter(
            MstCheckpoint.checkpoint_id.in_(checkpoint_ids_list),
            MstCheckpoint.disabled == False,
            MstCheckpoint.is_deleted == False
        ).all()
    else:
        accessible_checkpoints = []
    
    # Get cameras for accessible checkpoints
    from application.database.models.camera import MstCamera
    accessible_checkpoint_ids = [cp.checkpoint_id for cp in accessible_checkpoints]
    cameras_for_checkpoints = db.query(MstCamera).filter(
        MstCamera.checkpoint_id.in_(accessible_checkpoint_ids),
        MstCamera.disabled == False,
        MstCamera.is_deleted == False
    ).all() if accessible_checkpoint_ids else []
    
    # Get compute boxes for accessible locations
    from application.database.models.compute_box import MstComputeBox
    accessible_location_ids = [loc.location_id for loc in accessible_locations]
    compute_boxes_for_locations = db.query(MstComputeBox).filter(
        MstComputeBox.location_id.in_(accessible_location_ids),
        MstComputeBox.disabled == False,
        MstComputeBox.is_deleted == False
    ).all() if accessible_location_ids else []
    
    # Build locations with nested checkpoints, cameras, and compute boxes
    locations = []
    for loc in accessible_locations:
        loc_checkpoints = [cp for cp in accessible_checkpoints if cp.location_id == loc.location_id]
        loc_boxes = [box for box in compute_boxes_for_locations if box.location_id == loc.location_id]
        
        locations.append({
            "location_id": loc.location_id,
            "location_name": loc.location_name,
            "location_code": loc.location_code,
            "location_type": loc.location_type,
            "location_address": loc.location_address,
            "compute_boxes": [
                {
                    "box_id": box.box_id,
                    "box_name": box.box_name,
                    "box_type": box.box_type,
                    "hardware_model": box.hardware_model,
                    "ip_address": box.ip_address,
                    "mac_address": box.mac_address,
                    "is_online": box.is_online,
                    "last_heartbeat": box.last_heartbeat.isoformat() if box.last_heartbeat else None
                }
                for box in loc_boxes
            ],
            "checkpoints": [
                {
                    "checkpoint_id": cp.checkpoint_id,
                    "checkpoint_name": cp.name,
                    "checkpoint_type": cp.checkpoint_type,
                    "direction": cp.direction,
                    "sequence_order": cp.sequence_order,
                    "cameras": [
                        {
                            "camera_id": cam.camera_id,
                            "device_id": cam.device_id,
                            "camera_name": cam.camera_name,
                            "camera_type": cam.camera_type,
                            "camera_model": cam.camera_model,
                            "ip_address": cam.ip_address
                        }
                        for cam in cameras_for_checkpoints if cam.checkpoint_id == cp.checkpoint_id
                    ]
                }
                for cp in loc_checkpoints
            ]
        })
    
    total_components = sum(len(t["components"]) for t in tabs)
    total_checkpoints = sum(len(l["checkpoints"]) for l in locations)
    total_boxes = sum(len(l["compute_boxes"]) for l in locations)
    
    logger.info(f"Access Control Fetched :: UserID -> {user_id} :: Username -> {current_user.username} :: Tabs -> {len(tabs)} :: Components -> {total_components} :: Locations -> {len(locations)} :: Checkpoints -> {total_checkpoints} :: ComputeBoxes -> {total_boxes}")
    
    # Format created_at date
    created_date = user.created_at.strftime("%d %b %Y") if user.created_at else None
    
    return {
        "user": {
            "user_id": current_user.user_id,
            "username": current_user.username,
            "email": current_user.email,
            "name": current_user.name,
            "role": current_user.role,
            "company_id": current_user.company_id,
            "company_name": company_name,
            "created_at": created_date
        },
        "access_control": {
            "tabs": tabs,
            "locations": locations
        },
        "summary": {
            "total_tabs": len(tabs),
            "total_components": total_components,
            "total_locations": len(locations),
            "total_checkpoints": total_checkpoints,
            "total_compute_boxes": total_boxes
        }
    }