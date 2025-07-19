# tests/test_my_alerts.py
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


def test_get_my_alerts_empty(client: TestClient, db_session: Session, test_user):
    """Test getting my alerts when user has none."""
    client.set_user_id(test_user.userid)

    response = client.get("/alerts/my-alerts")
    assert response.status_code == 200
    assert response.json() == []


def test_get_my_alerts_with_data(client: TestClient, db_session: Session, test_user):
    """Test getting my alerts when user has created some."""
    client.set_user_id(test_user.userid)

    # Create some alerts
    alert_data_1 = {
        "description": "First alert by user",
        "type": "alert",
        "location": {"type": "Point", "coordinates": [-122.4194, 37.7749]},
        "severity": 3,
    }
    alert_data_2 = {
        "description": "Second alert by user",
        "type": "news",
        "location": {"type": "Point", "coordinates": [-122.4194, 37.7749]},
        "severity": 2,
    }

    # Create alerts
    response1 = client.post("/alerts/", json=alert_data_1)
    response2 = client.post("/alerts/", json=alert_data_2)
    assert response1.status_code == 201
    assert response2.status_code == 201

    # Get my alerts
    response = client.get("/alerts/my-alerts")
    assert response.status_code == 200

    my_alerts = response.json()
    assert len(my_alerts) == 2

    # Fix: If they're coming back in creation order (oldest first)
    assert my_alerts[0]["description"] == "First alert by user"
    assert my_alerts[1]["description"] == "Second alert by user"


def test_get_my_alerts_filtered_by_status(
    client: TestClient, db_session: Session, test_user, test_admin
):
    """Test filtering my alerts by status."""
    client.set_user_id(test_user.userid)

    # Create an alert
    alert_data = {
        "description": "Alert to be approved",
        "type": "news",
        "location": {"type": "Point", "coordinates": [-122.4194, 37.7749]},
        "severity": 2,
    }

    create_response = client.post("/alerts/", json=alert_data)
    alert_id = create_response.json()["id"]

    # Check pending alerts
    response = client.get("/alerts/my-alerts?status=pending")
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["status"] == "pending"

    # Check reviewed alerts (should be empty)
    response = client.get("/alerts/my-alerts?status=reviewed")
    assert response.status_code == 200
    assert len(response.json()) == 0

    # Approve the alert (as admin)
    from tests.test_admin_flow import create_admin_user

    admin1 = create_admin_user(
        db_session, "admin_my_alerts_1", "admin1.myalerts@test.com"
    )
    admin2 = create_admin_user(
        db_session, "admin_my_alerts_2", "admin2.myalerts@test.com"
    )

    # Two approvals needed
    client.set_user_id(admin1.userid)
    client.post(f"/api/admin/alerts/{alert_id}/review", json={"vote": True})

    client.set_user_id(admin2.userid)
    review_response = client.post(
        f"/api/admin/alerts/{alert_id}/review", json={"vote": True}
    )
    assert review_response.json()["status"] == "reviewed"

    # Check as original user
    client.set_user_id(test_user.userid)

    # Check pending alerts (should be empty now)
    response = client.get("/alerts/my-alerts?status=pending")
    assert len(response.json()) == 0

    # Check reviewed alerts (should have one)
    response = client.get("/alerts/my-alerts?status=reviewed")
    assert len(response.json()) == 1
    assert response.json()[0]["status"] == "reviewed"


def test_get_my_alert_stats(client: TestClient, db_session: Session, test_user):
    """Test getting user alert statistics."""
    client.set_user_id(test_user.userid)

    # Initially no alerts
    response = client.get("/alerts/my-alerts/stats")
    assert response.status_code == 200
    stats = response.json()
    assert stats["total"] == 0
    assert stats["pending"] == 0
    assert stats["approved"] == 0
    assert stats["rejected"] == 0

    # Create some alerts
    for i in range(3):
        alert_data = {
            "description": f"Test alert {i}",
            "type": "news",
            "location": {"type": "Point", "coordinates": [-122.4194, 37.7749]},
            "severity": 1,
        }
        client.post("/alerts/", json=alert_data)

    # Check stats again
    response = client.get("/alerts/my-alerts/stats")
    assert response.status_code == 200
    stats = response.json()
    assert stats["total"] == 3
    assert stats["pending"] == 3
    assert stats["approved"] == 0
    assert stats["rejected"] == 0


def test_cannot_see_other_users_alerts(
    client: TestClient, db_session: Session, test_user, test_admin
):
    """Test that users can only see their own alerts in my-alerts."""

    # User creates an alert
    client.set_user_id(test_user.userid)
    user_alert_data = {
        "description": "User's private alert",
        "type": "help",
        "location": {"type": "Point", "coordinates": [-122.4194, 37.7749]},
        "severity": 1,
    }
    client.post("/alerts/", json=user_alert_data)

    # Admin creates an alert
    client.set_user_id(test_admin.userid)
    admin_alert_data = {
        "description": "Admin's private alert",
        "type": "news",
        "location": {"type": "Point", "coordinates": [-122.4194, 37.7749]},
        "severity": 2,
    }
    client.post("/alerts/", json=admin_alert_data)

    # User should only see their own alert
    client.set_user_id(test_user.userid)
    response = client.get("/alerts/my-alerts")
    my_alerts = response.json()
    assert len(my_alerts) == 1
    assert my_alerts[0]["description"] == "User's private alert"

    # Admin should only see their own alert
    client.set_user_id(test_admin.userid)
    response = client.get("/alerts/my-alerts")
    admin_alerts = response.json()
    assert len(admin_alerts) == 1
    assert admin_alerts[0]["description"] == "Admin's private alert"


def test_my_alerts_requires_authentication(client: TestClient):
    """Test that my-alerts endpoint requires authentication."""
    client.clear_user_id()

    response = client.get("/alerts/my-alerts")
    assert response.status_code == 401

    response = client.get("/alerts/my-alerts/stats")
    assert response.status_code == 401
