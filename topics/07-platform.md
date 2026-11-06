# 07 · 平台侧（小红书风控与读取）

> read_when: 判断是不是被风控、读取已发笔记、排查登录态时
> 本文件是 `MEMORY.md` 第 7 节的展开。**结论以主文件为准**。

## 单一权威

- **风控规则单一权威 = `xhs-risk-guard` patch**
  （A 读取域 / B 登录域 / C 接口域 / D 假风控表 / E 发布域）
- **不要在别处另写一套**

## 判断顺序（铁律）

> **先排除我方问题，再怀疑平台。**

09-11、09-12 两次误判都跳过这步。典型「假风控」：

| 现象 | 真实原因 |
| --- | --- |
| 页面结构变了 | CDP `Network.enable` 参数误写 `maxPostSize`（应为 `maxPostDataSize`） |
| 页面结构变了 | TLS 假报 |
| 探活假死 | 裸 socket 探活 |

## 读取额度

- 公开页有风控额度：连续约 **30 篇**后一律重定向登录页 = **限流，不是登录失效**
- 单次 ≤25 篇
- 批次间隔数小时
- **连续 3 篇失败即停**（`read_note_body.py` 已守卫）

## 读已发笔记正文

唯一读取路径 = 公开页 + `xsec_token`：

```
explore/<id>?xsec_token=<tok>&xsec_source=pc_user
```

取 `#detail-desc`。

- ⚠️ **编辑已发笔记我们不支持**，只能平台侧手动改 / 删

## 登录态

- 登录态落盘，Chrome 重启仍登录
- 真失效现象：`…/login?redirectReason=401`

## 列表分页

- `?tab=0&page=N`（**0 基**，每页 10）
- **必须驱动页面滚动**才带签名头（页面内 `fetch` 会 406）
- 复用 `XiaohongshuPublisher`，**别自搓 CDP**

## 无节流批量扫描 → 滑块验证码（2026-09-16 23:4x 实测，我自己踩的）

**现象**：连续无间隔跑 `get-feed-detail` 扫 54 篇 → 之后所有导航卡死 180s 超时。
探针确认：www 任一页都会被重定向到
`https://www.xiaohongshu.com/website-login/captcha?...`，
页面标题 `Security Verification`、正文 `Drag the arrow to complete the puzzle`。

**判据**：看到 `captcha` / `Security Verification` / `Drag the arrow` 任一 → 立即**熔断停批**，
不要重试（重试只会加重风控）。**只能人工在 Chrome 里拖一次滑块**恢复。

**预防**（已写进 `_scan_0916_night2.py`）：
- 每篇之间 **sleep 8~16s 随机**（可 `--gap N` 调大）
- 脚本内检测 captcha 关键字 → `break` 整批
- 单篇 `TimeoutExpired` 只记 error 继续，**不中断批次**（v1 未捕获 → 整批崩）

**教训**：读评论的节奏约束以前只写在「回复」（铁律 12：每条 20~30s 随机），
**没覆盖「读取/扫描」** —— 扫描同样会吃风控额度。以后任何批量读，先定节流。

## 平台侧全量清单（下架核对 / 状态审计）
唯一路径 = `publish-loop-guard/helpers/list_all_notes.py`（创作者中心**管理页**，只读，**不占公开页风控额度**）：

```bash
cd <skill>/red-book-skills-patches/publish-loop-guard/helpers
<skill>/red-book-skills/.venv/Scripts/python.exe list_all_notes.py \
  --days 3 --json --out <工作区>/xhs_publish/logs/platform_notes_<date>.json
```

- 只读第一页的快速版是 `recent_published.py`（漏发复核用）；**下架核对必须用 `list_all_notes`**——被误发的稿子在 9/13，滚不到位就看不见
- 输出即 `dup_check` 的**平台侧数据源**（`logs/*platform_notes*.json`）→ 复核完**保留**，自动并入双源查重
- ⚠️ **批次发布链跑完会顺手关掉 Chrome**（`tasklist` 里 0 个 chrome.exe、<PORT_COMMENT> 拒连）。
  复核前必须先拉起：`cd <skill>/red-book-skills && .venv/Scripts/python.exe scripts/cdp_publish.py check-login`
  （该子命令自启 Chrome；**先删 `tmp/login_status_cache.json`** 免读旧结论；判据 = stdout `[cdp_publish] Login confirmed.`）
