# 01 · 单篇发布流程（完整版）

> read_when: 实际执行发布、需要各闸门的完整命令与判据时
> 本文件是 `SKILL.md`「单篇发布流程 13 步」的展开。**结论与顺序以 SKILL.md 为准**。
>
> **source: patch** —— 13 步闸门由各 patch 规则合并而成，上游更新一般不影响本文件；
> 但若上游改动了发布流程本身，需重新核对与上游客观流程是否一致。

发布一篇笔记，按顺序过以下闸门。任意一步未通过都不得进入下一步。

## 1. 输入确认

- 标题（**≤20 字宽**——汉字/全角=1、英文/数字/半角=0.5，按 18 字宽留余量；
  旧的「≤38」是错的）、正文（**核心 200–600 字、全篇 <1000 字**——
  核心 = 末个 `—` 分隔行之前的文字）、封面图（本地路径或 URL）三件齐备；缺一不得发布。
- 发布前再次让用户确认最终标题、正文、配图。

## 2. 地域范围 / 时效窗口 / 可发布资格 / 选题配额

patch: `timeliness-window`，活动/展会类必做，**最先做的闸门，按此顺序判**。

- **先判地域**：会展活动**只发江浙沪或珠三角**，其他地区一律排除
  （研究成果/政策类不受限）：
  `helpers/geo_check.py --city <举办城市>`（或 `--text <正文>`），退出码 `0` 才继续。
- 再判时效与资格，一条命令同时判两件事：
  ```bash
  helpers/check_window.py --start <开幕日> [--end <闭幕日>] [--deadline <报名截止>] \
    --live <yes|no|unknown> --public-signup <yes|no|unknown>
  ```
- 退出码 `0` = 可发布 / `1` = 时效不合格 / `3` = 资格不合格；**只有 0 才进入写稿**。
- 时效合格口径：以发布当天为基准 D，窗口 = [D, D+7]
  - 正在举行 / 即将开幕（开幕日 ≤ D+7）/ 报名截止日 ≤ D+7 → 任意满足一条即可
- 时效不合格：太早（开幕日 > D+7 且无近截止的报名）/ 已过期。
- 资格判定：**无线上直播 且 普通观众无法自行报名 → 不发**
  （读者既去不了也看不了，如闭门会、仅限邀约、仅限特定从业者）；
  有直播 → 可发，且**正文必须写明直播信息**（观看平台、直播时间、是否需预约，有回放也注明）；
  直播/报名情况未核实 → 按不可发布处理，先查清再动笔。
- 时效不合格的远期活动、资格不合格的活动**都不要写稿**，
  登记到 `state/pending_pool.json`（资格类须在 `remark` 写明原因），
  日后复查是否新增直播或放开报名。
- **同类第 2 道闸：选题配额**（同 patch）——高频选题限量，
  **恶劣天气类（含台风影响）每自然日至多 1 篇**（含预警 / 热带低压 / 热带扰动 / 暴雨 / 高温 / 大风等）：
  `helpers/quota_check.py --kind weather --level <级别>`，退出码 `0` 才可发；
  **当日为红色或黑色预警时上限放宽至 3 篇**（蓝 / 黄 / 橙 / 未指定仍 1 篇）；
  已满则压到次日或进待发池。配额按发布日志里的**发布时间所在日期**统计。

## 3. 事实核查（patch: `writing-facts-only`）

- 时间、方向、数据、人物已核到具名信源。
- 正文末尾已列出来源与发布时间。
- 报名类如有多个截止口径，取**最早**做窗口判断，正文里如实列出差异。

## 4. 写作风格检查（patch: `writing-facts-only`）

- 不含评论、不含战略建议、不含抒情收尾、不含设问。
- 标题中性，无判断虚词。
- **标题必须说明文章内容**，不得用「流水号 + 日期」式命名。
- **活动/展会类必须写明参与方式**：是否仅限邀约或仅对专业观众、
  是否需登记/审核、截止时间与入场凭证。

## 5. 用词与字数预检（patch: `safe-wording-guard`）

- 跑 `helpers/check_wording.py --title "..." --file <正文>`，退出码必须为 0
  （**来源标注也一起查**）。
- 标题 ≤20 字宽（汉字/全角=1，英文/数字/半角=0.5）、
  **核心正文 200–600 字、全篇 <1000 字**；
  **每次改稿后都要重测字数**（并检查分段：一段一信息点、段 ≤3 行、无文字墙）。

## 6. 配图合规（patch: `cover-image-rules`）

- 允许官方宣传图（含来源标注）/ 裁切到无人物区域 / 文生图。
- **真实感照片风格优先**，不用简单几何抽象的示意图；
  无二维码、无具体人物、无地图、无灾情实拍。
- **封面文件逐张打开核对**：数量对得上、没有被同名覆盖
  （生图文件名前缀相同会互相覆盖）。
- 含 AI 生成图时带「AI 生成」水印，并注明「配图为 AI 生成示意图，非实拍」。

## 7. AI 声明（patch: `cover-image-rules`）

- 配图中只要有一张是 AI 生成，发布时传 `--content-declaration "笔记含AI合成内容"`。
- 全部为官方实拍且正文非 AI 撰写时可省略。

## 8. 间隔闸门（连续发布时 patch: `publish-interval-guard`）

- 先 `publish-interval-guard` 的 `check --json`；
  若 `ready: false`，用 `wait --max-block 900` 阻塞至本次目标间隔满足
  （8~12 分钟随机，由脚本抽签锁定）。

## 9. 发布（Windows 沙箱环境下用 patch: `windows-sandbox-workaround`）

