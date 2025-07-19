# tests/test_notifications.py
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app import models, schemas


def test_get_notifications_empty(client: TestClient, db_session: Session, test_user):
    """Test getting notifications when user has none."""
    client.set_user_id(test_user.userid)

    response = client.get("/notifications/")
    assert response.status_code == 200
    assert response.json() == []


def test_create_notification_via_crud(db_session: Session, test_user):
    """Test creating notification via CRUD function."""
    from app import crud

    notification_data = schemas.NotificationCreate(
        user_id=test_user.id,
        title="Test Notification",
        message="This is a test notification",
        type="system",
        data={"test_key": "test_value"},
    )

    notification = crud.create_notification(db_session, notification_data)

    assert notification.id is not None
    assert notification.title == "Test Notification"
    assert notification.message == "This is a test notification"
    assert notification.type == "system"
    assert not notification.read
    assert notification.data == {"test_key": "test_value"}


def test_get_notifications_with_data(
    client: TestClient, db_session: Session, test_user
):
    """Test getting notifications when user has some."""
    from app import crud

    client.set_user_id(test_user.userid)

    # Create test notifications
    notification1 = schemas.NotificationCreate(
        user_id=test_user.id,
        title="First Notification",
        message="First message",
        type="alert",
    )
    notification2 = schemas.NotificationCreate(
        user_id=test_user.id,
        title="Second Notification",
        message="Second message",
        type="admin",
    )

    crud.create_notification(db_session, notification1)
    crud.create_notification(db_session, notification2)

    response = client.get("/notifications/")
    assert response.status_code == 200

    notifications = response.json()
    assert len(notifications) == 2

    # Fix: If they're coming back in creation order (oldest first)
    assert notifications[0]["title"] == "First Notification"
    assert notifications[1]["title"] == "Second Notification"


def test_get_unread_notifications_only(
    client: TestClient, db_session: Session, test_user
):
    """Test filtering for unread notifications only."""
    from app import crud

    client.set_user_id(test_user.userid)

    # Create one read and one unread notification
    notification1 = crud.create_notification(
        db_session,
        schemas.NotificationCreate(
            user_id=test_user.id,
            title="Read Notification",
            message="This is read",
            type="system",
        ),
    )
    crud.create_notification(
        db_session,
        schemas.NotificationCreate(
            user_id=test_user.id,
            title="Unread Notification",
            message="This is unread",
            type="alert",
        ),
    )

    # Mark first notification as read
    notification1.read = True
    db_session.commit()

    # Get only unread notifications
    response = client.get("/notifications/?unread_only=true")
    assert response.status_code == 200

    notifications = response.json()
    assert len(notifications) == 1
    assert notifications[0]["title"] == "Unread Notification"


def test_get_unread_count(client: TestClient, db_session: Session, test_user):
    """Test getting unread notification count."""
    from app import crud

    client.set_user_id(test_user.userid)

    # Initially no notifications
    response = client.get("/notifications/count")
    assert response.status_code == 200
    assert response.json()["unread_count"] == 0

    # Create some notifications
    for i in range(3):
        crud.create_notification(
            db_session,
            schemas.NotificationCreate(
                user_id=test_user.id,
                title=f"Notification {i}",
                message=f"Message {i}",
                type="alert",
            ),
        )

    response = client.get("/notifications/count")
    assert response.status_code == 200
    assert response.json()["unread_count"] == 3


def test_mark_notification_as_read(client: TestClient, db_session: Session, test_user):
    """Test marking a specific notification as read."""
    from app import crud

    client.set_user_id(test_user.userid)

    # Create a notification
    notification = crud.create_notification(
        db_session,
        schemas.NotificationCreate(
            user_id=test_user.id,
            title="Test Notification",
            message="Test message",
            type="alert",
        ),
    )

    assert not notification.read

    # Mark as read
    response = client.put(f"/notifications/{notification.id}/read")
    assert response.status_code == 200
    assert response.json()["message"] == "Notification marked as read"

    # Verify it's marked as read
    db_session.refresh(notification)
    assert notification.read


