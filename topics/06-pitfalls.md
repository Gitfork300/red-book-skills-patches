# 06 · 已知坑（踩过的雷全集）

> read_when: 排查发布失败 / 脚本异常 / 环境问题时，先看这里有没有同类
> 本文件是 `MEMORY.md` 第 6 节的展开。**结论以主文件为准**。

## 发布与查重

- **查重必须双源**：`dup_check.py` 同时读
  1. `<workspace>/.state/publish/publish_log.json`（**11-06 起**；旧址 `publish-interval-guard/state/` 已迁出，只剩 `.migrated-20261106`）
  2. `xhs_publish/logs/*platform_notes*.json`（平台快照，无日期条目标 `always=True`）

  只比日志会漏（**实测漏过 2 条**）。**预检必须在发布前做**。

- **自建 `_publish_chain_*.py` 的 `check_one` 必须齐**：
  dup_check + 用词 + 字宽 + 地域 + 主办资质 + 时效；评级块已废除，不再作为闸门
  - 模板：`_publish_chain_s0914.py`
  - 事故：漏 dup_check → 已发过的峰会再次排队并误发

## 长批次

- **长批次后台会被回收**：`nohup &` 与 `run_in_background` 均实测被回收，
  重定向 stdout 因缓冲全丢
- 对策：`python -u` 实时落盘
- 中断后**先双查**最后一篇（日志 + 平台侧 `recent_published.py` 近 10 条），
  再 `--from-key <key>` 续跑
  - `verify-note` 此场景**假阴性**
- ⚠️ **`list_all_notes.py` 的全量不是全量**（2026-10-05 实测）：滚动上限约 **210 条**，
  而平台计数 **676** → **不能**拿它判「某篇还在不在」（会同时产生误判与漏判）。
  判断「某篇是否仍在平台」的正确三步：
  ① `recent_published.py`（近 10 条快查）；
  ② 创作者「笔记管理」页 **tab 计数**（全部 / 已发布 / 审核中 / 未通过）+ 逐个点开；
  ③ **页内搜索框**（`搜索已发布的笔记`）按关键词查。
- ⚠️ **`/explore/<note_id>` 不带 `xsec_token` 打开必然 404**（error_code=300031），
  **与笔记是否在线无关** —— 2026-10-05 用已知在线的 `d1005_05` 做了对照，同样 404。
  别拿「explore 页 404」当作「已被下架」的证据。

## 登录态

- **`check-login` 判据 = stdout `[cdp_publish] Login confirmed.`**
  - 无 JSON、退出码不区分
  - 正确调用：`python scripts/cdp_publish.py check-login`
  - **不存在** `check_login.py`
- 查真登录态先删 `tmp/login_status_cache.json`（TTL 12h 会返旧结论）
- **「找不到上传图文 tab / 页面结构变了」多为假警报** ——
  常伴 CDP `no close frame received or sent` 出现。
  先跑 check-login 排除，再决定是否停队列

## 工程习惯

- 同文件**不要并行 Edit**（后写覆盖前写且**静默失败**）；改完 grep 确认落地
- 按显示坐标裁图会裁错（Read 是缩放版，比例 1.4222），按实际分辨率换算
- 预检脚本**不要无条件跑按题材的闸门**（天气配额对非天气批次误报）
- `git status` 不要整体 `.strip()`（吃掉 ` M` 前导空格），用 `repr()`
- `curl -sL -o` 会**静默失败留空文件** → 校验非空，优先 Python `urllib`
- 内容对比**忽略行尾差异**（CRLF vs LF）

## 环境（Windows / bash）

- bash 环境多次异常（`dirname` / `head` 等基础命令 not found）
- **bash 全线不可用时唯一可靠路径：绝对路径直调 managed python**
  ```
  C:/Users/<u>/.workbuddy/binaries/python/versions/3.13.12/python.exe script.py
  ```
  - ⚠️ **2026-09-16 更正**：`export PATH=.../PortableGit/versions/<ver>/usr/bin:.../bin:$PATH` **实测无效**
    —— export 之后 `ls/cat/tail/grep` 仍 `command not found`。
  - 替代通道：**绝对路径调 PortableGit 的 exe ＋ stdout 落盘**
    （`"$G/ls.exe" ... > 输出文件`，再用 Read/Grep 工具读；**绝对路径调用的 stdout 不回传**）。
    `tasklist` 等 Windows 原生 exe 例外，stdout 可直接读。
  - PortableGit 真实位置：`~/.workbuddy/binaries/PortableGit/versions/<ver>/usr/bin`
    （**不是** `AppData/Local/Programs/PortableGit`，后者不存在）。
  - 文件读写走 Read / Write / Grep / Glob
  - **PowerShell 工具的 stdout 也不回传**
