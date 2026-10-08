#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全量笔记清单（只读）—— 把创作者中心笔记管理页**滚到底**，汇总所有页。

与 recent_published.py 的分工：
  - recent_published.py：只读**第一页**（最近 10 条），用于高频漏发复核，快
  - list_all_notes.py  ：**滚到底**拿全量，用于合规审计（下架核对 / 状态分布 / 标题复扫）

为什么必须"驱动页面滚动"，而不能直接调接口：
  - 列表接口 `GET /api/galaxy/v2/creator/note/user/posted?tab=0&page=N`（0 基、每页 10）
  - 该接口需要页面自身生成的签名请求头；在页面里直接 `fetch` 会返回 406
  - 所以只能滚页面、由页面发请求，我们从 CDP 网络响应里收集
  - 页签（全部/已发布/审核中/未通过）是**本地过滤**，不重发请求 → 只看 tab=0 即可，
    状态从每条记录的 `tab_status` 读

实现要点（2026-09-12 踩坑记录）：
  - 必须复用主脚本的 `XiaohongshuPublisher`，不要自己手搓 CDP。
    自搓版本把 `Network.enable` 的参数写成 `maxPostSize`（正确名是
    `maxPostDataSize`），导致网络域根本没启用、一个事件都收不到，
    现象是"页面渲染正常但接口完全没有发出请求"，极易误判成风控。
  - 复用 publisher 还自带 `_event_queue` 缓冲：`_send` 等待响应期间收到的
    事件不会丢，滚动与收集可以安全交替。

用法：
  python list_all_notes.py                 # 全量清单 + 状态分布
  python list_all_notes.py --json          # 机器可读
  python list_all_notes.py --out a.json    # 落盘
  python list_all_notes.py --wording       # 顺带用 check_wording 扫标题（P0）
  python list_all_notes.py --days 3        # 只看最近 3 天

退出码：
  0 = 正常（无非「已发布」条目；若 --wording 则标题也无 P0）
  1 = 存在非「已发布」条目，或 --wording 命中 P0
  2 = 环境错误（Chrome 未起 / 登录失效 / 依赖缺失）

环境变量：
  XHS_SKILL_DIR   运行层目录，默认本仓库 runtime/
  XHS_CDP_HOST / XHS_CDP_PORT   默认 127.0.0.1 / 9222
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
PATCH_ROOT = os.path.normpath(os.path.join(HERE, ".."))          # <patch>/publish-loop-guard
PATCHES_ROOT = os.path.normpath(os.path.join(PATCH_ROOT, ".."))  # <skills>/red-book-skills-patches
SKILLS_ROOT = os.path.normpath(os.path.join(PATCHES_ROOT, ".."))

SKILL_DIR = (
    os.environ.get("XHS_SKILL_DIR")
    or os.environ.get("RED_BOOK_SKILLS_ROOT")
    or os.path.join(PATCHES_ROOT, "runtime")
)
SKILL_SCRIPTS = os.path.join(SKILL_DIR, "scripts")

HOST = os.environ.get("XHS_CDP_HOST", "127.0.0.1")
PORT = int(os.environ.get("XHS_CDP_PORT", "9222"))

PAGE_URL = "https://creator.xiaohongshu.com/new/note-manager?source=official"
API_PATH = "/api/galaxy/v2/creator/note/user/posted"

STATUS = {1: "已发布", 0: "审核中", 2: "审核中", 3: "未通过", -1: "未通过"}

# 滚「内容容器」（笔记列表在自己可滚的 div 里，滚 window 无效）
SCROLL_JS = r"""
(() => {
  let best = null;
  document.querySelectorAll('*').forEach(e => {
    if (e.scrollHeight > e.clientHeight + 40 && e.clientHeight > 150) {
      if (!best || e.clientHeight > best.clientHeight) best = e;
    }
  });
  const el = best || document.scrollingElement;
  el.scrollTop = el.scrollTop + Math.max(200, el.clientHeight * 0.9);
  return {a: el.scrollTop, sh: el.scrollHeight, ch: el.clientHeight};
})()
"""


