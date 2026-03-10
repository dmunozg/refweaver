# RefWeaver REST API

This document describes the current FastAPI behavior for all exposed endpoints,
including headers, payload validation, error handling, and async run lifecycle.

## Base URL

- Local default: `http://localhost:8000`

## Running the API

```bash
uvicorn refweaver.api.main:app --reload
```

## Authentication, Headers, and Request Limits

### Header rules

- `GET /health` does **not** require auth headers.
- All other endpoints require `X-User-Id`.
- `X-API-Key` is required on protected endpoints only when
  `REFWEAVER_API_KEY` is configured on the server.

Protected endpoints are:

- `POST /analyze`
- `GET /jobs/{job_id}`
- `POST /search`
- `POST /enrich`
- `POST /report`
- `GET /runs/{run_id}`

### Rate limiting

- Per-user limit based on `X-User-Id`.
- Controlled by `REFWEAVER_RATE_LIMIT_PER_MINUTE` (`0` disables).
- Backed by in-memory or Redis via `REFWEAVER_RATE_LIMIT_BACKEND`.
- Exceeded limit returns `429` with details:

```json
{
  "detail": {
    "error_code": "rate_limited",
    "message": "Rate limit exceeded",
    "details": {"limit_per_minute": "60"}
  }
}
```

### Request body size limit

- Controlled by `REFWEAVER_MAX_REQUEST_BYTES`.
- Oversized request body returns `413`:

```json
{
  "error_code": "request_too_large",
  "message": "Request body exceeds size limit",
  "details": {"max_bytes": "5000000"}
}
```

## Error Model

Application-level errors use this envelope:

- `error_code` (machine-readable)
- `message` (human-readable)
- `details` (optional key/value strings)

For route/dependency errors, the envelope is returned under `detail`:

```json
{
  "detail": {
    "error_code": "missing_user",
    "message": "Missing user id header",
    "details": null
  }
}
```

FastAPI/Pydantic validation failures return `422` with the framework's standard
validation structure.

## GET /health

Checks service dependencies and returns DB/Redis health details.

- **Method/Path:** `GET /health`
- **Headers:** none required
- **Success:** `200 OK` when both DB and Redis checks are healthy
- **Degraded:** `503 Service Unavailable` when DB or Redis check fails

### 200 response

```json
{
  "status": "ok",
  "db": {"status": "ok", "message": null},
  "redis": {"status": "ok", "message": null}
}
```

### 503 response

```json
{
  "status": "error",
  "db": {"status": "error", "message": "db down"},
  "redis": {"status": "ok", "message": null}
}
```

### Example

```bash
curl -s http://localhost:8000/health
```

## POST /analyze

Creates a run and always enqueues asynchronous analysis work.

- **Method/Path:** `POST /analyze`
- **Headers:** `X-User-Id` required; `X-API-Key` conditionally required
- **Body schema:**
  - `text` (string, required, must be non-empty after trim)
  - `include_markdown` (boolean, optional, default `true`)
  - Extra/unknown fields are rejected (`422`)
- **Responses:**
  - `200 OK` queued response
  - `400` missing user header
  - `401` invalid API key (when API key auth enabled)
  - `413` input too long (`error_code: input_too_long`) or request too large
  - `422` validation error
  - `429` rate limit exceeded

### 200 response

```json
{
  "run_id": "7f5f67c58f8842a1acda1339abf8bde4",
  "status": "queued",
  "job_id": "a7b6dc35-1f41-4011-9e25-57f23cb3ecad",
  "job_url": "/jobs/a7b6dc35-1f41-4011-9e25-57f23cb3ecad"
}
```

### Example

```bash
curl -s \
  -H "X-User-Id: user-1" \
  -H "Content-Type: application/json" \
  -d '{"text":"This is a test sentence.","include_markdown":true}' \
  http://localhost:8000/analyze
```

## GET /jobs/{job_id}

Retrieves async job state for the requesting user.

- **Method/Path:** `GET /jobs/{job_id}`
- **Headers:** `X-User-Id` required; `X-API-Key` conditionally required
- **Path params:** `job_id` string
- **Responses:**
  - `200 OK` with job payload when job belongs to `X-User-Id`
  - `404` if job is missing or belongs to another user (`error_code: not_found`)
  - `400/401/429` for header/auth/rate-limit errors

### 200 response examples

In progress:

```json
{
  "status": "started",
  "job_id": "a7b6dc35-1f41-4011-9e25-57f23cb3ecad",
  "user_id": "user-1"
}
```

Finished with run link:

```json
{
  "status": "finished",
  "job_id": "a7b6dc35-1f41-4011-9e25-57f23cb3ecad",
  "user_id": "user-1",
  "run_id": "7f5f67c58f8842a1acda1339abf8bde4",
  "run_url": "/runs/7f5f67c58f8842a1acda1339abf8bde4"
}
```

### Example

```bash
curl -s \
  -H "X-User-Id: user-1" \
  http://localhost:8000/jobs/a7b6dc35-1f41-4011-9e25-57f23cb3ecad
```

## POST /search

Searches for articles and optionally enriches each result.

