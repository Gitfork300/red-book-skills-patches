# 01 · 架构铁律与上游同步

> read_when: 要改本体源码、同步上游、判断 git 状态、处理 PRISTINE/DRIFTED 时
> 本文件是 `MEMORY.md` 第 1 节的展开。**结论以主文件为准**，这里放操作步骤与原理。

## 核心原则

> 改动放 patch；上游仅作参考、择优移植，**不要直接改受管运行层文件**。

## 目录职责

- 本体（执行层）＝ **`<patch>/runtime/`**（随 patch 分发，2026-10 起已不再依赖同级 `red-book-skills/`）
  - 9 个覆盖产物 = `core-overrides/overrides/` 的应用结果；先审查 dry-run，再决定是否 `apply`
- 定制全部在 `~/.workbuddy/skills/red-book-skills-patches/`
- 改本体的唯一路径：改 `core-overrides/overrides/` → `apply`

## 开工体检（2026-10-09 起）

```powershell
.\.venv\Scripts\python.exe tools\doctor.py      # 0=全通过 1=警告 2=阻断
```

一次串完 clean(自愈) → ensure_compatible → post_sync_check → check_patch_versions →
check_doc_layers → unittest → check_public_release。日常单跑 `ensure_compatible.py` 也可。
**`__pycache__/*.pyc` 已不进覆盖清单**（曾导致永久 DRIFTED、门禁卡死）；
遇到疑似卡死先跑 `apply_overrides.py clean`。

## 铁律

- 本仓库分发 `runtime/`；受管执行文件和权威覆盖副本需要保持一致。
- 不得用上游快照覆盖本仓库，也不得以 `checkout`、`reset` 或 `clean` 覆盖用户改动。
- 更新前先核对 Git 状态并保护本机状态、登录态和未提交修改。

## 同步动作序列（2026-09-14 修订）

```
update_check.py diff-local          → 评估映射差异，不自动覆盖
逐项审阅候选改动                    → 只移植经过批准的内容
apply_overrides.py apply --dry-run  → 检查影响
apply_overrides.py apply            → 应用已审阅的覆盖层
apply_overrides.py verify           → 校验覆盖副本与运行层
post_sync_check.py                  → 契约自检
运行测试和兼容门禁，再登记已采纳基线
```

`baseline.json` 记录参考源映射，不代表可覆盖许可。A2 的目录结构不同，禁止对
A2 快照使用旧布局的 `rebase --from` 或 `post_sync_check --upstream`；见 `UPGRADING.md`。

## 整文件覆盖的代价

替换整份文件意味着上游后续改动不会自动进入运行层；须逐项评估并移植。
契约清单 `core-overrides/contracts.json`：`we_add` = 我们的特征串，
`upstream_anchors` = **我们依赖的上游符号**（新增依赖必须补，否则上游删改时静默失效）。

覆盖清单（**9 个文件** = `INSTRUCTIONS.md` + 4 个 `references/*.md` + 4 个 `scripts/*.py`）：

| 文件 | 我们的改动 |
| --- | --- |
| `INSTRUCTIONS.md` | 运行层入口：铁律 + 流程顺序 + 索引 |
| `references/01-publish-flow.md` | 发布流程各闸门命令与判据 |
| `references/03-constraints.md` | 异常处置 / 不确定提交 / 风控误判（mixed） |
| `references/04-pitfalls.md` | 我们的踩坑（视频方向 / `--preview` / 沙箱） |
| `references/05-patches-upstream.md` | Patch 索引、触发词、上游更新 |
| `scripts/cdp_publish.py` | 发布按钮三级激活重试 |
| `scripts/chrome_launcher.py` | Windows 脱离 job object |
| `scripts/publish_pipeline.py` | 接 interval-guard record |
| `scripts/run_lock.py` | 发布进程互斥 |

## 改一条规则时要同步哪些副本（2026-09-15 实测）

同一条规则在本仓**至少 6 处**有副本 —— 只改一两处，规则会自相矛盾。
2026-09-15 改「天气配额」时第一遍只改了 patch 的 2 个文件、**漏了 6 处**，靠全仓 grep 才补齐。
固定动作：

1. **先全仓 grep 规则关键词**（如「每日至多 1 篇」「quota_check」），覆盖：
   patch 各 `SKILL.md` / `helpers/`、`core-overrides/overrides/`、本体、
   工作区 `MEMORY.md` + `topics/`、`INDEX.md`
2. **区分 LIVE 与快照**：历史快照已移至 `C:/xhs/_skill-backup/skill-scan-exclusions/legacy-collisions-20261107/core-overrides-state-backup/`；`_archived_*` 是历史快照，**不改**。不要把含 `SKILL.md` 的旧备份放回技能扫描树。
3. **改动顺序**：patch 正文 → `INDEX.md`（表格版本列 + 修改记录）→ `core-overrides/overrides/`
   → `apply --dry-run` → `apply` → `verify` → 工作区 `MEMORY.md` / `topics/`
4. **各 patch 的 `修改记录` 段是历史，不要改**（除非在修正历史事实本身）
5. 改完**再 grep 一遍**，确认旧措辞只剩在历史记录与快照里

⚠️ `INDEX.md` 的 **patch 列表「版本」列容易落后**（2026-09-15 实测：表里 `timeliness-window` 写 1.3.0，
实际 `SKILL.md` 已是 1.6.0；`publish-preflight-guard` 写 1.11.0，实际 1.13.0）。
动任何 patch 时顺手核对该行版本。

## 自动化

- update-checker 间隔 **5 天**（432000）+ 每周五 10:00 automation `7d437f5c`
  - ⚠️ **间隔必须显著小于触发周期（7 天）**：`check` 在「距上次 < 间隔」时
    **静默 exit 0 且不写状态**，间隔贴着 7 天设会退化成两周真查一次，且外面看不出来
  - 别手工跑 `check` 后不看 `status` —— 会把 `last_check` 推后，可能让下个周五被跳过
- 快照 automation `cb3d513f` 每日 23:00 → `~/Documents/red-book-skills-backup/`
  - ⚠️ **白天不手动备份**（automation 已覆盖）
- 失败双告警：备份目录写 `FAILED.txt` + 桌面 txt
- Agent Mail 已 connected（2026-09-13）

## 文档分层（2026-09-14 新增）

md 文件按三层拆分，规范见 `red-book-skills-patches/DOC_LAYOUT.md`，
校验脚本 `tools/check_doc_layers.py`（检查字数上限、索引断链、孤儿文件、**关键锚点是否丢失**）。

拆任何 md 之前先读 `DOC_LAYOUT.md`；**拆完必须跑校验 + 人工三版对照**（该文件第九节）。

覆盖层是受管文件的权威副本；`apply` 按完整文件覆盖运行层，更新前必须审查差异。
具体命令和执行参考以本仓库 `runtime/` 和根目录文档为准，不假设上游自动同步。


## 本体可移植性（2026-09-17 从 MEMORY.md 外移）

完整安装须包含本仓库运行层、覆盖层、Patch、工具和依赖；
patch 改动须成对同步（改规则全仓 grep LIVE 副本）。
