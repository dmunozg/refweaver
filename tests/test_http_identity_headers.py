"""Tests for outbound HTTP identity header construction."""

from refweaver.http_identity import (
    build_crossref_user_agent,
    build_openrouter_identity_headers,
)
from refweaver.models import Article


def test_openrouter_identity_headers_use_env_overrides(monkeypatch):
    monkeypatch.setenv("REFWEAVER_HTTP_REFERER", "https://refweaver.example/agent")
    monkeypatch.setenv("REFWEAVER_HTTP_TITLE", "RefWeaver Test Client")

    headers = build_openrouter_identity_headers()

    assert headers["HTTP-Referer"] == "https://refweaver.example/agent"
    assert headers["X-Title"] == "RefWeaver Test Client"


def test_crossref_user_agent_uses_contact_email_env_override(monkeypatch):
    monkeypatch.setenv("REFWEAVER_CONTACT_EMAIL", "ops@example.org")

    captured: dict[str, object] = {}

    class _CrossrefResponse:
        text = "@article{x,title={Updated title},author={Doe, Jane},year={2024}}"

        def raise_for_status(self) -> None:
            return None

    def fake_get(url, headers, timeout):
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
