"""原仓库更新检查 —— 定期检查 aus666666/red-book-skills 是否有新提交。

为什么独立成脚本：
  - agent 不主动检查；必须定时跑
  - 只读 GitHub API，不修改任何 skill 文件
  - 优雅降级：无网/限流不抛错
  - 退出码语义化：0=无需检查/最新；1=有更新；2=网络错误；3=限流

用法：
  check                   若距上次检查 >= 间隔则执行；否则直接 exit 0
  check-now               强制立即检查（忽略间隔）
  status                  打印 state/update_state.json 的可读摘要
  diff-local              下载上游快照，逐文件对比本地 skill（忽略行尾/BOM）
  set-interval <秒>       调整检查间隔（默认 604800 = 7 天）
  acknowledge --sha SHA   标记某 commit 已读，避免重复提醒

为什么需要 diff-local：
  只比 commit sha 无法回答"这次上游改动会不会砸到我的本地定制"。
  本地 red-book-skills 是拷贝安装（无 .git），且带若干本地增强，
  订阅 sha 只能告诉你"上游动了"，不能告诉你"动了哪里"。
  diff-local 拉上游 tarball 做内容级比对，并按行尾归一化消除
  Windows CRLF 与上游 LF 造成的满屏假阳性。
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime

PATCH_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
STATE_DIR = os.path.join(PATCH_ROOT, "state")
STATE_FILE = os.path.join(STATE_DIR, "update_state.json")

# PATCH_ROOT 是本 patch 自己的目录：.../skills/red-book-skills-patches/update-checker
# 主 skill 与 patches 目录同级：上一级是 red-book-skills-patches，再上一级才是 skills
LOCAL_SKILL = os.path.normpath(os.path.join(PATCH_ROOT, "..", "..", "red-book-skills"))

REPO = "aus666666/red-book-skills"
GITHUB_API = "https://api.github.com"
GIT_LS_REMOTE = f"https://github.com/{REPO}.git"
DEFAULT_INTERVAL = 7 * 24 * 3600
NOTIFY_COOLDOWN = 24 * 3600  # 同 sha 提醒冷却

USER_AGENT = "xhs-update-checker/1.1"

# 对比时跳过的目录：运行时产物，不属于 skill 源码，比了只会刷屏
DIFF_SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", "tmp", ".pytest_cache", "node_modules"}

ENDPOINTS = [
    f"{GITHUB_API}/repos/{REPO}/commits?per_page=1",
    f"{GITHUB_API}/repos/{REPO}/commits?per_page=1&sha=master",
]


def _now():
    return time.time()


def _fmt(ts):
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


def _iso(ts):
    return datetime.fromtimestamp(ts).astimezone().isoformat(timespec="seconds")


def _load_state():
    if not os.path.exists(STATE_FILE):
        return {
            "last_check_epoch": 0,
            "last_check_iso": None,
            "last_check_status": None,
            "last_known_sha": None,
            "last_known_iso": None,
            "last_known_message": None,
            "last_notified_sha": None,
            "interval_sec": DEFAULT_INTERVAL,
        }
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            d = json.load(f)
        d.setdefault("interval_sec", DEFAULT_INTERVAL)
        return d
    except Exception:
        return {"interval_sec": DEFAULT_INTERVAL}


def _save_state(d):
    os.makedirs(STATE_DIR, exist_ok=True)
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    os.replace(tmp, STATE_FILE)


def _http_get_json(url, timeout=10):
    req = urllib.request.Request(url, headers={"User-Agent": "xhs-update-checker/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        if r.status == 403:
            raise RuntimeError("rate_limited")
        if r.status >= 400:
            raise RuntimeError(f"http {r.status}")
        return json.loads(r.read().decode("utf-8", errors="replace"))


def _git_ls_remote():
    try:
        out = subprocess.run(
            ["git", "ls-remote", GIT_LS_REMOTE, "HEAD"],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=15,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return None
    line = (out.stdout or "").strip().splitlines()
    if not line:
        return None
    sha = line[0].split()[0]
    return {"sha": sha, "iso": None, "message": "(via git ls-remote, no timestamp)"}


def fetch_latest():
    """依次尝试 GitHub API → git ls-remote；返回 dict 或抛 RuntimeError。"""
    last_err = None
    for url in ENDPOINTS:
        try:
            data = _http_get_json(url)
        except RuntimeError as e:
            last_err = e
            continue
        except (urllib.error.URLError, OSError) as e:
            last_err = e
            continue
        if isinstance(data, list) and data:
            c = data[0]
            sha = c.get("sha")
            commit = c.get("commit", {})
            ts = commit.get("author", {}).get("date") or commit.get("committer", {}).get("date")
            msg = (commit.get("message") or "").split("\n", 1)[0]
            return {"sha": sha, "iso": ts, "message": msg}
    g = _git_ls_remote()
    if g:
        return g
    raise RuntimeError(last_err or "all probes failed")


def cmd_check(args):
    state = _load_state()
    interval = state.get("interval_sec", DEFAULT_INTERVAL)
    last_check = state.get("last_check_epoch", 0) or 0
    if not args.now and (_now() - last_check) < interval:
        print(f"距上次检查仅 {_fmt(_now() - last_check)}，未到间隔 ({interval}s)，跳过")
        print("如需立即检查，加 --now")
        return 0
    return _do_check(state)


def _do_check(state):
    print("=== 检查原仓库最新 commit ===", flush=True)
    try:
        latest = fetch_latest()
    except RuntimeError as e:
        msg = str(e)
        status = "rate_limited" if "rate_limited" in msg else "network_error"
        state.update({
            "last_check_epoch": _now(),
            "last_check_iso": _iso(_now()),
            "last_check_status": status,
        })
        _save_state(state)
        print(f"!! 检查失败：{status}（{msg}）")
        return 2 if status == "network_error" else 3

    sha = latest["sha"]
    iso = latest.get("iso")
    msg = latest.get("message", "")
    last_known = state.get("last_known_sha")

    state.update({
        "last_check_epoch": _now(),
        "last_check_iso": _iso(_now()),
        "last_check_status": "ok",
        "last_known_sha": sha,
        "last_known_iso": iso,
        "last_known_message": msg,
    })

    if last_known == sha:
        print(f"已是最新：{sha[:10]}  {msg}")
        _save_state(state)
        return 0

    # 有更新
    last_notified = state.get("last_notified_sha")
    cooldown_ok = (last_notified != sha)
    if last_notified and (last_known and (sha != last_known)):
        # last_known 是旧的、last_notified 可能是更旧——以 _now-last_notified_ts 的时间戳比较
        # 简化：直接用 cooldown_ok 标记
        pass
    state["last_notified_sha"] = sha
    _save_state(state)

    if not cooldown_ok:
        # 实际几乎不会走到这里——cooldown 在 last_notified==sha 时为 False
        print("检测到更新但冷却期未过，跳过提醒")
        return 0

    print("=== UPDATE_AVAILABLE ===", flush=True)
    print(f"原仓库: {REPO}")
    print(f"  新 commit: {sha}")
    print(f"  时间    : {iso}")
    print(f"  标题    : {msg}")
    print(f"  本地最后: {last_known or '(无记录)'}")
    print()
    print("如何合并（详见 update-checker SKILL.md）：")
    print("  1. 评估影响范围（小改直接 pull；BREAKING 暂停使用）")
    print("  2. 查 patches/*/META.json 的 applies_to_main_version 是否还满足")
    print("  3. 合并完成后：acknowledge --sha", sha)
    return 1


def _fetch_default_branch():
    try:
        d = _http_get_json(f"{GITHUB_API}/repos/{REPO}")
        return d.get("default_branch")
    except Exception:
        return None


def _download_upstream(dest):
    """下载上游默认分支 tar.gz 并解压；返回解压后的仓库根目录。"""
    branch = _fetch_default_branch() or "main"
    url = f"https://codeload.github.com/{REPO}/tar.gz/refs/heads/{branch}"
    tgz = os.path.join(dest, "upstream.tgz")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=60) as r, open(tgz, "wb") as f:
            shutil.copyfileobj(r, f)
    except (urllib.error.URLError, OSError) as e:
        raise RuntimeError(f"download failed: {e}")
    try:
        with tarfile.open(tgz, "r:gz") as tf:
            # 3.12+ 显式传 filter，避免 DeprecationWarning 与路径穿越风险
            try:
                tf.extractall(dest, filter="data")
            except TypeError:
                tf.extractall(dest)
    except (tarfile.TarError, OSError) as e:
        raise RuntimeError(f"extract failed: {e}")

    for entry in sorted(os.listdir(dest)):
        cand = os.path.join(dest, entry)
        if os.path.isdir(cand) and os.path.exists(os.path.join(cand, "SKILL.md")):
            return cand
    return None


def _norm_bytes(path):
    """读文件并归一化：统一行尾 + 去 BOM。

    Windows 安装的副本通常是 CRLF，上游仓库是 LF；
    不归一化会导致几乎每个文件都被误报为"不同"。
    """
    with open(path, "rb") as f:
        d = f.read()
    return d.replace(b"\r\n", b"\n").replace(b"\r", b"\n").lstrip(b"\xef\xbb\xbf")


def _walk_files(root):
    out = {}
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in DIFF_SKIP_DIRS]
        for fn in fns:
            if fn.endswith(".pyc"):
                continue
            fp = os.path.join(dp, fn)
            out[os.path.relpath(fp, root).replace("\\", "/")] = fp
    return out


def _sha_norm(path):
    return hashlib.sha256(_norm_bytes(path)).hexdigest()


def _check_overrides(up_root):
    """对照 core-overrides/baseline.json，检测上游是否也改动了被我们覆盖的文件。

    返回 None（无覆盖层）或 (unchanged, conflict, missing)：
      unchanged 上游未动的被覆盖文件
      conflict  [(rel, baseline_sha, upstream_sha)] 双方都改了 —— 直接覆盖会丢上游改动
      missing   上游已无此文件
    """
    bl = os.path.normpath(
        os.path.join(PATCH_ROOT, "..", "core-overrides", "baseline.json")
    )
    if not os.path.exists(bl):
        return None
    try:
        with open(bl, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return None

    unchanged, conflict, missing = [], [], []
    for rel, meta in (data.get("files") or {}).items():
        base_sha = meta.get("upstream_sha256")
        cur = os.path.join(up_root, rel)
        if not os.path.exists(cur):
            missing.append(rel)
            continue
        now_sha = _sha_norm(cur)
        if base_sha and now_sha == base_sha:
            unchanged.append(rel)
        else:
            conflict.append((rel, base_sha or "(未记录)", now_sha))
    return unchanged, conflict, missing


def cmd_diff_local(args):
    local = args.local or LOCAL_SKILL
    if not os.path.isdir(local):
        print(f"!! 本地 skill 目录不存在：{local}", file=sys.stderr)
        return 2

    tmp = tempfile.mkdtemp(prefix="rb_upstream_")
    try:
        try:
            up = _download_upstream(tmp)
        except RuntimeError as e:
            print(f"!! 无法获取上游快照：{e}")
            return 2
        if not up:
            print("!! 上游快照解压后未找到 SKILL.md，结构可能变了")
            return 2

        u, l = _walk_files(up), _walk_files(local)
        same, diff, only_local, only_up = [], [], [], []
        for rel in sorted(set(u) | set(l)):
            if rel in u and rel in l:
                (same if _norm_bytes(u[rel]) == _norm_bytes(l[rel]) else diff).append(rel)
            elif rel in l:
                only_local.append(rel)
            else:
                only_up.append(rel)

        ov = _check_overrides(up)
        result = {
            "upstream_root": up,
            "local_root": local,
            "same": same,
            "modified": diff,
            "only_local": only_local,
            "only_upstream": only_up,
        }
        if ov:
            result["overrides_conflict"] = [c[0] for c in ov[1]]

        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"本地 skill : {local}")
            print(f"上游快照   : {os.path.basename(up)}")
            print(f"（已忽略行尾差异；跳过 {', '.join(sorted(DIFF_SKIP_DIRS))}）")
            print()
            print(f"相同      : {len(same)} 个文件")
            print(f"内容不同  : {len(diff)} 个")
            for r in diff:
                print(f"   ~ {r}")
            print(f"仅上游有  : {len(only_up)} 个（本地缺失，可能是上游新增文件）")
            for r in only_up:
                print(f"   + {r}")
            print(f"仅本地有  : {len(only_local)} 个（本地增补或运行时产物）")
            for r in only_local:
                print(f"   - {r}")
            print()

            if ov:
                unchanged, conflict, missing = ov
                print("=== 覆盖层冲突检查（core-overrides/baseline.json）===")
                if conflict:
                    print(f"  !! 上游改动了 {len(conflict)} 个被我们覆盖的文件 —— 直接覆盖会丢上游改动：")
                    for rel, b, c in conflict:
                        print(f"     {rel}")
                        print(f"       基线={b[:12]}   上游当前={c[:12]}")
                    print("     处置：把上游改动人工合并进 core-overrides/overrides/ 后再 apply")
                else:
                    print(f"  OK 被覆盖的 {len(unchanged)} 个文件上游均未改动，覆盖层安全")
                for rel in missing:
                    print(f"  ?? 上游已无此文件：{rel}（可能被重构删除/改名）")
                print()

            if not (diff or only_up):
                print("结论：本地与上游内容一致。")
            else:
                print("结论：存在差异。'仅上游有' 与 '内容不同' 中属于上游新增/修改的部分需要评估；")
                print("      '仅本地有' 与本地增强导致的 '内容不同' 属于定制，覆盖会丢失，务必逐项确认。")
            if ov and ov[1]:
                print("      !! 另有覆盖层冲突（见上），合并前不要覆盖本体。")

        return 1 if (diff or only_up) else 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def cmd_status(args):
    state = _load_state()
    print(f"  interval     : {state.get('interval_sec', DEFAULT_INTERVAL)}s ({(state.get('interval_sec', DEFAULT_INTERVAL) or DEFAULT_INTERVAL) // 86400} 天)")
    print(f"  last_check   : {state.get('last_check_iso') or '(never)'}")
    print(f"  status       : {state.get('last_check_status') or '(unknown)'}")
    print(f"  last_known   : {state.get('last_known_sha') or '(unknown)'}")
    if state.get("last_known_iso"):
        print(f"                 @ {state['last_known_iso']}")
    if state.get("last_known_message"):
        print(f"                 : {state['last_known_message']}")
    print(f"  last_notify  : {state.get('last_notified_sha') or '(never)'}")
    if state.get("last_check_epoch"):
        next_due = state["last_check_epoch"] + state.get("interval_sec", DEFAULT_INTERVAL)
        if _now() < next_due:
            print(f"  下次检查     : {_fmt(next_due)}（{int(next_due - _now())} 秒后）")
        else:
            print(f"  下次检查     : 已到期（任何 check 都会执行）")
    return 0


def cmd_set_interval(args):
    state = _load_state()
    state["interval_sec"] = int(args.seconds)
    _save_state(state)
    print(f"已设置 interval = {args.seconds} 秒 ({args.seconds // 86400} 天)")
    return 0


def cmd_acknowledge(args):
    state = _load_state()
    state["last_notified_sha"] = args.sha
    _save_state(state)
    print(f"已标记 {args.sha[:10]} 为已读，下次检查起将不再重复提醒此 commit")
    return 0


def main():
    p = argparse.ArgumentParser(description="red-book-skills 上游更新检查")
    p.add_argument("action",
                   choices=["check", "check-now", "status", "diff-local", "set-interval", "acknowledge"])
    p.add_argument("--now", action="store_true",
                   help="(check 用) 忽略间隔，强制执行")
    p.add_argument("seconds", nargs="?", type=int,
                   help="(set-interval 用) 间隔秒数")
    p.add_argument("--sha", help="(acknowledge 用) 标记的 commit sha")
    p.add_argument("--local", help="(diff-local 用) 指定本地 skill 目录，默认同级 red-book-skills")
    p.add_argument("--json", action="store_true", help="(diff-local 用) 输出 JSON")
    args = p.parse_args()

    if args.action == "check":
        return cmd_check(args)
    if args.action == "check-now":
        args.now = True
        return cmd_check(args)
    if args.action == "status":
        return cmd_status(args)
    if args.action == "diff-local":
        return cmd_diff_local(args)
    if args.action == "set-interval":
        if not args.seconds:
            print("!! set-interval 需要秒数参数", file=sys.stderr)
            return 2
        return cmd_set_interval(args)
    if args.action == "acknowledge":
        if not args.sha:
            print("!! acknowledge 需要 --sha", file=sys.stderr)
            return 2
        return cmd_acknowledge(args)
    return 2


if __name__ == "__main__":
    sys.exit(main())
