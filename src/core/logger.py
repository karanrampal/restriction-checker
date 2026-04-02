"""Logging functionality."""

import logging
from enum import Enum
from string import Template
from typing import Literal, NotRequired, TypedDict, Unpack, override


class Color(Enum):
    """ANSI escape codes for terminal colors."""

    RED = "\033[0;91m"
    GREEN = "\033[0;92m"
    YELLOW = "\033[0;93m"
    BLUE = "\033[0;94m"
    PURPLE = "\033[0;95m"
    WHITE = "\033[0;97m"
    RESET = "\033[0m"


class CustomFormatter(logging.Formatter):
    """Formatter that optionally applies ANSI colors to log output."""

    _TEMPLATE = Template("$color$logtext$reset")
    _LEVEL_COLORS = {
        logging.DEBUG: Color.GREEN.value,
        logging.INFO: Color.WHITE.value,
        logging.WARNING: Color.YELLOW.value,
        logging.ERROR: Color.RED.value,
        logging.CRITICAL: Color.PURPLE.value,
    }

    def __init__(
        self,
        format_str: str = "%(asctime)s [%(levelname)5s|%(name)5s|L:%(lineno)3d]: %(message)s",
        date_fmt: str = "%Y-%m-%d %H:%M:%S %Z",
        use_colors: Literal["full", "partial", "none"] = "none",
    ) -> None:
        super().__init__(format_str, date_fmt)
        self.use_colors = use_colors

        # Pre-build formatters for "full" color mode so we don't create them on every format() call.
        self._full_formatters: dict[int, logging.Formatter] = {}
        if use_colors == "full":
            for level, color in self._LEVEL_COLORS.items():
                colored_fmt = self._TEMPLATE.substitute(
                    color=color, logtext=format_str, reset=Color.RESET.value
                )
                self._full_formatters[level] = logging.Formatter(colored_fmt, date_fmt)

    @override
    def format(self, record: logging.LogRecord) -> str:
        """Format the log record, applying colors based on the level."""
        if self.use_colors == "none":
            return super().format(record)

        if self.use_colors == "full":
            formatter = self._full_formatters.get(record.levelno)
            if formatter:
                return formatter.format(record)
            return super().format(record)

        # partial - colorize only the level name
        color = self._LEVEL_COLORS.get(record.levelno, Color.WHITE.value)
        record = logging.makeLogRecord(record.__dict__)
        record.levelname = f"{color}{record.levelname}{Color.RESET.value}"
        return super().format(record)


class CustomFilter(logging.Filter):  # pylint: disable=too-few-public-methods
    """Filter log records by logger name using hierarchy-aware matching.

    Behavior:
        - If *keep_loggers* is provided, only loggers whose name starts
          with one of the listed prefixes (respecting the "."`
          hierarchy separator) are allowed through.
        - If *exclude_loggers* is provided, loggers matching any of the
          listed prefixes are blocked.
        - When both are provided, exclusion takes precedence.
    """

    def __init__(
        self,
        keep_loggers: list[str] | None = None,
        exclude_loggers: list[str] | None = None,
    ) -> None:
        super().__init__()
        self.keep_loggers = keep_loggers or []
        self.exclude_loggers = exclude_loggers or []

    @override
    def filter(self, record: logging.LogRecord) -> bool:
        """Return `True` if the record should be emitted."""
        is_included = not self.keep_loggers or any(
            self._matches(record.name, prefix) for prefix in self.keep_loggers
        )
        is_excluded = self.exclude_loggers and any(
            self._matches(record.name, prefix) for prefix in self.exclude_loggers
        )

        return is_included and not is_excluded

    @staticmethod
    def _matches(logger_name: str, prefix: str) -> bool:
        """Check if *logger_name* belongs to the *prefix* hierarchy."""
        return logger_name == prefix or logger_name.startswith(prefix + ".")


class LogParameters(TypedDict):
    """Keyword parameters accepted by :func:`setup_logger`."""

    format_str: NotRequired[str]
    date_fmt: NotRequired[str]
    use_colors: NotRequired[Literal["full", "partial", "none"]]
    keep_loggers: NotRequired[list[str]]
    exclude_loggers: NotRequired[list[str]]


def setup_logger(
    log_level: int = logging.INFO,
    log_path: str | None = None,
    **kwargs: Unpack[LogParameters],
) -> None:
    """Configure the root logger with a console handler and optional file handler.

    Args:
        log_level: Logging level (e.g. `logging.INFO`).
        log_path: Path for an additional file handler. `None` disables
            file logging.
        **kwargs: See :class:`LogParameters` for accepted keys.
    """
    format_str = kwargs.get(
        "format_str", "%(asctime)s [%(levelname)5s|%(name)5s|L:%(lineno)3d]: %(message)s"
    )
    date_fmt = kwargs.get("date_fmt", "%Y-%m-%d %H:%M:%S %Z")
    keep_loggers = kwargs.get("keep_loggers")
    exclude_loggers = kwargs.get("exclude_loggers")

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(
        CustomFormatter(format_str, date_fmt, kwargs.get("use_colors", "none"))
    )

    all_handlers: list[logging.Handler] = [stream_handler]
    if log_path:
        file_handler = logging.FileHandler(log_path, mode="w")
        file_handler.setFormatter(logging.Formatter(format_str, date_fmt))
        all_handlers.append(file_handler)

    if keep_loggers or exclude_loggers:
        custom_filter = CustomFilter(keep_loggers, exclude_loggers)
        for handler in all_handlers:
            handler.addFilter(custom_filter)

    logging.basicConfig(level=log_level, handlers=all_handlers, force=True)