- 控制台输出中文时加 `sys.stdout.reconfigure(encoding="utf-8", errors="replace")`

## 重复发布事故：补发链续跑 + 系列豁免放行同名（2026-09-16）
- 现象：b3「[SS] 数据要素专场 缺数据下单」平台上两条（09:20 原发 / 10:03 重复）。
- 成因1：--from-key b2 语义是从 b2 跑到结尾，把已发 b3 重跑。改：默认只跑指定 key，续跑须 --continue。
- 成因2：dup_check --series 系列豁免把「标题完全相同」也豁免；而完全相同判据只比 drafts（待发稿），
  不比 entries（已发），导致已发同名篇一路放行。改：豁免仅放宽公共子串，norm(title) 相等仍判重复。
- 新增铁律：发布前先查 state/near_dup_tags.json，同标题已记录即 SKIP（台账是最硬的「已发过」证据）。
- 脚本无删除笔记能力，重复笔记只能 App 手动删。

## 换标题重发同一活动：前两道信号都能绕过（2026-09-16 深夜）

Canary 第二轮 c6/c7 **两篇预检都 PASS**，与已发稿是同一活动：

- c6 `[Canary] 香港医疗AI论坛922 报名` 撞 **9/15 已发** `香港具身智能医疗论坛 9月22`（同场 CREATE Symposium）
- c7 `[Canary] ASSIST2026 报名与议程` 撞**当日 12:53 已发** `[S] 上科大AI研讨会918开幕`（正文首段**逐字相同**）

> ⚠️ **口径已修正（2026-09-17 用户定稿）**：`[Canary]` 是实验性标记，**不在「不得重复」范围**，
> 「同一活动换标题重发」**不算违规、不追责、不下架**。下文「取消 Canary 豁免」的结论已作废。
> 现口径：Canary 稿**豁免查重**、允许复用同一活动，唯一底线是「标题逐字不相同」。

**为什么当时会漏**：① 事件标识要求专名**完全相等**（「香港医疗AI论坛」≠「香港具身智能医疗论坛」）；
② 公共子串阈值 5 字，而 `identity()` 剥掉日期后只剩「医疗」「论坛」各 2 字；
③ 我还传了 `--series Canary2026` 走豁免。⚠️ 该豁免源自用户原话「**不受限制，允许发挥**」，**确实存在**。

**第三道信号「地点 + 日期」仍保留，但对 Canary 稿豁免**（`publish-loop-guard` 1.8.0 / INDEX v1.8.23）：
- 同城 + 同会期（`922`/`9月22`/`9-22` 归一为 `0922`），剥掉**地名/日期/事件后缀/通用词**后仍有 ≥2 字公共词 → 判重复；只挂单条预检。
- 系列稿（`--series`）不豁免本信号；**`[Canary]` 稿豁免**（只查标题逐字）。
- 行业类窗口 **3→7 天**（回归用户原话「行业级 7 天内不重复」，实现曾少写 4 天）。

**盲区（待办 34）**：标题既无会期又无城市时第三道信号无效（`ASSIST2026` 正是此例）→
根治需台账记录**正文首句**，同活动的稿子首句必然高度相似。

**教训（仅适用于非 Canary 常规稿）**：「换个说法」不是新选题。当一篇稿的活动 / 日期 / 地点与已发篇全部重合时，
它就是重复 —— 改标题只会让闸门失效、让平台多一条重复内容。**Canary 稿不在此列**。

## 保活档退出 ≠ 必然回收 Chrome；看「持有者是否归零」（2026-09-16 双实例）
- 现象：发布链进程还在跑，但 `chrome.exe` 从 tasklist 归零、<PORT_COMMENT> 拒连 → 看着像"发布器故障"，实为**持有者归零**。
- **真因（15:00 修正）**：Chrome 是**引用计数式**存活 —— `ensure_chrome()` 拉起的 Chrome 随**持有它的档**回收，
  但**只要还有另一个 `_chrome_hold*.py` 活着持有，就带不走 Chrome**。
  - 12:43 **出事**：唯一持有者（60 分钟档）退出 → Chrome 归零、<PORT_COMMENT> 断。
  - 15:00 **无事**：180 分钟档退出，但 XL（13:33 起）与 XL2（12:48 起）都活着 → **CDP 仍 200 / chrome.exe 36 个**。
