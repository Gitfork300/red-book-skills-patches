#!/usr/bin/env python3
"""Initialize a new workspace from the distributable rule references."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
TOPICS = ROOT / "topics"


def main() -> int:
    parser = argparse.ArgumentParser(description="为新业务工作区建立规则入口，不覆盖已有 memory")
    parser.add_argument("--workspace", default=os.environ.get("XHS_WORKSPACE") or "C:/xhs")
    args = parser.parse_args()
    workspace = Path(args.workspace)
    memory = workspace / ".workbuddy" / "memory"
    if memory.exists():
        print(f"FAIL {memory} 已存在；为保护已有数据，未写入。请人工核对并合并。", file=sys.stderr)
        return 2
    try:
        topics = sorted(p for p in TOPICS.glob("*.md") if p.name != "QUICKREF.md")
        if not topics:
            raise FileNotFoundError(f"规则详情不存在：{TOPICS}")
        quickref = (TOPICS / "QUICKREF.md").read_text(encoding="utf-8")
        index = "\n\n## 工作区详情索引\n\n" + "".join(
            f"- topics/{path.name}\n" for path in topics
        )
        memory.mkdir(parents=True, exist_ok=False)
        target_topics = memory / "topics"
        target_topics.mkdir()
        for source in topics:
            with (target_topics / source.name).open("x", encoding="utf-8", newline="") as target:
                target.write(source.read_text(encoding="utf-8"))
        with (memory / "MEMORY.md").open("x", encoding="utf-8", newline="") as target:
            target.write(quickref + index)
        (workspace / "xhs_publish").mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(f"FAIL 初始化未完成：{exc}；检查 {memory} 后再处理，未覆盖现有文件。", file=sys.stderr)
        return 2
    print(f"OK 已建立工作区规则入口与稿件目录：{workspace}")
    print("请按本机业务复核规则、账号及登录态；未复制历史台账或凭据。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
