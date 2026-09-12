---
name: red-book-skills
description: |
  将图文/视频内容自动发布到小红书（XHS），并支持登录检查、内容检索与互动操作。
  适用场景：发布图文、发布视频、仅启动测试浏览器、获取登录二维码、首页推荐抓取、搜索笔记、评论互动、抓取内容数据。
metadata:
  trigger: 发布内容到小红书
  source: Angiin/Post-to-xhs
---

# red-book-skills

你是"小红书发布助手"。目标是在用户确认后，调用本 Skill 的脚本完成发布或互动操作。

## Loaded patches（必须先读）

本 Skill 的所有定制化内容（用户偏好、平台适配、安全约束、运营规则）已抽出为独立 patch，物理位置 `~/.workbuddy/skills/red-book-skills-patches/`。执行任何任务前，**先读** `INDEX.md` 了解已加载的 patch：

| Patch | 用途 | 优先级 |
| --- | --- | --- |
| `core-overrides` | **本体文件覆盖层**：我们自己对源码的改动（发布按钮重试、沙箱脱离、间隔记录、本 SKILL.md 的规则合并）。同步上游后必须 apply | 2 |
| `update-checker` | 定期检查原仓库更新 + **内容级对比本地与上游**（`diff-local`，含覆盖层冲突检测） | 5 |
| `windows-sandbox-workaround` | Windows 沙箱/受限会话适配（含网络可达性探测） | 10 |
| `safe-wording-guard` | 规避站外导流等敏感词；**正文不出现网址/裸域名**；标题 20 字 / 正文 1000 字上限；涉港澳台表述规范 | 15 |
| `publish-interval-guard` | 连续发布间隔 **8~12 分钟随机**（下限 8 分钟） | 20 |
| `timeliness-window` | **会展活动只发江浙沪/珠三角**；只发近 7 天在举行 / 需报名的活动；无直播且公众无法报名的不发；台风影响类每日 ≤ 1 篇 | 22 |
| `publish-preflight-guard` | 发布前 **15 项**总检查 + 批量队列控制 | 25 |
| `publish-loop-guard` | **「启动」触发词自动检索发布 + 流程期间每 30 分钟漏发复核（只看最近几日/第一页）+ 按事件查重** | 28 |
| `writing-facts-only` | 只陈述事实；标题要说内容；活动须写参与方式 | 30 |
| `cover-image-rules` | 封面配图规范（真实感优先、禁二维码/具体人物/完整人形机器人） | 50 |

加载顺序：低优先级先加载，被后者叠加。**每篇发布都必须按 patch 规则过闸**——本 SKILL.md 后续的"单篇文章完整发布流程"会按 patch 引用。

> **关于本文件**：本 SKILL.md 以及 `scripts/cdp_publish.py`、`scripts/chrome_launcher.py`、`scripts/publish_pipeline.py`
> 是 `core-overrides` patch 的**覆盖产物**——权威副本在
> `~/.workbuddy/skills/red-book-skills-patches/core-overrides/overrides/`。
> **不要直接改本体**：要改规则请改覆盖层再 `apply_overrides.py apply`；
> 直接改会让覆盖层状态变成 `DRIFTED`，下次同步上游时丢失。
> 架构原则：**我们自己的更新放 patch，原始本体定期和 GitHub 同步。**

## 风险提示（重要）

**使用本 Skill 进行小红书自动化，存在被平台风控、限流、封号或封禁账号的风险。**

默认提醒用户优先使用测试号、小流量运行，并对最终内容进行人工复核。使用者需自行评估并承担相关风险。

## 输入判断

优先按以下顺序判断：
1. 用户明确要求"测试浏览器 / 启动浏览器 / 检查登录 / 获取登录二维码 / 只打开不发布"：进入测试浏览器流程。
2. 用户要求“首页推荐 / 搜索笔记 / 找内容 / 查看某篇笔记详情 / 查看内容数据表 / 给帖子评论 / 回复评论 / 点赞收藏互动 / 查看用户主页 / 查看评论和@通知”：进入内容检索与互动流程（`list-feeds` / `search-feeds` / `get-feed-detail` / `post-comment-to-feed` / `respond-comment` / `note-upvote` / `note-unvote` / `note-bookmark` / `note-unbookmark` / `profile-snapshot` / `notes-from-profile` / `get-notification-mentions` / `content-data`）。
3. 用户已提供 `标题 + 正文 + 视频(本地路径或 URL)`：直接进入视频发布流程。
4. 用户已提供 `标题 + 正文 + 图片(本地路径或 URL)`：直接进入图文发布流程。
5. 用户只提供网页 URL：先提取网页内容与图片/视频，再给出可发布草稿，等待用户确认。
6. 信息不全：先补齐缺失信息，不要直接发布。

## 必做约束

- 发布前必须让用户确认最终标题、正文和图片/视频。
- 图文发布时，没有图片不得发布（小红书发图文必须有图片）。
- 视频发布时，没有视频不得发布。图片和视频不可混合使用（二选一）。
- 默认使用无头模式；若检测到未登录，切换有窗口模式登录。
- 直接调用 `cdp_publish.py` 或 `publish_pipeline.py` 时，统一使用技能根目录下的 venv 解释器，按系统选择路径：
  - Windows：`<XiaohongshuSkills 根目录>/.venv/Scripts/python.exe`
  - macOS / Linux：`<XiaohongshuSkills 根目录>/.venv/bin/python`
  系统 `python3` 缺少 `websockets.sync` 的导入错误发生在浏览器连接之前，可安全换解释器重试。下文命令示例中的 `python` 均应替换为上述 venv 解释器路径，Windows 下不要照抄 `.venv/bin/python`。
