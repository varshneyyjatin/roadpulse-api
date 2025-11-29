"""
Access Control Helper Functions
Provides utilities for managing user access and global feature launches
"""
from datetime import datetime
from typing import List, Dict, Optional
import json
from sqlalchemy import and_, or_


def create_user_with_access(db_session, user_data: dict, access_config: dict, created_by: str):
    """
    Create user and configure all access in one transaction.
    
    Args:
        db_session: SQLAlchemy session
        user_data: User basic info (name, email, role, company_id)
        access_config: Access configuration with tabs, features, locations, checkpoints
        created_by: Username of creator
        
    Returns:
        Created user object
    """
    from application.database.models.user import MstUser
    from application.database.models.transactions.user_access_model import TrnUserAccess
    
    # Create user
    user = MstUser(
        name=user_data['name'],
        username=user_data['username'],
        email=user_data['email'],
        phone=user_data.get('phone'),
        role=user_data['role'],
        company_id=user_data['company_id'],
        password_hash=user_data['password_hash'],
        created_by=created_by,
        updated_by=created_by
    )
    db_session.add(user)
    db_session.flush()  # Get user.id
    
    # Configure tab & component access
    for tab_config in access_config.get('tabs', []):
        if tab_config.get('enabled', False):
            # Add tab access
            tab_access = TrnUserAccess(
                user_id=user.id,
                access_type='tab',
                access_id=tab_config['tab_id'],
                can_view=True,
                created_by=created_by,
                updated_by=created_by
            )
            db_session.add(tab_access)
            
            # Add component access within tab
            for component_config in tab_config.get('components', []):
                if component_config.get('enabled', False):
                    perms = component_config.get('permissions', {})
                    component_access = TrnUserAccess(
                        user_id=user.id,
                        access_type='component',
                        access_id=component_config['component_id'],
                        can_view=perms.get('can_view', True),
                        can_create=perms.get('can_create', False),
                        can_update=perms.get('can_update', False),
                        can_delete=perms.get('can_delete', False),
                        can_export=perms.get('can_export', False),
                        created_by=created_by,
                        updated_by=created_by
                    )
                    db_session.add(component_access)
    
    # Configure location & checkpoint access
    for location_config in access_config.get('locations', []):
        if location_config.get('enabled', False):
            # Add location access
            location_access = TrnUserAccess(
                user_id=user.id,
                access_type='location',
                access_id=location_config['location_id'],
                can_view=True,
                created_by=created_by,
                updated_by=created_by
            )
            db_session.add(location_access)
            
            # Add checkpoint access within location
            for checkpoint_config in location_config.get('checkpoints', []):
                if checkpoint_config.get('enabled', False):
                    checkpoint_access = TrnUserAccess(
                        user_id=user.id,
                        access_type='checkpoint',
                        access_id=checkpoint_config['checkpoint_id'],
                        can_view=True,
                        created_by=created_by,
                        updated_by=created_by
                    )
                    db_session.add(checkpoint_access)
    
    db_session.commit()
    return user


