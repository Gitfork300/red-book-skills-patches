---
name: publish-loop-guard
system: publish
version: 1.8.1
patch_for: red-book-skills
applies_to_main_version: ">=0.1.0"
priority: 28
author: Eric (定制)
created: 2026-09-11
---

# publish-loop-guard

> Patch：**「启动」触发词 + 长流程漏发复核**。
> 1）用户说「启动」= 自动检索展会/活动并走完整发布流程；2）流程运行期间每 30 分钟复核一次历史文章是否漏发，漏发必须重新过预检再补发。

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
| 7 | 按 8~12 分钟随机间隔逐篇发布（每篇 verify 通过才计间隔） | `publish-interval-guard` |
| 8 | 流程全程挂 30 分钟漏发复核 | 本 patch |
| 9 | 逐篇回报 `note_id`，结束报总表 | — |

**启动时必须做两件事**（否则复核误判）：
1. 把本次队列所有 key 写入 `state/inflight.json`
2. 起后台看门狗 `helpers/watch_missing.py`

**既有要求**（用户 2026-09-10/11 明确）：活动须写明参与方式；标题说清内容、≤20 字；封面真实感照片优先、必带 AI 水印；只陈述事实、来源标注正文末尾；港澳台写「中国香港/中国澳门/中国台湾地区」。

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
- 公共子串 ≥5 字信号；**日期串、数字串、模板动词（开幕/举办/举行…）不作重复证据**（`identity()` 先剥）。
- 稿件同名 = 自己，不算重复；**日志里的同名必须拦**（= 已发过）。→ **预检必须在发布前做**。
- 🔴 **第三道信号：地点 + 日期**（2026-09-16 新增，案例见 `refs/01-detail.md`）。
  前两道**换标题措辞即可绕过**。同城 + 同会期，剥掉**地名/日期/事件后缀/通用词**后
  仍有 ≥2 字公共词 → 判重复。**`[Canary]` 稿豁免本信号**（只查标题逐字；`--series` 仍不豁免）。

### 🚨 查重必须双源

只读一个必漏（两者覆盖面不同）；`dup_check.py` 已双源合并且平台条目 `always=True` 绕时间窗。
**任何批量发布链，预检必须逐条跑 dup_check；缺失即为高危。** 细节见 `refs/01-detail.md`。

### 补发 / 续跑的三条铁律（2026-09-16 重复发布事故）
1. `--from-key X` 只跑 X（续跑须显式 `--continue`）；2. 发布前查 `state/near_dup_tags.json`，同标题即 SKIP；3. `--series` 只放宽「活动名公共子串」，标题完全相同仍判重复（详见 changelog v1.7.12）。

### 近似文章限次（层级 + 主题 双维）

`dup_check` 只拦「同一事件发两遍」，拦不住「**不同事件但看着像重复**」——
两场不同的国家级 AI 大会连着发，读者侧就是重复内容。这条由 `near_dup_limit.py` 管。

**双维标签**（撰稿时**必须显式给定**，脚本不猜——见下方坑）：

| 维度 | 取值 | 判据 |
|---|---|---|
| `level` 层级 | 国家级 / 区域级 / 行业级 / 机构级 / 企业级 | 按**主办方**：部委与国字头全国性组织 / 省市与港澳官方 / 行业协会联盟 / 高校院所 / 企业自办 |
| `topic` 主题 | 大模型与智能体、具身智能与机器人、生物医药AI、芯片与算力、智能驾驶与出行、网络安全、AI教育与人才、数字文娱与内容、其他产业AI、综合 | 按内容主线 |

**限次规则**（用户 2026-09-16 原话：「行业级 7 天内不重复，国家级 24 小时内不重复，专题不设限制」；
脚本顶部常量，改一处即全局生效）：

| 层级 | 窗口 | 窗口内上限 |
|---|---|---|
| 国家级 | 24 小时 | 1 篇（即「不重复」） |
| **行业级** | **7 天** | 1 篇 |
| 区域级 / 机构级 / 企业级 | 24 小时（用户未指定，**暂按国家级口径，待确认**） | 1 篇 |
| **专题系列**（`--series`，如「云栖2026」） | — | **不设限制** |

- 触限判据只看 `level`：窗口内已有同层级 1 篇即 SKIP，换层级或等窗口过去。
- `topic` 仍**必须显式给定**：虽不参与限次判定，但用于落标签与后续复盘
  （哪类主题发多了，与点击率/收藏率对照）。
- 专题系列是**策划意图**不是堆砌，**完全豁免**——v1 的「同层级 24h≤3」会把
  「云栖 10 篇/轮」卡死在 3 篇，已废。

