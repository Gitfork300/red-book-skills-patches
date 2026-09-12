# -*- coding: utf-8 -*-
"""
red-book-skills 定期版本备份（工作区真实快照，含未提交/未跟踪文件）

为什么不用 git bundle 单独做备份？
    git 只管"已跟踪且已提交"的内容。本体里有 3 类东西它管不到：
      - 未跟踪文件：helpers/README.md、scripts/xhs_publish_fail.png
      - 被 .gitignore 排除的文件（config/ 下的配置）
      - 工作区里 4 个 modified 的覆盖产物（HEAD 是纯上游，改动没提交）
    所以这里对**工作区目录**做 tar 快照，把 .git 目录一并打进去 ——
    解压即得到"带完整 git 历史的完整工作区"，恢复成本最低。

备份产物结构（DEST = ~/Documents/red-book-skills-backup/）：
    README.md                     恢复说明（脚本自动生成/维护）
    latest.json                   最近一次成功的指纹与快照路径
    FAILED.txt                    仅失败时存在，成功即删除（失败信号）
    logs/backup-YYYY-MM.log       每次运行一行
    snapshots/<ts>_<fp8>/
        META.json                 时间、指纹、两仓 git HEAD、文件数、体积、排除项
        body.tar.gz               本体工作区（排除 .venv/tmp/__pycache__ 等）
        patches.tar.gz            补丁仓工作区（排除 state/backup 等）

去重：内容指纹（逐文件 sha256 聚合）与上次一致 → 不留新快照，直接跳过。
轮转：只保留最近 --keep 个快照（默认 30），更旧的本工具自己删。

用法：
    python backup_snapshots.py                 # 常规运行（无变化则跳过）
    python backup_snapshots.py --force         # 强制留一份快照
    python backup_snapshots.py --keep 30       # 指定保留份数
    python backup_snapshots.py --list          # 只列出现有快照
    python backup_snapshots.py --restore <目录> [--dest <目标>]
                                               # 从快照恢复（默认恢复到临时目录）

退出码：0=成功或无需备份；1=失败（同时写 FAILED.txt）
"""

import argparse
import fnmatch
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import traceback
from datetime import datetime

HOME = os.path.expanduser("~")
BODY = os.path.join(HOME, ".workbuddy", "skills", "red-book-skills")
PATCH = os.path.join(HOME, ".workbuddy", "skills", "red-book-skills-patches")
DEFAULT_DEST = os.path.join(HOME, "Documents", "red-book-skills-backup")

# 排除规则：dirnames 按目录名任意层级匹配；rel_prefixes 按相对路径前缀；globs 按文件名
RULES = {
    "body": {
        "dirnames": {".venv", "venv", "tmp", "__pycache__", ".pytest_cache", "node_modules"},
        "rel_prefixes": (),
        "globs": ("*.pyc", "*.pyo", "*.bak", "*.swp", "*.log"),
    },
    "patches": {
        "dirnames": {"__pycache__", ".pytest_cache", "node_modules"},
        "rel_prefixes": ("core-overrides/state/backup",),
        "globs": ("*.pyc", "*.pyo", "*.bak", "*.swp"),
    },
}

# 凭据类文件：默认不纳入备份（本目录可能被云同步/分享）。
# 想连它一起备份，把下面改为 True。
INCLUDE_CREDENTIALS = False
CREDENTIAL_FILES = ("config/accounts.json",)


def out(msg=""):
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("utf-8", "replace").decode("ascii", "replace"))


