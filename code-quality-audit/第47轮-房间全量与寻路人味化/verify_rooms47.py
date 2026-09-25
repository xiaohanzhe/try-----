# -*- coding: utf-8 -*-
"""第47轮 · ch1/2/4/5 房间全量普查 + 逐场景可用性 回归锁（G2 的一部分）。

用户口径（本轮）：
    「复查一下1,2,4,5,章的room加起来到底有多少，别漏了，
      并且确保每一个都能用，且符合原作逻辑」

拆三条对应本锁三段：
  A **有多少 / 别漏了** —— 用四个权威源交叉，逐间过一遍（不抽样、不近似）
  B **每一个都能用**   —— 逐场景五条可判定事实（载体/注册/名字/原作 id/几何）
  C **符合原作逻辑**   —— 缺口的归因必须用**原作门图**，不许用名字猜

★ 本锁自己的两个方法论判据（都在 C 段）
----------------------------------------
· 「命名启发式只有 74% 覆盖」→ 反面证明"用名字分类"不可靠；
· 「同名不同命」（`room_shop1` 同时落在"有门"与"无门"两侧）→ 进一步钉死
  "判据只能是原作门图"。这两条是为了防止后来者把 C 段简化成"看名字"。

判据纪律：每条 print `[PASS] ` 字面量；不联网 / 不 import Qt / 不需要显示器。
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
SCENES = os.path.join(PET, 'assets', 'scenes')
EV42 = os.path.join(ROOT, 'code-quality-audit', '第42轮-原作拓扑取证', '_evidence')
EV38 = os.path.join(ROOT, 'code-quality-audit', '第38轮-场景系统审查', '_evidence')

FOUR = ('ch1', 'ch2', 'ch4', 'ch5')          # 用户本轮点名的四章
ALL5 = ('ch1', 'ch2', 'ch3', 'ch4', 'ch5')
NON_PLAYABLE = ('system', 'debug')

#: ★ 真缺口（原作门图里有边的未覆盖 playable 房间）—— 动手前写死的"事实快照"。
#: ch3 不在本轮范围（用户口径：第三章的黑暗喷泉开在 Kris 家里，那两个不能同时存在）。
REAL_GAPS_4 = {
    ('ch1', 33), ('ch1', 133), ('ch1', 134),
    ('ch2', 54), ('ch2', 229), ('ch2', 230), ('ch2', 231),
    ('ch4', 60),
    ('ch5', 49), ('ch5', 79),
}

PASS = 0
FAIL = 0


def check(name, cond, extra=''):
    global PASS, FAIL
    if cond:
        PASS += 1
        print('[PASS] %s' % name)
    else:
        FAIL += 1
        print('[FAIL] %s %s' % (name, extra))


def rd(p):
    with io.open(p, 'r', encoding='utf-8') as fh:
        return json.load(fh)


def main():
    print('=== 第47轮 房间全量普查 + 逐场景可用性 回归锁 ===')
    need = {
        'geo': os.path.join(SCENES, '_room_geometry.json'),
        'idx': os.path.join(SCENES, '_index.json'),
        'order': os.path.join(EV42, '_room_order.json'),
        'graph': os.path.join(EV42, '_room_graph.json'),
        'cls38': os.path.join(EV38, '房间表_全量.json'),
    }
    miss = [k for k, v in need.items() if not os.path.isfile(v)]
    check('前置：五个权威源都在位', not miss, '缺 %r' % miss)
    if miss:
        return 1
    geo = rd(need['geo'])
    idx = rd(need['idx'])
    order = rd(need['order'])
    graph = rd(need['graph'])
    cls38 = rd(need['cls38'])

    rooms = geo.get('rooms') or {}
    stats = geo.get('stats') or {}

    kind = {}
    for ch in ALL5:
        rec = (order.get('chapters') or {}).get(ch) or {}
        kind[ch] = {r['index']: (r.get('kind') or 'other')
                    for r in (rec.get('rooms') or [])
                    if isinstance(r.get('index'), int)}

    deg = {ch: {} for ch in ALL5}
    for ch in ALL5:
        for e in (((graph.get('chapters') or {}).get(ch) or {}).get('edges') or []):
            s, d = e.get('src'), e.get('dst')
            if not isinstance(s, int) or not isinstance(d, int):
                continue
            deg[ch].setdefault(s, {'in': 0, 'out': 0})['out'] += 1
            deg[ch].setdefault(d, {'in': 0, 'out': 0})['in'] += 1

    # =======================================================================
    print()
    print('== A. 房间全量：有多少 / 别漏了 ==')
    # =======================================================================
    expect_stats = {'ch1': 147, 'ch2': 278, 'ch3': 246, 'ch4': 328, 'ch5': 252}
    check('A1 五章原作房间数 == 147/278/246/328/252（合计 1,251）',
          all(int(stats.get(c) or 0) == v for c, v in expect_stats.items())
          and sum(expect_stats.values()) == 1251,
          'stats=%r' % {c: stats.get(c) for c in ALL5})
    check('A2 ★ ch1/2/4/5 合计 == 1,005（用户点名的四章）',
          sum(expect_stats[c] for c in FOUR) == 1005)

    # ★ "别漏了"的可判定形式：每章的下标必须是 0..n-1 **一个不缺**
    gaps_in_index = {}
    for ch in ALL5:
        idxs = sorted(int(k.split(':')[1]) for k in rooms if k.startswith(ch + ':'))
        n = int(stats.get(ch) or 0)
        if idxs != list(range(n)):
            gaps_in_index[ch] = (len(idxs), n, idxs[:3], idxs[-3:])
    check('A3 ★ 逐章下标 0..n-1 一个不缺（"别漏了"的穷尽判据）',
          not gaps_in_index, '异常章=%r' % gaps_in_index)

    # 分类表也必须逐间覆盖（否则 playable 少算 = 缺口算错）
    kind_miss = {ch: sorted(set(int(k.split(':')[1]) for k in rooms
                                if k.startswith(ch + ':')) - set(kind[ch]))
                 for ch in ALL5}
    kind_miss = {k: v for k, v in kind_miss.items() if v}
    check('A4 每间房在原作分类表里有 kind', not kind_miss, '缺 %r' % kind_miss)

    prod = {ch: {} for ch in ALL5}
    per_ch_scenes = {}
    for ch, crec in (idx.get('chapters') or {}).items():
        per_ch_scenes[ch] = 0
        for ak, arec in ((crec or {}).get('areas') or {}).items():
            for sid, srec in ((arec or {}).get('scenes') or {}).items():
                per_ch_scenes[ch] += 1
                rid = (srec or {}).get('original_room_id')
                # ★ 索引里 `desktop` **也是一个章节键**（1 个场景）——
                #   只遍历 ch1~ch5 会少算 1 个（第47轮第一版就是这么错的）。
                if ch in prod and isinstance(rid, int):
                    prod[ch].setdefault(rid, []).append(sid)
    n_scenes = sum(per_ch_scenes.values())
    n_scenes_4 = sum(per_ch_scenes.get(c, 0) for c in FOUR)
    check('A5 产品场景 == 1,014 个（含 desktop 1）；ch1/2/4/5 == 826 个',
          n_scenes == 1014 and n_scenes_4 == 826 and per_ch_scenes.get('desktop') == 1,
          '总 %d，四章 %d，分章 %r' % (n_scenes, n_scenes_4, per_ch_scenes))

    play, cov, missing = {}, {}, {}
    for ch in ALL5:
        idxs = [int(k.split(':')[1]) for k in rooms if k.startswith(ch + ':')]
        play[ch] = sorted(i for i in idxs if kind[ch].get(i) not in NON_PLAYABLE)
        cov[ch] = sorted(i for i in play[ch] if i in prod[ch])
        missing[ch] = sorted(i for i in play[ch] if i not in prod[ch])
    check('A6 ch1/2/4/5 playable == 853；已覆盖 == 812；未覆盖 == 41',
          sum(len(play[c]) for c in FOUR) == 853
          and sum(len(cov[c]) for c in FOUR) == 812
          and sum(len(missing[c]) for c in FOUR) == 41,
          'playable=%d cov=%d miss=%d'
          % (sum(len(play[c]) for c in FOUR), sum(len(cov[c]) for c in FOUR),
             sum(len(missing[c]) for c in FOUR)))

    real = set()
    iso = set()
    for ch in FOUR:
        for i in missing[ch]:
            d = deg.get(ch, {}).get(i) or {'in': 0, 'out': 0}
            (real if (d['in'] or d['out']) else iso).add((ch, i))
    check('A7 ★★ 真缺口（原作门图里有边）== 10 间，且集合精确相等',
          real == REAL_GAPS_4,
          '实得 %r；多=%r 少=%r'
          % (sorted(real), sorted(real - REAL_GAPS_4), sorted(REAL_GAPS_4 - real)))
    check('A8 ★ 负控制：真缺口(10) 严格少于未覆盖(41) —— 归因这步真筛过',
          len(real) == 10 and len(real) + len(iso) == 41,
          'real=%d iso=%d' % (len(real), len(iso)))
    check('A9 两集合不相交（归因是一刀两断，不是重叠）', not (real & iso))

    # =======================================================================
    print()
    print('== B. 逐场景可用性：每一个都能用 ==')
    # =======================================================================
    files = set(os.listdir(SCENES))
    zone_cache = {}
    bad = {'U1': [], 'U2': [], 'U3': [], 'U4': [], 'U5': []}
    n_bg = 0
    n_shard = 0           # ★ 用分片载体的场景数（负控制要用）
    for ch, crec in (idx.get('chapters') or {}).items():
        for ak, arec in (crec.get('areas') or {}).items():
            for sid, srec in ((arec or {}).get('scenes') or {}).items():
                rec = srec or {}
                # ★ 两种载体：独立件用 `file`；**分片场景的 `file` 是空串**，
                #   载体 = 区域级 `_zone.<章>.<区>.json`。
                #   第47轮第一版判据只看 `file` ⇒ 926 个分片场景被误报"缺文件"（判据过窄）。
                fname = rec.get('file') or ('_zone.%s.%s.json' % (ch, ak))
                if not rec.get('file'):
                    n_shard += 1
                if fname not in files:
                    bad['U1'].append((sid, fname))
                    continue
                if fname.startswith('_zone.'):
                    if fname not in zone_cache:
                        zone_cache[fname] = rd(os.path.join(SCENES, fname))
                    body = (zone_cache[fname].get('scenes') or {}).get(sid)
                else:
                    body = rd(os.path.join(SCENES, fname))
                if not isinstance(body, dict):
                    bad['U2'].append((sid, fname))
                    continue
                if not (rec.get('name') or '').strip():
                    bad['U3'].append(sid)
                rid = rec.get('original_room_id')
                if not isinstance(rid, int):
                    bad['U4'].append(sid)
                elif ('%s:%d' % (ch, rid)) not in rooms:
                    bad['U5'].append((sid, ch, rid))
                if body.get('bg'):
                    n_bg += 1

    check('B1 U1 载体文件缺失 == 0（两种载体都覆盖）', not bad['U1'],
          '%d 个，例 %r' % (len(bad['U1']), bad['U1'][:3]))
    check('B2 ★ 负控制：确实存在用分片载体的场景（B1 不是"没检查"过关）',
          n_shard == 926, '分片场景数=%d' % n_shard)
    check('B3 U2 载体里未注册该场景 == 0', not bad['U2'],
          '%d 个，例 %r' % (len(bad['U2']), bad['U2'][:3]))
    check('B4 U3 name 非空 == 全部', not bad['U3'], '%d 个' % len(bad['U3']))
    check('B5 U4 original_room_id 非 int 的只有 desktop（它本就不属于任何原作房间）',
          sorted(bad['U4']) == ['desktop'], '异常=%r' % bad['U4'])
    check('B6 ★ 负控制：desktop 确实在索引里（B5 不是"恰好没记录"的恒真）',
          any(sid == 'desktop'
              for crec in (idx.get('chapters') or {}).values()
              for arec in ((crec or {}).get('areas') or {}).values()
              for sid in ((arec or {}).get('scenes') or {})))
    check('B7 U5 几何表未命中 == 0（每间都能算尺寸 ⇒ 房内行走可算）',
          not bad['U5'], '%d 个，例 %r' % (len(bad['U5']), bad['U5'][:3]))
    # 背景覆盖率**不属于"能用"**，但必须如实钉住（缺口需要 UTMT 重新导出素材）
    check('B8 背景覆盖率如实钉住 == 235/1014（缺口 779，待重导素材）',
          n_bg == 235, '实得 %d' % n_bg)

    # =======================================================================
    print()
    print('== C. 符合原作逻辑：判据必须是门图，不是名字 ==')
    # =======================================================================
    c38 = {}
    for ch, rows in (cls38 or {}).items():
        for r in (rows or []):
            c38['%s:%s' % (ch, r.get('room_index'))] = r.get('cls')
    dist = {}
    for ch, i in real:
        k = c38.get('%s:%d' % (ch, i))
        dist[k] = dist.get(k, 0) + 1
    check('C1 ★ 10 个真缺口在第38轮 cls 里：maybe 9 / nonscene 1（当年"待裁定"至今没裁）',
          dist.get('maybe') == 9 and dist.get('nonscene') == 1 and len(dist) == 2,
          '实得 %r' % dist)

    names = {'%s:%d' % (ch, i): (rooms.get('%s:%d' % (ch, i)) or {}).get('name') or ''
             for ch, i in (real | iso)}
    KW = ('test', 'intro', 'sequence', 'anim', 'cutscene', 'lerp', 'tutorial')
    hit = sum(1 for k in ('%s:%d' % (ch, i) for ch, i in iso)
              if any(w in names[k].lower() for w in KW))
    check('C2 ★ 命名启发式**不足以**判定（孤立房里只有 %.0f%% 名字带调试/演出特征）'
          % (100.0 * hit / max(1, len(iso))),
          hit < len(iso) * 0.9,
          '命中 %d/%d' % (hit, len(iso)))
    both = sorted({names[k] for k in names
                   if names[k] and names[k] in
                   {names['%s:%d' % (c, j)] for c, j in real}
                   and names[k] in {names['%s:%d' % (c, j)] for c, j in iso}})
    check('C3 ★★ 同名不同命（%r 同时落在"有门/无门"两侧）⇒ 只能看门图' % both[:2],
          bool(both), '同名=%r' % both)
    check('C4 31 间孤立未覆盖房在原作门图里 in=0 且 out=0',
          all((deg.get(ch, {}).get(i) or {'in': 0, 'out': 0})['in'] == 0
              and (deg.get(ch, {}).get(i) or {'in': 0, 'out': 0})['out'] == 0
              for ch, i in iso))
    print()
    print('   [INFO] ch1/2/4/5：原作 1,005 间 / playable 853 / 已覆盖 812 / '
          '未覆盖 41 = 真缺口 10 + 孤立 31')

    print()
    print('=== RESULT: PASS=%d FAIL=%d ===' % (PASS, FAIL))
    return 0 if FAIL == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
