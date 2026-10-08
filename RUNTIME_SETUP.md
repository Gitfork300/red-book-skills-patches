# Runtime 初始化与跨设备使用

`runtime/` 内的执行脚本、规则说明和参考文档与 Patch 一起分发；不需要同级主 skill。
首次安装时创建本机 Python 虚拟环境：

```powershell
py -3 tools\setup_runtime.py
.\.venv\Scripts\python.exe tools\init_runtime.py
.\.venv\Scripts\python.exe tools\ensure_compatible.py --refresh
.\.venv\Scripts\python.exe tools\check_public_release.py
```

`requirements.txt` 只有 `requests` 和 `websockets` 两个直接依赖。Chrome/Chromium 由本机
提供。setup 不创建账号配置、登录态或业务稿件。

## 日常运行

只加载根目录 `SKILL.md`。脚本相对路径（如 `scripts/cdp_publish.py`）均相对于
`runtime/`；使用仓库 `.venv` 中的 Python 解释器。

```powershell
Set-Location runtime
..\.venv\Scripts\python.exe scripts\publish_pipeline.py --help
```

## 本机数据

首次运行时脚本可能创建 `runtime/config/accounts.json`、`runtime/tmp/` 和各 patch 的
`state/` 文件。这些属于本机状态，已列入忽略规则，不得提交。不要跨设备复制 Cookie、
账号配置、浏览器 Profile、会话缓存或状态 JSON；每台电脑独立登录。

清理状态前确认没有正在执行的发布任务；保留各 state 目录中的 `README.md` 与 `.gitkeep`。
