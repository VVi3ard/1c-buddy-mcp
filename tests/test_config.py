import pytest
from pydantic import ValidationError

from onec_buddy_mcp.config import Settings


def test_token_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ONEC_AI_TOKEN", raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_defaults_and_secret_repr() -> None:
    settings = Settings(_env_file=None, ONEC_AI_TOKEN="secret-token")

    assert settings.ONEC_AI_BASE_URL == "https://code.1c.ai"
    assert settings.ONEC_AI_TIMEOUT == 30
    assert "secret-token" not in repr(settings)
    assert settings.authorization_headers() == {
        "Authorization": "secret-token",
    }
    assert settings.ONEC_AI_INCLUDE_LIMITATIONS is True


def test_base_url_trailing_slash_is_removed() -> None:
    settings = Settings(
        _env_file=None,
        ONEC_AI_TOKEN="secret-token",
        ONEC_AI_BASE_URL="https://example.test/",
    )

    assert settings.ONEC_AI_BASE_URL == "https://example.test"


def test_limitations_can_be_disabled_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ONEC_AI_INCLUDE_LIMITATIONS", "false")

    settings = Settings(_env_file=None, ONEC_AI_TOKEN="token")

    assert settings.ONEC_AI_INCLUDE_LIMITATIONS is False