def test_mark_all_notifications_as_read(
    client: TestClient, db_session: Session, test_user
):
    """Test marking all notifications as read."""
    from app import crud

    client.set_user_id(test_user.userid)

    # Create multiple notifications
    for i in range(3):
        crud.create_notification(
            db_session,
            schemas.NotificationCreate(
                user_id=test_user.id,
                title=f"Notification {i}",
                message=f"Message {i}",
                type="alert",
            ),
        )

    # Mark all as read
    response = client.put("/notifications/mark-all-read")
    assert response.status_code == 200
    assert "Marked 3 notifications as read" in response.json()["message"]

    # Verify count is now 0
    response = client.get("/notifications/count")
    assert response.json()["unread_count"] == 0


def test_delete_notification(client: TestClient, db_session: Session, test_user):
    """Test deleting a specific notification."""
    from app import crud

    client.set_user_id(test_user.userid)

    # Create a notification
    notification = crud.create_notification(
        db_session,
        schemas.NotificationCreate(
            user_id=test_user.id,
            title="To Delete",
            message="This will be deleted",
            type="system",
        ),
    )

    # Delete the notification
    response = client.delete(f"/notifications/{notification.id}")
    assert response.status_code == 200
    assert response.json()["message"] == "Notification deleted"

    # Verify it's deleted
    deleted_notification = (
        db_session.query(models.Notification)
        .filter(models.Notification.id == notification.id)
        .first()
    )
    assert deleted_notification is None


def test_cannot_access_other_users_notifications(
    client: TestClient, db_session: Session, test_user, test_admin
):
    """Test that users cannot access other users' notifications."""
    from app import crud

    # Create notification for admin
    admin_notification = crud.create_notification(
        db_session,
        schemas.NotificationCreate(
            user_id=test_admin.id,
            title="Admin Notification",
            message="For admin only",
            type="admin",
        ),
    )

    # Try to access as regular user
    client.set_user_id(test_user.userid)

    # Try to mark admin's notification as read
    response = client.put(f"/notifications/{admin_notification.id}/read")
    assert response.status_code == 404

    # Try to delete admin's notification
    response = client.delete(f"/notifications/{admin_notification.id}")
    assert response.status_code == 404


def test_notification_created_on_alert_approval(
    client: TestClient, db_session: Session, test_user, test_admin
):
    """Test that notification is created when alert is approved."""

    # Create an alert
    alert_data = {
        "description": "Test alert for notification",
        "type": "news",
        "location": {"type": "Point", "coordinates": [-122.4194, 37.7749]},
        "severity": 2,
    }

    client.set_user_id(test_user.userid)
    create_response = client.post("/alerts/", json=alert_data)
    assert create_response.status_code == 201
    alert_id = create_response.json()["id"]

    # Admin approves the alert (need 2 approvals)
    client.set_user_id(test_admin.userid)

    # First approval
    review_response = client.post(
        f"/api/admin/alerts/{alert_id}/review", json={"vote": True}
    )
    assert review_response.status_code == 200

    # Create second admin for second approval
    from tests.test_admin_flow import create_admin_user

    admin2 = create_admin_user(
        db_session, "admin_notification_test", "admin.notif@test.com"
    )

    client.set_user_id(admin2.userid)
    review_response = client.post(
        f"/api/admin/alerts/{alert_id}/review", json={"vote": True}
    )
    assert review_response.status_code == 200
    assert review_response.json()["status"] == "reviewed"

    # Check that user got notification
    client.set_user_id(test_user.userid)
    notifications_response = client.get("/notifications/")
    notifications = notifications_response.json()

    assert len(notifications) == 1
    assert notifications[0]["title"] == "Alert Approved"
    assert "approved" in notifications[0]["message"]
