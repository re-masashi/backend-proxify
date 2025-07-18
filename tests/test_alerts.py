# tests/test_alerts.py

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import User

# --- Successful Creation Test ---


def test_create_alert_success(
    client: TestClient, db_session: Session, test_user: User, auth_headers
):
    """
    Tests successful creation of an alert by an authenticated user.
    """
    # Set the client to use this user's ID
    client.set_user_id(test_user.userid)

    alert_data = {
        "description": "Major sale at the city center mall this weekend.",
        "type": "sale",
        "location": {"type": "Point", "coordinates": [-74.0060, 40.7128]},
        "severity": 3,
        "attachments": ["http://example.com/image.jpg"],
    }

    response = client.post("/alerts/", json=alert_data)

    assert response.status_code == 201, response.text
    data = response.json()

    # Verify response body
    assert data["description"] == alert_data["description"]
    assert data["status"] == "pending"
    assert data["severity"] == 3
    assert data["user_id"] == str(test_user.id)


def test_create_alert_unauthenticated(client: TestClient):
    """
    Tests that an unauthenticated request is rejected with a 401 error.
    """

    # Set up the client to return None (unauthenticated)
    def override_get_current_user_id():
        from fastapi import HTTPException

        raise HTTPException(status_code=401, detail="Not authenticated")

    from app.dependencies import get_current_user_id
    from app.main import app

    app.dependency_overrides[get_current_user_id] = override_get_current_user_id

    alert_data = {"description": "This should not work."}
    response = client.post("/alerts/", json=alert_data)

    assert response.status_code == 401
    assert "Not authenticated" in response.json()["detail"]


def test_create_alert_with_user_not_in_db(
    client: TestClient, db_session: Session, auth_headers
):
    """
    Tests the edge case where a valid JWT is for a user not in our database.
    """
    # Set the client to use a user ID that doesn't exist in the database
    client.set_user_id("user_not_in_db_123")

    alert_data = {
        "description": "Testing a ghost user",
        "type": "help",
        "location": {"type": "Point", "coordinates": [0, 0]},
        "severity": 1,
    }

    response = client.post("/alerts/", json=alert_data)

    assert response.status_code == 404
    assert "Authenticated user not found in database" in response.json()["detail"]


@pytest.mark.parametrize(
    "field, value, error_msg",
    [
        ("description", "", "String should have at least 1 character"),
        (
            "type",
            "invalid_type",
            "Input should be 'alert', 'news', 'sale', 'help' or 'event'",
        ),
        ("severity", 0, "Input should be greater than or equal to 1"),
        ("severity", 6, "Input should be less than or equal to 5"),
        ("location", {"type": "Polygon", "coordinates": []}, "Input should be 'Point'"),
        (
            "location",
            {"type": "Point", "coordinates": [181, 90]},
            "longitude must be between -180 and 180",
        ),
    ],
)
def test_create_alert_with_invalid_data(
    client: TestClient, test_user: User, auth_headers, field, value, error_msg
):
    """
    Uses parameterization to test multiple invalid input scenarios efficiently.
    """
    client.set_user_id(test_user.userid)

    alert_data = {
        "description": "A valid description.",
        "type": "alert",
        "location": {"type": "Point", "coordinates": [10.0, 20.0]},
        "severity": 2,
    }
    # Overwrite the valid data with the invalid test case
    alert_data[field] = value

    response = client.post("/alerts/", json=alert_data)

    assert response.status_code == 422, response.text
    # Check that the specific error message is present in the response detail
    assert error_msg in str(response.json()["detail"])


def test_create_alert_with_missing_required_fields(
    client: TestClient, test_user: User, auth_headers
):
    """
    Tests that requests missing required fields are rejected.
    """
    client.set_user_id(test_user.userid)

    # Missing 'description'
    response = client.post(
        "/alerts/",
        json={
            "type": "sale",
            "location": {"type": "Point", "coordinates": [0, 0]},
            "severity": 1,
        },
    )
    assert response.status_code == 422
    assert "Field required" in str(response.json()["detail"])
    assert "description" in str(response.json()["detail"])

    # Missing 'location'
    response = client.post(
        "/alerts/", json={"description": "test", "type": "sale", "severity": 1}
    )
    assert response.status_code == 422
    assert "Field required" in str(response.json()["detail"])
    assert "location" in str(response.json()["detail"])