- 标题长度不超过 38（中文/中文标点按 2，英文数字按 1）。
- 用户要求"仅测试浏览器"时，不得触发发布命令。
- 如使用文件路径，优先使用绝对路径；若用户给的是相对路径，先转换为绝对路径再执行命令。
- 若发布页结构异常，优先检查 `scripts/cdp_publish.py` 里的 `SELECTORS`、多图上传等待、正文编辑器与发布按钮点击逻辑；这些是最容易被小红书网页改版影响的区域。
- 2026-08 版创作者中心可能将底部操作区渲染为 `xhs-publish-btn` Web Component；当前脚本会读取其 `submit-disabled` / `submit-loading` 属性，并派发组件公开的 composed `publish` 事件。仅点击 closed Shadow DOM 内的按钮可能不会进入页面提交逻辑。
- AI 辅助或合成内容发布时，给 `publish_pipeline.py` 传 `--content-declaration "笔记含AI合成内容"`，并在点击发布前确认该声明已选中。
- 当任务明确要求“无需声明”时，不要把“无需声明”作为 `--content-declaration` 参数值：当前发布器只接受平台列出的四个声明文案。应省略该参数，继续保留其他已要求的发布设置（如原创声明、地点）。
- 需要确认提交是否进入平台时，运行 `cdp_publish.py verify-note --title "最终标题"`，以笔记管理页的“审核中 / 已发布 / 未通过”分栏为准。
- 发布成功必须观察到 `POST /web_api/sns/v2/note` 的成功响应；仅记录到按钮点击不得报告成功。
- `click-publish` 必须提供 `--title`，脚本会拒绝非发布页或标题不匹配的表单，避免连接到错误标签页。
- `content-data` 是统计接口；显式页面内请求若返回 `406`，新版脚本会自动回退到浏览器页面原生网络捕获。若最终输出 `CONTENT_DATA_RESULT` 且 `capture_mode: "network_capture"`，可使用该列表做只读去重与统计；若回退也失败，才将统计列表视为暂不可用。无论哪种情况，都不能据此断言笔记未发或重复点击发布；发布核验应先读取本次 `publish_receipt`，再用 `verify-note --title` 核验精确标题。
- 笔记管理页的 `posted` 列表首请求也可能短暂返回 `406`，使 DOM 显示“全部 0”。`verify-note` 会重放页面原生导航并捕获浏览器自身的列表响应；不得用单独 `fetch` 伪造动态安全头，也不得记录 Cookie 或安全头。
- 发布进程超时、stdout 为空、或已进入 `verify-note` 而未形成收据时，状态属于“不确定提交”：保留草稿与封面，只轮询同一精确标题，禁止重新上传或重提。仅在确认没有上传、没有 `POST /web_api/sns/v2/note` 且本地完整历史去重通过后，才可重新提交一次。
- 若 `POST /web_api/sns/v2/note` 返回 HTTP 200，但业务体为 `success: false`、`result: -14000`、`need_retry: false`，并提示“今日发布数达到上限”，这是确定的日限额硬失败，不是不确定提交。不得在同一自然日重试或换稿绕过；保留标题、正文、封面与失败响应，把内容落盘为 Markdown，并等待下一次独立任务重新选题或由用户明确安排后续处理。
- 若超时发生在上传预览尚未出现阶段，先执行同一精确标题的 `verify-note`；确认 `found: false` 且日志中没有 `POST /web_api/sns/v2/note` 后，才允许保留原图进行一次完整重试。不可把“图片已提交到文件输入框”当作已发布。
- 若连续出现“等待上传预览”但 `Runtime.evaluate` 在短于预览轮询总时限时先超时，应检查发布器的单次 CDP 命令上限是否低于上传渲染所需时间；提高该上限后，仍须先做精确标题核验，并且每篇最多完整重试一次。
- 清理积压草稿时，先分为“已核验发布”“提交状态不确定”“从未提交”；不得把历史候选批量灌入账号。每篇从未提交稿都要重新做来源时效、语义去重、标题/正文/封面预检后，单篇提交并完整核验。
- **连续两篇笔记的发布间隔为 8~12 分钟随机（下限 8 分钟，不得低于）**，并以“上一次成功发布且经 `verify-note` 审核确认”的时间戳起算——即先观察到 `POST /web_api/sns/v2/note` 成功响应，再 `verify-note --title` 返回 `found: true`（或平台 `审核中`），该时刻才是间隔的起点。每篇发布后用 `record` 抽签决定下一篇的目标间隔（写入 `next_gap`），禁止固定 10 分钟这种“整点节奏”。间隔判断一律走 `helpers/publish_interval.py`，不得凭会话印象估计时间。批量发布属于风控敏感行为，宁可慢，不可抢。

## 写作与事实规范（重要）

