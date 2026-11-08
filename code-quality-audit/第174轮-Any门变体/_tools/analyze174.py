# -*- coding: utf-8 -*-
u"""第174轮 · `obj_doorAnyHorz` / `obj_doorAnyVert` 分类 + 与产品侧对账（**只读，不落边**）。

为什么这一轮不需要重跑 UTMT
--------------------------
第173轮的记忆里写着"Horz/Vert 没有既有取证"——**那是错的**。第172轮探针
`probe_any172.csx` 的对象过滤是**子串** `doorany`：

    if (on.ToLowerInvariant().IndexOf("doorany") < 0) continue;

`obj_doorAnyHorz` / `obj_doorAnyVert` / `obj_doorAnyModespecific` 的名字里都含
`doorany` ⇒ **四个变体的实例全部被录进** `probe_any172.ch5.json` 的 `instances`，
每条都带自己的 `creation_gml`（= `gml_RoomCC_<房>_<n>_PreCreate` 反编译）。
`analyze172.json` 里 `via` 全 None 只是**分析脚本没把 `obj` 字段带进 rows**，
不是探针没采到（881 = 830 + 42 + 9，一条不少）。

本脚本就是把那 51 条（42 + 9）捡出来，按第172轮同一套口径分类。

★★ 解析口径（沿用第172轮，不许事后改）
  源房 = 探针里的 `room_index`（= `Data.Rooms` 下标）→ 产品 `_index.json` 的
         `original_room_id` 反查出的 scene_id
  目标 = `PreCreate` 里的 `doorRoom = room_xxx` 字面量 → 同章房间名表取 index → 同上

五类（与 172 完全一致）：
  static_dst_ok        字面量目标 + 目标房**是**已登记场景
  static_dst_unmapped  字面量目标，但目标房没登记成场景
  relative_debug       无字面量、image_index ∈ 1..6 ⇒ Step_0 走 `room ± debug房`
  unknown_no_code      无字面量、无 PreCreate 代码、image_index = 0
  unknown_code_only    有 PreCreate 代码但里面没 doorRoom

★ A/B 锚点（两个**独立**读取路径互证，缺一不许开工）
  A = 第172轮 csx 探针（`probe_any172.ch5.json`，走 UTMT 对象模型读实例）
  B = 第42轮 CLI 普查（`ch5_inst42.json`，走另一条导出链）
  ⟹ 逐变体的 `{(room_index, x, y)}` 集合必须**完全相等**。

产物: `第174轮-Any门变体/_evidence/analyze174.json`
"""
import collections
import io
import json
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
SCENES = os.path.join(REPO, 'ralsei_pet', 'assets', 'scenes')
E172 = os.path.join(REPO, 'code-quality-audit', u'第172轮-Any门接线', '_evidence')
E42 = os.path.join(REPO, 'code-quality-audit', u'第42轮-原作拓扑取证', '_evidence')
OUT = os.path.join(ROUND, '_evidence', 'analyze174.json')

CHS = ['ch1', 'ch2', 'ch3', 'ch4', 'ch5']
#: 本轮的对象名（★ 与 173 的 `obj_doorAny` 互斥；`Modespecific` 只在对象表里有）
VARIANTS = ('obj_doorAnyHorz', 'obj_doorAnyVert', 'obj_doorAnyModespecific')
RE_DOORROOM = re.compile(r'doorRoom\s*=\s*([A-Za-z_][A-Za-z_0-9]*)\s*;')
KINDS = ['static_dst_ok', 'static_dst_unmapped', 'relative_debug',
         'unknown_no_code', 'unknown_code_only']
INST42 = {'ch1': 'inst42.json', 'ch2': 'ch2_inst42.json', 'ch3': 'ch3_inst42.json',
          'ch4': 'ch4_inst42.json', 'ch5': 'ch5_inst42.json'}


def jl(p):
    with io.open(p, 'r', encoding='utf-8') as f:
        return json.load(f)


