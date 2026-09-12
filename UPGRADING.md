# 升级主 skill 后的 patch 处理指南

> 当 `aus666666/red-book-skills` 有新版本时，本指南说明如何安全地把上游改动与我们的 patch 合并。

## 总原则

用户于 2026-09-12 定下的架构原则：

> **我们自己的更新放 patch，原始本体定期和 GitHub 同步。**

据此，两类东西必须分清：

| | 位置 | 内容 | 谁维护 |
| --- | --- | --- | --- |
| **本体** | `~/.workbuddy/skills/red-book-skills/` | 上游代码 + 覆盖层的**应用产物** | 上游 + `core-overrides` apply |
| **patch** | `~/.workbuddy/skills/red-book-skills-patches/` | 我们的**全部**定制 | 我们 |

本体里有 4 个文件被我们改过，它们的**权威副本在 `core-overrides/overrides/`**。
所以同步上游 = 覆盖本体 → `apply` 一次。

> **不再需要人工逐条"把本地改动打回去"。** 旧版本文件里那张 22 条的迁移清单
> 已被 `core-overrides` 机制取代，清单内容现在等价于覆盖层的 4 个文件（见
> `core-overrides/SKILL.md` 的「覆盖清单」）。

## 标准同步流程（照做即可）

```bash
PY=<解释器>   # 建议 <本体>/.venv/Scripts/python.exe
P=~/.workbuddy/skills/red-book-skills-patches

# 0. 先看清上游改了什么、会不会和我们的覆盖撞车
$PY $P/update-checker/helpers/update_check.py diff-local
#    看到「覆盖层冲突检查」报 !! → 先停止，按「覆盖层冲突处理」合并

# 1. 覆盖本体（本体不是 git 仓库，见下节）
#    ...

# 2. 重新应用我们的覆盖
$PY $P/core-overrides/helpers/apply_overrides.py status   # 预期全部 PRISTINE
$PY $P/core-overrides/helpers/apply_overrides.py apply

# 3. 校验
$PY $P/core-overrides/helpers/apply_overrides.py verify   # 预期 OK

# 4. 跑自测 + 端到端
<本体>/.venv/Scripts/python.exe -m pytest <本体>/tests/ -q

# 5. 更新基线 + 标记已读
#    把 core-overrides/baseline.json 的 baseline_commit / upstream_sha256 更新为新的上游版本
$PY $P/update-checker/helpers/update_check.py acknowledge --sha <新 sha>
```

## 本体不是 git 仓库 —— 同步方式不是 `git pull`

`~/.workbuddy/skills/red-book-skills/` 是**拷贝安装**的，没有 `.git`：

- ⚠️ 旧文档里的 `cd <本体> && git pull origin main` **会直接失败**
  （`fatal: not a git repository`），不要照抄。
- 正确做法是**下载上游快照覆盖文件**。

```bash
# 下载并解压上游
curl -sL https://codeload.github.com/aus666666/red-book-skills/tar.gz/refs/heads/main -o /tmp/up.tgz
mkdir -p /tmp/up && tar xzf /tmp/up.tgz -C /tmp/up

# 覆盖本体（保留本体独有的 helpers/、config/accounts.json）
cp -r /tmp/up/red-book-skills-main/. "<本体>/"

# 立刻 apply 我们的覆盖
$PY $P/core-overrides/helpers/apply_overrides.py apply
```

> 注意：覆盖只是"上游文件盖过来"，**不会删**本体里上游没有的文件
> （我们的 `helpers/`、`config/accounts.json` 等本来就该保留）。

**长期建议**：把本体 git 化，同步就变成 `git fetch upstream && git diff`，
能精确看到上游每次改了哪一行。见文末「可选：让本体成为 git 仓库」。

## 覆盖层冲突处理（core-overrides）

`diff-local` 会读 `core-overrides/baseline.json`，把**上游也改动过的被覆盖文件**标为冲突：

```
=== 覆盖层冲突检查（core-overrides/baseline.json）===
  !! 上游改动了 1 个被我们覆盖的文件 —— 直接覆盖会丢上游改动：
     SKILL.md
       基线=68a233e80c20   上游当前=ab12cd34ef56
     处置：把上游改动人工合并进 core-overrides/overrides/ 后再 apply
```

此时**不要直接覆盖本体**，否则上游这次改动就丢了。正确顺序：

1. `diff-local` 看到上游版本，人工读上游改了什么
2. 把上游改动**手工合并**进 `core-overrides/overrides/<文件>`
   （即：让覆盖层 = 上游新版 + 我们的改动）
