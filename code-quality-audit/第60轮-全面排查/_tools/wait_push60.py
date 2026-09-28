#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""第60轮 有界推送重试（链路降级时的处置；沿用第58轮口径）。

现象（2026-09-29 00:06 实测）：
  · 代理 7897 TCP/隧道 OK，但 **TLS 握手失败**（23:29 时还四关全过）；
  · 无可用代理 ⇒ 走直连 ⇒ `CONNECT tunnel failed, response 502`；
  · 沙箱内跑还会被 SIGTERM 且 stdout 缓冲丢失 ⇒ 必须 `-u` + 免沙箱。

铁律：**绝不无限重试**。上限 4 次 / 间隔 25s / 成功即停。
每次都用 `gitpush.py --push-only` 自己那套四级代理探测（不手搓 git 参数）。
"""
import io
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
AUDIT = os.path.dirname(ROUND)
REPO = os.path.dirname(AUDIT)
TOOL = os.path.join(AUDIT, '第38轮-场景系统审查', '_tools', 'gitpush.py')

MAX_TRIES = 4
GAP = 25.0


def main():
    print('=' * 72)
    print('有界推送重试：最多 %d 次 / 间隔 %.0fs' % (MAX_TRIES, GAP))
    print('=' * 72)
    for i in range(1, MAX_TRIES + 1):
        print()
        print('---- 第 %d/%d 次 ----' % (i, MAX_TRIES))
        p = subprocess.run([sys.executable, '-u', TOOL, '--push-only'],
                           cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           env=dict(os.environ, PYTHONUNBUFFERED='1'),
                           timeout=420)
        out = p.stdout.decode('utf-8', 'replace')
        tail = [ln for ln in out.splitlines()
                if ln.startswith('[5c]') or ln.startswith('[6]') or ln.startswith('[9]')
                or '结论' in ln or 'proxy ' in ln]
        for ln in tail[-12:]:
            print('   %s' % ln[:160])
        if 'PUSHED' in out and 'NOT_PUSHED' not in out:
            print()
            print('=== 成功（第 %d 次）===' % i)
            return 0
        if i < MAX_TRIES:
            print('   未成功，等 %.0fs 再来（有界，不无限重试）' % GAP)
            time.sleep(GAP)
    print()
    print('=== 结论 = 4 次都未成功（链路持续降级）。已提交但未推送，'
          '下次网络恢复用 `gitpush.py --push-only` 补推即可 ===')
    return 5


if __name__ == '__main__':
    sys.exit(main())
