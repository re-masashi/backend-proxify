# tests/test_admin_flow.py

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app import models, schemas

def create_admin_user(db_session: Session, userid: str, email: str) -> models.User:
    admin_data = schemas.UserCreate(userid=userid, email=email, is_admin=True)
    user = models.User(**admin_data.model_dump())
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user

def test_admin_review_workflow(client: TestClient, db_session: Session, test_user: models.User, auth_headers):
    # 1. Create an alert as a regular user
    client.set_user_id(test_user.userid)
    
    alert_data = {
        "description": "Suspicious activity",
        "type": "alert",
        "location": {"type": "Point", "coordinates": [1.0, 1.0]},
        "severity": 5
    }
    
    response = client.post("/alerts/", json=alert_data)
    assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"
    alert_id = response.json()["id"]
    print(f"DEBUG: Created alert with ID: {alert_id}")

    # 2. Create admin users with UNIQUE IDs
    admin1 = create_admin_user(db_session, "admin_user_1", "admin1@test.com")
    admin2 = create_admin_user(db_session, "admin_user_2", "admin2@test.com")
    admin3 = create_admin_user(db_session, "admin_user_3", "admin3@test.com")
    
    print(f"DEBUG: Created admin1: {admin1.userid}")
    print(f"DEBUG: Created admin2: {admin2.userid}")
    print(f"DEBUG: Created admin3: {admin3.userid}")
    
    # 3. First admin approves
    client.set_user_id(admin1.userid)
    print(f"DEBUG: Admin1 ({admin1.userid}) voting...")
    
    review_url = f"/api/admin/alerts/{alert_id}/review"
    res1 = client.post(review_url, json={"vote": True})
    print(f"DEBUG: Admin1 vote response: {res1.status_code} - {res1.text}")
    
    assert res1.status_code == 200, f"Expected 200, got {res1.status_code}: {res1.text}"
    
    # 4. Second admin approves
    client.set_user_id(admin2.userid)
    print(f"DEBUG: Admin2 ({admin2.userid}) voting...")
    
    res2 = client.post(review_url, json={"vote": True})
    print(f"DEBUG: Admin2 vote response: {res2.status_code} - {res2.text}")
    
    assert res2.status_code == 200, f"Expected 200, got {res2.status_code}: {res2.text}"
    
    response_data = res2.json()
    print(f"DEBUG: Admin2 response data: {response_data}")
    
    # The response should indicate the status change
    assert response_data["status"] == "reviewed", f"Expected 'reviewed', got '{response_data['status']}'"
    
    # Refresh the database session to see the committed changes
    db_session.expire_all()
    alert = db_session.get(models.Alert, alert_id)
    assert alert.status == "reviewed", f"Alert status should be 'reviewed', got '{alert.status}'"
