"""验证 V1.5 真实 QA 与回放验收入口。

该脚本串联 Sprint 21 与 Sprint 22 的源码级验收，作为 V1.5 本地最小验收命令。
"""

from __future__ import annotations

import verify_sprint21_real_qa
import verify_sprint22_replay


def main() -> None:
    """执行 V1.5 真实 QA、引用、回放和对比的最小验收。"""
    verify_sprint21_real_qa.main()
    verify_sprint22_replay.main()
    print("V1.5 real QA replay verification passed.")


if __name__ == "__main__":
    main()
