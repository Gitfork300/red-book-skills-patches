# -*- coding: utf-8 -*-
"""主办资质闸门 —— 活动 / 展会 / 论坛类稿件发布前必过。

判据（用户 2026-09-13 口径，反复强调 3 次）：
    展会 / 活动 必须是「事业单位 / 行业龙头 / 行业协会」牵头的中大型活动，
    且正文要体现含金量。不接受：私人机构、付费小班、无名私企、小型沙龙 / 对接会。

设计原则
--------
- 只管「活动 / 展会 / 论坛」类内容；研究 / 案例 / 科普资讯类（无活动名词）直接跳过（exit 0），
  由 safe-wording-guard 的站外导流闸门接管。
- 硬性拒绝（exit 1，最高置信、零误杀）：命中付费 / 私企小班名词、活动含收费价格、或命中私人机构黑名单。
- 显名私企（exit 1）：正文出现「主办方 / 承办方 / 由 … 主办」等语境，且主办实体不含任何
  事业单位 / 行业龙头 / 协会字样 → 判定为私人机构，拒绝。
- 软性复核（exit 2）：活动类但全文找不到明确主办方 → 列出待人工确认，不阻断。
- 通过（exit 0）：识别到合规主办方 + 正文有含金量信号。

用法
----
    python check_organizer.py --title "..." --content "..."
    python check_organizer.py --title "..." --file content.txt
退出码：0=通过 / 1=硬拒(含显名私企) / 2=复核
"""
import argparse
import os
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# ---------- 1. 活动类识别（非活动类直接跳过）----------
EVENT_NOWNS = [
    "举办", "开幕", "召开", "论坛", "大会", "展会", "展览", "沙龙", "分享会", "研讨会",
    "研修班", "训练营", "特训营", "对接会", "座谈会", "嘉年华", "黑客屋", "创科节",
    "公开课", "讲座", "峰会", "博览会", "开放日", "体验日", "市集", "比赛", "大赛",
    "赛事", "活动", "招募", "报名通道", "开放报名", "线下", "到场", "看展", "参展",
    "workshop", "meetup", "hackathon",
    # 招聘类（2026-09-14 补：原先「招聘会」不触发活动识别，招聘类稿件被整类跳过）
    "招聘会", "双选会", "人才交流", "校招", "宣讲会",
]
EVENT_RE = re.compile("|".join(re.escape(w) for w in EVENT_NOWNS), re.I)

# ---------- 2. 硬拒：私人培训 / 卖课小班性质（无条件硬拒，无论主办是谁）----------
# 这类词指向「卖课/内训/高端局」，即便挂在某个机构名下也不属于可发布的公开活动。
HARD_REJECT = [
    "报名费", "培训费", "课程费", "学费", "收款码",
    "私董会", "内训", "1对1辅导", "一对一辅导",
    "研修班", "特训营", "总裁班", "私享会", "小班课", "游学", "考察团",
    "训练营", "高端局",
]
HARD_RE = re.compile("|".join(re.escape(w) for w in HARD_REJECT))

# ---------- 2b. 收费形式：不是原罪，看主办方性质（2026-09-14 用户口径）----------
# 用户原话：「收费理解错了，我说的是私人活动存在收费，所以不发。
#           如果是政府部门或者行业峰会，还是可以发的。要注明是谁免费，谁收费，谁邀约。」
# → 政府/事业单位/高校/协会/行业龙头/会议品牌主办的活动，即便有收费也可发，
#   但正文必须写清「谁免费 / 谁收费 / 谁邀约」；识别不到公共属性主办的收费活动 → 硬拒。
# 不含「收费」二字本身 —— 它由下面的 CHARGED_STRICT_RE 带否定语境排除后单独匹配
CHARGE_WORDS = [
    "票价", "门票¥", "早鸟价", "会务费", "缴费", "付费参与", "付费报名",
    "展位费", "招商", "赞助席位", "商业合作",
]
CHARGED_RE = re.compile("|".join(re.escape(w) for w in CHARGE_WORDS))
# 「收费」需排除否定语境（不/免/无/未 收费），避免「免费 / 不收费」被误杀
CHARGED_STRICT_RE = re.compile(r"(?<!不)(?<!免)(?<!无)(?<!未)收费")

# 价格（非零）→ 活动语境下视为收费信号
PRICE_RE = re.compile(r"(?<![0-9])[1-9]\d{0,4}(?:\.\d+)?\s*元")
YEN_RE = re.compile(r"¥\s*[1-9]\d{0,4}")
USD_RE = re.compile(r"(?<![0-9])\$\s*[1-9]\d{0,4}")

