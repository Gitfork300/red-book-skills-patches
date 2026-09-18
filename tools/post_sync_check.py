"""上游同步后的自检 —— 回答两个 diff/apply 都回答不了的问题。

背景：
  core-overrides 用「整文件覆盖」。这带来一个隐性代价：
  1. 上游对我们覆盖的 3 个脚本的任何后续改动，我们**拿不到**（文件被我们锁死在旧版）；
  2. 上游若删改了我们依赖的符号，覆盖层 apply 照样成功，但**运行时才炸**。

  `apply status/verify` 只回答「我们的东西叠回去没有」，回答不了上面两条。
  本脚本补上：
    - 契约检查：我们依赖的上游符号还在不在（contracts.json）
    - 吸收检查：上游在我们锁死的文件里改了多少、我们还没吸收哪些

用法：
  python tools/post_sync_check.py                        # 自检（不联网，随时可跑）
  python tools/post_sync_check.py --upstream <快照目录>   # 同步后：拿上游新版做 BREAKING 探测
  python tools/post_sync_check.py --upstream <dir> --json

退出码：
  0  全通过
  1  有警告（上游存在我们未吸收的改动，需人工评估）
  2  BREAKING：上游删改了我们依赖的符号 / 契约文件缺失 / 覆盖层未 apply
"""
import argparse
import difflib
import json
import os
import subprocess
import sys

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

PATCH_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
CORE = os.path.join(PATCH_ROOT, "core-overrides")
OVERRIDES = os.path.join(CORE, "overrides")
CONTRACTS = os.path.join(CORE, "contracts.json")
LOCAL_SKILL = os.path.normpath(
    os.environ.get("RED_BOOK_SKILLS_ROOT", os.path.join(PATCH_ROOT, "..", "red-book-skills"))
)
APPLY = os.path.join(CORE, "helpers", "apply_overrides.py")

EXIT_OK, EXIT_WARN, EXIT_FAIL = 0, 1, 2


def _read(path):
    with open(path, "rb") as f:
        d = f.read()
    return d.replace(b"\r\n", b"\n").replace(b"\r", b"\n").lstrip(b"\xef\xbb\xbf").decode("utf-8", "replace")


def _diff_stat(a_text, b_text):
    """返回 (新增行数, 删除行数)。"""
    add = dele = 0
    for line in difflib.unified_diff(a_text.split("\n"), b_text.split("\n"), n=0, lineterm=""):
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+"):
            add += 1
        elif line.startswith("-"):
            dele += 1
    return add, dele


def load_contracts():
    if not os.path.exists(CONTRACTS):
        print(f"!! 契约文件不存在：{CONTRACTS}", file=sys.stderr)
        return None
    with open(CONTRACTS, encoding="utf-8") as f:
        return json.load(f)


