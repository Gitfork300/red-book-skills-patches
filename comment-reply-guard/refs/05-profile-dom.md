# 个人主页 DOM 与抓取（2026-09-17 改版适配）

> 从 `refs/01-dom-and-scripts.md` 拆出：那份已 8898/9000 触顶。
> 场景：**巡检前要拿到 `note_id + xsec_token` 清单**时读这份。

## 一、改版前后对照（2026-09-17 实测）

| 项 | 旧（2026-09-15 前可用） | **新（2026-09-17 实测）** |
| --- | --- | --- |
| 笔记链接 | `a[href*="/explore/"]`，href 形如 `/explore/<id>?xsec_token=XXX` | `a[href*="/explore/"]` 仍在，但 **`display:none`** 且 **href 只有 `/explore/<id>`，不带 token** |
| token 位置 | 上面那个 a 的 href | **`a.cover` 的 href**：`/user/profile/<uid>/<note_id>?xsec_token=XXX&xsec_source=pc_user` |
| note_id 取法 | 解析 href | **`section.note-item` 的 `data-note-id` 属性**（最稳） |
| 标题 | `a span/div` 的 innerText | `section.note-item a.title span`（兜底 `a.title`） |
| 滚动容器 | `window.scrollTo` | **`#userPostedFeeds.feeds-container`**，滚 window **无效** |

**失效症状**：旧脚本不报错，直接 `saved 0`。判断标准不是「有没有异常」，而是**抓到的条数**。

## 二、可用代码（已验证，2026-09-17 抓到 276 条全带 token）

```python
PARSE_JS = r"""
(() => {
  const out = [];
  document.querySelectorAll('section.note-item').forEach(sec => {
    const nid = sec.getAttribute('data-note-id') || '';
    let tok = '';
    const cover = sec.querySelector('a.cover');
    if (cover) {
      const m = (cover.getAttribute('href') || '').match(/xsec_token=([^&"']+)/);
      if (m) tok = m[1];
    }
    if (!tok) {                                  // 兜底：整棵子树里搜
      const m2 = (sec.outerHTML || '').match(/xsec_token=([^&"\s]+)/);
      if (m2) tok = m2[1];
    }
    const t = sec.querySelector('a.title span, a.title');
    if (nid) out.push({id: nid, xsec_token: tok,
                       title: t ? (t.innerText||'').trim().slice(0,60) : ''});
  });
  return JSON.stringify(out);
})()
"""

SCROLL_JS = r"""
(() => {
  let best = null;
  document.querySelectorAll('*').forEach(e => {
    if (e.scrollHeight > e.clientHeight + 40 && e.clientHeight > 150) {
      if (!best || e.clientHeight > best.clientHeight) best = e;
    }
  });
  if (best) { best.scrollTop = best.scrollHeight; return 'scrolled'; }
  window.scrollTo(0, document.body.scrollHeight);
  return 'scrolled window';
})()
"""
```

实测：滚 16 轮 × 2s → 276 条（30 → 49 → … → 276 后不再增长）。

## 三、补 `time` 字段（扫描脚本靠它做 `--since` 过滤）

抓下来的清单**没有发布时间**，而扫描脚本按 `time >= since` 过滤。补法（按优先级）：

1. `publish_log.json` 按 `note_id` 精确匹配 `ts`（100 条环形缓冲，覆盖最近的）
2. 上一轮合并快照按 `id` 匹配 `time`
3. 都没有 → 留空（会被 since 过滤掉 = 不扫老笔记，符合铁律 19）

参考 `comment/_merge_notes_0917.py`（本次 276 条：publish_log 供 99 / 旧快照供 177 / 缺失 0）。

## 四、脚本清单

| 用途 | 脚本 |
| --- | --- |
| 抓主页清单（适配改版） | `comment/_grab_profile_xsec_0917.py` |
| 合并 + 补 time | `comment/_merge_notes_0917.py` |
| 扫评论（节流 + 验证码熔断） | `comment/_scan_0917.py`（`--since` / `--gap`） |

抓完/扫完记得跑 `comment/_tab_guard.py --clean`（铁律 15 / 18）。