def build_maps():
    """每章两张表：room_id→scene_id（主）、name_raw→scene_id（副）。"""
    idx = jl(os.path.join(SCENES, '_index.json'))
    by_id, by_name = {}, {}
    for ch, node in (idx.get('chapters') or {}).items():
        m_id, m_nm = {}, {}
        for _area, anode in (node.get('areas') or {}).items():
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


def census_variants():
    """第42轮普查里的变体实例：`{ch: {obj: {(room_index, x, y)}}}`（A/B 的 B 侧）。"""
    out = {}
    for ch, fn in INST42.items():
        p = os.path.join(E42, fn)
        if not os.path.isfile(p):
            continue
        d = jl(p)
        per = collections.defaultdict(set)
        for rec in (d.get('rooms') or []):
            rid = rec.get('index')
            if not isinstance(rid, int):
                continue
            for it in (rec.get('insts') or []):
                o = it.get('obj')
                if o not in VARIANTS:
                    continue
                x, y = it.get('x'), it.get('y')
                if not isinstance(x, int) or not isinstance(y, int):
                    continue
                per[o].add((rid, x, y))
        out[ch] = dict(per)
    return out


def main():
    by_id, by_name = build_maps()
    routes = jl(os.path.join(SCENES, '_routes.json'))
    rl = routes.get('routes') if isinstance(routes, dict) else routes
    rl = rl or []
    have_pairs, have_src = set(), set()
    for r in rl:
        sc = r.get('when_scene')
        if sc:
            have_src.add(sc)
            if r.get('to'):
                have_pairs.add((sc, r.get('to')))

    census = census_variants()

    rows, per_ch = [], {}
    stat = dict((k, 0) for k in KINDS)
    n_prc_unmapped = 0            # 源房没登记成场景
    ab_report = {}
    for ch in CHS:
        probe_p = os.path.join(E172, 'probe_any172.%s.json' % ch)
        if not os.path.exists(probe_p):
            continue
        d = jl(probe_p)
        rid2name = dict((r['index'], r['name']) for r in (d.get('rooms') or []))
        name2rid = dict((r['name'], r['index']) for r in (d.get('rooms') or []))
        m_id = by_id.get(ch) or {}
        cnt = dict(inst=0, src_unmapped=0, **dict((k, 0) for k in KINDS))
        probe_set = collections.defaultdict(set)
        for i in (d.get('instances') or []):
            o = i.get('obj')
            if o not in VARIANTS:
                continue
            cnt['inst'] += 1
            ri = i.get('room_index')
            rn = i.get('room')
            x, y = i.get('x'), i.get('y')
            if isinstance(ri, int) and isinstance(x, int) and isinstance(y, int):
                probe_set[o].add((ri, x, y))
            src = m_id.get(ri)
            if not src:
                src = (by_name.get(ch) or {}).get(rn)
            g = i.get('creation_gml') or ''
            m = RE_DOORROOM.search(g)
            tgt = m.group(1) if m else None
            idxv = i.get('image_index')
            dst = None
            if tgt:
                trid = name2rid.get(tgt)
                dst = m_id.get(trid) if isinstance(trid, int) else None
                if not dst:
                    dst = (by_name.get(ch) or {}).get(tgt)
                kind = 'static_dst_ok' if dst else 'static_dst_unmapped'
            elif idxv not in (None, 0, '0'):
                kind = 'relative_debug'
            elif i.get('creation_code'):
                kind = 'unknown_code_only'
            else:
                kind = 'unknown_no_code'
            if not src:
                cnt['src_unmapped'] += 1
                n_prc_unmapped += 1
            stat[kind] += 1
            cnt[kind] += 1
            rows.append(dict(ch=ch, room=rn, room_index=ri, obj=o, src=src,
                             x=x, y=y, image_index=idxv, code=i.get('creation_code'),
                             doorroom=tgt, dst=dst, kind=kind,
                             src_room_name=tgt and None))
        per_ch[ch] = dict(cnt)
        # ---- A/B：本变体在两条独立读取路径上的实例集合必须相等 ----
        bside = (census.get(ch) or {})
        for o in VARIANTS:
            if o in probe_set or o in bside:
                A, B = probe_set.get(o, set()), bside.get(o, set())
                ab_report['%s/%s' % (ch, o)] = dict(nA=len(A), nB=len(B),
                                                   onlyA=sorted(A - B), onlyB=sorted(B - A))

    # ---- 候选边 ----
    cand = {}
    n_pair_dup_coord = 0
    for r in rows:
        if r['kind'] != 'static_dst_ok' or not r['src']:
            continue
        k = (r['src'], r['dst'])
        cand[k] = cand.get(k, 0) + 1
    new_pairs = dict((k, v) for k, v in cand.items() if k not in have_pairs)
    dup_pairs = dict((k, v) for k, v in cand.items() if k in have_pairs)

    # ---- 每条实例一行（物化/落边都用这个口径，**不按对去重**）----
    inst_rows = [r for r in rows if r['kind'] == 'static_dst_ok' and r['src']]
    seen = set()
    uniq = []
    for r in inst_rows:
        k = (r['ch'], r['room_index'], r['obj'], r['dst'], r['x'], r['y'])
        if k in seen:
            n_pair_dup_coord += 1
            continue
        seen.add(k)
        uniq.append(r)

    out = dict(per_ch=per_ch, total=stat, n_rows=len(rows),
               n_src_unmapped=n_prc_unmapped,
               n_cand_pairs=len(cand), n_new_pairs=len(new_pairs),
               n_dup_pairs=len(dup_pairs),
               n_inst_ok=len(inst_rows), n_inst_uniq=len(uniq),
               n_inst_dup_coord=n_pair_dup_coord,
               ab=ab_report, rows=rows,
               new_pairs=sorted('%s -> %s' % k for k in new_pairs),
               dup_pairs=sorted('%s -> %s' % k for k in dup_pairs))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with io.open(OUT, 'w', encoding='utf-8', newline='') as f:
        f.write(json.dumps(out, ensure_ascii=False, indent=1))

    print(u'== 逐章（扇数）==')
    for ch, c in per_ch.items():
        print('  %-4s inst=%-3d ok=%-3d unmapped=%-2d debug_rel=%-2d unk(code)=%-2d '
              u'unk(nocode)=%-2d src_unmapped=%d'
              % (ch, c['inst'], c['static_dst_ok'], c['static_dst_unmapped'],
                 c['relative_debug'], c['unknown_code_only'], c['unknown_no_code'],
                 c['src_unmapped']))
    print(u'== 合计 ==')
    print(u'  ' + u'  '.join(u'%s=%d' % (k, stat[k]) for k in KINDS))
    print(u'  扇数=%d | 源房未登记=%d' % (len(rows), n_prc_unmapped))
    print(u'  候选 (源场景→目标场景) 对(去重) = %d | 新对 = %d | 表里已有 = %d'
          % (len(cand), len(new_pairs), len(dup_pairs)))
    print(u'  可落边实例 = %d | 去重(章,房,对象,目标,x,y)后 = %d | 重复坐标 = %d'
          % (len(inst_rows), len(uniq), n_pair_dup_coord))
    print(u'== A/B 锚点（csx 探针 vs 第42轮 CLI 普查，逐变体实例集合）==')
    ab_bad = 0
    for k in sorted(ab_report):
        v = ab_report[k]
        flag = u'IDENTICAL' if not v['onlyA'] and not v['onlyB'] else u'★DIFF★'
        if flag != u'IDENTICAL' or v['nA'] != v['nB']:
            ab_bad += 1
        print(u'  %-30s A=%-3d B=%-3d %s %r %r'
              % (k, v['nA'], v['nB'], flag, v['onlyA'][:3], v['onlyB'][:3]))
    print(u'  → 不一致的变体数 = %d' % ab_bad)
    print(u'out = %s (%d B)' % (OUT, os.path.getsize(OUT)))
    return 0 if ab_bad == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
