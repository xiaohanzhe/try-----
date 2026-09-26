# -*- coding: utf-8 -*-
"""第51轮验证：**跨房间配对** —— `src` 的 `obj_door<L>` ⇄ `dst` 的 `obj_marker<L>`。

为什么要这一步（以及为什么同房间配对是错的判据）
------------------------------------------------
第一次普查（`survey_doors51.py`）里我按"**同一房间内** door 字母 ⊇ marker 字母"
统计，得到 356 个"字母不配对"场景。**那是判据过窄的误报**（项目记忆 §4：
判据过窄 = 会误报，与过宽 = 恒真同样要防）。

看样本就明白：`ch1.card_castle.cc_entrance` 只有 `doorA` + `markerB` ——
那不是缺陷，而是**正常的**：`doorA` 是"从这个房间通往 +1 室"的门；
`markerB` 是"从 -1 室（对侧看是它的 B 门）进来时的落点"。两者**本就不是同一条边**。

⇒ 正确判据是**跨房间**配对：
    房间 X 的 `obj_door<L>`  ⇒  目标房间 Y 的 `obj_marker<L>`
因为落点在**目标房间**里。（`_room_graph.json` 的 782 条边给了 X→Y 与门的名字。）

本脚本的产出直接决定"逐门执行"能不能做：
    · `door` 命中率 = 能不能**走到门口**；
    · `marker` 命中率 = 换场景后**能不能站对地方**。
"""
import io
import json
import os
import sys

REPO = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
sys.path.insert(0, os.path.join(REPO, 'ralsei_pet', 'modules'))
sys.path.insert(0, os.path.join(REPO, 'ralsei_pet'))

import scene_system      # noqa: E402
import scene_pathfind    # noqa: E402

EV = os.path.join(REPO, 'code-quality-audit', '第51轮-真机巡行与交互', '_evidence')
OUT_JSON = os.path.join(EV, 'door_edges51.json')
OUT_TXT = os.path.join(EV, 'door_edges51.txt')

lines = []


def w(s=''):
    lines.append(str(s))


def letters_of(src, prefix):
    if not isinstance(src, str) or not src.startswith(prefix):
        return None
    tail = src[len(prefix):]
    if not tail:
        return None
    ch = tail[0]
    return ch.upper() if ch.isalpha() else None


def prim_of(src):
    """`obj_doorA` → ('door','A')；`obj_markerB` → ('marker','B')；否则 (None,None)。"""
    for kind, prefix in (('door', 'obj_door'), ('marker', 'obj_marker')):
        L = letters_of(src, prefix)
        if L:
            return kind, L
    return None, None


def nodes_of(scene):
    doors, markers = {}, {}
    for ob in (getattr(scene, 'objects', None) or ()):
        if not isinstance(ob, dict):
            continue
        kind, L = prim_of(ob.get('src') or ob.get('id') or '')
        pos = ob.get('pos')
        if not (kind and isinstance(pos, (list, tuple)) and len(pos) >= 2):
            continue
        tgt = doors if kind == 'door' else markers
        tgt.setdefault(L, (int(pos[0]), int(pos[1])))
    return doors, markers


