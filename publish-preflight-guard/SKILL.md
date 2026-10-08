---
name: publish-preflight-guard
system: publish
version: 1.20.0
patch_for: red-book-skills
applies_to_main_version: ">=0.1.0"
priority: 25
author: Project maintainers
created: 2026-09-11
---

# publish-preflight-guard（发布前总检查与队列控制）

> 核心结论：**已发布的笔记改不回来**（脚本不能编辑，只能 App 人工改且重新过审）。
> 所有闸门必须前置到发布前；已排队未发出的稿都还能拦下来。

## 一、发布前总检查（19 项，任一不过不得排队）

| # | 检查项 | 判据（细节见对应 patch） | 归属 |
|---|---|---|---|
| 1 | 选题查重（**双源**） | `dup_check.py --title … --class a\|industry\|other` 退 0；按"事件"判；A 类当天/行业 3 天/其他 15 天；读 `publish_log.json` + 平台快照 | `publish-loop-guard` |
| 2 | 地域范围 | `geo_check.py` 退 0；只发江浙沪/珠三角 | `timeliness-window` |
| 3 | 时效窗口 / 可发布资格 | `check_window.py` **必须退 0**；非 0 一律阻断（1=时效不符，3=资格不符或字段 UNKNOWN） | `timeliness-window` |
| 4 | 可发布资格 | 传 `--live`/`--public-signup`；无直播且不能报名 → 不发 | `timeliness-window` |
| 5 | 事实与时效 | 时间/价格/人数双源核实 | `writing-facts-only` |
| 6 | 标题说明内容 | 非"流水号+日期"，含主体+看点/门槛 | `writing-facts-only` |
| 7 | 参与方式写全 | 邀约/登记/审核/截止/凭证/名额 | `writing-facts-only` |
| 8 | 用词预检 | `check_wording.py` 退 0；正文/标题**一律不出现网址或裸域名** | `safe-wording-guard` |
| 9 | 字数硬限 | 标题 ≤20（字宽）、**核心正文（末个 `—` 之前）450–600 字、全篇 <1000 字** + 分段合规 + **口径必须与发布链一致（含空格计，禁止去空格后自算）** | `safe-wording-guard` |
| 10 | 封面合规 + **来源台账** | 真实感优先，无二维码/人物/文字/地图/机器人；`check_cover_source.py --batch-dir <目录>` 退 0——**展会/活动类批次官方宣传图 ≥80%**，无台账=不能排队 | `cover-image-rules` |
| 11 | 封面文件核对 | 数量对、每张打开看过、无同名覆盖 | `cover-image-rules` |
| 12 | AI 声明 | 含 AI 图/文 → 传 `--content-declaration` | `cover-image-rules` |
| 13 | 间隔闸门 | **8~12 分钟随机**（下限 8 分钟） | `publish-interval-guard` |
| 14 | 选题配额 | `quota_check.py --kind weather --level <级别>` 退 0；恶劣天气 ≤1 篇（红/黑 3 篇） | `timeliness-window` |
| 15 | 网络可达性 | `net_probe.py` 退 0；**必须真做 TLS 握手** | `windows-sandbox-workaround` |
| 16 | 主办资质 | `check_organizer.py` 退 0（研究/案例类跳过） | `organizer-qualification-guard` |
| 17 | 底部评级块 | 展会/活动类必带；首行 **`综合 ★…`（汉字在前、星级在后）** + 四维 + 来源 | `writing-facts-only` |
| 18 | 近似文章限次 | `near_dup_limit.py --title … --level <层级｜grade> --topic <主题>` 退 0；SSS/国家级 24h≤1 篇、A/行业级 **7 天**≤1 篇、专题系列不设限制 | `publish-loop-guard` |
| 19 | **标题标记** | `title_tag.py --check "<标题>"` 退 0：必须有且仅有 **1 个** 方括号前缀（`[SSS]/[SS]/[S]/[A]/[P]/[X]/[天气]/[Canary]`），优先级 Canary > 天气 > 等级；字宽 ≤18（硬限 20） | `publish-loop-guard` |

> 第 2→3→4 是"选题闸门"，**按顺序判**：先地域（外地直接排除）→ 时效 → 资格 → 配额，最后才动笔。
> ⚠️ **字数口径必须同口径**（2026-09-16 踩坑）：本地脚本"去空格"算 **607**、发布链 `check_wording`
> 按"含空格"算 **647** —— 同一篇两边结论不同。**一律以 `check_wording.py` / `batch_preflight.py`
> 的输出为准**，自算脚本不要先去空格。
> 第 9 条每次改稿都要重跑字数（加了内容字数会变）；第 15 条不可达时空转会烧间隔配额，先等恢复再按漏发复核补发；第 17 条整批常由同一模板生成会集体缺行/反序，改模板后必须整批重跑。

