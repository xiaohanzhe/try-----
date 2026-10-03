# -*- coding: utf-8 -*-
u"""第81轮 · 层4 存档**端到端往返**实测（真 import 真跑，落 E:\\Download\\_tmp）。"""
import io
import os
import shutil
import sys
import tempfile

REPO = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..')
sys.path.insert(0, os.path.join(REPO, 'ralsei_pet'))
sys.path.insert(0, os.path.join(REPO, 'ralsei_pet', 'modules'))

from modules import npc_roam as nr
from modules import npc_intent as ni
from modules import npc_plan_store as nps

PASS = 0
FAIL = 0


def ok(cond, msg):
    global PASS, FAIL
    if cond:
        PASS += 1
        print('[PASS] %s' % msg)
    else:
        FAIL += 1
        print('[FAIL] %s' % msg)


tmp = tempfile.mkdtemp(prefix='ralsei_l4_')
path = os.path.join(tmp, 'npc_life.json')

try:
    # ---- 1. 造一个"世界"：驻留表 + 规划 ----
    roam = nr.RoamState(enabled=True)
    roam.put('susie', 'ch1.town.town_church', now=1000.0, dwell=600.0, reason='wander')
    roam.put('lancer', 'ch1.card_castle.cc_prison', now=1000.0, dwell=600.0,
             reason='wander')

    book = nps.Book(roam=roam)
    p = book.plan_of('susie')
    p.day = 42
    p.note(ni.Intent('go_scene', 'ch1.town.town_church', why='wander'))
    p.note(ni.Intent('visit_friend', None, who='lancer', why='social'))
    book.note_sleep('susie', 'ch1.kris_room.kris_room')
    book.plan_of('lancer').note(ni.Intent('stay', None, why='idle'))

    ok(nps.save(path, book) is True, '1 save() 返回 True')
    ok(os.path.isfile(path), '1 文件真在盘上：%s' % path)

    # ---- 2. 重读 ----
    book2 = nps.load(path)
    ok(book2 is not None, '2 load() 不返回 None')
    ok(book2.roam is not None, '2 ★★ 驻留表被还原（不是 None）')
    ok(book2.roam.resident_of('susie') == 'ch1.town.town_church',
       '2 ★ 驻留真还原：susie @ %r' % (book2.roam.resident_of('susie'),))
    ok(book2.roam.resident_of('lancer') == 'ch1.card_castle.cc_prison',
       '2 ★ 驻留真还原：lancer')
    ok(sorted(book2.ids()) == ['lancer', 'susie'],
       '2 ★ 两人规划都在：%s' % (book2.ids(),))
    ok(book2.last_sleep_of('susie') == 'ch1.kris_room.kris_room',
       '2 ★★★ **昨晚睡哪**真还原（层4 的核心）：%r'
       % (book2.last_sleep_of('susie'),))
    su = book2.plan_of('susie')
    ok(su.day == 42, '2 day 真还原：%r' % (su.day,))
    ok(len(su.history) == 2, '2 history 真还原：%d 条' % len(su.history))
    ok(getattr(su.intent, 'what', None) == 'visit_friend',
       '2 ★★ **上一次意图**真还原（`decide(last=...)` 吃的就是这个）：%r'
       % (getattr(su.intent, 'what', None),))

    # ---- 3. ★★★ 闭环：还原出来的 last_sleep 真能影响下一次决策 ----
    #   （"函数写对了 ≠ 产品用上了" —— 这里断的是**产品路径**上的效果）
    #   ★ 夹具关键：**家**与**朋友家**必须是两个**不同**的地点，否则两条路都指向
    #     同一个 scene，降权没有可比较对象（第一版就写错成同一个地点 ⇒ 200/200 平手，
    #     那是**夹具**的问题，不是产品的问题）。
    HOME = 'ch1.kris_room.kris_room'
    FRIEND_HOME = 'ch1.town.town_home'      # 朋友家 = 另一个地点
    scenes = [HOME, FRIEND_HOME]
    hits = {}
    for tag, ls in (('none', None), ('friend', FRIEND_HOME)):
        n = 0
        for day in range(400):
            s, _why = ni.choose_sleep_scene(
                'susie', 1000.0 + day * 86400,
                home=HOME,
                friends=[('lancer', 1.0, FRIEND_HOME)],
                reachable=scenes, last_sleep=ls)
            if s == HOME:
                n += 1
        hits[tag] = n
    #   ★ 方向别搞反：`last_sleep=FRIEND_HOME` ⇒ 被 ×0.6 削的是**朋友家**
    #     ⇒ 相对地，**自己家**被选中的次数应当**上升**（hits['none'] < hits['friend']）。
    #     ★★ 判据第一版把方向写反了（`>`），被这条真跑抓出来 —— 又一次印证
    #     「判据本身也是被测物」。
    ok(hits['none'] < hits['friend'],
       '3 ★★★ 连睡降权**真生效**：无记忆时 400 天选**自己家** %d 次，'
       '昨睡朋友家后升到 %d 次（朋友家被 ×0.6 削 ⇒ 自己家相对更常被选）'
       % (hits['none'], hits['friend']))

    # ---- 4. 容错（绝不抛）----
    with io.open(os.path.join(tmp, 'junk.json'), 'w', encoding='utf-8') as fh:
        fh.write('{ this is not json ]')
    ok(nps.load(os.path.join(tmp, 'junk.json')).ids() == [],
       '4 坏 JSON ⇒ 空书（不抛）')
    ok(nps.load(os.path.join(tmp, 'nope.json')).ids() == [],
       '4 不存在的路径 ⇒ 空书（不抛）')
    ok(nps.load(None).ids() == [], '4 path=None ⇒ 空书（不抛）')
    ok(nps.save(None, book) is False, '4 save(None) ⇒ False（不抛）')

    # ---- 5. 版本不符 ⇒ 空书（不静默读半截）----
    import json
    with io.open(os.path.join(tmp, 'v9.json'), 'w', encoding='utf-8') as fh:
        json.dump({'schema_version': 9, 'plans': {'x': {}}}, fh)
    ok(nps.load(os.path.join(tmp, 'v9.json')).ids() == [],
       '5 schema_version 不符 ⇒ 空书（不把陌生结构当真）')

    # ---- 6. 原子写：不留 .tmp 残骸 ----
    ok(not os.path.exists(path + '.tmp'), '6 原子写不留 .tmp 残骸')

    # ---- 7. WIRING 诚实 ----
    ok(nps.WIRING['wired'] is True, '7 ★ npc_plan_store.WIRING wired=True')
    ok(nps.WIRING['not_yet'] == [], '7 ★★ not_yet 已清空（不留谎）')
    ok(len(nps.WIRING['used_by']) >= 4, '7 used_by 逐条登记（%d 条）'
       % len(nps.WIRING['used_by']))
    ok(ni.WIRING['wired'] is True, '7 ★ npc_intent.WIRING wired 翻正 =True')
    ok(ni.WIRING['not_yet'] == [], '7 ★★ npc_intent not_yet 已清空')
    ok(nr.WIRING['not_yet'] == [], '7 ★★ npc_roam not_yet 已清空')
    ok('npc_plan_store' in ' '.join(nr.WIRING['used_by']),
       '7 ★ npc_roam.used_by 登记了 npc_plan_store')

    # ---- 8. 文件名同源（main.NPC_LIFE_FILE == npc_plan_store.FILENAME）----
    ok(nps.FILENAME == 'npc_life.json',
       '8 FILENAME == %r' % (nps.FILENAME,))

    print('')
    print('PASS=%d FAIL=%d' % (PASS, FAIL))
finally:
    shutil.rmtree(tmp, ignore_errors=True)
