"""Environment-backed settings for the standalone MCP server."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration loaded from environment variables only."""

    model_config = SettingsConfigDict(
        case_sensitive=True,
        extra="ignore",
    )

    ONEC_AI_TOKEN: SecretStr = Field(description="1C.ai API token")
    ONEC_AI_BASE_URL: str = "https://code.1c.ai"
    ONEC_AI_TIMEOUT: int = Field(default=30, gt=0)
    ONEC_AI_UI_LANGUAGE: str = "russian"
    ONEC_AI_PROGRAMMING_LANGUAGE: str = ""
    DEFAULT_SSL_VERSION: str = ""
    DEFAULT_1C_CONFIGURATION: str = ""
    MCP_TOOL_INPUT_MIN_LENGTH: int = Field(default=4, ge=0)
    MCP_TOOL_INPUT_MAX_LENGTH: int = Field(default=100000, gt=0)
    MCP_TOOL_CALL_MODE: Literal["direct", "standard"] = "direct"
    ONEC_AI_INCLUDE_LIMITATIONS: bool = True

    @field_validator("ONEC_AI_BASE_URL")
    @classmethod
    def normalize_base_url(cls, value: str) -> str:
        normalized = value.strip().rstrip("/")
        if not normalized:
            raise ValueError("ONEC_AI_BASE_URL must not be empty")
        return normalized

    def authorization_headers(self) -> dict[str, str]:
        return {
            "Authorization": self.ONEC_AI_TOKEN.get_secret_value(),
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
