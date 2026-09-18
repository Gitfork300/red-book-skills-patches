# 更新位置与上游恢复约定

本文件是仓库地址、安装目录和更新来源的唯一位置说明。不要把本机目录名
当成 GitHub 仓库地址，也不要从 `Gitfork300/red-book-skills` 抓取上游。

## 固定位置

| 用途 | 地址或路径 |
| --- | --- |
| 原作者上游仓库 | `https://github.com/aus666666/red-book-skills.git` |
| 本 Patch 公开仓库 | `https://github.com/Gitfork300/red-book-skills-patches.git` |
| 上游运行目录 | `red-book-skills/` |
| Patch 运行目录 | `red-book-skills-patches/` |
| 本地上游备份 | `red-book-skills-patches/red-book-skills-upstream/` |

安装后两个运行目录必须位于同一个 `skills` 父目录。`red-book-skills-upstream/`
是本机只读备份，不是第三个 Skill，不参与日常加载，也不会上传到 Patch 仓库。

## 更新时使用哪个位置

1. 从原作者仓库获取新版上游快照，解压到临时目录。
2. 先使用 [`UPGRADING.md`](./UPGRADING.md) 的差异检查流程。
3. 确认后把新版上游同步到 `red-book-skills/`，再运行：

   ```powershell
   py -3 tools\ensure_compatible.py --refresh
   ```

4. Patch 的规则和源码覆盖只修改本仓库的 `core-overrides/overrides/`；
   不要直接把长期修改写进 `red-book-skills/`。

## 缺失依赖的本地恢复

`tools/ensure_compatible.py` 会在兼容检查前，针对以下声明的上游依赖进行
“仅补缺、不覆盖”恢复：

- `SKILL.md`
- `scripts/account_manager.py`
- `scripts/cdp_publish.py`
- `scripts/chrome_launcher.py`
- `scripts/feed_explorer.py`
- `scripts/image_downloader.py`
- `scripts/publish_pipeline.py`
- `scripts/run_lock.py`

默认恢复源是：

```text
red-book-skills-patches/red-book-skills-upstream/
```

只有当运行目录中的目标文件不存在、备份目录确实是 `red-book-skills` 上游快照、
且备份中存在同一路径文件时才会复制。已有文件不会被备份覆盖；备份中也没有的
文件仍会使门禁失败，不会伪造空文件或静默绕过检查。

如果备份不在默认位置，可显式指定：

```powershell
py -3 tools\ensure_compatible.py `
  --upstream-backup 'D:\backup\red-book-skills-upstream' `
  --refresh
```

也可以设置环境变量 `RED_BOOK_SKILLS_UPSTREAM_BACKUP`。恢复属于本机修复动作，
不会修改 Patch Git 中的上游备份目录，也不会把 Cookie、账号配置、日志或运行时
状态带入公开仓库。
