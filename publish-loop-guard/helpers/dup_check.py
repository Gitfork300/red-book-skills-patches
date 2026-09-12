"""选题查重（按"事件"而不是按"标题字面"）。

为什么需要它
------------
`check_missing.py` 用**标题精确匹配**判断"发没发过"，这个口径对"漏发复核"是对的，
但用来**查重**会漏：同一个活动，两次写稿的标题措辞必然不同，精确匹配永远判为"没发过"。

2026-09-11 实例（真实事故）：
  - 00:48 发出 `浦江创新论坛AI科研专题13日开幕`（ex0911_1）
  - 06:12 又发出 `浦江创新论坛设AI与类脑专题`（ai0911_13）
  同一场活动（2026 第十九届浦江创新论坛，9/11-14 上海张江科学会堂）被发了两遍。
  两稿标题字面不同，精确匹配漏了。读者侧表现为重复内容。

判定方式
--------
**严格模式（默认，全量扫描用）**：只看第 1 道信号 —— **事件标识相同**
（标题里以 论坛/大会/峰会/展/博览会/年会… 结尾的专名一致）。误报极低。

**宽松模式（`--loose`，或 `--title` 单条预检时自动叠加）**：再加第 2 道信号 ——
**最长公共子串 ≥ N 个汉字**（默认 5，且至少 4 个汉字、不能是"9月11日"这类日期串）。
措辞不同但事件名会照抄。

> 单条预检（`--title`）默认就同时用两道信号，因为"拦住一篇要发的稿子"比"少报"更重要。

用法
----
    python dup_check.py                            # 全量扫描（严格）
    python dup_check.py --loose                    # 全量扫描（宽松，会多看一批系列稿）
    python dup_check.py --title "浦江创新论坛设AI与类脑专题"   # 单条预检（排队前用）
    python dup_check.py --days 7                   # 只看近 7 天
    python dup_check.py --json

退出码：0 = 未发现重复 / 1 = 疑似重复 / 2 = 参数或环境错误

环境变量：
  XHS_DRAFT_DIR      稿件目录，默认 <workspace>/xhs_publish
  XHS_INTERVAL_LOG   发布日志，默认 <patches>/publish-interval-guard/state/publish_log.json
"""
import argparse
import glob
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
PATCH_ROOT = os.path.normpath(os.path.join(HERE, ".."))
PATCHES_ROOT = os.path.normpath(os.path.join(PATCH_ROOT, ".."))

WS_DEFAULT = r"C:/Users/EricSupport(DMSH)/Documents/workbuddy-skill"
DRAFT_DIR = os.environ.get("XHS_DRAFT_DIR") or os.path.join(WS_DEFAULT, "xhs_publish")
LOG_PATH = os.environ.get("XHS_INTERVAL_LOG") or os.path.join(
    PATCHES_ROOT, "publish-interval-guard", "state", "publish_log.json"
)

# 事件类后缀：从长到短匹配，取最长的那个作为"事件标识词"的结尾
SUFFIXES = [
    "博览会", "展览会", "发布会", "交流会", "对接会", "研讨会", "专题论坛",
    "大会", "论坛", "峰会", "年会", "展会", "会议", "讲坛", "展", "节", "周", "赛",
]
NOISE = re.compile(r"[\s\u3000·—\-–—,:：;；。、！!？?（）()\[\]【】《》<>\"'“”‘’/\\|+~]+")
TIME_HEAD = re.compile(r"^(今年|本届|此届|第[一二三四五六七八九十百千0-9]+届|今日|今天|明日|明天|昨日|昨天|次日)+")


def norm(title):
    """去标点/空白，只留可见字符，便于比较。"""
    return NOISE.sub("", title or "").strip()


def event_key(title):
    """抽取"事件标识词"，如「浦江创新论坛」「宁波智博会」。抽不到返回 None。"""
    t = norm(title)
    if not t:
        return None
    best = None
    for suf in SUFFIXES:
        idx = t.rfind(suf)
        if idx < 0:
            continue
        pre = t[max(0, idx - 6):idx]
        pre = TIME_HEAD.sub("", pre)
        cand = pre + suf
        if best is None or len(cand) > len(best):
            best = cand
    return best


def lcs(a, b):
    """最长公共子串（连续）。返回子串本身。"""
    if not a or not b:
        return ""
    prev = [0] * (len(b) + 1)
    best_len = 0
    best_end = 0
    for i in range(1, len(a) + 1):
        cur = [0] * (len(b) + 1)
        ai = a[i - 1]
        for j in range(1, len(b) + 1):
            if ai == b[j - 1]:
                cur[j] = prev[j - 1] + 1
                if cur[j] > best_len:
                    best_len = cur[j]
                    best_end = i
        prev = cur
    return a[best_end - best_len:best_end]


def cjk_count(s):
    return sum(1 for ch in s if "\u4e00" <= ch <= "\u9fff")


