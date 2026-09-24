from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.bed import Bed
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


def is_admin(
    db: Session,
    user: User,
) -> bool:
    role = db.get(Role, user.role_id)

    return role is not None and role.name == "ADMIN"


def _can_access_department(
    db: Session,
    user: User,
    department_id: int,
) -> bool:
    department = db.get(Department, department_id)

    if department is None:
        return False

    if is_admin(db, user):
        return True

    assignment = db.scalar(
        select(UserDepartment.id).where(
            UserDepartment.user_id == user.id,
            UserDepartment.department_id == department_id,
        )
    )

    if assignment is not None:
        return True

    ward_exists = db.scalar(
        select(UserWard.id)
        .join(
            Ward,
            Ward.id == UserWard.ward_id,
        )
        .where(
            UserWard.user_id == user.id,
            Ward.department_id == department_id,
        )
    )

    return ward_exists is not None


def _can_access_ward(
    db: Session,
    user: User,
    ward_id: int,
) -> bool:
    ward = db.get(Ward, ward_id)

    if ward is None:
        return False

    if is_admin(db, user):
        return True

    if _can_access_department(
        db,
        user,
        ward.department_id,
    ):
        return True

    assignment = db.scalar(
        select(UserWard.id).where(
            UserWard.user_id == user.id,
            UserWard.ward_id == ward_id,
        )
    )

    return assignment is not None


def _can_access_room(
    db: Session,
    user: User,
    room_id: int,
) -> bool:
    room = db.get(Room, room_id)

    if room is None:
        return False

    if is_admin(db, user):
        return True

    if _can_access_ward(
        db,
        user,
        room.ward_id,
    ):
        return True

    assignment = db.scalar(
        select(UserRoom.id).where(
            UserRoom.user_id == user.id,
            UserRoom.room_id == room_id,
        )
    )

    return assignment is not None


def _can_access_bed(
    db: Session,
    user: User,
    bed_id: int,
) -> bool:
    bed = db.get(Bed, bed_id)

    if bed is None:
        return False

    if is_admin(db, user):
        return True

    if _can_access_room(
        db,
        user,
        bed.room_id,
    ):
        return True

    assignment = db.scalar(
        select(UserBed.id).where(
            UserBed.user_id == user.id,
            UserBed.bed_id == bed_id,
        )
    )

    return assignment is not None


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
        record_authorization_decision(
            db,
            user_id=user.id,
            action="DEPARTMENT_ACCESS",
            resource_type="department",
            resource_id=department_id,
            allowed=allowed,
            reason=(
                "ADMIN_BYPASS"
                if allowed and is_admin(db, user)
                else (
                    "RESOURCE_SCOPE"
                    if allowed
                    else "RESOURCE_SCOPE_DENIED"
                )
            ),
        )
        db.commit()

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
        record_authorization_decision(
            db,
            user_id=user.id,
            action="WARD_ACCESS",
            resource_type="ward",
            resource_id=ward_id,
            allowed=allowed,
            reason=(
                "ADMIN_BYPASS"
                if allowed and is_admin(db, user)
                else (
                    "RESOURCE_SCOPE"
                    if allowed
                    else "RESOURCE_SCOPE_DENIED"
                )
            ),
        )
        db.commit()

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
        record_authorization_decision(
            db,
            user_id=user.id,
            action="ROOM_ACCESS",
            resource_type="room",
            resource_id=room_id,
            allowed=allowed,
            reason=(
                "ADMIN_BYPASS"
                if allowed and is_admin(db, user)
                else (
                    "RESOURCE_SCOPE"
                    if allowed
                    else "RESOURCE_SCOPE_DENIED"
                )
            ),
        )
        db.commit()

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
        record_authorization_decision(
            db,
            user_id=user.id,
            action="BED_ACCESS",
            resource_type="bed",
            resource_id=bed_id,
            allowed=allowed,
            reason=(
                "ADMIN_BYPASS"
                if allowed and is_admin(db, user)
                else (
                    "RESOURCE_SCOPE"
                    if allowed
                    else "RESOURCE_SCOPE_DENIED"
                )
            ),
        )
        db.commit()

    return allowed