"""Custom implementation of a chatbot."""

import json
import logging
from collections.abc import AsyncGenerator
from typing import override

from google.adk.agents import BaseAgent, LlmAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events.event import Event, EventActions
from google.genai import types
from pydantic import ValidationError

from agents.qa import create_qa_agent
from agents.restrictor import create_restrictor_agent
from core.config import AgentConfig
from data_processing.image_processor import process_image

logger = logging.getLogger(__name__)


class ChatAgent(BaseAgent):  # pylint: disable=abstract-method
    """A chatbot that will answer user queries and if an image url is provided, it will analyze
    the image and check for restricted items.

    Args:
        name: Name of the agent.
        qa_agent: Agent responsible for answering user queries.
        restrictor_agent: Agent responsible for checking if the query contains restricted items.
    """

    qa_agent: LlmAgent
    restrictor_agent: LlmAgent
    max_retries: int = 3

    model_config = {"arbitrary_types_allowed": True}

    def __init__(
        self,
        name: str,  # pylint: disable=unused-argument
        qa_agent: LlmAgent,
        restrictor_agent: LlmAgent,
        max_retries: int = 3,
    ):
        super().__init__(
            name="chat_agent",
            description=(
                "A chatbot that will answer users queries and possibly check for restricted items."
            ),
            qa_agent=qa_agent,
            restrictor_agent=restrictor_agent,
            max_retries=max_retries,
            sub_agents=[qa_agent, restrictor_agent],
        )  # type: ignore [call-arg]

    async def _run_agent_with_retry(
        self,
        agent: LlmAgent,
        base_ctx: InvocationContext,
        state_key: str,
    ) -> tuple[list[Event], dict]:
        """Run agent with retry logic on ValidationError.

        Args:
            agent: The sub-agent to run.
            base_ctx: The base invocation context (never mutated).
            state_key: The `state_delta` key whose value is extracted as output.

        Returns:
            A tuple of `(collected_events, output_dict)`.

        Raises:
            RuntimeError: When retries are exhausted.
        """
        events: list[Event] = []
        output: dict = {}
        ctx = base_ctx
        for attempt in range(self.max_retries + 1):
            events = []
            output = {}
            try:
                async for event in agent.run_async(ctx):
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug(
                            "[%s] Event from %s: %s",
                            self.name,
                            agent.name,
                            event.model_dump_json(indent=2, exclude_none=True),
                        )
                    if event.actions and event.actions.state_delta:
                        delta = event.actions.state_delta.get(state_key)
                        if isinstance(delta, dict):
                            output.update(delta)
                    events.append(event)
                break
            except ValidationError as e:
                logger.warning(
                    "%s: %s attempt %d failed validation: %s",
                    self.name,
                    agent.name,
                    attempt + 1,
                    e,
                )
                if attempt == self.max_retries:
                    logger.error("%s: %s exhausted retries.", self.name, agent.name)
                    raise RuntimeError(
                        f"{self.name}: {agent.name} failed after {self.max_retries} retries."
                    ) from e
                ctx = base_ctx.model_copy(
                    update={
                        "user_content": types.Content(
                            role="user",
                            parts=(
                                base_ctx.user_content.parts or [] if base_ctx.user_content else []
                            )
                            + [
                                types.Part(
                                    text=(
                                        f"Your previous response failed validation: {e}. "
                                        "Please correct the format and try again."
                                    )
                                )
                            ],
                        )
                    }
                )
        return events, output

    @override
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        logger.info("%s: Starting execution.", self.name)

        qa_events, qa_output = await self._run_agent_with_retry(
            self.qa_agent, ctx, "qa_agent_output_key"
        )
        for event in qa_events:
            yield event

        if not qa_output:
            logger.error("%s: Missing 'qa_agent_output_key' after qa_agent run.", self.name)
            return

        logger.info(
            "%s: Retrieved 'qa_agent_output_key': %s", self.name, json.dumps(qa_output, indent=2)
        )

        if not qa_output["url"]:
            logger.info("%s: Finished execution.", self.name)
            yield Event(
                author=self.name,
                content=types.Content(
                    role="model",
                    parts=[types.Part(text=json.dumps(qa_output))],
                ),
                actions=EventActions(state_delta={"qa_agent_output_key": qa_output}),
            )
            return

        try:
            image = await process_image(qa_output["url"])
            restrictor_ctx = ctx.model_copy(deep=True)
            if restrictor_ctx.user_content and restrictor_ctx.user_content.parts:
                restrictor_ctx.user_content.parts += [
                    types.Part(text="Does this image have any restricted items?"),
                    image.part,
                ]
            else:
                restrictor_ctx.user_content = types.Content(
                    role="user",
                    parts=[
                        types.Part(text="Does this image have any restricted items?"),
                        image.part,
                    ],
                )
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Failed to fetch image: %s", e)
            yield Event(
                author=self.name,
                content=types.Content(
                    role="model",
                    parts=[types.Part(text=f"Failed to fetch the image: {e}. Please try again.")],
                ),
            )
            return

        restrictor_events, restrictor_output = await self._run_agent_with_retry(
            self.restrictor_agent, restrictor_ctx, "restrictor_agent_output_key"
        )
        for event in restrictor_events:
            yield event

        if not restrictor_output:
            logger.error(
                "%s: Missing 'restrictor_agent_output_key' after restrictor_agent run.", self.name
            )
            return

        logger.info(
            "%s: Retrieved 'restrictor_agent_output_key': %s",
            self.name,
            json.dumps(restrictor_output, indent=2),
        )
        logger.info("%s: Finished execution.", self.name)
        yield Event(
            author=self.name,
            content=types.Content(
                role="model",
                parts=[types.Part(text=json.dumps(qa_output | restrictor_output))],
            ),
            actions=EventActions(
                state_delta={
                    "qa_agent_output_key": qa_output,
                    "restrictor_agent_output_key": restrictor_output,
                },
            ),
        )


def create_chat_agent(agent_configs: dict[str, AgentConfig]) -> ChatAgent:
    """Creates the Chat Agent.
    Args:
        agent_configs: Configuration for the agents.
    Returns:
        Configured Chat Agent.
    """
    return ChatAgent(
        name="chat_agent",
        qa_agent=create_qa_agent(agent_configs["qa"]),
        restrictor_agent=create_restrictor_agent(agent_configs["restrictor"]),
        max_retries=3,
    )
