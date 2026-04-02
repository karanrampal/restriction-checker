"""Unit tests for the restrictor agent module."""

from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm

from agents.restrictor import RestrictorItemResponse, create_restrictor_agent
from core.config import AgentConfig


class TestRestrictorItemResponse:  # pylint: disable=too-few-public-methods
    """Tests for the RestrictorItemResponse schema."""

    def test_valid_instantiation(self) -> None:
        """Test creating a valid response object."""
        response = RestrictorItemResponse(
            found=True, item="Weapon", reasoning="Looks like a weapon."
        )
        assert response.found is True
        assert response.item == "Weapon"
        assert response.reasoning == "Looks like a weapon."


class TestCreateRestrictorAgent:
    """Tests for create_restrictor_agent."""

    def test_create_with_base_url(self, agent_config: AgentConfig) -> None:
        """Test creating agent using LiteLlm proxy (with base_url).

        This dynamically utilizes the 'agent_config' fixture from conftest.py
        which has base_url configured already.
        """
        agent = create_restrictor_agent(agent_config)

        assert isinstance(agent, LlmAgent)
        assert agent.name == "restrictor_agent"
        assert isinstance(agent.model, LiteLlm)
        assert getattr(agent.model, "model") == "test-model"
        assert getattr(agent.model, "_additional_args").get("api_base") == "http://test-url"
        assert agent.output_key == "restrictor_agent_output_key"
        assert agent.output_schema == RestrictorItemResponse

    def test_create_without_base_url(self) -> None:
        """Test creating agent using native model string (no base_url)."""
        config = AgentConfig(model_name="gemini-pro", base_url=None)
        agent = create_restrictor_agent(config)

        assert isinstance(agent, LlmAgent)
        assert agent.model == "gemini-pro"
        assert agent.generate_content_config is not None
        assert agent.generate_content_config.temperature is None
        assert agent.generate_content_config.max_output_tokens is None
