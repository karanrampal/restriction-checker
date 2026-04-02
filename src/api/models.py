"""Pydantic request and response models for the API."""

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Request body for the /chat endpoint."""

    message: str = Field(description="The user's message or question. May contain an image URL.")
    session_id: str | None = Field(
        default=None,
        description="Session ID for multi-turn conversations. Omit to start a new session.",
    )


class CheckResponse(BaseModel):
    """Restriction check result for an image."""

    found: bool = Field(description="Whether a restricted item was found in the image.")
    item: str = Field(description="The restricted item found, or 'Ok' if none.")
    reasoning: str = Field(description="Reasoning behind the assessment.")


class ChatResponse(BaseModel):
    """Response body for the /chat endpoint."""

    reply: str = Field(description="The agent's text reply to the user's message.")
    session_id: str = Field(description="The session ID associated with this chat turn.")
    restriction: CheckResponse | None = Field(
        default=None,
        description="Restriction check result, present only when an image URL was detected.",
    )


class ChatInteraction(BaseModel):
    """A single turn in a chat session."""

    message: str = Field(description="The user's message for this turn.")
    reply: str = Field(description="The agent's text reply.")
    restriction: CheckResponse | None = Field(
        default=None,
        description="Restriction check result, present only when an image URL was detected.",
    )
    timestamp: str = Field(description="Timestamp of when the interaction occurred.")


class ChatHistorySummary(BaseModel):
    """Summary of a chat session for listing in the sidebar."""

    session_id: str = Field(description="Unique identifier for the session.")
    created_at: str = Field(description="Timestamp of the first interaction in the session.")
