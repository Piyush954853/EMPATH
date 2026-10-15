
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 - Register application models
from app.core.database import Base, get_db
from app.core.security import hash_password
from app.main import app
from app.models.role import Role
from app.models.user import User


TEST_PASSWORD = "LoginTest#2026"


@pytest.fixture
def login_api_env():
    """Use an isolated database for real HTTP login tests."""

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    db = None
    client = None
    old_overrides = app.dependency_overrides.copy()

    try:
        Base.metadata.create_all(bind=engine)

        TestSession = sessionmaker(
            bind=engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )
        db = TestSession()

        # The login endpoint does not require a permission mapping,
        # but each test user must have a valid role.
        role = Role(
            name="LOGIN_TEST_ROLE",
            description="Role for HTTP login integration tests",
            is_active=True,
        )
        db.add(role)
        db.commit()
        db.refresh(role)

        # Hash the test password using the application's actual
        # password hashing implementation.
        stored_password_hash = hash_password(TEST_PASSWORD)

        active_user = User(
            username="login_test_active",
            email="login_test_active@example.test",
            full_name="Login Test Active User",
            role_id=role.id,
            password_hash=stored_password_hash,
            is_active=True,
        )

        inactive_user = User(
            username="login_test_inactive",
            email="login_test_inactive@example.test",
            full_name="Login Test Inactive User",
            role_id=role.id,
            password_hash=stored_password_hash,
            is_active=False,
        )

        db.add_all([active_user, inactive_user])
        db.commit()

        db.refresh(active_user)
        db.refresh(inactive_user)

        def override_get_db():
            yield db

        # Override only the database dependency. The actual login
        # endpoint, password verification and JWT generation remain
        # the application's real implementations.
        app.dependency_overrides[get_db] = override_get_db

        client = TestClient(app)

        yield SimpleNamespace(
            client=client,
            active_user=active_user,
            inactive_user=inactive_user,
        )

    finally:
        if client is not None:
            client.close()

        app.dependency_overrides.clear()
        app.dependency_overrides.update(old_overrides)

        if db is not None:
            db.close()

        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_login_valid_credentials_returns_working_token(login_api_env):
    env = login_api_env

    response = env.client.post(
        "/auth/login",
        json={
            "username": env.active_user.username,
            "password": TEST_PASSWORD,
        },
    )

    assert response.status_code == 200, response.text

    payload = response.json()
    assert isinstance(payload.get("access_token"), str)
    assert payload["access_token"]

    # Verify the returned JWT through the real authenticated endpoint.
    me_response = env.client.get(
        "/auth/me",
        headers={
            "Authorization": f"Bearer {payload['access_token']}"
        },
    )

    assert me_response.status_code == 200, me_response.text

    me_payload = me_response.json()
    assert me_payload["id"] == env.active_user.id
    assert me_payload["username"] == env.active_user.username
    assert me_payload["is_active"] is True
    assert "password_hash" not in me_payload


def test_login_rejects_incorrect_password(login_api_env):
    env = login_api_env

    response = env.client.post(
        "/auth/login",
        json={
            "username": env.active_user.username,
            "password": "DefinitelyWrong#2026",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == (
        "Invalid username or password"
    )


def test_login_rejects_unknown_username(login_api_env):
    env = login_api_env

    response = env.client.post(
        "/auth/login",
        json={
            "username": "username_that_does_not_exist",
            "password": TEST_PASSWORD,
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == (
        "Invalid username or password"
    )


def test_login_rejects_inactive_user(login_api_env):
    env = login_api_env

    response = env.client.post(
        "/auth/login",
        json={
            "username": env.inactive_user.username,
            "password": TEST_PASSWORD,
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == (
        "Invalid username or password"
    )
