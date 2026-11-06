#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cover-image-rules / check_qr：封面（含任何配图）二维码检测

红线（2026-10-23 用户拍板，B-101）：**任何图都不应该包含二维码** ——
官方图、官方海报、AI 生成图、字卡一律适用；含码属站外导流高危元素。

用法：
    python check_qr.py --dir <稿件目录>            # 扫该目录全部 *_cover.png
    python check_qr.py --dir <稿件目录> --date 1023
    python check_qr.py --file a.png b.png          # 指定文件
    python check_qr.py --dir <dir> --mark-ok a.png b.png   # 目检通过后登记白名单

检测方案（2026-10-23 校准，见本文件底部「校准记录」）：
    全分辨率 detect() 会在无码海报上误报（f01_p1 全分辨率 True / 二值化 False），
    故统一走「灰度 → 等比缩放 → Otsu 二值化 → detect() 定位」，命中后再裁剪放大解码确认。
      · 解码成功      → 确认含码
      · 仅定位未解码  → 疑似含码（AI 生成图的点阵/网格纹理会误报，必须人工目检裁决）

退出码：
    0 = 全部无码（或已登记目检白名单）
    1 = 确认含码（禁发，必须换图源或换裁选区）
    2 = 疑似含码且未登记白名单（必须人工目检；目检无码后用 --mark-ok 登记）
    3 = 依赖缺失、无输入或无法读取/检测图片
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import os
import sys
from datetime import datetime
from pathlib import Path

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

try:
    import cv2
    import numpy as np
except ImportError as _cv2_err:  # pragma: no cover
    print("❌ 缺少 opencv（opencv-python）：二维码门禁无法执行。"
          "请在 patch venv 内安装：pip install 'opencv-python>=4.8.0'\n"
          "（%s）" % _cv2_err, file=sys.stderr)
    sys.exit(3)

PATCH_ROOT = Path(__file__).resolve().parent.parent.parent
WORKSPACE_ROOT = Path(os.environ.get("XHS_WORKSPACE", "C:/xhs"))
STATE_ROOT = Path(os.environ.get("XHS_STATE_ROOT", str(WORKSPACE_ROOT / ".state")))
WHITELIST = Path(os.environ.get(
    "XHS_QR_WHITELIST",
    str(STATE_ROOT / "covers" / "qr_whitelist.json"),
))
LEGACY_WHITELIST = PATCH_ROOT / "cover-image-rules" / "state" / "qr_whitelist.json"
DET = cv2.QRCodeDetector()


