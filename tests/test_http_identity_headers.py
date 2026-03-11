"""Tests for outbound HTTP identity header construction."""

from pytest import MonkeyPatch

from refweaver.http_identity import (
    build_crossref_user_agent,
    build_openrouter_identity_headers,
    validate_http_identity_config,
)
from refweaver.models import Article


def test_openrouter_identity_headers_use_env_overrides(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("REFWEAVER_HTTP_REFERER", "https://refweaver.example/agent")
    monkeypatch.setenv("REFWEAVER_HTTP_TITLE", "RefWeaver Test Client")

    headers = build_openrouter_identity_headers()

    assert headers["HTTP-Referer"] == "https://refweaver.example/agent"
    assert headers["X-Title"] == "RefWeaver Test Client"


def test_crossref_user_agent_uses_contact_email_env_override(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("REFWEAVER_CONTACT_EMAIL", "ops@example.org")

    captured: dict[str, object] = {}

    class _CrossrefResponse:
        text = "@article{x,title={Updated title},author={Doe, Jane},year={2024}}"

        def raise_for_status(self) -> None:
            return None

    def fake_get(url: str, headers: dict[str, str], timeout: float) -> _CrossrefResponse:
        captured["headers"] = headers
        return _CrossrefResponse()

    monkeypatch.setattr("requests.get", fake_get)
    monkeypatch.setattr("refweaver.rate_limit.rate_limit", lambda *_: None)

    article = Article(
        source="openalex",
        external_id="W1",
        title="Original",
        authors=["A"],
        doi="10.1000/test",
    )

    enriched = article.enrich_from_crossref()

    headers = captured["headers"]
    assert isinstance(headers, dict)
    assert headers["User-Agent"] == build_crossref_user_agent()
    assert enriched.title == "Updated title"


def test_validate_http_identity_config_warns_on_default_placeholders(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.delenv("REFWEAVER_HTTP_REFERER", raising=False)
    monkeypatch.delenv("REFWEAVER_CONTACT_EMAIL", raising=False)

    warnings: list[str] = []

    def fake_warning(message: str, *_args: object, **_kwargs: object) -> None:
        warnings.append(message)

    monkeypatch.setattr("refweaver.http_identity.logger.warning", fake_warning)

    validate_http_identity_config()

    assert len(warnings) == 3
    assert any("REFWEAVER_HTTP_REFERER" in warning for warning in warnings)
    assert any("REFWEAVER_CONTACT_EMAIL" in warning for warning in warnings)