def sha256_file(path, buf=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(buf)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def git(repo, *args):
    """本地 git 查询；失败返回 None（不抛异常，备份不依赖 git）"""
    try:
        r = subprocess.run(["git", "-C", repo] + list(args),
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=60)
        return r.stdout.strip() if r.returncode == 0 else None
    except Exception:
        return None


def collect(root, rule):
    """返回 [(abs_path, rel_path)]，已应用排除规则"""
    files = []
    if not os.path.isdir(root):
        return files
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = os.path.relpath(dirpath, root).replace(os.sep, "/")
        rel_dir = "" if rel_dir == "." else rel_dir
        # 目录级排除
        dirnames[:] = sorted(d for d in dirnames if d not in rule["dirnames"])
        if rel_dir:
            if any(rel_dir == p or rel_dir.startswith(p + "/") for p in rule["rel_prefixes"]):
                dirnames[:] = []
                continue
            if any(rel_dir.startswith(p) for p in rule["rel_prefixes"]):
                dirnames[:] = []
                continue
        for fn in sorted(filenames):
            rel = (rel_dir + "/" + fn) if rel_dir else fn
            if any(fnmatch.fnmatch(fn, g) for g in rule["globs"]):
                continue
            if not INCLUDE_CREDENTIALS and root == BODY and rel in CREDENTIAL_FILES:
                continue
            files.append((os.path.join(dirpath, fn), rel))
    return files


def fingerprint(files):
    """内容指纹：逐文件 sha256（含路径），聚合后取前 16 位"""
    h = hashlib.sha256()
    for abs_p, rel in sorted(files, key=lambda x: x[1]):
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        h.update(sha256_file(abs_p).encode("ascii"))
        h.update(b"\n")
    return h.hexdigest()[:16]


def pack(root, files, out_tar, arc_base):
    """把文件列表打成 tar.gz；用 create 前算好的清单，避免边扫边变"""
    with tarfile.open(out_tar, "w:gz", compresslevel=6) as tf:
        for abs_p, rel in sorted(files, key=lambda x: x[1]):
            tf.add(abs_p, arcname=arc_base + "/" + rel, recursive=False)
    return os.path.getsize(out_tar)


def verify_tar(tar_path, files, arc_base):
    """回读校验：条目数 + 逐文件 sha256 与打包前清单一致。
    不一致说明打包期间文件被改动（自动化并发写入），需要重来。"""
    expected = {rel: sha256_file(a) for a, rel in files}
    seen = {}
    with tarfile.open(tar_path, "r:gz") as tf:
        for ti in tf:
            if not ti.isfile():
                continue
            key = ti.name[len(arc_base) + 1:] if ti.name.startswith(arc_base + "/") else ti.name
            fh = tf.extractfile(ti)
            if fh is None:
                return False, "无法读取成员: %s" % ti.name
            h = hashlib.sha256()
            while True:
                chunk = fh.read(1 << 20)
                if not chunk:
                    break
                h.update(chunk)
            seen[key] = h.hexdigest()
    if set(seen) != set(expected):
        miss = sorted(set(expected) - set(seen))[:5]
        extra = sorted(set(seen) - set(expected))[:5]
        return False, "条目不一致 缺失=%s 多出=%s" % (miss, extra)
    bad = [k for k in expected if expected[k] != seen[k]]
    if bad:
        return False, "内容不一致(%d 个，例: %s)" % (len(bad), bad[:3])
    return True, "OK (%d 文件全部一致)" % len(expected)


def human(n):
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024 or u == "GB":
            return "%.1f %s" % (n, u) if u != "B" else "%d B" % n
        n /= 1024.0


def write_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def log_line(dest, text):
    d = os.path.join(dest, "logs")
    os.makedirs(d, exist_ok=True)
    fn = os.path.join(d, "backup-%s.log" % datetime.now().strftime("%Y-%m"))
    with open(fn, "a", encoding="utf-8") as fh:
        fh.write("[%s] %s\n" % (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), text))


FAIL_NAME = "FAILED.txt"
DESKTOP_ALERT = "!!备份失败-red-book-skills.txt"


def desktop_dir():
    """真实桌面路径。Windows 下桌面常被 OneDrive 重定向，不能假设 ~/Desktop。"""
    if os.name == "nt":
        try:
            import winreg
            k = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                               r"Software\Microsoft\Windows\CurrentVersion"
                               r"\Explorer\User Shell Folders")
            v, _ = winreg.QueryValueEx(k, "Desktop")
            p = os.path.expandvars(v)
            if os.path.isdir(p):
                return p
        except Exception:
            pass
    for cand in (os.path.join(HOME, "Desktop"),
                 os.path.join(HOME, "OneDrive", "Desktop"),
                 os.path.join(HOME, "OneDrive - 个人", "Desktop")):
        if os.path.isdir(cand):
            return cand
    return None


