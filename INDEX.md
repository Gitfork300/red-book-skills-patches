# red-book-skills Patches

> 可独立运行的小红书 skill；内置 Windows 兼容运行层。更新参考源为 `Gitfork300/xiaohongshu-skills-A2`。
> 物理位置：本仓库根目录
> 目的：将可执行代码、用户规则、平台适配和安全约束一并维护，运行不依赖同级主 skill。

## 设计原则

- **实现与权威覆盖副本分离**：运行代码随仓库分发；受管改动放 `core-overrides/overrides/` 再 apply。
- **每个 patch 是独立 skill**：有自己的 `SKILL.md` + 可选 `helpers/` + `META.json`
- **本机状态隔离**：发布台账和锁默认位于工作区 `.state/publish/`；其他状态依各 patch 的路径说明存放，不随源码发布
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
> | **共用基座** | `shared` | `core-overrides`、`update-checker`、`windows-sandbox-workaround`、`xhs-risk-guard`、`daily-closeout-guard`、`tools` |
>
> **改哪个体系只动哪套 skill**；确需跨体系生效的规则，必须先在 `SYSTEMS.md` 交叉点清单登记，
> 再在两边的 SKILL.md 互相指向。

| # | Patch | 优先级 | 版本 | 用途 | 规则入口 |
| --- | --- | --- | --- | --- | --- |
| 1 | `core-overrides` | 2 | 1.5.4 | 运行层权威覆盖与页签守卫 | [SKILL.md](./core-overrides/SKILL.md) |
| 2 | `update-checker` | 5 | 1.5.0 | 上游更新检测与差异评估 | [SKILL.md](./update-checker/SKILL.md) |
| 3 | `windows-sandbox-workaround` | 10 | 1.7.0 | Windows 环境和进程兼容 | [SKILL.md](./windows-sandbox-workaround/SKILL.md) |
| 3.5 | `comment-reply-guard` | 11 | 1.24.1 | 评论、私信和回复规则 | [SKILL.md](./comment-reply-guard/SKILL.md) |
| 4 | `xhs-risk-guard` | 12 | 1.3.0 | 平台风控及访问守卫 | [SKILL.md](./xhs-risk-guard/SKILL.md) |
| 5 | `safe-wording-guard` | 15 | 0.8.0 | 文案用词和标题规范 | [SKILL.md](./safe-wording-guard/SKILL.md) |
| 6 | `publish-interval-guard` | 20 | 1.6.1 | 发布间隔及并发保护 | [SKILL.md](./publish-interval-guard/SKILL.md) |
| 7 | `timeliness-window` | 22 | 1.9.1 | 时效、地域及配额门禁 | [SKILL.md](./timeliness-window/SKILL.md) |
| 7.5 | `organizer-qualification-guard` | 23 | 1.3.0 | 活动主办资质门禁 | [SKILL.md](./organizer-qualification-guard/SKILL.md) |
| 8 | `publish-preflight-guard` | 25 | 1.20.0 | 发布前检查及批量预检 | [SKILL.md](./publish-preflight-guard/SKILL.md) |
| 9 | `publish-loop-guard` | 28 | 1.13.3 | 发布流程、查重与漏发复核 | [SKILL.md](./publish-loop-guard/SKILL.md) |
| 10 | `writing-facts-only` | 30 | 1.6.2 | 事实写作与内容规范 | [SKILL.md](./writing-facts-only/SKILL.md) |
| 11 | `cover-image-rules` | 50 | 1.8.3 | 封面来源、去重与二维码门禁 | [SKILL.md](./cover-image-rules/SKILL.md) |
| 12 | `daily-closeout-guard` | 60 | 1.4.1 | 日终收口及问题登记 | [SKILL.md](./daily-closeout-guard/SKILL.md) |

版本列供 `tools/check_patch_versions.py` 校验；具体规则与脚本以各 Patch 入口和 `META.json` 为准。
加载顺序：低优先级先加载（被后者叠加）。

## 加载方式

日常应加载根目录 [`SKILL.md`](./SKILL.md)，它是 `red-book-skills-patch` 的唯一门面。
执行脚本和操作参考位于本仓库 `runtime/`，不需要同级安装。首次安装后使用本仓库 `.venv`
运行 `tools/ensure_compatible.py`；更新规则/代码后用 `--refresh`。本目录的
`core-overrides` 将权威修复应用到本仓库的 bundled runtime。

## 快速检查

```bash
# 环境与变量自检（装机后先跑这个，主动暴露缺口）
python tools/check_env.py --fix-hint

# 一键体检（首选）：先自愈（清覆盖层编译缓存），再依次跑环境自检、覆盖层、契约、
# 版本登记、文档分层、回归测试、发布安全门禁
python tools/doctor.py
```

退出码：0 全通过 / 1 仅警告 / 2 有阻断项（先处理再发布）。分步排查时再跑下面这些。
常见问题见 [`HELP.md`](./HELP.md)。

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
> 受管 runtime 文件的完整权威副本位于 `core-overrides/overrides/`；更新时须先评估 A2 差异并择优移植到权威副本，再审查和应用，不能盲目将旧上游快照覆盖当前实现。

已全部拆分（2026-09-15 收尾）：
- 本体 `SKILL.md` → `references/` 4 个
- 工作区 `MEMORY.md` → `topics/` 15 个（`00`~`14`）+ `QUICKREF.md`（规则速查卡，随 skill 分发，敏感信息已占位）
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
   ├── requirements.txt       ← requests、websockets、opencv-python、Pillow
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

`tools/backup_snapshots.py` 把**bundled runtime 与 Patch 工作区**打包到 `C:/xhs/_skill-backup/`，
并将发布台账与封面二维码白名单另存为业务状态快照；`state/` JSON 不进入源码包。
完整说明（去重、排除项、失败告警）见 **[`UPGRADING.md`](./UPGRADING.md)「本机快照备份」**。
Local Agent Host 已配置每日 10:00 运行备份。快照为本机明文文件，同盘备份不替代异机/离线备份。

## 变更记录归档

本文件只维护当前加载契约、patch 清单和操作入口，不重复保存事故复盘或逐版本 changelog。

- 各 patch 的现行事故速查与历史记录指针留在 `refs/`；完整 changelog / incident 原文归档于 [`history/`](./history/README.md)，不作为当前规则加载。
- 体系边界和跨体系冲突只看 [`SYSTEMS.md`](./SYSTEMS.md)。
- 文档分层和体量限制只看 [`DOC_LAYOUT.md`](./DOC_LAYOUT.md)。
- 上游同步、备份和回滚流程只看 [`UPGRADING.md`](./UPGRADING.md)。
- 安装、变量、登录态、门禁等常见问题自助排查看 [`HELP.md`](./HELP.md)。
- **版本升级的待办、口径冲突、回滚点与升级记录只看 [`HANDOVER.md`](./HANDOVER.md)**（交接给下一个 agent 时先读它）。
- 修改版本时同步更新 `SKILL.md`、`META.json`、本表版本列，并运行 `tools/check_patch_versions.py`。