- **判活前置**：先 `ls logs/_chrome_hold*.log` 数有几个 mtime 在最近 1 分钟内 → ≥1 则退档无风险；0 则立刻补档。
  再按序：① 日志末行 → ② `tasklist /FI "IMAGENAME eq chrome.exe" /NH`（正常 30–40 个）→ ③ 才到 <PORT_COMMENT>。
- 补拉有**约 30 秒空窗**（别的档要等下一个 tick 才探测到 <PORT_COMMENT> DOWN 再补拉）。
- 本机保活档族（逻辑相同，只有 `range()` 不同，每 tick 30 秒）：
  `_chrome_hold.py`=120 次/60 min、`_chrome_hold_long.py`=360/180 min、`_chrome_hold_xl.py`=600/300 min。
- **铁律（两条）**：① 总时长 > 60 分钟的批次，开跑前就起 300 分钟档，不许用 60 分钟档「接力」（接力点必有空窗）；
  ② 单档最长 300 分钟，**超长任务同时挂 2 档、起始时间错开**，覆盖区间重叠 → 任一档到期都不归零。
- 探 <PORT_COMMENT> **必须用 `http.client.HTTPConnection`**；`urllib.request` **走系统代理返 502**（假信号，与死活无关）。
- Chrome 重启后**登录态仍在**（profile 落盘）；标签变 `chrome://newtab/` 属正常。
  验登录先删 `tmp/login_status_cache.json`（TTL 12h），再用 `cdp_publish.py --reuse-existing-tab check-login`。
- ⚠️ `cdp_publish.py` 的 `--reuse-existing-tab`/`--account`/`--port` 是**全局参数，必须写在子命令之前**，
  写后面报 `unrecognized arguments`。


## 🚫 正文里的 `#XX` 不会变成话题 —— 必须走编辑器实体（B-034，2026-10-09）

- **现象**：末尾写了 `#量子计算 #IBM #量子纠错`，发布后是可点的蓝色话题？**不是**，是普通黑字。
- **根因**：runtime `_fill_content()` 是 DOM 直塞 —— 每行包成 `<p>` 塞进 `div.tiptap.ProseMirror`。
  ProseMirror 只在**真实输入 `#` → 拉起推荐面板 → 选中词条**这条路径上建 topic 节点
  （DOM 标志：`<a class="tiptap-topic">#XX[话题]#</a>`）。DOM 直塞 / 整段粘贴一律不解析。
  全仓此前**没有任何话题处理代码**，所以不是格式写错，是根本没做。
- **修法**（不改 runtime，走 patch）：
  1. 把 `_content.txt` 拆成 body（剥离标签行）+ topics 两路输入；
  2. `cdp_publish.py fill --title … --content-file <body> --images …`（`fill` 本就不发布）；
  3. `_attach_topics.py` 逐个 `Input.insertText("#")` + 关键词 + Enter，让编辑器自己生成节点；
  4. `cdp_publish.py click-publish` 提交。
  已封装 `_publish_with_topics.py`（含 prewarm、间隔守卫 reserve/record、23:50 窗口动态收敛）。
- **验收**：不看「sent / rc=0」，看 DOM 里有没有 `a.tiptap-topic`（09 三标签、10 四标签均已验证）。
- ⚠️ 遗留：`_chain_*.py` 还是一次性 `publish`，发出来**没有真话题** → 下次开工先迁移。

## 🚫 回复脚本报 `sent` ≠ 平台收到 —— Vue 不吃合成 click（B-032，2026-10-09）

- **现象**：`_inbox_reply.py` 回执 sent、复读文本也对，但在页面上**找不到这条回复**。
- **根因**：小红书前端是 Vue，JS 合成的 `element.click()` 被忽略 → 假成功。
- **修法**：CDP 真实鼠标事件 + `Input.insertText`，并监听 `comment/post` 接口回执验收
  （`_reply_realclick_1009.py`）。**以接口回执为准，不以 sent 为准**（与铁律 19 同理）。
