"""Shared utility helpers."""

import re

_URL_RE = re.compile(r'https?://[^\s]+[^.,;:?!"\'\s]')
_IMAGE_EXTENSION_RE = re.compile(
    r"\.(?:jpg|jpeg|png|gif|webp|bmp|tiff|tif)(\?.*)?$",
    re.IGNORECASE,
)


def check_url_extension(url: str, pattern: re.Pattern = _IMAGE_EXTENSION_RE) -> bool:
    """Check if the URL has a specific file extension."""
    return bool(pattern.search(url))


def check_url_prefix(url: str, allowed_prefixes: list[str]) -> bool:
    """Check if the URL starts with any of the allowed prefixes."""
    return any(url.startswith(prefix) for prefix in allowed_prefixes)


def extract_url_from_text(text: str) -> str | None:
    """Return the first URL found in *text*, or None if no URL is present.

    Args:
        text: The input text to search for a URL.

    Returns:
        The first URL found in the text, or None if no URL is found.
    """
    m = _URL_RE.search(text)
    return m.group(0) if m else None


def extract_all_urls_from_text(text: str) -> list[str]:
    """Return all URLs found in *text*.

    Args:
        text: The input text to search for URLs.

    Returns:
        A list of all URLs found in the text (may be empty).
    """
    return _URL_RE.findall(text)
