"""Unit tests for the core utils module."""

import re

import pytest

from core.utils import (
    check_url_extension,
    check_url_prefix,
    extract_all_urls_from_text,
    extract_url_from_text,
)


class TestExtractUrlFromText:
    """Tests for the extract_url_from_text helper."""

    def test_extracts_url(self) -> None:
        """Extracts a plain URL embedded in text."""
        assert (
            extract_url_from_text("Check this: https://example.com/image.jpg")
            == "https://example.com/image.jpg"
        )

    def test_no_url_returns_none(self) -> None:
        """Returns None when no URL is present."""
        assert extract_url_from_text("no url here") is None

    def test_url_with_query_params(self) -> None:
        """Preserves query parameters in the extracted URL."""
        url = "https://example.com/img?foo=bar&baz=1"
        assert extract_url_from_text(f"url: {url}") == url

    def test_first_url_extracted_from_multiple(self) -> None:
        """Returns only the first URL when multiple are present."""
        text = "https://first.com and https://second.com"
        assert extract_url_from_text(text) == "https://first.com"

    def test_strips_trailing_period(self) -> None:
        """Trailing period is not included in the extracted URL."""
        result = extract_url_from_text("See https://example.com/page.")
        assert result is not None
        assert not result.endswith(".")

    def test_strips_trailing_comma(self) -> None:
        """Trailing comma is not included in the extracted URL."""
        result = extract_url_from_text("Visit https://example.com/page, then continue.")
        assert result is not None
        assert not result.endswith(",")

    def test_url_only_input(self) -> None:
        """Works when the input is a bare URL with no surrounding text."""
        assert extract_url_from_text("https://example.com") == "https://example.com"

    def test_empty_string_returns_none(self) -> None:
        assert extract_url_from_text("") is None

    def test_returns_first_url(self) -> None:
        assert (
            extract_url_from_text("See https://example.com for details.") == "https://example.com"
        )

    def test_returns_none_when_no_url(self) -> None:
        assert extract_url_from_text("no links here") is None


class TestCheckUrlExtension:
    """Tests for check_url_extension."""

    @pytest.mark.parametrize(
        "url",
        [
            "https://example.com/photo.jpg",
            "https://example.com/photo.jpeg",
            "https://example.com/image.PNG",
            "https://example.com/image.WEBP",
            "https://example.com/anim.gif",
            "https://example.com/drawing.bmp",
            "https://example.com/scan.tiff",
            "https://example.com/scan.tif",
        ],
    )
    def test_recognises_image_extensions(self, url: str) -> None:
        """Known image extensions return True."""
        assert check_url_extension(url) is True

    def test_url_with_query_string(self) -> None:
        """Query string after the extension is allowed."""
        assert check_url_extension("https://cdn.example.com/img.jpg?v=2&size=large") is True

    def test_non_image_extension_returns_false(self) -> None:
        assert check_url_extension("https://example.com/document.pdf") is False

    def test_no_extension_returns_false(self) -> None:
        assert check_url_extension("https://example.com/path/to/resource") is False

    def test_empty_string_returns_false(self) -> None:
        assert check_url_extension("") is False

    def test_custom_pattern(self) -> None:
        """Accepts an alternative compiled pattern."""
        pdf_pattern = re.compile(r"\.pdf$", re.IGNORECASE)
        assert check_url_extension("https://example.com/report.pdf", pdf_pattern) is True
        assert check_url_extension("https://example.com/report.jpg", pdf_pattern) is False


class TestCheckUrlPrefix:
    """Tests for check_url_prefix."""

    def test_matching_prefix(self) -> None:
        assert (
            check_url_prefix("https://example.com/images/cat.jpg", ["https://example.com/"]) is True
        )

    def test_no_matching_prefix(self) -> None:
        assert check_url_prefix("https://other.com/cat.jpg", ["https://example.com/"]) is False

    def test_multiple_prefixes_first_matches(self) -> None:
        prefixes = ["https://a.com/", "https://b.com/"]
        assert check_url_prefix("https://a.com/img.png", prefixes) is True

    def test_multiple_prefixes_second_matches(self) -> None:
        prefixes = ["https://a.com/", "https://b.com/"]
        assert check_url_prefix("https://b.com/img.png", prefixes) is True

    def test_empty_prefix_list_returns_false(self) -> None:
        assert check_url_prefix("https://example.com/img.png", []) is False

    def test_partial_prefix_does_not_match(self) -> None:
        """A prefix that doesn't fully include the path segment should not match."""
        assert (
            check_url_prefix("https://example.com/images/cat.jpg", ["https://example.com/v"])
            is False
        )

    def test_exact_url_matches_itself_as_prefix(self) -> None:
        url = "https://example.com/img.jpg"
        assert check_url_prefix(url, [url]) is True


class TestExtractAllUrlsFromText:
    """Tests for extract_all_urls_from_text."""

    def test_returns_all_urls(self) -> None:
        text = "First: https://a.com/1 and second: https://b.com/2"
        assert extract_all_urls_from_text(text) == ["https://a.com/1", "https://b.com/2"]

    def test_single_url(self) -> None:
        assert extract_all_urls_from_text("Visit https://example.com/page") == [
            "https://example.com/page"
        ]

    def test_no_urls_returns_empty_list(self) -> None:
        assert extract_all_urls_from_text("no links here") == []

    def test_empty_string_returns_empty_list(self) -> None:
        assert extract_all_urls_from_text("") == []

    def test_trailing_punctuation_stripped(self) -> None:
        """Trailing punctuation is not included in any extracted URL."""
        urls = extract_all_urls_from_text("Go to https://a.com/x. Then https://b.com/y,")
        assert urls == ["https://a.com/x", "https://b.com/y"]

    def test_urls_with_query_params(self) -> None:
        text = "img1: https://cdn.example.com/a.jpg?w=100 img2: https://cdn.example.com/b.jpg?w=200"
        urls = extract_all_urls_from_text(text)
        assert urls == [
            "https://cdn.example.com/a.jpg?w=100",
            "https://cdn.example.com/b.jpg?w=200",
        ]

    def test_duplicate_urls_both_returned(self) -> None:
        """The same URL appearing twice is returned twice."""
        text = "https://example.com https://example.com"
        assert extract_all_urls_from_text(text) == ["https://example.com", "https://example.com"]
