from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


NBA_STATUS_NEW = "new"
NBA_STATUS_ACCEPTED = "accepted"
NBA_STATUS_REJECTED = "rejected"
ACTION_STATUSES = {NBA_STATUS_ACCEPTED, NBA_STATUS_REJECTED}
NBA_STATUSES = {NBA_STATUS_NEW, NBA_STATUS_ACCEPTED, NBA_STATUS_REJECTED}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class NbaRecord:
    id: str
    nba_definition_id: str
    enterprise_number: str | None = None
    account_id: str | None = None
    contact_id: str | None = None
    active: bool = True
    status: str = NBA_STATUS_NEW
    priority: int = 0
    context: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)


@dataclass(slots=True)
class NbaEventLogRecord:
    id: str
    nba_id: str
    status: str
    context: dict[str, Any] = field(default_factory=dict)
    acted_by: str | None = None
    action_at: datetime = field(default_factory=utc_now)


@dataclass(slots=True)
class UserContext:
    username: str
    allowed_accounts: set[str] = field(default_factory=set)
    allowed_clients: set[str] = field(default_factory=set)
