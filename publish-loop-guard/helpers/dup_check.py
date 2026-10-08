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

> 第 2 道信号**不在原始标题上算**，而是在 `identity()` 上算 —— 先把**日期**（`16日`/`9月`/`第3届`）
> 与**模板动词**（`开幕`/`举办`/`举行`/`同期`…）剥掉，只让「事件名本体」参与比对。
> 否则 `苏州AI算力展16日开幕` 与 `深圳低空经济展16日开幕` 会因公共子串「展16日开幕」被误判重复
> （两者是不同城市的两个展会，2026-09-12 真实误报）。

> 单条预检（`--title`）默认就同时用两道信号，因为"拦住一篇要发的稿子"比"少报"更重要。

**单条预检的比对范围（2026-09-12 修订）**：只与**已发日志**比，回答的是
"这个选题平台上发过没有"。**不再与"同批其它待发稿"比** —— 稿件目录里的同名稿件就是
这条稿子**自己**（排队前预检时标题已落盘），而**同一批次的系列专题**（如一个大会拆 6 篇）
事件标识天然相同，那是**策划意图、不是重复**。按事件标识与待发稿比会让整批互相撞死
（2026-09-12 外滩大会 6 篇专题因此全批 FAIL）。
批内仍保留一道保险：**标题与同批次另一篇完全相同**会被报出，防手滑重复提交。

用法
----
    python dup_check.py                            # 全量扫描（严格）
    python dup_check.py --loose                    # 全量扫描（宽松，会多看一批系列稿）
    python dup_check.py --title "浦江创新论坛设AI与类脑专题"   # 单条预检（排队前用）
    python dup_check.py --days 7                   # 只看近 7 天
    python dup_check.py --json

退出码：0 = 未发现重复 / 1 = 疑似重复 / 2 = 参数或环境错误

类别化查重窗口 + 发布优先级（2026-09-12 用户要求）
--------------------------------------------------
选题分三类，**发布优先级 A > 行业 > 其他**，且各类有各自的"不得重复"回看窗口：

| 类别 | `--class` | 窗口 | 含义 |
|---|---|---|---|
| A 类（公众型：免费/低门槛，普通读者能到场） | `a` | **当天** | 同一自然日内同一活动不得重复发 |
| 行业类（专业展/面向特定从业者） | `industry` | **7 天** | 7 天内不得重复（用户口径原话；2026-09-16 由 3 天回归） |
| 其他 | `other` | **15 天** | 15 天内不得重复 |

窗口越大越保守；**不确定该归哪类时按更长的窗口判**（拿不准就走 `other`）。
单条预检示例：

    python dup_check.py --title "广东科普创新展18日开幕" --class a

环境变量：
  XHS_WORKSPACE      工作区根目录（换机器必设），默认 ~/xhs-workspace
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

WS_DEFAULT = os.environ.get("XHS_WORKSPACE") or os.path.expanduser("~/xhs-workspace")
DRAFT_DIR = os.environ.get("XHS_DRAFT_DIR") or os.path.join(WS_DEFAULT, "xhs_publish")
LOG_PATH = os.environ.get("XHS_INTERVAL_LOG") or os.path.join(
    PATCHES_ROOT, "publish-interval-guard", "state", "publish_log.json"
)

# 类别化查重窗口：
#   a        → 当天（同一自然日）内不得重复（对应用户口径「国家级 24 小时内不重复」）
#   industry → **7 天**内不得重复（用户口径原话：「行业级 7 天内不重复」）
#   other    → 15 天内不得重复
#
# ⚠️ 2026-09-16 夜间修正：industry 原为 3 天，与用户明确说过的「行业级 7 天内不重复」
# **差 4 天**，属实现偏离口径。实测代价：9/13 发的佛山 CCF 与 9/15 发的香港 CREATE
# 在 3 天窗口下已滚出，若非 title 撞车就会被放行。按用户口径回归 **7 天**。
CLASS_WINDOW = {"a": ("same-day", 0), "industry": ("days", 7), "other": ("days", 15)}

