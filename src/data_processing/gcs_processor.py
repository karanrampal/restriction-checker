"""Utilities for processing data from Google Cloud Storage (GCS)."""

import json
import logging
from typing import Any

import gcsfs

logger = logging.getLogger(__name__)


class GCSChatStorage:
    """Manager for storing and retrieving chat history in GCS."""

    def __init__(self, project: str, bucket: str) -> None:
        """Initialize the storage manager.

        Args:
            project: The GCP project ID.
            bucket: The GCS bucket name to use for storage.
        """
        self.bucket = bucket
        self.fs = gcsfs.GCSFileSystem(project=project, asynchronous=True)

    def _get_path(self, user_id: str, session_id: str) -> str:
        """Helper to generate the file path for a specific session."""
        safe_user_id = user_id.replace("@", "_at_").replace(".", "_dot_")
        return f"{self.bucket}/chats/{safe_user_id}/{session_id}.json"

    async def save_chat_interaction(
        self, user_id: str, session_id: str, interaction: dict[str, Any]
    ) -> None:
        """Appends a new interaction to the user's session chat history in GCS.

        Args:
            user_id: The identifier for the user (e.g., email).
            session_id: The unique identifier for the chat session.
            interaction: A dictionary representing the chat interaction to save.
        """
        path = self._get_path(user_id, session_id)

        history = []
        if await self.fs._exists(path):  # pylint: disable=protected-access
            try:
                content = await self.fs._cat(path)  # pylint: disable=protected-access
                history = json.loads(content.decode("utf-8"))
            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.error("Failed to read existing chat history at %s: %s", path, e)

        history.append(interaction)

        try:
            content_bytes = json.dumps(history, indent=2).encode("utf-8")
            await self.fs._pipe(path, content_bytes)  # pylint: disable=protected-access
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Failed to write chat history at %s: %s", path, e)
            raise

    async def get_chat_session(self, user_id: str, session_id: str) -> list[dict[str, Any]]:
        """Retrieves the full chat history array for a specific session.

        Args:
            user_id: The identifier for the user (e.g., email).
            session_id: The unique identifier for the chat session.

        Returns:
            A list of dictionaries representing the chat interactions in the session.
        """
        path = self._get_path(user_id, session_id)
        if not await self.fs._exists(path):  # pylint: disable=protected-access
            return []

        try:
            content = await self.fs._cat(path)  # pylint: disable=protected-access
            return json.loads(content.decode("utf-8"))
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Failed to read chat history at %s: %s", path, e)
            return []

    async def list_chat_sessions(self, user_id: str) -> list[dict[str, Any]]:
        """Lists all chat sessions for a specific user, returning summaries.

        Args:
            user_id: The identifier for the user (e.g., email).

        Returns:
            A list of dictionaries containing session summaries.
        """
        safe_user_id = user_id.replace("@", "_at_").replace(".", "_dot_")
        dir_path = f"{self.bucket}/chats/{safe_user_id}"

        try:
            if not await self.fs._exists(dir_path):  # pylint: disable=protected-access
                return []

            files = await self.fs._ls(dir_path)  # pylint: disable=protected-access
            sessions = []

            for file_info in files:
                file_path = file_info if isinstance(file_info, str) else file_info.get("name", "")
                if not file_path.endswith(".json"):
                    continue

                # Extract session_id from "bucket/chats/user_id/session_id.json"
                session_id = file_path.split("/")[-1].replace(".json", "")

                created_at = "Unknown"
                try:
                    content = await self.fs._cat(file_path)  # pylint: disable=protected-access
                    data = json.loads(content.decode("utf-8"))
                    if data and isinstance(data, list) and "timestamp" in data[0]:
                        created_at = data[0]["timestamp"]
                except Exception:  # pylint: disable=broad-exception-caught
                    pass

                sessions.append({"session_id": session_id, "created_at": created_at})

            sessions.sort(key=lambda x: x["created_at"], reverse=True)
            return sessions

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Failed to list chat sessions for user %s: %s", user_id, e)
            return []

    async def delete_chat_session(self, user_id: str, session_id: str) -> None:
        """Deletes a chat session from GCS.

        Args:
            user_id: The identifier for the user (e.g., email).
            session_id: The unique identifier for the chat session.
        """
        path = self._get_path(user_id, session_id)
        if await self.fs._exists(path):  # pylint: disable=protected-access
            try:
                await self.fs._rm(path)  # pylint: disable=protected-access
            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.error("Failed to delete chat history at %s: %s", path, e)
                raise

    async def delete_all_chat_sessions(self, user_id: str) -> None:
        """Deletes all chat sessions for a specific user from GCS.

        Args:
            user_id: The identifier for the user (e.g., email).
        """
        safe_user_id = user_id.replace("@", "_at_").replace(".", "_dot_")
        dir_path = f"{self.bucket}/chats/{safe_user_id}"

        if await self.fs._exists(dir_path):  # pylint: disable=protected-access
            try:
                await self.fs._rm(dir_path, recursive=True)  # pylint: disable=protected-access
            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.error("Failed to delete all chat history at %s: %s", dir_path, e)
                raise