def is_datey(s):
    """纯日期/数字串（如「9月11日」「16日开幕」的前半）不算重复证据。"""
    if not s:
        return True
    if re.fullmatch(r"[0-9年月日号届次第]+", s):
        return True
    digits = sum(1 for ch in s if ch.isdigit())
    return digits / len(s) > 0.4


def similar(t1, t2, min_lcs=5, loose=True):
    """返回 (是否疑似重复, 原因)。

    loose=False 时只看"事件标识相同"这一条高置信信号。
    """
    n1, n2 = norm(t1), norm(t2)
    if not n1 or not n2:
        return False, ""
    if n1 == n2:
        return True, "标题完全相同"
    k1, k2 = event_key(t1), event_key(t2)
    if k1 and k2 and k1 == k2:
        return True, f"事件标识相同「{k1}」"
    if not loose:
        return False, ""
    run = lcs(n1, n2)
    if len(run) >= min_lcs and cjk_count(run) >= 4 and not is_datey(run):
        return True, f"公共子串「{run}」({len(run)}字)"
    return False, ""


def parse_ts(s):
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            continue
    return None


def load_log():
    if not os.path.exists(LOG_PATH):
        return []
    with open(LOG_PATH, encoding="utf-8") as f:
        data = json.load(f)
    out = []
    for e in data:
        t = e.get("title") or ""
        if t:
            out.append({"title": t, "ts": e.get("ts", ""), "src": "log"})
    return out


def load_drafts():
    out = []
    for p in sorted(glob.glob(os.path.join(DRAFT_DIR, "*_title.txt"))):
        try:
            with open(p, encoding="utf-8") as f:
                t = f.read().strip()
        except Exception:
            continue
        if t:
            out.append({"title": t, "src": os.path.basename(p).replace("_title.txt", "")})
    return out


def main():
    ap = argparse.ArgumentParser(description="选题查重（按事件，不按标题字面）")
    ap.add_argument("--title", help="只检查这一条标题（排队前预检用）")
    ap.add_argument("--days", type=int, default=0, help="只看近 N 天的发布记录，0=不限")
    ap.add_argument("--min-lcs", type=int, default=5, help="公共子串判定阈值（默认 5 字）")
    ap.add_argument("--loose", action="store_true",
                    help="全量扫描时也启用「公共子串」信号（默认只比事件标识）")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if not os.path.isdir(DRAFT_DIR):
        print(f"稿件目录不存在：{DRAFT_DIR}", file=sys.stderr)
        return 2

    entries = load_log()
    if args.days > 0:
        cutoff = datetime.now() - timedelta(days=args.days)
        entries = [e for e in entries
                   if (parse_ts(e["ts"]) or datetime.min) >= cutoff]
    drafts = load_drafts()

    def add(a, b, why):
        key = tuple(sorted([norm(a["title"]), norm(b["title"])]))
        if key in seen:
            return
        seen.add(key)
        findings.append({
            "a": a["title"], "a_src": a["src"], "a_ts": a.get("ts", ""),
            "b": b["title"], "b_src": b["src"], "b_ts": b.get("ts", ""),
            "why": why,
        })

    findings = []
    seen = set()
    loose = True if args.title else args.loose

    if args.title:
        me = {"title": args.title, "src": "(待发)"}
        for e in entries + drafts:
            if e["src"] == "(待发)":
                continue
            ok, why = similar(args.title, e["title"], args.min_lcs, loose=True)
            if ok:
                add(me, e, why)
    else:
        # 日志内部两两比较
        for i in range(len(entries)):
            for j in range(i + 1, len(entries)):
                ok, why = similar(entries[i]["title"], entries[j]["title"],
                                  args.min_lcs, loose=loose)
                if ok:
                    add(entries[i], entries[j], why)
        # 稿件 vs 已发（完全同名的稿件=已发稿，跳过，不算重复）
        log_norms = {norm(e["title"]) for e in entries}
        for d in drafts:
            if norm(d["title"]) in log_norms:
                continue
            for e in entries:
                ok, why = similar(d["title"], e["title"], args.min_lcs, loose=loose)
                if ok:
                    add(d, e, why)

    if args.json:
        print(json.dumps({"count": len(findings), "findings": findings},
                         ensure_ascii=False, indent=2))
    else:
        mode = "宽松（事件标识 + 公共子串）" if loose else "严格（只看事件标识）"
        print(f"[dup] 日志 {len(entries)} 条 / 稿件 {len(drafts)} 篇；模式：{mode}"
              + (f"；公共子串阈值 ≥ {args.min_lcs} 字" if loose else ""))
        if not findings:
            print("[dup] OK 未发现重复选题")
        else:
            print(f"[dup] !! 疑似重复 {len(findings)} 组：")
            for f in findings:
                print(f"  - 「{f['a']}」({f['a_src']}{' ' + f.get('a_ts', '') if f.get('a_ts') else ''})")
                print(f"    与「{f['b']}」({f['b_src']}{' ' + f.get('b_ts', '') if f.get('b_ts') else ''})")
                print(f"    理由：{f['why']}")
            print("[dup] 处置：同一活动只保留一篇；已在平台上的重复内容需人工下架其一")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
