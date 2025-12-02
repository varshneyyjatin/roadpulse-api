"""
Database Seed Script
Creates initial company, location, checkpoint, camera, user, tab, component and access control data
"""
import sys
from sqlalchemy.orm import Session
from application.database.session import SessionLocal
from application.database.models.company import MstCompany
from application.database.models.location import MstLocation
from application.database.models.checkpoint import MstCheckpoint
from application.database.models.camera import MstCamera
from application.database.models.user import MstUser
from application.database.models.tab import MstTab
from application.database.models.component import MstComponent
from application.database.models.transactions.access_control import TrnAccessControl


def seed_database():
    """Main seeding function"""
    db: Session = SessionLocal()
    
    try:
        print("🌱 Starting database seeding...")
        
        # Create Company
        print("\n🏢 Creating company...")
        company = create_company(db)
        
        # Create Locations
        print("\n📍 Creating locations...")
        locations = create_locations(db, company)
        
        # Create Checkpoints
        print("\n🚪 Creating checkpoints...")
        checkpoints = create_checkpoints(db, locations)
        
        # Create Cameras
        print("\n📹 Creating cameras...")
        cameras = create_cameras(db, checkpoints, locations)
        
        # Create Users
        print("\n👤 Creating users...")
        users = create_users(db, company)
        
        # Create Tabs
        print("\n📑 Creating tabs...")
        tabs = create_tabs(db)
        
        # Create Components
        print("\n🧩 Creating components...")
        components = create_components(db, tabs)
        
        # Create Access Control
        print("\n🔐 Creating access control...")
        access_controls = create_access_control(db, users, tabs, components, locations)
        
        db.commit()
        print("\n✅ Database seeding completed successfully!")
        print_summary(company, locations, checkpoints, cameras, users, tabs, components, access_controls)
        
    except Exception as e:
        db.rollback()
        print(f"\n❌ Error during seeding: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()


def create_company(db: Session):
    """Create Transline Technologies company"""
    company = MstCompany(
        company_code="TTL",
        name="Transline Technologies",
        email="transline@gmail.com",
        phone="9876543210",
        address="Transline Technologies Office, India",
        data_retention_days=90,
        disabled=False,
        created_by="seed_script",
        updated_by="seed_script"
    )
    db.add(company)
    db.flush()
    
    print(f"   ✓ Created company: {company.name} (Code: {company.company_code})")
    return company


def create_locations(db: Session, company):
    """Create locations for Transline Technologies"""
    locations_data = [
        {
            "name": "Moti Nagar",
            "code": "TTL-MN",
            "type": "Office",
            "address": "Moti Nagar, New Delhi, India",
            "contact_person": "Site Manager",
            "phone": "9876543211"
        },
        {
            "name": "Navi Mumbai",
            "code": "TTL-NM",
            "type": "Office",
            "address": "Navi Mumbai, Maharashtra, India",
            "contact_person": "Site Manager",
            "phone": "9876543212"
        }
    ]
    
    locations = []
    for data in locations_data:
        location = MstLocation(
            company_id=company.id,
            location_name=data["name"],
            location_code=data["code"],
            location_type=data["type"],
            location_address=data["address"],
            contact_person_name=data["contact_person"],
            contact_person_phone=data["phone"],
            disabled=False,
            created_by="seed_script",
            updated_by="seed_script"
        )
        db.add(location)
        locations.append(location)
    
    db.flush()
    print(f"   ✓ Created {len(locations)} locations")
    return locations


def create_checkpoints(db: Session, locations):
    """Create checkpoints for locations"""
    checkpoints_data = [
        # Moti Nagar checkpoints
        {
            "location_idx": 0,  # Moti Nagar
            "name": "Parking",
            "type": "Entry",
            "description": "Parking area checkpoint"
        },
        {
            "location_idx": 0,  # Moti Nagar
            "name": "Basement",
            "type": "Internal",
            "description": "Basement checkpoint"
        },
        {
            "location_idx": 0,  # Moti Nagar
            "name": "Head Office",
            "type": "Entry",
            "description": "Head office entrance checkpoint"
        },
        # Navi Mumbai checkpoint
        {
            "location_idx": 1,  # Navi Mumbai
            "name": "1st Floor",
            "type": "Internal",
            "description": "1st floor checkpoint"
        }
    ]
    
    checkpoints = []
    for data in checkpoints_data:
        location = locations[data["location_idx"]]
        checkpoint = MstCheckpoint(
            location_id=location.location_id,
            name=data["name"],
            # description=data["description"],
            checkpoint_type=data["type"],
            latitude=28.6692 if data["location_idx"] == 0 else 19.0330,  # Delhi/Mumbai coords
            longitude=77.1510 if data["location_idx"] == 0 else 73.0297,
            disabled=False,
            created_by="seed_script",
            updated_by="seed_script"
        )
        db.add(checkpoint)
        checkpoints.append(checkpoint)
    
    db.flush()
    print(f"   ✓ Created {len(checkpoints)} checkpoints")
    return checkpoints


def create_cameras(db: Session, checkpoints, locations):
    """Create cameras for checkpoints"""
    cameras = []
    camera_counter = 1
    
    for checkpoint in checkpoints:
        # Parking checkpoint gets 2 cameras, others get 1
        num_cameras = 2 if checkpoint.name == "Parking" else 1
        
        for i in range(num_cameras):
            camera = MstCamera(
                checkpoint_id=checkpoint.checkpoint_id,
                location_id=checkpoint.location_id,
                box_id=None,  # No compute box for now
                device_id=f"CAM-{checkpoint.checkpoint_id}-{i+1}",
                camera_name=f"{checkpoint.name} Camera {i+1}",
                camera_type="IP",
                camera_model="Hikvision DS-2CD2T47G2-L",
                fps=25,
                ip_address=f"192.168.1.{100 + camera_counter}",
                username="admin",
                password_hash="admin123",
                disabled=False,
                deployment_type="Edge",
                created_by="seed_script",
                updated_by="seed_script"
            )
            db.add(camera)
            cameras.append(camera)
            camera_counter += 1
    
    db.flush()
    print(f"   ✓ Created {len(cameras)} cameras")
    return cameras


def create_users(db: Session, company):
    """Create users for Transline Technologies"""
    from application.auth.utils import hash_password
    
    users_data = [
        {
            "name": "Mansi Khattar",
            "username": "mansi.khattar",
            "email": "mansi.khattar@transline.com",
            "phone": "9876000001",
            "role": "superadmin",
            "password": "mansi.khattar"
        },
        {
            "name": "Jatin Varshney",
            "username": "jatin.varshney",
            "email": "jatin.varshney@transline.com",
            "phone": "9876000002",
            "role": "superadmin",
            "password": "jatin.varshney"
        },
        {
            "name": "Deepak Singh",
            "username": "deepak.singh",
            "email": "deepak.singh@transline.com",
            "phone": "9876000003",
            "role": "manager",
            "password": "deepak.singh"
        },
        {
            "name": "Abhidha",
            "username": "abhidha",
            "email": "abhidha@transline.com",
            "phone": "9876000004",
            "role": "admin",
            "password": "abhidha"
        },
        {
            "name": "Jatin",
            "username": "jatin",
            "email": "jatin@transline.com",
            "phone": "9876000005",
            "role": "creator",
            "password": "jatin"
        }
    ]
    
    users = []
    for data in users_data:
        user = MstUser(
            company_id=company.id,
            name=data["name"],
            username=data["username"],
            email=data["email"],
            phone=data["phone"],
            role=data["role"],
            password_hash=hash_password(data["password"]),
            disabled=False,
            created_by="seed_script",
            updated_by="seed_script"
        )
        db.add(user)
        users.append(user)
    
    db.flush()
    print(f"   ✓ Created {len(users)} users")
    
    # Print credentials
    print("\n" + "="*80)
    print("👤 USER CREDENTIALS")
    print("="*80)
    for data in users_data:
        print(f"Username: {data['username']:<20} | Password: {data['password']:<20} | Role: {data['role']}")
    print("="*80 + "\n")
    
    return users


def create_tabs(db: Session):
    """Create application tabs"""
    tabs_data = [
        {
            "name": "Dashboard",
            "description": "Main dashboard with KPIs and overview",
            "order": 1
        },
        {
            "name": "Reports",
            "description": "Reports and analytics",
            "order": 2
        },
        {
            "name": "Watchlist",
            "description": "Watchlist management",
            "order": 3
        },
        {
            "name": "Configurations",
            "description": "All Configurations settings",
            "order": 5
        }
    ]
    
    tabs = []
    for data in tabs_data:
        tab = MstTab(
            tab_name=data["name"],
            tab_description=data["description"],
            display_order=data["order"],
            disabled=False,
            created_by="seed_script",
            updated_by="seed_script"
        )
        db.add(tab)
        tabs.append(tab)
    
    db.flush()
    print(f"   ✓ Created {len(tabs)} tabs")
    return tabs


def create_components(db: Session, tabs):
    """Create components for each tab"""
    components_data = [
        # Dashboard components (tab_idx: 0)
        {"tab_idx": 0, "name": "Dashboard : KPIs", "code": "comp001", "type": "widget", "desc": "Dashboard : KPIs"},
        {"tab_idx": 0, "name": "Dashboard : Summary Data Table", "code": "comp002", "type": "table", "desc": "Dashboard : Summary Data Table"},
        {"tab_idx": 0, "name": "Dashboard : Date Range Filter", "code": "comp003", "type": "widget", "desc": "Dashboard : Date Range Filter"},
        {"tab_idx": 0, "name": "Dashboard : Add to Watchlist", "code": "comp004", "type": "table", "desc": "Dashboard : Add to Watchlist"},
        {"tab_idx": 0, "name": "Dashboard : Fix Vehicle Number", "code": "comp005", "type": "table", "desc": "Dashboard : Fix Vehicle Number"},
        {"tab_idx": 0, "name": "Dashboard : Vehicle Image Card Download", "code": "comp006", "type": "table", "desc": "Dashboard : Vehicle Image Card Download"},
        
        # Reports components (tab_idx: 1)
        {"tab_idx": 1, "name": "Report : Records Table", "code": "comp011", "type": "table", "desc": "Report : Records Table"},
        {"tab_idx": 1, "name": "Report : Vehicle Image Card Download", "code": "comp012", "type": "table", "desc": "Report : Vehicle Image Card Download"},
        {"tab_idx": 1, "name": "Report : Export Excel", "code": "comp013", "type": "table", "desc": "Report : Export Excel"},
        
        # Watchlist components (tab_idx: 2)
        {"tab_idx": 2, "name": "Table", "code": "comp009", "type": "table", "desc": "Table component for Watchlist"}
    ]
    
    components = []
    for data in components_data:
        tab = tabs[data["tab_idx"]]
        component = MstComponent(
            tab_id=tab.tab_id,
            component_name=data["name"],
            component_code=data["code"],
            component_type=data["type"],
            component_description=data["desc"],
            disabled=False,
            created_by="seed_script",
            updated_by="seed_script"
        )
        db.add(component)
        components.append(component)
    
    db.flush()
    print(f"   ✓ Created {len(components)} components")
    return components


def create_access_control(db: Session, users, tabs, components, locations):
    """Create access control for users using JSON format"""
    import json
    access_controls = []
    
    # Find users by username
    deepak = next(u for u in users if u.username == "deepak.singh")
    mansi = next(u for u in users if u.username == "mansi.khattar")
    jatin_varshney = next(u for u in users if u.username == "jatin.varshney")
    abhidha = next(u for u in users if u.username == "abhidha")
    jatin = next(u for u in users if u.username == "jatin")
    
    # Find tabs by name
    dashboard_tab = next(t for t in tabs if t.tab_name == "Dashboard")
    reports_tab = next(t for t in tabs if t.tab_name == "Reports")
    watchlist_tab = next(t for t in tabs if t.tab_name == "Watchlist")
    
    # Find components
    comp001 = next(c for c in components if c.component_code == "comp001")  # Dashboard KPIs
    comp002 = next(c for c in components if c.component_code == "comp002")  # Dashboard Table
    comp009 = next(c for c in components if c.component_code == "comp009")  # Watchlist Table
    comp003 = next(c for c in components if c.component_code == "comp003")  # Date Range Filter
    
    # Find locations
    moti_nagar = next(l for l in locations if l.location_code == "TTL-MN")
    navi_mumbai = next(l for l in locations if l.location_code == "TTL-NM")
    
    # ========== DEEPAK SINGH (Manager) - Full Access ==========
    # All tabs (NULL access_data = ALL)
    access_controls.append(TrnAccessControl(
        user_id=deepak.id, access_type='tab', access_data=None,
        can_view=True, can_create=True, can_update=True, can_delete=True,
        disabled=False, created_by="seed_script", updated_by="seed_script"
    ))
    
    # All components (NULL access_data = ALL)
    access_controls.append(TrnAccessControl(
        user_id=deepak.id, access_type='component', access_data=None,
        can_view=True, can_create=True, can_update=True, can_delete=True,
        disabled=False, created_by="seed_script", updated_by="seed_script"
    ))
    
    # All locations (NULL access_data = ALL)
    access_controls.append(TrnAccessControl(
        user_id=deepak.id, access_type='location', access_data=None,
        can_view=True, can_create=True, can_update=True, can_delete=True,
        disabled=False, created_by="seed_script", updated_by="seed_script"
    ))
    
    # All checkpoints (NULL access_data = ALL)
    access_controls.append(TrnAccessControl(
        user_id=deepak.id, access_type='checkpoint', access_data=None,
        can_view=True, can_create=True, can_update=True, can_delete=True,
        disabled=False, created_by="seed_script", updated_by="seed_script"
    ))
    
    # ========== MANSI (Superadmin) - Dashboard & Reports tabs only ==========
    # Only Dashboard and Reports tabs
    tab_ids = [dashboard_tab.tab_id, reports_tab.tab_id]
    access_controls.append(TrnAccessControl(
        user_id=mansi.id, access_type='tab',
        access_data=json.dumps({"access_ids": tab_ids}),
        can_view=True, can_create=True, can_update=True, can_delete=True,
        disabled=False, created_by="seed_script", updated_by="seed_script"
    ))
    
    # All components (NULL = ALL)
    access_controls.append(TrnAccessControl(
        user_id=mansi.id, access_type='component', access_data=None,
        can_view=True, can_create=True, can_update=True, can_delete=True,
        disabled=False, created_by="seed_script", updated_by="seed_script"
    ))
    
    # All locations
    access_controls.append(TrnAccessControl(
        user_id=mansi.id, access_type='location', access_data=None,
        can_view=True, can_create=True, can_update=True, can_delete=True,
        disabled=False, created_by="seed_script", updated_by="seed_script"
    ))
    
    # All checkpoints
    access_controls.append(TrnAccessControl(
        user_id=mansi.id, access_type='checkpoint', access_data=None,
        can_view=True, can_create=True, can_update=True, can_delete=True,
        disabled=False, created_by="seed_script", updated_by="seed_script"
    ))
    
    # ========== JATIN VARSHNEY (Superadmin) - Dashboard & Reports with specific components ==========
    # Only Dashboard and Reports tabs
    access_controls.append(TrnAccessControl(
        user_id=jatin_varshney.id, access_type='tab',
        access_data=json.dumps({"access_ids": tab_ids}),
        can_view=True, can_create=True, can_update=True, can_delete=True,
        disabled=False, created_by="seed_script", updated_by="seed_script"
    ))
    
    # Specific components: comp001, comp002, comp009, comp003
    component_ids = [comp001.component_id, comp002.component_id, comp009.component_id, comp003.component_id]
    access_controls.append(TrnAccessControl(
        user_id=jatin_varshney.id, access_type='component',
        access_data=json.dumps({"access_ids": component_ids}),
        can_view=True, can_create=True, can_update=True, can_delete=True,
        disabled=False, created_by="seed_script", updated_by="seed_script"
    ))
    
    # All locations
    access_controls.append(TrnAccessControl(
        user_id=jatin_varshney.id, access_type='location', access_data=None,
        can_view=True, can_create=True, can_update=True, can_delete=True,
        disabled=False, created_by="seed_script", updated_by="seed_script"
    ))
    
    # All checkpoints
    access_controls.append(TrnAccessControl(
        user_id=jatin_varshney.id, access_type='checkpoint', access_data=None,
        can_view=True, can_create=True, can_update=True, can_delete=True,
        disabled=False, created_by="seed_script", updated_by="seed_script"
    ))
    
    # ========== ABHIDHA (Admin) - Limited Access ==========
    # Only Dashboard tab
    access_controls.append(TrnAccessControl(
        user_id=abhidha.id, access_type='tab',
        access_data=json.dumps({"access_ids": [dashboard_tab.tab_id]}),
        can_view=True, can_create=False, can_update=False, can_delete=False,
        disabled=False, created_by="seed_script", updated_by="seed_script"
    ))
    
    # Components: comp002, comp001 (Dashboard Table and KPIs)
    abhidha_components = [comp002.component_id, comp001.component_id]
    access_controls.append(TrnAccessControl(
        user_id=abhidha.id, access_type='component',
        access_data=json.dumps({"access_ids": abhidha_components}),
        can_view=True, can_create=False, can_update=False, can_delete=False,
        disabled=False, created_by="seed_script", updated_by="seed_script"
    ))
    
    # Only Moti Nagar location
    access_controls.append(TrnAccessControl(
        user_id=abhidha.id, access_type='location',
        access_data=json.dumps({"access_ids": [moti_nagar.location_id]}),
        can_view=True, can_create=False, can_update=False, can_delete=False,
        disabled=False, created_by="seed_script", updated_by="seed_script"
    ))
    
    # All checkpoints
    access_controls.append(TrnAccessControl(
        user_id=abhidha.id, access_type='checkpoint', access_data=None,
        can_view=True, can_create=False, can_update=False, can_delete=False,
        disabled=False, created_by="seed_script", updated_by="seed_script"
    ))
    
    # ========== JATIN (Creator) - Full Access ==========
    # All tabs (NULL access_data = ALL)
    access_controls.append(TrnAccessControl(
        user_id=jatin.id, access_type='tab', access_data=None,
        can_view=True, can_create=True, can_update=True, can_delete=True,
        disabled=False, created_by="seed_script", updated_by="seed_script"
    ))
    
    # All components (NULL access_data = ALL)
    access_controls.append(TrnAccessControl(
        user_id=jatin.id, access_type='component', access_data=None,
        can_view=True, can_create=True, can_update=True, can_delete=True,
        disabled=False, created_by="seed_script", updated_by="seed_script"
    ))
    
    # All locations (NULL access_data = ALL)
    access_controls.append(TrnAccessControl(
        user_id=jatin.id, access_type='location', access_data=None,
        can_view=True, can_create=True, can_update=True, can_delete=True,
        disabled=False, created_by="seed_script", updated_by="seed_script"
    ))
    
    # All checkpoints (NULL access_data = ALL)
    access_controls.append(TrnAccessControl(
        user_id=jatin.id, access_type='checkpoint', access_data=None,
        can_view=True, can_create=True, can_update=True, can_delete=True,
        disabled=False, created_by="seed_script", updated_by="seed_script"
    ))
    
    # Add all to database
    for ac in access_controls:
        db.add(ac)
    
    db.flush()
    print(f"   ✓ Created {len(access_controls)} access control entries")
    return access_controls


def print_summary(company, locations, checkpoints, cameras, users, tabs, components, access_controls):
    """Print summary of created data"""
    print("\n" + "="*70)
    print("📊 SEEDING SUMMARY")
    print("="*70)
    print(f"🏢 Company Created:")
    print(f"   • Name: {company.name}")
    print(f"   • Code: {company.company_code}")
    print(f"   • Email: {company.email}")
    
    print(f"\n📍 Locations: {len(locations)}")
    for loc in locations:
        print(f"   • {loc.location_name} ({loc.location_code})")
    
    print(f"\n👥 Users: {len(users)}")
    for user in users:
        user_access = [ac for ac in access_controls if ac.user_id == user.id]
        print(f"   • {user.name} ({user.role}) - {len(user_access)} access entries")
    
    print(f"\n📑 Tabs & Components: {len(tabs)} tabs, {len(components)} components")
    
    print(f"\n🔐 Access Control Summary:")
    print(f"   • Deepak Singh: Full access to everything")
    print(f"   • Mansi & Jatin: All tabs, no Blacklist/Drivers components")
    print(f"   • Abhidha: Dashboard only, no KPI, Moti Nagar only")
    
    print(f"\n📊 Total Summary:")
    print(f"   • Locations: {len(locations)}")
    print(f"   • Checkpoints: {len(checkpoints)}")
    print(f"   • Cameras: {len(cameras)}")
    print(f"   • Users: {len(users)}")
    print(f"   • Tabs: {len(tabs)}")
    print(f"   • Components: {len(components)}")
    print(f"   • Access Controls: {len(access_controls)}")
    print("="*70)


if __name__ == "__main__":
    print("🚀 ANPR Database Seeding Script")
    print("="*60)
    seed_database()
