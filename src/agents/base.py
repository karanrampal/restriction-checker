"""Base agent utilities"""

from dataclasses import dataclass

from google.adk.agents import LlmAgent
from google.adk.agents.llm_agent import ToolUnion
from google.adk.models.lite_llm import LiteLlm
from google.adk.planners import BuiltInPlanner
from google.genai import types
from pydantic import BaseModel

from core.config import AgentConfig

_SAFETY_SETTINGS: list[types.SafetySetting] = [
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
        threshold=types.HarmBlockThreshold.BLOCK_LOW_AND_ABOVE,
    ),
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
        threshold=types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    ),
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
        threshold=types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    ),
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
        threshold=types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    ),
]


def _build_planner(agent_config: AgentConfig) -> BuiltInPlanner | None:
    """Return a planner with thinking enabled, or `None` when disabled.

    Only gemini-3.1 models use thinking; controlled via ``thinking_level``.
    All other models have no planner.
    """
    if agent_config.thinking_level is None:
        return None

    return BuiltInPlanner(
        thinking_config=types.ThinkingConfig(
            include_thoughts=True,
            thinking_level=agent_config.thinking_level,
        )
    )


@dataclass(frozen=True)
class AgentSpec:
    """Specification defining an agent's behavior and capabilities."""

    name: str
    description: str
    instruction: str
    output_schema: type[BaseModel] | None = None
    tools: list[ToolUnion] | None = None


def create_agent(
    agent_spec: AgentSpec,
    agent_config: AgentConfig,
) -> LlmAgent:
    """Create an agent with the given configuration.

    Args:
        agent_spec: Specification of the agent's behavior and capabilities.
        agent_config: Configuration for the agent.

    Returns:
        Configured Agent.
    """
    client = (
        LiteLlm(model=agent_config.model_name, api_base=agent_config.base_url)
        if agent_config.base_url
        else agent_config.model_name
    )
    return LlmAgent(
        model=client,
        name=agent_spec.name,
        description=agent_spec.description,
        planner=_build_planner(agent_config),
        generate_content_config=types.GenerateContentConfig(
            temperature=agent_config.temperature,
            top_p=agent_config.top_p,
            max_output_tokens=agent_config.max_output_tokens,
            safety_settings=_SAFETY_SETTINGS,
        ),
        output_schema=agent_spec.output_schema,
        output_key=f"{agent_spec.name}_output_key",
        instruction=agent_spec.instruction,
        tools=agent_spec.tools or [],
    )
