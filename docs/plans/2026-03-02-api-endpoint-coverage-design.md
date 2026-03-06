# API Endpoint Coverage Design

**Goal:** Add happy-path and malicious-payload test coverage for API endpoints that currently lack success-path tests, with explicit wrong-user isolation checks returning 404.

## Architecture
Tests will exercise FastAPI routes using `TestClient` while overriding dependencies or patching route-level helpers to avoid real database/queue dependencies. For wrong-user access, tests will simulate resources owned by a different user and assert a 404 to avoid existence leaks. Malformed payload tests will rely on FastAPI/Pydantic validation to return 422.

## Components
- `tests/test_api.py`
  - Add happy-path tests for `/enrich` and `/report`.
  - Add malformed payload tests for `/enrich` and `/report` (invalid types, missing required fields, odd characters).
- `tests/test_api_routes_db.py` (or new `tests/test_api_routes_security.py`)
  - Add happy-path tests for `/runs/{run_id}` and `/jobs/{job_id}` by patching route helpers.
  - Add wrong-user isolation tests for `/runs/{run_id}` and `/jobs/{job_id}` asserting 404.

## Data Flow
1. Client sends request with `X-User-Id` header set to user A.
2. Route handler or patched helper returns data belonging to user B (wrong user).
3. Route responds with 404 to avoid leaking existence.
4. For malformed payloads, request validation fails and returns 422.

## Error Handling
- Wrong-user access: 404 Not Found.
- Malformed payloads: 422 Unprocessable Entity (FastAPI/Pydantic validation).

## Testing Plan
- Happy-path coverage:
  - `/enrich`: return empty or mocked enrichment payload, assert 200 and shape.
  - `/report`: return mocked report, assert 200 and shape.
  - `/runs/{run_id}`: return mocked run payload, assert 200 and shape.
  - `/jobs/{job_id}`: return mocked job payload, assert 200 and shape.
- Malicious payloads:
  - `/enrich`: invalid types (e.g., `articles` as string), missing fields, weird characters.
  - `/report`: invalid `run_id` types, missing `run_id`, weird characters.
- Wrong-user isolation:
  - `/runs/{run_id}` with user A requesting run owned by user B -> 404.
  - `/jobs/{job_id}` with user A requesting job owned by user B -> 404.

## Non-Goals
- No changes to production route logic or schema behavior.
- No end-to-end DB integration in tests.
