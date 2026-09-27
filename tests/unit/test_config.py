"""Unit tests for typed configuration loading and validation."""

import os
from unittest.mock import patch

from packages.core.config import Environment, PixelConfig


def test_default_configuration() -> None:
    config = PixelConfig()
    assert config.env == Environment.DEVELOPMENT
    assert config.port == 8000
    assert config.host == "127.0.0.1"
    assert config.strict_sandbox is True
    assert config.allow_network_tools is False


def test_configuration_from_environment() -> None:
    test_env = {
        "PIXEL_ENV": "production",
        "PIXEL_PORT": "9000",
        "PIXEL_HOST": "0.0.0.0",
        "PIXEL_LOG_LEVEL": "WARNING",
        "PIXEL_STRICT_SANDBOX": "true",
        "PIXEL_ALLOW_NETWORK_TOOLS": "true",
    }
    with patch.dict(os.environ, test_env, clear=True):
        config = PixelConfig.from_env()
        assert config.env == Environment.PRODUCTION
        assert config.port == 9000
        assert config.host == "0.0.0.0"
        assert config.log_level == "WARNING"
        assert config.strict_sandbox is True
        assert config.allow_network_tools is True


def test_invalid_env_falls_back_gracefully() -> None:
    test_env = {
        "PIXEL_ENV": "invalid_environment_name",
        "PIXEL_PORT": "not_a_number",
    }
    with patch.dict(os.environ, test_env, clear=True):
        config = PixelConfig.from_env()
        assert config.env == Environment.DEVELOPMENT
        assert config.port == 8000
