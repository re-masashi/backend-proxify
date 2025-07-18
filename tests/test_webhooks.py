import hashlib
import hmac
import json
import time

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core import settings
from app.models import User


def generate_svix_headers(payload: str, secret: str) -> dict:
    """Generates the required svix headers for a mock webhook request."""
    timestamp = str(int(time.time()))
    to_sign = f"v1.{timestamp}.{payload}"
    signature = hmac.new(
        secret.encode("utf-8"), msg=to_sign.encode("utf-8"), digestmod=hashlib.sha256
    ).hexdigest()

    return {
        "svix-id": "msg_2d2gQa8RulR4dYxJ2d2gQa8RulR4",
        "svix-timestamp": timestamp,
        "svix-signature": f"v1,{signature}",
        "Content-Type": "application/json",
    }


def test_clerk_webhook_user_created_success(client: TestClient, db_session: Session):
    # Payload for a new user
    payload = {
        "type": "user.created",
        "data": {
            "id": "user_12345",
            "email_addresses": [{"email_address": "newuser@example.com"}],
        },
    }
    payload_str = json.dumps(payload)
    headers = generate_svix_headers(payload_str, settings.CLERK_WEBHOOK_SECRET)

    response = client.post(
        "/api/v1/webhooks/clerk", content=payload_str, headers=headers
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Successfully created user user_12345"

    # Verify user was created in the database
    user = db_session.query(User).filter(User.userid == "user_12345").first()
    assert user is not None
    assert user.email == "newuser@example.com"
    assert not user.is_admin


def test_clerk_webhook_idempotency(client: TestClient, db_session: Session, test_user):
    # `test_user` already exists with userid 'user_regular_123'
    payload = {
        "type": "user.created",
        "data": {
            "id": "user_regular_123",
            "email_addresses": [{"email_address": "testuser@example.com"}],
        },
    }
    payload_str = json.dumps(payload)
    headers = generate_svix_headers(payload_str, settings.CLERK_WEBHOOK_SECRET)

    response = client.post(
        "/api/v1/webhooks/clerk", content=payload_str, headers=headers
    )

    # Should return success but indicate the user already exists
    assert response.status_code == 200
    assert response.json()["message"] == "User already exists."

    # Verify no new user was created
    user_count = (
        db_session.query(User).filter(User.userid == "user_regular_123").count()
    )
    assert user_count == 1


def test_clerk_webhook_verification_failure(client: TestClient):
    payload = {"type": "user.created", "data": {}}
    payload_str = json.dumps(payload)
    # Use a wrong secret to generate headers
    headers = generate_svix_headers(payload_str, "wrong_secret")

    response = client.post(
        "/api/v1/webhooks/clerk", content=payload_str, headers=headers
    )

    assert response.status_code == 400
    assert "Webhook verification failed" in response.json()["detail"]


def test_health_check(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