# 事件类后缀：从长到短匹配，取最长的那个作为"事件标识词"的结尾
SUFFIXES = [
    "博览会", "展览会", "发布会", "交流会", "对接会", "研讨会", "专题论坛",
    "大会", "论坛", "峰会", "年会", "展会", "会议", "讲坛", "展", "节", "周", "赛",
]
NOISE = re.compile(r"[\s\u3000·—\-–—,:：;；。、！!？?（）()\[\]【】《》<>\"'“”‘’/\\|+~]+")
TIME_HEAD = re.compile(r"^(今年|本届|此届|第[一二三四五六七八九十百千0-9]+届|今日|今天|明日|明天|昨日|昨天|次日)+")

# ---- 「不构成同一事件证据」的成分（2026-09-12 修 false positive）----
# 原实现直接在**原始标题**上算 LCS，于是「…展16日开幕」这种「日期 + 模板动词」的组合
# 会被当成事件证据：苏州AI算力展 与 深圳低空经济展 被误判为重复（真实事故，见修改记录 v1.7.1）。
# 日期本就不算证据（原 is_datey 已声明），模板动词同理 —— 两者都只是文章的写法，不是事件。
# 做法：先把这两类成分从标题里剥掉，再算 LCS，只让「事件名本体」参与比对。
# 2026-09-14 追加：原 `\d{1,2}\s*月` 只剥「9月」，`9月20上海` 会残留成 `20上海`，
# 使「全球AI芯片峰会9月20上海」与「PAIR物理AI峰会9月20上海」撞出「峰会20上海」——两个完全
# 不同的大会被误判重复。改为**月 + 可选日一起剥**（`9月20` / `9月20日` 整体消失）。
DATE_PAT = re.compile(r"\d{4}\s*年|\d{1,2}\s*月(?:\s*\d{1,2}\s*[日号]?)?|\d{1,2}\s*[日号]|\d{1,2}\s*[届次]|第\s*\d+")
TEMPLATE_WORDS = [
    "开幕", "举办", "举行", "启幕", "开展", "召开", "登场", "来袭", "上线", "发布",
    "同期", "今天", "今日", "明天", "明日", "次日", "昨日", "昨天", "举行",
]


# 系列标记（标题开头的 [xxx]）：如 [2026云栖大会] / [赛博户外] / [Canary] / [P]。
# 同一系列的每篇都带同一个标记，天然相同。若让它参与公共子串比对，本系列内部会互判重复
# （实测 [2026云栖大会] 标记 6 字 ≥ 阈值 5，导致该专题 5 篇全部 FAIL）。
# 因此算 identity 时先剥掉标题开头的系列标记；对于 environment 标题完全相同的情况，
# 由标题级相同判据兜底，不会漏放行。
SERIES_TAG = re.compile(r"^\[[^\]]{1,24}\]")


def identity(title):
    """标题的「事件名本体」：剥掉系列标记、日期与模板动词，只留可能标识事件的部分。"""
    t = SERIES_TAG.sub("", (title or "").strip())
    t = norm(t)
    t = DATE_PAT.sub("", t)
    for w in TEMPLATE_WORDS:
        t = t.replace(w, "")
    return t


def norm(title):
    """去标点/空白，只留可见字符，便于比较。"""
    return NOISE.sub("", title or "").strip()


def event_key(title):
    """抽取"事件标识词"，如「浦江创新论坛」「宁波智博会」。抽不到返回 None。

    注：系列标记（标题开头的 [xxx]）先剥掉。否则专题连载的每一篇都会抽到同一个
    事件标识，被判成同一活动的重复稿 —— 2026 云栖专题 5 篇/天就是这么全 FAIL 的。
    标题完全相同的情况由标题级相同判据兜底，不会漏放行。
    """
    t = SERIES_TAG.sub("", (title or "").strip())
    t = norm(t)
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


