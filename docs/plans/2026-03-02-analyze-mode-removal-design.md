# Analyze Mode Removal Design

## Goal
Remove the `mode` parameter from the `/analyze` endpoint request schema and reject requests that include it.

## Context
The `/analyze` endpoint currently validates `mode` but does not change behavior based on it. Downstream analysis always runs paragraph analysis, and persistence in jobs hardcodes `mode="paragraph"`. Keeping `mode` in the request creates misleading API surface and unused validation.

## Proposed Approach
- Remove `mode` from `AnalyzeRequest` in `src/refweaver/api/schemas.py`.
- Remove `mode` validation and any request-time checks in `src/refweaver/api/routes/analyze.py`.
- When queueing async runs in `/analyze`, omit `mode` from `create_queued_run` since it no longer comes from the request.
- Update tests to ensure requests containing `mode` are rejected (422) and remove any tests that rely on `mode` being accepted.

## Data Flow
- Client sends `text`, `async_mode`, and `include_markdown` only.
- `/analyze` performs text validation and dispatches the paragraph analysis job.
- Jobs persist runs with `mode="paragraph"` (unchanged behavior).

## Error Handling
- Pydantic validation rejects payloads including `mode` with HTTP 422.
- No changes to runtime error handling inside analysis jobs.

## Impacted Components
- `src/refweaver/api/schemas.py`
- `src/refweaver/api/routes/analyze.py`
- `tests/test_api.py` (plus any other tests that submit `mode`)

## Testing
- Update or add tests to ensure `mode` is rejected when present.
- Run `pytest tests/test_api.py` for focused coverage.

## Rollout
- Breaking change for clients still sending `mode`; document in release notes if applicable.
