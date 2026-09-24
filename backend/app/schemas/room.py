from pydantic import BaseModel, ConfigDict


class RoomCreate(BaseModel):
    ward_id: int
    name: str
    code: str


class RoomUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    is_active: bool | None = None


class RoomResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ward_id: int
    name: str
    code: str
    is_active: bool
