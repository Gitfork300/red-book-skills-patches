"""启动小红书专用 Chrome -> 取二维码 -> 窗口置顶 -> 轮询等待扫码登录。

全程在同一次调用内完成，避免上层会话结束时 Chrome 被回收。

用法：
  python xhs_login_wait.py [等待秒数] [模式]

模式：
  （缺省）  登录成功后**优雅关闭** Chrome —— 确保 Cookie/会话落盘，
            适合"登完就走、稍后再起"的场景
  publish   登录成功后**不关窗，直接在同一会话内发布**
  keep-open 登录成功后**保持窗口打开**（不关闭）—— 适合用户还想继续操作，
            或需要立刻在同一会话里做后续任务（如平台只读核验）
"""
import base64
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

HELPERS = os.path.dirname(os.path.abspath(__file__))
PATCH_ROOT = os.path.normpath(os.path.join(HELPERS, "..", ".."))
SKILL = (
    os.environ.get("RED_BOOK_SKILLS_ROOT")
    or os.path.join(PATCH_ROOT, "runtime")
)
PY = (
    os.environ.get("RED_BOOK_SKILLS_PYTHON")
    or os.path.join(PATCH_ROOT, ".venv", "Scripts", "python.exe")
)
if not os.path.isfile(PY):
    PY = sys.executable
CACHE = os.path.join(SKILL, "tmp", "login_status_cache.json")
FOCUS_PS1 = os.path.join(HELPERS, "xhs_focus.ps1")
PORT = 9222
# 与 publish-interval-guard patch 解耦：仅当编排层显式注入路径时才集成
GUARD = os.environ.get("XHS_INTERVAL_GUARD")

# 本机 CDP 一律绕过代理。沙箱代理（sandbox-cli）在故障期对 127.0.0.1 也会返回
# 502 Bad Gateway，导致 Chrome 明明活着却被判定已死。与 cdp_publish.py 同口径。
_CDP_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def resolve_workspace():
    """定位稿件工作区。

    脚本被放进 helpers/ 后，按自身位置解析会指到 helpers 下面的目录，
    因此改为：优先读 XHS_WORKSPACE，再从 cwd / 脚本位置向上找 xhs_publish。
    """
    env = os.environ.get("XHS_WORKSPACE")
    if env and os.path.isdir(env):
        return os.path.abspath(env)
    for base in (os.getcwd(), HELPERS):
        d = base
        for _ in range(6):
            if os.path.isdir(os.path.join(d, "xhs_publish")):
                return d
            parent = os.path.dirname(d)
            if parent == d:
                break
            d = parent
    return os.getcwd()


WS = resolve_workspace()
QR_PNG = os.path.join(WS, "xhs_login_qrcode.png")


def clear_cache():
    if os.path.exists(CACHE):
        os.remove(CACHE)


def run(args, timeout=180):
    return subprocess.run(
        [PY] + args, cwd=SKILL, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=timeout,
    )


def tabs():
    with _CDP_OPENER.open(f"http://127.0.0.1:{PORT}/json", timeout=5) as r:
        return json.load(r)


def xhs_tabs():
    return [t for t in tabs() if t.get("type") == "page"
            and "xiaohongshu.com" in t.get("url", "")]


def login_tab():
    """优先返回当前停在登录页的标签，避免命中历史残留标签。"""
    ts = xhs_tabs()
    for t in ts:
        if "login" in t.get("url", "").lower():
            return t
    return ts[0] if ts else None


def graceful_shutdown():
    """优雅关闭 Chrome，确保 Cookie/会话写入 profile 后再退出。

    上层会话结束时会强制回收子进程，未落盘的 Cookie 会丢失，
    导致下一次启动又回到未登录状态。
    """
    try:
        from websockets.sync.client import connect
        with _CDP_OPENER.open(
            f"http://127.0.0.1:{PORT}/json/version", timeout=5
        ) as r:
            info = json.load(r)
        ws_url = info.get("webSocketDebuggerUrl")
        if not ws_url:
            return "no browser ws url"
        with connect(ws_url, open_timeout=5, proxy=None) as ws:
            ws.send(json.dumps({"id": 1, "method": "Browser.close"}))
            try:
                ws.recv(timeout=3)
            except Exception:
                pass
    except Exception as e:
        return f"shutdown send failed: {e}"

    for i in range(30):
        time.sleep(1)
        try:
            with _CDP_OPENER.open(
                f"http://127.0.0.1:{PORT}/json/version", timeout=2
            ):
                pass
        except Exception:
            return f"Chrome 已优雅退出 ({i + 1}s)"
    return "Chrome 未自动退出（可能仍在写盘）"


