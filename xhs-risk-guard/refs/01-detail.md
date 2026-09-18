> read_when: 需要 xhs-risk-guard 建立背景、E6/F 域详细判定、接入代码示例时
> 本文件是 `SKILL.md` 的展开，规则结论仍以 SKILL.md 为准（system: shared）。

# xhs-risk-guard / refs — 背景、判定细节与接入

## 一、为什么有这个 patch（背景）

风控规则此前散落在三处（`publish-loop-guard` 的已知坑、`windows-sandbox-workaround` 排查章、各 helper docstring），结果是"读得到但不一定照做"。

> 2026-09-12 实测：`read_note_body.py` 连续读公开页，1–27 篇读到 24 篇，第 28–54 篇 27 篇全被重定向到登录页。脚本当时无额度概念，硬撞 27 次无效请求才跑完——每次无效请求都在加重风控。更早（09-11）还因此误判过一次"读不到正文 = 桌面端没有入口"，真因是会话已失效。

所以本 patch 做两件事：规则集中（一处说清）+ 守卫固化（脚本自动停）。

## 二、E6 单一商业品牌专场判定（2026-09-15 实测）

触发特征（任一即高危，两条同时基本必挂）：
1. 全文围绕一家公司（品牌名 ≥4 次，含产品线名如「至强」）
2. 出现展位号（如「2-A10」）——等同招商信息
3. 出现品牌自有直播/频道（如「英特尔商用频道全程直播」）——等同导流

- 用词检查（`check_wording`）判不出来：这是内容形态问题，不是词问题 → 选题阶段拦。
- 合规写法：品牌降为举例之一，正文主体写「议题方向/技术主题/适合谁听」，删展位号与品牌直播，品牌名 ≤2 次。
- 已发且被判未通过：不要原样重发，改写后再发。

## 三、接入代码示例

```python
import sys, os
sys.path.insert(0, os.path.join(PATCHES_ROOT, "xhs-risk-guard", "helpers"))
import risk_state

ok, why = risk_state.can_start("read-body")
if not ok:
    print(why); sys.exit(3)

limit = min(user_limit or 999, risk_state.budget("read-body"))
# ……循环中……
if risk_state.should_stop("read-body", consecutive_fail):
    break
# ……结束……
risk_state.record("read-body", ok=ok_n, fail=fail_n, stopped=reason)
```

## 四、判据提醒

- D 类全部由"我方实现细节"造成，与账号/平台无关；归因"风控"前先排除 D1/D2/D3。
- F 段行号 `F*` 与标记 `[E1]` 不同域：`E1`~`E6` 是发布域行号，`[E1]` 是"异常事件回复"标记，别混。
