"""Module for loading configuration files."""

from __future__ import annotations

import logging
from pathlib import Path

import yaml
from google.genai import types
from pydantic import BaseModel, ConfigDict, Field, model_validator

logger = logging.getLogger(__name__)


_THINKING_LEVELS_BY_MODEL: dict[str, frozenset[types.ThinkingLevel]] = {
    "gemini-3.1-pro-preview": frozenset(
        {
            types.ThinkingLevel.LOW,
            types.ThinkingLevel.MEDIUM,
            types.ThinkingLevel.HIGH,
        }
    ),
}


class ProjectConfig(BaseModel):
    """Configuration for the project."""

    model_config = ConfigDict(frozen=True)

    id: str
    location: str


class AgentConfig(BaseModel):
    """Configuration for an individual agent."""

    model_config = ConfigDict(frozen=True)

    model_name: str
    base_url: str | None = None
    max_output_tokens: int | None = Field(default=None, gt=0)

    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    top_p: float | None = Field(default=None, ge=0.0, le=1.0)
    thinking_level: types.ThinkingLevel | None = None
    thinking_budget: int | None = Field(default=None, gt=-1)

    @model_validator(mode="after")
    def _validate_model_params(self) -> AgentConfig:
        if self.model_name.startswith("gemini-3.1"):
            for param, value in (
                ("temperature", self.temperature),
                ("top_p", self.top_p),
            ):
                if value is not None:
                    raise ValueError(
                        f"{param!r} must not be set for {self.model_name!r}; "
                        "use thinking_level instead."
                    )
        if self.model_name.startswith("gemini-2.5"):
            if self.thinking_level is not None:
                raise ValueError(f"thinking_level must not be set for {self.model_name!r}")
            if (
                self.max_output_tokens is not None
                and self.thinking_budget is not None
                and self.max_output_tokens <= self.thinking_budget
            ):
                raise ValueError(
                    f"max_output_tokens for {self.model_name!r} should be greater than"
                    " thinking_budget."
                )
        elif self.thinking_budget is not None:
            raise ValueError(
                f"thinking_budget is only supported for gemini-2.5 models, not {self.model_name!r}."
            )
        if self.thinking_level is not None:
            allowed = _THINKING_LEVELS_BY_MODEL.get(self.model_name)
            if allowed is None:
                raise ValueError(
                    f"thinking_level is not supported for {self.model_name!r}. "
                    f"Known models: {list(_THINKING_LEVELS_BY_MODEL.keys())}"
                )
            if self.thinking_level not in allowed:
                level_names = sorted(lv.value for lv in allowed)
                raise ValueError(
                    f"thinking_level={self.thinking_level.value!r} is not supported by "  # pylint: disable=no-member
                    f"{self.model_name!r}. Allowed: {level_names}"
                )
        return self


class StorageConfig(BaseModel):
    """Configuration for storage."""

    model_config = ConfigDict(frozen=True)

    gcs_bucket: str


class ApiConfig(BaseModel):
    """Configuration for the API."""

    model_config = ConfigDict(frozen=True)

    allowed_url_prefixes: list[str] = Field(default_factory=list)


class AppConfig(BaseModel):
    """Configuration for the entire application."""

    model_config = ConfigDict(frozen=True)

    project: ProjectConfig
    agents: dict[str, AgentConfig]
    storage: StorageConfig
    api: ApiConfig = Field(default_factory=ApiConfig)


def load_config(config_path: str = "configs/config.yaml") -> AppConfig:
    """Load configuration from a YAML file and validate it.

    Resolves *config_path* relative to the current working directory first,
    then falls back to the project root (two levels above this file).

    Args:
        config_path: Path to the YAML configuration file.

    Returns:
        Validated application configuration.

    Raises:
        FileNotFoundError: If the configuration file cannot be found.
    """
    path = Path(config_path)
    if not path.exists():
        root_path = Path(__file__).resolve().parent.parent.parent / config_path
        if root_path.exists():
            path = root_path
        else:
            raise FileNotFoundError(f"Config file not found at {config_path}")

    with path.open(encoding="utf-8") as f:
        raw_config = yaml.safe_load(f)

    logger.info("Loaded configuration from %s", path)
    return AppConfig(**raw_config)
