---
name: xhs-risk-guard
system: shared
version: 1.3.0
patch_for: red-book-skills
applies_to_main_version: ">=0.1.0"
priority: 12
author: Eric (定制)
created: 2026-09-12
---

# xhs-risk-guard

> Patch：**小红书风控规则的单一权威来源 + 可执行限流守卫**。
> 把实测撞出来的风控边界集中一处，并让脚本自己守规矩——规则不再只是"已知坑"里的一段话，而是会被强制执行。

## 风控规则总表（照表格执行，不做临场发挥）

### A. 读取域（公开页读正文）

| # | 现象 | 真因 | 允许 | 禁止 |
| --- | --- | --- | --- | --- |
| A1 | 连续读约 30 篇公开页后请求一律重定向登录页 | 读取限流，非登录失效 | 单次会话 ≤25 篇；批间隔数小时（冷却 4h） | 撞额度后连续重试 |
| A2 | 连续 `ok=false` | 已触限流 | 连续 3 次自动熔断、标 `skipped`、当场停手 | 把剩余硬跑完 |
| A3 | 裸链 `explore/<id>` 撞登录墙 | 缺 `xsec_token` | 必须带 `?xsec_token=<tok>&xsec_source=pc_user` | 拿裸链猜 |
| A4 | 想一次读完 54 篇 | — | 先 `list_all_notes.py --wording` 零成本扫标题，只读可疑篇目 | 全量读正文 |

### B. 登录域

| # | 现象 | 真因 | 允许 | 禁止 |
| --- | --- | --- | --- | --- |
| B1 | `check-login` 报已登录但接口 401 | 命中 `tmp/login_status_cache.json`（TTL 12h） | 先删缓存再验 | 拿缓存结论当证据 |
| B2 | 落地 URL 变 `…/login?redirectReason=401` | 会话失效 | 重新扫码 | 误判"页面结构变了/功能下线" |
| B3 | 担心每次要扫码 | 登录态会落盘 profile | 扫一次即可，重启 Chrome 仍有效 | 每次重新扫 |
| B4 | 扫码窗口一闪而过 | 宿主回收 Chrome | 同一次调用完成；`keep-open` 留时间 | 分两次调用 |

### C. 平台接口域

| # | 现象 | 真因 | 允许 | 禁止 |
| --- | --- | --- | --- | --- |
| C1 | 页面内 `fetch` 列表接口 406 | 需页面自生成签名头 | 驱动滚动、从 CDP 响应收；复用 `XiaohongshuPublisher` | 页面里直调接口 |
| C2 | 切页签但请求没重发 | 页签是本地过滤 | 只读 `tab=0`，状态看 `tab_status`（1 已发布/0,2 审核中/3,-1 未通过） | 以为切页签能拿不同数据 |
| C3 | 例行复核翻页慢且没结论 | 翻页拉长耗时放大风控 | 只读第一页（最新 10 条） | 为"查全"翻第 5 页 |
| C4 | 列表页首次导航偶发 406 | 页面在完成动态握手 | 重试 2–3 次 | 第一次 406 就判失败 |

### D. 「假风控」清单（看着像被平台拦，其实是我们自己写错）

**这类最坑，历史上两次误判都源于此。** 在把问题归因为"风控"前，先排除 D1/D2/D3。

| # | 现象 | 真因（我方问题） | 正确做法 |
| --- | --- | --- | --- |
| D1 | 页面渲染正常但接口没发请求（网络事件 0） | `Network.enable` 参数写成 `maxPostSize`，正确名 `maxPostDataSize` | 别自搓 CDP，复用 `XiaohongshuPublisher` |
| D2 | `上传图文 tab` 报"页面结构可能变了" | 443 TLS 握手被整段丢弃（网络问题） | 发布前跑 `net_probe.py` 探 TLS |
| D3 | 裸 socket 探 9222 超时，以为 Chrome 没起 | loopback 裸连在正常服务时也超时 | 用 CDP HTTP 端点探活 |
| D4 | `tasklist` 无 chrome.exe，以为浏览器挂了 | 本沙箱 tasklist 可能返 0 条而 Chrome 在服务 | 以 CDP 探针为准 |
| D5 | venv python 进程"出现两次"，以为两个队列 | Windows 父子双进程、命令行相同 | 读 `_xhs_publish.lock` pid 认持有者 |

