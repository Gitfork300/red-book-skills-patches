# 交接卡 · 版本升级专用

> 生成：2026-11-06 11:20｜当前复核：2026-11-06（root 1.3.6）｜对象：本 skill 全树（14 个 patch + root 门面）
> 用途：把本 skill 交接给下一个 agent 做**大版本升级**。**本卡是两端唯一桥梁**，读完本页再动任何文件。
> 本 skill 的定位（用户 11-06 明确）：**包含全部核心内容**——既能单独部署到新机器直接跑，也是本次升级的基线物。
> 因此「卡里写的」必须等于「树里有的」；记录与实物不符时，以实物为准并当天改卡，不许留悬空描述。
> **可核对的硬事实在同目录 [`HANDOVER_BASELINE.md`](./HANDOVER_BASELINE.md)**：9 个覆盖文件 hash、15 个版本、`topics/` 字符数、结构判据。
> 该页由 `python tools/gen_handover_baseline.py` 生成，`--check` 校验；`doctor` 第 10 步 `check_baseline` 会比对。
> 改完受管文件必须重跑生成，**否则卡与实物脱钩，等于没有交接**。
> 上游参考：`Gitfork300/xiaohongshu-skills-A2`（基线 `b043748` / 2026-05-23），仅评估用，**不是运行依赖**。

## 当前整合状态（2026-11-06）

- GitHub patches `main` 已获取，基线为 `7ef76318bd7cb3265b9322faf95e71928ff0cf38`；本仓库有 Git，以下无 Git 描述仅为 demo 交接时的历史记录。
- 业务工作区和本仓库相关现行规则已同步为 360–840 秒；文档层级上限已调整，工作区文档校验通过。
- 现有发布台账及登录数据未覆盖；新旧台账均存在，迁移前须停止发布进程并核实，绝不覆盖已有目标。
- 2026-11-06 用户手动运行完整 `doctor`，提供的输出显示 10 个步骤均为 OK；随后复核 9 个覆盖文件与交接基线一致。以下旧体检结果仅为 demo 交接时的历史记录。
- 1.3.4 修正了过期评级块及虚拟环境说明；用户于 18:56 审查 dry-run 并备份应用两个受管文件，verify 显示 9 个文件一致。备份位于 `C:/xhs/_skill-backup/core-overrides-preapply/20261106_185625`。
- 本机 Python 3.13.9 安装于 `D:/VS-SKILL/python-3.13.9`；原有不可启动的 `.venv` 保留在 `D:/VS-SKILL/red-book-skills-patches-venv-backup-20261106`，仓库 `.venv` 已重建。
- 本机便携 Git 位于 `D:/VS-SKILL/git-portable-2.56.0/cmd`，未修改系统 PATH。需要 Git 的检查可先在当前 PowerShell 会话设置 `$env:PATH = 'D:\VS-SKILL\git-portable-2.56.0\cmd;' + $env:PATH`。
- 本地版本 1.3.6 和更新内容记录在 `CHANGELOG.md`；新机器完整流程见 `INSTALL.md`。本地变更尚未提交或推送，新机器 clone 仍取得旧版。
- 1.3.5 从工作区分组规范提炼 `topics/14-group-rules.md` 并补全速查卡；每日待分发结果仍属于业务工作区。工作区运营脚本未随此文档迁移。
- 1.3.6 修正过期分组任务树、`publish_log.json` 进度来源和每日结果存放口径；15 份 Patch 历史原文移至 `history/patches/`，Skill 内保留事故三列表与历史指针。
- 本次远端核查：patches `main` 仍为 `7ef76318bd7cb3265b9322faf95e71928ff0cf38`，A2 `main` 仍为 `b043748282a57e347c52f517dfb59819121134ab`，未发现新的 core 参考提交。后续发现变更按 `UPGRADING.md` 评估并移植适用改动。
- 已将 9 份历史快照及 `red-book-skills-upstream/`（含其未跟踪文件）共 10 份旧 `red-book-skills` 入口移至 `C:/xhs/_skill-backup/skill-scan-exclusions/legacy-collisions-20261107/`；SHA-256 清单验证一致，仓库内撞名检查通过。
- 2026-11-06 已配置 Local Agent Host 每日 10:00 运行备份。最新实跑生成源码快照（227 文件）及独立业务状态快照；台账 SHA-256 与原文件一致，路径记录于 `C:/xhs/_skill-backup/latest.json` 与业务状态 `MANIFEST.json`。二维码白名单当前不存在，未创建空文件。快照明文且同机，不能替代异机/离线备份，也不含 `.git` 历史。

## 一、交接时点的体检结论（2026-11-06 12:17 实跑 `tools/doctor.py`）

> 以下为 demo 历史快照，不代表当前仓库或最新修改的验证结果。

| 步骤 | 结果 |
| --- | --- |
| clean / check_env / ensure_compatible / post_sync_check / check_patch_versions | OK |
| unittest、check_public_release、**check_handover** | OK |
| **check_doc_layers** | **FAIL：`C:/xhs/.workbuddy/memory/topics/03-publish-rhythm.md` 9528 字符 > 上限 9000** |

