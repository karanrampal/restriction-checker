"""Streamlit front-end for the restriction-checker API."""

import base64
import json
import os
import uuid
from typing import Any

import google.auth.transport.requests
import google.oauth2.id_token
import httpx
import streamlit as st

from core.config import AppConfig, load_config
from core.utils import check_url_extension, check_url_prefix, extract_url_from_text

API_URL = os.environ.get("API_URL", "http://localhost:8080")


@st.cache_resource
def _load_config() -> AppConfig:
    """Load and cache the application configuration."""
    return load_config()


def _extract_image_url(text: str) -> str | None:
    """Return the first image URL found in *text*, or None."""
    url = extract_url_from_text(text)
    if not url or not check_url_extension(url):
        return None
    allowed_prefixes = _load_config().api.allowed_url_prefixes  # pylint: disable=no-member
    if allowed_prefixes and not check_url_prefix(url, allowed_prefixes):
        return None
    return url


def _render_user_message(content: str) -> None:
    """Write user message text and, if an image URL is present, display the image."""
    st.write(content)
    image_url = _extract_image_url(content)
    if image_url:
        st.image(image_url)


def _get_iap_user_email() -> str | None:
    """Extract user email from the IAP JWT assertion."""
    iap_jwt = st.context.headers.get("x-goog-iap-jwt-assertion")
    if not iap_jwt:
        return None

    try:
        segments = iap_jwt.split(".")
        if len(segments) != 3:
            return None

        payload_b64 = segments[1]
        payload_b64 += "=" * (4 - len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))

        extracted = payload.get("email") or payload.get("sub")
        return str(extracted) if extracted else None
    except Exception as e:  # pylint: disable=broad-exception-caught
        st.warning(f"Failed to decode IAP JWT: {e}")
        return None


def _get_api_headers() -> dict[str, str]:
    """Helper to get authentication headers for the API."""
    headers = {}
    if not API_URL.startswith("http://localhost") and not API_URL.startswith("http://127.0.0.1"):
        try:
            auth_req = google.auth.transport.requests.Request()
            token = google.oauth2.id_token.fetch_id_token(auth_req, API_URL)
            headers["Authorization"] = f"Bearer {token}"

            extracted_email = _get_iap_user_email()
            if extracted_email:
                headers["X-App-User-Email"] = extracted_email
        except Exception as e:  # pylint: disable=broad-exception-caught
            st.warning(f"Failed to fetch ID token: {e}")
    return headers


