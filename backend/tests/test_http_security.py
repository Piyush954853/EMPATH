
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 - Register all application models
from app.api import alert as alert_api
from app.core.database import Base, get_db
from app.core.jwt import create_access_token
from app.main import app
from app.models.alert import Alert
from app.models.event import Event
from app.models.permission import Permission
from app.models.role import Role
from app.models.role_permission import RolePermission
from app.models.user import User


def auth_headers(user):
    """Create a real application JWT for a test user."""
    token = create_access_token(str(user.id))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def http_security_env(monkeypatch):
    """
    Use an isolated SQLite database while retaining real HTTP,
    JWT decoding, get_current_user, and require_permission logic.

    Only alert resource-scope checking is simulated here. Real
    camera/bed resource-scope authorization needs separate tests.
    """

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

        # -----------------------------------------------------
        # 1. Roles
        # -----------------------------------------------------
        nurse_role = Role(
            name="NURSE",
            description="HTTP security test Nurse",
            is_active=True,
        )
        doctor_role = Role(
            name="DOCTOR",
            description="HTTP security test Doctor",
            is_active=True,
        )
        limited_role = Role(
            name="LIMITED",
            description="Role without alert permissions",
            is_active=True,
        )

        db.add_all([nurse_role, doctor_role, limited_role])
        db.commit()

        db.refresh(nurse_role)
        db.refresh(doctor_role)
        db.refresh(limited_role)

        # -----------------------------------------------------
        # 2. Actual database permissions
        # -----------------------------------------------------
        users_read = Permission(
            name="users.read",
            description="Read users",
            is_active=True,
        )
        alerts_read = Permission(
            name="alerts.read",
            description="Read alerts",
            is_active=True,
        )
        alerts_acknowledge = Permission(
            name="alerts.acknowledge",
            description="Acknowledge and transfer alerts",
            is_active=True,
        )

        db.add_all([users_read, alerts_read, alerts_acknowledge])
        db.commit()

        for permission in (
            users_read,
            alerts_read,
            alerts_acknowledge,
        ):
            db.refresh(permission)

        # Nurse receives all three permissions.
        # Doctor receives transfer permission intentionally, so the
        # route's active-Nurse business rule can be exercised.
        # Limited role receives no permissions.
        db.add_all(
            [
                RolePermission(
                    role_id=nurse_role.id,
                    permission_id=users_read.id,
                ),
                RolePermission(
                    role_id=nurse_role.id,
                    permission_id=alerts_read.id,
                ),
                RolePermission(
                    role_id=nurse_role.id,
                    permission_id=alerts_acknowledge.id,
                ),
                RolePermission(
                    role_id=doctor_role.id,
                    permission_id=alerts_acknowledge.id,
                ),
            ]
        )
        db.commit()

        # -----------------------------------------------------
        # 3. Users
        # -----------------------------------------------------
        nurse_from = User(
            username="http_nurse_from",
            email="http_nurse_from@example.test",
            full_name="HTTP Nurse From",
            role_id=nurse_role.id,
            password_hash="test-only-unused-hash",
            is_active=True,
        )
        nurse_to = User(
            username="http_nurse_to",
            email="http_nurse_to@example.test",
            full_name="HTTP Nurse To",
            role_id=nurse_role.id,
            password_hash="test-only-unused-hash",
            is_active=True,
        )
        doctor = User(
            username="http_doctor",
            email="http_doctor@example.test",
            full_name="HTTP Doctor",
            role_id=doctor_role.id,
            password_hash="test-only-unused-hash",
            is_active=True,
        )
        limited_user = User(
            username="http_limited_user",
            email="http_limited_user@example.test",
            full_name="HTTP Limited User",
            role_id=limited_role.id,
            password_hash="test-only-unused-hash",
            is_active=True,
        )

        db.add_all([nurse_from, nurse_to, doctor, limited_user])
        db.commit()

        for user in (nurse_from, nurse_to, doctor, limited_user):
            db.refresh(user)

        # -----------------------------------------------------
        # 4. Test event and alert
        # -----------------------------------------------------
        event = Event(
            event_type="alert_handoff_test",
            source_type="manual_test",
            severity="medium",
            status="test",
            camera_id=None,
            patient_id=None,
            confidence=None,
            description="HTTP security test event.",
            metadata_json='{"test_only": true}',
        )

        db.add(event)
        db.commit()
        db.refresh(event)

        alert = Alert(
            event_id=event.id,
            priority="medium",
            status="active",
            title="TEST - HTTP Handoff",
            message="Test-only alert.",
            summary="Test-only summary.",
            assigned_to_user_id=nurse_from.id,
        )

        db.add(alert)
        db.commit()
        db.refresh(alert)

        state = {
            "resource_access_user_ids": {
                nurse_from.id,
                nurse_to.id,
                doctor.id,
                limited_user.id,
            }
        }

        # Override only the database session. JWT parsing and role
        # permission checks remain the real application functions.
        def override_get_db():
            yield db

        app.dependency_overrides[get_db] = override_get_db

        # Resource-scope logic is outside the scope of this test file.
        # This fake makes scope explicitly controllable per test.
        def fake_can_access_alert(_db, user, _alert):
            return (
                user.id in state["resource_access_user_ids"]
            )

        monkeypatch.setattr(
            alert_api,
            "can_access_alert",
            fake_can_access_alert,
        )

        client = TestClient(app)

        yield SimpleNamespace(
            client=client,
            db=db,
            state=state,
            nurse_from=nurse_from,
            nurse_to=nurse_to,
            doctor=doctor,
            limited_user=limited_user,
            alert=alert,
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


def test_http_me_accepts_valid_jwt(http_security_env):
    env = http_security_env

    response = env.client.get(
        "/auth/me",
        headers=auth_headers(env.nurse_from),
    )

    assert response.status_code == 200, response.text

    payload = response.json()
    assert payload["id"] == env.nurse_from.id
    assert payload["username"] == env.nurse_from.username
    assert payload["role_name"] == "NURSE"
    assert "password_hash" not in payload


def test_http_me_rejects_missing_token(http_security_env):
    response = http_security_env.client.get("/auth/me")

    assert response.status_code in (401, 403)


def test_http_me_rejects_invalid_token(http_security_env):
    response = http_security_env.client.get(
        "/auth/me",
        headers={"Authorization": "Bearer invalid.token.value"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired token"


def test_http_permission_endpoint_allows_authorized_role(
    http_security_env,
):
    env = http_security_env

    response = env.client.get(
        "/auth/permission-test",
        headers=auth_headers(env.nurse_from),
    )

    assert response.status_code == 200, response.text
    assert response.json() == {
        "status": "allowed",
        "user": env.nurse_from.username,
        "permission": "users.read",
    }


def test_http_permission_endpoint_rejects_missing_permission(
    http_security_env,
):
    env = http_security_env

    response = env.client.get(
        "/auth/permission-test",
        headers=auth_headers(env.limited_user),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Permission denied"


def test_http_alert_transfer_updates_assignment_and_history(
    http_security_env,
):
    env = http_security_env

    response = env.client.post(
        f"/alerts/{env.alert.id}/transfer",
        headers=auth_headers(env.nurse_from),
        json={
            "to_user_id": env.nurse_to.id,
            "reason": "Real JWT HTTP integration test.",
        },
    )

    assert response.status_code == 200, response.text

    payload = response.json()
    assert payload["assigned_to_user_id"] == env.nurse_to.id
    assert payload["status"] == "active"

    history_response = env.client.get(
        f"/alerts/{env.alert.id}/history",
        headers=auth_headers(env.nurse_from),
    )

    assert history_response.status_code == 200, history_response.text

    history = history_response.json()
    assert len(history) == 1
    assert history[0]["from_user_id"] == env.nurse_from.id
    assert history[0]["to_user_id"] == env.nurse_to.id
    assert history[0]["transferred_by_user_id"] == env.nurse_from.id
    assert history[0]["reason"] == "Real JWT HTTP integration test."


def test_http_alert_transfer_rejects_missing_token(
    http_security_env,
):
    env = http_security_env

    response = env.client.post(
        f"/alerts/{env.alert.id}/transfer",
        json={
            "to_user_id": env.nurse_to.id,
            "reason": "Missing token test.",
        },
    )

    assert response.status_code in (401, 403)


def test_http_alert_transfer_rejects_missing_permission(
    http_security_env,
):
    env = http_security_env

    response = env.client.post(
        f"/alerts/{env.alert.id}/transfer",
        headers=auth_headers(env.limited_user),
        json={
            "to_user_id": env.nurse_to.id,
            "reason": "No transfer permission test.",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Permission denied"


def test_http_alert_transfer_rejects_non_nurse(
    http_security_env,
):
    env = http_security_env

    # This role has the endpoint permission so the request reaches
    # the real active-Nurse business-rule check.
    response = env.client.post(
        f"/alerts/{env.alert.id}/transfer",
        headers=auth_headers(env.doctor),
        json={
            "to_user_id": env.nurse_to.id,
            "reason": "Doctor role must not transfer an alert.",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Only active Nurses can assign or transfer alerts."
    )


def test_http_alert_transfer_rejects_non_assignee(
    http_security_env,
):
    env = http_security_env

    # The alert is assigned to nurse_from, not nurse_to.
    response = env.client.post(
        f"/alerts/{env.alert.id}/transfer",
        headers=auth_headers(env.nurse_to),
        json={
            "to_user_id": env.nurse_from.id,
            "reason": "Non-assignee transfer test.",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Only the currently assigned Nurse can transfer this alert."
    )


def test_http_eligible_nurses_returns_other_accessible_nurses(
    http_security_env,
):
    env = http_security_env

    response = env.client.get(
        f"/alerts/{env.alert.id}/eligible-nurses",
        headers=auth_headers(env.nurse_from),
    )

    assert response.status_code == 200, response.text

    payload = response.json()

    assert len(payload) == 1
    assert payload[0]["user_id"] == env.nurse_to.id
    assert payload[0]["username"] == env.nurse_to.username


def test_http_transfer_rejects_recipient_without_scope_access(
    http_security_env,
):
    env = http_security_env

    # Sender remains in scope, but recipient is removed.
    env.state["resource_access_user_ids"] = {
        env.nurse_from.id,
    }

    response = env.client.post(
        f"/alerts/{env.alert.id}/transfer",
        headers=auth_headers(env.nurse_from),
        json={
            "to_user_id": env.nurse_to.id,
            "reason": "Recipient resource scope test.",
        },
    )

    assert response.status_code == 403
    assert "receiving Nurse does not have access" in (
        response.json()["detail"]
    )

    history_response = env.client.get(
        f"/alerts/{env.alert.id}/history",
        headers=auth_headers(env.nurse_from),
    )

    assert history_response.status_code == 200
    assert history_response.json() == []
