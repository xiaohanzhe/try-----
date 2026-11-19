# -*- coding: utf-8 -*-
"""第200轮 · 生成"拼版"任务书（本地，只读）

产物 `_evidence/sheet_plan.json`：每人一条 `{id, work, files:[...]}`，
交给 Mac 端渲染成一张拼版 PNG（4 列网格 + 文件名 + 真实像素尺寸）。

为什么不在本地渲染：这活是纯图像 IO + 缩放，放到 Mac 上做**本地就不用占 CPU
跑回归**；而且 Mac 是独立机器，它的解码结果与本地不一致时能立刻发现（与冷备
那条"独立校验"同一个道理）。
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
SPR = os.path.join(ROOT, 'ralsei_pet', 'assets', 'sprites')
OUT = os.path.join(ROUND, '_evidence', 'sheet_plan.json')
COV = os.path.join(ROUND, '_evidence', 'coverage200.json')


def main():
    cov = json.loads(io.open(COV, encoding='utf-8').read())
    plan = []
    for it in cov:
        if not it['frames']:
            continue
        w, i = it['work'], it['id']
        d = os.path.join(SPR, w)
        if not os.path.isdir(d):
            continue
        base = i.split('_', 1)[1] if '_' in i else i
        cand = [n for n in sorted(os.listdir(d)) if base.lower() in n.lower()]
        if not cand and '_' in base:
            b2 = base.split('_')[0]
            cand = [n for n in sorted(os.listdir(d)) if b2.lower() in n.lower()]
        if cand:
            plan.append({'id': i, 'work': w, 'files': cand})
    with io.open(OUT, 'w', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(plan, ensure_ascii=False, indent=1))
    print('拼版任务 %d 条 → %s' % (len(plan), OUT))
    for p in plan[:3]:
        print('  %-22s %2d 张  %s' % (p['id'], len(p['files']), p['files'][0]))


if __name__ == '__main__':
    sys.exit(main())
