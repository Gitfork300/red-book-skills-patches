# red-book-skills Patches

> 可独立运行的小红书 skill；内置 Windows 兼容运行层。更新参考源为 `Gitfork300/xiaohongshu-skills-A2`。
> 物理位置：本仓库根目录
> 目的：将可执行代码、用户规则、平台适配和安全约束一并维护，运行不依赖同级主 skill。

## 设计原则

- **实现与权威覆盖副本分离**：运行代码随仓库分发；受管改动放 `core-overrides/overrides/` 再 apply。
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
| 1 | `core-overrides` | 2 | 1.2.0 | **随仓库 runtime 的权威覆盖层**：发布页蜜罐防护、风控响应分类、Chrome 沙箱脱离、间隔记录和操作说明 | `helpers/apply_overrides.py` |
| 2 | `update-checker` | 5 | 1.4.0 | 可选检测 A2 Fork 更新；版本未变则跳过 commit 查询，另含 `diff-local` 映射差异/覆盖冲突；只通知，不参与日常运行 | `helpers/update_check.py` |
| 3 | `windows-sandbox-workaround` | 10 | 1.7.0 | Windows 沙箱/受限会话适配 + 进程/探活/网络可达性排查坑位 + **登录态与风控规则索引** + 无人值守巡检失败停止与新鲜度核验 | `helpers/xhs_login_wait.py`, `helpers/xhs_focus.ps1`, `helpers/net_probe.py` |
| 3.5 | `comment-reply-guard` | 11 | 1.22.0 | **评论体系**：评论 / 私信的读取与回复 —— 回复标记、报名网址、提醒登记、**每日回复配额制（回复量/当日评论量 ≥50%，2026-09-29 由 80% 下调，question>correction>eval>chat，评价类仅在配额不足时补，达标即停）**、**回复文案零废话（禁「感谢分享/仅供参考」类客套，评价类须带话题相关实质内容）**、Tab/内存守护、读取节流、2 天笔记窗口、历史快照合并、私信已回判定与 DOM 适配、mentions 失效后的新定位路径、收件箱直答与风控处置、**昵称是 AI展会叻**、**发评论必须 CDP 真实事件**、**点封面图/mentions 抓包取 note_id**、**核验必须先展开折叠的子评论（否则假阴性→重发）** | — |
| 4 | `xhs-risk-guard` | 12 | 1.3.0 | **小红书风控规则单一权威**（读取限流 / 登录态 / 接口签名 / 「假风控」四域总表）+ **可执行守卫**（预算·冷却·连续失败熔断） | `helpers/risk_state.py` |
| 5 | `safe-wording-guard` | 15 | 0.7.0 | 规避站外导流等敏感词，**正文一律不出现网址/裸域名**；**标题 20 上限按「字宽」计**；**标题不写序号（①/（一）/系列N，P0）**；含涉港澳台表述规范 | `helpers/check_wording.py` |
| 6 | `publish-interval-guard` | 20 | 1.4.1 | 连续发布间隔 **8~12 分钟随机**（下限 8 分钟）；**`record` 按 note_id 幂等**；**`state/publish_log.json` 是 100 条环形缓冲 —— 不得用条目数当「当日已发篇数」**；**verify-note 判据＝`found:true`（不是 grep "SUCCESS"），摘要只取 stdout**；**`reserve`/`release` 发布资格抢占（堵 TOCTOU 并发重复发布）** | `helpers/publish_interval.py` |
| 7 | `timeliness-window` | 22 | 1.9.0 | **会展活动只发江浙沪/珠三角；只发近 7 天在举行 / 需报名的活动（专题系列 15 天）；无直播且公众无法报名的不发（邀请制可发）；恶劣天气类每日 ≤1 篇，红 / 黑色预警放宽至 3 篇；天气稿不得跨日顺延；专题未闭幕不得停更（停止/切换＝闭幕日 T+2）** | `helpers/geo_check.py`, `helpers/check_window.py`, `helpers/quota_check.py` |
| 7.5 | `organizer-qualification-guard` | 23 | 1.3.0 | **主办资质闸门**：活动/展会/论坛类须事业单位/行业龙头/行业协会牵头的中大型活动且正文有含金量；付费小班/价格/私企黑名单/无合规主办方 → 硬拒（第 16 项） | `helpers/check_organizer.py` |
| 8 | `publish-preflight-guard` | 25 | 1.20.0 | **发布前 19 项总检查 + 批量队列控制**；第 3+4 项资格 UNKNOWN 硬阻断；第 19 项校验专题全名及有效期；非活动稿须声明 `non_activity`；必需标题/正文文件无效即报错 | `helpers/batch_preflight.py` |
| 9 | `publish-loop-guard` | 28 | 1.10.0 | **「启动」触发词自动检索发布 + 每 30 分钟漏发复核（只看最近几日/第一页）+ 按事件查重（三道信号：事件标识／公共子串／**地点+日期**；类别化窗口：A 类当天／行业类 **7 天**／其他 15 天，优先级 A>行业>其他；`--series` 只放宽公共子串，不放宽第三道信号；**发布链重试前必须 verify 防重复发布**）+ 长批次硬停止时间 + 合规审计（全量清单 + 正文核验，含风控熔断）+ 专题全名标记到期拦截** | `helpers/check_missing.py`, `helpers/watch_missing.py`, `helpers/dup_check.py`, `helpers/recent_published.py`, `helpers/list_all_notes.py`, `helpers/read_note_body.py` |
| 10 | `writing-facts-only` | 30 | 1.6.2 | 只陈述事实；标题要说内容；活动须写参与方式；分页统计需确认记录不重复并按稳定键去重 | — |
| 11 | `cover-image-rules` | 50 | 1.7.0 | 封面配图规范（真实感优先、禁二维码/人物/完整人形机器人）；**展会/活动类官方宣传图 ≥80% 硬闸门（台账 + `check_cover_source.py`）**；防止源图拉伸与标题重绘 | `helpers/check_cover_source.py` |

