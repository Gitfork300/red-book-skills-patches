# 常见问题（HELP）

> 本文件覆盖安装、变量、工作区、登录态、门禁等最常见的问题，自助排查。
> 排查前先跑一次环境自检，能定位大多数「变量未设置 / 依赖缺失」问题：

```powershell
.\.venv\Scripts\python.exe tools\check_env.py --fix-hint
```

退出码 0 = 全部就绪；1 = 有缺失（会逐项列出缺什么、怎么补）。

---

## 一、安装与首次运行

### Q：clone 之后第一步该做什么？

按 [`INSTALL.md`](./INSTALL.md) 完成环境安装、工作区初始化与门禁。新机器示例：

```powershell
py -3 tools\setup_runtime.py                 # 建 .venv + 安装 requirements.txt 全部依赖
.\.venv\Scripts\python.exe tools\init_runtime.py   # 初始化本机状态目录
.\.venv\Scripts\python.exe tools\init_workspace.py # 仅新工作区，已有 memory 则拒绝覆盖
.\.venv\Scripts\python.exe tools\check_env.py --fix-hint
```

`doctor.py` 会清理生成物并可能应用覆盖层，先检查 dry-run 和现有修改，再决定执行。

### Q：`doctor.py` 报 `缺少 requests`？

你用了**系统 Python** 而不是 `.venv` 里的解释器。所有脚本统一用 `.venv\Scripts\python.exe` 运行：

```powershell
.\.venv\Scripts\python.exe tools\doctor.py
```

不要用 `python tools\doctor.py`（系统 Python 没有装 `requests`）。

### Q：`doctor.py` 退出码 0 / 1 / 2 分别是什么意思？

- `0` = 全通过，可以正常使用；
- `1` = 有警告（不阻断，但要记账，比如环境变量缺失）；
- `2` = 有阻断项，**必须先修再发布**。

---

## 二、变量与工作区

### Q：`check_env.py` 报「未定位到业务工作区」？

业务工作区是守卫脚本和文档校验的依据，判定锚点是 `.workbuddy\memory\MEMORY.md`。定位顺序：

1. 环境变量 `XHS_WORKSPACE`（最高优先）
2. 硬编码 `C:\xhs`（默认，零配置）
3. 当前目录向上回溯
4. `~/WorkBuddy/` 下一层扫描

修复（任选其一）：

```powershell
# 方式 A：把业务工作区放到默认位置 C:\xhs
# 方式 B：用环境变量指向你的实际位置
$env:XHS_WORKSPACE = "D:\your-workspace"
```

### Q：端口占位符 `<PORT_PUBLISH>` / `<PORT_COMMENT>` 是什么？

规则文档里出现的 `<PORT_PUBLISH>`（发布实例）和 `<PORT_COMMENT>`（评论实例）是**脱敏占位符**，不是真实端口。真实默认值：

| 占位符 | 默认值 | 环境变量覆盖 |
| --- | --- | --- |
| `<PORT_PUBLISH>` | 9333 | `XHS_CDP_PORT_PUBLISH` |
| `<PORT_COMMENT>` | 9222 | `XHS_CDP_PORT_COMMENT` |

复刻到新机器时，如果实例端口不同，设对应环境变量即可，无需改文档。

### Q：换机器 / 换位置后怎么保证行为一致？

全新工作区运行 `tools\init_workspace.py`，已有业务资料须逐项核对后安全迁移；
不要整目录复制。凭据、锁和浏览器 Profile 禁止跨设备复制；历史台账如需延续，须先停发布进程并核对冲突。

---

## 三、登录态与账号

### Q：发布/评论提示 461 全败？

HTTP 461 + body `{"code":0,...}` = **creator 登录态失效**（不是风控、不是稿件问题）。

排查：删 `runtime\tmp\login_status_cache.json` 后跑 `check-login`，若导航落到 `/login` 即确诊。恢复：起 `login` 开二维码页 → 扫码 → 续跑。UI 显示"已登录"可能是缓存假象，以 `check-login` 落点为准。

### Q：账号配置、Cookie 应该放在哪？

一律放本机（`runtime/config/`、`runtime/tmp/`、各 patch 的 `state/`），**不要提交到 Git、不要跨设备复制**。每台电脑独立登录。

---

## 四、门禁与规则

### Q：`ensure_compatible` 一直报 DRIFTED 修不好？

大概率是 `__pycache__/*.pyc` 被当成覆盖文件（pyc 内嵌路径与 mtime，永远对不上）。`doctor.py` 已自动清理；手动处理：

```powershell
.\.venv\Scripts\python.exe core-overrides\helpers\apply_overrides.py clean
```

### Q：`check_doc_layers.py` 报「工作区主入口不存在」？

见「二、变量与工作区」。旧版曾硬编码路径，现版已自动探测；仍失败就设 `XHS_WORKSPACE` 再跑。

### Q：中文打印变成乱码 / traceback？

Windows 下中文 print 可能撞系统 ANSI 代码页。先检查专用 `.venv` 和 `sitecustomize.py`；
不要为排错直接重跑 setup 修改已安装环境。确需修复时，按 `RUNTIME_SETUP.md` 审查和安全迁移。

### Q：`check_public_release.py` 抛 `CalledProcessError`？

Git 不可用或目录不是有效的 Git 仓库时检查会失败；恢复 Git 和仓库后重跑，不可跳过。

---

## 五、规则知识在哪？

- 铁律速查 → `topics/QUICKREF.md`；
- 各主题规则细节 → `topics/00-rules-detail.md` ~ `14-group-rules.md`；
- 边界与交叉点 → `SYSTEMS.md`；
- 文档分层规范 → `DOC_LAYOUT.md`；
- 升级/备份/回滚 → `UPGRADING.md`。

> 说明：`topics/` 下的规则文档是随 skill 分发的**脱敏副本**（账号、运营数据已去除，端口以占位符表示），供复刻环境复核规则；你本机的真实运营数据仍在业务工作区，不进 Git。

---

## 六、快速排查速查表

| 症状 | 先跑 | 大概率原因 |
| --- | --- | --- |
| 刚 clone 就报缺依赖 | `setup_runtime.py` | 没建 .venv |
| 环境变量缺失提示 | `check_env.py --fix-hint` | 没设 `XHS_WORKSPACE` 等 |
| 工作区定位失败 | `check_env.py` | `C:\xhs` 不存在且没设环境变量 |
| 门禁 DRIFTED | `doctor.py` | 覆盖层混入 `__pycache__` |
| 发布 461 | `check-login` | creator 登录失效 |
| 中文乱码 | 查阅 `RUNTIME_SETUP.md` 的环境维护说明 | 可能丢了 `sitecustomize.py` 兜底 |