### E. 发布域

| # | 规则 | 归属 |
| --- | --- | --- |
| E1 | 连续发布间隔 8~12 分钟随机（下限 8），计时起点 verify-note 通过后 | `publish-interval-guard` |
| E2 | 长队列每篇发布前探活 Chrome，别只在开头探一次 | `windows-sandbox-workaround` |
| E3 | 标题 20 上限按字宽计（汉字/全角=1，英文数字半角每 2 计 1） | `safe-wording-guard` |
| E4 | 正文一律不出现网址或裸域名 | `safe-wording-guard` |
| E5 | 网络不可达不空转重试（烧间隔配额），恢复后按漏发复核补发 | `windows-sandbox-workaround` |
| E6 | 不写「单一商业品牌专场」稿：品牌名 ≥4 次 或「展位号+品牌直播」→ 判商业推广 | `xhs-risk-guard` |

E6 判定：任一即高危（品牌名≥4 次 / 展位号 / 品牌自有直播频道）。`check_wording` 判不出（是内容形态不是词问题）→ 选题阶段拦。合规写法：品牌降为举例之一、删展位号与品牌直播、品牌名 ≤2 次。

### F. 互动域（评论/私信）

🔴 平台提示禁止批量自动回复 → 先降量拉间隔，按 D 段先排除我方问题（前缀遗漏/重复回复/模板雷同）再怀疑平台。

| # | 规则 | 归属 |
| --- | --- | --- |
| F1 | 每条回复必须以标记开头：`[A1]` 评论 / `[A2]` 私信 / `[A9]` 其他 / `[E1]` 异常；格式 = 标记 + 半角空格 + 正文 | `comment-reply-guard` |
| F2 | 控量：评论 35 秒/条、单轮 ≤20；私信 20 秒/条、单轮 ≤20 | `comment-reply-guard` |
| F3 | 广告/纯表情/纯 @ 不回；官方机器人推广与对方广告不问不回 | `comment-reply-guard` |
| F4 | 已回复判定以我方昵称 `叻叻财` 为准，不能只认前缀 | `comment-reply-guard` |

## 可执行守卫（`helpers/risk_state.py`）

```bash
$PY $P/helpers/risk_state.py check --kind read-body    # 0 可跑 / 3 冷却中
$PY $P/helpers/risk_state.py status                    # 全域状态
$PY $P/helpers/risk_state.py record --kind read-body --ok 24 --fail 3 --stopped consecutive-fail
$PY $P/helpers/risk_state.py reset --kind read-body    # 慎用：只清本地记忆，不解除平台限流
```

| kind | 单次预算 | 冷却 | 连续失败熔断 | 适用 |
| --- | --- | --- | --- | --- |
| `read-body` | 25 篇 | 4 小时 | 3 次 | 公开页读正文 |
| `list-notes` | 不限 | — | — | 全量清单审计 |
| `publish` | 不限 | — | — | 发布（间隔另管） |

脚本侧已接线：`read_note_body.py` 启动查冷却 → 批次夹预算 → 连续失败熔断 → 结束落盘。

## 与其他 patch 关系

不改本体、不改其它 patch 规则，只集中登记；E1–E5 权威定义仍在各自 patch，本 patch 只提供索引与守卫。

## 已知坑

- 额度是观察值不是承诺（25/30 随时收紧），真被挡先看 `state/risk_state.json` 的 `stopped`。
- `reset` 慎用（只清本地记忆，不自欺）。
- 冷却期内换 kind 不算绕过（`read-body` 限流时跑 `list-notes` 安全），但换脚本接着读公开页不允许。
- 别把 D 类当风控（历史两次误判都出在这）。

## 展开阅读（命中场景才读）

| 场景 | 读哪个文件 |
| --- | --- |
| 建立背景（事故复盘）、E6/F 域详细判定、接入代码示例 | `refs/01-detail.md` |
| 版本修改记录（v1.0.0 ~ v1.3.0） | `refs/02-changelog.md` |
