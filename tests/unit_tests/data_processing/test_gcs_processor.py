"""Unit tests for GCS processing module."""

import json
from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from data_processing.gcs_processor import GCSChatStorage


@pytest.fixture
def mock_gcsfs() -> Generator[AsyncMock, None, None]:
    """Fixture to mock gcsfs.GCSFileSystem."""
    with patch("data_processing.gcs_processor.gcsfs.GCSFileSystem") as MockGCSFS:
        mock_fs_instance = AsyncMock()
        MockGCSFS.return_value = mock_fs_instance
        yield mock_fs_instance


@pytest.fixture
def storage(mock_gcsfs: AsyncMock) -> GCSChatStorage:
    """Fixture to initialize GCSChatStorage with a mocked filesystem."""
    return GCSChatStorage(project="test-project", bucket="test-bucket")


class TestGCSChatStorage:
    """Unit tests for GCSChatStorage class."""

    def test_init(self, mock_gcsfs: AsyncMock) -> None:
        """Test initialization of GCSChatStorage."""
        local_storage = GCSChatStorage(project="test-project", bucket="test-bucket")
        assert local_storage.bucket == "test-bucket"
        assert local_storage.fs == mock_gcsfs

    def test_get_path(self, storage: GCSChatStorage) -> None:
        """Test path generation with email escaping."""
        path = storage._get_path("user.name@example.com", "session_123")  # pylint: disable=protected-access
        assert path == "test-bucket/chats/user_dot_name_at_example_dot_com/session_123.json"

    @pytest.mark.asyncio
    async def test_save_chat_interaction_new_file(self, storage: GCSChatStorage) -> None:
        """Test saving chat interaction when file doesn't exist."""
        storage.fs._exists.return_value = False

        interaction = {"role": "user", "content": "hello"}
        await storage.save_chat_interaction("user@test.com", "sess1", interaction)

        storage.fs._exists.assert_called_once_with(
            "test-bucket/chats/user_at_test_dot_com/sess1.json"
        )
        storage.fs._pipe.assert_called_once()

        args, _ = storage.fs._pipe.call_args
        saved_path, saved_bytes = args
        assert saved_path == "test-bucket/chats/user_at_test_dot_com/sess1.json"

        saved_json = json.loads(saved_bytes.decode("utf-8"))
        assert len(saved_json) == 1
        assert saved_json[0] == interaction

    @pytest.mark.asyncio
    async def test_save_chat_interaction_existing_file(self, storage: GCSChatStorage) -> None:
        """Test saving chat interaction when file already exists."""
        storage.fs._exists.return_value = True
        existing_history = [{"role": "user", "content": "hi"}]
        storage.fs._cat.return_value = json.dumps(existing_history).encode("utf-8")

        new_interaction = {"role": "bot", "content": "hello there"}
        await storage.save_chat_interaction("user@test.com", "sess1", new_interaction)

        storage.fs._cat.assert_called_once_with("test-bucket/chats/user_at_test_dot_com/sess1.json")

        args, _ = storage.fs._pipe.call_args
        saved_bytes = args[1]
        saved_json = json.loads(saved_bytes.decode("utf-8"))

        assert len(saved_json) == 2
        assert saved_json[0] == existing_history[0]
        assert saved_json[1] == new_interaction

    @pytest.mark.asyncio
    async def test_save_chat_interaction_read_error(self, storage: GCSChatStorage) -> None:
        """Test saving chat interaction when reading existing file fails."""
        storage.fs._exists.return_value = True
        storage.fs._cat.side_effect = Exception("Read error")

        interaction = {"role": "user", "content": "hello"}

        await storage.save_chat_interaction("user@test.com", "sess1", interaction)

        args, _ = storage.fs._pipe.call_args
        saved_bytes = args[1]
        saved_json = json.loads(saved_bytes.decode("utf-8"))
        assert len(saved_json) == 1
        assert saved_json[0] == interaction

    @pytest.mark.asyncio
    async def test_save_chat_interaction_write_error(self, storage: GCSChatStorage) -> None:
        """Test saving chat interaction when writing fails."""
        storage.fs._exists.return_value = False
        storage.fs._pipe.side_effect = Exception("Write error")

        interaction = {"role": "user", "content": "hello"}

        with pytest.raises(Exception, match="Write error"):
            await storage.save_chat_interaction("user@test.com", "sess1", interaction)

    @pytest.mark.asyncio
    async def test_get_chat_session_exists(self, storage: GCSChatStorage) -> None:
        """Test getting a chat session that exists."""
        storage.fs._exists.return_value = True
        expected_history = [{"role": "user", "content": "hi"}]
        storage.fs._cat.return_value = json.dumps(expected_history).encode("utf-8")

        result = await storage.get_chat_session("user@test.com", "sess1")

        assert result == expected_history
        storage.fs._exists.assert_called_once_with(
            "test-bucket/chats/user_at_test_dot_com/sess1.json"
        )
        storage.fs._cat.assert_called_once_with("test-bucket/chats/user_at_test_dot_com/sess1.json")

    @pytest.mark.asyncio
    async def test_get_chat_session_not_exists(self, storage: GCSChatStorage) -> None:
        """Test getting a chat session that does not exist."""
        storage.fs._exists.return_value = False

        result = await storage.get_chat_session("user@test.com", "sess1")

        assert result == []
        storage.fs._cat.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_chat_session_read_error(self, storage: GCSChatStorage) -> None:
        """Test getting a chat session when reading fails."""
        storage.fs._exists.return_value = True
        storage.fs._cat.side_effect = Exception("Read error")

        result = await storage.get_chat_session("user@test.com", "sess1")

        assert result == []

    @pytest.mark.asyncio
    async def test_list_chat_sessions_exists(self, storage: GCSChatStorage) -> None:
        """Test listing chat sessions when directory exists and has files."""
        storage.fs._exists.return_value = True

        storage.fs._ls.return_value = [
            "test-bucket/chats/user_at_test_dot_com/sess1.json",
            {"name": "test-bucket/chats/user_at_test_dot_com/sess2.json"},
            "test-bucket/chats/user_at_test_dot_com/not_json.txt",
        ]

        async def mock_cat(path: str) -> bytes:
            if "sess1" in path:
                return json.dumps([{"timestamp": "2023-01-01T10:00:00Z"}]).encode("utf-8")
            if "sess2" in path:
                return json.dumps([{"timestamp": "2023-01-02T10:00:00Z"}]).encode("utf-8")
            return b"[]"

        storage.fs._cat.side_effect = mock_cat

        results = await storage.list_chat_sessions("user@test.com")

        assert len(results) == 2
        assert results[0]["session_id"] == "sess2"
        assert results[0]["created_at"] == "2023-01-02T10:00:00Z"
        assert results[1]["session_id"] == "sess1"
        assert results[1]["created_at"] == "2023-01-01T10:00:00Z"

    @pytest.mark.asyncio
    async def test_list_chat_sessions_not_exists(self, storage: GCSChatStorage) -> None:
        """Test listing chat sessions when directory doesn't exist."""
        storage.fs._exists.return_value = False

        results = await storage.list_chat_sessions("user@test.com")

        assert results == []
        storage.fs._ls.assert_not_called()

    @pytest.mark.asyncio
    async def test_list_chat_sessions_read_error(self, storage: GCSChatStorage) -> None:
        """Test listing chat sessions when listing directory fails."""
        storage.fs._exists.side_effect = Exception("List error")

        results = await storage.list_chat_sessions("user@test.com")

        assert results == []

    @pytest.mark.asyncio
    async def test_list_chat_sessions_file_read_error(self, storage: GCSChatStorage) -> None:
        """Test listing chat sessions handles individual file read errors."""
        storage.fs._exists.return_value = True
        storage.fs._ls.return_value = ["test-bucket/chats/user_at_test_dot_com/sess1.json"]

        storage.fs._cat.side_effect = Exception("File read error")

        results = await storage.list_chat_sessions("user@test.com")

        assert len(results) == 1
        assert results[0]["session_id"] == "sess1"
        assert results[0]["created_at"] == "Unknown"

    @pytest.mark.asyncio
    async def test_delete_chat_session_exists(self, storage: GCSChatStorage) -> None:
        """Test deleting a specific chat session."""
        storage.fs._exists.return_value = True

        await storage.delete_chat_session("user@test.com", "sess1")

        storage.fs._exists.assert_called_once_with(
            "test-bucket/chats/user_at_test_dot_com/sess1.json"
        )
        storage.fs._rm.assert_called_once_with("test-bucket/chats/user_at_test_dot_com/sess1.json")

    @pytest.mark.asyncio
    async def test_delete_chat_session_not_exists(self, storage: GCSChatStorage) -> None:
        """Test deleting a chat session that doesn't exist."""
        storage.fs._exists.return_value = False

        await storage.delete_chat_session("user@test.com", "sess1")

        storage.fs._rm.assert_not_called()

    @pytest.mark.asyncio
    async def test_delete_chat_session_error(self, storage: GCSChatStorage) -> None:
        """Test handling errors during chat session deletion."""
        storage.fs._exists.return_value = True
        storage.fs._rm.side_effect = Exception("Delete error")

        with pytest.raises(Exception, match="Delete error"):
            await storage.delete_chat_session("user@test.com", "sess1")

    @pytest.mark.asyncio
    async def test_delete_all_chat_sessions_exists(self, storage: GCSChatStorage) -> None:
        """Test deleting all chat sessions for a user."""
        storage.fs._exists.return_value = True

        await storage.delete_all_chat_sessions("user@test.com")

        storage.fs._exists.assert_called_once_with("test-bucket/chats/user_at_test_dot_com")
        storage.fs._rm.assert_called_once_with(
            "test-bucket/chats/user_at_test_dot_com", recursive=True
        )

    @pytest.mark.asyncio
    async def test_delete_all_chat_sessions_not_exists(self, storage: GCSChatStorage) -> None:
        """Test deleting all chat sessions when user directory doesn't exist."""
        storage.fs._exists.return_value = False

        await storage.delete_all_chat_sessions("user@test.com")

        storage.fs._rm.assert_not_called()

    @pytest.mark.asyncio
    async def test_delete_all_chat_sessions_error(self, storage: GCSChatStorage) -> None:
        """Test handling errors during deletion of all chat sessions."""
        storage.fs._exists.return_value = True
        storage.fs._rm.side_effect = Exception("Delete all error")

        with pytest.raises(Exception, match="Delete all error"):
            await storage.delete_all_chat_sessions("user@test.com")
