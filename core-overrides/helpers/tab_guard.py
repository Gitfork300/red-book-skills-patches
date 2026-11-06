# -*- coding: utf-8 -*-
"""页签守卫：全局 page tab 超阈值时自动关闭最早的残留批（B-057；2026-10-25 升级全局）。

背景（B-057，2026-10-16 登记）：`cdp_publish._find_or_create_tab` 每次发布都
`PUT /json/new` 建新 tab，全脚本无 `/json/close` 调用 → 一天堆 30+ 个 page tab，
吃 ~2GB 内存并助推 Chrome 崩溃（B-056）。

**自动路径**：`cdp_publish.py` 已在 `_find_or_create_tab` 里内建守卫
（`TAB_GUARD_MAX=10` 全局），每次建 tab 前自动执行，无需手工干预。
**本脚本**是它的独立版，用于：收口清理、巡检、发布链之外的人工处置、验证效果。

用户铁律（2026-10-25）：「任何阶段的浏览器页签都不要超过 10，避免卡顿」。
  9222 = 评论实例（profile=comment，www.xiaohongshu.com）
  9333 = 发布实例（profile=default，creator.xiaohongshu.com）

规则（与内建守卫完全一致，默认双实例全局口径）：
  - 9222 + 9333 合计 **≥ 10** → 触发；回收至 **≤ 9**（给新建 tab 留余量）；
  - 每实例保留最新 N 个（9333=3：发布/verify 在用的 tab 永远最新；9222=1：
    notification 着陆页），只回收保留数之后的旧页；`/json/list` 顺序 = 创建顺序；
  - **受保护不关**：`creator.xiaohongshu.com/login`（可能正用于人工扫码）；
  - 每实例至少留 1 个 page（关掉最后一个 tab 会导致 Chrome 整体退出）；
  - 默认**只报告**，加 `--apply` 才真正关闭。

⚠️ 发布链运行中**可以**跑本脚本（内建守卫同理）：只关调用时已存在的空闲页，
不碰本轮持有 WebSocket 的页。真正禁止的是「停链后跑旧脚本 `_clean_creator_tabs.py`
那种按前缀清空」的粗放做法。

⚠️ 行为变化（2026-10-25）：旧版「www 页受保护 + 只卡单实例」已废止——
   全局上限要求两个实例一起管；只关保留数之外的旧残留，不影响在飞发布/巡检。

用法：
  python tab_guard.py                      # 只读报告（双实例全局）
  python tab_guard.py --port 9222          # 只看/清评论实例（单实例模式）
  python tab_guard.py --apply              # 执行全局清理
  python tab_guard.py --max 10 --apply     # 自定义阈值

退出码：0 = 未超阈值 / 已清理完成；1 = 超过阈值（只读模式下提醒需清理）；2 = Chrome 不可达。
"""
import argparse
import sys

try:
    import requests
except ImportError:
    print("需要 requests：请用 patch 自带 .venv 运行")
    sys.exit(2)

NO_PROXY = {"http": None, "https": None}
PROTECTED = (
    "https://creator.xiaohongshu.com/login",
)

PORTS = (9222, 9333)                 # 9222=评论实例  9333=发布实例
KEEP_NEWEST = {9222: 1, 9333: 3}     # 每实例保留的最新页数（其余可回收）
DEFAULT_MAX = 10                     # 全局合计上限（用户铁律）
DEFAULT_KEEP_AFTER = 9               # 回收后总量（给新建 tab 留 1 个余量）


def get_pages(base):
    r = requests.get(base + "/json/list", timeout=8, proxies=NO_PROXY)
    r.raise_for_status()
    return [t for t in r.json() if t.get("type") == "page"]


def snapshot(ports):
    """{port: [page,...]}；全部不可达返回 None。"""
    snap, alive = {}, 0
    for p in ports:
        try:
            snap[p] = get_pages("http://127.0.0.1:%d" % p)
            alive += 1
        except Exception:
            snap[p] = []
    return snap if alive else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=None,
                    help="只管理该实例（默认双实例全局口径）")
    ap.add_argument("--max", type=int, default=DEFAULT_MAX,
                    help="全局 page tab 合计达到该数量即触发（默认 10）")
    ap.add_argument("--keep-after", type=int, default=DEFAULT_KEEP_AFTER,
                    help="回收后全局合计（默认 9，给新建 tab 留余量）")
    ap.add_argument("--apply", action="store_true", help="真正执行关闭")
    a = ap.parse_args()

    ports = (a.port,) if a.port else PORTS
    snap = snapshot(ports)
    if snap is None:
        print("Chrome 不可达（%s）" % "/".join(str(p) for p in ports))
        return 2

    total = sum(len(v) for v in snap.values())
    for p in ports:
        print("  [%d] page tab %d 个（保留最新 %d，其余可回收）"
              % (p, len(snap[p]), KEEP_NEWEST.get(p, 1)))
    print("全局合计 page tab %d 个（阈值 %d）" % (total, a.max))
    if total < a.max:
        print("未超阈值，无需清理")
        return 0

    kill = []
    for p in ports:                  # 返回顺序 = 创建顺序，最早在前
        keep = KEEP_NEWEST.get(p, 1)
        for t in snap[p][: max(0, len(snap[p]) - keep)]:
            if (t.get("url") or "").startswith(PROTECTED):
                continue
            kill.append((p, t))
    print("将关闭最旧 %d 个残留页（login 受保护，已跳过）" % len(kill))

    if not a.apply:
        print("(只读模式，加 --apply 执行清理)")
        return 1

    ok = 0
    for p, t in kill:
        if total - ok <= a.keep_after:
            break
        try:
            requests.get("http://%s:%d/json/close/%s" % (a.host, p, t["id"]),
                         timeout=5, proxies=NO_PROXY)
            ok += 1
        except Exception as e:
            print("  关闭失败 [%d][%s]：%s" % (p, str(t.get("id", ""))[:8], e))
    left = sum(len(v) for v in snapshot(ports).values())
    print("已关闭 %d 个，剩余全局 page tab %d 个" % (ok, left))
    return 0


if __name__ == "__main__":
    sys.exit(main())
