---
name: core-overrides
system: shared
version: 1.5.4
description: "bundled runtime 的权威覆盖层：apply/verify/status 三态管理，页签全局守卫（9222+9333 合计≥10 回收至≤9）。改 runtime 必须走本 patch。触发词：apply 覆盖、DRIFTED、页签清理、tab 堆积。"
patch_for: red-book-skills
applies_to_main_version: ">=0.1.0"
priority: 2
author: Project maintainers
created: 2026-09-12
---

# core-overrides

> Patch：bundled runtime 的源码覆盖层。存放**我们自己对执行脚本和运行说明的修改**的权威副本。
> 独立运行层位于本仓库 `runtime/`，不要求另装同级 skill。

## 为什么需要

用户定下的架构原则：

> **我们自己的更新放 patch；可信 Fork 由用户单独维护，定期评估后只合并批准的改动。**

要落实这句话，必须解决一个矛盾：

- 发布可靠性、沙箱适配这类改动必须存在于可执行的 runtime 文件中——
  Python 不会自动 import 一个说明文档里的实现。
- runtime 随 Patch 一起分发；权威副本与应用产物分开，方便复核和重放。

本 patch 的做法：**权威副本放 `overrides/`，bundled runtime 里那份只是"应用产物"**。

```
改我们的东西  → 改 core-overrides/overrides/  → apply 到 runtime/
评估 A2 更新  → 只移植批准的改动 → apply（不拉取、不全量覆盖）
```

这样覆盖文件的改动可以通过权威副本重放；仍禁止整包覆盖，避免丢失上游未审核变更。

## 加载方式

日常先加载根级 `SKILL.md`，再由其运行 `tools/ensure_compatible.py`。
门禁通过后使用仓库内 `runtime/scripts/`。`apply` 将覆盖复制到 `runtime/`；
根级 `SKILL.md` 是独立入口，`runtime/INSTRUCTIONS.md` 是详细操作规则。

## 覆盖清单

| runtime 文件 | 我们的改动 | 不应用会怎样 |
| --- | --- | --- |
| `INSTRUCTIONS.md`（上游 `SKILL.md`） | 合并各 patch 规则（封面规范/写作规范/间隔/时效地域/用词/预检） | 所有 patch 规则失效 |
| `scripts/cdp_publish.py` | 发布按钮三级激活重试（组件事件 → 真实鼠标 → 键盘 Enter）；**页签守卫**：9222+9333 全局 page tab ≥10 自动回收最旧残留（发布实例留最新 3/评论实例留最新 1） | 按钮监听被换后静默失败，笔记不提交；tab 无界堆积吃内存并助推 Chrome 崩溃（B-056/B-057） |
| `scripts/chrome_launcher.py` | Windows 下用 `CREATE_BREAKAWAY_FROM_JOB` 等让 Chrome 脱离 job object | 启动器退出后 9222 端口约 5 秒内死掉 |
| `scripts/publish_pipeline.py` | 接入 `publish-interval-guard`，发布成功后写间隔记录 | 间隔守卫查不到上次记录，误判可立即发布 |

## 目录结构

```
core-overrides/
├── SKILL.md               本文件
├── META.json
├── baseline.json          A2 一对一/映射源的评估哈希（行尾归一化后）
├── overrides/             权威副本（脚本和参考文件映射到 runtime/）
│   ├── INSTRUCTIONS.md      （上游 SKILL.md；2026-10-30 起改名，避免被注册成独立技能）
│   ├── references/
│   └── scripts/
│       ├── cdp_publish.py
│       ├── chrome_launcher.py
│       ├── publish_pipeline.py
│       └── run_lock.py
├── state/                  运行状态（applied.json，仅本机，不入库）
└── helpers/
    ├── apply_overrides.py
    └── tab_guard.py        页签守卫独立版（双实例全局 ≥10 回收至 ≤9）
```

> apply 前的本体备份**不在** `state/backup/`（2026-10-07 起）：
> 落在 `C:/xhs/_skill-backup/core-overrides-preapply/<时间戳>/`。
> 移出技能树的原因：扫描器递归扫 `skills/**/SKILL.md` 并按 `name` 注册，
> 备份的 SKILL.md 与本体同名 → 列表出现多条同名技能，且备份是旧版，
> 加载到哪份不确定。改位置用环境变量 `RED_BOOK_OVERRIDES_BACKUP_DIR`。

## 用法

```bash
# 查看 bundled runtime 每个覆盖文件的状态
python <patch>/core-overrides/helpers/apply_overrides.py status

# 校验 runtime == 覆盖层（不一致退出 1）
python <patch>/core-overrides/helpers/apply_overrides.py verify

# 应用覆盖（自动备份原文件到 C:/xhs/_skill-backup/core-overrides-preapply/）
python <patch>/core-overrides/helpers/apply_overrides.py apply --dry-run   # 先看会改什么
python <patch>/core-overrides/helpers/apply_overrides.py apply

# 看某个文件「本体 → 覆盖层」的差异
python <patch>/core-overrides/helpers/apply_overrides.py diff scripts/chrome_launcher.py
```

## 状态含义

| 状态 | 含义 | 处置 |
| --- | --- | --- |
| `APPLIED` | runtime 已应用权威版本 | 正常态，无需动作 |
| `PRISTINE` | runtime 是所记录的原版 | 同步后尚未 apply → 跑 `apply` |
| `DRIFTED` | 既非权威版本也非基线 | **有人直接改了 runtime** → 先审查并保存改动，再修复 |

退出码：`status` 0=全部 APPLIED / 1=存在非 APPLIED / 2=错误；`verify` 0=一致 / 1=不一致。

## 铁律

