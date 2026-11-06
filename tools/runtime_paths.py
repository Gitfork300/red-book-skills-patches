#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""运行态路径的唯一权威（skill 树内只放代码，不放状态）。

为什么要有这个文件
------------------
2026-11-06 用户指出：`publish_log.json`、`.guard.lock`、`compatibility.json`、
`__pycache__/`、`runtime/tmp/` 都落在 **skill 树内**。后果有三条，条条要命：

1. **全量替换包会连状态一起覆盖**：升级时 state 被新包冲掉＝发布日志丢、间隔判断从头开始，
   极端情况会当天重发。
2. **跨机复制会把本机运行态带过去**：锁文件本身存在不代表持锁；台账中的未过期 pending
   可能阻塞发布，错误复制台账也会导致 `dup_check` 误判。跨机迁移台账须人工核对。
3. **缓存里存绝对路径**：`compatibility.json` 记的是 `C:/Users/<某台机器>/...`，
   换机器/换目录后要么假绿、要么每次重算。为此本模块把路径统一成「相对 PATCH_ROOT」再入缓存。

布局（默认）
------------
```
<workspace>/.state/            ← XHS_STATE_ROOT，整棵树可在升级中被保留
├── publish/publish_log.json   ← 发布台账（唯一权威）
├── publish/.guard.lock        ← 间隔锁的承载文件（常驻，不删）
├── covers/qr_whitelist.json   ← 封面二维码白名单（业务状态）
├── cache/compatibility.json   ← 环境兼容缓存（路径存相对值）
├── pycache/                   ← 所有 __pycache__ 归集处（sys.pycache_prefix）
└── tmp/                       ← 临时产物归集处
```

覆盖优先级：显式环境变量 > `<workspace>/.state` > （只读）skill 内旧路径。

用法
----
    python tools/runtime_paths.py            # 人读：打印解析结果
    python tools/runtime_paths.py --json      # 机读：给其他脚本/排障用
    python tools/runtime_paths.py --init      # 建目录 + 把旧日志迁到新址（幂等）

退出码：0 = 正常 / 2 = 目录创建失败
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile

PATCHES_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

# ── 工作区与状态根 ────────────────────────────────────────────────
WORKSPACE = os.environ.get("XHS_WORKSPACE") or "C:/xhs"
STATE_ROOT = os.environ.get("XHS_STATE_ROOT") or os.path.join(WORKSPACE, ".state")

PUBLISH_DIR = os.path.join(STATE_ROOT, "publish")
PUBLISH_LOG = os.environ.get("XHS_INTERVAL_LOG") or os.path.join(PUBLISH_DIR, "publish_log.json")
GUARD_LOCK = os.environ.get("XHS_GUARD_LOCK") or os.path.join(PUBLISH_DIR, ".guard.lock")
COVERS_DIR = os.path.join(STATE_ROOT, "covers")
QR_WHITELIST = os.environ.get("XHS_QR_WHITELIST") or os.path.join(COVERS_DIR, "qr_whitelist.json")
CACHE_DIR = os.path.join(STATE_ROOT, "cache")
COMPAT_CACHE = os.environ.get("XHS_COMPAT_CACHE") or os.path.join(CACHE_DIR, "compatibility.json")
PYCACHE_DIR = os.environ.get("PYTHONPYCACHEPREFIX") or os.path.join(STATE_ROOT, "pycache")
TMP_DIR = os.environ.get("XHS_TMP_DIR") or os.path.join(STATE_ROOT, "tmp")

# ── 旧位置（只读兼容；升级后逐步废弃）──────────────────────────
LEGACY_PUBLISH_DIR = os.path.join(PATCHES_ROOT, "publish-interval-guard", "state")
LEGACY_PUBLISH_LOG = os.path.join(LEGACY_PUBLISH_DIR, "publish_log.json")
LEGACY_COMPAT_CACHE = os.path.join(PATCHES_ROOT, "state", "compatibility.json")


