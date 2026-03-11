# RefWeaver

RefWeaver analyzes manuscript text, identifies claims that need citations, retrieves relevant literature, and generates sentence-level support verdicts.

## What RefWeaver does

- Splits input text into analyzed sentences.
- Detects whether each sentence needs references.
- Retrieves and enriches candidate sources.
- Produces per-sentence outcomes, including no-reference-needed cases.
- Exposes async API endpoints for job status, run retrieval, and report generation.

## Architecture at a glance

- `api`: FastAPI service (`/health`, `/analyze`, `/jobs/{job_id}`, `/runs/{run_id}`, `/report`).
- `worker`: background job processor (RQ).
- `redis`: queue backend.
- `postgres`: persistence for runs/sentences/verdicts/evaluations.

## Prerequisites

Choose one runtime path:

- Containerized: Docker Compose or Podman Compose.
- Local Python: `uv` (recommended for dependency and venv management).

## First-time run (Docker/Podman)

1) Create your local environment file from the template:

```bash
cp .env.example .env
```

2) Edit `.env` and set values for required variables:

- `OPENAI_BASE_URL`
- `OPENAI_API_KEY`
- `DB_PASSWORD`

Recommended:

- `OPENROUTER_API_KEY`

If required variables are missing, startup fails immediately due to required-variable checks in `compose.yml`.

3) Start the stack:

```bash
docker compose up --build
```

For Podman:

```bash
podman compose up --build
```

4) Check health:

```bash
curl http://localhost:8000/health
```

## Quick API usage

Queue an analysis job:

```bash
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -H "X-User-Id: demo-user" \
  -d '{"text":"According to WHO reports, vaccination reduced measles mortality. The moon orbits Earth."}'
```

Use the returned `job_id` and `run_id` to poll job state and fetch results:

- `GET /jobs/{job_id}`
- `GET /runs/{run_id}`
- `POST /report`

For full endpoint contracts and response schemas, see `docs/API.md`.

## Local development (without containers)

Install dependencies:

```bash
uv sync --extra dev
```

Run API:

```bash
uv run python -m refweaver.api.main
```

Run worker (separate shell):

```bash
uv run python -m refweaver.worker
```

You still need reachable Redis/Postgres and compatible `.env` values.

## Testing

Run the full suite:

```bash
uv run pytest -q
```

## Publishing container images

This repository is configured to publish images to GHCR when a version tag is
pushed.

- Registry: `ghcr.io/dmunozg/refweaver`
- Trigger: push tags matching `v*.*.*` (for example `v1.4.0`)
- Published tags for `v1.4.0`:
  - `1.4.0`
  - `1.4`
  - `1`
  - `latest`

Create and push a release tag:

```bash
git tag v1.4.0
git push origin v1.4.0
```

Published packages are visible at:
`https://github.com/dmunozg/refweaver/pkgs/container/refweaver`

## Documentation

- API reference: `docs/API.md`
- Architecture and operational notes: `docs/`

## License

MIT
