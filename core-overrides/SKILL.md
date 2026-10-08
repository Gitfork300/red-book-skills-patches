---
name: core-overrides
system: shared
version: 1.2.0
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
| `SKILL.md` | 合并各 patch 规则（封面规范/写作规范/间隔/时效地域/用词/预检） | 所有 patch 规则失效 |
| `scripts/cdp_publish.py` | 发布按钮三级激活重试（组件事件 → 真实鼠标 → 键盘 Enter） | 按钮监听被换后静默失败，笔记不提交 |
| `scripts/chrome_launcher.py` | Windows 下用 `CREATE_BREAKAWAY_FROM_JOB` 等让 Chrome 脱离 job object | 启动器退出后 9222 端口约 5 秒内死掉 |
| `scripts/publish_pipeline.py` | 接入 `publish-interval-guard`，发布成功后写间隔记录 | 间隔守卫查不到上次记录，误判可立即发布 |

## 目录结构

```
core-overrides/
├── SKILL.md               本文件
├── META.json
├── baseline.json          A2 一对一/映射源的评估哈希（行尾归一化后）
├── overrides/             权威副本（脚本和参考文件映射到 runtime/）
│   ├── SKILL.md
│   ├── references/
│   └── scripts/
│       ├── cdp_publish.py
│       ├── chrome_launcher.py
│       ├── publish_pipeline.py
│       └── run_lock.py
├── state/                  运行状态（applied.json，仅本机，不入库）
└── helpers/apply_overrides.py
```

> apply 前的本体备份**不在** `state/backup/`（2026-10-07 起）：
> 落在 `~/xhs-workspace/_skill-backup/core-overrides-preapply/<时间戳>/`。
> 移出技能树的原因：扫描器递归扫 `skills/**/SKILL.md` 并按 `name` 注册，
> 备份的 SKILL.md 与本体同名 → 列表出现多条同名技能，且备份是旧版，
> 加载到哪份不确定。改位置用环境变量 `RED_BOOK_OVERRIDES_BACKUP_DIR`。

## 用法

```bash
# 查看 bundled runtime 每个覆盖文件的状态
python <patch>/core-overrides/helpers/apply_overrides.py status

# 校验 runtime == 覆盖层（不一致退出 1）
python <patch>/core-overrides/helpers/apply_overrides.py verify

# 应用覆盖（自动备份原文件到 ~/xhs-workspace/_skill-backup/core-overrides-preapply/）
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
3. `apply` 会自动备份原文件到 `~/xhs-workspace/_skill-backup/core-overrides-preapply/<时间戳>/`，出问题可从那里回滚。
4. 想撤销某个覆盖 → 从 `overrides/` 删掉该文件，再 `apply`（或手动还原备份）。

## 更新上游后怎么办

当前可信参考源 A2 与本地 runtime 目录结构不一致。**不得**把 A2 快照传给
`rebase --from` 或 `post_sync_check.py --upstream`；请按 [`UPGRADING.md`](../UPGRADING.md)
手动评估和移植。

1. 用 `update_checker.py diff-local` 评估 Fork 的逐文件改动；不自动拉取或覆盖。
2. 只同步审核通过的非覆盖文件。
3. 覆盖文件先把选中的上游改动合并进 `overrides/`，再显式列出这些路径运行 `rebase --from <Fork快照> --paths <文件...> --commit <新sha>`。省略 `--paths` 会拒绝推进基线。
4. `apply` → `verify` → `post_sync_check.py --upstream <Fork快照>`；未采纳的差异保留并继续告警。

## 与主 skill 的冲突点

- **就是它的本身职责**：本 patch 覆盖运行说明、发布脚本和参考文件。
- 与其他 patch 的关系：`SKILL.md` 的覆盖内容里**包含**其他 patch 的规则；
  其他 patch 若修改 `SKILL.md` 的规范，需同步更新本 patch 的 `overrides/SKILL.md`。

## 修改记录

- v1.2.0 (2026-10-08) 覆盖目标切到随仓库分发的 runtime；A2 仅作评估源，运行不再依赖同级 skill。
- v1.1.0 (2026-10-08) 支持 `rebase --paths`，让覆盖层基线只推进已审核并合入的文件。
- v1.0.0 (2026-09-12) 初版。从本体抽出 4 个被直接修改的文件（约 470 行我们的改动），
  建立覆盖层 + 基线指纹 + apply/verify/status 工具
