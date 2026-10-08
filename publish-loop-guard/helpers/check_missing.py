"""漏发复核 —— 对比「稿件目录」与「发布日志」，找出该发却没发的文章。

为什么要独立成脚本：批量发布是长流程（1~2 小时），中途失败、进程被杀、间隔
守卫超时都会造成静默漏发；而 agent 对"我发了几篇"的印象不可靠。
把判定做成可重复运行的脚本，才能每 30 分钟无脑复核一次。

判定链：
  1) 扫描稿件标题文件（*_title.txt / *_title_rev.txt）
  2) 与 publish_log.json 的标题精确匹配 —— 命中即视为已发
  3) 排除三类「本来就不该算漏发」的 key：
     - state/inflight.json    当前队列在发 / 待发
     - state/abandoned.json   明确作废、口径变更、不再发
     - timeliness-window/state/pending_pool.json  待发池（时效或资格不合格，故意压着）
  4) 剩下的即「疑似漏发」候选
  5) 加 --verify 时对候选跑 verify-note，确认平台确实没有 —— 才是真漏发

⚠️ 候选 ≠ 直接重发。确认漏发后必须**重新走完整预检**（时效 → 资格 → 用词/字数 → 封面），
   内容不合规的先改稿，再按 8~12 分钟随机间隔补发。

用法：
  check_missing.py                     # 最近 2 天的稿件，不加浏览器
  check_missing.py --days 7            # 放宽到 7 天
  check_missing.py --keys ex0911_4,hk0911a_1   # 只查指定 key（队列场景最准）
  check_missing.py --verify            # 对候选跑平台核验（需要 Chrome + 9222）
  check_missing.py --json              # 机器可读

范围口径（2026-09-11 定）：
  **只关注最近几日**。例行复核默认扫最近 2 天改动的稿件，不做全账号体检。
  平台侧核验只读 note-manager 第一页（见 recent_published.py），不翻页。

退出码：
  0 = 无漏发
  1 = 有漏发（或未核验的候选，需要人工/agent 处置）
  2 = 参数或环境错误

环境变量：
  XHS_WORKSPACE      工作区根目录（换机器必设），默认 ~/xhs-workspace
  XHS_DRAFT_DIR      稿件目录，默认 <workspace>/xhs_publish
  XHS_INTERVAL_LOG   发布日志，默认 <patches>/publish-interval-guard/state/publish_log.json
  XHS_PENDING_POOL   待发池，默认 <patches>/timeliness-window/state/pending_pool.json
  XHS_SKILL_DIR      运行层目录（--verify 用），默认本仓库 runtime/
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
PATCH_ROOT = os.path.normpath(os.path.join(HERE, ".."))          # <patch>/publish-loop-guard
PATCHES_ROOT = os.path.normpath(os.path.join(PATCH_ROOT, ".."))  # <skills>/red-book-skills-patches
SKILLS_ROOT = os.path.normpath(os.path.join(PATCHES_ROOT, ".."))

WS_DEFAULT = os.environ.get("XHS_WORKSPACE") or os.path.expanduser("~/xhs-workspace")
DRAFT_DIR = os.environ.get("XHS_DRAFT_DIR") or os.path.join(WS_DEFAULT, "xhs_publish")
LOG_PATH = os.environ.get("XHS_INTERVAL_LOG") or os.path.join(
    PATCHES_ROOT, "publish-interval-guard", "state", "publish_log.json"
)
POOL_PATH = os.environ.get("XHS_PENDING_POOL") or os.path.join(
    PATCHES_ROOT, "timeliness-window", "state", "pending_pool.json"
)
SKILL_DIR = (
    os.environ.get("XHS_SKILL_DIR")
    or os.environ.get("RED_BOOK_SKILLS_ROOT")
    or os.path.join(PATCHES_ROOT, "runtime")
)

INFLIGHT = os.path.join(PATCH_ROOT, "state", "inflight.json")
ABANDONED = os.path.join(PATCH_ROOT, "state", "abandoned.json")

TITLE_RE = re.compile(r"^(?P<key>.+?)_title(?:_rev)?\.txt$", re.IGNORECASE)


def _norm(s):
    if not s:
        return ""
    s = s.replace("\u3000", " ").replace("\ufeff", "").replace("\u200b", "")
    return " ".join(s.split()).strip()


def _read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _load_keys(path, field="keys"):
    data = _read_json(path, {})
    if isinstance(data, list):
        return {str(x) for x in data}
    if isinstance(data, dict):
        vals = data.get(field) or data.get("items") or []
        out = set()
        for v in vals:
            if isinstance(v, str):
                out.add(v)
            elif isinstance(v, dict):
                k = v.get("key") or v.get("name")
                if k:
                    out.add(str(k))
        return out
    return set()


def _load_keys_multi(path, fields):
    out = set()
    for f in fields:
        out |= _load_keys(path, f)
    return out


def _published_titles():
    data = _read_json(LOG_PATH, [])
    titles = set()
    if isinstance(data, list):
        for r in data:
            if isinstance(r, dict):
                t = _norm(r.get("title"))
                if t:
                    titles.add(t)
    return titles


def _load_files(path):
    data = _read_json(path, {})
    vals = data.get("files", []) if isinstance(data, dict) else []
    out = set()
    for v in vals:
        if isinstance(v, str):
            out.add(v.lower())
        elif isinstance(v, dict) and v.get("file"):
            out.add(str(v["file"]).lower())
    return out


def _scan_titles(scan_dir, days, keys, skip_files=None):
    found = []
    skip_files = skip_files or set()
    if not os.path.isdir(scan_dir):
        return found, f"稿件目录不存在: {scan_dir}"
    now = time.time()
    want = {k.strip() for k in keys if k.strip()} if keys else None
    for name in sorted(os.listdir(scan_dir)):
        m = TITLE_RE.match(name)
        if not m:
            continue
        if name.lower() in skip_files:
            continue
        key = m.group("key")
        path = os.path.join(scan_dir, name)
        if want is not None and key not in want:
            continue
        if want is None and days is not None:
            try:
                age_days = (now - os.path.getmtime(path)) / 86400.0
            except OSError:
                continue
            if age_days > days:
                continue
        try:
            with open(path, encoding="utf-8") as f:
                title = _norm(f.read())
        except Exception:
            continue
        if not title:
            continue
        found.append({"key": key, "title": title, "path": path})
    return found, None


def _verify_on_platform(title, timeout=90):
    """返回 True/False/None（None = 无法核验）。"""
    py = os.environ.get("RED_BOOK_SKILLS_PYTHON")
    if not py:
        candidates = (
            os.path.join(PATCHES_ROOT, ".venv", "Scripts", "python.exe"),
            os.path.join(PATCHES_ROOT, ".venv", "bin", "python"),
        )
        py = next((candidate for candidate in candidates if os.path.isfile(candidate)), sys.executable)
    try:
        r = subprocess.run(
            [py, "scripts/cdp_publish.py", "verify-note",
             "--title", title, "--timeout-seconds", "60"],
            cwd=SKILL_DIR, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
        )
    except Exception:
        return None
    blob = (r.stdout or "").lower()
    if '"found": true' in blob or '"found":true' in blob:
        return True
    if '"found": false' in blob or '"found":false' in blob:
        return False
    return None


def run(scan_dir, days, keys, verify, verify_limit):
    published = _published_titles()
    inflight = _load_keys(INFLIGHT)
    abandoned = _load_keys_multi(ABANDONED, ["keys", "archived"])
    pool = _load_keys(POOL_PATH)
    # 待发池里 key 可能缺失（老条目），再按名字兜底
    pool_data = _read_json(POOL_PATH, {})
    pool_titles = set()
    if isinstance(pool_data, dict):
        for it in pool_data.get("items", []) or []:
            if isinstance(it, dict):
                pool_titles.add(_norm(it.get("name")))

    drafts, err = _scan_titles(scan_dir, days, keys, _load_files(ABANDONED))
    if err:
        return 2, {"error": err}, err

    excluded, candidates = [], []
    for d in drafts:
        reason = None
        if _norm(d["title"]) in published:
            reason = "published"
        elif d["key"] in inflight:
            reason = "inflight"
        elif d["key"] in abandoned:
            reason = "abandoned"
        elif d["key"] in pool or _norm(d["title"]) in pool_titles:
            reason = "pending_pool"
        if reason in ("published", "inflight", "abandoned", "pending_pool"):
            excluded.append(dict(d, why=reason))
        else:
            candidates.append(dict(d, why="NO_LOG"))

    verified = []
    if verify and candidates:
        for i, c in enumerate(candidates):
            if verify_limit and i >= verify_limit:
                c["platform"] = "skipped"
                verified.append(c)
                continue
            res = _verify_on_platform(c["title"])
            c["platform"] = {True: "found", False: "absent", None: "unknown"}[res]
            verified.append(c)
        candidates = verified

    missing = [c for c in candidates
               if (not verify) or c.get("platform") == "absent"]
    confirmed_published = [c for c in candidates if c.get("platform") == "found"]

    result = {
        "draft_count": len(drafts),
        "published_log_count": len(published),
        "excluded": excluded,
        "candidates": candidates,
        "missing": missing,
        "verified_published_but_missing_log": confirmed_published,
        "scan_dir": scan_dir,
        "log_path": LOG_PATH,
    }
    return (1 if candidates else 0), result, None


def main():
    ap = argparse.ArgumentParser(description="小红书漏发复核")
    ap.add_argument("--scan", default=DRAFT_DIR)
    ap.add_argument("--days", type=float, default=2.0,
                    help="只扫描最近 N 天内改动过的稿件（默认 2 天）")
    ap.add_argument("--keys", default="",
                    help="只查这些 key，逗号分隔；给定后忽略 --days")
    ap.add_argument("--verify", action="store_true",
                    help="对候选跑 verify-note（需 Chrome + 9222）")
    ap.add_argument("--verify-limit", type=int, default=0)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    keys = [k for k in args.keys.split(",")] if args.keys else []
    rc, result, err = run(args.scan, None if keys else args.days, keys,
                          args.verify, args.verify_limit)

    if err:
        print(f"[missing] !! {err}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return rc

    when = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[missing] {when} 扫描 {result['scan_dir']}")
    print(f"[missing] 稿件 {result['draft_count']} 篇；发布日志 {result['published_log_count']} 条")
    if result["excluded"]:
        by_why = {}
        for e in result["excluded"]:
            by_why.setdefault(e["why"], []).append(e["key"])
        for why, ks in sorted(by_why.items()):
            label = {"published": "已发", "inflight": "在队",
                     "abandoned": "作废", "pending_pool": "待发池"}.get(why, why)
            print(f"[missing]   排除·{label}({len(ks)}): {', '.join(sorted(ks))}")

    if not result["candidates"]:
        print("[missing] OK 无漏发")
        return 0

    print(f"[missing] !! 疑似漏发 {len(result['candidates'])} 篇：")
    for c in result["candidates"]:
        plat = c.get("platform")
        tail = "" if plat is None else f" | 平台={plat}"
        print(f"  - [{c['key']}] {c['title']}{tail}")
        print(f"      稿件: {c['path']}")

    if result["verified_published_but_missing_log"]:
        print("[missing] 注意：以下候选平台已存在，只是日志缺记录，建议补 record：")
        for c in result["verified_published_but_missing_log"]:
            print(f"  - [{c['key']}] {c['title']}")

    if not args.verify:
        print("[missing] 提示：加 --verify 可确认平台是否真的缺失（需要浏览器）")
    print("[missing] 处置：确认漏发后必须重跑完整预检（时效/资格/用词/字数/封面），"
          "改稿合规后按 8~12 分钟随机间隔补发；不合规的进待发池")
    return 1


if __name__ == "__main__":
    sys.exit(main())
