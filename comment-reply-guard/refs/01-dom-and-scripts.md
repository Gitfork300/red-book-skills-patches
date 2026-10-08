> read_when: 需要评论/私信的具体 DOM 结构、选择器、CDP 抓取写法、脚本参数时
> 本文件是 `SKILL.md` 的展开，规则结论仍以 SKILL.md 为准（system: comment）。

# comment-reply-guard / refs — DOM 与脚本细节

## 一、能力盘点（命令与依赖）

| 能力 | 命令 | 依赖 |
| --- | --- | --- |
| 读笔记评论（含二级回复） | `get-feed-detail --load-all-comments --limit 30 --click-more-replies --reply-limit 10` | 需主页登录态 + `feed_id` + `xsec_token` |
| 回复指定评论 | `respond-comment --feed-id … --comment-id … --content …` | 同上 |
| 发一级评论 | `post-comment-to-feed` | 同上 |
| 通知「评论和@」 | `get-notification-mentions` | 需主页登录态 |
| 私信（DM） | 无现成命令，走 CDP 直操作 `/chat` 页 | 需主页登录态 |

## 二、头号坑：`--comment-id` 必须带 `comment-` 前缀

评论容器 DOM：

```html
<div class="comment-item" id="comment-6aa7ecf00000000014039a8d">
```

接口返回 `comment_id` 是纯 id `6aa7ecf00000000014039a8d`。`respond-comment` 内部
`extractCommentId()` 取 DOM 属性原值（保留前缀），再 `id === targetId` 全等比较 → 传纯 id 永远匹配不上：

```
CDPError: Failed to locate reply target comment: target_comment_not_matched
```

**正确用法**（把前缀带上）：

```bash
python scripts/cdp_publish.py respond-comment \
  --feed-id <FEED_ID> --xsec-token <XSEC> \
  --comment-id "comment-<纯comment_id>" \
  --content "回复内容"
```

成功返回有 `matched_author` / `matched_text_preview`，据此确认定位到对的人。

**备选定位**（拿不到 id 时）：`--comment-author`（+30 分）/ `--comment-snippet`（+20 分），
但都是模糊匹配，同文案重复时易回错人，能用 id 就别用。

## 三、二号坑：回复按钮是 svg（无"回复"文本）

实测 3 条评论 `respond-comment` 只成功 1 条，另两条报 `reply_button_not_found`。
根因：`findReplyControl()` 靠 `textContent === "回复"` 找按钮，但小红书回复控件是 svg 图标：

```html
<div class="reply icon-container">
  <svg class="reds-icon reply-icon" ...><use href="...#reply"></use></svg>
  <span class="count">1</span>
</div>
```

评论 `innerText` 只有 `昵称 / 内容 / 时间地点 / 赞 / 1`，**没有"回复"**。
偶尔成功是 `click_more_replies` 展开二级后页面里才出现"回复"字样，属碰运气。**别 hover**（实测无效）。

**正确解法（v2 回复器）**：

```js
var el = document.getElementById('comment-<cid>');
var rc = el.querySelector('div.reply.icon-container')
      || el.querySelector('[class*="reply"][class*="icon"]')
      || el.querySelector('svg.reply-icon');
(rc.tagName === 'svg' ? rc.parentElement : rc).click();
```

- 输入框 = `P.content-input`（contenteditable）
- 填充：`el.innerText = txt` + `dispatchEvent(new InputEvent('input',{bubbles:true}))`
- 发送：找 `innerText === '发送'` 的按钮点击
- 参考实现：`xhs_publish/comment/_reply_v2.py`（已跑通，2/2）

> 发送后仍必须回读验证（`_verify_v2.py`）：重拉 `get-feed-detail`，确认 `subComments` 出现我方回复。

## 四、`/you/mentions` 接口直取 id（首选定位）

通知页背后调用 `https://edith.xiaohongshu.com/api/sns/web/v1/you/mentions?num=20&cursor=`，每条带：

| 字段 | 用途 |
| --- | --- |
| `item_info.id` / `item_info.xsec_token` | 笔记 note_id / xsec_token |
| `item_info.content` | 笔记标题 |
| `comment_info.id` / `comment_info.content` | 评论 id / 正文 |
| `time` | unix 秒（精确） |
| `user_info.nickname` | 评论人昵称 |

**怎么拿**（⚠️ 别用页面内 `fetch`）：

| 做法 | 结果 |
| --- | --- |
| 页面内 `fetch('/you/mentions')` | ❌ 406（缺 `x-s` 签名） |
| CDP：`Network.enable` → 重载 / 点「评论和@」→ 收 `Network.responseReceived` → `getResponseBody` | ✅ 成功 |

🔴 **事件循环要写对**：同一 `recv()` 循环里既路由 `id`（命令响应）又收集 `method`（事件）。
只在"等命令响应"时收消息、丢事件 → 一条都抓不到。参考实现：`xhs_publish/comment/_probe_notif_api3.py`（`Conn` 类）。

**局限**：只返回最新一页 20 条（cursor 翻页未验证）；实测曾漏 1 条；不含"是否已回复"。