def _ensure_venv_runtime() -> None:
    """cdp_publish 依赖装在 Patch 的 .venv 里；用错解释器就换过去重跑一遍。

    注意：Windows 上 os.execv 会丢掉父 shell 已接管的标准输出，
    表现为"退出码 0 但没有任何输出"，所以这里用 subprocess 转发。
    """
    if SKILL_SCRIPTS not in sys.path:
        sys.path.insert(0, SKILL_SCRIPTS)
    try:
        import cdp_publish  # noqa: F401
        return
    except Exception:
        pass
    venv_py = os.environ.get("RED_BOOK_SKILLS_PYTHON")
    if not venv_py:
        candidates = (
            os.path.join(PATCHES_ROOT, ".venv", "Scripts", "python.exe"),
            os.path.join(PATCHES_ROOT, ".venv", "bin", "python"),
        )
        venv_py = next((candidate for candidate in candidates if os.path.isfile(candidate)), sys.executable)
    if os.path.isfile(venv_py) and os.path.abspath(sys.executable) != os.path.abspath(venv_py):
        r = subprocess.run([venv_py, os.path.abspath(__file__)] + sys.argv[1:])
        sys.exit(r.returncode)
    raise SystemExit("cdp_publish 导入失败；请先运行 tools/setup_runtime.py")


def fetch_all_notes(max_scrolls: int = 40, quiet: bool = False) -> list[dict]:
    """滚到底收集全部笔记。返回 [{id,title,status,time,xsec_token}]。"""
    _ensure_venv_runtime()
    from cdp_publish import XiaohongshuPublisher  # noqa: E402

    pub = XiaohongshuPublisher(host=HOST, port=PORT)
    found: dict[str, dict] = {}
    urls: dict[str, str] = {}
    http_seen: list[int] = []

    try:
        pub.connect(reuse_existing_tab=True)
    except Exception as exc:  # noqa: BLE001
        print(f"[list-all] !! 连不上 Chrome 调试端口 {HOST}:{PORT} 或登录失效（{exc}）",
              file=sys.stderr)
        return []

    def collect(seconds: float) -> None:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            msg = pub._receive_cdp_message(min(1.0, max(0.1, deadline - time.monotonic())))
            if not msg:
                continue
            method = msg.get("method")
            p = msg.get("params", {})
            if method == "Network.requestWillBeSent":
                rid = p.get("requestId")
                if isinstance(rid, str):
                    urls[rid] = str(p.get("request", {}).get("url", ""))
                continue
            if method != "Network.responseReceived":
                continue
            rid = p.get("requestId")
            if not isinstance(rid, str) or API_PATH not in urls.get(rid, ""):
                continue
            st = int(p.get("response", {}).get("status") or 0)
            http_seen.append(st)
            if st != 200:
                continue
            try:
                rb = pub._get_response_body_with_retry(rid)
            except Exception:  # noqa: BLE001
                continue
            body = str(rb.get("body") or "")
            if rb.get("base64Encoded"):
                body = base64.b64decode(body).decode("utf-8", errors="replace")
            try:
                payload = json.loads(body)
            except Exception:  # noqa: BLE001
                continue
            data = payload.get("data") if isinstance(payload, dict) else None
            for n in (data or {}).get("notes", []) or []:
                if not isinstance(n, dict):
                    continue
                nid = n.get("id")
                if nid and nid not in found:
                    found[nid] = {
                        "id": nid,
                        "title": n.get("display_title") or n.get("title") or "",
                        "status": STATUS.get(n.get("tab_status"), "?"),
                        "time": n.get("time", ""),
                        "xsec_token": n.get("xsec_token", ""),
                    }

    try:
        pub._send("Page.enable")
        # 参数名必须是 maxPostDataSize（写成 maxPostSize 会静默失效）
        pub._send("Network.enable", {"maxPostDataSize": 65536})

        # 首次导航可能撞上 HTTP 406（页面在完成动态安全握手，
        # 主脚本 _capture_note_manager_notes 的注释同样记载了这一点）→ 重试几次。
        for attempt in range(3):
            pub._send("Page.navigate", {"url": PAGE_URL})
            collect(10)
            if found:
                break
            if not quiet:
                print(f"[list-all]   首次导航未取到数据，重试 {attempt + 1}/3", file=sys.stderr)

        if not found:
            if not quiet:
                try:
                    where = pub._evaluate("location.href")
                except Exception:  # noqa: BLE001
                    where = "?"
                print(f"[list-all]   落地 URL：{where}", file=sys.stderr)
                print(f"[list-all]   列表接口 HTTP 状态：{http_seen or '（完全没有发出请求）'}"
                      f"（收到网络事件 {len(urls)} 个）", file=sys.stderr)
            return []

        stagnant = 0
        for i in range(max(1, max_scrolls)):
            before = len(found)
            try:
                pub._evaluate(SCROLL_JS)
            except Exception:  # noqa: BLE001
                pass
            collect(2.5)
            stagnant = stagnant + 1 if len(found) == before else 0
            if stagnant >= 4:
                break
            if not quiet and (i % 5 == 4):
                print(f"[list-all]   滚动 {i + 1} 次，已收 {len(found)} 条", file=sys.stderr)
    finally:
        try:
            pub.disconnect()
        except Exception:  # noqa: BLE001
            pass

    return sorted(found.values(), key=lambda x: x.get("time", ""), reverse=True)


