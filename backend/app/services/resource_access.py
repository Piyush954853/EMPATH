
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.bed import Bed
from app.models.camera import Camera
from app.models.department import Department
from app.models.role import Role
from app.models.room import Room
from app.models.user import User
from app.models.user_bed import UserBed
from app.models.user_department import UserDepartment
from app.models.user_room import UserRoom
from app.models.user_ward import UserWard
from app.models.ward import Ward
from app.services.authorization_audit import (
    record_authorization_decision,
)


# =========================================================
# PRINCIPAL AND ROLE VALIDATION
# =========================================================

def is_admin(
    db: Session,
    user: User,
) -> bool:
    """Return True only for an active user with an active ADMIN role."""

    if not user.is_active:
        return False

    role = db.get(Role, user.role_id)

    return (
        role is not None
        and role.is_active
        and role.name.upper() == "ADMIN"
    )


def _has_active_principal(
    db: Session,
    user: User,
) -> bool:
    """Fail closed when the user or their role is inactive or missing."""

    if not user.is_active:
        return False

    role = db.get(Role, user.role_id)

    return role is not None and role.is_active


# =========================================================
# DEPARTMENT ACCESS
#
# Direct department assignment grants access to that department.
# Department access can be inherited DOWNWARD by its wards,
# rooms, beds, and room cameras.
#
# Ward, room, and bed assignments do NOT grant parent
# department access.
# =========================================================

def _can_access_department(
    db: Session,
    user: User,
    department_id: int,
) -> bool:
    department = db.get(Department, department_id)

    if department is None:
        return False

    if not _has_active_principal(db, user):
        return False

    if is_admin(db, user):
        return True

    assignment = db.scalar(
        select(UserDepartment.id).where(
            UserDepartment.user_id == user.id,
            UserDepartment.department_id == department_id,
        )
    )

    return assignment is not None


# =========================================================
# WARD ACCESS
#
# Access may come from:
# 1. Active ADMIN role
# 2. Direct assignment to the ward's department
# 3. Direct assignment to this ward
#
# Room and bed assignments do not grant ward access.
# =========================================================

def _can_access_ward(
    db: Session,
    user: User,
    ward_id: int,
) -> bool:
    ward = db.get(Ward, ward_id)

    if ward is None:
        return False

    if not _has_active_principal(db, user):
        return False

    if is_admin(db, user):
        return True

    # A direct parent-department assignment inherits downward.
    if _can_access_department(
        db,
        user,
        ward.department_id,
    ):
        return True

    # Otherwise, the user must be assigned to this ward.
    assignment = db.scalar(
        select(UserWard.id).where(
            UserWard.user_id == user.id,
            UserWard.ward_id == ward_id,
        )
    )

    return assignment is not None


# =========================================================
# ROOM ACCESS
#
# Access may come from:
# 1. Active ADMIN role
# 2. Parent department assignment
# 3. Parent ward assignment
# 4. Direct assignment to this room
#
# Bed assignment does not grant room access.
# =========================================================

def _can_access_room(
    db: Session,
    user: User,
    room_id: int,
) -> bool:
    room = db.get(Room, room_id)

    if room is None:
        return False

    if not _has_active_principal(db, user):
        return False

    if is_admin(db, user):
        return True

    # Department and ward assignments grant descendant access.
    if _can_access_ward(
        db,
        user,
        room.ward_id,
    ):
        return True

    # Otherwise, require a direct assignment to this room.
    assignment = db.scalar(
        select(UserRoom.id).where(
            UserRoom.user_id == user.id,
            UserRoom.room_id == room_id,
        )
    )

    return assignment is not None


# =========================================================
# BED ACCESS
#
# Access may come from:
# 1. Active ADMIN role
# 2. Parent department assignment
# 3. Parent ward assignment
# 4. Parent room assignment
# 5. Direct assignment to this bed
#
# A bed assignment alone does not grant room or parent access.
# =========================================================

