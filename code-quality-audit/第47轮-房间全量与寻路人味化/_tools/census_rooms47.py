# -*- coding: utf-8 -*-
"""第47轮工具：ch1/2/4/5 **房间全量普查 + 缺口归因**（从权威源重算，不手抄）。

用户口径（本轮）：
    「复查一下1,2,4,5,章的room加起来到底有多少，别漏了，
      并且确保每一个都能用，且符合原作逻辑」

「别漏了」= 必须**穷尽**，不许用近似/抽样。所以本工具把每一间房都过一遍，
四个权威源交叉核对：

  ① `_room_geometry.json`.stats      —— 原作房间总数（键 = "<章>:<Data.Rooms 下标>"）
  ② `_room_order.json`               —— 原作**逻辑分类**（home/town/dark/system/debug…）
  ③ `_index.json`                    —— 产品已落地的场景（scene_id → original_room_id）
  ④ `_room_graph.json`               —— 原作**门连接**（可达性 / 缺口是否真是"原作能进"）

输出：`_evidence/房间普查47.json` + `房间普查47.txt`
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
SCENES = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes')
EV42 = os.path.join(ROOT, 'code-quality-audit', '第42轮-原作拓扑取证', '_evidence')
EV38 = os.path.join(ROOT, 'code-quality-audit', '第38轮-场景系统审查', '_evidence')
OUT = os.path.join(HERE, '..', '_evidence')

CHAPS = ('ch1', 'ch2', 'ch4', 'ch5')      # 用户本轮点名的四章
ALL_CHAPS = ('ch1', 'ch2', 'ch3', 'ch4', 'ch5')

#: 原作里**不可玩**的分类（进不去 / 没内容）。
NON_PLAYABLE = ('system', 'debug')


def rd(path):
    with io.open(path, 'r', encoding='utf-8') as fh:
        return json.load(fh)


def main():
    geo = rd(os.path.join(SCENES, '_room_geometry.json'))
    order = rd(os.path.join(EV42, '_room_order.json'))
    index = rd(os.path.join(SCENES, '_index.json'))
    graph = rd(os.path.join(EV42, '_room_graph.json'))
    cls38_path = os.path.join(EV38, '房间表_全量.json')
    cls38 = rd(cls38_path) if os.path.isfile(cls38_path) else None

    # --- ② 分类：{ch: {index: kind}} ---
    kind = {}
    for ch in ALL_CHAPS:
        rec = (order.get('chapters') or {}).get(ch) or {}
        kind[ch] = {r['index']: r.get('kind') or 'other'
                    for r in (rec.get('rooms') or [])
                    if isinstance(r.get('index'), int)}

    # --- ③ 产品场景：{ch: {room_index: [scene_id,...]}} ---
    # ★ 口径注意：`_index.json.chapters` **含有 `desktop` 键**（桌面=独立前置章），
    #   统计"产品场景总数"必须遍历**全部章节键**，否则会少算 1（第47轮踩过）。
    prod = {ch: {} for ch in ALL_CHAPS}
    n_scenes = 0                       # 全部章节键（含 desktop）
    n_scenes_ch = 0                    # 仅 ch1~ch5
    for ch, crec in (index.get('chapters') or {}).items():
        for ak, arec in ((crec or {}).get('areas') or {}).items():
            for sid, srec in ((arec or {}).get('scenes') or {}).items():
                n_scenes += 1
                if ch in prod:
                    n_scenes_ch += 1
                rid = (srec or {}).get('original_room_id')
                if ch in prod and isinstance(rid, int):
                    prod[ch].setdefault(rid, []).append(sid)

    # --- ④ 门图：{ch: {room: {out,in}}} ---
    deg = {ch: {} for ch in ALL_CHAPS}
    for ch in ALL_CHAPS:
        crec = (graph.get('chapters') or {}).get(ch) or {}
        for e in (crec.get('edges') or []):
            s, d = e.get('src'), e.get('dst')
            if not isinstance(s, int) or not isinstance(d, int):
                continue
            deg[ch].setdefault(s, {'out': 0, 'in': 0})['out'] += 1
            deg[ch].setdefault(d, {'out': 0, 'in': 0})['in'] += 1

    # --- ① 原作房间总量 ---
    stats = geo.get('stats') or {}
    geo_rooms = geo.get('rooms') or {}

    report = {}
    lines = []
    ap = lines.append

    ap('第47轮 · ch1/2/4/5 房间全量普查（四个权威源交叉）')
    ap('=' * 78)
    ap('权威源：① _room_geometry.json.stats  ② _room_order.json  ③ _index.json  '
       '④ _room_graph.json')
    ap('')
    ap('%-5s %6s %8s %8s %8s %8s %9s %8s' % (
        '章', '原作', 'system', 'debug', '其它', 'playable', '产品已覆盖', '★未覆盖'))
    tot = {'orig': 0, 'sys': 0, 'dbg': 0, 'oth': 0, 'play': 0, 'prod': 0, 'miss': 0}
    for ch in ALL_CHAPS:
        n_orig = int(stats.get(ch) or 0)
        # 以几何表为准逐间过一遍（"别漏了"）
        idxs = sorted(int(k.split(':')[1]) for k in geo_rooms
                      if k.startswith(ch + ':'))
        if len(idxs) != n_orig:
            ap('  ⚠️ %s stats=%d 与 rooms 键数=%d 不一致' % (ch, n_orig, len(idxs)))
        kk = kind.get(ch) or {}
        n_sys = sum(1 for i in idxs if kk.get(i) == 'system')
        n_dbg = sum(1 for i in idxs if kk.get(i) == 'debug')
        n_oth = sum(1 for i in idxs if kk.get(i) not in NON_PLAYABLE
                    and kk.get(i) is None)
        play = [i for i in idxs if kk.get(i) not in NON_PLAYABLE and kk.get(i) is not None]
        covered = [i for i in play if i in prod.get(ch, {})]
        miss = [i for i in play if i not in prod.get(ch, {})]
        ap('%-5s %6d %8d %8d %8d %8d %9d %8d'
           % (ch, n_orig, n_sys, n_dbg, n_oth, len(play), len(covered), len(miss)))
        report[ch] = {'orig': n_orig, 'system': n_sys, 'debug': n_dbg, 'other_None': n_oth,
                      'playable': len(play), 'covered': len(covered), 'missing': len(miss),
                      'missing_rooms': miss}
        tot['orig'] += n_orig
        tot['sys'] += n_sys
        tot['dbg'] += n_dbg
        tot['oth'] += n_oth
        tot['play'] += len(play)
        tot['prod'] += len(covered)
        tot['miss'] += len(miss)
    ap('-' * 78)
    ap('%-5s %6d %8d %8d %8d %8d %9d %8d' % ('合计', tot['orig'], tot['sys'], tot['dbg'],
                                              tot['oth'], tot['play'], tot['prod'], tot['miss']))
    ap('')
    ap('全部五章：原作 %d 间；产品场景 %d 个（ch1~ch5 = %d，另含 desktop 章 %d 个）'
       % (sum(int(stats.get(c) or 0) for c in ALL_CHAPS), n_scenes, n_scenes_ch,
          n_scenes - n_scenes_ch))

    # --- ★ 缺口归因：未覆盖的房间里，哪些"原作里能进"（有入边/出边）---
    ap('')
    ap('★ 缺口归因：未覆盖 playable 房间里，**原作门图里有边**的（= 原作能进 ⇒ 必须做）')
    ap('-' * 78)
    real_gaps = []
    isolated = []
    for ch in ALL_CHAPS:
        for i in report[ch]['missing_rooms']:
            d = deg.get(ch, {}).get(i) or {'in': 0, 'out': 0}
            name = (geo_rooms.get('%s:%d' % (ch, i)) or {}).get('name') or ''
            item = {'chapter': ch, 'room_index': i, 'name': name,
                    'kind': kk.get(i) if False else (kind.get(ch, {}).get(i)),
                    'in': d['in'], 'out': d['out']}
            if d['in'] or d['out']:
                real_gaps.append(item)
            else:
                isolated.append(item)
    ap('有门可达（真缺口）= %d 间：' % len(real_gaps))
    for it in sorted(real_gaps, key=lambda x: (x['chapter'], x['room_index'])):
        ap('   %s 下标 %-4d %-28s kind=%-10s in=%d out=%d'
           % (it['chapter'], it['room_index'], it['name'], it['kind'],
              it['in'], it['out']))
    ap('')
    ap('无门孤立（原作里也进不去，按原作逻辑**不该做**）= %d 间' % len(isolated))
    from collections import Counter
    cn = Counter(it['name'] for it in isolated)
    for nm, c in cn.most_common():
        ap('   %-32s × %d' % (nm, c))

    # --- 38 轮 cls=maybe 交叉（"待裁定"至今未裁的那些）---
    if cls38:
        ap('')
        ap('★ 与第38轮 `cls` 交叉（maybe = 当年留的"待裁定"）')
        ap('-' * 78)
        c38 = {}
        for ch, rows in cls38.items():
            for r in rows or []:
                c38.setdefault('%s:%s' % (ch, r.get('room_index')), r.get('cls'))
        for it in sorted(real_gaps, key=lambda x: (x['chapter'], x['room_index'])):
            k = '%s:%s' % (it['chapter'], it['room_index'])
            ap('   %-10s %s' % (k, c38.get(k)))
        rep = Counter(c38.get('%s:%s' % (it['chapter'], it['room_index']))
                      for it in real_gaps)
        ap('   真缺口的 38 轮 cls 分布：%r' % dict(rep))

    report['_totals'] = tot
    report['_n_product_scenes'] = n_scenes
    report['_real_gaps'] = real_gaps
    report['_isolated_missing'] = isolated
    report['_authority_stats'] = stats

    text = '\n'.join(lines)
    print(text)
    if not os.path.isdir(OUT):
        os.makedirs(OUT)
    with io.open(os.path.join(OUT, '房间普查47.txt'), 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(text + '\n')
    with io.open(os.path.join(OUT, '房间普查47.json'), 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(json.dumps(report, ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
