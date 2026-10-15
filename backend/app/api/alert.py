from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.permissions import require_permission
from app.core.database import get_db
from app.models.alert import Alert
from app.models.alert_handoff import AlertHandoffHistory
from app.models.event import Event
from app.models.patient import Patient
from app.models.role import Role
from app.models.user import User
from app.schemas.alert import (
    AlertHandoffHistoryResponse,
    AlertResponse,
    AlertTransferRequest,
    EligibleNurseResponse,
)
from app.services.alert import (
    acknowledge_alert,
    dismiss_alert,
    get_alert_handoff_history,
    resolve_alert,
    transfer_alert,
)
from app.services.resource_access import (
    can_access_bed,
    can_access_camera,
)


router = APIRouter(
    prefix="/alerts",
    tags=["Alerts"],
)


def can_access_alert(
    db: Session,
    current_user: User,
    alert: Alert,
) -> bool:
    """Check access through the alert's linked camera or patient bed."""

    event = db.get(Event, alert.event_id)

    if event is None:
        return False

    if event.camera_id is not None and can_access_camera(
        db,
        current_user,
        event.camera_id,
    ):
        return True

    if event.patient_id is not None:
        patient = db.get(Patient, event.patient_id)

        if patient is not None and can_access_bed(
            db,
            current_user,
            patient.bed_id,
        ):
            return True

    return False


def is_active_nurse(
    db: Session,
    user: User,
) -> bool:
    """Return True only for an active user with an active NURSE role."""

    if not user.is_active:
        return False

    role = db.get(Role, user.role_id)

    return (
        role is not None
        and role.is_active
        and role.name.upper() == "NURSE"
    )


def get_alert_or_404(
    db: Session,
    alert_id: int,
) -> Alert:
    alert = db.get(Alert, alert_id)

    if alert is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found",
        )

    return alert


def require_alert_access(
    db: Session,
    current_user: User,
    alert: Alert,
) -> None:
    if not can_access_alert(db, current_user, alert):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Alert access denied",
        )


@router.get(
    "",
    response_model=list[AlertResponse],
)
def list_alerts(
    status_filter: str | None = None,
    current_user: User = Depends(
        require_permission("alerts.read")
    ),
    db: Session = Depends(get_db),
):
    """List alerts accessible to the current user."""

    query = select(Alert)

    if status_filter is not None:
        query = query.where(Alert.status == status_filter)

    alerts = db.scalars(
        query.order_by(Alert.created_at.desc())
    ).all()

    return [
        alert
        for alert in alerts
        if can_access_alert(db, current_user, alert)
    ]


@router.get(
    "/{alert_id}/eligible-nurses",
    response_model=list[EligibleNurseResponse],
)
def list_eligible_nurses(
    alert_id: int,
    current_user: User = Depends(
        require_permission("alerts.read")
    ),
    db: Session = Depends(get_db),
):
    """List active Nurses who can access this alert's resource."""

    alert = get_alert_or_404(db, alert_id)
    require_alert_access(db, current_user, alert)

    if not is_active_nurse(db, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only active Nurses can use the Nurse handoff workflow.",
        )

    nurses = db.scalars(
        select(User)
        .join(Role, User.role_id == Role.id)
        .where(
            User.is_active.is_(True),
            Role.name == "NURSE",
            Role.is_active.is_(True),
        )
        .order_by(User.full_name, User.username)
    ).all()

    eligible = []

    for nurse in nurses:
        if nurse.id == current_user.id:
            continue

        if can_access_alert(db, nurse, alert):
            eligible.append(
                EligibleNurseResponse(
                    user_id=nurse.id,
                    username=nurse.username,
                    full_name=nurse.full_name or nurse.username,
                )
            )

    return eligible


@router.get(
    "/{alert_id}/history",
    response_model=list[AlertHandoffHistoryResponse],
)
def get_alert_history(
    alert_id: int,
    current_user: User = Depends(
        require_permission("alerts.read")
    ),
    db: Session = Depends(get_db),
):
    """Return the alert's persistent assignment and transfer history."""

    alert = get_alert_or_404(db, alert_id)
    require_alert_access(db, current_user, alert)

    return get_alert_handoff_history(
        db,
        alert_id=alert.id,
    )


@router.post(
    "/{alert_id}/transfer",
    response_model=AlertResponse,
)
def transfer_alert_api(
    alert_id: int,
    payload: AlertTransferRequest,
    current_user: User = Depends(
        require_permission("alerts.acknowledge")
    ),
    db: Session = Depends(get_db),
):
    """
    Assign an unassigned alert or transfer an assigned alert to another Nurse.

    Transfer is separate from resolving an alert.
    """

    alert = get_alert_or_404(db, alert_id)
    require_alert_access(db, current_user, alert)

    if not is_active_nurse(db, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only active Nurses can assign or transfer alerts.",
        )

    if alert.assigned_to_user_id is not None:
        if alert.assigned_to_user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the currently assigned Nurse can transfer this alert.",
            )

    recipient = db.get(User, payload.to_user_id)

    if recipient is None or not is_active_nurse(db, recipient):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The recipient must be an active Nurse.",
        )

    if recipient.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="You cannot transfer an alert to yourself.",
        )

    if not can_access_alert(db, recipient, alert):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The receiving Nurse does not have access to this alert's camera or patient scope.",
        )

    try:
        updated_alert, _history = transfer_alert(
            db,
            alert=alert,
            to_user_id=recipient.id,
            transferred_by_user_id=current_user.id,
            reason=payload.reason,
        )
        return updated_alert

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )


@router.get(
    "/{alert_id}",
    response_model=AlertResponse,
)
def get_alert(
    alert_id: int,
    current_user: User = Depends(
        require_permission("alerts.read")
    ),
    db: Session = Depends(get_db),
):
    """Get one alert."""

    alert = get_alert_or_404(db, alert_id)
    require_alert_access(db, current_user, alert)

    return alert


@router.post(
    "/{alert_id}/acknowledge",
    response_model=AlertResponse,
)
def acknowledge_alert_api(
    alert_id: int,
    current_user: User = Depends(
        require_permission("alerts.acknowledge")
    ),
    db: Session = Depends(get_db),
):
    """Acknowledge an active alert."""

    alert = get_alert_or_404(db, alert_id)
    require_alert_access(db, current_user, alert)

    try:
        return acknowledge_alert(
            db,
            alert=alert,
            user_id=current_user.id,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )


@router.post(
    "/{alert_id}/resolve",
    response_model=AlertResponse,
)
def resolve_alert_api(
    alert_id: int,
    current_user: User = Depends(
        require_permission("alerts.acknowledge")
    ),
    db: Session = Depends(get_db),
):
    """Resolve an active or acknowledged alert."""

    alert = get_alert_or_404(db, alert_id)
    require_alert_access(db, current_user, alert)

    try:
        return resolve_alert(
            db,
            alert=alert,
            user_id=current_user.id,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )


@router.post(
    "/{alert_id}/dismiss",
    response_model=AlertResponse,
)
def dismiss_alert_api(
    alert_id: int,
    current_user: User = Depends(
        require_permission("alerts.acknowledge")
    ),
    db: Session = Depends(get_db),
):
    """Dismiss an active or acknowledged alert the user can access."""

    alert = get_alert_or_404(db, alert_id)
    require_alert_access(db, current_user, alert)

    try:
        return dismiss_alert(
            db,
            alert=alert,
            user_id=current_user.id,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
