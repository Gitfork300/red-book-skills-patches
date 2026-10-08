# -*- coding: utf-8 -*-
"""文档分层校验 —— 拆 md 之后的机器兜底。

为什么需要：
  拆分最大的风险不是"切歪了"，而是**规则被静默删掉**：
  一段话挪走时顺手丢了半句硬限制，事后没人发现，直到某天踩坑。
  本脚本用四条检查把这件事变成可检测的错误。

检查项：
  1. 字数/行数是否超过该层上限
  2. 主入口索引里引用的文件是否真实存在（防断链）
  3. 详情目录里是否有没被主入口引用的孤儿文件（防漏挂）
  4. 主入口是否仍包含声明的关键锚点词（**防规则被误删** —— 核心保险）

用法：
  python tools/check_doc_layers.py                 # 用默认 manifest
  python tools/check_doc_layers.py --all-md        # 额外全量扫描 md 体量
  python tools/check_doc_layers.py --manifest x.json

退出码：0=全部通过 / 1=有问题 / 2=错误
"""
import argparse
import json
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
PATCH_ROOT = os.path.normpath(os.path.join(HERE, ".."))
SKILLS = os.path.normpath(os.path.join(PATCH_ROOT, ".."))
WORKSPACE = os.environ.get("XHS_WORKSPACE") or os.path.expanduser("~/xhs-workspace")

DEFAULT_MANIFEST = os.path.join(HERE, "doc_layers.json")

# 引用形如 `references/foo.md` / `topics/01-x.md`，出现在主入口文本里
REF_RE = re.compile(r"`?((?:references|topics|refs)/[A-Za-z0-9_\-\.]+\.md)`?")


def read(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def stats(path):
    t = read(path)
    return len(t), t.count("\n") + 1


def check_entry(entry, problems, infos):
    root = entry["root"].replace("${PATCH_ROOT}", PATCH_ROOT)
    root = root.replace("${SKILLS}", SKILLS).replace("${WORKSPACE}", WORKSPACE)
    main_rel = entry["main"]
    main_path = os.path.join(root, main_rel)

    if not os.path.exists(main_path):
        problems.append("[%s] 主入口不存在: %s" % (entry["id"], main_path))
        return

    chars, lines = stats(main_path)
    lim_c = entry.get("limit_main", 6000)
    lim_l = entry.get("limit_main_lines", 180)
    tag = "[%s] %s" % (entry["id"], main_rel)
    if chars > lim_c:
        problems.append("%s 主入口 %d 字符 > 上限 %d（超 %d）"
                        % (tag, chars, lim_c, chars - lim_c))
    if lines > lim_l:
        problems.append("%s 主入口 %d 行 > 上限 %d" % (tag, lines, lim_l))
    infos.append("%s %d 字符 / %d 行（上限 %d / %d）" % (tag, chars, lines, lim_c, lim_l))

    main_txt = read(main_path)

    # 检查 2：索引里引用的文件必须存在
    refs = sorted(set(REF_RE.findall(main_txt)))
    for r in refs:
        p = os.path.join(root, r.replace("/", os.sep))
        if not os.path.exists(p):
            problems.append("%s 引用了不存在的文件: %s" % (tag, r))

    # 检查 3：详情目录里的文件必须被主入口引用（防孤儿）
    for d in entry.get("detail_dirs", []):
        dd = os.path.join(root, d)
        if not os.path.isdir(dd):
            continue
        for fn in sorted(os.listdir(dd)):
            if not fn.lower().endswith(".md"):
                continue
            rel = "%s/%s" % (d, fn)
            if rel not in main_txt and fn not in main_txt:
                problems.append("%s 孤儿文件（未被主入口索引）: %s" % (tag, rel))
            fp = os.path.join(dd, fn)
            c, l = stats(fp)
            lc = entry.get("limit_detail", 9000)
            ll = entry.get("limit_detail_lines", 260)
            if c > lc:
                problems.append("%s 详情 %s %d 字符 > 上限 %d" % (tag, rel, c, lc))
            if l > ll:
                problems.append("%s 详情 %s %d 行 > 上限 %d" % (tag, rel, l, ll))
            infos.append("%s %s %d 字符 / %d 行" % (tag, rel, c, l))

    # 检查 4：关键锚点必须还在主入口（防规则被误删）—— 核心保险
    miss = [a for a in entry.get("anchors", []) if a not in main_txt]
    for a in miss:
        problems.append("%s **关键锚点丢失**: %r —— 拆分时把规则删掉了？" % (tag, a))
    if entry.get("anchors") and not miss:
        infos.append("%s 锚点 %d/%d 命中" % (tag, len(entry["anchors"]), len(entry["anchors"])))


def scan_all_md():
    roots = [PATCH_ROOT, os.path.join(WORKSPACE, ".workbuddy", "memory")]
    skip = {".venv", "site-packages", "__pycache__", ".git", "backup", ".pytest_cache"}
    rows = []
    for root in roots:
        if not os.path.isdir(root):
            continue
        for dp, dns, fns in os.walk(root):
            dns[:] = [d for d in dns if d not in skip]
            for fn in fns:
                if not fn.lower().endswith(".md"):
                    continue
                p = os.path.join(dp, fn)
                c, l = stats(p)
                if c >= 3000:
                    rows.append((c, l, os.path.relpath(p, root)))
    rows.sort(reverse=True)
    return rows


def main():
    ap = argparse.ArgumentParser(description="文档分层校验")
    ap.add_argument("--manifest", default=DEFAULT_MANIFEST)
    ap.add_argument("--all-md", action="store_true", help="额外列出所有 ≥3000 字符的 md")
    args = ap.parse_args()

    if not os.path.exists(args.manifest):
        print("!! 找不到 manifest: %s" % args.manifest)
        return 2
    with open(args.manifest, encoding="utf-8") as f:
        manifest = json.load(f)

    problems, infos = [], []
    for e in manifest.get("entries", []):
        check_entry(e, problems, infos)

    for i in infos:
        print("   " + i)
    print()

    if problems:
        print("!! 发现 %d 个问题：" % len(problems))
        for p in problems:
            print("   - " + p)
    else:
        print("OK 文档分层校验全部通过（%d 个条目）" % len(manifest.get("entries", [])))

    if args.all_md:
        print("\n---- 体量扫描（≥3000 字符）----")
        for c, l, rel in scan_all_md():
            print("   %7d 字符 %5d 行  %s" % (c, l, rel))

    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