退出码 1（仅警告）之外唯一的阻断项就是上面这条，**属业务工作区文档，不是 skill 代码缺陷**。
注意：本 skill 的 `topics/03-publish-rhythm.md` 已与工作区同步、同为 9528 字符；`doc_layers.json` 目前只校验
`${WORKSPACE}/.workbuddy/memory` 与各 patch 根，**不扫 `topics/`**，故 skill 侧不报红——但若日后把 `topics/`
纳入校验，这条会立刻变红，P0-1 应与 skill 一起解。
当时 demo 树无 `.git`；当前工作仓库有 Git，且含未提交修改。

**基线快照已生成**（升级前回滚点）：
`C:/xhs/_skill-backup/snapshots/20261106_111752_46a872c36a44b7e7`（1.3 MB，本体 13 文件 + 补丁 168 文件）。
该快照仅为历史参考；当前不得直接解压整树覆盖或以 checkout 丢弃现有修改，恢复须先审查范围及现存数据。

## 一之二、升级方式：**全量包落地 → git 取资源**（两阶段，2026-11-06 用户定）

> **历史方案，禁止直接照做**：当前仓库有未提交修改和本机数据；现行流程为 `UPGRADING.md` 的审查、逐项移植和验证，不整树覆盖。

### 历史阶段 A · 全量替换包

- 来源：远端 `Gitfork300/red-book-skills-patches`；本次是**全量更新包**，不是增量补丁。
- 角色：本机是**接收方**——只收、不改远端、**不推送**。
- 旧方案曾要求整树覆盖，可能丢失本地内容；当前禁止执行。
- 当前应先保全并审查本地修改，再按 `UPGRADING.md` 逐项移植和验证。

### 历史阶段 B · git 取资源

用户口径：「全量更新后，你要通过 git 获取资源」。即 git **不是**用来覆盖本地树的，而是覆盖完成后的**资源补全与差异核对**通道。

| 动作 | 允许 | 说明 |
| --- | --- | --- |
| `git ls-remote <repo>` | ✅ | 先确认远端 HEAD 与包内版本是否一致（对齐基线） |
| `git clone --depth 1 <repo> <树外临时目录>` | ✅ | 目标**必须在 skills 树外**，如 `C:/xhs/_upgrade_1106/_pkg_snapshot/`，只读比对 |
| `diff` / 逐文件 hash 比对 | ✅ | 用 §一之三 的 9 个 overrides + 14 个版本号判定「包是否真全量」 |
| `git pull` / `checkout` / `reset` / 整仓覆盖 | ❌ | 红线第 2 条：会静默回退本地定制（`cdp_publish.py` 等 9 个文件） |
| `apply_overrides.py rebase --from` / `post_sync_check.py --upstream` | ❌ | 旧布局工具，输入契约不满足，喂 A2/整仓快照会报错或误改 |
| 推送 / 建 PR / 改远端 | ❌ | 本机是接收方，无此授权 |

- 当时 demo 无 `.git`；当前仓库有 Git，须保护未提交修改。
- A2 是更新参考源，发现新提交须评估并移植适用改动；只有完成评估并记录理由后才确认提交，不得为消除告警提前 acknowledge。

## 一之三、本地定制清单（替换后逐项核对，缺一即停）

| 类别 | 内容 | 位置 | 替换后要求 |
| --- | --- | --- | --- |
| 代码定制（9 个文件，实测 overrides 与 runtime 逐一致） | `scripts/cdp_publish.py`（蜜罐过滤/-9130~9140 风控/三级发布激活）、`chrome_launcher.py`（脱离 job object）、`publish_pipeline.py`、`run_lock.py`（跨平台内核锁）、`INSTRUCTIONS.md`、`references/01,03,04,05` | `core-overrides/overrides/` | 9 个文件必须仍在，且 hash 与替换前一致 |
| 规则定制（14 个 patch） | 见 §五 版本台账 | 各 patch 目录 | 版本号不得回退 |
| 门禁与用例 | `tools/`（12 个 .py + `doc_layers.json`）、`tests/` | 根目录 | `doctor.py` 10 步可跑（9 步 OK + `check_doc_layers` 1 项工作区超限） |
| 可核对基线 | `HANDOVER_BASELINE.md`（`tools/gen_handover_baseline.py` 生成） | 根目录 | 替换后 `--check` 必须 OK；新包不含则先补回 |
| 交接文档 | 本文件 `HANDOVER.md` | 根目录 | **新包大概率不含 → 替换后立即补回** |
| 规则知识库 | `topics/` 15 篇 + `QUICKREF.md` | `topics/` | 含随 Skill 分发的分组规范；工作区副本须核对合并，不能整树覆盖 |
| 交接文档 | 本文件 `HANDOVER.md` | 根目录 | **新包大概率不含 → 替换后立即补回**；`doctor` 第 9 步 `check_handover` 会报警 |
| 工作区权威副本 | `MEMORY.md` + `topics/`（运行版，端口为真实值） | `C:/xhs/.workbuddy/memory/` | 不随包，独立存在，勿被 skill 覆盖 |
| 树外台账 | `_BUGS.md`、`_SKILL_OPT_BACKLOG.md` | `C:/xhs/` | 不随包 |
| 运行态（**已迁出**，2026-11-06） | `publish_log.json`、`.guard.lock`、`compatibility.json`、`__pycache__/`、`runtime/tmp/` | `<workspace>/.state/`（`C:/xhs/.state`） | **不随包**；新机跑 `python tools/runtime_paths.py --init` 建目录 |
| 账号配置 | `runtime/config/accounts.json`（本机状态，不随包） | 树内忽略文件 | 不复制 demo 的本机配置；新机由账号管理器生成或配置 |

