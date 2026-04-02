"""Performance tests for GCSChatStorage."""

import asyncio
from typing import Any
from unittest.mock import AsyncMock, patch

from data_processing.gcs_processor import GCSChatStorage

SAVE_INTERACTION_MAX_MEAN = 0.050  # 50 ms
LIST_SESSIONS_MAX_MEAN = 0.050  # 50 ms
GET_SESSION_MAX_MEAN = 0.050  # 50 ms
DELETE_SESSION_MAX_MEAN = 0.050  # 50 ms
DELETE_ALL_SESSIONS_MAX_MEAN = 0.100  # 100 ms


class TestGCSProcessorLatency:  # pylint: disable=too-few-public-methods
    """Benchmark the GCS processor."""

    def test_save_chat_interaction(
        self,
        benchmark: Any,
        assert_max_mean: Any,
        bench_loop: asyncio.AbstractEventLoop,
    ) -> None:
        """Benchmark saving a chat interaction with mocked IO."""
        with patch("data_processing.gcs_processor.gcsfs.GCSFileSystem") as mock_fs_class:
            mock_fs = AsyncMock()
            mock_fs_class.return_value = mock_fs
            mock_fs._exists.return_value = True
            mock_fs._cat.return_value = b'[{"role": "user", "content": "hi"}]'

            storage = GCSChatStorage("project", "bucket")
            interaction = {"role": "bot", "content": "hello"}

            def run_once() -> None:
                bench_loop.run_until_complete(storage.save_chat_interaction("u", "s", interaction))

            benchmark(run_once)
            assert_max_mean(benchmark, SAVE_INTERACTION_MAX_MEAN)

    def test_list_chat_sessions(
        self,
        benchmark: Any,
        assert_max_mean: Any,
        bench_loop: asyncio.AbstractEventLoop,
    ) -> None:
        """Benchmark listing chat sessions (simulating 50 sessions)."""
        with patch("data_processing.gcs_processor.gcsfs.GCSFileSystem") as mock_fs_class:
            mock_fs = AsyncMock()
            mock_fs_class.return_value = mock_fs
            mock_fs._exists.return_value = True

            fake_files = [f"bucket/chats/user/sess_{i}.json" for i in range(50)]
            mock_fs._ls.return_value = fake_files

            async def mock_cat(path: str) -> bytes:  # pylint: disable=unused-argument
                return b'[{"timestamp": "2023-01-01T10:00:00Z"}]'

            mock_fs._cat.side_effect = mock_cat

            storage = GCSChatStorage("project", "bucket")

            def run_once() -> Any:
                return bench_loop.run_until_complete(storage.list_chat_sessions("u"))

            result = benchmark(run_once)
            assert len(result) == 50
            assert_max_mean(benchmark, LIST_SESSIONS_MAX_MEAN)

    def test_get_chat_session(
        self,
        benchmark: Any,
        assert_max_mean: Any,
        bench_loop: asyncio.AbstractEventLoop,
    ) -> None:
        """Benchmark retrieving a specific chat session."""
        with patch("data_processing.gcs_processor.gcsfs.GCSFileSystem") as mock_fs_class:
            mock_fs = AsyncMock()
            mock_fs_class.return_value = mock_fs
            mock_fs._exists.return_value = True
            mock_fs._cat.return_value = (
                b'[{"role": "user", "content": "hi"}, {"role": "bot", "content": "hello"}]'
            )

            storage = GCSChatStorage("project", "bucket")

            def run_once() -> Any:
                return bench_loop.run_until_complete(storage.get_chat_session("u", "s"))

            result = benchmark(run_once)
            assert len(result) == 2
            assert_max_mean(benchmark, GET_SESSION_MAX_MEAN)

    def test_delete_chat_session(
        self,
        benchmark: Any,
        assert_max_mean: Any,
        bench_loop: asyncio.AbstractEventLoop,
    ) -> None:
        """Benchmark deleting a specific chat session."""
        with patch("data_processing.gcs_processor.gcsfs.GCSFileSystem") as mock_fs_class:
            mock_fs = AsyncMock()
            mock_fs_class.return_value = mock_fs
            mock_fs._exists.return_value = True

            storage = GCSChatStorage("project", "bucket")

            def run_once() -> None:
                bench_loop.run_until_complete(storage.delete_chat_session("u", "s"))

            benchmark(run_once)
            assert_max_mean(benchmark, DELETE_SESSION_MAX_MEAN)

    def test_delete_all_chat_sessions(
        self,
        benchmark: Any,
        assert_max_mean: Any,
        bench_loop: asyncio.AbstractEventLoop,
    ) -> None:
        """Benchmark deleting all chat sessions for a user."""
        with patch("data_processing.gcs_processor.gcsfs.GCSFileSystem") as mock_fs_class:
            mock_fs = AsyncMock()
            mock_fs_class.return_value = mock_fs
            mock_fs._exists.return_value = True

            storage = GCSChatStorage("project", "bucket")

            def run_once() -> None:
                bench_loop.run_until_complete(storage.delete_all_chat_sessions("u"))

            benchmark(run_once)
            assert_max_mean(benchmark, DELETE_ALL_SESSIONS_MAX_MEAN)
