"""近似文章限次（按**活动层级**设窗口，2026-09-16 用户原话口径 v2）。

与 `dup_check.py` 的分工
------------------------
- `dup_check.py`      → 防「**同一事件**被发两遍」（按事件标识 / 公共子串判）
- `near_dup_limit.py` → 防「**近似文章过密**」（不同事件、但层级雷同，读者看着像重复）

用户原话（2026-09-16，覆盖 v1 的 R1/R2/R3 三条推定值）：
  「重复次数限制是**近似文章在一定时间内限制重复发送**。比如国家级，行业级等」
  「**行业级 7 天内不重复，国家级 24 小时内不重复，专题不设限制**」

→ 现行规则（改脚本顶部常量即全局生效）
--------------------------------------
| 层级（新标记 / 旧 level） | 窗口 | 窗口内上限 |
|---|---|---|
| **SSS** / 国家级 | 24 小时 | 1 篇（即「不重复」） |
| **A** / 行业级 | **7 天** | 1 篇 |
| **SS** / 区域级、**S** / 机构级、**P** / 企业级、**X** | 24 小时（用户未指定，暂按国家级口径；**待确认**） | 1 篇 |
| **专题系列**（`--series`，如「云栖2026」） | — | **不设限制** |

新标记（title_tag.py 的 grade）与旧 level 等价，两种写法都接受：
`SSS=国家级`、`SS=区域级`、`A=行业级`、`S=机构级`、`P=企业级`。

说明：
- 「不重复」= 窗口内最多 1 篇；已有 1 篇就要换层级或等窗口过去。
- 专题系列是**策划意图**不是堆砌，故完全豁免层级窗口
  （v1 的 R2 24h≤3 会把「云栖 10 篇/轮」卡死在 3 篇，已废）。
- `topic` 仍**必须显式给定**：虽不再参与限次判定，但用于落标签与后续复盘
  （哪类主题发多了、与点击率/收藏率对照）。

⚠️ 为什么**不能靠标题自动判层级**（2026-09-16 实测踩坑）
--------------------------------------------------------
第一版用关键词在**标题**上猜 level/topic，拿近 15 天 100 条已发记录一跑：
**94 条被归到「行业级」、其中 56 条「综合」** —— 标题里根本没有主办方信息，
猜不准又默认兜底，结果是**每篇稿都会触限**，闸门等于封死。
→ 结论：**level / topic 必须由撰稿时显式给定**，只对**已打标**的条目计数。
  历史未打标条目不参与计数（宁可少拦，不可全拦）。

分类（level，按主办方层级）
--------------------------
| level  | 判据 |
|---|---|
| 国家级 | 中央部委及直属机构；「中国XX协会/学会/联合会/贸促会」等国字头全国性组织；国家实验室/中心 |
| 区域级 | 省/市/区政府与厅局委办、园区管委会；港澳官方机构；区域协同机制 |
| 行业级 | 行业协会/学会/产业联盟/专业媒体/会展公司主办的垂直行业活动（非国字头） |
| 机构级 | 高校、科研院所、医院等学术与科研机构主办 |
| 企业级 | 企业自办 |

分类（topic）：大模型与智能体 / 具身智能与机器人 / 生物医药AI / 芯片与算力 /
智能驾驶与出行 / 网络安全 / AI教育与人才 / 数字文娱与内容 / 其他产业AI /
智能终端与硬件 / 办公与生产力 / 开发者工具 / 综合

超限处置：该篇 **SKIP**，换层级或等窗口，**不硬凑**。

用法
----
    # 1) 排队前逐篇校验
    python near_dup_limit.py --title "云栖开源生态分论坛 9月23" \\
        --level 企业级 --topic 大模型与智能体

    # 2) 整轮队列批量校验（按数组顺序即发布顺序）
    python near_dup_limit.py --plan round_queue.json

    # 3) 专题系列（不设限制）
    python near_dup_limit.py --title "云栖专题 07" --level 企业级 \\
        --topic 综合 --series 云栖2026

    # 4) 发布成功后**必须**落标签（否则后续轮次无据可查）
    python near_dup_limit.py --record --title "..." --level 企业级 \\
        --topic 大模型与智能体 --note-id 6aa8...

退出码：0 = 可发 / 1 = 触限（换稿或改期） / 2 = 参数或环境错误
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
PATCH_ROOT = os.path.normpath(os.path.join(HERE, ".."))
PATCHES_ROOT = os.path.normpath(os.path.join(PATCH_ROOT, ".."))

WS_DEFAULT = os.environ.get("XHS_WORKSPACE") or os.path.expanduser("~/Documents/workbuddy-skill")
TAGS_PATH = os.environ.get("XHS_NEAR_DUP_TAGS") or os.path.join(
    PATCH_ROOT, "state", "near_dup_tags.json"
)

# ---- 限次常量（用户口径 v2，改这里即可全局生效）----
# 层级 → 窗口小时数；窗口内上限统一为 LEVEL_MAX_IN_WINDOW（「不重复」= 1）
LEVEL_WINDOW_HOURS = {
    "国家级": 24,
    "行业级": 24 * 7,      # 7 天
    "区域级": 24,          # 用户未指定，暂按国家级口径（待确认）
    "机构级": 24,          # 同上
    "企业级": 24,          # 同上
}
LEVEL_MAX_IN_WINDOW = 1     # 「不重复」= 窗口内最多 1 篇
SERIES_UNLIMITED = True     # 专题系列不设限制（用户原话）
# 注：v1 曾推定「相邻两篇不得层级+主题全同」（R3）——用户 2026-09-16 明确否定
#   「没人说过」，已彻底删除，不做开关保留。

LEVELS = ["国家级", "区域级", "行业级", "机构级", "企业级"]
# 新标题标记体系（2026-09-16）：grade ⇄ level 双向别名，两种写法都接受
GRADES = ["SSS", "SS", "S", "A", "P", "X"]
GRADE2LEVEL = {"SSS": "国家级", "SS": "区域级", "S": "机构级",
               "A": "行业级", "P": "企业级", "X": "企业级"}
LEVEL2GRADE = {v: k for k, v in GRADE2LEVEL.items()}


def norm_level(level):
    """把 grade 或 level 归一化为内部 level（两种写法等价）。"""
    lv = (level or "").strip()
    if lv.upper() in GRADES:
        return GRADE2LEVEL[lv.upper()]
    return lv
TOPICS = ["大模型与智能体", "具身智能与机器人", "生物医药AI", "芯片与算力",
          "智能驾驶与出行", "网络安全", "AI教育与人才", "数字文娱与内容",
          "其他产业AI", "智能终端与硬件", "办公与生产力", "开发者工具", "综合"]


def parse_ts(s):
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            continue
    return None


def window_text(hours):
    return f"{hours} 小时" if hours < 48 else f"{hours // 24} 天"


def load_tags():
    """已打标的已发条目（唯一计数依据）。"""
    if not os.path.exists(TAGS_PATH):
        return []
    try:
        with open(TAGS_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []
    out = []
    for e in data:
        ts = parse_ts(e.get("ts", "")) or datetime.min
        out.append({"title": e.get("title", ""), "ts": ts,
                    "level": e.get("level", ""), "topic": e.get("topic", ""),
                    "note_id": e.get("note_id", ""),
                    # series 必须读回：漏了它主题系列判定会永远失败（字段为 None）
                    "series": e.get("series", "") or ""})
    return out


def check(title, level, topic, tags=None, series=None):
    """返回 (ok, reasons, meta)。ok=False → 触限，不该发。

    tags：已打标历史条目；
    series：专题系列名（如 `云栖2026`）——不设限制，直接放行。
    """
    level = norm_level(level)
    if level not in LEVELS:
        return False, [f"level/grade 非法：{level}（须为 {'/'.join(LEVELS)}"
                       f" 或 {'/'.join(GRADES)}）"], {"level": level, "topic": topic}
    if topic not in TOPICS:
        return False, [f"topic 非法：{topic}（须为 {'/'.join(TOPICS)}）"], {}

    tags = load_tags() if tags is None else tags
    now = datetime.now()
    reasons = []

    # 专题系列：用户口径「专题不设限制」→ 直接放行（仍落标签供复盘）
    if series and SERIES_UNLIMITED:
        return True, [], {"level": level, "topic": topic, "series": series,
                          "exempt": "专题系列不设限制"}

    hours = LEVEL_WINDOW_HOURS.get(level, 24)
    win = timedelta(hours=hours)

    # 同层级窗口计数：历史条目若属同一专题系列，也不计入（系列篇不该占用散篇额度）
    same_lv = [t for t in tags
               if t["level"] == level
               and not (series and t.get("series") == series)
               and (now - t["ts"]) < win]
    if len(same_lv) + 1 > LEVEL_MAX_IN_WINDOW:
        reasons.append(
            f"L1 {level} 窗口内重复：{window_text(hours)}内已有 {len(same_lv)} 篇"
            f"（上限 {LEVEL_MAX_IN_WINDOW}）→ "
            + "、".join(f"「{x['title']}」{x['ts']:%m-%d %H:%M}" for x in same_lv[:3]))

    return (len(reasons) == 0), reasons, {"level": level, "topic": topic,
                                          "window_hours": hours}


def record(title, level, topic, note_id="", series=""):
    # 必须归一化：否则 --level A 落盘成 "A"、check 时按 "行业级" 比对 → 永远计不到数
    level = norm_level(level)
    os.makedirs(os.path.dirname(TAGS_PATH), exist_ok=True)
    data = []
    if os.path.exists(TAGS_PATH):
        try:
            with open(TAGS_PATH, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = []
    data.append({"ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                 "title": title, "level": level, "topic": topic,
                 "note_id": note_id, "series": series or ""})
    with open(TAGS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return len(data)


def main():
    ap = argparse.ArgumentParser(description="近似文章限次（按层级设窗口）")
    ap.add_argument("--title", help="待发标题")
    ap.add_argument("--level", help="活动层级（**必填**，按主办方判）："
                    + "/".join(LEVELS) + "，或新标记 " + "/".join(GRADES))
    ap.add_argument("--topic", help="主题（**必填**；自由文本，预设列表仅作参考："
                    + "/".join(TOPICS) + "）")
    ap.add_argument("--plan", help="批量校验队列 JSON（[{title,level,topic,series?}]，按数组顺序即发布顺序）")
    ap.add_argument("--record", action="store_true",
                    help="发布成功后落标签（与 --title/--level/--topic/--note-id 同用）")
    ap.add_argument("--note-id", default="", help="发布后的 note_id（--record 用）")
    ap.add_argument("--series", default="",
                    help="专题系列名（如 云栖2026）：专题不设限制，直接放行")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if args.record:
        if not (args.title and args.level and args.topic):
            print("--record 需要 --title / --level / --topic", file=sys.stderr)
            return 2
        if norm_level(args.level) not in LEVELS:
            print(f"--level 非法：{args.level}（须为 {'/'.join(LEVELS)}"
                  f" 或 {'/'.join(GRADES)}）", file=sys.stderr)
            return 2
        n = record(args.title, args.level, args.topic, args.note_id, args.series)
        print(f"[near-dup] 已落标签：{args.level}/{args.topic}「{args.title}」（累计 {n} 条）")
        return 0

    if args.plan:
        try:
            with open(args.plan, encoding="utf-8") as f:
                items = json.load(f)
        except Exception as e:
            print(f"队列文件读取失败：{e}", file=sys.stderr)
            return 2
        tags = load_tags()
        bad = []
        for it in items:
            ok, reasons, meta = check(it.get("title", ""), it.get("level", ""),
                                      it.get("topic", ""), tags,
                                      it.get("series"))
            it["_level"], it["_topic"] = meta.get("level", ""), meta.get("topic", "")
            if not ok:
                it["_reasons"] = reasons
                bad.append(it)
        print(f"[near-dup] 队列 {len(items)} 篇，触限 {len(bad)} 篇"
              f"（已打标历史 {len(tags)} 条）")
        for it in bad:
            print(f"  !! 「{it.get('title')}」({it['_level']}/{it['_topic']})")
            for r in it["_reasons"]:
                print(f"     - {r}")
        print("[near-dup] 处置：触限篇换层级或等窗口过去，不硬凑")
        return 1 if bad else 0

    if not (args.title and args.level and args.topic):
        print("需要 --title / --level / --topic（层级与主题必须显式给定，脚本不猜）",
              file=sys.stderr)
        return 2
    if norm_level(args.level) not in LEVELS:
        print(f"--level 非法：{args.level}（须为 {'/'.join(LEVELS)}"
              f" 或 {'/'.join(GRADES)}）", file=sys.stderr)
        return 2

    ok, reasons, meta = check(args.title, args.level, args.topic, series=args.series)
    if args.json:
        print(json.dumps({"ok": ok, "reasons": reasons, **meta}, ensure_ascii=False, indent=2))
    else:
        print(f"[near-dup] 判定：{meta['level']} / {meta['topic']}"
              + (f"（系列 {args.series}）" if args.series else ""))
        if meta.get("exempt"):
            print(f"[near-dup] 规则：{meta['exempt']}")
        else:
            print(f"[near-dup] 规则：{meta['level']} {window_text(meta['window_hours'])}"
                  f"内 ≤{LEVEL_MAX_IN_WINDOW} 篇")
        if ok:
            print("[near-dup] OK 可发")
        else:
            print("[near-dup] !! 触限，换层级或等窗口：")
            for r in reasons:
                print(f"  - {r}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
