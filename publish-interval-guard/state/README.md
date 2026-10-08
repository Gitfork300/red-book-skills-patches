# 发布间隔本地状态

首次运行 `helpers/publish_interval.py` 时自动生成：

- `publish_log.json`：最近发布记录和下一次间隔
- `.guard.lock`：**内核咨询锁的承载文件（常驻，不要手工删）**
  - 锁由操作系统按文件句柄管理，**关句柄 / 进程崩溃即自动释放**，
    因此 **文件存在 ≠ 锁被占用**；里面的 `pid` 只是**最后一次持有者**，仅用于锁超时报错时排查。
  - 看到 `.guard.lock` 停在某个早已退出的 pid 上**是正常现象**，无需清理；
    手工删除既不必要，也会丢掉排查线索（2026-09-26 曾据此误判为"残留锁"）。
  - **真正会拦住后续发布的是未过期的 pending 占位**（存在 `publish_log.json` 里），
    由 `--pending-ttl`（默认 1800 秒）自动回收；确需手动释放时才用
    `publish_interval.py release --reserve-id <rid>`（`rid` 见链日志的 `RESERVE ok` 行）。

这些文件包含本机业务运行数据，公开仓库只保留本说明和 `.gitkeep`。
新电脑 clone 后直接运行 `reserve` 或 `check` 即可初始化目录；没有历史记录时按“无记录”处理。
