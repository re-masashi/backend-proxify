import uuid

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from . import models, schemas


def get_user_by_clerk_id(db: Session, clerk_user_id: str):
    return db.query(models.User).filter(models.User.userid == clerk_user_id).first()


def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()


def create_user(db: Session, user: schemas.UserCreate):
    db_user = models.User(userid=user.userid, email=user.email, is_admin=user.is_admin)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def create_alert(
    db: Session, alert: schemas.AlertCreate, user_id: uuid.UUID
) -> models.Alert:
    # Convert GeoJSON-like Pydantic model to WKT format for GeoAlchemy2
    wkt_location = (
        f"POINT({alert.location.coordinates[0]} {alert.location.coordinates[1]})"
    )

    db_alert = models.Alert(
        description=alert.description,
        type=alert.type,
        location=wkt_location,
        severity=alert.severity,
        attachments=alert.attachments,
        user_id=user_id,
        status="pending",  # All new alerts start as pending
    )
    db.add(db_alert)
    db.commit()
    db.refresh(db_alert)
    return db_alert


def get_pending_alerts(db: Session):
    """Fetches all alerts that need admin review."""
    return (
        db.query(models.Alert)
        .filter(
            or_(models.Alert.status == "pending", models.Alert.status == "ai_reviewed")
        )
        .all()
    )


def get_alert_by_id(db: Session, alert_id: uuid.UUID) -> models.Alert | None:
    return db.query(models.Alert).filter(models.Alert.id == alert_id).first()


def get_alerts(db: Session, status: str = "reviewed", limit: int = 50):
    return (
        db.query(models.Alert)
        .options(
            joinedload(models.Alert.user)  # Single JOIN query, not N+1
        )
        .filter(models.Alert.status == status)
        .order_by(models.Alert.created_at.desc())
        .limit(limit)
        .all()
    )


def get_review_by_admin_and_alert(
    db: Session, alert_id: uuid.UUID, admin_id: uuid.UUID
):
    """Check if an admin has already voted on a specific alert."""
    return (
        db.query(models.AdminReview)
        .filter(
            models.AdminReview.alert_id == alert_id,
            models.AdminReview.admin_id == admin_id,
        )
        .first()
    )


def add_admin_review(db: Session, alert_id: uuid.UUID, admin_id: uuid.UUID, vote: bool):
    review = models.AdminReview(alert_id=alert_id, admin_id=admin_id, vote=vote)
    db.add(review)
    # We commit this as part of the larger transaction in the API endpoint
    return review


def count_alert_votes(db: Session, alert_id: uuid.UUID):
    approvals = (
        db.query(models.AdminReview)
        .filter(models.AdminReview.alert_id == alert_id, models.AdminReview.vote)
        .count()
    )
    rejections = (
        db.query(models.AdminReview)
        .filter(models.AdminReview.alert_id == alert_id, not models.AdminReview.vote)
        .count()
    )
    return approvals, rejections


def update_alert_status(db: Session, alert: models.Alert, status: str):
    alert.status = status
    # Don't commit here - let the endpoint handle the transaction
    db.flush()
    return alert


def delete_alert(db: Session, alert: models.Alert):
    db.delete(alert)
    # Don't commit here - let the endpoint handle the transaction
    db.flush()


# def count_alert_votes(db: Session, alert_id: uuid.UUID):
#     """Count approval and rejection votes for an alert."""
#     approvals = db.query(models.AdminReview).filter(
#         models.AdminReview.alert_id == alert_id,
#         models.AdminReview.vote
#     ).count()

#     rejections = db.query(models.AdminReview).filter(
#         models.AdminReview.alert_id == alert_id,
#         not models.AdminReview.vote
#     ).count()

#     print(f"DEBUG: Counting votes for alert {alert_id}: {approvals} approvals, {rejections} rejections")
#     return approvals, rejections


def get_user_alerts(
    db: Session, user_id: uuid.UUID, status: str | None = None, limit: int = 50
) -> list[models.Alert]:
    """Get all alerts for a specific user, optionally filtered by status."""
    query = (
        db.query(models.Alert)
        .options(joinedload(models.Alert.user))
        .filter(models.Alert.user_id == user_id)
    )

    if status:
        query = query.filter(models.Alert.status == status)

    return query.order_by(models.Alert.created_at.desc()).limit(limit).all()


def get_user_alert_stats(db: Session, user_id: uuid.UUID) -> dict:
    """Get statistics about a user's alerts."""
    total = db.query(models.Alert).filter(models.Alert.user_id == user_id).count()
    pending = (
        db.query(models.Alert)
        .filter(models.Alert.user_id == user_id, models.Alert.status == "pending")
        .count()
    )
    approved = (
        db.query(models.Alert)
        .filter(models.Alert.user_id == user_id, models.Alert.status == "reviewed")
        .count()
    )
    rejected = (
        db.query(models.Alert)
        .filter(models.Alert.user_id == user_id, models.Alert.status == "rejected")
        .count()
    )

    return {
        "total": total,
        "pending": pending,
        "approved": approved,
        "rejected": rejected,
    }


