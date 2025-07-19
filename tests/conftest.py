# tests/conftest.py

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models, schemas
from app.core import settings
from app.database import Base, get_db
from app.dependencies import get_current_user_id
from app.main import app

SQLALCHEMY_DATABASE_URL = settings.DATABASE_URL
engine = create_engine(SQLALCHEMY_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def db_session(setup_test_database):
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


# tests/conftest.py


@pytest.fixture(scope="function")
def client(db_session):
    current_user_id = {"value": None}

    def override_get_current_user_id():
        if current_user_id["value"] is None:
            from fastapi import HTTPException

            raise HTTPException(status_code=401, detail="Not authenticated")
        return current_user_id["value"]

    def override_get_current_admin_user():
        if current_user_id["value"] is None:
            from fastapi import HTTPException

            raise HTTPException(status_code=401, detail="Not authenticated")

        from app import crud

        user = crud.get_user_by_clerk_id(
            db_session, clerk_user_id=current_user_id["value"]
        )
        if not user:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="User not found in database")
        if not user.is_admin:
            from fastapi import HTTPException

            raise HTTPException(status_code=403, detail="Not an admin")
        return user

    # CRITICAL FIX: Create a function that returns the exact same session
    def override_get_db():
        try:
            yield db_session
        finally:
            pass  # Don't close the session, let pytest handle it

    # Import the app and dependencies
    from app.dependencies import get_current_admin_user

    # Apply overrides BEFORE creating TestClient
    app.dependency_overrides[get_current_user_id] = override_get_current_user_id
    app.dependency_overrides[get_current_admin_user] = override_get_current_admin_user
    app.dependency_overrides[get_db] = override_get_db

    # Now create client
    client_instance = TestClient(app)

    def set_user_id(user_id):
        current_user_id["value"] = user_id

    def clear_user_id():
        current_user_id["value"] = None

    client_instance.set_user_id = set_user_id
    client_instance.clear_user_id = clear_user_id

    yield client_instance

    # Clear overrides after test
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers():
    """
    Factory fixture to create authentication headers for a given user.
    """

    def _auth_headers(user: models.User):
        return {"Authorization": f"Bearer {user.userid}"}

    return _auth_headers


# --- Re-usable data fixtures ---


@pytest.fixture
def test_user(db_session):
    user_data = schemas.UserCreate(
        userid="user_regular_123", email="testuser@example.com"
    )
    user = models.User(**user_data.model_dump())
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_admin(db_session):
    admin_data = schemas.UserCreate(
        userid="user_admin_123", email="admin@example.com", is_admin=True
    )
    user = models.User(**admin_data.model_dump())
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user
