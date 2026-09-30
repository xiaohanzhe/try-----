# -*- coding: utf-8 -*-
"""核对清单文里引用的"现状数字"，逐个真数（不抄记忆）。"""
import io, json, os

ROOT = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
PET = os.path.join(ROOT, 'ralsei_pet')

reg = json.load(io.open(os.path.join(PET, 'assets', 'npc', '_registry.json'), encoding='utf-8'))


def count_npcs(o):
    if isinstance(o, dict):
        for k in ('npcs', 'npcs_list', 'entries'):
            if k in o and isinstance(o[k], list):
                return len(o[k])
        # 兜底：数形如 npc 记录的 dict
        n = 0
        for v in o.values():
            if isinstance(v, list):
                for x in v:
                    if isinstance(x, dict) and ('id' in x or 'name' in x):
                        n += 1
            elif isinstance(v, dict) and ('id' in v or 'name' in v):
                n += 1
        return n
    if isinstance(o, list):
        return len(o)
    return -1


print('registry 顶层键 =', list(reg.keys())[:8] if isinstance(reg, dict) else type(reg))
print('NPC 条数 =', count_npcs(reg))

pdir = os.path.join(PET, 'assets', 'npc', 'persona')
txt = [f for f in os.listdir(pdir) if f.endswith('.txt')]
print('persona/*.txt =', len(txt))

idx = json.load(io.open(os.path.join(PET, 'assets', 'npc', '_personas.json'), encoding='utf-8'))
n_idx = len(idx.get('personas', idx)) if isinstance(idx, dict) else len(idx)
print('_personas.json 条数 =', n_idx)

sp = os.path.join(PET, 'assets', 'sprites')
png = 0
for dp, dn, fn in os.walk(sp):
    png += sum(1 for f in fn if f.lower().endswith('.png'))
print('assets/sprites/**/*.png =', png)
for d in sorted(os.listdir(sp)):
    p = os.path.join(sp, d)
    if os.path.isdir(p):
        c = sum(1 for f in os.listdir(p) if f.lower().endswith('.png'))
        print('   %-8s %d png' % (d, c))
