#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""对外网络可达性探测（发布前用）。

为什么需要它
------------
发布链路走的是 **TLS(443)**。实测本机会出现"假通"：
TCP connect 成功、`ping` 通、甚至 HTTP:80 都能返回 302，
但 **443 上的 TLS 握手被整段丢弃**（ClientHello 发出去没有任何回包，直到超时）。
此时 `creator.xiaohongshu.com` 打不开，发布流水线会在
`Clicking '上传图文' tab` 处失败，看起来像"页面结构变了"，实际是网络问题。

所以判定"小红书能不能发"，**必须真做一次 TLS 握手**，
不能只看 TCP 连通 / ping / 首页 HTTP 状态码。

用法
----
    python net_probe.py                       # 探一次，OK 退出 0，不可达退出 1
    python net_probe.py --json                # 输出 JSON
    python net_probe.py --wait-minutes 180    # 每 60 秒重试，直到可达或超时
    python net_probe.py --hosts a.com,b.com   # 自定义探测目标

退出码：0 = 可达 / 1 = 不可达 / 2 = 参数错误
"""
import argparse
import json
import socket
import ssl
import sys
import time

DEFAULT_HOSTS = ["creator.xiaohongshu.com", "www.xiaohongshu.com"]


def probe(host, timeout=8.0):
    """返回 (ok, detail)。ok=True 时 detail 为协商到的 TLS 版本。"""
    ctx = ssl.create_default_context()
    raw = socket.socket()
    raw.settimeout(timeout)
    t0 = time.time()
    try:
        ip = socket.gethostbyname(host)
    except Exception as e:
        raw.close()
        return False, f"DNS 解析失败: {type(e).__name__}"
    try:
        raw.connect((ip, 443))
    except Exception as e:
        raw.close()
        return False, f"TCP 连接失败: {type(e).__name__}"
    try:
        s = ctx.wrap_socket(raw, server_hostname=host)
        ver = s.version()
        s.close()
        return True, f"{ver} ({ip}, {time.time() - t0:.2f}s)"
    except Exception as e:
        return False, f"TLS 握手失败: {type(e).__name__} (TCP 已连 {ip})"
    finally:
        try:
            raw.close()
        except Exception:
            pass


def probe_all(hosts, timeout=8.0):
    return {h: probe(h, timeout) for h in hosts}


def main():
    ap = argparse.ArgumentParser(description="对外网络可达性探测（TLS 握手）")
    ap.add_argument("--hosts", default=",".join(DEFAULT_HOSTS),
                    help="逗号分隔的域名，默认 creator/www 小红书")
    ap.add_argument("--timeout", type=float, default=8.0)
    ap.add_argument("--wait-minutes", type=int, default=0,
                    help=">0 时每 60 秒重试一次，直到全部可达或超时")
    ap.add_argument("--interval", type=int, default=60, help="重试间隔秒数")
    ap.add_argument("--json", action="store_true", help="以 JSON 输出")
    args = ap.parse_args()

    hosts = [h.strip() for h in args.hosts.split(",") if h.strip()]
    if not hosts:
        print("没有可探测的域名", file=sys.stderr)
        return 2

    deadline = time.time() + args.wait_minutes * 60
    attempt = 0
    while True:
        attempt += 1
        res = probe_all(hosts, args.timeout)
        ok_all = all(v[0] for v in res.values())
        if args.json:
            print(json.dumps(
                {"attempt": attempt, "ok": ok_all,
                 "results": {k: {"ok": v[0], "detail": v[1]} for k, v in res.items()}},
                ensure_ascii=False))
        else:
            tag = "OK" if ok_all else "UNREACHABLE"
            print(f"[{time.strftime('%H:%M:%S')}] 第 {attempt} 次探测 -> {tag}")
            for h, (ok, detail) in res.items():
                print(f"    {'✓' if ok else '✗'} {h}: {detail}")
        if ok_all or args.wait_minutes <= 0 or time.time() >= deadline:
            return 0 if ok_all else 1
        time.sleep(args.interval)


if __name__ == "__main__":
    sys.exit(main())