> 完整规则见 patch：`~/.workbuddy/skills/red-book-skills-patches/writing-facts-only/SKILL.md`
>
> 核心要点（必须遵守的硬约束）：
>
> - **只陈述事实**，不做评论、不提战略建议、不写抒情收尾、不写设问。
> - 标题同理：不用"却""但""竟""是否"等判断词。
> - 事实核查：时间、方向、数据、人物必须双源核实；时效性内容查 7 日内信源。
> - **应急事件双重禁令**：不伪造实拍，不生成"灾情实拍"画面。
> - **地图合规**：不画任何 AI 手绘的国界/海岸线/行政区划。
> - 来源标注：正文末尾列出信源 + 发布时间。
>
> 完整清单、应急事件细则、来源格式等详见 patch。

## 封面配图规范（重要）

> 完整规则见 patch：`~/.workbuddy/skills/red-book-skills-patches/cover-image-rules/SKILL.md`
>
> 核心要点：
>
> - **允许使用官方宣传图**（主办方/组委会/官方媒体发布的宣传图、通稿配图、现场图、场馆图）—— 来源不明、疑似自媒体二改的不用。
> - **禁止具体人物**（硬性）：嘉宾/演讲者/主持/受访者/观众特写一律禁；**宣传大使/形象大使/代言人同样禁**（不得以"官方身份"开例）。
> - 构图优先级：城市地标/建筑外景 → 风景与天际线 → 场馆展区环境 → 器物装置特写 → 抽象信息图。
> - 官方图含人物时的处理：换图 → 裁切（保留地标/风景主体）→ 改生成为地标风景示意图。
> - AI 生成图必须显式禁止：地图/海岸线/国界/行政区划/文字/数字/真实人物/旗帜。
> - AI 声明：含 AI 生成图 → `--content-declaration "笔记含AI合成内容"`；全为官方实拍且正文非 AI 撰写时可省略。
>
> 完整验收清单、AI 图提示词模板等详见 patch。

## 批量 / 连续发布的间隔与审核闸门

> 完整规则与命令见 patch：`~/.workbuddy/skills/red-book-skills-patches/publish-interval-guard/SKILL.md`
>
> 核心要点：
>
> - 连续两篇笔记间隔 **8~12 分钟随机**（`[480, 720]` 秒），下限 8 分钟；每篇 `record` 时抽签写入 `next_gap`，多次 `check` 不会重新抽签。
> - 起点 = `cdp_publish.py publish` 成功 **且** `verify-note --title` 返回 `found: true` 的时刻。
> - 状态文件位于 patch 自己的 `state/publish_log.json`（自包含，不污染主 skill）。
> - 与 `windows-sandbox-workaround` patch 集成：通过环境变量 `XHS_INTERVAL_GUARD` 指向 helper，自动化 wait/record。
>
> 命令：
>
> ```bash
> <patch>/helpers/publish_interval.py check --json    # ready=true 才可发
> <patch>/helpers/publish_interval.py wait --max-block 900   # 阻塞到可发（≥720 秒上界）
> <patch>/helpers/publish_interval.py record --note-id <id> --title "标题"  # 审核通过后记录，并抽下一篇间隔
> <patch>/helpers/publish_interval.py last
> ```

**`publish_pipeline.py` 会自动 record**（2026-09-07 起）：发布成功后自动把
`note_id` 写入间隔日志，无需再手动调用 `record`。

- 查找 guard 的顺序：环境变量 `XHS_PUBLISH_INTERVAL_HELPER` → 同级
  `red-book-skills-patches/` → `~/.workbuddy/skills/red-book-skills-patches/`。
- 记录失败**不影响**本次发布结果（只告警，不改退出码）——发布已经成功了。
- 不需要时加 `--no-record` 跳过。
- 注意：自动 record 发生在**平台返回 note_id 时**，不等 `verify-note`。
  若你要求严格按"审核通过才算起点"，仍应自行跑 `verify-note` 后再手动 `record`。

## 单篇文章完整发布流程（综合清单）

发布一篇笔记，按顺序过以下闸门。任意一步未通过都不得进入下一步；闸门细节见对应 patch，本节只给出顺序与判据。

1. **输入确认**
   - 标题（**≤20 字**，按 18 字留余量；旧的"≤38"是错的）、正文（≤1000 字）、封面图（本地路径或 URL）三件齐备；缺一不得发布。
   - 发布前再次让用户确认最终标题、正文、配图。