## 一之四、自包含核对（为什么本 skill 能单机直接用）

用户 11-06 定：本 skill 要**既能单机部署、又是升级基线**。以下 6 项是「自包含」的判据，替换后逐项过：

| # | 判据 | 现状 |
| --- | --- | --- |
| 1 | 无外部依赖，不读同级 `red-book-skills`、运行时不联网 GitHub | ✅ `SKILL.md` 已声明 |
| 2 | 依赖可重建：`requirements.txt` + `tools/setup_runtime.py` + `tools/init_runtime.py` | ✅ 三件齐全（`.venv` 197 MB **不入包**，新机重建） |
| 3 | 脚本无硬编码绝对路径 | ✅ 已扫，路径走 `XHS_WORKSPACE` 等环境变量 + 缺省回落 |
| 4 | 敏感值脱敏、且**脱敏规则有文档**：端口写 `<PORT_PUBLISH>` / `<PORT_COMMENT>` | ✅ 见 `HELP.md` Q&A：发布实例＝**9333**、评论实例＝**9222**（新机照此复刻即可还原） |
| 5 | 规则正文随 Skill 分发 | `topics/` 15 篇 + `QUICKREF.md`；业务执行器须单独确认可用 |
| 6 | 本机账号和登录态不随包 | ✅ 仓库不携带 `runtime/config/accounts.json`；由本机账号管理器生成或配置 |

⚠️ **第 4 条是本次最重要的一条发现**：`topics/` 与工作区副本的差异，**大部分是脱敏造成的假差异**（`9333→<PORT_PUBLISH>`、`9222→<PORT_COMMENT>`）。
此前把 8 个差异文件一律当「漂移」，会得出「裸拷贝工作区覆盖 skill」的错误结论——那会把真实端口写回公开包，且破坏分发口径。
**正确的同步方式＝带上脱敏替换再回灌**，本次已按此执行。

## 一之五、运行态归集：state 全部搬出 skill 树（2026-11-06 用户裁定）

### 为什么要搬

历史整树替换会冲掉 skill 树内的 state；当前升级禁止直接整树覆盖：

| 文件 | 留在树内的实际后果 |
| --- | --- |
| `publish_log.json` | 台账丢 → 判重从 0 开始 → **可能重发当天已发过的内容** |
| `.guard.lock` | 本机内核锁承载文件，不应复制；文件存在不等于持锁，未过期 pending 才会持续拦截 |
| `compatibility.json` | 缓存里记绝对路径 → 换机/换目录后指纹永不对，等于每次重算 |
| `__pycache__/`（15 个） | 880 KB 垃圾；`.pyc` 混进覆盖层清单会永久 DRIFTED（红线 4） |
| `runtime/tmp/` | `login_status_cache.json` 丢失 → 登录态要重探，多一次浏览器往返 |

### 新布局（唯一权威：`tools/runtime_paths.py`）

```
<workspace>/.state/            ← XHS_STATE_ROOT（缺省 C:/xhs/.state，整棵树替换时保留）
├── publish/publish_log.json   ← 台账
├── publish/.guard.lock        ← 间隔锁承载文件（常驻，不删）
├── cache/compatibility.json   ← 兼容缓存（只存相对路径 main_rel="runtime"）
├── pycache/                   ← sys.pycache_prefix 指向此处
└── tmp/                       ← XHS_RUNTIME_TMP 指向此处
```

覆盖优先级：`XHS_INTERVAL_LOG` / `XHS_INTERVAL_STATE_DIR` / `XHS_STATE_ROOT` / `XHS_COMPAT_CACHE` / `XHS_RUNTIME_TMP` > 上述默认。

### 改了哪些代码（4 个 patch + 2 个工具）

| 文件 | 改动 |
| --- | --- |
| `publish-interval-guard/helpers/publish_interval.py` | `STATE_DIR/LOG/LOCK` 改由 runtime_paths 解析；加锁前建目录 |
| `publish-loop-guard/helpers/dup_check.py`、`check_missing.py`、`title_tag.py` | `LOG_PATH` 同一套解析（`title_tag --scan` 也是） |
| `timeliness-window/helpers/quota_check.py` | 同上 |
| `core-overrides/overrides/scripts/cdp_publish.py` | `LOGIN_CACHE_FILE` 读 `XHS_RUNTIME_TMP`，未设时回落旧路径 |
| `tools/setup_runtime.py` | 写入 venv 的 `sitecustomize.py` 增加 `sys.pycache_prefix` + 注入 `XHS_RUNTIME_TMP` |
| `tools/ensure_compatible.py` | 缓存改到 `.state/cache`；指纹与 `main_rel` 全部用**相对路径** |

### 新增工具

- `tools/runtime_paths.py`：路径权威。`--json` 打印解析结果，`--init` 建目录并迁移旧状态（幂等）。
- `tools/clean_artifacts.py`：一次性清扫——删树内 `__pycache__`、把 `runtime/tmp` 内容搬走。`--dry-run` 可预演。

