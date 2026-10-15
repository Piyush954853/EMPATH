
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 - Register application models
from app.core.database import Base
from app.models.bed import Bed
from app.models.camera import Camera
from app.models.department import Department
from app.models.hospital import Hospital
from app.models.role import Role
from app.models.room import Room
from app.models.user import User
from app.models.user_bed import UserBed
from app.models.user_department import UserDepartment
from app.models.user_room import UserRoom
from app.models.user_ward import UserWard
from app.models.ward import Ward
from app.services import resource_access


@pytest.fixture
def resource_env():
    """Build real database-backed resource authorization fixtures."""

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    db = None

    try:
        Base.metadata.create_all(bind=engine)

        TestSession = sessionmaker(
            bind=engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )
        db = TestSession()

        # Roles
        nurse_role = Role(
            name="NURSE",
            description="Test Nurse",
            is_active=True,
        )
        admin_role = Role(
            name="ADMIN",
            description="Test Administrator",
            is_active=True,
        )

        db.add_all([nurse_role, admin_role])
        db.commit()
        db.refresh(nurse_role)
        db.refresh(admin_role)

        # Users
        def create_user(username, role):
            return User(
                username=username,
                email=f"{username}@example.test",
                full_name=username.replace("_", " ").title(),
                role_id=role.id,
                password_hash="test-only-unused-hash",
                is_active=True,
            )

        department_user = create_user("scope_department_user", nurse_role)
        ward_user = create_user("scope_ward_user", nurse_role)
        room_user = create_user("scope_room_user", nurse_role)
        bed_user = create_user("scope_bed_user", nurse_role)
        outsider = create_user("scope_outsider", nurse_role)
        admin_user = create_user("scope_admin", admin_role)

        db.add_all([
            department_user,
            ward_user,
            room_user,
            bed_user,
            outsider,
            admin_user,
        ])
        db.commit()

        for user in (
            department_user,
            ward_user,
            room_user,
            bed_user,
            outsider,
            admin_user,
        ):
            db.refresh(user)

        # Hospital
        hospital = Hospital(
            name="Authorization Test Hospital",
            code="AUTH-TEST-HOSPITAL",
            address="Test address",
            is_active=True,
        )
        db.add(hospital)
        db.commit()
        db.refresh(hospital)

        # Two departments
        department_a = Department(
            hospital_id=hospital.id,
            name="Department A",
            code="AUTH-DEPT-A",
            is_active=True,
        )
        department_b = Department(
            hospital_id=hospital.id,
            name="Department B",
            code="AUTH-DEPT-B",
            is_active=True,
        )
        db.add_all([department_a, department_b])
        db.commit()
        db.refresh(department_a)
        db.refresh(department_b)

        # Three wards across the two departments
        ward_a1 = Ward(
            department_id=department_a.id,
            name="Ward A1",
            code="AUTH-WARD-A1",
            is_active=True,
        )
        ward_a2 = Ward(
            department_id=department_a.id,
            name="Ward A2",
            code="AUTH-WARD-A2",
            is_active=True,
        )
        ward_b1 = Ward(
            department_id=department_b.id,
            name="Ward B1",
            code="AUTH-WARD-B1",
            is_active=True,
        )
        db.add_all([ward_a1, ward_a2, ward_b1])
        db.commit()

        for ward in (ward_a1, ward_a2, ward_b1):
            db.refresh(ward)

        # Four rooms
        room_a1 = Room(
            ward_id=ward_a1.id,
            name="Room A1",
            code="AUTH-ROOM-A1",
            is_active=True,
        )
        room_a2 = Room(
            ward_id=ward_a1.id,
            name="Room A2",
            code="AUTH-ROOM-A2",
            is_active=True,
        )
        room_a3 = Room(
            ward_id=ward_a2.id,
            name="Room A3",
            code="AUTH-ROOM-A3",
            is_active=True,
        )
        room_b1 = Room(
            ward_id=ward_b1.id,
            name="Room B1",
            code="AUTH-ROOM-B1",
            is_active=True,
        )
        db.add_all([room_a1, room_a2, room_a3, room_b1])
        db.commit()

        for room in (room_a1, room_a2, room_a3, room_b1):
            db.refresh(room)

        # Four beds
        bed_a1 = Bed(
            room_id=room_a1.id,
            name="Bed A1",
            code="AUTH-BED-A1",
            is_occupied=True,
            is_active=True,
        )
        bed_a2 = Bed(
            room_id=room_a2.id,
            name="Bed A2",
            code="AUTH-BED-A2",
            is_occupied=False,
            is_active=True,
        )
        bed_a3 = Bed(
            room_id=room_a3.id,
            name="Bed A3",
            code="AUTH-BED-A3",
            is_occupied=False,
            is_active=True,
        )
        bed_b1 = Bed(
            room_id=room_b1.id,
            name="Bed B1",
            code="AUTH-BED-B1",
            is_occupied=False,
            is_active=True,
        )
        db.add_all([bed_a1, bed_a2, bed_a3, bed_b1])
        db.commit()

        for bed in (bed_a1, bed_a2, bed_a3, bed_b1):
            db.refresh(bed)

        # Four cameras
        camera_a1 = Camera(
            room_id=room_a1.id,
            name="Camera A1",
            code="AUTH-CAMERA-A1",
            source_type="test",
            source_url=None,
            is_active=True,
        )
        camera_a2 = Camera(
            room_id=room_a2.id,
            name="Camera A2",
            code="AUTH-CAMERA-A2",
            source_type="test",
            source_url=None,
            is_active=True,
        )
        camera_a3 = Camera(
            room_id=room_a3.id,
            name="Camera A3",
            code="AUTH-CAMERA-A3",
            source_type="test",
            source_url=None,
            is_active=True,
        )
        camera_b1 = Camera(
            room_id=room_b1.id,
            name="Camera B1",
            code="AUTH-CAMERA-B1",
            source_type="test",
            source_url=None,
            is_active=True,
        )
        db.add_all([camera_a1, camera_a2, camera_a3, camera_b1])
        db.commit()

        for camera in (camera_a1, camera_a2, camera_a3, camera_b1):
            db.refresh(camera)

        # Independent assignments
        db.add_all([
            UserDepartment(
                user_id=department_user.id,
                department_id=department_a.id,
            ),
            UserWard(
                user_id=ward_user.id,
                ward_id=ward_a1.id,
            ),
            UserRoom(
                user_id=room_user.id,
                room_id=room_a1.id,
            ),
            UserBed(
                user_id=bed_user.id,
                bed_id=bed_a1.id,
            ),
        ])
        db.commit()

        yield SimpleNamespace(
            db=db,
            nurse_role=nurse_role,
            department_user=department_user,
            ward_user=ward_user,
            room_user=room_user,
            bed_user=bed_user,
            outsider=outsider,
            admin_user=admin_user,
            department_a=department_a,
            department_b=department_b,
            ward_a1=ward_a1,
            ward_a2=ward_a2,
            ward_b1=ward_b1,
            room_a1=room_a1,
            room_a2=room_a2,
            room_a3=room_a3,
            room_b1=room_b1,
            bed_a1=bed_a1,
            bed_a2=bed_a2,
            bed_a3=bed_a3,
            bed_b1=bed_b1,
            camera_a1=camera_a1,
            camera_a2=camera_a2,
            camera_a3=camera_a3,
            camera_b1=camera_b1,
        )

    finally:
        if db is not None:
            db.close()

        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_department_assignment_inherits_descendant_access(resource_env):
    env = resource_env
    db = env.db
    user = env.department_user

    assert resource_access.can_access_department(
        db, user, env.department_a.id, audit=False
    )
    assert not resource_access.can_access_department(
        db, user, env.department_b.id, audit=False
    )

    for ward in (env.ward_a1, env.ward_a2):
        assert resource_access.can_access_ward(
            db, user, ward.id, audit=False
        )

    assert not resource_access.can_access_ward(
        db, user, env.ward_b1.id, audit=False
    )

    for room in (env.room_a1, env.room_a2, env.room_a3):
        assert resource_access.can_access_room(
            db, user, room.id, audit=False
        )

    assert not resource_access.can_access_room(
        db, user, env.room_b1.id, audit=False
    )

    for bed in (env.bed_a1, env.bed_a2, env.bed_a3):
        assert resource_access.can_access_bed(
            db, user, bed.id, audit=False
        )

    assert not resource_access.can_access_bed(
        db, user, env.bed_b1.id, audit=False
    )

    for camera in (env.camera_a1, env.camera_a2, env.camera_a3):
        assert resource_access.can_access_camera(
            db, user, camera.id, audit=False
        )

    assert not resource_access.can_access_camera(
        db, user, env.camera_b1.id, audit=False
    )


