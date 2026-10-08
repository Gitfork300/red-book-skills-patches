"""Single-instance lock helpers for publish scripts.

── 2026-09-17 修复说明（核心） ──────────────────────────────────────────
原实现是「O_EXCL 建文件 = 拿锁，删文件 = 放锁」，并在 O_EXCL 失败时调用
_cleanup_stale_lock() 判断旧锁是否失效。它有一个必然触发的竞态：

    进程 A: os.open(O_CREAT|O_EXCL) 成功  →  文件已存在但**内容还是空的**
    进程 B: os.open 抛 FileExistsError
            → _read_lock_data() 读到空文件 → json.load 抛异常 → 返回 {}
            → pid = None → `isinstance(pid, int)` 为假 → **跳过存活判断**
            → os.remove(path) 成功 → 判定"旧锁已失效"
            → B 建自己的锁，认为自己持有
    进程 A: 继续写 payload（写进已被删除的 inode），也认为自己持有
    ⇒ 双方同时持锁

实测证据（2026-09-17）：同一批 A 被并发跑了两遍，3 组笔记的 note_id
解码后两两相差 2~6 秒（6aab2fec/6aab2ff0、6aab3399/6aab339b、6aab363f/6aab3645），
即两条完整发布管线同时在跑。

修复采用操作系统级咨询锁（msvcrt.locking / fcntl.flock）：
  - 锁由内核按文件句柄管理，关闭句柄即释放，进程崩溃也自动释放；
  - **全程不需要删除锁文件**，因此既没有"删文件失败就死锁"的问题
    （本机 python 被沙箱 shim 接管，os.remove 可能 fail-closed），
    也没有"删掉别人的锁"的竞态；
  - 锁文件常驻 temp 目录，只承载锁本身，属正常现象。

同时保留 pid/started_at 元数据，但**仅用于冲突报错时给出线索**，不参与锁判定。
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any

try:  # Python 3.11+
    from typing import Self  # noqa: F401
except ImportError:  # pragma: no cover
    pass


class SingleInstanceError(RuntimeError):
    """Raised when another publish process is already running."""


# 等锁上限。持锁方是整条发布流程（最长约 10 分钟），所以这里的默认值只用于
# "拿不到就快速失败"，真正的等待由调用方（批次脚本）决定。
DEFAULT_LOCK_TIMEOUT = 5.0


def _lock_path(lock_name: str) -> str:
    safe_name = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in lock_name)
    return os.path.join(tempfile.gettempdir(), f"{safe_name}.lock")


def _os_lock_acquire(fd: int) -> None:
    """非阻塞地尝试独占锁；已被占用则抛 OSError。"""
    if os.name == "nt":
        import msvcrt

        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
    else:
        import fcntl

        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)


def _os_lock_release(fd: int) -> None:
    if os.name == "nt":
        import msvcrt

        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(fd, fcntl.LOCK_UN)


def _read_lock_data(path: str) -> dict[str, Any]:
    """读锁文件里的持有者元数据（仅用于报错，不参与锁判定）。"""
    try:
        with open(path, "r", encoding="utf-8") as file_handle:
            data = json.load(file_handle)
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def _format_conflict_message(path: str, lock_data: dict[str, Any]) -> str:
    pid = lock_data.get("pid")
    started_at = lock_data.get("started_at")

    if isinstance(pid, int):
        msg = f"Another publish process is running (pid={pid})"
        if isinstance(started_at, str) and started_at:
            msg += f", started at {started_at}"
        argv = lock_data.get("argv")
        if isinstance(argv, list) and argv:
            msg += f", argv={' '.join(str(a) for a in argv[:6])}"
        return msg + ". Please wait or terminate it before retrying."

    return (
        f"Another publish process is running (lock: {path}). "
        "Please wait before retrying."
    )


@contextmanager
def single_instance(lock_name: str = "post_to_xhs_publish", timeout: float = DEFAULT_LOCK_TIMEOUT):
    """Acquire a process-wide lock to prevent concurrent publish runs.

    锁由内核按文件句柄持有；yield 期间一直持有，退出 with 块自动释放。
    timeout 秒内拿不到锁就抛 SingleInstanceError。
    """
    import time

    path = _lock_path(lock_name)
    os.makedirs(os.path.dirname(path), exist_ok=True)

    fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    deadline = time.time() + max(0.0, timeout)
    acquired = False
    try:
        while True:
            try:
                _os_lock_acquire(fd)
                acquired = True
                break
            except OSError:
                if time.time() >= deadline:
                    raise SingleInstanceError(
                        _format_conflict_message(path, _read_lock_data(path))
                    ) from None
                time.sleep(0.1)

        # 拿到锁后写入元数据（诊断用；写失败不影响持锁）
        try:
            payload = {
                "pid": os.getpid(),
                "started_at": datetime.now(timezone.utc).isoformat(),
                "argv": sys.argv,
                "cwd": os.getcwd(),
            }
            os.lseek(fd, 0, os.SEEK_SET)
            os.truncate(fd, 0)
            os.write(fd, json.dumps(payload, ensure_ascii=False).encode("utf-8"))
            os.fsync(fd)
        except Exception:
            pass

        yield
    finally:
        if acquired:
            try:
                _os_lock_release(fd)
            except Exception:
                pass
        try:
            os.close(fd)
        except Exception:
            pass
