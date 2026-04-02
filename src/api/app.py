"""FastAPI application factory and lifespan for the API."""

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import cast

import httpx
from fastapi import FastAPI
from fastapi.requests import Request
from fastapi.responses import Response
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from agents.agent_runner import AgentRunner
from agents.chatbot import create_chat_agent
from api.dependencies import limiter
from api.routes import router
from core.config import load_config
from core.logger import setup_logger
from data_processing.gcs_processor import GCSChatStorage

_LLM_MAX_CONCURRENCY = 20

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI) -> AsyncIterator[None]:
    """Initialise shared resources once at startup and clean up on shutdown."""
    setup_logger(keep_loggers=["api", "agents", "data_processing", "core"])

    logger.info("Loading configuration...")
    config = load_config()
    fastapi_app.state.config = config

    logger.info(
        "Initialising restrictor agent (model: %s)...", config.agents["restrictor"].model_name
    )
    agent = create_chat_agent(config.agents)
    fastapi_app.state.agent_runner = AgentRunner(agent=agent, app_name="RestrictionCheckerAPI")
    fastapi_app.state.llm_semaphore = asyncio.Semaphore(_LLM_MAX_CONCURRENCY)
    fastapi_app.state.limiter = limiter
    fastapi_app.state.http_client = httpx.AsyncClient(
        limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        timeout=httpx.Timeout(30.0, connect=10.0),
    )
    chat_storage = GCSChatStorage(project=config.project.id, bucket=config.storage.gcs_bucket)
    fastapi_app.state.chat_storage = chat_storage

    logger.info("API ready.")
    yield

    await fastapi_app.state.http_client.aclose()
    logger.info("Shutting down.")


app = FastAPI(
    title="Restriction Checker API",
    description="Checks an image URL for restricted content using an LLM agent.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_exception_handler(
    RateLimitExceeded,
    cast(
        Callable[[Request, Exception], Response | Awaitable[Response]],
        _rate_limit_exceeded_handler,
    ),
)
app.include_router(router)
