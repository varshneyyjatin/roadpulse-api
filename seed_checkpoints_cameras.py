"""Seed Script - Add Checkpoints and Cameras Only
Adds checkpoints and cameras to existing company and locations"""

import sys
from sqlalchemy.orm import Session
from application.database.session import SessionLocal
from application.database.models.location import MstLocation
from application.database.models.checkpoint import MstCheckpoint
from application.database.models.camera import MstCamera

def seed_checkpoints_cameras():
    """Add checkpoints and cameras to existing database"""
    db: Session = SessionLocal()
    
    try:
        print("🌱 Starting checkpoint and camera seeding...")
        
        # Get existing locations
        print("\n📍 Fetching existing locations...")
        locations = db.query(MstLocation).all()
        
        if not locations:
            print("❌ No locations found! Please run the main seed script first.")
            sys.exit(1)
        
        print(f"   ✓ Found {len(locations)} locations")
        for loc in locations:
            print(f"     • {loc.location_name} ({loc.location_code})")
        
        # Create location lookup
        location_map = {loc.location_code: loc for loc in locations}
        
        # Create Checkpoints
        print("\n🚪 Creating checkpoints...")
        checkpoints = create_checkpoints(db, location_map)
        
        # Create Cameras
        print("\n📹 Creating cameras...")
        cameras = create_cameras(db, checkpoints)
        
        db.commit()
        print("\n✅ Checkpoints and cameras seeding completed successfully!")
        print_summary(checkpoints, cameras)
        
    except Exception as e:
        db.rollback()
        print(f"\n❌ Error during seeding: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()


def create_checkpoints(db: Session, location_map):
    """Create checkpoints for locations"""
    checkpoints_data = [
        # Moti Nagar checkpoints
        {
            "location_code": "TTL-MN",
            "name": "Parking",
            "checkpoint_type": "Entry",
            "direction": "In",
            "sequence_order": 1,
            "latitude": 28.6692,
            "longitude": 77.1510
        },
        {
            "location_code": "TTL-MN",
            "name": "Basement",
            "checkpoint_type": "Internal",
            "direction": None,
            "sequence_order": 2,
            "latitude": 28.6692,
            "longitude": 77.1510
        },
        {
            "location_code": "TTL-MN",
            "name": "Head Office",
            "checkpoint_type": "Entry",
            "direction": "In",
            "sequence_order": 3,
            "latitude": 28.6692,
            "longitude": 77.1510
        },
        # Navi Mumbai checkpoint
        {
            "location_code": "TTL-NM",
            "name": "1st Floor",
            "checkpoint_type": "Internal",
            "direction": None,
            "sequence_order": 1,
            "latitude": 19.0330,
            "longitude": 73.0297
        }
    ]
    
    checkpoints = []
    for data in checkpoints_data:
        location = location_map.get(data["location_code"])
        if not location:
            print(f"   ⚠️  Location {data['location_code']} not found, skipping checkpoint {data['name']}")
            continue
        
        checkpoint = MstCheckpoint(
            location_id=location.location_id,
            name=data["name"],
            checkpoint_type=data["checkpoint_type"],
            direction=data["direction"],
            sequence_order=data["sequence_order"],
            latitude=data["latitude"],
            longitude=data["longitude"],
            disabled=False,
            created_by="seed_script",
            updated_by="seed_script"
        )
        db.add(checkpoint)
        checkpoints.append(checkpoint)
    
    db.flush()
    print(f"   ✓ Created {len(checkpoints)} checkpoints")
    for cp in checkpoints:
        print(f"     • {cp.name} at location ID {cp.location_id}")
    
    return checkpoints


def create_cameras(db: Session, checkpoints):
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
                box_id=None,
                device_id=f"CAM-{checkpoint.checkpoint_id}-{i+1}",
                camera_name=f"{checkpoint.name} Camera {i+1}",
                camera_type="IP",
                camera_model="Hikvision DS-2CD2T47G2-L",
                fps=25,
                ip_address=f"192.168.1.{100 + camera_counter}",
                username="admin",
                password_hash="admin123",
                roi=None,
                loi=None,
                installed_on=None,
                disabled=False,
                deployment_type="Edge",
                remarks=None,
                created_by="seed_script",
                updated_by="seed_script"
            )
            db.add(camera)
            cameras.append(camera)
            camera_counter += 1
    
    db.flush()
    print(f"   ✓ Created {len(cameras)} cameras")
    for cam in cameras:
        print(f"     • {cam.camera_name} (Device: {cam.device_id})")
    
    return cameras


def print_summary(checkpoints, cameras):
    """Print summary of created data"""
    print("\n" + "="*70)
    print("📊 SEEDING SUMMARY")
    print("="*70)
    
    print(f"\n🚪 Checkpoints Created: {len(checkpoints)}")
    for cp in checkpoints:
        checkpoint_cameras = [c for c in cameras if c.checkpoint_id == cp.checkpoint_id]
        print(f"   • {cp.name} ({cp.checkpoint_type}) - {len(checkpoint_cameras)} camera(s)")
    
    print(f"\n📹 Cameras Created: {len(cameras)}")
    for cam in cameras:
        print(f"   • {cam.camera_name}")
        print(f"     - Device ID: {cam.device_id}")
        print(f"     - IP: {cam.ip_address}")
    
    print("\n" + "="*70)


if __name__ == "__main__":
    print("🚀 ANPR Checkpoint & Camera Seeding Script")
    print("="*60)
    seed_checkpoints_cameras()
