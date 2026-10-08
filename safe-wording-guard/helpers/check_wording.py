#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
safe-wording-guard：小红书文案用词预检

用法：
    python check_wording.py --content <file>
    python check_wording.py --title "..." --content "..."
    cat content.txt | python check_wording.py

退出码：
    0 = 全部安全
    1 = 命中 P0（高危，必须改）
    2 = 命中 P1（中危，建议改）
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path


# 平台硬限制（实测确认，2026-09-06；口径修正 2026-09-12）：
# 标题上限 20 是「字宽」不是字符数：汉字/全角符号计 1，英文/数字/半角符号每 2 个计 1
# （多方实现一致，例：hello=3、你好hello=4）。旧版按 len() 逐字符计数 → 误报。
# 2026-09-12 复核实证：两篇已正常发布的标题被旧版判 P0——
#   「2026外滩大会：9月9日至12日在上海举行」实宽 18；「外滩大会2020-2026：主题与规模演变」实宽 16.5。
# 标题超限时，小红书不会报错、不会禁用按钮，而是点发布后完全静默失败
# —— 不发请求、不弹提示，只有编辑器内部的 toast「标题最多输入20字哦~」。
# 所以字数必须当作 P0 拦截，不能靠发布阶段发现。
MAX_TITLE_CHARS = 20
MAX_CONTENT_CHARS = 1000


# 常见站外域名后缀（用于裸域名识别）。
# 站外导流判定不看"有没有 http://"，只看"读者能不能顺着找到站外"——
# 裸域名（github.com/xxx、xxx.ai、www.xxx.com）与带协议的 URL 同罪，
# 但历史上的 P0 只写了 https?:// ，于是 `github.com/google/mantis`、
# `autoclaw.z.ai/blog/...` 这类全部漏检。2026-09-11 按用户要求补上。
_TLDS = (
    "com|cn|org|net|io|ai|dev|app|xyz|co|me|edu|gov|tech|top|"
    "site|info|club|vip|shop|art|store|cloud|online|ltd|group|live|fun|work"
)
# 允许域名前出现子域与路径（github.com/a/b、autoclaw.z.ai/blog/x）
_URLISH = (
    r"(?<![A-Za-z0-9._-])"
    r"(?:[A-Za-z0-9][A-Za-z0-9-]*\.)+(?:" + _TLDS + r")"
    r"(?:/[^\s，。；、）)】」』]*)?"
)

# P0：直接踩线
P0_PATTERNS: list[tuple[str, str]] = [
    (r"https?://[^\s\u4e00-\u9fff]+", "出现 URL —— 不在正文放链接"),
    (r"\bwww\.[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+", "出现 www 网址"),
    (_URLISH, "出现站外域名（如 github.com / xxx.ai）—— 正文一律不写网址，改写成机构名+项目名"),
    (r"扫码|扫一扫|加好友|加群|添加微", "出现导流词：扫码/加好友/加群"),
    (r"官方\s*H5|官方\s*小程序|官方\s*公众号|官方\s*App|官方\s*报名|官方\s*通道|官方\s*入口", '点名『官方 H5 / 小程序 / 公众号 / App』一类的官方渠道'),
    (r"微信(?!支付)|公众号(?!号)|支付宝\s*小程序|抖音号|B\s*站号|知乎号", '点名第三方平台（除『微信支付』外）'),
]

# P1：建议改
P1_PATTERNS: list[tuple[str, str]] = [
    (r"突破\s*\d+\s*万|刷屏|现象级|售罄|全网\s*第一", "自夸类数据，未认证时容易踩线"),
]

# 上下文敏感词：单独出现还好，配上"免费/0 元/限时"就高危
# 上下文敏感词：单独出现还好，配上"免费/0元/限时"就高危
# 关键字"报名|预约|注册|下载" 要用前后边界；"0 元"前不能是数字（避免"10 元/小时"误伤）
P1_COMBO_PATTERNS: list[tuple[re.Pattern, re.Pattern, str]] = [
    (
        re.compile(r"(?:报名|预约|注册|下载)"),
        re.compile(r"免费|(?<![\d])0\s*元|限时|优惠|折扣"),
        "报名/预约/注册 + 免费/限时 组合触发拉新判定",
    ),
]


# 电话号（手机号 / 座机 / 400 客服号）—— 平台视为导流违规
# 手机号检测：避免笔记正文中出现手机号码。
# 前缀手机号 11 位、以 1[3-9] 开头；座机带区号；允许号码内部用空格 / 短横分隔。
# 左右边界排除 ASCII 字母 / 数字 / 点，避免把代码或编号里的数字串（如 ID12345678901）
# 误判成电话；但中文 / 空格 / 标点后的号码仍会命中。
PHONE_RE = re.compile(
    r"(?<![A-Za-z0-9.])"
    r"(?:"
    r"1[3-9]\d{1,2}(?:[ -]?\d{4}){2}"   # 手机号（可含空格/短横）
    r"|0\d{2,3}[ -]?\d{7,8}"             # 座机（区号+号码）
    r"|400[ -]?\d{3}[ -]?\d{4}"          # 400 客服号
    r")"
    r"(?![A-Za-z0-9.])"
)


