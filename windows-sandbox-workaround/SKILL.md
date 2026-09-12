---
name: windows-sandbox-workaround
version: 1.5.0
patch_for: red-book-skills
applies_to_main_version: ">=0.1.0"
priority: 10
author: Eric (定制)
created: 2026-09-04
---

# windows-sandbox-workaround

> Patch：解决 Windows 受限执行环境下 Chrome 子进程被会话回收、Cookie 无法落盘、用户看不到浏览器的问题。
> 适用范围：Windows 沙箱 / 受限会话 / WSL / Git Bash / PowerShell ACP 沙箱。

## 问题描述

在某些 Windows 执行宿主中，**由命令启动的 Chrome 会在该命令结束时被强制回收**。两个后果：

1. **窗口一闪而过，用户看不到浏览器**，无法扫码
2. **Cookie 来不及落盘**，下次启动又回到未登录 → 用户被迫反复扫码

常见判定：

```bash
tasklist | findstr chrome.exe   # 0
curl http://127.0.0.1:9222/json/version  # 无响应
```

`Start-Process` 和 WMI（`Invoke-CimMethod Win32_Process.Create`）都无法让 Chrome 逃过回收——前者仍在进程树内，后者甚至可能被安全策略直接拦截。

## 解决方案

**把"登录等待 + 发布"放进同一次调用内完成**，全程不关闭浏览器，最后用 CDP `Browser.close` 优雅退出让 Cookie 落盘。

## 加载方式

主 skill 顶部 `Loaded patches` 段会引用本 patch。
本 patch 自包含 `helpers/xhs_login_wait.py` 和 `helpers/xhs_focus.ps1`，可直接调用。

## 使用

```bash
# 仅登录（优雅关闭以保存会话）
<patch>/helpers/xhs_login_wait.py 200

# 登录成功后立即发布（推荐，避免二次扫码）
<patch>/helpers/xhs_login_wait.py 200 publish

# 与 publish-interval-guard 集成
export XHS_INTERVAL_GUARD=<publish-interval-guard>/helpers/publish_interval.py
<patch>/helpers/xhs_login_wait.py 200 publish
```

## 行为流程

```
1. 启动 Chrome（带 --user-data-dir、--remote-debugging-port=9222）
2. 取二维码，保存为 <workspace>/xhs_login_qrcode.png
3. 调用 xhs_focus.ps1 把窗口最大化并置顶
4. 按 tab ID 锁定登录页，每 4 秒轮询
5. 检测到离开 /login 后做二次验证（重新导航到创作者中心）
6. （如带 publish 参数）执行 publish + verify-note + record
7. 调用 CDP Browser.close 优雅退出
```

## 稿件约定（publish 模式）

```
<workspace>/
├── xhs_publish/
│   ├── title.txt
│   └── content.txt
├── xhs_cover.png  (优先)
│   或 xhs_typhoon_cover.png  (兼容)
│   或 xhs_publish/ 下第一张图片
```

工作区解析顺序：`XHS_WORKSPACE` 环境变量 → 从 cwd 向上找 `xhs_publish/` → 从脚本位置向上找 → 退回 cwd。

## 关键实现要点

### 1. 必须按 tab ID 锁定登录页

若只按"第一个小红书标签"判断，Chrome 会话恢复产生的残留 `/new/home` 标签会让检测在 5 秒内误报"已登录"。

### 2. 必须二次验证

看到 URL 不含 `/login` 还不够。要重新导航到 `creator.xiaohongshu.com/new/home`，确认未被重定向回登录页，才算真登录。

### 3. 必须优雅关闭（不能依赖上层回收）

硬杀会让本次登录的 Cookie 丢失。必须用 CDP `Browser.close`，让 profile 正常落盘。

## 本机进程排查的坑（Windows 沙箱）

排查"是否有并发队列 / 看门狗在跑"时，本机有三个容易误判的点：

1. **venv 的 `python.exe` 每次调用会出现父子两个进程，命令行完全相同**
   → `tasklist` / CIM 里每个 python 任务都"出现两次"。
   **不要据此判定有两个队列在跑**；看 `ParentProcessId` 配对，或直接读
   `_xhs_publish.lock` 里的 pid 认准唯一持有者（锁定 pid 才是真正在发布的那个）。
2. **`wmic` 在本机不可用**（`FileNotFoundError [WinError 2]`）。
   改用 PowerShell 工具执行 `Get-CimInstance Win32_Process -Filter "Name='python.exe'"` 取命令行。
   ⚠️ **但 CIM 快照本身不可靠**：实测同一时刻会**漏报仍活着的进程且不报错**。
   → **进程清单一律以 `tasklist /FO CSV /NH` 为准**（可靠），CIM 只用来补 `CommandLine` / `ParentProcessId`。
3. **端口/浏览器的死活判定只能用 CDP HTTP 端点 —— 裸 socket 会骗人**
   实测：`socket.connect(("127.0.0.1", 9222))` 在 Chrome **正常服务时也会超时**，
   导致脚本误判"没有 Chrome"，于是又去启一个 → 见下面第 6 条的自杀链。
   ✅ 正确探活（直连，绕过代理）：
   ```python
   urllib.request.build_opener(urllib.request.ProxyHandler({})).open(
       "http://127.0.0.1:9222/json/version", timeout=3).read(64)
   ```
   ⚠️ 别用 `curl` 直连（会走代理），也**别用 `tasklist` 里 `chrome.exe` 的条数**交叉验证——
   本沙箱里 Chrome 明明在服务，`tasklist` 仍可能返回 0 条 chrome，会误导。
   更稳的写法：CDP 探针为主，裸 socket（超时放宽到 2.5 秒）仅作兜底。