## 五、通知页 DOM 一次抓全量（`_scan_notifications.py`）

读 `/notification` 页「评论和@」DOM，20 秒抓 56 条（3 天内 45 条）。要点：
- 默认停在「赞和收藏」tab，**必须先点「评论和@」**（`innerText==='评论和@' && children.length===0`）。
- 通知项最小容器：同时含「用户名+行为行+内容行」且不包含其他候选（`cands.filter(el => !cands.some(o => o!==el && el.contains(o)))`）。
- 时间 = 行为词之后的全部（"评论了你的笔记昨天 22:37" → `昨天 22:37`）。

**🔴 通知页只能发现、不能回复**：DOM 里 `a[href*="/explore/"]` 为空；点通知项主体/「回复」按钮均不跳转不展开。

**已知失败路径（别再踩）**：
| 尝试 | 结果 |
| --- | --- |
| 页面内 fetch `you/mentions` | 406 → 改用 CDP 抓响应体 |
| 页面内 fetch content-data | 406；每页固定 10 条（164 篇 = 17 页） |
| `notes-from-profile --profile-url /user/profile/me` | 返回 0 条（需真实 user_id） |

定位候选笔记：xsec 来自本地快照 `xhs_publish/logs/platform_notes_*.json`。
降成本：去掉 `--click-more-replies`、`--limit` 30→10~15、timeout 400→120。

## 六、mentions 首屏不全 + 二级评论展开控件

- **首屏只返回 6 条**（`num=6`），通知页 DOM 有 16 条，滚动分页累计 72 条。做法：reload → 点「评论和@」→ 循环滚动 8 轮 → 合并全部 mentions 响应按 `comment_info.id` 去重。参考实现：`xhs_publish/comment/_probe_mentions_all.py`（输出 `logs/mentions_all.json`）。
- **二级展开控件 = `.show-more`**，文本「展开 1 条回复」**含空格** → 正则 `展开\s*\d+\s*条回复`（`展开\d+条回复` 一条都点不到）；且二级可能不在首屏，先循环「点 `.show-more` + 滚到底」再按 id 定位。

## 七、私信（DM）选择器与判据

| 项 | 值 |
| --- | --- |
| 私信页 URL | `https://www.xiaohongshu.com/chat`（非 `/im`） |
| 会话条目 | `.xhs-im-conv-item`（子元素带 `__` 后缀，须过滤） |
| 消息区 | `.xhs-im-msg-list-wrap` |
| 输入框 | `div.xhs-im-input-bar-editor`（contenteditable） |
| 发送 | **Enter 键**（见下方「输入与发送」；❌ 点发送按钮实测无效） |
| 会话 ID | `el.getAttribute('data-conv-id')`；单会话 = `/chat/<conv-id>` |

- **我方消息判据 = `.chat-item__bubble--me`**（对方 = `--other`）；`.chat-item` 本身不带左右标记。
- **首选定位 = 按 `data-conv-id` 导航直达**；❌ 点列表会大面积失败（虚拟滚动 + 已读重排，62 个候选后 30 个 `notfound`）。
- 抓列表前必须 `navigate` 到**不带 id 的 `/chat`**（带 id 时列表被过滤）；抓列表边滚边累积去重（`scrollTop += 620`）。

### 输入与发送（2026-09-25 实测，🔴 与旧版不同）

- ❌ **`Input.insertText`（CDP）会「假成功」**：文本确实写进 DOM、`innerText` 校验也通过，
  但 **React 受控状态没更新** → 点发送/按 Enter 都无任何反应、**消息根本没发出**，
  若不复读核验就会误记为"已回"。
- ✅ 正解三步：`el.focus()` → `document.execCommand('insertText', false, MSG)` →
  校验 `innerText` 含关键片段 → **`Input.dispatchKeyEvent` 发 Enter**
  （`keyDown` + `keyUp`，`windowsVirtualKeyCode=13`, `nativeVirtualKeyCode=13`, `text="\r"`）。
- ❌ **不要点 `.xhs-im-input-bar-action-btn`**：实测点击后消息数不变（即使 `disabled=false`）。
- 旧版写的 `el.innerText = txt` + `InputEvent('input')` 未在本轮复测，**优先用 execCommand 方案**。
- **发送后必须复读核验**：重读 `.xhs-im-msg-list` 最后一条，确认 `--me` 且文本**逐字全等**。
- 🔴 **凡动过「发送」动作的脚本，包括探针 / diag，都必须写回统一台账**
  （如 `_dm_results.json`）：2026-09-25 有一条私信是在 `_patrol_dm_diag.py` 里验证
  execCommand+Enter 时发出的（bubbles 1→2、`last_is_me=true`，确实发成功），
  但没落进结果文件 → 汇总按文件数得 14，实际会话覆盖是 15，**计数口径差 1**，
  险些误判成「还有 1 条没回」。规则：**脚本名字不重要，发过就要记。**

### 笔记评论定位（mentions 406 / profile DOM 不渲染时的替代路径，2026-09-25 实测）

