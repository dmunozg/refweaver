# RefWeaver Agent Guide

This file helps coding agents work in this repo with minimal friction.
It reflects current tooling, style, and conventions in the codebase.

## Project Snapshot
- Python package in `src/refweaver/`
- Tests in `tests/`
- Build backend: Hatchling (see `pyproject.toml`)
- Type checking: mypy (strict)
- Lint/format: ruff
- Logging: loguru

## Cursor/Copilot Rules
- No `.cursor/rules/`, `.cursorrules`, or `.github/copilot-instructions.md` found.

## Install / Environment
Choose one of the following depending on your tooling:

### Using uv (preferred if available)
- `uv sync --all-extras`
- `uv run python -m pytest`

### Using pip
- `python -m pip install -e ".[dev]"`
- `python -m pytest`

Notes:
- Python requirement is `>=3.13` (see `pyproject.toml`).
- Some functionality needs external services (OpenRouter, OpenAI-compatible LLM).

## Build Commands
- `python -m build` (requires `build` package)
- `hatch build` (if Hatch is installed)

## Lint / Format Commands
- `ruff check .`
- `ruff format .`

## Type Check Commands
- `mypy src`

## Test Commands
- `pytest`
- `pytest tests`

### Run a single test
- `pytest tests/test_analyzer.py::TestSentenceAnalyzer::test_analyze_paragraph_single_sentence_no_ref`
- `pytest tests/test_text_utils.py::TestSplitSentences::test_basic_sentences`

### Run a single file
- `pytest tests/test_llm.py`

### Run tests with verbose output
- `pytest -vv`

### Coverage (configured in `pyproject.toml`)
- `pytest --cov=src --cov-report=term-missing`

## Code Style and Conventions

### Formatting
- Line length: 100 (ruff)
- Quotes: double quotes (ruff format)
- Indentation: spaces
- Keep docstrings on public classes and functions

### Imports
- Order: standard library, third-party, local (ruff/isort handles this)
- Prefer explicit imports over wildcard imports
- Use `from typing import ...` and `from collections.abc import ...` as needed

### Typing
- Use Python 3.13 typing syntax: `list[str]`, `dict[str, Any]`, `Foo | None`
- Avoid untyped defs (mypy strict)
- Use `Any` sparingly when external library types are loose
- Prefer `BaseModel` and Pydantic types for structured data

### Naming
- Modules: `snake_case.py`
- Classes: `PascalCase`
- Functions/variables: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- Tests: `test_*.py`, classes `Test*`, functions `test_*`

### Models and Data Handling
- Pydantic models are frozen/immutable in `refweaver.models`
- Prefer constructing new models over mutating existing ones
- Use `model_copy(update=...)` when cloning with updates

### Error Handling
- Log failures with `loguru` and return safe fallbacks when possible
- Use explicit exceptions for invalid inputs (e.g., `ValueError`)
- Guard external calls with timeouts (`run_with_timeout`)
- Prefer `warnings.warn(..., stacklevel=2)` for non-fatal user-facing warnings
- Avoid swallowing errors silently; log context

### Logging
- Use `loguru.logger` (already configured)
- Keep messages structured and concise
- Use `logger.debug` for verbose info, `logger.info` for lifecycle events

### Testing Practices
- Tests use pytest fixtures and `unittest.mock`
- Prefer small, deterministic unit tests
- Mock external services (LLMs, HTTP APIs, Selenium)
- Keep tests close to public behavior, not internal details

## Repository Layout
- `src/refweaver/` core library
- `src/refweaver/adapters/` API adapters
- `tests/` pytest suite
- `data/`, `docs/` for sample inputs and documentation

## Runtime Configuration
- LLM configuration via env vars:
  - `OPENAI_BASE_URL`
  - `OPENAI_API_KEY`
  - `LLM_MODEL`
  - `LLM_MAX_TOKENS`
  - `LLM_TEMPERATURE`
- Perplexity (OpenRouter) uses `OPENROUTER_API_KEY`

## Common Patterns to Follow
- Keep adapters thin; map external data into `Article`
- Keep pipeline stages explicit (relevance -> stance -> synthesis)
- Prefer small helper functions for parsing and formatting
- Use `contextlib.suppress` for non-critical parsing failures

## Files to Check When Editing
- `pyproject.toml` for tooling and strictness settings
- `src/refweaver/models.py` for canonical model shapes
- `tests/` for expected behavior and edge cases

## Notes for Agents
- Do not add new tooling without updating `pyproject.toml`
- If you add new deps, consider adding to `[project.optional-dependencies].dev`
- Keep ASCII in files unless existing content uses Unicode
- `docs/plans/` is gitignored; copy or symlink it into each worktree when using plan-based workflows
