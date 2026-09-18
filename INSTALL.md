# 双 Skill 安装与调用

本方案保留两个独立目录，不合并、不拆分上游源码：

```text
<skills>/
├── red-book-skills/          # 上游执行本体
└── red-book-skills-patches/  # 日常唯一入口与兼容门禁
```

## 安装顺序

先安装上游，再安装 Patch，并确保两个目录位于同一个 `skills` 父目录：

```powershell
git clone https://github.com/aus666666/red-book-skills.git red-book-skills
git clone https://github.com/Gitfork300/red-book-skills-patches.git red-book-skills-patches
Set-Location red-book-skills-patches
py -3 tools\init_runtime.py
py -3 tools\ensure_compatible.py
```

仓库地址、目录关系和缺失依赖恢复规则见
[`UPDATE_LOCATIONS.md`](./UPDATE_LOCATIONS.md)。不要访问或创建
`Gitfork300/red-book-skills`；它不是本项目的上游仓库。

如果上游不在同级目录，可设置本机环境变量，或传入 `--main`：

```powershell
$env:RED_BOOK_SKILLS_ROOT = 'D:\skills\ned-book-skills'
py -3 tools\ensure_compatible.py
```

## 日常调用

加载 `red-book-skills-patches/SKILL.md`，不要直接加载上游 `SKILL.md`。
首次加载 Patch 或切换/更新上游后执行一次：

```powershell
py -3 tools\ensure_compatible.py
```

门禁通过后，才调用输出路径下的上游脚本。门禁失败时禁止绕过 Patch。
同一会话后续任务直接复用该结果，不重复执行。需要强制复核时使用
`py -3 tools\ensure_compatible.py --refresh`。

## 更新上游

更新或重新安装 `red-book-skills` 后，重新运行 `ensure_compatible.py`。
若出现 `DRIFTED`、来源异常或契约缺失，不要强制覆盖，按
[`UPGRADING.md`](./UPGRADING.md) 合并和复核。

## 安全边界

- 上游源码仍由原作者仓库维护；Patch 只保存定制规则和覆盖层。
- Cookie、账号配置、浏览器 Profile、日志、状态 JSON 不进入任一公开仓库。
- `red-book-skills-upstream/` 只是本机检查备份，不属于安装内容。
- 如果同级上游目录缺少已声明的依赖文件，`ensure_compatible.py` 会从
  `red-book-skills-upstream/` 仅补回缺失文件；已有文件不会被覆盖。