1. `cdp_publish.py search-feeds --keyword "<笔记标题>"` → 结果 `feeds[]` 含 **`xsecToken`**，
   按自己的 `note_id` 精确匹配取 token（profile 页与搜索页的 DOM 均可能返回 0 条，**不可用**）。
2. `get-feed-detail --feed-id <nid> --xsec-token <tok> --load-all-comments --limit 10`
   → `comments.list[]`（含 `id` / `content` / `subComments` / `userInfo.nickname`）。
3. 无 token 直接访问 `/explore/<nid>` → **404**（`error_code=300031`）。

**节奏**：间隔 32~44 秒/条，跨轮以「已成功名单」自动跳过（日志 `logs/dm_sent2.json`）。

### respond-comment 定位：`--comment-id` 可能失效，改用作者 + 片段（2026-09-25 实测）

- ❌ 把 `get-feed-detail` 返回的 `comments[].id` 传给 `--comment-id`，脚本拿它去比对 DOM
  `data-comment-id` → **对不上**，报 `CDPError: Failed to locate reply target comment:
  target_comment_not_matched`（rc=1）；加 `comment-` 前缀同样无效。
- ✅ 正解：`--comment-author <昵称>` + `--comment-snippet <评论正文片段>` 模糊定位，
  实测一次命中。`snippet` 取正文前 10~15 字、**只取纯文字**（带表情/换行会匹配失败）。
- 回复后复读核验：重读评论列表，确认**评论数 +1**、最后一条作者是自己、文本**逐字全等**。
- 失败即止，**不要连续重试**（重试容易落成一级评论，见第八节事故）。

## 八、🔴 头号事故：回复被发成「一级评论」（2026-09-16 实测）

**现象**：脚本报 `send: sent`，但回复没有挂在目标评论下，而是在笔记下**多出一条我方一级评论**（污染笔记、要逐条删）。

**根因（两处叠加）**：

1. **`el.click()` 对 React 组件无效** —— 和小红书回复/删除菜单都是 React 渲染的，
   合成 click 不触发 state 更新。必须用 CDP 真实鼠标事件：
   ```
   Input.dispatchMouseEvent mouseMoved → mousePressed → mouseReleased
   ```
   （与第五节「二级展开」同理，但回复图标**必须**真实事件，否则只是"聚焦"不进回复模式）
2. **输入框取错** —— 页面上有 2 个框：
   - `TEXTAREA.textarea`：视口外（`y≈-9000`），主评论框，**必须避开**
   - `P.content-input`：底部唯一可见输入框（未展开 162px，**进入回复模式后 327px**）

**正确流程（已验证 6/6 成功）**：

```
1. 打开笔记页 → 循环点 .show-more 展开二级 + 滚到底（4 轮）
2. 取目标评论内 .reply.icon-container 的坐标（不是 el.click()）
3. Input.dispatchMouseEvent 真实点击（moved/pressed/released）
4. 校验是否进入回复模式：底部 .engage-bar 的 innerText 含
   「回复 <昵称> <评论摘要>」  ← 没有这句就放弃，绝不能硬发
5. 填 P.content-input（最后一个可见的）：innerText + InputEvent('input')
6. 从该输入框的祖先逐层（lv0→lv4）找 innerText==='发送' 并点击
   （不要全页从后往前找，会点到主评论框的发送）
```

**判据要点**：
- **进入回复模式 = `.engage-bar` 出现「回复 @昵称」**，这是唯一可靠判据；
  「对比点击前后输入框数量」不可靠（页面可能本来就有 3 个框，或只是宽度变化）。
- **成功判据不能用 DOM 回读**：二级回复在 DOM 里是**兄弟节点**，
  `#comment-<cid>`.innerText 里搜不到我方昵称（实测 6/6 都 `not_found`，实际全成功）。
  ✅ 必须用 `cdp_publish.py get-feed-detail --load-all-comments --click-more-replies`
  看 `subComments` 里是否出现我方昵称。参考 `xhs_publish/comment/_check_reply_landing.py`。

**参考实现**：`xhs_publish/comment/_reply_0916b.py`（修复后版本）。

## 九、删除自己的评论（入口与流程）

- **入口**：`div.comment-delete-dropdown > svg.reds-icon.more`（"更多"图标，**svg 无文本**，
  与回复按钮同款，文本搜索找不到）。
- **打开方式**：同样必须**真实鼠标事件**（`el.click()` 无效，实测 hover 也不出菜单）。
- **菜单项文本 = 「删除评论」**（不是「删除」）→ 精确匹配，避免误点「举报」。
- **二次确认**：点「删除评论」后弹窗，确认按钮文本为「确定」。
- **安全**：删除前必须校验 `#comment-<cid>` 的第一行 innerText 是本号昵称，否则跳过。

**参考实现**：`xhs_publish/comment/_delete_0916.py`（带作者校验 + 菜单文本校验 + 回读验证）。

> 📦 **批量清理不合规存量评论 + 第二轮补删与判据修正**（原第九、十节之后的部分）
> 因本文件触上限已外移到 `refs/07-batch-cleanup.md`，内容完整保留。
