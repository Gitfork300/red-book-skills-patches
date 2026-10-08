> read_when: 需要 windows 沙箱下进程排查/工具链/网络探测的完整坑案例与脚本片段时
> 本文件是 `SKILL.md` 的展开，规则结论仍以 SKILL.md 为准（system: shared）。

# windows-sandbox-workaround / refs — 坑案例与脚本

## 一、本机进程排查的坑（Windows 沙箱）

1. **venv 的 `python.exe` 每次调用出现父子两个进程，命令行完全相同** → `tasklist`/CIM 里每个 python 任务"出现两次"。不要据此判定两个队列在跑；看 `ParentProcessId` 配对，或读 `_xhs_publish.lock` 里的 pid 认唯一持有者。
2. **`wmic` 在本机不可用**（`FileNotFoundError [WinError 2]`）。改用 PowerShell 工具 `Get-CimInstance Win32_Process -Filter "Name='python.exe'"`。⚠️ CIM 快照会漏报仍活着的进程且不报错 → **进程清单一律以 `tasklist /FO CSV /NH` 为准**。
3. **端口/浏览器死活判定只能用 CDP HTTP 端点 —— 裸 socket 会骗人**：`socket.connect(("127.0.0.1", 9222))` 在 Chrome 正常服务时也会超时。
   ```python
   urllib.request.build_opener(urllib.request.ProxyHandler({})).open(
       "http://127.0.0.1:9222/json/version", timeout=3).read(64)
   ```
   ⚠️ 别用 `curl` 直连（走代理）；**代理的典型症状是 `HTTP 502 Bad Gateway` 不是超时**。要么 `ProxyHandler({})`，要么 `http.client.HTTPConnection("127.0.0.1", 9222)`（默认不走代理，最省心）。
4. **`chrome.exe` 以 `code=0` 秒退不是错误**：profile 被现有实例占用时，新进程交接给老实例后立即退出。正确处置 = 退出后重新用 CDP 探针确认端口可达，可达即"复用现有 Chrome"。
5. **PowerShell 工具 stdout 在本环境不回传**（exit 0 但无输出）→ 必须 `Set-Content` 写文件再 Read。
6. `taskkill /PID <父> /T /F` 会连子进程一起杀；对已被连带杀掉的子 pid 再执行报 `not found` 属无害噪音。
7. **不要从 Bash 里调 PowerShell**（安全策略拦截），用 PowerShell 工具。
8. **长批次不要用 `nohup <cmd> &` 起后台** —— Bash 工具调用一返回，整个后台进程组被回收，python 与内联 chrome 一起消失，日志停在半路不报错。✅ 用 Bash 工具自带 `run_in_background`。
   ⚠️ 队列中断后先确认"最后一篇发没发"再重跑：以平台侧全量清单 `list_all_notes.py --days 1` 为准；`verify-note` 在此场景假阴性（`found:false` 但 stderr 刷 `CDP error: No resource with given identifier found`，检索没跑完）。

清理重复进程姿势：先 `tasklist` 拿 pid，再 CIM 补命令行归类，看 `ppid` 链，把整组（父+子）一起 kill，最后 `tasklist` 数量前后对比确认。

**浏览器会被回收**：即使宿主 python 仍活着，内联启动的 Chrome 也可能中途消失（9222 无响应）。长队列要**每篇发布前**探活并自动重启 Chrome，别只在开头 `ensure_chrome()` 一次。

**Chrome 与启动它的 python 进程同生共死**：`chrome_launcher.py` 单独跑完即退出 → 9222 约 6 秒内拒绝连接（`CREATE_BREAKAWAY_FROM_JOB | DETACHED_PROCESS` 也拦不住）。需多命令间复用 Chrome 时，另起保活进程：

```python
# xhs_publish/_keep_chrome_alive.py —— 后台常驻
sys.path.insert(0, r"<skill>\scripts"); os.chdir(r"<skill>")
from chrome_launcher import ensure_chrome
ensure_chrome()
while True:
    time.sleep(30)
    if not port_open(): ensure_chrome()
```

判据：保活进程活着 → 9222 持续可用；进程一停 → Chrome 秒级消失。

