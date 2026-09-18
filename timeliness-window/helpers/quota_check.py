"""选题配额闸门 —— 某些高频、易刷屏的选题每天限发篇数。

当前硬配额：
  **恶劣天气类（含台风影响 / 预警 / 热带系统），每自然日限 1 篇；
  当日涉及红色或黑色预警时，放宽至 3 篇。**

  - 「每自然日至多 1 篇」为用户 2026-09-11 要求；
  - 「红色 / 黑色预警放宽到 3 篇」为用户 2026-09-15 要求，
    **仅在传入的预警级别为红 / 黑色时生效**，蓝 / 黄 / 橙 / 未指定一律仍按 1 篇计。

为什么单独成脚本：配额是"跨篇"约束，单篇预检看不出来；
一旦当天已经发了上限篇数，再发即使时效、资格、用词、封面全过也必须压住。

用法：
  quota_check.py --kind weather                        # 默认 1 篇
  quota_check.py --kind weather --level 红              # 红/黑色 → 3 篇
  quota_check.py --kind weather --level black          # 支持 black / 黑色 / 黑
  quota_check.py --kind weather --level 橙色            # 非红非黑 → 仍 1 篇
  quota_check.py --kind typhoon --level red            # typhoon 是 weather 的别名，同一套配额
  quota_check.py --kind weather --date 2026-09-15
  quota_check.py --kind weather --json
  quota_check.py --kind weather --add --title "标题"    # 预占配额（发布前登记，可选）

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

# 恶劣天气 / 台风影响 —— 合并为一个配额池（"预警"本身也是天气影响内容，不拆类计数）
_WEATHER_SPEC = {
    "label": "恶劣天气（含台风影响）",
    "limit": 1,          # 蓝 / 黄 / 橙 / 未指定
    "limit_high": 3,     # 红色 / 黑色预警
    "level_sensitive": True,
    "keywords": [
        # —— 热带系统 ——
        "台风", "热带低压", "热带风暴", "强热带风暴", "超强台风",
        "热带扰动", "南海扰动", "风暴潮",
        # —— 灾害类型 ——
        "暴雨", "强降水", "强对流", "雷暴", "雷雨大风", "冰雹",
        "高温", "寒潮", "低温", "大风", "大雾", "霾", "内涝",
        # —— 通用 ——
        "预警",
    ],
}

KINDS = {
    "weather": _WEATHER_SPEC,
    "typhoon": _WEATHER_SPEC,   # 别名：台风影响与恶劣天气共用同一配额池
}
GLOBAL_LIMIT = 1  # 默认每类每天 1 篇


def _norm(level):
    """级别归一化：红色→红、black→黑、RED→红。"""
    s = str(level or "").strip().lower()
    if s in {"红", "红色", "red", "r"}:
        return "红"
    if s in {"黑", "黑色", "black", "b"}:
        return "黑"
    for canon in ("红", "黑"):
        if s.startswith(canon):
            return canon
    if s.startswith("red"):
        return "红"
    if s.startswith("black"):
        return "黑"
    return s


def effective_limit(spec, level, override=None):
    """算出当日有效上限，并返回 (limit, tier) —— tier 用于打印口径来源。"""
    base = override if override is not None else spec.get("limit", GLOBAL_LIMIT)
    if level and spec.get("level_sensitive"):
        norm = _norm(level)
        if norm in {"红", "黑"}:
            return spec.get("limit_high", base), f"红/黑色预警 → 放宽至 {spec.get('limit_high', base)} 篇"
    return base, f"{spec.get('label', '')}常规 → {base} 篇"


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
    ap.add_argument("--kind", default="weather", choices=sorted(KINDS.keys()))
    ap.add_argument("--level", default=None,
                    help="本条稿件对应的预警级别（红/黑/橙/黄/蓝）；红或黑时上限放宽至 3 篇")
    ap.add_argument("--date", default=None, help="YYYY-MM-DD，默认今天")
    ap.add_argument("--limit", type=int, default=None, help="手工覆盖上限（优先于级别推算）")
    ap.add_argument("--keywords", default=None, help="自定义关键词，逗号分隔")
    ap.add_argument("--log", default=LOG_PATH)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    spec = KINDS[args.kind]
    keywords = ([k.strip() for k in args.keywords.split(",") if k.strip()]
                if args.keywords else spec["keywords"])
    limit, tier = effective_limit(spec, args.level, args.limit)
    date_str = args.date or datetime.now().strftime("%Y-%m-%d")

    level_norm = _norm(args.level) if args.level else ""

    hits = count_on(date_str, keywords, args.log)
    used = len(hits)
    ok = used < limit

    if args.json:
        print(json.dumps({
            "kind": args.kind,
            "label": spec["label"],
            "date": date_str,
            "level": level_norm or None,
            "tier": tier,
            "used": used,
            "limit": limit,
            "allow": ok,
            "hits": [{"ts": h.get("ts"), "title": h.get("title"),
                      "note_id": h.get("note_id")} for h in hits],
        }, ensure_ascii=False))
    else:
        lv = f"（级别：{level_norm}）" if level_norm else "（未指定级别 → 按常规上限）"
        print(f"[quota] {date_str} 「{spec['label']}」已发 {used}/{limit} 篇{lv}")
        print(f"[quota] 口径：{tier}")
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
