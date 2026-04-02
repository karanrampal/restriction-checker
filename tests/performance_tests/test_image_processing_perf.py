"""Performance tests for image-processing utilities."""

from typing import Any

import pytest

from data_processing.image_processor import (
    _convert_to_png,
    _downscale_image,
    get_mime_type,
)

MIME_TYPE_MAX_MEAN = 0.001  # 1 ms
CONVERT_SMALL_MAX_MEAN = 0.050  # 50 ms
CONVERT_LARGE_MAX_MEAN = 1.000  # 1 s   (4 000 × 4 000 - PIL + zlib can vary widely)
DOWNSCALE_MAX_MEAN = 1.000  # 1 s  (iterative resize)
NO_DOWNSCALE_MAX_MEAN = 0.001  # 1 ms (early return)


class TestMimeTypeDetection:  # pylint: disable=too-few-public-methods
    """Benchmark `get_mime_type` URL parsing."""

    @pytest.mark.parametrize(
        "url",
        [
            "https://cdn.example.com/product/image.jpg",
            "https://cdn.example.com/product/image.png?w=800&h=600",
            "https://cdn.example.com/product/image.webp#section",
        ],
        ids=["jpeg", "png-with-query", "webp-with-fragment"],
    )
    def test_mime_type(self, benchmark: Any, assert_max_mean: Any, url: str) -> None:
        """URL parsing for MIME-type detection."""
        benchmark(get_mime_type, url)

        assert_max_mean(benchmark, MIME_TYPE_MAX_MEAN)


class TestConvertToPng:
    """Benchmark BMP / PNG → PNG conversion via `_convert_to_png`."""

    def test_convert_small_bmp(
        self,
        benchmark: Any,
        assert_max_mean: Any,
        small_bmp_bytes: bytes,
    ) -> None:
        """100 × 100 BMP → PNG."""
        result = benchmark(_convert_to_png, small_bmp_bytes)

        assert len(result) > 0
        assert_max_mean(benchmark, CONVERT_SMALL_MAX_MEAN)

    def test_convert_large_png(
        self,
        benchmark: Any,
        assert_max_mean: Any,
        large_png_bytes: bytes,
    ) -> None:
        """4 000 × 4 000 PNG re-encode exercises the full PIL pipeline."""
        result = benchmark(_convert_to_png, large_png_bytes)

        assert len(result) > 0
        assert_max_mean(benchmark, CONVERT_LARGE_MAX_MEAN)


class TestDownscaleImage:
    """Benchmark `_downscale_image`."""

    def test_no_downscale_needed(
        self,
        benchmark: Any,
        assert_max_mean: Any,
        small_png_bytes: bytes,
    ) -> None:
        """Image already within the limit → immediate return, no work."""
        result = benchmark(_downscale_image, small_png_bytes)

        assert result == small_png_bytes
        assert_max_mean(benchmark, NO_DOWNSCALE_MAX_MEAN)

    def test_forced_downscale(
        self,
        benchmark: Any,
        assert_max_mean: Any,
        noisy_png_bytes: bytes,
    ) -> None:
        """Force iterative downscaling by setting a tight size limit."""
        target = len(noisy_png_bytes) // 4

        result = benchmark(lambda: _downscale_image(noisy_png_bytes, max_size_bytes=target))

        assert len(result) <= target or len(result) < len(noisy_png_bytes)
        assert_max_mean(benchmark, DOWNSCALE_MAX_MEAN)
