"""发布间隔守卫 —— 连续两篇笔记之间必须间隔 8~12 分钟（随机，默认区间）。

为什么要独立成脚本：间隔判断依赖"上一次成功发布"的真实时间戳，
而 agent 自身的会话时间感不可靠（跨调用、上下文压缩、长任务等待都会失真）。
把时间戳落盘，由脚本裁定，才不会凭印象提前发。

为什么要随机：固定 10 分钟这种"整齐"的节奏本身就是机器特征。
每次发布后在 [480, 720] 秒之间抽一个目标间隔（8~12 分钟），
落在记录里（next_gap），由脚本锁定，避免反复 check 时抖动。

存储位置：本 patch 自己的 state/ 目录（不依赖主 skill 的 tmp/）。
这样未来重装主 skill、迁移 patch、跨机器同步都不会丢记录。

用法：
  check                     距上次发布是否已满足本次目标间隔；exit 0 = 可发布，exit 1 = 需等待
  check --json              同上，输出机器可读结果
  wait                      阻塞等待到可发布；exit 0 = 可发布，exit 1 = 仍未满足（超出 max-block）
  wait --max-block 900      最长阻塞秒数，默认 900
  record --title "标题"      记录一次"已审核的成功发布"（仅在 publish 成功、且 verify-note 审核确认 found:true 之后调用）
  record --note-id ID --title "标题"
  reset                     清空发布记录
  last                      查看上次发布时间、本次目标间隔与还需等待的秒数

间隔参数：
  --interval-min N   随机下界，默认 480（8 分钟）
  --interval-max N   随机上界，默认 720（12 分钟）
  --interval N       固定间隔（覆盖随机），用于特殊场景/回放
  --seed N           指定随机种子（仅调试/自测，正式发布不要用）

环境变量（优先级低于命令行）：
  XHS_INTERVAL_MIN / XHS_INTERVAL_MAX / XHS_INTERVAL

与编排层集成：
  通过环境变量 XHS_INTERVAL_GUARD 指向本脚本，xhs_login_wait.py 会自动调用 wait/record。
  直接调用本脚本时，存储路径取决于 <patch>/state/publish_log.json。
"""
import argparse
import json
import os
import random
import sys
import time
from datetime import datetime

PATCH_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
LOG = os.path.join(PATCH_ROOT, "state", "publish_log.json")

DEFAULT_MIN = 480          # 8 分钟
DEFAULT_MAX = 720          # 12 分钟
DEFAULT_MAX_BLOCK = 900


def _env_int(name, fallback):
    raw = os.environ.get(name)
    if raw is None or str(raw).strip() == "":
        return fallback
    try:
        return int(float(str(raw).strip()))
    except Exception:
        return fallback


def _load():
    if not os.path.exists(LOG):
        return []
    try:
        with open(LOG, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []
    return data if isinstance(data, list) else []


def _save(records):
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "w", encoding="utf-8") as f:
        json.dump(records[-100:], f, ensure_ascii=False, indent=2)


def last_record():
    rs = _load()
    if not rs:
        return None
    return max(rs, key=lambda r: r.get("epoch", 0))


def _draw(min_sec, max_sec, rng, fixed=None):
    if fixed is not None:
        return int(fixed)
    lo, hi = min_sec, max_sec
    if lo > hi:
        lo, hi = hi, lo
    if hi <= lo:
        return int(lo)
    return rng.randint(int(lo), int(hi))


def ensure_next_gap(min_sec, max_sec, rng, fixed=None):
    """确保"上一条记录"带有本次要等待的目标间隔 next_gap。

    旧版本记录没有该字段；首次遇到时补一个随机值并落盘，
    这样后续每次 check/wait 读到的目标都是同一个数，不会来回抖动。
    """
    rs = _load()
    if not rs:
        return None
    last = max(rs, key=lambda r: r.get("epoch", 0))
    gap = last.get("next_gap")
    if not isinstance(gap, (int, float)) or gap <= 0:
        gap = _draw(min_sec, max_sec, rng, fixed)
        last["next_gap"] = int(gap)
        # 兼容 fixed 模式：目标间隔即会被写成固定值
        _save(rs)
    return int(gap)


def remaining(target):
    r = last_record()
    if r is None or target is None:
        return 0.0
    return max(0.0, target - (time.time() - r.get("epoch", 0)))


def _fmt(ts):
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


def _human(sec):
    sec = int(round(sec))
    if sec >= 60:
        return f"{sec // 60} 分 {sec % 60} 秒"
    return f"{sec} 秒"


def _resolve(args):
    min_sec = args.interval_min if args.interval_min is not None else _env_int("XHS_INTERVAL_MIN", DEFAULT_MIN)
    max_sec = args.interval_max if args.interval_max is not None else _env_int("XHS_INTERVAL_MAX", DEFAULT_MAX)
    if min_sec > max_sec:
        min_sec, max_sec = max_sec, min_sec
    fixed = args.interval if args.interval is not None else _env_int("XHS_INTERVAL", None)
    if fixed is not None and fixed <= 0:
        fixed = None
    rng = random.Random(args.seed) if args.seed is not None else random.Random()

    def draw():
        return _draw(min_sec, max_sec, rng, fixed)

    return min_sec, max_sec, fixed, rng, draw


