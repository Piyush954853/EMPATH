from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.permissions import require_permission
from app.core.database import get_db
from app.models.bed import Bed
from app.models.room import Room
from app.models.user import User
from app.schemas.bed import BedCreate, BedResponse, BedUpdate


router = APIRouter(
    prefix="/beds",
    tags=["Beds"],
)


@router.get(
    "",
    response_model=list[BedResponse],
)
def list_beds(
    room_id: int | None = None,
    current_user: User = Depends(
        require_permission("hospital.read")
    ),
    db: Session = Depends(get_db),
):
    query = select(Bed)

    if room_id is not None:
        query = query.where(
            Bed.room_id == room_id
        )

    return db.scalars(
        query.order_by(Bed.id)
    ).all()


@router.get(
    "/{bed_id}",
    response_model=BedResponse,
)
def get_bed(
    bed_id: int,
    current_user: User = Depends(
        require_permission("hospital.read")
    ),
    db: Session = Depends(get_db),
):
    bed = db.get(Bed, bed_id)

    if bed is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bed not found",
        )

    return bed


@router.post(
    "",
    response_model=BedResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_bed(
    request: BedCreate,
    current_user: User = Depends(
        require_permission("hospital.manage")
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
        select(Bed).where(
            Bed.room_id == request.room_id,
            (
                (Bed.name == request.name)
                | (Bed.code == request.code)
            ),
        )
    )

    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bed name or code already exists in this room",
        )

    bed = Bed(
        room_id=request.room_id,
        name=request.name,
        code=request.code,
    )

    db.add(bed)
    db.commit()
    db.refresh(bed)

    return bed


@router.patch(
    "/{bed_id}",
    response_model=BedResponse,
)
def update_bed(
    bed_id: int,
    request: BedUpdate,
    current_user: User = Depends(
        require_permission("hospital.manage")
    ),
    db: Session = Depends(get_db),
):
    bed = db.get(
        Bed,
        bed_id,
    )

    if bed is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bed not found",
        )

    update_data = request.model_dump(
        exclude_unset=True
    )

    if "name" in update_data or "code" in update_data:
        name = update_data.get(
            "name",
            bed.name,
        )

        code = update_data.get(
            "code",
            bed.code,
        )

        existing = db.scalar(
            select(Bed).where(
                Bed.room_id == bed.room_id,
                (
                    (Bed.name == name)
                    | (Bed.code == code)
                ),
                Bed.id != bed_id,
            )
        )

        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Bed name or code already exists in this room",
            )

    for field, value in update_data.items():
        setattr(bed, field, value)

    db.commit()
    db.refresh(bed)

    return bed
