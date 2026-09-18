# -*- coding: utf-8 -*-
"""封面来源台账校验：展会/活动类批次官方宣传图占比 >= 80%（硬指标）。

用法:
    python check_cover_source.py --batch-dir <稿件目录> [--ledger <json>] [--min-official 0.8]

台账格式 (cover_sources_<批>.json):
    {"batch": "...", "min_official": 0.8,
     "notes": [{"key": "...", "source": "official|ai_gen|gradient|scenic|infographic",
                "url": "官方图必填", "origin": "图源说明", "reason": "非官方图必填",
                "treatment": "处理方式", "backup": "旧封面备份(可选)"}]}

退出码: 0=通过  2=官方图占比不足  3=缺台账或台账不完整  4=封面文件缺失
"""
import argparse
import glob
import io
import json
import os
import sys

VALID_SOURCES = {"official", "ai_gen", "gradient", "scenic", "infographic"}


def load_ledger(batch_dir, ledger_path):
    if ledger_path:
        p = ledger_path
    else:
        cands = sorted(glob.glob(os.path.join(batch_dir, "cover_sources_*.json")))
        if not cands:
            return None, "batch 目录下无 cover_sources_*.json 台账"
        p = cands[-1]
    if not os.path.exists(p):
        return None, f"台账不存在: {p}"
    try:
        data = json.load(io.open(p, encoding="utf-8"))
    except Exception as e:
        return None, f"台账解析失败 {p}: {e}"
    return data, p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch-dir", required=True)
    ap.add_argument("--ledger", default=None)
    ap.add_argument("--min-official", type=float, default=0.8)
    args = ap.parse_args()

    data, where = load_ledger(args.batch_dir, args.ledger)
    if data is None:
        print(f"[FAIL] {where}（展会/活动类批次必须先写封面来源台账）")
        return 3

    notes = data.get("notes") or []
    if not notes:
        print(f"[FAIL] 台账 {where} 无 notes 记录")
        return 3

    problems, missing_cover, bad = [], [], []
    n_official = 0
    for n in notes:
        key = n.get("key", "?")
        src = (n.get("source") or "").strip().lower()
        if src not in VALID_SOURCES:
            bad.append(f"{key}: 非法 source '{src}'（{sorted(VALID_SOURCES)}）")
            continue
        if src == "official":
            n_official += 1
            if not (n.get("url") or "").strip():
                bad.append(f"{key}: official 缺 url（图源必须留痕）")
        else:
            if not (n.get("reason") or "").strip():
                bad.append(f"{key}: 非 official 缺 reason（兜底原因必须留痕）")
        cover = os.path.join(args.batch_dir, key + "_cover.png")
        if not os.path.exists(cover):
            missing_cover.append(cover)

    total = len(notes)
    ratio = n_official / total if total else 0.0
    min_ratio = float(data.get("min_official", args.min_official))

    print(f"批次 {data.get('batch','?')}: 官方图 {n_official}/{total} = {ratio:.0%}"
          f"（硬指标 >= {min_ratio:.0%}）")
    for b in bad:
        print("[FAIL]", b)
    for m in missing_cover:
        print("[FAIL] 封面文件缺失:", m)

    if bad or missing_cover:
        return 3 if bad else 4
    if ratio < min_ratio:
        print(f"[FAIL] 官方图占比 {ratio:.0%} < {min_ratio:.0%}："
              f"还差 {int(-(-min_ratio * total - n_official))} 篇需补官方图，不得用字卡凑数")
        return 2
    print("[PASS] 封面来源台账合规")
    return 0


if __name__ == "__main__":
    sys.exit(main())
