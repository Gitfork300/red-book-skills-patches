# Runtime 初始化与跨设备使用

`runtime/` 内的执行脚本、规则说明和参考文档与 Patch 一起分发；不需要同级主 skill。
首次安装时创建本机 Python 虚拟环境：

```powershell
py -3 tools\setup_runtime.py
.\.venv\Scripts\python.exe tools\init_runtime.py
.\.venv\Scripts\python.exe tools\init_workspace.py  # 仅全新工作区
.\.venv\Scripts\python.exe tools\check_env.py --fix-hint
```

`requirements.txt` 包含 `requests`、`websockets`、`opencv-python` 和 `Pillow`。Chrome/Chromium 由本机
提供。setup 不创建账号配置、登录态或业务稿件。
已有 `.workbuddy\memory` 时初始化工具会拒绝覆盖，需人工合并。完整新机器步骤及执行
`doctor.py` 前的影响审查见 [`INSTALL.md`](./INSTALL.md)。

> `check_env.py` 是本机环境自检（Python / .venv / 业务工作区 / Chrome / 实例端口），
> 变量未设置时给出明确提示而非静默失败，建议装机后先跑它。详见 [`HELP.md`](./HELP.md)。

## 虚拟环境的来源与维护

`.venv` 是本 Skill 专用、首次安装时在使用方机器生成的环境，不是 Git 跟踪的源码。
**使用方日常运行或更新 Skill 时应保留现有环境，不更新、替换、移动或复制它**，以免解释器和路径错配。
推送到 GitHub 只更新受跟踪的源码和规则，远端仓库不会包含使用方机器上的 `.venv/`；
推送本身不会触碰部署机器的环境。部署更新必须在原安装路径进行，并保留 `.venv/`。
原位 Git 更新只修改受跟踪文件，通常会保留被忽略的 `.venv/`；若通过压缩包、同步器或安装器更新，
必须明确排除 `.venv/`，不得先删除/清空整个安装目录再复制新版本。无法保证保留时应停止更新，
不要用重新 clone 或复制另一台机器的 `.venv` 作为替代。
`tools\setup_runtime.py` 使用**运行该脚本的 Python**（最低 3.10）创建缺失的环境，再按
`requirements.txt` 安装依赖并写入 `sitecustomize.py`（输出 UTF-8，并在默认配置下归集
字节码和运行临时文件）。已有 `.venv` 时，setup 明确拒绝执行，不安装依赖也不改环境；
即使首次安装中途失败留下了目录，也须先检查并安全备份该目录。

每台机器的 `.venv\pyvenv.cfg` 都会记录创建它时使用的基础 Python 路径和版本；
这是本机配置，不应复制到另一台机器，也不要照抄维护者的解释器路径。
若基础解释器被移动或移除，环境可能无法运行。重建前按本文件的安全迁移步骤备份旧环境；
不要覆盖已有备份。

`requirements.txt` 是直接依赖的**最低版本约束，不是锁文件**。当前本机已安装
`requests 2.34.2`、`websockets 17.4`、`opencv-python 5.0.0.93`、`Pillow 13.0.0`
及其间接依赖；这些仅为本机快照，不保证新机器或重建后得到相同版本。
Python 本体和 pip 也不会因更新仓库而自动升级。

日常在仓库根目录直接使用环境解释器，无需激活：

```powershell
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe tools\check_env.py --fix-hint
```

维护方可随 Skill 更新环境**构建方案**（Python 兼容要求、`requirements.txt`、setup 及测试）；
新安装按更新后的方案创建本机 `.venv`，不意味着要改动已有使用方环境。维护方须评估新版
Skill 与既有环境的兼容性并记录结果；不兼容时明确阻止使用并提供单独迁移方案，不能静默升级。
由于依赖没有锁定，新安装结果可能随包来源和时间变化，不保证与维护方环境一致。

仅在确需修复、迁移或经使用方明确同意更换环境时：先停止相关任务，保护业务台账、
账号及浏览器资料；确认无进程使用环境后，将旧 `.venv` 重命名为**不存在的唯一备份路径**，
不要覆盖现有备份。用新位置的 Python 从仓库根目录重新运行 `tools\setup_runtime.py`，
然后核对版本、`pip check` 和相关回归测试。不要复制 `.venv` 到新机：在新机用本机 Python 重建。
这些步骤不会迁移业务历史台账或登录状态；处理业务数据须遵循下方保护规则。

## 日常运行

只加载根目录 `SKILL.md`。脚本相对路径（如 `scripts/cdp_publish.py`）均相对于
`runtime/`；使用仓库 `.venv` 中的 Python 解释器。

```powershell
Set-Location runtime
..\.venv\Scripts\python.exe scripts\publish_pipeline.py --help
```

## 本机数据

首次运行时脚本可能创建 `runtime/config/accounts.json` 和各 patch 的
`state/` 文件。这些属于本机状态，已列入忽略规则，不得提交。不要跨设备复制 Cookie、
账号配置、浏览器 Profile、会话缓存或状态 JSON；每台电脑独立登录。历史发布台账如需延续，
必须停止发布进程、核对来源与目标并保护现存数据，不能用空台账替代历史记录。

清理状态前确认没有正在执行的发布任务；保留各 state 目录中的 `README.md` 与 `.gitkeep`。

发布台账默认位于 `C:\xhs\.state\publish\publish_log.json`。迁移旧台账前必须停止所有
发布进程；`python tools\runtime_paths.py --init` 只在新位置不存在时复制旧台账，
保留原文件，不覆盖已有新台账。新台账存在后，旧文件不再参与间隔判断。
二维码目检白名单默认位于 `C:\xhs\.state\covers\qr_whitelist.json`；旧 Skill 树内白名单在首次检查时
只会在新址不存在或内容完全相同时迁移，冲突时停止并要求人工核对。定期备份工具会将发布台账与白名单
单独复制到 `C:\xhs\_skill-backup\business-state\`，源码快照不再收录 `state/` 下的 JSON。