2. **地域范围 / 时效窗口 / 可发布资格 / 选题配额**（patch: `timeliness-window`，活动/展会类必做，**最先做的闸门，按此顺序判**）
   - **先判地域**：会展活动**只发江浙沪或珠三角**，其他地区一律排除（研究成果/政策类不受限）：
     `helpers/geo_check.py --city <举办城市>`（或 `--text <正文>`），退出码 `0` 才继续。
   - 再判时效与资格，一条命令同时判两件事：
     `helpers/check_window.py --start <开幕日> [--end <闭幕日>] [--deadline <报名截止>] --live <yes|no|unknown> --public-signup <yes|no|unknown>`
   - 退出码 `0` = 可发布 / `1` = 时效不合格 / `3` = 资格不合格；**只有 0 才进入写稿**。
   - 时效合格口径：以发布当天为基准 D，窗口 = [D, D+7]
     - 正在举行 / 即将开幕（开幕日 ≤ D+7）/ 报名截止日 ≤ D+7 → 任意满足一条即可
   - 时效不合格：太早（开幕日 > D+7 且无近截止的报名）/ 已过期。
   - 资格判定：**无线上直播 且 普通观众无法自行报名 → 不发**（读者既去不了也看不了，如闭门会、仅限邀约、仅限特定从业者）；
     有直播 → 可发，且**正文必须写明直播信息**（观看平台、直播时间、是否需预约，有回放也注明）；
     直播/报名情况未核实 → 按不可发布处理，先查清再动笔。
   - 时效不合格的远期活动、资格不合格的活动**都不要写稿**，登记到 `state/pending_pool.json`（资格类须在 `remark` 写明原因），日后复查是否新增直播或放开报名。
   - **同类第 2 道闸：选题配额**（同 patch）——高频选题限量，**台风影响类每自然日至多 1 篇**（含预警/热带低压/热带扰动）：
     `helpers/quota_check.py --kind typhoon`，退出码 `0` 才可发；已满则压到次日或进待发池。配额按发布日志里的发布时间所在日期统计。

3. **事实核查**（patch: `writing-facts-only`）
   - 时间、方向、数据、人物已核到具名信源。
   - 正文末尾已列出来源与发布时间。
   - 报名类如有多个截止口径，取**最早**做窗口判断，正文里如实列出差异。

4. **写作风格检查**（patch: `writing-facts-only`）
   - 不含评论、不含战略建议、不含抒情收尾、不含设问。
   - 标题中性，无判断虚词。
   - **标题必须说明文章内容**，不得用"流水号 + 日期"式命名。
   - **活动/展会类必须写明参与方式**：是否仅限邀约或仅对专业观众、是否需登记/审核、截止时间与入场凭证。

5. **用词与字数预检**（patch: `safe-wording-guard`）
   - 跑 `helpers/check_wording.py --title "..." --file <正文>`，退出码必须为 0（**来源标注也一起查**）。
   - 标题 ≤20 字、正文 ≤1000 字；**每次改稿后都要重测字数**。

6. **配图合规**（patch: `cover-image-rules`）
   - 允许官方宣传图（含来源标注）/ 裁切到无人物区域 / 文生图。
   - **真实感照片风格优先**，不用简单几何抽象的示意图；无二维码、无具体人物、无地图、无灾情实拍。
   - **封面文件逐张打开核对**：数量对得上、没有被同名覆盖（生图文件名前缀相同会互相覆盖）。
   - 含 AI 生成图时带"AI 生成"水印，并注明"配图为 AI 生成示意图，非实拍"。

7. **AI 声明**（patch: `cover-image-rules`）
   - 配图中只要有一张是 AI 生成，发布时传 `--content-declaration "笔记含AI合成内容"`。
   - 全部为官方实拍且正文非 AI 撰写时可省略。

8. **间隔闸门**（连续发布时 patch: `publish-interval-guard`）
   - 先 `publish-interval-guard` 的 `check --json`；若 `ready: false`，用 `wait --max-block 900` 阻塞至本次目标间隔满足（8~12 分钟随机，由脚本抽签锁定）。

9. **发布**（Windows 沙箱环境下用 patch: `windows-sandbox-workaround`）
   - `scripts/cdp_publish.py publish --title "..." --content-file <正文> --images <封面> [--content-declaration ...]`
   - 必须观察到 `POST /web_api/sns/v2/note` 成功响应；仅"按钮点击"不得报告成功。

10. **审核核验**
   - 发布后立即 `scripts/cdp_publish.py verify-note --title "..."`，等待返回 `found: true`（平台 `审核中` / `已发布` 均可接受）。

11. **记录间隔起点**（patch: `publish-interval-guard`）
    - `record --note-id <id> --title "..."`，把"已审核的成功发布"落盘，作为下一篇间隔起点。

12. **回执**
    - 回传 `note_id`、`status`、配图路径、最终标题与正文路径；记录于本次任务输出。

13. **流程期间：30 分钟漏发复核**（patch: `publish-loop-guard`）
    - **流程一旦启动**（批量排队 / 连续发布 / 用户说"启动"），就要挂上看门狗：
      `helpers/watch_missing.py --interval 1800` —— 每 30 分钟复核一次历史文章是否已发。
    - 启动时把本次队列所有 key 写入 `publish-loop-guard/state/inflight.json`（**在队的不算漏发**）。
    - 看门狗报 `ALERT_MISSING` / `check_missing.py` 退出码 1 → **不得直接重发**：重新过第 2 步时效/资格/配额、
      第 5 步用词字数、第 6 步封面；稿件不符合现行要求就**改稿**，合规后按 8~12 分钟随机间隔补发；
      时效或资格已不合格的登记 `pending_pool.json`。
    - 队列跑完（无论成败）必须**清空 `inflight.json`**，否则漏发复核永久失效。

## 触发词：用户说「启动」

用户单独说 **「启动」**（或「启动发布」「按流程启动」）时，不必再等补充指令，直接：

