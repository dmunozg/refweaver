# RefWeaver REST API

This document explains how to use the RefWeaver REST API and provides curl
examples for each endpoint. The API is internal-only and requires a user ID
header on all requests. If an API key is configured, it must be provided on
every request as well.

## Base URL

Use the base URL where your FastAPI app is running, for example:

- `http://localhost:8000`

## Authentication and Headers

Required headers:

- `X-User-Id`: The user identifier used to associate runs and jobs.

Optional (if configured):

- `X-API-Key`: Required when `REFWEAVER_API_KEY` is set.

## Common Errors

- `400`: Missing user header or invalid request headers.
- `401`: Invalid API key.
- `404`: Resource not found.
- `413`: Request body too large.
- `422`: Validation error for request payloads.
- `429`: Rate limit exceeded.

## GET /health

Health check endpoint.

Example:

```bash
curl -s \
  -H "X-User-Id: user-1" \
  http://localhost:8000/health
```

Response:

```json
{"status": "ok"}
```

## POST /analyze

Analyze a sentence/paragraph/document and return results.

Request body:

- `text` (string, required): Input text to analyze.
- `mode` (string, optional): `sentence`, `paragraph`, or `document`. Default: `paragraph`.
- `async_mode` (boolean, optional): If true, enqueue a background job. Default: false.
- `include_markdown` (boolean, optional): Include a markdown report. Default: true.

Example (sync):

```bash
curl -s \
  -H "X-User-Id: user-1" \
  -H "Content-Type: application/json" \
  -d '{"text":"This is a test sentence.","mode":"paragraph","include_markdown":false}' \
  http://localhost:8000/analyze
```

Example (async):

```bash
curl -s \
  -H "X-User-Id: user-1" \
  -H "Content-Type: application/json" \
  -d '{"text":"This is a test sentence.","async_mode":true}' \
  http://localhost:8000/analyze
```

Response (sync):

```json
{
  "run_id": "<run-id>",
  "status": "completed",
  "results": [
    {
      "sentence": {"text": "..."},
      "sentence_for_evaluation": "...",
      "sentence_original_text": "...",
      "verdict": {"overall_assessment": "..."},
      "evaluations": []
    }
  ],
  "markdown_report": null
}
```

Response (async):

```json
{
  "run_id": "<run-id>",
  "status": "queued",
  "job_id": "<job-id>",
  "job_url": "/jobs/<job-id>"
}
```

## GET /jobs/{job_id}

Check the status of an async job.

Example:

```bash
curl -s \
  -H "X-User-Id: user-1" \
  http://localhost:8000/jobs/<job-id>
```

Response (finished):

```json
{
  "status": "finished",
  "job_id": "<job-id>",
  "run_id": "<run-id>",
  "run_url": "/runs/<run-id>"
}
```

## POST /search

Search for articles. Enrichment is optional and off by default.

Request body:

- `query` (string, required)
- `limit_per_source` (int, optional, default 5)
- `enrich` (boolean, optional, default false)

Example:

```bash
curl -s \
  -H "X-User-Id: user-1" \
  -H "Content-Type: application/json" \
  -d '{"query":"climate change", "limit_per_source": 3, "enrich": false}' \
  http://localhost:8000/search
```

Response:

```json
{"results": [{"source": "openalex", "external_id": "..."}]}
```

## POST /enrich

Enrich a list of articles (e.g., fill missing abstracts).

Request body:

- `articles` (list of Article objects, required)
- `try_llm` (boolean, optional, default false)

Example:

```bash
curl -s \
  -H "X-User-Id: user-1" \
  -H "Content-Type: application/json" \
  -d '{"articles":[{"source":"openalex","external_id":"oa-1","title":"Example","authors":["Author"],"year":2023}],"try_llm":false}' \
  http://localhost:8000/enrich
```

Response:

```json
{"results": [{"source": "openalex", "external_id": "oa-1", "abstract": "..."}]}
```

## POST /report

Generate a report for a stored run.

Request body:

- `run_id` (string, required)
- `format` (string, optional): `markdown` or `json`.

Example:

```bash
curl -s \
  -H "X-User-Id: user-1" \
  -H "Content-Type: application/json" \
  -d '{"run_id":"<run-id>","format":"markdown"}' \
  http://localhost:8000/report
```

Response:

```json
{"run_id": "<run-id>", "report": "# Run ...\n- Sentence ..."}
```

## GET /runs/{run_id}

Retrieve a stored run and its sentences, verdicts, and evaluations.

Query params:

- `format` (optional): `json` or `markdown`.

Example:

```bash
curl -s \
  -H "X-User-Id: user-1" \
  "http://localhost:8000/runs/<run-id>?format=markdown"
```

Response (json):

```json
{
  "run": {"id": "<run-id>", "user_id": "user-1"},
  "sentences": [],
  "verdicts": {},
  "evaluations": []
}
```

Response (markdown):

```json
{
  "run": {"id": "<run-id>", "user_id": "user-1"},
  "sentences": [],
  "verdicts": {},
  "evaluations": [],
  "report": "# Run <run-id>\n- ..."
}
```

## Configuration Reference

- `DATABASE_URL`: DB connection string.
- `REFWEAVER_API_KEY`: API key (optional).
- `REFWEAVER_RATE_LIMIT_PER_MINUTE`: Requests per minute per user (0 disables).
- `REFWEAVER_MAX_REQUEST_BYTES`: Max request size in bytes.
- `OPENALEX_EMAIL`: Optional for OpenAlex.
- `SEMANTIC_SCHOLAR_API_KEY`: Optional for enrichment.