def _within_days(ts: str, days: float) -> bool:
    if not ts or days <= 0:
        return True
    try:
        return datetime.now() - datetime.strptime(ts.strip(), "%Y-%m-%d %H:%M") <= timedelta(days=days)
    except Exception:  # noqa: BLE001
        return True


def title_wording_hits(notes: list[dict]) -> list[tuple[dict, str]]:
    """用 safe-wording-guard 的 check_wording.py 扫标题，返回命中 P0 的条目。"""
    chk = os.path.join(PATCHES_ROOT, "safe-wording-guard", "helpers", "check_wording.py")
    if not os.path.isfile(chk):
        return []
    hits = []
    for n in notes:
        r = subprocess.run([sys.executable, chk, "--title", n["title"]],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode != 0:
            hits.append((n, (r.stdout or "").strip()))
    return hits


def main() -> int:
    ap = argparse.ArgumentParser(description="全量笔记清单（只读，滚动到底）")
    ap.add_argument("--days", type=float, default=0.0, help="只保留最近 N 天（默认 0 = 全部）")
    ap.add_argument("--status", default="", help="只看某状态：已发布/审核中/未通过")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--out", help="把全量清单写到该路径")
    ap.add_argument("--wording", action="store_true", help="顺带扫标题用词（P0）")
    ap.add_argument("--max-scrolls", type=int, default=40)
    args = ap.parse_args()

    notes = fetch_all_notes(max_scrolls=args.max_scrolls)
    if not notes:
        print("[list-all] !! 未取到任何笔记：确认 Chrome 在跑（9222）且登录有效", file=sys.stderr)
        return 2

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(notes, fh, ensure_ascii=False, indent=2)

    shown = [n for n in notes if _within_days(n["time"], args.days)]
    if args.status:
        shown = [n for n in shown if n["status"] == args.status]

    dist: dict[str, int] = {}
    for n in notes:
        dist[n["status"]] = dist.get(n["status"], 0) + 1
    abnormal = [n for n in notes if n["status"] != "已发布"]

    wording = title_wording_hits(shown) if args.wording else []

    if args.json:
        print(json.dumps({
            "total": len(notes), "shown": len(shown),
            "status_dist": dist, "abnormal": abnormal,
            "wording_p0": [{"time": n["time"], "title": n["title"], "hit": h} for n, h in wording],
            "rows": shown,
        }, ensure_ascii=False, indent=2))
    else:
        scope = f"最近 {args.days:g} 天" if args.days > 0 else "全部"
        print(f"[list-all] 全量 {len(notes)} 条；{scope}命中 {len(shown)} 条")
        print(f"[list-all] 状态分布：" + "、".join(f"{k} {v}" for k, v in sorted(dist.items())))
        print(f"[list-all] 时间范围：{notes[-1]['time']} ~ {notes[0]['time']}")
        for n in shown:
            print(f"  {n['time']}\t{n['status']}\t{n['title']}")
        if abnormal:
            print(f"[list-all] !! 非「已发布」{len(abnormal)} 条：")
            for n in abnormal:
                print(f"  - [{n['status']}] {n['time']} {n['title']}")
        if args.wording:
            if wording:
                print(f"[list-all] !! 标题 P0 {len(wording)} 条：")
                for n, h in wording:
                    print(f"  - {n['time']} {n['title']}\n      {h.splitlines()[-1] if h else ''}")
            else:
                print("[list-all] 标题用词扫描：无 P0")

    if args.out:
        print(f"[list-all] 已写入 {args.out}", file=sys.stderr)

    return 1 if (abnormal or wording) else 0


if __name__ == "__main__":
    sys.exit(main())
