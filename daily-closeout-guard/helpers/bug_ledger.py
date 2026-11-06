#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""收尾第 7 步 · 事故台账盘点（防「只记不闭环」）。

为什么需要
----------
事故写进 `_BUGS.md` 后，如果没有固定窗口回头看，就会长期挂着没人修（B-053 类问题）。
本脚本在日终收口时把**未闭环**条目列出来，逼出一次「能修当场修 / 不能修登记进 _NEXT_」的动作。

判定口径
--------
- 条目 = `_BUGS.md` 中 `## ` 开头的段落；编号取标题里的 `B-<数字>`。
- **未闭环** = 标题或正文**不含**「已修 / 已闭环 / 已解决 / 已修复」；
  含「未修 / 待查 / 待观察 / 登记」关键字的会**强制判为未闭环**（防止正文里出现「已」字误判）。
- 只做只读盘点，**不改写台账**（回写由执行者手工完成 —— 见 SKILL.md 第三节第 4 点）。

用法
----
    python helpers/bug_ledger.py                       # 自动探测工作区
    python helpers/bug_ledger.py --root <工作区路径>
    python helpers/bug_ledger.py --json
    python helpers/bug_ledger.py --fail-on-open        # 有未闭环则退出码 1（供断言）

退出码：0 = 盘点完成 / 1 = 有未闭环（仅在 --fail-on-open）/ 2 = 未找到台账
"""
import argparse
import json
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BUG_RE = re.compile(r"##\s*(B-\d+)")
CLOSED_WORDS = ("已修", "已闭环", "已解决", "已修复")
OPEN_WORDS = ("未修", "待查", "待观察", "待修", "登记，未修", "登记，未")


def locate_root(explicit=None):
    if explicit:
        return explicit
    env = os.environ.get("XHS_WORKSPACE")
    if env and os.path.isdir(env):
        return env
    here = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
    for cand in (os.getcwd(), here, "C:/xhs"):
        if os.path.exists(os.path.join(cand, "_BUGS.md")):
            return cand
    return os.getcwd()


def parse(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    chunks = re.split(r"(?m)^##\s+", text)
    items = []
    for chunk in chunks[1:]:
        head = chunk.splitlines()[0] if chunk.splitlines() else ""
        body = chunk
        m = BUG_RE.search("## " + head)
        if not m:
            m = re.search(r"(B-\d+)", head)
        bid = m.group(1) if m else "(无编号)"
        title = head.strip()
        lowered = title + "\n" + body
        forced_open = any(w in lowered for w in OPEN_WORDS)
        closed = (not forced_open) and any(w in lowered for w in CLOSED_WORDS)
        summary = ""
        for line in chunk.splitlines()[1:]:
            line = line.strip()
            if line.startswith("-") and ("现象" in line or "影响" in line or line.startswith("- **现象")):
                summary = line.lstrip("- ").strip()
                break
        if not summary:
            for line in chunk.splitlines()[1:]:
                if line.strip():
                    summary = line.strip()
                    break
        items.append({"id": bid, "title": title, "closed": closed, "summary": summary[:120]})
    return items


def main():
    ap = argparse.ArgumentParser(description="收尾第 7 步：事故台账未闭环盘点")
    ap.add_argument("--root", default=None, help="工作区根目录（含 _BUGS.md）")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--fail-on-open", action="store_true", help="存在未闭环时退出码 1")
    args = ap.parse_args()

    root = locate_root(args.root)
    path = os.path.join(root, "_BUGS.md")
    if not os.path.exists(path):
        sys.stderr.write("[bug-ledger] 未找到台账：%s（先建 _BUGS.md 或用 --root 指定）\n" % path)
        return 2

    items = parse(path)
    # 同编号多段（登记段 + 解除段）按编号聚合：任一段落已闭环即视为该编号闭环
    merged = {}
    order = []
    for it in items:
        key = it["id"]
        if key == "(无编号)":
            order.append(it)
            continue
        if key not in merged:
            merged[key] = dict(it)
            order.append(merged[key])
        else:
            merged[key]["closed"] = merged[key]["closed"] or it["closed"]
            if not merged[key]["summary"] and it["summary"]:
                merged[key]["summary"] = it["summary"]

    opened = [i for i in order if not i["closed"]]
    closed = [i for i in order if i["closed"]]

    if args.json:
        print(json.dumps({"root": root, "total": len(items),
                          "open": opened, "closed_count": len(closed)},
                         ensure_ascii=False, indent=2))
    else:
        print("[bug-ledger] 台账：%s" % path)
        print("[bug-ledger] 总条目 %d —— 未闭环 %d / 已闭环 %d" % (len(items), len(opened), len(closed)))
        if opened:
            print("\n== 未闭环（收尾须处理：能修当场修 ≤2 项，否则登记进 _NEXT_）==")
            for i in opened:
                print("  - %s %s" % (i["id"], i["title"]))
                if i["summary"]:
                    print("      %s" % i["summary"])
        else:
            print("\n== 无未闭环条目 ==")
        print("\n提示：修完须复跑对应校验脚本（check_patch_versions / check_doc_layers）才可回写「已修」。")

    return 1 if (args.fail_on_open and opened) else 0


if __name__ == "__main__":
    sys.exit(main())