def desktop_alert(stage, exc_text, fp):
    """桌面告警：进程/机器层面的显眼提示。失败必写，成功必清。"""
    d = desktop_dir()
    if not d:
        return None
    p = os.path.join(d, DESKTOP_ALERT)
    try:
        with open(p, "w", encoding="utf-8") as fh:
            fh.write("red-book-skills 备份失败\n")
            fh.write("=" * 40 + "\n")
            fh.write("时间: %s\n" % datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            fh.write("阶段: %s\n\n" % stage)
            fh.write("这意味着「定期版本备份」没有产生新快照，\n")
            fh.write("期间的改动处于无备份保护状态。\n\n")
            fh.write("完整错误详情见:\n  %s\n\n" % fp)
            fh.write("错误摘要:\n%s\n\n" % "\n".join(exc_text.strip().splitlines()[-12:]))
            fh.write("处理后重跑:\n")
            fh.write('  python "%s" --force\n' % os.path.join(PATCH, "tools", "backup_snapshots.py"))
            fh.write("\n（备份成功时本文件会被自动删除）\n")
        return p
    except Exception:
        return None


def desktop_alert_clear():
    d = desktop_dir()
    if not d:
        return
    p = os.path.join(d, DESKTOP_ALERT)
    if os.path.exists(p):
        try:
            os.remove(p)
        except Exception:
            pass


def fail(dest, stage, exc_text):
    """失败信号：写 FAILED.txt + 桌面告警（成功时两者都自动删除）"""
    os.makedirs(dest, exist_ok=True)
    fp = os.path.join(dest, FAIL_NAME)
    with open(fp, "w", encoding="utf-8") as fh:
        fh.write("red-book-skills 备份失败\n")
        fh.write("时间   : %s\n" % datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        fh.write("阶段   : %s\n" % stage)
        fh.write("详情   :\n%s\n" % exc_text)
        fh.write("\n处理：修复后运行 python \"%s\" --force\n"
                 % os.path.join(PATCH, "tools", "backup_snapshots.py"))
    dp = desktop_alert(stage, exc_text, fp)
    log_line(dest, "FAILED at %s :: %s%s"
             % (stage, exc_text.strip().splitlines()[-1] if exc_text.strip() else "",
                "  桌面告警=%s" % dp if dp else "  (桌面告警不可用)"))
    return fp


def clear_alerts(dest):
    """备份确实成功（或探测到无变化）时，撤掉所有告警信号"""
    fp = os.path.join(dest, FAIL_NAME)
    if os.path.exists(fp):
        try:
            os.remove(fp)
        except Exception:
            pass
    desktop_alert_clear()


def make_readme(dest):
    txt = """# red-book-skills 版本备份

由 `red-book-skills-patches/tools/backup_snapshots.py` 定期生成，**不要手工改动本目录的
`snapshots/` 结构**（命名格式被轮转逻辑依赖）。

## 里面是什么

每个 `snapshots/<时间戳>_<指纹>/` 是一份完整可恢复的快照：

| 文件 | 内容 |
| --- | --- |
| `body.tar.gz` | 本体工作区 `~/.workbuddy/skills/red-book-skills/`（含 `.git`、未跟踪文件、未提交的覆盖产物） |
| `patches.tar.gz` | 补丁仓 `~/.workbuddy/skills/red-book-skills-patches/`（含 `.git`） |
| `META.json` | 生成时间、内容指纹、两仓 git HEAD、文件数、体积、当时生效的排除规则 |

排除项（可重建，不进备份）：本体的 `.venv/ tmp/ __pycache__/ .pytest_cache/`、
补丁仓的 `core-overrides/state/backup/`、`*.pyc/*.bak/*.swp`。
`config/accounts.json`（凭据）默认**不在**备份内，如需纳入见脚本顶部 `INCLUDE_CREDENTIALS`。

## 怎么恢复

```bash
PY="<python>"
S="$PY <patches>/tools/backup_snapshots.py"

# 1) 看有哪些快照
$S --list

# 2) 解压到临时目录先检查（默认行为）
$S --restore 20260912_1015_ab12cd34
#    指定目标目录
$S --restore 20260912_1015_ab12cd34 --target /tmp/restore_check

# 3) 确认无误后再覆盖本体（先手工备份当前目录！）
#    tar xzf <快照>/body.tar.gz -C ~/.workbuddy/skills/
```

## 告警

备份失败时会同时留下**两处**信号，任何一处存在都表示"最近一次备份没成功"：

| 位置 | 文件 |
| --- | --- |
| 本目录 | `FAILED.txt`（含阶段与完整 traceback） |
| 桌面 | `!!备份失败-red-book-skills.txt`（显眼提示，含摘要与处理步骤） |

**两者都在备份成功（或检测到内容无变化）时被自动删除**，所以在 = 待处理。
桌面路径从注册表读取，兼容 OneDrive 重定向的桌面。
"""
    fp = os.path.join(dest, "README.md")
    with open(fp, "w", encoding="utf-8") as fh:
        fh.write(txt)
    return fp


def rotate(dest, keep):
    """只删本工具生成格式的快照目录，最旧的先删"""
    snap = os.path.join(dest, "snapshots")
    if not os.path.isdir(snap):
        return []
    items = []
    for e in os.listdir(snap):
        fp = os.path.join(snap, e)
        if os.path.isdir(fp) and len(e) > 9 and e[8] == "_":
            items.append(e)
    items.sort()
    removed = []
    for e in items[:-keep] if keep > 0 else []:
        shutil.rmtree(os.path.join(snap, e), ignore_errors=True)
        removed.append(e)
    return removed


def do_backup(dest, keep, force):
    os.makedirs(dest, exist_ok=True)
    os.makedirs(os.path.join(dest, "snapshots"), exist_ok=True)
    make_readme(dest)

    body_files = collect(BODY, RULES["body"])
    patch_files = collect(PATCH, RULES["patches"])
    if not body_files:
        raise RuntimeError("本体目录没有采集到任何文件，路径可能不对: %s" % BODY)
    if not patch_files:
        raise RuntimeError("补丁目录没有采集到任何文件，路径可能不对: %s" % PATCH)

    body_fp = fingerprint(body_files)
    patch_fp = fingerprint(patch_files)
    combined = hashlib.sha256((body_fp + patch_fp).encode()).hexdigest()[:16]

    latest_p = os.path.join(dest, "latest.json")
    latest = {}
    if os.path.isfile(latest_p):
        try:
            with open(latest_p, encoding="utf-8") as fh:
                latest = json.load(fh)
        except Exception:
            latest = {}

    body_sz = sum(os.path.getsize(a) for a, _ in body_files)
    patch_sz = sum(os.path.getsize(a) for a, _ in patch_files)

    if not force and latest.get("fingerprint") == combined:
        msg = ("无变化，跳过备份（指纹 %s）；上次快照 %s"
               % (combined, latest.get("snapshot", "?")))
        out("[skip] " + msg)
        log_line(dest, "SKIP " + msg)
        clear_alerts(dest)         # 上轮可能失败；这轮探测通过 → 撤告警
        return {"status": "skip", "fingerprint": combined}

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    name = "%s_%s" % (ts, combined)
    snap_dir = os.path.join(dest, "snapshots", name)
    stage_dir = snap_dir + ".part"
    if os.path.isdir(stage_dir):
        shutil.rmtree(stage_dir, ignore_errors=True)
    os.makedirs(stage_dir)

    try:
        results = []
        for label, root, files, sz in (("body", BODY, body_files, body_sz),
                                       ("patches", PATCH, patch_files, patch_sz)):
            tar_path = os.path.join(stage_dir, "%s.tar.gz" % label)
            base = "red-book-skills" if label == "body" else "red-book-skills-patches"
            tries = 0
            while True:
                tries += 1
                pack(root, files, tar_path, base)
                ok, detail = verify_tar(tar_path, files, base)
                if ok:
                    break
                if tries >= 3:
                    raise RuntimeError("%s.tar.gz 校验失败（重试 %d 次）：%s" % (label, tries, detail))
                out("[retry] %s.tar.gz 校验失败，重打包：%s" % (label, detail))
                files = collect(root, RULES[label])       # 重新采集后再试
                body_files = files if label == "body" else body_files
                patch_files = files if label == "patches" else patch_files
                if label == "body":
                    body_sz = sum(os.path.getsize(a) for a, _ in files)
                else:
                    patch_sz = sum(os.path.getsize(a) for a, _ in files)
            results.append((label, tar_path, len(files), sz, detail))
            out("[pack] %-8s %6d 文件  %s  ← %s"
                % (label, len(files), human(os.path.getsize(tar_path)), detail))

        meta = {
            "created_at": datetime.now().astimezone().isoformat(),
            "fingerprint": combined,
            "body": {
                "path": BODY,
                "files": len(body_files),
                "bytes": body_sz,
                "fingerprint": body_fp,
                "git_head": git(BODY, "rev-parse", "HEAD"),
                "git_branch": git(BODY, "rev-parse", "--abbrev-ref", "HEAD"),
                "git_dirty": len((git(BODY, "status", "--porcelain", "-uall") or "").splitlines()),
            },
            "patches": {
                "path": PATCH,
                "files": len(patch_files),
                "bytes": patch_sz,
                "fingerprint": patch_fp,
                "git_head": git(PATCH, "rev-parse", "HEAD"),
                "git_branch": git(PATCH, "rev-parse", "--abbrev-ref", "HEAD"),
                "git_dirty": len((git(PATCH, "status", "--porcelain", "-uall") or "").splitlines()),
            },
            "excludes": {
                "body_dirnames": sorted(RULES["body"]["dirnames"]),
                "patches_dirnames": sorted(RULES["patches"]["dirnames"]),
                "patches_rel_prefixes": list(RULES["patches"]["rel_prefixes"]),
                "globs": sorted(set(RULES["body"]["globs"]) | set(RULES["patches"]["globs"])),
                "credentials_included": INCLUDE_CREDENTIALS,
            },
            "tool": "red-book-skills-patches/tools/backup_snapshots.py",
        }
        write_json(os.path.join(stage_dir, "META.json"), meta)
        write_json(os.path.join(stage_dir, "MANIFEST.json"),
                   {"files": {"body": sorted(r for _, r in body_files),
                              "patches": sorted(r for _, r in patch_files)}})
        os.replace(stage_dir, snap_dir)                  # 原子落盘：只有完整快照才可见
    except Exception:
        shutil.rmtree(stage_dir, ignore_errors=True)
        raise

    total = sum(os.path.getsize(os.path.join(snap_dir, f)) for f in os.listdir(snap_dir))
    removed = rotate(dest, keep)

    write_json(latest_p, {
        "fingerprint": combined,
        "snapshot": name,
        "created_at": meta["created_at"],
        "body_git_head": meta["body"]["git_head"],
        "patches_git_head": meta["patches"]["git_head"],
        "body_files": meta["body"]["files"],
        "patches_files": meta["patches"]["files"],
    })
    clear_alerts(dest)

    msg = ("新快照 %s | 本体 %d 文件(HEAD %s) + 补丁 %d 文件(HEAD %s) | 体积 %s | 轮转删除 %s"
           % (name, len(body_files), (meta["body"]["git_head"] or "?")[:7],
              len(patch_files), (meta["patches"]["git_head"] or "?")[:7],
              human(total), removed or "无"))
    out("[ok] " + msg)
    log_line(dest, "OK " + msg)
    return {"status": "created", "snapshot": snap_dir, "fingerprint": combined,
            "bytes": total, "removed": removed}


def do_list(dest):
    snap = os.path.join(dest, "snapshots")
    if not os.path.isdir(snap):
        out("(还没有任何快照：%s)" % snap)
        return 0
    items = sorted(e for e in os.listdir(snap)
                   if os.path.isdir(os.path.join(snap, e)))
    out("备份目录: %s" % dest)
    out("快照数: %d" % len(items))
    for e in items:
        fp = os.path.join(snap, e)
        sz = sum(os.path.getsize(os.path.join(r, f))
                 for r, _, fs in os.walk(fp) for f in fs)
        meta_p = os.path.join(fp, "META.json")
        head = ""
        if os.path.isfile(meta_p):
            try:
                with open(meta_p, encoding="utf-8") as fh:
                    m = json.load(fh)
                head = " body=%s patches=%s" % ((m["body"]["git_head"] or "?")[:7],
                                                (m["patches"]["git_head"] or "?")[:7])
            except Exception:
                pass
        out("  %-26s %9s%s" % (e, human(sz), head))
    fflag = os.path.join(dest, FAIL_NAME)
    out("告警(备份目录): %s" % ("存在 → %s" % fflag if os.path.exists(fflag) else "无（最近一次成功）"))
    d = desktop_dir()
    if d:
        dalert = os.path.join(d, DESKTOP_ALERT)
        out("告警(桌面)    : %s" % ("存在 → %s" % dalert if os.path.exists(dalert)
                                    else "无（桌面 %s）" % d))
    else:
        out("告警(桌面)    : 未找到桌面路径，跳过")
    return 0


def do_restore(dest, name, target):
    snap_dir = os.path.join(dest, "snapshots", name)
    if not os.path.isdir(snap_dir):
        cands = sorted(e for e in os.listdir(os.path.join(dest, "snapshots"))
                       if e.startswith(name)) if os.path.isdir(os.path.join(dest, "snapshots")) else []
        if len(cands) == 1:
            snap_dir = os.path.join(dest, "snapshots", cands[0])
            name = cands[0]
        else:
            out("找不到快照 %s（候选: %s）" % (name, cands or "无"))
            return 1
    if not target:
        target = tempfile.mkdtemp(prefix="rbs-restore-")
    os.makedirs(target, exist_ok=True)
    with tarfile.open(os.path.join(snap_dir, "body.tar.gz"), "r:gz") as tf:
        tf.extractall(target)
    with tarfile.open(os.path.join(snap_dir, "patches.tar.gz"), "r:gz") as tf:
        tf.extractall(target)
    out("已恢复到: %s" % target)
    out("（含 body/ 与 patches/ 两个目录，各自带 .git 历史。确认无误后再覆盖真实路径）")
    return 0


def main():
    ap = argparse.ArgumentParser(description="red-book-skills 定期版本备份")
    ap.add_argument("--dest", default=DEFAULT_DEST)
    ap.add_argument("--keep", type=int, default=30, help="保留最近 N 个快照（默认 30）")
    ap.add_argument("--force", action="store_true", help="无变化也留一份快照")
    ap.add_argument("--list", action="store_true", help="列出现有快照")
    ap.add_argument("--restore", metavar="SNAPSHOT", help="从指定快照恢复")
    args = ap.parse_args()

    dest = os.path.abspath(os.path.expanduser(args.dest))
    if args.list:
        return do_list(dest)
    if args.restore:
        return do_restore(dest, args.restore, None if args.dest == DEFAULT_DEST else dest)

    try:
        res = do_backup(dest, args.keep, args.force)
        out(json.dumps(res, ensure_ascii=False))
        return 0
    except Exception:
        tb = traceback.format_exc()
        p = fail(dest, "backup", tb)
        out("[FAIL] 备份失败，已写告警文件: %s" % p)
        out(tb)
        return 1


if __name__ == "__main__":
    sys.exit(main())
