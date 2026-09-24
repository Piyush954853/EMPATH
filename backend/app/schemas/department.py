from pydantic import BaseModel, ConfigDict


class DepartmentCreate(BaseModel):
    hospital_id: int
    name: str
    code: str


class DepartmentUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    is_active: bool | None = None


class DepartmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    hospital_id: int
    name: str
    code: str
    is_active: bool