#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校验 patches 目录里各 patch 的版本号是否一致。

为什么需要
----------
每个 patch 的版本号出现在**三个地方**：`META.json` 的 `version`、
`SKILL.md` frontmatter 的 `version:`、以及 `INDEX.md` 表格的版本列。
手动升级时极易只改其中一两处，长期就会漂移。

2026-09-11 实例：一次收尾检查发现 4 处不一致 ——
`timeliness-window`（frontmatter 落后 META 一版）、`cover-image-rules`（META 落后）、
`writing-facts-only`（META 落后）、`safe-wording-guard`（内容已加规则但版本没升）。
这类漂移会让"这份规则到底是哪一版"变得无法回答。

用法
----
    python tools/check_patch_versions.py            # 全目录校验
    python tools/check_patch_versions.py --json

退出码：0 = 全部一致 / 1 = 存在不一致 / 2 = 目录错误
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PATCHES_ROOT = os.path.normpath(os.path.join(HERE, ".."))
FM_RE = re.compile(r"^version:\s*(.+?)\s*$", re.MULTILINE)


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
    ap = argparse.ArgumentParser(description="校验各 patch 的版本号一致性")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if not os.path.isdir(PATCHES_ROOT):
        print(f"patches 目录不存在：{PATCHES_ROOT}", file=sys.stderr)
        return 2

    index = read_index_versions(os.path.join(PATCHES_ROOT, "INDEX.md"))
    rows = []
    problems = 0
    for name in sorted(os.listdir(PATCHES_ROOT)):
        d = os.path.join(PATCHES_ROOT, name)
        meta_path = os.path.join(d, "META.json")
        if not os.path.exists(meta_path):
            continue
        meta_v = read_meta_version(meta_path)
        fm_v = read_fm_version(os.path.join(d, "SKILL.md"))
        idx_v = index.get(name)
        vals = [v for v in (meta_v, fm_v, idx_v) if v]
        ok = len(set(vals)) <= 1
        if not ok:
            problems += 1
        rows.append({"patch": name, "meta": meta_v, "skill": fm_v,
                     "index": idx_v, "ok": ok})

    if args.json:
        print(json.dumps({"problems": problems, "rows": rows},
                         ensure_ascii=False, indent=2))
    else:
        print(f"{'patch':34s} {'META':9s} {'SKILL':9s} {'INDEX':9s} 结果")
        for r in rows:
            mark = "OK" if r["ok"] else "<<< 不一致"
            print(f"{r['patch']:34s} {str(r['meta']):9s} {str(r['skill']):9s} "
                  f"{str(r['index']):9s} {mark}")
        print()
        if problems:
            print(f"[ver] !! {problems} 个 patch 版本号不一致 —— 升级时只改了部分位置，请补齐")
        else:
            print("[ver] OK 全部一致")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