加载顺序：低优先级先加载（被后者叠加）。

## 加载方式

日常应加载根目录 [`SKILL.md`](./SKILL.md)，它是 `red-book-skills-patch` 的唯一门面。
执行脚本和操作参考位于本仓库 `runtime/`，不需要同级安装。首次安装后使用本仓库 `.venv`
运行 `tools/ensure_compatible.py`；更新规则/代码后用 `--refresh`。本目录的
`core-overrides` 将权威修复应用到本仓库的 bundled runtime。

## 快速检查

```bash
# 列出本仓库目录
Get-ChildItem .

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

## 独立运行结构

```
独立 skill（本目录）
└─ red-book-skills-patches/
   ├── SKILL.md               ← 唯一加载入口
   ├── runtime/scripts/       ← 随仓库分发的发布、登录、检索和互动代码
   ├── runtime/references/    ← 操作细节（不注册成额外 skill）
   ├── runtime/INSTRUCTIONS.md ← 详细运行规则
   ├── core-overrides/        ← bundled runtime 的权威覆盖副本
   ├── requirements.txt       ← 仅 requests 与 websockets
   └── ...                    ← patch 规则、状态守卫与本地工具
```

更新参考源 A2 与 bundled runtime 架构不同。先评估差异，再择优移植到 `runtime/`；
禁止把整个 Fork 快照覆盖到本仓库。发布、登录、检索和互动不依赖 GitHub。

## 评估 A2 更新

1. 使用 `update-checker` 检查 A2 版本和差异；路径/文件数差异不等于可直接移植。
2. 确认其实现优于当前方案且满足 Windows、本仓库 contracts 后，再合并到 overrides/runtime。
3. 运行本地回归测试、`apply`、`verify`、`ensure_compatible.py --refresh`。
4. 只有审核结论完成后才 `acknowledge --sha`。

完整流程与故障排查详见 [`UPGRADING.md`](./UPGRADING.md)。

## 修改本目录的注意事项

- 删 patch 目录前先确认没有自动化/脚本引用
- 改 patch 内文件不会触发主 skill 重载
- 新增 patch 必须在 INDEX.md 同步登记
- **不要在 skills 树内留 SKILL.md 副本**（备份、导出、临时快照一律放树外）：
  扫描器递归扫 `skills/**/SKILL.md` 并按 frontmatter `name` 注册，副本会与本体撞名，
  同名时加载哪份不确定 —— 若命中旧副本会静默回退。
  自检：`python tools/check_skill_name_collisions.py`（撞名但内容一致=SAME 无风险，
  内容不同=DIFF 必须处理；`--root <dir>` 可扫项目级技能目录）。
  历史事故见该脚本头部注释（2026-10-07，`state/backup/` 已迁到 `_skill-backup/`）。

## 版本备份（防丢失）

`tools/backup_snapshots.py` 把**bundled runtime 与 Patch 工作区**打包成快照落到 `~/xhs-workspace/_skill-backup/`。
完整说明（为什么不能只靠 git、去重、排除项、失败告警）见 **[`UPGRADING.md`](./UPGRADING.md)「版本备份」**。已挂每日 10:00 自动备份任务。

## 变更记录归档

本文件只维护当前加载契约、patch 清单和操作入口，不重复保存事故复盘或逐版本 changelog。

- 各 patch 的历史变更放在对应的 `refs/*changelog*.md`。
- 体系边界和跨体系冲突只看 [`SYSTEMS.md`](./SYSTEMS.md)。
- 文档分层和体量限制只看 [`DOC_LAYOUT.md`](./DOC_LAYOUT.md)。
- 上游同步、备份和回滚流程只看 [`UPGRADING.md`](./UPGRADING.md)。
- 修改版本时同步更新 `SKILL.md`、`META.json`、本表版本列，并运行 `tools/check_patch_versions.py`。