def main():
    index = scene_system.load_index()
    scenes = index.get('scenes') or {}

    # 房间下标 → scene_id（按章）。
    # ★ 用 scene_pathfind 自己的展平函数：`_index.json` 的场景住在 `chapters` 下，
    #   entry 的形状由它统一（`_locate_scene` 同源）。**不要**自己猜 entry 的键 ——
    #   猜错会静默得到空表、然后"全部边都没登记"（那是判据侧的假问题）。
    by_room = {}
    for rec in scene_pathfind._scene_pool(index):
        ch = rec.get('chapter_id')
        rid = rec.get('original_room_id')
        if isinstance(rid, int) and ch:
            by_room.setdefault((ch, rid), rec['scene_id'])
    w('=== 跨房间配对验证（第51轮）===')
    w('by_room 键数=%d（章,房间下标 → scene_id）' % len(by_room))

    graph = scene_pathfind.load_room_graph()
    w('房间图 ok=%s  err=%s' % (graph.get('ok'), graph.get('error')))
    edges_by_ch = graph.get('edges_by_chapter') or {}

    cache = {}

    def scene_nodes(sid):
        if sid not in cache:
            sc = scene_system.load_scene(sid, entry=scenes.get(sid))
            cache[sid] = nodes_of(sc) if sc is not None else ({}, {})
        return cache[sid]

    # ---------- 锚点自检：先确认"门的字母真的决定了目标房间" ----------
    w('')
    w('[A] 锚点自检：ch1 room 45(Castle Town) 的 doorA 应指向 room 46 且那边有 markerA')
    a_src = by_room.get(('ch1', 45))
    sd, sm = scene_nodes(a_src) if a_src else ({}, {})
    w('    src=%s doors=%s markers=%s' % (a_src, sd, sm))
    # A = +1 口径（记忆 §43.2）。用门名反查边，而不是自己算下标。
    tgt_a = by_room.get(('ch1', 46))
    if tgt_a:
        td, tm = scene_nodes(tgt_a)
        w('    dst(ch1:46)=%s doors=%s markers=%s' % (tgt_a, td, tm))
        w('    markerA 在目标房间？ %s' % ('A' in tm))
    else:
        w('    !! ch1:46 未登记为场景，锚点无法自检')

    # ---------- 全量：逐边核对 ----------
    tot = door_hit = marker_hit = both = 0
    no_src_scene = no_dst_scene = 0
    miss_samples = []
    per_ch = {}
    for ch, edges in sorted(edges_by_ch.items()):
        rec = per_ch.setdefault(ch, {'edges': 0, 'door': 0, 'marker': 0, 'both': 0,
                                     'no_src': 0, 'no_dst': 0})
        for e in edges or ():
            if not isinstance(e, dict):
                continue
            src_i, dst_i = e.get('src'), e.get('dst')
            door = e.get('door') or ''
            _, L = prim_of(door) if door.startswith('obj_') else (None, None)
            if L is None:
                L = (door[-1].upper() if door and door[-1].isalpha() else None)
            tot += 1
            rec['edges'] += 1
            sid = by_room.get((ch, src_i))
            tid = by_room.get((ch, dst_i))
            if sid is None:
                no_src_scene += 1
                rec['no_src'] += 1
                continue
            if tid is None:
                no_dst_scene += 1
                rec['no_dst'] += 1
                continue
            sd_, _sm_ = scene_nodes(sid)
            _td_, tm_ = scene_nodes(tid)
            hit_d = bool(L) and (L in sd_)
            hit_m = bool(L) and (L in tm_)
            if hit_d:
                door_hit += 1
                rec['door'] += 1
            if hit_m:
                marker_hit += 1
                rec['marker'] += 1
            if hit_d and hit_m:
                both += 1
                rec['both'] += 1
            elif len(miss_samples) < 25:
                miss_samples.append({
                    'ch': ch, 'src': src_i, 'dst': dst_i, 'door': door, 'letter': L,
                    'src_scene': sid, 'dst_scene': tid,
                    'src_doors': sorted(sd_), 'dst_markers': sorted(tm_),
                    'door_hit': hit_d, 'marker_hit': hit_m,
                })

    w('')
    w('[B] 全量逐边核对（边总数 %d）' % tot)
    w('    两端场景都没登记的边 = 未登记 src %d / dst %d' % (no_src_scene, no_dst_scene))
    w('    门坐标命中        = %d / %d  (%.1f%%)'
      % (door_hit, tot, 100.0 * door_hit / max(1, tot)))
    w('    落点坐标命中      = %d / %d  (%.1f%%)'
      % (marker_hit, tot, 100.0 * marker_hit / max(1, tot)))
    w('    **两端都齐（可逐门执行）= %d / %d  (%.1f%%)**'
      % (both, tot, 100.0 * both / max(1, tot)))
    w('')
    w('    分章：')
    for ch in sorted(per_ch):
        r = per_ch[ch]
        w('      %-4s 边 %4d  门命中 %4d  落点命中 %4d  两端齐 %4d  (未登记 src %d/dst %d)'
          % (ch, r['edges'], r['door'], r['marker'], r['both'],
             r['no_src'], r['no_dst']))
    if miss_samples:
        w('')
        w('    未两端齐的样本（前 %d）：' % len(miss_samples))
        for m in miss_samples:
            w('      %s %d->%d %s(%s) door_hit=%s marker_hit=%s'
              % (m['ch'], m['src'], m['dst'], m['door'], m['letter'],
                 m['door_hit'], m['marker_hit']))
            w('         src_doors=%s  dst_markers=%s'
              % (m['src_doors'], m['dst_markers']))

    payload = {
        'edges_total': tot,
        'no_src_scene': no_src_scene, 'no_dst_scene': no_dst_scene,
        'door_hit': door_hit, 'marker_hit': marker_hit, 'both_ends': both,
        'by_chapter': per_ch, 'miss_samples': miss_samples,
    }
    with io.open(OUT_JSON, 'w', encoding='utf-8') as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1)
    text = '\n'.join(lines) + '\n'
    with io.open(OUT_TXT, 'w', encoding='utf-8') as fh:
        fh.write(text)
    print(text)
    return 0


if __name__ == '__main__':
    sys.exit(main())
