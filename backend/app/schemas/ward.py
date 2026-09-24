from pydantic import BaseModel, ConfigDict


class WardCreate(BaseModel):
    department_id: int
    name: str
    code: str


class WardUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    is_active: bool | None = None


class WardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    department_id: int
    name: str
    code: str
    is_active: bool