# 「谁免费」说明（收费活动可发的前提之一）
FREE_RE = re.compile(r"(免费|不收费|零费用|公益)")
# 「谁邀约」说明（邀请制活动按 timeliness-window v1.5.0 必须注明）
INVITE_RE = re.compile(r"(邀请制|凭请柬|定向邀请|受邀|审核制|审核后)")

# 私人机构黑名单（确证私企，可直接扩写）
PRIVATE_ORG = ["赤道象限", "预策科技", "Monad", "monad", "宇树海康参访"]
PRIVATE_RE = re.compile("|".join(re.escape(w) for w in PRIVATE_ORG))

# ---------- 3. 合规主办方识别 ----------
# 3.1 事业单位 / 高校 / 园区（严格：只在「主办/承办」语境或知名机构名时生效，避免地点词误判）
GOV_INST = [
    "中科院", "社科院", "农科院", "医科院", "研究院", "研究所", "公立", "事业单位",
    "清华", "北大", "复旦", "上海交大", "浙大", "南大", "中科大", "哈工大", "同济",
    "武大", "华科", "西交", "北航", "北理工", "中国信通院", "之江实验室", "鹏城实验室",
    "科协", "科技局", "文旅局", "教育局", "管委会", "高新区", "经开区", "新区",
    # 政府机关 / 公共就业服务机构（2026-09-14 补：「人社局」等未被识别，导致政府主办的
    # 收费/免费活动都被判为"非公共属性主办"）
    "人民政府", "人力资源和社会保障", "人社", "社会保障", "人才服务中心", "就业促进中心",
    "公共就业", "人才市场", "经信委", "发改委", "科委", "商务局", "市场监管局", "服务中心",
    # 2026-09-14 再补：「人才网 / 人才交流中心 / 人力资源市场」等公共就业服务机构载体名
    "人才网", "人才交流中心", "人力资源市场", "就业服务",
    # 高校（2026-09-14 补：白名单原先只列内地名校简称，漏了港校与「大学」通称，
    # 导致「香港大学CAMO AI落地实验室」这类高校下属研究机构被误判非事业单位）
    "香港大学", "港大", "香港中文大学", "香港科技大学", "香港城市大学", "香港理工大学",
    "香港浸会大学", "澳门大学", "大学",
    # 政府共建的公共科创平台（2026-09-14 补：「模速空间」是上海市经信委与徐汇区共建的
    # 大模型创新生态社区，属公共平台而非商业机构；其自办/联合主办的产业峰会视为公共属性）
    "模速空间",
]
GOV_INST_RE = re.compile("|".join(re.escape(w) for w in GOV_INST))
# 政府/街道/社区 仅在「主办/承办/由…」语境后判定
GOV_CTX_RE = re.compile(
    r"(?:主办方|主办单位|承办方|承办单位|协办方|协办单位|由).{0,18}?"
    r"(政府|街道|社区|村委会|居委会|少年宫|青少年宫|图书馆|博物馆|文化馆)",
    re.S,
)

# 3.2 行业协会 / 学会 / 联盟
ASSOC = [
    "协会", "学会", "商会", "联合会", "联盟", "委员会", "基金会", "促进会", "研究会",
    "CCF", "中国计算机学会", "IEEE", "ACM",
]
ASSOC_RE = re.compile("|".join(re.escape(w) for w in ASSOC))

# 3.2b 国家级创新平台（2026-09-14 补：这类机构名不含"协会/学会/中心"等通用字样，
#      词表匹配不到，但属国家级公共平台 —— 如「国家机器人创新中心」被误判非事业单位）
NATIONAL_PLATFORM_RE = re.compile(
    r"国家.{0,12}(?:创新中心|实验室|工程研究中心|工程实验室|技术创新中心|制造业创新中心)"
    r"|国家.{0,6}研究院"
)

