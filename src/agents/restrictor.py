"""Module for creating a Restrictor Agent."""

from google.adk.agents import LlmAgent
from pydantic import BaseModel, Field

from agents.base import AgentSpec, create_agent
from agents.system_instructions import RESTRICTOR_INSTRUCTION
from core.config import AgentConfig


class RestrictorItemResponse(BaseModel):
    """The structured output response to generate for restricted items."""

    found: bool = Field(description="If the restricted item was found or not")
    item: str = Field(description="The restricted item that was found else `Ok`")
    reasoning: str = Field(description="Your reasoning for the answer")


def create_restrictor_agent(agent_config: AgentConfig) -> LlmAgent:
    """Create the Restrictor Agent.

    Args:
        agent_config: Configuration for the agent.

    Returns:
        Configured Restrictor Agent.
    """
    agent_spec = AgentSpec(
        name="restrictor_agent",
        description="Agent to check if image contains restricted items.",
        instruction=RESTRICTOR_INSTRUCTION,
        output_schema=RestrictorItemResponse,
    )
    return create_agent(
        agent_spec=agent_spec,
        agent_config=agent_config,
    )
