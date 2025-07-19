# scripts/seed_alerts.py
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

from geoalchemy2 import WKTElement
from sqlalchemy.orm import Session

sys.path.append(Path.parent(Path.parent(Path.resolve(__file__))))

from app import models
from app.database import engine

# First, create the users we'll reference
USERS_DATA = [
    {"clerk_id": "user_kolkata_123", "email": "weather@kolkata.gov.in"},
    {"clerk_id": "user_metro_official", "email": "info@metrorailway.gov.in"},
    {"clerk_id": "user_pet_owner_45", "email": "bruno.owner@gmail.com"},
    {"clerk_id": "user_forum_mall", "email": "marketing@forummall.in"},
    {"clerk_id": "user_ruby_hospital", "email": "events@rubyhospital.in"},
    {"clerk_id": "user_traffic_dept", "email": "traffic@kolkatapolice.gov.in"},
    {"clerk_id": "user_victoria_memorial", "email": "events@victoriamemorial.in"},
    {"clerk_id": "user_sskm_hospital", "email": "emergency@sskm.gov.in"},
]

NEARBY_ALERTS = [
    {
        "id": "alert_001",
        "description": "Heavy rainfall expected in Salt Lake area. Roads near City Centre may flood.",
        "type": "alert",
        "severity": 4,
        "coords": (88.4795, 22.6195),
        "user_clerk_id": "user_kolkata_123",
        "created_at": "2025-07-19T09:30:00Z",
    },
    {
        "id": "alert_002",
        "description": "Metro services delayed on Blue Line (Dakshineswar to Garia) due to technical issues",
        "type": "news",
        "severity": 3,
        "coords": (88.4856, 22.6289),
        "user_clerk_id": "user_metro_official",
        "created_at": "2025-07-19T08:15:00Z",
    },
    {
        "id": "alert_003",
        "description": "Lost golden retriever near Eco Park. Name is Bruno. Please contact if found.",
        "type": "help",
        "severity": 2,
        "coords": (88.4923, 22.6587),
        "user_clerk_id": "user_pet_owner_45",
        "created_at": "2025-07-19T07:45:00Z",
        "attachments": ["image_bruno_1.jpg"],
    },
    {
        "id": "alert_004",
        "description": "50% off on electronics at Forum Mall this weekend. Grand sale on all gadgets!",
        "type": "sale",
        "severity": 1,
        "coords": (88.4869, 22.6145),
        "user_clerk_id": "user_forum_mall",
        "created_at": "2025-07-19T06:00:00Z",
        "attachments": ["sale_poster.jpg"],
    },
    {
        "id": "alert_005",
        "description": "Free health checkup camp at Ruby Hospital today 10 AM - 4 PM",
        "type": "event",
        "severity": 2,
        "coords": (88.4134, 22.6039),
        "user_clerk_id": "user_ruby_hospital",
        "created_at": "2025-07-19T05:30:00Z",
    },
]

FEATURED_ALERTS = [
    {
        "id": "featured_001",
        "description": "Durga Puja pandal construction begins in Park Street area. Expect traffic diversions.",
        "type": "news",
        "severity": 3,
        "coords": (88.3639, 22.5726),
        "user_clerk_id": "user_traffic_dept",
        "created_at": "2025-07-19T04:00:00Z",
    },
    {
        "id": "featured_002",
        "description": "Bengali New Year celebration at Victoria Memorial. Cultural programs all day.",
        "type": "event",
        "severity": 1,
        "coords": (88.3426, 22.5448),
        "user_clerk_id": "user_victoria_memorial",
        "created_at": "2025-07-19T03:15:00Z",
    },
    {
        "id": "featured_003",
        "description": "Emergency: Blood donation needed urgently at SSKM Hospital for accident victim",
        "type": "help",
        "severity": 5,
        "coords": (88.3697, 22.5412),
        "user_clerk_id": "user_sskm_hospital",
        "created_at": "2025-07-19T02:30:00Z",
    },
]


def create_users(db: Session) -> dict:
    """Create users and return a mapping of clerk_id to UUID"""
    user_mapping = {}

    for user_data in USERS_DATA:
        # Check if user already exists
        existing_user = (
            db.query(models.User)
            .filter(models.User.userid == user_data["clerk_id"])
            .first()
        )

        if existing_user:
            user_mapping[user_data["clerk_id"]] = existing_user.id
            continue

        # Create new user
        new_user = models.User(
            userid=user_data["clerk_id"],
            email=user_data["email"],
            is_admin=False,
            created_at=datetime.now(UTC),
        )

        db.add(new_user)
        db.flush()  # Get the ID
        user_mapping[user_data["clerk_id"]] = new_user.id

    db.commit()
    return user_mapping


def make_alert(row: dict, user_mapping: dict) -> models.Alert:
    """Convert a row dict into an Alert SQLAlchemy model."""
    lon, lat = row["coords"]
    user_uuid = user_mapping[row["user_clerk_id"]]

    return models.Alert(
        id=uuid.uuid5(uuid.NAMESPACE_URL, row["id"]),
        user_id=user_uuid,  # Now using actual UUID
        description=row["description"],
        type=row["type"],
        severity=row["severity"],
        status="reviewed",
        location=WKTElement(f"POINT({lon} {lat})", srid=4326),
        attachments=row.get("attachments", []),
        created_at=datetime.fromisoformat(row["created_at"].replace("Z", "+00:00")),
        updated_at=datetime.now(UTC),
    )


def seed():
    models.Base.metadata.create_all(bind=engine)

    with Session(engine) as db:
        print("Creating users...")
        user_mapping = create_users(db)
        print(f"Created/found {len(user_mapping)} users")

        print("Checking existing alerts...")
        existing_alert_ids = {str(a.id) for a in db.query(models.Alert.id).all()}

        new_alerts = []
        all_alert_data = NEARBY_ALERTS + FEATURED_ALERTS

        for row in all_alert_data:
            alert_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, row["id"]))
            if alert_uuid not in existing_alert_ids:
                new_alerts.append(make_alert(row, user_mapping))

        if not new_alerts:
            print("Nothing to insert — alerts already seeded.")
            return

        print(f"Inserting {len(new_alerts)} alerts...")
        db.add_all(new_alerts)
        db.commit()
        print(f"✅ Successfully inserted {len(new_alerts)} alerts!")


if __name__ == "__main__":
    seed()
