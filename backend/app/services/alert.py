from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.alert import Alert
from app.models.event import Event


ACTIVE_STATUS = "active"
ACKNOWLEDGED_STATUS = "acknowledged"
RESOLVED_STATUS = "resolved"
DISMISSED_STATUS = "dismissed"


def create_alert(
    db: Session,
    *,
    event: Event,
    priority: str,
    title: str,
    message: str | None = None,
) -> Alert:
    alert = Alert(
        event_id=event.id,
        priority=priority,
        status=ACTIVE_STATUS,
        title=title,
        message=message,
    )

    db.add(alert)
    db.commit()
    db.refresh(alert)

    return alert


def acknowledge_alert(
    db: Session,
    *,
    alert: Alert,
    user_id: int,
) -> Alert:
    if alert.status != ACTIVE_STATUS:
        raise ValueError(
            f"Cannot acknowledge alert with status '{alert.status}'"
        )

    alert.status = ACKNOWLEDGED_STATUS
    alert.acknowledged_by = user_id
    alert.acknowledged_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(alert)

    return alert


def resolve_alert(
    db: Session,
    *,
    alert: Alert,
    user_id: int,
) -> Alert:
    if alert.status not in {
        ACTIVE_STATUS,
        ACKNOWLEDGED_STATUS,
    }:
        raise ValueError(
            f"Cannot resolve alert with status '{alert.status}'"
        )

    alert.status = RESOLVED_STATUS
    alert.resolved_by = user_id
    alert.resolved_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(alert)

    return alert


def dismiss_alert(
    db: Session,
    *,
    alert: Alert,
) -> Alert:
    if alert.status not in {
        ACTIVE_STATUS,
        ACKNOWLEDGED_STATUS,
    }:
        raise ValueError(
            f"Cannot dismiss alert with status '{alert.status}'"
        )

    alert.status = DISMISSED_STATUS

    db.commit()
    db.refresh(alert)

    return alert