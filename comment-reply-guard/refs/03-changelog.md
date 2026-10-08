> read_when: 需要回溯 comment-reply-guard 的历史版本变更、判断某条规则何时定的时
> 本文件是 `SKILL.md` 的修改记录（v1.0.0 ~ v1.22.0），规则结论仍以 SKILL.md 为准（system: comment）。

# comment-reply-guard / refs — 修改记录

- v1.22.0 (2026-09-29)
  - 🔻 **铁律 34 配额下调：80% → 50%**（用户原话「评论比例可以降低至50%，减少无效回答」）。
    目标条数 = `ceil(planned*0.5)`；台账脚本 `_reply_quota.py` 的 `TARGET_RATIO` 同步改为 `0.50`。
  - ⚠️ **铁律 35 追加**：50% 是**上限不是指标** —— 达标即停，不许为回满 eval 继续发，
    宁可少回、不留无信息量的回复。
  - 🆕 **新增铁律 37 回复文案「零废话」**（用户原话「『感谢补充使用体验』这样的废话不要有。
    可以发表话题相关的看法。」）：
    · **禁止**「感谢分享 / 感谢反馈 / 谢谢关注 / 笔记仅整理官方公开信息」等零信息量客套；
    · **评价类回复必须带话题相关的实质内容**（可核对事实/背景/口径，或有信息量的看法 ——
      回复侧允许表达观点，与发布侧「只陈述事实」不同，但不得编造数据）；
    · 查不到可核对信息时**宁可不回**，或写「公开信息没查到 X，以官方公布为准」。

- v1.21.0 (2026-09-27)
  - 🆕 **新增铁律 34 每日回复配额制**（用户拍板）：**回复量 / 当日评论量 ≥ 80%**。
    分母 `planned` = 当日收到的评论总数（按**评论时间**归自然日，不剔除任何类别）；
    目标条数 = `ceil(planned*0.8)`；`planned 1~2 → 至少 1 条`，`0 → 不回`。
    回复优先级 `question > correction > eval > chat`：前两类必回，
    **eval 仅在前两类回完仍有缺口时补**，chat 永不回。
  - 🆕 **新增铁律 35** 澄清「当日评论不足」= **配额缺口**，不是评论条数少；
    `planned` 按评论时间归日，36h 窗口跨天不并入。
  - ⚠️ **铁律 13 增加例外**：原「非提问不回」改为**默认口径** ——
    评价类（针对我方内容发表看法、未提问）在配额不足时**升级为可回**；
    闲聊附和 / 纯表情 / @别人 / 粗口仍不回。
  - 新增台账 `xhs_publish/_reply_quota.json` 与脚本 `xhs_publish/_reply_quota.py`
    （`sync` / `add` / `status` / `plan`），分类函数 `classify()` 为单一出处。
  - 🔴 **新增铁律 36（本轮最贵的坑）**：笔记页**子评论默认折叠** ——
    未点「展开 N 条回复」就查 `[A1]`/昵称 = **0 命中的假阴性**，与「真没发出」无法区分。
    据此误判 2 条失败并补发 -> 实际各发两遍（`[A1]` x4）-> 逐条删除才恢复。
    核验标准动作改为：滚动 -> 点展开 -> 再滚 -> 才数 `[A1]`（`_expand_check.py`）。
  - ⚠️ 监听判据纠错：`"/api/sns/" in url` 会被 `unread_count`/`you/mentions` 恒定命中
    -> 假阳性；必须写 `"comment/post" in url`。
  - 误发补救：删除入口 = 我方子评论 `.comment-menu-sub` -> 菜单「删除」-> 确认「确定」
    （`_del_dup.py`，每轮删 1 条并即时核数 4->3->2）。