def get_chat_history() -> list[dict[str, Any]]:
    """Fetch the list of chat sessions for the current user."""
    headers = _get_api_headers()
    try:
        response = httpx.get(f"{API_URL}/history", headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:  # pylint: disable=broad-exception-caught
        st.sidebar.error(f"Failed to load history: {e}")
        return []


def get_chat_session(session_id: str) -> list[dict[str, Any]]:
    """Fetch the full interactions for a specific chat session."""
    headers = _get_api_headers()
    try:
        response = httpx.get(f"{API_URL}/history/{session_id}", headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:  # pylint: disable=broad-exception-caught
        st.error(f"Failed to load chat session: {e}")
        return []


def delete_chat_session(session_id: str) -> None:
    """Delete the chat session."""
    headers = _get_api_headers()
    try:
        response = httpx.delete(f"{API_URL}/history/{session_id}", headers=headers, timeout=30)
        response.raise_for_status()
    except Exception as e:  # pylint: disable=broad-exception-caught
        st.sidebar.error(f"Failed to delete chat session: {e}")


def delete_all_chat_history() -> None:
    """Delete all chat history."""
    headers = _get_api_headers()
    try:
        response = httpx.delete(f"{API_URL}/history", headers=headers, timeout=30)
        response.raise_for_status()
    except Exception as e:  # pylint: disable=broad-exception-caught
        st.sidebar.error(f"Failed to delete all chat history: {e}")


def send_chat_message(message: str, session_id: str) -> dict[str, Any]:
    """Call the /chat endpoint and return the parsed response."""
    headers = _get_api_headers()
    response = httpx.post(
        f"{API_URL}/chat",
        json={"message": message, "session_id": session_id},
        headers=headers,
        timeout=180,
    )
    response.raise_for_status()
    return response.json()


def render_assistant_message(payload: dict[str, Any] | str) -> None:
    """Render an assistant message from either a live response or stored history."""
    if isinstance(payload, str):
        st.error(payload)
        return

    st.write(payload.get("reply", ""))

    restriction = payload.get("restriction")
    if restriction:
        if restriction.get("found"):
            st.info(f"Restricted item found: **{restriction.get('item', 'Unknown')}**")
        else:
            st.success("No restricted items found.")
        st.write(f"**Reasoning:** {restriction.get('reasoning', '')}")
        with st.expander("Raw JSON"):
            st.json(restriction)


def render_history() -> None:
    """Replay the full chat history."""
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            if message["role"] == "user":
                _render_user_message(message["content"])
            else:
                render_assistant_message(message["content"])


def render_sidebar() -> None:
    """Render the sidebar with chat history and actions."""
    with st.sidebar:
        st.header("Chat History")

        if st.button("➕ New Chat", use_container_width=True):
            st.session_state.session_id = str(uuid.uuid4())
            st.session_state.messages = []
            st.rerun()

        if st.button("🗑️ Delete All History", use_container_width=True):
            delete_all_chat_history()
            st.session_state.session_id = str(uuid.uuid4())
            st.session_state.messages = []
            st.rerun()

        st.divider()

        sessions = get_chat_history()
        if sessions:
            st.subheader("Past Sessions")
            for summary in sessions:
                sid = summary["session_id"]
                display_name = f"{summary.get('created_at', sid)[:10]}... ({sid[:5]})"

                col1, col2 = st.columns([4, 1])
                with col1:
                    if st.button(display_name, key=sid, use_container_width=True):
                        st.session_state.session_id = sid
                        interactions = get_chat_session(sid)

                        st.session_state.messages = []
                        for interaction in interactions:
                            st.session_state.messages.append(
                                {
                                    "role": "user",
                                    "content": interaction.get("message", ""),
                                }
                            )
                            st.session_state.messages.append(
                                {
                                    "role": "assistant",
                                    "content": {
                                        "reply": interaction.get("reply", ""),
                                        "restriction": interaction.get("restriction"),
                                    },
                                }
                            )
                        st.rerun()
                with col2:
                    if st.button("🗑️", key=f"del_{sid}"):
                        delete_chat_session(sid)
                        if st.session_state.session_id == sid:
                            st.session_state.session_id = str(uuid.uuid4())
                            st.session_state.messages = []
                        st.rerun()
        else:
            st.info("No past chats found.")


def main() -> None:
    """Main Streamlit app entry point."""
    st.set_page_config(page_title="Restriction Checker", page_icon="🔍", layout="wide")
    st.title("Restriction Checker")

    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
    if "messages" not in st.session_state:
        st.session_state.messages = []

    render_sidebar()

    render_history()

    if user_message := st.chat_input("Ask a question or paste an image URL…"):
        st.session_state.messages.append({"role": "user", "content": user_message})
        with st.chat_message("user"):
            _render_user_message(user_message)

        with st.chat_message("assistant"), st.spinner("Thinking…"):
            try:
                data = send_chat_message(user_message, st.session_state.session_id)
            except httpx.HTTPStatusError as e:
                msg = f"API error {e.response.status_code}: {e.response.text}"
                st.error(msg)
                st.session_state.messages.append({"role": "assistant", "content": msg})
            except Exception as e:  # pylint: disable=broad-exception-caught
                msg = f"Request failed: {e}"
                st.error(msg)
                st.session_state.messages.append({"role": "assistant", "content": msg})
            else:
                # Keep session_id in sync with what the API assigned
                st.session_state.session_id = data["session_id"]
                assistant_payload = {
                    "reply": data["reply"],
                    "restriction": data.get("restriction"),
                }
                render_assistant_message(assistant_payload)
                st.session_state.messages.append(
                    {"role": "assistant", "content": assistant_payload}
                )


main()
