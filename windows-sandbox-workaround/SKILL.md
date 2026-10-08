---
name: windows-sandbox-workaround
system: shared
version: 1.7.0
patch_for: red-book-skills
applies_to_main_version: ">=0.1.0"
priority: 10
author: Project maintainers
created: 2026-09-04
---

# windows-sandbox-workaround

> Patch：解决 Windows 受限执行环境下 Chrome 子进程被会话回收、Cookie 无法落盘、用户看不到浏览器的问题。
> 适用范围：Windows 沙箱 / 受限会话 / WSL / Git Bash / PowerShell ACP 沙箱。
> 定时巡检/复核先探测配置的 CDP HTTP 端点；不可达就明确失败并停止，不要自动启动 Chrome，也不要用过期快照下结论。

## 铁律速查

1. **把「登录等待 + 发布」放进同一次调用内完成**，全程不关浏览器，最后用 CDP `Browser.close` 优雅退出让 Cookie 落盘。
2. **用户要扫码时一律用 `keep-open`**（登完不关窗，会话生效后正常关窗即落盘）。
3. **按 tab ID 锁定登录页**（残留 `/new/home` 标签会让"第一个小红书标签"误报已登录）；**二次验证** = 重导航 `creator.xiaohongshu.com/new/home` 确认没被重定向回登录页。
4. **登录成功哨兵串 = stdout 里的 `Login confirmed`**（缓存命中为 `Login confirmed (cached).`）；该命令**不输出 JSON、退出码不区分**登录与否。别去找 `{"logged_in": true}`。
5. **判断顺序：先排除我方问题，再怀疑平台。**
6. **长批次用 Bash 工具自带的后台执行（`run_in_background`），不要 `nohup`/`&`**（命令返回即整组被回收，日志停在半路）。
7. **探活只看 CDP HTTP 端点**（裸 socket 会假超时、走代理会返 502）；`tasklist` 的 chrome 条数不可作证据。
8. **对外网络可达性：TLS 443 握手成功才算数**（`ping` / TCP / 80 端口都是假通）。
9. **同一文件不要并行发多个 Edit**（后写覆盖前写、都报成功）；改完逐文件回读复核。
10. **含 `()` 的路径偶发失败**（Write 会 EPERM 截断、Read/Glob 假报不存在）→ 原样重试一次，仍败换通道（heredoc / `%TEMP%` 中转 / PowerShell 落盘）。
11. **无人值守巡检先探测预期 CDP HTTP 端点**；端口不可达则明确失败并停止，不得为巡检自动拉起新的 Chrome。
12. 取数后的快照必须核对 `fetched_at` 确属本轮新取；时间戳缺失或过旧即视为取数失败，不得据此给出“无变化/无数据”结论。

## 使用

```bash
<patch>/helpers/xhs_login_wait.py 200            # 仅登录（优雅关闭保存会话）
<patch>/helpers/xhs_login_wait.py 200 keep-open  # 登录后保持窗口（用户扫码）
<patch>/helpers/xhs_login_wait.py 200 publish    # 登录后立即发布（推荐）
```

工作区解析顺序：`XHS_WORKSPACE` 环境变量 → 从 cwd 向上找 `xhs_publish/` → 从脚本位置向上找 → 退回 cwd。
稿件约定：`xhs_publish/title.txt` + `content.txt`；封面优先 `xhs_cover.png`。

## 登录态与风控（最容易踩的几条，全表见 `xhs-risk-guard`）

| 现象 | 真因 | 做法 |
| --- | --- | --- |
| `check-login` 报已登录但接口 401 | 命中 `tmp/login_status_cache.json`（TTL 12h） | 先删缓存再验（`clear_cache()`） |
| 落地 URL 变 `…/login?redirectReason=401` | 会话真失效 | 重走登录，别判成"功能下线" |
| 以为每次要重新扫码 | 登录态会落盘 profile | 扫一次即可，重启 Chrome 仍有效 |
| 扫码窗口一闪而过 | 宿主回收 Chrome | 同一次调用内完成；用 `keep-open` |
| `captureScreenshot` 超时 | 多半已扫码成功（页面跳 `/new/home`） | 先看 9222 落地 URL / 直接 `check-login` |

## 本机进程排查（要点，细节见 refs）

1. venv 的 `python.exe` 每次出现**父子两个进程、命令行相同** → 看 `ParentProcessId` 或读 `_xhs_publish.lock` 认唯一持有者。
   - **❗️先别当成两个实例**（2026-09-16 实测）：`.venv\Scripts\python.exe` 是**启动器 stub**，会 re-exec 基础解释器，于是同一命令行出现两行。
   - 区分方法：**看内存**——stub ≈ **10 MB**、真实解释器 ≈ **24 MB**。两行内存一高一低＝一个逻辑进程；
     两行都 ≈24 MB 才是真重复实例（此时才需要停一个）。
   - 走**系统 python 绝对路径**（`~/.workbuddy/binaries/python/versions/<ver>/python.exe`）启动时**只有一行**，无 stub。
