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


def _portable_path(path: Path) -> str:
    """把路径压成「相对 PATCH_ROOT」的写法，供缓存与指纹使用。

    为什么不能存绝对路径（2026-11-06 用户裁定）：缓存里记 `C:/Users/<某机>/...`，
    换机器或换目录后这份缓存要么假绿、要么每次重算；指纹里混入绝对路径还会让
    「同一份代码」在不同机器上得出不同指纹，等于缓存永远失效。
    """
    try:
        return path.resolve().relative_to(PATCH_ROOT.resolve()).as_posix()
    except (ValueError, OSError):
        return path.name


def _cache_path() -> Path:
    """缓存位置：env 覆盖 > 工作区 `.state/cache`（迁移期回落树内旧址）。

    权威见 `tools/runtime_paths.py`。缓存属运行态，不能随 skill 包分发。
    """
    override = os.environ.get("XHS_COMPAT_CACHE")
    if override:
        return Path(override)
    import runtime_paths

    return Path(runtime_paths.resolve_compat_cache())
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
    for module in ("requests", "websockets", "cv2", "PIL"):
        if importlib.util.find_spec(module) is None:
            return (
                f"当前 Python 环境缺少 {module}；确认正在使用 Skill 的 .venv。"
                "若环境已存在，请保留并按 RUNTIME_SETUP.md 排查和安全迁移；"
                "仅首次安装时运行 tools/setup_runtime.py。"
            )
    return None


# 生成物（__pycache__ / .pyc …）不参与指纹与覆盖比对。
# 否则任何一次 import / py_compile 都会让指纹变化、状态永久 DRIFTED，
# 表现为「这个 skill 每次跑都报错」。与 apply_overrides.py 保持同一套规则。
IGNORE_DIR_NAMES = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ipynb_checkpoints"}
IGNORE_SUFFIXES = (".pyc", ".pyo", ".pyd", ".bak", ".orig", ".tmp", ".swp")
IGNORE_FILE_NAMES = {".DS_Store", "Thumbs.db"}


def _is_generated(path: Path) -> bool:
    if any(part in IGNORE_DIR_NAMES for part in path.parts):
        return True
    return path.name in IGNORE_FILE_NAMES or path.name.lower().endswith(IGNORE_SUFFIXES)


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
    # 只用相对路径参与指纹：绝对路径会把「同一份代码」在不同机器上算成不同指纹
    digest.update(_portable_path(main).encode("utf-8"))
    paths = list(fixed_paths)
    overrides = PATCH_ROOT / "core-overrides" / "overrides"
    paths.extend(sorted(path for path in overrides.rglob("*")
                        if path.is_file() and not _is_generated(path)))
    for path in paths:
        digest.update(_portable_path(path).encode("utf-8"))
        digest.update(
            _hash_file(path).encode("ascii") if path.is_file() else b"missing"
        )
    return digest.hexdigest()


def _load_cache(main: Path, fingerprint: str) -> bool:
    try:
        data = json.loads(_cache_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return (
        data.get("status") == "ok"
        and data.get("main_rel") == _portable_path(main)
        and data.get("fingerprint") == fingerprint
    )


def _save_cache(main: Path, fingerprint: str) -> None:
    cache = _cache_path()
    cache.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": "ok",
        "main_rel": _portable_path(main),
        "fingerprint": fingerprint,
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    temporary = cache.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(cache)


def apply_and_verify() -> tuple[bool, str]:
    # 先清掉覆盖层里的编译缓存（自愈）：.pyc 内嵌路径与 mtime，
    # 混入清单会造成永久 DRIFTED，是本门禁最常见的假故障源。
    clean = run([sys.executable, str(APPLY), "clean"])
    if clean.returncode != 0:
        return False, clean.stdout or clean.stderr or "覆盖层生成物清理失败"

    # 用结构化输出判定，而不是在整段文本里搜 "DRIFTED"
    # —— 后者会被说明文字、路径名里的同名目录误伤。
    status = run([sys.executable, str(APPLY), "status", "--json"])
    if status.returncode not in (0, 1):
        return False, status.stderr or status.stdout or "无法检查覆盖层状态"
    try:
        data = json.loads(status.stdout)
    except ValueError:
        return False, ("覆盖层状态无法解析（apply_overrides.py 可能失败了）：\n"
                       + (status.stdout or status.stderr or "").strip())
    drifted = [f["path"] for f in data.get("files", []) if f.get("status") == "DRIFTED"]
    if drifted:
        return False, (
            "检测到本体被直接改动（DRIFTED），拒绝自动覆盖：\n  " + "\n  ".join(drifted)
            + "\n  处置：把改动搬进 core-overrides/overrides/ 后重跑；"
              "若确认是生成物，运行 "
              f"'{sys.executable} {APPLY} clean'"
        )

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
