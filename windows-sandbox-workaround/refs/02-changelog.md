> read_when: 需要回溯 windows-sandbox-workaround 历史版本时
> 本文件是 `SKILL.md` 的修改记录（v1.0.0 ~ v1.6.9），规则结论仍以 SKILL.md 为准（system: shared）。

# windows-sandbox-workaround / refs — 修改记录

- v1.6.9 (2026-09-16 晚) **新增「自然到期 vs 被外部清理」判据 + 覆盖时长算法**：
  复盘 D 批 t20 丢失事故 —— XL（13:33 起）/ XL2（12:48 起）两档 **都在 17:13 前后同时停止**；
  按 300 分钟档应分别到 18:33 / 17:48，**均未跑满** → 非自然到期（**推断**为外部统一清理，尚未确证）。
  补两条：① 判据 `alive N min` 明显小于档位总分钟＝被清理，加长档位无用，需改前台阻塞 / 独立会话；
  ② 覆盖时长须加「最后一篇放行等待 + 发布耗时」，预留约 2 个间隔。
- v1.6.8 (2026-09-16) **修正 v1.6.7 的因果表述**（同日第二个保活实例证伪了它）：
  v1.6.7 写的是"保活档跑满到期 = 一次 Chrome 回收"，**漏了前提**。15:00 实测：180 分钟档
  `_chrome_hold_long.py`（11:59 起）跑满退出，**Chrome 完好** —— CDP 200 / Chrome 152 / `chrome.exe` 36 个在册。
  真因是 **Chrome 为引用计数式存活，持有者归零才回收**；此刻 `_chrome_holdXL.log`（13:33 起）与
  `_chrome_holdXL2.log`（12:48 起）两个持有者都活着，退一档无影响。改动三处：
  ① `SKILL.md` 第 6 条改为「引用计数式存活」，加**判活前置**：先数有几个 `_chrome_hold*.log` mtime 在最近 1 分钟内，
  ≥1 则退档无风险、0 则立刻补档；并新增「长批次靠多档叠加而非单档够长」。
  ② `refs/01-pitfalls.md` 第四节重写为 **A（12:43 唯一持有者→出事）/ B（15:00 多持有者→无事）双实例对照**，
  含「可操作的判活顺序」0–3 步。
  ③ 本文件。
- v1.6.7 (2026-09-16) 两处**实测纠错**，均来自 C 批 → W 天气稿 → D 批串行接力任务：
  ① **推翻 v1.6.6 的"Bash 整段失效 → `export PATH=` 即可完全恢复"**。2026-09-16 实测在命令开头
  `export PATH=.../PortableGit/versions/1.2.0/usr/bin:.../bin:$PATH` 之后，`ls/cat/tail/grep` **仍**
  `command not found`（shim 自身持续刷 `dirname: command not found` / `cd: null directory`，属噪声可忽略）。
  可靠通道改为：**绝对路径调用 `"$G/ls.exe"`（`G=.../PortableGit/versions/<ver>/usr/bin`）＋ stdout 落盘**，
  再用 Read / Grep 工具读该文件 —— **绝对路径调用的 stdout 不回传工具**（显示 `(empty)`），这正是必须落盘的原因；
  **例外**：`tasklist` 等 Windows 原生 exe 的 stdout 可直接读到。另固化 PortableGit 真实位置为
  `~/.workbuddy/binaries/PortableGit/versions/<ver>/usr/bin`，**不是** `AppData/Local/Programs/PortableGit`。
  ② **venv `python.exe` 出现双进程 ≠ 两个实例**：`.venv\Scripts\python.exe` 是**启动器 stub**，会 re-exec
  基础解释器，于是同一命令行出现两行。**看内存区分**：stub ≈ **10 MB**、真实解释器 ≈ **24 MB**；
  一高一低＝一个逻辑进程，两行都 ≈24 MB 才是真重复实例（此时才需停一个）。走系统 python 绝对路径
  （`~/.workbuddy/binaries/python/versions/<ver>/python.exe`）启动则只出现一行。
  （今日曾差点把 `_start_T_after_C.py` 接力器误判为双实例误杀。）
  ③ **保活档「跑满到期」＝一次 Chrome 回收，而非发布器故障**：60 分钟档 `alive 60 min` 收尾退出时，它拉起的
  Chrome 一并消失（`tasklist` 里 `chrome.exe` 归零、9222 拒绝连接）；**其余保活档要等下一个 30 秒 tick 才探测到
  9222 DOWN 并补拉 → 约 30 秒空窗**。故**总时长 > 60 分钟的批次必须提前起超长档**（`_chrome_hold_xl.py` = 300 分钟），
  **不能用 60 分钟档「接力」** —— 接力点必有空窗，空窗正好落在发布触发点就丢稿。
  判定顺序固化：先看 `logs/_chrome_hold*.log` 末行 + `chrome.exe` 是否在 `tasklist`，再判 9222。
  另：Chrome 重启后**登录态仍有效**（profile 落盘），新标签页属正常，别判成掉登录。
  来源：2026-09-16 C 批进行中（60 分钟档 11:43→12:43 到期带走 Chrome，C 批 c5 抢在空窗前 12:44:01 发出）。