def _binarize(img, scale=0.5):
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    if scale != 1.0:
        g = cv2.resize(g, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    _, b = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return b


def _locate(img):
    """多尺度二值化定位候选二维码点集。"""
    for scale in (0.5, 0.35, 1.0):
        b = _binarize(img, scale)
        ok, pts = DET.detect(b)
        if ok and pts is not None:
            return [(float(p[0]) / scale, float(p[1]) / scale)
                    for p in np.asarray(pts).reshape(-1, 2)]
    return []


def _decode_crops(img, pts):
    h, w = img.shape[:2]
    data = []
    if not pts:
        return data
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    x0, x1 = int(min(xs)), int(max(xs))
    y0, y1 = int(min(ys)), int(max(ys))
    pad = int(0.25 * max(x1 - x0, y1 - y0, 10))
    boxes = [(x0 - pad, y0 - pad, x1 + pad, y1 + pad),
             (max(0, x0 - 2 * pad), max(0, y0 - 2 * pad),
              min(w, x1 + 2 * pad), min(h, y1 + 2 * pad))]
    for (X0, Y0, X1, Y1) in boxes:
        crop = img[max(0, Y0):Y1, max(0, X0):X1]
        if crop.size == 0:
            continue
        crop = cv2.resize(crop, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        for cand in (crop, _binarize(crop, 1.0)):
            r = DET.detectAndDecode(cand)
            if r and r[0]:
                data.append(r[0][:60])
    return data


def md5_of(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def load_wl():
    migrate_legacy_whitelist()
    if WHITELIST.exists():
        data = json.loads(WHITELIST.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("二维码白名单必须是 JSON 对象")
        return data
    return {}


def migrate_legacy_whitelist():
    if not LEGACY_WHITELIST.is_file():
        return
    if LEGACY_WHITELIST.resolve() == WHITELIST.resolve():
        return
    WHITELIST.parent.mkdir(parents=True, exist_ok=True)
    if WHITELIST.exists():
        if WHITELIST.read_bytes() != LEGACY_WHITELIST.read_bytes():
            raise ValueError(
                "Skill 内旧二维码白名单与 C:/xhs 状态副本不一致；"
                "请先人工核对后再继续"
            )
    else:
        created = False
        try:
            with WHITELIST.open("xb") as target:
                created = True
                with LEGACY_WHITELIST.open("rb") as source:
                    shutil.copyfileobj(source, target)
        except Exception:
            if created and WHITELIST.exists():
                WHITELIST.unlink()
            raise
        if WHITELIST.read_bytes() != LEGACY_WHITELIST.read_bytes():
            WHITELIST.unlink()
            raise OSError("二维码白名单迁移校验失败；旧文件已保留")
    LEGACY_WHITELIST.unlink()


def save_wl(wl):
    migrate_legacy_whitelist()
    WHITELIST.parent.mkdir(parents=True, exist_ok=True)
    WHITELIST.write_text(json.dumps(wl, ensure_ascii=False, indent=1), encoding="utf-8")


def check_one(path, wl):
    img = cv2.imread(path)
    if img is None:
        return "skip", []
    pts = _locate(img)
    if not pts:
        return "clean", []
    data = _decode_crops(img, pts)
    if data:
        return "qr", data
    digest = md5_of(path)
    rec = wl.get(digest)
    if rec:
        return "clean", []
    return "suspect", []


def main() -> int:
    ap = argparse.ArgumentParser(description="封面二维码检测（任何图禁二维码）")
    ap.add_argument("--dir", help="稿件目录")
    ap.add_argument("--file", nargs="*", help="指定图片文件")
    ap.add_argument("--date", help="日期标记（如 1023），仅用于白名单记录")
    ap.add_argument("--mark-ok", nargs="*", default=None,
                    help="人工目检确认无二维码的文件，登记白名单")
    ap.add_argument("--note", default="", help="白名单备注（目检结论）")
    args = ap.parse_args()

    try:
        wl = load_wl()
    except (OSError, ValueError) as exc:
        print(f"FAIL 无法读取二维码白名单: {exc}", file=sys.stderr)
        return 3

    if args.mark_ok:
        invalid = [p for p in args.mark_ok if not os.path.isfile(p)]
        if invalid:
            for p in invalid:
                print("[错误] 文件不存在: %s" % p, file=sys.stderr)
            return 3
        unreadable = [p for p in args.mark_ok if cv2.imread(p) is None]
        if unreadable:
            for p in unreadable:
                print("[错误] 图片读不出: %s" % p, file=sys.stderr)
            return 3
        for p in args.mark_ok:
            d = md5_of(p)
            wl[d] = {
                "file": os.path.basename(p),
                "date": args.date or "",
                "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "note": args.note or "人工目检无二维码",
            }
            print("[登记白名单] %s  md5=%s" % (os.path.basename(p), d[:12]))
        save_wl(wl)
        return 0

    files = []
    if args.file:
        files = [Path(f) for f in args.file]
    elif args.dir:
        files = sorted(Path(args.dir).glob("*_cover.png"))
        if not files:
            files = sorted([p for p in Path(args.dir).glob("*.png")])
    else:
        print("需要 --dir 或 --file", file=sys.stderr)
        return 2

    if not files:
        print("FAIL 未找到待检测的图片", file=sys.stderr)
        return 3

    qr, suspect, clean = [], [], 0
    for p in files:
        try:
            kind, data = check_one(str(p), wl)
        except (OSError, cv2.error, ValueError) as exc:
            print(f"FAIL 无法检测 {p.name}: {exc}", file=sys.stderr)
            return 3
        if kind == "qr":
            qr.append((p, data))
            print("[确认含码] %s  解码=%s" % (p.name, data))
        elif kind == "suspect":
            suspect.append(p)
            print("[疑似含码] %s  需人工目检（定位到码形但未解码成功）" % p.name)
        elif kind == "clean":
            clean += 1
        else:
            print("[错误] 读不出: %s" % p.name, file=sys.stderr)
            return 3

    print("\n扫描 %d 张，确认含码 %d，疑似 %d，无码 %d" % (len(files), len(qr), len(suspect), clean))
    if qr:
        print("命中（确认含码，禁发）：")
        for p, _ in qr:
            print("  - %s" % p.name)
        print("判定：❌ 存在含二维码图 —— 必须换图源或换裁选区，禁止排队发布")
        return 1
    if suspect:
        print("待目检（疑似含码）：")
        for p in suspect:
            print("  - %s" % p.name)
        print("判定：⚠️ 疑似含码未裁决 —— 必须人工目检；确认无码后用 --mark-ok 登记白名单")
        return 2
    print("判定：✅ 全部无二维码")
    return 0


if __name__ == "__main__":
    sys.exit(main())
