from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.permissions import require_permission
from app.core.database import get_db
from app.models.event import Event
from app.models.user import User
from app.schemas.event import EventCreate, EventResponse
from app.services.event import create_event
from app.services.resource_access import can_access_camera, can_access_bed


router = APIRouter(
    prefix="/events",
    tags=["Events"],
)


def can_access_event(
    db: Session,
    current_user: User,
    event: Event,
) -> bool:
    if event.camera_id is not None:
        if can_access_camera(
            db,
            current_user,
            event.camera_id,
            audit=False,
        ):
            return True

    if event.patient_id is not None:
        from app.models.patient import Patient

        patient = db.get(
            Patient,
            event.patient_id,
        )

        if patient is not None:
            if can_access_bed(
                db,
                current_user,
                patient.bed_id,
                audit=False,
            ):
                return True

    return False


@router.get(
    "",
    response_model=list[EventResponse],
)
def list_events(
    camera_id: int | None = None,
    patient_id: int | None = None,
    current_user: User = Depends(
        require_permission("events.read")
    ),
    db: Session = Depends(get_db),
):
    query = select(Event)

    if camera_id is not None:
        query = query.where(
            Event.camera_id == camera_id
        )

    if patient_id is not None:
        query = query.where(
            Event.patient_id == patient_id
        )

    events = db.scalars(
        query.order_by(Event.id)
    ).all()

    return [
        event
        for event in events
        if can_access_event(
            db,
            current_user,
            event,
        )
    ]


@router.get(
    "/{event_id}",
    response_model=EventResponse,
)
def get_event(
    event_id: int,
    current_user: User = Depends(
        require_permission("events.read")
    ),
    db: Session = Depends(get_db),
):
    event = db.get(
        Event,
        event_id,
    )

    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )

    if not can_access_event(
        db,
        current_user,
        event,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Event access denied",
        )

    return event


@router.post(
    "",
    response_model=EventResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_event_api(
    request: EventCreate,
    current_user: User = Depends(
        require_permission("events.create")
    ),
    db: Session = Depends(get_db),
):
    if request.camera_id is not None:
        if not can_access_camera(
            db,
            current_user,
            request.camera_id,
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Camera access denied",
            )

    if request.patient_id is not None:
        from app.models.patient import Patient

        patient = db.get(
            Patient,
            request.patient_id,
        )

        if patient is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient not found",
            )

        if not can_access_bed(
            db,
            current_user,
            patient.bed_id,
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Patient access denied",
            )

    return create_event(
        db,
        event_type=request.event_type,
        source_type=request.source_type,
        severity=request.severity,
        camera_id=request.camera_id,
        patient_id=request.patient_id,
        confidence=request.confidence,
        description=request.description,
        metadata=request.metadata,
    )