### 迁移实况（2026-11-06 12:12–12:17 实跑）

```
publish_log:    migrated → C:/xhs/.state/publish/publish_log.json（旧址改名 .migrated-20261106）
compatibility:  migrated → C:/xhs/.state/cache/compatibility.json（同）
树内 __pycache__ 15 个 / 880 KB → 已清除（后续字节码写入 .state/pycache）
runtime/tmp 1 个文件 → 已搬到 .state/tmp（取了较新副本，sha256 48d929c88934）
旧 .guard.lock → 退役到 _skill-backup/artifacts_20261106/
```

验收：`title_tag --scan` 读到 **100 篇**（证明读到迁移后的台账）；`dup_check --title "<最近标题>"` 正确判重；
`apply/verify` 9 文件一致；`ensure_compatible --refresh` 缓存写 `main_rel:"runtime"`；doctor 10 步仍只有 P0-1 一项红。

### 遗留与坑（接手必看）

1. **升级前已启动的进程仍写旧址**：`sys.pycache_prefix` 与 `XHS_RUNTIME_TMP` 由 venv 的 `sitecustomize` 在**进程启动时**注入，
   12:12 之前起的进程（`_keep9333` 等）内存里还是旧路径，会继续往 `runtime/tmp` 写。**重启后自然归位**，不需要改代码。
2. **工作区旧脚本硬编码了旧址**（不在本次范围，但升级后若复用需改）：`weather/_audit_interval_0917.py`、
   `weather/_logtail_0917.py`（还写着已失效的旧用户名路径）、`xhs_publish/publish/_publish_chain_{P0916,round4,round5}.py`。
   现行链脚本走 `dup_check.py` 子进程，**不受影响**。
3. **`state/*` 其余文件没动**：`core-overrides/state/applied.json`（应用状态）、`cover-image-rules/state/qr_whitelist.json`（业务白名单）
   仍在树内 —— 前者随包换新无害（apply 会重算），后者是业务数据，**升级前要单独备份**。

### P0-4（✅ 已修 2026-11-06 11:50）`core-overrides/META.json` 曾漏列 5 个覆盖文件
原 `files` 只登记 8 项，漏 `overrides/references/01/03/04/05`（4 个）与 `overrides/scripts/run_lock.py`；
`contracts.json`、`state/applied.json` 也未列。全量包若按 META 清单搬运，本地定制只会带走 4/9，
`run_lock.py` 丢失会退回旧式文件锁（B-041 同族竞态）。

**已修**：`files` 补至 **15 项**、`overrides.targets` 补至 **9 项**（与 `overrides/` 实有 9 个文件逐一对应，脚本校验无缺项）；
`baseline.json` 按既有 `upstream_absent` 模式补入 `scripts/run_lock.py`（注明纯本地新增、无上游对应）；
`core-overrides` 版本 1.5.0 → **1.5.1**，`SKILL.md` / `META.json` / `INDEX.md` 三处已同步，`check_patch_versions` 通过。
注意：apply/verify 的受管清单来自 `_file_list()` 遍历目录，**不读 META**，故本次修改不影响 apply 行为。

### P0-5（✅ 已修 2026-11-06 12:05）树内发布失败截图残留
`runtime/scripts/xhs_publish_fail.png`（350 KB，2026-10-21 留下的发布失败截图）混在脚本目录。

**它本身不是无用文件，是运行时产物**：`cdp_publish.py` 在发布失败分支里用
`Page.captureScreenshot` 写到脚本同目录（`runtime/scripts/`），下次失败会自动重写。
`core-overrides/contracts.json` 里把它列进 `we_add`，但那是核验**脚本里存在该字符串**（`post_sync_check` 读脚本），
**不要求 png 存在**——删掉不会触发契约告警，已实跑验证。

**已处置**：移到树外 `C:/xhs/_skill-backup/artifacts_20261106/xhs_publish_fail_20261021.png`
（sha256 前 16 位 `9afe4599bc5ed3fa`，可回滚）；副本包内同名文件一并清除，避免 350 KB 冗余随包下发；
`.gitignore` 增 `runtime/scripts/*.png` 并注明成因，防止再入库。
**注意**：不要把它加进 `core-overrides/overrides/`——那是受管源码清单，产物不属于覆盖层，加进去会造成「文件不存在=DRIFTED」。

## 二、升级前必须先定三件事（否则升完会倒退）

### P0-1 修 doctor 阻断（文档分层超限，本次整合已修）
- 位置：`C:/xhs/.workbuddy/memory/topics/03-publish-rhythm.md`（9528 字符 / 213 行，上限 9000/260）。
- 按用户「调上限优于删条目」的约定，上调工作区入口和详情字符上限；行数上限保持不变。
- 验收：`python tools/doctor.py` → 退出码 ≤1 且无 check_doc_layers 项。

### P0-2 发布间隔口径**全树不一致**（本次整合已修）
现行口径是 **360–840 秒（6–14 分钟随机）**（2026-10-31 收窄，见 `publish-interval-guard/SKILL.md`），
整合前下列规则文件写着旧值 `8~12 分钟 / 下限 8 / 480–720`；本次已统一为现行口径：

