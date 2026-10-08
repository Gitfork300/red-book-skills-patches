# red-book-skills-patches

[![Python tests](https://github.com/Gitfork300/red-book-skills-patches/actions/workflows/python-app.yml/badge.svg)](https://github.com/Gitfork300/red-book-skills-patches/actions/workflows/python-app.yml)

面向小红书内容发布与互动流程的独立 Skill 集合，包含随仓库分发的 Windows 兼容运行层、可组合规则 Patch、预检工具和本机状态保护。仓库首页由本 README 提供。

本仓库自包含运行所需代码，不依赖同级安装另一份主 Skill。日常运行不需要访问 GitHub；浏览器自动化需要本机安装 Chrome 或 Chromium。

## 功能概览

- **独立运行**：发布执行代码和参考文档位于 [`runtime/`](./runtime/)，由本仓库统一维护。
- **规则分层**：发布、评论及共用基座各自维护；Patch 清单、版本和加载顺序见 [`INDEX.md`](./INDEX.md)。
- **发布前守卫**：提供稿件预检、用词与时效规则、重复内容检查和运行状态保护。
- **可审查升级**：可信参考来源为 [`Gitfork300/xiaohongshu-skills-A2`](https://github.com/Gitfork300/xiaohongshu-skills-A2)，仅用于可选的更新评估，不是运行依赖。
- **隐私优先**：Cookie、账号配置、浏览器 Profile、稿件及运行状态属于本机数据，不应提交或跨设备复制。

## 环境要求

- Windows PowerShell（本仓库主要运行环境）
- Python 3.10 或更新版本
- 本机安装 Chrome 或 Chromium
- 网络连接仅在安装 Python 依赖或主动检查参考源更新时需要

Python 直接依赖为 `requests` 和 `websockets`，由仓库脚本安装到本地 `.venv/`。

## 快速开始

```powershell
git clone https://github.com/Gitfork300/red-book-skills-patches.git
Set-Location red-book-skills-patches
py -3 tools\setup_runtime.py
.\.venv\Scripts\python.exe tools\init_runtime.py
.\.venv\Scripts\python.exe tools\ensure_compatible.py --refresh
```

门禁通过后，按仓库根目录 [`SKILL.md`](./SKILL.md) 加载和使用本 Skill。发布脚本的相对路径以 `runtime/` 为当前目录，例如：

```powershell
Set-Location runtime
..\.venv\Scripts\python.exe scripts\publish_pipeline.py --help
```

遇到兼容门禁失败、文件漂移或依赖缺失时，应先停止并排查，不要跳过检查直接运行发布流程。更多说明见 [`INSTALL.md`](./INSTALL.md) 和 [`RUNTIME_SETUP.md`](./RUNTIME_SETUP.md)。

## 项目结构

| 路径 | 内容 |
| --- | --- |
| [`runtime/`](./runtime/) | 随仓库分发的独立运行层及操作参考 |
| [`core-overrides/`](./core-overrides/) | 运行层受管覆盖文件及应用、验证工具 |
| 各 Patch 目录 | 专项规则、辅助脚本、版本元数据和状态说明 |
| [`tools/`](./tools/) | 安装、兼容性、文档、版本与发布安全检查 |
| [`tests/`](./tests/) | 自动化回归测试 |

## 维护与验证

安装依赖后，在仓库根目录执行：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
.\.venv\Scripts\python.exe tools\ensure_compatible.py --refresh
.\.venv\Scripts\python.exe core-overrides\helpers\apply_overrides.py verify
.\.venv\Scripts\python.exe tools\check_patch_versions.py
.\.venv\Scripts\python.exe tools\check_doc_layers.py
.\.venv\Scripts\python.exe tools\check_public_release.py
```

评估参考源更新时只择优合并经过检查的改动，不将上游快照直接覆盖到 `runtime/`。详细约定见 [`UPGRADING.md`](./UPGRADING.md)、[`UPDATE_LOCATIONS.md`](./UPDATE_LOCATIONS.md) 和 [`SYSTEMS.md`](./SYSTEMS.md)。

## 本机数据与安全

不要提交或公开 Cookie、账号配置、浏览器 Profile、认证响应、稿件、日志或运行时状态文件。运行前应审阅规则和脚本；平台页面、接口与政策可能变化，关键行为需在当前环境重新验证。

## 许可证

当前仓库未提供有效的许可证文件。公开复用或再分发前，请先由维护者确认适用许可。
