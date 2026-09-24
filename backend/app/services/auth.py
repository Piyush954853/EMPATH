from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.jwt import create_access_token
from app.core.security import verify_password
from app.models.user import User


def authenticate_user(
    db: Session,
    username: str,
    password: str,
) -> str | None:
    user = db.scalar(
        select(User).where(User.username == username)
    )

    if user is None:
        return None

    if not user.is_active:
        return None

    if not verify_password(password, user.password_hash):
        return None

    return create_access_token(str(user.id))