| 文件 | 行 |
| --- | --- |
| `publish-preflight-guard/SKILL.md` | 34（第 13 项闸门） |
| `publish-loop-guard/SKILL.md` | 32、110 |
| `core-overrides/overrides/INSTRUCTIONS.md` | 29、70、114 |
| `core-overrides/overrides/references/01-publish-flow.md` | 87、119、158 |
| `core-overrides/overrides/references/03-constraints.md` | 93 |
| `core-overrides/overrides/references/05-patches-upstream.md` | 22 |
| `runtime/INSTRUCTIONS.md`、`runtime/references/01|03|05` | 同上镜像，随 apply 同步 |
| `xhs-risk-guard/SKILL.md` | 63（E1 行） |
| `INDEX.md` | 39（patch 表用途列） |

⚠️ **假绿陷阱**：旧文档锚点命中历史沿革不代表现行规则正确。本次已同步更新
`tools/doc_layers.json` 的现行口径锚点；以后调整时仍须同步检查所有生效副本与脚本默认值。
本仓库及 `C:/xhs/.workbuddy/memory/topics/` 的相关生效规则已核对同步；
历史记录保留原始口径，以后修改时仍须检查两处。

### P0-3（✅ 已修 2026-11-06 11:58）topics 双副本：8 个「漂移」实为 5 假 3 真
复核结论（逐行 diff，脱敏归一后判定）：

| 类型 | 文件 | 结论 |
| --- | --- | --- |
| **假差异**（仅端口脱敏） | 06、07、09、10、12 共 5 篇 | skill 是**脱敏版**（`9333→<PORT_PUBLISH>`、`9222→<PORT_COMMENT>`），内容与工作区完全一致，**不是漂移、不用动** |
| **真差异**（新规则未入 skill） | 03（+12 行）、08（+15 行）、11（+18 行） | 均为 11-04 / 11-06 用户新裁定：**Z 纪律**、**源闸门配额 v1.3**、**天气兜底 B-130「只能正推不能反否」**、`_quota_source_gate.py` 入链路 |

**历史处置**：把 03/08/11 三篇按脱敏规则回灌进 `topics/`（原文件备份在
`C:/xhs/_skill-backup/topics_before_backfill_20261106/`）。当时复核 14 篇一致；
当前双副本存在少量措辞或迁移说明差异，现行台账位置与天气间隔已重新核对，不再宣称逐字零漂移。
`QUICKREF.md` 为 skill 独有速查页，工作区不需要，保留即可。

**下游影响**：此项未修前，交接出去的是**缺 Z 纪律与源闸门 v1.3 的旧规则集**——下一 agent 会照旧口径排配额、把无源缺口挂 Z。
现已在包内。后续任何工作区规则改动，都需按同一脱敏规则回灌一次（建议做成 `tools/sync_topics.py --desensitize`）。

## 三、待办清单（升级范围内的正式条目）

| ID | 优先级 | 事项 | 判据／验收 |
| --- | --- | --- | --- |
| P0-1 | ✅ | 调整工作区文档上限 | 用户运行 doctor 的 check_doc_layers 为 OK |
| P0-2 | ✅ | 统一间隔口径 6–14 分钟并更新锚点 | 已核对生效规则，2026-11-06 复核补正工作区天气规则 |
| P0-3 | ✅ | 已回灌 03/08/11 并补充分组规范 | 新增 `topics/14-group-rules.md`；保留工作区业务结果，不整目录覆盖 |
| ~~P0-5~~ | ✅ | 移出 `runtime/scripts/xhs_publish_fail.png`（350KB 产物）→ `_skill-backup/artifacts_20261106/`；`.gitignore` 增 `runtime/scripts/*.png` | 已验：`post_sync_check` OK、`doctor` 无新增红项 |
| P1-4 | ✅ | GitHub 核实 A2 `main` 仍为 `b043748282a57e347c52f517dfb59819121134ab`，与 `core-overrides/baseline.json` 一致；`b006891...` 属于另一仓库，不作为 A2 基线。更新器网络请求被重置，改用 GitHub commit 列表核验；已清除同 SHA 的 pending | 无新上游提交；pending 已清除，现有 core 基线不需更新 |
| P1-5 | ✅ | `backup_snapshots.py` 已分开备份源码、发布台账及二维码白名单；Local Agent Host 每日 10:00 已配置并实跑验证。二维码白名单源文件当前不存在，不生成空文件 | 源码保留 30 份，业务状态副本不自动轮转并经 SHA-256 校验；C/D 属同一物理盘，已明确仅防误改/覆盖，未配置异机/离线灾备 |
| P1-6 | ✅ | 修正活跃规则中过期分组任务树、`publish_log` 用途、组间隔和每日结果存放口径；事故复盘改为当前可执行的判据/处置摘要 | 旧历史原文归档；活跃规则按 `SKILL.md`、`topics/14-group-rules.md` 及各组三列表复核 |
| P2-7 | ✅ | 15 份 Patch changelog / incident 原文（75,276 bytes）移至 `history/patches/` 保留；Skill 内用 3 列事故速查或历史指针替代 | `history/README.md` 可索引原文；摘要与指针留在原路径，`check_doc_layers` 验证无孤儿 |
| P2-8 | ✅ | `INDEX.md` 表格瘦身为简要用途与各 Patch 入口 | 保留版本校验工具要求的名称、优先级和版本列；详细规则以各 Patch 为准 |
| P2-9 | ✅ | `topics/QUICKREF.md` 汇总现行硬规则并列出八个发布 patch | 单测验证不超过 6000 字符；详细规则和工作区执行器仍需按需核查 |
| P2-10 | ✅ 不实施 | 已评估：现架构以完整受管文件为权威源，按基线 SHA 检查双方漂移，再由 apply/verify 整文件复制；diff 会引入补丁叠加、冲突裁决和回滚语义 | 保持完整副本架构；如未来要改，须另立迁移方案及兼容测试，不把 diff 与本次更新混做 |
| P2-11 | ✅ | `.venv/` 留在技能树内 | 已验证 `.gitignore` 排除；体积和本机扫描开销仍存在 |
| P2-12 | ✅ | 9 份历史快照与上游参考 clone 共 10 个旧 `red-book-skills` 入口移出仓库扫描范围 | 外置 `RELOCATION-MANIFEST.json` 记录 SHA-256；`check_skill_name_collisions.py --root .` 无撞名 |

