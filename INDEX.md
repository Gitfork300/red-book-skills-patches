# red-book-skills Patches

> 定制 patch 集合，叠加在主 skill `aus666666/red-book-skills` 之上。
> 物理位置：`~/.workbuddy/skills/red-book-skills-patches/`
> 目的：让所有定制化内容（用户偏好、平台适配、安全约束、运营规则）独立于主 skill 维护，主 skill 升级时不会丢，且可逐项审视。

## 设计原则

- **本体与补丁分离**（2026-09-12 定）：**我们自己的更新放 patch，原始本体定期和 GitHub 同步**。
  对本体源码的改动不直接写在本体里，而是放 `core-overrides/overrides/` 再 apply
- **每个 patch 是独立 skill**：有自己的 `SKILL.md` + 可选 `helpers/` + `META.json`
- **状态文件自包含**：每个 patch 的状态（间隔记录、更新状态等）放在 patch 自己的 `state/`，不污染主 skill
- **可逐项启用/禁用**：通过 `<patch>/META.json` 中的 `priority` 字段控制加载顺序；删除目录即可停用
- **可逐项升级**：未来增改 patch 不影响主 skill
- **更新提示而非自动合并**：update-checker 只检测上游，不修改任何文件

## Patch 列表（按 priority 升序加载）

| # | Patch | 优先级 | 版本 | 用途 | 配套脚本 |
| --- | --- | --- | --- | --- | --- |
| 1 | `core-overrides` | 2 | 1.0.0 | **本体文件覆盖层**：我们自己对源码的改动（发布按钮重试、沙箱脱离、间隔记录、SKILL.md 规则合并）。同步上游后必须 apply | `helpers/apply_overrides.py` |
| 2 | `update-checker` | 5 | 1.1.0 | 检测原仓库更新 + **内容级对比本地与上游（`diff-local`，忽略行尾假阳性，含覆盖层冲突检测）** | `helpers/update_check.py` |
| 3 | `windows-sandbox-workaround` | 10 | 1.5.0 | Windows 沙箱/受限会话适配 + 进程/探活/网络可达性排查坑位 | `helpers/xhs_login_wait.py`, `helpers/xhs_focus.ps1`, `helpers/net_probe.py` |
| 4 | `safe-wording-guard` | 15 | 0.4.1 | 规避站外导流等敏感词，**正文一律不出现网址/裸域名**；含涉港澳台表述规范 | `helpers/check_wording.py` |
| 5 | `publish-interval-guard` | 20 | 1.2.0 | 连续发布间隔 **8~12 分钟随机**（下限 8 分钟） | `helpers/publish_interval.py` |
| 6 | `timeliness-window` | 22 | 1.3.0 | **会展活动只发江浙沪/珠三角；只发近 7 天在举行 / 需报名的活动；无直播且公众无法报名的不发；台风影响类每日 ≤1 篇** | `helpers/geo_check.py`, `helpers/check_window.py`, `helpers/quota_check.py` |
| 7 | `publish-preflight-guard` | 25 | 1.8.0 | **发布前 15 项总检查 + 批量队列控制** | — |
| 8 | `publish-loop-guard` | 28 | 1.3.0 | **「启动」触发词自动检索发布 + 每 30 分钟漏发复核（只看最近几日/第一页）+ 按事件查重 + 长批次硬停止时间** | `helpers/check_missing.py`, `helpers/watch_missing.py`, `helpers/dup_check.py`, `helpers/recent_published.py` |
| 9 | `writing-facts-only` | 30 | 1.1.0 | 只陈述事实；标题要说内容；活动须写参与方式 | — |
| 10 | `cover-image-rules` | 50 | 1.2.0 | 封面配图规范（真实感优先、禁二维码/人物/完整人形机器人） | — |

加载顺序：低优先级先加载（被后者叠加）。

## 加载方式

主 skill 顶部 `Loaded patches` 段会引用本 INDEX.md。
agent 在执行任何 red-book-skills 任务前，应先扫本目录确认 patch 列表，按 priority 顺序应用。

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

## 与主 skill 的关系

