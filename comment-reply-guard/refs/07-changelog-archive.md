> read_when: 需要回溯 comment-reply-guard 的**早期版本**（v1.15.0 / v1.17.0 / v1.19.0）变更时
> 本文件从 `refs/03-changelog.md` 外移（03 触 9000 字符上限）。内容一字未改。
> 较新版本（v1.20+）仍在 `refs/03-changelog.md`。

## v1.15.0 (2026-09-17)

- 新增**铁律 23「个人主页抓笔记的 DOM 已改版」**：
  `a[href*="/explore/"]` 现为 `display:none` 隐藏链接且 href 不带 token，
  导致旧脚本 `comment/_grab_profile_xsec.py` **静默抓到 0 条**（不报错，最容易误判成"没笔记"）。
  正确取法：`section.note-item[data-note-id]` + `a.cover` 的 `?xsec_token=`；
  滚动容器是 `#userPostedFeeds`，**滚 window 无效**。
- 新建 `refs/05-profile-dom.md` 承载细节（`refs/01` 已 8898/9000 触顶）。
- 四处版本同步：SKILL.md / META.json / INDEX.md / 本文件。

## v1.17.0 (2026-09-27)

- 新增**铁律 24「/you/mentions 已失效 + 覆盖缺口根治」**（本轮最重要）：
  - `/you/mentions` 长期返回 **406**，铁律 4 的首选定位路径作废（铁律 4 已加失效标注）。
  - 三条替代路径：**私信**走 `https://www.xiaohongshu.com/chat`（**不是 /im**，/im 导航 45s 超时），
    条目 `[data-conv-id]`（class `xhs-im-conv-item`），一次拿全部会话（实测 101 个）；
    **评论**优先读 `_*_pub_progress.json` 的 `note_url`（发布链自本日起落盘）；
    **老笔记补 token** 用 `search_feeds(标题)` 按 `note_id` 匹配取 `xsecToken`。
  - **主页只渲染最近约 30 条**：当天发满 30+ 篇后，昨天及更早的笔记完全取不到 token，
    曾导致「扫 32 篇、0 未回复」的**假阴性**。这是覆盖缺口根因。
  - 创作中心 `_capture_note_manager_notes()` 的 token 是**账号级不可复用**（10 条同值，前缀 `YBey`），
    配 `/explore/{id}` 报 `This Page Isn't Available`。
- 新增**铁律 25「CDP 连接必须用 XiaohongshuPublisher」**：自建 websocket 会被本机 ALL_PROXY 劫持
  （永久挂起、无报错）；`_send()` 只接位置参数；浏览器挂了用 `chrome_launcher.py --port 9333 --restart`。
- 配套脚本（工作区 `xhs_publish/`）：`_grab_chat_list.py`（私信列表）、`_read_chat.py`（读会话）、
  `_dm_send.py`（私信发送+复读核验）、`_scan_old_comments.py`（老笔记补扫）、`_grab_last_token.py`（发布后抓 token）。
- 发布链 `_chain_live.py` 已打补丁：发布后落盘 `note_url`，从根上消除覆盖缺口。
- 新增**铁律 26「发现评论必须以消息为中心，不要遍历笔记」**（用户 2026-09-27 指出后修正）：
  - 错法 = 枚举笔记逐篇读详情（44 篇 28 分钟，且受主页 30 条限制，靠搜索补 token，等于用蛮力重建收件箱）。
  - 对法 = 读通知页 `/notification`「评论和@」DOM，**20 秒抓 128 条**，天然覆盖所有笔记的最新评论。
    脚本 `_scan_notif_v2.py`（修了旧版 `_scan_notifications.py` 的两个致命过时点：端口 9222→9333、
    自建 ws→cdp_publish）。要点：必须先点「评论和@」tab。
  - 分工明确：**发现走通知页，定位/回复走详情页**（通知页拿不到 note_id 与 comment_id）。
- 新增**铁律 27「评论数据在 `detail` 里，不在顶层」**：`get_feed_detail` 返回
  `{"detail": {"comments": {"list": [...]}}}`；**读顶层 `det["comments"]` 恒为 None**，
  曾造成「遍历 67 篇、0 未回复」的全量假阴性。旧脚本 `_scan_0927.py` / `_scan_old_comments.py` 均已修。
- 实测结论（本轮）：通知页 36 小时内有 **11 条未回复评论**，而修正前的遍历报告是 **0** ——
  假阴性会直接让用户误判"没有超时未回"，危害大于漏扫。

## v1.19.0（2026-09-27 晚 · 风控静置后恢复轮）

