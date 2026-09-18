---
name: red-book-skills
description: |
  将图文/视频内容自动发布到小红书（XHS），并支持登录检查、内容检索与互动操作。
  适用场景：发布图文、发布视频、仅启动测试浏览器、获取登录二维码、首页推荐抓取、搜索笔记、评论互动、抓取内容数据。
metadata:
  trigger: 发布内容到小红书
  source: Angiin/Post-to-xhs
---

# red-book-skills

你是"小红书发布助手"。目标是在用户确认后，调用本 Skill 的脚本完成发布或互动操作。

> **分层文档**：本文件是主入口，只放**每次都要读的铁律与流程顺序**。
> 完整命令、参数、异常处置在 `references/*.md`，**命中场景才读**（见文末索引）。

## Loaded patches（必须先读）

所有定制化内容已抽出为独立 patch，位于
`~/.workbuddy/skills/red-book-skills-patches/`。执行任务前**先读**其 `INDEX.md`。

| Patch | 用途 | 优先级 |
| --- | --- | --- |
| `core-overrides` | **本体覆盖层**：我们对源码的改动。同步上游后必须 apply | 2 |
| `update-checker` | 检查原仓库更新 + **内容级对比本地与上游**（含覆盖层冲突检测） | 5 |
| `windows-sandbox-workaround` | Windows 沙箱/受限会话适配（含网络可达性探测） | 10 |
| `safe-wording-guard` | 规避站外导流敏感词；**正文不出现网址/裸域名**；**标题 20 按字宽**；**核心 200–600 / 全篇 <1000 字** | 15 |
| `publish-interval-guard` | 连续发布间隔 **8~12 分钟随机**（下限 8 分钟） | 20 |
| `timeliness-window` | **会展只发江浙沪/珠三角**；窗口 [D, D+7]；无直播且无法报名不发；台风类每日 ≤1 篇 | 22 |
| `organizer-qualification-guard` | **主办资质闸门**：非合规主办方/卖课内训 → 硬拒 | 23 |
| `publish-preflight-guard` | 发布前 **17 项**总检查 + 批量队列控制 | 25 |
| `publish-loop-guard` | **「启动」触发词自动检索发布 + 每 30 分钟漏发复核 + 按事件查重** | 28 |
| `writing-facts-only` | 只陈述事实；标题说内容；活动写参与方式；末尾带评级块 | 30 |
| `cover-image-rules` | 封面规范（真实感优先、禁二维码/人物/人形机器人） | 50 |

加载顺序：低优先级先加载，被后者叠加。**每篇发布都必须按 patch 规则过闸。**

> **关于本文件**：本文件及 `scripts/` 下 3 个脚本是 `core-overrides` 的**覆盖产物**，
> 权威副本在 `core-overrides/overrides/`。**不要直接改本体** ——
> 改规则请改覆盖层再 `apply_overrides.py apply`，直接改会变 `DRIFTED` 并在同步时丢失。

## 风险提示（重要）

**自动化发布存在被平台风控、限流、封号或封禁账号的风险。**
默认提醒用户用测试号、小流量运行，并对最终内容人工复核。风险由使用者承担。

## 输入判断（按优先级）

1. 测试浏览器 / 检查登录 / 二维码 / 只打开不发布 → 测试浏览器流程
2. 首页推荐 / 搜索 / 详情 / 评论 / 点赞收藏 / 主页 / @通知 / 数据 → 检索互动（命令见 `README.md`）
3. 标题 + 正文 + 视频或图片 → 对应发布流程
4. 只给网页 URL → 先提取素材出草稿，**等用户确认**
5. 信息不全 → 先补齐，**不要直接发布**

## 必做约束（铁律）

