#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 / 校验交接基线页 `HANDOVER_BASELINE.md`。

为什么需要它
------------
`HANDOVER.md` 是升级交接的桥梁，但它是**散文**——版本号、hash、篇数写在正文里，
改了文件忘了改卡，两端就会各说各话。本脚本把「卡上声称的事实」变成**可重算**的：

- `python tools/gen_handover_baseline.py`          重写 `HANDOVER_BASELINE.md`
- `python tools/gen_handover_baseline.py --check`  只比对，不一致则列出差异行并退出 1

覆盖四类事实
------------
1. `core-overrides/overrides` 9 个受管文件的 sha256 前 16 位
2. root + 14 个 patch 的版本与优先级
3. `topics/` 每个 md 的字符数（脱敏版知识库）
4. 结构性判据（META 条目数、锚点、端口占位符是否裸露）

纪律：**改完任何受管文件，必须重跑本脚本并提交基线页**，否则 doctor 的
`check_baseline` 会持续告警（warn 级，不阻断发布）。

用法
----
    python tools/gen_handover_baseline.py            # 重写
    python tools/gen_handover_baseline.py --check    # 校验（CI / 交接前必跑）

退出码：0 = 一致 / 2 = 有差异或基线缺失或目录错误
（注意不能用 1：doctor 的 warn 级把 1 当作 EXIT_WARN 视为可接受，会吞掉真实差异）
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
BASELINE = os.path.join(ROOT, "HANDOVER_BASELINE.md")
OVERRIDES = os.path.join(ROOT, "core-overrides", "overrides")
TOPICS = os.path.join(ROOT, "topics")
SKIP_EXT = (".pyc", ".pyo")


