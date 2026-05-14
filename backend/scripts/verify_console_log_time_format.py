import io
import logging
from pathlib import Path
import re
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.logging import configure_console_logging  # noqa: E402


TIME_PREFIX_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} ")


def capture_console_log_line() -> str:
    """捕获一条后端控制台日志，用于验证日志格式是否以时间开头。"""
    stream = io.StringIO()
    configure_console_logging(stream=stream)
    logging.getLogger("uvicorn.error").info("server ready")
    return stream.getvalue().strip()


def main() -> None:
    """验证后端控制台日志行首包含可读时间。"""
    line = capture_console_log_line()
    if not TIME_PREFIX_PATTERN.match(line):
        raise AssertionError(f"Console log should start with time, got: {line!r}")
    print("Console log time format verification passed.")


if __name__ == "__main__":
    main()
