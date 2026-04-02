"""Performance tests for in-memory session operations."""

import asyncio
from collections.abc import Callable
from typing import Any

from agents.agent_runner import AgentRunner

SESSION_OP_MAX_MEAN = 0.050  # 50 ms per operation


class TestGetSessionState:
    """Benchmark `AgentRunner.get_session_state`."""

    def test_get_existing_state(
        self,
        benchmark: Any,
        assert_max_mean: Any,
        agent_runner_factory: Callable[..., AgentRunner],
        bench_loop: asyncio.AbstractEventLoop,
    ) -> None:
        """Retrieving state for an existing session should be near-instant."""
        runner = agent_runner_factory()

        bench_loop.run_until_complete(
            runner.session_service.create_session(
                app_name=runner.app_name,
                user_id="u1",
                session_id="s1",
                state={"key": "value"},
            )
        )

        def run_once() -> dict:
            return bench_loop.run_until_complete(runner.get_session_state("u1", "s1"))

        state = benchmark(run_once)

        assert isinstance(state, dict)
        assert_max_mean(benchmark, SESSION_OP_MAX_MEAN)

    def test_get_missing_state(
        self,
        benchmark: Any,
        assert_max_mean: Any,
        agent_runner_factory: Callable[..., AgentRunner],
        bench_loop: asyncio.AbstractEventLoop,
    ) -> None:
        """Querying a non-existent session should also be fast."""
        runner = agent_runner_factory()

        def run_once() -> dict:
            return bench_loop.run_until_complete(runner.get_session_state("no-user", "no-session"))

        state = benchmark(run_once)

        assert state == {}
        assert_max_mean(benchmark, SESSION_OP_MAX_MEAN)


class TestResetSession:  # pylint: disable=too-few-public-methods
    """Benchmark `AgentRunner.reset_session`."""

    def test_reset(
        self,
        benchmark: Any,
        assert_max_mean: Any,
        agent_runner_factory: Callable[..., AgentRunner],
        bench_loop: asyncio.AbstractEventLoop,
    ) -> None:
        """Creating + immediately resetting a session."""
        runner = agent_runner_factory()

        def run_once() -> None:
            bench_loop.run_until_complete(
                runner.session_service.create_session(
                    app_name=runner.app_name,
                    user_id="u1",
                    session_id="s-reset",
                    state={"data": "test"},
                )
            )
            bench_loop.run_until_complete(runner.reset_session("u1", "s-reset"))

        benchmark(run_once)

        assert_max_mean(benchmark, SESSION_OP_MAX_MEAN)


class TestClearHistoryOnly:  # pylint: disable=too-few-public-methods
    """Benchmark `AgentRunner.clear_history_only`."""

    def test_clear_history(
        self,
        benchmark: Any,
        assert_max_mean: Any,
        agent_runner_factory: Callable[..., AgentRunner],
        bench_loop: asyncio.AbstractEventLoop,
    ) -> None:
        """Clearing history while preserving state.

        `clear_history_only` deletes and re-creates the session, so it
        survives across benchmark iterations.
        """
        runner = agent_runner_factory()

        bench_loop.run_until_complete(
            runner.session_service.create_session(
                app_name=runner.app_name,
                user_id="u1",
                session_id="s-clear",
                state={"preserved": True},
            )
        )

        def run_once() -> None:
            bench_loop.run_until_complete(runner.clear_history_only("u1", "s-clear"))

        benchmark(run_once)

        assert_max_mean(benchmark, SESSION_OP_MAX_MEAN)
