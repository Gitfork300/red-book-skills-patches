"""发布间隔守卫 + 跨进程发布互斥 —— 连续两篇笔记之间必须间隔 8~12 分钟（随机）。

为什么要独立成脚本：间隔判断依赖"上一次成功发布"的真实时间戳，
而 agent 自身的会话时间感不可靠（跨调用、上下文压缩、长任务等待都会失真）。
把时间戳落盘，由脚本裁定，才不会凭印象提前发。

为什么要随机：固定 10 分钟这种"整齐"的节奏本身就是机器特征。
每次发布后在 [480, 720] 秒之间抽一个目标间隔（8~12 分钟），
落在记录里（next_gap），由脚本锁定，避免反复 check 时抖动。

存储位置：本 patch 自己的 state/ 目录（不依赖主 skill 的 tmp/）。
这样未来重装主 skill、迁移 patch、跨机器同步都不会丢记录。

用法：
  check                     距上次发布是否已满足本次目标间隔；exit 0 = 可发布，exit 1 = 需等待
  check --json              同上，输出机器可读结果
  wait                      阻塞等待到可发布；exit 0 = 可发布，exit 1 = 仍未满足（超出 max-block）
  wait --max-block 900      最长阻塞秒数，默认 900
  reserve --title "标题"     原子「检查 + 占位」，拿到发布资格；exit 0 = 可发（并输出 reserve_id）
  reserve --max-block 900   间隔未满时最多阻塞等待多久（默认 0 = 立刻返回 exit 1）
  release --reserve-id ID   撤销占位（发布失败时调用；未实际发布，不该占用间隔）
  record --title "标题"      记录一次"已审核的成功发布"（仅在 publish 成功、且 verify-note 确认后调用）
  record --note-id ID --title "标题" --reserve-id ID
  reset                     清空发布记录
  last                      查看上次发布时间、本次目标间隔与还需等待的秒数

间隔参数：
  --interval-min N   随机下界，默认 480（8 分钟）
  --interval-max N   随机上界，默认 720（12 分钟）
  --interval N       固定间隔（覆盖随机），用于特殊场景/回放
  --seed N           指定随机种子（仅调试/自测，正式发布不要用）

环境变量（优先级低于命令行）：
  XHS_INTERVAL_MIN / XHS_INTERVAL_MAX / XHS_INTERVAL

与编排层集成：
  通过环境变量 XHS_INTERVAL_GUARD 指向本脚本，xhs_login_wait.py 会自动调用 reserve/record。
  直接调用本脚本时，存储路径取决于 <patch>/state/publish_log.json。

──── v1.4.0（2026-09-17）跨进程互斥 ────────────────────────────────
原实现只有 check/wait（**只读**）+ record（**事后补账**），中间隔着整条发布流程。
两个批次各自读到「可发」后同时进入发布流程，谁也拦不住谁 —— 间隔失效。

实测（2026-09-17，publish_log.json）三组同标题笔记，note_id 相差 2~6 秒：
    08:10:20 6aab2fec  vs  08:10:24 6aab2ff0   [S] GACS2026 开幕式议程②
    08:26:01 6aab3399  vs  08:26:03 6aab339b   [S] GACS2026 大模型芯片论坛③
    08:37:19 6aab363f  vs  08:37:25 6aab3645   [S] GACS2026 Agent芯片论坛④
（note_id 高 8 位即创建时间的十六进制 epoch，两条相差 2~6 秒 ⇒ 同一条内容发了两遍。）

修正：
  1) reserve  —— 原子「检查 + 占位」。在同一把文件锁内完成
                 「读日志 → 判定 → 写占位」，占位本身就是一条 pending 记录，
                 其他进程立刻可见并需等待。**这才是权威闸门**，
                 check/wait 退化为「提前预判、省得白干活」。
  2) release  —— 发布失败时撤销占位（没实际发布就不该占用间隔）。
  3) 同标题拦截 —— reserve 时若标题已在本日志里（含其他进程的 pending 占位）→ exit 3。
                 跨进程防重发，不依赖易失的台账文件；--allow-same-title 可放行。
  4) 落盘原子化 —— 临时文件 + os.replace，避免并发写把台账截断成半截 JSON。
  5) 锁改用内核咨询锁 —— msvcrt.locking / fcntl.flock，关句柄即释放、崩溃自动释放，
                 不依赖"删锁文件"。原因：本机 python 被沙箱 shim 接管，
                 `os.remove` 被代理到宿主回收站，宿主不可用时 fail-closed 且不报错
                 （实测打印 [safe-delete][SAFE_DELETE_FAIL_CLOSED] 后文件仍在），
                 删锁文件式的实现会因此漏锁、把后续所有进程卡到超时。
  6) 过期占位回收 —— pending 超过 --pending-ttl（默认 1800 秒）标记为 expired，
                 保留其 epoch（保守：只把后续发布推后，不会让间隔变短）。

退出码：
  0 成功 / 可发布
  1 间隔未满足
  2 参数错误
  3 同标题已被发布或占位（跨进程防重发）
  4 等锁超时
"""
import argparse
import json
import os
import random
import sys
import time
import uuid
from contextlib import contextmanager
from datetime import datetime