def launch_component_globally(db_session, component_id: int, launch_config: dict, created_by: str):
    """
    Launch a component globally to all users (or specific scope) for a time period.
    
    Args:
        db_session: SQLAlchemy session
        component_id: Component to launch
        launch_config: Launch configuration
        created_by: Username of creator
        
    Example launch_config:
    {
        "launch_name": "AI Analytics Beta",
        "launch_from": "2024-01-01 00:00:00",
        "launch_until": "2024-01-31 23:59:59",
        "target_scope": "all",  # or "company", "location", "role"
        "target_scope_ids": [1, 2, 3],  # if scope is company/location
        "target_roles": ["admin", "manager"],  # if scope is role
        "permissions": {
            "can_view": True,
            "can_create": False,
            "can_update": False,
            "can_delete": False,
            "can_export": False
        },
        "post_launch_action": "lock",  # "lock", "keep", "ask"
        "launch_message": "New AI Analytics feature available!"
    }
    """
    from application.database.models.transactions.global_feature_launch_model import TrnGlobalComponentLaunch
    from application.database.models.transactions.user_access_model import TrnUserAccess
    from application.database.models.user import MstUser
    
    # Create global launch record
    launch = TrnGlobalComponentLaunch(
        component_id=component_id,
        launch_name=launch_config['launch_name'],
        launch_description=launch_config.get('launch_description'),
        launch_message=launch_config.get('launch_message'),
        launch_from=datetime.fromisoformat(launch_config['launch_from']),
        launch_until=datetime.fromisoformat(launch_config['launch_until']) if launch_config.get('launch_until') else None,
        target_scope=launch_config.get('target_scope', 'all'),
        target_scope_ids=json.dumps(launch_config.get('target_scope_ids', [])) if launch_config.get('target_scope_ids') else None,
        target_roles=json.dumps(launch_config.get('target_roles', [])) if launch_config.get('target_roles') else None,
        default_can_view=launch_config['permissions'].get('can_view', True),
        default_can_create=launch_config['permissions'].get('can_create', False),
        default_can_update=launch_config['permissions'].get('can_update', False),
        default_can_delete=launch_config['permissions'].get('can_delete', False),
        default_can_export=launch_config['permissions'].get('can_export', False),
        post_launch_action=launch_config.get('post_launch_action', 'lock'),
        launch_status='scheduled',
        created_by=created_by,
        updated_by=created_by
    )
    db_session.add(launch)
    db_session.flush()
    
    # Get target users
    users_query = db_session.query(MstUser).filter(MstUser.is_active == True)
    
    if launch_config.get('target_scope') == 'company' and launch_config.get('target_scope_ids'):
        users_query = users_query.filter(MstUser.company_id.in_(launch_config['target_scope_ids']))
    
    if launch_config.get('target_roles'):
        users_query = users_query.filter(MstUser.role.in_(launch_config['target_roles']))
    
    target_users = users_query.all()
    
    # Grant access to all target users
    for user in target_users:
        user_access = TrnUserAccess(
            user_id=user.id,
            access_type='component',
            access_id=component_id,
            can_view=launch_config['permissions'].get('can_view', True),
            can_create=launch_config['permissions'].get('can_create', False),
            can_update=launch_config['permissions'].get('can_update', False),
            can_delete=launch_config['permissions'].get('can_delete', False),
            can_export=launch_config['permissions'].get('can_export', False),
            active_from=datetime.fromisoformat(launch_config['launch_from']),
            active_until=datetime.fromisoformat(launch_config['launch_until']) if launch_config.get('launch_until') else None,
            global_launch_id=launch.id,  # Link to global launch
            created_by=created_by,
            updated_by=created_by
        )
        db_session.add(user_access)
    
    # Update launch stats
    launch.total_users_granted = len(target_users)
    launch.launch_status = 'active' if datetime.now() >= launch.launch_from else 'scheduled'
    
    db_session.commit()
    return launch


def check_user_access(db_session, user_id: int, access_type: str, access_id: int) -> Optional[Dict]:
    """
    Check if user has access to a specific resource.
    
    Args:
        db_session: SQLAlchemy session
        user_id: User ID
        access_type: 'tab', 'component', 'location', 'checkpoint'
        access_id: ID of the resource
    
    Returns:
        Dict with permissions if access exists, None otherwise
    """
    from application.database.models.transactions.user_access_model import TrnUserAccess
    
    now = datetime.now()
    
    access = db_session.query(TrnUserAccess).filter(
        TrnUserAccess.user_id == user_id,
        TrnUserAccess.access_type == access_type,
        TrnUserAccess.access_id == access_id,
        TrnUserAccess.is_active == True,
        TrnUserAccess.soft_deleted_at.is_(None),
        or_(
            TrnUserAccess.active_from.is_(None),
            TrnUserAccess.active_from <= now
        ),
        or_(
            TrnUserAccess.active_until.is_(None),
            TrnUserAccess.active_until >= now
        )
    ).first()
    
    if access:
        return {
            'can_view': access.can_view,
            'can_create': access.can_create,
            'can_update': access.can_update,
            'can_delete': access.can_delete,
            'can_export': access.can_export,
            'is_global_launch': access.is_global_launch,
            'launch_message': access.launch_message
        }
    
    return None


def get_user_accessible_tabs(db_session, user_id: int) -> List[int]:
    """Get list of tab IDs user can access"""
    from application.database.models.transactions.user_access_model import TrnUserAccess
    
    now = datetime.now()
    
    tabs = db_session.query(TrnUserAccess.access_id).filter(
        TrnUserAccess.user_id == user_id,
        TrnUserAccess.access_type == 'tab',
        TrnUserAccess.is_active == True,
        TrnUserAccess.soft_deleted_at.is_(None),
        or_(
            TrnUserAccess.active_from.is_(None),
            TrnUserAccess.active_from <= now
        ),
        or_(
            TrnUserAccess.active_until.is_(None),
            TrnUserAccess.active_until >= now
        )
    ).all()
    
    return [tab[0] for tab in tabs]


