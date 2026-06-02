"""B-296: 外部培训应用联调脚本单元测试。"""

import importlib
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# 确保 backend 目录在 sys.path 中
_backend = str(Path(__file__).resolve().parents[3])
if _backend not in sys.path:
    sys.path.insert(0, _backend)

script = importlib.import_module("scripts.verify_external_training_e2e")


class TestHasBlockingStatus:
    """验证阻断判断逻辑。"""

    def test_fail_always_blocks(self):
        checks = [{"name": "x", "status": "FAIL"}]
        assert script._has_blocking_status(checks, allow_skips=True) is True
        assert script._has_blocking_status(checks, allow_skips=False) is True

    def test_skip_blocks_when_not_allowed(self):
        checks = [{"name": "x", "status": "SKIP"}]
        assert script._has_blocking_status(checks, allow_skips=False) is True

    def test_skip_does_not_block_when_allowed(self):
        checks = [{"name": "x", "status": "SKIP"}]
        assert script._has_blocking_status(checks, allow_skips=True) is False

    def test_pass_never_blocks(self):
        checks = [{"name": "x", "status": "PASS"}]
        assert script._has_blocking_status(checks, allow_skips=False) is False
        assert script._has_blocking_status(checks, allow_skips=True) is False

    def test_mixed_checks(self):
        checks = [
            {"name": "a", "status": "PASS"},
            {"name": "b", "status": "SKIP"},
            {"name": "c", "status": "PASS"},
        ]
        assert script._has_blocking_status(checks, allow_skips=False) is True
        assert script._has_blocking_status(checks, allow_skips=True) is False


class TestSkippedHealthChecksBlock:
    """验证 SKIP 健康检查默认阻断退出。"""

    def test_skipped_health_checks_block_default_exit(self):
        assert script._has_blocking_status(
            [{"name": "externalAppHealth", "status": "SKIP"}],
            allow_skips=False,
        )

    def test_skipped_health_checks_pass_with_allow_skips(self):
        assert not script._has_blocking_status(
            [{"name": "externalAppHealth", "status": "SKIP"}],
            allow_skips=True,
        )