- 退出码：`0` = 无非「已发布」条目；`1` = 有审核中/未通过（**可当发布健康度用**）

## 回复标记（2026-09-15 用户定稿）

> 触发事件：**平台提示「禁止批量自动回复」**。

- 每条评论/私信回复**必须以标记开头**，格式 = **标记 + 半角空格 + 正文**：
  `[A1]` 自动回复评论 / `[A2]` 自动回复私信 / `[A9]` 其他回复 / `[E1]` 异常事件回复
- 归属优先级：内容涉及异常（取消/改期/地点变更/主办方澄清/我方更正）→ 一律 `[E1]`；
  否则按渠道 `A1` / `A2` / `A9`
- **旧前缀全部作废**：`[自动回复[拥抱]]`、`[自动回复，可转人工[拥抱]]`、「可转人工」措辞
  （评论与私信不再有前缀差异；私信打招呼也要带 `[A2]`）
- 判据兼容：读历史回复时同时认新旧标记；**主判据仍是昵称 `叻叻财`**（只认前缀会漏判手动回复）
- 权威细则：`comment-reply-guard` **v1.9.0**（话术、地域×时间分类、DM 实操、**报名网址口径**）
- 已同步脚本（`xhs_publish/`）：`_reply_36h.py`、`_reply_v2.py`、`_reply_via_hover.py`、
  `_reply3.py`、`_reply_batch.py` → `[A1]`；`_send_dm.py`（含 GREET）→ `[A2]`；
  `_scan_all_comments.py` / `_verify_v2.py` / `_diag_delete_reply*.py` → 兼容匹配
- 被平台提示后的处置：**先降量、拉间隔**（基线 20~30s/条、被提示后 40~60s/条，单轮 ≤20），
  再按铁律 9 排除我方问题（前缀遗漏 / 重复回复 / 模板雷同）

> **标记更名（2026-09-15 下午）**：用户裁定 `[A]` 比 `[X]` 更合适 -> 现用
> **`[A1]` 评论 / `[A2]` 私信 / `[A9]` 其他 / `[E1]` 异常事件**（`[E1]` 不变）。
> 读取判据保留 `[X1]/[X2]/[X9]` 兼容（已发出回复不回改）。

## 报名答复必须给具体网址（2026-09-15 傍晚 用户定稿）

> 用户原话：「当有人问到如何报名相关的内容，需要**额外报名相关的具体网址**，
> 不能含糊，**尽可能确保对方一步到位**。」

- 触发词：怎么报名 / 在哪报名 / 报名入口 / 报名链接 / 怎么参加 / 怎么登记
  → 回复**正文里必须出现完整 URL**（`https://…`）
- ❌ **不许**的含糊说法：「可通过官方渠道登记」「可通过 CCF 会议系统登记」
  「报名请以主办方官方渠道公布为准」（后者只在**查不到**时的兜底，且须声明"未查到线上入口"）
- URL 来源优先级：① 官方报名系统直达页 ② 主办/承办方官网活动页 ③ 官方公告页 ④ 官方咨询渠道
- URL 须**当场核实可打开**、与活动**一一对应**，不许凭记忆拼域名
- 🔴 **素材文件里通常没有 URL**：`wd*.txt` / `ai_events_*.txt` 全量中**仅 1 个文件含 URL**，
  报名信息一律写成「可通过官方渠道登记」→ **照抄素材必然踩坑**，必须回捞官方页
- 核实结果**落盘归档**到 `xhs_publish/registration_links.md`（报名入口索引），供后续复用
- **报名已截止 ≠ 不给网址**：仍给报名页 URL，同时如实说截止时间，但不再引导报名
- 一步到位 = **URL + 报名截止时间 + 是否审核/收费**，三样尽量齐
- 已核实三场（2026-09-15）：
  - 佛山 CCF 大湾区AI青年论坛（9/19，免费公开报名，**报名中**）
    → `conf.ccf.org.cn/web/html8/index.html?globalId=m1547233241625399296178893075100&type=1`
  - 深圳「芯」赋能 Physical AI 沙龙（9/16，20人需审核，**9/15 12:00 已截止**）
    → `sziota.com/NewsView/2078.html`
  - 第四届香港具身智能医疗科技论坛 CREATE Symposium（9/22–23，中国香港，**报名中**）
    → `forms.office.com/r/ePnu6HMySU`
## 到期提醒类请求（2026-09-15 傍晚 用户裁定）

