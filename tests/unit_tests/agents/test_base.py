"""Unit tests for the base agent module."""

from google.adk.planners import BuiltInPlanner
from google.genai import types

from agents.base import _build_planner
from core.config import AgentConfig


class TestBuildPlanner:
    """Tests for the _build_planner helper function."""

    def test_no_planner(self) -> None:
        """Test returns None when no thinking_level is set."""
        config = AgentConfig(model_name="test")
        planner = _build_planner(config)
        assert planner is None

    def test_level_planner(self) -> None:
        """Test creates planner with thinking level."""
        config = AgentConfig(
            model_name="gemini-3.1-pro-preview",
            thinking_level=types.ThinkingLevel.HIGH,
        )
        planner = _build_planner(config)
        assert isinstance(planner, BuiltInPlanner)
        assert planner.thinking_config.thinking_level == types.ThinkingLevel.HIGH
