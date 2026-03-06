# Sentence Serialization Guard Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Guard sentence serialization in `analyze_paragraph_job` so non-`Sentence` values are safely serialized as strings.

**Architecture:** Add a type guard before calling `Sentence.model_dump`. Preserve the existing structured payload for `Sentence` instances while falling back to `str(sentence)` for rare non-`Sentence` values.

**Tech Stack:** Python, pytest, Pydantic.

---

### Task 1: Add a failing test for non-Sentence serialization

**Files:**
- Modify: `tests/test_jobs.py`

**Step 1: Write the failing test**

```python
def test_analyze_paragraph_job_serializes_non_sentence(monkeypatch) -> None:
    def fake_analyze_paragraph_with_evidence(_paragraph: str):
        class FakeVerdict:
            def model_dump(self, mode: str):
                assert mode == "json"
                return {"label": "ok"}

        class FakeEvaluation:
            def model_dump(self, mode: str):
                assert mode == "json"
                return {"source": "fake"}

        return [("Not a sentence", FakeVerdict(), [FakeEvaluation()])]

    monkeypatch.setattr(
        jobs, "analyze_paragraph_with_evidence", fake_analyze_paragraph_with_evidence
    )

    response = jobs.analyze_paragraph_job(
        "Example paragraph.",
        run_id="run-1",
        user_id="user-1",
        include_markdown=False,
    )

    assert response["results"][0]["sentence"] == "Not a sentence"
    assert response["results"][0]["sentence_for_evaluation"] == "Not a sentence"
    assert response["results"][0]["sentence_original_text"] == "Not a sentence"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_jobs.py::test_analyze_paragraph_job_serializes_non_sentence -v`

Expected: FAIL due to `model_dump` being called on a `str`.

**Step 3: Commit**

```bash
git add tests/test_jobs.py
git commit -m "test: cover non-sentence job serialization"
```

### Task 2: Guard sentence serialization

**Files:**
- Modify: `src/refweaver/jobs.py`

**Step 1: Write minimal implementation**

```python
        if isinstance(sentence, Sentence):
            sentence_payload = sentence.model_dump(mode="json")
            sentence_for_evaluation = sentence.sentence_with_context or sentence.text
            sentence_original_text = sentence.text
        else:
            sentence_for_evaluation = str(sentence)
            sentence_original_text = sentence_for_evaluation
            sentence_payload = sentence_for_evaluation
```

**Step 2: Run test to verify it passes**

Run: `pytest tests/test_jobs.py::test_analyze_paragraph_job_serializes_non_sentence -v`

Expected: PASS

**Step 3: Commit**

```bash
git add src/refweaver/jobs.py
git commit -m "fix: guard sentence serialization in jobs"
```

### Task 3: Full test suite

**Files:**
- None

**Step 1: Run full suite**

Run: `pytest`

Expected: PASS