3. `apply_overrides.py apply`
4. 更新 `baseline.json` 的 `upstream_sha256` 为新的上游 hash，`baseline_commit` 为新 commit

## 三种更新场景与对应处理

### 场景 A：更新只影响文档/示例

典型：README 调整、注释更新。

处理：走**标准同步流程**即可。注意 `SKILL.md` 在覆盖清单里，
所以覆盖后必须 `apply`，否则所有 patch 规则会失效。

### 场景 B：更新改了 `scripts/` 但签名兼容

典型：内部重构、性能优化、修了某个边缘 bug。**这类最需要小心**——
`cdp_publish.py` / `chrome_launcher.py` / `publish_pipeline.py` 三个都在覆盖清单里。

处理：

1. `diff-local` + 逐文件看上游 diff
2. 若上游改的就是我们覆盖过的区域 → 按「覆盖层冲突处理」合并进 `overrides/`
3. `apply` → 跑自测：

   ```bash
   <本体>/.venv/Scripts/python.exe -m pytest <本体>/tests/ -q
   ```
4. `acknowledge --sha`

### 场景 C：更新含 BREAKING

典型：`--content-declaration` 取值变了；`verify-note` 改名/删除；`SELECTORS` 重写。

处理：

1. **不要立即覆盖**。先读上游 README/CHANGELOG（或 `diff-local` 看 diff）
2. 对照 `patches/*/META.json` 的 `conflict_points` 与下方「冲突点检查清单」
3. 改覆盖层：把兼容性适配写进 `core-overrides/overrides/` 对应文件
4. 覆盖本体 → `apply` → 端到端测试（登录 → 发布 → verify → record）
5. 更新各 patch 的 `applies_to_main_version` 与 `version`，`acknowledge --sha`

## 冲突点检查清单（按 patch 分组）

| Patch | 检查项 |
| --- | --- |
| `core-overrides` | **本体 4 个文件的覆盖是否仍适用**：`cdp_publish.py` 的发布按钮选择器与 `SELECTORS` 结构、`chrome_launcher.py` 的启动函数签名、`publish_pipeline.py` 的 CLI 参数、`SKILL.md` 的章节结构 |
| `windows-sandbox-workaround` | `scripts/cdp_publish.py` 的 `--title / --content-file / --images / --content-declaration / --reuse-existing-tab` 参数；CDP `Browser.close` 行为；tag attach 机制 |
| `publish-interval-guard` | 不依赖主 skill 代码（纯本地落盘）；但依赖 `publish_pipeline.py` 调用它的 hook（在覆盖层里） |
| `cover-image-rules` | `publish` 是否支持 `--content-declaration`；声明文案枚举是否变化 |
| `writing-facts-only` | 纯内容策略，与代码无关 |
| `publish-loop-guard` | 纯流程编排 + 只读复核；只依赖稿件目录与发布日志的路径约定 |
| `update-checker` | 纯本地状态；`diff-local` 依赖上游仓库结构（顶层需有 `SKILL.md`） |
| `timeliness-window` | 纯本地判断 + 网络检索 |
| `publish-preflight-guard` | 汇总各 patch 的检查项，项数随其它 patch 变化 |
| `safe-wording-guard` | 纯文本检查 |

## 自动化检查

`update-checker` 已注册每周五 10:00 自动检查（automation id `7d437f5c`）。

> **已知特性**：`check` 在"距上次 < interval(7天)"时直接 `exit 0` 且**不写状态**。
> 于是"每周五触发 + 7 天间隔"实际约**每两周才真检查一次**。
> 若要每周必查，跑 `update_check.py set-interval 518400`（6 天）。

检测到更新后：

1. agent 转告 `UPDATE_AVAILABLE` 段
2. 跑 `diff-local` 看上游实际改了什么 + 覆盖层是否冲突
3. 按 A/B/C 场景处理
4. `acknowledge --sha` 标记

## 跨机器同步 patch

patch 目录自包含，可整包跨机器同步：

```bash
# 源机器
tar -czf patches.tgz -C ~/.workbuddy/skills red-book-skills-patches

# 目标机器
tar -xzf patches.tgz -C ~/.workbuddy/skills
python <patch>/core-overrides/helpers/apply_overrides.py apply   # 新机器上必须执行
```

注意：

- `state/` 下是运行期状态（`publish_log.json` / `update_state.json` / `applied.json`），
  可以一起带；建议在新机器上 reset 发布日志避免历史污染
- **新机器上一定要 `apply`**，否则本体没有我们的改动，发布可靠性修复不生效