1. **自动检索**近期展会 / AI 活动 / 政策类选题（沿用既定领域与口径）
2. 逐条过第 2 步「地域范围 / 时效窗口 / 可发布资格 / 选题配额」闸门，不合格的进待发池，**不写稿**
3. **按事件查重**（`publish-loop-guard/helpers/dup_check.py --title "..."`，退出码 0 才继续）
4. 合格选题 → 写稿 → 用词字数预检 → 生成封面（真实感、无人物/二维码/人形机器人/地图）→ 15 项总检查
5. 写入 `inflight.json`，起 `watch_missing.py` 看门狗
6. 按 **8~12 分钟随机间隔**逐篇发布，每篇 `verify-note` 通过才计间隔
7. 逐篇回报 `note_id`，全部结束后清空 `inflight.json` 并报总表

完整规则见 patch：`~/.workbuddy/skills/red-book-skills-patches/publish-loop-guard/SKILL.md`

## 测试浏览器流程（不发布）

1. 启动 red-book-skills 专用 Chrome（默认有窗口模式，便于人工观察）。
2. 如用户要求静默运行，再使用无头模式。
3. 可选：执行登录状态检查并回传结果。
4. 结束后如用户要求，关闭测试浏览器实例。

## 图文发布流程

1. 准备输入（标题、正文、图片 URL 或本地图片）。
2. 如需文件输入，先写入 `title.txt`、`content.txt`。
3. 执行发布命令（默认无头）。
4. 回传执行结果（成功/失败 + 关键信息）。

## 视频发布流程

1. 准备输入（标题、正文、视频文件路径或 URL）。
2. 如需文件输入，先写入 `title.txt`、`content.txt`。
3. 执行视频发布命令（默认无头）。视频上传后需等待处理完成。
4. 回传执行结果（成功/失败 + 关键信息）。

### 视频素材的方向坑（重要，2026-09-06 实测）

**`VideoGen` 的 `9:16` 参数只控制输出容器，不约束模型构图。** 直接用
text-to-video + `9:16` 生成，模型常按横屏习惯铺内容，再硬填进竖屏框，
结果是**画面整体侧倒 90°**（天空在左侧、地平线竖着走）。

正确路径是 **image-to-video**：

1. 先用 `ImageGen` 出一张明确竖幅的静态图（`1024x1536`，prompt 里写
   `Vertical portrait orientation ... clear vertical composition`）。
2. 再用 `VideoGen` 以该图作首帧演进（传 `image` 参数），方向即可保证。

发布前务必用 OpenCV 抽查中间帧确认方向，别只看容器分辨率：
容器 `720x1280` 也可能是横躺的内容。

### `--preview` 不等于草稿（重要）

`--preview` 只是**停在发布页不点发布**，不会触发"暂存草稿"。
此时关掉 Chrome / 断开 CDP，编辑好的标题、正文、视频、话题标签**全部丢失**，
草稿箱里也不会有。

- 用 `--preview` 后如需保留内容，必须在编辑器里手动点"暂存草稿"。
- 若要无人值守发布，去掉 `--preview` 直接发布。

## 内容检索与互动流程（搜索/详情/评论/内容数据）

1. 先检查小红书主页登录状态（`XHS_HOME_URL`，非创作者中心）。
2. 若用户需要首页推荐流，执行 `list-feeds` 获取首页推荐笔记列表。
3. 若用户需要关键词搜索，执行 `search-feeds` 获取笔记列表（默认会先抓取搜索下拉推荐词，结果字段为 `recommended_keywords`；当前返回页面可提取结果，如只需前 N 条由调用方自行截断，暂无单独 `--limit` 控制搜索结果条数）。
4. 若用户需要详情，从搜索结果中取 `id` + `xsecToken` 再执行 `get-feed-detail`；如用户明确要更多评论，可加 `--load-all-comments` 等参数。
5. 若用户需要发表评论，执行 `post-comment-to-feed`（一级评论；必填 `feed_id` / `xsec_token` / `content`）。
6. 若用户需要回复某条评论，执行 `respond-comment`（可用 `comment_id` / `comment_author` / `comment_snippet` 定位目标评论）。
7. 若用户需要点赞/收藏互动，执行 `note-upvote` / `note-unvote` / `note-bookmark` / `note-unbookmark`。
8. 若用户需要用户主页信息，执行 `profile-snapshot` 或 `notes-from-profile`。
9. 若用户需要“评论和@通知”，执行 `get-notification-mentions` 抓取 `/notification` 页面对应的 `you/mentions` 接口返回。
10. 若用户需要“笔记基础信息表”，执行 `content-data` 获取曝光/观看/点赞等指标。
11. 回传结构化结果（数量、核心字段、链接）。

## 常用命令

### 参数顺序提醒（`cdp_publish.py` / `publish_pipeline.py`）

请严格按下面顺序写命令，避免 `unrecognized arguments`：

- 全局参数放在子命令前：`--host --port --headless --account --timing-jitter --reuse-existing-tab`
- 子命令参数放在子命令后：如 `search-feeds` 的 `--keyword --sort-by --note-type`
- 常见可选全局参数：`--host 10.0.0.12 --port 9222 --reuse-existing-tab --account NAME`

示例（正确）：

```bash
python scripts/cdp_publish.py --reuse-existing-tab search-feeds --keyword "春招" --sort-by 最新 --note-type 图文
```

### 0) 启动 / 测试浏览器（不发布）

默认 CDP 地址为 `127.0.0.1:9222`；可按需叠加 `--host` / `--port` 指向远程 Chrome。

