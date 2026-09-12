---
name: publish-interval-guard
version: 1.2.0
patch_for: red-book-skills
applies_to_main_version: ">=0.1.0"
priority: 20
author: Eric (定制)
created: 2026-09-04
---

# publish-interval-guard

> Patch：连续两篇笔记的发布间隔为 **8~12 分钟随机**（审核确认后起算），不得低于 8 分钟。
> 适用范围：所有 `publish` 流程。强制硬性约束，不靠 agent 记忆时间。

## 为什么需要

- 短时间内连发 = 平台风控/限流/封号高风险信号
- agent 自身的"时间感"不可靠（跨调用、上下文压缩、长任务等待都会失真）
- 必须把时间戳落盘、由脚本裁定
- **固定 10 分钟这种"整点节奏"本身就是机器特征**：每次发布后在 `[480, 720]` 秒之间抽一个目标间隔（8~12 分钟），节奏才像真人

## 加载方式

主 skill 顶部 `Loaded patches` 段会引用本 patch。
本 patch 自身不接管发布流程，仅在编排层显式调用时介入：

- **集成入口**：`xhs_login_wait.py`（windows-sandbox-workaround patch）通过环境变量 `XHS_INTERVAL_GUARD` 指向本 patch 的 `helpers/publish_interval.py`，自动在 publish 前 `wait`、publish 后 `record`
- **手工集成**：在 agent 编排层，发布前调 `wait`，发布成功且 `verify-note found:true` 后调 `record`

## 规则

### 间隔时长

| 模式 | 间隔 | 备注 |
| --- | --- | --- |
| **同一账号**连续发布（默认） | **8~12 分钟随机**，即 `[480, 720]` 秒 | 每次 `record` 时抽一个值写入 `next_gap`，由脚本锁定 |
| 固定间隔（可选） | `--interval N` | 覆盖随机；仅用于调试/回放 |
| **审核确认前** | 不计入 | 仅当 `verify-note` 返回 `found:true` 才视为可记录 |
| **发布失败** | 不计入 | 仅当 `publish` 返回 0 才记录 |

### 目标间隔的稳定性

- 目标间隔在 **`record` 那一刻抽签**并写入该条记录的 `next_gap`
- 单调 `check` / `wait` **不会重新抽签**，读到的一直是同一个数（否则等待过程会来回抖动）
- 旧记录没有 `next_gap` 时，脚本会自动补抽一个并落盘（迁移友好）
- **实际可见间隔 = 抽签目标 + 上一篇的发布耗时**（上传 + verify，实测约 20~60 秒）。
  所以目标 720 秒时，日志里两篇的时间差通常落在 12 分出头，属正常，不是守卫失效。

### 检查顺序

1. **发布前**：`check` 或 `wait` → 确认已满足目标间隔
2. **执行发布**：`publish`
3. **审核确认**：`verify-note`（必须 `found:true`）
4. **记录**：`record --note-id <id> --title "<标题>"` → 同时抽出下一篇的目标间隔
5. 下一篇从第 1 步重新开始

### 状态机

```
[无记录]  --record-->  [等待 next_gap]  --时间到--> [可发] --publish+verify+record--> [重新抽签等待]
```

## 使用

### 命令行

```bash
# 集成
export XHS_INTERVAL_GUARD=/path/to/publish-interval-guard/helpers/publish_interval.py
# 可选：调整随机区间
export XHS_INTERVAL_MIN=480     # 8 分钟
export XHS_INTERVAL_MAX=720     # 12 分钟

# 检查（是否已满足本次目标间隔）
python helpers/publish_interval.py check
python helpers/publish_interval.py check --json

# 阻塞等待（最长 900 秒，覆盖 720 秒上界）
python helpers/publish_interval.py wait --max-block 900

# 记录一次发布（仅在 verify-note 审核确认后）—— 同时抽下一篇的目标间隔
python helpers/publish_interval.py record --note-id 6a9a...68b3 --title "标题"

# 调试
python helpers/publish_interval.py last
python helpers/publish_interval.py reset   # 清空（仅调试用）

# 固定间隔 / 复现（调试）
python helpers/publish_interval.py record --title "x" --interval 600
python helpers/publish_interval.py check --interval-min 480 --interval-max 720 --seed 42
```

### 退出码

| 退出码 | 含义 |
| --- | --- |
| 0 | 间隔已满足 / 操作成功 |
| 1 | 间隔未满足（`check` / `wait` 超时） |
| 2 | 参数错误 |

## 与主 skill 的冲突点

- **无**。本 patch 不改主 skill 的 `scripts/cdp_publish.py`。
- **隐式约定**：调用方必须遵守"先审核、再 record"；否则间隔判断会被失败发布污染。
- **max-block 必须 ≥ 720**：否则随机到接近 12 分钟时会 `WAIT_INCOMPLETE`。默认已改为 900。

## 修改记录

- v1.0.0 (2026-09-04) 初版，从主 SKILL.md 第 148-167 行抽出
- v1.1.0 (2026-09-04) 物理迁移到 patch 目录，状态文件改到 `state/publish_log.json`（自包含）
- v1.2.0 (2026-09-11) 间隔从固定 600 秒改为 **480~720 秒随机**（8~12 分钟）；
  新增 `next_gap` 落盘（抽签一次、多次 check 不抖动）、旧记录自动补抽、
  `--interval-min/--interval-max`/`--seed`，max-block 默认 700 → 900