- **Method/Path:** `POST /search`
- **Headers:** `X-User-Id` required; `X-API-Key` conditionally required
- **Body schema:**
  - `query` (string, required, non-empty after trim)
  - `limit_per_source` (int, optional, default `5`, min `1`, max `50`)
  - `enrich` (boolean, optional, default `false`)
- **Responses:**
  - `200 OK` with `results`
  - `400/401/422/429`

### 200 response

```json
{
  "results": [
    {
      "source": "openalex",
      "external_id": "W123",
      "title": "Example Article"
    }
  ]
}
```

### Example

```bash
curl -s \
  -H "X-User-Id: user-1" \
  -H "Content-Type: application/json" \
  -d '{"query":"climate change","limit_per_source":3,"enrich":false}' \
  http://localhost:8000/search
```

## POST /enrich

Enriches caller-provided article records.

- **Method/Path:** `POST /enrich`
- **Headers:** `X-User-Id` required; `X-API-Key` conditionally required
- **Body schema:**
  - `articles` (required, non-empty array)
    - each item:
      - `source` (string, required)
      - `external_id` (string, required)
      - `title` (string, required)
      - `authors` (array of strings, optional, default `[]`)
      - `year` (int or null, optional)
      - `doi` (string or null, optional)
      - `url` (valid URL or null, optional)
  - `try_llm` (boolean, optional, default `false`)
- **Responses:**
  - `200 OK` with enriched `results`
  - `400/401/422/429`

### Example

```bash
curl -s \
  -H "X-User-Id: user-1" \
  -H "Content-Type: application/json" \
  -d '{"articles":[{"source":"openalex","external_id":"oa-1","title":"Example","authors":["Author"],"year":2023}],"try_llm":false}' \
  http://localhost:8000/enrich
```

## POST /report

Builds a report for an existing run owned by the caller.

- **Method/Path:** `POST /report`
- **Headers:** `X-User-Id` required; `X-API-Key` conditionally required
- **Body schema:**
  - `run_id` (string, required)
  - `format` (string, optional, default `markdown`, allowed: `markdown`, `json`)
- **Responses:**
  - `200 OK`
  - `404` if run does not exist or is not owned by caller
  - `400/401/422/429`

### 200 response (`format=markdown`, default)

```json
{
  "run_id": "7f5f67c58f8842a1acda1339abf8bde4",
  "report": "# Run 7f5f67c58f8842a1acda1339abf8bde4\n..."
}
```

### 200 response (`format=json`)

```json
{
  "run_id": "7f5f67c58f8842a1acda1339abf8bde4",
  "sentences": [
    {"id": "s1", "text": "Sentence text", "verdict": "supported"}
  ]
}
```

### Example

```bash
curl -s \
  -H "X-User-Id: user-1" \
  -H "Content-Type: application/json" \
  -d '{"run_id":"7f5f67c58f8842a1acda1339abf8bde4","format":"markdown"}' \
  http://localhost:8000/report
```

## GET /runs/{run_id}

Returns stored run data (run metadata, sentences, verdicts, evaluations) and
optionally a markdown report.

- **Method/Path:** `GET /runs/{run_id}`
- **Headers:** `X-User-Id` required; `X-API-Key` conditionally required
- **Path params:** `run_id` string
- **Query params:**
  - `format` (optional, default `json`)
  - When `format=markdown`, response includes `report`
  - Any value other than `markdown` behaves as JSON mode
- **Responses:**
  - `200 OK`
  - `404` if run missing or owned by another user
  - `400/401/429`

### 200 response (`format=json`)

```json
{
  "run": {
    "id": "7f5f67c58f8842a1acda1339abf8bde4",
    "user_id": "user-1",
    "mode": "paragraph",
    "status": "complete",
    "input_text": "This is a test sentence.",
    "created_at": "2026-03-09T10:00:00+00:00",
    "updated_at": "2026-03-09T10:00:10+00:00"
  },
  "sentences": [],
  "verdicts": {},
  "evaluations": []
}
```

### 200 response (`format=markdown`)

```json
{
  "run": {
    "id": "7f5f67c58f8842a1acda1339abf8bde4",
    "user_id": "user-1",
    "mode": "paragraph",
    "status": "complete",
    "input_text": "This is a test sentence.",
    "created_at": "2026-03-09T10:00:00+00:00",
    "updated_at": "2026-03-09T10:00:10+00:00"
  },
  "sentences": [],
  "verdicts": {},
  "evaluations": [],
  "report": "# Run 7f5f67c58f8842a1acda1339abf8bde4\n..."
}
```

### Example

```bash
curl -s \
  -H "X-User-Id: user-1" \
  "http://localhost:8000/runs/7f5f67c58f8842a1acda1339abf8bde4?format=markdown"
```

## Configuration Reference

- `DATABASE_URL`: SQLAlchemy database connection string.
- `REFWEAVER_API_KEY`: Enables API-key auth when set.
- `REFWEAVER_RATE_LIMIT_PER_MINUTE`: Per-user requests per minute (`0` disables).
- `REFWEAVER_RATE_LIMIT_BACKEND`: `memory` or `redis`.
- `REFWEAVER_MAX_REQUEST_BYTES`: Max request body size in bytes.
- `OPENALEX_EMAIL`: Optional OpenAlex config used by enrichment.
- `SEMANTIC_SCHOLAR_API_KEY`: Optional Semantic Scholar config used by enrichment.
