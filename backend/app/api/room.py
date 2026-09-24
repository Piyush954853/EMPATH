from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.permissions import require_permission
from app.core.database import get_db
from app.models.room import Room
from app.models.user import User
from app.models.ward import Ward
from app.schemas.room import RoomCreate, RoomResponse, RoomUpdate


router = APIRouter(
    prefix="/rooms",
    tags=["Rooms"],
)


@router.get(
    "",
    response_model=list[RoomResponse],
)
def list_rooms(
    ward_id: int | None = None,
    current_user: User = Depends(
        require_permission("hospital.read")
    ),
    db: Session = Depends(get_db),
):
    query = select(Room)

    if ward_id is not None:
        query = query.where(
            Room.ward_id == ward_id
        )

    return db.scalars(
        query.order_by(Room.id)
    ).all()


@router.get(
    "/{room_id}",
    response_model=RoomResponse,
)
def get_room(
    room_id: int,
    current_user: User = Depends(
        require_permission("hospital.read")
    ),
    db: Session = Depends(get_db),
):
    room = db.get(Room, room_id)

    if room is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Room not found",
        )

    return room


@router.post(
    "",
    response_model=RoomResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_room(
    request: RoomCreate,
    current_user: User = Depends(
        require_permission("hospital.manage")
    ),
    db: Session = Depends(get_db),
):
    ward = db.get(
        Ward,
        request.ward_id,
    )

    if ward is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ward not found",
        )

    existing = db.scalar(
        select(Room).where(
            Room.ward_id == request.ward_id,
            (
                (Room.name == request.name)
                | (Room.code == request.code)
            ),
        )
    )

    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Room name or code already exists in this ward",
        )

    room = Room(
        ward_id=request.ward_id,
        name=request.name,
        code=request.code,
    )

    db.add(room)
    db.commit()
    db.refresh(room)

    return room


@router.patch(
    "/{room_id}",
    response_model=RoomResponse,
)
def update_room(
    room_id: int,
    request: RoomUpdate,
    current_user: User = Depends(
        require_permission("hospital.manage")
    ),
    db: Session = Depends(get_db),
):
    room = db.get(
        Room,
        room_id,
    )

    if room is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Room not found",
        )

    update_data = request.model_dump(
        exclude_unset=True
    )

    if "name" in update_data or "code" in update_data:
        name = update_data.get(
            "name",
            room.name,
        )

        code = update_data.get(
            "code",
            room.code,
        )

        existing = db.scalar(
            select(Room).where(
                Room.ward_id == room.ward_id,
                (
                    (Room.name == name)
                    | (Room.code == code)
                ),
                Room.id != room_id,
            )
        )

        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Room name or code already exists in this ward",
            )

    for field, value in update_data.items():
        setattr(room, field, value)

    db.commit()
    db.refresh(room)

    return room