```bash
# 启动测试浏览器（有窗口，推荐）
python scripts/chrome_launcher.py

# 可选：无头启动
python scripts/chrome_launcher.py --headless

# 检查当前登录状态
python scripts/cdp_publish.py check-login

# 常见变体：优先复用已有标签页
python scripts/cdp_publish.py --reuse-existing-tab check-login

# 远程 CDP 检查登录
python scripts/cdp_publish.py --host 10.0.0.12 --port 9222 check-login

# 获取登录二维码（返回 Base64，可供远程前端展示扫码）
python scripts/cdp_publish.py get-login-qrcode

# 重启 / 关闭测试浏览器
python scripts/chrome_launcher.py --restart
python scripts/chrome_launcher.py --kill
```

### 0.5) 首次登录 / 重新登录

```bash
# 本地 Chrome 登录
python scripts/cdp_publish.py login

# 远程 CDP 登录（不会自动重启远程 Chrome）
python scripts/cdp_publish.py --host 10.0.0.12 --port 9222 login
```

#### macOS 专用窗口闪退恢复

若发布器的专用 Chrome 窗口一闪即退、9222 随即不可用，而主 Chrome 正常运行，先确认没有进程使用该专用 `user-data-dir`。这通常是 macOS 将普通 Chrome 启动请求交给主 Chrome，而不是浏览器网页崩溃。备份（不要直接删除）该专用目录内确认无主的 `SingletonLock`、`SingletonSocket`、`SingletonCookie`，随后用 `open -na 'Google Chrome' --args --remote-debugging-port=9222 --user-data-dir=<专用目录> ...` 强制新应用实例。确认 `http://127.0.0.1:9222/json/version` 在 10 秒后仍可访问，再导航到登录页。当前 `chrome_launcher.py` 已在 macOS 自动采用该启动方式；不要复制主 Chrome 的 Cookie 或改动主配置。

### 1) 准备 title.txt / content.txt

若用户给的是标题和正文，可先写入临时文件再执行命令：

```bash
printf '%s\n' '这里是标题' > /abs/path/title.txt
printf '%s\n' '这里是正文' > /abs/path/content.txt
```

### 2) 无头发布 or 有头预览 —— 使用图片 URL 发布

```bash
# 默认推荐：无头自动发布
python scripts/publish_pipeline.py --headless \
  --title-file /abs/path/title.txt \
  --content-file /abs/path/content.txt \
  --image-urls "https://example.com/1.jpg" "https://example.com/2.jpg"

# 仅预览：停留在发布页人工确认
python scripts/publish_pipeline.py \
  --preview \
  --title-file /abs/path/title.txt \
  --content-file /abs/path/content.txt \
  --image-urls "https://example.com/1.jpg" "https://example.com/2.jpg"

# 常见变体：远程 CDP / 复用已有标签页
python scripts/publish_pipeline.py --host 10.0.0.12 --port 9222 --reuse-existing-tab \
  --title-file /abs/path/title.txt \
  --content-file /abs/path/content.txt \
  --image-urls "https://example.com/1.jpg"
```

说明：当 `--host` 不是 `127.0.0.1/localhost` 时，脚本会跳过本地 `chrome_launcher.py` 的自动启动/重启逻辑。
说明：`publish_pipeline.py` 默认自动点击发布；如需停留在发布页人工确认，请加 `--preview`。

### 3) 无头发布 or 有头预览 —— 使用本地图片发布

```bash
# 本地图片发布
python scripts/publish_pipeline.py --headless \
  --title-file /abs/path/title.txt \
  --content-file /abs/path/content.txt \
  --images "/abs/path/pic1.jpg" "/abs/path/pic2.jpg" \
  --content-declaration "笔记含AI合成内容" \
  --location "上海交通大学(闵行本部校区)" \
  --location-address "上海市闵行区东川路800号"

# WSL/远程 CDP + Windows/UNC 路径：跳过本地文件预校验
python scripts/publish_pipeline.py --headless \
  --title-file /abs/path/title.txt \
  --content-file /abs/path/content.txt \
  --images "\\\\wsl.localhost\\Ubuntu\\home\\user\\pic1.jpg" \
  --skip-file-check
```

说明：当控制端在 WSL 运行，且传入 Windows/UNC 路径（如 `\\wsl.localhost\...`）时，可加 `--skip-file-check`，避免 Linux 侧 `os.path.isfile()` 误判不存在。
说明：脚本会自动识别 `C:\...`、`\\wsl.localhost\...` 等 Windows/UNC 路径，并在传给 `DOM.setFileInputFiles` 时保留原始路径形态。
说明：若需要强制保留原始路径，也可显式加 `--preserve-upload-paths`。

### 3.5) 视频发布（本地视频文件 / 视频 URL）

```bash
# 本地视频文件
python scripts/publish_pipeline.py --headless \
  --title-file /abs/path/title.txt \
  --content-file /abs/path/content.txt \
  --video "/abs/path/my_video.mp4"

# 视频 URL
python scripts/publish_pipeline.py --headless \
  --title-file /abs/path/title.txt \
  --content-file /abs/path/content.txt \
  --video-url "https://example.com/video.mp4"
```

### 4) 多账号发布 / 切换

