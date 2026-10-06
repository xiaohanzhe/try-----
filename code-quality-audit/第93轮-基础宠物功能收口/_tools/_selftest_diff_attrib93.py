# -*- coding: utf-8 -*-
"""diff_attrib93.py 的正/负控制（一次性自检，跑完即删）。

  A 纯数字漂移          -> 期望 [纯数字漂移]
  B 一个词不同          -> 期望 [NOT-PURE]
  C hunk 两侧行数不等    -> 期望 [NOT-PURE] shape
  D 0 差异              -> 期望 [IDENTICAL]
★ 并断言 A/B/C/D 的**结论各不相同**，否则判据无区分度（恒真）。
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import diff_attrib93 as M

TMP = os.path.join(os.environ.get('TEMP', '.'), 'attr93_selftest')
if not os.path.isdir(TMP):
    os.makedirs(TMP)

CASES = {
    # A: 只有数字变（行号偏移 + 计数）
    'A_pure': (
        '@@ -1,2 +1,2 @@\n'
        '-  main.py:57146 camera_follow 1 处\n'
        '-  窗口 640x480\n'
        '+  main.py:57473 camera_follow 1 处\n'
        '+  窗口 640x480\n'),
    # B: 一个词不同（camera_follow -> camera_target）
    'B_word': (
        '@@ -1,1 +1,1 @@\n'
        '-  main.py:57146 camera_follow 1 处\n'
        '+  main.py:57146 camera_target 1 处\n'),
    # C: hunk 内两侧行数不等（2- / 1+）
    'C_shape': (
        '@@ -1,2 +1,1 @@\n'
        '-  甲 1\n'
        '-  乙 2\n'
        '+  甲 9\n'),
    # D: 无差异行
    'D_none': (
        '@@ -1,1 +1,1 @@\n'
        '   context only\n'),
}

M.OUT = TMP
for name, body in CASES.items():
    with io.open(os.path.join(TMP, name + '.diff.txt'), 'w', encoding='utf-8', newline='') as f:
        f.write(body)

import contextlib
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    rc = M.main(list(CASES.keys()))
out = buf.getvalue()
print(out)
print('rc =', rc)

def verdict(name):
    for ln in out.split('\n'):
        if ln.startswith(name.ljust(22)):
            for tag in ('[NOT-PURE]', '[纯数字漂移]', '[IDENTICAL]', '[SKIP]'):
                if tag in ln:
                    return tag
    return '??'

va, vb, vc, vd = verdict('A_pure'), verdict('B_word'), verdict('C_shape'), verdict('D_none')
print('A=%s B=%s C=%s D=%s' % (va, vb, vc, vd))
checksum = [
    ('A 纯数字漂移', va == '[纯数字漂移]'),
    ('B 一词之差异报红', vb == '[NOT-PURE]'),
    ('C hunk 不齐报红', vc == '[NOT-PURE]'),
    ('D 零差异报 IDENTICAL', vd == '[IDENTICAL]'),
    ('无区分度自检：四结论不全相同', len({va, vb, vc, vd}) >= 3),
    ('rc 反映有坏例', rc == 1),
]
bad = 0
for d, ok in checksum:
    print(('  [PASS] ' if ok else '  [FAIL] ') + d)
    if not ok:
        bad += 1
print('SELFTEST', 'PASS' if bad == 0 else 'FAIL', 'bad=', bad)
sys.exit(1 if bad else 0)
