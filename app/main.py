import json
import logging
import os
import sys
import uuid
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    FastAPI,
    HTTPException,
    Request,
    Response,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from sqladmin import Admin
from sqlalchemy.orm import Session, joinedload
from svix.webhooks import Webhook, WebhookVerificationError

from . import crud, models, schemas
from .admin import (
    AdminReviewAdmin,
    AlertAdmin,
    FeaturedItemAdmin,
    UserAdmin,
    WarningAdmin,
)
from .admin_auth import authentication_backend
from .core import settings
from .database import engine, get_db
from .dependencies import get_current_admin_user, get_current_user_id
from .telemetry import configure_telemetry

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler("app.log")],
)

logger = logging.getLogger(__name__)

# Create all database tables on startup
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Proxify")

router_webhooks = APIRouter(prefix="/api/v1/webhooks", tags=["Webhooks"])


@router_webhooks.post("/clerk", status_code=status.HTTP_200_OK)
async def clerk_webhook(request: Request, db: Annotated[Session, Depends(get_db)]):
    headers = request.headers
    payload_bytes = await request.body()
    payload_str = payload_bytes.decode("utf-8")

    # Skip signature verification in test environment
    if os.getenv("TESTING") or os.getenv("PYTEST_CURRENT_TEST"):
        try:
            evt = json.loads(payload_str)
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}") from e
    else:
        # Production: verify signature
        try:
            headers_dict = dict(headers)
            wh = Webhook(settings.CLERK_WEBHOOK_SECRET)
            evt = wh.verify(payload_str, headers_dict)
        except WebhookVerificationError as e:
            raise HTTPException(
                status_code=400, detail=f"Webhook verification failed: {e}"
            ) from e
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid payload: {e}") from e

    # Rest of the handler logic stays the same
    event_type = evt.get("type")
    data = evt.get("data")

    if event_type == "user.created":
        email_info = data.get("email_addresses", [{}])[0]
        email = email_info.get("email_address")
        clerk_user_id = data.get("id")

        if not email or not clerk_user_id:
            raise HTTPException(
                status_code=400, detail="Missing email or user ID in webhook payload."
            )

        db_user = crud.get_user_by_clerk_id(db, clerk_user_id=clerk_user_id)
        if db_user:
            return {"message": "User already exists."}

        user_in = schemas.UserCreate(userid=clerk_user_id, email=email)
        crud.create_user(db=db, user=user_in)

        return {"message": f"Successfully created user {clerk_user_id}"}

    return Response(status_code=status.HTTP_200_OK)


# --- Alerts Router (for authenticated users) ---
router_alerts = APIRouter(prefix="/alerts", tags=["Alerts"])


@router_alerts.get("/", response_model=list[schemas.AlertResponse])
def get_alerts(
    db: Annotated[Session, Depends(get_db)],
    status: str = "reviewed",  # Only show approved alerts
    limit: int = 50,
):
    """
    Get all approved alerts for the home page.
    """
    alerts = (
        db.query(models.Alert)
        .filter(models.Alert.status == status)
        .order_by(models.Alert.created_at.desc())
        .limit(limit)
        .all()
    )

    return alerts