2. `wmic` 不可用；CIM 快照会漏报 → **进程清单一律以 `tasklist /FO CSV /NH` 为准**，CIM 只补 CommandLine/ParentProcessId。
3. 端口/浏览器死活**只能用 CDP HTTP 端点**；裸 socket 在 Chrome 正常服务时也超时。
4. `chrome.exe` 以 `code=0` 秒退（profile 被占用）**不是错误** → 用 CDP 探针确认端口可达即"复用现有 Chrome"。
5. PowerShell 工具 stdout 不回传 → `Set-Content` 落盘再 Read。
6. **Chrome 是「引用计数式」存活 —— 持有者归零才被回收**：需多命令间复用 Chrome 时，另起保活进程常驻持有。
   - **❗️保活档退出是否致命，取决于「还有没有别的持有者」**（2026-09-16 两实例对照）：
     12:43 唯一持有者（60 分钟档）退出 → Chrome 归零、9222 断；15:00 多持有者时 180 分钟档退出 → **CDP 仍 200**。
     ~~"档位跑满 = 一次回收"~~ 漏了前提，勿再照抄。
   - **判活前置**：`ls logs/_chrome_hold*.log` 数有几个 mtime 在最近 1 分钟内 → **≥1 则退档无风险，0 则立刻补档**。
     再按序看：日志末行 → `chrome.exe` 是否在册（正常 30–40 个）→ 才到 9222。
   - **补拉有约 30 秒空窗**：另一档要等下一个 tick 才探测到 `!! 9222 DOWN` 并补拉；空窗落在发布触发点就丢稿。
   - **长批次靠「多档叠加」而非单档够长**：最长档 300 分钟，超长任务同时挂 2 档、起始时间错开、覆盖区间重叠。
     **不要用 60 分钟档「接力」**——接力点必有空窗。
   - **❗️区分「自然到期」与「被外部清理」——后者加长档位没用**（2026-09-16 D 批 t20 丢失实例）：
     两档（XL 13:33 起 / XL2 12:48 起）**在 17:13 前后同时停止**；按 300 分钟档它们应分别到 18:33 / 17:48，
     **都没跑满** → 不是自然到期，**推断**为外部统一清理（已知坑：宿主在后台任务结束时可能清理进程树，
     连带误杀后台子进程；⚠️ 此推断**尚未确证**）。t20 的放行时刻（约 17:16）正好落在 Chrome 已回收的空窗里 → 丢失。
     - **判据**：日志末行 `alive N min` 的 N **明显小于档位总分钟数** ＝ 被清理（对比：自然到期时 N ≈ 档位分钟）。
       此时**再加长档位没有用**，要改**前台阻塞**（`subprocess.run` 而非 `Popen`）或换独立会话跑保活。
     - **覆盖时长算法**：不能只按「篇数 × 间隔」，须再加**最后一篇的放行等待 + 发布耗时**（预留约 2 个间隔）。
   - 保活档到期 **≠ 发布器故障** —— 判活顺序错了必然误判。
   - Chrome 重启后**登录态仍有效**（profile 落盘），但出现新标签页属正常，不要当成"掉登录"；仍按铁律**先删 `tmp/login_status_cache.json` 再验**。
7. **不要从 Bash 里调 PowerShell**（安全策略拦截）；用 PowerShell 工具。

## 本机工具链（要点，细节见 refs）

- Bash 整段失效（`ls/cat/grep` 全 `command not found`）→ 两种通道，**优先第 2 种**：
  1. 命令开头 `export PATH=.../PortableGit/versions/<ver>/usr/bin:.../bin:$PATH`——**不保证恢复**。
     **2026-09-16 实测失效**：export 之后 `ls/cat/tail/grep` 仍 `command not found`，
     且 shim 自身刷 `dirname: command not found` / `cd: null directory`（可忽略的噪声）。
  2. **绝对路径调用 + stdout 落盘**（可靠）：`G='~/.workbuddy/binaries/PortableGit/versions/<ver>/usr/bin'`
     然后 `"$G/ls.exe" ... > 输出文件`，再用 **Read / Grep 工具读该文件**。
     ⚠️ 绝对路径调用的 **stdout 不回传工具**（显示 `(empty)`），所以必须落盘再读。
     **例外**：Windows 原生 exe（`tasklist`）stdout 可直接读到，无需落盘。
  - ⚠️ PortableGit 真实位置在 `~/.workbuddy/binaries/PortableGit/versions/<ver>/usr/bin`，
    **不是** `AppData/Local/Programs/PortableGit`（后者不存在，指错会一直 command not found）。
  - 只读文件内容时直接走 Read/Grep/Glob 工具，不必折腾 shell。
- 路径风格口诀：**shell 用 POSIX `/c/`，`python.exe` 入参用 `C:/`**；`cd` 偶发失败故命令内全用绝对路径。
- 多行逻辑 Write 成临时 `.py` 再跑，别憋内联 `-c`。

## 对外网络可达性

发布走 **TLS(443)**。`ping` / `socket.connect` / 80 端口状态码**都会假通**；
443 的 TLS 握手被整段丢弃时，流水线会在 `上传图文` tab 处报"页面结构可能变化"（实为网络不通）。

| 现象 | 结论 |
| --- | --- |
| TLS 握手成功 | 可发布 |
| TCP 可连但 TLS 超时 | 不可发布（别空转烧间隔配额，等恢复） |
| DNS/TCP 失败 | 不可发布 |

长队列遇不可达：先等网络恢复，没发出去的那篇按 `publish-loop-guard` 漏发复核补发。

## 已知限制

- 会话内被 SIGKILL/Stop-Process 仍会丢 Chrome（本 patch 只覆盖"命令自然完成"）。
- 不支持 headless（要扫码）；WSL 下可能无效。

## 与主 skill 的冲突点

无（不改 `scripts/cdp_publish.py`）；隐式依赖其支持 `--title/--content-file/--images/--content-declaration`。

## 展开阅读（命中场景才读）

| 场景 | 读哪个文件 |
| --- | --- |
| 本机进程/工具链/网络的完整坑案例与脚本 | `refs/01-pitfalls.md` |
| 版本修改记录（v1.0.0 ~ v1.7.0） | `refs/02-changelog.md` |