PATCH_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
# 可用 XHS_INTERVAL_STATE_DIR 把台账/锁重定向到别处（自测、回放、多账号隔离用）；
# 不设时就是 patch 自己的 state/，与历史行为一致。
STATE_DIR = os.environ.get("XHS_INTERVAL_STATE_DIR") or os.path.join(PATCH_ROOT, "state")
LOG = os.path.join(STATE_DIR, "publish_log.json")
LOCK = os.path.join(STATE_DIR, ".guard.lock")

DEFAULT_MIN = 480          # 8 分钟
DEFAULT_MAX = 720          # 12 分钟
DEFAULT_MAX_BLOCK = 900
DEFAULT_PENDING_TTL = 1800  # 占位最长存活 30 分钟（实测单次发布最慢约 10 分钟）
DEFAULT_LOCK_TIMEOUT = 20   # 等锁上限（持锁方只做毫秒级读写）

EXIT_OK = 0
EXIT_WAIT = 1
EXIT_ARG = 2
EXIT_DUP_TITLE = 3
EXIT_LOCK_TIMEOUT = 4


class LockTimeout(RuntimeError):
    pass


# 输出统一 UTF-8。
# 为什么必须显式设置：Windows 下 stdout 被重定向到文件或管道时，Python 会退回
# 本地编码（本机实测 cp1252），脚本里任何中文 print 都会抛 UnicodeEncodeError。
# 后果很隐蔽 —— 台账其实已经写成功了，进程却以退出码 1 结束，
# 调用方（publish_pipeline / xhs_login_wait）会把「记录成功」误判为「记录失败」。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def _env_int(name, fallback):
    raw = os.environ.get(name)
    if raw is None or str(raw).strip() == "":
        return fallback
    try:
        return int(float(str(raw).strip()))
    except Exception:
        return fallback


# ── 台账读写 ────────────────────────────────────────────────────
def _load():
    if not os.path.exists(LOG):
        return []
    try:
        with open(LOG, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []
    return data if isinstance(data, list) else []


def _save(records):
    """原子落盘：先写临时文件再 os.replace，避免并发写截断台账。"""
    os.makedirs(STATE_DIR, exist_ok=True)
    tmp = "%s.tmp.%d" % (LOG, os.getpid())
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(records[-100:], f, ensure_ascii=False, indent=2)
        os.replace(tmp, LOG)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


# ── 进程存活探测（Windows 安全）──────────────────────────────────
def _pid_alive(pid):
    """判断 pid 是否仍在运行。

    不使用 os.kill(pid, 0)：Windows 上它落到 GenerateConsoleCtrlEvent(CTRL_C_EVENT, pid)，
    语义与 POSIX 不同（实测本机对普通子进程恰好也返回 True，但属巧合，不该依赖）。
    """
    if not isinstance(pid, int) or pid <= 0:
        return False
    if pid == os.getpid():
        return True
    if os.name == "nt":
        try:
            import ctypes

            SYNCHRONIZE = 0x00100000
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            WAIT_TIMEOUT = 0x00000102
            k32 = ctypes.windll.kernel32
            handle = k32.OpenProcess(
                SYNCHRONIZE | PROCESS_QUERY_LIMITED_INFORMATION, False, pid
            )
            if not handle:
                return False
            try:
                return k32.WaitForSingleObject(handle, 0) == WAIT_TIMEOUT
            finally:
                k32.CloseHandle(handle)
        except Exception:
            return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


# ── 跨进程文件锁 ────────────────────────────────────────────────
def _os_lock_acquire(fd):
    """非阻塞地尝试独占锁；已被占用则抛 OSError。"""
    if os.name == "nt":
        import msvcrt

        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
    else:
        import fcntl

        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)


