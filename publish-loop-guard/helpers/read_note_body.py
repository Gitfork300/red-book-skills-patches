#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""读已发布笔记的**正文**（只读）—— 借 note-manager 的 `xsec_token` 走公开页。

为什么需要它：
  创作者中心桌面端**读不到已发布笔记的正文**（列表接口无正文字段、无编辑/预览入口、
  编辑页不回填正文）。要核验"已发内容里还有没有违规词"，只能走公开页。
  但公开页裸链会撞登录墙，**必须带上 `xsec_token`**；该 token 只有 note-manager
  接口返回，所以流程是：list_all_notes.py 拿 token → 本脚本读正文。

前置条件（缺一不可）：
  1. Chrome 在跑（9222）且**创作者中心已登录**
     —— 登录态一旦建立会落盘，重启 Chrome 仍有效（除非长期不用过期）
  2. 快照文件含 `xsec_token`（`list_all_notes.py --out` 产出的就有）

用法：
  python read_note_body.py --snapshot <notes_snapshot.json>            # 全部
  python read_note_body.py --snapshot <...> --only Mantis              # 标题含关键字
  python read_note_body.py --snapshot <...> --limit 6 --json
  python read_note_body.py --snapshot <...> --wording                  # 顺带跑用词预检
  python read_note_body.py --snapshot <...> --out bodies.json

退出码：
  0 = 全部读到，且（若 --wording）无 P0
  1 = 存在读不到的条目（含被熔断跳过的），或 --wording 命中 P0
  2 = 环境错误（Chrome 未起 / 登录失效 / 快照缺失）
  3 = 被风控守卫拦下（仍在冷却期，未执行）

⚠️ **风控限流（2026-09-12 实测，务必遵守）**：
  连续访问约 **30 个**公开页后，平台开始把后续请求**一律重定向到登录页**
  （落地 URL 变 `www.xiaohongshu.com/login?redirectPath=…`），此时本脚本会把该篇判为
  `ok=false`。这不是登录失效，是**限流**。实测：第 1–27 篇读到 24 篇；
  紧接着的第 28–54 篇 **27 篇全被挡**——当时脚本没有额度概念，白撞了 27 次。
  → 先用 `list_all_notes.py --wording` 扫标题（零成本），只对可疑篇目读正文。

✅ **本脚本已内建守卫**（规则见 `xhs-risk-guard` patch），不再靠人记：
  1. 启动时查冷却期 —— 上次被熔断过且未满 4 小时，直接退 3 不执行；
  2. 单次批次自动夹到**预算 25 篇**（`--limit` 填更大也会被夹，并告警）；
  3. 循环中**连续 3 篇 `ok=false` 立即熔断**，剩余篇目标为 `skipped`，
     当场停手（这正是上次白撞 27 篇要避免的）；
  4. 结束时把本次结果写入 `xhs-risk-guard/state/risk_state.json`。
  冷却期被拦时，确认平台已恢复才执行：
  `xhs-risk-guard/helpers/risk_state.py reset --kind read-body`

