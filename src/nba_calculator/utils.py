from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import parse
from urllib import request
from uuid import uuid4
import sqlite3
import hashlib

DATABASE_LOCATION = Path("../../mock_db.sqlite3")


class CalculatorUtils:
    """Reusable helpers for NBA calculator scripts."""

    @staticmethod
    def utc_now_iso() -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _create_event_payload(
        *,
        nba_definition_id: str,
        source: str,
        enterprise_number: str,
        context: dict[str, Any],
        account_id: str | None = None,
        contact_id: str | None = None,
        create_nba: bool = True,
        deactivate_nba_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        event: dict[str, Any] = {
            "event_id": str(uuid4()),
            "occurred_at": CalculatorUtils.utc_now_iso(),
            "source": source,
            "nba_definition_id": nba_definition_id,
            "enterprise_number": str(enterprise_number),
            "context": context,
        }

        if account_id:
            event["account_id"] = str(account_id)
        if contact_id:
            event["contact_id"] = str(contact_id)
        if not create_nba:
            event["create_nba"] = False
        if deactivate_nba_ids:
            event["deactivate_nba_ids"] = [str(nba_id) for nba_id in deactivate_nba_ids]

        return event

    @staticmethod
    def create_event(*args, **kwargs) -> dict[str, Any]:
        """
        Create an NBA calculation event.

        Supported call styles:
        1) Explicit fields:
           create_event(nba_definition_id=..., source=..., enterprise_number=..., context=..., ...)
        2) Client object shorthand:
           create_event(client, context, nba_definition_id=..., source=..., ...)
        """
        if args:
            if len(args) != 2:
                raise TypeError("create_event(client, context, ...) expects exactly 2 positional arguments")
            client, context = args
            if not isinstance(client, dict) or not isinstance(context, dict):
                raise TypeError("create_event(client, context, ...) expects dict arguments")

            nba_definition_id = kwargs.pop("nba_definition_id", None)
            source = kwargs.pop("source", None)
            contact_id = kwargs.pop("contact_id", None)
            create_nba = kwargs.pop("create_nba", True)
            deactivate_nba_ids = kwargs.pop("deactivate_nba_ids", None)

            if kwargs:
                unexpected = ", ".join(sorted(kwargs.keys()))
                raise TypeError(f"unexpected keyword argument(s): {unexpected}")
            if not nba_definition_id or not source:
                raise TypeError("nba_definition_id and source are required")

            return CalculatorUtils._create_event_payload(
                nba_definition_id=nba_definition_id,
                source=source,
                enterprise_number=str(client.get("enterprise_number", "")),
                account_id=str(client.get("account_id", "")) or None,
                contact_id=contact_id,
                create_nba=bool(create_nba),
                deactivate_nba_ids=deactivate_nba_ids,
                context=context,
            )

        return CalculatorUtils._create_event_payload(**kwargs)

    @staticmethod
    def post_event(endpoint: str, event: dict[str, Any], request_id: str | None = None) -> tuple[int, str]:
        data = json.dumps(event).encode("utf-8")
        req = request.Request(endpoint, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        if request_id:
            req.add_header("X-Request-Id", request_id)

        with request.urlopen(req) as response:
            body = response.read().decode("utf-8")
            return response.status, body

    @staticmethod
    def make_request_id(prefix: str, index: int) -> str:
        return f"{prefix}-{index}"

    @staticmethod
    def fetch_active_nbas_for_definition(
        *,
        nba_list_endpoint: str,
        nba_definition_id: str,
        account_id: str | None = None,
        enterprise_number: str | None = None,
        limit: int = 200,
        timeout_seconds: float = 10.0,
    ) -> list[dict[str, Any]]:
        page_limit = max(1, min(limit, 200))
        offset = 0
        matched_items: list[dict[str, Any]] = []

        while True:
            query: dict[str, str | int] = {
                "status": "new",
                "limit": page_limit,
                "offset": offset,
            }
            if account_id:
                query["account_id"] = account_id
            if enterprise_number:
                query["enterprise_number"] = enterprise_number

            url = f"{nba_list_endpoint}?{parse.urlencode(query)}"
            req = request.Request(url, method="GET")

            with request.urlopen(req, timeout=timeout_seconds) as response:
                body = response.read().decode("utf-8")
                payload = json.loads(body)

            items = payload.get("items", [])
            total = int(payload.get("total", 0))
            matched_items.extend(
                [
                    item
                    for item in items
                    if item.get("status") == "new"
                    and item.get("nba_definition_id") == nba_definition_id
                ]
            )

            offset += len(items)
            if offset >= total or not items:
                break

        return matched_items

    @staticmethod
    def execute_sql_query(query: str):
        with sqlite3.connect(DATABASE_LOCATION) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query).fetchall()
            
        return [dict(row) for row in rows]

    @staticmethod
    def calculate_hash(event_context):
        payload = json.dumps(event_context, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
    
    @staticmethod
    def post_events(events, dry_run: bool, endpoint: str, request_id_prefix: str):
        if dry_run:
            for event in events:
                print(json.dumps(event,indent=2))
                print()
        else:
            for idx, event in enumerate(events, start=1):
                request_id = CalculatorUtils.make_request_id(request_id_prefix, idx)
                status, body = CalculatorUtils.post_event(endpoint, event, request_id=request_id)
                print({"request_id": request_id, "event_id": event["event_id"], "status": status, "response": body})
    
    @staticmethod
    def create_delete_event(client, context, nba_ids_to_delete, nba_definition_id, source):
        return CalculatorUtils.create_event(
            nba_definition_id=nba_definition_id,
            source=source,
            enterprise_number=client.get("enterprise_number",""),
            account_id=client.get("account_id",""),
            deactivate_nba_ids=nba_ids_to_delete,
            create_nba=False,
            context=context)
    
    @staticmethod
    def set_context_hash(context):
        context_hash = CalculatorUtils.calculate_hash(context)
        context["hash"] = context_hash

        return context
    
class EnvConfig:
    """Typed environment readers for calculator notebooks."""

    @staticmethod
    def str(name: str, default: str) -> str:
        return os.getenv(name, default)

    @staticmethod
    def int(name: str, default: int) -> int:
        return int(os.getenv(name, str(default)))

    @staticmethod
    def float(name: str, default: float) -> float:
        return float(os.getenv(name, str(default)))

    @staticmethod
    def bool(name: str, default: bool) -> bool:
        raw = os.getenv(name, str(default)).strip().lower()
        return raw in {"1", "true", "yes", "on"}

    @staticmethod
    def path(name: str, default: str | Path) -> Path:
        return Path(os.getenv(name, str(default)))

    @staticmethod
    def csv(name: str, default: list[str]) -> list[str]:
        raw = os.getenv(name)
        if raw is None:
            return list(default)
        return [item.strip() for item in raw.split(",") if item.strip()]
