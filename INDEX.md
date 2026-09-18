# red-book-skills Patches

> 定制 patch 集合，叠加在主 skill `aus666666/red-book-skills` 之上。
> 物理位置：`~/.workbuddy/skills/red-book-skills-patches/`
> 目的：让所有定制化内容（用户偏好、平台适配、安全约束、运营规则）独立于主 skill 维护，主 skill 升级时不会丢，且可逐项审视。

> **更新位置唯一说明**：仓库地址、运行目录、上游备份和缺失依赖恢复规则见
> [`UPDATE_LOCATIONS.md`](./UPDATE_LOCATIONS.md)。上游只认
> `aus666666/red-book-skills`，Patch 只认 `Gitfork300/red-book-skills-patches`。

## 设计原则

- **本体与补丁分离**（2026-09-12 定）：**我们自己的更新放 patch，原始本体定期和 GitHub 同步**。
  对本体源码的改动不直接写在本体里，而是放 `core-overrides/overrides/` 再 apply
- **每个 patch 是独立 skill**：有自己的 `SKILL.md` + 可选 `helpers/` + `META.json`
- **状态文件自包含**：每个 patch 的状态（间隔记录、更新状态等）放在 patch 自己的 `state/`，不污染主 skill
- **可逐项启用/禁用**：通过 `<patch>/META.json` 中的 `priority` 字段控制加载顺序；删除目录即可停用
- **可逐项升级**：未来增改 patch 不影响主 skill
- **更新提示而非自动合并**：update-checker 只检测上游，不修改任何文件

## Patch 列表（按 priority 升序加载）

> **体系分组（2026-09-15 用户裁定：评论与发布是两套体系，独立维护，避免干扰）**
> 边界权威见 **[`SYSTEMS.md`](./SYSTEMS.md)**；每个 patch 的 `SKILL.md` frontmatter 带 `system:` 字段。
> 规则冲突一律按 `SYSTEMS.md` 第三节「交叉点清单」判定。
>
> | 体系 | 代号 | 成员 |
> | --- | --- | --- |
> | **发布** | `publish` | `writing-facts-only`、`safe-wording-guard`、`cover-image-rules`、`timeliness-window`、`organizer-qualification-guard`、`publish-preflight-guard`、`publish-interval-guard`、`publish-loop-guard` |
> | **评论** | `comment` | `comment-reply-guard` |
> | **共用基座** | `shared` | `core-overrides`、`update-checker`、`windows-sandbox-workaround`、`xhs-risk-guard`、`tools` |
>
> **改哪个体系只动哪套 skill**；确需跨体系生效的规则，必须先在 `SYSTEMS.md` 交叉点清单登记，
> 再在两边的 SKILL.md 互相指向。

