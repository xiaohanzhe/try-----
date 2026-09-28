# -*- coding: utf-8 -*-
u"""第61轮 · 工具：下载 UTMT CLI v0.9.2.0（经代理 + sha256 校验）。

纪律：逐个代理实测，成功即停；不无限重试。
用法：python dl61.py [--probe]
"""
from __future__ import print_function

import hashlib
import io
import os
import sys
import time
import urllib.request

URL = (u'https://github.com/UnderminersTeam/UndertaleModTool/releases/download/'
       u'0.9.2.0/UTMT_CLI_v0.9.2.0-Windows.zip')
SHA256 = u'e7573e45d107be34f81f955c6e4afc3c7c8f2628e5a6f307a871e3825b3dfb40'
EXPECT_SIZE = 62585935

DEST_DIR = u'E:\\Download\\_tools\\UTMT_CLI_0.9.2.0'
DEST = os.path.join(DEST_DIR, u'UTMT_CLI_v0.9.2.0-Windows.zip')

#: (标签, proxy 或 None=显式不走代理)
ROUTES = [
    (u'7897', u'http://127.0.0.1:7897'),
    (u'7375', u'http://127.0.0.1:7375'),
    (u'直连', None),
]


def opener_for(proxy):
    if proxy is None:
        return urllib.request.build_opener(urllib.request.ProxyHandler({}))
    return urllib.request.build_opener(
        urllib.request.ProxyHandler({u'http': proxy, u'https': proxy}))


def probe():
    for label, proxy in ROUTES:
        t0 = time.time()
        try:
            op = opener_for(proxy)
            req = urllib.request.Request(URL, method=u'HEAD')
            with op.open(req, timeout=20) as r:
                print(u'[%s] %s  status=%s  len=%s  (%.1fs)'
                      % (label, u'OK', r.status, r.headers.get(u'Content-Length'), time.time() - t0))
        except Exception as e:  # noqa: BLE001
            print(u'[%s] FAIL  %s: %s  (%.1fs)' % (label, type(e).__name__, e, time.time() - t0))
    return 0


def download():
    if not os.path.isdir(DEST_DIR):
        os.makedirs(DEST_DIR)
    for label, proxy in ROUTES:
        print(u'--- 尝试路由 %s ---' % label)
        t0 = time.time()
        try:
            op = opener_for(proxy)
            req = urllib.request.Request(URL, headers={u'User-Agent': u'python-urllib/61'})
            with op.open(req, timeout=45) as r:
                total = int(r.headers.get(u'Content-Length') or 0)
                got = 0
                h = hashlib.sha256()
                last = 0.0
                tmp = DEST + u'.part'
                with io.open(tmp, u'wb') as fh:
                    while True:
                        chunk = r.read(262144)
                        if not chunk:
                            break
                        fh.write(chunk)
                        h.update(chunk)
                        got += len(chunk)
                        now = time.time()
                        if now - last > 3.0:
                            last = now
                            pct = (100.0 * got / total) if total else 0.0
                            print(u'    %s / %s  (%.1f%%)  %.1fs'
                                  % (got, total, pct, now - t0))
                dig = h.hexdigest()
                print(u'  下载完成: %d bytes, sha256=%s' % (got, dig))
                if dig.lower() != SHA256.lower():
                    print(u'  !! sha256 不匹配（期望 %s）—— 丢弃' % SHA256)
                    os.remove(tmp)
                    continue
                if os.path.exists(DEST):
                    os.remove(DEST)
                os.rename(tmp, DEST)
                print(u'  ✅ sha256 校验通过 -> %s' % DEST)
                return 0
        except Exception as e:  # noqa: BLE001
            print(u'  路由 %s 失败: %s: %s' % (label, type(e).__name__, e))
    print(u'!! 所有路由均失败')
    return 1


if __name__ == u'__main__':
    if u'--probe' in sys.argv:
        raise SystemExit(probe())
    raise SystemExit(download())