TITLE_FILE = os.path.join(WS, "xhs_publish", "title.txt")
CONTENT_FILE = os.path.join(WS, "xhs_publish", "content.txt")
# 依次尝试通用封面名，兼容历史稿件里出现过的文件名
COVER_CANDIDATES = ["xhs_cover.png", "xhs_typhoon_cover.png"]


def resolve_cover():
    for name in COVER_CANDIDATES:
        p = os.path.join(WS, name)
        if os.path.exists(p):
            return p
    pd = os.path.join(WS, "xhs_publish")
    if os.path.isdir(pd):
        for name in sorted(os.listdir(pd)):
            if name.lower().endswith((".png", ".jpg", ".jpeg")):
                return os.path.join(pd, name)
    return None


def publish():
    """在同一个 Chrome 会话内直接发布，全程不重启浏览器。"""
    cover = resolve_cover()
    for p in (TITLE_FILE, CONTENT_FILE):
        if not os.path.exists(p):
            print(f"!! 缺少稿件文件: {p}", flush=True)
            return 3
    if not cover:
        print(f"!! 未找到封面图（已查找 {COVER_CANDIDATES} 及 xhs_publish/）", flush=True)
        return 3

    title = open(TITLE_FILE, encoding="utf-8").read().strip()
    print(f"标题({len(title)}字): {title}", flush=True)
    print(f"正文: {CONTENT_FILE}", flush=True)
    print(f"配图: {cover}", flush=True)

    # 间隔守卫：连续发布需间隔 8~12 分钟（随机，下限 8 分钟），否则直接放弃，不重复提交
    if GUARD and os.path.isfile(GUARD):
        print("=== 检查发布间隔（XHS_INTERVAL_GUARD 已注入）===", flush=True)
        try:
            g = subprocess.run(
                [PY, GUARD, "wait", "--max-block", "900"],
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=1000,
            )
        except subprocess.TimeoutExpired:
            print("!! 间隔等待超时(1000s)，放弃本次发布", flush=True)
            return 5
        print((g.stdout or "").strip(), flush=True)
        if g.returncode != 0:
            print("!! 发布间隔未满足，已放弃本次发布（未重复提交）", flush=True)
            return 5
    else:
        print("=== 未注入 XHS_INTERVAL_GUARD，跳过间隔检查（由编排层负责）===", flush=True)

    cmd = [
        PY, "scripts/cdp_publish.py", "publish",
        "--title", title,
        "--content-file", CONTENT_FILE,
        "--images", cover,
    ]
    try:
        r = subprocess.run(
            cmd, cwd=SKILL, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=420,
        )
    except subprocess.TimeoutExpired:
        print("!! 发布超时(420s)", flush=True)
        return 4

    print("--- publish 输出 ---", flush=True)
    print((r.stdout or "")[-4000:], flush=True)
    if r.stderr:
        print("--- publish stderr ---", flush=True)
        print(r.stderr[-1500:], flush=True)
    print(f"publish exit={r.returncode}", flush=True)

    if r.returncode == 0:
        # 仅在发布成功后记录时间戳；失败提交不消耗间隔额度
        if GUARD and os.path.isfile(GUARD):
            note_id = None
            m = re.search(
                r"[\"']?note_?id[\"']?\s*[=:]\s*[\"']?([0-9a-zA-Z]+)",
                r.stdout or "", re.IGNORECASE,
            )
            if m:
                note_id = m.group(1)
            subprocess.run(
                [PY, GUARD, "record", "--note-id", note_id or "", "--title", title],
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=60,
            )
            print(f"已记录发布时间（note_id={note_id}）", flush=True)
        else:
            print("未注入 XHS_INTERVAL_GUARD，跳过记录（由编排层负责）", flush=True)

    return r.returncode


def verify_login(tab_id):
    """二次验证：确认标签已稳定离开登录页，排除历史残留标签误判。"""
    try:
        with _CDP_OPENER.open(
            f"http://127.0.0.1:{PORT}/json/activate/{tab_id}", timeout=5
        ):
            pass
    except Exception:
        pass
    time.sleep(1)
    for _ in range(6):
        try:
            for t in tabs():
                if t.get("id") == tab_id:
                    url = t.get("url", "")
                    if "login" not in url.lower() and "xiaohongshu.com" in url:
                        return True, url
        except Exception:
            pass
        time.sleep(2)
    return False, ""


