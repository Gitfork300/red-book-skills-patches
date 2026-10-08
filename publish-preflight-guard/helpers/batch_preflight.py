# -*- coding: utf-8 -*-
r"""批次发布前总检查 —— 一次跑完 publish-preflight-guard 的可自动化条目。

为什么需要它
------------
`publish-preflight-guard` 的 19 项检查里，有 12 项是可自动化的（1/2/3/4/8/9/10/11/14/15/16/17），
但每开一个新批次都要现写一遍胶水脚本 —— 2026-09-12 ai0912 批次就是这么干的。
把它固化下来，此后一条命令跑完，人工只判剩下的 6 项。

输入：批次稿件 JSON（约定 schema，与 `xhs_publish/*_notes.json` 一致）

    {
      "batch": "ai0912",
      "notes": [
        {
          "key": "ai0912_1",                  # 必填，稿件文件名前缀
          "name": "2026 广东省科普创新展",     # 可选，仅用于打印
          "city": "广州",                      # 必填，第 2 项地域
          "start": "2026-09-18",              # 必填，第 3 项时效
          "end": "2026-09-20",
          "live": false,                      # 必填，第 4 项资格
          "public_signup": true,
          "non_activity": false,              # 非活动类（技术前沿/天气/Canary）设 true
          "class": "a",                       # 可选，第 1 项查重窗口：a|industry|other
          "title": "…",                       # 必填，可用 title_file 代替
          "content": "…",                     # 必填，可用 content_file 代替
          "cover": "…/ai0912_1_cover.png"     # 必填，第 11 项
        }
      ]
    }

`title_file`、`content_file` 和 `cover` 的相对路径均以**当前工作目录**为基准；
建议使用绝对路径或从路径所依据的目录启动。标题/正文文件缺失或为空会报错退出，
不会用空文本继续预检。非活动类每篇需设 `"non_activity": true`，以跳过会展地域、
时效/资格闸门，并在正文使用「阅读门槛 / 适合人群 / 专业性 / 信息量级」评级维度。

用法
----
    python batch_preflight.py --notes xhs_publish/ai0912_notes.json
    python batch_preflight.py --notes … --default-class industry   # 未标 class 的按此归类
    python batch_preflight.py --notes … --order file               # 按 JSON 顺序，不按优先级
    python batch_preflight.py --notes … --only 1,8,9               # 只跑指定「检查项」
    python batch_preflight.py --notes … --only-notes 1,3,5         # 只检查指定「稿件」

退出码：0 = 自动化条目全过 / 1 = 有未通过 / 2 = 参数或环境错误

新增第 16 项「主办资质闸门」：调用 organizer-qualification-guard 的 check_organizer.py，
仅对活动/展会/论坛类生效，exit 1（私企/付费小班/无合规主办方）计入 fails 阻断发布，
exit 2（找不到明确主办方）仅打印复核提示。

约定与判据
----------
- **第 1 项查重**：`dup_check.py --title … --class …`，退出码须为 0。
  类别窗口（用户 2026-09-12 要求）：**A 类当天 / 行业类 3 天 / 其他 15 天内不得重复**。
- **第 9 项字数**（2026-09-14 用户口径）：脚本自算两个数 —— **核心正文**（末个 `—` 分隔行之前，
  不含评级块 / 来源）须 **200–600 字**；**全篇**（整个正文文件）须 **<1000 字**。任一越界即 fail。
  旧的「正文 200–700（含评级块）」口径已作废。
- **第 14 项配额**：`quota_check.py --kind weather --level <级别>` **仅当本批含恶劣天气类选题时才跑**
  —— 对非天气批次无条件下闸门会误报"今日配额已满"。
- **第 17 项评级块**：正文须含 `参与难度 / 适合人群 / 专业性 / 活动规模 / 来源：` 五字段，
  且首行匹配 `^综合\s*[★☆]`（**汉字在前、星级在后**）。缺任一项即 fail。
  来源：2026-09-14 云栖批次整批漏写「综合」行 / 顺序写反，旧预检未覆盖此格式闸门。
- **未标 `class` 时按 `--default-class`（默认 other）**，即走最长窗口（更保守）。
- 第 5/6/7/10/12/13 项是人工判据，脚本只列出待核对清单，不给结论。
"""
import argparse
import json
import os
import re
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
PATCH_ROOT = os.path.normpath(os.path.join(HERE, ".."))
PATCHES_ROOT = os.path.normpath(os.path.join(PATCH_ROOT, ".."))
DUP = os.path.join(PATCHES_ROOT, "publish-loop-guard", "helpers", "dup_check.py")
GEO = os.path.join(PATCHES_ROOT, "timeliness-window", "helpers", "geo_check.py")
WIN = os.path.join(PATCHES_ROOT, "timeliness-window", "helpers", "check_window.py")
QUOTA = os.path.join(PATCHES_ROOT, "timeliness-window", "helpers", "quota_check.py")
WORD = os.path.join(PATCHES_ROOT, "safe-wording-guard", "helpers", "check_wording.py")
ORG = os.path.join(PATCHES_ROOT, "organizer-qualification-guard", "helpers", "check_organizer.py")
NET = os.path.join(PATCHES_ROOT, "windows-sandbox-workaround", "helpers", "net_probe.py")