# ---- 第三道信号：地点 + 日期（2026-09-16 夜间新增）----
# 事故：`[Canary] 香港医疗AI论坛922 报名`（9/16 21:20 已发）与 9/15 已发
# `香港具身智能医疗论坛 9月22` 是**同一场活动**，但原有两道信号都没报：
#   - 事件标识：一个抽到「香港医疗AI论坛」、一个抽到「香港具身智能医疗论坛」→ 不相等；
#   - 公共子串：identity 剥日期后最长公共子串只有 2 字（「医疗」/「论坛」）→ < 5 字阈值。
# 结果：**改一改标题措辞就能绕过闸门**，同一活动被发了第二遍。
# 同一场活动的「举办地 + 举办日期」是绕不过去的，故补此第三道信号。
# 为避免误伤「同城同日两个不同活动」（如上海同一天两场会），要求剥掉地名与日期后
# 仍存在 ≥2 字公共词（「上海A大会」vs「上海B论坛」→ 剥完只剩 A大会 / B论坛 → 不报）。
PLACES = [
    "香港", "澳门", "上海", "北京", "深圳", "广州", "佛山", "东莞", "珠海", "中山",
    "惠州", "江门", "肇庆", "汕头", "湛江", "杭州", "宁波", "温州", "嘉兴", "绍兴",
    "湖州", "金华", "台州", "苏州", "南京", "无锡", "常州", "南通", "扬州", "徐州",
    "合肥", "厦门", "福州", "泉州", "南昌", "长沙", "武汉", "郑州", "济南", "青岛",
    "烟台", "天津", "重庆", "成都", "西安", "昆明", "贵阳", "南宁", "海口", "三亚",
    "大连", "沈阳", "哈尔滨", "长春", "石家庄", "太原", "兰州", "银川",
]


# 通用修饰词：高频但**不指向具体活动**，与事件后缀一同从「活动身份」里剥离
NOISE_WORDS = SUFFIXES + [
    "产业", "行业", "智能", "科技", "创新", "数据", "数字", "未来", "全球", "国际",
    "中国", "世界", "年度", "发展", "生态", "赋能", "融合", "趋势", "前沿", "机遇",
    "挑战", "实践", "应用", "平台", "服务",
]


def dates(text):
    """标题里的日期 token → 规整成 MMDD 集合（`922` / `9月22` / `9-22` 归一）。"""
    out = set()
    t = text or ""
    for m in re.finditer(r"(\d{1,2})\s*月\s*(\d{1,2})", t):
        out.add("%02d%02d" % (int(m.group(1)), int(m.group(2))))
    for m in re.finditer(r"(?<!\d)(\d{1,2})\s*[-/.]\s*(\d{1,2})(?!\d)", t):
        out.add("%02d%02d" % (int(m.group(1)), int(m.group(2))))
    for m in re.finditer(r"(?<!\d)(\d{1,2})\s*[日号]", t):
        # 只有「日」、没有「月」时无法归一成 MMDD，用 Dnn 占位参与同城比对
        # （「苏州A展16日开幕」vs「苏州B展16日开幕」——月未知但同城同日号仍可能同活动）
        out.add("D%02d" % int(m.group(1)))
    for m in re.finditer(r"(?<!\d)(\d{3,4})(?!\d)", t):
        d = m.group(1)
        if d.startswith("20"):      # 2026 这类年份不是会期
            continue
        out.add(("0" + d) if len(d) == 3 else d)
    return out