| # | Patch | 优先级 | 版本 | 用途 | 配套脚本 |
| --- | --- | --- | --- | --- | --- |
| 1 | `core-overrides` | 2 | 1.0.0 | **本体文件覆盖层**：我们自己对源码的改动（发布按钮重试、沙箱脱离、间隔记录、SKILL.md 规则合并）。同步上游后必须 apply。**本体 SKILL.md 已拆分为主入口 + `references/`（5 个），新增文件会随 apply 自动同步** | `helpers/apply_overrides.py` |
| 2 | `update-checker` | 5 | 1.1.0 | 检测原仓库更新 + **内容级对比本地与上游（`diff-local`，忽略行尾假阳性，含覆盖层冲突检测）** | `helpers/update_check.py` |
| 3 | `windows-sandbox-workaround` | 10 | 1.6.9 | Windows 沙箱/受限会话适配 + 进程/探活/网络可达性排查坑位 + **登录态与风控规则索引** | `helpers/xhs_login_wait.py`, `helpers/xhs_focus.ps1`, `helpers/net_probe.py` |
| 3.5 | `comment-reply-guard` | 11 | 1.15.0 | **评论体系**：评论 / 私信的读取与回复 —— 回复标记、报名网址、提醒登记、非提问不回、Tab/内存守护、读取节流、2 天笔记窗口、历史快照合并、私信已回判定与 DOM 适配 | — |
| 4 | `xhs-risk-guard` | 12 | 1.3.0 | **小红书风控规则单一权威**（读取限流 / 登录态 / 接口签名 / 「假风控」四域总表）+ **可执行守卫**（预算·冷却·连续失败熔断） | `helpers/risk_state.py` |
| 5 | `safe-wording-guard` | 15 | 0.7.0 | 规避站外导流等敏感词，**正文一律不出现网址/裸域名**；**标题 20 上限按「字宽」计**；**标题不写序号（①/（一）/系列N，P0）**；含涉港澳台表述规范 | `helpers/check_wording.py` |
| 6 | `publish-interval-guard` | 20 | 1.4.0 | 连续发布间隔 **8~12 分钟随机**（下限 8 分钟）；**`record` 按 note_id 幂等**；**`state/publish_log.json` 是 100 条环形缓冲 —— 不得用条目数当「当日已发篇数」**；**verify-note 判据＝`found:true`（不是 grep "SUCCESS"），摘要只取 stdout**；**`reserve`/`release` 发布资格抢占（堵 TOCTOU 并发重复发布）** | `helpers/publish_interval.py` |
| 7 | `timeliness-window` | 22 | 1.8.0 | **会展活动只发江浙沪/珠三角；只发近 7 天在举行 / 需报名的活动（专题系列 15 天）；无直播且公众无法报名的不发（邀请制可发）；恶劣天气类每日 ≤1 篇，红 / 黑色预警放宽至 3 篇；专题未闭幕不得停更（停止/切换＝闭幕日 T+2）** | `helpers/geo_check.py`, `helpers/check_window.py`, `helpers/quota_check.py` |
| 7.5 | `organizer-qualification-guard` | 23 | 1.3.0 | **主办资质闸门**：活动/展会/论坛类须事业单位/行业龙头/行业协会牵头的中大型活动且正文有含金量；付费小班/价格/私企黑名单/无合规主办方 → 硬拒（第 16 项） | `helpers/check_organizer.py` |
| 8 | `publish-preflight-guard` | 25 | 1.17.0 | **发布前 19 项总检查 + 批量队列控制**；第 9 项字数**必须与发布链同口径**（含空格计 —— 去空格自算会差 40 字） | `helpers/batch_preflight.py` |
| 9 | `publish-loop-guard` | 28 | 1.8.1 | **「启动」触发词自动检索发布 + 每 30 分钟漏发复核（只看最近几日/第一页）+ 按事件查重（三道信号：事件标识／公共子串／**地点+日期**；类别化窗口：A 类当天／行业类 **7 天**／其他 15 天，优先级 A>行业>其他；`--series` 只放宽公共子串，不放宽第三道信号；**发布链重试前必须 verify 防重复发布**）+ 长批次硬停止时间 + 合规审计（全量清单 + 正文核验，含风控熔断）** | `helpers/check_missing.py`, `helpers/watch_missing.py`, `helpers/dup_check.py`, `helpers/recent_published.py`, `helpers/list_all_notes.py`, `helpers/read_note_body.py` |
| 10 | `writing-facts-only` | 30 | 1.6.1 | 只陈述事实；标题要说内容；活动须写参与方式 | — |
| 11 | `cover-image-rules` | 50 | 1.6.0 | 封面配图规范（真实感优先、禁二维码/人物/完整人形机器人）；**展会/活动类官方宣传图 ≥80% 硬闸门（台账 + `check_cover_source.py`）**；紧急事件（台风等）改用矢量示意图 | `helpers/check_cover_source.py` |

加载顺序：低优先级先加载（被后者叠加）。

## 加载方式

日常应加载根目录 [`SKILL.md`](./SKILL.md)，它是 `red-book-skills-patch` 的唯一门面。
同级 `red-book-skills` 只作为上游执行本体，不得直接调用；首次加载 Patch 或上游变化
后运行一次 `python tools/ensure_compatible.py`。同一会话后续任务复用门禁结果；需要
强制复核时加 `--refresh`。门禁通过后，再按本 INDEX 的 priority 顺序应用规则。
本目录的 `core-overrides` 负责把必须进入执行本体的兼容修复安全应用回上游目录。

## 快速检查

```bash
# 列出已安装 patch
ls ~/.workbuddy/skills/red-book-skills-patches/

# 验证所有 helper 可用
for d in ~/.workbuddy/skills/red-book-skills-patches/*/; do
  for f in "$d/helpers/"*.py; do
    [ -f "$f" ] && echo "=== $f ===" && python -m py_compile "$f" && echo OK
  done
done
```

公开发布前额外运行本地安全门禁（只检查本地工作树和 Git 索引，不联网）：

```bash
python tools/init_runtime.py
python tools/check_public_release.py
```

`init_runtime.py` 只创建空的本地状态目录；首次运行 helper 时才生成状态 JSON。
该门禁只阻断登录态、凭据和运行日志；业务标题、活动信息和规则文档可以保留。
跨电脑安装和清理规则见 [`RUNTIME_SETUP.md`](./RUNTIME_SETUP.md)。

## 文档分层（md 拆分与串联）

