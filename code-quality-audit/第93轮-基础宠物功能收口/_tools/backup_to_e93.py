# -*- coding: utf-8 -*-
u"""备份核心文件到 E:\\Download\\_tmp（E 盘不可写则回落 TEMP）。只读源文件、只写备份。

用法： python backup_to_e93.py <src> [<dst_dir_name>]
"""
import os
import shutil
import sys
import tempfile

ROOT = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'


def pick_dir():
    for d in (r'E:\Download\_tmp\m88', os.path.join(tempfile.gettempdir(), 'm88')):
        try:
            os.makedirs(d, exist_ok=True)
            f = os.path.join(d, '_probe.tmp')
            open(f, 'wb').write(b'x')
            os.remove(f)
            return d
        except Exception:
            continue
    return None


def main():
    src = sys.argv[1]
    dst = pick_dir()
    if dst is None:
        print('没有可写目录')
        return 2
    if not os.path.isabs(src):
        src = os.path.join(ROOT, src)
    out = os.path.join(dst, os.path.basename(src) + '.bak')
    shutil.copy2(src, out)
    print('backup -> %s  (%d bytes)' % (out, os.path.getsize(out)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
