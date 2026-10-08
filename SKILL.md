---
name: red-book-skills-patch
description: |
  独立运行的小红书发布与运营 skill。内置 Windows 兼容执行脚本、质量门禁和本地规则；
  A2 Fork 仅作为可选更新评估来源，不是运行依赖。
metadata:
  trigger: 小红书发布、登录、检索、评论、互动
  source: bundled-runtime
system: shared
version: 1.1.0
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
.\.venv\Scripts\python.exe tools\ensure_compatible.py --refresh
```

门禁会校验随仓库分发的脚本和参考文件、依赖、覆盖层及运行契约。任一步失败都必须
停止并修复；不要跳过门禁直接发布。需要在会话内重复运行时，已通过的结果可复用；
代码或规则更新后重新运行 `ensure_compatible.py --refresh`。

## 执行任务

每次执行前先遵守本文件、[`INDEX.md`](./INDEX.md)、[`SYSTEMS.md`](./SYSTEMS.md) 和
[`runtime/INSTRUCTIONS.md`](./runtime/INSTRUCTIONS.md) 中的发布安全、内容和核验规则。
详见 `runtime/references/`。

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

- Python 3.10+；直接 Python 依赖只有 `requests` 与 `websockets`，由
  `tools/setup_runtime.py` 安装到仓库内 `.venv/`。
- Chrome/Chromium 是本机外部程序，不随仓库分发。
- A2 更新检查由 `update-checker` 按需访问 GitHub；发布、登录、搜索和互动不依赖 A2、
  Git remote 或网络下载代码。
- 评估更新时只移植经过复核且兼容本地行为的改动，禁止整仓覆盖。