# 用本体系里的 python（默认当前解释器）
PY = os.environ.get("PREFLIGHT_PY") or sys.executable

CLASS_ORDER = {"a": 0, "industry": 1, "other": 2}
TYPHOON_KW = ("台风", "热带低压", "热带风暴", "强热带风暴", "热带扰动", "强对流")
# 恶劣天气类选题识别词（2026-09-15 扩表：原仅 6 个台风词，现覆盖全部灾害类型 + 预警）
WEATHER_KW = TYPHOON_KW + ("暴雨", "强降水", "雷暴", "雷雨大风", "冰雹", "高温",
                           "寒潮", "低温", "大风", "大雾", "霾", "内涝", "风暴潮", "预警")
# 预警级别优先级：红/黑触发 3 篇额度，其余仍 1 篇（用户 2026-09-15）
LEVEL_ORDER = ("红色", "黑色", "橙色", "黄色", "蓝色")

# 第 17 项：底部评级块（展会/活动类必带）
RATING_FIELDS = ("参与难度", "适合人群", "专业性", "活动规模", "来源：")
# 第 17 项适配版：技术前沿（非活动类）用「阅读门槛 / 信息量级」替换「参与难度 / 活动规模」
RATING_FIELDS_ADAPTED = ("阅读门槛", "适合人群", "专业性", "信息量级", "来源：")
# 首行必须是「综合 ★…」——汉字在前、星级在后（2026-09-14 用户口径，不能写成「★… 综合」）
OVERALL_RE = re.compile(r"^综合\s*[★☆]", re.M)

# 第 9 项：字数闸门（2026-09-14 用户口径）
#   核心正文 = 末个「—」分隔行之前的文字（不含评级块 / 来源）
#   全篇     = 整个正文文件
CORE_MIN, CORE_MAX = 200, 600
TOTAL_MAX = 1000


def split_core(content):
    """按**末个**「—」分隔行切分，返回 (核心正文, 附加内容)。

    无分隔行时整篇视作核心正文。切分点与发布链模板 `_publish_chain_s0914.py` 保持一致。
    """
    lines = content.splitlines()
    idx = [i for i, l in enumerate(lines) if l.strip() == "—"]
    if not idx:
        return content, ""
    cut = idx[-1]
    return "\n".join(lines[:cut]), "\n".join(lines[cut:])


