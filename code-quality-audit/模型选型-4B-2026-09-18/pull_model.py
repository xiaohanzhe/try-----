# -*- coding: utf-8 -*-
"""
带进度目视的模型拉取器（第十三轮）。

为什么不用 `ollama pull`：
  1. 它是**客户端**，真正下载的是 ollama daemon；
     在客户端 shell 里设 HTTP_PROXY/HTTPS_PROXY **对 daemon 无效** ——
     上一轮两次 pull 失败都栽在这（一次 TLS handshake timeout，一次静默卡死）。
  2. CLI 的进度条带 ANSI 控制序列，重定向到文件后完全看不出进度。
本脚本直接打 daemon 的 /api/pull 流式接口，把每层 completed/total 落成纯文本，
卡死时能直接看出是"哪一层、停在多少字节"。
"""
import json
import sys
import time
import urllib.request

HOST = 'http://localhost:11434'
MODEL = sys.argv[1] if len(sys.argv) > 1 else 'qwen3:4b-instruct-2507-q4_K_M'
OUT = sys.argv[2] if len(sys.argv) > 2 else 'pull_log.txt'

req = urllib.request.Request(
    HOST + '/api/pull',
    data=json.dumps({'model': MODEL, 'stream': True}).encode('utf-8'),
    headers={'Content-Type': 'application/json'},
)

t0 = time.time()
last = {}
lines = []
stall_warned = False
last_ts = time.time()

with open(OUT, 'w', encoding='utf-8') as f:
    def emit(s):
        f.write(s + '\n')
        f.flush()

    emit('model=%s  start=%s' % (MODEL, time.strftime('%H:%M:%S')))
    try:
        resp = urllib.request.urlopen(req, timeout=600)
        for raw in resp:
            raw = raw.decode('utf-8', 'replace').strip()
            if not raw:
                continue
            try:
                d = json.loads(raw)
            except ValueError:
                continue
            st = d.get('status', '')
            if 'digest' in d:
                dig = d['digest'][:16]
                comp = d.get('completed', 0) or 0
                tot = d.get('total', 0) or 0
                if comp != last.get(dig) or tot != last.get(dig + '_t'):
                    last[dig] = comp
                    last[dig + '_t'] = tot
                    last_ts = time.time()
                    pct = (comp / tot * 100) if tot else 0
                    emit('%6.1fs  %-18s %-22s %6.1f/%.1f MB  %5.1f%%'
                         % (time.time() - t0, st, dig, comp / 1e6, tot / 1e6, pct))
            else:
                emit('%6.1fs  %s' % (time.time() - t0, st))
                last_ts = time.time()

            # 卡死检测：60 秒没有新字节
            if time.time() - last_ts > 60 and not stall_warned:
                emit('!! 已 60 秒无进展，可能卡死（daemon 侧连接问题）')
                stall_warned = True
    except Exception as e:
        emit('EXCEPTION %s: %s' % (type(e).__name__, e))
    emit('end=%s  elapsed=%.0fs' % (time.strftime('%H:%M:%S'), time.time() - t0))
