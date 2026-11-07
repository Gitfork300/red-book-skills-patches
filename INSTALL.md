# 独立安装与调用

本仓库包含执行脚本、发布规则、操作参考和本地守卫，不需要单独安装同级 `red-book-skills`。
A2 Fork 不参与日常运行；发现上游更新后须评估并移植适用的 core 改动。

## 安装

需要 Git、Python 3.10+（含 pip）及 Chrome/Chromium。首次安装可从 GitHub 获取完整仓库：

```powershell
git clone https://github.com/Gitfork300/red-book-skills-patches.git red-book-skills-patches
Set-Location red-book-skills-patches
py -3 tools\setup_runtime.py
.\.venv\Scripts\python.exe tools\init_runtime.py
```

setup 需要 Python 3.10+，安装 `requirements.txt` 中的 `requests`、`websockets`、
`opencv-python` 和 `Pillow`；后两者用于封面二维码与相似度检查。
发布时另需本机安装 Chrome/Chromium。不要将登录态、账号配置或浏览器 Profile 放进 Git。
setup 仅用于首次创建；已存在 `.venv` 时会拒绝修改。日常升级保留现有环境，维护方更新环境方案与
必要时的安全迁移见 [`RUNTIME_SETUP.md`](./RUNTIME_SETUP.md#虚拟环境的来源与维护)。
**更新已有安装时不得删除或整目录替换安装目录**：应在原路径更新 Git 跟踪文件，或使用明确排除
`.venv/` 的文件同步方式。推送到 GitHub 只更新仓库跟踪内容，不会上传或删除部署机器上的 `.venv/`；
若部署工具会先清空目标目录，先停止并修改其行为，不能继续安装。

### 本机变量与脱敏占位符

规则和示例中的 `<WORKSPACE_ROOT>`、`<PORT_PUBLISH>`、`<PORT_COMMENT>` 是占位符，不是有效路径或可直接执行的命令参数。
按本机实际位置或 Chrome/CDP 监听端口替换后再运行；不要将替换后的个人路径、端口写回共享 Skill 文件或提交。
工作区路径可在当前 PowerShell 会话设置，也可写入当前用户环境变量：

```powershell
$workspaceRoot = Read-Host "Enter the local business workspace path"
$env:XHS_WORKSPACE = $workspaceRoot
[Environment]::SetEnvironmentVariable("XHS_WORKSPACE", $workspaceRoot, "User")
```

端口占位符只表示规则文本中的本机值。`XHS_CDP_PORT_PUBLISH` / `XHS_CDP_PORT_COMMENT` 供环境自检展示期望值，
不是所有运行脚本通用的端口覆盖开关；请将实际端口配置到 Chrome 启动方式及所用命令支持的 `--port` 参数中。
新安装后运行 `tools\check_env.py --fix-hint` 并按其输出完成自检。

对于**全新**业务工作区，建立规则入口及空稿件目录（默认 `C:\xhs`）：

```powershell
.\.venv\Scripts\python.exe tools\init_workspace.py
```

初始化只复制随 Skill 分发的强制规则、建立空 `xhs_publish/` 目录；不会搬迁每日选题、稿件、排名、
进度、台账或安装工作区专用执行器。已有业务工作区不运行初始化覆盖；升级 Skill 时保留业务数据。

该命令在 `.workbuddy\memory` 已存在时拒绝写入，绝不覆盖原有业务记忆；已有工作区请人工核对合并。
它会提供分组概述和分组规范数据等规则初始副本（强制规范），并创建空的 `xhs_publish/` 目录；
不会创建或迁移每日待分发结果、业务稿件、账号、历史台账或登录态。必须复核适用规则及业务工具，
不保证跨机器已有运营行为一致。然后执行：

```powershell
.\.venv\Scripts\python.exe tools\check_env.py --fix-hint
.\.venv\Scripts\python.exe tools\check_doc_layers.py
.\.venv\Scripts\python.exe core-overrides\helpers\apply_overrides.py apply --dry-run
```

审查 dry-run 和现存修改；`doctor.py` 会清理覆盖层生成物并可能应用覆盖层，只在确认其影响后运行：
`.\.venv\Scripts\python.exe tools\doctor.py`。不得跳过阻断项。常见问题见 [`HELP.md`](./HELP.md)。

## 日常调用

加载仓库根目录 [`SKILL.md`](./SKILL.md)。首次安装或更新后执行：

```powershell
.\.venv\Scripts\python.exe tools\ensure_compatible.py
```

发布执行脚本的工作目录设为 `runtime/`，例如：

```powershell
Set-Location runtime
..\.venv\Scripts\python.exe scripts\publish_pipeline.py --help
```

若门禁报告 `DRIFTED`、文件缺失或契约失败，应先修复；不要跳过门禁发布。

## 业务工作区约定

本仓库的守卫脚本与文档校验（`check_doc_layers.py`、`dup_check`、`bug_ledger` 等）依赖一个
**业务工作区**目录，其中同时包含：

- `.workbuddy/memory/MEMORY.md`（运营铁律主入口，判定工作区的锚点）
- `xhs_publish/`（稿件、封面、发布链、进度 JSON）

定位顺序（`tools/check_doc_layers.py` 的 `resolve_workspace()`）：

1. 环境变量 `XHS_WORKSPACE`（换机器时可用它覆盖默认位置）
2. **硬编码 `C:\xhs`**（默认业务工作区，零配置即生效）
3. 当前工作目录向上回溯（找含 `.workbuddy/memory/MEMORY.md` 的目录）
4. `~/WorkBuddy/` 下一层扫描（历史兜底）

> 2026-11-02 起，业务工作区**硬编码为 `C:\xhs`**（用户拍板，避免冗余数据侵占 user 目录），
> 与 skill 生态隔离：运营内容 + 项目记忆都在 `C:\xhs`，skill 本体在 `~/.workbuddy/skills/`。
> 新机器可用 `tools\init_workspace.py` 建立规则初始副本。已有业务资料须逐项筛选并确认授权后迁移；
> **不要整目录复制**，尤其排除 `.state`、锁、缓存、账号、Cookie 和浏览器 Profile。
> 若业务需要延续历史发布台账，应先停掉所有发布进程并人工核对来源、目标与冲突；
> 不应以空台账继续同一账号发布，也不得覆盖已有目标。

换机器 / 更换位置时可用环境变量覆盖：

```powershell
$env:XHS_WORKSPACE = "D:\your-workspace"   # 覆盖默认 C:\xhs
.\.venv\Scripts\python.exe tools\check_doc_layers.py
```

## 更新参考源

可信参考源为 [`Gitfork300/xiaohongshu-skills-A2`](https://github.com/Gitfork300/xiaohongshu-skills-A2)。
`update-checker` 查询其更新；发现更新后须评估并将适用改动移植到 core。不得把 A2 仓库克隆到 `runtime/`
或整仓覆盖本仓库。详细流程见 [`UPGRADING.md`](./UPGRADING.md)。

## 本地数据

Cookie、账号配置、Chrome Profile、稿件、日志和状态 JSON 均属于本机数据，保留在运行时
目录或用户工作区；不要提交到 GitHub，也不要跨设备复制登录态。
