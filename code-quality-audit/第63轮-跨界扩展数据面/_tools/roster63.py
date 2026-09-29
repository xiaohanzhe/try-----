# -*- coding: utf-8 -*-
u"""第63轮附 · 人物设定「完整名单」核名（**只读**，不改任何东西）。

目的：上一版清单里混了素材内部代号（mkid / spiderb / mc / Pap / Napster / EN / AF …），
用户要求「说清楚、要完整的名字」。本脚本回原始数据取**原始素材名**，供人工对映正式全名。

三个数据源：
  ① OneShot  content/facepics/*.xnb + content/npc/*（真实文件名）
  ② outertale code-quality-audit/第63轮-跨界扩展数据面/_evidence/outertale63_assets.json（1,027 具名精灵）
  ③ Undertale / 黄魂  E:\\Download\\_extract61\\_data\\*\\ut*_objects.json + ut*_sprites.json

产出：_evidence/roster63.json（+ 打印可读清单）
"""
from __future__ import print_function

import io
import json
import os
import sys
from collections import OrderedDict

try:
    sys.stdout.reconfigure(encoding=u'utf-8', errors=u'replace')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
EVID = os.path.join(ROUND, u'_evidence')

OS_CONTENT = (u'C:\\Users\\23002\\Desktop\\项目文件夹\\niko的秘密\\'
              u'OneShot.World.Machine.Edition.Build.16512634\\content')
DATA = u'E:\\Download\\_extract61\\_data'


def ls(d):
    try:
        return sorted(os.listdir(d))
    except OSError:
        return []


# ------------------------------------------------------------------ ① OneShot
def oneshot():
    fp = os.path.join(OS_CONTENT, u'facepics')
    files = [f[:-4] for f in ls(fp) if f.lower().endswith(u'.xnb')]
    grp = OrderedDict()
    for f in files:
        head = f.split(u'_')[0]
        grp.setdefault(head, []).append(f)
    npc = [f[:-4] for f in ls(os.path.join(OS_CONTENT, u'npc'))
           if f.lower().endswith(u'.xnb')]
    return files, grp, npc


# --------------------------------------------------------------- ② outertale
def outertale():
    p = os.path.join(EVID, u'outertale63_assets.json')
    if not os.path.isfile(p):
        return [], {}
    d = json.load(io.open(p, encoding=u'utf-8'))
    top = d.get(u'entities_top') or []
    fam = d.get(u'entities') or {}
    return top, fam


# ------------------------------------------------- ③ Undertale / 黄魂 对象名
def gm(path):
    p = None
    for cand in (u'ut_objects.json', u'uty_objects.json'):
        q = os.path.join(path, cand)
        if os.path.isfile(q):
            p = q
            break
    if p is None:
        return [], []
    d = json.load(io.open(p, encoding=u'utf-8'))
    objs = d if isinstance(d, list) else (d.get(u'objects') or d.get(u'items') or [])
    names = []
    for o in objs:
        if isinstance(o, dict):
            n = o.get(u'name') or o.get(u'Name')
        else:
            n = o
        if isinstance(n, str):
            names.append(n)
    return names, sorted(set(names))


CHAR_HINT = (
    u'undyne asgore asriel papyrus sans alphys toriel mettaton monsterkid mkid '
    u'flowey napstablook muffet spiderb gaster icecap moldsmal astigmatism mewmew '
    u'strangeman grillby ripoff temmie riverperson bratty catty burgerpants '
    u'nicecream maddummy snowdrake lesserdog gyftrot froggit dummy chara frisk '
    u'martlet ceroba mo axis sousborg dalv starlo guardener chujin bowll feisty '
    u'frostermit insomnitot goosic ed jandroid decibat penilla clover chujin '
    u'dunebud cactony tellyvis ace angie macrofroggit'
).split()


def main():
    rep = {}

    print(u'=' * 78)
    print(u'① OneShot · content/facepics（%d 个 .xnb）' % len(oneshot()[0]))
    files, grp, npc = oneshot()
    print(u'   基础组 %d 个：' % len(grp))
    for k, v in grp.items():
        print(u'     %-16s %2d  %s' % (k, len(v), u', '.join(v)))
    print(u'   content/npc 条目 %d 个（角色用立绘之外的 NPC 贴图）' % len(npc))
    print(u'   npc 样本：%s' % u', '.join(npc[:40]))
    rep[u'oneshot'] = {u'facepics_total': len(files), u'groups': {k: v for k, v in grp.items()},
                       u'npc_total': len(npc), u'npc_sample': npc}

    print()
    print(u'=' * 78)
    top, fam = outertale()
    print(u'② outertale · entities_top（%d 条）' % len(top))
    for row in top[:90]:
        print(u'     %-16s %-5s %d' % (row[0], row[1], row[2]))
    rep[u'outertale_entities_top'] = top
    rep[u'outertale_entity_families'] = sorted(fam.keys())

    print()
    print(u'=' * 78)
    for tag, sub in ((u'undertale', u'undertale'), (u'undertale_yellow', u'undertale_yellow')):
        d = os.path.join(DATA, sub)
        names, uniq = gm(d)
        print(u'③ %s · ut_objects.json 共 %d 条，唯一名 %d' % (tag, len(names), len(uniq)))
        for toast in CHAR_HINT:
            hit = [n for n in uniq if toast in n.lower()]
            if hit:
                print(u'     %-14s -> %s' % (toast, u', '.join(hit[:12])))
        rep[tag] = {u'objects_total': len(names), u'unique_total': len(uniq)}

    if not os.path.isdir(EVID):
        os.makedirs(EVID)
    p = os.path.join(EVID, u'roster63.json')
    with io.open(p, u'w', encoding=u'utf-8') as fh:
        fh.write(json.dumps(rep, ensure_ascii=False, indent=1))
    print()
    print(u'证据 -> %s' % p)
    return 0


if __name__ == u'__main__':
    raise SystemExit(main())
