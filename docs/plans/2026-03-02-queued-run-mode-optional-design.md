# Queued Run Mode Optional Design

## Goal
Make `create_queued_run` default the mode to "paragraph" so API routes can omit it.

## Context
The analyze API no longer provides a mode in requests, which leaves `create_queued_run`
as the remaining required parameter and causes mypy failures.

## Proposed Approach
Update `create_queued_run` to accept `mode: str = "paragraph"` and use the default
when callers omit the parameter. Update any impacted call sites or types to align with
the new default. No behavior changes when a mode is explicitly provided.

## Error Handling
No new error handling is required; rely on existing validation and persistence logic.

## Testing
Run the API tests used in Task 3 and confirm mypy passes.