def ensure_dirs() -> None:
    """建齐状态目录。失败向上抛，让调用方以非零退出码收场（不要静默降级）。"""
    for path in (PUBLISH_DIR, COVERS_DIR, CACHE_DIR, PYCACHE_DIR, TMP_DIR):
        os.makedirs(path, exist_ok=True)


def resolve_publish_log() -> str:
    """读路径：显式 env > 新址（存在）> 旧址（存在）> 新址（待创建）。

    保留旧址回落只为一件事：升级/迁移的**过渡期**里，还没写过新址的机器仍能读到历史台账。
    一旦新址存在，旧址永不再被读取，避免双份台账各说各话。
    """
    if os.environ.get("XHS_INTERVAL_LOG"):
        return PUBLISH_LOG
    if os.path.exists(PUBLISH_LOG):
        return PUBLISH_LOG
    if os.path.exists(LEGACY_PUBLISH_LOG):
        return LEGACY_PUBLISH_LOG
    return PUBLISH_LOG


def resolve_compat_cache() -> str:
    if os.environ.get("XHS_COMPAT_CACHE"):
        return COMPAT_CACHE
    if os.path.exists(COMPAT_CACHE):
        return COMPAT_CACHE
    if os.path.exists(LEGACY_COMPAT_CACHE):
        return LEGACY_COMPAT_CACHE
    return COMPAT_CACHE


def _migrate_file(src: str, dst: str) -> str:
    """原子复制旧状态，不覆盖新址，也不修改旧文件。迁移时须停止所有发布进程。"""
    if not os.path.exists(src):
        return "skip(源不存在)"
    if os.path.exists(dst):
        return "skip(新址已存在)"
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".migrate-", dir=os.path.dirname(dst))
    try:
        with os.fdopen(fd, "wb") as target, open(src, "rb") as source:
            shutil.copyfileobj(source, target)
        try:
            os.link(temporary, dst)
        except FileExistsError:
            return "skip(新址已存在)"
    finally:
        os.unlink(temporary)
    return f"copied → {dst}（旧文件保留在原位）"


def init_state(migrate: bool = True) -> list[str]:
    ensure_dirs()
    report = []
    if migrate:
        report.append("publish_log: " + _migrate_file(LEGACY_PUBLISH_LOG, PUBLISH_LOG))
        report.append("compatibility: " + _migrate_file(LEGACY_COMPAT_CACHE, COMPAT_CACHE))
    return report


def snapshot() -> dict:
    return {
        "workspace": WORKSPACE,
        "state_root": STATE_ROOT,
        "publish_dir": PUBLISH_DIR,
        "publish_log": PUBLISH_LOG,
        "publish_log_in_use": resolve_publish_log(),
        "guard_lock": GUARD_LOCK,
        "qr_whitelist": QR_WHITELIST,
        "compat_cache": COMPAT_CACHE,
        "compat_cache_in_use": resolve_compat_cache(),
        "pycache": PYCACHE_DIR,
        "tmp": TMP_DIR,
        "legacy_publish_log": LEGACY_PUBLISH_LOG,
        "legacy_compat_cache": LEGACY_COMPAT_CACHE,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="运行态路径解析 / 初始化")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    parser.add_argument("--init", action="store_true", help="建目录并迁移旧状态")
    parser.add_argument("--no-migrate", action="store_true", help="只建目录，不动旧文件")
    options = parser.parse_args()

    try:
        if options.init:
            report = init_state(migrate=not options.no_migrate)
        else:
            ensure_dirs()
            report = []
    except OSError as exc:
        print(f"FAIL 无法创建状态目录：{exc}", file=sys.stderr)
        return 2

    data = snapshot()
    if options.json:
        data["actions"] = report
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0

    for key, value in data.items():
        print(f"{key:22s} {value}")
    for line in report:
        print("  ·", line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
