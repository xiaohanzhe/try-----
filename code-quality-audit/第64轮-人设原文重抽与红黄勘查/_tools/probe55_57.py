# -*- coding: utf-8 -*-
"""第64轮 · 为 case B（np_55 / mc_57 判据改写）取实测真值。

只读。回答四件事：
  Q1 人设字数的真实分布（决定 A9 区间怎么写才有鉴别力）
  Q2 索引 id ↔ file basename 是否同构（决定 P2 能不能写成不变式）
  Q3 注册表 persona 路径的形态（决定 R6/A8 的不变式怎么写）
  Q4 当前"确实没装设定"的 id 有哪些（决定 P9/W20/W22 换成谁）
"""
import io
import json
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
NPC = os.path.join(PET, 'assets', 'npc')
PDIR = os.path.join(NPC, 'persona')


def rj(p, d=None):
    try:
        with io.open(p, 'r', encoding='utf-8') as fh:
            return json.loads(fh.read())
    except Exception:
        return d


def rt(p):
    with io.open(p, 'r', encoding='utf-8') as fh:
        return fh.read()


print('=' * 70)
idx = rj(os.path.join(NPC, '_personas.json')) or {}
recs = idx.get('personas') or []
print('Q1 人设字数分布（索引登记 %d 份）' % len(recs))
lens = []
for r in recs:
    fp = os.path.join(PDIR, os.path.basename(r.get('file') or ''))
    if os.path.isfile(fp):
        lens.append((len(rt(fp)), r['id']))
lens.sort()
print('   最小 5 个: %r' % [(n, i) for n, i in lens[:5]])
print('   最大 5 个: %r' % [(n, i) for n, i in lens[-5:]])
vals = [n for n, _ in lens]
print('   n=%d min=%d max=%d avg=%d 中位=%d'
      % (len(vals), min(vals), max(vals), sum(vals) // len(vals),
         vals[len(vals) // 2]))
print('   落在 2000~9000 之外的: %r' % [(n, i) for n, i in lens if not (2000 <= n <= 9000)])
print('   落在 2000~12000 之外的: %r' % [(n, i) for n, i in lens if not (2000 <= n <= 12000)])
print('   < 2500 的: %r' % [(n, i) for n, i in lens if n < 2500])

print()
print('Q2 索引 id ↔ file basename 同构性')
bad = []
for r in recs:
    fn = os.path.basename(r.get('file') or '')
    stem = fn[:-4] if fn.endswith('.txt') else fn
    if stem != r['id']:
        bad.append((r['id'], fn))
print('   不同构的: %r' % bad)
print('   id 唯一? %s' % (len({r['id'] for r in recs}) == len(recs)))
print('   file 唯一? %s' % (len({os.path.basename(r.get('file') or '') for r in recs}) == len(recs)))
print('   persona 目录里的 .txt 文件数 = %d，索引登记 %d'
      % (len([f for f in os.listdir(PDIR) if f.endswith('.txt')]), len(recs)))
_disk = {f for f in os.listdir(PDIR) if f.endswith('.txt')}
_idx = {os.path.basename(r.get('file') or '') for r in recs}
print('   磁盘有索引没登记: %r' % sorted(_disk - _idx))
print('   索引登记磁盘没有: %r' % sorted(_idx - _disk))

print()
print('Q3 注册表 persona 形态')
reg = rj(os.path.join(NPC, '_registry.json')) or {}
npcs = reg.get('npcs') or []
with_p = [(n.get('id'), n.get('persona')) for n in npcs if n.get('persona')]
print('   persona 非空 %d 条' % len(with_p))
for i, p in with_p:
    print('     %-20s %r' % (i, p))

print()
print('Q4 当前"没装设定"的 id')
no_p = [n.get('id') for n in npcs if not n.get('persona')]
print('   注册表无 persona %d 条: %r' % (len(no_p), no_p))
need = [n.get('id') for n in npcs if n.get('needs_setting')]
print('   needs_setting %d 条: %r' % (len(need), need))
print()
print('   候选"必定未装人设"的 id：')
for c in ('knight', '__no_such_npc__', 'mike', 'spamton'):
    inidx = any(r['id'] == c for r in recs)
    inreg = any(n.get('id') == c for n in npcs)
    print('     %-20s 索引有=%s 注册表有=%s' % (c, inidx, inreg))
