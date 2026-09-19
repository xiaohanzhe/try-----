# -*- coding: utf-8 -*-
"""拉模型（带"静默卡死"检测）。

为什么不用 `ollama pull`
------------------------
① `ollama pull` 是客户端，真正的下载由 **daemon** 用它自己启动时的环境做 ——
   给客户端设 `HTTP_PROXY` 完全无效（表现为 `TLS handshake timeout`）。
② 直连时它会**静默卡死**：进程还在、进度不动、没有报错（上一次卡在 2.33GB 零增长）。
   根因是循环阻塞在 `for line in resp` 上 —— **读不到数据也不会抛异常**。

本脚本的修法
------------
给 urlopen 设 `timeout=30`：只要 30 秒内**一个字节都没来**，迭代就抛 `socket.timeout`
→ 捕获 → 重新发一次 `/api/pull`。Ollama 会**从已下好的分片续传**（不会从头来），
所以重连几乎不浪费。实测上一轮 4B 停在 95.4%，分片留在磁盘上，续传只需补齐尾部。

用法：python pull_model2.py <模型名>
"""
import json
import sys
import time
import urllib.request

HOST = 'http://localhost:11434'
MODEL = sys.argv[1] if len(sys.argv) > 1 else 'qwen3:4b-instruct-2507-q4_K_M'
MAX_ATTEMPTS = 60
STALL_TIMEOUT = 30


def fmt_mb(b):
    try:
        return '%.1fMB' % (float(b) / 1024.0 / 1024.0)
    except Exception:
        return str(b)


def pull_once():
    """跑一轮 /api/pull。返回 'ok' / 'stall' / 'error:<msg>'。"""
    body = json.dumps({'model': MODEL, 'stream': True}).encode('utf-8')
    req = urllib.request.Request(HOST + '/api/pull', data=body,
                                 headers={'Content-Type': 'application/json'})
    resp = urllib.request.urlopen(req, timeout=STALL_TIMEOUT)
    last_pct = -10
    done = False
    try:
        for raw in resp:
            raw = raw.decode('utf-8', 'replace').strip()
            if not raw:
                continue
            try:
                d = json.loads(raw)
            except ValueError:
                continue
            if d.get('error'):
                print('  ERROR %s' % d['error'], flush=True)
                return 'error:%s' % d['error']
            status = d.get('status') or ''
            total = d.get('total') or 0
            comp = d.get('completed') or 0
            if total:
                pct = int(100.0 * comp / total)
                if pct >= last_pct + 5:
                    last_pct = pct
                    print('  %3d%%  %s / %s' % (pct, fmt_mb(comp), fmt_mb(total)), flush=True)
            elif status:
                print('  [%s]' % status, flush=True)
            if status == 'success':
                done = True
                break
    except Exception as e:
        print('  轮次中断: %s: %s' % (type(e).__name__, e), flush=True)
        return 'ok' if done else 'stall'
    return 'ok' if done else 'stall'


def main():
    print('拉取 %s  (最多重连 %d 次，每次静默 %ds 即重连)' % (MODEL, MAX_ATTEMPTS, STALL_TIMEOUT), flush=True)
    t0 = time.time()
    for i in range(1, MAX_ATTEMPTS + 1):
        print('--- 第 %d 轮 (t=%.0fs) ---' % (i, time.time() - t0), flush=True)
        r = pull_once()
        if r == 'ok':
            print('DONE 用时 %.0fs' % (time.time() - t0), flush=True)
            return 0
        if r.startswith('error:'):
            print('FATAL %s' % r, flush=True)
            return 2
        time.sleep(2.0)
    print('GIVEUP 重连次数用尽，用时 %.0fs' % (time.time() - t0), flush=True)
    return 1


if __name__ == '__main__':
    sys.exit(main())
