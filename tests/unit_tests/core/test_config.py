"""Unit tests for config file manager module."""

from unittest.mock import MagicMock, mock_open, patch

import pytest
from google.genai import types
from pydantic import ValidationError

from core.config import (
    AgentConfig,
    ApiConfig,
    AppConfig,
    ProjectConfig,
    StorageConfig,
    load_config,
)


class TestApiConfig:
    """Unit tests for ApiConfig."""

    def test_defaults(self) -> None:
        """Test default values are set correctly for ApiConfig."""
        config = ApiConfig()
        assert config.allowed_url_prefixes == []


class TestProjectConfig:  # pylint: disable=too-few-public-methods
    """Unit tests for ProjectConfig."""

    def test_defaults(self) -> None:
        """Test default values are set correctly for ProjectConfig."""
        config = ProjectConfig(id="test-project", location="us-central1")
        assert config.id == "test-project"
        assert config.location == "us-central1"


class TestStorageConfig:  # pylint: disable=too-few-public-methods
    """Unit tests for StorageConfig."""

    def test_defaults(self) -> None:
        """Test default values are set correctly for StorageConfig."""
        config = StorageConfig(gcs_bucket="test-bucket")
        assert config.gcs_bucket == "test-bucket"


class TestAgentConfig:
    """Unit tests for AgentConfig."""

    def test_defaults(self) -> None:
        """Test default values are set correctly for AgentConfig."""
        config = AgentConfig(model_name="gemini-pro")
        assert config.model_name == "gemini-pro"
        assert config.base_url is None
        assert config.temperature is None
        assert config.top_p is None
        assert config.thinking_level is None
        assert config.max_output_tokens is None

    def test_validation_bounds(self) -> None:
        """Test parameter bounds validation throws errors on invalid input."""
        with pytest.raises(ValidationError):
            AgentConfig(model_name="test-model", temperature=-0.1)

        with pytest.raises(ValidationError):
            AgentConfig(model_name="test-model", top_p=1.5)

        with pytest.raises(ValidationError):
            AgentConfig(model_name="test-model", max_output_tokens=0)

        config = AgentConfig(model_name="test-model", top_p=1.0)
        assert config.top_p == 1.0

    def test_thinking_level_unsupported_model(self) -> None:
        """Test that thinking_level is rejected for models not in _THINKING_LEVELS_BY_MODEL."""
        with pytest.raises(ValidationError, match="not supported for"):
            AgentConfig(model_name="gemini-1.5-pro", thinking_level=types.ThinkingLevel.LOW)

    def test_gemini31_rejects_standard_params(self) -> None:
        """Test that temperature/top_p are rejected for gemini-3.1 models."""
        with pytest.raises(ValidationError, match="must not be set"):
            AgentConfig(
                model_name="gemini-3.1-pro-preview",
                thinking_level=types.ThinkingLevel.LOW,
                temperature=0.5,
            )
        with pytest.raises(ValidationError, match="must not be set"):
            AgentConfig(model_name="gemini-3.1-pro-preview", top_p=0.9)

    def test_gemini31_allows_no_thinking_level(self) -> None:
        """Test that gemini-3.1 models can be configured without thinking_level."""
        config = AgentConfig(model_name="gemini-3.1-pro-preview")
        assert config.thinking_level is None

    def test_thinking_budget_rejected_for_non_gemini25(self) -> None:
        """Test that thinking_budget is not accepted outside of gemini-2.5 models."""
        with pytest.raises(ValidationError, match="thinking_budget is only supported"):
            AgentConfig(model_name="gemini-pro", thinking_budget=512)

    def test_thinking_level_unsupported_level(self) -> None:
        """Test thinking level validation when specific level is unsupported."""
        with pytest.raises(ValidationError, match="is not supported by"):
            AgentConfig(
                model_name="gemini-3.1-pro-preview", thinking_level=types.ThinkingLevel.MINIMAL
            )

    def test_thinking_level_invalid_string(self) -> None:
        """Test that a nonsense string for thinking_level raises ValidationError.

        Google's ThinkingLevel enum coerces unknown strings leniently (with a UserWarning),
        so the model_validator is what rejects it rather than field-level enum parsing.
        """
        with pytest.raises(ValidationError):
            AgentConfig(model_name="gemini-3.1-pro-preview", thinking_level="abcd")  # type: ignore[arg-type]

    def test_thinking_level_invalid_type(self) -> None:
        """Test that a non-string/non-enum value for thinking_level raises ValidationError."""
        with pytest.raises(ValidationError):
            AgentConfig(model_name="gemini-3.1-pro-preview", thinking_level=True)  # type: ignore[arg-type]

    def test_thinking_level_success(self) -> None:
        """Test successful thinking level configuration."""
        config = AgentConfig(
            model_name="gemini-3.1-pro-preview", thinking_level=types.ThinkingLevel.HIGH
        )
        assert config.thinking_level == types.ThinkingLevel.HIGH


class TestLoadConfig:
    """Unit tests for load_config function."""

    @patch("core.config.Path.exists")
    @patch(
        "core.config.Path.open",
        new_callable=mock_open,
        read_data=(
            "project:\n"
            "  id: test-proj\n"
            "  location: us-west1\n"
            "agents:\n"
            "  default:\n"
            "    model_name: test-model\n"
            "storage:\n"
            "  gcs_bucket: test-bucket\n"
            "api:\n"
            "  allowed_url_prefixes:\n"
            "    - 'https://example.com/foo/'\n"
        ),
    )
    def test_load_config_success(  # pylint: disable=unused-argument
        self, mocking_open: MagicMock, mock_exists: MagicMock
    ) -> None:
        """Test successful loading of configuration."""
        mock_exists.return_value = True

        config = load_config("config.yaml")

        assert isinstance(config, AppConfig)
        assert config.project.id == "test-proj"
        assert config.agents["default"].model_name == "test-model"
        assert config.api.allowed_url_prefixes == ["https://example.com/foo/"]
        assert config.storage.gcs_bucket == "test-bucket"

    @patch("core.config.Path.exists")
    @patch(
        "core.config.Path.open",
        new_callable=mock_open,
        read_data=(
            "project:\n"
            "  id: root-proj\n"
            "  location: us-west1\n"
            "agents:\n"
            "  default:\n"
            "    model_name: test-model\n"
            "storage:\n"
            "  gcs_bucket: fallback-bucket\n"
        ),
    )
    def test_load_config_fallback_path(  # pylint: disable=unused-argument
        self, mocking_open: MagicMock, mock_exists: MagicMock
    ) -> None:
        """Test loading configuration when falling back to root path."""
        mock_exists.side_effect = [False, True]

        config = load_config("config.yaml")
        assert config.project.id == "root-proj"
        assert config.api.allowed_url_prefixes == []
        assert config.storage.gcs_bucket == "fallback-bucket"

    @patch("core.config.Path.exists")
    def test_load_config_file_not_found(self, mock_exists: MagicMock) -> None:
        """Test loading configuration when file is not found."""
        mock_exists.side_effect = [False, False]

        with pytest.raises(FileNotFoundError):
            load_config("missing.yaml")
