#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把散落的运行态产物归集到 `<workspace>/.state`（一次性清扫 + 幂等复用）。

为什么需要
----------
2026-11-06 用户裁定：`__pycache__/`、`runtime/tmp/` 这类产物不能散在 skill 树里。
两条实害：
1. 全量替换包会连产物一起覆盖，`runtime/tmp/login_status_cache.json` 一丢，
   登录态缓存就得重探（多花一次浏览器往返）。
2. `.pyc` 混进覆盖层清单会永久 DRIFTED（红线 4），而散落的 15 个 `__pycache__`
   目录正是 `apply_overrides.py clean` 要反复清的对象。

归集后：字节码 → `.state/pycache`（由 venv 的 `sys.pycache_prefix` 决定，见 setup_runtime.py），
临时产物 → `.state/tmp`（由 `XHS_RUNTIME_TMP` 决定，cdp_publish 已改为读该变量）。
本脚本只做两件事：**建目录** + **把树内已有的散落物搬走/清掉**。

用法
----
    python tools/clean_artifacts.py            # 清扫并报告
    python tools/clean_artifacts.py --dry-run  # 只看要动什么

退出码：0 = 完成 / 2 = 目录不可写
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PATCHES_ROOT = os.path.normpath(os.path.join(HERE, ".."))
SKIP_DIRS = {".venv", ".git", "__pycache__", "_archive", "red-book-skills-upstream"}

try:
    sys.path.insert(0, HERE)
    import runtime_paths
except Exception as exc:  # pragma: no cover - 只在文件缺失时触发
    print(f"FAIL 无法加载 tools/runtime_paths.py：{exc}", file=sys.stderr)
    sys.exit(2)


def stray_pycache(root: str) -> list[str]:
    found = []
    for dirpath, dirnames, _filenames in os.walk(root):
        pruned = []
        for name in dirnames:
            full = os.path.join(dirpath, name)
            if name in SKIP_DIRS:
                # __pycache__ 本身要被收集，其余目录不进入
                if name == "__pycache__":
                    found.append(full)
                continue
            pruned.append(name)
        dirnames[:] = pruned
    return sorted(found)


def main() -> int:
    parser = argparse.ArgumentParser(description="归集运行态产物到工作区 .state")
    parser.add_argument("--dry-run", action="store_true", help="只报告，不改动")
    options = parser.parse_args()

    if not options.dry_run:
        try:
            runtime_paths.ensure_dirs()
        except OSError as exc:
            print(f"FAIL 无法创建工作区状态目录：{exc}", file=sys.stderr)
            return 2

    print(f"[clean] 状态根：{runtime_paths.STATE_ROOT}")
    print(f"[clean] pycache：{runtime_paths.PYCACHE_DIR}")
    print(f"[clean] tmp    ：{runtime_paths.TMP_DIR}")

    # 1. 树内散落 __pycache__
    caches = stray_pycache(PATCHES_ROOT)
    reclaimed = 0
    for path in caches:
        for dirpath, _dirnames, filenames in os.walk(path):
            for name in filenames:
                try:
                    reclaimed += os.path.getsize(os.path.join(dirpath, name))
                except OSError:
                    pass
    print(f"[clean] 树内 __pycache__ {len(caches)} 个，约 {reclaimed / 1024:.0f} KB")
    if not options.dry_run:
        for path in caches:
            try:
                shutil.rmtree(path)
            except OSError as exc:
                print(f"FAIL 无法清理 {path}: {exc}", file=sys.stderr)
                return 2
        print("[clean] 已清除（后续字节码统一写入 .state/pycache，不再污染树）")

    # 2. runtime/tmp → 工作区 .state/tmp
    runtime_tmp = os.path.join(PATCHES_ROOT, "runtime", "tmp")
    moved = 0
    if os.path.isdir(runtime_tmp):
        for name in os.listdir(runtime_tmp):
            src = os.path.join(runtime_tmp, name)
            dst = os.path.join(runtime_paths.TMP_DIR, name)
            if os.path.isdir(src):
                continue
            moved += 1
            if options.dry_run:
                print(f"[clean] 将迁移 {name} → {dst}")
                continue
            if os.path.exists(dst):
                print(f"FAIL 目标已存在，保留两份文件: {src} / {dst}", file=sys.stderr)
                return 2
            try:
                shutil.move(src, dst)
            except OSError as exc:
                print(f"FAIL 无法迁移 {src}: {exc}", file=sys.stderr)
                return 2
    print(f"[clean] runtime/tmp 迁移文件 {moved} 个")

    # 3. 旧的树内状态（迁移后残留的 .migrated 文件只留证据，不再增长）
    for label, path in (
        ("publish_log", runtime_paths.LEGACY_PUBLISH_LOG),
        ("compatibility", runtime_paths.LEGACY_COMPAT_CACHE),
    ):
        if os.path.exists(path):
            print(f"[clean] 提示：{label} 仍在旧址 {path}，跑 tools/runtime_paths.py --init 迁移")

    if not options.dry_run:
        print("[clean] 完成。报告口径见 tools/runtime_paths.py --json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