1. **不要直接改本体**。改 `overrides/`，再 `apply`。直接改会让状态变成 `DRIFTED`。
2. **`apply` 前先 `apply --dry-run`**，确认要覆盖哪些文件。
3. `apply` 会自动备份原文件到 `C:/xhs/_skill-backup/core-overrides-preapply/<时间戳>/`，出问题可从那里回滚。
4. 想撤销某个覆盖 → 从 `overrides/` 删掉该文件，再 `apply`（或手动还原备份）。

## 页签守卫（B-057；v1.5.0 升级为全局上限）

`cdp_publish._find_or_create_tab` 每次发布都 `PUT /json/new` 建新 tab 却从不 `/json/close`，
一天堆 30+ 个 page tab（吃 ~2GB 内存）并助推 Chrome 崩溃（B-056）。已在覆盖层内建自动回收。

**用户铁律（2026-10-25）：「任何阶段的浏览器页签都不要超过 10，避免卡顿」**——
9222 评论实例 + 9333 发布实例**合计** ≤ 10（旧版只卡单实例 10，合计仍可到 20）。

| 项 | 值 |
| --- | --- |
| 触发 | 全局合计 page tab **≥ 10**（新建 tab 前） |
| 动作 | 回收至全局 **≤ 9**（给即将新建的 tab 留 1 个余量），保证新建后仍 ≤ 10 |
| 保留 | 9333 保留**最新 3** 个（发布/verify 在用的 tab 永远最新，旧的均为残留）；9222 保留**最新 1** 个（notification 着陆页） |
| 保护 | `creator.xiaohongshu.com/login`（可能正用于人工扫码）——**不关闭**；每实例至少留 1 个 page（关掉最后一个 tab 会导致 Chrome 整体退出） |
| 顺序 | `/json/list` 返回顺序 = 创建顺序（最早在前），只回收保留数之后的旧页，全局最旧优先 |
| 时机 | `_find_or_create_tab` 取完快照、尚未建立 WebSocket 时 → 不会关掉本轮正在连的页 |

**链运行中同样安全**，不必等停链（旧做法 `xhs_publish/_clean_creator_tabs.py` 按前缀清空、
必须停链后跑，已被本守卫取代）。独立版供收口 / 巡检 / 人工处置（默认双实例全局口径）：

```bash
python <patch>/core-overrides/helpers/tab_guard.py                      # 只读报告（双实例全局）
python <patch>/core-overrides/helpers/tab_guard.py --apply              # 执行全局清理
python <patch>/core-overrides/helpers/tab_guard.py --port 9222          # 只管评论实例（单实例模式）
```

评论链路另有一份同策略的项目层脚本：`xhs_publish/comment/_tab_guard.py`（`--clean` 执行清理）。

退出码：0 = 未超阈值 / 已清理；1 = 超阈值（只读模式提醒需清理）；2 = Chrome 不可达。

## 更新上游后怎么办

当前可信参考源 A2 与本地 runtime 目录结构不一致。**不得**把 A2 快照传给
`rebase --from` 或 `post_sync_check.py --upstream`；请按 [`UPGRADING.md`](../UPGRADING.md)
手动评估和移植。

1. 用 `update-checker/helpers/update_check.py diff-local` 评估 Fork 的映射差异；不自动覆盖。
2. 逐项评估并适配；受管文件先改 `overrides/`，其他运行文件按需同步。
3. 审查 `apply --dry-run`，再 `apply` → `verify` → `post_sync_check.py`（不传 A2 快照），运行回归测试。
4. 完成评估并记录采纳与不采纳理由后，按 `UPGRADING.md` 登记参考基线和确认提交。

## 与主 skill 的冲突点

- **就是它的本身职责**：本 patch 覆盖运行说明、发布脚本和参考文件。
- 与其他 patch 的关系：`SKILL.md` 的覆盖内容里**包含**其他 patch 的规则；
  其他 patch 若修改 `SKILL.md` 的规范，需同步更新本 patch 的 `overrides/INSTRUCTIONS.md`。

## 修改记录

- v1.5.4 (2026-11-06)：统一 A2 移植步骤并修正受管发布流程中的过期评级块要求。

- v1.5.0 (2026-10-25) 页签守卫**升级为全局上限**（用户铁律「任何阶段浏览器页签 ≤10，避免卡顿」）：
  9222+9333 合计 ≥10 即回收至 ≤9；9333 保留最新 3、9222 保留最新 1；login 仍受保护、
  每实例至少留 1 页；www 不再受保护（评论实例残留即回收对象）。`helpers/tab_guard.py`
  同步改全局口径（默认双实例，`--port` 退化为单实例模式）；项目层新增同策略的
  `xhs_publish/comment/_tab_guard.py`。
- v1.4.0 (2026-10-17) 页签守卫（B-057 根治）：`cdp_publish` 内建「page tab > 20 自动关闭最早 15 个」
- v1.4.1 (2026-10-17) 页签守卫**参数收紧**（用户拍板）：阈值 `TAB_GUARD_MAX` 20→**10**、每次关闭数 `TAB_GUARD_CLOSE` 15→**8**；保护页规则与触发时机不变。
  （login / www 页受保护），新增独立 helper `helpers/tab_guard.py`。
- v1.2.0 (2026-10-08) 覆盖目标切到随仓库分发的 runtime；A2 仅作评估源，运行不再依赖同级 skill。
- v1.1.0 (2026-10-08) 支持 `rebase --paths`，让覆盖层基线只推进已审核并合入的文件。
- v1.0.0 (2026-09-12) 初版。从本体抽出 4 个被直接修改的文件（约 470 行我们的改动），
  建立覆盖层 + 基线指纹 + apply/verify/status 工具