- 另：`_mentions_pages.py` / `_dm_scan_0929.py` 硬编码 **<PORT_PUBLISH>**（发布实例），巡检会撞发布链；
  已出 <PORT_COMMENT> 版 `_mentions_<PORT_COMMENT>.py`，私信脚本待改造（B-033）。

## 🚫 发布实例 <PORT_PUBLISH> 反复在「上传完成等待」崩溃（B-035，2026-10-09）

- **现象**：`fill` 卡在 `_wait_for_uploaded_images → _count_uploaded_images` 的 `Runtime.evaluate`
  （45s 超时），随后 Chrome 整机失联、<PORT_PUBLISH> 拒连。一晚崩 3 次。
- **规律**：都发生在「已跑过一轮之后再起」且 **<PORT_COMMENT> 评论实例并行**时；
  关掉 <PORT_COMMENT>、单实例前台重跑即一次通过。
- **处置**：① 先 `--kill <PORT_COMMENT>`；② `--restart <PORT_PUBLISH>`；③ 前台跑（不要 nohup 后台）；
  ④ 卡住时记得 `guard release <reserve-id>` 清占位，否则阻塞下一轮。
- 若再崩 → 考虑重建 profile（**需重新扫码**，先跟用户说）。

## 防复发清单（2026-10-12 事故沉淀，见 `xhs_publish/_REVIEW_1012.md`）

**改链脚本 / 加参数时：**
1. 数值、时间、开关类参数必须走 `_val()`；`_arg()` 只用于**路径**（会把 "660" 拼成 `<DIR>/660`）。
   症状：guard 报参数错误 → 链的 `re.search(r"\{.*\}")` 抓到 argparse usage 的 `{check,wait,…}` →
   全批 `RESERVE_JSON_ERR` 跳过（**不会误发，但会静默不发**）。
2. 改完必须 `python -m py_compile`，并用假 `sys.argv` 打印解析结果验证（不要只看编译通过）。
3. 新加的命令行参数要同步进 `_watchdog_*.py` 的重拉命令，否则看门狗重拉出的是「旧参数链」。

**收口 / 硬停：**
4. `--stop-after` 只在 `wait_window` 判**不够**——`reserve` 会阻塞等待间隔并跨越停止时间。
   必须双保险：链内「拿到 reserve 资格后复判 → release + 停链」+ 链外 stopper 强杀。
5. stopper 杀链后**必须撤销 pending 占位**（`guard release --reserve-id`），
   否则该标题被占 30min（pending-ttl），次日链判「同标题已占位」直接跳过 → **白丢一篇**。

**判进程死活：**
6. 判链死 = **三重确认**（心跳 >45min + 锁 pid 不存在 + 日志 >50min 无增长），任一条不满足就判活。
   轻率判活会漏拉；轻率判死会拉出**双链抢 guard 锁**（B-040 事故）。
6b. **`_chain_1010.py::acquire_lock()` 已于 10-13 加 pid 存活校验**（`_pid_alive()`：tasklist + 要求含 python，
   防 pid 复用；`_hb_age()`：.hb mtime）。判据：pid 活→abort；pid 死 + hb>45min 或锁 age>6h→**自动接管**；
   pid 死但 hb 新鲜→abort 交 watchdog。修之前死链会挡新链 ~50min（B-041），修后链可自愈。
   接力拉链时仍建议先删 `.lock`/`.hb`。
6c. **<PORT_PUBLISH> 新症状（B-043）**：端口监听正常、但页面层 `chrome-error://chromewebdata/`、找不到「上传图文」tab
   → prewarm 失败 → GIVEUP，连续 3 篇会熔断停链。待加规则：**连续 GIVEUP ≥2 就重建实例**（watchdog 现在只查端口，查不出这种）。
7. 本机**非交互后台进程约 90 分钟被回收**（链、Chrome 都中招，比铁律 26 的 3h 更短）→
   长任务必须有 watchdog；watchdog 自身也可能被回收，重要场合加平台级定时兜底。

**Chrome 调试实例（B-039，未解决）：**
8. 现象是 **CDP 端口掉线**（进程仍在、端口不监听），不是进程被杀。
   <PORT_PUBLISH>「看起来稳定」只是 watchdog 在重建。**评论实例要现启现用 + 挂保活**，不要指望常驻。
9. 已证伪：profile 损坏、headless、shell job object、双实例冲突、SingletonLock 残留。