# 3.3 行业龙头 / 国央企白名单
LEADER = [
    "华为", "腾讯", "阿里", "支付宝", "蚂蚁", "字节", "抖音", "百度", "京东", "美团",
    "小米", "中兴", "大疆", "商汤", "科大讯飞", "宁德时代", "比亚迪", "上汽", "广汽",
    "国家电网", "中国移动", "中国联通", "中国电信", "中芯国际", "中石油", "中石化",
    "中国铁建", "中国中车", "中国电子", "浪潮", "寒武纪", "旷视", "依图", "云从",
    "之江", "浦江论坛", "外滩大会", "世界人工智能大会", "WAIC", "智博会", "数博会",
    "服贸会", "进博会", "高交会", "中关村论坛", "世界互联网大会", "中国互联网大会",
    "算力大会", "张江", "临港", "海创园", "央视", "人民日报", "新华社", "36氪",
    "量子位", "机器之心", "甲子光年", "钛媒体",
    # AI 垂直媒体 / 会议品牌（2026-09-14 补：与上面「量子位/机器之心/钛媒体」同类先例 ——
    # 长期办会的行业媒体品牌，其自办峰会视为行业会议品牌）
    #   智东西 / 智猩猩 / 芯东西 → 全球AI芯片峰会 GACS（2018 年创办，已办七届）
    #   DeepTech 深科技 → PAIR Conference（物理 AI 前沿峰会，定向邀请制）
    "智东西", "智猩猩", "芯东西", "DeepTech", "深科技",
    # 全球科技龙头外企（2026-09-14 补：恩智浦/安富利被误判"非龙头"，实际均为行业巨头）
    "恩智浦", "NXP", "安富利", "Avnet", "英特尔", "Intel", "英伟达", "NVIDIA",
    "微软", "Microsoft", "谷歌", "Google", "苹果", "Apple", "亚马逊", "Amazon",
    "AMD", "高通", "Qualcomm", "三星", "索尼", "ARM", "美光", "Micron",
    "德州仪器", "博世", "西门子", "SAP", "甲骨文", "Oracle", "IBM", "特斯拉", "Tesla",
    # 全球云计算/网络基础设施龙头（2026-09-14 补：Cloudflare 上海AI技术峰会，
    # 与上面「西门子/SAP/甲骨文」同类 —— 全球头部技术企业自办技术峰会）
    "Cloudflare",
]
LEADER_RE = re.compile("|".join(re.escape(w) for w in LEADER))

# 3.4 国家级 / 国际会议品牌（标题/正文出现即合规，裸判通过）
BRAND = [
    "世界人工智能大会", "WAIC", "智博会", "数博会", "服贸会", "进博会", "高交会",
    "中关村论坛", "浦江创新论坛", "外滩大会", "世界互联网大会", "中国互联网大会",
    "世界模型大会", "全球人工智能峰会", "国际人工智能",
    "全联接大会", "云栖大会", "张江药谷", "世界人工智能", "中国工业AI大会",
]
BRAND_RE = re.compile("|".join(re.escape(w) for w in BRAND))

# 主办实体抽取（主办/承办/指导/由…主办 之后 2~20 字）
# 2026-09-14 补 trailing「指导」：不少政府/事业单位主导的活动，正文写法是
# 「由 X 指导，A、B 主办」——公共属性体现在**指导单位**而非主办单位
# （例：广东科普创新展 主办为广州产投科创集团+南方出版传媒两家国企，
#   指导单位为广东省科技厅/省科协/中科院广州分院/省科学院）。
# 原逻辑抽不到「指导」，导致组织者被误判为「非公共属性」。
ORG_PHRASE = re.compile(
    r"(?:主办方|主办单位|承办方|承办单位|协办方|协办单位|组委会|由)\s*[:：]?\s*"
    r"(.{2,20}?)\s*(?:指导|主办|承办|协办|举办|发起|出品|主办方|承办方)",
    re.S,
)

# ---------- 4. 含金量信号 ----------
GOLD = [
    "主办", "承办", "协办", "支持单位", "指导单位", "院士", "专家", "学者", "教授",
    "国家级", "省级", "市级", "国际", "全球", "万人", "千人参会", "参展企业", "展览面积",
    "论坛", "峰会", "主旨演讲", "发布", "签约", "议题", "专场", "分论坛", "平行论坛",
    "白皮书", "报告", "榜单", "颁奖", "竞赛", "挑战赛", "开源", "生态",
]
GOLD_RE = re.compile("|".join(re.escape(w) for w in GOLD))

# ---------- 招聘类：只发科技产业链定位（2026-09-14 用户口径） ----------
# 用户原话：招聘会继续发，且优先 AI / 科技产业链 —— 即普通综合招聘会不发。
RECRUIT_RE = re.compile("招聘会|双选会|人才交流|校招|宣讲会|人才招聘|求职者")
TECH_CHAIN = [
    "人工智能", "AI", "半导体", "集成电路", "芯片", "机器人", "具身智能",
    "智能制造", "工业智控", "自动化", "新能源", "新材料", "生物医药",
    "数字经济", "软件", "互联网", "电子信息", "智能网联", "算力",
    "大模型", "低空经济", "量子", "通信", "光电", "智能终端", "智能建造",
    "跨境电商", "大数据", "文创", "科技",
]
TECH_CHAIN_RE = re.compile("|".join(re.escape(w) for w in TECH_CHAIN))

