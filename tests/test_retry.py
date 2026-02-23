"""Tests for retry utilities."""

from __future__ import annotations

from typing import Any

import pytest

from refweaver.retry import retry_call


def test_retry_call_succeeds_after_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []

    def flaky() -> str:
        calls.append(1)
        if len(calls) < 2:
            raise RuntimeError("boom")
        return "ok"

    sleeps: list[float] = []

    def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr("refweaver.retry.time.sleep", fake_sleep)
    monkeypatch.setattr("refweaver.retry.random.uniform", lambda *_: 0.0)

    result = retry_call(flaky, retries=2, base_delay=0.5, jitter=0.1)

    assert result == "ok"
    assert len(calls) == 2
    assert sleeps == [0.5]


def test_retry_call_raises_after_exhaustion(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []

    def always_fail() -> None:
        calls.append(1)
        raise ValueError("nope")

    sleeps: list[float] = []

    def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr("refweaver.retry.time.sleep", fake_sleep)
    monkeypatch.setattr("refweaver.retry.random.uniform", lambda *_: 0.0)

    with pytest.raises(ValueError):
        retry_call(always_fail, retries=2, base_delay=1.0, jitter=0.1)

    assert len(calls) == 3
    assert sleeps == [1.0, 2.0]


def test_retry_call_only_retries_selected_exceptions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[int] = []

    class CustomError(RuntimeError):
        pass

    def fail_with_type() -> None:
        calls.append(1)
        raise CustomError("no retry")

    monkeypatch.setattr("refweaver.retry.time.sleep", lambda _delay: None)

    with pytest.raises(CustomError):
        retry_call(fail_with_type, retries=2, exceptions=(ValueError,))

    assert len(calls) == 1


def test_retry_call_passes_args_kwargs(monkeypatch: pytest.MonkeyPatch) -> None:
    def echo(a: int, b: int, *, c: int) -> tuple[int, int, int]:
        return a, b, c

    monkeypatch.setattr("refweaver.retry.time.sleep", lambda _delay: None)

    result = retry_call(echo, 1, 2, c=3)

    assert result == (1, 2, 3)
