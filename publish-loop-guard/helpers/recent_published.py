#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""近期已发速查 —— 只读笔记管理页「第一页」，不翻页。

设计口径（2026-09-11 按用户要求定）：
  - 复核只关心**最近几日**有没有发出、状态对不对；
  - 新发的笔记必然排在 note-manager 第一页（按时间倒序），
    所以**只取第一页（最新 10 条）就够了**，不需要翻到后面的页；
  - 翻页会成倍拉长耗时、放大风控暴露面，且对"漏发复核"没有任何增益。

它回答的问题：`publish_log.json` 里最近记录的那几篇，平台上到底在不在、什么状态。

与 check_missing.py 的分工：
  - check_missing.py：稿件目录 vs 发布日志（文件系统侧，不碰浏览器）
  - recent_published.py：平台上**实际最新 10 条**是什么（浏览器侧，只读一眼）

为什么需要后者：日志记的是"我提交过"，平台记的是"此刻在不在"。
被删除、被驳回、审核中的稿子，日志里看不出来，只有平台侧才看得到。

用法：
  python recent_published.py                      # 第一页 10 条
  python recent_published.py --days 2             # 只要最近 2 天的
  python recent_published.py --status 未通过      # 只看某个状态
  python recent_published.py --json

退出码：
  0 = 正常
  1 = 存在非「已发布」的近期条目（审核中/未通过），需留意
  2 = 环境错误（Chrome 未起 / 登录失效 / 依赖缺失）

环境变量：
  XHS_SKILL_DIR   运行层目录，默认本仓库 runtime/
  XHS_CDP_HOST / XHS_CDP_PORT   默认 127.0.0.1 / 9222
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
PATCH_ROOT = os.path.normpath(os.path.join(HERE, ".."))          # <patch>/publish-loop-guard
PATCHES_ROOT = os.path.normpath(os.path.join(PATCH_ROOT, ".."))  # <skills>/red-book-skills-patches
SKILLS_ROOT = os.path.normpath(os.path.join(PATCHES_ROOT, ".."))

SKILL_DIR = (
    os.environ.get("XHS_SKILL_DIR")
    or os.environ.get("RED_BOOK_SKILLS_ROOT")
    or os.path.join(PATCHES_ROOT, "runtime")
)
SKILL_SCRIPTS = os.path.join(SKILL_DIR, "scripts")

HOST = os.environ.get("XHS_CDP_HOST", "127.0.0.1")
PORT = int(os.environ.get("XHS_CDP_PORT", "9222"))


def _ensure_venv_runtime() -> None:
    """cdp_publish 依赖装在 Patch 的 .venv 里；用错解释器就换过去重跑一遍。

    注意：Windows 上 os.execv 会丢掉父 shell 已接管的标准输出，
    表现为"退出码 0 但没有任何输出"，所以这里用 subprocess 转发。
    """
    if SKILL_SCRIPTS not in sys.path:
        sys.path.insert(0, SKILL_SCRIPTS)
    try:
        import cdp_publish  # noqa: F401
        return
    except Exception:
        pass
    venv_py = os.environ.get("RED_BOOK_SKILLS_PYTHON")
    if not venv_py:
        candidates = (
            os.path.join(PATCHES_ROOT, ".venv", "Scripts", "python.exe"),
            os.path.join(PATCHES_ROOT, ".venv", "bin", "python"),
        )
        venv_py = next((candidate for candidate in candidates if os.path.isfile(candidate)), sys.executable)
    if os.path.isfile(venv_py) and os.path.abspath(sys.executable) != os.path.abspath(venv_py):
        r = subprocess.run([venv_py, os.path.abspath(__file__)] + sys.argv[1:])
        sys.exit(r.returncode)
    raise SystemExit("cdp_publish 导入失败；请先运行 tools/setup_runtime.py")


def fetch_first_page():
    """只读第一页。返回 (notes, err)。"""
    _ensure_venv_runtime()
    from cdp_publish import XiaohongshuPublisher  # noqa: E402

    pub = XiaohongshuPublisher(host=HOST, port=PORT)
    try:
        pub.connect(reuse_existing_tab=True)
        notes = pub._capture_note_manager_notes(retries=2)
    except Exception as exc:  # noqa: BLE001
        return None, f"{type(exc).__name__}: {exc}"
    rows = []
    for n in notes:
        rows.append({
            "time": n.get("time"),
            "status": pub._manager_note_status(n),
            "title": n.get("display_title"),
            "id": n.get("id"),
            "view": n.get("view_count"),
        })
    return rows, None


def _within_days(ts: str, days: float) -> bool:
    if not ts or days <= 0:
        return True
    try:
        t = datetime.strptime(ts.strip(), "%Y-%m-%d %H:%M")
    except Exception:
        return True
    return datetime.now() - t <= timedelta(days=days)


def main() -> int:
    ap = argparse.ArgumentParser(description="近期已发速查（只读第一页）")
    ap.add_argument("--days", type=float, default=3.0,
                    help="只显示最近 N 天（默认 3；传 0 显示整页）")
    ap.add_argument("--status", default="", help="只看某状态，如 已发布/审核中/未通过")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    rows, err = fetch_first_page()
    if err:
        print(f"[recent] !! 无法读取平台列表：{err}", file=sys.stderr)
        print("[recent] 提示：确认 Chrome 调试实例在跑（9222）、登录有效。", file=sys.stderr)
        return 2

    kept = [r for r in rows if _within_days(r["time"], args.days)]
    if args.status:
        kept = [r for r in kept if r["status"] == args.status]

    abnormal = [r for r in kept if r["status"] != "已发布"]

    if args.json:
        print(json.dumps({"page_size": len(rows), "shown": len(kept),
                          "abnormal": len(abnormal), "rows": kept},
                         ensure_ascii=False, indent=2))
    else:
        scope = f"最近 {args.days:g} 天" if args.days > 0 else "第一页全部"
        print(f"[recent] note-manager 第一页 {len(rows)} 条；{scope}命中 {len(kept)} 条"
              f"（只读第一页，未翻页）")
        for r in kept:
            print(f"  {r['time']}\t{r['status']}\t{r['title']}")
        if abnormal:
            print(f"[recent] !! 非「已发布」{len(abnormal)} 条，需留意：")
            for r in abnormal:
                print(f"  - [{r['status']}] {r['time']} {r['title']}")
        else:
            print("[recent] 近期条目状态均为「已发布」")

    return 1 if abnormal else 0


if __name__ == "__main__":
    sys.exit(main())