def test_ward_assignment_does_not_grant_parent_or_sibling_scope(
    resource_env,
):
    env = resource_env
    db = env.db
    user = env.ward_user

    assert not resource_access.can_access_department(
        db, user, env.department_a.id, audit=False
    )
    assert not resource_access.can_access_ward(
        db, user, env.ward_a2.id, audit=False
    )
    assert not resource_access.can_access_ward(
        db, user, env.ward_b1.id, audit=False
    )

    for room in (env.room_a1, env.room_a2):
        assert resource_access.can_access_room(
            db, user, room.id, audit=False
        )

    for room in (env.room_a3, env.room_b1):
        assert not resource_access.can_access_room(
            db, user, room.id, audit=False
        )

    assert resource_access.can_access_bed(
        db, user, env.bed_a1.id, audit=False
    )
    assert resource_access.can_access_bed(
        db, user, env.bed_a2.id, audit=False
    )
    assert not resource_access.can_access_bed(
        db, user, env.bed_a3.id, audit=False
    )
    assert not resource_access.can_access_bed(
        db, user, env.bed_b1.id, audit=False
    )

    assert resource_access.can_access_camera(
        db, user, env.camera_a1.id, audit=False
    )
    assert resource_access.can_access_camera(
        db, user, env.camera_a2.id, audit=False
    )
    assert not resource_access.can_access_camera(
        db, user, env.camera_a3.id, audit=False
    )


