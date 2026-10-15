from datetime import datetime, timezone
import logging

from sqlalchemy.orm import Session

from app.models.alert import Alert
from app.models.alert_handoff import AlertHandoffHistory
from app.services.alert_summary import generate_alert_summary


logger = logging.getLogger(__name__)

ACTIVE_STATUS = "active"
ACKNOWLEDGED_STATUS = "acknowledged"
RESOLVED_STATUS = "resolved"
DISMISSED_STATUS = "dismissed"


def create_alert(
    db: Session,
    *,
    event,
    priority: str,
    title: str,
    message: str | None = None,
) -> Alert:
    """
    Create and persist an alert before generating its summary.

    Alert creation is committed first so that a slow or failing local
    AI model cannot prevent the original alert from being saved.
    """

    alert = Alert(
        event_id=event.id,
        priority=priority,
        status=ACTIVE_STATUS,
        title=title,
        message=message,
        summary=None,
    )

    db.add(alert)
    db.commit()
    db.refresh(alert)

    alert_id = alert.id

    try:
        summary = generate_alert_summary(
            event,
            title=title,
            message=message,
            priority=priority,
        )

        alert.summary = summary
        db.commit()
        db.refresh(alert)

    except Exception:
        # The alert was already committed, so a summary failure
        # must not undo its creation.
        logger.exception(
            "Could not save summary for alert %s.",
            alert_id,
        )
        db.rollback()

        alert = db.get(Alert, alert_id)

        if alert is None:
            raise RuntimeError(
                f"Alert {alert_id} could not be retrieved "
                "after summary generation failed."
            )

    return alert


def acknowledge_alert(
    db: Session,
    *,
    alert: Alert,
    user_id: int,
) -> Alert:
    if alert.status != ACTIVE_STATUS:
        raise ValueError(
            f"Only active alerts can be acknowledged; "
            f"current status is '{alert.status}'."
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
            f"Only active or acknowledged alerts can be resolved; "
            f"current status is '{alert.status}'."
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
    user_id: int,
) -> Alert:
    """Dismiss an actionable alert and record who dismissed it and when."""

    if alert.status not in {
        ACTIVE_STATUS,
        ACKNOWLEDGED_STATUS,
    }:
        raise ValueError(
            f"Only active or acknowledged alerts can be dismissed; "
            f"current status is '{alert.status}'."
        )

    alert.status = DISMISSED_STATUS
    alert.dismissed_by = user_id
    alert.dismissed_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(alert)
    return alert


def transfer_alert(
    db: Session,
    *,
    alert: Alert,
    to_user_id: int,
    transferred_by_user_id: int,
    reason: str,
) -> tuple[Alert, AlertHandoffHistory]:
    """
    Assign an unassigned alert or transfer it to another Nurse.

    The API must validate user roles, permissions, and resource access.
    Assignment and its history record are committed together.
    """

    if alert.status not in {
        ACTIVE_STATUS,
        ACKNOWLEDGED_STATUS,
    }:
        raise ValueError(
            "Only active or acknowledged alerts can be assigned "
            "or transferred."
        )

    if alert.assigned_to_user_id == to_user_id:
        raise ValueError(
            "The alert is already assigned to this nurse."
        )

    clean_reason = reason.strip()

    if len(clean_reason) < 3:
        raise ValueError(
            "Please provide a transfer reason of at least "
            "3 characters."
        )

    previous_assignee_id = alert.assigned_to_user_id
    action = (
        "assigned"
        if previous_assignee_id is None
        else "transferred"
    )

    history = AlertHandoffHistory(
        alert_id=alert.id,
        from_user_id=previous_assignee_id,
        to_user_id=to_user_id,
        transferred_by_user_id=transferred_by_user_id,
        action=action,
        reason=clean_reason,
        created_at=datetime.now(timezone.utc),
    )

    try:
        alert.assigned_to_user_id = to_user_id

        # The receiving Nurse must acknowledge the alert themselves.
        alert.status = ACTIVE_STATUS
        alert.acknowledged_by = None
        alert.acknowledged_at = None

        db.add(history)
        db.commit()

        db.refresh(alert)
        db.refresh(history)

        return alert, history

    except Exception:
        db.rollback()
        raise


def get_alert_handoff_history(
    db: Session,
    *,
    alert_id: int,
) -> list[AlertHandoffHistory]:
    """Return the newest handoff-history entries first."""

    return (
        db.query(AlertHandoffHistory)
        .filter(
            AlertHandoffHistory.alert_id == alert_id
        )
        .order_by(
            AlertHandoffHistory.created_at.desc(),
            AlertHandoffHistory.id.desc(),
        )
        .all()
    )
