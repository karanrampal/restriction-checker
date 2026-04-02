"""FastAPI dependencies: per-user rate limiting and llm concurrency cap."""

import base64
import json
import logging
from collections.abc import AsyncGenerator

from fastapi import HTTPException, Request
from slowapi import Limiter

logger = logging.getLogger(__name__)


def get_user_identity(request: Request) -> str:
    """Extract caller identity from a Google IAM identity token.

    Cloud Run validates the token signature before requests reach this code,
    so we only decode the payload (no verification needed here). Used both as
    the slowapi rate-limit key and as the agent session user identifier.

    The result is cached on `request.state` so that slowapi's `key_func`
    call and the FastAPI `Depends` injection share one decode per request.

    Falls back to client IP for local dev / anonymous callers.

    Args:
        request: The incoming FastAPI request.

    Returns:
        The caller's email, `sub` claim, client IP, or `"unknown"`.
    """
    if hasattr(request.state, "user_id"):
        return request.state.user_id  # type: ignore[no-any-return]

    identity: str

    app_user = request.headers.get("x-app-user-email")
    if app_user:
        logger.debug("Identity derived from x-app-user-email header: %s", app_user)
        request.state.user_id = app_user
        return app_user

    iap_jwt = request.headers.get("x-goog-iap-jwt-assertion")
    if iap_jwt:
        try:
            segments = iap_jwt.split(".")
            if len(segments) == 3:
                payload_b64 = segments[1]
                payload_b64 += "=" * (4 - len(payload_b64) % 4)
                payload = json.loads(base64.urlsafe_b64decode(payload_b64))
                extracted = payload.get("email") or payload.get("sub")

                if extracted:
                    logger.debug("Identity derived from IAP JWT: %s", extracted)
                    identity = extracted
                    request.state.user_id = identity
                    return identity
        except Exception:  # pylint: disable=broad-exception-caught
            logger.warning("Failed to decode IAP JWT assertion; falling back.")

    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth.removeprefix("Bearer ")
        try:
            segments = token.split(".")
            if len(segments) == 3:
                payload_b64 = segments[1]
                payload_b64 += "=" * (4 - len(payload_b64) % 4)
                payload = json.loads(base64.urlsafe_b64decode(payload_b64))
                extracted = payload.get("email") or payload.get("sub")

                if extracted:
                    logger.debug("Identity derived from Authorization Bearer token: %s", extracted)
                    identity = extracted
                    request.state.user_id = identity
                    return identity
        except Exception:  # pylint: disable=broad-exception-caught
            logger.warning("Failed to decode identity token; falling back to client IP.")

    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        identity = forwarded.split(",")[0].strip()
        logger.debug("Identity derived from X-Forwarded-For: %s", identity)
    else:
        identity = request.client.host if request.client else "unknown"
        logger.debug("Identity derived from client host fallback: %s", identity)

    request.state.user_id = identity
    return identity


# Rate-limit key is the caller's identity (email / sub / IP) so each user gets their own independent
# bucket rather than sharing a per-IP bucket behind Cloud Run's load balancer.
limiter = Limiter(key_func=get_user_identity)


async def llm_concurrency(request: Request) -> AsyncGenerator[None]:
    """FastAPI dependency that caps simultaneous in-flight llm calls."""
    if request.app.state.llm_semaphore.locked():
        raise HTTPException(
            status_code=429, detail="Too many concurrent requests. Please try again later."
        )
    async with request.app.state.llm_semaphore:
        yield