## 故障排查

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| `git pull` 报 `not a git repository` | 本体不是 git 仓库 | 用「本体不是 git 仓库」一节的覆盖方式 |
| `apply_overrides.py status` 报 `DRIFTED` | 有人直接改了本体 | 把该改动搬进 `overrides/`，再 `apply` |
| `apply_overrides.py status` 报 `PRISTINE` | 刚覆盖过本体还没 apply | 跑 `apply` |
| `diff-local` 报覆盖层冲突 | 上游也改了被覆盖文件 | 按「覆盖层冲突处理」合并，**别直接覆盖** |
| patch helper 报 `ModuleNotFoundError` | 主 skill 重装后 `.venv` 没了 | `cd <本体> && .venv/Scripts/python.exe -m pip install -r requirements.txt` |
| `verify-note` 找不到精确标题 | 主 skill 改了 `SELECTORS` | 查覆盖层 `overrides/scripts/cdp_publish.py` 与上游差异 |
| 间隔守卫报"未到间隔"但实际已过 | 时钟漂移 / 状态被外部改 | 查 `state/publish_log.json`；reset 后重新 record |
| update_check 报 `rate_limited` | GitHub API 限流 | 等冷却；本 patch 用 cooldown 抑制重复提醒 |

## 可选：让本体成为 git 仓库

当前本体是拷贝安装、无 `.git`，所以只能靠 `diff-local` 做内容对比。
如果希望同步更精确，可以把本体 git 化：

```bash
cd <本体>
git init
git remote add upstream https://github.com/aus666666/red-book-skills.git
git add -A && git commit -m "baseline: 本地当前状态（含覆盖层应用产物）"

# 以后同步：
git fetch upstream
git diff HEAD upstream/main --stat      # 精确看上游改了哪些行
git checkout upstream/main -- .         # 只把上游版本取到工作区
python <patch>/core-overrides/helpers/apply_overrides.py apply
```

优点：能精确到行地看上游改动，冲突时可用三方合并。
注意：`.gitignore` 已排除 `.venv/`、`tmp/`、`config/accounts.json`（含凭据），
**不要把账号信息提交进去**。

> 是否启用由用户决定；不启用时 `diff-local` 已能覆盖全部需求。

## 修改记录

- v1.7.0 (2026-09-12) 适配 `core-overrides` 架构：**删除 22 条人工迁移清单**（由覆盖层接管）；
  修正失效的 `git pull` 指令（本体无 `.git`）；新增「标准同步流程」「覆盖层冲突处理」
  「可选：让本体成为 git 仓库」；补 `check` 间隔导致实际约两周才查一次的说明
- v1.6.3 (2026-09-11) 迁移清单追加：`safe-wording-guard` **裸域名 P0**（正文不出现网址/域名，来源改写成
  「机构名+项目名+论文编号」）；`publish-loop-guard` 复核范围收窄为「最近几日 + 第一页」
- v1.6.2 (2026-09-11) 迁移清单追加：`publish-loop-guard` 新增**按事件查重**（`dup_check.py`），
  `publish-preflight-guard` 第 1 项「选题查重」口径由「标题字面」改为「事件标识」
- v1.6.1 (2026-09-11) `windows-sandbox-workaround` 新增「网络可达性」判定与 `net_probe.py`；`publish-preflight-guard` 项数 14→**15**（新增「网络可达性」，发布前必做 TLS 握手探测）
- v1.6.0 (2026-09-11) 迁移清单追加：地域范围闸门（会展活动只发江浙沪/珠三角，`geo_check.py`），`timeliness-window` 用途与 `publish-preflight-guard` 项数（13→14）同步
- v1.5.0 (2026-09-11) 迁移清单追加 3 条：「启动」触发词自动检索发布、每 30 分钟漏发复核、选题配额（台风每日 ≤1）；冲突清单新增 `publish-loop-guard`
- v1.4.0 (2026-09-11) 迁移清单追加：`SKILL.md` 间隔描述改为「8~12 分钟随机」+ `wait --max-block 900`；间隔守卫检查项补 max-block ≥ 720 提醒
- v1.3.0 (2026-09-11) 迁移清单追加：`SKILL.md` 第 2 步扩为「时效窗口 与 可发布资格」（`--live` / `--public-signup`、退出码 3）、patch 表格 11→12 项
- v1.2.0 (2026-09-11) 迁移清单追加：`SKILL.md` 流程新增第 2 步「时效窗口」（`timeliness-window`），原 2–11 顺延为 3–12
- v1.1.0 (2026-09-11) 迁移清单追加 3 条 `SKILL.md` 本地改动（patch 表格、标题 20 字、发布流程增补）
- v1.0.0 (2026-09-04) 初版
