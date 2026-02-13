from __future__ import annotations

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse

from nba_backend.adapters.inmemory.repositories import (
    InMemoryNbaEventLogRepository,
    InMemoryNbaRepository,
    InMemoryProcessedEventRepository,
)
from nba_backend.adapters.queue.inmemory_queue import InMemoryCalculationEventQueue
from nba_backend.api.routes import router
from nba_backend.application.services import (
    AccessPolicyService,
    CalculationEventService,
    NbaActionService,
    NbaQueryService,
)
from nba_backend.logging_config import configure_logging


@dataclass(slots=True)
class Services:
    query: NbaQueryService
    action: NbaActionService
    calc: CalculationEventService


logger = logging.getLogger(__name__)


async def queue_worker(app: FastAPI) -> None:
    queue = app.state.queue
    services: Services = app.state.services
    while True:
        envelope = await queue.consume()
        payload = envelope["payload"]
        request_id = envelope.get("request_id", "n/a")
        event_id = payload.get("event_id", "n/a")
        logger.info(
            "queue.consume request_id=%s event_id=%s",
            request_id,
            event_id,
        )
        result = services.calc.process(payload)
        logger.info(
            "queue.processed request_id=%s event_id=%s action=%s nba_id=%s",
            request_id,
            event_id,
            result["action"],
            result["nba_id"],
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    logger.info("app.startup begin")

    nba_repo = InMemoryNbaRepository()
    event_repo = InMemoryNbaEventLogRepository()
    processed_repo = InMemoryProcessedEventRepository()

    access_policy = AccessPolicyService()
    query_service = NbaQueryService(nba_repo=nba_repo, access_policy=access_policy)
    action_service = NbaActionService(
        nba_repo=nba_repo,
        event_repo=event_repo,
        access_policy=access_policy,
    )
    calc_service = CalculationEventService(
        nba_repo=nba_repo,
        event_log_repo=event_repo,
        processed_repo=processed_repo,
    )

    app.state.services = Services(query=query_service, action=action_service, calc=calc_service)
    app.state.queue = InMemoryCalculationEventQueue()
    app.state.worker_task = asyncio.create_task(queue_worker(app))

    try:
        yield
    finally:
        logger.info("app.shutdown begin")
        app.state.worker_task.cancel()
        with suppress(asyncio.CancelledError):
            await app.state.worker_task
        logger.info("app.shutdown complete")


app = FastAPI(title="Next Best Action API", version="1.0.0", lifespan=lifespan)
app.include_router(router)


@app.middleware("http")
async def request_trace_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-Id") or f"req_{uuid4().hex[:10]}"
    request.state.request_id = request_id
    started = time.perf_counter()
    logger.info(
        "http.request.start request_id=%s method=%s path=%s",
        request_id,
        request.method,
        request.url.path,
    )
    response = await call_next(request)
    duration_ms = int((time.perf_counter() - started) * 1000)
    response.headers["X-Request-Id"] = request_id
    logger.info(
        "http.request.end request_id=%s method=%s path=%s status=%s duration_ms=%s",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/ui/active-nbas", response_class=HTMLResponse)
def active_nbas_ui() -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Active NBAs by Client</title>
  <style>
    :root {
      --bg: #f4f1e8;
      --panel: #fffdf8;
      --ink: #1f2937;
      --muted: #5b6473;
      --line: #d5ccbc;
      --accent: #0f766e;
      --accent-soft: #d6f2ee;
      --danger: #b42318;
      --shadow: 0 14px 32px rgba(31, 41, 55, 0.12);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      color: var(--ink);
      background:
        radial-gradient(circle at 15% 15%, #d9efe8 0%, transparent 42%),
        radial-gradient(circle at 86% 8%, #fde7c7 0%, transparent 38%),
        var(--bg);
      font-family: "Space Grotesk", "Avenir Next", "Segoe UI", sans-serif;
      min-height: 100vh;
    }
    .wrap {
      max-width: 980px;
      margin: 0 auto;
      padding: 28px 18px 48px;
    }
    .hero {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 18px;
      box-shadow: var(--shadow);
      padding: 18px;
    }
    h1 {
      margin: 0 0 8px;
      font-size: clamp(1.4rem, 2.2vw, 2rem);
      letter-spacing: -0.02em;
    }
    .sub {
      margin: 0 0 16px;
      color: var(--muted);
      font-size: 0.95rem;
    }
    .controls {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 10px;
    }
    label {
      display: block;
      font-size: 0.78rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--muted);
      margin-bottom: 5px;
    }
    input {
      width: 100%;
      padding: 10px 12px;
      border: 1px solid var(--line);
      border-radius: 10px;
      font: inherit;
      background: #fff;
      color: var(--ink);
    }
    button {
      margin-top: 23px;
      width: 100%;
      padding: 11px 12px;
      border: none;
      border-radius: 10px;
      font: inherit;
      font-weight: 700;
      color: #fff;
      background: linear-gradient(135deg, #0f766e, #0f766e 55%, #0e9388);
      cursor: pointer;
    }
    .meta {
      display: flex;
      gap: 12px;
      align-items: center;
      margin: 12px 0 4px;
      color: var(--muted);
      font-size: 0.9rem;
      flex-wrap: wrap;
    }
    .status-pill {
      padding: 3px 8px;
      border-radius: 999px;
      background: var(--accent-soft);
      color: var(--accent);
      font-size: 0.8rem;
      font-weight: 700;
    }
    #list {
      margin-top: 14px;
      display: grid;
      gap: 12px;
    }
    .card {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 14px;
      box-shadow: 0 5px 14px rgba(31, 41, 55, 0.08);
    }
    .row {
      display: flex;
      justify-content: space-between;
      gap: 10px;
      flex-wrap: wrap;
    }
    .id {
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      color: #0f172a;
      font-size: 0.86rem;
    }
    .def {
      color: #0f172a;
      font-weight: 700;
    }
    .kvs {
      margin-top: 10px;
      padding: 10px;
      border-radius: 10px;
      background: #f7f3ea;
      border: 1px solid #eadfca;
      overflow: auto;
      font: 12px/1.4 ui-monospace, SFMono-Regular, Menlo, monospace;
    }
    .empty, .error {
      margin-top: 14px;
      padding: 14px;
      border-radius: 12px;
      border: 1px dashed var(--line);
      background: #fbfaf7;
      color: var(--muted);
    }
    .error {
      color: var(--danger);
      border-color: #efc2be;
      background: #fff6f5;
    }
    @media (max-width: 760px) {
      .controls { grid-template-columns: 1fr; }
      button { margin-top: 0; }
    }
  </style>
</head>
<body>
  <main class="wrap">
    <section class="hero">
      <h1>Active NBAs Per Client</h1>
      <p class="sub">Switch clients by URL using <code>?client=&lt;enterprise_number&gt;</code>.</p>
      <div class="controls">
        <div>
          <label for="clientInput">Client (Enterprise Number)</label>
          <input id="clientInput" placeholder="0123456789" />
        </div>
        <div>
          <button id="loadButton" type="button">Load Active NBAs</button>
        </div>
      </div>
      <div class="meta">
        <span id="count" class="status-pill">0 active</span>
        <span id="scope"></span>
      </div>
      <div id="error" class="error" style="display:none"></div>
      <div id="list"></div>
      <div id="empty" class="empty" style="display:none">No active NBAs found for this client.</div>
    </section>
  </main>
  <script>
    const defaults = { client: "0123456789" };
    const params = new URLSearchParams(window.location.search);
    const clientInput = document.getElementById("clientInput");
    const loadButton = document.getElementById("loadButton");
    const listEl = document.getElementById("list");
    const countEl = document.getElementById("count");
    const scopeEl = document.getElementById("scope");
    const errorEl = document.getElementById("error");
    const emptyEl = document.getElementById("empty");

    function readState() {
      return {
        client: (params.get("client") || defaults.client).trim(),
      };
    }

    function writeState(client) {
      const next = new URLSearchParams(window.location.search);
      next.set("client", client);
      const nextUrl = `${window.location.pathname}?${next.toString()}`;
      window.history.replaceState(null, "", nextUrl);
      params.set("client", client);
    }

    function setLoading(loading) {
      loadButton.disabled = loading;
      loadButton.textContent = loading ? "Loading..." : "Load Active NBAs";
    }

    function clearMessages() {
      errorEl.style.display = "none";
      errorEl.textContent = "";
      emptyEl.style.display = "none";
    }

    function renderItems(items) {
      listEl.innerHTML = "";
      for (const item of items) {
        const card = document.createElement("article");
        card.className = "card";
        card.innerHTML = `
          <div class="row">
            <div class="def">${item.nba_definition_id}</div>
            <div class="status-pill">${item.status}</div>
          </div>
          <div class="row" style="margin-top: 6px;">
            <div class="id">nba_id: ${item.id}</div>
            <div class="id">priority: ${item.priority}</div>
          </div>
          <div class="kvs">${JSON.stringify(item.context || {}, null, 2)}</div>
        `;
        listEl.appendChild(card);
      }
    }

    async function loadNbas(client) {
      clearMessages();
      setLoading(true);
      scopeEl.textContent = `client=${client}`;
      try {
        const url = new URL("/api/v1/nba", window.location.origin);
        url.searchParams.set("enterprise_number", client);
        url.searchParams.set("status", "new");
        url.searchParams.set("limit", "200");

        const res = await fetch(url);
        const payload = await res.json();
        if (!res.ok) {
          throw new Error(payload.message || `Request failed with status ${res.status}`);
        }

        const items = payload.items || [];
        countEl.textContent = `${items.length} active`;
        renderItems(items);
        if (!items.length) {
          emptyEl.style.display = "block";
        }
      } catch (err) {
        listEl.innerHTML = "";
        countEl.textContent = "0 active";
        errorEl.style.display = "block";
        errorEl.textContent = String(err.message || err);
      } finally {
        setLoading(false);
      }
    }

    function onSubmit() {
      const client = clientInput.value.trim() || defaults.client;
      writeState(client);
      loadNbas(client);
    }

    loadButton.addEventListener("click", onSubmit);
    clientInput.addEventListener("keydown", (event) => {
      if (event.key === "Enter") onSubmit();
    });
    const initial = readState();
    clientInput.value = initial.client;
    loadNbas(initial.client);
  </script>
</body>
</html>
"""


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    code_map = {
        400: "bad_request",
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        409: "conflict",
    }
    code = code_map.get(exc.status_code, "error")
    request_id = getattr(request.state, "request_id", "n/a")
    logger.warning(
        "http.error request_id=%s status=%s code=%s detail=%s",
        request_id,
        exc.status_code,
        code,
        exc.detail,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": code, "message": str(exc.detail)},
    )
