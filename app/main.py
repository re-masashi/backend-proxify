import json
from fastapi import FastAPI, Depends, HTTPException, Request, Response, status, APIRouter
from sqlalchemy.orm import Session
from svix.webhooks import Webhook, WebhookVerificationError
import uuid
from sqladmin import Admin
from typing import List

from . import crud, models, schemas
from .core import settings
from .database import engine, get_db
from .dependencies import get_current_user_id, get_current_admin_user
from .admin import UserAdmin, AlertAdmin, AdminReviewAdmin, WarningAdmin, FeaturedItemAdmin
from .admin_auth import authentication_backend

# Create all database tables on startup
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Proxify")

router_webhooks = APIRouter(prefix="/api/v1/webhooks", tags=["Webhooks"])

@router_webhooks.post("/clerk", status_code=status.HTTP_200_OK)
async def clerk_webhook(request: Request, db: Session = Depends(get_db)):
    headers = request.headers
    try:
        payload_bytes = await request.body()
        wh = Webhook(settings.CLERK_WEBHOOK_SECRET)
        evt = wh.verify(payload_bytes.decode('utf-8'), headers)
    except WebhookVerificationError as e:
        raise HTTPException(status_code=400, detail=f"Webhook verification failed: {e}")
    
    event_type = evt.get("type")
    data = evt.get("data")

    if event_type == "user.created":
        email = data.get("email_addresses", [{}])[0].get("email_address")
        clerk_user_id = data.get("id")
        if not email or not clerk_user_id:
            raise HTTPException(status_code=400, detail="Missing data in webhook.")

        if crud.get_user_by_clerk_id(db, clerk_user_id=clerk_user_id):
            return {"message": "User already exists."}

        user_in = schemas.UserCreate(userid=clerk_user_id, email=email)
        crud.create_user(db=db, user=user_in)
        return {"message": f"Successfully created user {clerk_user_id}"}
    
    return Response(status_code=status.HTTP_200_OK)

# --- Alerts Router (for authenticated users) ---
router_alerts = APIRouter(prefix="/alerts", tags=["Alerts"])

@router_alerts.post("/", response_model=schemas.AlertResponse, status_code=status.HTTP_201_CREATED)
def create_alert(
    alert: schemas.AlertCreate,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id)
):
    user = crud.get_user_by_clerk_id(db, clerk_user_id=current_user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Authenticated user not found in database.")
    
    # TODO: Trigger AI review in a background task after creation
    return crud.create_alert(db=db, alert=alert, user_id=user.id)


# --- Admin Router ---
router_admin = APIRouter(
    prefix="/api/admin/alerts",
    tags=["Admin"],
    dependencies=[Depends(get_current_admin_user)] # Protects all endpoints in this router
)


@router_admin.get("/{alert_id}/votes")
def debug_get_votes(
    alert_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin_user: models.User = Depends(get_current_admin_user)
):
    """Temporary debug endpoint to check vote counts"""
    approvals, rejections = crud.count_alert_votes(db, alert_id=alert_id)
    
    # Get all votes for this alert
    votes = db.query(models.AdminReview).filter(models.AdminReview.alert_id == alert_id).all()
    vote_details = [{"admin_id": str(vote.admin_id), "vote": vote.vote} for vote in votes]
    
    return {
        "alert_id": alert_id,
        "approvals": approvals,
        "rejections": rejections,
        "vote_details": vote_details
    }

@router_admin.get("/pending", response_model=List[schemas.AlertResponse])
def get_pending_alerts_for_review(db: Session = Depends(get_db)):
    return crud.get_pending_alerts(db)

@router_admin.post("/{alert_id}/review", response_model=schemas.AdminReviewResponse)
def review_alert(
    alert_id: uuid.UUID,
    review: schemas.AdminReviewCreate,
    db: Session = Depends(get_db),
    admin_user: models.User = Depends(get_current_admin_user)
):
    alert = crud.get_alert_by_id(db, alert_id=alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found.")
    
    if alert.status == 'reviewed':
        raise HTTPException(status_code=400, detail="This alert has already been reviewed and approved.")

    if crud.get_review_by_admin_and_alert(db, alert_id=alert_id, admin_id=admin_user.id):
        raise HTTPException(status_code=400, detail="You have already voted on this alert.")
    
    # Add the vote first
    crud.add_admin_review(db=db, alert_id=alert_id, admin_id=admin_user.id, vote=review.vote)
    db.flush()  # Ensure the vote is written to the database
    
    # Now get the updated vote counts
    approvals, rejections = crud.count_alert_votes(db, alert_id=alert_id)
    
    print(f"DEBUG: Alert {alert_id} - Approvals: {approvals}, Rejections: {rejections}")  # Debug line

    # Handle rejection logic
    if rejections >= 3:
        crud.delete_alert(db, alert=alert)
        db.commit()
        return {
            "message": f"Alert {alert_id} has been deleted after {rejections} rejections.",
            "alert_id": alert_id,
            "status": "deleted"
        }
    
    # Handle approval logic
    if approvals >= 2:
        alert.status = "reviewed"  # Update the status directly
        db.commit()
        return {
            "message": f"Alert {alert_id} has been approved with {approvals} votes.",
            "alert_id": alert_id,
            "status": "reviewed"
        }

    # If no threshold was met, just commit the vote
    db.commit()
    return {
        "message": "Vote recorded successfully.",
        "alert_id": alert_id,
        "status": alert.status
    }

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
