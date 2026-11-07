# -*- coding: utf-8 -*-
u"""第170轮：严格判定「哪些房间真的能按门实例精确映射」。

判定要三条同时成立（缺一条就不算）
----------------------------------
  ① 每条位置分支**恰好命中 1 个**实例（命中 0 个＝区间对不上；命中 ≥2 个＝分不开）
  ② 各分支命中的实例**互不相同**（同一扇门不可能同时去两个房间）
  ③ 分支数与实例数一致（多于分支的实例＝原作没给它路由，要单独记）

★ 为什么要 ②：第一版只看「每条命中 1 个」就把
  `room_dw_mansion_east_2f_d`（两条分支都是 `x > 1200`、房里只有 1 个实例）算成了
  「可完整映射」。**那其实是同一扇门去两个房间** —— 条件里必然还有一层
  运行状态（`plot` / `flag`），是我的 `pos` 分类没兜住。判据不自证就会假绿。
"""
import collections
import glob
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
SCENES = os.path.join(REPO, 'ralsei_pet', 'assets', 'scenes')
GML = os.path.join(ROUND, '_evidence', 'gml170.json')
OUT = os.path.join(ROUND, '_evidence', 'feasible170.json')


def jl(p):
    return json.loads(io.open(p, encoding='utf-8', errors='replace', newline='').read())


def in_range(v, b):
    lo, li, hi, hii = b['lo'], b['lo_incl'], b['hi'], b['hi_incl']
    if lo is not None:
        if li:
            if v < lo:
                return False
        elif v <= lo:
            return False
    if hi is not None:
        if hii:
            if v > hi:
                return False
        elif v >= hi:
            return False
    return True


def main():
    g = jl(GML)
    M = {}
    by_room = collections.defaultdict(dict)
    for f in glob.glob(os.path.join(SCENES, '_zone.*.json')):
        z = jl(f)
        ch = z.get('chapter_id') or ''
        s = z.get('scenes')
        it = (s.items() if isinstance(s, dict) else ((v.get('scene_id'), v) for v in s))
        for k, v in it:
            if not isinstance(v, dict):
                continue
            sid = v.get('scene_id') or k
            M[sid] = v.get('objects') or []
            if v.get('original_room_id') is not None:
                by_room[ch][v['original_room_id']] = sid

    rows = []
    for ch, chd in g['chapters'].items():
        for obj, d in chd.items():
            for room, v in sorted(d['rooms'].items()):
                brs = v['branches']
                if len(brs) < 2:
                    continue
                sid = (by_room.get(ch) or {}).get(v['room_id'])
                inst = [(i, (o.get('pos') or [None, None]))
                        for i, o in enumerate(M.get(sid) or []) if o.get('src') == obj]
                pos = [b for b in brs if b['kind'] in ('pos', 'pos_state')]
                detail = []
                for b in brs:
                    if b['kind'] not in ('pos', 'pos_state'):
                        detail.append({'to': b['to_id'], 'kind': b['kind'],
                                       'cond': b['cond'], 'hit': None})
                        continue
                    ax = 0 if b['axis'] == 'x' else 1
                    hit = [c[0] for c in inst
                           if c[1][ax] is not None and in_range(c[1][ax], b)]
                    detail.append({'to': b['to_id'], 'kind': b['kind'],
                                   'cond': b['cond'], 'axis': b['axis'],
                                   'lo': b['lo'], 'hi': b['hi'],
                                   'hit': hit})
                ok1 = all(len(x['hit']) == 1 for x in detail if x['hit'] is not None)
                # ★ 这里必须用真值判断而不是 `is not None`：命中 0 个时 `hit == []`，
                #   取 `[0]` 会越界（第一版就崩在这）。空列表本身就该让 ok1 变 False。
                hits = [x['hit'][0] for x in detail if x['hit']]
                ok2 = len(set(hits)) == len(hits) and bool(hits)
                ok3 = len(inst) == len(brs)
                any_state = any(x['kind'] not in ('pos', 'pos_state') for x in detail)
                if ok1 and ok2 and ok3 and not any_state:
                    tag = 'FULL'
                elif ok1 and ok2 and not any_state:
                    tag = 'NEAR'      # 实例数与分支数不等
                elif any_state:
                    tag = 'STATE'     # 同一房间混了运行状态分支
                else:
                    tag = 'BROKEN'
                rows.append({'tag': tag, 'ch': ch, 'obj': obj, 'room': room,
                             'sid': sid, 'n_branch': len(brs), 'n_inst': len(inst),
                             'detail': detail, 'ok1': ok1, 'ok2': ok2, 'ok3': ok3})

    c = collections.Counter(r['tag'] for r in rows)
    print(u'== 多分支房间共 %d 个 ==' % len(rows))
    for k in ('FULL', 'NEAR', 'STATE', 'BROKEN'):
        print(u'  %-7s %d' % (k, c.get(k, 0)))
    print()
    for tag in ('FULL', 'NEAR', 'STATE', 'BROKEN'):
        sub = [r for r in rows if r['tag'] == tag]
        if not sub:
            continue
        print(u'--- %s ---' % tag)
        for r in sub:
            print(u'  %-4s %-20s %-34s 实例%d 分支%d'
                  % (r['ch'], r['obj'], r['room'], r['n_inst'], r['n_branch']))
            for x in r['detail']:
                print(u'        %-40s hit=%r' % ((x['cond'] or '-')[:40], x['hit']))
        print()

    text = json.dumps({'stat': dict(c), 'rows': rows}, ensure_ascii=False, indent=1)
    io.open(OUT, 'wb').write(text.replace('\n', '\r\n').encode('utf-8'))
    print(u'落盘 %s (%d B)' % (OUT, os.path.getsize(OUT)))


if __name__ == '__main__':
    main()
