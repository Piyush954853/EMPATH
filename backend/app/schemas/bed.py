from pydantic import BaseModel, ConfigDict


class BedCreate(BaseModel):
    room_id: int
    name: str
    code: str


class BedUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    is_occupied: bool | None = None
    is_active: bool | None = None


class BedResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    room_id: int
    name: str
    code: str
    is_occupied: bool
    is_active: bool
