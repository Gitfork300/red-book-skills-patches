---
name: comment-reply-guard
system: comment
version: 1.22.0
patch_for: red-book-skills
applies_to_main_version: ">=0.1.0"
priority: 11
author: Project maintainers
created: 2026-09-14
---

# comment-reply-guard

> **体系：`comment`（评论体系）** —— 只管**评论与私信的读取 / 回复**，**不管笔记文案**。
> 与发布体系（`publish`）是两套独立体系：写作 / 配图 / 时效 / 间隔 / 预检规则**一律不适用于回复**。
> 已知交叉点：正文网址（发布禁 / 回复问报名时必须给）→ 见 `SYSTEMS.md` X1。

## 铁律速查（每条必须遵守）

> 每条的**展开与实测依据** → `refs/06-rules-detail.md`（按编号索引）。

1. **回复必以标记开头**：`[A1]` 评论 / `[A2]` 私信 / `[A9]` 其他 / `[E1]` 异常 = 标记 + **半角空格** + 正文。
2. `--comment-id` **必须带 `comment-` 前缀**（接口返纯 id，DOM 属性带前缀，全等比较）。
3. 回复按钮是 **svg 图标（无"回复"文本）** → 点 `.reply.icon-container`；**不能用 `respond-comment`**。
4. 定位首选 **`/you/mentions`**：`Network.enable` → 监听 `Network.responseReceived` → `getResponseBody`
   （主动 `fetch` 调它 = 406，页面自己加载时才返 200）。
5. 通知页 DOM **只能发现、不能回复**（拿不到 id）；回复 = mentions 定位 + detail 核对 + 点图标发送。
6. **已回判据 = `subComments` 里有我方昵称 `AI展会叻`**（**不是**「叻叻财」）。
7. **增量回复**：取上次回复时间（日志 mtime）做窗口，无法判断时兜底 **36 小时**。
8. 答复前**必须查证**：≥2 源；查不到如实说「以主办方公布为准」，**不许套模板**。
9. **报名类必给具体报名网址**（`https://…`，当场核实可打开、一一对应），不能只说"官方渠道登记"。
10. **「X 日踢我」→ 登记 `COMMENT_REMINDERS.md` + 挂一次性自动化**，到期真去提醒；**禁回「没法单独提醒」**。
11. 私信：**只处理 3 天内**（新朋友招呼放宽 5 天）；已回忽略（判据 = 最后一条是我方 `.chat-item__bubble--me`）。
12. 节奏：每条 **≥35 秒**、单轮 ≤20 条；站外链接高风险，**控量 + 盯异常**。
13. **非提问不回**：只回「向我方提问」与「对我方内容的质疑/纠错」；闲聊附和 / 纯表情 / @别人 / 粗口**不回**，
    存疑归「不回」。例外：**当日配额不足时 `eval` 评价类升级为可回**（见 34 / 35）。
14. **历史标记复查**：只允许 `[A1]/[A2]/[A9]/[E1]`；`[X1]` / `[自动回复]` 存量列待清理，报用户拍板后处理。
15. **Tab 守护**：评论链**自建独立 tab**（`PUT /json/new`），用完 `finally` 关闭；**绝不碰 `creator.xiaohongshu.com` tab**；
    收尾跑 `_tab_guard.py`（只读，有残留再 `--clean`）。
16. **单篇量大只回前 2 页**（不额外翻页）；定位不到**直接跳过**，连续 2~3 次失败即弃；单条重试 ≤3 轮。
17. **白天超时预算**：单项 ≤180s 且 ≤2 轮、单轮巡检 ≤30min；白天**禁**重构脚本 / 跨源深挖 / 复盘；
    执行器 `_daybudget.py`（`status` / `wrap` / `skip`，超时 rc=124）；同类 skip ≥3 停手。
18. **扫描也要节流**：每篇 sleep 8~16s；命中 `captcha` / `Security Verification` / `Drag the arrow`
    → **立即整批 break，不重试**（人工拖滑块恢复）；`TimeoutExpired` 必须捕获。
19. **评论巡检只管 2 天内发布的笔记**（`--since YYYY-MM-DD`，按**笔记发布时间**过滤；与 36h 评论窗口不冲突）。
20. **扫描范围 = 合并清单**（列表单次只出 100 条，`_merge_notes_src.py` 合并历史快照），不能只用新抓的。
21. **回复 ≤150 字**（长了平台**静默丢弃**：461/189 字失败、~130 字成功）；发送后**必须 API 复查**。
22. 私信「已回」**不能看 summary 前缀**（它显示的是最后一条，不论谁发）→ 进会话看 `.chat-item__bubble--me`（`_dm_read_ctx.py`）。
23. 个人主页 DOM 已改版：token 在 `a.cover` 的 href；`section.note-item[data-note-id]`；滚 `#userPostedFeeds`。→ `refs/05`
24. mentions 不可用时的替代：私信走 **`/chat`**（非 `/im`）；评论取 `_*_pub_progress.json` 的 `note_url`；
    老笔记 `search_feeds` 补 token。⚠️ 主页只渲染最近 ~30 条 → 覆盖缺口。→ `refs/06` §定位路径演变
25. **CDP 必须用 `XiaohongshuPublisher`**（自建 ws 会被 ALL_PROXY 劫持、无报错挂起）；`_send(方法, 参数字典)` 只接位置参数。
26. **发现评论要「以消息为中心」**：直接读通知页「评论和@」DOM（20 秒抓 100+ 条），**不遍历笔记**；
    默认停在「赞和收藏」tab，**必须先点「评论和@」**。
