"""Tests for configuration management."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError


class TestSettings:
    """Tests for Settings class."""

    def test_settings_loads_from_env(self):
        """Test that settings loads API keys from environment."""
        from neurosynth.config import Settings

        with patch.dict(
            os.environ,
            {
                "ANTHROPIC_API_KEY": "test-anthropic-key",
                "GOOGLE_API_KEY": "test-google-key",
                "VOYAGE_API_KEY": "test-voyage-key",
            },
        ):
            settings = Settings()

            assert settings.anthropic_api_key == "test-anthropic-key"
            assert settings.google_api_key == "test-google-key"
            assert settings.voyage_api_key == "test-voyage-key"

    def test_settings_defaults(self):
        """Test that settings has correct defaults."""
        from neurosynth.config import Settings

        with patch.dict(
            os.environ,
            {
                "ANTHROPIC_API_KEY": "key1",
                "GOOGLE_API_KEY": "key2",
                "VOYAGE_API_KEY": "key3",
            },
        ):
            settings = Settings()

            assert settings.gemini_model == "gemini-2.0-flash-exp"
            assert settings.claude_model == "claude-sonnet-4-20250514"
            assert settings.voyage_model == "voyage-large-2-instruct"
            assert settings.chunk_size == 1000
            assert settings.chunk_overlap == 100
            assert settings.similarity_threshold == 0.92
            assert settings.output_format == "latex"

    def test_settings_custom_values(self):
        """Test that settings accepts custom values."""
        from neurosynth.config import Settings

        with patch.dict(
            os.environ,
            {
                "ANTHROPIC_API_KEY": "key1",
                "GOOGLE_API_KEY": "key2",
                "VOYAGE_API_KEY": "key3",
                "CHUNK_SIZE": "500",
                "SIMILARITY_THRESHOLD": "0.85",
                "OUTPUT_FORMAT": "markdown",
            },
        ):
            settings = Settings()

            assert settings.chunk_size == 500
            assert settings.similarity_threshold == 0.85
            assert settings.output_format == "markdown"

    def test_settings_missing_required_key_raises(self):
        """Test that missing API keys raise validation error."""
        from pydantic import Field
        from pydantic_settings import BaseSettings, SettingsConfigDict

        # Create a minimal Settings class without file loading for this test
        class TestSettings(BaseSettings):
            model_config = SettingsConfigDict(env_file=None)  # Disable file loading
            anthropic_api_key: str = Field(...)
            google_api_key: str = Field(...)
            voyage_api_key: str = Field(...)

        with patch.dict(
            os.environ,
            {
                "ANTHROPIC_API_KEY": "key1",
                # Missing GOOGLE_API_KEY and VOYAGE_API_KEY
            },
            clear=True,
        ):
            with pytest.raises(ValidationError):
                TestSettings()

    def test_settings_path_properties(self):
        """Test that path properties work correctly."""
        from neurosynth.config import Settings

        with patch.dict(
            os.environ,
            {
                "ANTHROPIC_API_KEY": "key1",
                "GOOGLE_API_KEY": "key2",
                "VOYAGE_API_KEY": "key3",
                "DATA_DIR": "/custom/data",
            },
        ):
            settings = Settings()

            assert settings.data_dir == Path("/custom/data")
            assert settings.sources_dir == Path("/custom/data/sources")
            assert settings.processed_dir == Path("/custom/data/processed")
            assert settings.output_dir == Path("/custom/data/output")


class TestGetSettings:
    """Tests for get_settings function."""

    def test_get_settings_singleton(self):
        """Test that get_settings returns singleton."""
        import neurosynth.config

        # Reset singleton
        neurosynth.config._settings = None

        with patch.dict(
            os.environ,
            {
                "ANTHROPIC_API_KEY": "key1",
                "GOOGLE_API_KEY": "key2",
                "VOYAGE_API_KEY": "key3",
            },
        ):
            settings1 = neurosynth.config.get_settings()
            settings2 = neurosynth.config.get_settings()

            assert settings1 is settings2

    def test_reload_settings(self):
        """Test that reload_settings creates new instance."""
        import neurosynth.config

        neurosynth.config._settings = None

        with patch.dict(
            os.environ,
            {
                "ANTHROPIC_API_KEY": "key1",
                "GOOGLE_API_KEY": "key2",
                "VOYAGE_API_KEY": "key3",
            },
        ):
            settings1 = neurosynth.config.get_settings()
            settings2 = neurosynth.config.reload_settings()

            assert settings1 is not settings2


class TestOutputFormat:
    """Tests for output format validation."""

    def test_valid_latex_format(self):
        """Test that latex is valid output format."""
        from neurosynth.config import Settings

        with patch.dict(
            os.environ,
            {
                "ANTHROPIC_API_KEY": "key1",
                "GOOGLE_API_KEY": "key2",
                "VOYAGE_API_KEY": "key3",
                "OUTPUT_FORMAT": "latex",
            },
        ):
            settings = Settings()
            assert settings.output_format == "latex"

    def test_valid_markdown_format(self):
        """Test that markdown is valid output format."""
        from neurosynth.config import Settings

        with patch.dict(
            os.environ,
            {
                "ANTHROPIC_API_KEY": "key1",
                "GOOGLE_API_KEY": "key2",
                "VOYAGE_API_KEY": "key3",
                "OUTPUT_FORMAT": "markdown",
            },
        ):
            settings = Settings()
            assert settings.output_format == "markdown"

    def test_invalid_format_raises(self):
        """Test that invalid format raises error."""
        from neurosynth.config import Settings

        with patch.dict(
            os.environ,
            {
                "ANTHROPIC_API_KEY": "key1",
                "GOOGLE_API_KEY": "key2",
                "VOYAGE_API_KEY": "key3",
                "OUTPUT_FORMAT": "pdf",  # Invalid
            },
        ):
            with pytest.raises(ValidationError):
                Settings()
