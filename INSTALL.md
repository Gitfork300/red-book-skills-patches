# 独立安装与调用

本仓库包含执行脚本、发布规则、操作参考和本地守卫，不需要单独安装同级 `red-book-skills`。
A2 Fork 是可选的更新评估来源，不参与日常运行。

## 安装

在 PowerShell 中：

```powershell
git clone https://github.com/Gitfork300/red-book-skills-patches.git red-book-skills-patches
Set-Location red-book-skills-patches
py -3 tools\setup_runtime.py
.\.venv\Scripts\python.exe tools\init_runtime.py
.\.venv\Scripts\python.exe tools\ensure_compatible.py --refresh
```

setup 需要 Python 3.10+，只安装 `requirements.txt` 中的 `requests` 和 `websockets`。
发布时另需本机安装 Chrome/Chromium。不要将登录态、账号配置或浏览器 Profile 放进 Git。

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

## 更新参考源

可信参考源为 [`Gitfork300/xiaohongshu-skills-A2`](https://github.com/Gitfork300/xiaohongshu-skills-A2)。
`update-checker` 可选地查询其更新；更新须评估后择优移植。不得把 A2 仓库克隆到 `runtime/`
或整仓覆盖本仓库。详细流程见 [`UPGRADING.md`](./UPGRADING.md)。

## 本地数据

Cookie、账号配置、Chrome Profile、稿件、日志和状态 JSON 均属于本机数据，保留在运行时
目录或用户工作区；不要提交到 GitHub，也不要跨设备复制登录态。
