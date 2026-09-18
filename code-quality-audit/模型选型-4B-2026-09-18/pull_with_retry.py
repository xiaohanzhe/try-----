# -*- coding: utf-8 -*-
"""
抗断续传拉取器（第十三轮）。

背景：本机到 Ollama CDN 的连接会**传一阵就被掐断**（实测两次：
一次 5.9 MB/s 跑 34% 后掉到 0.02 MB/s；一次 9.7 MB/s 跑 50% 后同样卡死），
但每次**重新发起** /api/pull 都能从断点续传出新的一段。

所以策略：把每个连接当成"一次最多传 N 秒的短连接"——
  超过 STALL_SEC 没有新字节，就主动断掉、重连、续传。
Ollama 的 /api/pull 本身支持断点续传（blobs/*-partial），所以这样是安全的。
"""
import json
import os
import sys
import time
import urllib.request

HOST = 'http://localhost:11434'
MODEL = sys.argv[1] if len(sys.argv) > 1 else 'qwen3:4b-instruct-2507-q4_K_M'
OUT = sys.argv[2] if len(sys.argv) > 2 else 'pull_retry.txt'
STALL_SEC = 90          # 某层 90 秒没有新字节 → 断掉重连
MAX_ROUNDS = 40

lines = []


def emit(s):
    line = '%s  %s' % (time.strftime('%H:%M:%S'), s)
    lines.append(line)
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')


def one_round(rnd):
    req = urllib.request.Request(
        HOST + '/api/pull',
        data=json.dumps({'model': MODEL, 'stream': True}).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
    )
    seen = {}
    resp = urllib.request.urlopen(req, timeout=STALL_SEC)
    last_ts = time.time()
    best = 0
    tot = 0
    for raw in resp:
        raw = raw.decode('utf-8', 'replace').strip()
        if not raw:
            continue
        try:
            d = json.loads(raw)
        except ValueError:
            continue
        st = d.get('status', '')
        if st == 'success':
            return True, best, tot
        if 'digest' in d:
            comp = d.get('completed', 0) or 0
            tot = d.get('total', 0) or tot
            if comp != seen.get('c'):
                seen['c'] = comp
                last_ts = time.time()
                best = max(best, comp)
        if time.time() - last_ts > STALL_SEC:
            emit('round%d 层无进展 >%ds，主动断线重连（已到 %.1f/%.1f MB）'
                 % (rnd, STALL_SEC, best / 1e6, tot / 1e6))
            return False, best, tot
    return False, best, tot


def main():
    done = False
    last_tot = 0
    for rnd in range(1, MAX_ROUNDS + 1):
        try:
            done, comp, tot = one_round(rnd)
        except Exception as e:
            emit('round%d EXCEPTION %s: %s' % (rnd, type(e).__name__, e))
            time.sleep(2)
            continue
        if done:
            emit('round%d ✅ 拉取完成' % rnd)
            break
        emit('round%d 断开  进度 %.1f/%.1f MB (%.1f%%)'
             % (rnd, comp / 1e6, tot / 1e6, (comp / tot * 100) if tot else 0))
        last_tot = tot
        if tot and comp >= tot:
            # 全部字节到齐但还没收到 success，再问一次即可
            time.sleep(2)
            continue
        time.sleep(1)
    else:
        emit('达到最大重试轮数 %d，放弃' % MAX_ROUNDS)
    emit('DONE=%s' % done)


if __name__ == '__main__':
    main()
