#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
timeliness-window / geo_check.py —— 会展活动地域范围预检

规则（用户 2026-09-11 要求）：
    会展活动类选题，**只发江浙沪（上海 / 江苏 / 浙江）或珠三角（广州 / 深圳 /
    佛山 / 东莞 / 珠海 / 中山 / 惠州 / 江门 / 肇庆）**，其他地区一律不发。

用法：
    python geo_check.py --city 杭州
    python geo_check.py --city 廊坊 --json
    python geo_check.py --text "<稿件正文>"          # 从文本里找城市名
    python geo_check.py --list                       # 打印白名单

退出码：
    0 = 在允许范围内
    1 = 不在允许范围内（不得发布；可登记待发池或换选题）
    2 = 参数错误 / 未能识别城市（按不合格处理，且需人工确认）

设计说明：
- 白名单是"城市/地名"，判断前先做归一化（去掉「市 / 地区 / 自治州 / 新区」等后缀）。
- 另设「常见辖区外城市」黑名单，命中即直接判不合格，避免只靠白名单漏判。
- 判断不依赖 agent 的印象，避免"写了外地活动却没发现"。
"""
from __future__ import annotations

import argparse
import json
import re
import sys

# —— 白名单：江浙沪 ——
JIANGZHEHU = {
    # 上海
    "上海", "浦东", "浦西", "徐汇", "黄浦", "静安", "长宁", "普陀", "虹口", "杨浦",
    "闵行", "宝山", "嘉定", "金山", "松江", "青浦", "奉贤", "崇明",
    # 江苏
    "江苏", "南京", "苏州", "无锡", "常州", "南通", "扬州", "镇江", "泰州",
    "盐城", "徐州", "淮安", "连云港", "宿迁", "江阴", "昆山", "张家港", "常熟",
    "太仓", "宜兴", "吴江", "武进",
    # 浙江
    "浙江", "杭州", "宁波", "温州", "嘉兴", "湖州", "绍兴", "金华", "衢州",
    "舟山", "台州", "丽水", "义乌", "余杭", "萧山", "滨江", "鄞州", "慈溪", "余姚",
}

# —— 白名单：珠三角（含港澳，按"中国香港/中国澳门"表述）——
# 2026-09-14 用户口径：**说到"珠三角"自动包含港澳活动**。
# 识别兼容裸称（香港/澳门/HK），但**成稿一律写"中国香港 / 中国澳门"**。
ZHUJIANGSAN = {
    "珠三角", "粤港澳大湾区", "大湾区", "广州", "深圳", "佛山", "东莞", "珠海",
    "中山", "惠州", "江门", "肇庆", "南沙", "前海", "横琴", "番禺", "顺德",
    "南海", "宝安", "福田", "南山", "龙岗", "黄埔", "增城", "中国香港", "中国澳门",
    "香港", "澳门", "香港特别行政区", "澳门特别行政区", "HK", "Hong Kong", "Macao",
}

ALLOWED = JIANGZHEHU | ZHUJIANGSAN

# —— 黑名单：常见的辖区外会展城市（命中即不合格）——
BLOCKED = {
    "北京", "天津", "重庆", "石家庄", "保定", "唐山", "廊坊", "秦皇岛", "张家口",
    "太原", "大同", "呼和浩特", "包头", "沈阳", "大连", "鞍山", "长春", "吉林",
    "哈尔滨", "济南", "青岛", "烟台", "潍坊", "威海", "临沂", "淄博",
    "郑州", "洛阳", "武汉", "宜昌", "襄阳", "长沙", "株洲", "湘潭", "南昌",
    "合肥", "芜湖", "福州", "厦门", "泉州", "南宁", "桂林", "柳州",
    "海口", "三亚", "成都", "绵阳", "贵阳", "昆明", "拉萨", "西安", "兰州",
    "西宁", "银川", "乌鲁木齐", "汕头", "湛江", "韶关", "梅州", "茂名",
}

_SUFFIX = re.compile(r"(市|地区|自治州|自治县|新区|经济特区|特别行政区)$")


def normalize(raw: str) -> str:
    s = (raw or "").strip()
    s = s.replace(" ", "")
    s = _SUFFIX.sub("", s)
    return s


def judge(city: str) -> tuple[bool, str]:
    """返回 (是否合格, 判定值)"""
    c = normalize(city)
    if not c:
        return False, "UNKNOWN"
    # 白名单优先（避免「上海」被其他规则误伤）
    for name in ALLOWED:
        if name and (name in c or c in name):
            return True, "IN_SCOPE"
    for name in BLOCKED:
        if name and name in c:
            return False, "OUT_OF_SCOPE"
    return False, "UNKNOWN"


def scan_text(text: str) -> list[tuple[str, bool, str]]:
    hits: list[tuple[str, bool, str]] = []
    for name in sorted(ALLOWED | BLOCKED, key=len, reverse=True):
        if name in (text or ""):
            hits.append((name, name in ALLOWED, "IN_SCOPE" if name in ALLOWED else "OUT_OF_SCOPE"))
    # 去重：若一个地名是另一个的子串，保留更长的
    out: list[tuple[str, bool, str]] = []
    for name, ok, code in hits:
        if any(name != o and name in o for o, _, _ in hits):
            continue
        out.append((name, ok, code))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="会展活动地域范围预检（江浙沪 / 珠三角）")
    ap.add_argument("--city", help="活动举办城市/地区，如 杭州 / 深圳 / 廊坊")
    ap.add_argument("--text", help="稿件全文；用于扫描其中的城市名")
    ap.add_argument("--list", action="store_true", help="打印白名单")
    ap.add_argument("--json", action="store_true", help="输出机器可读结果")
    args = ap.parse_args()

    if args.list:
        print("白名单（江浙沪）：" + "、".join(sorted(JIANGZHEHU)))
        print("白名单（珠三角）：" + "、".join(sorted(ZHUJIANGSAN)))
        return 0

    if args.city:
        ok, code = judge(args.city)
        msg = {
            "IN_SCOPE": f"{args.city} 在允许范围（江浙沪/珠三角）",
            "OUT_OF_SCOPE": f"{args.city} 不在允许范围 —— 会展活动不得发布",
            "UNKNOWN": f"无法识别「{args.city}」是否在范围内 —— 按不合格处理，需人工确认",
        }[code]
        if args.json:
            print(json.dumps({"city": args.city, "in_scope": ok, "code": code, "message": msg},
                             ensure_ascii=False))
        else:
            print(("[PASS 范围合格] " if ok else "[BLOCK 范围不合格] ") + msg)
        return 0 if ok else 1

    if args.text:
        hits = scan_text(args.text)
        bad = [(n, c) for n, ok, c in hits if not ok]
        if args.json:
            print(json.dumps({"hits": [{"name": n, "in_scope": ok, "code": c} for n, ok, c in hits],
                              "out_of_scope": [n for n, _ in bad]}, ensure_ascii=False))
        else:
            if hits:
                print("识别到地名：" + "、".join(f"{n}({'在范围内' if ok else '范围外'})"
                                             for n, ok, c in hits))
            else:
                print("未识别到已知地名 —— 按不合格处理，需人工确认")
        if bad:
            print("[BLOCK 范围不合格] 出现辖区外地名：" + "、".join(n for n, _ in bad))
            return 1
        return 0 if hits else 1

    ap.error("需要 --city 或 --text 之一（或 --list）")
    return 2


if __name__ == "__main__":
    sys.exit(main())