```
本体（上游代码 + 覆盖产物）
└─ red-book-skills/          ← 来自 aus666666/red-book-skills
   ├── scripts/              ← 核心 CDP 自动化（3 个文件被 core-overrides 覆盖）
   ├── SKILL.md              ← 上游骨架 + patch 规则合并（同样被覆盖）
   └── ...                   ← ⚠️ 拷贝安装，无 .git，不能用 git pull 同步

patch 集（本目录）
└─ red-book-skills-patches/  ← 独立维护，物理隔离
   ├── INDEX.md
   ├── core-overrides/        ← 本体文件覆盖层（权威副本在这里）
   ├── update-checker/
   ├── windows-sandbox-workaround/
   ├── safe-wording-guard/
   ├── publish-interval-guard/
   ├── timeliness-window/
   ├── publish-preflight-guard/
   ├── publish-loop-guard/
   ├── writing-facts-only/
   └── cover-image-rules/
```

**同步上游 = 覆盖本体 → `apply_overrides.py apply`**。本体里被我们改过的文件只是
"应用产物"，权威副本在 `core-overrides/overrides/`，所以覆盖不会丢东西。

## 升级主 skill 后如何处理 patch

1. 跑 `update-checker diff-local` —— 看上游改了什么、**覆盖层有没有冲突**
2. **有覆盖层冲突** → 先把上游改动人工合并进 `core-overrides/overrides/`（别直接覆盖本体）
3. 覆盖本体（下载上游快照覆盖，**不是 `git pull`**）
4. `apply_overrides.py status`（预期 PRISTINE）→ `apply` → `verify`
5. 跑自测 + 端到端；更新 `baseline.json` 与 `acknowledge --sha`

完整流程与故障排查详见 [`UPGRADING.md`](./UPGRADING.md)。

## 修改本目录的注意事项

- 删 patch 目录前先确认没有自动化/脚本引用
- 改 patch 内文件不会触发主 skill 重载
- 新增 patch 必须在 INDEX.md 同步登记

## 修改记录

- v1.6.9 (2026-09-12) **确立「本体与补丁分离」架构**（用户原则：我们自己的更新放 patch，
  原始本体定期和 GitHub 同步）。新增 `core-overrides`（priority 2）：把此前**直接改在本体里的
  4 个文件**（约 470 行我们的改动：`SKILL.md` / `cdp_publish.py` / `chrome_launcher.py` /
  `publish_pipeline.py`）抽成覆盖层 —— 权威副本在 patch，本体里的是应用产物，
  配 `apply_overrides.py`（status/verify/apply/diff）+ `baseline.json` 基线指纹；
  `update-checker` 的 `diff-local` 增加**覆盖层冲突检测**（上游也改过被覆盖文件即报警）；
  `UPGRADING.md` 1.6.3→**1.7.0** 删除 22 条人工迁移清单、修正失效的 `git pull` 指令。
  来源：查上游更新时发现本体被我们改脏，无法安全同步
- v1.6.8 (2026-09-12) `update-checker` 1.0.0→**1.1.0**：新增 `diff-local` 子命令
  （拉上游快照做**内容级对比**，内置行尾 CRLF/LF 与 BOM 归一化、跳过运行时目录，
  输出「相同/内容不同/仅上游有/仅本地有」四分类），并补记**本地增强清单**
  （`cdp_publish.py` 发布按钮三级重试、`chrome_launcher.py` 沙箱脱离 job、
  `publish_pipeline.py` 间隔记录、`SKILL.md` patch 合并）——覆盖即回退。
  来源：查上游更新时只比 commit sha 无法判断"这次改动会不会砸到本地定制"
- v1.6.7 (2026-09-11) `safe-wording-guard` 0.3.0→**0.4.0**：**裸域名纳入 P0**（`github.com/xxx`、
  `xxx.ai`、`www.xxx.com` 与完整 URL 同罪）；新增「来源标注的合规写法」（只写机构名+项目名+论文编号）。
  来源：用户要求『不要直接出现网站』，而当时 P0 只拦 `https?://`，ai0911_04/08/10/18 四篇研究成果稿
  的 `github.com/...`、`Z.ai` 全部漏检并发出。`publish-loop-guard` 1.2.0→**1.3.0**：明确复核范围
  「只看最近 2~3 天 + 平台侧只读第一页」，新增 `helpers/recent_published.py`
- v1.6.6 (2026-09-11) `publish-loop-guard` 1.1.0→**1.2.0**：新增「**排队前的选题查重（按事件，不按标题字面）**」
  与 `helpers/dup_check.py`（「事件标识相同」+「公共子串 ≥5 字」双信号，日期串不算证据）。
  来源：`浦江创新论坛` 同一场活动被发了两遍（00:48 / 06:12），精确匹配的查重没拦住；
  `publish-preflight-guard` 第 1 项「选题查重」改为指向 `dup_check.py`
