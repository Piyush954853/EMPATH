
import re

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PositiveInt,
    field_validator,
)


def normalize_email(value: str) -> str:
    """
    Normalize and validate an email-style address.

    Deliberately supports internal/demo domains such as empath.local.
    This checks address syntax, not whether the mailbox exists.
    """
    value = value.strip().lower()

    local_part, separator, domain = value.partition("@")
    domain_labels = domain.split(".")

    valid_local_part = re.fullmatch(
        r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]+",
        local_part,
    )

    valid_domain = (
        len(domain_labels) >= 2
        and all(
            re.fullmatch(
                r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?",
                label,
            )
            is not None
            for label in domain_labels
        )
    )

    if (
        not separator
        or value.count("@") != 1
        or not valid_local_part
        or local_part.startswith(".")
        or local_part.endswith(".")
        or ".." in local_part
        or not valid_domain
        or len(value) > 200
    ):
        raise ValueError("Enter a valid email-style address")

    return value


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=100)
    email: str = Field(min_length=5, max_length=200)
    full_name: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=10, max_length=128)
    role_id: PositiveInt

    @field_validator("username", "full_name", mode="before")
    @classmethod
    def strip_required_text(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()

            if not value:
                raise ValueError("This field cannot be empty")

        return value

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalize_email(value)


class UserUpdate(BaseModel):
    full_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
    )
    email: str | None = Field(
        default=None,
        min_length=5,
        max_length=200,
    )
    password: str | None = Field(
        default=None,
        min_length=10,
        max_length=128,
    )
    role_id: PositiveInt | None = None
    is_active: bool | None = None

    @field_validator("full_name", mode="before")
    @classmethod
    def strip_full_name(cls, value: object) -> object:
        if value is None:
            return None

        if isinstance(value, str):
            value = value.strip()

            if not value:
                raise ValueError("Full name cannot be empty")

        return value

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        if value is None:
            return None

        return normalize_email(value)


class UserResponse(BaseModel):
    """
    Public user response.

    Email is intentionally a plain string because legacy/demo accounts
    may use internal domains such as empath.local.
    Never include password hashes or raw passwords in this response.
    """
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    full_name: str
    role_id: int
    is_active: bool
    role_name: str | None = None


class RoleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    is_active: bool


class UserAssignmentsUpdate(BaseModel):
    department_ids: list[PositiveInt] = Field(default_factory=list)
    ward_ids: list[PositiveInt] = Field(default_factory=list)
    room_ids: list[PositiveInt] = Field(default_factory=list)
    bed_ids: list[PositiveInt] = Field(default_factory=list)


class UserAssignmentsResponse(BaseModel):
    user_id: int
    department_ids: list[int]
    ward_ids: list[int]
    room_ids: list[int]
    bed_ids: list[int]
