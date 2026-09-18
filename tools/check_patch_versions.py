#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校验 patches 目录里各 patch 的版本号与登记状态是否一致。

检查五件事
----------
1. **版本号三处一致**：`META.json` 的 `version`、`SKILL.md` frontmatter 的 `version:`、
   以及 `INDEX.md` 表格的版本列。手动升级时极易只改其中一两处，长期就会漂移。
2. **INDEX 已登记**：有 `SKILL.md` 的 patch 必须出现在 INDEX 表格里（2026-09-15 发现
   `comment-reply-guard` 建了两天仍没登记 —— 评论体系整条链路在索引中缺席）。
3. **META.json 存在**：patch 必须有 `META.json`（登记完整性）。
4. **`system` 字段一致**：`SKILL.md` frontmatter 必须有 `system: publish|comment|shared`，
   且与 `META.json` 的 `system` 相同（体系边界契约见 `SYSTEMS.md`）。
5. **`priority` 字段一致**：加载顺序只能由 `META.json` 的数字优先级决定，
   `SKILL.md` frontmatter 必须使用同一个数字，禁止使用 `P0` 等另一套等级。

历史实例
--------
- 2026-09-11：一次收尾检查发现 4 处版本漂移 ——
  `timeliness-window`（frontmatter 落后 META 一版）、`cover-image-rules`（META 落后）、
  `writing-facts-only`（META 落后）、`safe-wording-guard`（内容已加规则但版本没升）。
- 2026-09-15：发现 8 个 patch 三处不一致 + `comment-reply-guard` 既无 META 也没登记。

用法
----
    python tools/check_patch_versions.py            # 全目录校验
    python tools/check_patch_versions.py --json

退出码：0 = 全部一致 / 1 = 存在问题 / 2 = 目录错误
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PATCHES_ROOT = os.path.normpath(os.path.join(HERE, ".."))
FM_RE = re.compile(r"^version:\s*(.+?)\s*$", re.MULTILINE)
FM_PRIORITY_RE = re.compile(r"^priority:\s*(\d+)\s*$", re.MULTILINE)


def read_meta_version(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f).get("version")
    except Exception:
        return None


def read_fm_version(path):
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        head = "".join(f.readlines()[:15])
    m = FM_RE.search(head)
    return m.group(1) if m else None


def read_fm_priority(path):
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        head = "".join(f.readlines()[:20])
    m = FM_PRIORITY_RE.search(head)
    return int(m.group(1)) if m else None


