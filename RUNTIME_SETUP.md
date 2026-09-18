# Runtime 初始化与跨电脑同步

本仓库只同步规则、脚本和运行时目录的说明文件。`state/`、`logs/` 中的 JSON、
锁文件、备份、日志、cookie、账号配置和浏览器登录态均属于本机数据，不能提交。

`red-book-skills-upstream/` 是本机只读的上游源码备份，不是 Patch，不参与加载，
也不会随公开 Patch 仓库同步。Patch 仍通过 `core-overrides` 与上游 skill 衔接，
不复制或拆分上游源码。

仓库地址和更新位置以 [`UPDATE_LOCATIONS.md`](./UPDATE_LOCATIONS.md) 为准：
上游是 `aus666666/red-book-skills`，Patch 是
`Gitfork300/red-book-skills-patches`。不要使用不存在的
`Gitfork300/red-book-skills` 作为抓取地址。

## Clone 后初始化

在仓库根目录执行：

```bash
python tools/init_runtime.py
python tools/ensure_compatible.py
python tools/check_public_release.py
```

`init_runtime.py` 只创建空目录，不创建业务数据、伪造登录态或写入凭据。各 helper
首次需要写入状态时会自行创建对应 JSON 文件。

如果上游运行目录缺少声明的依赖，`ensure_compatible.py` 会从本机
`red-book-skills-upstream/` 仅恢复缺失文件后再继续门禁；也可使用
`--upstream-backup <目录>` 指定备份位置。恢复不会覆盖已有文件。

日常只加载根目录 `SKILL.md`（`red-book-skills-patch`）。`ensure_compatible.py`
首次通过后，Patch 才会把同级 `red-book-skills` 作为执行本体使用；同一会话后续
任务复用结果，不重复调用门禁。上游或 Patch 变化时会自动失效，也可用
`python tools/ensure_compatible.py --refresh` 强制检查。不要直接加载或调用上游 skill。

Windows PowerShell：

```powershell
py -3 tools\init_runtime.py
py -3 tools\ensure_compatible.py
py -3 tools\check_public_release.py
```

## 本机登录与状态

每台电脑都必须使用本机浏览器重新建立登录态。不要复制另一台电脑的 cookie、
session、账号配置、浏览器 profile 或状态 JSON。业务规则和业务文档可以同步；
运行记录只用于当前电脑的节流、风控、查重和恢复。

## 清理本机状态

可删除各 patch 的 `state/` 下除 `README.md` 和 `.gitkeep` 外的内容，再运行
`python tools/init_runtime.py`。清理前确认没有正在执行的发布任务。
