"""Route definitions for the API."""

import json
import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request

from api.dependencies import get_user_identity, limiter, llm_concurrency
from api.models import ChatHistorySummary, ChatInteraction, ChatRequest, ChatResponse, CheckResponse
from core.utils import check_url_prefix, extract_url_from_text

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    """Simple liveness probe."""
    return {"status": "ok"}


@router.post(
    "/chat",
    response_model=ChatResponse,
    tags=["chat"],
    dependencies=[Depends(llm_concurrency)],
)
@limiter.limit("30/minute")
async def chat(
    request: Request,
    body: ChatRequest,
    user_id: str = Depends(get_user_identity),
) -> ChatResponse:
    """Send a message to the chatbot and receive a reply.

    The agent answers general questions as plain text. If the message contains
    an image URL, the agent also checks it for restricted content and includes
    the result in the response. Sessions are preserved between calls for
    multi-turn conversations - pass the returned `session_id` in subsequent
    requests to continue the same session.

    Args:
        request: The incoming FastAPI request (used to access `app.state`).
        body: Request body containing the user message and optional session ID.
        user_id: Parsed identifier injected by `get_user_identity` dependency.

    Returns:
        A `ChatResponse` with the agent's reply and an optional restriction block.

    Raises:
        HTTPException 403: If the message contains a URL not from an allowed source.
        HTTPException 502: If the agent fails or returns an unexpected response.
        HTTPException 504: If the agent times out.
    """
    session_id = str(body.session_id) if body.session_id else str(uuid.uuid4())

    allowed_prefixes = request.app.state.config.api.allowed_url_prefixes
    if allowed_prefixes:
        url = extract_url_from_text(body.message)
        if url and not check_url_prefix(url, allowed_prefixes):
            logger.warning("Rejected URL not in allowed prefixes: %s", url)
            raise HTTPException(
                status_code=403,
                detail="Message contains a URL that is not from an allowed source.",
            )

    logger.info("Chat request from user=%s session=%s", user_id, session_id)

    agent_runner = request.app.state.agent_runner
    try:
        response_text = await agent_runner.run(
            user_id=user_id,
            session_id=session_id,
            user_input=body.message,
        )
    except TimeoutError as exc:
        logger.error("Agent timed out: %s", exc)
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.error("Agent error: %s", exc)
        raise HTTPException(status_code=502, detail=f"Agent error: {exc}") from exc

    try:
        response_dict = json.loads(response_text)
    except json.JSONDecodeError:
        # Agent returned plain text - treat it as the reply directly.
        return ChatResponse(reply=response_text, session_id=session_id)

    reply = response_dict.get("answer", response_text)
    restriction: CheckResponse | None = None
    if "found" in response_dict:
        restriction = CheckResponse(
            found=response_dict["found"],
            item=response_dict["item"],
            reasoning=response_dict["reasoning"],
        )

    chat_response = ChatResponse(reply=reply, session_id=session_id, restriction=restriction)

    interaction = ChatInteraction(
        message=body.message,
        reply=reply,
        restriction=restriction,
        timestamp=datetime.now().isoformat(),
    )
    try:
        await request.app.state.chat_storage.save_chat_interaction(
            user_id=user_id,
            session_id=session_id,
            interaction=interaction.model_dump(mode="json"),
        )
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Failed to save chat interaction to GCS: %s", e)

    return chat_response


@router.get(
    "/history",
    response_model=list[ChatHistorySummary],
    tags=["history"],
)
async def list_chat_history(
    request: Request,
    user_id: str = Depends(get_user_identity),
) -> list[ChatHistorySummary]:
    """Retrieve a list of past chat sessions for the current user."""
    try:
        sessions = await request.app.state.chat_storage.list_chat_sessions(user_id)
        return [ChatHistorySummary(**sess) for sess in sessions]
    except Exception as exc:
        logger.error("Failed to list chat history for user %s: %s", user_id, exc)
        raise HTTPException(status_code=500, detail="Failed to retrieve chat history.") from exc


@router.get(
    "/history/{session_id}",
    response_model=list[ChatInteraction],
    tags=["history"],
)
async def get_chat_history_detail(
    session_id: str,
    request: Request,
    user_id: str = Depends(get_user_identity),
) -> list[ChatInteraction]:
    """Retrieve the full chat interaction history for a specific session."""
    try:
        history = await request.app.state.chat_storage.get_chat_session(user_id, session_id)
        if not history:
            # We return empty instead of 404 so UI can start fresh smoothly.
            return []
        return [ChatInteraction(**interaction) for interaction in history]
    except Exception as exc:
        logger.error(
            "Failed to get chat details for user %s session %s: %s", user_id, session_id, exc
        )
        raise HTTPException(status_code=500, detail="Failed to retrieve chat session.") from exc


@router.delete(
    "/history/{session_id}",
    tags=["history"],
)
async def delete_chat_history_detail(
    session_id: str,
    request: Request,
    user_id: str = Depends(get_user_identity),
) -> dict[str, str]:
    """Delete a specific chat session."""
    try:
        await request.app.state.chat_storage.delete_chat_session(user_id, session_id)
        return {"status": "success", "message": f"Session {session_id} deleted"}
    except Exception as exc:
        logger.error(
            "Failed to delete chat session for user %s session %s: %s", user_id, session_id, exc
        )
        raise HTTPException(status_code=500, detail="Failed to delete chat session.") from exc


@router.delete(
    "/history",
    tags=["history"],
)
async def delete_all_chat_history(
    request: Request,
    user_id: str = Depends(get_user_identity),
) -> dict[str, str]:
    """Delete all chat sessions for the current user."""
    try:
        await request.app.state.chat_storage.delete_all_chat_sessions(user_id)
        return {"status": "success", "message": "All chat history deleted"}
    except Exception as exc:
        logger.error("Failed to delete all chat history for user %s: %s", user_id, exc)
        raise HTTPException(status_code=500, detail="Failed to delete all chat history.") from exc