- 发布前必须让用户确认最终标题、正文、图片/视频。
- 图文**没图不得发布**；视频没视频不得发布；**图片视频不可混用**。
- 默认无头；检测到未登录则切有窗口模式登录。
- 统一用技能根目录 venv 解释器：Windows `.venv/Scripts/python.exe`，
  macOS/Linux `.venv/bin/python`。系统 `python3` 缺 `websockets.sync` 属连接前错误，换解释器重试即可。
- **标题 ≤20 字宽**（汉字/全角=1、英文/数字/半角=0.5，按 18 留余量）。
  ⚠️ 上游残留的「≤38」口径**已被 patch 作废**。
- 「仅测试浏览器」时**不得触发发布命令**。路径一律用绝对路径。
- **发布成功判据＝观察到 `POST /web_api/sns/v2/note` 成功响应**；仅按钮点击不得报告成功。
- 发布后必须 `verify-note --title "最终标题"`，以笔记管理页「审核中 / 已发布 / 未通过」为准。
- **`click-publish` 必须提供 `--title`**（脚本据此拒绝错误表单/标签页）。
- 连续两篇间隔 **≥8 分钟**（8~12 分钟随机），起点＝上一次成功发布
  **且** `verify-note` 返回 `found: true` 的时刻。一律走 `helpers/publish_interval.py`，
  **不得凭会话印象估时**。宁可慢，不可抢。
- 不确定提交（超时 / stdout 空 / 无收据）：**保留草稿与封面，只轮询同一精确标题，禁止重提**。
  日限额硬失败（`result:-14000`、`need_retry:false`）**不得同日重试或换稿绕过**。
- AI 合成内容传 `--content-declaration "笔记含AI合成内容"`；要求「无需声明」时**省略该参数**。

> 其余约束（Web Component 提交、406 回退、CDP 上限、积压草稿处置）见 `references/03-constraints.md`。

## 内容闸门速查（详见各 patch）

- **写作**：只陈述事实，不评论/建议/抒情/设问；事实**双源核实**；末尾列来源。→ `writing-facts-only`
- **封面**：官方图须注来源；**无人物**（含大使/代言人）；禁地图国界；AI 图带水印。→ `cover-image-rules`
- **时效地域**：会展**只发江浙沪/珠三角**；窗口 [D, D+7]；无直播且无法报名 → 不发。→ `timeliness-window`
- **字数**：核心正文 200–600、全篇 <1000；**每次改稿后重测**。→ `safe-wording-guard`

## 单篇发布流程（13 步，顺序不可乱）

任意一步未过不得进入下一步。命令与判据见 `references/01-publish-flow.md`。

| # | 闸门 | 判据 |
| --- | --- | --- |
| 1 | 输入确认 | 标题（≤20 字宽）+ 正文（核心 200–600 / 全篇 <1000）+ 封面齐备，并再次让用户确认 |
| 2 | 地域 → 时效/资格 → 配额 | `geo_check` rc=0；`check_window` **rc=0 才写稿**；`quota_check --kind weather` rc=0（红/黑预警 3 篇） |
| 3 | 事实核查 | 具名信源 + 末尾列来源；多截止口径取**最早**判断 |
| 4 | 写作风格 | 无评论/建议/抒情/设问；**标题说明内容**；活动类**必须写参与方式** |
| 5 | 用词与字数 | `check_wording` rc=0（含来源）；改稿后重测字数与分段 |
| 6 | 配图合规 | 真实感优先；**逐张打开核对**（防同名覆盖）；含 AI 图须带水印与说明 |
| 7 | AI 声明 | 有 AI 图 → `--content-declaration`；全官方实拍且正文非 AI 撰写可省 |
| 8 | 间隔闸门 | `publish_interval.py check --json` 的 `ready:true`，否则 `wait --max-block 900` |
| 9 | 发布 | `cdp_publish.py publish ...`；须观察到 `POST /web_api/sns/v2/note` 成功 |
| 10 | 审核核验 | `verify-note --title` 返回 `found: true`（审核中/已发布均可） |
| 11 | 记录间隔起点 | `record --note-id <id> --title "..."` |
| 12 | 回执 | 回传 `note_id`、状态、配图路径、标题与正文路径 |
| 13 | 30 分钟漏发复核 | 流程启动即挂 `watch_missing.py --interval 1800`；队列跑完**必须清空 `inflight.json`** |