用法：
  python read_note_body.py --snapshot sj/*.json --since 2026-09-10 --wording
  python read_note_body.py --snapshot sj/*.json --only Mantis
  python read_note_body.py --snapshot sj/*.json --skip 25 --limit 25
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
PATCH_ROOT = os.path.normpath(os.path.join(HERE, ".."))
PATCHES_ROOT = os.path.normpath(os.path.join(PATCH_ROOT, ".."))
SKILLS_ROOT = os.path.normpath(os.path.join(PATCHES_ROOT, ".."))
SKILL_DIR = os.environ.get("XHS_SKILL_DIR") or os.path.join(SKILLS_ROOT, "red-book-skills")

HOST = os.environ.get("XHS_CDP_HOST", "127.0.0.1")
PORT = int(os.environ.get("XHS_CDP_PORT", "9222"))
CDP = f"http://{HOST}:{PORT}"

CHECK_WORDING = os.path.join(PATCHES_ROOT, "safe-wording-guard", "helpers", "check_wording.py")
RISK_GUARD_DIR = os.path.join(PATCHES_ROOT, "xhs-risk-guard", "helpers")

EXPLORE = "https://www.xiaohongshu.com/explore/{nid}?xsec_token={tok}&xsec_source=pc_user"

RISK_KIND = "read-body"


class _FallbackRisk:
    """找不到 xhs-risk-guard 时的本地降级 —— 保守默认，宁少勿多。"""

    BUDGET = 25
    STOP_AFTER = 3

    def can_start(self, kind):  # noqa: ARG002
        return True, "未加载到 xhs-risk-guard，使用内置保守默认（25 篇 / 连续 3 次熔断）"

    def budget(self, kind):  # noqa: ARG002
        return self.BUDGET

    def should_stop(self, kind, consecutive_fail):  # noqa: ARG002
        return consecutive_fail >= self.STOP_AFTER

    def record(self, *a, **k):  # noqa: ARG002
        return ""


def _risk():
    """加载风控守卫模块；失败则返回保守的降级对象（不影响主流程）。"""
    if os.path.isdir(RISK_GUARD_DIR) and RISK_GUARD_DIR not in sys.path:
        sys.path.insert(0, RISK_GUARD_DIR)
    try:
        import risk_state  # type: ignore
        return risk_state
    except Exception:  # noqa: BLE001
        return _FallbackRisk()

# 正文容器：优先 #detail-desc，再退到若干历史选择器，最后整页文本
EXTRACT_JS = r"""
(() => {
  const sels = ['#detail-desc', '.note-text', '.desc', '.note-content'];
  for (const s of sels) {
    const e = document.querySelector(s);
    if (e && e.innerText && e.innerText.trim()) {
      return JSON.stringify({sel: s, text: e.innerText});
    }
  }
  return JSON.stringify({sel: 'body', text: document.body.innerText});
})()
"""

TITLE_JS = r"""
(() => {
  const e = document.querySelector('#detail-title, .title, .note-title');
  return e && e.innerText ? e.innerText.trim() : '';
})()
"""


def _http_json(method: str, path: str):
    req = urllib.request.Request(CDP + path, method=method)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def _default_snapshot() -> str | None:
    """找最新的 notes_snapshot_*.json（依次在 workspace / 常见位置）。"""
    cands: list[str] = []
    env = os.environ.get("XHS_WORKSPACE")
    bases = [b for b in (env, os.getcwd()) if b]
    d = os.getcwd()
    for _ in range(6):
        bases.append(d)
        p = os.path.dirname(d)
        if p == d:
            break
        d = p
    for b in bases:
        cands += glob.glob(os.path.join(b, "xhs_publish", "notes_snapshot_*.json"))
    cands = [c for c in cands if not c.endswith(".bak")]
    return max(cands, key=os.path.getmtime) if cands else None


def read_one(send, nid: str, tok: str, delay: float, debug: bool = False):
    """返回 (body, title, landed_url)。"""
    url = EXPLORE.format(nid=nid, tok=urllib.parse.quote(tok))
    send("Page.navigate", {"url": url})
    time.sleep(delay)
    out = send("Runtime.evaluate", {"expression": "location.href", "returnByValue": True})
    landed = out.get("result", {}).get("result", {}).get("value") or ""
    out = send("Runtime.evaluate", {"expression": EXTRACT_JS, "returnByValue": True})
    raw = out.get("result", {}).get("result", {}).get("value") or "{}"
    try:
        got = json.loads(raw)
    except Exception:  # noqa: BLE001
        got = {"sel": "?", "text": ""}
    out = send("Runtime.evaluate", {"expression": TITLE_JS, "returnByValue": True})
    title = out.get("result", {}).get("result", {}).get("value") or ""
    if debug:
        print(f"    [debug] selector={got.get('sel')} landed={landed[:80]}", file=sys.stderr)
    return got.get("text", ""), title, landed


def wording_hits(title: str, body: str) -> str:
    """跑 safe-wording-guard 的预检。返回输出文本（空串=无问题）。"""
    if not os.path.isfile(CHECK_WORDING):
        return ""
    tmp = os.path.join(os.path.dirname(CHECK_WORDING), "_body_tmp.txt")
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(body)
        cmd = [sys.executable, CHECK_WORDING, "--file", tmp]
        if title:
            cmd += ["--title", title]
        r = subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        return "" if r.returncode == 0 else ((r.stdout or "") + (r.stderr or "")).strip()
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass


def main() -> int:
    ap = argparse.ArgumentParser(description="读已发布笔记正文（只读，走公开页+xsec_token）")
    ap.add_argument("--snapshot", help="含 id/xsec_token 的快照 JSON（默认取最新 notes_snapshot_*.json）")
    ap.add_argument("--only", default="", help="只处理标题含该关键字的条目（可多次传，逗号分隔）")
    ap.add_argument("--since", default="", help="只处理该日期（含）之后发布的，如 2026-09-01")
    ap.add_argument("--skip", type=int, default=0, help="跳过前 N 条（配合 --limit 分批用）")
    ap.add_argument("--limit", type=int, default=0,
                    help="最多处理 N 条（默认取风控预算 25；填更大会被夹到预算）")
    ap.add_argument("--delay", type=float, default=8.0, help="每篇导航后等待秒数（默认 8）")
    ap.add_argument("--wording", action="store_true", help="顺带跑用词预检")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--out", help="把结果写到该 JSON 路径")
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args()

    risk = _risk()

    # ① 冷却期检查：上次被熔断过且未满冷却时间，直接不跑（避免重复加重风控）
    can, why = risk.can_start(RISK_KIND)
    if not can:
        print(f"[body] !! 被风控守卫拦下，本次不执行 —— {why}", file=sys.stderr)
        print("[body]    确认平台已恢复（换过网络/隔了更久）才执行：", file=sys.stderr)
        print(f"[body]    {os.path.join(RISK_GUARD_DIR, 'risk_state.py')} reset --kind {RISK_KIND}",
              file=sys.stderr)
        return 3

    snap = args.snapshot or _default_snapshot()
    if not snap or not os.path.isfile(snap):
        print("[body] !! 找不到快照 JSON；先跑 list_all_notes.py --out <path>", file=sys.stderr)
        return 2
    notes = json.load(open(snap, encoding="utf-8"))
    notes = [n for n in notes if n.get("id") and n.get("xsec_token")]

    if args.only:
        keys = [k.strip() for k in args.only.split(",") if k.strip()]
        notes = [n for n in notes if any(k in (n.get("title") or "") for k in keys)]
    if args.since:
        notes = [n for n in notes if (n.get("time") or "") >= args.since]
    if args.skip > 0:
        notes = notes[args.skip:]

    # ② 批次夹到风控预算内（--limit 填更大也会被夹，并明确告警）
    cap = risk.budget(RISK_KIND)
    want = args.limit if args.limit > 0 else 0
    if cap > 0 and (want <= 0 or want > cap):
        if want > cap:
            print(f"[body] !! --limit {want} 超出单次风控预算 {cap}，已夹到 {cap} 篇", file=sys.stderr)
        elif want == 0:
            print(f"[body]    未指定 --limit，按风控预算取前 {cap} 篇", file=sys.stderr)
        want = cap
    if want > 0:
        notes = notes[:want]
    if not notes:
        print("[body] !! 过滤后没有可处理条目（快照里要有 xsec_token）", file=sys.stderr)
        return 2

    _ensure_venv_runtime()
    from websockets.sync.client import connect

    try:
        tab = _http_json("PUT", "/json/new?" + urllib.parse.quote("about:blank", safe=""))
    except Exception as exc:  # noqa: BLE001
        print(f"[body] !! 连不上 Chrome 调试端口 {CDP}（{exc}）", file=sys.stderr)
        return 2

    results: list[dict] = []
    stop_reason = ""
    consecutive_fail = 0
    try:
        with connect(tab["webSocketDebuggerUrl"], max_size=32 * 1024 * 1024) as ws:
            cid = [0]

            def send(method, params=None):
                cid[0] += 1
                ws.send(json.dumps({"id": cid[0], "method": method, "params": params or {}}))
                while True:
                    m = json.loads(ws.recv())
                    if m.get("id") == cid[0]:
                        return m

            send("Page.enable")
            for i, n in enumerate(notes, 1):
                body, page_title, landed = read_one(
                    send, n["id"], n["xsec_token"], args.delay, args.debug
                )
                blocked = ("login" in landed.lower()) or ("404" in landed)
                rec = {
                    "id": n["id"],
                    "title": n.get("title") or page_title,
                    "time": n.get("time", ""),
                    "ok": bool(body.strip()) and not blocked,
                    "landed": landed,
                    "body_len": len(body),
                    "body": body,
                }
                if args.wording and rec["ok"]:
                    hit = wording_hits(rec["title"], body)
                    rec["wording_hit"] = hit
                    rec["wording_ok"] = not hit
                results.append(rec)
                flag = "OK " if rec["ok"] else "!! "
                print(f"[body] {i}/{len(notes)} [{flag}] {rec['title'][:34]}  {rec['body_len']}字",
                      file=sys.stderr)

                # ③ 连续失败熔断：撞到限流就立刻停手，别把剩余篇目硬跑完
                if rec["ok"]:
                    consecutive_fail = 0
                    continue
                consecutive_fail += 1
                if not risk.should_stop(RISK_KIND, consecutive_fail):
                    continue
                stop_reason = "consecutive-fail"
                rest = notes[i:]
                print(f"[body] !! 连续 {consecutive_fail} 篇被挡 —— 判定触发读取限流，"
                      f"自动停手（风控守卫）", file=sys.stderr)
                if rest:
                    print(f"[body]    剩余 {len(rest)} 篇未读，已标 skipped。**不要立刻重试** —— "
                          f"继续请求只会加重风控；数小时后再跑。", file=sys.stderr)
                for m in rest:
                    results.append({
                        "id": m["id"],
                        "title": m.get("title") or "",
                        "time": m.get("time", ""),
                        "ok": False,
                        "skipped": True,
                        "reason": "risk-guard-stopped",
                        "landed": "",
                        "body_len": 0,
                        "body": "",
                    })
                break
    finally:
        try:
            _http_json("GET", "/json/close/" + str(tab.get("id")))
        except Exception:  # noqa: BLE001
            pass

    bad = [r for r in results if not r["ok"]]
    wbad = [r for r in results if r.get("wording_ok") is False]
    skipped = [r for r in bad if r.get("skipped")]

    # ④ 把本次结果写进风控守卫 —— 下次开批前 can_start() 会据此拦冷却
    risk.record(RISK_KIND,
                ok=len(results) - len(bad),
                fail=len(bad) - len(skipped),
                stopped=stop_reason,
                total=len(notes))

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(results, fh, ensure_ascii=False, indent=2)

    if args.json:
        print(json.dumps({"total": len(results), "unreadable": bad,
                          "stopped": stop_reason, "skipped": len(skipped),
                          "wording_p0": [{"title": r["title"], "hit": r["wording_hit"]} for r in wbad],
                          "rows": results}, ensure_ascii=False, indent=2))
    else:
        print(f"[body] 共 {len(results)} 篇；读到 {len(results) - len(bad)} 篇，"
              f"读不到 {len(bad) - len(skipped)} 篇，熔断跳过 {len(skipped)} 篇")
        for r in bad:
            if r.get("skipped"):
                continue
            print(f"  !! 读不到: {r['title']}  (landed={r['landed'][:70]})")
        if skipped:
            print(f"[body] !! 风控熔断：{len(skipped)} 篇未读（已跳过，未发起请求）")
            print(f"[body]    下次开批前先查冷却："
                  f"{os.path.join(RISK_GUARD_DIR, 'risk_state.py')} check --kind {RISK_KIND}")
        if args.wording:
            if wbad:
                print(f"[body] !! 用词 P0 {len(wbad)} 篇：")
                for r in wbad:
                    print(f"  - {r['time']} {r['title']}")
                    for line in r["wording_hit"].splitlines():
                        if any(k in line for k in ("P0", "P1", "命中", "违规")):
                            print("      " + line.strip())
            else:
                print("[body] 用词预检：无 P0")

    return 1 if (bad or wbad) else 0


def _ensure_venv_runtime() -> None:
    """websockets 装在 skill 的 .venv 里；解释器不对就用 .venv 重跑一遍。"""
    try:
        import websockets  # noqa: F401
        return
    except Exception:
        pass
    venv_py = os.path.join(SKILL_DIR, ".venv", "Scripts", "python.exe")
    if not os.path.isfile(venv_py):
        venv_py = os.path.join(SKILL_DIR, ".venv", "bin", "python")
    if os.path.isfile(venv_py) and os.path.abspath(sys.executable) != os.path.abspath(venv_py):
        r = subprocess.run([venv_py, os.path.abspath(__file__)] + sys.argv[1:])
        sys.exit(r.returncode)
    raise SystemExit("找不到运行环境：需要 websockets（装在 skill 的 .venv 内）")


if __name__ == "__main__":
    sys.exit(main())
