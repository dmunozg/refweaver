# REST API Implementation Plan

Date: 2026-02-27

## Goals

- Provide a FastAPI-based REST API for analysis, search, enrichment, and reporting.
- Add persistence with a database and ORM to store results for later retrieval.
- Support sync and async workflows using the existing Redis/RQ job system.
- Keep endpoints aligned with the proposed API in `docs/TODO.md`.
- Keep the API internal-only but still associate each job/run with a user ID.

## Phase 1: API Skeleton

- Create `src/refweaver/api/` package with:
  - `main.py` FastAPI app entrypoint.
  - `routes/` module for endpoint routers.
  - `schemas.py` for request/response models.
  - `settings.py` using Pydantic settings to read env vars.
  - `errors.py` for consistent error responses.
- Add OpenAPI tags and endpoint descriptions.

## Phase 2: Database + ORM

### Technology choice

- Use SQLModel (Pydantic + SQLAlchemy) or SQLAlchemy 2.0 + Pydantic models.
- Default DB: SQLite for dev, PostgreSQL for prod.

### Data models

- `User`: minimal record with a user_id and timestamps.
- `Run`: analysis session metadata (input text, mode, status, timestamps, config).
- `SentenceRecord`: derived sentences per run (original, rewritten, needs_reference, reason).
- `ArticleRecord`: articles used in evaluations.
- `EvaluationRecord`: per-sentence evaluations (relevance, stance, evidence, article link).
- `VerdictRecord`: per-sentence final verdict (confidence, synthesis, sources).

Relationships:
- `Run.user_id` -> `User.id` (required)
- `SentenceRecord.run_id` -> `Run.id`
- `EvaluationRecord.sentence_id` -> `SentenceRecord.id`
- `EvaluationRecord.article_id` -> `ArticleRecord.id`
- `VerdictRecord.sentence_id` -> `SentenceRecord.id`

### Migrations

- Use Alembic for migrations.
- Add initial migration with above tables and indexes (run_id, sentence_id, article_id).

## Phase 3: Core Endpoints

### POST /analyze

- Request: `text`, `mode` (sentence|paragraph|document), `async`, options.
- Behavior:
  - If `async=true`, enqueue job and return `202` with job ID.
  - If sync, run pipeline and persist results in DB.
  - If input exceeds token limits, return `413` with a structured error.
- Response:
  - Sync: results + `run_id` + optional markdown.
  - Async: job metadata + `run_id` + status URL.

### GET /jobs/{job_id}

- Query RQ for job status.
- When finished, include `run_id`, `run_url`, and optionally inline results.

### POST /search

- Request: keywords/query, sources, limits, `enrich` (boolean, default false).
- Response: list of `Article` models (enriched only when `enrich=true`).
- Optionally store searches for analytics.

### POST /enrich

- Request: list of articles to enrich.
- Response: enriched articles list.

### POST /report

- Request: run_id or raw evaluations + format.
- Response: markdown or JSON report.
- Alternative: replace with `/runs/{run_id}/report` to avoid duplication with `/runs/{run_id}`.

### GET /runs/{run_id}

- Fetch persisted run + sentences + evaluations + verdicts.
- Allow `format` query for `json|markdown` and include `report` if requested.

## Phase 4: Async + Worker Integration

- Update job payload to store `run_id` and persist results on completion.
- Add `refweaver-worker` to write results into DB.

## Phase 5: Auth, Rate Limiting, Validation

- API key header (env var controlled) and user ID header to associate runs/jobs.
- Add request size limits and rate limiting hooks.
- Standardize error responses.
- Validate all inputs (size, token estimate, allowed enums, and required fields).

## Phase 6: Tests & Documentation

- API tests with FastAPI TestClient.
- DB tests with SQLite in-memory.
- Docs: usage examples and curl snippets in `docs/API.md`.

## Configuration

- `DATABASE_URL` (default SQLite)
- `REDIS_URL`
- `API_KEY` (optional)
- `API_USER_HEADER` (e.g., `X-User-Id`)
- `RUN_ASYNC_THRESHOLD` (length)
- `MAX_INPUT_TOKENS` (default 64000)