## 二、本机工具链的坑

### 1. 同一文件不要并行发多个 Edit —— 会静默丢失

对同一文件同一轮发两个 Edit：后写覆盖前写，先发的改动静默消失，且两步都报"成功"。
做法：同文件多次修改串行发；改完逐文件 grep/Read 复核；只有跨文件互不影响才并行。

### 2. Bash 整段失效时的唯一可靠路径

✅ 命令开头显式补 PATH 即可让 `ls`/`grep`/`head` 全部恢复（根因：shim 脚本 `dirname` 找不到、PATH 没设好）：

```bash
export PATH="/c/Users/<user>/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:\
/c/Users/<user>/.workbuddy/binaries/PortableGit/versions/1.2.0/bin:/c/Windows/System32:/c/Windows:$PATH"
```

三条配套铁律：
1. shell 路径一律 POSIX `/c/Users/...`（用 `C:/` 会报 No such file）。
2. `cd` 偶发失败 → 命令内全用绝对路径。
3. `python.exe` 入参必须 `C:/`（收到 `/c/` 报 No such file）。

| 想做的事 | 可靠做法 |
|---|---|
| 跑 Python | 绝对路径直呼 managed 解释器 |
| 读/写/搜文件 | Read/Write/Edit/Grep/Glob 工具 |
| 拿 PowerShell 输出 | 先 `Out-File` 落盘再 Read |
| 列/杀进程 | `tasklist /FO CSV /NH` |

> 稍复杂逻辑一律 Write 成临时 `.py` 再执行，比调试内联 `-c` 的引号快。

### 3. Read / Write / Glob 对含 `()` 的路径偶发失败

用户名或路径中包含括号时，`Write` 可能报 `EPERM` 并截断路径；`Read`/`Glob` 也可能暂时报"不存在"。做法：原样重试一次，仍败换通道：

| 通道 | 用法 |
|---|---|
| Bash heredoc | `cat > 目标 << 'PYEOF' … PYEOF` |
| 临时目录中转 | 写到无括号的 `%TEMP%\x.py`，执行完删除 |
| PowerShell | `[System.IO.File]::WriteAllText`（stdout 不回传，落盘再读） |

## 三、对外网络可达性（TLS 握手才算数）

本机会"假通"：TCP connect 成功、`ping` 通、`curl http://<host>/`（80）拿到 302，但 443 的 TLS 握手被整段丢弃。
此时流水线在 `Clicking '上传图文' tab` 报 `Could not find '上传图文' tab. The page structure may have changed.` —— 看着像页面改版，实为网络不通；Chrome 里表现为 `chrome-error://chromewebdata/`。

2026-09-11 实例：批次 17/18 正常，收尾一篇失败；`creator/www.xiaohongshu.com`、`www.bilibili.com` TLS 全超时，`baidu/qq/jd/taobao` 正常 → 对端短时不可达，非账号或页面问题。

```bash
python <patch>/helpers/net_probe.py                    # 探一次
python <patch>/helpers/net_probe.py --wait-minutes 180 # 每 60 秒重试，最多 180 分钟
```

## 四、保活档到期**不一定**回收 Chrome —— 取决于「持有者是否归零」（2026-09-16 两个对照实例）

> **结论先行**：危险的**不是「某个档跑满退出」**，而是「**Chrome 的持有者归零**」。
> 判断一次保活档退出是否致命，先数**还有几个 `_chrome_hold*.log` 在持续更新**：
> ≥1 个 → 退档无风险；0 个 → 必然回收，立刻补档。

### 实例 A（12:43，**出事**）：唯一持有者退出
C 批 10 篇错峰发布进行到第 6 篇前，`chrome.exe` 从 `tasklist` 消失、`9222` 拒绝连接；
但发布链进程仍在跑，看起来像"发布器挂了"。

| 时刻 | 事件 |
|---|---|
| 11:43 | 60 分钟档 `_chrome_hold.py` 启动，`ensure_chrome()` **拉起并持有** Chrome |
| ~12:43 | 该档 `alive 60 min` 跑满退出 → **它是当时 Chrome 的唯一持有者** → Chrome 随父进程被回收 |
| ~12:43 | 180 分钟档 `_chrome_hold_long.py` 下一个 tick 探测到 `!! 9222 DOWN`，开始 `ensure_chrome()` 补拉 |
| ~12:44 | 补拉输出落到日志、9222 恢复 → 但此间约 **30 秒**端口不可用 |