## 二、批量预检脚本 `helpers/batch_preflight.py`

19 项里 12 项可自动化（1/2/3/4/8/9/10/11/14/15/16/17；第 10 项经 `cover-image-rules/helpers/check_cover_source.py` 查台账）：

```bash
python helpers/batch_preflight.py --notes xhs_publish/ai0912_notes.json
```

- 第 14 项按题材条件适用（无恶劣天气选题跳过）；级别从稿件文本嗅探透传 `--level`（红/黑 3 篇，其余 1 篇）。
- 每篇 notes 必须提供非空 `title`/`content` 或有效的 `title_file`/`content_file`；`non_activity: true` 用于非活动类，并触发非活动四维评级块及跳过会展地域/时效/资格闸门。
- `title_file`、`content_file`、`cover` 相对路径按启动命令时的**当前工作目录**解析；建议绝对路径。缺失的标题/正文文件现在会报错退出，不再静默当空文本。
- 第 9 项自算核心正文 450–600 / 全篇 <1000；第 17 项校验 `^综合\s*[★☆]`。
- 默认按发布优先级排序；未标 class 走 `other`（最保守）。
- 只给自动化结论，5/6/7/10/12/13 仍需人工判（脚本列待核对清单）。
- ⚠️ **务必发布前跑**：对已发布稿重跑，第 1 项"查重不过"是正确结论（已发过），不是误报。
- `--only 1,8,9` = 只跑指定**检查项**；`--only-notes 1,3,5` = 只检查指定**稿件**（2026-10-03 修正，详见 refs/02-changelog v1.19.0）。

### 🚨 台账填报纪律（活动类）—— 2026-10-03 血的教训

`live` / `public_signup` / `deadline` / `category` 这四个字段**决定第 3+4 项能否放行**，
必须照**正文事实**核实后填写，不许照模板默认值随手带过：

- `public_signup`：缴费注册 / 公开票务 → `true`；邀约无名额 → `invited`；都不能就别写这条稿。
- `deadline`：报名/缴费/投稿截止日，填了才能走「截止日在窗口内」这条路径。
- `category`：`series` 才有 15 天窗口（专题系列预热/连载），单篇普通稿只有 7 天。

后果实测：CICAI 2026（A 组 3 篇）正文白纸黑字写「参会需缴注册费、缴费截止 10-13」，
台账却填 `public_signup=false` → 修复后的闸门判 NOT_ELIGIBLE，当场 kill 发布链才拦下。
反过来，在旧脚本（`ok = rc in (0, 3)`）下这类错判**一律显示 OK**，从不会报警。
只读回溯工具：`xhs_publish/_audit_eligibility_1003.py`（只判资格，避开已过期的时效噪音）。

## 三、批量队列控制

- 「启动」= 自动跑全流程 + 挂 30 分钟漏发复核（见 `publish-loop-guard`）。
- 启动时先写 `publish-loop-guard/state/inflight.json` **再**起看门狗（顺序不能反）；跑完（无论成败）**必须清空 `inflight.json`**。
- 稿件在"发布那一刻"才被读取 → 改磁盘稿件对尚未发布的篇章有效；趁那一篇还在等间隔时改。
- 稿件尚未真正发布时停队列是安全的；已发出去的那篇单独人工处理，**不要重发**。
- 改批量脚本 `NOTES` 列表删已成功条目，避免重复发布。

### 🚨 发布链脚本预检必须含 6 项硬闸门

自己写的发布链脚本常漏调 `dup_check` → 已发布选题被二次发布（2026-09-14 `r1 第九届中国机器人峰会` 被重发）。
硬要求：逐篇预检必须**同时**跑 7 项，任一不过即 SKIP：**查重（双源）/ 用词+字数 / 地域 / 主办 / 时效资格 / 评级块格式 / 封面来源台账（展会/活动类，`check_cover_source.py` 退 0）**。
模板 `xhs_publish/publish/_publish_chain_s0914.py` 已含；新批次复制改写，不从零重写。

## 四、已发布笔记补救

脚本不能编辑已发笔记，只能 App 走「编辑」。修订稿另存 `*_title_rev.txt`/`*_content_rev.txt`，先跑预检再复制替换；换封面同样满足 `cover-image-rules`。

## 五、与主 skill 冲突点

无结构冲突（流程层，不改主 skill 脚本）。

## 展开阅读（命中场景才读）

| 场景 | 读哪个文件 |
| --- | --- |
| 典型事故复盘、验收清单 | `refs/01-incidents.md` |
| 版本修改记录（v1.0.0 ~ v1.20.0） | `refs/02-changelog.md` |
