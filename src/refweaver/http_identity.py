"""Helpers for normalized outbound HTTP identity headers."""

import os

from loguru import logger

DEFAULT_HTTP_REFERER = "https://example.com/refweaver"
DEFAULT_CONTACT_EMAIL = "contact@example.com"
DEFAULT_HTTP_TITLE = "RefWeaver Academic Search"


def _get_env_str(name: str, default: str) -> str:
    """Read an environment variable with whitespace trimming and fallback."""
    raw = os.getenv(name)
    if not raw:
        return default

    value = raw.strip()
    return value or default


def get_http_referer() -> str:
    """Return the outbound HTTP referer identity value."""
    return _get_env_str("REFWEAVER_HTTP_REFERER", DEFAULT_HTTP_REFERER)


def get_contact_email() -> str:
    """Return the outbound contact email identity value."""
    return _get_env_str("REFWEAVER_CONTACT_EMAIL", DEFAULT_CONTACT_EMAIL)


def build_crossref_user_agent() -> str:
    """Build a User-Agent string that includes a contact email."""
    return f"RefWeaver/1.0 (mailto:{get_contact_email()})"


def get_http_title() -> str:
    """Return the outbound HTTP title identity value."""
    return _get_env_str("REFWEAVER_HTTP_TITLE", DEFAULT_HTTP_TITLE)


def build_openrouter_identity_headers() -> dict[str, str]:
    """Build identity headers required/recommended by OpenRouter."""
    return {"HTTP-Referer": get_http_referer(), "X-Title": get_http_title()}


def validate_http_identity_config() -> None:
    """Warn when outbound HTTP identity settings still use placeholder defaults."""
    if get_http_referer() == DEFAULT_HTTP_REFERER:
        logger.warning(
            "REFWEAVER_HTTP_REFERER is using placeholder default '{}'; set it to your project URL",
            DEFAULT_HTTP_REFERER,
        )

    if get_http_title() == DEFAULT_HTTP_TITLE:
        logger.warning(
            "REFWEAVER_HTTP_TITLE is using default '{}'; set it to your client/app name",
            DEFAULT_HTTP_TITLE,
        )

    if get_contact_email() == DEFAULT_CONTACT_EMAIL:
        logger.warning(
            "REFWEAVER_CONTACT_EMAIL is using placeholder default '{}'; set it to a monitored contact email",
            DEFAULT_CONTACT_EMAIL,
        )
