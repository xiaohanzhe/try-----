# -*- coding: utf-8 -*-
"""复算 G2 默认模式的比对列（IDENTICAL / DIFF），不重跑。

理由：`run_all.py` 的 `status` 只看 exit / n_fail，**DIFF 不计入 FAIL**，
只写进"【问题】"段。所以"FAIL=0"**不能**证明零 DIFF —— 必须单独看比对列。

本脚本 import run_all 拿到**产品自己的** `normalize` / `sha256`，
对 `_out/<id>.txt`（本次运行留下的原始输出）与 `baseline.json` 逐套件比对。
"""
import importlib.util
import json
import os
import sys

REG = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))),
    'code-quality-audit', 'regress')

spec = importlib.util.spec_from_file_location('run_all', os.path.join(REG, 'run_all.py'))
ra = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ra)

base = json.load(open(os.path.join(REG, 'baseline.json'), encoding='utf-8'))
suites = base.get('suites', {})
print('基线套件数 =', len(suites))

diffs, missing = [], []
for sid in sorted(suites):
    old = suites[sid]
    p = os.path.join(REG, '_out', sid + '.txt')
    if not os.path.exists(p):
        missing.append(sid)
        continue
    with open(p, encoding='utf-8', newline='') as fh:
        raw = fh.read()
    sha = ra.sha256(ra.normalize(raw))
    if sha != old.get('sha256'):
        diffs.append(sid)

print('本次有原始输出的套件 =', len(suites) - len(missing))
print('缺原始输出 =', len(missing), missing[:10])
print()
print('=== DIFF 清单 ===')
if diffs:
    print('[FAIL] %d 个套件与基线不一致：%s' % (len(diffs), diffs))
    sys.exit(1)
print('[PASS] 全部套件 IDENTICAL（0 个 DIFF）')
