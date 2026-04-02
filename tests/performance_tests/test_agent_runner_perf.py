"""Performance tests for AgentRunner orchestration overhead."""

import asyncio
from collections.abc import Callable
from typing import Any

from agents.agent_runner import AgentRunner
from data_processing.image_processor import ImageType

SINGLE_RUN_MAX_MEAN = 0.200  # 200 ms
CONCURRENT_10_MAX_MEAN = 1.000  # 1 s for 10 parallel runs

_SAMPLE_MESSAGE = "What are your opening hours?"


class TestSingleRunLatency:  # pylint: disable=too-few-public-methods
    """Benchmark a single `AgentRunner.run()` with a mocked LLM."""

    def test_single_run(
        self,
        benchmark: Any,
        assert_max_mean: Any,
        agent_runner_factory: Callable[..., AgentRunner],
        sample_image: ImageType,
        bench_loop: asyncio.AbstractEventLoop,
    ) -> None:
        """Orchestration overhead for one image should stay below threshold."""
        runner = agent_runner_factory()

        def run_once() -> str:
            return bench_loop.run_until_complete(
                runner.run(user_id="u", session_id="s", user_input=sample_image)
            )

        result = benchmark(run_once)

        assert result is not None
        assert_max_mean(benchmark, SINGLE_RUN_MAX_MEAN)


class TestStringInputLatency:  # pylint: disable=too-few-public-methods
    """Benchmark `AgentRunner.run()` with a plain-text string.

    This mirrors the primary code path exercised by the `/chat` endpoint,
    which passes `body.message` (a string) directly to `agent_runner.run()`.
    """

    def test_single_run_string_input(
        self,
        benchmark: Any,
        assert_max_mean: Any,
        agent_runner_factory: Callable[..., AgentRunner],
        bench_loop: asyncio.AbstractEventLoop,
    ) -> None:
        """String input orchestration overhead should stay below the same threshold."""
        runner = agent_runner_factory()

        def run_once() -> str:
            return bench_loop.run_until_complete(
                runner.run(user_id="u", session_id="s", user_input=_SAMPLE_MESSAGE)
            )

        result = benchmark(run_once)

        assert result is not None
        assert_max_mean(benchmark, SINGLE_RUN_MAX_MEAN)


class TestConcurrentRuns:  # pylint: disable=too-few-public-methods
    """Benchmark multiple simultaneous `AgentRunner.run()` calls.

    This mirrors the concurrency pattern used by `evaluate.py` and
    ensures the async orchestration scales without linear degradation.
    """

    def test_ten_concurrent_runs(
        self,
        benchmark: Any,
        assert_max_mean: Any,
        agent_runner_factory: Callable[..., AgentRunner],
        sample_image: ImageType,
        bench_loop: asyncio.AbstractEventLoop,
    ) -> None:
        """Ten parallel runs should complete within the time budget."""
        runner = agent_runner_factory()

        async def _batch() -> list[str]:
            return list(
                await asyncio.gather(
                    *(
                        runner.run(
                            user_id=f"u{i}",
                            session_id=f"s{i}",
                            user_input=sample_image,
                        )
                        for i in range(10)
                    )
                )
            )

        def run_once() -> list[str]:
            return bench_loop.run_until_complete(_batch())

        results = benchmark(run_once)

        assert len(results) == 10
        assert all(r is not None for r in results)
        assert_max_mean(benchmark, CONCURRENT_10_MAX_MEAN)