# 专题系列标题序号（P0）—— 用户 2026-09-18：「另外[专题] 后续不要写序号在主题中」。
# 禁止 ①-⑳、（一）~（十）（全/半角括号）、系列① / 系列1 / 系列一。
# 只查标题：正文里的序号（如议程"论坛（一）"）不受此限，避免误伤。
TITLE_SERIAL_RE = re.compile(
    r"[\u2460-\u2473]"                              # ①-⑳
    r"|[（(]\s*[一二三四五六七八九十]\s*[）)]"        # （一）（二）…（全/半角括号）
    r"|系列\s*[0-9一二三四五六七八九十①-⑳]"          # 系列① / 系列1 / 系列一
)


def check_title_serial(title: str | None) -> list[str]:
    """专题标题不写序号（用户 2026-09-18），命中按 P0。仅查标题。"""
    if not title:
        return []
    m = TITLE_SERIAL_RE.search(title)
    if m:
        return [
            f"[P0] 标题含序号「{m.group()}」—— 用户规则（2026-09-18）："
            "标题/主题不写序号（①、（一）、系列N 一律去掉），直接写内容本体"
        ]
    return []


def check(text: str) -> tuple[int, list[str], list[str]]:
    text = text.strip()
    p0_hits: list[str] = []
    p1_hits: list[str] = []

    for pattern, msg in P0_PATTERNS:
        if re.search(pattern, text):
            p0_hits.append(f"[P0] {msg}")

    m = PHONE_RE.search(text)
    if m:
        p0_hits.append(
            f"[P0] 出现电话号「{m.group()}」—— 平台视为导流违规，正文一律不写电话，"
            "改用『联系主办方官方账号』等表述"
        )

    for pattern, msg in P1_PATTERNS:
        if re.search(pattern, text):
            p1_hits.append(f"[P1] {msg}")

    for kw, ctx, msg in P1_COMBO_PATTERNS:
        if kw.search(text) and ctx.search(text):
            p1_hits.append(f"[P1] {msg}")

    if p0_hits:
        return 1, p0_hits, p1_hits
    if p1_hits:
        return 2, p0_hits, p1_hits
    return 0, [], []


def title_width(text: str) -> float:
    """小红书标题「字宽」：汉字/全角 = 1，英文/数字/半角 = 0.5。"""
    return sum(0.5 if ord(ch) < 128 else 1.0 for ch in text)


def _fmt_width(w: float) -> str:
    return str(int(w)) if float(w).is_integer() else f"{w:g}"


def check_length(title: str | None, content: str | None) -> list[str]:
    """平台硬限制检查：超长会导致发布静默失败，按 P0 处理。"""
    hits: list[str] = []
    if title is not None:
        w = title_width(title.strip())
        if w > MAX_TITLE_CHARS:
            hits.append(
                f"[P0] 标题 {_fmt_width(w)}/{MAX_TITLE_CHARS} 字（按字宽计：汉字/全角=1，英文/数字/半角=0.5）"
                " —— 平台会静默拒绝发布（无报错、按钮仍可点）"
            )
    if content is not None and len(content.strip()) > MAX_CONTENT_CHARS:
        hits.append(
            f"[P0] 正文 {len(content.strip())} 字，超过 {MAX_CONTENT_CHARS} 字上限"
        )
    return hits


def main() -> int:
    parser = argparse.ArgumentParser(description="小红书用词预检")
    parser.add_argument("--title", help="标题文本")
    parser.add_argument("--content", help="正文文本（也可用 --file）")
    parser.add_argument("--file", help="正文文件路径")
    args = parser.parse_args()

    parts: list[str] = []
    if args.title:
        parts.append(args.title)
    if args.content:
        # 防呆：把文件路径误当正文传入。
        # 2026-09-11 事故：批量预检时写成 `--content xhs_publish/xx_content.txt`，
        # 脚本于是检查了"路径字符串"而不是文件内容，返回 0（安全），
        # 结果含「扫码」P0 的稿子照发不误。这里直接按文件读取，宁可多说一句。
        if os.path.isfile(args.content):
            print(f"[warn] --content 收到的是文件路径，已按文件内容读取：{args.content}",
                  file=sys.stderr)
            parts.append(Path(args.content).read_text(encoding="utf-8"))
        else:
            parts.append(args.content)
    if args.file:
        text = Path(args.file).read_text(encoding="utf-8")
        parts.append(text)

    if not parts and not sys.stdin.isatty():
        parts.append(sys.stdin.read())

    if not parts:
        print("没有传入文本（用 --title/--content/--file，或从 stdin 传入）", file=sys.stderr)
        return 2

    text = "\n".join(parts)
    code, p0, p1 = check(text)
    p0 = p0 + check_length(args.title, args.content or (parts[-1] if args.file else None))
    p0 = p0 + check_title_serial(args.title)

    if args.title:
        print(f"标题 {_fmt_width(title_width(args.title.strip()))}/{MAX_TITLE_CHARS} 字（字宽）", file=sys.stderr)
    if p0:
        code = 1

    if code == 0:
        print("✅ 用词安全")
        return 0
    if code == 1:
        print("❌ 命中 P0（必须改）：")
        for h in p0:
            print(f"  - {h}")
        for h in p1:
            print(f"  - {h}")
        return 1
    # code == 2
    print("⚠️ 命中 P1（建议改）：")
    for h in p1:
        print(f"  - {h}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
