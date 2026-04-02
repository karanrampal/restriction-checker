"""Unit tests for the QA agent module."""

from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm

from agents.qa import QAResponse, create_qa_agent
from core.config import AgentConfig


class TestQAResponse:
    """Tests for the QAResponse schema."""

    def test_valid_instantiation(self) -> None:
        resp = QAResponse(url="https://example.com", answer="Here is your answer.")
        assert resp.url == "https://example.com"
        assert resp.answer == "Here is your answer."

    def test_empty_url(self) -> None:
        """Empty string is a valid url value (no URL in the query)."""
        resp = QAResponse(url="", answer="No URL detected.")
        assert resp.url == ""


class TestCreateQaAgent:
    """Tests for create_qa_agent."""

    def test_create_with_base_url(self, agent_config: AgentConfig) -> None:
        """Agent uses LiteLlm proxy when base_url is configured."""
        agent = create_qa_agent(agent_config)

        assert isinstance(agent, LlmAgent)
        assert agent.name == "qa_agent"
        assert isinstance(agent.model, LiteLlm)
        assert getattr(agent.model, "model") == "test-model"
        assert getattr(agent.model, "_additional_args").get("api_base") == "http://test-url"

    def test_create_without_base_url(self) -> None:
        """Agent uses native model string when no base_url is given."""
        config = AgentConfig(model_name="gemini-pro", base_url=None)
        agent = create_qa_agent(config)

        assert isinstance(agent, LlmAgent)
        assert agent.model == "gemini-pro"

    def test_output_key_and_schema(self, agent_config: AgentConfig) -> None:
        agent = create_qa_agent(agent_config)

        assert agent.output_key == "qa_agent_output_key"
        assert agent.output_schema == QAResponse

    def test_generate_content_config_defaults(self) -> None:
        """Generation config values are forwarded from AgentConfig defaults."""
        config = AgentConfig(model_name="gemini-pro", base_url=None, temperature=0.5)
        agent = create_qa_agent(config)

        assert agent.generate_content_config is not None
        assert agent.generate_content_config.temperature == 0.5