def _os_lock_release(fd):
    if os.name == "nt":
        import msvcrt

        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(fd, fcntl.LOCK_UN)


def _lock_holder():
    """读锁文件里的持有者信息，仅用于超时报错时给出线索（不参与锁判定）。"""
    try:
        with open(LOCK, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return "持有者信息不可读"
    if not isinstance(data, dict):
        return "持有者信息不可读"
    pid = data.get("pid")
    alive = _pid_alive(pid) if isinstance(pid, int) else None
    return "pid=%s(存活=%s) 自 %s" % (pid, alive, data.get("at"))


@contextmanager
def _file_lock(timeout=DEFAULT_LOCK_TIMEOUT):
    """同一台机器上串行化对 publish_log.json 的「读-改-写」。

    只保护台账的读写（毫秒级），**不横跨整条发布流程** —— 跨进程的发布互斥
    由 reserve 写下的 pending 占位承担，锁本身不长时间持有。

    为什么用操作系统级咨询锁，而不是"建文件=拿锁、删文件=放锁"：
      1) 本机 python 被 WorkBuddy 沙箱 shim 接管，`os.remove` 被换成
         `_safe_remove` —— 非临时目录下的删除要经宿主回收站，宿主不可用时
         **fail-closed 且不报错**（实测打印 [safe-delete][SAFE_DELETE_FAIL_CLOSED] 后
         文件仍在）。锁文件删不掉 → 后续所有进程等锁超时。
      2) "先 O_EXCL 建文件、再写内容"存在竞态窗口：竞争者读到空文件 → 解析失败 →
         判为死锁 → 把别人的锁删掉。run_lock.py 的 _cleanup_stale_lock 正是这个写法，
         实测确实会把刚建立的锁当失效锁删除（见 _lockprobe_out.txt）。

    改为 msvcrt.locking（Windows）/ fcntl.flock（POSIX）：
      - 锁由内核按文件句柄管理，**关句柄即释放，进程崩溃也自动释放**，不依赖删除；
      - 锁文件常驻磁盘（这很正常），只为承载锁而存在。
    """
    os.makedirs(STATE_DIR, exist_ok=True)
    fd = os.open(LOCK, os.O_CREAT | os.O_RDWR, 0o600)
    deadline = time.time() + max(0, timeout)
    try:
        while True:
            try:
                _os_lock_acquire(fd)
                break
            except OSError:
                if time.time() >= deadline:
                    raise LockTimeout(
                        "等待发布台账锁超时（%.0f 秒）：%s 被占用（%s）"
                        % (timeout, LOCK, _lock_holder())
                    )
                time.sleep(0.05)
        # 拿到锁后写入持有者信息（仅用于排查，不参与锁判定）
        try:
            os.lseek(fd, 0, os.SEEK_SET)
            os.truncate(fd, 0)
            os.write(fd, json.dumps(
                {"pid": os.getpid(), "at": _fmt(time.time()), "argv": sys.argv[1:2]},
                ensure_ascii=False).encode("utf-8"))
        except Exception:
            pass
        yield
    finally:
        try:
            _os_lock_release(fd)
        except Exception:
            pass
        try:
            os.close(fd)
        except Exception:
            pass


# ── 记录与占位 ──────────────────────────────────────────────────
def _draw(min_sec, max_sec, rng, fixed=None):
    if fixed is not None:
        return int(fixed)
    lo, hi = min_sec, max_sec
    if lo > hi:
        lo, hi = hi, lo
    if hi <= lo:
        return int(lo)
    return rng.randint(int(lo), int(hi))


def _latest(rs):
    return max(rs, key=lambda r: r.get("epoch", 0)) if rs else None


def _is_pending(r):
    return bool(r) and r.get("pending") is True


def _reap(rs, ttl):
    """把过期占位标记为 expired（保留 epoch，保守：只推后、不缩短间隔）。"""
    changed = False
    now = time.time()
    for r in rs:
        if _is_pending(r) and now - float(r.get("epoch", 0)) > ttl:
            r["pending"] = False
            r["expired"] = True
            changed = True
    return changed


def last_record():
    return _latest(_load())


def _target_of(min_sec, max_sec, rng, fixed=None, save=True):
    """确保最新一条记录带有本次要等待的目标间隔 next_gap。"""
    rs = _load()
    last = _latest(rs)
    if last is None:
        return None
    gap = last.get("next_gap")
    if not isinstance(gap, (int, float)) or gap <= 0:
        gap = _draw(min_sec, max_sec, rng, fixed)
        last["next_gap"] = int(gap)
        if save:
            _save(rs)
    return int(gap)


def ensure_next_gap(min_sec, max_sec, rng, fixed=None):
    return _target_of(min_sec, max_sec, rng, fixed, save=True)


def remaining(target):
    r = last_record()
    if r is None or target is None:
        return 0.0
    return max(0.0, target - (time.time() - r.get("epoch", 0)))


def _fmt(ts):
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


def _human(sec):
    sec = int(round(sec))
    if sec >= 60:
        return f"{sec // 60} 分 {sec % 60} 秒"
    return f"{sec} 秒"


def _resolve(args):
    min_sec = args.interval_min if args.interval_min is not None else _env_int("XHS_INTERVAL_MIN", DEFAULT_MIN)
    max_sec = args.interval_max if args.interval_max is not None else _env_int("XHS_INTERVAL_MAX", DEFAULT_MAX)
    if min_sec > max_sec:
        min_sec, max_sec = max_sec, min_sec
    fixed = args.interval if args.interval is not None else _env_int("XHS_INTERVAL", None)
    if fixed is not None and fixed <= 0:
        fixed = None
    rng = random.Random(args.seed) if args.seed is not None else random.Random()

    def draw():
        return _draw(min_sec, max_sec, rng, fixed)

    return min_sec, max_sec, fixed, rng, draw


def _state_of(r):
    if r is None:
        return "none"
    if _is_pending(r):
        return "pending"
    if r.get("expired"):
        return "expired"
    return "done"


def _describe(r):
    if r is None:
        return "无记录"
    st = _state_of(r)
    tag = {"pending": "进行中(占位)", "expired": "占位已过期"}.get(st, "")
    return f"{r.get('ts')}{(' ' + tag) if tag else ''}"


# ── 子命令 ──────────────────────────────────────────────────────
def cmd_check(args):
    min_sec, max_sec, fixed, rng, draw = _resolve(args)
    with _file_lock(args.lock_timeout):
        rs = _load()
        if _reap(rs, args.pending_ttl):
            _save(rs)
        target = _target_of(min_sec, max_sec, rng, fixed, save=True)
        r = _latest(rs)
        state = _state_of(r)
        left = 0.0
        if r is not None and target:
            left = max(0.0, target - (time.time() - r.get("epoch", 0)))
    if args.json:
        print(json.dumps({
            "ready": left <= 0,
            "remaining_sec": round(left),
            "target_gap_sec": target,
            "interval_min_sec": min_sec,
            "interval_max_sec": max_sec,
            "mode": "fixed" if fixed is not None else "random",
            "last_publish": _fmt(r["epoch"]) if r else None,
            "last_title": r.get("title") if r else None,
            "last_state": state,
        }, ensure_ascii=False))
    else:
        if r is None:
            print(f"无发布记录，可直接发布（本次目标间隔 {_human(target) if target else '—'}）")
        elif left <= 0:
            print(f"距上次发布（{_describe(r)}）已满足目标间隔 {_human(target)}，可发布")
        elif state == "pending":
            print(f"另一个进程正在发布（占位 {_describe(r)}），需再等 {_human(left)}")
        else:
            print(f"距上次发布（{_describe(r)}）需再等 {_human(left)}（本次目标间隔 {_human(target)}）")
    return EXIT_OK if left <= 0 else EXIT_WAIT


def cmd_wait(args):
    min_sec, max_sec, fixed, rng, draw = _resolve(args)
    target = ensure_next_gap(min_sec, max_sec, rng, fixed)
    left = remaining(target)
    if left <= 0:
        print(f"间隔已满足（目标 {_human(target)}），可立即发布", flush=True)
        return EXIT_OK

    mode = "固定" if fixed is not None else f"随机 {_human(min_sec)}~{_human(max_sec)}"
    block = min(left, args.max_block)
    if block < left:
        print(
            f"需等待 {_human(left)}，但 max-block 只有 {args.max_block} 秒；"
            f"本次最多等待 {_human(block)} 后返回未满足状态",
            flush=True,
        )

    deadline = time.time() + block
    next_report = None
    print(f"本次目标间隔 {_human(target)}（{mode}），还需等待 {_human(left)}", flush=True)
    while True:
        left = remaining(target)
        if left <= 0:
            print(f"间隔已满足（目标 {_human(target)}），可发布", flush=True)
            return EXIT_OK
        if time.time() >= deadline:
            print(f"WAIT_INCOMPLETE 仍需等待 {_human(left)}", flush=True)
            return EXIT_WAIT
        bucket = int(left) // 60
        if bucket != next_report:
            next_report = bucket
            print(f"  还需等待 {_human(left)}...", flush=True)
        time.sleep(max(0.5, min(5.0, left, deadline - time.time())))


def cmd_reserve(args):
    """原子「检查 + 占位」：拿到发布资格才继续。

    整段「读日志 → 查重 → 判间隔 → 写占位」在同一把文件锁内完成，
    因此两个并发进程不可能同时拿到资格。
    """
    min_sec, max_sec, fixed, rng, draw = _resolve(args)
    deadline = time.time() + max(0, args.max_block)
    waited = 0.0
    while True:
        with _file_lock(args.lock_timeout):
            rs = _load()
            if _reap(rs, args.pending_ttl):
                _save(rs)

            # ① 同标题拦截（含其他进程的 pending 占位）—— 跨进程防重复发布
            if args.title and not args.allow_same_title:
                for r in rs:
                    if r.get("title") == args.title and not r.get("expired"):
                        msg = (
                            f"同标题已在台账中（{r.get('ts')}，"
                            f"{'占位中' if _is_pending(r) else '已发布'}，"
                            f"note_id={r.get('note_id') or '—'}）→ 拒绝重复提交"
                        )
                        if args.json:
                            print(json.dumps({"reserved": False, "reason": "dup_title",
                                              "detail": msg}, ensure_ascii=False))
                        else:
                            print("DUP_TITLE: " + msg)
                            print("  确需重发（例如旧稿已被删除）：加 --allow-same-title", flush=True)
                        return EXIT_DUP_TITLE

            # ② 间隔判定
            last = _latest(rs)
            target = last.get("next_gap") if last else None
            if not isinstance(target, (int, float)) or target <= 0:
                target = draw()
            target = int(target)
            left = 0.0
            if last is not None:
                left = max(0.0, target - (time.time() - last.get("epoch", 0)))

            if left > 0:
                if time.time() < deadline:
                    need = min(left, deadline - time.time())
                    print(f"间隔未满（还需 {_human(left)}），占位等待中…", flush=True)
                    time.sleep(max(0.2, min(need, 5.0)))
                    waited += need
                    continue
                msg = (
                    f"间隔未满足：距上次发布（{_describe(last)}）还需 {_human(left)}"
                    f"（目标间隔 {_human(target)}）"
                )
                if args.json:
                    print(json.dumps({"reserved": False, "reason": "interval",
                                      "remaining_sec": round(left),
                                      "target_gap_sec": target, "detail": msg},
                                     ensure_ascii=False))
                else:
                    print("INTERVAL_NOT_MET: " + msg)
                return EXIT_WAIT

            # ③ 写占位
            now = time.time()
            rid = uuid.uuid4().hex[:12]
            prev = last.get("epoch") if last else None
            rs.append({
                "epoch": now,
                "ts": _fmt(now),
                "note_id": "",
                "title": args.title or "(未指定标题)",
                "actual_gap_sec": int(round(now - prev)) if prev else None,
                "next_gap": draw(),
                "pending": True,
                "reserve_id": rid,
                "pid": os.getpid(),
            })
            _save(rs)
        # 出锁后才输出，缩短持锁时间
        if args.json:
            print(json.dumps({"reserved": True, "reserve_id": rid,
                              "target_gap_sec": target,
                              "waited_sec": round(waited, 1)}, ensure_ascii=False))
        else:
            print(f"已占位 reserve_id={rid}（目标间隔 {_human(target)}）")
            print(f"RESERVE_ID: {rid}")
        return EXIT_OK


def cmd_release(args):
    """撤销占位：发布失败时调用，释放间隔。"""
    with _file_lock(args.lock_timeout):
        rs = _load()
        _reap(rs, args.pending_ttl)
        hit = None
        if args.reserve_id:
            for r in rs:
                if r.get("reserve_id") == args.reserve_id:
                    hit = r
                    break
        else:
            # 未指定 id：撤销最新一个仍 pending 的占位
            for r in sorted(rs, key=lambda x: x.get("epoch", 0), reverse=True):
                if _is_pending(r):
                    hit = r
                    break
        if hit is None:
            print("未找到对应占位（可能已 record 升级或已被回收），无需释放")
            return EXIT_OK
        rs.remove(hit)
        _save(rs)
    print(f"已释放占位 {hit.get('reserve_id')}（{hit.get('ts')}，{hit.get('title')}）")
    return EXIT_OK


def cmd_record(args):
    min_sec, max_sec, fixed, rng, draw = _resolve(args)
    with _file_lock(args.lock_timeout):
        recs = _load()
        _reap(recs, args.pending_ttl)

        # ── 幂等：同一条笔记只记一次 ──────────────────────────────
        # 背景：core-overrides 已把 record 接进 scripts/publish_pipeline.py（发布成功即自动记录），
        # 而历史批量脚本骨架（xhs_batch_publish_*.py）里又显式调了一次 record
        # —— 同一篇被记两次，表现为「台风配额 2/1」且间隔显示刚发过。
        # 2026-09-12 实测踩到（12:08:34 与 12:08:54 两条同 note_id）。
        # 在 record 这个唯一入口加幂等，比逐个改散落的历史脚本可靠。
        if args.note_id:
            for r in recs:
                if r.get("note_id") == args.note_id:
                    print(f"已存在相同 note_id 的记录（{r.get('ts')}），跳过重复记录")
                    print(f"  标题: {r.get('title')}")
                    return EXIT_OK

        # ── 把占位升级为正式记录（不新增一条，避免一次发布占两个间隔位）──
        resv = None
        if args.reserve_id:
            for r in recs:
                if r.get("reserve_id") == args.reserve_id and _is_pending(r):
                    resv = r
                    break
        if resv is None and args.title:
            for r in sorted(recs, key=lambda x: x.get("epoch", 0), reverse=True):
                if _is_pending(r) and r.get("title") == args.title:
                    resv = r
                    break
        if resv is None:
            # 兼容：没有占位时也允许直接补记（老的调用方）
            for r in sorted(recs, key=lambda x: x.get("epoch", 0), reverse=True):
                if _is_pending(r) and not args.reserve_id:
                    resv = r
                    break

        now = time.time()
        if resv is not None:
            prev_epochs = [r.get("epoch", 0) for r in recs if r is not resv]
            prev = max(prev_epochs) if prev_epochs else None
            resv["note_id"] = args.note_id or resv.get("note_id") or ""
            if args.title:
                resv["title"] = args.title
            resv["pending"] = False
            resv["epoch"] = now          # 以"审核确认时刻"为发布时刻（比占位时刻更保守）
            resv["ts"] = _fmt(now)
            actual_gap = int(round(now - prev)) if prev else None
            resv["actual_gap_sec"] = actual_gap
            if not isinstance(resv.get("next_gap"), (int, float)) or resv["next_gap"] <= 0:
                resv["next_gap"] = draw()
            next_gap = int(resv["next_gap"])
            upgraded = True
        else:
            prev = _latest(recs)
            actual_gap = int(round(now - prev["epoch"])) if prev else None
            next_gap = draw()
            recs.append({
                "epoch": now,
                "ts": _fmt(now),
                "note_id": args.note_id,
                "title": args.title,
                "actual_gap_sec": actual_gap,
                "next_gap": next_gap,
            })
            upgraded = False
        _save(recs)

    mode = "固定" if fixed is not None else "随机"
    tail = "（由占位升级）" if upgraded else ""
    print(f"已记录发布时间 {_fmt(now)}{tail}"
          + (f"（距上一篇 {_human(actual_gap)}）" if actual_gap else ""))
    print(f"下一篇目标间隔：{_human(next_gap)}（{mode} {_human(min_sec)}~{_human(max_sec)}）")
    return EXIT_OK


def cmd_reset(args):
    with _file_lock(args.lock_timeout):
        if os.path.exists(LOG):
            os.remove(LOG)
            print(f"已清空发布记录 {LOG}")
        else:
            print("无发布记录")
    return EXIT_OK


def cmd_last(args):
    min_sec, max_sec, fixed, rng, draw = _resolve(args)
    with _file_lock(args.lock_timeout):
        rs = _load()
        _reap(rs, args.pending_ttl)
        r = _latest(rs)
        if r is None:
            print("无发布记录")
            return EXIT_OK
        target = r.get("next_gap")
        if not isinstance(target, (int, float)) or target <= 0:
            target = draw()
            r["next_gap"] = int(target)
            _save(rs)
        left = max(0.0, int(target) - (time.time() - r.get("epoch", 0)))
    print(f"上次发布: {r.get('ts')}  [{_state_of(r)}]")
    print(f"  标题   : {r.get('title')}")
    print(f"  note_id: {r.get('note_id') or '—'}")
    if r.get("reserve_id"):
        print(f"  占位 id: {r.get('reserve_id')}（pid {r.get('pid')}）")
    print(f"  目标间隔: {_human(target)}"
          + (f"（上篇实际间隔 {_human(r['actual_gap_sec'])}）" if r.get("actual_gap_sec") else ""))
    print(f"  还需等待: {_human(left) if left > 0 else '0（可发布）'}")
    return EXIT_OK


def main():
    p = argparse.ArgumentParser(description="小红书连续发布间隔守卫 + 跨进程互斥（8~12 分钟随机）")
    p.add_argument("action",
                   choices=["check", "wait", "reserve", "release", "record", "reset", "last"])
    p.add_argument("--interval", type=int, default=None, help="固定间隔秒数（覆盖随机）")
    p.add_argument("--interval-min", type=int, default=None, help="随机下界秒数，默认 480")
    p.add_argument("--interval-max", type=int, default=None, help="随机上界秒数，默认 720")
    p.add_argument("--max-block", type=int, default=None)
    p.add_argument("--note-id", default=None)
    p.add_argument("--title", default=None)
    p.add_argument("--reserve-id", default=None)
    p.add_argument("--allow-same-title", action="store_true",
                   help="reserve 时放行「标题已存在」（默认拦，防跨进程重复发布）")
    p.add_argument("--pending-ttl", type=int, default=DEFAULT_PENDING_TTL)
    p.add_argument("--lock-timeout", type=int, default=DEFAULT_LOCK_TIMEOUT)
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    if args.max_block is None:
        # wait 默认长阻塞；reserve 默认不阻塞（调用方显式指定才等）
        args.max_block = DEFAULT_MAX_BLOCK if args.action == "wait" else 0

    fn = {
        "check": cmd_check,
        "wait": cmd_wait,
        "reserve": cmd_reserve,
        "release": cmd_release,
        "record": cmd_record,
        "reset": cmd_reset,
        "last": cmd_last,
    }[args.action]
    try:
        return fn(args)
    except LockTimeout as e:
        print(f"LOCK_TIMEOUT: {e}", file=sys.stderr)
        return EXIT_LOCK_TIMEOUT


if __name__ == "__main__":
    sys.exit(main())