- **修正铁律 4**：`/you/mentions` 并非失效——主动 fetch 才 406，页面自加载时返回 200。
  新增**铁律 32**：`Network.enable` 监听响应体即可拿到 note_id/comment_id/xsec_token 精确映射
  （新脚本 `xhs_publish/_mentions_pages.py`，实测 120 条）。
- **新增铁律 31**：通知页就地提交（铁律 28 链路）**静默失败**——`.submit` 返回 sent 但评论里没有回复，
  连续 2 轮、排除填错对象与文案过长，非风控。**待解决**，下一轮改走详情页路径。
- 新增脚本：`_probe_mentions.py`（单页抓响应体）、`_mentions_pages.py`（翻页全量）、
  `_reply_0927_batch.py`（带文案+实时按钮定位+正文级复读核验）。
- 落盘：`_mentions_all.json`（120 条映射）、`xhs_publish/_reply_plan_pending_0927.json`（3 条待发文案+精确 id）。

---

- v1.6.0 (2026-09-15 下午) —— 🔴 **定位提速：`/you/mentions` 接口直取 id**
  - 推翻 v1.3.0/v1.4.0 的"mentions 是死路"：页面内 `fetch` 确实 406，但 CDP `Network.getResponseBody` 能拿完整响应。
  - 回复定位不再需要逐篇 `get-feed-detail`（旧法 80+ 分钟），降到秒级；同时绕开"最新笔记拿不到 xsec"缺口。
  - 事件循环坑：只等命令响应、丢事件 → 抓不到任何接口（第一次探针命中 0）。
  - 新增三之四增量回复：用「上次回复时间」做窗口，无法判断退回 36 小时。
  - 工具：`_probe_notif_api3.py`（CDP 抓体）、回复器 `_reply_0915_1500.py`。
  - 新增两个二级评论坑：① `subComments` 恒只返回最新 1 条（看 `subCommentCount`）；② 二级默认折叠，不能文本兜底。

- v1.0.0 (2026-09-14) 初版。来源：回复「问报名」类评论的实操。头号坑 = `--comment-id` 带前缀；次坑 = mentions 通知流不完整；确立回读验证；记录外链可行但风险自担。
- v1.1.0 (2026-09-15) 修正私信不是"无工具"（CDP 直操作 `/chat`）；新增二号坑（回复按钮 svg）；话术前缀定稿 `[自动回复，可转人工[拥抱]]`；新增查证规则、地域×时间话术、私信口径。
- v1.2.0 (2026-09-15 晚) v2 回复器跑通 2/2；修正「已回复」判据须按昵称 `叻叻财`（只认前缀会漏判用户手动回复）。
- v1.3.0 (2026-09-15 深夜) 检索提速（`_scan_notifications.py` 20 秒抓 56 条）；明确通知页只能发现不能回复；记录三条死路。
- v1.4.0 (2026-09-15 凌晨) content-data 评论字段全 0 不可信；新增四个核对坑；记录 user_id；发布时须落盘 note_id+xsec。
- v1.5.0 (2026-09-15 下午) —— 回复标记换血：平台禁止批量自动回复，改用 `[X1]`/`[X2]`/`[X9]`/`[E1]`；旧 `[自动回复…]`、`[拥抱]`、「可转人工」全废弃。
- v1.7.0 (2026-09-15 下午) —— 回复标记更名 `[X]`→`[A]`（用户裁定 A 更合适）；读取判据保留 `[X1]`/`[X2]`/`[X9]` 兼容（当日已发 4 条 `[X1]`）；改用表驱动脚本防并行 Edit 覆盖。
- v1.8.0 (2026-09-15 下午) —— 私信链路重写：推翻按索引点击（虚拟滚动+已读重排），改用 `data-conv-id` 直连；我方消息判据 `.chat-item__bubble--me`；新朋友放宽到 5 天；间隔 20s→32~44s。
- v1.9.0 (2026-09-15 傍晚) —— 报名类必须给具体网址：网址来源优先级 + 七条硬性要求；素材全量仅 1 个含 URL 的坑；落地佛山 CCF / 深圳沙龙两例；新增 `registration_links.md`。
- v1.10.0 (2026-09-15 傍晚) —— 两套体系独立化 + 到期提醒规则：新增 `SYSTEMS.md`、frontmatter 加 `system: comment`；新增五之五「到期提醒」登记待办+挂自动化；「没法单独提醒」作废。
- v1.11.0 (2026-09-15 深夜) —— mentions 首屏不全（单次 6 条、滚动累计 72 条，须合并去重）+ 二级展开控件 `.show-more`（文本含空格，正则 `展开\s*\d+\s*条回复`）。本轮成果：评论 8/8、私信打招呼 11 条、新增 4 条报名入口。
