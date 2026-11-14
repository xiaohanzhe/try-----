# -*- coding: utf-8 -*-
"""看一眼 raw30 里 48 轮基线到底存在不存在（只读）。"""
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
EVID = os.path.join(ROOT, 'code-quality-audit', '第113轮-全体角色AI训练', '_evidence')
RAW = os.path.join(EVID, 'raw30')

for fid in ('hy_martlet', 'hy_ace', 'os_niko'):
    p = os.path.join(RAW, fid + '.jsonl')
    if not os.path.isfile(p):
        print('%-14s 缺文件' % fid)
        continue
    rows = []
    rec48 = None
    for line in io.open(p, encoding='utf-8', errors='replace'):
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            rows.append(('<parse-fail>', None))
            continue
        rows.append((r.get('turns_n'), len(r.get('turns') or [])))
        if r.get('turns_n') == 48:
            rec48 = r
    print('%-14s %d 条记录：%r' % (fid, len(rows), rows))
    if rec48:
        t0 = (rec48.get('turns') or [None])[0]
        print('    顶层键 %r' % sorted(rec48.keys()))
        print('    turn[0] 键 %r' % (sorted(t0.keys()) if isinstance(t0, dict) else t0))
        if isinstance(t0, dict):
            for k, v in t0.items():
                s = repr(v)
                print('      %-12s %s' % (k, s[:90]))
