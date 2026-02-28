# REST API Implementation Plan

Date: 2026-02-27

## Goals

- [x] Provide a FastAPI-based REST API for analysis, search, enrichment, and reporting.
- [x] Add persistence with a database and ORM to store results for later retrieval.
- [x] Support sync and async workflows using the existing Redis/RQ job system.
- [x] Keep endpoints aligned with the proposed API in `docs/TODO.md`.
- [x] Keep the API internal-only but still associate each job/run with a user ID.

## Phase 1: API Skeleton

- [x] Create `src/refweaver/api/` package with:
  - [x] `main.py` FastAPI app entrypoint.
  - [x] `routes/` module for endpoint routers.
  - [x] `schemas.py` for request/response models.
  - [x] `settings.py` using Pydantic settings to read env vars.
  - [x] `errors.py` for consistent error responses.
- [x] Add OpenAPI tags and endpoint descriptions.

## Phase 2: Database + ORM

### Technology choice

- [x] Use SQLAlchemy 2.0 + Pydantic models.
- [x] Default DB: SQLite for dev, PostgreSQL for prod.

### Data models

- [x] `User`: minimal record with a user_id and timestamps.
- [x] `Run`: analysis session metadata (input text, mode, status, timestamps, config).
- [x] `SentenceRecord`: derived sentences per run (original, rewritten, needs_reference, reason).
- [x] `ArticleRecord`: articles used in evaluations.
- [x] `EvaluationRecord`: per-sentence evaluations (relevance, stance, evidence, article link).
- [x] `VerdictRecord`: per-sentence final verdict (confidence, synthesis, sources).

Relationships:
- [x] `Run.user_id` -> `User.id` (required)
- [x] `SentenceRecord.run_id` -> `Run.id`
- [x] `EvaluationRecord.sentence_id` -> `SentenceRecord.id`
- [x] `EvaluationRecord.article_id` -> `ArticleRecord.id`
- [x] `VerdictRecord.sentence_id` -> `SentenceRecord.id`

### Migrations

- [x] Use Alembic for migrations.
- [x] Add initial migration with above tables and indexes (run_id, sentence_id, article_id).

## Phase 3: Core Endpoints

### POST /analyze

- [x] Request: `text`, `mode` (sentence|paragraph|document), `async`, options.
- [x] Behavior:
  - [x] If `async=true`, enqueue job and return `202` with job ID.
  - [x] If sync, run pipeline and persist results in DB.
  - [x] If input exceeds token limits, return `413` with a structured error.
- [x] Response:
  - [x] Sync: results + `run_id` + optional markdown.
  - [x] Async: job metadata + `run_id` + status URL.

### GET /jobs/{job_id}

- [x] Query RQ for job status.
- [x] When finished, include `run_id`, `run_url`, and optionally inline results.

### POST /search

- [x] Request: keywords/query, sources, limits, `enrich` (boolean, default false).
- [x] Response: list of `Article` models (enriched only when `enrich=true`).
- [ ] Optionally store searches for analytics.

### POST /enrich

- [x] Request: list of articles to enrich.
- [x] Response: enriched articles list.

### POST /report

- [x] Request: run_id or raw evaluations + format.
- [x] Response: markdown or JSON report.
- [ ] Alternative: replace with `/runs/{run_id}/report` to avoid duplication with `/runs/{run_id}`.

### GET /runs/{run_id}

- [x] Fetch persisted run + sentences + evaluations + verdicts.
- [x] Allow `format` query for `json|markdown` and include `report` if requested.

## Phase 4: Async + Worker Integration

- [x] Update job payload to store `run_id` and persist results on completion.
- [x] Add `refweaver-worker` to write results into DB.

## Phase 5: Auth, Rate Limiting, Validation

- [x] API key header (env var controlled) and user ID header to associate runs/jobs.
- [x] Add request size limits and rate limiting hooks.
- [x] Standardize error responses.
- [x] Validate all inputs (size, token estimate, allowed enums, and required fields).

## Phase 6: Tests & Documentation

- [x] API tests with FastAPI TestClient.
- [ ] DB tests with SQLite in-memory.
- [ ] Docs: usage examples and curl snippets in `docs/API.md`.

## Configuration

- [x] `DATABASE_URL` (default SQLite)
- [x] `REDIS_URL`
- [x] `API_KEY` (optional)
- [x] `API_USER_HEADER` (e.g., `X-User-Id`)
- [x] `RUN_ASYNC_THRESHOLD` (length)
- [x] `MAX_INPUT_TOKENS` (default 64000)
