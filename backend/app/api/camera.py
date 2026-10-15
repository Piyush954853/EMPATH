
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.permissions import require_permission
from app.core.database import get_db
from app.models.camera import Camera
from app.models.room import Room
from app.models.user import User
from app.schemas.camera import (
    CameraCreate,
    CameraResponse,
    CameraUpdate,
)
from app.services.resource_access import (
    can_access_room,
    is_admin,
)


router = APIRouter(
    prefix="/cameras",
    tags=["Cameras"],
)


# =========================================================
# ADMIN-ONLY CAMERA CONFIGURATION
# =========================================================

def ensure_admin_camera_management(
    db: Session,
    current_user: User,
) -> None:
    """
    Only users whose actual database role is ADMIN can
    create or modify camera configuration.

    The existing cameras.manage permission is also retained
    on the create/update endpoints as an additional check.
    """
    if not is_admin(db, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Only administrators can manage "
                "camera configuration"
            ),
        )


# =========================================================
# COMMON HELPERS
# =========================================================

def get_camera_or_404(
    db: Session,
    camera_id: int,
) -> Camera:
    camera = db.get(Camera, camera_id)

    if camera is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Camera not found",
        )

    return camera


def get_room_or_404(
    db: Session,
    room_id: int,
) -> Room:
    room = db.get(Room, room_id)

    if room is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Room not found",
        )

    return room


def ensure_room_is_active(room: Room) -> None:
    if not room.is_active:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cannot assign a camera to an inactive room",
        )


def ensure_room_access(
    db: Session,
    current_user: User,
    room_id: int,
) -> None:
    if not can_access_room(
        db,
        current_user,
        room_id,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Target room access denied",
        )


def ensure_unique_camera_code(
    db: Session,
    code: str,
    exclude_camera_id: int | None = None,
) -> None:
    query = select(Camera.id).where(
        Camera.code == code
    )

    if exclude_camera_id is not None:
        query = query.where(
            Camera.id != exclude_camera_id
        )

    existing_id = db.scalar(query)

    if existing_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Camera code already exists",
        )


# =========================================================
# LIST CAMERAS
# Authorized users can see cameras within their room scope.
# =========================================================

@router.get(
    "",
    response_model=list[CameraResponse],
)
def list_cameras(
    room_id: int | None = None,
    current_user: User = Depends(
        require_permission("cameras.read")
    ),
    db: Session = Depends(get_db),
):
    query = select(Camera)

    if room_id is not None:
        query = query.where(
            Camera.room_id == room_id
        )

    cameras = db.scalars(
        query.order_by(Camera.id)
    ).all()

    return [
        camera
        for camera in cameras
        if can_access_room(
            db,
            current_user,
            camera.room_id,
            audit=False,
        )
    ]


# =========================================================
# GET ONE CAMERA
# =========================================================

@router.get(
    "/{camera_id}",
    response_model=CameraResponse,
)
def get_camera(
    camera_id: int,
    current_user: User = Depends(
        require_permission("cameras.read")
    ),
    db: Session = Depends(get_db),
):
    camera = get_camera_or_404(
        db,
        camera_id,
    )

    ensure_room_access(
        db,
        current_user,
        camera.room_id,
    )

    return camera


# =========================================================
# CREATE CAMERA
# ADMIN ONLY
# =========================================================

@router.post(
    "",
    response_model=CameraResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_camera(
    request: CameraCreate,
    current_user: User = Depends(
        require_permission("cameras.manage")
    ),
    db: Session = Depends(get_db),
):
    # Check the actual database role, not just the UI.
    ensure_admin_camera_management(
        db,
        current_user,
    )

    room = get_room_or_404(
        db,
        request.room_id,
    )

    ensure_room_is_active(room)

    ensure_room_access(
        db,
        current_user,
        room.id,
    )

    code = request.code.strip()

    ensure_unique_camera_code(
        db,
        code,
    )

    camera = Camera(
        room_id=room.id,
        name=request.name.strip(),
        code=code,
        source_type=request.source_type.strip(),
        source_url=request.source_url,
    )

    db.add(camera)

    try:
        db.commit()
        db.refresh(camera)

    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Camera could not be created. "
                "Verify its unique code and room."
            ),
        )

    return camera


# =========================================================
# UPDATE CAMERA
# ADMIN ONLY
#
# Supports updating:
# name, code, source type, source URL,
# assigned room and active status.
# =========================================================

@router.patch(
    "/{camera_id}",
    response_model=CameraResponse,
)
def update_camera(
    camera_id: int,
    request: CameraUpdate,
    current_user: User = Depends(
        require_permission("cameras.manage")
    ),
    db: Session = Depends(get_db),
):
    # Check the actual database role, not just the UI.
    ensure_admin_camera_management(
        db,
        current_user,
    )

    camera = get_camera_or_404(
        db,
        camera_id,
    )

    # Verify access to the existing camera first.
    ensure_room_access(
        db,
        current_user,
        camera.room_id,
    )

    update_data = request.model_dump(
        exclude_unset=True
    )

    if not update_data:
        return camera

    # Prevent null values in required camera fields.
    required_fields = (
        "room_id",
        "name",
        "code",
        "source_type",
        "is_active",
    )

    for field in required_fields:
        if (
            field in update_data
            and update_data[field] is None
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"{field} cannot be null",
            )

    # Validate destination room before reassignment.
    if "room_id" in update_data:
        target_room = get_room_or_404(
            db,
            update_data["room_id"],
        )

        ensure_room_is_active(target_room)

        ensure_room_access(
            db,
            current_user,
            target_room.id,
        )

    # Ensure camera codes remain unique.
    if "code" in update_data:
        update_data["code"] = (
            update_data["code"].strip()
        )

        ensure_unique_camera_code(
            db,
            update_data["code"],
            exclude_camera_id=camera.id,
        )

    if "name" in update_data:
        update_data["name"] = (
            update_data["name"].strip()
        )

    if "source_type" in update_data:
        update_data["source_type"] = (
            update_data["source_type"].strip()
        )

    for field, value in update_data.items():
        setattr(
            camera,
            field,
            value,
        )

    try:
        db.commit()
        db.refresh(camera)

    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Camera update conflicts with "
                "an existing record"
            ),
        )

    return camera
