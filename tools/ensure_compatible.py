#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Activate red-book-skills only after the Patch compatibility gates pass."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
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
DEFAULT_MAIN = PATCH_ROOT.parent / "red-book-skills"
DEFAULT_BACKUP = PATCH_ROOT / "red-book-skills-upstream"
APPLY = PATCH_ROOT / "core-overrides" / "helpers" / "apply_overrides.py"
POST_SYNC = PATCH_ROOT / "tools" / "post_sync_check.py"
CACHE = PATCH_ROOT / "state" / "compatibility.json"
UPSTREAM_REQUIRED = (
    "SKILL.md",
    "scripts",
    "scripts/account_manager.py",
    "scripts/cdp_publish.py",
    "scripts/chrome_launcher.py",
    "scripts/feed_explorer.py",
    "scripts/image_downloader.py",
    "scripts/publish_pipeline.py",
    "scripts/run_lock.py",
)


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


def resolve_backup(explicit: str | None) -> Path:
    value = explicit or os.environ.get("RED_BOOK_SKILLS_UPSTREAM_BACKUP")
    return Path(value).expanduser().resolve() if value else DEFAULT_BACKUP.resolve()


def _is_upstream_root(root: Path) -> bool:
    skill = root / "SKILL.md"
    if not skill.is_file():
        return False
    return "name: red-book-skills" in skill.read_text(
        encoding="utf-8", errors="replace"
    )


def restore_missing(main: Path, backup: Path) -> list[str]:
    """Restore only missing declared dependencies from the local upstream snapshot."""
    if not backup.is_dir() or not _is_upstream_root(backup):
        return []
    restored = []
    for relative in UPSTREAM_REQUIRED:
        source = backup / relative
        target = main / relative
        if target.exists() or not source.is_file():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        restored.append(relative)
    return restored


def check_upstream_root(main: Path) -> str | None:
    if not main.is_dir():
        return f"找不到上游目录：{main}"
    missing = [item for item in UPSTREAM_REQUIRED if not (main / item).exists()]
    if missing:
        return f"上游目录不完整，缺少：{', '.join(missing)}"
    skill_text = (main / "SKILL.md").read_text(encoding="utf-8", errors="replace")
    if "name: red-book-skills" not in skill_text:
        return "上游 SKILL.md 不是 red-book-skills"
    return None


def check_source(main: Path) -> str | None:
    git_dir = main / ".git"
    if not git_dir.exists():
        return None
    result = run(["git", "-C", str(main), "remote", "-v"])
    remotes = result.stdout.lower()
    if remotes and "aus666666/red-book-skills" not in remotes:
        return "上游 Git remote 不是 aus666666/red-book-skills；请显式确认后再运行"
    return None


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_head(main: Path) -> str:
    result = run(["git", "-C", str(main), "rev-parse", "HEAD"])
    return result.stdout.strip() if result.returncode == 0 else ""


def _fingerprint(main: Path) -> str:
    fixed_paths = [
        PATCH_ROOT / "core-overrides" / "baseline.json",
        PATCH_ROOT / "core-overrides" / "contracts.json",
        main / "SKILL.md",
        main / "scripts" / "cdp_publish.py",
        main / "scripts" / "chrome_launcher.py",
        main / "scripts" / "publish_pipeline.py",
    ]
    digest = hashlib.sha256()
    digest.update(str(main).encode("utf-8"))
    digest.update(_git_head(main).encode("ascii", "replace"))
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
    parser = argparse.ArgumentParser(description="启用 red-book-skills 的 Patch 安全兼容门面")
    parser.add_argument("--main", help="上游 red-book-skills 目录；默认使用同级目录")
    parser.add_argument(
        "--upstream-backup",
        help="本地上游备份目录；默认使用同级 Patch 下的 red-book-skills-upstream",
    )
    parser.add_argument("--refresh", action="store_true",
                        help="忽略本机兼容缓存并重新执行完整门禁")
    args = parser.parse_args()

    if not APPLY.exists() or not POST_SYNC.exists():
        return fail("Patch 文件不完整：缺少 core-overrides 或 post_sync_check")
    main_root = resolve_main(args.main)
    backup_root = resolve_backup(args.upstream_backup)
    if not main_root.is_dir():
        return fail(f"找不到上游目录：{main_root}")
    restored = restore_missing(main_root, backup_root)
    if restored:
        print(f"RESTORED 从本地上游备份补回 {len(restored)} 个缺失依赖：")
        for relative in restored:
            print(f"  - {relative}")
    for error in (check_upstream_root(main_root), check_source(main_root)):
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
    print(f"OK red-book-skills-patch active")
    print(f"  patch : {PATCH_ROOT}")
    print(f"  main  : {main_root}")
    print("  route : call scripts only after this gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
