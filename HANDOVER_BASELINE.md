# 交接基线（机器可核对）
> 生成：由 `tools/gen_handover_baseline.py` 自动产出｜root 1.3.7
> 用途：`HANDOVER.md` 的**可核对副本**。全量替换后按本页逐行比对，任何一行不符即停并回滚。
> 纪律：改完任何受管文件必须 `python tools/gen_handover_baseline.py` 重跑本页，否则记录与实物脱钩。

## 一、覆盖层受管文件（全量包必须原样携带，hash 必须一致）

| 文件 | sha256（前 16 位） |
| --- | --- |
| `INSTRUCTIONS.md` | `75694350ecda19c1` |
| `references/01-publish-flow.md` | `f819e33533020c8c` |
| `references/03-constraints.md` | `eb4e3d6f740e510a` |
| `references/04-pitfalls.md` | `e4b80502595f2529` |
| `references/05-patches-upstream.md` | `a0ee0efe7b630268` |
| `scripts/cdp_publish.py` | `712946f5010d0f7e` |
| `scripts/chrome_launcher.py` | `b6846788b7eeb6d9` |
| `scripts/publish_pipeline.py` | `ca3e7e3fe1acb0a4` |
| `scripts/run_lock.py` | `f49e32fb898d6922` |

> 共 9 个文件。

## 二、版本（不得回退）

| 组件 | 版本 | 优先级 |
| --- | --- | --- |
| root `SKILL.md` | 1.3.7 | — |
| `core-overrides` | 1.5.4 | 2 |
| `update-checker` | 1.5.0 | 5 |
| `windows-sandbox-workaround` | 1.7.0 | 10 |
| `comment-reply-guard` | 1.24.1 | 11 |
| `xhs-risk-guard` | 1.3.0 | 12 |
| `safe-wording-guard` | 0.8.0 | 15 |
| `publish-interval-guard` | 1.6.1 | 20 |
| `timeliness-window` | 1.9.1 | 22 |
| `organizer-qualification-guard` | 1.3.0 | 23 |
| `publish-preflight-guard` | 1.20.0 | 25 |
| `publish-loop-guard` | 1.13.3 | 28 |
| `writing-facts-only` | 1.6.2 | 30 |
| `cover-image-rules` | 1.8.3 | 50 |
| `daily-closeout-guard` | 1.4.1 | 60 |

## 三、规则知识库 `topics/`（不得少于下列字符数）

| 文件 | 字符数 |
| --- | --- |
| `00-rules-detail.md` | 5997 |
| `01-architecture.md` | 3888 |
| `02-timeliness.md` | 1715 |
| `03-publish-rhythm.md` | 9644 |
| `04-content-redlines.md` | 6048 |
| `05-covers.md` | 8291 |
| `06-pitfalls.md` | 8817 |
| `07-platform.md` | 6802 |
| `08-weather.md` | 5246 |
| `09-cleanup.md` | 3201 |
| `10-legacy-xhs.md` | 4839 |
| `11-ops-playbook.md` | 8813 |
| `12-tab-rules.md` | 3609 |
| `13-deadline.md` | 2528 |
| `14-group-rules.md` | 1720 |
| `QUICKREF.md` | 4257 |
| **合计** | **85415** |

## 四、结构性判据

- `core-overrides/META.json`：`files` = 15、`overrides.targets` = 9
- `topics/`：正文篇数 = 16（含 `QUICKREF.md`）
- `HANDOVER.md` 三锚点：`全量替换包`、`本地定制清单`、`升级记录表`
- 敏感值：`topics/` 内不得出现真实端口字面量 9333 / 9222（须为 `<PORT_PUBLISH>` / `<PORT_COMMENT>`）