# ---------- 个人付费 ≥99 且非年度举办 → 硬拒（2026-09-14 用户口径） ----------
# 用户原话：私人机构不好过滤。要求个人付费 99 以上的且非年度形式举办的活动，都屏蔽掉。
# 用「价格 + 频次」代替主办方黑名单来过滤一次性收费活动（多为私人机构办的营利场）。
PERSONAL_PRICE_MIN = 99  # 含 99
PRICE_ALL_RE = re.compile(
    r"([0-9]+(?:\.[0-9]+)?)\s*元"
    r"|[¥￥]\s*([0-9]+(?:\.[0-9]+)?)"
    r"|\$\s*([0-9]+(?:\.[0-9]+)?)"
)
# 价格附近出现这些词 → 判定为面向个人的收费
PERSONAL_PAY_CTX = [
    "个人", "每人", "单人", "每人每", "观众", "参会者", "参会人", "参会人员",
    "门票", "入场", "票价", "参会费", "报名费", "席位", "学员", "用户", "票",
]
# 价格附近出现这些词 → 属 B 端/企业收费，不算个人付费（避免误杀招聘会展位费等）
# 注意：不要放「机构/主办」这类泛指词，「由某机构主办」不代表该价格是 B 端收费（2026-09-14 修正）
BIZ_PAY_CTX = ["企业", "展位", "展商", "团体", "赞助", "招商", "B端", "商家", "厂商"]
# 价格附近出现这些词 → 是赠品/原价锚定，不是实际收费
GIFT_PAY_CTX = ["原价", "价值", "赠送", "礼包", "奖品", "免费送", "减免"]
# 年度 / 届次形式举办 → 不因价格屏蔽
ANNUAL_RE = re.compile(
    r"第\s*[0-9一二三四五六七八九十百]+\s*届"
    r"|年度|annual|Annual|ANNUAL"
    r"|每年|常年|一年一届|一年一度"
    r"|第\s*[0-9]+\s*年"
)


def personal_pay_hits(text):
    """返回面向个人、且 ≥ PERSONAL_PRICE_MIN 的价格列表 [(数值, 上下文片段)]"""
    out = []
    for m in PRICE_ALL_RE.finditer(text):
        raw = next((g for g in m.groups() if g), None)
        if not raw:
            continue
        try:
            val = float(raw)
        except ValueError:
            continue
        if val < PERSONAL_PRICE_MIN:
            continue
        ctx = text[max(0, m.start() - 30): m.end() + 30]
        if any(w in ctx for w in GIFT_PAY_CTX):
            continue
        if any(w in ctx for w in BIZ_PAY_CTX):
            continue
        # 出现 B 端词已排除；其余一律视为面向个人（含无标记价格，保守处理）
        out.append((val, ctx.strip().replace("\n", " ")))
    return out


def is_event(text):
    return bool(EVENT_RE.search(text))


def has_public_keyword(s):
    return bool(GOV_INST_RE.search(s) or GOV_CTX_RE.search(s) or ASSOC_RE.search(s)
                or LEADER_RE.search(s) or BRAND_RE.search(s)
                or NATIONAL_PLATFORM_RE.search(s))


