import logging
import os
import sys

_RESET = "\033[0m"
_GREY = "\033[90m"
_CYAN = "\033[36m"
_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_RED = "\033[31m"
_RED_BOLD = "\033[1;31m"

_COLORS = {
    logging.DEBUG: _GREY,
    logging.INFO: _GREEN,
    logging.WARNING: _YELLOW,
    logging.ERROR: _RED,
    logging.CRITICAL: _RED_BOLD,
}


class _Formatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        color = _COLORS.get(record.levelno, _RESET)
        time = f"{_GREY}{self.formatTime(record, '%H:%M:%S')}{_RESET}"
        level = f"{color}{record.levelname:<8}{_RESET}"
        # Use only the last segment of the dotted name (e.g. "planner" not "agents.planner")
        name = record.name.split(".")[-1]
        module = f"{_CYAN}{name:<12}{_RESET}"
        msg = record.getMessage()
        if record.exc_info:
            msg += "\n" + self.formatException(record.exc_info)
        return f"{time} {level} {module} {msg}"


def _setup() -> None:
    root = logging.getLogger()
    if root.handlers:
        return  # already configured (e.g. called twice)

    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    root.setLevel(level)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_Formatter())
    root.addHandler(handler)

    # Suppress noisy third-party loggers
    for lib in ("httpx", "httpcore", "urllib3", "google", "langchain", "langgraph", "hpack"):
        logging.getLogger(lib).setLevel(logging.WARNING)


_setup()


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
