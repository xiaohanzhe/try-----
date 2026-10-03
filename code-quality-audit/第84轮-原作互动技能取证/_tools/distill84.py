# -*- coding: utf-8 -*-
u"""第84轮 · 把 dr_*.json 蒸馏成可核对的「原作互动技能清单」（落进仓库 _evidence/）。

输入（UTMT 反编译产物）：copytarget 目录里的 dr_objects.json / dr_code.json / dr_scripts.json
输出：_evidence/dr84_*.txt/md（仓库内，可长期复核）
"""
from __future__ import print_function
import io, json, os, re, sys

SRC = u'E:\\Download\\_tmp84c\\_data'
HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
EV = os.path.join(ROUND, u'_evidence')


def rd(name):
    p = os.path.join(SRC, name)
    with io.open(p, u'r', encoding=u'utf-8') as fh:
        return json.load(fh)


def w(name, txt):
    if not os.path.isdir(EV):
        os.makedirs(EV)
    p = os.path.join(EV, name)
    with io.open(p, u'w', encoding=u'utf-8', newline=u'\n') as fh:
        fh.write(txt)
    print(u'  wrote %8d B  %s' % (os.path.getsize(p), name))


def w_json(name, obj):
    u"""原样搬一份 JSON 进仓库（铁律：不依赖外部盘）。"""
    if not os.path.isdir(EV):
        os.makedirs(EV)
    p = os.path.join(EV, name)
    with io.open(p, u'w', encoding=u'utf-8', newline=u'\n') as fh:
        fh.write(json.dumps(obj, ensure_ascii=False, separators=(u',', u':')))
    print(u'  wrote %8d B  %s  (raw)' % (os.path.getsize(p), name))


def main():
    obj = rd(u'dr_objects.json')
    code = rd(u'dr_code.json')
    scr = rd(u'dr_scripts.json')
    print(u'[in] objects=%d codes=%d scripts=%d'
          % (len(obj[u'objects']), code[u'code_count'], len(scr[u'scripts'])))

    # ---- 1. 全量对象表（TSV，便于 grep）
    lines = [u'# Deltarune ch1 · 交互相关对象全量（name\ti\tsprite\tparent\tn_events）',
             u'# 源：chapter1_windows/data.win (14,658,588 B)，UTMT CLI v0.9.2.0',
             u'']
    for o in obj[u'objects']:
        lines.append(u'%s\t%d\t%s\t%s\t%d' % (
            o[u'name'], o[u'i'], o[u'sprite'], o[u'parent'], o[u'n_events']))
    w(u'dr84_objects_all.tsv', u'\n'.join(lines) + u'\n')

    # ---- 2. 全量脚本名
    w(u'dr84_scripts_all.txt',
      u'\n'.join(scr[u'scripts']) + u'\n')

    # ---- 3. 代码全量（分段，便于 Read）
    parts = []
    for c in code[u'codes']:
        parts.append(u'\n' + u'=' * 78)
        parts.append(u'### %s   (%d chars)' % (c[u'name'], c[u'len']))
        parts.append(u'=' * 78)
        parts.append(c[u'src'])
    w(u'dr84_code_dump.txt', u'\n'.join(parts) + u'\n')

    # ---- 4. 关键锚点：grep interact / myinteract
    hits = []
    for c in code[u'codes']:
        if u'interact' in c[u'src'].lower():
            hits.append(c[u'name'])
    w(u'dr84_interact_codes.txt',
      u'\n'.join(sorted(hits)) + u'\n')

    # ---- 4b. ★★ 三份原始产物也进仓库（铁律：回归套件不许依赖 E 盘临时区）
    w_json(u'dr_objects.json', obj)
    w_json(u'dr_code.json', code)
    w_json(u'dr_scripts.json', scr)

    # ---- 5. 脚本名分类
    cat = {}
    for s in scr[u'scripts']:
        low = s.lower()
        for k, pat in (
            (u'interact', u'interact'), (u'depth', u'depth'), (u'npc', u'npc'),
            (u'talk', u'talk'), (u'caterpillar', u'caterpillar'),
            (u'chara', u'chara'), (u'door', u'door'), (u'save', u'save'),
            (u'item', u'item'), (u'menu', u'menu'), (u'party', u'party'),
        ):
            if pat in low:
                cat.setdefault(k, []).append(s)
    out = [u'# Deltarune ch1 · scr_* 名字分类（131 条）', u'']
    for k in sorted(cat):
        out.append(u'## %s (%d)' % (k, len(cat[k])))
        for s in cat[k]:
            out.append(u'  ' + s)
        out.append(u'')
    w(u'dr84_scripts_cat.md', u'\n'.join(out) + u'\n')

    print(u'[ok] 5 份 evidence 落盘 -> %s' % EV)
    return 0


if __name__ == u'__main__':
    sys.exit(main())
