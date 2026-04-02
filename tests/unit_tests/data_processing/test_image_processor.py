"""Unit tests for the image_processor module."""

import io
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from google.genai import types
from PIL import Image

from data_processing.image_processor import (
    ImageType,
    _convert_to_png,
    _downscale_image,
    download_image,
    get_mime_type,
    process_image,
)


class TestImageType:  # pylint: disable=too-few-public-methods
    """Tests for the ImageType class."""

    def test_image_type_initialization(self) -> None:
        """Test default and custom initialization."""
        part = types.Part.from_bytes(data=b"test", mime_type="image/jpeg")

        img1 = ImageType(url="http://example.com/a.jpg", part=part)
        assert img1.id is not None
        assert img1.url == "http://example.com/a.jpg"
        assert img1.part is part

        img2 = ImageType(id="custom-id", url="http://example.com/b.jpg", part=part)
        assert img2.id == "custom-id"


class TestGetMimeType:
    """Tests for get_mime_type."""

    @pytest.mark.parametrize(
        "url,expected",
        [
            ("http://a.com/img.jpg", "image/jpeg"),
            ("http://a.com/img.jpeg", "image/jpeg"),
            ("http://a.com/img.png", "image/png"),
            ("http://a.com/img.webp", "image/webp"),
            ("http://a.com/img.gif", "image/gif"),
            ("http://a.com/img.bmp", "image/bmp"),
            ("http://a.com/img.tiff", "image/tiff"),
            ("http://a.com/img.JpG?query=1#frag", "image/jpeg"),
        ],
    )
    def test_supported_formats(self, url: str, expected: str) -> None:
        """Test supported image formats are correctly mapped."""
        assert get_mime_type(url) == expected

    def test_unsupported_formats(self) -> None:
        """Test unsupported formats raise ValueError."""
        with pytest.raises(ValueError, match="Unsupported image format"):
            get_mime_type("http://example.com/img.pdf")
        with pytest.raises(ValueError, match="Unsupported image format"):
            get_mime_type("http://example.com/img")


class TestDownloadImage:
    """Tests for download_image."""

    @pytest.mark.asyncio
    async def test_download_with_provided_client(self, mock_httpx_client: AsyncMock) -> None:
        """Test downloading an image providing an existing client."""
        content = await download_image("http://example.com/img.jpg", client=mock_httpx_client)
        assert content == b"image_data"
        mock_httpx_client.get.assert_called_once_with("http://example.com/img.jpg", timeout=10.0)

    @pytest.mark.asyncio
    @patch("data_processing.image_processor.httpx.AsyncClient")
    async def test_download_without_client(self, mock_async_client_class: AsyncMock) -> None:
        """Test downloading an image creating a new client."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = b"new_image_data"
        mock_client.get.return_value = mock_response
        mock_async_client_class.return_value.__aenter__.return_value = mock_client

        content = await download_image("http://example.com/img.jpg")
        assert content == b"new_image_data"
        mock_client.get.assert_called_once_with("http://example.com/img.jpg", timeout=10.0)

    @pytest.mark.asyncio
    async def test_download_http_error(self, mock_httpx_client: AsyncMock) -> None:
        """Test downloading an image raises error on HTTP failure."""
        mock_httpx_client.get.return_value.raise_for_status.side_effect = httpx.HTTPStatusError(
            message="Error", request=AsyncMock(), response=AsyncMock()
        )
        with pytest.raises(httpx.HTTPStatusError):
            await download_image("http://example.com/img.jpg", client=mock_httpx_client)


def create_test_image_bytes(
    img_format: str = "JPEG",
    size: tuple[int, int] = (100, 100),
    color: str = "blue",
    mode: str = "RGB",
) -> bytes:
    """Create a dummy image in memory and return its bytes."""
    img = Image.new(mode, size, color=color)
    buffer = io.BytesIO()
    img.save(buffer, format=img_format)
    return buffer.getvalue()


class TestConvertToPng:
    """Tests for _convert_to_png."""

    def test_conversion_success(self) -> None:
        """Test successful conversion from JPEG to PNG."""
        jpeg_bytes = create_test_image_bytes(img_format="JPEG")
        png_bytes = _convert_to_png(jpeg_bytes)

        with Image.open(io.BytesIO(png_bytes)) as img:
            assert img.format == "PNG"

    def test_conversion_failure(self) -> None:
        """Test conversion handles invalid image data."""
        with pytest.raises(ValueError, match="Failed to convert image"):
            _convert_to_png(b"not an image")


class TestDownscaleImage:
    """Tests for _downscale_image."""

    def test_no_downscale_needed(self) -> None:
        """Test skipping downscale for small images."""
        small_image = create_test_image_bytes(size=(10, 10))
        result = _downscale_image(small_image, max_size_bytes=1024 * 1024)
        assert result == small_image

    def test_downscale_needed(self) -> None:
        """Test downscaling works for large images."""
        img_bytes = create_test_image_bytes(img_format="BMP", size=(1000, 1000))
        max_size = len(img_bytes) // 2
        result = _downscale_image(img_bytes, max_size_bytes=max_size)
        assert len(result) < len(img_bytes)
        with Image.open(io.BytesIO(result)) as img:
            assert img.size[0] < 1000
            assert img.size[1] < 1000


class TestProcessImage:
    """Tests for process_image."""

    @pytest.mark.asyncio
    @patch("data_processing.image_processor.download_image")
    async def test_process_jpeg_image(self, mock_download: AsyncMock) -> None:
        """Test processing a JPEG image (no format conversion)."""
        jpeg_img = create_test_image_bytes(img_format="JPEG", size=(10, 10))
        mock_download.return_value = jpeg_img

        result = await process_image("http://example.com/img.jpg", img_id="test-id")

        assert result.id == "test-id"
        assert result.url == "http://example.com/img.jpg"
        assert result.part.inline_data is not None
        assert result.part.inline_data.mime_type == "image/jpeg"
        mock_download.assert_called_once()

    @pytest.mark.asyncio
    @patch("data_processing.image_processor.download_image")
    async def test_process_gif_image(self, mock_download: AsyncMock) -> None:
        """Test processing a GIF image (format conversion needed)."""
        gif_img = create_test_image_bytes(img_format="GIF", size=(10, 10))
        mock_download.return_value = gif_img

        result = await process_image("http://example.com/img.gif")

        assert result.id is not None
        assert result.url == "http://example.com/img.gif"
        assert result.part.inline_data is not None
        assert result.part.inline_data.mime_type == "image/png"
