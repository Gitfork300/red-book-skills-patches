# 发布间隔本地状态

首次运行 `helpers/publish_interval.py` 时自动生成：

- `publish_log.json`：最近发布记录和下一次间隔
- `.guard.lock`：本机进程锁

这些文件包含本机业务运行数据，公开仓库只保留本说明和 `.gitkeep`。
新电脑 clone 后直接运行 `reserve` 或 `check` 即可初始化目录；没有历史记录时按“无记录”处理。
