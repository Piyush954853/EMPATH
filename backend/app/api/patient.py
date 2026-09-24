from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.permissions import require_permission
from app.core.database import get_db
from app.models.patient import Patient
from app.models.bed import Bed
from app.models.user import User
from app.schemas.patient import PatientCreate, PatientResponse, PatientUpdate


router = APIRouter(
    prefix="/patients",
    tags=["Patients"],
)


@router.get(
    "",
    response_model=list[PatientResponse],
)
def list_patients(
    bed_id: int | None = None,
    current_user: User = Depends(
        require_permission("patients.read")
    ),
    db: Session = Depends(get_db),
):
    query = select(Patient)

    if bed_id is not None:
        query = query.where(
            Patient.bed_id == bed_id
        )

    return db.scalars(
        query.order_by(Patient.id)
    ).all()


@router.get(
    "/{patient_id}",
    response_model=PatientResponse,
)
def get_patient(
    patient_id: int,
    current_user: User = Depends(
        require_permission("patients.read")
    ),
    db: Session = Depends(get_db),
):
    patient = db.get(Patient, patient_id)

    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )

    return patient


@router.post(
    "",
    response_model=PatientResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_patient(
    request: PatientCreate,
    current_user: User = Depends(
        require_permission("patients.manage")
    ),
    db: Session = Depends(get_db),
):
    bed = db.get(
        Bed,
        request.bed_id,
    )

    if bed is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bed not found",
        )

    existing = db.scalar(
        select(Patient).where(
            Patient.patient_code == request.patient_code
        )
    )

    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Patient code already exists",
        )

    patient = Patient(
        bed_id=request.bed_id,
        patient_code=request.patient_code,
        name=request.name,
    )

    db.add(patient)
    db.commit()
    db.refresh(patient)

    return patient


@router.patch(
    "/{patient_id}",
    response_model=PatientResponse,
)
def update_patient(
    patient_id: int,
    request: PatientUpdate,
    current_user: User = Depends(
        require_permission("patients.manage")
    ),
    db: Session = Depends(get_db),
):
    patient = db.get(
        Patient,
        patient_id,
    )

    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )

    update_data = request.model_dump(
        exclude_unset=True
    )

    if "patient_code" in update_data:
        existing = db.scalar(
            select(Patient).where(
                Patient.patient_code == update_data["patient_code"],
                Patient.id != patient_id,
            )
        )

        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Patient code already exists",
            )

    for field, value in update_data.items():
        setattr(patient, field, value)

    db.commit()
    db.refresh(patient)

    return patient
