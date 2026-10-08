# A2 更新评估与独立运行维护

可信参考源为 [`Gitfork300/xiaohongshu-skills-A2`](https://github.com/Gitfork300/xiaohongshu-skills-A2)。
此仓库的 `runtime/` 是可独立执行的 Windows 兼容运行层；A2 只用于可选的更新评估，不是运行依赖。

## 运行边界

- 发布、登录、搜索和互动使用本仓库 `runtime/scripts/`，不要求同级安装、不要求 Git remote，
  日常运行不访问 GitHub。
- Python 直接依赖只有 `requests` 和 `websockets`，通过 `tools/setup_runtime.py` 安装到仓库
  `.venv/`。Chrome/Chromium 由本机提供。
- 账号配置、登录态、Chrome Profile、稿件和运行状态均为本机数据，不进入仓库或跨设备复制。

## A2 与本地架构

A2 使用模块化 `scripts/xhs/`、`skills/` 和浏览器扩展；本地运行层依赖
`scripts/cdp_publish.py`、`scripts/publish_pipeline.py` 等兼容接口。不能把 A2 同名文件当作
本地实现直接覆盖，也不能将 A2 克隆为运行目录。

当前记录的 A2 基线：

| 项目 | 值 |
| --- | --- |
| 分支 | `main` |
| commit | `b043748282a57e347c52f517dfb59819121134ab` |
| 日期 | `2026-05-23T16:14:35Z` |
| 发布模块映射 | `scripts/xhs/publish.py`, `scripts/xhs/cdp.py`, `scripts/xhs/errors.py` |

`core-overrides/baseline.json` 仅追踪 root `SKILL.md` 和已声明的 A2 对应模块哈希。
未建立一对一映射的本地文件明确不可比较；检查结果不是可覆盖许可。

## 评估和移植步骤

1. 运行 `update-checker` 查看 A2 最新提交；需要完整差异时将快照解压到临时目录。
2. 对每个候选改动核对 A2 实际实现、本地行为、平台风险和当前测试；明确记录采纳、保留或拒绝。
3. 已采纳改动先合并进 `core-overrides/overrides/`；没有覆盖层的受管文件则更新 bundled `runtime/`。
4. 运行：

   ```powershell
   .\.venv\Scripts\python.exe core-overrides\helpers\apply_overrides.py apply --dry-run
   .\.venv\Scripts\python.exe core-overrides\helpers\apply_overrides.py apply
   .\.venv\Scripts\python.exe core-overrides\helpers\apply_overrides.py verify
   .\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
   .\.venv\Scripts\python.exe tools\ensure_compatible.py --refresh
   .\.venv\Scripts\python.exe tools\check_doc_layers.py
   ```

5. 确认全部通过后才更新 baseline/mapping、版本与修改记录，并 acknowledge 上游 commit。

**禁止**把 A2 快照传给 `apply_overrides.py rebase --from` 或
`tools/post_sync_check.py --upstream`。这两个旧布局工具需要同路径文件；A2 不满足输入契约。
不得用整仓复制、`git pull`、`checkout` 或 `reset` 更新本地运行层。

## 已移植的 A2 改进

- 发布页 tab 定位过滤 `data-hp-kind`/`button-hp-installed` 蜜罐节点，优先使用可信绑定节点，
  并验证可见和 active 状态；仅在上传区已就绪时兼容回退。
- 明确识别 `-9130` 至 `-9140` 风控响应及相关限制消息，保留精确发布响应校验和标题回查。
- 未移植页面内 fetch/XHR/console/MutationObserver 多层 hook；当前实现直接使用 CDP Network
  响应验证，侵入性更低且发布成功判据更严格。
- 未替换现有 `run_lock.py`；本地跨平台内核锁实现避免了旧式文件锁竞态。

对应实现位于 `core-overrides/overrides/scripts/cdp_publish.py`；回归用例位于 `tests/`。

## 本机快照备份

`tools/backup_snapshots.py` 用于备份 bundled runtime 和 Patch 工作区；它不备份 Chrome Profile、
Cookie 或 `runtime/config/accounts.json`。备份写入 `~/xhs-workspace/_skill-backup/`，
保留策略和告警见脚本头部说明。不要把生成的快照放进技能树或提交到公开仓库。