def get_user_accessible_components(db_session, user_id: int, tab_id: int = None) -> List[Dict]:
    """
    Get list of components user can access with permissions.
    Optionally filter by tab_id.
    """
    from application.database.models.transactions.user_access_model import TrnUserAccess
    from application.database.models.component import MstComponent
    
    now = datetime.now()
    
    query = db_session.query(TrnUserAccess, MstComponent).join(
        MstComponent,
        TrnUserAccess.access_id == MstComponent.component_id
    ).filter(
        TrnUserAccess.user_id == user_id,
        TrnUserAccess.access_type == 'component',
        TrnUserAccess.is_active == True,
        TrnUserAccess.soft_deleted_at.is_(None),
        MstComponent.is_active == True,
        or_(
            TrnUserAccess.active_from.is_(None),
            TrnUserAccess.active_from <= now
        ),
        or_(
            TrnUserAccess.active_until.is_(None),
            TrnUserAccess.active_until >= now
        )
    )
    
    if tab_id:
        query = query.filter(MstComponent.tab_id == tab_id)
    
    results = query.all()
    
    return [{
        'component_id': access.access_id,
        'component_name': component.component_name,
        'component_code': component.component_code,
        'component_type': component.component_type,
        'tab_id': component.tab_id,
        'display_order': component.display_order,
        'permissions': {
            'can_view': access.can_view,
            'can_create': access.can_create,
            'can_update': access.can_update,
            'can_delete': access.can_delete,
            'can_export': access.can_export
        },
        'is_global_launch': access.is_global_launch,
        'launch_message': access.launch_message
    } for access, component in results]


def get_user_tabs_with_components(db_session, user_id: int) -> List[Dict]:
    """
    Get all tabs user can access along with their accessible components.
    Returns hierarchical structure: tabs with nested components.
    """
    from application.database.models.transactions.user_access_model import TrnUserAccess
    from application.database.models.tab import MstTab
    from application.database.models.component import MstComponent
    
    now = datetime.now()
    
    # Get accessible tabs
    tab_ids = get_user_accessible_tabs(db_session, user_id)
    
    if not tab_ids:
        return []
    
    # Get tab details
    tabs = db_session.query(MstTab).filter(
        MstTab.tab_id.in_(tab_ids),
        MstTab.is_active == True,
        MstTab.soft_deleted_at.is_(None)
    ).order_by(MstTab.display_order).all()
    
    result = []
    for tab in tabs:
        # Get components for this tab
        components = get_user_accessible_components(db_session, user_id, tab.tab_id)
        
        result.append({
            'tab_id': tab.tab_id,
            'tab_name': tab.tab_name,
            'tab_code': tab.tab_code,
            'tab_icon': tab.tab_icon,
            'tab_route': tab.tab_route,
            'display_order': tab.display_order,
            'components': components
        })
    
    return result


def lock_expired_component_launches(db_session):
    """
    Background job to lock/remove expired component launches.
    Should be run periodically (e.g., daily cron job)
    """
    from application.database.models.transactions.global_feature_launch_model import TrnGlobalComponentLaunch
    from application.database.models.transactions.user_access_model import TrnUserAccess
    
    now = datetime.now()
    
    # Find expired launches
    expired_launches = db_session.query(TrnGlobalComponentLaunch).filter(
        TrnGlobalComponentLaunch.launch_status == 'active',
        TrnGlobalComponentLaunch.launch_until < now,
        TrnGlobalComponentLaunch.is_active == True
    ).all()
    
    for launch in expired_launches:
        if launch.post_launch_action == 'lock':
            # Disable all user accesses for this component launch
            db_session.query(TrnUserAccess).filter(
                TrnUserAccess.access_type == 'component',
                TrnUserAccess.access_id == launch.component_id,
                TrnUserAccess.is_global_launch == True,
                TrnUserAccess.active_until == launch.launch_until
            ).update({
                'is_active': False,
                'updated_by': 'system_cron'
            })
        
        # Mark launch as completed
        launch.launch_status = 'completed'
        launch.updated_by = 'system_cron'
    
    db_session.commit()
    return len(expired_launches)
