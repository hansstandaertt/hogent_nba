from __future__ import annotations

from datetime import timezone
import logging
from uuid import uuid4

from fastapi import HTTPException, status

from nba_backend.domain.models import (
    ACTION_STATUSES,
    NBA_STATUS_ACCEPTED,
    NBA_STATUS_NEW,
    NBA_STATUS_REJECTED,
    NbaEventLogRecord,
    UserContext,
    utc_now,
)
from nba_backend.ports.repositories import (
    NbaEventLogRepository,
    NbaRepository,
    ProcessedEventRepository,
)

logger = logging.getLogger(__name__)


class AccessPolicyService:
    def assert_query_access(
        self,
        user: UserContext,
        *,
        account_id: str | None,
        enterprise_number: str | None,
    ) -> None:
        # Header-derived access restrictions are intentionally disabled.
        return None

    def assert_nba_access(self, user: UserContext, *, account_id: str | None, enterprise_number: str | None) -> None:
        # Header-derived access restrictions are intentionally disabled.
        return None


class NbaQueryService:
    def __init__(self, nba_repo: NbaRepository, access_policy: AccessPolicyService) -> None:
        self._nba_repo = nba_repo
        self._access_policy = access_policy

    def list_for_user(
        self,
        user: UserContext,
        *,
        account_id: str | None,
        enterprise_number: str | None,
        status_filter: str | None,
        limit: int,
        offset: int,
    ):
        self._access_policy.assert_query_access(
            user,
            account_id=account_id,
            enterprise_number=enterprise_number,
        )

        items, total = self._nba_repo.list_nbas(
            account_id=account_id,
            enterprise_number=enterprise_number,
            status=status_filter,
            limit=limit,
            offset=offset,
        )
        return items, total


class NbaActionService:
    def __init__(
        self,
        nba_repo: NbaRepository,
        event_repo: NbaEventLogRepository,
        access_policy: AccessPolicyService,
    ) -> None:
        self._nba_repo = nba_repo
        self._event_repo = event_repo
        self._access_policy = access_policy

    def register_action(
        self,
        *,
        nba_id: str,
        status_value: str,
        action_at,
        comment: str | None,
        user: UserContext,
    ) -> NbaEventLogRecord:
        if status_value not in ACTION_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="status must be accepted or rejected",
            )

        nba = self._nba_repo.get_nba(nba_id)
        if nba is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="nba not found")

        self._access_policy.assert_nba_access(
            user,
            account_id=nba.account_id,
            enterprise_number=nba.enterprise_number,
        )

        if nba.status in {NBA_STATUS_ACCEPTED, NBA_STATUS_REJECTED}:
            if nba.status == status_value:
                existing = self._event_repo.find_action_event(nba_id, status_value)
                if existing:
                    return existing
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="state transition is not allowed",
            )

        final_action_at = action_at or utc_now()
        if final_action_at.tzinfo is None:
            final_action_at = final_action_at.replace(tzinfo=timezone.utc)

        self._nba_repo.update_status(nba_id, status_value)
        event = NbaEventLogRecord(
            id=f"evt_{uuid4().hex[:10]}",
            nba_id=nba_id,
            status=status_value,
            context={"comment": comment} if comment else {},
            acted_by=user.username,
            action_at=final_action_at,
        )
        return self._event_repo.add(event)


class CalculationEventService:
    def __init__(
        self,
        nba_repo: NbaRepository,
        event_log_repo: NbaEventLogRepository,
        processed_repo: ProcessedEventRepository,
        reference_data=None,
    ) -> None:
        self._nba_repo = nba_repo
        self._event_log_repo = event_log_repo
        self._processed_repo = processed_repo
        self._reference_data = reference_data

    def process(self, payload: dict) -> dict[str, str]:
        event_id = payload["event_id"]
        if self._processed_repo.is_processed(event_id):
            logger.info("calc.skip_duplicate event_id=%s", event_id)
            return {"action": "duplicate_skipped", "nba_id": "n/a"}

        account_id = payload.get("account_id")
        enterprise_number = payload.get("enterprise_number")
        create_nba = bool(payload.get("create_nba", True))
        deactivate_nba_ids = payload.get("deactivate_nba_ids") or []
        if self._reference_data is not None:
            account_id, enterprise_number = self._reference_data.enrich_target_identifiers(
                account_id=account_id,
                enterprise_number=enterprise_number,
            )

        if deactivate_nba_ids:
            deactivated_by_id = self._nba_repo.deactivate_nbas_by_ids(nba_ids=deactivate_nba_ids)
            logger.info(
                "calc.nba_deactivated_by_ids event_id=%s requested=%s deactivated=%s",
                event_id,
                len(deactivate_nba_ids),
                deactivated_by_id,
            )

        if not create_nba:
            self._processed_repo.mark_processed(event_id)
            logger.info("calc.event_processed event_id=%s action=deactivated_only", event_id)
            return {"action": "deactivated_only", "nba_id": "n/a"}

        nba = self._nba_repo.upsert_from_calculation_event(
            event_id=event_id,
            nba_definition_id=payload["nba_definition_id"],
            enterprise_number=enterprise_number,
            account_id=account_id,
            contact_id=payload.get("contact_id"),
            context=payload.get("context", {}),
        )
        if nba:
            logger.info(
                "calc.nba_upserted event_id=%s nba_id=%s account_id=%s enterprise_number=%s",
                event_id,
                nba.id,
                nba.account_id,
                nba.enterprise_number,
            )
            deactivated = self._nba_repo.deactivate_other_active_new_for_scope(
                keep_nba_id=nba.id,
                nba_definition_id=nba.nba_definition_id,
                enterprise_number=nba.enterprise_number,
                account_id=nba.account_id,
                contact_id=nba.contact_id,
            )
            if deactivated:
                logger.info(
                    "calc.nba_deactivated event_id=%s keep_nba_id=%s deactivated=%s",
                    event_id,
                    nba.id,
                    deactivated,
                )
            self._event_log_repo.add(
                NbaEventLogRecord(
                    id=f"evt_{uuid4().hex[:10]}",
                    nba_id=nba.id,
                    status=NBA_STATUS_NEW,
                    context={
                        "source": payload.get("source"),
                        "occurred_at": payload.get("occurred_at"),
                    },
                )
            )

        self._processed_repo.mark_processed(event_id)
        logger.info("calc.event_processed event_id=%s", event_id)
        return {"action": "created", "nba_id": nba.id if nba else "n/a"}
