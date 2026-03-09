#!/bin/sh
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/app}"

cd "$PROJECT_ROOT"

if [ ! -f "$PROJECT_ROOT/alembic.ini" ]; then
  echo "alembic.ini not found at $PROJECT_ROOT; cannot run migrations." >&2
  exit 1
fi

if [ ! -d "$PROJECT_ROOT/alembic" ]; then
  echo "alembic/ directory not found at $PROJECT_ROOT; cannot run migrations." >&2
  exit 1
fi

echo "Running database migrations..."
if ! alembic -c "$PROJECT_ROOT/alembic.ini" upgrade head; then
  echo "Database migration failed; aborting startup." >&2
  exit 1
fi
echo "Database migrations applied."

exec "$@"
