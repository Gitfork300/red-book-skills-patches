#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""小红书风控守卫 —— 预算 / 冷却 / 连续失败熔断（状态落盘）。

为什么需要
----------
2026-09-12 实测：连续访问约 30 个公开页后，平台把后续请求**一律重定向到登录页**。
当时的 `read_note_body.py` 没有任何额度概念，硬撞 27 次无效请求才跑完，
而每次无效请求都在**加重风控**。规则写在文档里没用，得让脚本自己停。

本模块把"每个操作域能跑多少、撞墙后多久不能跑"变成可查询、可记录的状态。

用法（CLI）
-----------
    python risk_state.py status                              # 全部域
    python risk_state.py check  --kind read-body             # 0可跑/3冷却中/4状态损坏
    python risk_state.py record --kind read-body --ok 24 --fail 3 --stopped consecutive-fail
    python risk_state.py reset  --kind read-body             # 显式解除本地冷却
    python risk_state.py paths                                # 打印状态文件位置

用法（模块）
-----------
    import risk_state
    ok, why = risk_state.can_start("read-body")
    limit = risk_state.budget("read-body")
    if risk_state.should_stop("read-body", consecutive_fail): break
    risk_state.record("read-body", ok=24, fail=3, stopped="consecutive-fail")

退出码：0 = 可跑 / 3 = 冷却中 / 4 = 状态文件损坏（保守起见按不可跑处理）
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
PATCH_ROOT = os.path.normpath(os.path.join(HERE, ".."))
STATE_DIR = os.path.join(PATCH_ROOT, "state")
STATE_FILE = os.path.join(STATE_DIR, "risk_state.json")

TS_FMT = "%Y-%m-%d %H:%M"
MAX_RUNS = 10  # 每个域只保留最近 N 次会话记录

# ── 内置额度（改这里就是改全局）────────────────────────────────────────────
# budget            单次会话上限（0 = 不限）
# cooldown_hours    被熔断/限流后，多久内不允许再开新会话（0 = 不冷却）
# stop_consecutive  连续失败达到几次就熔断（0 = 不熔断）
KINDS: dict[str, dict] = {
    "read-body": {
        "budget": 25,
        "cooldown_hours": 4,
        "stop_consecutive": 3,
        "desc": "公开页读正文（read_note_body.py）—— 约 30 篇触限流，留余量取 25",
    },
    "list-notes": {
        "budget": 0,
        "cooldown_hours": 0,
        "stop_consecutive": 0,
        "desc": "创作者中心全量清单（list_all_notes.py）—— 走签名接口，配额宽松",
    },
    "publish": {
        "budget": 0,
        "cooldown_hours": 0,
        "stop_consecutive": 0,
        "desc": "发布 —— 频率由 publish-interval-guard 管（≥8 分钟/篇）",
    },
}


# ── 配置读取 ────────────────────────────────────────────────────────────
def spec(kind: str) -> dict:
    if kind not in KINDS:
        raise KeyError(f"未知的操作域 {kind!r}；可选：{', '.join(KINDS)}")
    return KINDS[kind]


def budget(kind: str) -> int:
    """单次会话上限；0 表示不限。"""
    return int(spec(kind).get("budget", 0))


def cooldown_hours(kind: str) -> float:
    return float(spec(kind).get("cooldown_hours", 0))


def stop_after_consecutive_fail(kind: str) -> int:
    return int(spec(kind).get("stop_consecutive", 0))


# ── 状态读写 ────────────────────────────────────────────────────────────
def _load() -> dict:
    """读状态；文件缺失返回空状态；损坏时抛 ValueError。"""
    if not os.path.isfile(STATE_FILE):
        return {"version": 1, "kinds": {}}
    with open(STATE_FILE, encoding="utf-8") as fh:
        raw = fh.read().strip()
    if not raw:
        return {"version": 1, "kinds": {}}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"状态文件损坏：{STATE_FILE}（{exc}）") from exc
    if not isinstance(data, dict):
        raise ValueError(f"状态文件格式异常：{STATE_FILE}")
    data.setdefault("version", 1)
    data.setdefault("kinds", {})
    return data


def _save(data: dict) -> None:
    os.makedirs(STATE_DIR, exist_ok=True)
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, STATE_FILE)


def _parse_ts(s: str) -> datetime | None:
    try:
        return datetime.strptime(s.strip(), TS_FMT)
    except Exception:  # noqa: BLE001
        return None


