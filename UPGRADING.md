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

# 1. 覆盖本体（本体已 git 化，但仍需 tarball 覆盖 —— 见下节）
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

## 本体已 git 化（2026-09-12）—— 但仍不能靠 `git pull` 同步

`~/.workbuddy/skills/red-book-skills/` 现在**是** git 仓库，但用法与普通仓库不同：

| | 值 |
| --- | --- |
| 分支 / HEAD | `main`，**恒等于纯上游基线**（建于 `b006891a`） |
| 4 个覆盖产物 | 只停在工作区，**永远是未暂存 modified** —— 这是特性，一眼看到我们动了哪 4 个文件 |
| `core.autocrlf` | **`true`** —— 本体文件是 CRLF、上游是 LF，必须归一化后比较，否则 19 个文件全部误报 modified |
| remote `upstream` | 已配 `aus666666/red-book-skills.git`（**本机当前不可达**，见下） |

### ⚠️ 本机 `github.com` 的 git 端点不可达

2026-09-12 实测三通道：

| 端点 | 走代理 `127.0.0.1:11455` | 直连 |
| --- | --- | --- |
| `api.github.com` | ✅ | ✅ |
| `codeload.github.com`（tarball） | ✅ | ✅ |
| **`github.com`（git 端点）** | ❌ 502 | ❌ 超时 |

所以 **`git fetch` / `git clone` / `git ls-remote` 全都用不了**。
附带发现：`update-checker` 里那个 `git ls-remote` 兜底探测在本机**一直是失效的**，
它实际只靠 GitHub API 在跑。

**结论：上游快照只能走 `codeload` tarball**，同步的实质动作没有变化：

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

### git 化在当前网络下提供了什么

- ✅ `git status` —— 一眼看到我们改了哪 4 个文件
- ✅ `git diff` —— 我们相对上游的改动
- ✅ `git log` / `git checkout <sha> -- .` —— 版本记录与回退
- ❌ `git fetch upstream` + `git diff HEAD upstream/main` —— **行级看上游改动，目前用不了**

因此**上游差异对比仍以 `diff-local` 为准**。若将来 `github.com` 可达，
升级为「fetch → diff → checkout → 推进基线 → apply」（见文末）。

### ⚠️ git 化新增的误操作面

本体有 `.git` 之后，这些命令会**一键抹掉覆盖产物**：

```bash
git checkout .          # 或 git reset --hard / git stash / git clean
```

兜底：`apply_overrides.py status` 会立刻报 `PRISTINE`，跑一次 `apply` 即恢复。

**约定：本体仓库只保留"纯上游"的提交，永不 commit 覆盖产物** ——
否则 HEAD 变成"上游+覆盖"混合体，`git diff` 就分不清谁改了哪行，git 化白做。

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

patch 目录自包含，可整包跨机器同步。**patches 已于 2026-09-12 git 化**（本地仓库、无 remote），
因此迁移也可用 `git bundle create patches.bundle --all` 或直接 clone，不再只能打 tar。

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
| `git fetch upstream` 报 502 / 连接超时 | 本机 `github.com` git 端点不可达 | 改用 `codeload` tarball 覆盖（见「本体已 git 化」一节） |
| `git status` 显示十几个文件全 modified | `core.autocrlf` 被设成了 `false` | `git config core.autocrlf true` 后重看 |
| 覆盖产物"不见了"（`git status` 变干净） | 误跑 `git checkout .` / `reset --hard` / `stash` | `apply_overrides.py status` 会报 `PRISTINE`，跑 `apply` 恢复 |
| `apply_overrides.py status` 报 `DRIFTED` | 有人直接改了本体 | 把该改动搬进 `overrides/`，再 `apply` |
| `apply_overrides.py status` 报 `PRISTINE` | 刚覆盖过本体还没 apply | 跑 `apply` |
| `diff-local` 报覆盖层冲突 | 上游也改了被覆盖文件 | 按「覆盖层冲突处理」合并，**别直接覆盖** |
| patch helper 报 `ModuleNotFoundError` | 主 skill 重装后 `.venv` 没了 | `cd <本体> && .venv/Scripts/python.exe -m pip install -r requirements.txt` |
| `verify-note` 找不到精确标题 | 主 skill 改了 `SELECTORS` | 查覆盖层 `overrides/scripts/cdp_publish.py` 与上游差异 |
| 间隔守卫报"未到间隔"但实际已过 | 时钟漂移 / 状态被外部改 | 查 `state/publish_log.json`；reset 后重新 record |
| update_check 报 `rate_limited` | GitHub API 限流 | 等冷却；本 patch 用 cooldown 抑制重复提醒 |

