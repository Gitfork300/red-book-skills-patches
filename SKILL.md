---
name: red-book-skills-patch
description: |
  独立运行的小红书发布与运营 skill。内置 Windows 兼容执行脚本、质量门禁和本地规则；
  A2 Fork 仅作为可选更新评估来源，不是运行依赖。
metadata:
  trigger: 小红书发布、登录、检索、评论、互动
  source: bundled-runtime
system: shared
version: 1.3.8
---

# red-book-skills-patch

本 skill 自包含脚本、规则、覆盖层及质量门禁；
无需同级 `red-book-skills`，运行时不访问 GitHub。可信 A2 Fork 仅供评估更新和择优
移植，A2 快照不得覆盖本地 runtime。

## 首次安装与验证

在本仓库根目录运行：

```powershell
py -3 tools\setup_runtime.py
.\.venv\Scripts\python.exe tools\init_runtime.py
.\.venv\Scripts\python.exe tools\init_workspace.py        # 仅新工作区；已有 memory 时拒绝覆盖
.\.venv\Scripts\python.exe tools\check_env.py --fix-hint   # 环境与变量自检（Python/venv/工作区/Chrome/端口）
```

先审查覆盖层 dry-run 和现存修改，再运行 `.\.venv\Scripts\python.exe tools\doctor.py`；
新机器完整流程见 [`INSTALL.md`](./INSTALL.md)。
更新已安装副本时须保留原安装目录和其中的 `.venv`；不要删除或整目录替换，详见
[`RUNTIME_SETUP.md`](./RUNTIME_SETUP.md#虚拟环境的来源与维护)。
`doctor.py` 先自愈再校验，一次串完环境自检、覆盖层、契约、版本登记、文档分层、
回归测试与发布安全门禁（退出码 0 全通过 / 1 仅警告 / 2 阻断）。任一步失败都必须
停止并修复；不要跳过门禁直接发布。日常只需跑 `ensure_compatible.py`（不带
`--refresh` 会复用本次会话已通过的缓存结果）；代码或规则更新后重新运行
`ensure_compatible.py --refresh`。

## Skill 规则与业务工作区

强制规则和分组概述随 Skill 保存在 `topics/`；每日排名、选题、稿件、队列、进度及发布台账属于业务数据，
应保存在 `C:\xhs` 工作区或其 `.state/`，不得回写 Skill。`init_workspace.py` 只复制规则并创建空的
`xhs_publish/` 目录，不迁移旧业务结果，也不安装工作区专用执行器；使用前需单独确认所需工具存在。

> 环境变量（`XHS_WORKSPACE`、实例端口等）未设置不会让脚本崩溃，而是**静默退化**；
> 用 `check_env.py` 能主动暴露这些缺口并给出修复命令。常见问题见 [`HELP.md`](./HELP.md)。

## 常见故障速查

| 现象 | 原因 | 处置 |
| --- | --- | --- |
| `ensure_compatible` 报 DRIFTED 且总是修不好 | `overrides/scripts/__pycache__/*.pyc` 被当成覆盖文件；pyc 内嵌路径与 mtime，永远对不上 | 已被 `doctor.py` / `ensure_compatible.py` 自动清理；手动：`apply_overrides.py clean` |
| 命令"失败"但看不到业务错误，输出里是 traceback | Windows 下中文 print 撞系统 ANSI 代码页 | 检查专用环境，必要时按 `RUNTIME_SETUP.md` 安全迁移 |
| `check_public_release.py` 无法检查已跟踪文件 | 目录不是 Git 仓库或 Git 不可用 | 修复 Git/仓库后重跑，不能跳过发布安全门禁 |
| `check_doc_layers.py` 报工作区主入口不存在 | 旧版硬编码 `C:/xhs` | 已改为自动探测；如需指定：`$env:XHS_WORKSPACE="…"` |
| 环境变量缺失 / 依赖没装却"跑通了" | 脚本静默退化，没主动报缺 | 先跑 `tools\check_env.py --fix-hint` 主动暴露缺口 |
| 其他安装、变量、登录态、门禁问题 | — | 见 [`HELP.md`](./HELP.md) |

## 执行任务

每次执行前先遵守本文件、[`INDEX.md`](./INDEX.md)、[`SYSTEMS.md`](./SYSTEMS.md) 和
[`runtime/INSTRUCTIONS.md`](./runtime/INSTRUCTIONS.md) 中的发布安全、内容和核验规则。
详见 `runtime/references/`。

**触发词**：用户说「**收尾**」「**落盘**」「日终收口」= 立即执行日终收口，不等补充指令；
标准 **≤30 分钟**，带「加急」则 **≤5 分钟**。流程与清单见
[`daily-closeout-guard`](./daily-closeout-guard/SKILL.md)。

**触发即回执**（通用，适用于本 skill 所有触发词，如「启动」「收尾」）：
听到触发词时**第一句先回执** —— 「收到关键词「<原词>」，正在执行：<流程名>（<预算/模式>），
目标 <对象/日期>」，然后立即开工。回执要让对方一眼确认**识别到的词、将做的事、时间预算**；
对方可随即纠偏，未纠偏即按回执执行到底。

运行相对路径为 `scripts/...` 的脚本时，将工作目录设为 `runtime/`：

```powershell
Set-Location runtime
..\.venv\Scripts\python.exe scripts\publish_pipeline.py --help
```

底层脚本可直接使用同一虚拟环境解释器，例如：

```powershell
..\.venv\Scripts\python.exe scripts\cdp_publish.py check-login
```

本机需安装 Chrome/Chromium；登录态、账号配置、浏览器 Profile、稿件和状态文件均保留
在本机，不要提交到 GitHub 或跨设备复制。

## 依赖和更新

- Python 3.10+；直接 Python 依赖包括 `requests`、`websockets`、`opencv-python` 和 `Pillow`，由
  `tools/setup_runtime.py` 安装到仓库内 `.venv/`。
- Chrome/Chromium 是本机外部程序，不随仓库分发。
- A2 更新检查由 `update-checker` 按需访问 GitHub，发现提交后须评估并将适用改动移植至 core；发布、登录、搜索和互动不依赖 A2、
  Git remote 或网络下载代码。
- 评估更新时只移植经过复核且兼容本地行为的改动，禁止整仓覆盖。
- 升级交接状态、待办清单与回滚点见 [`HANDOVER.md`](./HANDOVER.md)。
