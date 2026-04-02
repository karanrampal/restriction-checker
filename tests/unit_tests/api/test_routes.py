"""Unit tests for api/routes.py."""

import json
from unittest.mock import AsyncMock

import httpx
import pytest

from api.app import app
from api.models import ChatResponse

_VALID_MESSAGE = "What is this? https://example.com/product.png"
_VALID_BODY = {"message": _VALID_MESSAGE}
_QA_ONLY_BODY = {"message": "What are your opening hours?"}


class TestHealthEndpoint:  # pylint: disable=too-few-public-methods
    """Tests for GET /health."""

    @pytest.mark.asyncio
    async def test_returns_ok(self, api_client: httpx.AsyncClient) -> None:
        """Liveness probe always returns 200 with status ok."""
        response = await api_client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestChatEndpoint:
    """Tests for POST /chat."""

    @pytest.mark.asyncio
    async def test_success_text_only(
        self, api_client: httpx.AsyncClient, mock_agent_runner: AsyncMock
    ) -> None:
        """Plain-text message with no URL returns a reply and no restriction block."""
        mock_agent_runner.run.return_value = json.dumps({"answer": "We open at 9am.", "url": ""})

        response = await api_client.post("/chat", json=_QA_ONLY_BODY)

        assert response.status_code == 200
        body = ChatResponse(**response.json())
        assert body.reply == "We open at 9am."
        assert body.restriction is None
        assert body.session_id

    @pytest.mark.asyncio
    async def test_success_with_restriction(
        self, api_client: httpx.AsyncClient, mock_agent_runner: AsyncMock
    ) -> None:
        """Message with a URL returns reply and a populated restriction block."""
        mock_agent_runner.run.return_value = json.dumps(
            {
                "answer": "Checked the image.",
                "url": "https://example.com/product.png",
                "found": True,
                "item": "Knife",
                "reasoning": "Blade visible.",
            }
        )

        response = await api_client.post("/chat", json=_VALID_BODY)

        assert response.status_code == 200
        body = ChatResponse(**response.json())
        assert body.reply == "Checked the image."
        assert body.restriction is not None
        assert body.restriction.found is True
        assert body.restriction.item == "Knife"
        mock_agent_runner.run.assert_called_once()

    @pytest.mark.asyncio
    async def test_session_id_preserved_across_turns(
        self, api_client: httpx.AsyncClient, mock_agent_runner: AsyncMock
    ) -> None:
        """Session ID returned by the API is echoed back in the response body."""
        mock_agent_runner.run.return_value = json.dumps({"answer": "Hello.", "url": ""})
        session_id = "my-existing-session"

        response = await api_client.post("/chat", json={"message": "Hi", "session_id": session_id})

        assert response.status_code == 200
        assert response.json()["session_id"] == session_id

    @pytest.mark.asyncio
    async def test_not_allowed_url_returns_403(self, api_client: httpx.AsyncClient) -> None:
        """A URL not matching allowed prefixes returns 403 before calling the agent."""
        response = await api_client.post(
            "/chat", json={"message": "Check https://malicious.com/image.png"}
        )

        assert response.status_code == 403
        assert "not from an allowed source" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_allowed_url_passes_validation(
        self, api_client: httpx.AsyncClient, mock_agent_runner: AsyncMock
    ) -> None:
        """A URL matching the allowed prefix passes the 403 guard."""
        mock_agent_runner.run.return_value = json.dumps({"answer": "ok", "url": ""})

        response = await api_client.post("/chat", json=_VALID_BODY)

        assert response.status_code != 403

    @pytest.mark.asyncio
    async def test_agent_timeout_returns_504(
        self, api_client: httpx.AsyncClient, mock_agent_runner: AsyncMock
    ) -> None:
        """TimeoutError from the agent runner produces a 504 Gateway Timeout."""
        mock_agent_runner.run.side_effect = TimeoutError("agent took too long")

        response = await api_client.post("/chat", json=_QA_ONLY_BODY)

        assert response.status_code == 504

    @pytest.mark.asyncio
    async def test_agent_error_returns_502(
        self, api_client: httpx.AsyncClient, mock_agent_runner: AsyncMock
    ) -> None:
        """Unexpected exception from the agent runner produces a 502."""
        mock_agent_runner.run.side_effect = ValueError("model failure")

        response = await api_client.post("/chat", json=_QA_ONLY_BODY)

        assert response.status_code == 502

    @pytest.mark.asyncio
    async def test_agent_plain_text_fallback(
        self, api_client: httpx.AsyncClient, mock_agent_runner: AsyncMock
    ) -> None:
        """Non-JSON text from the agent is returned as-is in reply (no 502)."""
        mock_agent_runner.run.return_value = "Agent did not produce a final response."

        response = await api_client.post("/chat", json=_QA_ONLY_BODY)

        assert response.status_code == 200
        body = response.json()
        assert body["reply"] == "Agent did not produce a final response."
        assert body["restriction"] is None

    @pytest.mark.asyncio
    async def test_run_called_with_correct_user_input(
        self, api_client: httpx.AsyncClient, mock_agent_runner: AsyncMock
    ) -> None:
        """The agent runner receives the raw message string from the request body."""
        mock_agent_runner.run.return_value = json.dumps({"answer": "ok", "url": ""})

        await api_client.post(
            "/chat",
            json={"message": "hello world"},
            headers={"x-app-user-email": "user@example.com"},
        )

        call_kwargs = mock_agent_runner.run.call_args
        assert call_kwargs.kwargs["user_input"] == "hello world"

    @pytest.mark.asyncio
    async def test_interaction_saved_to_storage(
        self, api_client: httpx.AsyncClient, mock_agent_runner: AsyncMock
    ) -> None:
        """A successful chat turn is persisted to GCS storage."""
        mock_agent_runner.run.return_value = json.dumps({"answer": "Saved!", "url": ""})

        await api_client.post(
            "/chat",
            json={"message": "save me", "session_id": "sess-save"},
            headers={"x-app-user-email": "user@example.com"},
        )

        app.state.chat_storage.save_chat_interaction.assert_called_once()
        saved = app.state.chat_storage.save_chat_interaction.call_args.kwargs["interaction"]
        assert saved["message"] == "save me"
        assert saved["reply"] == "Saved!"

    @pytest.mark.asyncio
    async def test_storage_failure_does_not_affect_response(
        self, api_client: httpx.AsyncClient, mock_agent_runner: AsyncMock
    ) -> None:
        """A GCS write failure does not cause the endpoint to error."""
        mock_agent_runner.run.return_value = json.dumps({"answer": "ok", "url": ""})
        app.state.chat_storage.save_chat_interaction.side_effect = Exception("GCS down")

        response = await api_client.post("/chat", json=_QA_ONLY_BODY)

        assert response.status_code == 200


