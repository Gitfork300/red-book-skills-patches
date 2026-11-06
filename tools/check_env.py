#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""环境与变量自检 —— 装机后第一件事：确认运行所需的变量/依赖都已就绪。

为什么需要
----------
这个 skill 依赖几个「环境约定」：业务工作区位置、Python 版本、虚拟环境、
Chrome、以及发布/评论实例端口。这些若未就绪，脚本不会崩、而是**静默退化**——
例如 `check_doc_layers.py` 找不到工作区就跳过校验、端口没设就用默认值，
结果看起来「跑通了」，实际漏了关键变量，复核的人根本不知道缺了什么。

本脚本把散落的约定集中起来，一次性逐项体检，**每一项都给出 PASS/FAIL 和
一句话原因**，未满足时明确提示「该设什么、在哪设、怎么设」，而不是静默跳过。

用法
----
    python tools/check_env.py                # 全量自检（退出码：0 全就绪 / 1 有缺失）
    python tools/check_env.py --json         # 结构化输出，便于脚本消费
    python tools/check_env.py --fix-hint     # 额外打印可复制的修复命令

退出码：0 = 全部就绪 / 1 = 存在缺失项（不阻断发布，但建议先补齐）
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent

# 端口约定（与 topics/ 文档里的占位符一致；本机实例请按实际情况覆盖）
ENV_PORT_PUBLISH = "XHS_CDP_PORT_PUBLISH"   # 发布实例端口（文档占位 <PORT_PUBLISH>）
ENV_PORT_COMMENT = "XHS_CDP_PORT_COMMENT"   # 评论实例端口（文档占位 <PORT_COMMENT>）
DEFAULT_PORT_PUBLISH = 9333
DEFAULT_PORT_COMMENT = 9222


def _workspace_candidates() -> list[str]:
    """业务工作区候选（与 check_doc_layers.resolve_workspace 同源）。"""
    cands: list[str] = []
    env = os.environ.get("XHS_WORKSPACE")
    if env:
        cands.append(env)
    cands.append("C:/xhs")
    # 当前目录向上回溯
    cur = os.path.abspath(os.getcwd())
    for _ in range(6):
        cands.append(cur)
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    # ~/WorkBuddy 下一层
    hub = os.path.expanduser("~/WorkBuddy")
    if os.path.isdir(hub):
        try:
            for name in sorted(os.listdir(hub))[:200]:
                cands.append(os.path.join(hub, name))
        except OSError:
            pass
    return cands


def _looks_like_workspace(path: str) -> bool:
    return os.path.exists(os.path.join(path, ".workbuddy", "memory", "MEMORY.md"))


def _find_workspace() -> str | None:
    for c in _workspace_candidates():
        if _looks_like_workspace(c):
            return c
    return None


def check_python() -> tuple[bool, str]:
    v = sys.version_info
    if v < (3, 10):
        return False, f"Python {v.major}.{v.minor} 过低，需 3.10+（当前 {sys.version.split()[0]}）"
    return True, f"Python {v.major}.{v.minor}.{v.micro}"


