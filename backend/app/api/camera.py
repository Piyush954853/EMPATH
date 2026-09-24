from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.permissions import require_permission
from app.core.database import get_db
from app.models.camera import Camera
from app.models.room import Room
from app.models.user import User
from app.schemas.camera import CameraCreate, CameraResponse, CameraUpdate
from app.services.resource_access import can_access_room


router = APIRouter(
    prefix="/cameras",
    tags=["Cameras"],
)


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
    camera = db.get(
        Camera,
        camera_id,
    )

    if camera is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Camera not found",
        )

    if not can_access_room(
        db,
        current_user,
        camera.room_id,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Camera access denied",
        )

    return camera


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
    room = db.get(
        Room,
        request.room_id,
    )

    if room is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Room not found",
        )

    existing = db.scalar(
        select(Camera).where(
            Camera.code == request.code
        )
    )

    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Camera code already exists",
        )

    camera = Camera(
        room_id=request.room_id,
        name=request.name,
        code=request.code,
        source_type=request.source_type,
        source_url=request.source_url,
    )

    db.add(camera)
    db.commit()
    db.refresh(camera)

    return camera


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
    camera = db.get(
        Camera,
        camera_id,
    )

    if camera is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Camera not found",
        )

    if not can_access_room(
        db,
        current_user,
        camera.room_id,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Camera access denied",
        )

    update_data = request.model_dump(
        exclude_unset=True
    )

    if "code" in update_data:
        existing = db.scalar(
            select(Camera).where(
                Camera.code == update_data["code"],
                Camera.id != camera_id,
            )
        )

        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Camera code already exists",
            )

    for field, value in update_data.items():
        setattr(camera, field, value)

    db.commit()
    db.refresh(camera)

    return camera