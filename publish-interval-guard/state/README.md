# 发布间隔本地状态（已迁出本目录）

> **2026-11-06 起，本目录不再存放台账与锁。**
> 它们默认落在 `<workspace>/.state/publish/`（`XHS_WORKSPACE` 缺省 `C:/xhs`）：
> - `<workspace>/.state/publish/publish_log.json` —— 最近 100 条发布记录与下一次间隔
> - `<workspace>/.state/publish/.guard.lock` —— 内核咨询锁的承载文件（常驻，不要手工删）
>
> 路径权威：`<patches>/tools/runtime_paths.py`；`python tools/runtime_paths.py --json` 可打印实际解析结果。

## 为什么搬出去

历史整树替换会冲掉 skill 树内的 state，台账丢失可能导致重复发布。
当前升级须保护本机状态并按根目录 `UPGRADING.md` 逐项合并，不整树覆盖。
不跨机器复制锁文件或本机状态；锁文件本身的存在并不表示锁被持有。

## 仍然生效的锁语义（没变，只是文件换了位置）

- 锁由操作系统按文件句柄管理，**关句柄 / 进程崩溃即自动释放**，
  因此 **文件存在 ≠ 锁被占用**；里面的 `pid` 只是**最后一次持有者**，仅用于锁超时报错时排查。
- 看到 `.guard.lock` 停在某个早已退出的 pid 上**是正常现象**，无需清理；
  手工删除既不必要，也会丢掉排查线索（2026-09-26 曾据此误判为"残留锁"）。
- **真正会拦住后续发布的是未过期的 pending 占位**（存在 `publish_log.json` 里），
  由 `--pending-ttl`（默认 1800 秒）自动回收；确需手动释放时才用
  `publish_interval.py release --reserve-id <rid>`（`rid` 见链日志的 `RESERVE ok` 行）。

## 本目录保留什么

只保留本说明与 `.gitkeep`，用于说明「这里曾经是 state」并防止空目录被误删。
迁移前停止所有发布进程。运行 `python tools/runtime_paths.py --init` 建状态目录；
仅当新台账不存在时复制旧台账，并保留旧文件；新台账存在时绝不覆盖。
迁移期如遇旧址残留 `publish_log.json.migrated-20261106`，那是迁移证据，不要再写回。