**危险点**：空窗期间任何一次发布触发都会失败。本次是 C 批 c5 恰在 **12:44:01** 发出（抢在空窗前），
属运气；若 c6 的 `publish_interval` 恰好在 12:43:40 放行，就会丢稿。

### 实例 B（15:00，**未出事**）：多持有者，退一档无影响
180 分钟档 `_chrome_hold_long.py`（11:59 起）跑满 180 分钟退出，**Chrome 完好无损**：

| 时刻 | 事件 |
|---|---|
| 15:00:05 | 现场探测：CDP **200 / Chrome 152.0.7977.83**、`chrome.exe` **36 个进程**在册 |
| 15:00 | `_chrome_holdXL.log`（接力器 13:33 起）最后更新 **14:57**、`_chrome_holdXL2.log`（12:48 起）最后更新 **15:00** → **两个持有者都活着** |

**这是对实例 A 结论的必要修正**：上午把因果写成「档位跑满 = 一次回收」，其实漏了前提。
Chrome 是**引用计数式**存活 —— 只要还有另一个 `_chrome_hold*` 进程持有它，退档就不回收。

### 可操作的判活顺序（含本次新增的前置检查）
0. **前置**：`ls logs/_chrome_hold*.log` 看**有几个在持续更新**（mtime 在最近 1 分钟内）。
   - ≥1 → Chrome 有人持有，**任何档退出都不用慌**；
   - 0 → 立即补起 `_chrome_hold_xl.py`，再往下查。
1. `logs/_chrome_hold*.log` **末行**（`alive N min | port9222=True/False`）。
2. `tasklist /FI "IMAGENAME eq chrome.exe" /NH`（在册数量；正常 30–40 个，多进程架构）。
3. 才到 9222。**顺序错了会把「保活档到期」误判成「发布器故障」**。

### 固化做法
1. **总时长 > 60 分钟的批次，开跑前就起 `_chrome_hold_xl.py`（300 分钟）**，不要用 60 分钟档接力。
   本机脚本族：`_chrome_hold.py`=60 min / `_chrome_hold_long.py`=180 min / `_chrome_hold_xl.py`=300 min
   （三者逻辑相同，只有 `range()` 次数不同：120 / 360 / 600，每 tick 30 秒）。
2. **保活覆盖靠「多档叠加」，不靠单档够长**：最长档只有 300 分钟，长批次要**同时挂 2 档、起始时间错开**，
   覆盖区间互相重叠 → 任一档到期都不会让持有者归零。本日实测：13:33 起的 XL 档（→18:33）
   + 12:48 起的 XL2 档（→17:48），稳稳覆盖 D 批 17:30 的收尾。
3. **判活顺序**见上「可操作的判活顺序」（前置数活跃档 → 日志末行 → `chrome.exe` 在册 → 9222）。
4. **探 9222 一律用 `http.client.HTTPConnection`**。`urllib.request` **走系统代理**会返 `502 Bad Gateway`
   （假信号）；本机代理环境实测每次都 502，与 Chrome 死活无关。
5. Chrome 重启后 **登录态仍有效**（profile 落盘于
   `%LOCALAPPDATA%\Google\Chrome\XiaohongshuProfiles\<account>`）；标签变成 `chrome://newtab/` 属正常。
   验登录时**先删 `tmp/login_status_cache.json`**（TTL 12h，否则误报已登录）。

### 顺带：`cdp_publish.py` 的两个参数陷阱
- `--reuse-existing-tab` / `--account` / `--port` 是**全局参数，必须写在子命令之前**：
  `python scripts/cdp_publish.py --reuse-existing-tab check-login` ✅
  `python scripts/cdp_publish.py check-login --reuse-existing-tab` ❌ → `unrecognized arguments`。
- 登录成功哨兵串是 **`Login confirmed.`**（缓存命中为 `Login confirmed (cached).`）；退出码 0/1 区分是否已登录。
