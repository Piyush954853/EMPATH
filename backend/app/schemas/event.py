from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EventCreate(BaseModel):
    event_type: str = Field(min_length=1, max_length=100)
    source_type: str = Field(min_length=1, max_length=50)
    severity: str = Field(min_length=1, max_length=50)

    camera_id: int | None = None
    patient_id: int | None = None

    confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )

    description: str | None = None
    metadata: dict | None = None


class EventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    camera_id: int | None
    patient_id: int | None
    event_type: str
    source_type: str
    severity: str
    status: str
    confidence: float | None
    description: str | None
    metadata_json: str | None
    detected_at: datetime