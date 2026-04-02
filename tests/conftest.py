"""Shared fixtures for agent tests."""

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from core.config import AgentConfig, AppConfig, ProjectConfig, StorageConfig


@pytest.fixture(name="agent_config")
def fixture_agent_config() -> AgentConfig:
    """Fixture for agent configuration."""
    return AgentConfig(
        model_name="test-model",
        base_url="http://test-url",
        temperature=0.0,
        top_p=0.95,
        max_output_tokens=100,
    )


@pytest.fixture(name="app_config")
def fixture_app_config(agent_config: AgentConfig) -> AppConfig:
    """Fixture for app configuration."""
    return AppConfig(
        project=ProjectConfig(id="test-project", location="test-loc"),
        agents={"restrictor": agent_config},
        storage=StorageConfig(gcs_bucket="test-bucket"),
    )


@pytest.fixture
def mock_httpx_client() -> AsyncMock:
    """Mock an httpx.AsyncClient returning b'image_data'."""
    client = AsyncMock(spec=httpx.AsyncClient)
    response = AsyncMock()
    response.content = b"image_data"
    response.raise_for_status = MagicMock()
    client.get.return_value = response
    return client
