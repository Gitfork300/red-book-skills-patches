# 04 · 我们的踩坑补充（非上游内容）

> read_when: 走图文/视频流程、用 `--preview`、或在 Windows 受限环境发布时
> **source: patch**（本文件全部是我们自己的经验，上游更新不影响它）
>
> ⚠️ 上游的标准流程（测试浏览器 / 图文 / 视频 / 检索互动）**不在本文件** ——
> 见仓库根目录 `README.md`。本仓库的操作规则以 `runtime/INSTRUCTIONS.md` 和 `runtime/references/` 为准，
> 避免在 apply 时把上游的新改动覆盖回旧版本。

## ⚠️ 视频素材的方向坑（2026-09-06 实测）

**`VideoGen` 的 `9:16` 参数只控制输出容器，不约束模型构图。**
直接用 text-to-video + `9:16` 生成，模型常按横屏习惯铺内容，再硬填进竖屏框，
结果是**画面整体侧倒 90°**（天空在左侧、地平线竖着走）。

正确路径是 **image-to-video**：

1. 先用 `ImageGen` 出一张明确竖幅的静态图（`1024x1536`，prompt 里写
   `Vertical portrait orientation ... clear vertical composition`）。
2. 再用 `VideoGen` 以该图作首帧演进（传 `image` 参数），方向即可保证。

发布前务必用 OpenCV **抽查中间帧**确认方向，别只看容器分辨率 ——
容器 `720x1280` 也可能是横躺的内容。

## ⚠️ `--preview` 不等于草稿（重要）

`--preview` 只是**停在发布页不点发布**，不会触发「暂存草稿」。
此时关掉 Chrome / 断开 CDP，编辑好的标题、正文、视频、话题标签**全部丢失**，
草稿箱里也不会有。

- 用 `--preview` 后如需保留内容，必须在编辑器里**手动点「暂存草稿」**。
- 若要无人值守发布，去掉 `--preview` 直接发布。

## Windows 受限执行环境（进程会被会话回收）

完整规则与脚本见 patch：`../../windows-sandbox-workaround/SKILL.md`

- 沙箱/受限会话中，**命令结束时 Chrome 被强制回收**，窗口闪退 + Cookie 无法落盘。
- **正确做法**：把「登录等待 + 发布」放进同一次调用，全程不关浏览器，
  最后用 CDP `Browser.close` **优雅退出**。
- 与 `publish-interval-guard` 集成：通过环境变量 `XHS_INTERVAL_GUARD` 指向其 helper，
  自动化 wait/record。

```bash
<patch>/helpers/xhs_login_wait.py 200            # 仅登录（优雅关闭以保存会话）
<patch>/helpers/xhs_login_wait.py 200 publish    # 登录成功后立即发布（推荐，避免二次扫码）
```

关键实现点：**按标签 ID 锁定登录页**、**必须做二次验证**、**必须优雅关闭**。详见 patch。

## 检索与互动的注意点

- 检查登录状态用**主页** `XHS_HOME_URL`，**不是创作者中心**。
- `search-feeds` **没有 `--limit` 参数**，只要前 N 条请在调用方截断返回列表。
- `check-login` 有 **12h 本地缓存且只缓存「已登录」** → 查真登录态先删
  `tmp/login_status_cache.json`，否则拿到旧结论。
