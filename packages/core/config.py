"""Typed Configuration Management for PIXEL Runtime."""

import os
from enum import StrEnum

from pydantic import BaseModel, Field


class Environment(StrEnum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"


class PixelConfig(BaseModel):
    """Immutable runtime configuration parsed from environment variables."""
    env: Environment = Field(default=Environment.DEVELOPMENT)
    host: str = Field(default="127.0.0.1")
    port: int = Field(default=8000, ge=1024, le=65535)
    log_level: str = Field(default="INFO")
    secret_key: str = Field(default="dev-insecure-secret-key-replace-in-production")

    # Persistence
    database_url: str = Field(default="sqlite+aiosqlite:///./data/pixel.db")
    redis_url: str = Field(default="redis://localhost:6379/0")

    # Voice defaults
    vad_mode: str = Field(default="silero")
    stt_provider: str = Field(default="faster-whisper")
    tts_provider: str = Field(default="kokoro")
    default_language: str = Field(default="hi-Latn")

    # Security & Policy
    strict_sandbox: bool = Field(default=True)
    allow_network_tools: bool = Field(default=False)

    @classmethod
    def from_env(cls) -> "PixelConfig":
        """Loads configuration from environment variables with safe defaults."""
        raw_env = os.getenv("PIXEL_ENV", "development").lower()
        try:
            env = Environment(raw_env)
        except ValueError:
            env = Environment.DEVELOPMENT

        try:
            port = int(os.getenv("PIXEL_PORT", "8000"))
        except ValueError:
            port = 8000

        return cls(
            env=env,
            host=os.getenv("PIXEL_HOST", "127.0.0.1"),
            port=port,
            log_level=os.getenv("PIXEL_LOG_LEVEL", "INFO").upper(),
            secret_key=os.getenv("PIXEL_SECRET_KEY", "dev-insecure-secret-key-replace-in-production"),
            database_url=os.getenv("PIXEL_DATABASE_URL", "sqlite+aiosqlite:///./data/pixel.db"),
            redis_url=os.getenv("PIXEL_REDIS_URL", "redis://localhost:6379/0"),
            vad_mode=os.getenv("PIXEL_VAD_MODE", "silero"),
            stt_provider=os.getenv("PIXEL_STT_PROVIDER", "faster-whisper"),
            tts_provider=os.getenv("PIXEL_TTS_PROVIDER", "kokoro"),
            default_language=os.getenv("PIXEL_DEFAULT_LANGUAGE", "hi-Latn"),
            strict_sandbox=os.getenv("PIXEL_STRICT_SANDBOX", "true").lower() in ["1", "true", "yes"],
            allow_network_tools=os.getenv("PIXEL_ALLOW_NETWORK_TOOLS", "false").lower() in ["1", "true", "yes"],
        )