## 四、工程线遗留（**不在本次升级范围**，别顺手改 runtime）

以下均登记在 `C:/xhs/_BUGS.md`，属运营脚本/环境调度问题：

| 编号 | 状态 | 一句话 |
| --- | --- | --- |
| B-046 | 未修 | 9222（评论 profile）登录态无自动恢复路径 |
| B-105 / B-117 | 已遏制未根治 | 后台链随会话被整体回收 → 起链必须「常驻托管器（while True）+ 后台任务」，禁用一次性 boot 脚本 |
| B-111 | 已遏制 | 发布树双进程嵌套，同一篇被两个 `publish_one` 并发 |
| B-112 | 未修 | 文档分层锚点词表过期 → 假红/假绿（与 P0-2 同源） |
| B-116 | 未修 | 5 个长期 recurring 在本环境无法确认存活（属用户侧重建） |
| B-118 | 半修 | 「时段全不可发→长等 300s」只修在当日链脚本，`_make_chain_scripts.py` 模板未固化 |
| B-119 | 未修 | 天气兜底脚本只查 `findAlarm`，漏「台风正式编号」→ 假阴性 |
| B-120 | 未修 | 巡检调度器午轮后被回收，晚轮 20:30 漏跑 |

## 五、版本台账（交接时点，均与 `META.json` 一致）

| patch | ver | pri | patch | ver | pri |
| --- | --- | --- | --- | --- | --- |
| root `SKILL.md` | 1.3.6 | — | `publish-interval-guard` | 1.6.1 | 20 |
| `core-overrides` | 1.5.4 | 2 | `timeliness-window` | 1.9.1 | 22 |
| `update-checker` | 1.5.0 | 5 | `organizer-qualification-guard` | 1.3.0 | 23 |
| `windows-sandbox-workaround` | 1.7.0 | 10 | `publish-preflight-guard` | 1.20.0 | 25 |
| `comment-reply-guard` | 1.24.1 | 11 | `publish-loop-guard` | 1.13.3 | 28 |
| `xhs-risk-guard` | 1.3.0 | 12 | `writing-facts-only` | 1.6.2 | 30 |
| `safe-wording-guard` | 0.8.0 | 15 | `cover-image-rules` | 1.8.3 | 50 |
| `daily-closeout-guard` | 1.4.1 | 60 | | | |

## 六、升级标准动作（顺序不可换）

```powershell
# 0) 回滚点（已做：20261106_111752_46a872c36a44b7e7）
.\.venv\Scripts\python.exe tools\backup_snapshots.py

# 1) 改动只进覆盖层，不直接改 runtime/scripts
#    改完跑：
.\.venv\Scripts\python.exe core-overrides\helpers\apply_overrides.py apply --dry-run
.\.venv\Scripts\python.exe core-overrides\helpers\apply_overrides.py apply
.\.venv\Scripts\python.exe core-overrides\helpers\apply_overrides.py verify

# 2) 全链验收（任何一项红都停，不许跳过发布）
.\.venv\Scripts\python.exe tools\doctor.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
.\.venv\Scripts\python.exe tools\ensure_compatible.py --refresh
.\.venv\Scripts\python.exe tools\check_patch_versions.py
.\.venv\Scripts\python.exe tools\check_doc_layers.py
.\.venv\Scripts\python.exe tools\check_skill_name_collisions.py
```

改版本号必须**四处同步**：`SKILL.md` frontmatter、`<patch>/META.json`、`INDEX.md` 版本列、
以及 `core-overrides/baseline.json` / `contracts.json` / `state/applied.json`（改了覆盖层文件名时）。
root `SKILL.md` 无 `META.json`、不在 `check_patch_versions` 覆盖范围内，**版本靠人工维护**——改它必须同时改 §五 台账与 §九 记录。

### 🔴 记录纪律（用户 11-06 强调：近期更新记录很重要）

**一条改动 = 一次登记，且登记必须与最终文件逐项对得上。**