def create_notification(
    db: Session, notification: schemas.NotificationCreate
) -> models.Notification:
    """Create a new notification for a user."""
    db_notification = models.Notification(**notification.model_dump())
    db.add(db_notification)
    db.commit()
    db.refresh(db_notification)
    return db_notification


def get_user_notifications(
    db: Session,
    user_id: uuid.UUID,  # This should be the UUID, not Clerk ID
    unread_only: bool = False,
    limit: int = 50,
) -> list[models.Notification]:
    """Get notifications for a specific user."""
    print(f"🔍 CRUD: Looking for notifications for user_id: {user_id}")

    query = db.query(models.Notification).filter(models.Notification.user_id == user_id)

    if unread_only:
        query = query.filter(not models.Notification.read)

    notifications = (
        query.order_by(models.Notification.created_at.desc()).limit(limit).all()
    )

    print(f"🔍 CRUD: Found {len(notifications)} notifications")
    return notifications


def mark_notification_as_read(
    db: Session, notification_id: uuid.UUID, user_id: uuid.UUID
) -> models.Notification | None:
    """Mark a notification as read (only if it belongs to the user)."""
    notification = (
        db.query(models.Notification)
        .filter(
            models.Notification.id == notification_id,
            models.Notification.user_id == user_id,
        )
        .first()
    )

    if notification:
        notification.read = True
        db.commit()
        db.refresh(notification)

    return notification


def mark_all_notifications_as_read(db: Session, user_id: uuid.UUID) -> int:
    """Mark all notifications as read for a user. Returns count of updated notifications."""
    print(f"🔍 CRUD mark_all_notifications_as_read: user_id={user_id}")

    # Debug: Check notifications before update
    before_count = (
        db.query(models.Notification)
        .filter(models.Notification.user_id == user_id, not models.Notification.read)
        .count()
    )
    print(f"🔍 Unread notifications before update: {before_count}")

    updated_count = (
        db.query(models.Notification)
        .filter(models.Notification.user_id == user_id, not models.Notification.read)
        .update({"read": True})
    )

    print(f"🔍 Updated count: {updated_count}")

    db.commit()
    return updated_count


def delete_notification(
    db: Session, notification_id: uuid.UUID, user_id: uuid.UUID
) -> bool:
    """Delete a notification (only if it belongs to the user)."""
    notification = (
        db.query(models.Notification)
        .filter(
            models.Notification.id == notification_id,
            models.Notification.user_id == user_id,
        )
        .first()
    )

    if notification:
        db.delete(notification)
        db.commit()
        return True

    return False


def get_unread_notification_count(db: Session, user_id: uuid.UUID) -> int:
    """Get count of unread notifications for a user."""
    print(f"🔍 CRUD get_unread_notification_count: user_id={user_id}")

    # Debug: Check if any notifications exist for this user at all
    total_count = (
        db.query(models.Notification)
        .filter(models.Notification.user_id == user_id)
        .count()
    )
    print(f"🔍 Total notifications for user: {total_count}")

    # Debug: Check unread notifications
    unread_count = (
        db.query(models.Notification)
        .filter(models.Notification.user_id == user_id, not models.Notification.read)
        .count()
    )
    print(f"🔍 Unread notifications for user: {unread_count}")

    return unread_count


# Notification creation helpers
def notify_alert_approved(db: Session, alert: models.Alert):
    """Create notification when alert is approved."""
    notification = schemas.NotificationCreate(
        user_id=alert.user_id,
        title="Alert Approved",
        message=f"Your alert '{alert.description[:50]}...' has been approved and is now visible to the community.",
        type="admin",
        data={"alert_id": str(alert.id), "alert_type": alert.type},
    )
    return create_notification(db, notification)


def notify_alert_rejected(db: Session, alert: models.Alert):
    """Create notification when alert is rejected."""
    notification = schemas.NotificationCreate(
        user_id=alert.user_id,
        title="Alert Rejected",
        message=f"Your alert '{alert.description[:50]}...' was not approved. Please review our community guidelines.",
        type="admin",
        data={"alert_id": str(alert.id), "alert_type": alert.type},
    )
    return create_notification(db, notification)


def notify_nearby_alert(db: Session, user_id: uuid.UUID, alert: models.Alert):
    """Create notification for nearby alert."""
    notification = schemas.NotificationCreate(
        user_id=user_id,
        title="New Alert Nearby",
        message=f"A new {alert.type} alert has been reported near your location: {alert.description[:100]}...",
        type="alert",
        data={
            "alert_id": str(alert.id),
            "alert_type": alert.type,
            "severity": alert.severity,
        },
    )
    return create_notification(db, notification)
