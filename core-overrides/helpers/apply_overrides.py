"""本体覆盖层 —— 把「我们自己的改动」与「上游本体」分开管理。

为什么需要：
  用户原则：**我们自己的更新放 patch，原始本体定期和 GitHub 同步。**
  但发布可靠性/沙箱适配这类改动必须落在本体脚本里才有用（Python 不会自动
  import 一个 patch）。于是本 patch 持有这些文件的**权威副本**，本体里的
  那份只是「应用产物」：
    - 想改 → 改 patch 的 overrides/，再 apply
    - 想同步上游 → 覆盖本体 → 再 apply（我们的改动自动回来）
  这样本体可以被安全覆盖，我们的改动不会被冲掉。

用法：
  status                        本体每个覆盖文件的状态（APPLIED / PRISTINE / DRIFTED）
  verify                        校验本体 == overrides；不一致退出 1
  apply [--dry-run] [--backup]  把 overrides 复制到本体
  rebase                        上游同步后刷新 baseline.json 的上游基线（见下）
  diff [路径]                   显示本体与 override 的差异
  hash                          重新计算并打印各文件指纹

rebase 为什么必须存在：
  baseline.json 里存着「上游原版」的 sha256，用来判断某文件是「上游新版待 apply」
  还是「被人手改过」。上游一更新，旧的 upstream_sha256 就失效了 —— 此时本体的
  新上游内容三者（override / 旧基线 / 上次 apply）都不匹配，会被 status 报成
  DRIFTED「疑似直接改了本体」。照这条提示去「把改动搬进 overrides」，
  等于把上游新版当成我们的定制写进覆盖层 —— 直接污染覆盖层。
  所以：**每次用上游快照覆盖本体之后、apply 之前，必须先跑一次 rebase。**

状态含义：
  APPLIED   本体已应用我们的版本（正常态）
  PRISTINE  本体是上游原版，尚未 apply（同步后、apply 前）
  STALE     覆盖层已更新、本体还是上一次 apply 的版本 —— 跑 apply 即可
  DRIFTED   本体既非我们的版本、也非上游基线、也非上次 apply 版本 ——
            有人直接改了本体，应当把该改动搬进 overrides/，否则下次同步会丢

退出码：
  status  0=全部 APPLIED / 1=存在非 APPLIED / 2=错误
  verify  0=一致 / 1=不一致 / 2=错误
  apply   0=成功 / 2=失败
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime

# 输出统一 UTF-8。
# 为什么必须显式设置：Windows 下 stdout 被重定向到文件或管道时，Python 会退回本地编码
# （本机实测 cp1252），脚本里任何中文 print 都会抛 UnicodeEncodeError 并以退出码 1 结束。
# 现象极具误导性 —— 命令看起来"失败了"，实际只是打印崩了。
# 2026-09-17 实测：`apply_overrides.py status > out.txt` 直接 traceback。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

PATCH_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
OVERRIDES = os.path.join(PATCH_ROOT, "overrides")
BASELINE = os.path.join(PATCH_ROOT, "baseline.json")
STATE_DIR = os.path.join(PATCH_ROOT, "state")
BACKUP_DIR = os.path.join(STATE_DIR, "backup")
APPLIED_STATE = os.path.join(STATE_DIR, "applied.json")

# PATCH_ROOT 是本 patch 目录；默认主 skill 与 patches 目录同级。
# 安装器可用 RED_BOOK_SKILLS_ROOT 指向另一份本体，避免把路径写死。
LOCAL_SKILL = os.path.normpath(
    os.environ.get(
        "RED_BOOK_SKILLS_ROOT",
        os.path.join(PATCH_ROOT, "..", "..", "red-book-skills"),
    )
)

STATUS_APPLIED = "APPLIED"
STATUS_PRISTINE = "PRISTINE"
STATUS_STALE = "STALE"
STATUS_DRIFTED = "DRIFTED"


def _norm(path):
    """读文件并归一化行尾/BOM —— 与 update-checker 同口径，避免 CRLF 假阳性。"""
    with open(path, "rb") as f:
        d = f.read()
    return d.replace(b"\r\n", b"\n").replace(b"\r", b"\n").lstrip(b"\xef\xbb\xbf")


def _sha(path):
    return hashlib.sha256(_norm(path)).hexdigest()


def _load_baseline():
    if not os.path.exists(BASELINE):
        return {"files": {}}
    with open(BASELINE, encoding="utf-8") as f:
        return json.load(f)


def _load_applied():
    if not os.path.exists(APPLIED_STATE):
        return {}
    try:
        with open(APPLIED_STATE, encoding="utf-8") as f:
            return json.load(f).get("files", {})
    except Exception:
        return {}


def _save_applied(files):
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(APPLIED_STATE, "w", encoding="utf-8") as f:
        json.dump(
            {"note": "上次 apply 时写入的覆盖层指纹；用于区分「覆盖层已更新」与「本体被手改」",
             "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
             "files": files},
            f, ensure_ascii=False, indent=2,
        )


def _refresh_override_hashes():
    """apply 后刷新 baseline.json 里的 override_sha256（upstream_sha256 不动）。"""
    base = _load_baseline()
    files = base.get("files")
    if not files:
        return
    for rel in _file_list():
        if rel in files:
            files[rel]["override_sha256"] = _sha(os.path.join(OVERRIDES, rel))
    base["captured_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    with open(BASELINE, "w", encoding="utf-8") as f:
        json.dump(base, f, ensure_ascii=False, indent=2)


def _file_list():
    """overrides/ 下所有文件（相对路径，正斜杠）。"""
    out = []
    for dp, _dns, fns in os.walk(OVERRIDES):
        for fn in fns:
            fp = os.path.join(dp, fn)
            out.append(os.path.relpath(fp, OVERRIDES).replace("\\", "/"))
    return sorted(out)


def _classify(rel, base, applied):
    """返回 (状态, 说明)。"""
    ov = os.path.join(OVERRIDES, rel)
    lo = os.path.join(LOCAL_SKILL, rel)
    if not os.path.exists(lo):
        return STATUS_DRIFTED, "本体内该文件不存在"
    h_ov, h_lo = _sha(ov), _sha(lo)
    if h_ov == h_lo:
        return STATUS_APPLIED, "已应用"
    up = (base.get("files", {}).get(rel) or {}).get("upstream_sha256")
    if up and h_lo == up:
        return STATUS_PRISTINE, "本体为上游原版（尚未 apply）"
    if applied.get(rel) and h_lo == applied[rel]:
        return STATUS_STALE, "覆盖层已更新，本体还是上次 apply 的版本"
    return STATUS_DRIFTED, "本体内容与覆盖层、上游基线、上次 apply 版本都不同 —— 疑似直接改了本体"


def cmd_status(args):
    base = _load_baseline()
    applied = _load_applied()
    files = _file_list()
    print(f"主 skill   : {LOCAL_SKILL}")
    print(f"覆盖文件   : {len(files)} 个")
    print(f"基线 commit: {base.get('baseline_commit', '(无)')}  @ {base.get('baseline_date', '?')}")
    print()
    bad = 0
    for rel in files:
        st, why = _classify(rel, base, applied)
        mark = {"APPLIED": "OK ", "PRISTINE": "!! ", "STALE": ".. ", "DRIFTED": "?? "}[st]
        print(f"  [{mark}] {st:9} {rel}")
        print(f"         {why}")
        if st != STATUS_APPLIED:
            bad += 1
    print()
    if bad == 0:
        print("结论：本体与覆盖层一致（正常态）。")
    elif bad == len(files):
        print("结论：本体全部为上游原版 —— 同步后尚未 apply，请跑 `apply`。")
    else:
        print(f"结论：{bad} 个文件需要处理（见上）。")
    return 0 if bad == 0 else 1


def cmd_verify(args):
    base = _load_baseline()
    applied = _load_applied()
    bad = [r for r in _file_list() if _classify(r, base, applied)[0] != STATUS_APPLIED]
    if bad:
        print("!! 本体与覆盖层不一致：")
        for r in bad:
            st, why = _classify(r, base, applied)
            print(f"   {st:9} {r}  ({why})")
        print("   修复：python helpers/apply_overrides.py apply")
        return 1
    print(f"OK 本体 {len(_file_list())} 个覆盖文件全部与覆盖层一致")
    return 0


def cmd_apply(args):
    base = _load_baseline()
    applied = _load_applied()
    files = _file_list()
    todo = []
    for rel in files:
        st, why = _classify(rel, base, applied)
        if st != STATUS_APPLIED:
            todo.append((rel, st, why))

    if not todo:
        print(f"OK 无需应用：{len(files)} 个文件均已一致")
        return 0

    print(f"将写入 {len(todo)} 个文件到 {LOCAL_SKILL}")
    for rel, st, why in todo:
        print(f"   {rel:34} [{st}] {why}")

    if args.dry_run:
        print("\n(--dry-run：未做任何修改)")
        return 0

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = os.path.join(BACKUP_DIR, stamp)
    for rel, _st, _why in todo:
        lo = os.path.join(LOCAL_SKILL, rel)
        if os.path.exists(lo):
            bp = os.path.join(dest, rel)
            os.makedirs(os.path.dirname(bp), exist_ok=True)
            shutil.copy2(lo, bp)
    print(f"\n已备份原文件 → {dest}")

    for rel, _st, _why in todo:
        src = os.path.join(OVERRIDES, rel)
        lo = os.path.join(LOCAL_SKILL, rel)
        os.makedirs(os.path.dirname(lo), exist_ok=True)
        shutil.copy2(src, lo)
        print(f"   写入 {rel}")

    _save_applied({rel: _sha(os.path.join(OVERRIDES, rel)) for rel in files})
    _refresh_override_hashes()
    print()
    return cmd_verify(args)


def cmd_rebase(args):
    """把 baseline.json 的上游基线推进到「当前上游版本」。

    两种取上游原版的方式：
      --from <dir>   从上游快照目录读（推荐，与执行时机无关，最准）
      缺省           从本体读；此时若文件处于 APPLIED 状态则拒绝，
                     因为读到的会是我们自己的覆盖版本而非上游原版
    """
    base = _load_baseline()
    applied = _load_applied()
    files = _file_list()
    src_dir = args.source

    if src_dir and not os.path.isdir(src_dir):
        print(f"!! 上游快照目录不存在：{src_dir}", file=sys.stderr)
        return 2

    if not src_dir:
        risky = []
        for rel in files:
            lo = os.path.join(LOCAL_SKILL, rel)
            if os.path.exists(lo) and _sha(lo) == _sha(os.path.join(OVERRIDES, rel)):
                risky.append(rel)
        if risky:
            print("!! 拒绝 rebase：以下文件本体 == 覆盖层（已 apply），"
                  "无法从中读出上游原版：", file=sys.stderr)
            for r in risky:
                print(f"     {r}", file=sys.stderr)
            print("\n   请改用 --from <上游快照目录>，或先用上游快照覆盖本体再跑本命令。",
                  file=sys.stderr)
            return 2

    result = {}
    for rel in files:
        if src_dir:
            up_file = os.path.join(src_dir, rel)
        else:
            up_file = os.path.join(LOCAL_SKILL, rel)
        if os.path.exists(up_file):
            result[rel] = _sha(up_file)
        else:
            # 上游没有这个文件（例如我们自己新增的 references/）—— 记为缺席
            result[rel] = None

    changed, absent, unchanged = [], [], []
    old_files = base.setdefault("files", {})
    for rel, h in result.items():
        old = (old_files.get(rel) or {}).get("upstream_sha256")
        entry = old_files.setdefault(rel, {})
        if h is None:
            entry["upstream_sha256"] = None
            entry["upstream_absent"] = True
            absent.append(rel)
        else:
            entry["upstream_sha256"] = h
            entry.pop("upstream_absent", None)
            if old != h:
                changed.append(rel)
            else:
                unchanged.append(rel)

    if args.commit:
        base["baseline_commit"] = args.commit
    if args.date:
        base["baseline_date"] = args.date
    base["captured_at"] = datetime.now().astimezone().isoformat(timespec="seconds")

    os.makedirs(PATCH_ROOT, exist_ok=True)
    with open(BASELINE, "w", encoding="utf-8") as f:
        json.dump(base, f, ensure_ascii=False, indent=2)

    print(f"上游基线已推进  ({'来源: ' + src_dir if src_dir else '来源: 本体（未 apply 状态）'})")
    print(f"  baseline_commit: {base.get('baseline_commit', '(未设置)')}")
    print()
    print(f"  upstream_sha256 变化   {len(changed)} 个")
    for r in changed:
        print(f"      {r}")
    print(f"  upstream_sha256 未变   {len(unchanged)} 个")
    print(f"  上游无此文件            {len(absent)} 个（我们独有，正常）")
    for r in absent:
        print(f"      {r}")
    print()
    if changed:
        print("!! 上游改动了被我们覆盖的文件 —— 覆盖层还是旧版，直接 apply 会回退上游改动。")
        print("   1) 读上游新版对应段落，把上游改动人工合并进 core-overrides/overrides/")
        for r in changed:
            print(f"      - {r}")
        print("   2) 合并完再跑 apply；只有确认「上游改动与我们无关」才可跳过第 1 步")
    else:
        print("上游未改动被覆盖文件 —— 可直接 apply。")
    print("\n下一步：python helpers/apply_overrides.py apply")
    return 0


def cmd_diff(args):
    base = _load_baseline()
    files = _file_list()
    targets = [args.path] if args.path else files
    for rel in targets:
        if rel not in files:
            print(f"!! 不在覆盖清单中：{rel}", file=sys.stderr)
            return 2
        ov, lo = os.path.join(OVERRIDES, rel), os.path.join(LOCAL_SKILL, rel)
        r = subprocess.run(
            ["diff", "--strip-trailing-cr", "-u", lo, ov],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        print(f"================ {rel}  (本体 → 覆盖层) ================")
        print(r.stdout or "（无差异）")
    return 0


def cmd_hash(args):
    base = _load_baseline()
    for rel in _file_list():
        ov, lo = os.path.join(OVERRIDES, rel), os.path.join(LOCAL_SKILL, rel)
        up = (base.get("files", {}).get(rel) or {}).get("upstream_sha256", "(未记录)")
        print(f"{rel}")
        print(f"    upstream {up[:16] if up != '(未记录)' else up}")
        print(f"    override {_sha(ov)[:16]}")
        if os.path.exists(lo):
            print(f"    local    {_sha(lo)[:16]}")
    return 0


def main():
    p = argparse.ArgumentParser(description="本体覆盖层：应用/校验我们自己的改动")
    p.add_argument("action", choices=["status", "verify", "apply", "rebase", "diff", "hash"])
    p.add_argument("path", nargs="?", help="(diff 用) 指定单个文件")
    p.add_argument("--dry-run", action="store_true", help="(apply 用) 只报告不写入")
    p.add_argument("--backup", action="store_true", help="(apply 用) 保留原文件备份（默认即备份）")
    p.add_argument("--from", dest="source", help="(rebase 用) 上游快照解压目录，推荐显式指定")
    p.add_argument("--commit", help="(rebase 用) 新的上游 commit sha")
    p.add_argument("--date", help="(rebase 用) 新的上游 commit 日期 ISO8601")
    args = p.parse_args()

    if not os.path.isdir(LOCAL_SKILL):
        print(f"!! 主 skill 目录不存在：{LOCAL_SKILL}", file=sys.stderr)
        return 2
    if not os.path.isdir(OVERRIDES):
        print(f"!! overrides 目录不存在：{OVERRIDES}", file=sys.stderr)
        return 2

    return {
        "status": cmd_status,
        "verify": cmd_verify,
        "apply": cmd_apply,
        "rebase": cmd_rebase,
        "diff": cmd_diff,
        "hash": cmd_hash,
    }[args.action](args)


if __name__ == "__main__":
    sys.exit(main())