> 规范权威见 **`DOC_LAYOUT.md`**（拆任何 md 之前先读）；校验跑 `tools/check_doc_layers.py`（拆完必跑）。
> 三层模型：L0 主入口（铁律+索引，≤6000 字符/180 行）→ L1 详情（`refs/`，≤9000/260）→ L2 归档（日志/快照）。
> 第 0 铁律（针对本体覆盖层）：**覆盖层不持有上游内容副本**——上游命令/流程/参数指向上游文档（如本体 `README.md`），否则主体更新后 `apply` 会把旧快照覆盖回去 = 回退上游改动。

已全部拆分（2026-09-15 收尾）：
- 本体 `SKILL.md` → `references/` 4 个
- 工作区 `MEMORY.md` → `topics/` 9 个
- 8 个 patch `SKILL.md` → 各自 `refs/`：comment-reply-guard / windows-sandbox-workaround / publish-loop-guard / timeliness-window / publish-preflight-guard / writing-facts-only / xhs-risk-guard / safe-wording-guard

## 与主 skill 的关系

```
本体（上游代码 + 覆盖产物）
└─ red-book-skills/          ← 来自 aus666666/red-book-skills
   ├── scripts/              ← 核心 CDP 自动化（3 个文件被 core-overrides 覆盖）
   ├── SKILL.md              ← 主入口（铁律 + 流程 + 索引），已瘦身至 ~5.8k 字符
   ├── references/           ← 只放**我们自己的**展开文档（4 个，**不做上游内容副本**）
   └── ...                   ← 已 git 化：HEAD 恒为纯上游，覆盖产物恒为未暂存 modified

patch 集（本目录）
└─ red-book-skills-patches/  ← 独立维护，物理隔离
   ├── INDEX.md
   ├── core-overrides/        ← 本体文件覆盖层（权威副本在这里）
   ├── update-checker/
   ├── windows-sandbox-workaround/
   ├── xhs-risk-guard/        ← 风控规则单一权威 + 可执行守卫
   ├── safe-wording-guard/
   ├── publish-interval-guard/
   ├── timeliness-window/
   ├── publish-preflight-guard/
   ├── publish-loop-guard/
   ├── writing-facts-only/
   ├── cover-image-rules/
   └── tools/                 ← 工程工具：check_patch_versions.py、backup_snapshots.py
```

**同步上游 = 覆盖本体 → `apply_overrides.py apply`**。本体里被我们改过的文件只是
"应用产物"，权威副本在 `core-overrides/overrides/`，所以覆盖不会丢东西。

本体已于 2026-09-12 git 化（HEAD 恒等于纯上游基线，4 个覆盖产物只停在工作区）。
⚠️ **`git checkout .` / `git reset --hard` / `git stash` 会一键抹掉覆盖产物** ——
兜底：`apply_overrides.py status` 会报 `PRISTINE`，再 `apply` 即恢复。
本机 `github.com` 的 git 端点不可达（走代理 502 / 直连超时），`git fetch upstream` 用不了，
上游差异对比仍以 `diff-local` 为准。

## 升级主 skill 后如何处理 patch

1. 跑 `update-checker diff-local` —— 看上游改了什么、**覆盖层有没有冲突**
2. **有覆盖层冲突** → 先把上游改动人工合并进 `core-overrides/overrides/`（别直接覆盖本体）
3. 覆盖本体（下载上游快照覆盖；本机 `github.com` git 端点不可达，`git fetch` 用不了）
4. `apply_overrides.py status`（预期 PRISTINE）→ `apply` → `verify`
5. 跑自测 + 端到端；更新 `baseline.json` 与 `acknowledge --sha`

完整流程与故障排查详见 [`UPGRADING.md`](./UPGRADING.md)。

## 修改本目录的注意事项

- 删 patch 目录前先确认没有自动化/脚本引用
- 改 patch 内文件不会触发主 skill 重载
- 新增 patch 必须在 INDEX.md 同步登记

## 版本备份（防丢失）

`tools/backup_snapshots.py` 把**本体与补丁仓的工作区**打包成快照落到 `~/Documents/red-book-skills-backup/`。
完整说明（为什么不能只靠 git、去重、排除项、失败告警）见 **[`UPGRADING.md`](./UPGRADING.md)「版本备份」**。已挂每日 10:00 自动备份任务。

## 变更记录归档

本文件只维护当前加载契约、patch 清单和操作入口，不重复保存事故复盘或逐版本 changelog。

- 各 patch 的历史变更放在对应的 `refs/*changelog*.md`。
- 体系边界和跨体系冲突只看 [`SYSTEMS.md`](./SYSTEMS.md)。
- 文档分层和体量限制只看 [`DOC_LAYOUT.md`](./DOC_LAYOUT.md)。
- 上游同步、备份和回滚流程只看 [`UPGRADING.md`](./UPGRADING.md)。
- 修改版本时同步更新 `SKILL.md`、`META.json`、本表版本列，并运行 `tools/check_patch_versions.py`。