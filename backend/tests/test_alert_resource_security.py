
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 - Register application models
from app.core.database import Base, get_db
from app.core.jwt import create_access_token
from app.main import app
from app.models.alert import Alert
from app.models.bed import Bed
from app.models.camera import Camera
from app.models.department import Department
from app.models.event import Event
from app.models.hospital import Hospital
from app.models.patient import Patient
from app.models.permission import Permission
from app.models.role import Role
from app.models.role_permission import RolePermission
from app.models.room import Room
from app.models.user import User
from app.models.user_bed import UserBed
from app.models.user_room import UserRoom
from app.models.ward import Ward


def auth_headers(user):
    """Generate a real application JWT for this test user."""
    token = create_access_token(str(user.id))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def real_alert_scope_env():
    """
    Use an isolated SQLite database and the real resource authorization
    implementation. Only get_db is overridden.

    JWT validation, current-user resolution, permission checks, alert
    routes, and can_access_alert all remain the real application code.
    """

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    db = None
    client = None
    previous_overrides = app.dependency_overrides.copy()

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
        # 1. Role and actual endpoint permissions
        # -----------------------------------------------------
        nurse_role = Role(
            name="NURSE",
            description="Real resource-security test Nurse",
            is_active=True,
        )

        db.add(nurse_role)
        db.commit()
        db.refresh(nurse_role)

        alerts_read = Permission(
            name="alerts.read",
            description="Read alert resources",
            is_active=True,
        )
        alerts_acknowledge = Permission(
            name="alerts.acknowledge",
            description="Transfer and acknowledge alerts",
            is_active=True,
        )

        db.add_all([alerts_read, alerts_acknowledge])
        db.commit()

        db.refresh(alerts_read)
        db.refresh(alerts_acknowledge)

        db.add_all([
            RolePermission(
                role_id=nurse_role.id,
                permission_id=alerts_read.id,
            ),
            RolePermission(
                role_id=nurse_role.id,
                permission_id=alerts_acknowledge.id,
            ),
        ])
        db.commit()

        # -----------------------------------------------------
        # 2. Four active Nurses
        # -----------------------------------------------------
        def create_user(username):
            return User(
                username=username,
                email=f"{username}@example.test",
                full_name=username.replace("_", " ").title(),
                role_id=nurse_role.id,
                password_hash="test-only-unused-hash",
                is_active=True,
            )

        nurse_room_a = create_user("scope_http_room_a")
        nurse_room_a_peer = create_user("scope_http_room_a_peer")
        nurse_room_b = create_user("scope_http_room_b")
        nurse_bed_a = create_user("scope_http_bed_a")

        db.add_all([
            nurse_room_a,
            nurse_room_a_peer,
            nurse_room_b,
            nurse_bed_a,
        ])
        db.commit()

        for user in (
            nurse_room_a,
            nurse_room_a_peer,
            nurse_room_b,
            nurse_bed_a,
        ):
            db.refresh(user)

        # -----------------------------------------------------
        # 3. Hospital, department and ward
        # -----------------------------------------------------
        hospital = Hospital(
            name="HTTP Scope Test Hospital",
            code="HTTP-SCOPE-HOSPITAL",
            address="Test address",
            is_active=True,
        )
        db.add(hospital)
        db.commit()
        db.refresh(hospital)

        department = Department(
            hospital_id=hospital.id,
            name="HTTP Scope Department",
            code="HTTP-SCOPE-DEPT",
            is_active=True,
        )
        db.add(department)
        db.commit()
        db.refresh(department)

        ward = Ward(
            department_id=department.id,
            name="HTTP Scope Ward",
            code="HTTP-SCOPE-WARD",
            is_active=True,
        )
        db.add(ward)
        db.commit()
        db.refresh(ward)

        # -----------------------------------------------------
        # 4. Two separate rooms
        # -----------------------------------------------------
        room_a = Room(
            ward_id=ward.id,
            name="HTTP Scope Room A",
            code="HTTP-SCOPE-ROOM-A",
            is_active=True,
        )
        room_b = Room(
            ward_id=ward.id,
            name="HTTP Scope Room B",
            code="HTTP-SCOPE-ROOM-B",
            is_active=True,
        )

        db.add_all([room_a, room_b])
        db.commit()
        db.refresh(room_a)
        db.refresh(room_b)

        # -----------------------------------------------------
        # 5. One bed and camera in each room
        # -----------------------------------------------------
        bed_a = Bed(
            room_id=room_a.id,
            name="HTTP Scope Bed A",
            code="HTTP-SCOPE-BED-A",
            is_occupied=True,
            is_active=True,
        )
        bed_b = Bed(
            room_id=room_b.id,
            name="HTTP Scope Bed B",
            code="HTTP-SCOPE-BED-B",
            is_occupied=True,
            is_active=True,
        )

        db.add_all([bed_a, bed_b])
        db.commit()
        db.refresh(bed_a)
        db.refresh(bed_b)

        camera_a = Camera(
            room_id=room_a.id,
            name="HTTP Scope Camera A",
            code="HTTP-SCOPE-CAMERA-A",
            source_type="test",
            source_url=None,
            is_active=True,
        )
        camera_b = Camera(
            room_id=room_b.id,
            name="HTTP Scope Camera B",
            code="HTTP-SCOPE-CAMERA-B",
            source_type="test",
            source_url=None,
            is_active=True,
        )

        db.add_all([camera_a, camera_b])
        db.commit()
        db.refresh(camera_a)
        db.refresh(camera_b)

        # -----------------------------------------------------
        # 6. Patients linked to their beds
        # -----------------------------------------------------
        patient_a = Patient(
            bed_id=bed_a.id,
            patient_code="HTTP-SCOPE-PATIENT-A",
            name="Test Patient A",
            is_active=True,
        )
        patient_b = Patient(
            bed_id=bed_b.id,
            patient_code="HTTP-SCOPE-PATIENT-B",
            name="Test Patient B",
            is_active=True,
        )

        db.add_all([patient_a, patient_b])
        db.commit()
        db.refresh(patient_a)
        db.refresh(patient_b)

        # -----------------------------------------------------
        # 7. Explicit user resource assignments
        # -----------------------------------------------------
        db.add_all([
            UserRoom(
                user_id=nurse_room_a.id,
                room_id=room_a.id,
            ),
            UserRoom(
                user_id=nurse_room_a_peer.id,
                room_id=room_a.id,
            ),
            UserRoom(
                user_id=nurse_room_b.id,
                room_id=room_b.id,
            ),
            UserBed(
                user_id=nurse_bed_a.id,
                bed_id=bed_a.id,
            ),
        ])
        db.commit()

        # -----------------------------------------------------
        # 8. Events with actual camera/patient foreign keys
        # -----------------------------------------------------
        camera_event_a = Event(
            camera_id=camera_a.id,
            patient_id=None,
            event_type="alert_handoff_test",
            source_type="manual_test",
            severity="medium",
            status="test",
            confidence=None,
            description="Test camera event in room A.",
            metadata_json='{"test_only": true}',
        )
        camera_event_b = Event(
            camera_id=camera_b.id,
            patient_id=None,
            event_type="alert_handoff_test",
            source_type="manual_test",
            severity="medium",
            status="test",
            confidence=None,
            description="Test camera event in room B.",
            metadata_json='{"test_only": true}',
        )
        patient_event_a = Event(
            camera_id=None,
            patient_id=patient_a.id,
            event_type="alert_handoff_test",
            source_type="manual_test",
            severity="medium",
            status="test",
            confidence=None,
            description="Test patient event for bed A.",
            metadata_json='{"test_only": true}',
        )
        patient_event_b = Event(
            camera_id=None,
            patient_id=patient_b.id,
            event_type="alert_handoff_test",
            source_type="manual_test",
            severity="medium",
            status="test",
            confidence=None,
            description="Test patient event for bed B.",
            metadata_json='{"test_only": true}',
        )

        db.add_all([
            camera_event_a,
            camera_event_b,
            patient_event_a,
            patient_event_b,
        ])
        db.commit()

        for event in (
            camera_event_a,
            camera_event_b,
            patient_event_a,
            patient_event_b,
        ):
            db.refresh(event)

        # -----------------------------------------------------
        # 9. Alerts linked to their real events
        # -----------------------------------------------------
        camera_alert_a = Alert(
            event_id=camera_event_a.id,
            priority="medium",
            status="active",
            title="TEST - Room A Camera Alert",
            message="Test camera alert for room A.",
            summary="Test-only summary.",
            assigned_to_user_id=nurse_room_a.id,
        )
        camera_alert_b = Alert(
            event_id=camera_event_b.id,
            priority="medium",
            status="active",
            title="TEST - Room B Camera Alert",
            message="Test camera alert for room B.",
            summary="Test-only summary.",
            assigned_to_user_id=nurse_room_b.id,
        )
        patient_alert_a = Alert(
            event_id=patient_event_a.id,
            priority="medium",
            status="active",
            title="TEST - Patient A Alert",
            message="Test patient alert for bed A.",
            summary="Test-only summary.",
            assigned_to_user_id=nurse_bed_a.id,
        )
        patient_alert_b = Alert(
            event_id=patient_event_b.id,
            priority="medium",
            status="active",
            title="TEST - Patient B Alert",
            message="Test patient alert for bed B.",
            summary="Test-only summary.",
            assigned_to_user_id=nurse_room_b.id,
        )

        db.add_all([
            camera_alert_a,
            camera_alert_b,
            patient_alert_a,
            patient_alert_b,
        ])
        db.commit()

        for alert in (
            camera_alert_a,
            camera_alert_b,
            patient_alert_a,
            patient_alert_b,
        ):
            db.refresh(alert)

        # Override only the database dependency.
        # Do not override get_current_user, permissions,
        # can_access_alert, or resource-access functions.
        def override_get_db():
            yield db

        app.dependency_overrides[get_db] = override_get_db

        client = TestClient(app)

        yield SimpleNamespace(
            client=client,
            nurse_room_a=nurse_room_a,
            nurse_room_a_peer=nurse_room_a_peer,
            nurse_room_b=nurse_room_b,
            nurse_bed_a=nurse_bed_a,
            camera_alert_a=camera_alert_a,
            camera_alert_b=camera_alert_b,
            patient_alert_a=patient_alert_a,
            patient_alert_b=patient_alert_b,
        )

    finally:
        if client is not None:
            client.close()

        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)

        if db is not None:
            db.close()

        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_room_nurse_can_read_camera_alert_in_assigned_room(
    real_alert_scope_env,
):
    env = real_alert_scope_env

    response = env.client.get(
        f"/alerts/{env.camera_alert_a.id}",
        headers=auth_headers(env.nurse_room_a),
    )

    assert response.status_code == 200, response.text
    assert response.json()["id"] == env.camera_alert_a.id


