#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Create the local virtual environment and install the small runtime dependency set."""
from __future__ import annotations

import os
import subprocess
import sys
import venv
from pathlib import Path

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

PATCH_ROOT = Path(__file__).resolve().parent.parent
VENV_DIR = PATCH_ROOT / ".venv"
REQUIREMENTS = PATCH_ROOT / "requirements.txt"


SITECUSTOMIZE = '''"""Windows 输出编码兜底 —— 由 tools/setup_runtime.py 写入 .venv，勿手工编辑。

为什么需要
----------
Windows 下 stdout/stderr 被重定向到文件或管道时，Python 会退回系统 ANSI 代码页
（本机实测 cp1252）。脚本里任何中文 print 都会抛 UnicodeEncodeError 并以非零
退出码结束 —— 现象极具误导性：命令看起来"失败了"，实际只是打印崩了。
2026-09-17 实测：`apply_overrides.py status > out.txt` 直接 traceback。

本模块由 venv 的 site 机制自动加载，对所有用本 venv 解释器运行的脚本生效，
不需要改动任何业务脚本（也就不用去改随仓库分发的 runtime 本体）。
"""
import sys

for _stream in (getattr(sys, "stdout", None), getattr(sys, "stderr", None)):
    try:
        if _stream is None or not hasattr(_stream, "reconfigure"):
            continue
        if (_stream.encoding or "").lower().replace("-", "") != "utf8":
            _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ── __pycache__ 归集（2026-11-06）──────────────────────────────
# 默认解释器会在每个包目录旁散落 __pycache__/，既污染随包分发的 skill 树，
# 又可能让 .pyc 混进覆盖层清单造成永久 DRIFTED（红线 4）。
# sys.pycache_prefix 把字节码统一写到 <workspace>/.state/pycache，树内不再产生。
# 已显式设 PYTHONPYCACHEPREFIX 时不动（尊重外部约定）。
import os as _os

if not _os.environ.get("PYTHONPYCACHEPREFIX"):
    _root = _os.environ.get("XHS_STATE_ROOT") or _os.path.join(
        _os.environ.get("XHS_WORKSPACE") or "C:/xhs", ".state"
    )
    try:
        _prefix = _os.path.join(_root, "pycache")
        _os.makedirs(_prefix, exist_ok=True)
        sys.pycache_prefix = _prefix
        # 运行层脚本（runtime/scripts/*）只读环境变量，不认识 skill 内的 tools/；
        # 在这里统一注入，避免它们各自回落 skill 树内的 runtime/tmp。
        _tmp = _os.path.join(_root, "tmp")
        _os.makedirs(_tmp, exist_ok=True)
        _os.environ.setdefault("XHS_RUNTIME_TMP", _tmp)
    except Exception:
        pass
'''


def venv_python() -> Path:
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def write_sitecustomize() -> None:
    """把 UTF-8 输出兜底写进 venv 的 site-packages。

    只对 venv 生效、不改任何业务脚本；venv 重建后本函数会再次写入，不会漏。
    """
    # Windows venv 是 Lib\site-packages；POSIX venv 是 lib\pythonX.Y\site-packages
    if os.name == "nt":
        candidates = [VENV_DIR / "Lib" / "site-packages"]
    else:
        candidates = sorted((VENV_DIR / "lib").glob("python*/site-packages"))
    for candidate in candidates:
        if not candidate.is_dir():
            continue
        target = candidate / "sitecustomize.py"
        target.write_text(SITECUSTOMIZE, encoding="utf-8")
        print(f"OK 已写入输出编码兜底: {target}")
        return
    raise FileNotFoundError(f"虚拟环境的 site-packages 不存在：{VENV_DIR}")


def main() -> int:
    if sys.version_info < (3, 10):
        print("需要 Python 3.10 或更新版本。", file=sys.stderr)
        return 2
    if not REQUIREMENTS.is_file():
        print(f"依赖清单不存在：{REQUIREMENTS}", file=sys.stderr)
        return 2

    if VENV_DIR.exists():
        print("已有 .venv；为保护本机环境，setup 不会修改它。"
              "首次安装失败或确需更换时，请先审查并安全备份原环境，再按指引重建。",
              file=sys.stderr)
        return 2
    venv.EnvBuilder(with_pip=True).create(VENV_DIR)

    result = subprocess.run(
        [
            str(venv_python()),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "-r",
            str(REQUIREMENTS),
        ],
        check=False,
    )
    if result.returncode != 0:
        print("运行依赖安装失败；请检查 Python/pip 与网络后重试。", file=sys.stderr)
        return result.returncode

    try:
        write_sitecustomize()
    except OSError as exc:
        print(f"写入 sitecustomize 失败：{exc}", file=sys.stderr)
        return 2
    print(f"OK standalone runtime ready: {venv_python()}")
    print("Dependencies: requests, websockets, opencv-python, Pillow")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