```bash
scripts/cdp_publish.py publish --title "..." --content-file <正文> --images <封面> \
  [--content-declaration ...]
```

必须观察到 `POST /web_api/sns/v2/note` 成功响应；仅「按钮点击」不得报告成功。

## 10. 审核核验

发布后立即 `scripts/cdp_publish.py verify-note --title "..."`，
等待返回 `found: true`（平台 `审核中` / `已发布` 均可接受）。

## 11. 记录间隔起点（patch: `publish-interval-guard`）

`record --note-id <id> --title "..."`，把「已审核的成功发布」落盘，作为下一篇间隔起点。

## 12. 回执

回传 `note_id`、`status`、配图路径、最终标题与正文路径；记录于本次任务输出。

## 13. 流程期间：30 分钟漏发复核（patch: `publish-loop-guard`）

- **流程一旦启动**（批量排队 / 连续发布 / 用户说「启动」），就要挂上看门狗：
  `helpers/watch_missing.py --interval 1800` —— 每 30 分钟复核一次历史文章是否已发。
- 启动时把本次队列所有 key 写入 `publish-loop-guard/state/inflight.json`
  （**在队的不算漏发**）。
- 看门狗报 `ALERT_MISSING` / `check_missing.py` 退出码 1 → **不得直接重发**：
  重新过第 2 步时效/资格/配额、第 5 步用词字数、第 6 步封面；
  稿件不符合现行要求就**改稿**，合规后按 8~12 分钟随机间隔补发；
  时效或资格已不合格的登记 `pending_pool.json`。
- 队列跑完（无论成败）必须**清空 `inflight.json`**，否则漏发复核永久失效。

---

## 附：写作与事实规范（patch: `writing-facts-only` 摘要）

完整规则见 `~/.workbuddy/skills/red-book-skills-patches/writing-facts-only/SKILL.md`。

- **只陈述事实**，不做评论、不提战略建议、不写抒情收尾、不写设问。
- 标题同理：不用「却」「但」「竟」「是否」等判断词。
- 事实核查：时间、方向、数据、人物必须**双源核实**；时效性内容查 7 日内信源。
- **应急事件双重禁令**：不伪造实拍，不生成「灾情实拍」画面。
- **地图合规**：不画任何 AI 手绘的国界/海岸线/行政区划。
- **活动稿末尾必须有打星评级块**（发布链硬闸门：缺行或写成 `★… 综合` 即拒发）：
  首行 **`综合 ★…`**（**汉字在前、星级在后**），下接 `参与难度` / `适合人群` /
  `专业性` / `活动规模` 四维（**括号只写事实，不写评价**）+ `来源：`。
  **适合人群不打星**用标签。活动类**一律要有**，不因篇幅紧而省。
- 来源标注：正文末尾列出信源 + 发布时间。

## 附：封面配图规范（patch: `cover-image-rules` 摘要）

完整规则见 `~/.workbuddy/skills/red-book-skills-patches/cover-image-rules/SKILL.md`。

- **允许使用官方宣传图**（主办方/组委会/官方媒体发布的宣传图、通稿配图、现场图、场馆图）
  —— 来源不明、疑似自媒体二改的不用。
- **禁止具体人物**（硬性）：嘉宾/演讲者/主持/受访者/观众特写一律禁；
  **宣传大使/形象大使/代言人同样禁**（不得以「官方身份」开例）。
- 构图优先级：城市地标/建筑外景 → 风景与天际线 → 场馆展区环境 → 器物装置特写 → 抽象信息图。
- 官方图含人物时的处理：换图 → 裁切（保留地标/风景主体）→ 改生成为地标风景示意图。
- AI 生成图必须显式禁止：地图/海岸线/国界/行政区划/文字/数字/真实人物/旗帜。
- AI 声明：含 AI 生成图 → `--content-declaration "笔记含AI合成内容"`；
  全为官方实拍且正文非 AI 撰写时可省略。

## 附：间隔与审核闸门（patch: `publish-interval-guard` 摘要）

完整规则见 `~/.workbuddy/skills/red-book-skills-patches/publish-interval-guard/SKILL.md`。

- 连续两篇笔记间隔 **8~12 分钟随机**（`[480, 720]` 秒），下限 8 分钟；
  每篇 `record` 时抽签写入 `next_gap`，**多次 `check` 不会重新抽签**。
- 起点 = `cdp_publish.py publish` 成功 **且** `verify-note --title` 返回 `found: true` 的时刻。
- 状态文件位于 patch 自己的 `state/publish_log.json`（自包含，不污染主 skill）。
- 与 `windows-sandbox-workaround` 集成：通过环境变量 `XHS_INTERVAL_GUARD` 指向 helper。

```bash
<patch>/helpers/publish_interval.py check --json    # ready=true 才可发
<patch>/helpers/publish_interval.py wait --max-block 900   # 阻塞到可发
<patch>/helpers/publish_interval.py record --note-id <id> --title "标题"
<patch>/helpers/publish_interval.py last
```

**`publish_pipeline.py` 会自动 record**（2026-09-07 起）：发布成功后自动把 `note_id`
写入间隔日志，无需手动 `record`。

- 查找 guard 顺序：环境变量 `XHS_PUBLISH_INTERVAL_HELPER` → 同级
  `red-book-skills-patches/` → `~/.workbuddy/skills/red-book-skills-patches/`。
- 记录失败**不影响**本次发布结果（只告警，不改退出码）——发布已经成功了。
- 不需要时加 `--no-record` 跳过。
- ⚠️ 自动 record 发生在**平台返回 note_id 时**，不等 `verify-note`。
  若要求严格按「审核通过才算起点」，应自行跑 `verify-note` 后再手动 `record`。
