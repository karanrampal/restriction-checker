"""Unit tests for the logger module."""

import logging
from unittest.mock import MagicMock, patch

from core.logger import Color, CustomFilter, CustomFormatter, setup_logger


class TestCustomFormatter:
    """Tests for the CustomFormatter string modifications."""

    def test_no_colors(self) -> None:
        """Test formatting without colors."""
        formatter = CustomFormatter(format_str="%(levelname)s: %(message)s", use_colors="none")
        record = logging.makeLogRecord(
            {"levelno": logging.INFO, "levelname": "INFO", "msg": "test"}
        )
        assert formatter.format(record) == "INFO: test"

    def test_full_colors(self) -> None:
        """Test full color formatting wraps the entire log."""
        formatter = CustomFormatter(format_str="%(levelname)s: %(message)s", use_colors="full")
        record = logging.makeLogRecord(
            {"levelno": logging.ERROR, "levelname": "ERROR", "msg": "test"}
        )
        formatted = formatter.format(record)
        assert Color.RED.value in formatted
        assert "ERROR: test" in formatted
        assert Color.RESET.value in formatted

    def test_partial_colors(self) -> None:
        """Test partial color formatting only wraps the levelname."""
        formatter = CustomFormatter(format_str="%(levelname)s: %(message)s", use_colors="partial")
        record = logging.makeLogRecord(
            {"levelno": logging.WARNING, "levelname": "WARNING", "msg": "warn test"}
        )
        formatted = formatter.format(record)
        assert f"{Color.YELLOW.value}WARNING{Color.RESET.value}: warn test" in formatted

    def test_full_colors_unknown_level(self) -> None:
        """Test full color formatting safely falls back when level is unknown."""
        formatter = CustomFormatter(format_str="%(levelname)s: %(message)s", use_colors="full")
        record = logging.makeLogRecord({"levelno": 999, "levelname": "UNKNOWN", "msg": "test"})
        formatted = formatter.format(record)
        assert "UNKNOWN: test" in formatted
        assert Color.WHITE.value not in formatted


class TestCustomFilter:
    """Tests for the CustomFilter hierarchy string matching."""

    def test_keep_loggers(self) -> None:
        """Test allowing only specific logger hierarchies."""
        filt = CustomFilter(keep_loggers=["app.agent"])
        assert filt.filter(logging.makeLogRecord({"name": "app.agent"})) is True
        assert filt.filter(logging.makeLogRecord({"name": "app.agent.restrictor"})) is True
        assert filt.filter(logging.makeLogRecord({"name": "app"})) is False
        assert filt.filter(logging.makeLogRecord({"name": "other"})) is False

    def test_exclude_loggers(self) -> None:
        """Test explicitly denying specific logger hierarchies."""
        filt = CustomFilter(exclude_loggers=["app.secret"])
        assert filt.filter(logging.makeLogRecord({"name": "app"})) is True
        assert filt.filter(logging.makeLogRecord({"name": "app.secret"})) is False
        assert filt.filter(logging.makeLogRecord({"name": "app.secret.key"})) is False

    def test_keep_and_exclude(self) -> None:
        """Test exclude takes precedence over keep rules."""
        filt = CustomFilter(keep_loggers=["app"], exclude_loggers=["app.secret"])
        assert filt.filter(logging.makeLogRecord({"name": "app.public"})) is True
        assert filt.filter(logging.makeLogRecord({"name": "app.secret"})) is False
        assert filt.filter(logging.makeLogRecord({"name": "other"})) is False


class TestSetupLogger:
    """Tests for the setup_logger global configurator."""

    @patch("core.logger.logging.basicConfig")
    def test_setup_stream_only(self, mock_basic_config: MagicMock) -> None:
        """Test setup_logger correctly configures basic console output."""
        setup_logger(log_level=logging.DEBUG, use_colors="none")
        mock_basic_config.assert_called_once()
        kwargs = mock_basic_config.call_args.kwargs
        assert kwargs["level"] == logging.DEBUG
        assert kwargs["force"] is True
        assert len(kwargs["handlers"]) == 1
        assert isinstance(kwargs["handlers"][0], logging.StreamHandler)

    @patch("core.logger.logging.FileHandler")
    @patch("core.logger.logging.basicConfig")
    def test_setup_with_file(
        self, mock_basic_config: MagicMock, mock_file_handler: MagicMock
    ) -> None:
        """Test setup_logger appends a FileHandler when log_path is provided."""
        mock_fh_instance = MagicMock()
        mock_file_handler.return_value = mock_fh_instance

        setup_logger(log_path="test.log")

        mock_file_handler.assert_called_once_with("test.log", mode="w")
        kwargs = mock_basic_config.call_args.kwargs
        handlers = kwargs["handlers"]
        assert len(handlers) == 2
        assert mock_fh_instance in handlers

    @patch("core.logger.logging.basicConfig")
    def test_setup_with_filters(self, mock_basic_config: MagicMock) -> None:
        """Test setup_logger propagates the constructed filters to all its handlers."""
        setup_logger(keep_loggers=["test"], exclude_loggers=["test.bad"])
        kwargs = mock_basic_config.call_args.kwargs
        handler = kwargs["handlers"][0]
        assert len(handler.filters) == 1
        filter_instance = handler.filters[0]
        assert isinstance(filter_instance, CustomFilter)
        assert filter_instance.keep_loggers == ["test"]
        assert filter_instance.exclude_loggers == ["test.bad"]
