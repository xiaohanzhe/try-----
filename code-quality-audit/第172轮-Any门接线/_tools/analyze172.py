# -*- coding: utf-8 -*-
"""第172轮 · obj_doorAny 分类 + 产品侧对账（**只读，不落边**）。

★★ 解析口径（本轮定死，别事后改）：
  源房 = 探针里的 `room_index`（= `Data.Rooms` 下标）→ 产品 `original_room_id`
         （★ ch2 实测 26 一致 / 0 冲突，名字对账只作副证）
  目标 = PreCreate 里的 `doorRoom = room_xxx` 字面量 → 同章房间名表取 index → 同上映射

五类：
  static_dst_ok        字面量目标 + 目标房**是**已登记场景
  static_dst_unmapped  字面量目标，但目标房没登记成场景（属"场景抽取"那条线）
  relative_debug       无字面量、image_index ∈ 1..6 ⇒ Step_0 走 `room ± debug房`
  unknown_no_code      无字面量、无 PreCreate 代码、image_index = 0
  unknown_code_only    有 PreCreate 代码但里面没 doorRoom
另记 `src_unmapped`：源房本身没登记成场景（这些**不能**入边）。
"""
import io
import json
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
EV = os.path.join(ROUND, '_evidence')
SCENES = os.path.join(REPO, 'ralsei_pet', 'assets', 'scenes')
OUT = os.path.join(EV, 'analyze172.json')

CHS = ['ch1', 'ch2', 'ch3', 'ch4', 'ch5']
RE_DOORROOM = re.compile(r'doorRoom\s*=\s*([A-Za-z_][A-Za-z_0-9]*)\s*;')
KINDS = ['static_dst_ok', 'static_dst_unmapped', 'relative_debug',
         'unknown_no_code', 'unknown_code_only']


def jl(p):
    with io.open(p, 'r', encoding='utf-8') as f:
        return json.load(f)


def build_maps():
    """每章两张表：id→sid（主）、name_raw→sid（副）"""
    idx = jl(os.path.join(SCENES, '_index.json'))
    by_id, by_name = {}, {}
    for ch, node in (idx.get('chapters') or {}).items():
        m_id, m_nm = {}, {}
        for area, anode in (node.get('areas') or {}).items():
            for sid, s in (anode.get('scenes') or {}).items():
                s = s or {}
                rid = s.get('original_room_id')
                if isinstance(rid, int):
                    m_id[rid] = sid
                raw = s.get('name_raw')
                if raw:
                    m_nm[raw] = sid
        by_id[ch], by_name[ch] = m_id, m_nm
    return by_id, by_name


