"""Performance tests for configuration loading and Pydantic validation."""

import textwrap
from pathlib import Path
from typing import Any

from agents.restrictor import RestrictorItemResponse
from api.models import ChatInteraction, ChatRequest, ChatResponse, CheckResponse
from core.config import AgentConfig, AppConfig, load_config

CONFIG_LOAD_MAX_MEAN = 0.050  # 50 ms
SCHEMA_VALIDATION_MAX_MEAN = 0.010  # 10 ms
CHAT_MODEL_VALIDATION_MAX_MEAN = 0.010  # 10 ms


class TestConfigLoading:  # pylint: disable=too-few-public-methods
    """Benchmark `load_config` from a YAML file."""

    def test_load_config(self, benchmark: Any, assert_max_mean: Any, tmp_path: Path) -> None:
        """YAML round-trip: disk to validated `AppConfig`."""
        config_yaml = textwrap.dedent("""\
            project:
              id: perf-test-project
              location: us-central1
            storage:
              gcs_bucket: perf-test-bucket
            api:
              allowed_url_prefixes:
                - https://valid.com/
            agents:
              qa:
                model_name: gemini-2.5-flash
                temperature: 0.0
                top_p: 0.5
                max_output_tokens: 1536
              restrictor:
                model_name: gemini-2.5-pro
                temperature: 0.0
                top_p: 0.5
                max_output_tokens: 512
        """)
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_yaml)

        result = benchmark(load_config, str(config_file))

        assert isinstance(result, AppConfig)
        assert "restrictor" in result.agents
        assert_max_mean(benchmark, CONFIG_LOAD_MAX_MEAN)


class TestSchemaValidation:
    """Benchmark Pydantic `model_validate` for various schemas."""

    def test_restrictor_response_validation(self, benchmark: Any, assert_max_mean: Any) -> None:
        """Validate the LLM response schema."""
        data = {
            "found": True,
            "item": "Weapon",
            "reasoning": "The image clearly shows a realistic-looking handgun.",
        }

        result = benchmark(RestrictorItemResponse.model_validate, data)

        assert result.found is True
        assert result.item == "Weapon"
        assert_max_mean(benchmark, SCHEMA_VALIDATION_MAX_MEAN)

    def test_agent_config_validation(self, benchmark: Any, assert_max_mean: Any) -> None:
        """Validate the agent configuration schema."""
        data = {
            "model_name": "gemini-2.5-pro",
            "temperature": 0.5,
            "top_p": 0.8,
            "thinking_budget": 512,
            "max_output_tokens": 1024,
        }

        result = benchmark(AgentConfig.model_validate, data)

        assert result.model_name == "gemini-2.5-pro"
        assert_max_mean(benchmark, SCHEMA_VALIDATION_MAX_MEAN)

    def test_full_app_config_validation(self, benchmark: Any, assert_max_mean: Any) -> None:
        """Validate the complete `AppConfig` from a raw dict."""
        data = {
            "project": {"id": "test-proj", "location": "eu-west1"},
            "storage": {"gcs_bucket": "test-bucket"},
            "api": {"allowed_url_prefixes": ["https://valid.com/"]},
            "agents": {
                "qa": {
                    "model_name": "gemini-2.5-flash",
                    "temperature": 0.0,
                    "top_p": 0.5,
                    "thinking_budget": 512,
                    "max_output_tokens": 1536,
                },
                "restrictor": {
                    "model_name": "gemini-2.5-pro",
                    "temperature": 0.0,
                    "top_p": 0.5,
                    "thinking_budget": 0,
                    "max_output_tokens": 512,
                },
            },
        }

        result = benchmark(AppConfig.model_validate, data)

        assert isinstance(result, AppConfig)
        assert "qa" in result.agents
        assert "restrictor" in result.agents
        assert_max_mean(benchmark, SCHEMA_VALIDATION_MAX_MEAN)


class TestApiModelValidation:
    """Benchmark Pydantic validation for the new chat API request/response models."""

    def test_chat_request_validation(self, benchmark: Any, assert_max_mean: Any) -> None:
        """Validate the incoming `ChatRequest` schema."""
        data = {
            "message": "Can you check this image? https://valid.com/img.png",
            "session_id": "abc-123",
        }

        result = benchmark(ChatRequest.model_validate, data)

        assert result.message.startswith("Can you check")
        assert result.session_id == "abc-123"
        assert_max_mean(benchmark, CHAT_MODEL_VALIDATION_MAX_MEAN)

    def test_chat_response_with_restriction_validation(
        self, benchmark: Any, assert_max_mean: Any
    ) -> None:
        """Validate `ChatResponse` when a restriction block is present."""
        data = {
            "reply": "I checked the image.",
            "session_id": "abc-123",
            "restriction": {"found": True, "item": "Knife", "reasoning": "Blade visible."},
        }

        result = benchmark(ChatResponse.model_validate, data)

        assert result.restriction is not None
        assert result.restriction.found is True
        assert_max_mean(benchmark, CHAT_MODEL_VALIDATION_MAX_MEAN)

    def test_chat_response_without_restriction_validation(
        self, benchmark: Any, assert_max_mean: Any
    ) -> None:
        """Validate `ChatResponse` when no restriction block is returned (text-only reply)."""
        data = {"reply": "We open at 9am.", "session_id": "abc-123", "restriction": None}

        result = benchmark(ChatResponse.model_validate, data)

        assert result.restriction is None
        assert_max_mean(benchmark, CHAT_MODEL_VALIDATION_MAX_MEAN)

    def test_chat_interaction_validation(self, benchmark: Any, assert_max_mean: Any) -> None:
        """Validate `ChatInteraction` as stored in GCS chat history."""
        data = {
            "message": "Is this image ok?",
            "reply": "No restricted items found.",
            "restriction": {"found": False, "item": "Ok", "reasoning": "Image is clean."},
            "timestamp": "2026-03-16T10:00:00",
        }

        result = benchmark(ChatInteraction.model_validate, data)

        assert result.restriction is not None
        assert result.restriction.found is False
        assert_max_mean(benchmark, CHAT_MODEL_VALIDATION_MAX_MEAN)

    def test_check_response_validation(self, benchmark: Any, assert_max_mean: Any) -> None:
        """Validate the standalone `CheckResponse` (restriction block)."""
        data = {"found": False, "item": "Ok", "reasoning": "Image is clean."}

        result = benchmark(CheckResponse.model_validate, data)

        assert result.found is False
        assert_max_mean(benchmark, CHAT_MODEL_VALIDATION_MAX_MEAN)
