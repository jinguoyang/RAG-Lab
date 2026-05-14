import logging
import sys
from typing import TextIO


LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
CONSOLE_LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
CONSOLE_LOGGER_NAMES = ("app", "uvicorn", "uvicorn.error", "uvicorn.access")


def configure_console_logging(stream: TextIO | None = None) -> None:
    """统一后端控制台日志格式，确保每行日志以可读时间开头。"""
    console_stream = stream or sys.stderr
    formatter = logging.Formatter(CONSOLE_LOG_FORMAT, datefmt=LOG_DATE_FORMAT)
    handler = logging.StreamHandler(console_stream)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(logging.WARNING)

    for logger_name in CONSOLE_LOGGER_NAMES:
        logger = logging.getLogger(logger_name)
        logger.handlers = [handler]
        logger.setLevel(logging.INFO)
        logger.propagate = False
