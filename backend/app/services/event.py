import json

from sqlalchemy.orm import Session

from app.models.event import Event


def create_event(
    db: Session,
    *,
    event_type: str,
    source_type: str,
    severity: str,
    camera_id: int | None = None,
    patient_id: int | None = None,
    confidence: float | None = None,
    description: str | None = None,
    metadata: dict | None = None,
) -> Event:
    event = Event(
        camera_id=camera_id,
        patient_id=patient_id,
        event_type=event_type,
        source_type=source_type,
        severity=severity,
        confidence=confidence,
        description=description,
        metadata_json=json.dumps(metadata) if metadata is not None else None,
    )

    db.add(event)
    db.commit()
    db.refresh(event)

    return event