- v1.20.0 (2026-09-27)
  - 🔴 **昵称纠错**：我方评论昵称是 **`AI展会叻`**，不是 `叻叻财`（由 `comment/post`
    响应体 `data.comment.user_info.nickname` 确认）。旧值导致「是否已回复」判据恒为假，
    大量已回评论被反复误列为未回。已同步修 SKILL/refs/xhs-risk-guard/doc_layers。
  - 🔴 **判据纠错**：通知页「回复」按钮**常驻**，回复后仍在 —— 「有按钮 ⇔ 未回复」是错的，
    会重复列待回清单。改为「条目 innerText 含我方回复正文片段」或看 comment/post 响应体。
  - ✅ **就地回复「静默失败」已解决**（原铁律 31 标为未解决）：根因是点击落空 ——
    `el.click()` 不触发 Vue 发送（UI 清空输入框但**没发请求**）。修法：
    先 scrollIntoView 再取坐标 + CDP `Input.dispatchMouseEvent` 真实点击 +
    `Input.insertText` 键入；验收 = 出现 comment/post 且响应含 `你的回复已发布`。
  - ✅ **新增铁律 33**：点通知右侧封面图 `<img class="extra-image">`（在 `.info`
    **外层**整行上，只查 .info 会误判无图）直达 `/explore/<note_id>`，实测 8/8 拿 id。
  - 环境坑：新 Chrome 首次导航常踢到 /login，重试 2~4 次即可；**别 --restart**
    （每次重启掉登录态）；脚本须清 HTTP(S)_PROXY/ALL_PROXY，否则 CDP 连 127.0.0.1
    被代理劫持 502 → 误判 Chrome 已死 → 重启 → 又掉登录。
- v1.18.0 (2026-09-27 下午) —— 🔴 **收件箱直答 inbox-first：策略换血，修掉系统性漏回复**：
  - **根因（三条，全部实测证伪后才下结论）**：
    1. `_scan_notif_v2.py` 用正则 `/已回复|回复了/` 在整块 innerText 上判断「已回复」——
       而通知里的**动作文本「回复了你的评论」本身就含「回复了」**，恒定命中 →
       **把未回复的判成已回复**。这是用户看到「36 小时内还有未回复」的直接原因。**该脚本已废弃。**
    2. 判据换成「**`<div class="action-text">回复</div>` 按钮是否存在**」：有按钮 ⇔ 未回复。
    3. v1.17.0 的「通知页**只能发现、不能回复**」是错的。实测通知页**可以就地回复**：
       点回复按钮 → 内联展开 `<textarea class="comment-input" placeholder="回复 XXX">`
       → 填 value + 派发 input/change → 点 `.submit`。**全程不需要 note_id / comment_id / xsec_token。**
  - **「通知页取 note_id」这条路是死的**，已排除全部绕行路径，别再试：
    全站 `<a>` 里 `/explore/` 链接数为 **0**（329 个链接全指向 `/user/profile/*`）；
    **点通知卡片主体不跳转**（URL 停在 /notification）；后端
    `/api/sns/web/v1/notice/{recent_list,interaction_list,mentions_list,comments_list,list}`
    5 条路径**全部 500**（`create invoker failed, service: jarvis-gateway-default`）。
  - **答复要贴合原笔记时**（用户口径：只检索**有评论对应的**那几篇，不全量遍历）：
    `_match_comment_to_note.py`（本地 594 篇做 IDF 加权关键词反查，出 top-3 候选）→
    `_locate_comment.py`（**只拉这几篇候选**的详情，按「用户名+评论原文」精确命中）。
    局限：短而泛的评论（「怎么报名」「都有哪些岗位呀」）本地反查无法唯一定位，必须二次确认。
  - 主脚本 `xhs_publish/_inbox_reply.py`（`--hours 36` 只读扫描）。本次实扫：**36h 内 8 条未回复**。
  - 新增铁律 28（收件箱直答）、29（「访问频繁」风控处置）、30（PowerShell 被沙箱拦的绕法）；
    修正铁律 26 的过期结论。
  - 同 V1.18.0 当天 16:45 撞「访问频繁」风控 → 停手静置 2 小时，并**同步暂停周期性巡检自动化**
    （否则它会在静置期内自动触发）。恢复后 `--gap` 拉到 8~16s。
  - 同步：`SKILL.md` / `META.json` version → **1.18.0**。

