# -*- coding: utf-8 -*-
"""第91轮：6 个「会实例化 App」的 G2 套件到底是不是**环境抖动**？

为什么必须先判这个（不能直接 --update）：
  这 6 个套件（round8_anim / soul_round55 / npc_persona55 / npc_place56 / check67 / check73）
  的输出里**既有**确定性差异（我这轮新增 `walk_down_sleep` ⇒ 114→115 组），
  **又有**环境依赖行（`可交互物 N 个`、E 盘路径、`<TMP>`）。
  若直接 --update，会把"E 盘离线"这一瞬的抖动一并固化 ⇒ E 盘恢复后又 DIFF（**假绿**）。
  判据：**连跑 3 轮**，看同一套件的归一化 sha 是否稳定。
    · 3 轮全同 ⇒ 稳定（可固）
    · 有变化   ⇒ 抖动（不可固，须先修掉环境依赖）
只读（只跑套件、重算 sha），不改 baseline。
"""
import hashlib
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'))
REGRESS = os.path.join(ROOT, 'code-quality-audit', 'regress')
sys.path.insert(0, REGRESS)
import run_all as R  # noqa: E402

IDS = ['round8_anim', 'soul_round55', 'npc_persona55',
       'npc_place56', 'check67', 'check73']
PY = r'C:\Python311\python.exe'


def run_once():
    args = [PY, os.path.join('code-quality-audit', 'regress', 'run_all.py')]
    for i in IDS:
        args += ['--only', i]
    subprocess.run(args, cwd=ROOT, capture_output=True)
    snap = {}
    for i in IDS:
        p = os.path.join(R.OUT_DIR, i + '.txt')
        txt = open(p, encoding='utf-8', errors='replace').read()
        snap[i] = hashlib.sha256(R.normalize(txt).encode('utf-8')).hexdigest()[:12]
    return snap


rounds = [run_once() for _ in range(3)]
print('%-16s %-14s %-14s %-14s %s' % ('suite', 'run1', 'run2', 'run3', '结论'))
print('-' * 72)
stable, jitter = [], []
for i in IDS:
    vals = [r[i] for r in rounds]
    ok = (vals[0] == vals[1] == vals[2])
    (stable if ok else jitter).append(i)
    print('%-16s %-14s %-14s %-14s %s' % (i, vals[0], vals[1], vals[2],
                                          '稳定(可固)' if ok else '★抖动(不可固)'))
print('-' * 72)
print('稳定 %d: %s' % (len(stable), stable))
print('抖动 %d: %s' % (len(jitter), jitter))
