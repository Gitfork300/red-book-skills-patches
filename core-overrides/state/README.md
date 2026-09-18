# 本地运行状态目录

本目录只在本机保存 `apply_overrides.py` 的运行状态和备份。

- 公开仓库只保留本说明和 `.gitkeep`。
- `applied.json`、锁文件和 `backup/<时间戳>/` 只在本机生成，禁止提交。
- 新电脑 clone 后直接运行 `helpers/apply_overrides.py status` 或 `apply`，脚本会自动补齐状态目录。
