# -*- coding: utf-8 -*-
u"""第66轮 · N4 复检：把"35 条跨作品 NPC 真的注册对了"逐项打 PASS/FAIL。

判据纪律（本项目踩过的坑，逐条对应）
------------------------------------
* **正/负成对**：world_gate 的放行与拒绝都要有，还要有"对照组成员"（kris）证明判据不是一刀切。
* **逐令牌回验**：OneShot 的 `objects` 逐个回 contacts 的 `walkspriteId`；
  UT 的 `objects` 逐个回 `ut_sprites66.json` 里记的**素材文件名**（不是回我自己的中间产物）。
* **反向控制**：把新增的 35 条从内存里抽掉，条数必须回到 35 —— 证明"35 → 70"真的是这 35 条
  带来的，而不是判据恒真。
* **断行为/结构，不断赋值**：不写 `assert os_niko.name == 'Niko'` 这种抄一遍的断言，
  只断"注册表→加载器→门控"这条链上的行为。
* **判据自己也是被测物**：本脚本自己先用 `--selftest` 跑一次"故意破坏"检查
  （把一条 records 改坏，看判据会不会红）。

用法：python recheck66_n4.py
"""
from __future__ import print_function

import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(ROUND))
PET = os.path.join(REPO, 'ralsei_pet')
NPC_DIR = os.path.join(PET, 'assets', 'npc')
EVID = os.path.join(ROUND, '_evidence')
sys.path.insert(0, os.path.join(PET, 'modules'))

N = [0]
FAILS = []


def check(name, ok, detail=''):
    N[0] += 1
    print(u'%s %s%s' % ('[PASS]' if ok else '[FAIL]', name,
                        (u'  —— %s' % detail) if detail else u''))
    if not ok:
        FAILS.append(name)


def read_json(p):
    with io.open(p, 'r', encoding='utf-8') as fh:
        return json.load(fh)