def test_room_assignment_is_limited_to_room_and_descendants(resource_env):
    env = resource_env
    db = env.db
    user = env.room_user

    assert not resource_access.can_access_department(
        db, user, env.department_a.id, audit=False
    )
    assert not resource_access.can_access_ward(
        db, user, env.ward_a1.id, audit=False
    )

    assert resource_access.can_access_room(
        db, user, env.room_a1.id, audit=False
    )

    for room in (env.room_a2, env.room_a3, env.room_b1):
        assert not resource_access.can_access_room(
            db, user, room.id, audit=False
        )

    assert resource_access.can_access_bed(
        db, user, env.bed_a1.id, audit=False
    )

    for bed in (env.bed_a2, env.bed_a3, env.bed_b1):
        assert not resource_access.can_access_bed(
            db, user, bed.id, audit=False
        )

    assert resource_access.can_access_camera(
        db, user, env.camera_a1.id, audit=False
    )

    for camera in (env.camera_a2, env.camera_a3, env.camera_b1):
        assert not resource_access.can_access_camera(
            db, user, camera.id, audit=False
        )


def test_bed_assignment_does_not_grant_room_camera_or_parent_access(
    resource_env,
):
    env = resource_env
    db = env.db
    user = env.bed_user

    assert not resource_access.can_access_department(
        db, user, env.department_a.id, audit=False
    )
    assert not resource_access.can_access_ward(
        db, user, env.ward_a1.id, audit=False
    )
    assert not resource_access.can_access_room(
        db, user, env.room_a1.id, audit=False
    )

    assert resource_access.can_access_bed(
        db, user, env.bed_a1.id, audit=False
    )

    for bed in (env.bed_a2, env.bed_a3, env.bed_b1):
        assert not resource_access.can_access_bed(
            db, user, bed.id, audit=False
        )

    assert not resource_access.can_access_camera(
        db, user, env.camera_a1.id, audit=False
    )


