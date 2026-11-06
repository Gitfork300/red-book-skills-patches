# 页签三铁律与守卫护栏（32 / 8c / 32b / 32c 完整口径）

> 主入口 `../MEMORY.md` 只留速查行；细节在此。相关：`11-ops-playbook.md`（收尾流程）、`06-pitfalls.md`（B-104 事故）。

## 一、页签守卫两条护栏（10-27，B-107 / B-108，**已修 patch 层**）

主入口 `../MEMORY.md` 的 `32b` 只留一行指向。

### 1.1 B-107：匹配目标页签必须用**新鲜快照**
- **现象**：评论巡检抛 `CDPError: CDP receive failed while waiting for Page.enable:
  no close frame received or sent`；日志 `Reusing matching target tab: …/notification` → 连上 → 秒断。
- **根因**：`cdp_publish._find_or_create_tab()` 取 `pages` 快照 → 调 `_guard_tabs(pages)` 关页
  → **仍用那份过期快照**匹配 `target_url_prefix` 并返回其 `webSocketDebuggerUrl`；
  守卫刚把该页关掉，ws 地址已失效。
- **修法**：守卫跑完后**重新拉一次 `/json/list`**，并从**最新往回**匹配目标页签。

### 1.2 B-108：`/json/list` 顺序 ≠ 创建顺序 → 必须保护本轮目标页
- **现象**：B-107 修完仍连不上；日志 `tab_guard: 全局 page tab 12 ≥ 10，回收最旧 3 个`，
  而随后连的正是那条 `explore/<note_id>` 目标页 —— 它被当成「最旧页」关掉了。
- **根因**：守卫把 `/json/list` 返回顺序当作创建顺序（源码注释原文即如此论断，已更正）；
  实际 Chrome 的 `/json/list` 顺序**不保证**是创建顺序（页面 reload / tab 复用后会变），
  于是「保留最新 N 个」保留的并不是真正在用的那页。
- **修法**：`_guard_tabs()` 增加 `protect_prefix` 参数 —— **本轮要复用的目标页免回收**；
  调用点 `_find_or_create_tab()` 传入 `target_url_prefix`。
- **通则**：任何「按顺序回收最旧」的逻辑，**必须先保护本轮要用的目标**，
  不能依赖列表顺序推断新旧。

### 1.3 改 runtime 的标准流程（不可绕过）
1. 改动先写进 `core-overrides/overrides/scripts/cdp_publish.py`（**权威副本**）；
2. `core-overrides/helpers/apply_overrides.py apply --backup`
   （默认备份到 `C:/xhs/_skill-backup/core-overrides-preapply/<时间戳>/`；可用 `RED_BOOK_OVERRIDES_BACKUP_DIR` 覆盖）；
3. `tools/ensure_compatible.py --refresh` 门禁通过后才能调用 `runtime/scripts/*`。
- **DRIFTED 处置**：`ensure_compatible` 报「本体被直接改动」= runtime 里带着**手改但没回写
  overrides** 的内容（10-25 就发生过一次）。处置 = 先把改动搬进 overrides 再 apply，
  **不要**去 `clean` 本体。
- **WinError 5 处置**：`ensure_compatible.py` 末尾 rename `state/compatibility.tmp` 时被
  杀软/索引器瞬时占用 → `rm -f state/compatibility.tmp` 后重跑即可（B-109）。

### 1.4 起链不接管道 + 后台监测
- **起因**：起链命令接 `| tail -N` 会让 stdout **缓冲到进程结束才落盘**，
  盯盘期间看不到任何中间状态（本次连续两次误判「链卡死」）。
- **现状**：`_publish_chain_1026.py` 的 `print` 改为**同时落盘** `_chain_1026_run.log`；
  另建 `_monitor_1026.py` 后台监测：60s 轮询 `_1026_pub_progress.json`，
  新 `published` 即时落盘 `_chain_1026_monitor.log`，8 分钟无进展自动告警，
  全发完自动退出。
- **铁律**：**起链一律不接管道。**

### 1.5 巡检抓取工具（10-27 新增）
- `comment/_mentions_all_1027.py`（由 `_probe_mentions_all.py` 改输出路径生成）：
  mentions API **全量**抓取 —— 滚动通知页触发 cursor 分页 → 合并去重
  （实测 9 个响应 / 去重 180 条）。与 `comment/logs/reply_ledger_*.jsonl` 的已回复 cid
  求差集 → **精准定位新增待回评论**，避免翻通知页肉眼比对。
- 通知页 DOM 抓取（`_notif_items_1026pm.py`）只滚 6 轮 ≈ 116 条，
  **不足以覆盖全部新增**，必须与 mentions API 交叉验证。

---

## 二、页签三铁律（32 / 8c）



### 2.1 【32】全局 page tab ≤10（2026-10-25 用户铁律）
- **原话**：「任何阶段的浏览器页签都不要超过 10，避免卡顿」。
- **口径**：= **<PORT_COMMENT>（评论）+ <PORT_PUBLISH>（发布）合计**。旧口径只卡单实例 10，合计可到 20 → 已废弃。
- **自动回收**：`cdp_publish._guard_tabs` 在新建 tab 前检查合计，≥10 即回收至 ≤9：
  - **<PORT_PUBLISH> 留最新 3**（在飞发布 / verify 的 tab 永远最新）
  - **<PORT_COMMENT> 留最新 1**
  - `login` 页不碰；**每实例至少留 1 个 page**（关掉最后一个 tab 会导致 Chrome 整体退出）
  - `www` 域**不再受保护**（评论残留页即回收对象）
- **人工清理**：
  - `comment/_tab_guard.py`（默认只读，加 `--clean` 才关）
  - `core-overrides/helpers/tab_guard.py --apply`（默认双实例全局口径，`--port` 退化为单实例）
- **版本**：core-overrides 已升 **v1.5.0**。
- **已废止**：评论链「绝不碰 creator」的人工禁令 → 改为自动回收。

### 2.2 【8c】多步同页操作必须显式绑定 tab_id（B-104，2026-10-26）
- **现象**：`no title` 连败 —— 话题与提交动作**落到了错误的页签**。
- **根因**：<PORT_PUBLISH> 残留 publish 页签 + **`/json/list` 顺序 ≠ 刚填那页**（与 1.2 同源）。
- **修法**：多步同页操作**必须显式绑定 tab_id**：
  1. `fill` 之后按**标题锁定**页签
  2. `attach_topics` / `ai_decl` 传 `--tab-id`
  3. 提交直连该页签
- **已并入** `_publish_with_topics.py`（链脚本零改动即继承）。
- **待办**：此修复仍在**项目层** `xhs_publish/`，建议下次同步时上提 patch 层（须先过 `ensure_compatible.py`）。

### 2.3 【32b+32c】见上文第一章（页签守卫两条护栏 + 起链不接管道）