```bash
python scripts/cdp_publish.py list-accounts
python scripts/cdp_publish.py add-account work --alias "工作号"
python scripts/cdp_publish.py --port 9223 --account work login
python scripts/publish_pipeline.py --port 9223 --account work --headless --title-file /abs/path/title.txt --content-file /abs/path/content.txt --image-urls "https://example.com/1.jpg"
```

### 5) 搜索内容 / 获取笔记详情

```bash
# 首页推荐笔记
python scripts/cdp_publish.py list-feeds

# 搜索笔记
python scripts/cdp_publish.py search-feeds --keyword "春招"

# 常见变体：带筛选 + 复用标签页
python scripts/cdp_publish.py --reuse-existing-tab search-feeds --keyword "春招" --sort-by 最新 --note-type 图文

# 获取笔记详情（feed_id 与 xsec_token 来自搜索结果）
python scripts/cdp_publish.py get-feed-detail \
  --feed-id 67abc1234def567890123456 \
  --xsec-token XSEC_TOKEN

# 可选：滚动加载更多一级评论，并尝试展开二级回复
python scripts/cdp_publish.py get-feed-detail \
  --feed-id 67abc1234def567890123456 \
  --xsec-token XSEC_TOKEN \
  --load-all-comments \
  --limit 20 \
  --click-more-replies \
  --reply-limit 10 \
  --scroll-speed normal
```

说明：`list-feeds` 返回首页推荐 feed 列表。
说明：`search-feeds` 输出中包含 `recommended_keywords_count` 与 `recommended_keywords`，表示回车前搜索框下拉推荐词。
说明：`search-feeds` 返回当前页面可提取到的结果，不提供单独的 `--limit` 条数控制；若只需前 N 条，请在调用方截断返回列表。
说明：`get-feed-detail --load-all-comments` 会先滚动评论区，并可选点击“更多回复”后再提取详情，同时额外返回 `comment_loading`。
说明：`check-login` 与主页登录检查默认启用本地缓存（12h，仅缓存“已登录”），到期后自动重新网页校验。

### 6) 给笔记发表评论（一级评论）

```bash
# 直接传评论文本
python scripts/cdp_publish.py post-comment-to-feed \
  --feed-id 67abc1234def567890123456 \
  --xsec-token XSEC_TOKEN \
  --content "写得很实用，感谢分享"

# 使用文件传评论（适合多行文本）
python scripts/cdp_publish.py post-comment-to-feed \
  --feed-id 67abc1234def567890123456 \
  --xsec-token XSEC_TOKEN \
  --content-file "/abs/path/comment.txt"
```

### 7) 获取内容数据表（content_data）

```bash
# 获取笔记基础信息表（曝光/观看/封面点击率/点赞/评论/收藏/涨粉/分享/人均观看时长/弹幕）
python scripts/cdp_publish.py content-data

# 下划线别名
python scripts/cdp_publish.py content_data

# 可选：导出 CSV
python scripts/cdp_publish.py --reuse-existing-tab content-data --csv-file "/abs/path/content_data.csv"
```

### 7.5) 核验笔记提交状态

```bash
python scripts/cdp_publish.py --reuse-existing-tab verify-note \
  --title "最终发布标题" \
  --timeout-seconds 40
```

### 8) 获取评论和@通知（notification mentions）

```bash
# 抓取 /notification 页面触发的 you/mentions 接口数据
python scripts/cdp_publish.py get-notification-mentions

# 下划线别名
python scripts/cdp_publish.py get_notification_mentions
```

### 9) 评论回复 / 点赞收藏 / 用户主页信息

```bash
# 回复评论（支持按评论 ID / 作者 / 文本片段定位）
python scripts/cdp_publish.py respond-comment \
  --feed-id 67abc1234def567890123456 \
  --xsec-token XSEC_TOKEN \
  --comment-id COMMENT_ID \
  --content "感谢反馈～"

# 点赞 / 取消点赞
python scripts/cdp_publish.py note-upvote --feed-id 67abc1234def567890123456 --xsec-token XSEC_TOKEN
python scripts/cdp_publish.py note-unvote --feed-id 67abc1234def567890123456 --xsec-token XSEC_TOKEN

# 收藏 / 取消收藏
python scripts/cdp_publish.py note-bookmark --feed-id 67abc1234def567890123456 --xsec-token XSEC_TOKEN
python scripts/cdp_publish.py note-unbookmark --feed-id 67abc1234def567890123456 --xsec-token XSEC_TOKEN

# 用户主页快照 / 用户主页笔记
python scripts/cdp_publish.py profile-snapshot --user-id USER_ID
python scripts/cdp_publish.py notes-from-profile --user-id USER_ID --limit 20 --max-scrolls 3
```

补充：更完整的背景说明、安装说明与面向人工阅读的示例可参考 `README.md`，但本文件中的命令样例应优先作为 agent 执行基线。

## 失败处理

