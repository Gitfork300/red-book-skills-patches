# 运行目录与更新来源

运行代码随本仓库分发；A2 Fork 是独立、可选的评估来源。不要把运行位置、仓库地址和
上游参考地址混为一谈。

| 用途 | 地址或路径 |
| --- | --- |
| 可信参考 Fork | `https://github.com/Gitfork300/xiaohongshu-skills-A2` |
| 本 Patch/独立 Skill 仓库 | `https://github.com/Gitfork300/red-book-skills-patches` |
| 当前工作区 | `<repo-root>/` |
| 随仓库分发的运行代码 | `<repo-root>/runtime/` |
| 本地 Python 虚拟环境 | `<repo-root>/.venv/` |
| apply 前备份 | `<workspace>/_skill-backup/core-overrides-preapply/` |

## 更新运行代码

1. 把 A2 `main` 快照下载到临时目录，仅作差异评估。
2. 依照 [`UPGRADING.md`](./UPGRADING.md) 复核模块行为与安全约束。
3. 选择性移植已批准的修改到 `core-overrides/overrides/` 或 runtime 的其他独立文件。
4. 执行 `apply_overrides.py apply`、`verify`、本地测试和 `ensure_compatible.py --refresh`。
5. 更新 baseline/mapping 与修改记录；不要把 A2 快照直接作为运行层。

A2 与当前 Windows 兼容脚本布局不同。不得对 A2 快照运行旧布局的 `rebase --from`、
`post_sync_check.py --upstream`，也不得目录级覆盖。

## 本机状态和账号

`runtime/config/accounts.json`、`runtime/tmp/`、各 patch `state/`、Chrome 登录态、
稿件及日志均为本机数据。它们不属于公开仓库内容。安装脚本不会创建账号、Cookie、
浏览器 Profile 或业务状态。
