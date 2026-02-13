from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class NbaItemResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    nba_definition_id: str
    enterprise_number: str | None = None
    account_id: str | None = None
    contact_id: str | None = None
    active: bool
    status: Literal["new", "accepted", "rejected"]
    priority: int
    context: dict[str, Any] = Field(default_factory=dict)


class NbaListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[NbaItemResponse]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=200)
    offset: int = Field(ge=0)


class NbaActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["accepted", "rejected"]
    action_at: datetime | None = None
    comment: str | None = Field(default=None, max_length=1000)


class NbaActionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    nba_id: str
    status: Literal["accepted", "rejected"]
    acted_by: str
    action_at: datetime


class CalculationEventRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: UUID
    occurred_at: datetime
    source: str = Field(min_length=1)
    nba_definition_id: str = Field(min_length=1)
    enterprise_number: str | None = None
    account_id: str | None = None
    contact_id: str | None = None
    create_nba: bool = True
    deactivate_nba_ids: list[str] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_targets(self) -> "CalculationEventRequest":
        if not any([self.enterprise_number, self.account_id, self.contact_id]):
            raise ValueError(
                "At least one target identifier is required: enterprise_number, account_id or contact_id"
            )
        if self.occurred_at.tzinfo is None:
            self.occurred_at = self.occurred_at.replace(tzinfo=timezone.utc)
        return self


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