def cmd_check(args):
    min_sec, max_sec, fixed, rng, draw = _resolve(args)
    target = ensure_next_gap(min_sec, max_sec, rng, fixed)
    left = remaining(target)
    r = last_record()
    if args.json:
        print(json.dumps({
            "ready": left <= 0,
            "remaining_sec": round(left),
            "target_gap_sec": target,
            "interval_min_sec": min_sec,
            "interval_max_sec": max_sec,
            "mode": "fixed" if fixed is not None else "random",
            "last_publish": _fmt(r["epoch"]) if r else None,
            "last_title": r.get("title") if r else None,
        }, ensure_ascii=False))
    else:
        if r is None:
            print(f"无发布记录，可直接发布（本次目标间隔 {_human(target) if target else '—'}）")
        elif left <= 0:
            print(f"距上次发布（{_fmt(r['epoch'])}）已满足目标间隔 {_human(target)}，可发布")
        else:
            print(f"距上次发布（{_fmt(r['epoch'])}）需再等 {_human(left)}（本次目标间隔 {_human(target)}）")
    return 0 if left <= 0 else 1


def cmd_wait(args):
    min_sec, max_sec, fixed, rng, draw = _resolve(args)
    target = ensure_next_gap(min_sec, max_sec, rng, fixed)
    left = remaining(target)
    if left <= 0:
        print(f"间隔已满足（目标 {_human(target)}），可立即发布", flush=True)
        return 0

    mode = "固定" if fixed is not None else f"随机 {_human(min_sec)}~{_human(max_sec)}"
    block = min(left, args.max_block)
    if block < left:
        print(
            f"需等待 {_human(left)}，但 max-block 只有 {args.max_block} 秒；"
            f"本次最多等待 {_human(block)} 后返回未满足状态",
            flush=True,
        )

    deadline = time.time() + block
    next_report = None
    print(f"本次目标间隔 {_human(target)}（{mode}），还需等待 {_human(left)}", flush=True)
    while True:
        left = remaining(target)
        if left <= 0:
            print(f"间隔已满足（目标 {_human(target)}），可发布", flush=True)
            return 0
        if time.time() >= deadline:
            print(f"WAIT_INCOMPLETE 仍需等待 {_human(left)}", flush=True)
            return 1
        bucket = int(left) // 60
        if bucket != next_report:
            next_report = bucket
            print(f"  还需等待 {_human(left)}...", flush=True)
        # 不要睡过 deadline，否则会多等一个睡眠周期
        time.sleep(max(0.5, min(5.0, left, deadline - time.time())))


def cmd_record(args):
    min_sec, max_sec, fixed, rng, draw = _resolve(args)
    recs = _load()
    now = time.time()
    prev = max(recs, key=lambda r: r.get("epoch", 0)) if recs else None
    actual_gap = int(round(now - prev["epoch"])) if prev else None
    next_gap = draw()
    recs.append({
        "epoch": now,
        "ts": _fmt(now),
        "note_id": args.note_id,
        "title": args.title,
        "actual_gap_sec": actual_gap,
        "next_gap": next_gap,
    })
    _save(recs)
    mode = "固定" if fixed is not None else "随机"
    print(
        f"已记录发布时间 {_fmt(now)}"
        + (f"（距上一篇 {_human(actual_gap)}）" if actual_gap else "")
    )
    print(f"下一篇目标间隔：{_human(next_gap)}（{mode} {_human(min_sec)}~{_human(max_sec)}）")
    return 0


def cmd_reset(args):
    if os.path.exists(LOG):
        os.remove(LOG)
        print(f"已清空发布记录 {LOG}")
    else:
        print("无发布记录")
    return 0


def cmd_last(args):
    min_sec, max_sec, fixed, rng, draw = _resolve(args)
    r = last_record()
    if r is None:
        print("无发布记录")
        return 0
    target = ensure_next_gap(min_sec, max_sec, rng, fixed)
    left = remaining(target)
    print(f"上次发布: {r.get('ts')}")
    print(f"  标题   : {r.get('title')}")
    print(f"  note_id: {r.get('note_id')}")
    print(f"  目标间隔: {_human(target) if target else '—'}"
          + (f"（上篇实际间隔 {_human(r['actual_gap_sec'])}）" if r.get("actual_gap_sec") else ""))
    print(f"  还需等待: {_human(left) if left > 0 else '0（可发布）'}")
    return 0


def main():
    p = argparse.ArgumentParser(description="小红书连续发布间隔守卫（8~12 分钟随机）")
    p.add_argument("action", choices=["check", "wait", "record", "reset", "last"])
    p.add_argument("--interval", type=int, default=None, help="固定间隔秒数（覆盖随机）")
    p.add_argument("--interval-min", type=int, default=None, help="随机下界秒数，默认 480")
    p.add_argument("--interval-max", type=int, default=None, help="随机上界秒数，默认 720")
    p.add_argument("--max-block", type=int, default=DEFAULT_MAX_BLOCK)
    p.add_argument("--note-id", default=None)
    p.add_argument("--title", default=None)
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    return {
        "check": cmd_check,
        "wait": cmd_wait,
        "record": cmd_record,
        "reset": cmd_reset,
        "last": cmd_last,
    }[args.action](args)


if __name__ == "__main__":
    sys.exit(main())
