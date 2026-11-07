---
name: publish-loop-guard
system: publish
version: 1.13.3
description: "「启动」触发自动检索发布与漏发复核、事件三道信号查重、长批次硬停止；「进度」触发标准进度报告。触发词：启动、查重、进度、漏发。"
patch_for: red-book-skills
applies_to_main_version: ">=0.1.0"
priority: 28
author: Project maintainers
created: 2026-09-11
---

# publish-loop-guard

> Patch：**「启动」「进度」触发词 + 长流程漏发复核**。
> 1）用户说「启动」= 自动检索展会/活动并走完整发布流程；
> 2）流程运行期间每 30 分钟复核一次历史文章是否漏发，漏发必须重新过预检再补发；
> 3）用户问「进度 / 进展 / 推进情况」= 立即输出四块标准进度报告（见第二节）。

## 一、「启动」触发词

用户单独说「启动」时，不再等补充指令，直接按顺序自动跑：

| 步 | 动作 | 依据 patch |
| --- | --- | --- |
| 1 | 检索近期展会 / AI 活动 / 政策类选题 | — |
| 2 | 时效窗口：只留近 7 天在举行 / 近 7 天需报名 | `timeliness-window` |
| 3 | 可发布资格：无直播且普通观众无法报名 → 不发 | `timeliness-window` |
| 4 | 选题配额：恶劣天气类每日 ≤1 篇（红/黑预警放宽至 3 篇） | `timeliness-window` |
| 5 | 选题查重（按事件，不按标题字面）：每条待发跑 `dup_check.py`，退出码 0 | 本 patch |
| 6 | 写稿 → 用词/字数预检 → 封面 → 发布前 17 项总检查 | `writing-facts-only` 等 |
| 7 | 按 6~14 分钟随机间隔逐篇发布（每篇 verify 通过才计间隔） | `publish-interval-guard` |
| 8 | 流程全程挂 30 分钟漏发复核 | 本 patch |
| 9 | 逐篇回报 `note_id`，结束报总表 | — |

**启动必做**（否则复核误判）：
1. 把本次队列所有 key 写入 `state/inflight.json`
2. 起后台看门狗 `helpers/watch_missing.py`

**既有要求**：活动写明参与方式；标题说清内容、≤20 字；封面真实感照片优先、必带 AI 水印；只陈述事实、来源标注正文末尾；港澳台写「中国香港/中国澳门/中国台湾地区」。

### 选题查重（按事件，不按标题字面）

`check_missing.py` 用标题**精确匹配**判断"发没发过"，拿它查重会漏（同活动两次写稿标题必不同）。
排队前对每条待发标题跑 `dup_check.py --title "<标题>" --class a|industry|other`。

**类别化查重窗口与发布优先级**：

| 类别 | 判定 | `--class` | 不得重复窗口 |
|---|---|---|---|
| A 类（公众型） | 免费/低门槛，普通读者能到场 | `a` | 当天 |
| 行业类 | 专业展/面向特定从业者 | `industry` | 7 天 |
| 其他 | 其余 | `other` | 15 天 |

- 发布优先级 **A 类 > 行业类 > 其他**；拿不准 → 按更长窗口（`other`）。
- 命中「事件标识相同」（论坛/大会/峰会/展/博览会/年会…结尾专名一致）→ 高置信重复，**同一活动默认只留一篇**。
- 公共子串 ≥5 字信号；**日期/数字串、模板动词（开幕/举办/举行…）不作重复证据**（`identity()` 先剥）。
- 稿件同名 = 自己，不算重复；**日志里的同名必须拦**（= 已发过）。→ **预检必须在发布前做**。
- 🔴 **第三道信号：地点 + 日期**（案例见 `refs/01-detail.md`）。
  前两道**换标题措辞即可绕过**。同城 + 同会期，剥掉**地名/日期/事件后缀/通用词**后
  仍有 ≥2 字公共词 → 判重复。**`[Canary]` 稿豁免本信号**（只查标题逐字；`--series` 仍不豁免）。

