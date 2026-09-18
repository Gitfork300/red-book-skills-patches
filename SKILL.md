---
name: red-book-skills-patch
description: |
  red-book-skills 的安全兼容门面。日常调用必须先通过本 Patch 的安装、
  上游来源、覆盖层和契约检查，再委托给同级安装的 red-book-skills。
metadata:
  trigger: 小红书发布、登录、检索、评论、互动
  upstream: red-book-skills
  source: local-patch
system: shared
version: 1.0.0
patch_for: red-book-skills
---

# red-book-skills-patch

本目录是日常调用入口；同级的 `red-book-skills` 是上游执行本体。**不要直接调用
上游 skill**，也不要把上游源码复制或拆进本 Patch。

## 首次安装、切换电脑或上游变更

在本 Patch 根目录执行：

```bash
python tools/ensure_compatible.py
```

Windows PowerShell：

```powershell
py -3 tools\ensure_compatible.py
```

仓库和目录的固定位置见 [`UPDATE_LOCATIONS.md`](./UPDATE_LOCATIONS.md)。
上游只能从 `aus666666/red-book-skills` 获取，Patch 从
`Gitfork300/red-book-skills-patches` 获取。

该命令会：

1. 定位同级 `red-book-skills`（也可用 `RED_BOOK_SKILLS_ROOT` 指定）；
2. 检查上游入口和执行脚本存在，并在 Git 仓库中确认来源；
3. 如果声明的依赖文件缺失，从本机 `red-book-skills-upstream/` 仅补回缺失文件；
4. 拒绝直接改坏的覆盖层状态；
5. 自动应用 `core-overrides`，自动备份原文件；
6. 校验覆盖层和 33 项上游契约；
7. 通过后输出唯一可调用的本体路径。

任何一步失败都必须停止，不得绕过门禁直接调用上游脚本。

## 日常调用规则（会话内只初始化一次）

- 日常任务以本 Patch 的规则、`INDEX.md` 和 `SYSTEMS.md` 为准。
- 首次加载 Patch 时运行一次 `ensure_compatible.py`；同一会话后续任务复用已通过的结果，
  不重复调用、不重复解释上游规则。
- `ensure_compatible.py` 会比较本机指纹并缓存通过结果；上游、Patch 覆盖层或本体路径
  发生变化时才自动重新检查。需要强制复核时使用 `ensure_compatible.py --refresh`。
- 通过门禁后，只能调用它输出的同级 `red-book-skills` 脚本。
- Cookie、账号配置、浏览器 Profile、日志和状态 JSON 只保存在本机。
- 上游更新后重新运行门禁；若报告 `DRIFTED`、契约缺失或来源异常，停止操作并按
  [`UPGRADING.md`](./UPGRADING.md) 处理，不自动覆盖人工修改。

## 架构边界

```text
red-book-skills-patch  ← 日常加载/规则/安全门禁（唯一入口）
          │
          └── ensure_compatible.py
                    │
                    └── red-book-skills  ← 上游执行本体（不拆分、不复制）
```

完整同步和回滚流程见 [`UPGRADING.md`](./UPGRADING.md)；运行时目录规则见
[`RUNTIME_SETUP.md`](./RUNTIME_SETUP.md)。
