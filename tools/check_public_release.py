#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""公开发布前的本地安全门禁。

只检查当前工作树和 Git 索引，不联网，不读取或输出敏感值。
业务标题、活动名称和规则文本允许保留；登录态、凭据和运行日志必须阻断。
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

FORBIDDEN_PATH = re.compile(
    r"(^|/)(?:logs?|state|sessions?|auth|credentials|profiles?|browser-profile|chrome-profile)(?:/|$)"
    r"|(?:cookies?|accounts?|credentials?|auth|session)\.(?:json|cookie|cookies?)$",
    re.IGNORECASE,
)
SECRET_PATTERN = re.compile(
    r"(?:-----BEGIN (?:RSA|OPENSSH|EC|DSA|PGP) PRIVATE KEY-----)"
    r"|(?:\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b)"
    r"|(?:\bAKIA[0-9A-Z]{16}\b)"
    r"|(?:\bsk-[A-Za-z0-9]{20,}\b)"
    r"|(?:\bBearer\s+[A-Za-z0-9._~+/=-]{20,})"
    r"|(?:\b(?:password|passwd|client_secret|api[_-]?key|access[_-]?token|refresh[_-]?token)\s*[:=]\s*[\"']?[^ \t\"']{8,})",
    re.IGNORECASE,
)


def git(*args: str) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(ROOT), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def check_paths() -> list[str]:
    findings = []
    for path in git("ls-files"):
        normalized = path.replace("\\", "/")
        allowed_placeholder = normalized.endswith(("/README.md", "/.gitkeep"))
        if FORBIDDEN_PATH.search(normalized) and not allowed_placeholder:
            findings.append(f"tracked private path: {path}")
    return findings


def check_files() -> tuple[list[str], int]:
    findings = []
    scanned = 0
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [
            d for d in dirs
            if d not in {".git", "_archive", "__pycache__", ".venv"}
        ]
        for name in files:
            path = Path(base) / name
            try:
                data = path.read_bytes()
            except OSError:
                continue
            if b"\x00" in data[:4096]:
                continue
            scanned += 1
            text = data.decode("utf-8", "replace")
            match = SECRET_PATTERN.search(text)
            if match:
                line = text.count("\n", 0, match.start()) + 1
                findings.append(f"credential-like content: {path.relative_to(ROOT)}:{line}")
    return findings, scanned


def main() -> int:
    parser = argparse.ArgumentParser(description="公开发布前本地安全门禁")
    parser.add_argument("--quiet", action="store_true", help="只输出失败项")
    args = parser.parse_args()

    path_findings = check_paths()
    content_findings, scanned = check_files()
    findings = path_findings + content_findings

    if findings:
        for finding in findings:
            print(f"FAIL {finding}")
        return 1

    if not args.quiet:
        print(f"OK public release check passed; scanned {scanned} text files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
