> read_when: 需要 publish-preflight-guard 的事故复盘、验收清单细节时
> 本文件是 `SKILL.md` 的展开，规则结论仍以 SKILL.md 为准（system: publish）。

# publish-preflight-guard / refs — 事故与验收清单

## 一、典型事故（为什么要有这个 patch）

5 篇批量发布，第 1 篇 23:56 发出后才发现三个问题：① 第 2/3/4 篇正文 1159/1134/1065 字，全超 1000 字上限；② 封面是简单几何抽象示意图，用户不满意；③ 活动类稿件没写"需邀约/登记/审核"，读者会白跑。后果：后 4 篇拦下重做，第 1 篇只能人工编辑补救。

2026-09-11 又暴露第二类问题：**时效合格 ≠ 该发**。前海智库院长论坛（9/12 深圳）时效合规但"不面向公众开放报名、无直播"，读者既去不了也看不了，仍 00:58 发出。此后新增第 3 项「可发布资格」闸门。

## 二、批量队列控制细节

1. 稿件在"发布那一刻"才被读取 → 改磁盘稿件对未发布篇章有效，改文件要趁那篇还在等间隔。
2. 发现问题可安全停队列（稿件尚未真正发布时结束进程安全）：

```powershell
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object { $_.CommandLine -like "*xhs_batch_publish*" } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
Get-Process chrome -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.Id -Force }
```

停下后：改稿件 → 改脚本 → 重新排队；已发的那篇单独人工处理，不要重发。

## 三、验收清单

- [ ] 19 项全过（第 2/3/4/14/15/16/17 项最容易忘）？
- [ ] 第 14 项走红/黑 3 篇额度时，`--level` 确实传了红/黑（不传按 1 篇拦）？
- [ ] 字数双闸门：核心正文（末个 `—` 之前）200–600 字、全篇 <1000 字；分段适配扫读？
- [ ] 自己写的发布链脚本预检里真的调了 `dup_check`？
- [ ] 队列启动写了 `inflight.json` 并挂 30 分钟漏发看门狗？结束清空了？
- [ ] 每张封面实际打开看过（不是只看"生成成功"返回）？封面路径与稿件一一对应？
