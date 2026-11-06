> read_when: 需要排查并发重复发布、锁超时、verify-note 误报或台账异常时。
> 本文件是 `SKILL.md` 的展开，执行顺序仍以入口为准。

# 发布间隔实现细节

## 为什么必须 reserve

旧流程先 `check`、发布后才 `record`，两个进程可以同时通过只读检查，在数分钟后各自发布。
`reserve` 将“读台账、查标题、判间隔、写 pending”置于同一把内核咨询锁中，避免 TOCTOU。
Windows 使用 `msvcrt.locking`，POSIX 使用 `fcntl.flock`；锁由句柄管理，进程退出自动释放，
不删除锁文件。

批次级锁仍由批量脚本负责；单篇 publish 锁不能阻止两个批次交错发布。

## verify-note

发布链应分开捕获 stdout/stderr，从 stdout 的 `VERIFY_NOTE_RESULT` JSON 读取 `found:true`。
不要拼接 stderr 再取末行，否则 DeprecationWarning 可能被误报成 WebSocket 断连。

## 兼容与调试

历史脚本可能在 pipeline 自动 record 后再次调用 record；按 note_id 幂等是安全的。
`wait --max-block` 必须不小于当前的 `--interval-max`（**2026-10-22 起为 1080 秒**），默认使用 2400 秒。
注意 1920/1320/1080 这类数字会随间隔参数变更而变化，改 `DEFAULT_MIN/MAX` 时必须同步改 `DEFAULT_MAX_BLOCK`；
当前 `DEFAULT_MIN=480 / DEFAULT_MAX=1080 / DEFAULT_MAX_BLOCK=2400`，改任一项都要同步本文件、`SKILL.md`
与 `refs/02-changelog.md`。
`record --interval 600`，但不得把调试参数带入正式批次。
