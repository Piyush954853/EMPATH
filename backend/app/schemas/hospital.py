from pydantic import BaseModel, ConfigDict


class HospitalCreate(BaseModel):
    name: str
    code: str
    address: str | None = None


class HospitalUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    address: str | None = None
    is_active: bool | None = None


class HospitalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str
    address: str | None
    is_active: bool