"""漏发复核看门狗 —— 发布流程运行期间，每 30 分钟自动跑一次漏发复核。

与 check_missing.py 的分工：
  - check_missing.py：跑一次，出结论（一次性）
  - watch_missing.py：循环跑，直到「发现漏发」或「流程结束」才退出

为什么要它：批量发布是长流程，中途失败是静默的。agent 一边等间隔一边盯盘
容易漏；把 30 分钟一次的复核交给循环脚本，agent 只在它退出时被叫醒，
拿到的要么是"流程正常结束"，要么是"有漏发需要处置"，不会两头空。

用法：
  watch_missing.py                       # 默认每 1800 秒一次，最长守 8 小时
  watch_missing.py --interval 1800 --max-hours 6
  watch_missing.py --keys ex0911_4,hk0911a_1,hk0911a_2 --verify

退出码：
  0 = 流程已结束且无漏发
  3 = 发现漏发，需要 agent 介入（重新预检 → 改稿 → 补发）
  4 = 达到 max-hours 上限仍未结束（可重开一次继续守）

环境变量：
  XHS_FLOW_LOCK  队列锁文件路径（存在且 pid 活着 = 流程在跑），
                 默认 <workspace>/_xhs_publish.lock
"""
import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
PATCH_ROOT = os.path.normpath(os.path.join(HERE, ".."))
CHECK = os.path.join(HERE, "check_missing.py")
INFLIGHT = os.path.join(PATCH_ROOT, "state", "inflight.json")

WS_DEFAULT = os.environ.get("XHS_WORKSPACE") or os.path.expanduser("~/Documents/workbuddy-skill")
FLOW_LOCK = os.environ.get("XHS_FLOW_LOCK") or os.path.join(WS_DEFAULT, "_xhs_publish.lock")


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _inflight_keys():
    try:
        with open(INFLIGHT, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []
    if isinstance(data, dict):
        vals = data.get("keys") or data.get("items") or []
    elif isinstance(data, list):
        vals = data
    else:
        vals = []
    return [str(v) for v in vals if v]


def _pid_alive(pid):
    try:
        r = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=30)
    except Exception:
        return False
    return str(pid) in (r.stdout or "")


def flow_active():
    """流程在跑的判据：inflight 非空，或队列锁存在且持有者仍活着。"""
    if _inflight_keys():
        return True
    if os.path.exists(FLOW_LOCK):
        try:
            pid = int(open(FLOW_LOCK, encoding="utf-8").read().strip())
        except Exception:
            pid = -1
        if pid > 0 and _pid_alive(pid):
            return True
    return False


def run_check(args):
    cmd = [sys.executable, CHECK]
    if args.keys:
        cmd += ["--keys", args.keys]
    if args.scan:
        cmd += ["--scan", args.scan]
    if args.verify:
        cmd += ["--verify"]
    r = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main():
    ap = argparse.ArgumentParser(description="漏发复核看门狗（每 30 分钟一次）")
    ap.add_argument("--interval", type=int, default=1800, help="复核间隔秒数，默认 1800")
    ap.add_argument("--max-hours", type=float, default=8.0)
    ap.add_argument("--keys", default="")
    ap.add_argument("--scan", default="")
    ap.add_argument("--verify", action="store_true")
    args = ap.parse_args()

    deadline = time.time() + args.max_hours * 3600
    round_no = 0
    next_at = time.time()  # 先立刻跑一次基线

    while True:
        now = time.time()
        if now >= next_at:
            round_no += 1
            rc, out = run_check(args)
            print(f"\n=== [watch #{round_no}] {_now()} check_missing rc={rc} ===", flush=True)
            print(out.rstrip(), flush=True)
            if rc == 1:
                print(f"\n[watch] ALERT_MISSING 发现漏发，需处置（{_now()}）", flush=True)
                print("[watch] 处置：重新走完整预检（时效/资格/用词/字数/封面）→ "
                      "改稿合规 → 按 8~12 分钟随机间隔补发；不合规进待发池", flush=True)
                return 3
            if rc not in (0, 2):
                print(f"[watch] 复核异常 rc={rc}，继续等待下一轮", flush=True)
            next_at = time.time() + args.interval

        if not flow_active():
            # 收尾前再复核一次：最后一次定时复核可能发生在最后一篇发布之前
            print(f"\n[watch] 流程已结束，补跑收尾复核（{_now()}）", flush=True)
            rc, out = run_check(args)
            print(out.rstrip(), flush=True)
            if rc == 1:
                print(f"\n[watch] ALERT_MISSING 收尾复核发现漏发，需处置（{_now()}）", flush=True)
                return 3
            print(f"\n[watch] FLOW_IDLE 发布流程已结束，无漏发（{_now()}）", flush=True)
            return 0
        if time.time() >= deadline:
            print(f"\n[watch] TIMEOUT 已达 max-hours={args.max_hours}（{_now()}）", flush=True)
            return 4

        # 每 60 秒醒一次：既能按时复核，也能在流程结束时立刻退出
        time.sleep(min(60, max(5, next_at - time.time())))


if __name__ == "__main__":
    sys.exit(main())
