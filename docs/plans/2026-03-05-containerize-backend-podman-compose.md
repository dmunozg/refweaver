# Refweaver Containerization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Containerize the backend with a rootless Podman Compose stack using an Alpine-based Python image, add Postgres as the default DB in containers, require OpenAI env vars, and add `/health` endpoint with Redis/Postgres checks.

**Architecture:** Single Alpine-based Python image used by API (and optionally worker). Podman Compose runs API + Redis + Postgres with healthchecks and dependency gating. API reads `DATABASE_URL` pointing to Postgres and exposes `/health` for DB/Redis connectivity.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy, Redis/RQ, Postgres 16, Podman Compose.

---

### Task 1: Add container build artifacts (Dockerfile + ignore)

**Files:**
- Create: `Dockerfile`
- Create: `.dockerignore`

**Step 1: Write the failing test**
- Skip (infra change)

**Step 2: Create Dockerfile (Alpine, rootless)**
- Use `python:3.13-alpine`
- Add non-root user
- Install build deps if needed for `pymupdf`, `psycopg`, etc.
- Use `pip install` from `requirements.txt` or `pyproject.toml` (choose existing convention)

**Step 3: Add `.dockerignore`**
- Ignore `.venv`, `.git`, caches, local DB, logs

**Step 4: Build image to validate**
Run: `podman build -t refweaver:dev .`
Expected: Successful build

**Step 5: Commit**
```bash
git add Dockerfile .dockerignore
git commit -m "build: add alpine dockerfile for api"
```

---

### Task 2: Add Podman Compose services (api + redis + postgres)

**Files:**
- Modify: `compose.yml`

**Step 1: Update compose to include api + postgres**
- Add `api` service building from `Dockerfile`
- Add `postgres` service using `postgres:16-alpine`
- Configure `POSTGRES_USER`, `POSTGRES_DB`, `POSTGRES_PASSWORD`
- Wire `POSTGRES_PASSWORD` to `${DB_PASSWORD:?err}`

**Step 2: Configure required env vars for api**
- `OPENAI_BASE_URL: ${OPENAI_BASE_URL:?err}`
- `OPENAI_API_KEY: ${OPENAI_API_KEY:?err}`
- `DATABASE_URL: postgres://<user>:${DB_PASSWORD}@postgres:5432/<db>`

**Step 3: Add Redis healthcheck + Postgres healthcheck**
- Redis: `redis-cli ping`
- Postgres: `pg_isready -U <user> -d <db>`

**Step 4: Add depends_on health gating**
- `api` depends_on `redis` and `postgres` with condition: service_healthy

**Step 5: Commit**
```bash
git add compose.yml
git commit -m "chore: add podman compose stack with postgres and redis"
```

---

### Task 3: Ensure Postgres driver in dependencies

**Files:**
- Modify: `pyproject.toml` or `requirements.txt` (whichever is authoritative)

**Step 1: Add Postgres driver**
- Add `psycopg[binary]>=3.2.0` (or `psycopg2-binary` if you prefer)

**Step 2: Install and run tests**
Run: `uv sync` or `pip install -r requirements.txt`
Run: `pytest -q` (if feasible)

**Step 3: Commit**
```bash
git add pyproject.toml uv.lock
git commit -m "deps: add postgres driver"
```

---

### Task 4: Update DB session/config to support Postgres

**Files:**
- Modify: `src/refweaver/db/session.py` (or wherever engine is created)
- Modify: `src/refweaver/api/settings.py` (if needed)

**Step 1: Inspect DB session code**
- Confirm SQLAlchemy engine creation handles Postgres URL
- Ensure no SQLite-only flags (e.g., `connect_args={"check_same_thread": ...}`)

**Step 2: Adjust engine creation**
- Use conditional options for SQLite vs Postgres

**Step 3: Add minimal tests (if existing DB tests)**
- If no tests, add a light unit test to validate engine URL handling

**Step 4: Commit**
```bash
git add src/refweaver/db/session.py tests/...
git commit -m "fix: support postgres engine configuration"
```

---

### Task 5: Add `/health` endpoint with DB + Redis checks

**Files:**
- Create: `src/refweaver/api/routes/health.py` (if missing)
- Modify: `src/refweaver/api/main.py`
- Modify: `src/refweaver/queue.py` (if needed for Redis client ping)

**Step 1: Write failing test**
- Create API test hitting `/health`
- Assert `status=ok`, and subchecks for `db` and `redis`

**Step 2: Implement endpoint**
- DB: run simple `SELECT 1` via engine
- Redis: ping via queue connection
- Return structured JSON with `status`, `db`, `redis`

**Step 3: Run tests**
Run: `pytest tests/api/test_health.py -v`

**Step 4: Commit**
```bash
git add src/refweaver/api/routes/health.py src/refweaver/api/main.py tests/...
git commit -m "feat: add health endpoint with db and redis checks"
```

---

### Task 6: Add Podman Compose usage docs

**Files:**
- Modify: `README.md`

**Step 1: Document required env vars**
- `OPENAI_BASE_URL`, `OPENAI_API_KEY`, `DB_PASSWORD`

**Step 2: Document commands**
- `podman compose up --build`
- `curl http://localhost:8000/health`

**Step 3: Commit**
```bash
git add README.md
git commit -m "docs: add podman compose usage"
```