- v1.6.5 (2026-09-11) `windows-sandbox-workaround` 1.4.0→**1.5.0**：新增「对外网络可达性：发布前必探（TLS 握手才算数）」
  与 `helpers/net_probe.py`（TCP/`ping`/80 端口都会"假通"）；`publish-preflight-guard` 1.6.0→**1.7.0**
  （总检查 14→**15 项**，新增「网络可达性」）。来源：ai0911 第 18 篇在 `上传图文 tab` 处失败，实为 443 TLS 被丢包
- v1.6.4 (2026-09-11) `timeliness-window` 1.2.0→**1.3.0**：新增「地域范围」——**会展活动只发江浙沪或珠三角**
  （其他地区一律不发；研究成果/政策类不受限），新增 `helpers/geo_check.py`（白名单+黑名单，退出码 0/1/2）；
  `publish-preflight-guard` 1.5.0→**1.6.0**（总检查 13→**14 项**，地域范围列为第 2 项，闸门顺序「地域→时效→资格→配额」）
- v1.6.3 (2026-09-11) `publish-loop-guard` 1.0.0→**1.1.0**：新增「长批次的硬停止时间」写法
  （截止时间写进队列脚本，判定点放在间隔等待之后）；「已知坑」补**看门狗与 `inflight.json` 的启动竞态**
  （顺序反了首轮会把整批在队稿件误报为漏发并立即告警退出）
- v1.6.2 (2026-09-11) `windows-sandbox-workaround` 1.3.0→**1.4.0**：探活结论纠错
  （裸 socket 探 loopback 在服务正常时也会超时 → 必须用 CDP HTTP 端点；chrome.exe 条数不可作证据）、
  新增「Chrome 因 profile 占用 `code=0` 秒退不是错误」与「每篇发布前探活自动重启 Chrome」规则
- v1.6.1 (2026-09-11) `windows-sandbox-workaround` 1.2.0→**1.3.0**：新增「本机进程排查的坑」
  （venv python 父子双进程易误判并发队列、`wmic` 不可用、PowerShell stdout 需落盘再读、禁止从 Bash 调 PowerShell）
- v1.6.0 (2026-09-11) 新增 `publish-loop-guard`（priority 28：「启动」触发词自动检索发布 + 每 30 分钟漏发复核）；
  `timeliness-window` 1.1.0→**1.2.0**（新增选题配额：台风影响类每日 ≤1 篇 + `quota_check.py`）；
  `publish-preflight-guard` 1.2.0→**1.4.0**（总检查 12→**13 项**，补队列「启动」与看门狗要求）
- v1.5.0 (2026-09-11) `timeliness-window` 1.0.0→**1.1.0**：新增「可发布资格」（无直播且普通观众无法报名 → 不发；有直播必须提示直播信息），`check_window.py` 增 `--live` / `--public-signup` 与退出码 3；`publish-preflight-guard` 1.1.0→**1.2.0**（总检查 11→12 项）；表格版本列顺带修正
- v1.4.0 (2026-09-11) `safe-wording-guard` 0.2.0→**0.3.0**：新增「涉港澳台强制表述规范」章节（统一中国香港/中国澳门/中国台湾地区，涉台只陈述事实）
- v1.3.0 (2026-09-11) 新增 `timeliness-window`（priority 22，近 7 天时效窗口 + `check_window.py`
  预检 + 待发池 `state/pending_pool.json`）；表格重排
- v1.2.0 (2026-09-11) 新增 `publish-preflight-guard`（发布前 10 项总检查 + 队列控制）；
  `writing-facts-only` v1.1.0（标题规则 + 活动必写参与方式）；
  `cover-image-rules` v1.1.0（真实感优先 + 禁二维码 + 生图文件名冲突）；
  `safe-wording-guard` v0.2.0（"免费+登记"组合判定的修法）；表格按 priority 重排并补版本列
- v1.1.0 (2026-09-06) 新增 `safe-wording-guard`（站外导流等敏感词预检）
- v1.0.0 (2026-09-04) 初版，从主 SKILL.md 抽出 4 个章节（封面规范、写作规范、间隔、Windows 适配），新增 update-checker 与本 INDEX
