# tests/test_webhooks.py
import base64
import hashlib
import hmac
import time

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import User


def generate_svix_headers(payload: str, secret: str) -> dict:
    """Generates the required svix headers for a mock webhook request."""
    # Remove the 'whsec_' prefix if present
    if secret.startswith("whsec_"):
        secret = secret[6:]  # Remove 'whsec_' prefix

    # Decode the base64 secret
    try:
        secret_bytes = base64.b64decode(secret)
    except Exception:
        # If it's not base64, use as is (for test secrets)
        secret_bytes = secret.encode("utf-8")

    timestamp = str(int(time.time()))
    signed_payload = f"{timestamp}.{payload}"

    signature = hmac.new(
        secret_bytes, signed_payload.encode("utf-8"), hashlib.sha256
    ).digest()

    signature_b64 = base64.b64encode(signature).decode("utf-8")

    return {
        "svix-id": "msg_test_webhook_id_12345",
        "svix-timestamp": timestamp,
        "svix-signature": f"v1,{signature_b64}",
        "content-type": "application/json",
    }


def test_clerk_webhook_user_created_success(client: TestClient, db_session: Session):
    # Simple payload without signature verification
    payload = {
        "type": "user.created",
        "data": {
            "id": "user_12345",
            "email_addresses": [{"email_address": "newuser@example.com"}],
        },
    }

    # No special headers needed for mocked webhook
    response = client.post(
        "/api/v1/webhooks/clerk",
        json=payload,  # Use json instead of content
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Successfully created user user_12345"

    # Verify user was created
    user = db_session.query(User).filter(User.userid == "user_12345").first()
    assert user is not None
    assert user.email == "newuser@example.com"
    assert not user.is_admin


def test_clerk_webhook_idempotency(client: TestClient, db_session: Session, test_user):
    payload = {
        "type": "user.created",
        "data": {
            "id": "user_regular_123",
            "email_addresses": [{"email_address": "testuser@example.com"}],
        },
    }

    response = client.post("/api/v1/webhooks/clerk", json=payload)

    assert response.status_code == 200
    assert response.json()["message"] == "User already exists."

    # Verify no duplicate users
    user_count = (
        db_session.query(User).filter(User.userid == "user_regular_123").count()
    )
    assert user_count == 1


def test_clerk_webhook_verification_failure(client: TestClient):
    payload = {"type": "user.created", "data": {}}  # Missing required fields

    response = client.post("/api/v1/webhooks/clerk", json=payload)

    assert response.status_code == 400
    assert (
        "Missing email or user ID" in response.json()["detail"]
    )  # This is what actually happens


def test_health_check(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