## 本体 git 化的现状与维护

本体已于 **2026-09-12 git 化**。建库方式（记录备查）：

```bash
cd <本体>
git init -b main
git config core.autocrlf true      # ⚠️ 不能设 false，否则 CRLF/LF 会让 19 个文件全报 modified
git remote add upstream https://github.com/aus666666/red-book-skills.git

# 本机 github.com git 端点不可达，故用 codeload 取快照：
# 在临时目录做成"上游快照仓库"，再本地 fetch（不走网络）
<下载 tarball 并解压到 /tmp/up>
git -C /tmp/up init -b main && git -C /tmp/up add -A && git -C /tmp/up commit -m "upstream snapshot"

# 锚定纯上游：read-tree 只填索引，工作区一个字节都不动
git fetch /tmp/up HEAD
git read-tree FETCH_HEAD
git commit -m "baseline: upstream main @ <sha>"
```

结果：`HEAD` = 纯上游；4 个覆盖产物 = 未暂存 modified；`git status` 恒不干净（**预期如此**）。

### 建基线前务必校验快照

下载的 tarball 必须与 `core-overrides/baseline.json` 记录的 `upstream_sha256`
（行尾归一化后）**逐项比对，四项全 MATCH 才能用来建基线** ——
否则基线本身可能是被污染的。

### 若将来 `github.com` 可达，同步流程升级为

```bash
git fetch upstream
git diff HEAD upstream/main --stat     # 精确看上游改了哪些行
git checkout upstream/main -- .        # 工作区变成新上游（覆盖产物被冲掉，正常）
git add -A && git commit -m "baseline: upstream <新 sha>"   # 推进基线
$PY $P/core-overrides/helpers/apply_overrides.py apply      # 重新叠回我们的覆盖
```

⚠️ `checkout` 与 `commit` 的**顺序不能颠倒**：先 checkout 再 commit，基线才是纯上游；
若先 apply 再 commit，HEAD 又变成混合体了。

### 凭据

上游的 `.gitignore` 已排除 `.venv/`、`tmp/`、`config/accounts.json`（含凭据）。
建库后核对一次 `git ls-files` —— 应当**只**出现上游的
`config/accounts.json.example`，真实凭据绝不能进库。

## 修改记录

- v1.8.0 (2026-09-12) **本体 git 化**（用户下达"本体请同步git化"）：基线提交 `8f3e151`，
  HEAD 恒等于纯上游 `b006891a`，4 个覆盖产物只停在工作区（未暂存 modified）；
  `core.autocrlf=true`（本体 CRLF / 上游 LF，设 false 会让 19 个文件全误报）。
  **实测本机 `github.com` git 端点不可达**（走代理 502 / 直连超时）→ `git fetch` / `ls-remote`
  均不可用，快照只能走 `codeload`，故上游差异对比仍以 `diff-local` 为准。
  重写「本体不是 git 仓库」→「本体已 git 化（仍不能靠 git pull 同步）」；
  「可选：让本体成为 git 仓库」→「现状与维护」（含建基线前的 sha256 校验要求、
  网络恢复后的升级流程、checkout/commit 顺序警示、凭据核对）；
  故障排查表补 3 条（fetch 502 / autocrlf 误设 / 覆盖产物被抹）
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
