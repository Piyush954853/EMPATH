
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_id: int
    priority: str
    status: str
    title: str
    message: str | None
    summary: str | None
    acknowledged_by: int | None
    acknowledged_at: datetime | None
    resolved_by: int | None
    resolved_at: datetime | None
    dismissed_by: int | None
    dismissed_at: datetime | None
    created_at: datetime
    assigned_to_user_id: int | None


class AlertTransferRequest(BaseModel):
    to_user_id: int = Field(gt=0)
    reason: str = Field(min_length=3, max_length=1000)


class AlertHandoffHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    alert_id: int
    from_user_id: int | None
    to_user_id: int
    transferred_by_user_id: int
    action: str
    reason: str
    created_at: datetime


class EligibleNurseResponse(BaseModel):
    user_id: int
    username: str
    full_name: str