@router_alerts.get("/my-alerts", response_model=list[schemas.AlertResponse])
def get_my_alerts(
    db: Annotated[Session, Depends(get_db)],
    current_user_id: Annotated[str, Depends(get_current_user_id)],
    status: str | None = None,  # Optional filter by status
    limit: int = 50,
):
    """Get all alerts created by the current user."""
    user = crud.get_user_by_clerk_id(db, clerk_user_id=current_user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Build the query
    query = (
        db.query(models.Alert)
        .options(joinedload(models.Alert.user))
        .filter(models.Alert.user_id == user.id)
    )

    # Apply status filter if provided
    if status and status != "all":
        query = query.filter(models.Alert.status == status)

    # Order by creation date (newest first) and limit results
    alerts = query.order_by(models.Alert.created_at.desc()).limit(limit).all()

    return alerts


@router_alerts.get("/my-alerts/stats")
def get_my_alert_stats(
    db: Annotated[Session, Depends(get_db)],
    current_user_id: Annotated[str, Depends(get_current_user_id)],
):
    """Get statistics about the current user's alerts."""
    user = crud.get_user_by_clerk_id(db, clerk_user_id=current_user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    stats = crud.get_user_alert_stats(db, user_id=user.id)
    return stats


@router_alerts.get("/nearby", response_model=list[schemas.AlertResponse])
def get_nearby_alerts(
    lat: float,
    lon: float,
    db: Annotated[Session, Depends(get_db)],
    radius_km: float = 10.0,
):
    """
    Get alerts within a specified radius (in kilometers).
    """
    from sqlalchemy import func

    # Convert radius to meters for PostGIS
    radius_meters = radius_km * 1000

    alerts = (
        db.query(models.Alert)
        .filter(
            models.Alert.status == "reviewed",
            func.ST_DWithin(
                models.Alert.location,
                func.ST_GeomFromText(f"POINT({lon} {lat})", 4326),
                radius_meters,
            ),
        )
        .order_by(models.Alert.created_at.desc())
        .limit(50)
        .all()
    )

    return alerts


@router_alerts.get("/{alert_id}", response_model=schemas.AlertResponse)
def get_alert_by_id(alert_id: uuid.UUID, db: Annotated[Session, Depends(get_db)]):
    """
    Get a specific alert by ID.
    """
    alert = crud.get_alert_by_id(db, alert_id=alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    if alert.status != "reviewed":
        raise HTTPException(status_code=403, detail="Alert not approved")
    return alert


@router_alerts.post(
    "/", response_model=schemas.AlertResponse, status_code=status.HTTP_201_CREATED
)
def create_alert(
    alert: schemas.AlertCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user_id: Annotated[str, Depends(get_current_user_id)],
):
    user = crud.get_user_by_clerk_id(db, clerk_user_id=current_user_id)
    if not user:
        raise HTTPException(
            status_code=404, detail="Authenticated user not found in database."
        )

    # TODO: Trigger AI review in a background task after creation
    return crud.create_alert(db=db, alert=alert, user_id=user.id)


# --- Admin Router ---
router_admin = APIRouter(
    prefix="/api/admin/alerts",
    tags=["Admin"],
    dependencies=[
        Depends(get_current_admin_user)
    ],  # Protects all endpoints in this router
)


@router_admin.get("/{alert_id}/votes")
def debug_get_votes(
    alert_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    _admin_user: Annotated[models.User, Depends(get_current_admin_user)],
):
    """Temporary debug endpoint to check vote counts"""
    approvals, rejections = crud.count_alert_votes(db, alert_id=alert_id)

    # Get all votes for this alert
    votes = (
        db.query(models.AdminReview)
        .filter(models.AdminReview.alert_id == alert_id)
        .all()
    )
    vote_details = [
        {"admin_id": str(vote.admin_id), "vote": vote.vote} for vote in votes
    ]

    return {
        "alert_id": alert_id,
        "approvals": approvals,
        "rejections": rejections,
        "vote_details": vote_details,
    }


@router_admin.get("/pending", response_model=list[schemas.AlertResponse])
def get_pending_alerts_for_review(db: Annotated[Session, Depends(get_db)]):
    return crud.get_pending_alerts(db)


@router_admin.post("/{alert_id}/review", response_model=schemas.AdminReviewResponse)
def review_alert(
    alert_id: uuid.UUID,
    review: schemas.AdminReviewCreate,
    db: Annotated[Session, Depends(get_db)],
    admin_user: Annotated[models.User, Depends(get_current_admin_user)],
):
    alert = crud.get_alert_by_id(db, alert_id=alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found.")

    if alert.status == "reviewed":
        raise HTTPException(
            status_code=400, detail="This alert has already been reviewed and approved."
        )

    if crud.get_review_by_admin_and_alert(
        db, alert_id=alert_id, admin_id=admin_user.id
    ):
        raise HTTPException(
            status_code=400, detail="You have already voted on this alert."
        )

    # Add the vote
    crud.add_admin_review(
        db=db, alert_id=alert_id, admin_id=admin_user.id, vote=review.vote
    )
    db.flush()

    # Get the updated vote counts
    approvals, rejections = crud.count_alert_votes(db, alert_id=alert_id)

    # Handle rejection logic
    if rejections >= 3:
        # Create rejection notification before deleting alert
        crud.notify_alert_rejected(db, alert)
        crud.delete_alert(db, alert=alert)
        db.commit()
        return {
            "message": f"Alert {alert_id} has been deleted after {rejections} rejections.",
            "alert_id": alert_id,
            "status": "deleted",
        }

    # Handle approval logic
    if approvals >= 2:
        alert.status = "reviewed"
        # Create approval notification
        crud.notify_alert_approved(db, alert)
        db.commit()
        return {
            "message": f"Alert {alert_id} has been approved with {approvals} votes.",
            "alert_id": alert_id,
            "status": "reviewed",
        }

    # If no threshold was met, just commit the vote
    db.commit()
    return {
        "message": "Vote recorded successfully.",
        "alert_id": alert_id,
        "status": alert.status,
    }


router_notifications = APIRouter(prefix="/notifications", tags=["Notifications"])


@router_notifications.get("/", response_model=list[schemas.NotificationResponse])
def get_notifications(
    db: Annotated[Session, Depends(get_db)],
    current_user_id: Annotated[str, Depends(get_current_user_id)],
    unread_only: bool = False,
    limit: int = 50,
):
    """Get notifications for the current user."""
    # DEBUG: Add logging to see what's happening
    print(f"🔍 Looking for user with Clerk ID: {current_user_id}")

    user = crud.get_user_by_clerk_id(db, clerk_user_id=current_user_id)
    if not user:
        print(f"🔴 User not found with Clerk ID: {current_user_id}")
        raise HTTPException(status_code=404, detail="User not found")

    print(f"🔍 Found user with UUID: {user.id}")

    notifications = crud.get_user_notifications(
        db,
        user_id=user.id,  # Make sure this is the UUID, not the Clerk ID
        unread_only=unread_only,
        limit=limit,
    )

    print(f"🔍 Found {len(notifications)} notifications for user {user.id}")
    return notifications


@router_notifications.get("/count")
def get_unread_count(
    db: Annotated[Session, Depends(get_db)],
    current_user_id: Annotated[str, Depends(get_current_user_id)],
):
    """Get count of unread notifications for the current user."""
    print(f"🔍 Looking for user with Clerk ID: {current_user_id}")

    user = crud.get_user_by_clerk_id(db, clerk_user_id=current_user_id)
    if not user:
        print(f"🔴 User not found with Clerk ID: {current_user_id}")
        raise HTTPException(status_code=404, detail="User not found")

    print(f"🔍 Found user UUID: {user.id}")

    count = crud.get_unread_notification_count(db, user_id=user.id)
    print(f"🔍 Unread count: {count}")

    return {"unread_count": count}


@router_notifications.put("/{notification_id}/read")
def mark_notification_read(
    notification_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user_id: Annotated[str, Depends(get_current_user_id)],
):
    """Mark a specific notification as read."""
    user = crud.get_user_by_clerk_id(db, clerk_user_id=current_user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    notification = crud.mark_notification_as_read(db, notification_id, user.id)
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    return {"message": "Notification marked as read"}


@router_notifications.put("/mark-all-read")
def mark_all_notifications_read(
    db: Annotated[Session, Depends(get_db)],
    current_user_id: Annotated[str, Depends(get_current_user_id)],
):
    """Mark all notifications as read for the current user."""
    user = crud.get_user_by_clerk_id(db, clerk_user_id=current_user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    updated_count = crud.mark_all_notifications_as_read(db, user.id)
    return {"message": f"Marked {updated_count} notifications as read"}


@router_notifications.delete("/{notification_id}")
def delete_notification(
    notification_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user_id: Annotated[str, Depends(get_current_user_id)],
):
    """Delete a specific notification."""
    user = crud.get_user_by_clerk_id(db, clerk_user_id=current_user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    deleted = crud.delete_notification(db, notification_id, user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Notification not found")

    return {"message": "Notification deleted"}


app.include_router(router_notifications)

admin = Admin(app, engine, authentication_backend=authentication_backend)

admin.add_view(UserAdmin)
admin.add_view(AlertAdmin)
admin.add_view(AdminReviewAdmin)
admin.add_view(WarningAdmin)
admin.add_view(FeaturedItemAdmin)

# Include all routers in the main app
app.include_router(router_webhooks)
app.include_router(router_alerts)
app.include_router(router_admin)


@app.get("/health", status_code=status.HTTP_200_OK)
def health_check():
    """Endpoint for uptime monitoring to keep the free Render instance alive."""
    return {"status": "ok"}


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

configure_telemetry(app)


@app.on_event("startup")
async def startup_event():
    logger.info("🚀 Proxify API starting up...")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("🛑 Proxify API shutting down...")
