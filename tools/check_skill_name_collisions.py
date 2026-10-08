#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检测技能树内的 SKILL.md 撞名 —— 防止"技能列表出现多条同名项"。

背景（2026-10-07 事故）：
  WorkBuddy **递归扫描** ~/.workbuddy/skills/**/SKILL.md，按 frontmatter 的 `name:` 注册技能，
  **不区分**这个文件是不是别的技能的资源目录 / 备份目录。
  一旦某个副本的 name 与本体相同：
    1. 技能列表出现多条同名项；
    2. 同名时**加载哪份取决于扫描顺序、不确定** —— 若命中的是旧副本（如 apply 前的备份），
       覆盖层后续的修复会静默失效，且不报错。
  本次事故即由 `core-overrides/state/backup/<ts>/SKILL.md`（上游旧版副本）引起，
  该目录已迁到 `~/xhs-workspace/_skill-backup/core-overrides-preapply/`。

判定口径：
  撞名不等于有风险。若撞名的几份文件**内容完全一致**（行尾归一 + 去 BOM 后 sha256 相同），
  加载哪份结果都一样 —— 如 `core-overrides/overrides/SKILL.md`（覆盖层权威源，必须与本体同名，
  改 name 会在 apply 时污染本体）。这类标记为 `SAME`，不算失败。
  内容不同 → `DIFF`，是真风险，退出码 1。

用法：
  python tools/check_skill_name_collisions.py [--all] [--root <dir>]
    --all            打印全部已扫描文件（默认只报告问题）
    --root <dir>     扫描指定技能根目录（默认 ~/.workbuddy/skills；
                     项目级技能目录、临时测试目录用这个）

退出码：0=无内容冲突 / 1=存在内容不一致的撞名 / 2=错误
"""
from __future__ import annotations

import hashlib
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SKILLS_ROOT = os.path.join(os.path.expanduser("~"), ".workbuddy", "skills")
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv"}


def read_name(path: str) -> str | None:
    """读 frontmatter 的 name；无 frontmatter 或没有 name 返回 None。"""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            head = f.read(4096)
    except OSError:
        return None
    if not head.startswith("---"):
        return None
    for line in head.splitlines()[1:]:
        if line.strip() == "---":
            break
        if line.startswith("name:"):
            return line.split(":", 1)[1].strip().strip('"').strip("'")
    return None


def norm_sha(path: str) -> str:
    with open(path, "rb") as f:
        d = f.read()
    return hashlib.sha256(
        d.replace(b"\r\n", b"\n").replace(b"\r", b"\n").lstrip(b"\xef\xbb\xbf")
    ).hexdigest()


def collect(root: str) -> dict[str, list[str]]:
    """name -> [相对路径]"""
    grouped: dict[str, list[str]] = {}
    if not os.path.isdir(root):
        print(f"!! 技能根目录不存在：{root}", file=sys.stderr)
        return grouped
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in SKIP_DIRS]
        if "SKILL.md" not in fns:
            continue
        fp = os.path.join(dp, "SKILL.md")
        name = read_name(fp)
        if not name:
            continue
        grouped.setdefault(name, []).append(os.path.relpath(fp, root))
    return grouped


def _arg(name: str, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def main() -> int:
    show_all = "--all" in sys.argv
    root = _arg("--root", SKILLS_ROOT)
    grouped = collect(root)
    if not grouped:
        print("!! 未扫到任何 SKILL.md", file=sys.stderr)
        return 2

    total = sum(len(v) for v in grouped.values())
    print(f"技能根目录: {root}")
    print(f"已扫描 SKILL.md: {total} 个，不同 name: {len(grouped)} 个")
    print()

    if show_all:
        for name in sorted(grouped):
            for rel in grouped[name]:
                print(f"  {name:32} {rel}")
        print()

    bad = 0
    collisions = {n: ps for n, ps in grouped.items() if len(ps) > 1}
    if not collisions:
        print("OK 无撞名")
        return 0

    print(f"撞名 {len(collisions)} 组：")
    for name in sorted(collisions):
        paths = collisions[name]
        shas = {norm_sha(os.path.join(root, p)) for p in paths}
        tag = "SAME" if len(shas) == 1 else "DIFF"
        print(f"\n  [{tag}] {name}  ({len(paths)} 份)")
        for p in sorted(paths):
            print(f"        {p}")
        if tag == "SAME":
            print("        内容完全一致 → 加载哪份都一样，无风险")
        else:
            bad += 1
            print("        !! 内容不一致 —— 同名时加载到哪份不确定，旧版会让后续修复静默失效")
            print("           处置：把副本移到 skills 树之外，或让它不再含 frontmatter name")

    print()
    if bad:
        print(f"结论：{bad} 组撞名存在内容差异，需要处理。")
        return 1
    print("结论：所有撞名内容一致，无实际风险。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