def focus_window():
    try:
        r = subprocess.run(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
             "-File", FOCUS_PS1],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
        )
        return r.stdout.strip()
    except Exception as e:
        return f"focus failed: {e}"


def main():
    wait_total = int(sys.argv[1]) if len(sys.argv) > 1 else 150

    clear_cache()
    print("=== 1. 启动 Chrome 并获取登录二维码 ===", flush=True)
    r = run(["scripts/cdp_publish.py", "get-login-qrcode"], timeout=240)
    out = r.stdout or ""
    m = re.search(r"GET_LOGIN_QRCODE_RESULT:\s*(\{.*?\})\s*$", out, re.S | re.M)
    if not m:
        m = re.search(r"(\{.*\"qrcode_base64\".*\})", out, re.S)
    if m:
        data = json.loads(m.group(1))
        with open(QR_PNG, "wb") as f:
            f.write(base64.b64decode(data["qrcode_base64"]))
        print(f"二维码已保存: {QR_PNG}", flush=True)
        print(f"页面提示: {data.get('hint_text', '')}", flush=True)
    else:
        print("!! 未解析到二维码数据", flush=True)
        print(out[-800:], flush=True)

    print("=== 2. Chrome 窗口置顶 ===", flush=True)
    print(focus_window(), flush=True)

    target = login_tab()
    if not target:
        print("!! 未找到小红书标签页", flush=True)
        return 2
    tab_id = target.get("id")
    print(f"锁定标签: {tab_id}  {target.get('url')}", flush=True)
    print(f"全部小红书标签: {[t.get('url', '')[:40] for t in xhs_tabs()]}", flush=True)
    print(f"=== 3. 等待扫码（最长 {wait_total} 秒）===", flush=True)
    print(">>> 请在弹出的 Chrome 窗口中扫码，并在 App 内点确认 <<<", flush=True)

    deadline = time.time() + wait_total
    checked = 0
    while time.time() < deadline:
        time.sleep(4)
        checked += 1
        elapsed = checked * 4
        try:
            cur = None
            for t in tabs():
                if t.get("id") == tab_id:
                    cur = t
                    break
            if cur is None:
                print(f"[{elapsed:>3}s] 标签已关闭，重新查找登录页...", flush=True)
                nt = login_tab()
                if nt:
                    tab_id, cur = nt.get("id"), nt
                else:
                    continue
            url = cur.get("url", "")
            if "login" in url.lower():
                print(f"[{elapsed:>3}s] 待扫码 ({url.split('/')[-1] or url[:30]})", flush=True)
                continue

            # URL 已离开登录页 -> 二次导航验证，排除历史残留标签误判
            print(f"[{elapsed:>3}s] URL 已跳转: {url[:60]}，执行二次验证...", flush=True)
            ok, final_url = verify_login(tab_id)
            if ok:
                clear_cache()
                print(f"=== LOGIN_SUCCESS === {final_url}", flush=True)
                if len(sys.argv) > 2 and sys.argv[2] == "keep-open":
                    print("=== 4. keep-open：保持 Chrome 窗口打开，不关闭 ===", flush=True)
                    print("    会话已在当前浏览器中生效；如需落盘保存，稍后正常关闭该窗口即可。",
                          flush=True)
                    return 0
                if len(sys.argv) > 2 and sys.argv[2] == "publish":
                    print("=== 4. 浏览器保持打开，立即发布 ===", flush=True)
                    rc = publish()
                    print("=== 5. 发布结束，优雅关闭 Chrome 保存会话 ===", flush=True)
                    print(graceful_shutdown(), flush=True)
                    return rc
                print("=== 4. 优雅关闭 Chrome 以保存会话 ===", flush=True)
                # 给页面一点时间把 set-cookie 落盘
                time.sleep(3)
                print(graceful_shutdown(), flush=True)
                return 0
            print(f"[{elapsed:>3}s] 二次验证未通过，继续等待", flush=True)
        except Exception as e:
            print(f"[{elapsed:>3}s] 检测异常: {e}", flush=True)

    print("=== LOGIN_TIMEOUT === 二维码可能已过期", flush=True)
    return 1


if __name__ == "__main__":
    sys.exit(main())
