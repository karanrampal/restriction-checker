"""Unit tests for api/dependencies.py."""

import asyncio
import base64
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from fastapi.requests import Request

from api.dependencies import get_user_identity, llm_concurrency


def _make_jwt(payload: dict) -> str:
    """Return a minimal (unsigned) JWT with the given payload."""
    encoded = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    return f"ignored_header.{encoded}.ignored_signature"


def _make_request(
    auth_header: str | None = None,
    client_host: str | None = "127.0.0.1",
    iap_jwt: str | None = None,
    **kwargs: str,
) -> MagicMock:
    """Construct a minimal mock Request.

    Uses a real `SimpleNamespace` for `request.state` so that `hasattr`
    behaves correctly (MagicMock attributes always exist, which would make the
    cache-hit branch always fire).
    """
    req = MagicMock(spec=Request)
    req.state = SimpleNamespace()

    headers_dict = {}
    if auth_header:
        headers_dict["Authorization"] = auth_header
        headers_dict["authorization"] = auth_header
    if iap_jwt:
        headers_dict["x-goog-iap-jwt-assertion"] = iap_jwt

    app_user = kwargs.get("app_user")
    if app_user:
        headers_dict["x-app-user-email"] = app_user

    forwarded_for = kwargs.get("forwarded_for")
    if forwarded_for:
        headers_dict["x-forwarded-for"] = forwarded_for

    req.headers.get.side_effect = lambda k, d="": headers_dict.get(k, d)

    if client_host is not None:
        req.client = MagicMock()
        req.client.host = client_host
    else:
        req.client = None
    return req


class TestGetUserIdentity:
    """Unit tests for get_user_identity."""

    def test_returns_email_from_jwt(self) -> None:
        """Email claim takes priority over sub."""
        token = _make_jwt({"email": "user@example.com", "sub": "uid-123"})
        req = _make_request(auth_header=f"Bearer {token}")

        assert get_user_identity(req) == "user@example.com"

    def test_returns_sub_when_no_email(self) -> None:
        """Falls back to sub claim when email is absent."""
        token = _make_jwt({"sub": "uid-456"})
        req = _make_request(auth_header=f"Bearer {token}")

        assert get_user_identity(req) == "uid-456"

    def test_falls_back_to_client_ip_with_no_auth_header(self) -> None:
        """No Authorization header returns the client IP address."""
        req = _make_request(client_host="10.0.0.1")

        assert get_user_identity(req) == "10.0.0.1"

    def test_falls_back_to_x_forwarded_for_when_present(self) -> None:
        """Uses X-Forwarded-For if available instead of client host."""
        req = _make_request(client_host="10.0.0.1", forwarded_for="1.2.3.4, 5.6.7.8")

        assert get_user_identity(req) == "1.2.3.4"

    def test_falls_back_to_ip_on_malformed_token(self) -> None:
        """A Bearer token that is not a valid JWT falls back to client IP."""
        req = _make_request(auth_header="Bearer not.valid", client_host="1.2.3.4")

        assert get_user_identity(req) == "1.2.3.4"

    def test_falls_back_to_unknown_when_no_client(self) -> None:
        """Returns 'unknown' when request.client is None."""
        req = _make_request(client_host=None)

        assert get_user_identity(req) == "unknown"

    def test_result_cached_on_request_state(self) -> None:
        """Second call returns cached value without re-decoding the token."""
        token = _make_jwt({"email": "cached@example.com"})
        req = _make_request(auth_header=f"Bearer {token}")

        first = get_user_identity(req)
        # Corrupt the header so re-decoding would yield a different result.
        req.headers.get.return_value = ""
        second = get_user_identity(req)

        assert first == second == "cached@example.com"

    def test_stores_identity_on_request_state(self) -> None:
        """Identity is written to request.state.user_id for downstream use."""
        token = _make_jwt({"email": "state@example.com"})
        req = _make_request(auth_header=f"Bearer {token}")

        identity = get_user_identity(req)

        assert req.state.user_id == identity

    def test_returns_email_from_iap_jwt_assertion(self) -> None:
        """Extracts the identity using the IAP JWT assertion."""
        token = _make_jwt({"email": "iap-user@example.com"})
        req = _make_request(iap_jwt=token)

        assert get_user_identity(req) == "iap-user@example.com"

    def test_returns_email_from_app_user_header(self) -> None:
        """Extracts the identity using the custom app user header."""
        req = _make_request(app_user="app-user@example.com")

        assert get_user_identity(req) == "app-user@example.com"


class TestLlmConcurrency:
    """Unit tests for the llm_concurrency async dependency."""

    @pytest.mark.asyncio
    async def test_acquires_and_releases_semaphore(self) -> None:
        """Semaphore slot is held during the yield and released afterwards."""
        sem = asyncio.Semaphore(1)
        req = MagicMock(spec=Request)
        req.app.state.llm_semaphore = sem

        gen = llm_concurrency(req)
        try:
            await gen.__anext__()  # runs up to yield; acquires semaphore
            assert sem.locked()
        finally:
            await gen.aclose()  # runs cleanup block; releases semaphore

        assert not sem.locked()

    @pytest.mark.asyncio
    async def test_raises_429_when_semaphore_fully_locked(self) -> None:
        """Raises HTTP 429 immediately when all concurrency slots are taken."""
        sem = asyncio.Semaphore(1)
        await sem.acquire()
        req = MagicMock(spec=Request)
        req.app.state.llm_semaphore = sem

        with pytest.raises(HTTPException) as exc_info:
            await llm_concurrency(req).__anext__()

        assert exc_info.value.status_code == 429
        sem.release()
