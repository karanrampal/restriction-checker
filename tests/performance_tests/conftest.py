"""Shared fixtures for performance tests."""

import asyncio
import io
from collections.abc import Callable, Generator
from typing import Any, Self
from unittest.mock import MagicMock, patch

import pytest
from google.genai import types
from PIL import Image

from agents.agent_runner import AgentRunner
from data_processing.image_processor import ImageType


def _solid_image(width: int, height: int, fmt: str = "PNG") -> bytes:
    """Return bytes for a solid-colour test image."""
    img = Image.new("RGB", (width, height), color=(200, 100, 50))
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


def _noisy_image(width: int, height: int, fmt: str = "PNG") -> bytes:
    """Return bytes for an image with a deterministic cyclic gradient.

    The repeating 0-255 pattern produces a larger compressed file than a
    solid colour, which is useful for triggering the downscaler.
    """
    pixel_count = width * height * 3
    pattern = bytes(range(256))
    raw = (pattern * (pixel_count // 256 + 1))[:pixel_count]
    img = Image.frombytes("RGB", (width, height), raw)
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


@pytest.fixture
def assert_max_mean() -> Callable[[Any, float], None]:
    """Fixture returning a callable that asserts benchmark mean < threshold.

    Gracefully skips the assertion when stats are unavailable (e.g.
    when running with `--benchmark-disable`).

    Usage::

        def test_example(benchmark, assert_max_mean):
            benchmark(my_func)
            assert_max_mean(benchmark, 0.200)
    """

    def _check(benchmark: Any, threshold: float) -> None:
        try:
            stats = benchmark.stats
            if stats is None:
                return
            mean: float | None = stats.get("mean")
            if mean is not None:
                assert mean < threshold, f"Mean {mean:.4f}s exceeds threshold {threshold:.4f}s"
        except (AttributeError, TypeError, KeyError):
            pass

    return _check


@pytest.fixture
def small_png_bytes() -> bytes:
    """100 x 100 solid-colour PNG."""
    return _solid_image(100, 100, "PNG")


@pytest.fixture
def medium_png_bytes() -> bytes:
    """1 000 x 1 000 solid-colour PNG."""
    return _solid_image(1000, 1000, "PNG")


@pytest.fixture
def large_png_bytes() -> bytes:
    """4 000 x 4 000 solid-colour PNG."""
    return _solid_image(4000, 4000, "PNG")


@pytest.fixture
def small_bmp_bytes() -> bytes:
    """100 x 100 BMP (needs format conversion)."""
    return _solid_image(100, 100, "BMP")


@pytest.fixture
def noisy_png_bytes() -> bytes:
    """1 000 x 1 000 PNG with a cyclic gradient (larger compressed size)."""
    return _noisy_image(1000, 1000, "PNG")


@pytest.fixture
def sample_image() -> ImageType:
    """Minimal `ImageType` for agent-runner benchmarks."""
    return ImageType(
        id="perf-test-img",
        url="http://example.com/test.jpg",
        part=types.Part.from_bytes(data=b"fake-image-data", mime_type="image/jpeg"),
    )


@pytest.fixture(name="mock_final_event")
def fixture_mock_final_event() -> MagicMock:
    """Mock ADK event representing a successful final response."""
    event = MagicMock()
    event.is_final_response.return_value = True

    part = MagicMock()
    part.thought = False
    part.text = (
        '{"answer": "No restricted items found.", "url": "", '
        '"found": false, "item": "Ok", "reasoning": "No restricted items found."}'
    )

    event.content.parts = [part]
    event.actions = None

    return event


@pytest.fixture
def agent_runner_factory(mock_final_event: MagicMock) -> Callable[..., AgentRunner]:
    """Factory that creates an `AgentRunner` with a fully mocked LLM.

    Usage::

        def test_example(agent_runner_factory, sample_image):
            runner = agent_runner_factory()
            # runner.run(...) returns instantly without calling any LLM
    """

    def _create(**runner_kwargs: Any) -> AgentRunner:
        class _FakeAsyncIter:
            """Async iterator that yields a single event then stops.

            Unlike a bare `async def … yield` generator, this class
            has a synchronous (no-op) `aclose` so asyncio never warns
            about an un-awaited coroutine.
            """

            def __init__(self) -> None:
                self._done = False

            def __aiter__(self) -> Self:
                return self

            async def __anext__(self) -> MagicMock:
                if self._done:
                    raise StopAsyncIteration
                self._done = True
                return mock_final_event

            def aclose(self) -> None:
                """No-op close so asyncio skips the coroutine path."""

        def _fake_run_async(**_kw: Any) -> _FakeAsyncIter:
            """Return a fake async iterator mimicking `Runner.run_async`."""
            return _FakeAsyncIter()

        with patch("agents.agent_runner.Runner") as patched:
            patched.return_value.run_async = _fake_run_async
            return AgentRunner(
                agent=MagicMock(),
                app_name="perf-test",
                timeout=10.0,
                **runner_kwargs,
            )

    return _create


@pytest.fixture
def bench_loop() -> Generator[asyncio.AbstractEventLoop]:
    """Dedicated `asyncio` event loop for benchmark tests.

    We create our own loop instead of relying on `pytest-asyncio`
    because `pytest-benchmark` expects synchronous callables.
    """
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
