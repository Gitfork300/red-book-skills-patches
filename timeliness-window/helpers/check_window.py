#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""时效窗口 + 可发布资格 预检：判断一个展会/活动是否该发布。

窗口规则（patch: timeliness-window）
- 合格 A「正在举行/即将开幕」：开幕日落在 [今天, 今天+7]，且未结束
- 合格 B「报名窗口内」：报名截止日落在 [今天, 今天+7]
- 不合格 C「太早」：开幕日 > 今天+7 且（无报名截止 或 报名截止 > 今天+7）
- 不合格 D「已过期」：已闭幕，或报名截止 < 今天

资格规则（同 patch，2026-09-11 新增）
- 展会/活动类必须同时确认两件事：`--live` 是否有线上直播、`--public-signup` 普通观众能否报名
- **无直播 且 普通观众无法报名 → 不得发布**（读者既去不了也看不了）
- 有直播 → 可发布，但文案必须写明直播信息（平台 / 时间 / 是否需预约）
- 两参数都不传时只做时效判定，行为与旧版一致

退出码：0 = 可发布；1 = 时效不合格；2 = 参数错误；3 = 资格不合格

用法：
  python check_window.py --start 2026-09-12 --end 2026-09-14
  python check_window.py --start 2026-10-12 --deadline 2026-09-20
  python check_window.py --deadline 2026-09-15
  python check_window.py --start 2026-09-15 --live no  --public-signup yes   # 可发（能报名）
  python check_window.py --start 2026-09-12 --live no  --public-signup no    # 不得发布
  python check_window.py --start 2026-09-18 --live yes --public-signup no    # 可发（有直播，须提示）
  python check_window.py --start 2026-10-12 --json
