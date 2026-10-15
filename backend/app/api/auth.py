
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.api.permissions import require_permission
from app.core.database import get_db
from app.models.role import Role
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    TokenResponse,
    UserResponse,
)
from app.services.auth import authenticate_user


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


# =========================================================
# LOGIN
# Authenticates the user and returns an access token.
# =========================================================

@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate user",
    description="Validate user credentials and return an access token.",
)
def login(
    request: LoginRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:

    token = authenticate_user(
        db,
        request.username,
        request.password,
    )

    # Keep the login error generic to avoid exposing
    # whether a username exists or an account password is wrong.
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return TokenResponse(
        access_token=token,
    )


# =========================================================
# CURRENT AUTHENTICATED USER
# Returns account information and the user's role name.
# =========================================================

@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current user",
    description=(
        "Return the authenticated user's profile, "
        "role ID, and role name."
    ),
)
def get_me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserResponse:

    # Retrieve the role assigned to the authenticated user.
    role = db.get(
        Role,
        current_user.role_id,
    )

    # A user without a valid role indicates a database
    # or application configuration problem.
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User role configuration is invalid",
        )

    # Return the complete user profile.
    # Never include password_hash in the response.
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        full_name=current_user.full_name,
        role_id=current_user.role_id,
        is_active=current_user.is_active,
        role_name=role.name,
    )


# =========================================================
# PERMISSION TEST
# Confirms that the current user's role has users.read.
# =========================================================

@router.get(
    "/permission-test",
    response_model=dict[str, str],
    status_code=status.HTTP_200_OK,
    summary="Test user read permission",
    description=(
        "Return a success response when the authenticated "
        "user has the users.read permission."
    ),
)
def permission_test(
    current_user: User = Depends(
        require_permission("users.read")
    ),
) -> dict[str, str]:

    return {
        "status": "allowed",
        "user": current_user.username,
        "permission": "users.read",
    }
