# Shared API Engine Design

**Goal:** Reuse a single SQLAlchemy engine for the FastAPI app lifecycle, and create per-request sessions from that engine. CLI paths should not touch the database.

**Scope:** API server only. No changes to CLI behavior.

## Architecture
- Initialize a single SQLAlchemy `Engine` during FastAPI startup using `SETTINGS.database_url`.
- Store the engine on the FastAPI application state (`app.state.engine`).
- Provide a request-scoped session dependency that uses the shared engine, yields a `Session`, and always closes it.
- API routes use this dependency instead of calling `get_session` directly.
- CLI and background jobs remain unchanged, but should not call database helpers in normal usage.

## Components
- `src/refweaver/api/main.py`
  - Add startup/shutdown hooks to create and dispose the shared engine.
  - Ensure the engine is available on `app.state`.
- `src/refweaver/api/dependencies.py`
  - Add `get_db_session` dependency that pulls the engine from `request.app.state` and yields a `Session`.
  - If the engine is missing, raise a clear runtime error or `HTTPException` (500).
- `src/refweaver/api/routes/*`
  - Replace direct calls to `get_session(SETTINGS.database_url)` with dependency-injected sessions.

## Data Flow
1. API starts → create engine once and store on app state.
2. Each request → dependency creates a new `Session` bound to the shared engine.
3. Route uses session for DB operations.
4. Dependency closes session in a `finally` block.
5. API shuts down → dispose engine.

## Error Handling
- If a request hits a route before startup initialization (should not happen in normal FastAPI lifecycle), return a 500 with a clear error.
- Ensure session is closed even if the route raises an exception.

## Testing Plan
- Add a focused test that builds the FastAPI app and asserts the engine is created once on startup.
- Add a route-level test to assert sessions are closed (can be done by mocking the sessionmaker or using a lightweight in-memory DB).

## Non-Goals
- Changing CLI usage to interact with DB.
- Refactoring `refweaver.db.session` for non-API contexts.