def sha16(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()[:16]


def override_files() -> list[str]:
    out = []
    for dirpath, dirnames, filenames in os.walk(OVERRIDES):
        dirnames[:] = sorted(d for d in dirnames if d not in ("__pycache__", ".pytest_cache"))
        for name in sorted(filenames):
            if name.endswith(SKIP_EXT):
                continue
            rel = os.path.relpath(os.path.join(dirpath, name), OVERRIDES)
            out.append(rel.replace("\\", "/"))
    return sorted(out)


def root_version() -> str:
    with open(os.path.join(ROOT, "SKILL.md"), encoding="utf-8") as f:
        for line in f.read().splitlines()[:15]:
            if line.startswith("version:"):
                return line.split(":", 1)[1].strip()
    return "?"


def patch_versions() -> list[tuple[int, str, str]]:
    rows = []
    for name in sorted(os.listdir(ROOT)):
        meta = os.path.join(ROOT, name, "META.json")
        if not os.path.isfile(meta):
            continue
        with open(meta, encoding="utf-8") as f:
            data = json.load(f)
        rows.append((data.get("priority", 999), data.get("name", name), data.get("version", "?")))
    return sorted(rows)


def meta_counts() -> tuple[int, int]:
    with open(os.path.join(ROOT, "core-overrides", "META.json"), encoding="utf-8") as f:
        data = json.load(f)
    files = len(data.get("files", []))
    targets = len(data.get("overrides", {}).get("targets", []))
    return files, targets


def topic_sizes() -> dict[str, int]:
    sizes = {}
    for name in sorted(os.listdir(TOPICS)):
        if name.endswith(".md"):
            sizes[name] = len(open(os.path.join(TOPICS, name), encoding="utf-8").read())
    return sizes


def naked_ports() -> list[str]:
    """脱敏版知识库里不应出现真实端口字面量。"""
    hits = []
    for name in sorted(os.listdir(TOPICS)):
        if not name.endswith(".md"):
            continue
        text = open(os.path.join(TOPICS, name), encoding="utf-8").read()
        for port in ("9333", "9222"):
            if port in text:
                hits.append(f"{name}:{port}")
    return hits


def render() -> str:
    lines: list[str] = []
    add = lines.append
    rv = root_version()
    files, targets = meta_counts()
    add("# 交接基线（机器可核对）\n")
    add(f"> 生成：由 `tools/gen_handover_baseline.py` 自动产出｜root {rv}\n")
    add("> 用途：`HANDOVER.md` 的**可核对副本**。全量替换后按本页逐行比对，任何一行不符即停并回滚。\n")
    add("> 纪律：改完任何受管文件必须 `python tools/gen_handover_baseline.py` 重跑本页，否则记录与实物脱钩。\n")

    add("\n## 一、覆盖层受管文件（全量包必须原样携带，hash 必须一致）\n\n")
    add("| 文件 | sha256（前 16 位） |\n| --- | --- |\n")
    ov = override_files()
    for rel in ov:
        add("| `%s` | `%s` |\n" % (rel, sha16(os.path.join(OVERRIDES, rel))))
    add(f"\n> 共 {len(ov)} 个文件。\n")

    add("\n## 二、版本（不得回退）\n\n| 组件 | 版本 | 优先级 |\n| --- | --- | --- |\n")
    add("| root `SKILL.md` | %s | — |\n" % rv)
    for pri, name, ver in patch_versions():
        add("| `%s` | %s | %s |\n" % (name, ver, pri))

    add("\n## 三、规则知识库 `topics/`（不得少于下列字符数）\n\n| 文件 | 字符数 |\n| --- | --- |\n")
    sizes = topic_sizes()
    for name, n in sizes.items():
        add("| `%s` | %d |\n" % (name, n))
    add("| **合计** | **%d** |\n" % sum(sizes.values()))

    add("\n## 四、结构性判据\n\n")
    add("- `core-overrides/META.json`：`files` = %d、`overrides.targets` = %d\n" % (files, targets))
    add("- `topics/`：正文篇数 = %d（含 `QUICKREF.md`）\n" % len(sizes))
    add("- `HANDOVER.md` 三锚点：`全量替换包`、`本地定制清单`、`升级记录表`\n")
    add("- 敏感值：`topics/` 内不得出现真实端口字面量 9333 / 9222（须为 `<PORT_PUBLISH>` / `<PORT_COMMENT>`）\n")
    return "".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="生成/校验交接基线页")
    parser.add_argument("--check", action="store_true", help="只比对，不写文件")
    options = parser.parse_args()

    if not os.path.isdir(OVERRIDES) or not os.path.isdir(TOPICS):
        print("[baseline] 目录结构异常：缺 core-overrides/overrides 或 topics/", file=sys.stderr)
        return 2

    expected = render()

    if options.check:
        if not os.path.exists(BASELINE):
            print("[baseline] FAIL 缺少 HANDOVER_BASELINE.md，先跑 tools/gen_handover_baseline.py")
            return 2
        actual = open(BASELINE, encoding="utf-8").read()
        if actual.strip() == expected.strip():
            print("[baseline] OK 交接基线与实物一致")
            return 0
        import difflib
        diff = [l for l in difflib.unified_diff(
            actual.splitlines(), expected.splitlines(), "基线页", "实物", n=0, lineterm="")
            if l[:1] in "+-" and l[:3] not in ("+++", "---")]
        print("[baseline] FAIL 基线与实物不一致（%d 行），重跑 gen_handover_baseline.py：" % len(diff))
        for line in diff[:12]:
            print("   ", line[:120])
        if len(diff) > 12:
            print("    ... 另有 %d 行" % (len(diff) - 12))
        return 2

    with open(BASELINE, "w", encoding="utf-8", newline="\n") as f:
        f.write(expected)
    hits = naked_ports()
    print("[baseline] 已写出 HANDOVER_BASELINE.md（%d 字符）" % len(expected))
    if hits:
        print("[baseline] WARN topics 内出现真实端口字面量：" + "、".join(hits))
        print("           分发包须脱敏为 <PORT_PUBLISH> / <PORT_COMMENT>")
    return 0


if __name__ == "__main__":
    sys.exit(main())
