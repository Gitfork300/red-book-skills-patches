# -*- coding: utf-8 -*-
"""标题标记体系（2026-09-16 用户提出；与限次闸门共用一套等级）。

设计要点（为什么这样定）
------------------------
1. **标题只背 1 个方括号前缀**。用户原案把 [天气]（品类）、[专题]（形态）、
   [SSS]/[S]/[P]/[X]（等级）三个维度并列，若都进标题会吃掉大量字宽
   —— 平台标题 20 字上限按**字宽**计（汉字/全角=1，英文/数字/半角=0.5）：
   `[SSS]`=2.5、`[天气]`=3.0、`[专题]`=3.0、`[Canary]`=4.0，两个就占掉三分之一。
   → 等级与品类**互斥显示**（优先级：Canary > 天气 > 等级），其余维度落盘不进标题。

2. **等级与限次闸门对齐**，避免两套层级打架：
   `[SSS]` = 原「国家级」（用户原话 24h 不重复）
   `[A]`   = 原「行业级」（用户原话 **7 天**不重复）
   `[SS]`/`[S]` = 政府牵头中小（新增；用户原案只有 SSS/S 两档，
                 市级/区级活动会全部挤在 S 里 → 拆出 SS 便于统计与限次）
   `[P]`   = 小众消息（企业自办/社群/小展）
   `[X]`   = 其他无法归类

3. **[专题] 不进标题**，改用**系列编号**（如「云栖①」）：
   省 3 字宽，且连载编号制造追更动机 —— 官方数据显示本号涨粉率仅 **0.09%**
   （4 万阅读只涨 38 粉），缺的正是「关注理由」。

等级判据（按主办方，不按规模感觉）
----------------------------------
| 标记 | 判据 |
|---|---|
| SSS | 中央部委及直属机构、省政府、国家级新区主办的全国性/国际性活动 |
| SS  | 市政府、省厅局委办、国家级园区（张江、河套等）主办 |
| S   | 区政府、区级园区管委会、公立事业单位（图书馆、科技馆）主办 |
| A   | 行业协会/学会/产业联盟/专业媒体/会展公司主办的垂直行业活动（非国字头） |
| P   | 企业自办、社群、小型沙龙、闭门会、邀请制小场 |
| X   | 其他无法归类 |

用法
----
    # 1) 生成合规标题
    python title_tag.py --make "云栖大会9月22日启幕" --grade SSS
    python title_tag.py --make "参会全攻略" --grade A --canary
    python title_tag.py --make "台风预警" --category 天气

    # 2) 校验（退出码 0 通过 / 1 违规）
    python title_tag.py --check "[SSS] 云栖大会9月22日启幕"

    # 3) 批量校验队列 JSON（[{"title": "..."}]）
    python title_tag.py --plan round_queue.json

    # 4) 扫描已发日志，统计打标覆盖率（历史不追溯改标题，只作统计）
    python title_tag.py --scan
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
PATCH_ROOT = os.path.normpath(os.path.join(HERE, ".."))
PATCHES_ROOT = os.path.normpath(os.path.join(PATCH_ROOT, ".."))

# 复用 safe-wording-guard 的字宽实现（避免两套口径）
try:
    sys.path.insert(0, os.path.join(PATCHES_ROOT, "safe-wording-guard", "helpers"))
    from check_wording import title_width  # type: ignore
except Exception:  # pragma: no cover
    def title_width(text: str) -> float:
        return sum(0.5 if ord(ch) < 128 else 1.0 for ch in text)

# ---- 标记定义 ----
GRADES = {
    "SSS": "政府牵头·大型（部委/省政府/国家级新区）",
    "SS": "政府牵头·中型（市政府/省厅局/国家级园区）",
    "S": "政府牵头·小型（区政府/区级园区/事业单位）",
    "A": "行业事件（协会/学会/联盟/专业媒体/会展公司）",
    "P": "小众消息（企业自办/社群/沙龙/邀请制）",
    "X": "其他无法归类",
}
# 品类标记（与等级互斥显示；天气类必然政府发布，等级冗余 → 显示天气）
CATEGORIES = ["天气", "Canary"]
ALL_TAGS = list(GRADES) + CATEGORIES

# 等级 → 限次窗口小时数（与 near_dup_limit.LEVEL_WINDOW_HOURS 必须保持一致）
GRADE_WINDOW_HOURS = {
    "SSS": 24,
    "SS": 24,     # 用户未指定，暂按国家级口径（待确认）
    "S": 24,      # 同上
    "A": 24 * 7,  # 用户原话：行业级 7 天不重复
    "P": 24,      # 用户未指定（待确认）
    "X": 24,      # 用户未指定（待确认）
}
# 旧 level → 新 grade（向后兼容，历史已打标条目可平滑迁移）
LEVEL2GRADE = {"国家级": "SSS", "区域级": "SS", "行业级": "A",
               "机构级": "S", "企业级": "P"}

MAX_WIDTH_WARN = 18.0   # 留余量（平台硬限 20）
MAX_WIDTH_HARD = 20.0   # 超过会被平台静默拒绝

TAG_RE = re.compile(r"^\s*\[([^\]\[]+)\]\s*")
MULTI_TAG_RE = re.compile(r"^\s*(\[[^\]\[]+\]\s*){2,}")


def make_title(body, grade=None, category=None, canary=False, series_no=None):
    """生成带标记的标题。优先级：Canary > 天气 > 等级。"""
    body = (body or "").strip().lstrip("]").strip()
    body = re.sub(r"^\s*\[[^\]\[]+\]\s*", "", body)  # 去掉已有前缀，防重复叠加
    if canary:
        tag = "Canary"
    elif category == "天气" or category == "天气预警":
        tag = "天气"
    elif grade:
        tag = grade.upper()
    else:
        tag = "X"
    if tag not in ALL_TAGS:
        raise ValueError(f"非法标记 {tag}（合法：{'/'.join(ALL_TAGS)}）")
    # 系列编号：省字宽的「专题」表达，如 云栖①
    if series_no:
        body = f"{body} {series_no}"
    return f"[{tag}] {body}".strip()


def parse_title(title):
    """解析标题前缀 → dict(tag, kind, grade, category, canary, body)。"""
    t = title or ""
    m = TAG_RE.match(t)
    if not m:
        return {"tag": "", "kind": "none", "grade": "", "category": "",
                "canary": False, "body": t.strip(), "ok": False}
    tag = m.group(1).strip()
    body = t[m.end():].strip()
    if tag in CATEGORIES:
        return {"tag": tag, "kind": "category", "grade": "", "category": tag,
                "canary": tag == "Canary", "body": body, "ok": True}
    g = tag.upper()
    if g in GRADES:
        return {"tag": g, "kind": "grade", "grade": g, "category": "",
                "canary": False, "body": body, "ok": True}
    return {"tag": tag, "kind": "unknown", "grade": "", "category": "",
            "canary": False, "body": body, "ok": False}


def check_title(title):
    """校验标题标记。返回 (ok, hard_fail, reasons)。"""
    reasons, hard = [], False
    t = (title or "").strip()
    if not t:
        return False, True, ["标题为空"]
    if MULTI_TAG_RE.match(t):
        hard = True
        reasons.append(f"[P0] 标题含多个方括号前缀「{t[:24]}」——"
                       "标记**只能有一个**（等级与品类互斥），其余维度落盘不进标题")
    p = parse_title(t)
    if p["kind"] == "none":
        hard = True
        reasons.append(f"[P0] 缺少标题标记：须以 [{'/'.join(ALL_TAGS)}] 之一开头"
                       f"（如 `[A] xxx`、`[天气] xxx`、`[Canary] xxx`）")
    elif p["kind"] == "unknown":
        hard = True
        reasons.append(f"[P0] 标记 [{p['tag']}] 非法（合法：{'/'.join(ALL_TAGS)}）")
    w = title_width(t)
    if w > MAX_WIDTH_HARD:
        hard = True
        reasons.append(f"[P0] 标题 {w:g}/{MAX_WIDTH_HARD:g} 字宽 —— 平台会静默拒绝发布")
    elif w > MAX_WIDTH_WARN:
        reasons.append(f"[P1] 标题 {w:g} 字宽 > {MAX_WIDTH_WARN:g} 余量线"
                       "（标记已占位，正文标题要再压缩）")
    return (not hard), hard, reasons


def grade_of(level_or_grade):
    """把旧 level 或新 grade 归一化为 grade。"""
    g = (level_or_grade or "").strip()
    if g.upper() in GRADES:
        return g.upper()
    return LEVEL2GRADE.get(g, "")


def main():
    ap = argparse.ArgumentParser(description="标题标记体系（等级/品类/Canary）")
    ap.add_argument("--make", metavar="BODY", help="生成带标记的标题")
    ap.add_argument("--grade", help="等级：" + "/".join(GRADES))
    ap.add_argument("--category", help="品类：" + "/".join(CATEGORIES))
    ap.add_argument("--canary", action="store_true",
                    help="实验批次（10%% 新尝试）")
    ap.add_argument("--series-no", help="系列编号，如 云栖①（替代 [专题]，省字宽）")
    ap.add_argument("--check", metavar="TITLE", help="校验单个标题")
    ap.add_argument("--plan", help="批量校验队列 JSON（[{title,...}]）")
    ap.add_argument("--scan", action="store_true", help="扫描已发日志统计打标覆盖率")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if args.make:
        try:
            out = make_title(args.make, args.grade, args.category,
                             args.canary, args.series_no)
        except ValueError as e:
            print(str(e), file=sys.stderr)
            return 2
        ok, hard, reasons = check_title(out)
        print(out)
        print(f"  字宽 {title_width(out):g} / 余量线 {MAX_WIDTH_WARN:g}")
        for r in reasons:
            print("  " + r)
        return 0 if ok else 1

    if args.check:
        ok, hard, reasons = check_title(args.check)
        p = parse_title(args.check)
        if args.json:
            print(json.dumps({"ok": ok, "hard_fail": hard, "reasons": reasons, **p},
                             ensure_ascii=False, indent=2))
        else:
            print(f"[tag] 标记 [{p['tag']}] 类型={p['kind']} 等级={p['grade'] or '-'} "
                  f"品类={p['category'] or '-'} 字宽={title_width(args.check):g}")
            if ok and not reasons:
                print("[tag] OK")
            for r in reasons:
                print("  " + r)
        return 0 if ok else 1

    if args.plan:
        items = json.load(open(args.plan, encoding="utf-8"))
        bad = 0
        for it in items:
            t = it.get("title", "")
            ok, hard, reasons = check_title(t)
            if not ok or reasons:
                bad += 1
                print(f"  !! 「{t}」")
                for r in reasons:
                    print("     - " + r)
        print(f"[tag] 队列 {len(items)} 篇，有问题 {bad} 篇")
        return 1 if bad else 0

    if args.scan:
        cand = [os.path.join(PATCHES_ROOT, "publish-interval-guard", "state", "publish_log.json")]
        log = next((p for p in cand if os.path.exists(p)), None)
        if not log:
            print("找不到 publish_log.json", file=sys.stderr)
            return 2
        rows = json.load(open(log, encoding="utf-8"))
        cnt = {"none": 0, "unknown": 0}
        by = {}
        for r in rows:
            p = parse_title(r.get("title", ""))
            cnt[p["kind"]] = cnt.get(p["kind"], 0) + 1
            if p["kind"] in ("grade", "category"):
                by[p["tag"]] = by.get(p["tag"], 0) + 1
        total = len(rows)
        tagged = total - cnt.get("none", 0)
        print(f"[tag] 已发 {total} 篇，已打标 {tagged} 篇（{tagged/max(total,1)*100:.0f}%），"
              f"未打标 {cnt.get('none',0)} 篇")
        for k, v in sorted(by.items(), key=lambda x: -x[1]):
            print(f"   [{k}] {v} 篇")
        print("[tag] 说明：历史标题不追溯修改（改动已发笔记有风险），"
              "新标记自本轮生效；未打标条目不参与限次计数。")
        return 0

    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