27. `get_feed_detail` 的评论在 **`detail.comments.list`**，不在顶层（读顶层恒为 None → 全量假阴性）。
28. **通知页可就地回复**：判据 = 条目 innerText 含**我方回复正文片段**（**不是**回复按钮 / 不是正则猜文本）；
    链路 = 点回复 → 填 `textarea.comment-input` → `.submit`。
29. **风控「访问频繁」= 速率限制**：整批停手不重试，静置 ~2 小时（**同时暂停周期性巡检自动化**）；恢复后降速。
30. 查进程/系统信息用 Python `subprocess` 调 powershell（本机 PowerShell 工具会被沙箱拦，Bash `ls`/`wmic` 常失效），
    **输出写文件后用 Read 读**。
31. 通知页提交**必须真实点击**：先 `scrollIntoView` 再取坐标 → CDP `Input.dispatchMouseEvent` + `Input.insertText`；
    验收 = `comment/post` 响应含 `"toast":"你的回复已发布"`（监听判据必须写 `"comment/post" in url`）。
32. **评论→笔记映射**：抓 `you/mentions` 响应（`item_info.id` / `xsec_token` / `comment_info.id`）；
    脚本 `_mentions_pages.py [页数]`。
33. **点通知右侧封面图** `<img class="extra-image">` 直达 `/explore/<id>?xsec_token=...`（实测 8/8）；
    脚本 `_map_images.py`。⚠️ 首次导航常被踢 `/login`，**重试 2~4 次，别 `--restart`**；脚本清 `*_PROXY`。
34. **每日配额：回复量 / 当日评论量 ≥ 50%**（`ceil(planned*0.5)` 为必须达成条数）；
    优先级 `question` 必回 > `correction` 必回 > `eval` 补缺口 > `chat` 永不回；
    `planned≤2` → 至少回 1 条；结构性不可达时降到 cap 并标注。台账 `_reply_quota.json`，脚本 `_reply_quota.py`（`sync`/`add`/`status`/`plan`）。
35. **「当日评论不足」= 配额缺口，不是评论条数少**；**50% 是上限不是指标**，达标即停；
    `planned` 按评论时间归属自然日，昨天的算昨天。
36. **核验回复必须先展开折叠子评论**（`_expand_check.py`）；「页面查不到」≠「没发出」；
    金标准 = `comment/post` 响应 toast > 展开后能看到 `[A1]` + 昵称。误发删除入口 `div.comment-menu-sub`
    → `.menu-item`「删除」（`_del_dup.py`，**先只枚举不点击**）。
37. **零废话**：禁「感谢分享 / 感谢反馈 / 仅供参考」类客套；`eval` 回复必须带**与话题相关的实质内容**
    （回复侧允许表达观点，与发布侧不同，但不得编造数据）；查不到就不回。

## 关键判据与坑（要点）

**主页登录态 ≠ 创作者中心**：读/回评论要 `www.xiaohongshu.com` 主页登录态；只验 `check-login` 会误判"已登录"。

**地域 × 时间差异化话术**：回复前先定城市（长三角 / 珠三角 / **中国香港** / **中国澳门**）与开始日。
- 港澳**必须加**「前往需持有效港澳通行证及签注」，且不得表述为国家。
- 已办完的活动**如实说已结束**，不再引导报名。

**报名网址来源优先级**：官方报名系统直达页 → 承办方官网活动页 → 主办方公告页 → 官方咨询渠道。
素材文件通常**无 URL** → 必须回捞官方页补全，核实后落盘 `xhs_publish/registration_links.md`。

**私信入口**：`/chat`（非 `/im`）；会话 ID = `data-conv-id`，直连 `/chat/<conv-id>`；新朋友打招呼同样带 `[A2]`。

## 标准工作流（可复制）

```
1. 拿 (note_id, xsec_token, comment_id)：/you/mentions 响应体（CDP 抓，滚动合并去重）
2. 逐篇 get-feed-detail 核对（不是全量扫）
3. 判「是否已回」：subComments 里有没有昵称 AI展会叻（不是 叻叻财）
4. 回复：--comment-id 带 comment- 前缀 / 或按 .reply.icon-container 点击发送
5. 回读验证：重新 get-feed-detail（先展开折叠）确认 subComments 出现我方回复
```

## 展开阅读（命中场景才读）

| 场景 | 读哪个文件 |
| --- | --- |
| **铁律的展开与实测依据（按编号索引）** | `refs/06-rules-detail.md` |
| 评论/私信 DOM 结构、选择器、CDP 抓取细节、脚本参数 | `refs/01-dom-and-scripts.md` |
| 事故复盘、失败路径、已确认事实（user_id、表情码等） | `refs/02-incidents.md` |
| 版本修改记录 | `refs/03-changelog.md` |
| 删除链路与页面渲染坑（深评论删不掉、已回复复核口径） | `refs/04-delete-and-render.md` |
| 个人主页 DOM 改版（抓 note_id / xsec_token） | `refs/05-profile-dom.md` |
| 批量清理不合规存量评论 / 判据坑 | `refs/07-batch-cleanup.md` |
| 早期版本记录（v1.0~v1.11 / v1.15 / v1.17 / v1.19） | `refs/07-changelog-archive.md` |
