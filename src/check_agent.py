#!/usr/bin/env python
"""Main entry point for the Restriction Checker agent."""

import asyncio
import json

from agents.agent_runner import AgentRunner
from agents.chatbot import create_chat_agent
from agents.qa import create_qa_agent
from agents.restrictor import create_restrictor_agent
from core.config import load_config
from core.logger import setup_logger
from data_processing.image_processor import process_image

URL = "https://imagebankstorageprod.blob.core.windows.net/articleimagebank/4-2026/cf385c86-f26c-4e1c-a749-206fbbba7979/new-%20dune%20for%20print%2009-104.png?sv=2025-07-05&se=2032-01-13T13%3A59%3A31Z&sr=b&sp=rw&sig=4gqFkgcNpRiP3i%2BgD8tp1OzwHjRjNV%2BnCXhtkRYd4iE%3D"  # pylint: disable=line-too-long

TEST_AGENT = "chat"  # Change to "chat" or "restrictor" to test other agents


async def main() -> None:
    """Main function to run the agent."""
    setup_logger(keep_loggers=["agents", "core", "data_processing", "__main__"])

    config = load_config()

    chat_agent = create_chat_agent(config.agents)
    qa_agent = create_qa_agent(config.agents["qa"])
    restrictor_agent = create_restrictor_agent(config.agents["restrictor"])

    agent = (
        qa_agent if TEST_AGENT == "qa" else chat_agent if TEST_AGENT == "chat" else restrictor_agent
    )
    agent_runner = AgentRunner(agent=agent, app_name="TestApp")

    question = f"Hello, how are you? {URL}"
    image = await process_image(URL)
    query = image if TEST_AGENT == "restrictor" else question

    user_id = "test_user"
    session_id = "test_session"

    try:
        response = await agent_runner.run(user_id=user_id, session_id=session_id, user_input=query)
        print(f"\nRaw LLM response:\n{response}")
        print(f"\nParsed response:\n{json.loads(response)}")
    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f"\nError running agent: {e}")

    state = await agent_runner.get_session_state(user_id, session_id)
    print(f"\nSession state:\n{state}")

    hist = await agent_runner.get_session_history(user_id, session_id)
    print(f"\nSession history:\n{hist}")


if __name__ == "__main__":
    asyncio.run(main())
