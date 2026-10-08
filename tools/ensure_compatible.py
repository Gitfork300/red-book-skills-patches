#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Activate the bundled runtime only after its local compatibility gates pass."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

PATCH_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MAIN = PATCH_ROOT / "runtime"
APPLY = PATCH_ROOT / "core-overrides" / "helpers" / "apply_overrides.py"
POST_SYNC = PATCH_ROOT / "tools" / "post_sync_check.py"
CACHE = PATCH_ROOT / "state" / "compatibility.json"
def run(args: list[str], *, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=PATCH_ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=check,
    )


def fail(message: str) -> int:
    print(f"FAIL {message}", file=sys.stderr)
    return 1


def resolve_main(explicit: str | None) -> Path:
    value = explicit or os.environ.get("RED_BOOK_SKILLS_ROOT")
    return Path(value).expanduser().resolve() if value else DEFAULT_MAIN.resolve()


def check_upstream_root(main: Path) -> str | None:
    if not main.is_dir():
        return f"找不到随 Patch 分发的运行目录：{main}"
    required = (
        "INSTRUCTIONS.md",
        "scripts/account_manager.py",
        "scripts/cdp_publish.py",
        "scripts/chrome_launcher.py",
        "scripts/feed_explorer.py",
        "scripts/image_downloader.py",
        "scripts/publish_pipeline.py",
        "scripts/run_lock.py",
        "references/01-publish-flow.md",
    )
    missing = [item for item in required if not (main / item).exists()]
    if missing:
        return f"随 Patch 分发的运行文件不完整，缺少：{', '.join(missing)}"
    skill_text = (PATCH_ROOT / "SKILL.md").read_text(encoding="utf-8", errors="replace")
    if "name: red-book-skills-patch" not in skill_text:
        return "Patch 入口 SKILL.md 元数据无效"
    for module in ("requests", "websockets"):
        if importlib.util.find_spec(module) is None:
            return (
                f"当前 Python 环境缺少 {module}；请先运行 "
                f"'{sys.executable} {PATCH_ROOT / 'tools' / 'setup_runtime.py'}'"
            )
    return None


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fingerprint(main: Path) -> str:
    fixed_paths = [
        PATCH_ROOT / "core-overrides" / "baseline.json",
        PATCH_ROOT / "core-overrides" / "contracts.json",
        main / "INSTRUCTIONS.md",
        main / "scripts" / "account_manager.py",
        main / "scripts" / "cdp_publish.py",
        main / "scripts" / "chrome_launcher.py",
        main / "scripts" / "feed_explorer.py",
        main / "scripts" / "image_downloader.py",
        main / "scripts" / "publish_pipeline.py",
        main / "scripts" / "run_lock.py",
    ]
    digest = hashlib.sha256()
    digest.update(str(main).encode("utf-8"))
    paths = list(fixed_paths)
    overrides = PATCH_ROOT / "core-overrides" / "overrides"
    paths.extend(sorted(path for path in overrides.rglob("*") if path.is_file()))
    for path in paths:
        digest.update(str(path).encode("utf-8"))
        digest.update(
            _hash_file(path).encode("ascii") if path.is_file() else b"missing"
        )
    return digest.hexdigest()


def _load_cache(main: Path, fingerprint: str) -> bool:
    try:
        data = json.loads(CACHE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return (
        data.get("status") == "ok"
        and data.get("main") == str(main)
        and data.get("fingerprint") == fingerprint
    )


def _save_cache(main: Path, fingerprint: str) -> None:
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": "ok",
        "main": str(main),
        "fingerprint": fingerprint,
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    temporary = CACHE.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(CACHE)


def apply_and_verify() -> tuple[bool, str]:
    status = run([sys.executable, str(APPLY), "status"])
    status_text = f"{status.stdout}\n{status.stderr}"
    if "DRIFTED" in status_text:
        return False, "检测到本体或覆盖层被直接改动（DRIFTED），拒绝自动覆盖"
    applied = run([sys.executable, str(APPLY), "apply"])
    if applied.returncode != 0:
        return False, applied.stdout or applied.stderr
    verified = run([sys.executable, str(APPLY), "verify"])
    if verified.returncode != 0:
        return False, verified.stdout or verified.stderr
    return True, verified.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="启用随 Patch 分发的独立运行层")
    parser.add_argument("--main", help="兼容运行目录；默认使用 Patch 内 runtime/")
    parser.add_argument("--refresh", action="store_true",
                        help="忽略本机兼容缓存并重新执行完整门禁")
    args = parser.parse_args()

    if not APPLY.exists() or not POST_SYNC.exists():
        return fail("Patch 文件不完整：缺少 core-overrides 或 post_sync_check")
    main_root = resolve_main(args.main)
    for error in (check_upstream_root(main_root),):
        if error:
            return fail(error)

    os.environ["RED_BOOK_SKILLS_ROOT"] = str(main_root)
    fingerprint = _fingerprint(main_root)
    if not args.refresh and _load_cache(main_root, fingerprint):
        print("OK red-book-skills-patch active (cached compatibility check)")
        print(f"  patch : {PATCH_ROOT}")
        print(f"  main  : {main_root}")
        print("  route : reuse this result for the current session")
        return 0

    ok, detail = apply_and_verify()
    if not ok:
        return fail(detail)

    contract = run([sys.executable, str(POST_SYNC)])
    if contract.returncode != 0:
        return fail(contract.stdout or contract.stderr)
    _save_cache(main_root, _fingerprint(main_root))
    print(f"OK standalone red-book-skills-patch active")
    print(f"  patch : {PATCH_ROOT}")
    print(f"  main  : {main_root}")
    print("  route : call scripts only after this gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