class TestHistoryEndpoints:
    """Tests for GET /history and GET /history/{session_id}."""

    @pytest.mark.asyncio
    async def test_list_chat_history_success(self, api_client: httpx.AsyncClient) -> None:
        """Successfully returns a list of chat sessions."""
        app.state.chat_storage.list_chat_sessions.return_value = [
            {"session_id": "sess1", "created_at": "2023-01-01T10:00:00Z"},
            {"session_id": "sess2", "created_at": "2023-01-02T10:00:00Z"},
        ]

        response = await api_client.get(
            "/history", headers={"x-app-user-email": "user@example.com"}
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["session_id"] == "sess1"
        assert data[1]["session_id"] == "sess2"

    @pytest.mark.asyncio
    async def test_list_chat_history_error(self, api_client: httpx.AsyncClient) -> None:
        """Returns 500 when listing chat sessions fails."""
        app.state.chat_storage.list_chat_sessions.side_effect = Exception("Storage error")

        response = await api_client.get(
            "/history", headers={"x-app-user-email": "user@example.com"}
        )

        assert response.status_code == 500
        assert "Failed to retrieve chat history" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_chat_history_detail_success(self, api_client: httpx.AsyncClient) -> None:
        """Successfully returns a chat session's interactions."""
        app.state.chat_storage.get_chat_session.return_value = [
            {
                "message": "What is this? https://example.com/img.png",
                "reply": "Checked the image.",
                "restriction": {"found": False, "item": "Ok", "reasoning": "Clean."},
                "timestamp": "2023-01-01T10:00:00Z",
            }
        ]

        response = await api_client.get(
            "/history/sess1", headers={"x-app-user-email": "user@example.com"}
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["message"] == "What is this? https://example.com/img.png"
        assert data[0]["reply"] == "Checked the image."
        assert data[0]["restriction"]["item"] == "Ok"

    @pytest.mark.asyncio
    async def test_get_chat_history_detail_no_restriction(
        self, api_client: httpx.AsyncClient
    ) -> None:
        """Interactions without a restriction block are returned with restriction=null."""
        app.state.chat_storage.get_chat_session.return_value = [
            {
                "message": "What are your hours?",
                "reply": "We open at 9am.",
                "restriction": None,
                "timestamp": "2023-01-01T10:00:00Z",
            }
        ]

        response = await api_client.get(
            "/history/sess1", headers={"x-app-user-email": "user@example.com"}
        )

        assert response.status_code == 200
        assert response.json()[0]["restriction"] is None

    @pytest.mark.asyncio
    async def test_get_chat_history_detail_empty_returns_200(
        self, api_client: httpx.AsyncClient
    ) -> None:
        """Empty session returns 200 with an empty list (not 404)."""
        app.state.chat_storage.get_chat_session.return_value = []

        response = await api_client.get(
            "/history/sess1", headers={"x-app-user-email": "user@example.com"}
        )

        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_get_chat_history_detail_error(self, api_client: httpx.AsyncClient) -> None:
        """Returns 500 when getting chat history details fails."""
        app.state.chat_storage.get_chat_session.side_effect = Exception("Storage error")

        response = await api_client.get(
            "/history/sess1", headers={"x-app-user-email": "user@example.com"}
        )

        assert response.status_code == 500
        assert "Failed to retrieve chat session" in response.json()["detail"]


class TestHistoryDeletionEndpoints:
    """Tests for DELETE /history and DELETE /history/{session_id}."""

    @pytest.mark.asyncio
    async def test_delete_chat_history_detail_success(self, api_client: httpx.AsyncClient) -> None:
        """Successfully deletes a specific chat session."""
        app.state.chat_storage.delete_chat_session.return_value = None

        response = await api_client.delete(
            "/history/sess1", headers={"x-app-user-email": "user@example.com"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "sess1" in data["message"]
        app.state.chat_storage.delete_chat_session.assert_called_once_with(
            "user@example.com", "sess1"
        )

    @pytest.mark.asyncio
    async def test_delete_chat_history_detail_error(self, api_client: httpx.AsyncClient) -> None:
        """Returns 500 when deleting a specific chat session fails."""
        app.state.chat_storage.delete_chat_session.side_effect = Exception("Delete error")

        response = await api_client.delete(
            "/history/sess1", headers={"x-app-user-email": "user@example.com"}
        )

        assert response.status_code == 500
        assert "Failed to delete chat session" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_delete_all_chat_history_success(self, api_client: httpx.AsyncClient) -> None:
        """Successfully deletes all chat sessions."""
        app.state.chat_storage.delete_all_chat_sessions.return_value = None

        response = await api_client.delete(
            "/history", headers={"x-app-user-email": "user@example.com"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "All chat history deleted" in data["message"]
        app.state.chat_storage.delete_all_chat_sessions.assert_called_once_with("user@example.com")
