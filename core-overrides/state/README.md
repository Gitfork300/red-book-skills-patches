# 本地运行状态目录

本目录只在本机保存 `apply_overrides.py` 的运行状态。

- 公开仓库只保留本说明和 `.gitkeep`。
- `applied.json`、锁文件只在本机生成，禁止提交。
- **apply 前的本体备份不在这里**（2026-10-07 起）：落在
  `~/xhs-workspace/_skill-backup/core-overrides-preapply/<时间戳>/`。
  移出 `skills/` 树的原因：技能扫描器会递归扫 `skills/**/SKILL.md` 并按
  frontmatter 的 `name` 注册，备份里的 SKILL.md 与本体同名会撞名，
  且备份是旧版 —— 同名时加载哪份不确定，有回退风险。
  可用环境变量 `RED_BOOK_OVERRIDES_BACKUP_DIR` 改位置。
- 新电脑 clone 后直接运行 `helpers/apply_overrides.py status` 或 `apply`，脚本会自动补齐状态目录。
