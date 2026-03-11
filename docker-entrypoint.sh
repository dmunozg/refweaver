#!/bin/sh
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/app}"
RUN_MIGRATIONS="${REFWEAVER_RUN_MIGRATIONS:-1}"

cd "$PROJECT_ROOT"

if [ ! -f "$PROJECT_ROOT/alembic.ini" ]; then
  echo "alembic.ini not found at $PROJECT_ROOT; cannot run migrations." >&2
  exit 1
fi

if [ ! -d "$PROJECT_ROOT/alembic" ]; then
  echo "alembic/ directory not found at $PROJECT_ROOT; cannot run migrations." >&2
  exit 1
fi

if [ "$RUN_MIGRATIONS" = "1" ]; then
  echo "Running database migrations..."
  if ! alembic -c "$PROJECT_ROOT/alembic.ini" upgrade head; then
    echo "Database migration failed; aborting startup." >&2
    exit 1
  fi
  echo "Database migrations applied."
else
  echo "Skipping database migrations (REFWEAVER_RUN_MIGRATIONS=$RUN_MIGRATIONS)."
fi

exec "$@"