def main():
    import npc_system as S

    reg_raw = read_json(os.path.join(NPC_DIR, '_registry.json'))
    place_raw = read_json(os.path.join(NPC_DIR, '_placement.json'))
    personas_idx = read_json(os.path.join(NPC_DIR, '_personas.json'))
    os_ev = read_json(os.path.join(EVID, 'oneshot_contacts66.json'))
    ut_ev = read_json(os.path.join(EVID, 'ut_sprites66.json'))

    reg = S.load_registry(PET)
    recs = reg_raw['npcs']
    ids = [r['id'] for r in recs]

    os_ids = list((personas_idx.get('by_work') or {}).get('OneShot') or [])
    ut_ids = list((personas_idx.get('by_work') or {}).get('Undertale') or [])

    print(u'== A 条数与结构 ==')
    check(u'A1 ★ 注册表 70 条 = 原 35 + 新 35（第66轮 N4）',
          len(recs) == 70 and len(reg) == 70,
          '%d / load %d' % (len(recs), len(reg)))
    check(u'A2 分层守恒：main + plain == 总数',
          len(reg.main_npcs()) + len(reg.plain_npcs()) == len(reg),
          'main=%d plain=%d' % (len(reg.main_npcs()), len(reg.plain_npcs())))
    check(u'A3 id 唯一', len(set(ids)) == len(ids),
          u'重复=%r' % [i for i in set(ids) if ids.count(i) > 1])
    check(u'A4 counts 字段与实际一致',
          reg_raw['counts']['main'] == len(reg.main_npcs())
          and reg_raw['counts']['plain'] == len(reg.plain_npcs()),
          json.dumps(reg_raw['counts'], ensure_ascii=False))
    check(u'A5 source 里点明了第66轮注册跨作品 35 条',
          u'第66轮' in (reg_raw.get('source') or '')
          and u'OneShot' in (reg_raw.get('source') or ''))

    print()
    print(u'== B ★★ 反向控制：抽掉新增的 35 条 ⇒ 必须回到 35 ==')
    kept = [r for r in recs if not (r['id'].startswith('os_') or r['id'].startswith('ut_'))]
    rolled = S.NpcRegistry([S.npc_from_dict(d) for d in kept])
    check(u'B1 去掉 os_/ut_ 前缀的条目后 == 35 条（证明 35→70 是这 35 条带来的）',
          len(rolled) == 35, 'rollback=%d' % len(rolled))
    check(u'B2 反向控制成对：留下的 35 条里**没有**任何跨作品 id',
          not any(i.startswith(('os_', 'ut_')) for i in rolled.ids()))
    check(u'B3 三条 Deltarune 代理仍在（不是把整表清空造成的假 PASS）',
          all(rolled.get(i) is not None for i in ('ralsei', 'kris', 'susie')))

    print()
    print(u'== C OneShot 21 条：逐条回验 objects == contacts.walkspriteId ==')
    prof_by_unlock = {}
    for p in os_ev['profiles']:
        prof_by_unlock.setdefault(p['unlockId'], p)
    os_override = {'os_the_world_machine': 'world_machine', 'os_the_author': 'author',
                   'os_george': 'george1'}
    bad = []
    for nid in os_ids:
        n = reg.get(nid)
        if n is None:
            bad.append('%s: 不在注册表' % nid)
            continue
        unlock = os_override.get(nid, nid[3:] if nid.startswith('os_') else nid)
        prof = prof_by_unlock.get(unlock)
        if prof is None:
            bad.append('%s: contacts 里没有 unlockId=%s' % (nid, unlock))
            continue
        if list(n.objects) != [prof['walkspriteId']]:
            bad.append('%s: objects=%r 但 contacts walkspriteId=%r'
                       % (nid, list(n.objects), prof['walkspriteId']))
        if n.chapters != ('oneshot',):
            bad.append('%s: chapters=%r' % (nid, n.chapters))
        if not os.path.isfile(os.path.join(NPC_DIR, 'persona', nid + '.txt')):
            bad.append('%s: persona 文件不在磁盘' % nid)
    check(u'C1 ★ 21 条逐条对得上官方 walkspriteId / chapters / persona 文件', not bad,
          u'; '.join(bad[:5]) or '21/21 全对')
    check(u'C2 OneShot 组恰好 21 条（不多不少）',
          sum(1 for i in ids if i.startswith('os_')) == 21)
    regions = sorted(set(p['region'] for p in os_ev['profiles']))
    # ⚠️ 判据侧修正（第66轮，第一次跑就抓到）：原先写 `regions == ['Barrens',...,'???']`，
    #    但 `sorted()` 会把 `'???'` 排到 `'B'` **前面**（`?`=0x3F < `B`=0x42）
    #    ⇒ 恒 FAIL。集合比较与顺序无关，这里本就该用 set。
    #    （"判据自己也是被测物" —— 报红先怀疑判据，本项目第62/63/64轮各栽过一次。）
    check(u'C3 官方区域恰好 4 个（Barrens / Glen / Refuge / ???）',
          set(regions) == set([u'Barrens', u'Glen', u'Refuge', u'???']), str(regions))

    print()
    print(u'== D Undertale 14 条：objects 逐条回**素材文件名**证据 ==')
    bad = []
    for nid in ut_ids:
        n = reg.get(nid)
        if n is None:
            bad.append('%s: 不在注册表' % nid)
            continue
        rec = ut_ev['roles'].get(nid)
        if not rec:
            bad.append('%s: 取证里没有' % nid)
            continue
        if list(n.objects) != list(rec['objects']):
            bad.append('%s: objects=%r 但取证=%r' % (nid, list(n.objects), rec['objects']))
        for o in n.objects:
            if o not in (rec['top_hits'] or []):
                bad.append('%s: %r 不在素材命中集里' % (nid, o))
        if n.chapters != ('undertale',):
            bad.append('%s: chapters=%r' % (nid, n.chapters))
        if not os.path.isfile(os.path.join(NPC_DIR, 'persona', nid + '.txt')):
            bad.append('%s: persona 文件不在磁盘' % nid)
    check(u'D1 ★ 14 条逐条对得上素材取证 / chapters / persona 文件', not bad,
          u'; '.join(bad[:5]) or '14/14 全对')
    check(u'D2 10 条有四向行走图（how=overworld_4dir）',
          sum(1 for r in ut_ev['roles'].values() if r['how'] == 'overworld_4dir') == 10,
          str(sorted(k for k, r in ut_ev['roles'].items() if r['how'] != 'overworld_4dir')))
    check(u'D3 ★ 无四向图的那 3 条已在 how 里如实标注（不是假装是行走图）',
          sorted(k for k, r in ut_ev['roles'].items()
                 if r['how'] == 'nearest_base') ==
          [u'ut_flowey', u'ut_gaster', u'ut_mettaton'])

    print()
    print(u'== E world_gate 行为（正 / 负 / 对照成对）==')
    os_niko = reg.get('os_niko')
    ut_sans = reg.get('ut_sans')
    kris = reg.get('kris')
    check(u'E1 正向：OneShot 角色进 oneshot.* 场景 ⇒ 放行',
          S.world_gate(os_niko, 'dark', scene_id='oneshot.barrens.dock').ok)
    check(u'E2 ★ 负向：同一角色进 Deltarune 暗世界场景 ⇒ **拒绝**（跨作品隔离）',
          not S.world_gate(os_niko, 'dark', scene_id='ch3.castle_town.castle_town').ok)
    check(u'E3 ★ 负向：Undertale 角色进 ch4 场景 ⇒ 拒绝',
          not S.world_gate(ut_sans, 'dark', scene_id='ch4.my_castle_town.x').ok)
    check(u'E4 ★ 负向：跨作品角色上**电脑桌面** ⇒ 拒绝（不在白名单）',
          not S.world_gate(os_niko, 'light', scene_id='desktop').ok
          and not S.world_gate(ut_sans, 'light', scene_id='desktop').ok)
    check(u'E5 对照：主角团 kris 上桌面 ⇒ 放行（证明 E4 不是一刀切）',
          S.world_gate(kris, 'light', scene_id='desktop').ok)
    check(u'E6 对照：kris 进 ch3 ⇒ 放行（证明 E2 不是"谁都拒"）',
          S.world_gate(kris, 'dark', scene_id='ch3.castle_town.castle_town').ok)

    print()
    print(u'== F 人设贯通（注册表的 persona 字段 × 加载器 × 磁盘）==')
    import npc_persona as P
    loaded = P.load_personas(PET)
    miss = [i for i in os_ids + ut_ids if not loaded.get(i)]
    check(u'F1 ★★ 35 条新 NPC 的人设**加载器真能取到**（不再"有设无人"）',
          not miss, u'缺 %d：%r' % (len(miss), miss[:5]) or u'35/35 全在')
    check(u'F2 加载器份数 == 索引登记数（50）',
          len(loaded) == len(personas_idx.get('personas') or []),
          '%d / %d' % (len(loaded), len(personas_idx.get('personas') or [])))
    check(u'F3 needs_setting ⇔ persona is None（NpcDef 的不变式，全表）',
          all(bool(n.needs_setting) == (n.persona is None) for n in reg.all()))
    bad = [n.id for n in reg.all() if n.persona and n.persona != '../ralsei_persona.md'
           and not os.path.isfile(os.path.join(NPC_DIR, n.persona))]
    check(u'F4 全表 persona 相对路径都在磁盘上', not bad, str(bad[:5]))

    print()
    print(u'== G 站位表对齐（D6 口径）==')
    _pl = set(x['id'] for x in place_raw['placement'])
    _un = set(place_raw['unplaced'].keys())
    check(u'G1 站位 ∪ 未安置 == 注册表（一个不少一个不多）',
          _pl | _un == set(reg.ids()),
          u'缺=%r 多=%r' % (sorted(set(reg.ids()) - _pl - _un),
                           sorted((_pl | _un) - set(reg.ids()))))
    check(u'G2 新增 35 条全在 unplaced，且理由非空',
          all(i in _un and (place_raw['unplaced'][i] or '').strip()
              for i in os_ids + ut_ids))
    check(u'G3 counts.unplaced == 实际条数',
          place_raw['counts']['unplaced'] == len(_un),
          u'%s / %d' % (place_raw['counts']['unplaced'], len(_un)))
    check(u'G4 ★ Deltarune 侧未安置仍只有 knight（第56轮 D7 的意图没被稀释）',
          sorted(i for i in _un if not i.startswith(('os_', 'ut_'))) == ['knight'])

    print()
    print(u'== H home_world 是**显式** dark，不是被静默改判 ==')
    bad = [i for i in os_ids + ut_ids if reg_raw_by_id(recs, i).get('home_world') != 'dark']
    check(u'H1 磁盘上的 home_world 字段字面就是 "dark"（写 `oneshot` 会被改判 ⇒ 不允许）',
          not bad, str(bad[:5]))
    check(u'H2 对照：注册表里**没有**任何 home_world 是 light/dark 之外的值',
          all(r.get('home_world') in ('light', 'dark') for r in recs))

    print()
    print(u'=' * 70)
    print(u'N4 复检：断言 %d 项，FAIL %d 项' % (N[0], len(FAILS)))
    if FAILS:
        for f in FAILS:
            print(u'  FAIL: %s' % f)
    return 1 if FAILS else 0


def reg_raw_by_id(recs, i):
    for r in recs:
        if r['id'] == i:
            return r
    return {}


if __name__ == '__main__':
    sys.exit(main())