- v1.6.6 (2026-09-15 下午) 「本机工具链的坑」两处补充：
  ① 推翻 v1.6.0"Bash 失效就整轮换路径"—— 显式 `export PATH=` 指向 PortableGit 即可完全恢复，并固化三条配套铁律（shell 用 `/c/`、`cd` 偶发失败改绝对路径、`python.exe` 入参用 `C:/`）。
  ② 新增「Read/Write/Glob 对含 `()` 路径偶发失败」（Write EPERM 截断、Read/Glob 假报不存在），给出三条替代通道。来源：2026-09-15 回复标记更名 `[X]`→`[A]` 任务。
- v1.6.5 (2026-09-15) `get-login-qrcode` 的 `captureScreenshot` 超时 ≠ 故障（扫码成功后页面跳 `/new/home`，二维码 rect 失效）。来源：用户扫码后误判为截图失败。
- v1.6.4 (2026-09-14) ① Chrome 与启动它的 python 进程同生共死（`chrome_launcher.py` 退出后 9222 约 6 秒内被回收），需另起保活进程；② 代理典型症状是 502 非超时（`http.client.HTTPConnection` 默认不走代理）。
- v1.0.0 (2026-09-04) 初版，从主 SKILL.md 抽出。
- v1.1.0 (2026-09-04) 物理迁移到 patch；与 publish-interval-guard 通过 `XHS_INTERVAL_GUARD` 解耦。
- v1.2.0 (2026-09-11) 间隔等待 max-block 700→900、子进程超时 800→1000 秒，适配 8~12 分钟随机上界 720 秒。
- v1.3.0 (2026-09-11) 新增「本机进程排查的坑」（venv 父子双进程、`wmic` 不可用、PowerShell stdout 落盘）。
- v1.4.0 (2026-09-11) 修正探活结论（裸 socket 会假超时，改用 CDP HTTP 端点）；Chrome 因 profile 占用 `code=0` 秒退不是错误；补「每篇发布前探活」「含 `( )` 路径 cd 偶发失败」。
- v1.5.0 (2026-09-11) 新增「对外网络可达性：TLS 握手才算数」与 `helpers/net_probe.py`。
- v1.6.3 (2026-09-14) 新增「本机工具链的坑」（同文件并行 Edit 静默丢失、Bash 整段失效唯一可靠路径）。
- v1.6.2 (2026-09-14) 登录成功哨兵串：判据是 stdout 的 `[cdp_publish] Login confirmed.`（不输出 JSON、退出码不区分）。
- v1.6.1 (2026-09-12) 长批次禁用 `nohup &` 后台（进程组被回收、日志停半路），改用 `run_in_background`；确立中断后先用 `list_all_notes.py --days 1` 确认再重跑。
- v1.6.0 (2026-09-12) 新增「登录态与风控（规则索引）」，确立「先排除我方问题，再怀疑平台」判断顺序；补 `keep-open` 模式文档。
