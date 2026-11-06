#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一键体检 —— 把散落在各处的门禁串成一条命令，并对已知故障自愈。

为什么需要
----------
这个 skill 的门禁原本要手动依次跑 5~6 个脚本，漏一步就带着隐患上阵；
其中「覆盖层混入 __pycache__」这类故障还会让门禁**永久失败**且看不出原因。
本脚本按固定顺序体检，先自愈、后只读校验，最后给出一句话结论。

执行顺序（先修复，再校验）
--------------------------
0. clean       —— 清掉覆盖层里的编译缓存（自愈，不动任何源文件）
1. check_env   —— 环境与变量自检（Python/venv/工作区/Chrome/端口；缺失仅警告不阻断）
2. ensure_compatible --refresh —— 应用覆盖层 + 契约自检（阻断）
3. post_sync_check            —— 覆盖层契约自洽（阻断 / 警告）
4. check_patch_versions       —— patch 版本与登记一致性（阻断）
5. check_doc_layers           —— 文档分层与关键锚点（阻断）
6. unittest discover          —— 回归测试（阻断）
7. check_public_release       —— 敏感信息门禁（阻断）

用法
----
    python tools/doctor.py              # 全量体检
    python tools/doctor.py --quick      # 跳过回归测试
    python tools/doctor.py --json       # 结构化输出，便于脚本消费

退出码：0 = 全通过 / 1 = 仅警告 / 2 = 存在阻断项或执行错误
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
APPLY = ROOT / "core-overrides" / "helpers" / "apply_overrides.py"

EXIT_OK, EXIT_WARN, EXIT_FAIL = 0, 1, 2


def run_step(args: list[str], *, timeout: int = 300) -> tuple[int, str]:
    try:
        result = subprocess.run(
            args,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return 124, f"超时（>{timeout}s）：{' '.join(str(a) for a in args)}"
    except OSError as exc:
        return 127, f"无法执行：{exc}"
    output = (result.stdout or "") + (result.stderr or "")
    return result.returncode, output.strip()


def tail(text: str, limit: int = 12) -> str:
    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) <= limit:
        return text
    return "\n".join(lines[:4] + ["      ..."] + lines[-limit:])


def main() -> int:
    parser = argparse.ArgumentParser(description="red-book-skills-patch 一键体检")
    parser.add_argument("--quick", action="store_true", help="跳过回归测试")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    options = parser.parse_args()

    steps: list[dict] = []

    def add(name: str, level: str, code: int, output: str) -> None:
        """level: block（失败即阻断）/ warn（失败仅警告）/ fix（自愈步骤）。"""
        if level == "fix":
            ok = code == 0
        else:
            ok = code == 0
        steps.append({"step": name, "level": level, "exit": code, "ok": ok, "output": output})

    # 0. 自愈：清掉覆盖层生成物 —— 这是历史最频繁的假故障源
    code, out = run_step([sys.executable, str(APPLY), "clean"])
    add("clean(覆盖层生成物)", "fix", code, out)

    # 1. 环境与变量自检（缺失仅警告，不阻断 —— 门禁与业务运行仍可继续）
    code, out = run_step([sys.executable, str(TOOLS / "check_env.py")])
    add("check_env", "warn", code, out)

    # 2. 启用门禁：应用覆盖层 + 契约自检
    code, out = run_step([sys.executable, str(TOOLS / "ensure_compatible.py"), "--refresh"])
    add("ensure_compatible", "block", code, out)

    # 3. 上游同步后自检（未吸收改动只警告）
    code, out = run_step([sys.executable, str(TOOLS / "post_sync_check.py")])
    add("post_sync_check", "block", code, out)

    # 4. patch 版本 / 登记一致性
    code, out = run_step([sys.executable, str(TOOLS / "check_patch_versions.py")])
    add("check_patch_versions", "block", code, out)

    # 5. 文档分层与关键锚点
    code, out = run_step([sys.executable, str(TOOLS / "check_doc_layers.py")])
    add("check_doc_layers", "block", code, out)

    # 6. 回归测试
    if not options.quick:
        code, out = run_step(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"],
            timeout=600,
        )
        add("unittest", "block", code, out)

    # 7. 敏感信息门禁
    code, out = run_step([sys.executable, str(TOOLS / "check_public_release.py"), "--quiet"])
    add("check_public_release", "block", code, out)

    # 8. 交接卡（HANDOVER.md）存在性与关键锚点
    #    全量替换包通常不含该文件；缺失时只告警不阻断发布，但必须人工补回，
    #    否则接手方拿不到「本地定制清单 / 全量替换口径 / 升级记录表」。
    handover = ROOT / "HANDOVER.md"
    if handover.exists():
        text = handover.read_text(encoding="utf-8", errors="replace")
        missing = [a for a in ("全量替换包", "本地定制清单", "升级记录表") if a not in text]
        if missing:
            add("check_handover", "warn", EXIT_FAIL,
                "HANDOVER.md 存在但缺锚点：" + "、".join(missing))
        else:
            add("check_handover", "warn", EXIT_OK, "HANDOVER.md 存在，3 个锚点齐全")
    else:
        add("check_handover", "warn", EXIT_FAIL,
            "缺失 HANDOVER.md —— 全量替换包通常不含，请从 "
            "C:/xhs/_skill-backup/snapshots/ 或 _upgrade_1106 副本补回")

    # 9. 交接基线（HANDOVER_BASELINE.md）与实物是否一致
    #    交接卡写的是散文，改文件忘改卡就会两端各说各话；这一步把「记录=实物」变成可执行判据。
    #    差异只告警不阻断：正文改动频繁，重跑 gen_handover_baseline.py 即可，不该拦住发布。
    code, out = run_step([sys.executable, str(TOOLS / "gen_handover_baseline.py"), "--check"])
    add("check_baseline", "warn", code, tail(out, 8))

    blocked = [s for s in steps if not s["ok"] and s["level"] in ("block", "fix")]
    warned = [s for s in steps if not s["ok"] and s["level"] == "warn"]
    fixed = [s for s in steps if s["level"] == "fix"]

    if options.json:
        print(json.dumps({
            "ok": not blocked,
            "blocked": [s["step"] for s in blocked],
            "warned": [s["step"] for s in warned],
            "steps": steps,
        }, ensure_ascii=False, indent=2))
        return EXIT_FAIL if blocked else (EXIT_WARN if warned else EXIT_OK)

    print("=" * 62)
    print("red-book-skills-patch 体检")
    print("=" * 62)
    for step in steps:
        if step["ok"]:
            mark = "OK  "
        elif step["level"] == "warn":
            mark = "WARN"
        else:
            mark = "FAIL"
        print(f"  [{mark}] {step['step']}")
        if not step["ok"]:
            print("        " + tail(step["output"]).replace("\n", "\n        "))
    print()

    if blocked:
        print(f"结论：!! {len(blocked)} 项阻断（{', '.join(s['step'] for s in blocked)}）"
              " —— 先处理再发布")
        return EXIT_FAIL
    if warned:
        print(f"结论：有 {len(warned)} 项警告，不阻断发布，但要记账")
        return EXIT_WARN
    print(f"结论：OK 全部通过（{len(steps)} 步，含 {len(fixed)} 步自愈）")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
