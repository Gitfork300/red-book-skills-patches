# 05 · Patch 索引、触发词与上游更新

> read_when: 需要了解某个 patch 细节、处理「启动」触发词、决策是否合并上游更新时
> 本文件是 `SKILL.md` 的展开。**铁律与顺序以 SKILL.md 为准**。
>
> **source: patch** —— 全部是我们自己的内容，上游更新不影响本文件。

## Patch 索引

所有 patch 的索引、加载顺序、状态文件位置见 `../../INDEX.md`。

## 触发词：用户说「启动」

用户单独说 **「启动」**（或「启动发布」「按流程启动」）时，不必再等补充指令，直接：

1. **自动检索**近期展会 / AI 活动 / 政策类选题（沿用既定领域与口径）
2. 逐条过第 2 步「地域范围 / 时效窗口 / 可发布资格 / 选题配额」闸门，
   不合格的进待发池，**不写稿**
3. **按事件查重**（`publish-loop-guard/helpers/dup_check.py --title "..."`，退出码 0 才继续）
4. 合格选题 → 写稿 → 用词字数预检 → 生成封面（真实感、无人物/二维码/人形机器人/地图）→ 17 项总检查
5. 写入 `inflight.json`，起 `watch_missing.py` 看门狗
6. 按 **8~12 分钟随机间隔**逐篇发布，每篇 `verify-note` 通过才计间隔
7. 逐篇回报 `note_id`，全部结束后清空 `inflight.json` 并报总表

完整规则见 patch：`../../publish-loop-guard/SKILL.md`

## 上游更新检查（patch: `update-checker`）

可信参考 Fork `Gitfork300/xiaohongshu-skills-A2` 会更新。A2 与当前 Windows 兼容运行层架构不同，
更新仅用于评估和择优移植；不可整仓替换，也不可将 A2 文件直接覆盖到不同接口的本地脚本。

- 默认每周检查一次（可由 patch 的 `set-interval` 调整）
- 自动化是否启用由本机调度器管理，不是 skill 运行依赖。
- 检测到更新后**由用户/agent 决策是否合并，不自动修改文件**
- 状态文件位置：`update-checker/state/update_state.json`

```bash
<update-checker>/helpers/update_check.py status                      # 状态查询
<update-checker>/helpers/update_check.py check-now                   # 强制立即检查
<update-checker>/helpers/update_check.py acknowledge --sha <sha>     # 标记某 commit 已读
```

检测到更新后如何处理：见 `../../update-checker/SKILL.md` 的「配合使用」一节。

## 文档分层维护

本 SKILL.md 与 `references/*.md` 属于分层文档，规范见
`../../DOC_LAYOUT.md`。

改动后跑校验：

```bash
python ../../tools/check_doc_layers.py
```

校验项：字数/行数上限、索引断链、孤儿文件、**关键锚点是否丢失**。

> ⚠️ 本目录是 `core-overrides` 的覆盖层。改完必须
> `apply_overrides.py apply` 才会同步到 bundled runtime `runtime/`。
