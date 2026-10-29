# -*- coding: utf-8 -*-
u"""第119轮 · 独立审计：现有正文表里的每条键，**是不是这间房**的键

## 为什么非查不可

`_readable_text.json` 是第117轮由 `readable_bind.tsv`（指令流侧的房间**下标**）映射来的。
映射链有两段可能出错且**都不报错**：
  · 指令流侧：房间守卫取成别的房间的整数（`pending` 只被"下一个 Push 字符串"消费一次）
  · 场景侧：`original_room_id → scene_id` 撞号只取第一个
一旦错位，正文会**安静地**绑到隔壁房间的可读物上 —— 看起来"有正文"，实际读的是别人的。

本脚本不重算任何一条绑定，只做对账：
    表的键集合  ?=  GML 原文里该 (房间, 对象) 的键集合

## 三种结论（互斥）

    OK        两边完全一致
    EXTRA     表里有、GML 里没有 ⇒ **污染**（高危，必须归因）
    MISSING   GML 里有、表里没有 ⇒ 漏收（多为同一组合的多条分支，属已知的"第二层守卫"）

★ 分母闸：两边都为空时**不算通过**（一个组合都没比 ⇒ 本脚本什么也没证明）。
"""
import collections
import glob
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.normpath(os.path.join(HERE, '..'))
ROOT = os.path.normpath(os.path.join(ROUND, '..', '..'))
EV = os.path.join(ROUND, '_evidence')
RAW = os.path.join(EV, 'raw')
SCENES = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes')

GAMES = ('ut', 'outertale')
ALARM_OBJ = re.compile(r'^gml_Object_(.+)_Alarm_0$')
RE_ROOM = re.compile(r'^room\s*==\s*(\w+)$')


def gml_keys(game):
    """(room, obj) -> set(keys)（只取 GML 侧的房间名，不碰下标）"""
    p = os.path.join(EV, 'readable_conds118.%s.tsv' % game)
    out = collections.defaultdict(set)
    for ln in io.open(p, encoding='utf-8'):
        q = ln.rstrip('\n').split('\t')
        if len(q) != 5 or q[0] == 'alarm':
            continue
        alarm, _d, cond, _t, key = q
        m = ALARM_OBJ.match(alarm)
        if not m:
            continue
        room = None
        for tok in (cond.split(' && ') if cond else []):
            mr = RE_ROOM.match(tok.strip())
            if mr:
                room = mr.group(1)
                break
        if room:
            out[(room, m.group(1))].add(key)
    return out


def oid_maps(game):
    """(name -> oid, oid -> scene_id)"""
    name_oid = {}
    for ln in io.open(os.path.join(RAW, game, 'inst_full.tsv'), encoding='utf-8'):
        q = ln.rstrip('\n').split('\t')
        if q[0] == 'R':
            name_oid[q[2]] = int(q[1])
    oid_sid = {}
    for p in sorted(glob.glob(os.path.join(SCENES, '_zone.%s.*.json' % game))):
        try:
            d = json.load(io.open(p, encoding='utf-8'))['scenes']
        except Exception:
            continue
        for sid, s in d.items():
            oid = s.get('original_room_id')
            if isinstance(oid, int):
                oid_sid.setdefault(oid, sid)
    return name_oid, oid_sid


def table_entries():
    d = json.load(io.open(os.path.join(SCENES, '_readable_text.json'),
                         encoding='utf-8'))['by_scene']
    out = collections.defaultdict(set)
    for sid, entries in d.items():
        for e in entries or ():
            if isinstance(e, dict) and e.get('obj') and e.get('key'):
                out[(sid, e['obj'])].add(e['key'])
    return out


def main():
    tab = table_entries()
    bad = 0
    for game in GAMES:
        gk = gml_keys(game)
        name_oid, oid_sid = oid_maps(game)
        # GML 侧 (scene, obj) -> keys
        g_by_sid = collections.defaultdict(set)
        no_scene = 0
        for (room, obj), ks in gk.items():
            oid = name_oid.get(room)
            sid = oid_sid.get(oid) if oid is not None else None
            if sid is None:
                no_scene += 1
                continue
            g_by_sid[(sid, obj)] |= ks
        t_by_sid = {(sid, obj): ks for (sid, obj), ks in tab.items()
                    if sid.startswith(game + '.')}

        both = set(g_by_sid) & set(t_by_sid)
        stat = collections.Counter()
        extras = []
        missings = []
        for gk2 in sorted(both):
            g, t = g_by_sid[gk2], t_by_sid[gk2]
            stat['compared'] += 1
            if g == t:
                stat['ok'] += 1
            if t - g:
                stat['extra'] += 1
                extras.append((gk2[0], gk2[1], sorted(t - g)))
            if g - t:
                stat['missing'] += 1
                missings.append((gk2[0], gk2[1], sorted(g - t)))
        only_t = set(t_by_sid) - set(g_by_sid)
        stat['only_table'] = len(only_t)
        stat['only_gml'] = len(set(g_by_sid) - set(t_by_sid))

        print(u'=== %s：可比组合 %d（表 %d / GML %d）'
              % (game, stat['compared'], len(t_by_sid), len(g_by_sid)))
        print(u'    完全一致 %d / 表里多出 %d / 表里缺少 %d / 只在表 %d / 只在 GML %d / GML 侧无场景 %d'
              % (stat['ok'], stat['extra'], stat['missing'],
                 stat['only_table'], stat['only_gml'], no_scene))
        for sid, obj, ks in extras[:15]:
            print(u'    [EXTRA]   %-42s %-24s %s' % (sid, obj, u','.join(ks)))
        for sid, obj, ks in missings[:10]:
            print(u'    [MISSING] %-42s %-24s %s' % (sid, obj, u','.join(ks)))

        if not both:
            print(u'[FAIL] %s 可比组合为 0 —— 本脚本什么也没证明' % game)
            return 1
        bad += stat['extra']

    print(u'\n合计：表里多出（污染）= %d 组' % bad)
    return 0


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.exit(main())
