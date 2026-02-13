from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from nba_backend.api.dependencies import get_user_context
from nba_backend.application.schemas import (
    CalculationEventRequest,
    ErrorResponse,
    NbaActionRequest,
    NbaActionResponse,
    NbaItemResponse,
    NbaListResponse,
)
from nba_backend.domain.models import NBA_STATUSES, UserContext

router = APIRouter(prefix="/api/v1")
logger = logging.getLogger(__name__)


@router.get("/mock-db/overview")
def mock_db_overview(request: Request) -> dict:
    mock_db = getattr(request.app.state, "mock_db", None)
    if mock_db is None:
        return {"users": 0, "invoices": 0, "user_products": 0, "client_employees": 0}
    return mock_db.overview()


@router.get(
    "/nba",
    response_model=NbaListResponse,
    responses={
        400: {"model": ErrorResponse},
    },
)
def list_nbas(
    request: Request,
    account_id: str | None = Query(default=None),
    enterprise_number: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: UserContext = Depends(get_user_context),
) -> NbaListResponse:
    services = request.app.state.services
    request_id = getattr(request.state, "request_id", "n/a")

    if status_filter and status_filter not in NBA_STATUSES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid status filter")

    items, total = services.query.list_for_user(
        user,
        account_id=account_id,
        enterprise_number=enterprise_number,
        status_filter=status_filter,
        limit=limit,
        offset=offset,
    )
    logger.info(
        "api.list_nba request_id=%s user=%s account_id=%s enterprise_number=%s status=%s total=%s",
        request_id,
        user.username,
        account_id,
        enterprise_number,
        status_filter,
        total,
    )

    return NbaListResponse(
        items=[
            NbaItemResponse(
                id=item.id,
                nba_definition_id=item.nba_definition_id,
                enterprise_number=item.enterprise_number,
                account_id=item.account_id,
                contact_id=item.contact_id,
                active=item.active,
                status=item.status,
                priority=item.priority,
                context=item.context,
            )
            for item in items
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/nba/{nba_id}/actions",
    response_model=NbaActionResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
)
def submit_action(
    nba_id: str,
    payload: NbaActionRequest,
    request: Request,
    user: UserContext = Depends(get_user_context),
) -> NbaActionResponse:
    services = request.app.state.services
    request_id = getattr(request.state, "request_id", "n/a")
    event = services.action.register_action(
        nba_id=nba_id,
        status_value=payload.status,
        action_at=payload.action_at,
        comment=payload.comment,
        user=user,
    )
    logger.info(
        "api.submit_action request_id=%s user=%s nba_id=%s status=%s event_id=%s",
        request_id,
        user.username,
        nba_id,
        payload.status,
        event.id,
    )
    return NbaActionResponse(
        event_id=event.id,
        nba_id=event.nba_id,
        status=event.status,
        acted_by=event.acted_by or user.username,
        action_at=event.action_at,
    )


@router.post(
    "/internal/events/nba-calculation",
    status_code=status.HTTP_202_ACCEPTED,
    responses={400: {"model": ErrorResponse}},
)
async def enqueue_calculation_event(payload: CalculationEventRequest, request: Request) -> dict:
    queue = request.app.state.queue
    request_id = getattr(request.state, "request_id", "n/a")
    normalized = payload.model_dump(mode="json")
    event_id = normalized["event_id"]
    logger.info(
        "api.enqueue_event request_id=%s event_id=%s source=%s",
        request_id,
        event_id,
        normalized.get("source"),
    )
    await queue.publish({"payload": normalized, "request_id": request_id})
    logger.info(
        "api.enqueued_event request_id=%s event_id=%s",
        request_id,
        event_id,
    )
    return {"status": "accepted", "event_id": str(payload.event_id)}
