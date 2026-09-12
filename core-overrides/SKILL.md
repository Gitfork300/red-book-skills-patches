---
name: core-overrides
version: 1.0.0
patch_for: red-book-skills
applies_to_main_version: ">=0.1.0"
priority: 2
author: Eric (定制)
created: 2026-09-12
---

# core-overrides

> Patch：本体文件覆盖层。存放**我们自己对主 skill 源码的修改**的权威副本。
> 适用范围：所有 red-book-skills 安装实例。

## 为什么需要

用户定下的架构原则：

> **我们自己的更新放 patch，原始本体定期和 GitHub 同步。**

要落实这句话，必须解决一个矛盾：

- 发布可靠性、沙箱适配这类改动**必须落在本体文件里才有用**——
  Python 不会去 import 一个 patch 目录，Chrome 启动器也不会读 patch 里的
  `chrome_launcher.py`。
- 但只要改动写在本体里，本体就"脏"了：分不清哪些行是上游的、哪些是我们的，
  一旦从 GitHub 同步（整包覆盖）就全丢。

本 patch 的做法：**权威副本放 patch，本体里那份只是"应用产物"**。

```
改我们的东西  → 改 core-overrides/overrides/  → apply
同步上游     → 覆盖本体 → apply（我们的改动自动回来）
```

这样本体可以被随意覆盖，我们的改动不会被冲掉。

## 加载方式

主 skill 顶部 `Loaded patches` 段会引用本 patch。
**本 patch 的 `apply` 是让所有其他 patch 规则生效的前提**——因为主 `SKILL.md`
本身就在覆盖清单里（各 patch 的规则被合并进了 SKILL.md）。

## 覆盖清单

| 本体文件 | 我们的改动 | 不应用会怎样 |
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
├── baseline.json          每个覆盖文件的上游基线 sha256（行尾归一化后）
├── overrides/             权威副本（与本体相对路径一致）
│   ├── SKILL.md
│   └── scripts/
│       ├── cdp_publish.py
│       ├── chrome_launcher.py
│       └── publish_pipeline.py
├── state/backup/<时间戳>/  每次 apply 前自动备份本体原文件
└── helpers/apply_overrides.py
```

## 用法

```bash
# 查看本体每个覆盖文件的状态
python <patch>/helpers/apply_overrides.py status

# 校验本体 == 覆盖层（不一致退出 1）
python <patch>/helpers/apply_overrides.py verify

# 应用覆盖（自动备份原文件到 state/backup/）
python <patch>/helpers/apply_overrides.py apply --dry-run   # 先看会改什么
python <patch>/helpers/apply_overrides.py apply

# 看某个文件「本体 → 覆盖层」的差异
python <patch>/helpers/apply_overrides.py diff scripts/chrome_launcher.py
```

## 状态含义

| 状态 | 含义 | 处置 |
| --- | --- | --- |
| `APPLIED` | 本体已应用我们的版本 | 正常态，无需动作 |
| `PRISTINE` | 本体是上游原版 | 同步后尚未 apply → 跑 `apply` |
| `DRIFTED` | 既非我们的版本也非上游基线 | **有人直接改了本体** → 把改动搬进 `overrides/`，否则下次同步会丢 |

退出码：`status` 0=全部 APPLIED / 1=存在非 APPLIED / 2=错误；`verify` 0=一致 / 1=不一致。

## 铁律

1. **不要直接改本体**。改 `overrides/`，再 `apply`。直接改会让状态变成 `DRIFTED`。
2. **`apply` 前先 `apply --dry-run`**，确认要覆盖哪些文件。
3. `apply` 会自动备份原文件到 `state/backup/<时间戳>/`，出问题可从那里回滚。
4. 想撤销某个覆盖 → 从 `overrides/` 删掉该文件，再 `apply`（或手动还原备份）。

## 更新上游后怎么办

1. 覆盖本体（GitHub 同步）
2. `apply_overrides.py status` → 预期全部 `PRISTINE`
3. **先看上游是否也改过这些文件**：`update_checker.py diff-local`
   —— 它会读本 patch 的 `baseline.json`，把"上游改动过的被覆盖文件"标为**冲突**
4. 有冲突 → 人工把上游改动合并进 `overrides/`（再看 diff 决定）
5. `apply` → `verify` → 更新 `baseline.json` 的基线到新 commit

## 与主 skill 的冲突点

- **就是它的本身职责**：本 patch 覆盖 4 个本体文件。
- 与其他 patch 的关系：`SKILL.md` 的覆盖内容里**包含**其他 patch 的规则；
  其他 patch 若修改 `SKILL.md` 的规范，需同步更新本 patch 的 `overrides/SKILL.md`。

## 修改记录

- v1.0.0 (2026-09-12) 初版。从本体抽出 4 个被直接修改的文件（约 470 行我们的改动），
  建立覆盖层 + 基线指纹 + apply/verify/status 工具
