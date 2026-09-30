# -*- coding: utf-8 -*-
"""探针：对 _index.json 真跑 npc_life.scene_traits，**两套口径**分别给出数字。

  L（松口径）= 任何带 'file' **或** 'name' 的节点键 —— 第73轮 check73 实际用的口径，
                会把章名/区域名一起收进来（更严，但"场景 id"这个词就名不副实）。
  P（精确）  = 住在 areas[*].scenes 里的键 + 自带 file 的锚点键 = 真场景。

用途：把报告/日志里的数字钉在"产物输出"上；并量化松口径多跑了什么、多算了几分。
"""
import os, io, json, sys, collections

HERE = os.path.dirname(os.path.abspath(__file__))
PET = os.path.join(HERE, '..', '..', '..', 'ralsei_pet')
sys.path.insert(0, PET)

from modules import npc_life as L  # noqa: E402

INDEX = os.path.join(PET, 'assets', 'scenes', '_index.json')


def load_sets():
    d = json.load(io.open(INDEX, encoding='utf-8'))
    ch = d.get('chapters') or {}
    scenes, areas, loose = set(), set(), set()

    def _walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if isinstance(v, dict):
                    if isinstance(v.get('scenes'), dict):
                        areas.add(k)
                        scenes.update(v['scenes'].keys())
                    if 'file' in v:
                        scenes.add(k)
                    if 'file' in v or 'name' in v:
                        loose.add(k)
                    _walk(v)
                elif isinstance(v, list):
                    _walk(v)
        elif isinstance(o, list):
            for x in o:
                _walk(x)
    _walk(ch)
    return sorted(scenes), set(ch.keys()), areas, sorted(loose)


def stats(ids):
    per_trait = collections.Counter()
    per_token = collections.Counter()
    none = 0
    for sid in ids:
        tr = L.scene_traits(sid)
        if not tr:
            none += 1
        for t in set(tr):
            per_trait[t] += 1
        for _t, ws in L.trait_hits(sid).items():
            for w in ws:
                per_token[w] += 1
    return per_trait, per_token, none


def main():
    scenes, chk, areas, loose = load_sets()
    print('真场景(精确) =', len(scenes))
    print('章键 =', len(chk), '区域键 =', len(areas))
    print('松口径 =', len(loose), ' 差集 =', len(set(loose) - set(scenes)))
    print('松口径差集是否全为章/区域名 =', (set(loose) - set(scenes)) <= (chk | areas))
    ev = {'scene_count': len(scenes), 'chapter_keys': len(chk),
          'area_keys': len(areas), 'loose_count': len(loose),
          'loose_minus_scenes_all_names': bool(
              (set(loose) - set(scenes)) <= (chk | areas))}
    for tag, ids in (('precise', scenes), ('loose', loose)):
        pt, pk, none = stats(ids)
        print('=' * 60)
        print('[%s] n=%d 无特质=%d' % (tag, len(ids), none))
        print('  每特质命中场景数:', {t: pt.get(t, 0) for t in L.TRAITS})
        print('  每令牌命中场景数:')
        for t in L.TRAITS:
            for tk in L.TRAIT_TOKENS.get(t, ()):
                print('    %-9s %-10s %d' % (t, tk, pk.get(tk, 0)))
        ev[tag] = {'n': len(ids), 'no_trait': none,
                   'per_trait': {t: pt.get(t, 0) for t in L.TRAITS},
                   'per_token': {tk: pk.get(tk, 0)
                                 for t in L.TRAITS
                                 for tk in L.TRAIT_TOKENS.get(t, ())}}
    #: 预留令牌在现网是否 0 命中（如实的另一半）
    res_only = collections.Counter()
    for sid in scenes:
        for t in set(L.scene_traits(sid, use_reserved=True)) - set(L.scene_traits(sid)):
            res_only[t] += 1
    ev['reserved_only_hits'] = dict(res_only)
    print('=' * 60)
    print('预留令牌在现网新增命中 =', dict(res_only) or '(无)')
    if '--write' in sys.argv:
        out = os.path.join(HERE, '..', '_evidence', 'probe73_traits.json')
        with io.open(out, 'w', encoding='utf-8', newline='\n') as fh:
            json.dump(ev, fh, ensure_ascii=False, indent=1)
            fh.write('\n')
        print('written:', os.path.abspath(out))


if __name__ == '__main__':
    main()
