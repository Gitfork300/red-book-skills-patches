# -*- coding: utf-8 -*-
"""封面唯一性门禁（2026-10-14 新增，起因：专题封面连续复用同一张官方物料触发平台违规）。

规则：
1. 同一天所有封面两两之间 ahash 距离必须 >= 阈值（默认 12）；
2. 同一天封面与**历史**（其它日期）封面之间也必须 >= 阈值；
3. 同一专题（同一组字母）内的封面禁止复用同一张源图。

用法：
  python _cover_dedup.py                # 扫描今天（按 --date）的全部封面
  python _cover_dedup.py --date 1014     # 指定日期串（匹配 *_<date>_cover.png）
  python _cover_dedup.py --files a1014_01 b1014_02   # 只查指定 key
退出码：0 = 全绿；1 = 存在近重复；2 = 依赖或输入错误。
"""
import os
import sys
import glob
import argparse
import itertools

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

try:
    from PIL import Image, UnidentifiedImageError
except ImportError as exc:
    print("FAIL 缺少 Pillow，无法执行封面唯一性检查: %s" % exc, file=sys.stderr)
    sys.exit(2)

HERE = os.path.dirname(os.path.abspath(__file__))
THRESHOLD = 12


def ahash(path, n=16):
    with Image.open(path) as source:
        im = source.convert("L").resize((n, n))
    px = list(im.tobytes())
    avg = sum(px) / float(len(px))
    return [1 if p > avg else 0 for p in px]


def dist(a, b):
    return sum(1 for x, y in zip(a, b) if x != y)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=None, help="日期串，如 1014；默认取今天")
    ap.add_argument("--files", nargs="*", default=None, help="只查这些 key（不含 _cover.png）")
    ap.add_argument("--threshold", type=int, default=THRESHOLD)
    args = ap.parse_args()

    if args.threshold < 0:
        ap.error("--threshold 不能为负数")

    if args.files:
        today = list(args.files)
    else:
        date = args.date or __import__("datetime").date.today().strftime("%m%d")
        today = sorted(
            f.replace("_cover.png", "")
            for f in glob.glob("*%s*_cover.png" % date)
            if not f.endswith("_v2_cover.png")
        )

    hist = sorted(
        f.replace("_cover.png", "")
        for f in glob.glob("*_cover.png")
        if not f.endswith("_v2_cover.png") and f.replace("_cover.png", "") not in today
    )

    if not today:
        print("FAIL 未找到待检测的封面", file=sys.stderr)
        return 2

    H = {}
    for k in today + hist:
        p = k + "_cover.png"
        try:
            H[k] = ahash(p)
        except (OSError, UnidentifiedImageError, ValueError) as e:
            print("FAIL 无法读取 %s: %s" % (p, e), file=sys.stderr)
            return 2

    today = [k for k in today if k in H]
    hist = [k for k in hist if k in H]

    bad = []
    for x, y in itertools.combinations(today, 2):
        dd = dist(H[x], H[y])
        if dd < args.threshold:
            bad.append(("TODAY", x, y, dd))
    for x in today:
        for y in hist:
            dd = dist(H[x], H[y])
            if dd < args.threshold:
                bad.append(("HIST", x, y, dd))

    print("封面唯一性门禁：今日 %d 张 vs 今日 + 历史(%d 张)，阈值 ahash >= %d"
          % (len(today), len(hist), args.threshold))
    for b in bad:
        print("  [红] %s %s vs %s 距离=%d" % b)
    if bad:
        print("结果：不通过（%d 对近重复）— 必须换源图/换构图重做后再发。" % len(bad))
        return 1
    print("结果：全绿 — 无近重复。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