评论者留言「**X 日踢我**」/「X 日提醒我」/「到时候叫我」= **要办的事**，不是客套。

- ❌ 禁止回复「这边只做公开信息整理，没法单独提醒哈」—— 我们有定时任务，能提醒。
- ✅ 四步：① 当场回「到 X 日我再来提醒你」② 登记 `xhs_publish/COMMENT_REMINDERS.md`
  ③ 挂**一次性自动化**（到期日，默认 10:00，prompt 自包含）④ 到期先复核活动/入口仍有效
  → 原评论下续回复 → 回读确认 → 状态改 `done`。
- 边界：本身**不是报名问题**（不必强塞网址）；但到期提醒内容若涉及参与方式 → 仍按报名规则给入口。
- 权威细则：`comment-reply-guard` 第五节之五

## 两套体系边界（2026-09-15 用户裁定）

**评论与发布是两套体系，独立维护，避免干扰。** 唯一权威：`red-book-skills-patches/SYSTEMS.md`。

| 体系 | 代号 | 成员 |
| --- | --- | --- |
| 发布 | `publish` | writing-facts-only / safe-wording-guard / cover-image-rules / timeliness-window / organizer-qualification-guard / publish-preflight-guard / publish-interval-guard / publish-loop-guard |
| 评论 | `comment` | comment-reply-guard |
| 共用基座 | `shared` | core-overrides / update-checker / windows-sandbox-workaround / xhs-risk-guard / tools |

- **改哪套只动哪套 skill**；跨体系生效须先在 `SYSTEMS.md` 交叉点清单登记，再两边互相指向。
- **最易踩的交叉点**：正文网址 —— 发布侧**一律禁**（`safe-wording-guard`），
  评论侧问报名**必须给**（`comment-reply-guard` 五之四）。**先判对象再套规则，不得交叉否决**。
- `writing-facts-only` 原「适用范围」误含「评论」，已收窄为"仅已发布笔记"（历史上的一处作用域泄漏）。
- 权威细则：`SYSTEMS.md` 第三节

## 登录态判据（2026-10-13 B-042 沉淀）

**两个登录态彼此独立**：
- `creator.xiaohongshu.com`（创作者中心）→ 决定**能不能发笔记**
- `www.xiaohongshu.com`（主页）→ 决定**能不能读/回评论与私信**

**判巡检可用性不要用 `check-login`** —— 它只探 creator 端，www 端失效时它照样返回通过
（B-042 就是因为这个连续 3 天误判「已登录」，巡检恒 0 条却查不出原因）。
正确判据：直接导航 `https://www.xiaohongshu.com/notification`，看是否 302 到 `/login`。

## HTTP 461 = creator 登录态失效签名（2026-10-24 实测）

- **签名**：`CDPError: Xiaohongshu publish failure: code=0, msg=''; HTTP 461, response={"code":0,"success":true,"data":{}}`
  —— body 是 `success:true` 空 data，**不是风控、不是稿件问题**；重试 8+ 次、轮换/重启 <PORT_PUBLISH> Chrome 均无效
- **判据**：删 `runtime/tmp/login_status_cache.json` 后跑 `cdp_publish.py --port <PORT_PUBLISH> check-login`，
  导航落 `https://creator.xiaohongshu.com/login` → 确诊 creator 会话过期
- ⚠️ **发布页 UI 显示「已登录」是缓存假象**，不能作判据（10-24 页面显示登录中，实际 461 全败）
- 处置：停链（防继续烧草稿）→ `cdp_publish.py --port <PORT_PUBLISH> login` 开 QR 页 → 用户扫码 →
  恢复后起 `_watchdog_<MMDD>.py` 续跑；default（<PORT_PUBLISH>）/comment（<PORT_COMMENT>）账号隔离，不能互借

## quote-info：判「是不是向我方提问」（2026-10-13 定）

通知页「评论和@」条目结构（`div.container`）：
`div.user-info`（评论者） / `div.interaction-content`（评论正文） /
**`div.quote-info`（在回复谁）** / `div.actions`（回复按钮）

**`quote-info` 非空且不是我方 → 该评论是评论者之间的互回复，判「不回」**，
哪怕正文带「？」、内容看着像在问入场规则。典型误判：
「我周五去，我看他们说现场可以扫码？」+ quote-info=「1111: 请问你进去了吗」→ 是在回 1111，不是问作者。

只按评论文本分类会把这类误判成 question（存 B-045，`_reply_quota.py::classify()` 待修）。
