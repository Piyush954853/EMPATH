
from pydantic import BaseModel, ConfigDict, Field, field_validator


class CameraCreate(BaseModel):
    room_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=100)
    code: str = Field(min_length=1, max_length=50)
    source_type: str = Field(min_length=1, max_length=50)
    source_url: str | None = Field(default=None, max_length=500)

    @field_validator("name", "code", "source_type")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("This field cannot be empty")

        return value

    @field_validator("source_url")
    @classmethod
    def normalize_source_url(cls, value: str | None) -> str | None:
        if value is None:
            return None

        value = value.strip()
        return value or None


class CameraUpdate(BaseModel):
    room_id: int | None = Field(default=None, gt=0)
    name: str | None = Field(default=None, min_length=1, max_length=100)
    code: str | None = Field(default=None, min_length=1, max_length=50)
    source_type: str | None = Field(
        default=None,
        min_length=1,
        max_length=50,
    )
    source_url: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None

    @field_validator("name", "code", "source_type")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None

        value = value.strip()

        if not value:
            raise ValueError("This field cannot be empty")

        return value

    @field_validator("source_url")
    @classmethod
    def normalize_optional_source_url(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        value = value.strip()
        return value or None


class CameraResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    room_id: int
    name: str
    code: str
    source_type: str
    source_url: str | None
    is_active: bool
