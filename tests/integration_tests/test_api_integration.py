"""Integration tests for the Restriction Checker API."""

import base64
import json
import uuid
from collections.abc import AsyncIterator
from unittest.mock import patch

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport

from api.app import app, lifespan

_TEST_IMAGE_URL = "https://imagebankstorageprod.blob.core.windows.net/articleimagebank/4-2026/cf385c86-f26c-4e1c-a749-206fbbba7979/new-%20dune%20for%20print%2009-104.png?sv=2025-07-05&se=2032-01-13T13%3A59%3A31Z&sr=b&sp=rw&sig=4gqFkgcNpRiP3i%2BgD8tp1OzwHjRjNV%2BnCXhtkRYd4iE%3D"  # pylint: disable=line-too-long
_VALID_MESSAGE = f"Can you check this image? {_TEST_IMAGE_URL}"
_VALID_BODY = {"message": _VALID_MESSAGE}
_VALID_AGENT_RESPONSE = (
    '{"answer": "Checked.", "url": "'
    + _TEST_IMAGE_URL
    + '", "found": false, "item": "Ok", "reasoning": "Image is clean."}'
)


def _make_jwt(email: str) -> str:
    """Return a minimal (unsigned) JWT whose payload matches what `get_user_identity` decodes."""
    payload = base64.urlsafe_b64encode(json.dumps({"email": email}).encode()).rstrip(b"=").decode()
    return f"header.{payload}.sig"


@pytest_asyncio.fixture(name="integration_client")
async def fixture_integration_client() -> AsyncIterator[httpx.AsyncClient]:
    """Provides an AsyncClient connected to the real FastAPI app."""
    async with (
        lifespan(app),
        httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client,
    ):
        yield client


class TestAPIIntegration:
    """End-to-End integration checks targeting the FastAPI layer."""

    @pytest.mark.network
    @pytest.mark.asyncio
    async def test_full_request_cycle(self, integration_client: httpx.AsyncClient) -> None:
        """The app routes the request end-to-end and returns a well-formed ChatResponse."""
        with (
            patch(
                "agents.agent_runner.AgentRunner.run", return_value=_VALID_AGENT_RESPONSE
            ) as mock_run,
            patch("data_processing.gcs_processor.GCSChatStorage.save_chat_interaction"),
        ):
            response = await integration_client.post(
                "/chat",
                json=_VALID_BODY,
                headers={"Authorization": f"Bearer {_make_jwt('cycle@test.com')}"},
            )

            assert response.status_code == 200, response.text

            data = response.json()
            assert "reply" in data, f"Response missing 'reply' key: {data}"
            assert "session_id" in data, f"Response missing 'session_id' key: {data}"
            assert data["restriction"] is not None, "Expected a restriction block for image message"
            assert data["restriction"]["item"] == "Ok", f"Unexpected item value: {data}"

            mock_run.assert_called_once()
            called_kwargs = mock_run.call_args.kwargs
            assert called_kwargs["user_input"] == _VALID_MESSAGE

    @pytest.mark.asyncio
    async def test_blocked_url_integration(self, integration_client: httpx.AsyncClient) -> None:
        """A request with a URL not matching the allowed prefixes returns 403 dynamically."""
        bad_url_body = {"message": "Check this: https://random-website.com/image.png"}

        response = await integration_client.post(
            "/chat",
            json=bad_url_body,
            headers={"Authorization": f"Bearer {_make_jwt('blocked@test.com')}"},
        )

        assert response.status_code == 403, response.text
        assert "not from an allowed source" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_rate_limiter_blocks_abuse(self, integration_client: httpx.AsyncClient) -> None:
        """Sending 31 rapid requests using identical headers hits the slowapi 429 barrier."""
        # Use a unique identity per run so prior runs don't consume this bucket.
        unique_email = f"spammer-{uuid.uuid4().hex[:8]}@test.com"
        headers = {"Authorization": f"Bearer {_make_jwt(unique_email)}"}

        with (
            patch("agents.agent_runner.AgentRunner.run", return_value=_VALID_AGENT_RESPONSE),
            patch("data_processing.gcs_processor.GCSChatStorage.save_chat_interaction"),
        ):
            # Send 30 successful requests (rate limit is 30/minute)
            for i in range(30):
                resp = await integration_client.post(
                    "/chat",
                    json=_VALID_BODY,
                    headers=headers,
                )
                assert resp.status_code == 200, (
                    f"Expected 200, got {resp.status_code} on request {i + 1} (pre-limit phase)."
                )

            # The 31st request should be blocked instantly
            resp_429 = await integration_client.post("/chat", json=_VALID_BODY, headers=headers)
            assert resp_429.status_code == 429
            assert (
                "Rate limit exceeded" in resp_429.text.strip()
                or "Too Many Requests" in resp_429.text.strip()
            )