### 🚨 查重必须双源

单源会漏（两者覆盖面不同）；`dup_check.py` 已双源合并且平台条目 `always=True` 绕时间窗。
**任何批量发布链，预检必须逐条跑 dup_check；缺失即为高危。** 细节见 `refs/01-detail.md`。

### 补发 / 续跑的三条铁律
1. `--from-key X` 只跑 X（续跑须显式 `--continue`）；2. 发布前查 `state/near_dup_tags.json`，同标题即 SKIP；3. `--series` 只放宽「活动名公共子串」，标题全同仍判重复。

### 近似文章限次（层级 + 主题 双维）

`dup_check` 拦不住「不同事件但看着像重复」，由 `near_dup_limit.py` 管：level×topic 双维限次
（国家级/行业级 24h/7天 ≤1，专题系列豁免），**发布成功后必须 `--record` 落标签**；
取值表、限次规则与「不要靠标题自动判层级」事故见 `refs/01-detail.md` §一点五。

## 二、「进度」触发词 —— 标准进度报告（v1.11.0，2026-10-16 用户拍板）

**触发词**：用户问「进度 / 进展 / 推进情况 / 怎么样了」→ **立即**输出四块标准进度报告，
不等补充指令（与「收尾/落盘」同款触发即回执）。

| 块 | 内容 | 数据来源 |
|---|---|---|
| ① 分组进度表 | 每组「已建仓/已发布/待发」+ 明细（key+状态） | jobs 文件 + `_NNNN_pub_progress.json` published 计数 |
| ② 预计推进表 | 「时段 × 预计进度 × 组」+ 收官 ETA 与数学账 | guard 末条 next_gap；间隔 IMIN/IMAX |
| ③ 小任务进度 | 天气/评论巡检/提醒/Canary/重发项/bug 债/收口 | memory 当日日志 + automation 列表 |
| ④ 阻塞与风险 | 卡点（事故/pending/Chrome/平台侧）+ 拍板项 ≤3 条 | 实时诊断：pending、<PORT_PUBLISH> LISTENING、creator 可达性 |

硬性要求（**列结构与标记符号照抄 `refs/03-progress-report.md` 样板**）：
① 篇数以 progress 文件 published 为准，**禁 `publish_log.json` 推算**（B-048 同族）；
② 推进表必带数学账（剩余×(间隔中值+80s)，上下界都算），ETA 超 22:00 或超用户收官点
**先算账再 AskUserQuestion 请示**（间隔压缩属规则级变更，660–1920s 为默认）；
③ 小任务八项逐项给状态；④ 拍板项 ≤3 条，与发布链解耦；⑤ 事故**先处置后报告**（见 refs 03 §三）；
⑥ ①表六列（组/内容/已建仓/已发布/待发/明细）与标记符号照抄 `refs/03` 样板。

## 三、30 分钟漏发复核

批量发布通常持续 1~2 小时，期间可能中断或超时。交由脚本每 30 分钟检查：

| 步 | 动作 |
| --- | --- |
| 1 | 先写 key 进 `state/inflight.json`，再起看门狗（顺序不能反） |
| 2 | 立即跑基线 `check_missing.py`，确认 `OK 无漏发` |
| 3 | 起 `watch_missing.py --interval 1800` |
| 4 | 见 `ALERT_MISSING` → **不是直接重发** |
| 5 | 重新过完整预检（时效 → 资格 → 配额 → 用词/字数 → 封面） |
| 6 | 内容不合规 → 改稿再发 |
| 7 | 时效/资格不合格 → 不补发，登记 `pending_pool.json` |
| 8 | 合规补发仍走 6~14 分钟随机间隔，记录 `note_id` |

