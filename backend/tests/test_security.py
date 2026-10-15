
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import jwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 - register all application models
from app.api.dependencies import get_current_user
from app.api.permissions import require_permission
from app.core.database import Base
from app.core.jwt import create_access_token
from app.core.settings import settings
from app.models.permission import Permission
from app.models.role import Role
from app.models.role_permission import RolePermission
from app.models.user import User


@pytest.fixture
def security_env():
    """Create an isolated database for real JWT and permission tests."""

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    db = None

    try:
        Base.metadata.create_all(bind=engine)

        TestSession = sessionmaker(
            bind=engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )
        db = TestSession()

        role = Role(
            name="SECURITY_TEST_NURSE",
            description="Role for automated security tests",
            is_active=True,
        )

        permission = Permission(
            name="security_test:access",
            description="Permission for security tests",
            is_active=True,
        )

        db.add_all([role, permission])
        db.commit()
        db.refresh(role)
        db.refresh(permission)

        user = User(
            username="security_test_nurse",
            email="security_test_nurse@example.test",
            full_name="Security Test Nurse",
            role_id=role.id,
            password_hash="test-only-unused-hash",
            is_active=True,
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        role_permission = RolePermission(
            role_id=role.id,
            permission_id=permission.id,
        )

        db.add(role_permission)
        db.commit()

        yield SimpleNamespace(
            db=db,
            user=user,
            role=role,
            permission=permission,
        )

    finally:
        if db is not None:
            db.close()

        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def make_credentials(token: str):
    """Build the same Bearer credentials object FastAPI supplies."""
    return HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=token,
    )


def assert_http_error(call, expected_status: int, expected_detail: str):
    """Check an expected HTTPException without hiding other failures."""
    with pytest.raises(HTTPException) as exc_info:
        call()

    assert exc_info.value.status_code == expected_status
    assert exc_info.value.detail == expected_detail


def test_valid_jwt_returns_active_user(security_env):
    env = security_env

    token = create_access_token(str(env.user.id))

    result = get_current_user(
        credentials=make_credentials(token),
        db=env.db,
    )

    assert result.id == env.user.id
    assert result.username == "security_test_nurse"
    assert result.is_active is True


def test_invalid_jwt_is_rejected(security_env):
    env = security_env

    assert_http_error(
        lambda: get_current_user(
            credentials=make_credentials("invalid.token.value"),
            db=env.db,
        ),
        401,
        "Invalid or expired token",
    )


def test_expired_jwt_is_rejected(security_env):
    env = security_env

    expired_token = jwt.encode(
        {
            "sub": str(env.user.id),
            "exp": datetime.now(timezone.utc) - timedelta(minutes=5),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    assert_http_error(
        lambda: get_current_user(
            credentials=make_credentials(expired_token),
            db=env.db,
        ),
        401,
        "Invalid or expired token",
    )


def test_jwt_without_subject_is_rejected(security_env):
    env = security_env

    token_without_subject = jwt.encode(
        {
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    assert_http_error(
        lambda: get_current_user(
            credentials=make_credentials(token_without_subject),
            db=env.db,
        ),
        401,
        "Invalid token",
    )


def test_inactive_user_is_rejected_even_with_valid_jwt(security_env):
    env = security_env

    token = create_access_token(str(env.user.id))

    env.user.is_active = False
    env.db.commit()

    assert_http_error(
        lambda: get_current_user(
            credentials=make_credentials(token),
            db=env.db,
        ),
        401,
        "User is inactive or does not exist",
    )


def test_role_with_active_permission_is_authorized(security_env):
    env = security_env

    guard = require_permission("security_test:access")

    result = guard(
        current_user=env.user,
        db=env.db,
    )

    assert result.id == env.user.id


def test_role_without_required_permission_is_rejected(security_env):
    env = security_env

    guard = require_permission("security_test:missing")

    assert_http_error(
        lambda: guard(
            current_user=env.user,
            db=env.db,
        ),
        403,
        "Permission denied",
    )


def test_inactive_permission_is_rejected(security_env):
    env = security_env

    env.permission.is_active = False
    env.db.commit()

    guard = require_permission("security_test:access")

    assert_http_error(
        lambda: guard(
            current_user=env.user,
            db=env.db,
        ),
        403,
        "Permission denied",
    )
