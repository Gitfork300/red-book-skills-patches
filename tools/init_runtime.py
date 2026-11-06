#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Create the empty local runtime directory layout without creating state data."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
RUNTIME_DIRS = (
    "runtime/config",
    "runtime/tmp",
    # 2026-10-07 起 apply 前备份移到工作区外的 _skill-backup/core-overrides-preapply/，
    # 不再在仓库内创建 state/backup —— 留在 skills/ 树内会与本体 SKILL.md 同名撞车。
    "core-overrides/state",
    "publish-interval-guard/state",
    "publish-loop-guard/state",
    "timeliness-window/state",
    "update-checker/state",
    "xhs-risk-guard/state",
)


def main() -> int:
    for relative in RUNTIME_DIRS:
        (ROOT / relative).mkdir(parents=True, exist_ok=True)
    # 运行态（台账/锁/缓存/pycache/tmp）在工作区 .state 下，不在本树 —— 见 tools/runtime_paths.py
    import runtime_paths

    try:
        runtime_paths.ensure_dirs()
    except OSError as exc:
        print(f"FAIL 无法创建工作区状态目录：{exc}", file=sys.stderr)
        return 2
    extra = f" + state dirs @ {runtime_paths.STATE_ROOT}"
    print(f"OK runtime directories ready ({len(RUNTIME_DIRS)} directories){extra}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
