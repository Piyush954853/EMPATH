from pydantic import BaseModel, ConfigDict


class CameraCreate(BaseModel):
    room_id: int
    name: str
    code: str
    source_type: str
    source_url: str | None = None


class CameraUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    source_type: str | None = None
    source_url: str | None = None
    is_active: bool | None = None


class CameraResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    room_id: int
    name: str
    code: str
    source_type: str
    source_url: str | None
    is_active: bool