def test_room_nurse_cannot_read_other_rooms_camera_alert(
    real_alert_scope_env,
):
    env = real_alert_scope_env

    response = env.client.get(
        f"/alerts/{env.camera_alert_a.id}",
        headers=auth_headers(env.nurse_room_b),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Alert access denied"


def test_bed_assignment_allows_patient_alert_only_for_assigned_bed(
    real_alert_scope_env,
):
    env = real_alert_scope_env

    allowed_response = env.client.get(
        f"/alerts/{env.patient_alert_a.id}",
        headers=auth_headers(env.nurse_bed_a),
    )

    assert allowed_response.status_code == 200, allowed_response.text

    denied_response = env.client.get(
        f"/alerts/{env.patient_alert_b.id}",
        headers=auth_headers(env.nurse_bed_a),
    )

    assert denied_response.status_code == 403
    assert denied_response.json()["detail"] == "Alert access denied"


def test_bed_only_assignment_does_not_allow_camera_alert(
    real_alert_scope_env,
):
    env = real_alert_scope_env

    response = env.client.get(
        f"/alerts/{env.camera_alert_a.id}",
        headers=auth_headers(env.nurse_bed_a),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Alert access denied"


def test_transfer_rejects_recipient_without_resource_scope(
    real_alert_scope_env,
):
    env = real_alert_scope_env

    response = env.client.post(
        f"/alerts/{env.camera_alert_a.id}/transfer",
        headers=auth_headers(env.nurse_room_a),
        json={
            "to_user_id": env.nurse_room_b.id,
            "reason": "Cross-room scope security test.",
        },
    )

    assert response.status_code == 403
    assert "receiving Nurse does not have access" in (
        response.json()["detail"]
    )

    # The rejected transfer must not create handoff history.
    history_response = env.client.get(
        f"/alerts/{env.camera_alert_a.id}/history",
        headers=auth_headers(env.nurse_room_a),
    )

    assert history_response.status_code == 200
    assert history_response.json() == []


def test_transfer_succeeds_when_both_nurses_have_room_scope(
    real_alert_scope_env,
):
    env = real_alert_scope_env

    response = env.client.post(
        f"/alerts/{env.camera_alert_a.id}/transfer",
        headers=auth_headers(env.nurse_room_a),
        json={
            "to_user_id": env.nurse_room_a_peer.id,
            "reason": "Authorized same-room handoff test.",
        },
    )

    assert response.status_code == 200, response.text

    payload = response.json()
    assert payload["assigned_to_user_id"] == env.nurse_room_a_peer.id
    assert payload["status"] == "active"

    history_response = env.client.get(
        f"/alerts/{env.camera_alert_a.id}/history",
        headers=auth_headers(env.nurse_room_a),
    )

    assert history_response.status_code == 200, history_response.text

    history = history_response.json()
    assert len(history) == 1
    assert history[0]["from_user_id"] == env.nurse_room_a.id
    assert history[0]["to_user_id"] == env.nurse_room_a_peer.id
    assert history[0]["transferred_by_user_id"] == env.nurse_room_a.id
    assert history[0]["reason"] == "Authorized same-room handoff test."


def test_eligible_nurses_are_filtered_by_real_room_scope(
    real_alert_scope_env,
):
    env = real_alert_scope_env

    response = env.client.get(
        f"/alerts/{env.camera_alert_a.id}/eligible-nurses",
        headers=auth_headers(env.nurse_room_a),
    )

    assert response.status_code == 200, response.text

    payload = response.json()

    # Only the other Nurse assigned to room A is eligible.
    assert [
        item["user_id"] for item in payload
    ] == [env.nurse_room_a_peer.id]
