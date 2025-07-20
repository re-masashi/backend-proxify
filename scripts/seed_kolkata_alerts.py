# scripts/seed_kolkata_alerts.py
import uuid
from datetime import UTC, datetime

from app import models
from app.database import SessionLocal

# Kolkata-specific mock alert data around your location (22.6254773, 88.4890283)
KOLKATA_ALERTS = [
    {
        "description": "Heavy monsoon flooding on Rashbehari Avenue near Gariahat Market. Water level 2-3 feet, avoid the area.",
        "type": "alert",
        "severity": 4,
        "location": {
            "type": "Point",
            "coordinates": [88.4890283, 22.6254773],
        },  # Your exact location
        "attachments": ["gariahat_flood.jpg", "rashbehari_water_level.mp4"],
    },
    {
        "description": "Traffic jam at Golpark crossing due to waterlogging. Buses and taxis stuck, use Metro instead.",
        "type": "alert",
        "severity": 3,
        "location": {
            "type": "Point",
            "coordinates": [88.4850283, 22.6204773],
        },  # 0.5km away
        "attachments": ["golpark_traffic.jpg"],
    },
    {
        "description": "Puja pandal setup causing road closure on Southern Avenue from 6 PM today. Pedestrian access only.",
        "type": "event",
        "severity": 2,
        "location": {
            "type": "Point",
            "coordinates": [88.4920283, 22.6280773],
        },  # 0.3km north
        "attachments": ["southern_avenue_pandal.jpg"],
    },
    {
        "description": "Lost cat near Kalighat Metro Station - Persian cat named Billu. Last seen yesterday evening.",
        "type": "help",
        "severity": 2,
        "location": {
            "type": "Point",
            "coordinates": [88.4870283, 22.6230773],
        },  # Near Kalighat
        "attachments": ["billu_cat_photo.jpg"],
    },
    {
        "description": "New Bengali sweets shop opening tomorrow at Triangular Park! First 100 customers get free rasgulla.",
        "type": "news",
        "severity": 1,
        "location": {
            "type": "Point",
            "coordinates": [88.4910283, 22.6270773],
        },  # Triangular Park area
        "attachments": ["sweet_shop_opening.jpg"],
    },
    {
        "description": "CESC power cut in Lake Gardens area from 2-6 PM today for maintenance work. Keep inverters charged!",
        "type": "alert",
        "severity": 3,
        "location": {
            "type": "Point",
            "coordinates": [88.4800283, 22.6300773],
        },  # Lake Gardens
        "attachments": ["cesc_notice.pdf"],
    },
    {
        "description": "Durga Puja organizing committee meeting at Ballygunge Phari tonight 8 PM. All volunteers welcome.",
        "type": "event",
        "severity": 1,
        "location": {
            "type": "Point",
            "coordinates": [88.4940283, 22.6290773],
        },  # Ballygunge
        "attachments": ["puja_committee_notice.jpg"],
    },
    {
        "description": "Rash driving by private bus (WB-01-AB-1234) on Rashbehari Avenue. Reported to traffic police.",
        "type": "alert",
        "severity": 3,
        "location": {
            "type": "Point",
            "coordinates": [88.4880283, 22.6240773],
        },  # Rashbehari
        "attachments": ["rash_bus_video.mp4"],
    },
    {
        "description": "Free health checkup camp at Rabindra Sarobar this weekend. Diabetes and BP screening available.",
        "type": "news",
        "severity": 1,
        "location": {
            "type": "Point",
            "coordinates": [88.4750283, 22.6180773],
        },  # Rabindra Sarobar
        "attachments": ["health_camp_details.pdf"],
    },
    {
        "description": "Street dogs gathering near Gariahat fish market creating disturbance. Local authorities notified.",
        "type": "help",
        "severity": 2,
        "location": {
            "type": "Point",
            "coordinates": [88.4900283, 22.6250773],
        },  # Gariahat market
        "attachments": ["stray_dogs_situation.jpg"],
    },
    {
        "description": "Buying old newspapers, books, and bottles. Good rates! Contact 98765-43210. Home collection available.",
        "type": "sale",
        "severity": 1,
        "location": {
            "type": "Point",
            "coordinates": [88.4860283, 22.6260773],
        },  # Nearby residential
        "attachments": [],
    },
    {
        "description": "Auto-rickshaw drivers on strike near Tollygunge Metro. Use app cabs or public buses instead.",
        "type": "alert",
        "severity": 3,
        "location": {
            "type": "Point",
            "coordinates": [88.4700283, 22.6150773],
        },  # Tollygunge
        "attachments": ["auto_strike_notice.jpg"],
    },
]


def seed_kolkata_alerts():
    """Seed the database with Kolkata-specific mock alerts."""
    db = SessionLocal()

    try:
        # Find or create a test user
        test_user = (
            db.query(models.User)
            .filter(models.User.userid == "user_kolkata_123")
            .first()
        )

        if not test_user:
            test_user = models.User(
                id=uuid.uuid4(),
                userid="user_kolkata_123",
                email="kolkata.user@example.com",
                is_admin=False,
            )
            db.add(test_user)
            db.commit()
            db.refresh(test_user)
            print(f"✅ Created Kolkata test user: {test_user.email}")

        # Delete existing test alerts for this user
        existing_alerts = (
            db.query(models.Alert).filter(models.Alert.user_id == test_user.id).all()
        )

        for alert in existing_alerts:
            db.delete(alert)

        db.commit()
        print(f"🗑️ Deleted {len(existing_alerts)} existing Kolkata alerts")

        # Create Kolkata-specific alerts
        created_alerts = []
        for _i, alert_data in enumerate(KOLKATA_ALERTS):
            alert = models.Alert(
                id=uuid.uuid4(),
                user_id=test_user.id,
                description=alert_data["description"],
                type=alert_data["type"],
                status="pending",  # All pending for admin review
                severity=alert_data["severity"],
                location=f"POINT({alert_data['location']['coordinates'][0]} {alert_data['location']['coordinates'][1]})",
                attachments=alert_data["attachments"],
                created_at=datetime.now(UTC),
            )

            db.add(alert)
            created_alerts.append(alert)

        db.commit()

        for alert in created_alerts:
            db.refresh(alert)

        print(f"✅ Created {len(created_alerts)} Kolkata-area alerts")
        print("\n🏙️ Kolkata alerts created:")
        for alert in created_alerts:
            distance_info = "Near your location (22.625, 88.489)"
            print(
                f"  - {alert.type.upper()}: {alert.description[:60]}... (Severity: {alert.severity}) - {distance_info}"
            )

        print("\n🎉 Kolkata database seeded successfully!")
        print("📍 All alerts are within 2km of your location: 22.6254773, 88.4890283")
        print(
            "🌆 Areas covered: Gariahat, Golpark, Ballygunge, Lake Gardens, Rabindra Sarobar"
        )

        # Print some useful coordinates for testing
        print("\n📱 Test your location-based queries with:")
        print("   Your location: lat=22.6254773, lon=88.4890283")
        print("   Radius: 2-5km should show all these alerts")

    except Exception as e:
        print(f"❌ Error seeding Kolkata alerts: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("🏙️ Seeding Kolkata-specific alerts...")
    seed_kolkata_alerts()
