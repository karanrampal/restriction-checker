"""Shared fixtures for API unit tests."""

import asyncio
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

import httpx
import pytest
import pytest_asyncio

from agents.agent_runner import AgentRunner
from api.app import app
from core.config import ApiConfig, AppConfig, ProjectConfig, StorageConfig


@pytest.fixture(name="mock_agent_runner")
def fixture_agent_runner() -> AsyncMock:
    """AgentRunner substitute with a default passing chat response."""
    runner = AsyncMock(spec=AgentRunner)
    runner.run.return_value = '{"answer": "No issue found.", "url": ""}'
    return runner


@pytest_asyncio.fixture
async def api_client(mock_agent_runner: AsyncMock) -> AsyncGenerator[httpx.AsyncClient]:
    """AsyncClient pointed at the FastAPI app with app.state injected directly.

    `httpx.ASGITransport` does not trigger the FastAPI lifespan, so all
    state that route handlers and dependencies read from `request.app.state`
    must be set up here, before requests are sent.
    """
    app.state.agent_runner = mock_agent_runner
    app.state.llm_semaphore = asyncio.Semaphore(20)
    app.state.http_client = AsyncMock(spec=httpx.AsyncClient)
    app.state.chat_storage = AsyncMock()
    app.state.config = AppConfig(
        project=ProjectConfig(id="test", location="test"),
        agents={},
        storage=StorageConfig(gcs_bucket="test-bucket"),
        api=ApiConfig(allowed_url_prefixes=["https://example.com/"]),
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client

    # Remove injected state so tests are fully isolated from each other.
    del app.state.agent_runner
    del app.state.llm_semaphore
    del app.state.http_client
    del app.state.chat_storage
    del app.state.config
