from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.api.permissions import require_permission
from app.core.database import get_db
from app.models.hospital import Hospital
from app.models.user import User
from app.schemas.hospital import (
    HospitalCreate,
    HospitalResponse,
    HospitalUpdate,
)


router = APIRouter(
    prefix="/hospitals",
    tags=["Hospitals"],
)


@router.get(
    "",
    response_model=list[HospitalResponse],
)
def list_hospitals(
    current_user: User = Depends(
        require_permission("hospital.read")
    ),
    db: Session = Depends(get_db),
):
    return db.scalars(
        select(Hospital).order_by(Hospital.id)
    ).all()


@router.get(
    "/{hospital_id}",
    response_model=HospitalResponse,
)
def get_hospital(
    hospital_id: int,
    current_user: User = Depends(
        require_permission("hospital.read")
    ),
    db: Session = Depends(get_db),
):
    hospital = db.get(Hospital, hospital_id)

    if hospital is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hospital not found",
        )

    return hospital


@router.post(
    "",
    response_model=HospitalResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_hospital(
    request: HospitalCreate,
    current_user: User = Depends(
        require_permission("hospital.manage")
    ),
    db: Session = Depends(get_db),
):
    existing = db.scalar(
        select(Hospital).where(
            (Hospital.name == request.name)
            | (Hospital.code == request.code)
        )
    )

    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Hospital name or code already exists",
        )

    hospital = Hospital(
        name=request.name,
        code=request.code,
        address=request.address,
    )

    db.add(hospital)
    db.commit()
    db.refresh(hospital)

    return hospital


@router.patch(
    "/{hospital_id}",
    response_model=HospitalResponse,
)
def update_hospital(
    hospital_id: int,
    request: HospitalUpdate,
    current_user: User = Depends(
        require_permission("hospital.manage")
    ),
    db: Session = Depends(get_db),
):
    hospital = db.get(Hospital, hospital_id)

    if hospital is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hospital not found",
        )

    update_data = request.model_dump(
        exclude_unset=True
    )

    if "name" in update_data or "code" in update_data:
        name = update_data.get(
            "name",
            hospital.name,
        )
        code = update_data.get(
            "code",
            hospital.code,
        )

        existing = db.scalar(
            select(Hospital).where(
                (
                    (Hospital.name == name)
                    | (Hospital.code == code)
                )
                & (Hospital.id != hospital_id)
            )
        )

        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Hospital name or code already exists",
            )

    for field, value in update_data.items():
        setattr(hospital, field, value)

    db.commit()
    db.refresh(hospital)

    return hospital