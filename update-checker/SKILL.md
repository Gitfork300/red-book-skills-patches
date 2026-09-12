---
name: update-checker
version: 1.1.0
patch_for: red-book-skills
applies_to_main_version: ">=0.1.0"
priority: 5
author: Eric (定制)
created: 2026-09-04
---

# update-checker

> Patch：定期检查上游 `aus666666/red-book-skills` 仓库是否有更新。
> 适用范围：所有 red-book-skills 安装实例。

## 为什么需要

- 原仓库会更新，patch 是叠加在主 skill 之上的独立 skill——更新检查让用户**及时**知道何时需要重新合并 patch。
- agent 不主动检查会"忘了"，必须由脚本定时跑。
- 不能自动合并——更新可能引入不兼容变更，必须人工决策。

## 加载方式

主 skill 顶部 `Loaded patches` 段会引用本 patch。
本 patch 自包含 `helpers/update_check.py`，可直接调用。

## 触发方式

### 1. 周期自动化（推荐）

由 WorkBuddy 自动化每周触发（已注册，cron 详见 `../.workbuddy/automations/`）。
自动化 prompt 调用本 patch 的 helper（见下）。

### 2. 手工触发

```bash
# 距上次检查 >= 间隔才执行
python <patch>/helpers/update_check.py check

# 强制立即检查（忽略间隔）
python <patch>/helpers/update_check.py check-now

# 查看状态
python <patch>/helpers/update_check.py status

# 内容级对比：拉上游快照，逐文件比对本地 skill（忽略行尾/BOM 假阳性）
python <patch>/helpers/update_check.py diff-local

# 对比结果打 JSON（供自动化/脚本消费）
python <patch>/helpers/update_check.py diff-local --json

# 调整检查间隔（默认 604800 = 7 天）
python <patch>/helpers/update_check.py set-interval 604800

# 标记已读（避免重复提醒）
python <patch>/helpers/update_check.py acknowledge --sha <commit-sha>
```

### 为什么需要 `diff-local`

只订阅 commit sha 只能回答"上游动没动"，回答不了"这次改动会不会砸到我的本地定制"。
本地 `red-book-skills` 是**拷贝安装（无 `.git`）**，且叠加了若干本地增强
（发布按钮三级重试、Windows 沙箱下 Chrome 脱离 job object、发布间隔记录等）。
`diff-local` 下载上游 tarball 做内容级比对，输出四类结果：

| 分类 | 含义 | 处置 |
| --- | --- | --- |
| 相同 | 双方一致 | 无需动作 |
| 内容不同 | 本地定制 或 上游已改 | **逐项 diff 判断**，不能整体覆盖 |
| 仅上游有 | 上游新增文件 | 评估是否引入 |
| 仅本地有 | 本地增补 / 运行时产物 | 保留；运行时产物可清 |

**必须忽略行尾差异**：Windows 副本是 CRLF、上游是 LF，不归一化会导致
几乎所有文件被误报为"不同"。脚本已内置归一化（统一行尾 + 去 BOM），
并跳过 `.venv`/`tmp`/`__pycache__`/`.pytest_cache` 等运行时目录。

## 行为规范

### 检测源

按以下顺序尝试，首个成功者为准：

1. `https://api.github.com/repos/aus666666/red-book-skills/commits?per_page=1`
2. `https://api.github.com/repos/aus666666/red-book-skills/commits?per_page=1&sha=master`
3. `git ls-remote https://github.com/aus666666/red-book-skills.git HEAD`（仅当 git 可用）

### 状态文件

`state/update_state.json`：

```json
{
  "last_check_epoch": 1725450000,
  "last_check_iso": "2026-09-04T16:54:55+08:00",
  "last_check_status": "ok | network_error | rate_limited",
  "last_known_sha": "abc123...",
  "last_known_iso": "2026-09-01T10:00:00+08:00",
  "last_known_message": "fix: ...",
  "last_notified_sha": "abc123...",
  "interval_sec": 604800
}
```

### 退出码

| 退出码 | 含义 |
| --- | --- |
| 0 | 无需检查（距上次 < 间隔）/ 已是最新 / `diff-local` 判定本地与上游完全一致 |
| 1 | 有可用更新；或 `diff-local` 检出差异（**注意：有本地定制时属正常**） |
| 2 | 网络错误（已写入 state.last_check_status=network_error）；`diff-local` 下载/解压失败或本地目录不存在 |
| 3 | API 限流（已写入 state.last_check_status=rate_limited） |

### 重要原则

- **只读**：本脚本从不修改主 skill 或 patch 文件（`diff-local` 也仅在系统临时目录解压）
- **不自动合并**：检测到更新只通知，不动手
- **重复提醒抑制**：距离上次成功提醒 < 1 天时不再重复输出
- **优雅降级**：无网/限流时退出 2/3，不影响其他流程
- **`diff-local` 退出码 1 不等于有问题**：只要本地有定制，退出码必然是 1；应看清单内容而非退出码

## 与主 skill 的冲突点

- **无**。本 patch 只读 GitHub API，不触碰本地文件。

## 配合使用（更新发现后如何合并）

1. 看到 `UPDATE_AVAILABLE` 提示后，先跑 `diff-local` 看清**上游到底改了哪些文件**，
   再对比 `state/update_state.json` 中的 `last_known_message`
2. 决策：
   - **更新影响小**（仅文档/示例）→ 直接覆盖对应文件（注意保留本地增强）
   - **更新影响 patch 范围** → 查 `patches/*/META.json` 的 `applies_to_main_version` 是否还满足
   - **更新含 BREAKING**（如 `scripts/cdp_publish.py` 改了关键签名）→ 暂停使用，联系 patch 作者适配
3. **切勿整体覆盖本地 skill**：本地若已有增强（见下表），覆盖即回退
4. 合并完成后执行 `acknowledge --sha <新 sha>`，避免重复提醒
5. 复核：再跑一次 `diff-local`，确认只剩预期中的定制差异

### 已知本地增强（截至 2026-09-12）

| 文件 | 本地改动 | 若被覆盖的后果 |
| --- | --- | --- |
| `scripts/cdp_publish.py` | 发布按钮三级激活重试（组件事件 → 真实鼠标 → 键盘 Enter） | 发布按钮被 Creator Center 换监听后静默失败 |
| `scripts/chrome_launcher.py` | Windows 下 Chrome 脱离 job object（`CREATE_BREAKAWAY_FROM_JOB` 等） | 启动器退出后 9222 端口约 5 秒内死掉 |
| `scripts/publish_pipeline.py` | 接入 `publish-interval-guard`，发布成功后写间隔记录 | 批量发布时间隔守卫查不到记录，误判可立即发布 |
| `SKILL.md` | 合并各 patch 规则（封面规范/写作规范/间隔/时效地域/用词） | 所有 patch 规则失效 |

## 修改记录

- v1.1.0 (2026-09-12) 新增 `diff-local` 子命令：拉上游快照做内容级对比，
  内置行尾/BOM 归一化，输出四分类差异；补记本地增强清单
- v1.0.0 (2026-09-04) 初版
