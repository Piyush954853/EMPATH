
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.permissions import require_permission
from app.core.database import get_db
from app.core.security import hash_password
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

from app.schemas.auth import UserResponse
from app.schemas.users import (
    RoleResponse,
    UserAssignmentsResponse,
    UserAssignmentsUpdate,
    UserCreate,
    UserUpdate,
)


router = APIRouter(prefix="/users", tags=["Users"])


def _user_or_404(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return user


def _user_response(db: Session, user: User) -> UserResponse:
    role = db.get(Role, user.role_id)

    if role is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User role configuration is invalid",
        )

    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        role_id=user.role_id,
        is_active=user.is_active,
        role_name=role.name,
    )


def _active_role_or_422(db: Session, role_id: int) -> Role:
    role = db.get(Role, role_id)

    if role is None or not role.is_active:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Selected role does not exist or is inactive",
        )

    return role


def _validated_active_ids(
    db: Session,
    model,
    ids: list[int],
    label: str,
) -> list[int]:
    ids = list(dict.fromkeys(ids))

    if not ids:
        return []

    existing_ids = set(
        db.scalars(
            select(model.id).where(
                model.id.in_(ids),
                model.is_active.is_(True),
            )
        ).all()
    )

    invalid_ids = sorted(set(ids) - existing_ids)

    if invalid_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid or inactive {label} IDs: {invalid_ids}",
        )

    return ids


def _read_assignments(
    db: Session,
    user_id: int,
) -> UserAssignmentsResponse:
    return UserAssignmentsResponse(
        user_id=user_id,
        department_ids=db.scalars(
            select(UserDepartment.department_id)
            .where(UserDepartment.user_id == user_id)
            .order_by(UserDepartment.department_id)
        ).all(),
        ward_ids=db.scalars(
            select(UserWard.ward_id)
            .where(UserWard.user_id == user_id)
            .order_by(UserWard.ward_id)
        ).all(),
        room_ids=db.scalars(
            select(UserRoom.room_id)
            .where(UserRoom.user_id == user_id)
            .order_by(UserRoom.room_id)
        ).all(),
        bed_ids=db.scalars(
            select(UserBed.bed_id)
            .where(UserBed.user_id == user_id)
            .order_by(UserBed.bed_id)
        ).all(),
    )


def _replace_assignment_rows(
    db: Session,
    user_id: int,
    model,
    id_field: str,
    ids: list[int],
) -> None:
    db.execute(
        delete(model).where(model.user_id == user_id)
    )

    for resource_id in ids:
        db.add(
            model(
                user_id=user_id,
                **{id_field: resource_id},
            )
        )


@router.get("/roles", response_model=list[RoleResponse])
def list_roles(
    current_user: User = Depends(
        require_permission("users.read")
    ),
    db: Session = Depends(get_db),
):
    return db.scalars(
        select(Role)
        .where(Role.is_active.is_(True))
        .order_by(Role.name)
    ).all()


@router.get("", response_model=list[UserResponse])
def list_users(
    current_user: User = Depends(
        require_permission("users.read")
    ),
    db: Session = Depends(get_db),
):
    users = db.scalars(
        select(User).order_by(User.id)
    ).all()

    return [
        _user_response(db, user)
        for user in users
    ]


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_user(
    request: UserCreate,
    current_user: User = Depends(
        require_permission("users.create")
    ),
    db: Session = Depends(get_db),
):
    _active_role_or_422(db, request.role_id)

    existing = db.scalar(
        select(User.id).where(
            (User.username == request.username)
            | (User.email == request.email)
        )
    )

    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username or email already exists",
        )

    user = User(
        username=request.username,
        email=request.email,
        full_name=request.full_name,
        role_id=request.role_id,
        password_hash=hash_password(request.password),
        is_active=True,
    )

    db.add(user)

    try:
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username or email already exists",
        )

    return _user_response(db, user)


@router.get(
    "/{user_id}/assignments",
    response_model=UserAssignmentsResponse,
)
def get_user_assignments(
    user_id: int,
    current_user: User = Depends(
        require_permission("users.read")
    ),
    db: Session = Depends(get_db),
):
    _user_or_404(db, user_id)

    return _read_assignments(db, user_id)


@router.put(
    "/{user_id}/assignments",
    response_model=UserAssignmentsResponse,
)
def update_user_assignments(
    user_id: int,
    request: UserAssignmentsUpdate,
    current_user: User = Depends(
        require_permission("users.update")
    ),
    db: Session = Depends(get_db),
):
    _user_or_404(db, user_id)

    department_ids = _validated_active_ids(
        db, Department, request.department_ids, "department"
    )
    ward_ids = _validated_active_ids(
        db, Ward, request.ward_ids, "ward"
    )
    room_ids = _validated_active_ids(
        db, Room, request.room_ids, "room"
    )
    bed_ids = _validated_active_ids(
        db, Bed, request.bed_ids, "bed"
    )

    try:
        _replace_assignment_rows(
            db, user_id, UserDepartment,
            "department_id", department_ids
        )
        _replace_assignment_rows(
            db, user_id, UserWard,
            "ward_id", ward_ids
        )
        _replace_assignment_rows(
            db, user_id, UserRoom,
            "room_id", room_ids
        )
        _replace_assignment_rows(
            db, user_id, UserBed,
            "bed_id", bed_ids
        )

        db.commit()

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Assignments could not be saved; verify selected resources",
        )

    return _read_assignments(db, user_id)


@router.patch(
    "/{user_id}",
    response_model=UserResponse,
)
def update_user(
    user_id: int,
    request: UserUpdate,
    current_user: User = Depends(
        require_permission("users.update")
    ),
    db: Session = Depends(get_db),
):
    user = _user_or_404(db, user_id)

    changes = request.model_dump(exclude_unset=True)

    if not changes:
        return _user_response(db, user)

    if any(value is None for value in changes.values()):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provided fields cannot be null",
        )

    if user.id == current_user.id and (
        changes.get("is_active") is False
        or (
            "role_id" in changes
            and changes["role_id"] != current_user.role_id
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot deactivate your own account or change your own role",
        )

    if "role_id" in changes:
        _active_role_or_422(db, changes["role_id"])

    if "email" in changes:
        duplicate = db.scalar(
            select(User.id).where(
                User.email == changes["email"],
                User.id != user_id,
            )
        )

        if duplicate is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already belongs to another user",
            )

    if "password" in changes:
        changes["password_hash"] = hash_password(
            changes.pop("password")
        )

    for field, value in changes.items():
        setattr(user, field, value)

    try:
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User update conflicts with an existing record",
        )

    return _user_response(db, user)


@router.delete(
    "/{user_id}",
    response_model=UserResponse,
)
def deactivate_user(
    user_id: int,
    current_user: User = Depends(
        require_permission("users.delete")
    ),
    db: Session = Depends(get_db),
):
    user = _user_or_404(db, user_id)

    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot deactivate your own account",
        )

    # Preserve records and assignments; deactivate the login.
    user.is_active = False

    db.commit()
    db.refresh(user)

    return _user_response(db, user)
