---
name: publish-interval-guard
system: publish
version: 1.6.1
description: "连续发布间隔随机下限控制，reserve/release 抢占发布资格以堵并发重复发布，verify-note 判据与发布日志环形缓冲口径。触发词：发布间隔、能否发下一篇、reserve、间隔记录。"
patch_for: red-book-skills
applies_to_main_version: ">=0.1.0"
priority: 20
author: Project maintainers
created: 2026-09-04
---

# publish-interval-guard

> **范围**：所有同一账号的 publish 流程。连续发布目标间隔为 **360–840 秒（6–14 分钟，随机）**，
> 只在 `verify-note` 返回 `found:true` 后记账。
>
> ⚠️ 沿革（均为用户拍板）：10-09 由 480–720 放宽 → 660–1920；10-20 上界 1920 → 1320；
> 10-22 收 660–1320 → 480–1080（8–18 分钟）；**10-31 再收 → 360–840（6–14 分钟）**，
> 目的是把整链压进 **06:00 硬收口**（单篇均耗 14.5 min = 间隔均值 10 + 执行 4.5）。
> **任何调用方传的 `--max-block` 必须 ≥ 840**（默认 2400，无需下调），
> 否则抽到长间隔时 `reserve`/`wait` 会在抽签值之前就返回「间隔未满足」，表现为发布莫名失败。
>
> 专题 key（A/B/C）可在区间下沿再收窄到 **360–600 秒**，由调用方按 key 决定，守卫本身不区分。
> ⚠️ 下限 360 秒已接近平台风控观察线；若连续出现 461/限流，**优先减量而非再压间隔**。

## 唯一执行流程

1. 发布前调用 `reserve`；它在同一把内核文件锁内完成查重、间隔判定和 pending 占位。
2. 获得资格后执行 publish；未获得资格不得启动发布。
3. 调用 `verify-note`，只接受 JSON 的 `found:true`，不得用日志中的 `SUCCESS` 字样判断。
4. 成功后调用 `record --reserve-id <rid>` 升级占位；失败或异常调用 `release --reserve-id <rid>`。
5. 只有发布链使用 `publish_pipeline.py` 时，才可依赖其 atexit 释放；其他路径必须自行释放。

`check` 和 `wait` 只读，不能代替 `reserve`。任何不经过 `publish_pipeline.py` 的发布路径也必须
自行调用 `reserve`，否则会重新引入 TOCTOU 并发重复发布。

## 间隔与状态

- 🔴 **台账与锁不在 skill 树内**（2026-11-06 用户裁定）：默认落在
  `<workspace>/.state/publish/`（`XHS_WORKSPACE` 缺省 `C:/xhs`），
  即 `publish_log.json` 与 `.guard.lock`。路径权威是 `<patches>/tools/runtime_paths.py`。
  理由：全量替换包会连 state 一起覆盖，台账留在树内＝升级即丢历史、判重从 0 开始。
  覆盖方式：`XHS_STATE_ROOT`（整棵状态根）或 `XHS_INTERVAL_STATE_DIR`（本 patch 单独重定向）。
- 目标间隔在 `record` 时抽取并写入 `next_gap`；`check`/`wait` 不重新抽签。
- `record` 仅在审核确认后写入；失败发布不计入间隔。
- `publish_log.json` 只保留最近 100 条，不能用条目数统计当日发布量。
- `record` 按 `note_id` 幂等；同一 note_id 重复调用不得新增记录。
- 🔴 **`.guard.lock` 是常驻文件，不是"残留锁"**（2026-09-26 曾据此误判并手工删过一次）：
  锁由内核按文件句柄管理、**关句柄/进程崩溃即自动释放**，所以**文件存在 ≠ 被占用**，
  里面的 `pid` 只是最后一次持有者、仅供超时报错排查。**看到它停在旧 pid 上属正常，不要删**。
- **真正会拦住后续发布的是未过期的 pending 占位**（在 `publish_log.json` 里），
  由 `--pending-ttl`（默认 1800 秒）自动回收；确需手动释放才 `release --reserve-id <rid>`。
  ⚠️ `release` 不带或带错 `--reserve-id`（如 `auto`）时会打印"未找到对应占位"，**这是正常结果**，
  它不会"另写一把锁"，也不会影响后续 `reserve`。

## 命令

```bash
python helpers/publish_interval.py reserve --title "标题" --json
python helpers/publish_interval.py record --note-id <id> --title "标题" --reserve-id <rid>
python helpers/publish_interval.py release --reserve-id <rid>
python helpers/publish_interval.py check --json
python helpers/publish_interval.py wait --max-block 2400
```

退出码：`0` 成功；`1` 间隔未满足/等待超时；`2` 参数错误；`3` 同标题；
`4` 锁超时或守卫缺失。`--allow-same-title` 只放行查重，不放行间隔。

## 展开阅读

| 场景 | 读哪个文件 |
| --- | --- |
| 锁实现、TOCTOU 事故、verify-note 输出、旧脚本双 record | `refs/01-detail.md` |
