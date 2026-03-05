# Pyright Migration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace mypy with pyright while preserving strict type checking intent and ignoring missing stubs.

**Architecture:** Keep configuration centralized in `pyproject.toml` using `[tool.pyright]`, remove mypy config and dev dependency, and update pre-commit + docs to reference pyright.

**Tech Stack:** Python 3.13, pyright, pre-commit, ruff.

---

### Task 1: Update tool configuration and dependencies

**Files:**
- Modify: `pyproject.toml`

**Step 1: Write minimal implementation**

Update `pyproject.toml`:
- Remove `[tool.mypy]` section.
- Replace `mypy` with `pyright` in `[project.optional-dependencies].dev`.
- Add `[tool.pyright]` section:

```toml
[tool.pyright]
typeCheckingMode = "strict"
reportMissingTypeStubs = false
pythonVersion = "3.13"
include = ["src"]
```

**Step 2: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add pyright configuration"
```

### Task 2: Replace pre-commit hook

**Files:**
- Modify: `.pre-commit-config.yaml`

**Step 1: Write minimal implementation**

Update `.pre-commit-config.yaml`:
- Remove `pre-commit/mirrors-mypy` hook.
- Add `pyright` hook (e.g., `repo: https://github.com/RobertCraigie/pyright-python`).
- Keep `files: ^src/` and add `additional_dependencies` for runtime libs if needed.

**Step 2: Commit**

```bash
git add .pre-commit-config.yaml
git commit -m "chore: switch pre-commit to pyright"
```

### Task 3: Update documentation

**Files:**
- Modify: `AGENTS.md`

**Step 1: Write minimal implementation**

Update `AGENTS.md`:
- Replace mypy references with pyright.
- Update type check command to `pyright`.

**Step 2: Commit**

```bash
git add AGENTS.md
git commit -m "docs: update type checking to pyright"
```

### Task 4: Verification

**Files:**
- None

**Step 1: Run type checker**

Run: `pyright`
Expected: No errors.

**Step 2: Run pre-commit (optional)**

Run: `pre-commit run --all-files`
Expected: All hooks pass.