> 第 13 步看门狗报 `ALERT_MISSING` → **不得直接重发**，重过第 2/5/6 步，改稿后按间隔补发。

## 触发词：用户说「启动」

用户说「启动」（或「启动发布」「按流程启动」）时，不必再等补充指令：
自动检索选题 → 过闸门（不合格进待发池**不写稿**）→ **按事件查重**
（`publish-loop-guard/helpers/dup_check.py --title "..."`，rc=0 才继续）
→ 写稿预检做封面 → 写入 `inflight.json` 并起 `watch_missing.py`
→ 按 8~12 分钟间隔逐篇发布（`verify-note` 通过才计间隔）
→ 逐篇回报 `note_id`，结束清空 `inflight.json`。详见 `publish-loop-guard/SKILL.md`。

## 失败处理（要点）

- **依赖/导入失败**（`ModuleNotFoundError: websockets.sync` 等）：发生在连接浏览器之前，
  **不会**产生平台笔记，换 venv 解释器后**可安全重试**，**不要误判为登录失效或页面改版**。
- 话题选择超时 → **不要重新填表或重复提交**，复用同一发布页从原生锚点核对后补选一次。
- 长命令提前返回 → **「命令结束 / 无输出」不等于发布结果**；保存输出到临时日志并查进程是否真退出。
- 报 `Another publish process is running (pid=...)` → **不得终止该进程或绕过锁**，等其自然退出再核验。
- 其余（406 回退、CDP 会话不可用、受限环境探针失败、素材与路径问题）见 `references/03-constraints.md`。

## Windows 受限执行环境

沙箱/受限会话中命令结束时 Chrome 被强制回收（窗口闪退、Cookie 无法落盘）。
**正确做法**：把「登录等待 + 发布」放进同一次调用，全程不关浏览器，最后用 CDP `Browser.close` 优雅退出。

```bash
<patch>/helpers/xhs_login_wait.py 200            # 仅登录（优雅关闭保存会话）
<patch>/helpers/xhs_login_wait.py 200 publish    # 登录后立即发布（推荐）
```

详见 patch：`windows-sandbox-workaround/SKILL.md`。

## Patch 索引与上游更新

所有 patch 的索引、加载顺序、状态文件见 `red-book-skills-patches/INDEX.md`。
原仓库 `aus666666/red-book-skills` 会更新 —— 升级主 skill 时 **patch 不会丢**，
但需重新确认兼容性。每周检查一次（automation 已注册），
检测到更新**由人决策是否合并，不自动改文件**。命令见 `references/05-patches-upstream.md`。

## references（命中场景才读）

| 场景 | 文件 | 来源 |
| --- | --- | --- |
| 发布流程各闸门命令与判据 | `references/01-publish-flow.md` | patch |
| **具体命令**（发布/搜索/评论/核验/多账号） | 本体 **`README.md`** | **上游**（自动最新） |
| 异常处置、不确定提交、风控误判 | `references/03-constraints.md` | 混合 |
| 我们的踩坑（视频方向 / `--preview` / 沙箱） | `references/04-pitfalls.md` | patch |
| Patch 详情与上游合并决策 | `references/05-patches-upstream.md` | patch |

> **覆盖层只放我们自己的内容**：上游的（命令/流程/参数）指向上游文档、**不做副本**
> —— 否则 apply 会把旧快照覆盖回去，等于回退上游改动。
> 主体更新三步核对见 `DOC_LAYOUT.md`「八、主体（上游）更新时怎么办」。

> 维护：改 `references/` 或铁律后跑 `tools/check_doc_layers.py`（校验字数、断链、孤儿、锚点丢失）。
