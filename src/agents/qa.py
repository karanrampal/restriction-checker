"""Module for creating a QA Agent."""

from google.adk.agents import LlmAgent
from pydantic import BaseModel, Field

from agents.base import AgentSpec, create_agent
from agents.system_instructions import QA_INSTRUCTION
from core.config import AgentConfig


class QAResponse(BaseModel):
    """The structured output response to generate by the qa agent."""

    url: str = Field(
        description="The extracted URL from the user question or empty string if no url present"
    )
    answer: str = Field(description="QA agents response to the user question")


def create_qa_agent(agent_config: AgentConfig) -> LlmAgent:
    """Create the question answering agent.

    Args:
        agent_config: Configuration for the agent.

    Returns:
        Configured question answering agent.
    """
    agent_spec = AgentSpec(
        name="qa_agent",
        description="Agent to answer user queries.",
        instruction=QA_INSTRUCTION,
        output_schema=QAResponse,
    )
    return create_agent(
        agent_spec=agent_spec,
        agent_config=agent_config,
    )