4. **`chrome.exe` 以 `code=0` 秒退不是错误**：若 `--user-data-dir` 指向的 profile
   已被现有 Chrome 实例占用，新进程会把请求交接给老实例后立刻退出。
   正确处置是**退出后重新用 CDP 探针确认端口可达**，可达即视为"复用现有 Chrome"继续跑；
   反之才是真失败。把它当致命错误会让队列在启动阶段直接自杀。
5. **PowerShell 工具的 stdout 在本环境不回传**（exit code 0 但无输出）。
   必须 `Set-Content` 写到文件，再用 Read 读取。
6. `taskkill /PID <父> /T /F` 会连子进程一起杀；对已被连带杀掉的子 pid 再执行会报
   `not found`，属无害噪音。
7. **不要从 Bash 里调 PowerShell**（安全策略会直接拦截），要用 PowerShell 工具。

清理重复进程的正确姿势：先用 `tasklist` 拿到 pid 清单，再用 CIM 补命令行归类，
看 `ppid` 链判断哪一组在持续工作，把整组（父+子）一起 kill，最后用 `tasklist` 数量前后对比确认。

**注意浏览器会被回收**：即使宿主 python 进程仍活着，它内联启动的 Chrome 也可能中途消失
（9222 变成 JSON 无响应）。长时间队列要在**每篇发布前**探活并自动重启 Chrome，
不要只在队列开头 `ensure_chrome()` 一次。

**`cd` 到含 `( )` 的工作区路径会偶发失败**（`No such file or directory`，路径本身没问题）。
Bash 命令里尽量**用绝对路径直接调用**，或失败后原样重试，别据此判断目录不存在。

## 对外网络可达性：发布前必探（TLS 握手才算数）

发布链路走 **TLS(443)**。本机会出现"**假通**"：TCP connect 成功、`ping` 通、
`curl http://<host>/`（80 端口）还能拿到 302，但 **443 上的 TLS 握手被整段丢弃**
——ClientHello 发出去没有任何回包，一直卡到超时。

这种情况下发布流水线会在 `Clicking '上传图文' tab` 处报
`Could not find '上传图文' tab. The page structure may have changed.`，
**看起来像页面结构变了，其实是网络不通**。Chrome 里表现为 `chrome-error://chromewebdata/`。

> 2026-09-11 实例：批次 17/18 篇正常，收尾那一篇失败。
> 排查发现 `creator.xiaohongshu.com` / `www.xiaohongshu.com` / `www.bilibili.com` TLS 全部超时，
> 而 `baidu / qq / jd / taobao` 全部正常 → 是链路上**对端短时不可达**，不是账号或页面问题。

**判定规则**：

| 现象 | 结论 |
|---|---|
| TLS 握手成功 | 可发布 |
| TCP 可连但 TLS 超时 | **不可发布**（不要重试到把队列跑废，直接等） |
| DNS 解析失败 / TCP 失败 | 不可发布（本机网络断了） |

**别用的判据**（都会骗人）：`ping`、`socket.connect(("host", 443))`、
`http://host/` 的 80 端口状态码、`tasklist` 里 chrome 的条数。

```bash
# 探一次
python <patch>/helpers/net_probe.py
# 网络恢复即自动继续（每 60 秒重试，最多 180 分钟）
python <patch>/helpers/net_probe.py --wait-minutes 180
```

长队列遇到不可达时：**不要空转重试烧掉间隔配额**，先等网络恢复；
已写好但没发出去的那篇按 `publish-loop-guard` 的漏发复核流程补发。

## 已知限制

- **会话内杀进程无法绕开**：如果上层直接 SIGKILL/Stop-Process 当前 shell，Chrome 仍会丢。本 patch 适用于"命令自然完成"的场景。
- **不支持 headless**：因为要扫码，必须有窗口模式。
- **WSL 下可能无效**：WSL 中的 Windows 进程会受 WSL 关闭时回收，与本 patch 同样的问题。

## 与主 skill 的冲突点

- **无**。本 patch 不改主 skill 的 `scripts/cdp_publish.py`。
- **隐式依赖**：`scripts/cdp_publish.py` 必须支持 `--title / --content-file / --images / --content-declaration` 参数。`>=0.1.0` 版本满足。

## 修改记录

- v1.0.0 (2026-09-04) 初版，从主 SKILL.md 第 505-538 行抽出
- v1.1.0 (2026-09-04) 物理迁移到 patch 目录；与 publish-interval-guard patch 通过 `XHS_INTERVAL_GUARD` 环境变量解耦
- v1.2.0 (2026-09-11) 间隔等待 max-block 700 → 900、子进程超时 800 → 1000 秒，适配「8~12 分钟随机」的上界 720 秒
- v1.3.0 (2026-09-11) 新增「本机进程排查的坑」（venv python 父子双进程易误判并发队列、`wmic` 不可用、PowerShell stdout 需落盘再读）
- v1.4.0 (2026-09-11) 修正探活结论：**裸 socket 探 127.0.0.1 在 Chrome 正常服务时也会超时**，
  必须改用 CDP HTTP 端点；`tasklist` 数 chrome.exe 条数不可作证据；新增
  「**Chrome 因 profile 被占用而 `code=0` 秒退不是错误**」的处置规则；
  补「每篇发布前探活并自动重启 Chrome」与「含 `( )` 的路径 `cd` 偶发失败」两条
- v1.5.0 (2026-09-11) 新增「**对外网络可达性：发布前必探（TLS 握手才算数）**」一节与
  `helpers/net_probe.py`：TCP/ping/80 端口都会出现"假通"，443 的 TLS 握手被丢包时
  流水线会在 `上传图文 tab` 处报错并被误认为"页面结构变了"。给出判定表与
  「不可达时空转会烧掉间隔配额，应等待恢复后按漏发复核补发」的处置规则