- 触限 → 该篇 **SKIP**，换层级或主题补位，**不硬凑**（与「合格即发、不足不凑」一致）。
- ⚠️ **发布成功后必须 `--record` 落标签**，否则下一轮无据可查。
- 🔴 **坑：不要靠标题自动判层级**。第一版用关键词在标题上猜，拿近 15 天 100 条已发记录实测，
  **94 条被归到「行业级」、56 条「综合」** —— 标题里没有主办方信息，猜不准又默认兜底，
  结果是**每篇稿都触限，闸门等于封死**。→ 只对**已打标**条目计数，历史未打标条目不参与。

## 二、30 分钟漏发复核

批量发布是 1~2 小时长流程，中途可能超时被杀 / 间隔守卫放弃 / verify 不过 / 双队列抢通道。
把判定交给脚本，每 30 分钟无脑跑一次：

| 步 | 动作 |
| --- | --- |
| 1 | 先写 key 进 `state/inflight.json`，再起看门狗（顺序不能反） |
| 2 | 立即跑基线 `check_missing.py`，确认 `OK 无漏发` |
| 3 | 起 `watch_missing.py --interval 1800` |
| 4 | 见 `ALERT_MISSING` → **不是直接重发** |
| 5 | 重新过完整预检（时效 → 资格 → 配额 → 用词/字数 → 封面） |
| 6 | 内容不合规 → 改稿再发 |
| 7 | 时效/资格不合格 → 不补发，登记 `pending_pool.json` |
| 8 | 合规补发仍走 8~12 分钟随机间隔，记录 `note_id` |

**复核范围（只查"这一批有没有漏"，不做全账号体检）**：
- 稿件侧只扫最近 2~3 天（`--days 2`）；
- 平台侧只读 note-manager 第一页（最新 10 条），不翻页、不切标签；
- 状态侧只看「已发布/审核中/未通过」。

**判定链**：稿件标题文件 → 与 `publish_log.json` 精确匹配 → 命中 = 已发；排除 inflight（在队）/ abandoned（作废）/ pending_pool（待发池）→ 剩余 = 疑似漏发；`--verify` 平台确认 = 真漏发。
**关键：在队不算漏发**——队列还在跑的篇目必须先写进 `inflight.json`。

**合规审计（独立一次性任务）**用 `list_all_notes.py`（全量清单+标题复扫），先标题后正文（读正文有风控额度）。

## 三、状态文件

| 文件 | 作用 | 谁维护 |
| --- | --- | --- |
| `state/inflight.json` | 当前队列在发/待发 key | 启动写入；**跑完必须清空** |
| `state/abandoned.json` | `keys` 明确作废永不补发；`files` 不参与复核 | 口径变更/废弃修订稿时追加 |
| `timeliness-window/state/pending_pool.json` | 时效/资格不合格待发池 | 复用 |

## 四、使用

```bash
PY=<red-book-skills>/.venv/Scripts/python.exe
P=~/.workbuddy/skills/red-book-skills-patches/publish-loop-guard
$PY $P/helpers/check_missing.py                 # 一次性复核（默认 2 天）
$PY $P/helpers/check_missing.py --keys k1,k2    # 队列场景只查本批
$PY $P/helpers/check_missing.py --verify        # 平台确认（要 Chrome+9222）
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

## 五、与其他 patch 关系

依赖时序：`timeliness-window` → `publish-preflight-guard` → 本 patch → `publish-interval-guard`。
**风控额度与熔断统一由 `xhs-risk-guard` 提供**，本 patch 不另立规则（helper 均为只读）。

## 六、已知坑

- `inflight.json` 忘清空 → 漏发永远查不出来；队列结束先清空再跑最后复核。
- 废弃稿留在稿件目录 → 每轮误报；写进 `abandoned.json`。
- `--verify` 有成本（每篇几十秒、占 9222），先默认模式筛再对少量候选 verify。
- 不为"查全"翻页（第 2 页以后既慢又无结论）。
- 配额与复核按**本地时间**自然日 / mtime 算。
- 风控以 `xhs-risk-guard` 为准；`check-login` 命中登录缓存（TTL 12h）会撒谎，先删缓存再验。
- **发布链重试前必须 verify**：输出无 `PUBLISH_STATUS` ≠ 没发出（超时会造成假失败→重发第二条）。

## 展开阅读（命中场景才读）

| 场景 | 读哪个文件 |
| --- | --- |
| 查重实现细节、双源事故复盘、漏发复核坑、**防重复发布** | `refs/01-detail.md` |
| 版本修改记录（v1.0.0 ~ v1.7.6） | `refs/02-changelog.md` |
