from __future__ import annotations

from dataclasses import replace
from typing import Iterable
from uuid import uuid4

from nba_backend.domain.models import NBA_STATUS_NEW, NbaEventLogRecord, NbaRecord, utc_now


class InMemoryNbaRepository:
    def __init__(self) -> None:
        self._nbas: dict[str, NbaRecord] = {}
        self._event_to_nba_id: dict[str, str] = {}

    def list_nbas(
        self,
        *,
        account_id: str | None,
        enterprise_number: str | None,
        status: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[NbaRecord], int]:
        filtered = [
            nba
            for nba in self._nbas.values()
            if nba.active
            and _match_identifiers(nba, account_id, enterprise_number)
            and (status is None or nba.status == status)
        ]
        filtered.sort(key=lambda n: n.created_at, reverse=True)
        total = len(filtered)
        return filtered[offset : offset + limit], total

    def get_nba(self, nba_id: str) -> NbaRecord | None:
        return self._nbas.get(nba_id)

    def upsert_from_calculation_event(
        self,
        *,
        event_id: str,
        nba_definition_id: str,
        enterprise_number: str | None,
        account_id: str | None,
        contact_id: str | None,
        context: dict,
    ) -> NbaRecord | None:
        if event_id in self._event_to_nba_id:
            nba_id = self._event_to_nba_id[event_id]
            return self._nbas.get(nba_id)

        nba = NbaRecord(
            id=f"nba_{uuid4().hex[:10]}",
            nba_definition_id=nba_definition_id,
            enterprise_number=enterprise_number,
            account_id=account_id,
            contact_id=contact_id,
            context=dict(context),
        )
        self._nbas[nba.id] = nba
        self._event_to_nba_id[event_id] = nba.id
        return nba

    def update_status(self, nba_id: str, status: str) -> NbaRecord:
        existing = self._nbas[nba_id]
        updated = replace(existing, status=status, updated_at=utc_now())
        self._nbas[nba_id] = updated
        return updated

    def deactivate_other_active_new_for_scope(
        self,
        *,
        keep_nba_id: str,
        nba_definition_id: str,
        enterprise_number: str | None,
        account_id: str | None,
        contact_id: str | None,
    ) -> int:
        deactivated = 0
        for nba_id, existing in list(self._nbas.items()):
            if nba_id == keep_nba_id:
                continue
            if not existing.active or existing.status != NBA_STATUS_NEW:
                continue
            if existing.nba_definition_id != nba_definition_id:
                continue
            if existing.enterprise_number != enterprise_number:
                continue
            if existing.account_id != account_id:
                continue
            if existing.contact_id != contact_id:
                continue

            self._nbas[nba_id] = replace(existing, active=False, updated_at=utc_now())
            deactivated += 1
        return deactivated

    def deactivate_nbas_by_ids(self, *, nba_ids: list[str]) -> int:
        deactivated = 0
        for nba_id in dict.fromkeys(nba_ids):
            existing = self._nbas.get(nba_id)
            if existing is None or not existing.active:
                continue
            self._nbas[nba_id] = replace(existing, active=False, updated_at=utc_now())
            deactivated += 1
        return deactivated


class InMemoryNbaEventLogRepository:
    def __init__(self) -> None:
        self._events: list[NbaEventLogRecord] = []

    def add(self, event: NbaEventLogRecord) -> NbaEventLogRecord:
        self._events.append(event)
        return event

    def list_for_nba(self, nba_id: str) -> list[NbaEventLogRecord]:
        return [event for event in self._events if event.nba_id == nba_id]

    def find_action_event(self, nba_id: str, status: str) -> NbaEventLogRecord | None:
        for event in self._events:
            if event.nba_id == nba_id and event.status == status and event.acted_by:
                return event
        return None


class InMemoryProcessedEventRepository:
    def __init__(self) -> None:
        self._processed: set[str] = set()

    def is_processed(self, event_id: str) -> bool:
        return event_id in self._processed

    def mark_processed(self, event_id: str) -> None:
        self._processed.add(event_id)


def _match_identifiers(
    nba: NbaRecord,
    account_id: str | None,
    enterprise_number: str | None,
) -> bool:
    checks: Iterable[bool] = (
        account_id is None or nba.account_id == account_id,
        enterprise_number is None or nba.enterprise_number == enterprise_number,
    )
    return all(checks)