# ── 核心 API ────────────────────────────────────────────────────────────
def can_start(kind: str, now: datetime | None = None) -> tuple[bool, str]:
    """现在能不能开一次新会话。返回 (可否, 原因)。

    只看**本地冷却记忆**，不会真的去探平台 —— 冷却期内开跑等于自欺。
    """
    spec(kind)  # 校验 kind
    now = now or datetime.now()
    hours = cooldown_hours(kind)
    if hours <= 0:
        return True, "无冷却限制"

    try:
        data = _load()
    except ValueError as exc:
        return False, f"状态文件不可读，保守起见按不可跑处理：{exc}"

    entry = data.get("kinds", {}).get(kind) or {}
    last_stop = _parse_ts(str(entry.get("last_stop_at") or ""))
    if not last_stop:
        return True, "无熔断记录，可跑"

    elapsed = now - last_stop
    remain = timedelta(hours=hours) - elapsed
    if remain.total_seconds() <= 0:
        return True, f"冷却已过（上次熔断于 {entry.get('last_stop_at')}，已 {elapsed.total_seconds()/3600:.1f} 小时）"
    mins = int(remain.total_seconds() // 60)
    h, m = divmod(mins, 60)
    reason = (f"仍在冷却中：上次熔断于 {entry.get('last_stop_at')}"
              f"（原因 {entry.get('last_stopped') or '未知'}），还需约 {h} 小时 {m} 分钟")
    return False, reason


def should_stop(kind: str, consecutive_fail: int) -> bool:
    """循环内的熔断判据：连续失败是否已达阈值。"""
    n = stop_after_consecutive_fail(kind)
    return n > 0 and consecutive_fail >= n


def record(kind: str, ok: int = 0, fail: int = 0, stopped: str = "",
           total: int | None = None) -> str:
    """记录一次会话结果。

    `stopped` 非空（如 `consecutive-fail` / `quota-blocked`）时，会写入
    `last_stop_at` 触发冷却 —— 这是"今天别再撞了"的记忆。
    """
    spec(kind)
    try:
        data = _load()
    except ValueError:
        data = {"version": 1, "kinds": {}}

    entry = data["kinds"].setdefault(kind, {})
    now_ts = datetime.now().strftime(TS_FMT)

    run = {"at": now_ts, "ok": int(ok), "fail": int(fail), "stopped": stopped or ""}
    if total is not None:
        run["total"] = int(total)
    entry.setdefault("runs", []).append(run)
    entry["runs"] = entry["runs"][-MAX_RUNS:]
    entry["last_at"] = now_ts
    if stopped:
        entry["last_stop_at"] = now_ts
        entry["last_stopped"] = stopped

    _save(data)
    return f"已记录 {kind}：ok={ok} fail={fail} stopped={stopped or '-'}"


def reset(kind: str | None = None, all_kinds: bool = False) -> str:
    """清除本地冷却记忆。**不会**让平台真的解除限流 —— 没证据就别 reset。"""
    try:
        data = _load()
    except ValueError:
        data = {"version": 1, "kinds": {}}

    if all_kinds or not kind:
        for entry in data.get("kinds", {}).values():
            entry.pop("last_stop_at", None)
            entry.pop("last_stopped", None)
        _save(data)
        return "已清除全部域的冷却记忆"

    spec(kind)
    entry = data["kinds"].setdefault(kind, {})
    entry.pop("last_stop_at", None)
    entry.pop("last_stopped", None)
    _save(data)
    return f"已清除 {kind} 的冷却记忆"


# ── CLI ─────────────────────────────────────────────────────────────────
def _print_status() -> int:
    try:
        data = _load()
    except ValueError as exc:
        print(f"[risk] !! {exc}", file=sys.stderr)
        return 4

    print(f"[risk] 状态文件：{STATE_FILE}")
    print(f"{'kind':12s} {'预算':>6s} {'冷却(h)':>8s} {'熔断':>5s}  最近会话")
    for kind, sp in KINDS.items():
        entry = data.get("kinds", {}).get(kind) or {}
        runs = entry.get("runs") or []
        last = runs[-1] if runs else None
        if last:
            tail = (f"{last['at']}  ok={last['ok']} fail={last['fail']}"
                    f"{'  stopped=' + last['stopped'] if last.get('stopped') else ''}")
        else:
            tail = "（无记录）"
        b = sp.get("budget", 0)
        print(f"{kind:12s} {('不限' if not b else str(b)):>6s} "
              f"{sp.get('cooldown_hours', 0):>8g} "
              f"{sp.get('stop_consecutive', 0):>5d}  {tail}")
    print()
    for kind in KINDS:
        ok, why = can_start(kind)
        print(f"  {'✅' if ok else '⛔'} {kind:12s} {why}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="小红书风控守卫（预算/冷却/熔断）")
    sub = ap.add_subparsers(dest="cmd")

    p_chk = sub.add_parser("check", help="现在能不能开新会话")
    p_chk.add_argument("--kind", required=True, choices=sorted(KINDS))

    p_rec = sub.add_parser("record", help="记录一次会话结果")
    p_rec.add_argument("--kind", required=True, choices=sorted(KINDS))
    p_rec.add_argument("--ok", type=int, default=0)
    p_rec.add_argument("--fail", type=int, default=0)
    p_rec.add_argument("--total", type=int, default=None)
    p_rec.add_argument("--stopped", default="", help="停止原因，如 consecutive-fail / quota-blocked")

    p_rst = sub.add_parser("reset", help="清除本地冷却记忆")
    p_rst.add_argument("--kind", choices=sorted(KINDS))
    p_rst.add_argument("--all", action="store_true")

    sub.add_parser("status", help="全部域状态")
    sub.add_parser("paths", help="打印状态文件位置")

    args = ap.parse_args()

    if args.cmd == "check":
        ok, why = can_start(args.kind)
        print(f"[risk] {'✅ 可跑' if ok else '⛔ 不可跑'} —— {why}")
        return 0 if ok else 3
    if args.cmd == "record":
        print("[risk] " + record(args.kind, args.ok, args.fail, args.stopped, args.total))
        return 0
    if args.cmd == "reset":
        print("[risk] " + reset(args.kind, args.all))
        return 0
    if args.cmd == "paths":
        print(STATE_FILE)
        return 0

    return _print_status()


if __name__ == "__main__":
    sys.exit(main())
