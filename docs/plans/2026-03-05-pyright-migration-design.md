# Pyright Migration Design

## Goal
Replace mypy with pyright to speed up type checking, while preserving the existing strictness intent and ignoring missing stubs.

## Scope
- Remove mypy configuration and dev dependency.
- Add pyright configuration in `pyproject.toml` with strict mode.
- Update pre-commit to run pyright instead of mypy.
- Update `AGENTS.md` to reference pyright commands.

## Non-Goals
- No code-level type refactors.
- No behavior changes outside tooling and docs.

## Configuration Mapping
- `mypy strict = true` -> `pyright.typeCheckingMode = "strict"`.
- `mypy ignore_missing_imports = true` -> `pyright.reportMissingTypeStubs = false`.
- Other mypy-only flags are dropped unless there is a direct pyright equivalent.

## Rollout Plan
- Commit 1: design doc (this file).
- Commit 2: configuration + tooling + docs migration.

## Risks
- Pyright and mypy disagree on some diagnostics; strict mode may surface new issues. We will rely on existing clean state and keep configuration minimal.

## Verification
- Run `pre-commit run --all-files` or `pyright` directly to confirm the new type checker runs successfully.
