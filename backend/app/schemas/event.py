import json
from datetime import datetime
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
)


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
    metadata: dict[str, Any] | None = None


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

    # ADDED: Expose metadata as a parsed JSON dictionary while
    # preserving metadata_json for existing API consumers.
    @computed_field(return_type=dict[str, Any] | None)
    @property
    def metadata(self) -> dict[str, Any] | None:
        """
        Return event metadata as a dictionary.

        Invalid, empty, or non-object JSON returns None rather
        than preventing an otherwise valid event response.
        """

        if not self.metadata_json:
            return None

        try:
            parsed_metadata = json.loads(self.metadata_json)
        except (json.JSONDecodeError, TypeError):
            return None

        if isinstance(parsed_metadata, dict):
            return parsed_metadata

        return None