def run(args, timeout=180):
    try:
        # 2026-10-03：args 可能混入 bool/None（JSON 里的 live / public_signup 写 true/false），
        # subprocess 只吃 str/bytes/PathLike，否则抛 TypeError 被下面 except 吞成 "exit=99"，
        # 整批第 3/4 项误报 FAIL。此处统一归一化后再交给子进程。
        args = [_s(a) for a in args]
        r = subprocess.run(args, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except Exception as e:
        return 99, f"(执行失败: {e})"


def _s(v):
    """把任意标量转成子进程可接受的命令行字符串。

    bool True/False → yes/no（check_window 的口径）；None → unknown；其余原样 str()。
    """
    if v is None:
        return "unknown"
    if isinstance(v, bool):
        return "yes" if v else "no"
    return str(v)


def tail(text, n=3):
    return [l for l in (text or "").splitlines() if l.strip()][-n:]


def field(note, key):
    """取 title/content：支持内联或 *_file 两种写法。"""
    value = note.get(key)
    if value is not None:
        if not isinstance(value, str):
            raise ValueError(f"{key} 必须是文本")
        if value.strip():
            return value
    p = note.get(key + "_file")
    if p:
        if not isinstance(p, str):
            raise ValueError(f"{key}_file 必须是路径文本")
        if not os.path.isfile(p):
            raise FileNotFoundError(
                f"{key}_file 不存在或不是文件：{p} "
                f"（相对路径按当前工作目录解析：{os.getcwd()}）"
            )
        with open(p, encoding="utf-8") as f:
            value = f.read()
        if value.strip():
            return value
        raise ValueError(f"{key}_file 内容为空：{p}")
    raise ValueError(
        f"稿件 {note.get('key') or '<未命名>'} 缺少 {key} 或 {key}_file"
    )


def main():
    ap = argparse.ArgumentParser(description="批次发布前总检查（可自动化条目）")
    ap.add_argument("--notes", required=True, help="批次稿件 JSON 路径")
    ap.add_argument("--default-class", default="other",
                    choices=["a", "industry", "other"], help="未标 class 的稿件按此归类（默认 other，最保守）")
    ap.add_argument("--order", default="priority", choices=["priority", "file"],
                    help="检查/发布顺序：priority=A类>行业类>其他；file=按 JSON 原序")
    ap.add_argument("--only", help="只跑指定**检查项**（19 项表里的编号，逗号分隔），如 1,8,9")
    ap.add_argument("--only-notes", help="只检查指定**稿件**（1 基，逗号分隔），如 1,3,5")
    ap.add_argument("--tmpdir", help="标题/正文落盘目录，默认 <notes 同目录>/tmp_check")
    args = ap.parse_args()

    if not os.path.exists(args.notes):
        print(f"稿件文件不存在：{args.notes}", file=sys.stderr)
        return 2
    with open(args.notes, encoding="utf-8") as f:
        data = json.load(f)
    notes = data.get("notes") or []
    if not notes:
        print("稿件 JSON 里没有 notes[]", file=sys.stderr)
        return 2

    for index, n in enumerate(notes, 1):
        if not isinstance(n, dict):
            print(f"第 {index} 篇稿件必须是 JSON 对象", file=sys.stderr)
            return 2
        try:
            n["_title_text"] = field(n, "title")
            n["_content_text"] = field(n, "content")
        except (OSError, ValueError) as error:
            print(f"稿件输入无效（第 {index} 篇，{n.get('key') or '<未命名>'}）：{error}",
                  file=sys.stderr)
            return 2
        n["_class"] = n.get("class") or args.default_class

    if args.order == "priority":
        notes.sort(key=lambda n: CLASS_ORDER.get(n["_class"], 9))

    # --only-notes 按稿件序号过滤；--only 按检查项编号过滤（2026-10-03 修正）
    if args.only_notes:
        want = {int(x) for x in re.split(r"[,\s]+", args.only_notes) if x.strip().isdigit()}
        notes = [n for i, n in enumerate(notes, 1) if i in want]
    CHECKS = None
    if args.only:
        CHECKS = {int(x) for x in re.split(r"[,\s]+", args.only) if x.strip().isdigit()}
        print(f"只跑检查项：{sorted(CHECKS)}")

    def want(*nums):
        """是否跑某个检查项（nums 为其覆盖的编号，如 8 和 9 同属一次 subprocess 调用）。"""
        return CHECKS is None or any(x in CHECKS for x in nums)

    tmp = args.tmpdir or os.path.join(os.path.dirname(os.path.abspath(args.notes)), "tmp_check")
    os.makedirs(tmp, exist_ok=True)

    print("=" * 78)
    print(f"批次发布前总检查：{data.get('batch') or os.path.basename(args.notes)}  共 {len(notes)} 篇")
    if args.order == "priority":
        print("顺序：A 类 > 行业类 > 其他（用户 2026-09-12 要求）")
    print("=" * 78)

    fails = []
    for i, n in enumerate(notes, 1):
        key, cls = n.get("key", f"#{i}"), n["_class"]
        title, content = n["_title_text"].strip(), n["_content_text"]
        print(f"\n{'-' * 78}")
        print(f"[{i}/{len(notes)}] {key}  ({'A 类' if cls == 'a' else '行业类' if cls == 'industry' else '其他'})"
              f"  {n.get('name', '')}")
        print(f"{'-' * 78}")
        print(f"  标题: {title}")
        # 检查项被 --only 跳过时，下游的 if rc != 0 / if not ok 不应炸 NameError
        rc, out, ok = 0, "", True

        tp = os.path.join(tmp, f"{key}_title.txt")
        cp = os.path.join(tmp, f"{key}_content.txt")
        with open(tp, "w", encoding="utf-8") as f:
            f.write(title)
        with open(cp, "w", encoding="utf-8") as f:
            f.write(content)

        # 1) 选题查重（类别化窗口）
        if not want(1):
            print("  [1]  查重".ljust(38) + "SKIP")
        else:
            rc, out = run([PY, DUP, "--title", title, "--class", cls])
            print(f"  [1]  查重(--class {cls})".ljust(38) + f"exit={rc} {'OK' if rc == 0 else '!! FAIL'}")
        for l in tail(out, 3):
            print("       " + l)
        if rc != 0:
            fails.append((key, 1, "查重"))

        # 2) 地域范围
        #    非活动类（技术前沿 / 天气）不适用会展三闸门（地域/时效/主办资格）——
        #    skill 明文口径；稿件用 non_activity=true 声明，此处显式 SKIP 而非假装通过。
        if not want(2):
            print("  [2]  地域".ljust(38) + "SKIP")
        elif n.get("non_activity"):
            print("  [2]  地域（非活动类·闸门不适用）".ljust(38) + "SKIP")
            rc = 0
        else:
            rc, out = run([PY, GEO, "--city", n.get("city", "")])
            print(f"  [2]  地域 {n.get('city', '?')}".ljust(38) + f"exit={rc} {'OK' if rc == 0 else '!! FAIL'}")
            for l in tail(out, 2):
                print("       " + l)
            if rc != 0:
                fails.append((key, 2, "地域"))

        # 3+4) 时效窗口 + 可发布资格（同上：非活动类不适用）
        if not want(3, 4):
            print("  [3/4] 时效+资格".ljust(38) + "SKIP")
        elif n.get("non_activity"):
            print("  [3/4] 时效+资格（非活动类·闸门不适用）".ljust(38) + "SKIP")
        else:
            rc, out = run([PY, WIN, "--start", n.get("start", ""), "--end", n.get("end", ""),
                           "--deadline", n.get("deadline", ""),
                           "--category", n.get("category", "normal"),
                           "--live", "yes" if n.get("live") else ("unknown" if n.get("live") is None else "no"),
                           "--public-signup", n.get("public_signup", "unknown")])
            # 退出码口径（check_window.main 末段）：0=全通过 / 1=时效 BLOCK / 3=**资格 BLOCK**。
            # 旧写法 `rc in (0, 3)` 把「资格不通过 / 资格未核实 UNKNOWN」当成 OK，
            # 2026-10-03 修 —— 与 judge_eligibility 一致，UNKNOWN 也必须阻断。
            ok = rc == 0
            print("  [3/4] 时效+资格".ljust(38) + f"exit={rc} {'OK' if ok else '!! FAIL'}"
                  f"  (start={n.get('start')} end={n.get('end')}"
                  f" live={n.get('live')} signup={n.get('public_signup')})")
            for l in tail(out, 3):
                print("       " + l)
            if not ok:
                fails.append((key, 3, "时效/资格"))

        # 8+9) 用词预检 + 字数
        if not want(8):
            print("  [8]   用词".ljust(38) + "SKIP")
        else:
            rc, out = run([PY, WORD, "--title", title, "--file", cp])
            print("  [8]   用词".ljust(38) + f"exit={rc} {'OK' if rc == 0 else '!! FAIL'}")
            for l in tail(out, 6):
                print("       " + l)
            if rc != 0:
                fails.append((key, 8, "用词"))

        # 9) 字数闸门：核心正文 200-600 + 全篇 <1000（2026-09-14 用户口径）
        if not want(9):
            print("  [9]  字数".ljust(38) + "SKIP")
        else:
            core, _extra = split_core(content)
            n_core, n_total = len(core.strip()), len(content.strip())
            why = []
            if not (CORE_MIN <= n_core <= CORE_MAX):
                why.append(f"核心正文 {n_core} 字 越界（{CORE_MIN}-{CORE_MAX}）")
            if n_total >= TOTAL_MAX:
                why.append(f"全篇 {n_total} 字 ≥ {TOTAL_MAX}")
            print("  [9]  字数".ljust(38)
                  + f"核心 {n_core}(200-600) / 全篇 {n_total}(<1000)"
                  + ("  OK" if not why else "  !! FAIL"))
            if why:
                print("       " + "；".join(why))
                fails.append((key, 9, "字数"))

        # 11) 封面文件核对（存在性 + 尺寸）
        cov = n.get("cover") or ""
        if not want(11):
            print("  [11] 封面".ljust(38) + "SKIP")
        elif cov and os.path.exists(cov):
            kb = os.path.getsize(cov) // 1024
            dim = ""
            try:
                import struct
                with open(cov, "rb") as f:
                    dim = "{}x{}".format(*struct.unpack(">II", f.read(33)[16:24]))
            except Exception:
                pass
            print(f"  [11] 封面 {os.path.basename(cov)} {dim} {kb} KB"
                  + "  ← 仍需**人工打开核对**红线（人/地图/文字/二维码/完整人形机器人）")
        else:
            print("  [11] 封面 !! 缺失")
            fails.append((key, 11, "封面缺失"))

        # 16) 主办资质闸门（仅活动类；非活动类自动跳过；exit 1=硬拒 2=复核）
        if not want(16):
            print("  [16] 主办资质".ljust(38) + "SKIP")
        else:
            rc, out = run([PY, ORG, "--title", title, "--file", cp])
            tag = "OK" if rc == 0 else ("⚠复核" if rc == 2 else "!! FAIL")
            print("  [16] 主办资质".ljust(38) + f"exit={rc} {tag}")
            for l in tail(out, 4):
                print("       " + l)
            if rc == 1:
                fails.append((key, 16, "主办资质"))

        # 17) 底部评级块（展会/活动类必带；首行「综合 ★…」汉字在前）
        #     技术前沿类用适配四维：阅读门槛 / 适合人群 / 专业性 / 信息量级
        #     （用户 2026-09-16 口径：话题 C 的评级块按适配维度校验）
        if want(17):
            if n.get("non_activity") and ("阅读门槛" in content or "信息量级" in content):
                miss = [f for f in RATING_FIELDS_ADAPTED if f not in content]
            else:
                miss = [f for f in RATING_FIELDS if f not in content]
            if miss:
                print("  [17] 底部评级块".ljust(38) + f"!! FAIL  缺字段：{'、'.join(miss)}")
                fails.append((key, 17, "评级块缺字段"))
            elif not OVERALL_RE.search(content):
                print("  [17] 底部评级块".ljust(38)
                      + "!! FAIL  缺首行「综合 ★…」（汉字在前，不能是「★… 综合」）")
                fails.append((key, 17, "评级块首行顺序/缺失"))
            else:
                print("  [17] 底部评级块".ljust(38) + "OK  首行「综合 ★…」+ 四维 + 来源")
        else:
            print("  [17] 底部评级块".ljust(38) + "SKIP")

    # 14) 选题配额 —— 仅当本批含恶劣天气类选题时适用
    #    红/黑预警放宽到 3 篇：从稿件文本嗅探级别并透传给 --level（查不到即按 1 篇拦）
    hit = []
    level = None
    for n in notes:
        text = n["_title_text"] + n["_content_text"]
        if not any(w in text for w in WEATHER_KW):
            continue
        hit.append(n.get("key"))
        if level is None:
            for lv in LEVEL_ORDER:
                if lv in text:
                    level = lv
                    break
    print(f"\n{'=' * 78}")
    if not want(14):
        print("  [14] 恶劣天气类配额".ljust(38) + "SKIP")
    elif hit:
        cmd = [PY, QUOTA, "--kind", "weather"]
        if level:
            cmd += ["--level", level]
        rc, out = run(cmd)
        tag = f"恶劣天气类配额（级别={level or '未识别→按 1 篇'}）"
        print(f"  [14] {tag}".ljust(38) + f"exit={rc} {'OK' if rc == 0 else '!! FAIL'}")
        for l in tail(out, 4):
            print("       " + l)
        if rc != 0:
            fails.append(("GLOBAL", 14, "配额"))
    else:
        print("  [14] 恶劣天气类配额".ljust(38) + "不适用（本批无天气影响类选题）")

    # 15) 网络可达性（必须真 TLS 握手）
    if not want(15):
        print("  [15] 网络可达性(TLS)".ljust(38) + "SKIP")
    else:
        rc, out = run([PY, NET])
        print("  [15] 网络可达性(TLS)".ljust(38) + f"exit={rc} {'OK' if rc == 0 else '!! FAIL'}")
        for l in tail(out, 4):
            print("       " + l)
        if rc != 0:
            fails.append(("GLOBAL", 15, "网络"))

    print(f"\n{'=' * 78}")
    if fails:
        print("结果: !! 有未通过项")
        for k, item, why in fails:
            print(f"  - {k} 第 {item} 项（{why}）")
        return 1

    print("结果: 自动化条目全过（1/2/3/4/8/9/11/14/15/16/17）")
    print("仍需人工判据（本脚本不给结论）：")
    print("  [5]  事实与时效   —— 时间/价格/人数/规模双源核实，信源在 7 日内")
    print("  [6]  标题说明内容 —— 含主体 + 看点或门槛，非「流水号 + 日期」式")
    print("  [7]  参与方式写全 —— 邀约 / 登记 / 审核 / 截止 / 凭证 / 名额限制")
    print("  [10] 封面合规     —— 逐张打开看过：无人物 / 地图边界 / 文字 / 二维码 / 完整人形机器人")
    print("  [12] AI 声明      —— 含 AI 图或 AI 文 → 发布传 --content-declaration")
    print("  [13] 间隔闸门     —— 8~12 分钟随机（publish_interval.py wait --max-block 900）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
