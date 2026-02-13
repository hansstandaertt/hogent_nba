# HOGENT NBA Backend

Python backend for a Next Best Action platform using an in-memory database and in-process queue.

## Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn nba_backend.main:app --reload
```

Base URL: `http://127.0.0.1:8000`

Docs:
- Swagger UI: `/docs`
- OpenAPI: `/openapi.json`
- Mini frontend: `/ui/active-nbas`

### Mini frontend: active NBAs per client

Open:

```bash
http://127.0.0.1:8000/ui/active-nbas?client=0123456789
```

Switch client directly in the URL by changing `client=<enterprise_number>`.
The page fetches active NBAs (`status=new`) via `GET /api/v1/nba`.

## Mock DB integration

At startup, the backend loads mock JSON tables from `examples/mock_db` by default.

- Override location with env var: `MOCK_DB_DIR`
- Startup log prints loaded row counts
- Calculation events are enriched with known `account_id`/`enterprise_number` pairs from mock users when one identifier is missing