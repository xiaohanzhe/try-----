# -*- coding: utf-8 -*-
"""直读 FILE_ATTRIBUTE —— 上一轮判据（os.stat().st_mode & S_IWRITE）在 Windows 上
是**恒假判据**（CPython 在 Windows 总返回 S_IWRITE|S_IREAD），必须改用
`GetFileAttributesW` 读真实的 attribute 位。

判据：0x1 = FILE_ATTRIBUTE_READONLY（只读）、0x2 = HIDDEN、0x20 = ARCHIVE。
对照：同目录下"我刚写的新文件"应当 READONLY=0（负控制 / 正控制）。
"""
import os
import sys
import io
import ctypes

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
GFA = ctypes.windll.kernel32.GetFileAttributesW
GFA.restype = ctypes.c_uint32
GFA.argtypes = [ctypes.c_wchar_p]
INVALID = 0xFFFFFFFF


def fa(p):
    a = GFA(p)
    return a


def label(a):
    if a == INVALID:
        return 'INVALID(路径不存在或不可访问)'
    return 'RO=%d HID=%d ARC=%d SYS=%d' % (
        bool(a & 0x1), bool(a & 0x2), bool(a & 0x20), bool(a & 0x4))


def probe(title, paths):
    print('\n=== %s ===' % title)
    for p in paths:
        a = fa(p)
        print('  [%s] %s' % (label(a), p))


def main():
    import glob
    V = r'E:\RalseiMemory'
    D = r'E:\Download\_tmp'

    probe('① vault 关键文件（产品要写的）', [
        os.path.join(V, 'config.json'),
        os.path.join(V, 'memory.json'),
        os.path.join(V, 'logs', 'ralsei_pet.log'),
        os.path.join(V, 'config.json.bak18'),
        os.path.join(V, 'customization_config.json'),
    ])

    # 老文件样本（上一轮判为不可写的）
    olds = sorted(glob.glob(os.path.join(D, '_*.py')))[:5]
    olds += sorted(glob.glob(os.path.join(D, 'commit_msg_*.txt')))[:3]
    probe('② E:\\Download\\_tmp 老文件（上一轮不可写）', olds)

    # 新文件样本（上一轮判为可写的）
    news = []
    for pat in ('tray_*.png', 'probe51*.jsonl', '*_stdout.log'):
        news += sorted(glob.glob(os.path.join(D, pat)))[:3]
    probe('③ E:\\Download\\_tmp 新文件（上一轮可写）', news)

    # 刚创建的文件（正控制）
    p = os.path.join(D, '_attr_now51.txt')
    try:
        open(p, 'w', encoding='utf-8').write('x')
        print('\n=== ④ 正控制：刚刚新建的文件 ===')
        print('  [%s] %s' % (label(fa(p)), p))
        os.remove(p)
    except Exception as e:
        print('  正控制失败', e)

    # 目录本身的属性
    print('\n=== ⑤ 目录属性 ===')
    for d in (V, os.path.join(V, 'logs'), D, 'E:\\'):
        print('  [%s] %s' % (label(fa(d)), d))

    print('\n=== ⑥ 同卷根目录抽样（E:\\ 顶层） ===')
    try:
        tops = [os.path.join('E:\\', n) for n in os.listdir('E:\\')[:12]]
        for p in tops:
            print('  [%s] %s' % (label(fa(p)), p))
    except Exception as e:
        print('  列目录失败', e)
    return 0


if __name__ == '__main__':
    sys.exit(main())
