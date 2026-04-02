"""Agent runner to manage sessions."""

import asyncio
import logging
from typing import Any

from google.adk.agents import BaseAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService, Session
from google.genai import types
from pydantic import ValidationError

from data_processing.image_processor import ImageType

logger = logging.getLogger(__name__)


class AgentRunner:
    """Runner to manage agent sessions and execute queries.

    Args:
        agent: The agent to run.
        app_name: Name of the application.
        max_retries: Maximum number of retries for validation errors.
        timeout: Maximum seconds to wait for each agent invocation.
            `None` disables the timeout.
    """

    def __init__(
        self,
        agent: BaseAgent,
        app_name: str,
        max_retries: int = 3,
        timeout: float | None = 180.0,
    ):
        self.agent = agent
        self.app_name = app_name
        self.max_retries = max_retries
        self.timeout = timeout
        self.session_service = InMemorySessionService()
        self.runner = Runner(
            agent=self.agent,
            app_name=self.app_name,
            session_service=self.session_service,
            auto_create_session=True,
        )

    async def _get_session(self, user_id: str, session_id: str) -> Session | None:
        """Retrieve the session for the given user and session ID.

        Args:
            user_id: The user ID.
            session_id: The session ID.

        Returns:
            The session object or `None` if not found.
        """
        return await self.session_service.get_session(
            app_name=self.app_name, user_id=user_id, session_id=session_id
        )

    async def run(
        self,
        user_id: str,
        session_id: str,
        user_input: str | ImageType,
        **kwargs: Any,
    ) -> str:
        """Run the agent with the given user question and handle validation retries.

        Args:
            user_id: The user ID.
            session_id: The session ID.
            user_input: User asked question or image to the agent.
            **kwargs: Initial session state (applied on first call only).

        Returns:
            Final response text from the agent.

        Raises:
            TimeoutError: If the agent does not respond within *timeout*.
        """
        ans = ""
        for attempt in range(self.max_retries + 1):
            try:
                ans = await asyncio.wait_for(
                    self._run_impl(user_id, session_id, user_input, **kwargs),
                    timeout=self.timeout,
                )
                break
            except TimeoutError as e:
                if attempt == self.max_retries:
                    raise TimeoutError(
                        f"Agent did not respond within {self.timeout}s"
                        f" for the user query after {self.max_retries} retries."
                    ) from e
                logger.warning(
                    "Attempt %d timed out for user query after %ss",
                    attempt + 1,
                    self.timeout,
                )
        return ans

    async def _run_impl(
        self,
        user_id: str,
        session_id: str,
        user_input: str | ImageType,
        **kwargs: Any,
    ) -> str:
        """Internal implementation of :meth:`run` (no timeout wrapper)."""
        if isinstance(user_input, ImageType):
            current_content = types.Content(
                role="user",
                parts=[
                    types.Part(text="Does this image have any restricted items?"),
                    user_input.part,
                ],
            )
            query = user_input.url
        else:
            current_content = types.Content(role="user", parts=[types.Part(text=user_input)])
            query = user_input
        current_state_delta: dict[str, Any] = {
            "current_user_query": query,
            "qa_agent_output_key": {},
            "restrictor_agent_output_key": {},
            **kwargs,
        }

        logger.info("Running on user query: %s ...", query)

        for attempt in range(self.max_retries + 1):
            try:
                final_response_text = "Agent did not produce a final response."

                async for event in self.runner.run_async(
                    user_id=user_id,
                    session_id=session_id,
                    new_message=current_content,
                    state_delta=current_state_delta,
                ):
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug(
                            "  [Event] Author: %s, Type: %s, Final: %s, Content: %s",
                            event.author,
                            type(event).__name__,
                            event.is_final_response(),
                            event.model_dump_json(indent=2, exclude_none=True),
                        )
                    if event.is_final_response():
                        if event.content and event.content.parts:
                            response_parts = [p for p in event.content.parts if not p.thought]
                            if response_parts:
                                final_response_text = response_parts[0].text or ""
                        elif event.actions and event.actions.escalate:
                            final_response_text = (
                                f"Agent escalated: {event.error_message or 'No specific message.'}"
                            )

                break

            except ValidationError as e:
                logger.warning(
                    "Attempt %d failed validation for user query %s: %s", attempt + 1, query, e
                )

                if attempt == self.max_retries:
                    logger.error(
                        "Max retries exceeded for user %s, session %s.", user_id, session_id
                    )
                    raise

                feedback_message = (
                    f"Your previous response failed validation with the following error: {e}. "
                    "Please correct the format and try again."
                )

                current_content = types.Content(
                    role="user", parts=[types.Part(text=feedback_message)]
                )

                # Clear state_delta so we don't overwrite the original context
                current_state_delta = {}

        return final_response_text

    async def get_session_state(self, user_id: str, session_id: str) -> dict[str, Any]:
        """Return the current state of the session.

        Args:
            user_id: The user ID.
            session_id: The session ID.

        Returns:
            The session state.
        """
        session = await self._get_session(user_id, session_id)
        if session:
            return session.state
        return {}

    async def get_session_history(self, user_id: str, session_id: str) -> list[Any]:
        """Return the event history of the session.

        Args:
            user_id: The user ID.
            session_id: The session ID.

        Returns:
            The list of events in the session.
        """
        session = await self._get_session(user_id, session_id)
        if session:
            return session.events
        return []

    async def reset_session(self, user_id: str, session_id: str) -> None:
        """Completely delete the session (history and state).

        Args:
            user_id: The user ID.
            session_id: The session ID.
        """
        logger.info("Resetting session for user: %s, session: %s", user_id, session_id)
        await self.session_service.delete_session(
            app_name=self.app_name, user_id=user_id, session_id=session_id
        )

    async def clear_history_only(self, user_id: str, session_id: str) -> None:
        """Clear the conversation history but keep the session state.

        Args:
            user_id: The user ID.
            session_id: The session ID.
        """
        session = await self._get_session(user_id, session_id)
        if session:
            logger.info("Clearing history for user: %s, session: %s", user_id, session_id)
            current_state = session.state

            await self.session_service.delete_session(
                app_name=self.app_name, user_id=user_id, session_id=session_id
            )

            await self.session_service.create_session(
                app_name=self.app_name,
                user_id=user_id,
                session_id=session_id,
                state=current_state,
            )
