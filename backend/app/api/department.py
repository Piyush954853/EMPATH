from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.permissions import require_permission
from app.core.database import get_db
from app.models.department import Department
from app.models.hospital import Hospital
from app.models.user import User
from app.schemas.department import (
    DepartmentCreate,
    DepartmentResponse,
    DepartmentUpdate,
)
from app.services.resource_access import can_access_department


router = APIRouter(
    prefix="/departments",
    tags=["Departments"],
)


@router.get(
    "",
    response_model=list[DepartmentResponse],
)
def list_departments(
    hospital_id: int | None = None,
    current_user: User = Depends(
        require_permission("hospital.read")
    ),
    db: Session = Depends(get_db),
):
    query = select(Department)

    if hospital_id is not None:
        query = query.where(
            Department.hospital_id == hospital_id
        )

    departments = db.scalars(
        query.order_by(Department.id)
    ).all()

    return [
        department
        for department in departments
        if can_access_department(
            db,
            current_user,
            department.id,
            audit=False,
        )
    ]


@router.get(
    "/{department_id}",
    response_model=DepartmentResponse,
)
def get_department(
    department_id: int,
    current_user: User = Depends(
        require_permission("hospital.read")
    ),
    db: Session = Depends(get_db),
):
    department = db.get(
        Department,
        department_id,
    )

    if department is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found",
        )

    if not can_access_department(
        db,
        current_user,
        department_id,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Department access denied",
        )

    return department


@router.post(
    "",
    response_model=DepartmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_department(
    request: DepartmentCreate,
    current_user: User = Depends(
        require_permission("hospital.manage")
    ),
    db: Session = Depends(get_db),
):
    hospital = db.get(
        Hospital,
        request.hospital_id,
    )

    if hospital is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hospital not found",
        )

    existing = db.scalar(
        select(Department).where(
            Department.hospital_id == request.hospital_id,
            (
                (Department.name == request.name)
                | (Department.code == request.code)
            ),
        )
    )

    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Department name or code already exists in this hospital",
        )

    department = Department(
        hospital_id=request.hospital_id,
        name=request.name,
        code=request.code,
    )

    db.add(department)
    db.commit()
    db.refresh(department)

    return department


@router.patch(
    "/{department_id}",
    response_model=DepartmentResponse,
)
def update_department(
    department_id: int,
    request: DepartmentUpdate,
    current_user: User = Depends(
        require_permission("hospital.manage")
    ),
    db: Session = Depends(get_db),
):
    department = db.get(
        Department,
        department_id,
    )

    if department is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found",
        )

    if not can_access_department(
        db,
        current_user,
        department_id,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Department access denied",
        )

    update_data = request.model_dump(
        exclude_unset=True
    )

    if "name" in update_data or "code" in update_data:
        name = update_data.get(
            "name",
            department.name,
        )

        code = update_data.get(
            "code",
            department.code,
        )

        existing = db.scalar(
            select(Department).where(
                Department.hospital_id
                == department.hospital_id,
                (
                    (Department.name == name)
                    | (Department.code == code)
                ),
                Department.id != department_id,
            )
        )

        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Department name or code already exists in this hospital",
            )

    for field, value in update_data.items():
        setattr(department, field, value)

    db.commit()
    db.refresh(department)

    return department