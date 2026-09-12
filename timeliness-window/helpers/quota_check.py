"""选题配额闸门 —— 某些高频、易刷屏的选题每天限发篇数。

当前唯一硬配额（用户 2026-09-11 要求）：
  **台风影响类，每自然日至多 1 篇**（以发布日志里的发布时间所在日期计）。

为什么单独成脚本：配额是"跨篇"约束，单篇预检看不出来；
一旦当天已经发过一篇台风，第二篇即使时效、资格、用词、封面全过也必须压住。

用法：
  quota_check.py --kind typhoon                 # 查今天台风类已发几篇
  quota_check.py --kind typhoon --date 2026-09-11
  quota_check.py --kind typhoon --limit 1 --json
  quota_check.py --kind typhoon --add --title "标题"   # 预占配额（发布前登记，可选）

退出码：
  0 = 配额未满，可以发
  1 = 配额已满，不得再发（压到明天或进待发池）
  2 = 参数错误

环境变量：
  XHS_INTERVAL_LOG  发布日志路径（默认读 publish-interval-guard 的 state/publish_log.json）
"""
import argparse
import json
import os
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
PATCH_ROOT = os.path.normpath(os.path.join(HERE, ".."))
PATCHES_ROOT = os.path.normpath(os.path.join(PATCH_ROOT, ".."))
LOG_PATH = os.environ.get("XHS_INTERVAL_LOG") or os.path.join(
    PATCHES_ROOT, "publish-interval-guard", "state", "publish_log.json"
)

KINDS = {
    "typhoon": {
        "label": "台风影响",
        "limit": 1,
        "keywords": ["台风", "热带低压", "热带风暴", "强热带风暴", "超强台风",
                     "热带扰动", "南海扰动", "风暴潮"],
    },
}
GLOBAL_LIMIT = 1  # 默认每类每天 1 篇


def _load_log(log_path):
    try:
        with open(log_path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []
    return data if isinstance(data, list) else []


def _hit(title, keywords):
    t = title or ""
    return any(k in t for k in keywords)


def count_on(date_str, keywords, log_path):
    hits = []
    for r in _load_log(log_path):
        if not isinstance(r, dict):
            continue
        ts = r.get("ts") or ""
        if not ts.startswith(date_str):
            continue
        if _hit(r.get("title"), keywords):
            hits.append(r)
    return hits


def main():
    ap = argparse.ArgumentParser(description="选题配额闸门")
    ap.add_argument("--kind", default="typhoon", choices=sorted(KINDS.keys()))
    ap.add_argument("--date", default=None, help="YYYY-MM-DD，默认今天")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--keywords", default=None, help="自定义关键词，逗号分隔")
    ap.add_argument("--log", default=LOG_PATH)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    spec = KINDS[args.kind]
    keywords = ([k.strip() for k in args.keywords.split(",") if k.strip()]
                if args.keywords else spec["keywords"])
    limit = args.limit if args.limit is not None else spec.get("limit", GLOBAL_LIMIT)
    date_str = args.date or datetime.now().strftime("%Y-%m-%d")

    hits = count_on(date_str, keywords, args.log)
    used = len(hits)
    ok = used < limit

    if args.json:
        print(json.dumps({
            "kind": args.kind,
            "label": spec["label"],
            "date": date_str,
            "used": used,
            "limit": limit,
            "allow": ok,
            "hits": [{"ts": h.get("ts"), "title": h.get("title"),
                      "note_id": h.get("note_id")} for h in hits],
        }, ensure_ascii=False))
    else:
        print(f"[quota] {date_str} 「{spec['label']}」已发 {used}/{limit} 篇")
        for h in hits:
            print(f"  - {h.get('ts')} {h.get('title')}")
        if ok:
            print(f"[quota] OK 配额未满，可发 (剩 {limit - used} 篇)")
        else:
            print(f"[quota] !! 今日「{spec['label']}」配额已满，不得再发；"
                  f"压到明天或进待发池")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
