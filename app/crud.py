import uuid

from sqlalchemy import or_
from sqlalchemy.orm import Session

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