| 改了什么 | 必须同步登记 |
| --- | --- |
| **任何受管文件**（覆盖层 / patch / topics） | 重跑 `python tools/gen_handover_baseline.py`，让 `HANDOVER_BASELINE.md` 重新对齐 |
| 任何 `SKILL.md` / `META.json` | 版本号（四处）+ 本卡 §五 台账 + §九 记录行 |
| 覆盖层 9 个文件任一 | 重算 sha256 写入树外 `overrides_hashes.txt` + §九 记录行 |
| `topics/` 回灌 | §一之三 表内篇数与漂移状态 + §九 记录行 |
| 新增/删除文件 | §一之三 清单 + `check_patch_versions` / `doctor` 复跑结果 |
| 只改文档、不改行为 | 也要记录，并注明「无行为变更」——否则下次核对会误判为漏登记 |

禁止「先改后补」跨天：**当天没写进 §九 的改动，视为未发生**（下一个 agent 会按卡上的版本号去核对实物，对不上就回滚）。
写完记录必须**复跑一次验收命令**并把结果填进「验收命令与结果」列，不许写「应该没问题」。

**历史全量替换包步骤已停用**：以下保留背景，不得对当前仓库执行整树覆盖或直接回滚；现行流程见 `UPGRADING.md`。

0. **收包前**：把 `HANDOVER_BASELINE.md` 拷到树外留底（9 个覆盖文件 hash + 15 个版本 + topics 字符数，
   现成副本：`C:/xhs/_upgrade_1106/_handover_refs/overrides_hashes.txt`）。
1. **历史阶段 A** 曾要求整树覆盖及快照回滚；现改为审查差异并逐项移植，异常时停止并核对备份。
2. **补回桥梁**：新包若不含 `HANDOVER.md`，先从 `_upgrade_1106` 副本或快照补回，**再**做任何记录（否则记录无处可写）。
3. **阶段 B git 取资源**：`ls-remote` 对齐基线 → `clone --depth 1` 到**树外**临时目录 → 逐文件 diff。
   **只用来核对与取料，不得回写运行层**（详见 §一之二 表）。
4. **登记**：把本次升级写进 §九（版本 + 摘要 + 实跑结果），复跑 doctor，同步 `_handover_refs/overrides_hashes.txt`。

## 七、八条红线（踩了会静默回退或丢改动）

1. **不直接改 `runtime/`**；改动进 `core-overrides/overrides/` 再 apply。
2. **A2 快照不得整仓覆盖**，也不得喂给 `apply_overrides.py rebase --from` 或 `post_sync_check.py --upstream`（旧布局工具，输入契约不满足）。
3. 覆盖层持有受管文件的完整权威副本；不得盲目将旧上游快照写入并 apply，以免回退当前改动。
4. `overrides/scripts/__pycache__/*.pyc` 会永久 DRIFTED → 先 `apply_overrides.py clean`。
5. 删 `refs/` 索引行会触发「孤儿文件」；文件名含 `changelog|archive|incidents` 才豁免。
6. skills 树内**不得留 `SKILL.md` 副本**（扫描器按 frontmatter `name` 注册，撞名会静默回退）。
7. 加 `description` 会顶破 6000 字符上限；每加一条都要复测（另见 BACKLOG 踩坑 3）。
8. 备份/导出/临时快照一律放树外 `C:/xhs/_skill-backup/`。

> **关于本卡（用户 11-06 定：交接卡是两端的桥梁）**：上列八条是技术红线，本卡另有两条**流程红线**——
> ① **不得删除、改写口径或弱化 `HANDOVER.md`**（`doctor` 第 9 步 `check_handover` 已守：缺文件或缺「全量替换包 / 本地定制清单 / 升级记录表」三锚点即告警）；
> ② **不得凭印象改卡**——卡上每个版本号、hash、篇数都必须能对应到实物，写不出实物依据就先核实再写。

## 八、接手第一句回执（历史，勿作为当前状态）

> 「已接 red-book-skills-patch **1.3.0** 大版本升级交接；基线快照 20261106_111752；
> 当前唯一阻断＝P0-1 文档超限（workspace 03-publish-rhythm.md 9528>9000）；
> 先做 P0-1→P0-2，再看 P1-4/P1-5；升级走『全量包落地 → 验收 → git 取资源核对』，不推送、不用 git 覆盖运行层。」

当前接手应先核实 Git 工作树、最新基线和未完成事项，按 `UPGRADING.md` 执行；不假定历史阻断仍存在。

## 九、升级记录表（下一 agent 逐条追加，勿删旧行）