def read_index_versions(path):
    """从 INDEX.md 表格里抽 {patch 名: 版本}。"""
    out = {}
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8") as f:
        for line in f:
            if not line.startswith("|"):
                continue
            cols = [c.strip() for c in line.strip().strip("|").split("|")]
            for i, c in enumerate(cols):
                m = re.fullmatch(r"`([a-z0-9\-]+)`", c)
                if m and i + 2 < len(cols) and re.fullmatch(r"\d+\.\d+\.\d+", cols[i + 2]):
                    out[m.group(1)] = cols[i + 2]
    return out


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="校验各 patch 的版本号一致性")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if not os.path.isdir(PATCHES_ROOT):
        print(f"patches 目录不存在：{PATCHES_ROOT}", file=sys.stderr)
        return 2

    index = read_index_versions(os.path.join(PATCHES_ROOT, "INDEX.md"))
    rows = []
    problems = 0
    priorities = {}
    dependencies = {}

    def read_fm_system(path):
        if not os.path.exists(path):
            return None
        with open(path, encoding="utf-8") as f:
            head = "".join(f.readlines()[:15])
        m = re.search(r"^system:\s*(.+?)\s*$", head, re.MULTILINE)
        return m.group(1) if m else None

    def read_meta_system(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f).get("system")
        except Exception:
            return None

    ignored_dirs = {"red-book-skills-upstream"}
    for name in sorted(os.listdir(PATCHES_ROOT)):
        d = os.path.join(PATCHES_ROOT, name)
        if (name.startswith("_") or name == "tools" or name in ignored_dirs
                or not os.path.isdir(d)):
            continue
        skill_path = os.path.join(d, "SKILL.md")
        if not os.path.exists(skill_path):
            continue
        meta_path = os.path.join(d, "META.json")
        notes = []
        if os.path.exists(meta_path):
            meta_v = read_meta_version(meta_path)
            meta_sys = read_meta_system(meta_path)
            try:
                with open(meta_path, encoding="utf-8") as f:
                    meta_data = json.load(f)
                    meta_priority = meta_data.get("priority")
                    raw_dependencies = list(meta_data.get("dependencies") or [])
                    dependencies[name] = [
                        dep if isinstance(dep, str) else dep.get("patch")
                        for dep in raw_dependencies
                        if isinstance(dep, str) or isinstance(dep, dict) and dep.get("patch")
                    ]
            except Exception:
                meta_priority = None
                dependencies[name] = []
        else:
            meta_v, meta_sys, meta_priority = None, None, None
            dependencies[name] = []
            notes.append("META.json 缺失")
        fm_v = read_fm_version(skill_path)
        fm_sys = read_fm_system(skill_path)
        fm_priority = read_fm_priority(skill_path)
        idx_v = index.get(name)
        if idx_v is None:
            notes.append("INDEX 未登记")
        if fm_sys is None:
            notes.append("SKILL 缺 system 字段")
        elif meta_sys and meta_sys != fm_sys:
            notes.append("system 不一致 %s/%s" % (meta_sys, fm_sys))
        if meta_priority is not None and fm_priority != meta_priority:
            notes.append("priority 不一致 %s/%s" % (meta_priority, fm_priority))
        if meta_priority is not None:
            priorities.setdefault(meta_priority, []).append(name)
        vals = [v for v in (meta_v, fm_v, idx_v) if v]
        ok = len(set(vals)) <= 1 and not notes
        if not ok:
            problems += 1
        rows.append({"patch": name, "meta": meta_v, "skill": fm_v,
                     "meta_priority": meta_priority, "skill_priority": fm_priority,
                     "index": idx_v, "ok": ok, "notes": notes})

    for priority, names in priorities.items():
        if len(names) > 1:
            problems += len(names)
            for row in rows:
                if row["patch"] in names:
                    row["ok"] = False
                    row["notes"].append(
                        "priority 重复 %s（%s）" % (priority, "、".join(names))
                    )

    known = set(dependencies)
    for name, deps in dependencies.items():
        for dep in deps:
            if dep not in known:
                problems += 1
                next(row for row in rows if row["patch"] == name)["notes"].append(
                    "依赖不存在 %s" % dep
                )

    visiting, visited = set(), set()

    def visit(name, chain):
        nonlocal problems
        if name in visiting:
            problems += 1
            owner = next(row for row in rows if row["patch"] == chain[0])
            owner["notes"].append("依赖循环 %s" % " -> ".join(chain + [name]))
            return
        if name in visited:
            return
        visiting.add(name)
        for dep in dependencies.get(name, []):
            if dep in known:
                visit(dep, chain + [dep])
        visiting.remove(name)
        visited.add(name)

    for name in known:
        visit(name, [name])

    if args.json:
        print(json.dumps({"problems": problems, "rows": rows},
                         ensure_ascii=False, indent=2))
    else:
        print(f"{'patch':32s} {'META':9s} {'SKILL':9s} {'INDEX':9s} 结果")
        for r in rows:
            if r["ok"]:
                mark = "OK"
            elif r["notes"]:
                mark = "<<< " + "；".join(r["notes"])
            else:
                mark = "<<< 版本不一致"
            print(f"{r['patch']:32s} {str(r['meta']):9s} {str(r['skill']):9s} "
                  f"{str(r['index']):9s} {mark}")
        print()
        if problems:
            print(f"[ver] !! {problems} 个 patch 有问题 —— 版本不一致 / INDEX 漏登记 / "
                  f"META 缺失 / system 字段缺失，请补齐")
        else:
            print("[ver] OK 全部一致（版本 · INDEX 登记 · META 存在 · system 字段）")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
