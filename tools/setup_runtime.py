#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Create the local virtual environment and install the small runtime dependency set."""
from __future__ import annotations

import os
import subprocess
import sys
import venv
from pathlib import Path

PATCH_ROOT = Path(__file__).resolve().parent.parent
VENV_DIR = PATCH_ROOT / ".venv"
REQUIREMENTS = PATCH_ROOT / "requirements.txt"


def venv_python() -> Path:
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def main() -> int:
    if sys.version_info < (3, 10):
        print("需要 Python 3.10 或更新版本。", file=sys.stderr)
        return 2
    if not REQUIREMENTS.is_file():
        print(f"依赖清单不存在：{REQUIREMENTS}", file=sys.stderr)
        return 2

    if not venv_python().is_file():
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

    print(f"OK standalone runtime ready: {venv_python()}")
    print("Dependencies: requests, websockets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