**复核范围（只查"这一批有没有漏"）**：稿件侧只扫最近 2~3 天（`--days 2`）；平台侧只读 note-manager 第一页（最新 10 条），不翻页、不切标签；状态侧只看「已发布/审核中/未通过」。
**判定链**：稿件标题 → 与 `publish_log.json` 精确匹配 → 命中 = 已发；排除 inflight（在队）/ abandoned（作废）/ pending_pool（待发池）→ 剩余 = 疑似漏发；`--verify` 平台确认 = 真漏发。**在队不算漏发**——在跑篇目先写进 `inflight.json`。

**合规审计（独立一次性任务）**用 `list_all_notes.py`（全量清单+标题复扫），先标题后正文（读正文有风控额度）。

## 四、状态文件

| 文件 | 作用 | 谁维护 |
| --- | --- | --- |
| `state/inflight.json` | 当前队列在发/待发 key | 启动写入；**跑完必须清空** |
| `state/abandoned.json` | `keys` 明确作废永不补发；`files` 不参与复核 | 口径变更/废弃修订稿时追加 |
| `timeliness-window/state/pending_pool.json` | 时效/资格不合格待发池 | 复用 |

## 五、使用

```bash
PY=<red-book-skills>/.venv/Scripts/python.exe
P=~/.workbuddy/skills/red-book-skills-patches/publish-loop-guard
$PY $P/helpers/check_missing.py                 # 一次性复核（默认 2 天）
$PY $P/helpers/check_missing.py --keys k1,k2    # 队列场景只查本批
$PY $P/helpers/check_missing.py --verify        # 平台确认（要 Chrome+<PORT_COMMENT>）
$PY $P/helpers/watch_missing.py --interval 1800 --max-hours 6
$PY $P/helpers/recent_published.py --days 2     # 平台侧轻量速查（只读第一页）
$PY $P/helpers/list_all_notes.py --wording      # 合规审计全量清单
$PY $P/helpers/near_dup_limit.py --title "<标题>" --level 企业级 --topic 大模型与智能体
$PY $P/helpers/near_dup_limit.py --plan round_queue.json      # 整轮队列批量校验
$PY $P/helpers/near_dup_limit.py --record --title "<标题>" --level 企业级 \
    --topic 大模型与智能体 --note-id <note_id>   # 发布后必落标签
$PY $P/helpers/read_note_body.py --snapshot <json> --since 2026-09-10 --wording
```

退出码：`check_missing.py` 0 无漏发 / 1 有漏发 / 2 环境错误；`watch_missing.py` 3 发现漏发 / 4 超时未结束。

## 六、与其他 patch 关系

依赖时序：`timeliness-window` → `publish-preflight-guard` → 本 patch → `publish-interval-guard`。
**风控额度与熔断统一由 `xhs-risk-guard` 提供**，本 patch 不另立规则（helper 均为只读）。

## 七、已知坑

- `inflight.json` 忘清空 → 漏发永远查不出；队列结束先清空再复核。
- 废弃稿留在稿件目录 → 每轮误报；写进 `abandoned.json`。
- `--verify` 有成本（每篇几十秒、占 <PORT_COMMENT>），先默认模式筛再对少量候选 verify。
- 不为"查全"翻页（第 2 页以后既慢又无结论）。
- 配额与复核按**本地时间**自然日 / mtime 算。
- 风控以 `xhs-risk-guard` 为准；`check-login` 命中登录缓存（TTL 12h）会撒谎，先删缓存再验。
- **发布链重试前必须 verify**：输出无 `PUBLISH_STATUS` ≠ 没发出（超时会造成假失败→重发第二条）。
- **页签全局 ≥10 自动回收至 ≤9**（B-057 根治，<PORT_COMMENT>+<PORT_PUBLISH> 合计口径，内建于 `cdp_publish`）；收口用 `core-overrides/helpers/tab_guard.py`（默认双实例）。

## 展开阅读（命中场景才读）

| 场景 | 读哪个文件 |
| --- | --- |
| 查重实现细节、双源事故复盘、漏发复核坑、**防重复发布** | `refs/01-detail.md` |