def check_applied():
    """覆盖层是否已应用到本体。"""
    if not os.path.exists(APPLY):
        return False, f"找不到 {APPLY}"
    r = subprocess.run([sys.executable, APPLY, "verify"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode == 0, (r.stdout or r.stderr or "").strip()


def check_self(contracts):
    """自洽检查：覆盖层里，我们的特征串在、依赖的上游符号也在。"""
    problems, checked = [], 0
    for rel, spec in contracts.get("files", {}).items():
        path = os.path.join(OVERRIDES, rel)
        if not os.path.exists(path):
            problems.append(f"{rel}: 覆盖层文件不存在")
            continue
        text = _read(path)
        for token in spec.get("we_add", []):
            checked += 1
            if token not in text:
                problems.append(f"{rel}: 我们注入的特征串不见了 → {token!r}（改动被上游冲掉或覆盖层被改坏）")
        for token in spec.get("upstream_anchors", []):
            checked += 1
            if token not in text:
                problems.append(f"{rel}: 依赖的上游符号在覆盖层里不存在 → {token!r}（契约过期，请更新 contracts.json）")
    return problems, checked


def _baseline_upstream_hashes():
    """读 baseline.json 里记录的上游 sha256（口径与 apply_overrides 一致）。"""
    path = os.path.join(CORE, "baseline.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return {k: (v or {}).get("upstream_sha256") for k, v in (data.get("files") or {}).items()}


def check_upstream(contracts, up_dir):
    """拿上游新版做 BREAKING 探测 + 未吸收改动统计。

    关键区分：快照若与 baseline 记录的上游版本一致，差异就纯粹是我们自己的定制，
    不属于「未吸收的上游改动」—— 不报，避免每次自检都告警导致告警疲劳。
    """
    import hashlib

    def _sha(path):
        with open(path, "rb") as f:
            d = f.read()
        return hashlib.sha256(d.replace(b"\r\n", b"\n").replace(b"\r", b"\n").lstrip(b"\xef\xbb\xbf")).hexdigest()

    baseline = _baseline_upstream_hashes()
    breaking, unabsorbed, own_only = [], [], []
    for rel, spec in contracts.get("files", {}).items():
        up_file = os.path.join(up_dir, rel)
        if not os.path.exists(up_file):
            continue  # 上游没有这个文件（我们独有），跳过
        up_text = _read(up_file)
        ov_text = _read(os.path.join(OVERRIDES, rel))

        missing = [t for t in spec.get("upstream_anchors", []) if t not in up_text]
        if missing:
            breaking.append((rel, missing))

        add, dele = _diff_stat(up_text, ov_text)
        if not (add or dele):
            continue
        if baseline.get(rel) and _sha(up_file) == baseline[rel]:
            own_only.append((rel, add, dele))   # 快照 == 当前基线 → 纯我们的定制
        else:
            unabsorbed.append((rel, add, dele))
    return breaking, unabsorbed, own_only


def main():
    p = argparse.ArgumentParser(description="上游同步后自检：契约 + 未吸收改动")
    p.add_argument("--upstream", help="上游快照解压目录（用于 BREAKING 探测）")
    p.add_argument("--json", action="store_true", help="输出 JSON")
    args = p.parse_args()

    contracts = load_contracts()
    if contracts is None:
        return EXIT_FAIL

    ok, msg = check_applied()
    self_problems, checked = check_self(contracts)
    breaking, unabsorbed, own_only = [], [], []
    if args.upstream:
        if not os.path.isdir(args.upstream):
            print(f"!! 上游快照目录不存在：{args.upstream}", file=sys.stderr)
            return EXIT_FAIL
        breaking, unabsorbed, own_only = check_upstream(contracts, args.upstream)

    if args.json:
        print(json.dumps({
            "applied": ok,
            "apply_verify": msg,
            "self_check_items": checked,
            "self_problems": self_problems,
            "breaking": [{"file": f, "missing": m} for f, m in breaking],
            "unabsorbed": [{"file": f, "added": a, "deleted": d} for f, a, d in unabsorbed],
            "own_customization": [{"file": f, "added": a, "deleted": d} for f, a, d in own_only],
        }, ensure_ascii=False, indent=2))
    else:
        print("=" * 62)
        print("上游同步后自检")
        print("=" * 62)
        print(f"\n[1] 覆盖层应用状态")
        print(f"    {'OK  已全部应用' if ok else '!!  未完全应用'}")
        if not ok:
            print(f"    {msg}")

        print(f"\n[2] 契约自洽（{checked} 项）")
        if self_problems:
            for s in self_problems:
                print(f"    !! {s}")
        else:
            print(f"    OK  我们的改动在、依赖的上游符号也都在")

        if args.upstream:
            print(f"\n[3] BREAKING 探测（对比上游快照 {args.upstream}）")
            if breaking:
                for rel, missing in breaking:
                    print(f"    !! {rel} —— 上游新版不再提供我们依赖的符号：")
                    for m in missing:
                        print(f"         - {m}")
                    print(f"       处置：改 core-overrides/overrides/{rel} 适配，"
                          f"否则 apply 成功但运行时失效")
            else:
                print("    OK  我们依赖的上游符号全部健在")

            print(f"\n[4] 我们未吸收的上游改动（整文件覆盖的代价）")
            if unabsorbed:
                for rel, add, dele in unabsorbed:
                    print(f"    ·  {rel}: 覆盖层相对上游新版 +{add} / -{dele} 行")
                print("\n    说明：这些差异既包含我们的定制，也可能包含上游的新修复。")
                print("    处置：读上游新版 diff，把与我们无关的上游改动合并进覆盖层再 apply。")
            else:
                print("    OK  上游未改动被覆盖文件（快照与基线一致）")
            if own_only:
                print("\n    （以下差异确认纯属我们自己的定制，非上游新改动，不计入待办：）")
                for rel, add, dele in own_only:
                    print(f"       - {rel}: +{add} / -{dele} 行")

        print("\n" + "=" * 62)

    if not ok or self_problems or breaking:
        print("结论：!! 有问题，先处理再发布")
        return EXIT_FAIL
    if unabsorbed:
        print("结论：有上游改动尚未吸收，需人工评估（不阻断发布，但要记账）")
        return EXIT_WARN
    print("结论：OK")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