- v1.17.0 (2026-09-27 上午) —— **`/you/mentions` 失效后的替代定位 + 覆盖缺口根治**（补记）：
  - `/you/mentions` 长期 406，铁律 4 首选路径作废 → 改走 `/chat`（非 `/im`）列表 +
    进度文件 `note_url` + `search_feeds` 补 token 三条。
  - 主页只渲染约 30 条导致「扫了 32 篇、0 未回复」的**假阴性**；
    创作中心 note-manager 的 token 不可复用（账号级，前缀 `YBey`）。
  - `get_feed_detail` 的评论在 `detail` 里不在顶层（读顶层恒为 None）。
  - 铁律 26 确立「以消息为中心、读通知页」。（其「不能回复」的结论后被 v1.18.0 推翻。）

- v1.16.0 (2026-09-25 晚) —— **respond-comment 定位改道 + 台账口径修补**：
  - 🔴 `--comment-id` 传 `get-feed-detail` 返回的 `comments[].id` **定位不上**
    （脚本拿它比对 DOM `data-comment-id`），报 `Failed to locate reply target comment:
    target_comment_not_matched`（rc=1）；加 `comment-` 前缀同样无效。
    → 改用 **`--comment-author` + `--comment-snippet`** 模糊定位，实测一次命中（refs/01 之七）。
  - 🔴 **台账口径修补**：凡动过「发送」的脚本（**含探针 / diag**）都要写回统一台账。
    当天一条私信是在 `_patrol_dm_diag.py` 里验证 execCommand+Enter 时发出的
    （bubbles 1→2、`last_is_me=true`，确实成功）却没进结果文件
    → 汇总按文件数得 14、实际会话覆盖 15，**计数整整差 1**，差点误判成「还有 1 条没回」。
  - 当日实绩：私信 **15/15** 会话全覆盖、评论扫 **75 篇**回 2 条（均复读核验逐字一致）。
  - 同步：`SKILL.md` / `META.json` version → **1.16.0**。

- v1.15.0 (2026-09-25) —— **私信输入改道（补记：上次改动漏写本日志）**：
  - ❌ CDP `Input.insertText` 会「假成功」：文本进 DOM、`innerText` 校验也过，
    但 React 受控状态没更新 → 按 Enter / 点按钮都没反应、**消息根本没发出**。
  - ✅ 正解三步：`el.focus()` → `document.execCommand('insertText', false, MSG)` →
    **发送 Enter 键**（点 `.xhs-im-input-bar-action-btn` 实测无效）。
  - 笔记评论定位补充路径：`mentions` 406 / profile DOM 不渲染时，
    用 **`search-feeds` 取 `xsecToken` → `get-feed-detail --load-all-comments`**。

- v1.12.0 (2026-09-16 傍晚) —— **白天超时预算制（铁律 17）** + 补记当日铁律 13~16：
  - 铁律 13 **非提问不回**（用户原话「可能这是和其他朋友间的聊天或者标记，我们无需打断」）；
    存疑归入「不回」。
  - 铁律 14 历史标记合规复查（`[X1]`/`[自动回复]`/误用 `[E1]` 列为待清理）。
  - 铁律 15 Tab 与内存守护（独立 tab、`finally` 关闭、绝不碰 creator、`_tab_guard.py`）。
  - 铁律 16 单篇量大只回前 2 页、连续 2~3 次定位失败即弃、禁止 >~3 轮重试、报跳过清单。
  - 铁律 17 **白天超时预算制**（用户原话「白天不要瞎琢磨，要尽可能按时完成任务为主」）：
    白天保量优先、卡住即弃；白天禁重构 / 深挖 / 复盘；单项 ≤180s 且 ≤2 轮（**暂定待确认**）。
  - 新增执行器 `_daybudget.py`（工作区根）：`status` / `wrap --budget N --tag X -- <cmd>`
    （超时 kill，rc=124，**存量脚本零改造**）/ `skip` 登记；弃项落 `_skip_<日期>.md`。
  - 触发背景：白天为「拍摄需要吗」广告评论连试 6 轮 4 个脚本无果，
    吃掉大量时间 → 立此机制。同类 skip ≥3 判系统性障碍，白天停手转夜间。
  - **18:17 用户拍板**：数值不再是暂定 —— 白天 08:00–22:00 / 单项 180s 且 ≤2 轮 /
    单轮 30min / 同类 skip ≥3 停手。三处规则副本（本铁律 17、`start-daily-task` §0、
    项目 MEMORY.md 铁律 17）已同步去「待确认」。
  - `_daybudget.py` 增强：`count_skips()` / `blocked_classes()` —— `status` 打印当日 skip 分布，
    `wrap` 超时时若同类已达阈值**自动告警「系统性障碍，白天停手」**。