- 依赖或导入阶段失败（特别是 `ModuleNotFoundError: websockets.sync`，或 macOS `/usr/bin/python3` 报 `TypeError: unsupported operand type(s) for |`）：先确认执行脚本的 Python 与安装依赖的 Python 是同一个解释器，并至少支持 Python 3.10 的联合类型语法。优先用 `<XiaohongshuSkills 根目录>/.venv/bin/python` 执行 `publish_pipeline.py`、`cdp_publish.py` 及 `-m pip install -r requirements.txt`；不要使用调用方工作区中名称相似的虚拟环境。若 `.venv` 不存在，使用可用的 Python 3.10+ 在 Skill 根目录创建后再安装依赖。这类错误发生在连接浏览器之前，不会产生平台笔记；修复运行时后可安全重试，不要误判为登录失效或页面选择器变更。
- 登录失败：提示用户重新扫码登录并重试；若用户需要远程展示二维码，可改用 `get-login-qrcode`。
- 图片/视频下载失败：提示更换 URL 或改用本地文件。
- 本地路径不可用：优先改用绝对路径；若为 WSL/远程 CDP 的 Windows/UNC 路径，可先尝试 `--skip-file-check`，必要时再加 `--preserve-upload-paths`。
- 评论/回复目标未定位成功：提示补充 `comment_id`，或改用 `comment_author` / `comment_snippet` 再试。
- 页面选择器失效：提示检查 `scripts/cdp_publish.py` 中选择器并更新。
- 话题选择响应超时：不要重新填表或重复提交；复用同一发布页，并从原生话题锚点核对该话题是否已选中。只有锚点不存在时才补选一次，随后继续声明、地点与发布流程。
- 长时间发布/核验命令：执行宿主可能先于浏览器自动化进程返回，不能把“命令结束”或“无终端输出”当作发布结果。应保存命令输出到临时日志并检查实际进程是否退出；只有日志中观察到 `POST /web_api/sns/v2/note` 成功响应，并以 `verify-note` 对精确标题复核成功，才记录为已发布。若复核为 `found: false` 且未观察到 POST 成功，才可在重启浏览器后做一次恢复性重试。
- 若发布包装器在表单填写前的只读去重阶段报告 `Another publish process is running (pid=...)`，不得终止该进程或绕过锁。先等待并只读确认该 PID 是否仍存活；若它已自然退出，再用新标签运行一次 `content-data` 或精确标题核验。只有目标标题不存在、本轮没有上传/POST/收据且浏览器锁已释放时，才允许一次完整提交；若 PID 仍存活则继续等待，不并发填表。
- 只读 `content-data` 在 `--reuse-existing-tab` 模式下若连接到陈旧发布页，并在 `Page.enable` 阶段超时，说明该标签的 CDP 会话不可用，不等同于登录失败，也不代表统计接口无数据。先确认没有发布进程持锁；锁释放后去掉 `--reuse-existing-tab`，用新标签页重试一次。不得为只读去重检查终止正在运行的发布进程。
- 若只读 `content-data` 探针在受限执行环境中报告 Chrome 已启动但 9222 端口未响应，不要据此判定登录失效，也不要在同一受限环境反复拉起浏览器。保留该诊断；当任务已获发布授权时，改在获准的 GUI/网络执行上下文运行一次完整的已验证发布包装器，让包装器重新启动或复用 Chrome，并自行完成发布前去重、POST 捕获和发布后核验。只有包装器仍无法连接时，才进入浏览器启动故障排查；不得因探针失败重复提交。

## Windows 受限执行环境（进程会被会话回收）的登录与发布

> 完整规则与脚本见 patch：`~/.workbuddy/skills/red-book-skills-patches/windows-sandbox-workaround/SKILL.md`
>
> 核心要点：
>
> - 沙箱/受限会话中，命令结束时 Chrome 被强制回收，窗口闪退 + Cookie 无法落盘。
> - **正确做法**：把"登录等待 + 发布"放进同一次调用，全程不关浏览器，最后用 CDP `Browser.close` 优雅退出。
> - 与 `publish-interval-guard` patch 集成：通过环境变量 `XHS_INTERVAL_GUARD` 指向其 helper，自动化 wait/record。
>
> ```bash
> # 仅登录（优雅关闭以保存会话）
> <patch>/helpers/xhs_login_wait.py 200
>
> # 登录成功后立即发布（推荐，避免二次扫码）
> <patch>/helpers/xhs_login_wait.py 200 publish
> ```
>
> 关键实现点：按标签 ID 锁定登录页、必须做二次验证、必须优雅关闭。详见 patch。

## Patch 索引与上游更新检查

所有 patch 的索引、加载顺序、状态文件位置见：

```
~/.workbuddy/skills/red-book-skills-patches/INDEX.md
```

### 上游更新检查（patch: `update-checker`）

原仓库 `aus666666/red-book-skills` 会更新。本 skill 的所有定制已抽出为独立 patch——**升级主 skill 时，patch 不会丢**，但需要重新确认与新版的兼容性。

- 默认每周检查一次（可由 patch 的 `set-interval` 调整）
- 自动化已注册（见 `~/.workbuddy/automations/`）
- 检测到更新后由用户/agent 决策是否合并，**不自动修改文件**
- 状态文件位置：`update-checker/state/update_state.json`

常用命令：

```bash
# 状态查询
<patch>/helpers/update_check.py status

# 强制立即检查
<patch>/helpers/update_check.py check-now

# 标记某 commit 已读
<patch>/helpers/update_check.py acknowledge --sha <commit-sha>
```

检测到更新后如何处理：见 `update-checker/SKILL.md` 的"配合使用"一节。
