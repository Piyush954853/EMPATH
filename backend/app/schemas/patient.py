from pydantic import BaseModel, ConfigDict


class PatientCreate(BaseModel):
    bed_id: int
    patient_code: str
    name: str


class PatientUpdate(BaseModel):
    patient_code: str | None = None
    name: str | None = None
    is_active: bool | None = None


class PatientResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    bed_id: int
    patient_code: str
    name: str
    is_active: bool
