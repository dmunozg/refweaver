# RefWeaver

RefWeaver analyzes manuscript text, identifies claims that need citations, retrieves relevant literature, and generates sentence-level support verdicts.

## Quick Start (Packaged Container)

These steps run RefWeaver from the published GHCR image (no local build required).

1) Create a working directory and enter it:

```bash
mkdir -p refweaver && cd refweaver
```

2) Download the image-based compose file for a tagged release:

```bash
wget -O compose.yml https://raw.githubusercontent.com/dmunozg/refweaver/v0.2.2/docs/compose.yml
```

3) Download the environment template directly into `.env`:

```bash
wget -O .env https://raw.githubusercontent.com/dmunozg/refweaver/v0.2.2/.env.example
```

4) Edit `.env` and set required values:

- `OPENAI_BASE_URL`
- `OPENAI_API_KEY`
- `DB_PASSWORD`

Recommended:

- `OPENROUTER_API_KEY`

5) Pull and start services:

```bash
podman compose pull
podman compose up -d
```

Docker alternative:

```bash
docker compose pull
docker compose up -d
```

6) Verify service health:

```bash
curl http://localhost:8000/health
```

Note: replace `v0.2.2` in the `wget` URLs with any newer release tag.

## Nightly / Build From Source

Use this when you want to run the latest repo state and build images locally.

1) Clone and enter the repository:

```bash
git clone https://github.com/dmunozg/refweaver.git
cd refweaver
```

2) Create `.env` from the example and edit values:

```bash
cp .env.example .env
```

Required:

- `OPENAI_BASE_URL`
- `OPENAI_API_KEY`
- `DB_PASSWORD`

Recommended:

- `OPENROUTER_API_KEY`

3) Build and run:

```bash
podman compose up --build -d
```

Docker alternative:

```bash
docker compose up --build -d
```

4) Verify health:

```bash
curl http://localhost:8000/health
```

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