def place_date_signal(t1, t2):
    """地点 + 日期 同时相同，且剥掉地名日期后仍有 ≥2 字公共词 → 视为同一活动。"""
    shared_d = dates(t1) & dates(t2)
    if not shared_d:
        return ""
    shared_p = {p for p in PLACES if p in (t1 or "")} & {p for p in PLACES if p in (t2 or "")}
    if not shared_p:
        return ""
    x1, x2 = identity(t1), identity(t2)
    for p in shared_p:
        x1, x2 = x1.replace(p, ""), x2.replace(p, "")
    # 通用修饰词与事件后缀一样**不是**活动身份证据，一并剥离。
    # 不加这层会误报（2026-09-16 全量回归实测）：
    #   「鲲鹏计算产业峰会 9月17上海」vs「上海生物医药产业周 9月17」只剩「产业」就命中。
    for w in NOISE_WORDS:
        x1, x2 = x1.replace(w, ""), x2.replace(w, "")
    run = lcs(x1, x2)
    if len(run) >= 2 and cjk_count(run) >= 2:
        return (f"地点+日期相同（{'/'.join(sorted(shared_p))} "
                f"{'/'.join(sorted(shared_d))}）且公共子串「{run}」→ 疑似同一活动"
                f"（改标题措辞也会命中）")
    return ""


