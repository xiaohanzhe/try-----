#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""第75轮 · 篡改体检（B4）—— 证明 check75 的判据**有鉴别力**。

做法：对产品文件做**逐字节可还原**的篡改，跑 check75，要求目标判据**报红**；
跑完把文件逐字节还原（用 sha256 前后比对自证）。

★ 纪律：只改**这一个**文件、只做**字符串替换**、**不留备份在工作区**。
"""

import hashlib
import io
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..', '..')
PET = os.path.join(ROOT, 'ralsei_pet')
PY = r'C:\Python311\python.exe'
CHECK = os.path.join(HERE, 'check75.py')

REL = os.path.join(PET, 'modules', 'relationship.py')
MAIN = os.path.join(PET, 'src', 'main.py')


def sha(p):
    return hashlib.sha256(io.open(p, 'rb').read()).hexdigest()


def run_check():
    r = subprocess.run([PY, CHECK], capture_output=True, text=True,
                       encoding='utf-8', errors='replace', cwd=ROOT)
    return (r.stdout or '') + (r.stderr or '')


# (名字, 文件, 旧串, 新串, 期望报红的判据号)
CASES = [
    ('1 下限归零',      REL, b'NERVOUS_FLOOR = 0.04', b'NERVOUS_FLOOR = 0.0', ['A2', 'C5b']),
    ('2 档位反序',      REL, b"'distrust': 0.62,", b"'distrust': 0.06,", ['A1']),
    ('3 harsh 压下去',  REL, b"'harsh': 0.30,", b"'harsh': -0.30,", ['A4']),
    ('4 文案塞数值',    REL, 'return \'【你现在的状态】\' + body',
                            'return \'【你现在的状态】\' + body + \'（紧张度 0.62）\'', ['B1']),
    ('5 接线被摘掉',    MAIN, b'        if _nerv_brief:\n            system = system + "\\n\\n" + _nerv_brief\n', b'', ['C2c']),
]


def main():
    base = {p: sha(p) for p in (REL, MAIN)}
    results = []
    for name, path, old, new, expect in CASES:
        raw = io.open(path, 'rb').read()
        ob = old.encode('utf-8') if isinstance(old, str) else old
        nb = new.encode('utf-8') if isinstance(new, str) else new
        if ob not in raw:
            results.append((name, False, '夹具没命中（替换串不存在）'))
            continue
        try:
            io.open(path, 'wb').write(raw.replace(ob, nb, 1))
            out = run_check()
            import re
            failed = set()
            for m in re.finditer(r'\[FAIL\]\s*(A\d+\w*|B\d+\w*|C\d+\w*)', out):
                failed.add(m.group(1))
            hit = [e for e in expect if any(f.startswith(e) for f in failed)]
            ok = len(hit) > 0
            results.append((name, ok, '报红={' + ','.join(sorted(failed)) + '}'))
        finally:
            io.open(path, 'wb').write(raw)      # 逐字节还原

    print('===== 篡改体检结果 =====')
    allok = True
    for name, ok, info in results:
        print('%s  %-14s  %s' % ('[ OK ]' if ok else '[FAIL]', name, info))
        allok = allok and ok

    print()
    print('===== 还原自证（sha256 必须与初始一致）=====')
    for p in (REL, MAIN):
        same = sha(p) == base[p]
        print('%s  %s  %s' % ('[ OK ]' if same else '[FAIL]',
                              os.path.relpath(p, ROOT), sha(p)[:16]))
        allok = allok and same
    print()
    print('tamper75：%s' % ('全部 OK' if allok else '有失败'))
    return 0 if allok else 1


if __name__ == '__main__':
    sys.exit(main())