def test_unassigned_user_is_denied_resource_access(resource_env):
    env = resource_env
    db = env.db
    user = env.outsider

    assert not resource_access.can_access_department(
        db, user, env.department_a.id, audit=False
    )
    assert not resource_access.can_access_ward(
        db, user, env.ward_a1.id, audit=False
    )
    assert not resource_access.can_access_room(
        db, user, env.room_a1.id, audit=False
    )
    assert not resource_access.can_access_bed(
        db, user, env.bed_a1.id, audit=False
    )
    assert not resource_access.can_access_camera(
        db, user, env.camera_a1.id, audit=False
    )


def test_admin_retains_access_to_existing_resources(resource_env):
    env = resource_env
    db = env.db
    user = env.admin_user

    assert resource_access.can_access_department(
        db, user, env.department_a.id, audit=False
    )
    assert resource_access.can_access_department(
        db, user, env.department_b.id, audit=False
    )
    assert resource_access.can_access_ward(
        db, user, env.ward_b1.id, audit=False
    )
    assert resource_access.can_access_room(
        db, user, env.room_b1.id, audit=False
    )
    assert resource_access.can_access_bed(
        db, user, env.bed_b1.id, audit=False
    )
    assert resource_access.can_access_camera(
        db, user, env.camera_b1.id, audit=False
    )


def test_inactive_user_or_role_is_denied(resource_env):
    env = resource_env
    db = env.db

    # Inactive user with an otherwise valid assignment.
    env.room_user.is_active = False
    db.commit()

    assert not resource_access.can_access_room(
        db, env.room_user, env.room_a1.id, audit=False
    )

    # Active user with an inactive role must also be denied.
    env.room_user.is_active = True
    env.nurse_role.is_active = False
    db.commit()

    assert not resource_access.can_access_room(
        db, env.room_user, env.room_a1.id, audit=False
    )
    assert not resource_access.can_access_bed(
        db, env.bed_user, env.bed_a1.id, audit=False
    )


def test_nonexistent_resources_are_denied(resource_env):
    env = resource_env
    db = env.db
    user = env.outsider
    missing_id = 999999

    assert not resource_access.can_access_department(
        db, user, missing_id, audit=False
    )
    assert not resource_access.can_access_ward(
        db, user, missing_id, audit=False
    )
    assert not resource_access.can_access_room(
        db, user, missing_id, audit=False
    )
    assert not resource_access.can_access_bed(
        db, user, missing_id, audit=False
    )
    assert not resource_access.can_access_camera(
        db, user, missing_id, audit=False
    )


def test_authorization_audit_records_allowed_and_denied_checks(
    resource_env,
    monkeypatch,
):
    env = resource_env
    calls = []

    def fake_record_authorization_decision(
        _db,
        *,
        user_id,
        action,
        resource_type,
        resource_id,
        allowed,
        reason,
    ):
        calls.append({
            "user_id": user_id,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "allowed": allowed,
            "reason": reason,
        })

    monkeypatch.setattr(
        resource_access,
        "record_authorization_decision",
        fake_record_authorization_decision,
    )

    assert resource_access.can_access_room(
        env.db,
        env.room_user,
        env.room_a1.id,
    )

    assert not resource_access.can_access_room(
        env.db,
        env.room_user,
        env.room_a2.id,
    )

    assert len(calls) == 2

    assert calls[0]["action"] == "ROOM_ACCESS"
    assert calls[0]["resource_type"] == "room"
    assert calls[0]["resource_id"] == env.room_a1.id
    assert calls[0]["allowed"] is True
    assert calls[0]["reason"] == "RESOURCE_SCOPE"

    assert calls[1]["action"] == "ROOM_ACCESS"
    assert calls[1]["resource_type"] == "room"
    assert calls[1]["resource_id"] == env.room_a2.id
    assert calls[1]["allowed"] is False
    assert calls[1]["reason"] == "RESOURCE_SCOPE_DENIED"

    # audit=False must not record an additional decision.
    assert not resource_access.can_access_room(
        env.db,
        env.room_user,
        env.room_a2.id,
        audit=False,
    )
    assert len(calls) == 2