| 日期 | 版本 | 改动摘要 | 验收命令与结果 | 操作者 |
| --- | --- | --- | --- | --- |
| 2026-11-06 | 1.2.0 | 交接盘点；生成基线快照；doctor 实跑（1 阻断） | doctor → 仅 check_doc_layers FAIL | WorkBuddy (Eric 会话) |
| 2026-11-06 | 1.2.0 | 登记升级方式＝远端全量替换包（接收方，不推送，~~git 待通知~~ → 已由 12:00 行改为「全量包落地 → git 取资源」两阶段）；补本地定制清单、P0-4 META 漏登记、P0-5 树内残留 | 9 个 overrides 与 runtime 逐文件 hash 一致；3 个未纳管脚本无本地改动痕迹 | WorkBuddy (Eric 会话) |
| 2026-11-06 | core-overrides 1.5.1 | 修 P0-4：`files` 8→15、`targets` 4→9、baseline 补 run_lock（upstream_absent）；doctor 新增 `check_handover` 步骤（warn 级）守住交接卡 | `check_patch_versions` OK；META 15 项全部存在、9 个 targets 全覆盖；doctor → 仅原 check_doc_layers FAIL | WorkBuddy (Eric 会话) |
| 2026-11-06 | root 1.2.1 | 修 P0-3：查明 8 个 topics「漂移」中 5 个仅脱敏差异（06/07/09/10/12），3 个为真增量（03 Z 纪律 / 08 B-130 天气兜底 / 11 源闸门 v1.3），按脱敏规则回灌；新增 §一之四 自包含 6 项判据；登记升级两阶段（全量包 → git 取资源）与记录纪律 | 回灌后 14 篇脱敏归一 diff=0、0 漂移；`check_public_release` OK；doctor → 仅原 check_doc_layers FAIL（9 步中 8 OK） | WorkBuddy (Eric 会话) |
| 2026-11-06 | root 1.2.1 | 新增 `HANDOVER_BASELINE.md`（9 hash + 15 版本 + topics 字符数 + 结构判据）与生成器 `tools/gen_handover_baseline.py`（`--check` 校验）；`doctor` 增第 10 步 `check_baseline`（warn）；补记「记录纪律」表 | `gen_handover_baseline.py --check` → OK；doctor 10 步 → 9 OK + 仅 check_doc_layers FAIL | WorkBuddy (Eric 会话) |
| 2026-11-06 | root 1.2.1 | 修 P0-5：`runtime/scripts/xhs_publish_fail.png`（350KB，10-21 失败截图产物）移出至 `_skill-backup/artifacts_20261106/`（sha256 `9afe4599bc5ed3fa`）；`.gitignore` 增 `runtime/scripts/*.png`；副本包内同名文件一并清除 | `post_sync_check` OK（contracts 只核脚本内字符串）；doctor 10 步 → 9 OK + 仅 check_doc_layers FAIL | WorkBuddy (Eric 会话) |
| 2026-11-06 | root 1.3.0 | 运行态归集（用户裁定）：台账/锁→`C:/xhs/.state/publish`、兼容缓存→`.state/cache`（只存相对路径）、`__pycache__`→`.state/pycache`（sys.pycache_prefix）、`runtime/tmp`→`.state/tmp`；新增 `tools/runtime_paths.py`、`tools/clean_artifacts.py`；4 个 patch 改路径解析，版本 1.6.0 / 1.13.3 / 1.9.1，core-overrides 1.5.2（cdp_publish 读 XHS_RUNTIME_TMP） | 迁 100 条台账 + 兼容缓存 + 1 个 tmp 文件，清 15 个 `__pycache__`（880KB）；`title_tag --scan`=100 篇、`dup_check` 正确判重；apply/verify 9 文件一致；doctor 10 步仅 P0-1 红 | WorkBuddy (Eric 会话) |
| 2026-11-06 | root 1.3.1–1.3.2 | 整合 1106 demo，更新 6–14 分钟规则、状态保护、装机和上游检查；保留原有台账 | 43 项回归通过；用户手动 doctor 10 步 OK | Copilot |
| 2026-11-06 | root 1.3.3 | 复核交接事项，修复版本备份私有文件采集及台账路径文档，登记剩余冲突和备份事项 | 44 项回归、9 文件 verify、契约、版本、文档、交接基线、公开发布检查均通过；技能撞名检查发现 10 份旧副本 | Copilot |
| 2026-11-06 | root 1.3.3 | 在工作区外保存源码快照，不覆盖既有备份 | ZIP CRC 和 172 项 SHA-256 校验通过；忽略项、Git 历史和业务状态不在快照内 | Copilot |
| 2026-11-06 | root 1.3.4、core-overrides 1.5.4、cover-image-rules 1.8.2 | 统一现行规则，保护使用方已安装环境，补充维护方环境方案；用户备份并应用受管说明 | 45 项 unittest、文档分层、版本、公开发布、pip check、交接基线及 9 文件 verify 通过；本次未重跑完整 doctor | Copilot / 用户 |
| 2026-11-06 | root 1.3.5 | 补充分组强制规范及速查卡，修正索引和锁语义，重新生成交接基线 | 47 项 unittest、文档分层、版本、公开发布、pip check、交接基线、9 文件 verify 与 33 项契约检查通过；未迁移业务脚本或改变现有台账 | Copilot |
| 2026-11-06 | root 1.3.6、cover-image-rules 1.8.3 | 修正分组任务树和台账用途冲突；二维码白名单迁入工作区状态；源码与业务状态分开备份；历史 changelog/incidents 外移并保留三列速查；确认 A2 无新提交 | 52 项 unittest、版本、文档分层、发布安全、交接基线通过；源码快照（227 文件）及业务台账快照经 SHA-256 校验；Local Agent Host 每日 10:00 已配置；更新器直连网络错误，GitHub commit API 核实 A2 仍为基线 | Copilot |
| | | | | |
