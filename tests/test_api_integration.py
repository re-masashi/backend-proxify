# tests/test_api_integration.py
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import User


def test_complete_alert_workflow(
    client: TestClient, db_session: Session, test_user: User, test_admin
):
    """Test the complete alert workflow from creation to approval"""

    # 1. User creates alert
    client.set_user_id(test_user.userid)
    alert_data = {
        "description": "Integration test alert",
        "type": "news",
        "location": {"type": "Point", "coordinates": [-122.4194, 37.7749]},
        "severity": 3,
    }

    create_response = client.post("/alerts/", json=alert_data)
    assert create_response.status_code == 201
    alert_id = create_response.json()["id"]

    # 2. Alert should not appear in public listing (not approved yet)
    public_response = client.get("/alerts/")
    assert (
        public_response.status_code == 200
    )  # Fix: Check public_response, not create_response
    alert_ids = [alert["id"] for alert in public_response.json()]
    assert alert_id not in alert_ids

    # 3. Admin can see pending alert
    client.set_user_id(test_admin.userid)
    pending_response = client.get("/api/admin/alerts/pending")
    assert pending_response.status_code == 200
    pending_ids = [alert["id"] for alert in pending_response.json()]
    assert alert_id in pending_ids

    # 4. First admin approves (should need 2 approvals)
    review_response1 = client.post(
        f"/api/admin/alerts/{alert_id}/review", json={"vote": True}
    )
    assert review_response1.status_code == 200

    # 5. Alert still not in public listing (needs 2 approvals)
    public_response = client.get("/alerts/")
    alert_ids = [alert["id"] for alert in public_response.json()]
    assert alert_id not in alert_ids

    # 6. Second admin approves (should approve alert)
    from tests.test_admin_flow import create_admin_user

    admin2 = create_admin_user(db_session, "admin_integration_2", "admin2@test.com")
    client.set_user_id(admin2.userid)

    review_response2 = client.post(
        f"/api/admin/alerts/{alert_id}/review", json={"vote": True}
    )
    assert review_response2.status_code == 200
    assert review_response2.json()["status"] == "reviewed"

    # 7. Alert now appears in public listing
    public_response = client.get("/alerts/")
    alert_ids = [alert["id"] for alert in public_response.json()]
    assert alert_id in alert_ids