def similar(t1, t2, min_lcs=5, loose=True):
    """返回 (是否疑似重复, 原因)。

    loose=False 时只看"事件标识相同"这一条高置信信号。

    公共子串信号在 `identity()`（已剥日期与模板动词）上计算并判定，
    避免「…展16日开幕」这类纯模板串被当成事件证据。
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
    i1, i2 = identity(t1), identity(t2)
    run = lcs(i1, i2)
    if len(run) >= min_lcs and cjk_count(run) >= 4 and not is_datey(run):
        return True, f"公共子串「{run}」({len(run)}字，已排除日期与模板动词)"
    # 第三道信号只挂在宽松模式（= 单条预检「拦住一篇要发的稿子」），
    # 全量扫描不加，避免历史上同城同日的不同活动被批量翻出来刷屏。
    why3 = place_date_signal(t1, t2)
    if why3:
        return True, why3
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


def load_platform_notes():
    """平台侧笔记快照（logs/*platform_notes*.json）——**第二来源**。

    为什么必须加（2026-09-14 事故）：
    只比对 `publish_log.json` 会漏掉「发过但没写进 interval-guard 日志」的笔记。
    当天实测有两条踩中：
      - 「广东科普创新展18日开幕 可线上领票」在平台侧存在，但不在 publish_log 里
        → r4 险些二次发布；
      - 「华南精准医学AI论坛19日广州举办」同理 → s8 险些二次发布。
    平台快照是唯一权威的"平台上到底有什么"，所以查重必须双源比对。

    这些条目的日期不可靠（快照无 ts），故标 always=True，**绕过时间窗过滤** ——
    宁可多拦，不可漏拦。
    """
    out = []
    for p in sorted(glob.glob(os.path.join(DRAFT_DIR, "logs", "*platform_notes*.json"))):
        try:
            with open(p, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue
        seen_t = set()

        def walk(o):
            if isinstance(o, dict):
                t = o.get("title")
                if isinstance(t, str) and t.strip() and t.strip() not in seen_t:
                    seen_t.add(t.strip())
                    out.append({"title": t.strip(), "ts": "", "src": "platform",
                                "always": True})
                for v in o.values():
                    walk(v)
            elif isinstance(o, list):
                for v in o:
                    walk(v)

        walk(data)
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
    ap.add_argument("--class", dest="cls", choices=["a", "industry", "other"], default=None,
                    help="选题类别，决定查重回看窗口：a=当天内不得重复；industry=7 天；other=15 天")
    ap.add_argument("--min-lcs", type=int, default=5, help="公共子串判定阈值（默认 5 字）")
    ap.add_argument("--series", default="",
                    help="专题系列名（如 广东AI对接2026）：与该系列已发篇共用活动名属策划意图，"
                         "按 near_dup_tags 豁免「公共子串/事件标识」信号（标题完全相同仍拦）")
    ap.add_argument("--loose", action="store_true",
                    help="全量扫描时也启用「公共子串」信号（默认只比事件标识）")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if not os.path.isdir(DRAFT_DIR):
        print(f"稿件目录不存在：{DRAFT_DIR}", file=sys.stderr)
        return 2

    entries = load_log() + load_platform_notes()
    win_desc = ""
    if args.days > 0:
        cutoff = datetime.now() - timedelta(days=args.days)
        entries = [e for e in entries if e.get("always")
                   or (parse_ts(e["ts"]) or datetime.min) >= cutoff]
        win_desc = f"近 {args.days} 天"
    elif args.cls:
        wmode, n = CLASS_WINDOW[args.cls]
        if wmode == "same-day":
            today = datetime.now().date()
            entries = [e for e in entries if e.get("always")
                       or (parse_ts(e["ts"]) or datetime.min).date() == today]
            win_desc = "当天（A 类）"
        else:
            cutoff = datetime.now() - timedelta(days=n)
            entries = [e for e in entries if e.get("always")
                       or (parse_ts(e["ts"]) or datetime.min) >= cutoff]
            win_desc = f"近 {n} 天（{'行业类' if args.cls == 'industry' else '其他'}）"
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
        mine = norm(args.title)
        # 0) 系列豁免：同一专题系列内先发篇会在日志里，串行发布时后发篇必然与它
        #    共享「活动名」（2026-09-16 实例：B 批 b2/b5 与 b1 撞「AI对接大会」全 SKIP）。
        #    同系列已发条目（按 near_dup_tags 的 series 字段匹配）跳过模糊比对；
        #    但标题完全相同仍判重复（见循环内 mine 相等分支，2026-09-16 修）。
        exempt_norms = set()
        if args.series:
            tags_p = os.path.join(PATCH_ROOT, "state", "near_dup_tags.json")
            try:
                tags = json.load(open(tags_p, encoding="utf-8"))
            except Exception:
                tags = []
            for t in tags:
                if isinstance(t, dict) and (t.get("series") or "") == args.series:
                    exempt_norms.add(norm(t.get("title") or ""))
        # 1) 与**已发日志**比：完整判据（事件标识 + 公共子串）。
        #    这是「防重复发布」的核心 —— 平台上发过的选题不该再发。
        for e in entries:
            if exempt_norms and norm(e["title"]) in exempt_norms:
                # 系列豁免只放宽「活动名公共子串」信号；标题完全相同=真重复，必须拦。
                # （2026-09-16 事故：b3 已发布，补发链从 b2 续跑时被此豁免放行，
                #   平台上出现两条同名笔记 —— 同系列不是重复发布的挡箭牌。）
                if norm(e["title"]) == mine:
                    add(me, e, "标题与同系列已发篇完全相同（系列豁免不适用）")
                continue
            ok, why = similar(args.title, e["title"], args.min_lcs, loose=True)
            if ok:
                add(me, e, why)
        # 2) 与**同批其它待发稿**比：只判「标题完全相同」。
        #    不再用事件标识 —— 同一批次的系列专题（如一个大会拆 6 篇）事件标识
        #    天然相同，那是策划意图、不是重复；按事件标识判会让整批互相撞死。
        #    （2026-09-12 修：外滩大会 6 篇专题曾因此全批 FAIL）
        #    同名稿件里必有一条是**这条稿子自己**（排队前预检时标题已落盘），
        #    所以 len(exact) > 1 才说明批次内真有一篇重名。
        exact = [d for d in drafts if norm(d["title"]) == mine]
        if len(exact) > 1:
            add(me, exact[1], "标题与同批次另一篇完全相同")
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
        print(f"[dup] 日志 {len(entries)} 条{('（窗口：' + win_desc + '）') if win_desc else ''}"
              f" / 稿件 {len(drafts)} 篇；模式：{mode}"
              + (f"；公共子串阈值 ≥ {args.min_lcs} 字" if loose else ""))
        if args.cls:
            print(f"[dup] 类别＝{args.cls}；发布优先级 A 类 > 行业类 > 其他；"
                  f"窗口：A 类当天 / 行业类 7 天 / 其他 15 天内不得重复")
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