def main():
    ap = argparse.ArgumentParser(description="主办资质闸门")
    ap.add_argument("--title", default="")
    ap.add_argument("--content", default="")
    ap.add_argument("--file", help="正文文件路径（与 --content 二选一）")
    args = ap.parse_args()

    title = (args.title or "").strip()
    content = args.content or ""
    if args.file and os.path.exists(args.file):
        with open(args.file, encoding="utf-8") as f:
            content = f.read()
    text = title + "\n" + content

    # 非活动类 → 跳过
    if not is_event(text):
        print("主办资质: 跳过（非活动/展会类内容）")
        return 0

    # 硬拒：私人机构黑名单（确证私企）
    priv = PRIVATE_RE.findall(text)
    if priv:
        print(f"主办资质: !! 硬拒 —— 命中私人机构黑名单: {sorted(set(priv))}")
        return 1
    # 硬拒：卖课/内训/私享会性质（与主办是谁无关）
    hard = HARD_RE.findall(text)
    if hard:
        print(f"主办资质: !! 硬拒 —— 命中培训/卖课/私享性质: {sorted(set(hard))}")
        return 1

    # 招聘类题材限定：须有科技产业链定位（2026-09-14 用户口径）
    if RECRUIT_RE.search(text) and not TECH_CHAIN_RE.search(text):
        print("主办资质: ⚠ 复核 —— 招聘类活动，但正文未出现任何科技产业链定位"
              "（AI/半导体/机器人/智能制造/生物医药/新能源…）。")
        print("          按用户口径：普通综合招聘会不发，只发有明确科技产业链定位的招聘/双选会。")
        print("          如确属科技类请补充产业链方向后重跑；否则不予发布。")
        return 2

    # 个人付费 ≥99 且非年度举办 → 硬拒（2026-09-14 用户口径，替代难穷举的私人机构名单）
    pp = personal_pay_hits(text)
    if pp:
        if ANNUAL_RE.search(text):
            print(f"主办资质: 提示 —— 正文含个人付费 {[v for v, _ in pp]}（≥{PERSONAL_PRICE_MIN}），"
                  f"但识别为年度/届次形式举办，不因价格屏蔽；仍需过主办方与「谁免费」校验")
        else:
            for v, ctx in pp:
                print(f"主办资质: !! 硬拒 —— 面向个人付费 {v:.0f} 元（≥{PERSONAL_PRICE_MIN}），"
                      f"且未识别为年度/届次形式举办 → 按「个人付费高价+非常设活动」屏蔽")
                print(f"          上下文: …{ctx[:60]}…")
            print("          若确为年度常设活动（第N届 / 年度峰会），请在正文写明届次后重跑")
            return 1

    # 主办实体（收费判定与资质判定共用，只抽一次）
    orgs = [m.group(1).strip() for m in ORG_PHRASE.finditer(text)]
    orgs = [o for o in orgs if o]
    public_org = [o for o in orgs if has_public_keyword(o)]
    brand = bool(BRAND_RE.search(text))

    # 收费：不是原罪，看主办方性质（2026-09-14 用户口径）
    #   政府/事业单位/高校/协会/行业龙头/会议品牌主办 且有收费 → 可发，
    #   但正文必须写清「谁免费」；识别不到公共属性主办的收费活动 → 硬拒（视为私人收费活动）
    charge_hits = (sorted(set(CHARGED_RE.findall(text)))
                   + sorted(set(CHARGED_STRICT_RE.findall(text))))
    price_hit = sorted(set(PRICE_RE.findall(text) + YEN_RE.findall(text) + USD_RE.findall(text)))
    if charge_hits or price_hit:
        what = charge_hits or price_hit
        if not (public_org or brand):
            print(f"主办资质: !! 硬拒 —— 活动含收费 {what}，且未识别到事业单位/高校/协会/"
                  f"行业龙头/会议品牌主办 → 按「私人活动收费不发」处理")
            return 1
        if not FREE_RE.search(text):
            print(f"主办资质: ⚠ 复核 —— 活动含收费 {what}；主办属公共/行业性质可发，"
                  f"但正文未写明「谁免费」，请补上免费对象（个人/观众/求职者等）")
            return 2
        print(f"主办资质: 提示 —— 含收费 {what}；主办合规且已写明免费对象。"
              f"发布前请再核：谁收费、谁邀约 是否在正文写清")
        if not INVITE_RE.search(text):
            print("主办资质: 提示 —— 正文未出现邀约说明；若本场含邀请/审核入场，须写明谁邀约")

    # 资质判定：品牌活动裸判通过，否则看主办实体
    if brand:
        pass
    else:
        if orgs:
            if not public_org:
                print(f"主办资质: !! 硬拒 —— 主办方非事业单位/行业龙头/协会: {orgs[0][:20]}")
                return 1
        else:
            print("主办资质: ⚠ 复核 —— 全文未找到明确主办方（主办/承办/由…主办），请人工确认")
            return 2

    # 含金量信号
    gold = GOLD_RE.findall(text)
    if not gold:
        print("主办资质: ⚠ 复核 —— 已识别合规主办方，但正文缺少含金量信号（主办/规模/权威/嘉宾等），建议人工确认")
        return 2

    print("主办资质: OK —— 合规主办方 + 含金量信号具足")
    print(f"   含金量信号: {sorted(set(gold))[:8]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