def _can_access_bed(
    db: Session,
    user: User,
    bed_id: int,
) -> bool:
    bed = db.get(Bed, bed_id)

    if bed is None:
        return False

    if not _has_active_principal(db, user):
        return False

    if is_admin(db, user):
        return True

    # Parent assignments inherit access to descendant beds.
    if _can_access_room(
        db,
        user,
        bed.room_id,
    ):
        return True

    # Otherwise, require a direct assignment to this bed.
    assignment = db.scalar(
        select(UserBed.id).where(
            UserBed.user_id == user.id,
            UserBed.bed_id == bed_id,
        )
    )

    return assignment is not None


# =========================================================
# CAMERA ACCESS
#
# There is no direct user-camera assignment table in the
# supplied models. Camera access therefore follows the room:
# parent department, parent ward, or direct room assignment.
#
# A bed-only assignment does not grant camera access.
# =========================================================

def _can_access_camera(
    db: Session,
    user: User,
    camera_id: int,
) -> bool:
    camera = db.get(Camera, camera_id)

    if camera is None:
        return False

    if not _has_active_principal(db, user):
        return False

    if is_admin(db, user):
        return True

    return _can_access_room(
        db,
        user,
        camera.room_id,
    )


# =========================================================
# SHARED AUTHORIZATION AUDIT
# =========================================================

def _record_access_decision(
    db: Session,
    user: User,
    *,
    action: str,
    resource_type: str,
    resource_id: int,
    allowed: bool,
) -> None:
    """
    Record one authorization decision and commit it.

    Existing action names, resource types, and reason values
    are retained for compatibility with current audit consumers.
    """

    admin_bypass = allowed and is_admin(db, user)

    if admin_bypass:
        reason = "ADMIN_BYPASS"
    elif allowed:
        reason = "RESOURCE_SCOPE"
    else:
        reason = "RESOURCE_SCOPE_DENIED"

    record_authorization_decision(
        db,
        user_id=user.id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        allowed=allowed,
        reason=reason,
    )

    db.commit()


# =========================================================
# PUBLIC ACCESS FUNCTIONS
# =========================================================

def can_access_department(
    db: Session,
    user: User,
    department_id: int,
    *,
    audit: bool = True,
) -> bool:
    allowed = _can_access_department(
        db,
        user,
        department_id,
    )

    if audit:
        _record_access_decision(
            db,
            user,
            action="DEPARTMENT_ACCESS",
            resource_type="department",
            resource_id=department_id,
            allowed=allowed,
        )

    return allowed


def can_access_ward(
    db: Session,
    user: User,
    ward_id: int,
    *,
    audit: bool = True,
) -> bool:
    allowed = _can_access_ward(
        db,
        user,
        ward_id,
    )

    if audit:
        _record_access_decision(
            db,
            user,
            action="WARD_ACCESS",
            resource_type="ward",
            resource_id=ward_id,
            allowed=allowed,
        )

    return allowed


def can_access_room(
    db: Session,
    user: User,
    room_id: int,
    *,
    audit: bool = True,
) -> bool:
    allowed = _can_access_room(
        db,
        user,
        room_id,
    )

    if audit:
        _record_access_decision(
            db,
            user,
            action="ROOM_ACCESS",
            resource_type="room",
            resource_id=room_id,
            allowed=allowed,
        )

    return allowed


def can_access_bed(
    db: Session,
    user: User,
    bed_id: int,
    *,
    audit: bool = True,
) -> bool:
    allowed = _can_access_bed(
        db,
        user,
        bed_id,
    )

    if audit:
        _record_access_decision(
            db,
            user,
            action="BED_ACCESS",
            resource_type="bed",
            resource_id=bed_id,
            allowed=allowed,
        )

    return allowed


def can_access_camera(
    db: Session,
    user: User,
    camera_id: int,
    *,
    audit: bool = True,
) -> bool:
    allowed = _can_access_camera(
        db,
        user,
        camera_id,
    )

    if audit:
        _record_access_decision(
            db,
            user,
            action="CAMERA_ACCESS",
            resource_type="camera",
            resource_id=camera_id,
            allowed=allowed,
        )

    return allowed
