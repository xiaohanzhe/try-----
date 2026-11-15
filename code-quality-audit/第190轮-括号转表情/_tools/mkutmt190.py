# -*- coding: utf-8 -*-
u"""第190轮 · 把 UTMT 从 E 盘复制到 D 盘，并**逐字节校验**。

为什么要复制
------------
E 盘有散落坏点（记忆「环境」条已记）。本轮实测到：

    System.ExecutionEngineException: In page error:
    Attempted to access a memory page that is not present, and the system
    is unable to load the page.

  rc = 3221225478（0xC0000602 FailFast），日志里**只有这一句**，
  发生在 Roslyn 加载 Magick.NET 元数据时 —— 看起来像"csx 写错了"，
  实际是**磁盘页读不出来**。E 盘原件 md5 逐一核对 213 个文件全 OK
  ⇒ 属于**偶发**读坏。同一份 csx 从 D 盘副本跑 ⇒ rc=0、117/117 页全成功。

★★ 所以复制**必须逐字节校验**：坏点可能正好落在复制的那一次读取上，
   校验通过才能证明副本可当唯一真源。

用法
----
    python mkutmt190.py            # 复制 + 校验
    python mkutmt190.py --check    # 只校验现有副本
"""
import hashlib
import io
import os
import shutil
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

SRC = u'E:\\Download\\UTMT_CLI_v0.9.2.0'
DST = u'D:\\_tmp190\\utmt'
#: 必须一致的关键文件（缺一个就不是同一份工具）
KEY = ['UndertaleModCli.exe', 'UndertaleModLib.dll',
       'Magick.NET-Q8-AnyCPU.dll', 'Magick.NET.Core.dll',
       'Magick.Native-Q8-x64.dll']


def md5(p, chunk=1 << 20):
    h = hashlib.md5()
    with io.open(p, 'rb') as fh:
        while True:
            b = fh.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def walk(root):
    out = {}
    for dp, _dn, fns in os.walk(root):
        for fn in fns:
            full = os.path.join(dp, fn)
            rel = os.path.relpath(full, root)
            out[rel] = full
    return out


def check():
    """返回 (ok, 说明)。"""
    if not os.path.isdir(DST):
        return False, u'副本目录不存在'
    a = walk(SRC)
    b = walk(DST)
    if set(a) != set(b):
        miss = sorted(set(a) - set(b))[:5]
        extra = sorted(set(b) - set(a))[:5]
        return False, u'文件清单不一致 缺=%s 多=%s' % (miss, extra)
    bad = []
    for rel in a:
        if md5(a[rel]) != md5(b[rel]):
            bad.append(rel)
    if bad:
        return False, u'%d 个文件内容不一致：%s' % (len(bad), bad[:5])
    for k in KEY:
        if k not in a:
            return False, u'缺关键文件 %s' % k
    return True, u'%d 个文件逐字节一致' % len(a)


def main():
    if '--check' in sys.argv[1:]:
        ok, msg = check()
        print('[%s] %s' % ('OK' if ok else '报红', msg))
        return 0 if ok else 4

    if not os.path.isdir(SRC):
        print('[停手] 源目录不存在：%s' % SRC)
        return 2
    t0 = time.time()
    # ★ 清空目标前先确认它在 D:\_tmp190 下（防手滑删别处）
    if os.path.isdir(DST) and not os.path.abspath(DST).lower().startswith('d:\\_tmp190'):
        print('[停手] 目标不在 D:\\_tmp190 下，拒绝清空：%s' % DST)
        return 2
    if os.path.isdir(DST):
        shutil.rmtree(DST)
    shutil.copytree(SRC, DST)
    print('[copy] %.1fs' % (time.time() - t0))

    ok, msg = check()
    print('[校验] %s  %s' % ('OK' if ok else '报红', msg))
    if not ok:
        print('[报红] 副本不可信 ⇒ 不许拿它跑 UTMT（坏点可能落在复制时的那次读取上）')
        return 4
    print('[完成] %s' % DST)
    return 0


if __name__ == '__main__':
    sys.exit(main())