- v1.13.0 (2026-09-16 深夜) —— **铁律 18「读取 / 扫描也要节流 + 命中滑块验证码立即熔断」**：
  - 起因：铁律 12 的节奏只管「回复」、**没管「读」** → 连续无间隔扫 54 篇 `get-feed-detail`
    触发小红书**滑块验证码**（`website-login/captcha`，标题 `Security Verification` /
    `Drag the arrow to complete the puzzle`），此后所有导航卡死 180s 超时，
    **只能人工在 Chrome 里拖一次滑块**才能恢复。
  - 规则：批量扫描每篇之间 **sleep 8~16s 随机**（`--gap N` 可调）；输出里出现
    `captcha` / `Security Verification` / `Drag the arrow` **任一 → 立即 `break` 整批、不要重试**
    （重试只会加重风控）；单篇 `subprocess.TimeoutExpired` **必须捕获**，只记 error 继续下一篇
    —— v1 脚本未捕获 → 整批崩掉、已扫结果险些白跑。
  - 扫完**必跑** `_tab_guard.py --clean`：`get-feed-detail` 每次自建 tab 且不关，54 篇积 **53 个残骸**。
  - 新脚本：`_scan_0916_night2.py`（节流 + 熔断 + 单篇异常不中断）、`_merge_notes_src.py`。

- v1.14.0 (2026-09-17 凌晨) —— **铁律 19「只巡检 2 天内发布的笔记」** + **铁律 20「扫描清单须合并历史快照」**：
  - 19（用户原话「**评论只需要关注 2 天以内发布的，不要追溯更久远的**」）：
    过滤维度是**笔记的发布时间**，不是评论时间（`--since YYYY-MM-DD`，字符串比较即可）；
    更老的笔记即使有未回评论也**不追** —— 读取本身吃风控额度（见铁律 18），
    为几年前的笔记赔上验证码不划算。与铁律 7 的 36 小时**评论**窗口**不冲突**：
    **19 先定候选笔记，7 再在候选内筛评论**。例外：用户点名的单篇 → 手工指定 note_id 单独扫。
  - 20：列表接口**单次只出 100 条** —— 新抓快照最旧只到 9/14 18:48，
    而评论最多的「上海AI Agent活动9月17」（9/14 18:15 发）**正好落在 100 条之外**；
    必须合并历史快照去重（`_merge_notes_src.py`，本次 100+197 → **253 条**）后再扫。
  - 同批补登：本轮 `check_patch_versions.py` 查出 **INDEX 版本列仍 1.13.0**
    （版本漂移**第三次复现**，已修 1.14.0）；新建 `refs/04-delete-and-render.md`
    承载「删除链路与页面渲染坑」—— `refs/01` 已 8898/9000 触顶，不能再加。

> 📦 **早期版本记录（v1.15.0 / v1.17.0 / v1.19.0）** 已外移到 `refs/07-changelog-archive.md`。

> 📦 **更早期的版本记录（v1.6.0 及之前、v1.0.0~v1.11.0 摘要）**
> 已外移到 `refs/07-changelog-archive.md`（本文件触 9000 字符上限）。
