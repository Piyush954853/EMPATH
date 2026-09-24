from sqlalchemy.orm import Session

from app.services.audit import log_action


def record_authorization_decision(
    db: Session,
    *,
    user_id: int | None,
    action: str,
    resource_type: str,
    resource_id: int | str,
    allowed: bool,
    reason: str,
    ip_address: str | None = None,
):
    return log_action(
        db,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id),
        result="ALLOWED" if allowed else "DENIED",
        reason=reason,
        ip_address=ip_address,
    )