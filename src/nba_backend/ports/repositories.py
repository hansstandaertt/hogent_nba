from __future__ import annotations

from typing import Protocol

from nba_backend.domain.models import NbaEventLogRecord, NbaRecord


class NbaRepository(Protocol):
    def list_nbas(
        self,
        *,
        account_id: str | None,
        enterprise_number: str | None,
        status: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[NbaRecord], int]: ...

    def get_nba(self, nba_id: str) -> NbaRecord | None: ...

    def upsert_from_calculation_event(
        self,
        *,
        event_id: str,
        nba_definition_id: str,
        enterprise_number: str | None,
        account_id: str | None,
        contact_id: str | None,
        context: dict,
    ) -> NbaRecord | None: ...

    def update_status(self, nba_id: str, status: str) -> NbaRecord: ...

    def deactivate_other_active_new_for_scope(
        self,
        *,
        keep_nba_id: str,
        nba_definition_id: str,
        enterprise_number: str | None,
        account_id: str | None,
        contact_id: str | None,
    ) -> int: ...

    def deactivate_nbas_by_ids(self, *, nba_ids: list[str]) -> int: ...


class NbaEventLogRepository(Protocol):
    def add(self, event: NbaEventLogRecord) -> NbaEventLogRecord: ...

    def list_for_nba(self, nba_id: str) -> list[NbaEventLogRecord]: ...

    def find_action_event(self, nba_id: str, status: str) -> NbaEventLogRecord | None: ...


class ProcessedEventRepository(Protocol):
    def is_processed(self, event_id: str) -> bool: ...

    def mark_processed(self, event_id: str) -> None: ...