"""

import argparse
import datetime as dt
import json
import sys

WINDOW_DAYS = 7


def _parse(s):
    if not s:
        return None
    s = s.strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"):
        try:
            return dt.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise SystemExit(f"[ERROR] 无法解析日期: {s}（应为 YYYY-MM-DD）")


def judge(start=None, end=None, deadline=None, today=None, window=WINDOW_DAYS,
          live=None, public_signup=None):
    """返回 (ok: bool, verdict: str, detail: str, gap: int|None)

    live / public_signup: True = 有直播 / 普通观众可报名，False = 无，None = 未提供
    """
    today = today or dt.date.today()
    limit = today + dt.timedelta(days=window)

    if end and end < today:
        return False, "EXPIRED", f"已于 {end} 闭幕（{(today - end).days} 天前）", (today - end).days
    if deadline and deadline < today:
        return False, "EXPIRED", f"报名已于 {deadline} 截止（{(today - deadline).days} 天前）", (today - deadline).days

    if start and end and start <= today <= end:
        left = (end - today).days
        return True, "ONGOING", f"正在举行，还剩 {left} 天（至 {end}）", 0
    if start and not end and start <= today:
        return True, "ONGOING", f"已于 {start} 开始，仍在窗口内", 0

    if start and today < start <= limit:
        d = (start - today).days
        return True, "OPENING_SOON", f"{d} 天后开幕（{start}）", d

    if deadline and today <= deadline <= limit:
        d = (deadline - today).days
        return True, "DEADLINE_SOON", f"报名还剩 {d} 天截止（{deadline}）", d

    if deadline and deadline > limit:
        d = (deadline - today).days
        return False, "TOO_EARLY", f"报名截止 {deadline}，距今 {d} 天，超出 7 天窗口", d

    if start:
        d = (start - today).days
        return False, "TOO_EARLY", f"开幕 {start}，距今 {d} 天，超出 7 天窗口", d

    return False, "NO_DATA", "未给出开幕日或报名截止日，无法判断", None


def judge_eligibility(live, public_signup):
    """发布资格判定（直播 / 报名门槛）。

    返回 (eligible: bool, verdict: str, detail: str, hint: str|None)
    """
    if live is False and public_signup is False:
        return (
            False, "NOT_ELIGIBLE",
            "既无线上直播，普通观众也无法自行报名（仅限邀约/特定从业者/闭门）",
            "读者既去不了也看不了 → 不写不发；如属远期可登记进待发池",
        )
    if live is True:
        return (
            True, "ELIGIBLE_LIVE",
            "有线上直播，普通观众可在线观看",
            "文案必须写明直播信息：观看平台、直播时间、是否需要预约（有回放也要注明）",
        )
    if public_signup is True:
        return (
            True, "ELIGIBLE_SIGNUP",
            "无直播但普通观众可自行报名参与",
            None,
        )
    # 任一未知 → 不足以判定可发布，要求先核实
    unknown = []
    if live is None:
        unknown.append("是否有线上直播")
    if public_signup is None:
        unknown.append("普通观众能否报名")
    return (
        False, "UNKNOWN",
        "以下信息未核实：" + "、".join(unknown),
        "展会/活动类必须先把这两项核实清楚再动笔；不确定按不可发布处理",
    )


def _tri(v):
    """yes→True / no→False / unknown|None→None"""
    if v is None or v == "unknown":
        return None
    return v == "yes"


def main():
    ap = argparse.ArgumentParser(description="展会时效窗口 + 可发布资格 预检")
    ap.add_argument("--start", help="开幕日期 YYYY-MM-DD")
    ap.add_argument("--end", help="闭幕日期 YYYY-MM-DD")
    ap.add_argument("--deadline", help="报名截止日期 YYYY-MM-DD")
    ap.add_argument("--live", choices=["yes", "no", "unknown"],
                    help="是否有线上直播（展会/活动类必填）")
    ap.add_argument("--public-signup", choices=["yes", "no", "unknown"],
                    help="普通观众能否自行报名参与（展会/活动类必填）")
    ap.add_argument("--today", help="基准日期，默认今天（测试用）")
    ap.add_argument("--window", type=int, default=WINDOW_DAYS, help=f"窗口天数，默认 {WINDOW_DAYS}")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    a = ap.parse_args()

    need_eligibility = a.live is not None or a.public_signup is not None
    if not (a.start or a.deadline):
        print("[ERROR] 至少需要提供 --start 或 --deadline", file=sys.stderr)
        return 2

    start, end, deadline, today = (
        _parse(a.start), _parse(a.end), _parse(a.deadline), _parse(a.today),
    )
    ok, verdict, detail, gap = judge(start, end, deadline, today, a.window)

    elig_ok, elig_verdict, elig_detail, elig_hint = True, None, None, None
    if need_eligibility:
        elig_ok, elig_verdict, elig_detail, elig_hint = judge_eligibility(
            _tri(a.live), _tri(a.public_signup)
        )

    final_ok = ok and elig_ok

    if a.json:
        print(json.dumps({
            "ok": final_ok,
            "window_ok": ok, "verdict": verdict, "detail": detail, "gap_days": gap,
            "eligibility_ok": elig_ok, "eligibility_verdict": elig_verdict,
            "eligibility_detail": elig_detail, "eligibility_hint": elig_hint,
            "start": str(start) if start else None,
            "end": str(end) if end else None,
            "deadline": str(deadline) if deadline else None,
            "today": str(today or dt.date.today()),
            "window_days": a.window,
        }, ensure_ascii=False, indent=2))
    else:
        mark = "PASS 可发布" if ok else "BLOCK 不得发布"
        print(f"[{mark}] {verdict} — {detail}")
        if not ok and verdict == "TOO_EARLY":
            target = deadline or start
            earliest = target - dt.timedelta(days=a.window)
            kind = "报名截止" if deadline else "开幕"
            print(f"  建议：{kind}日 {target}，最早 {earliest} 起进入窗口，届时再写稿发布")
        if need_eligibility:
            emark = "PASS 资格通过" if elig_ok else "BLOCK 资格不通过"
            print(f"[{emark}] {elig_verdict} — {elig_detail}")
            if elig_hint:
                print(f"  {'提示' if elig_ok else '建议'}：{elig_hint}")
        if final_ok:
            print("[OK] 时效与资格均通过，可进入写稿流程")
        else:
            print("[STOP] 本活动不得发布")

    if not ok:
        return 1
    if not elig_ok:
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
