from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.permissions import require_permission
from app.core.database import get_db
from app.models.department import Department
from app.models.user import User
from app.models.ward import Ward
from app.schemas.ward import (
    WardCreate,
    WardResponse,
    WardUpdate,
)
from app.services.resource_access import can_access_ward


router = APIRouter(
    prefix="/wards",
    tags=["Wards"],
)


@router.get(
    "",
    response_model=list[WardResponse],
)
def list_wards(
    department_id: int | None = None,
    current_user: User = Depends(
        require_permission("hospital.read")
    ),
    db: Session = Depends(get_db),
):
    query = select(Ward)

    if department_id is not None:
        query = query.where(
            Ward.department_id == department_id
        )

    wards = db.scalars(
        query.order_by(Ward.id)
    ).all()

    return [
        ward
        for ward in wards
        if can_access_ward(
            db,
            current_user,
            ward.id,
            audit=False,
        )
    ]


@router.get(
    "/{ward_id}",
    response_model=WardResponse,
)
def get_ward(
    ward_id: int,
    current_user: User = Depends(
        require_permission("hospital.read")
    ),
    db: Session = Depends(get_db),
):
    ward = db.get(
        Ward,
        ward_id,
    )

    if ward is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ward not found",
        )

    if not can_access_ward(
        db,
        current_user,
        ward_id,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Ward access denied",
        )

    return ward


@router.post(
    "",
    response_model=WardResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_ward(
    request: WardCreate,
    current_user: User = Depends(
        require_permission("hospital.manage")
    ),
    db: Session = Depends(get_db),
):
    department = db.get(
        Department,
        request.department_id,
    )

    if department is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found",
        )

    existing = db.scalar(
        select(Ward).where(
            Ward.department_id == request.department_id,
            (
                (Ward.name == request.name)
                | (Ward.code == request.code)
            ),
        )
    )

    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ward name or code already exists in this department",
        )

    ward = Ward(
        department_id=request.department_id,
        name=request.name,
        code=request.code,
    )

    db.add(ward)
    db.commit()
    db.refresh(ward)

    return ward


@router.patch(
    "/{ward_id}",
    response_model=WardResponse,
)
def update_ward(
    ward_id: int,
    request: WardUpdate,
    current_user: User = Depends(
        require_permission("hospital.manage")
    ),
    db: Session = Depends(get_db),
):
    ward = db.get(
        Ward,
        ward_id,
    )

    if ward is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ward not found",
        )

    if not can_access_ward(
        db,
        current_user,
        ward_id,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Ward access denied",
        )

    update_data = request.model_dump(
        exclude_unset=True
    )

    if "name" in update_data or "code" in update_data:
        name = update_data.get(
            "name",
            ward.name,
        )

        code = update_data.get(
            "code",
            ward.code,
        )

        existing = db.scalar(
            select(Ward).where(
                Ward.department_id == ward.department_id,
                (
                    (Ward.name == name)
                    | (Ward.code == code)
                ),
                Ward.id != ward_id,
            )
        )

        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ward name or code already exists in this department",
            )

    for field, value in update_data.items():
        setattr(ward, field, value)

    db.commit()
    db.refresh(ward)

    return ward