def check_venv() -> tuple[bool, str]:
    p = ROOT / ".venv" / ("Scripts" if os.name == "nt" else "bin") / (
        "python.exe" if os.name == "nt" else "python"
    )
    if not p.is_file():
        if (ROOT / ".venv").exists():
            return False, ".venv 不完整；保留现有环境并按 RUNTIME_SETUP.md 排查"
        return False, ".venv 缺失，首次安装运行 `py -3 tools\\setup_runtime.py`"
    try:
        result = subprocess.run(
            [str(p), "--version"], capture_output=True, text=True, timeout=15
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f".venv 无法启动：{exc}"
    if result.returncode:
        return False, f".venv 无法启动：{(result.stderr or result.stdout).strip()}"
    return True, f".venv 就绪（{result.stdout.strip()}）"


def check_workspace() -> tuple[bool, str]:
    env = os.environ.get("XHS_WORKSPACE")
    ws = _find_workspace()
    if ws:
        tag = "（环境变量 XHS_WORKSPACE）" if env else "（自动定位）"
        return True, f"业务工作区 = {ws} {tag}"
    hint = "设 `$env:XHS_WORKSPACE = \"<目录>\"`，或确保 `C:\\xhs\\.workbuddy\\memory\\MEMORY.md` 存在"
    return False, f"未定位到业务工作区 —— {hint}"


def check_workspace_anchor() -> tuple[bool, str]:
    ws = _find_workspace()
    if not ws:
        return True, "（工作区未定位，跳过锚点检查）"
    mem = os.path.join(ws, ".workbuddy", "memory", "MEMORY.md")
    pub = os.path.join(ws, "xhs_publish")
    missing = []
    if not os.path.exists(mem):
        missing.append("MEMORY.md")
    if not os.path.isdir(pub):
        missing.append("xhs_publish/")
    if missing:
        return False, f"工作区结构不完整，缺 {', '.join(missing)}"
    return True, "MEMORY.md + xhs_publish/ 齐备"


def check_chrome() -> tuple[bool, str]:
    candidates = [
        os.environ.get("PROGRAMFILES", r"C:\Program Files"),
        os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"),
        os.environ.get("LOCALAPPDATA", ""),
    ]
    exe_names = [
        r"Google\Chrome\Application\chrome.exe",
        r"Chromium\Application\chrome.exe",
        r"Google\Chrome\Application\chrome.exe",  # LOCALAPPDATA 下同结构
    ]
    for base in candidates:
        if not base:
            continue
        for name in exe_names:
            p = os.path.join(base, name)
            if os.path.isfile(p):
                return True, f"Chrome 就绪（{p}）"
    return False, "未找到 Chrome/Chromium，浏览器自动化需要本机安装 Chrome"


def check_ports() -> tuple[bool, str]:
    """端口变量：未设环境变量则回退默认值，不算缺失，但提示当前生效值。"""
    pub = os.environ.get(ENV_PORT_PUBLISH, str(DEFAULT_PORT_PUBLISH))
    com = os.environ.get(ENV_PORT_COMMENT, str(DEFAULT_PORT_COMMENT))
    note = []
    if ENV_PORT_PUBLISH not in os.environ:
        note.append(f"发布端口用默认 {DEFAULT_PORT_PUBLISH}（可设 {ENV_PORT_PUBLISH} 覆盖）")
    if ENV_PORT_COMMENT not in os.environ:
        note.append(f"评论端口用默认 {DEFAULT_PORT_COMMENT}（可设 {ENV_PORT_COMMENT} 覆盖）")
    if note:
        return True, f"端口生效值 发布={pub} 评论={com}（" + "；".join(note) + "）"
    return True, f"端口生效值 发布={pub} 评论={com}"


CHECKS = [
    ("python", "Python 版本", check_python),
    ("venv", "虚拟环境", check_venv),
    ("workspace", "业务工作区", check_workspace),
    ("workspace-anchor", "工作区结构", check_workspace_anchor),
    ("chrome", "Chrome/Chromium", check_chrome),
    ("ports", "实例端口", check_ports),
]


def main() -> int:
    ap = argparse.ArgumentParser(description="red-book-skills-patch 环境与变量自检")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--fix-hint", action="store_true", help="额外打印可复制的修复命令")
    args = ap.parse_args()

    results = []
    for key, label, fn in CHECKS:
        ok, msg = fn()
        results.append({"id": key, "label": label, "ok": ok, "msg": msg})

    missing = [r for r in results if not r["ok"]]

    if args.json:
        print(json.dumps({"ok": not missing, "missing": [r["id"] for r in missing],
                          "checks": results}, ensure_ascii=False, indent=2))
    else:
        print("=" * 62)
        print("red-book-skills-patch 环境与变量自检")
        print("=" * 62)
        for r in results:
            mark = "PASS" if r["ok"] else "FAIL"
            print(f"  [{mark}] {r['label']}: {r['msg']}")
        print()
        if missing:
            print(f"结论：!! {len(missing)} 项缺失 —— 不影响门禁，但建议补齐后复核")
            if args.fix_hint:
                print()
                print("修复命令参考：")
                if any(r["id"] == "venv" for r in missing):
                    print("  仅在 .venv 不存在时：py -3 tools\\setup_runtime.py")
                    print("  已有环境：保留并参阅 RUNTIME_SETUP.md 排查")
                if any(r["id"] == "workspace" for r in missing):
                    print('  $env:XHS_WORKSPACE = "C:\\xhs"   # 或你的业务工作区路径')
                if any(r["id"] == "workspace-anchor" for r in missing):
                    print("  确保工作区含 .workbuddy\\memory\\MEMORY.md 与 xhs_publish\\")
                if any(r["id"] == "chrome" for r in missing):
                    print("  安装 Chrome/Chromium 后重跑本脚本")
        else:
            print("结论：OK 环境与变量全部就绪")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