def main():
    by_id, by_name = build_maps()
    routes = jl(os.path.join(SCENES, '_routes.json'))
    rl = routes.get('routes') if isinstance(routes, dict) else routes
    have_pairs, have_src = set(), set()
    for r in rl:
        sc = r.get('when_scene')
        if sc:
            have_src.add(sc)
            if r.get('to'):
                have_pairs.add((sc, r.get('to')))

    rows, per_ch = [], {}
    stat = dict((k, 0) for k in KINDS)
    n_src_unmapped = 0
    name_conflict = []
    for ch in CHS:
        p = os.path.join(EV, 'probe_any172.%s.json' % ch)
        if not os.path.exists(p):
            continue
        d = jl(p)
        rid2name = dict((r['index'], r['name']) for r in (d.get('rooms') or []))
        name2rid = dict((r['name'], r['index']) for r in (d.get('rooms') or []))
        m_id = by_id.get(ch) or {}
        m_nm = by_name.get(ch) or {}
        cnt = dict(inst=0, src_unmapped=0, **dict((k, 0) for k in KINDS))
        for i in d.get('instances') or []:
            cnt['inst'] += 1
            ri = i.get('room_index')
            rn = i.get('room')
            src = m_id.get(ri)
            src_how = 'id'
            if not src:
                src = m_nm.get(rn)
                src_how = 'name'
            # 副证：name_raw 与房间名必须一致（对得上才敢用 id 口径）
            if src and rn and m_nm.get(rn) and m_nm.get(rn) != src:
                name_conflict.append((ch, ri, rn, src, m_nm.get(rn)))
            g = i.get('creation_gml') or ''
            m = RE_DOORROOM.search(g)
            tgt = m.group(1) if m else None
            idxv = i.get('image_index')
            dst = None
            if tgt:
                trid = name2rid.get(tgt)
                dst = m_id.get(trid) if isinstance(trid, int) else None
                if not dst:
                    dst = m_nm.get(tgt)
                kind = 'static_dst_ok' if dst else 'static_dst_unmapped'
            elif idxv not in (None, 0, '0'):
                kind = 'relative_debug'
            elif i.get('creation_code'):
                kind = 'unknown_code_only'
            else:
                kind = 'unknown_no_code'
            if not src:
                cnt['src_unmapped'] += 1
                n_src_unmapped += 1
            stat[kind] += 1
            cnt[kind] += 1
            rows.append(dict(ch=ch, room=rn, room_index=ri, src=src, src_how=src_how,
                             x=i.get('x'), y=i.get('y'), image_index=idxv,
                             code=i.get('creation_code'), doorroom=tgt,
                             dst=dst, kind=kind))
        per_ch[ch] = cnt

    cand = {}
    for r in rows:
        if r['kind'] != 'static_dst_ok' or not r['src']:
            continue
        k = (r['src'], r['dst'])
        cand[k] = cand.get(k, 0) + 1
    new_pairs = dict((k, v) for k, v in cand.items() if k not in have_pairs)
    dup_pairs = dict((k, v) for k, v in cand.items() if k in have_pairs)
    only_any_src = sorted(set(r['src'] for r in rows
                              if r['kind'] == 'static_dst_ok' and r['src']
                              and r['src'] not in have_src))

    # ---- A/B 锚点：ch2 两路取数逐条相等 ----
    ab = None
    p5 = os.path.join(EV, 'probe5_172.ch2.json')
    if os.path.exists(p5):
        b = jl(p5)
        B = {}
        for x in b.get('roomcc') or []:
            mm = RE_DOORROOM.search(x.get('lines') or '')
            if mm:
                B[x['code']] = mm.group(1)
        A = dict((r['code'], r['doorroom']) for r in rows
                 if r['ch'] == 'ch2' and r['code'] and r['doorroom'])
        diff = [(k, A.get(k), B.get(k)) for k in set(A) | set(B) if A.get(k) != B.get(k)]
        ab = dict(nA=len(A), nB=len(B), diff=diff)

    out = dict(per_ch=per_ch, total=stat, n_rows=len(rows),
               n_src_unmapped=n_src_unmapped, name_conflict=name_conflict,
               n_cand_pairs=len(cand), n_new_pairs=len(new_pairs),
               n_dup_pairs=len(dup_pairs), only_any_src=only_any_src,
               ab_ch2=ab, rows=rows,
               new_pairs=sorted('%s -> %s' % k for k in new_pairs),
               dup_pairs=sorted('%s -> %s' % k for k in dup_pairs))
    with io.open(OUT, 'w', encoding='utf-8', newline='') as f:
        f.write(json.dumps(out, ensure_ascii=False, indent=1))

    print('== 逐章（扇数）==')
    for ch, c in per_ch.items():
        print('  %-4s inst=%-4d ok=%-4d unmapped=%-4d debug_rel=%-2d unk(code)=%-2d unk(nocode)=%-2d src_unmapped=%d'
              % (ch, c['inst'], c['static_dst_ok'], c['static_dst_unmapped'],
                 c['relative_debug'], c['unknown_code_only'], c['unknown_no_code'],
                 c['src_unmapped']))
    print('== 合计 ==')
    print('  ' + '  '.join('%s=%d' % (k, stat[k]) for k in KINDS))
    print('  扇数=%d | 源房未登记=%d | 名字冲突=%d'
          % (len(rows), n_src_unmapped, len(name_conflict)))
    print('  候选边(去重，源已登记) = %d | 新边 = %d | 已存在 = %d'
          % (len(cand), len(new_pairs), len(dup_pairs)))
    print('  现有表里一条出边都没有、只能靠 Any 门出去的场景 = %d' % len(only_any_src))
    if ab:
        print('== A/B（ch2：实例属性读 vs 全局扫 RoomCC）==  A=%d B=%d 差=%d %r'
              % (ab['nA'], ab['nB'], len(ab['diff']), ab['diff'][:5]))
    print('out = %s (%d B)' % (OUT, os.path.getsize(OUT)))


if __name__ == '__main__':
    main()
