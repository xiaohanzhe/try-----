# -*- coding: utf-8 -*-
"""第87轮 R1「每人一个家」：建立**家表**（每条可回证）。

用户裁定（逐字）：
  「迁入场景后再找对应的，然后npc就按原作的分布规律来就好，
    oneshot那个就放在他游戏最后那个光门后面（原作最后出现他回家要跨过的拿到门，
    就安置在那里面，相当于没有，然后oneshot世界的入口你就用原作里的门就好）」
  ＋「立刻参与（推荐）」＋「标 authored，按原作分布规律安家（推荐）」

家表口径（三级证据）：
  · original —— 原作**硬证据**：对象实例落点 / 房间名直指（可回证到 _evidence/*.json）
  · derived  —— 场景语义强推（如"蒸汽工厂工作间"→Guardener 当班处）
  · authored —— 证据不足，按原作分布规律安家（**诚实标注，不冒充原作**）

输出：E:/_tmp87/build/homes87.json（中间产物，供 build_placement87.py 消费）
"""
import io, json, os

ROOT = r'C:/Users/23002/Desktop/项目文件夹/try - 副本'
EV = os.path.join(ROOT, 'code-quality-audit', '第87轮-每人一个家', '_evidence')
SC = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes')
NPC = os.path.join(ROOT, 'ralsei_pet', 'assets', 'npc')


def L(p):
    with io.open(p, encoding='utf-8') as f:
        return json.load(f)


def build_index():
    idx = L(os.path.join(SC, '_index.json'))
    by_room = {}
    for ch, cv in idx['chapters'].items():
        for an, av in (cv.get('areas') or {}).items():
            for sid, sv in (av.get('scenes') or {}).items():
                by_room[(ch, sv['name'])] = sid
    return by_room


# ---------------------------------------------------------------------------
# UT 家表：npc_id -> (房间名, source, evidence)
# evidence 必须能回证到 _evidence/ut_instances87.json 里的对象落点或房间名
# ---------------------------------------------------------------------------
UT_HOMES = {
    'ut_toriel':       ('room_torhouse1', 'original',
                        '房间名 room_torhouse1/2/3（Toriel 家）+ 实例 obj_torgen_house1(84,24) / obj_housemusic(260,20)'),
    'ut_frisk':        ('room_asrielroom', 'original',
                        '★用户点名"Toriel 家给他那间房"⇒ 原作给他睡的是 Asriel 旧房：room_asrielroom 有 obj_asrielbed(192,114)（唯一带床的客房）'),
    'ut_sans':         ('room_tundra_sanshouse', 'original',
                        '房间名 room_tundra_sanshouse + 实例 obj_npc_room(176,132)'),
    'ut_papyrus':      ('room_tundra_paproom', 'original',
                        '房间名 room_tundra_paproom + 实例 obj_papyrus_hisroom(206,150) + obj_carbed(45,145)'),
    'ut_undyne':       ('room_water_undynehouse', 'original',
                        '房间名 room_water_undynehouse（Undyne 家）'),
    'ut_napstablook':  ('room_water_blookhouse', 'original',
                        '房间名 room_water_blookhouse + 邻房 room_water_blookyard 的 obj_blookhouses(60,20)'),
    'ut_asgore':       ('room_asghouse1', 'original',
                        '房间名 room_asghouse1/2/3（Asgore 家）'),
    'ut_gaster':       ('room_gaster', 'original',
                        '房间名 room_gaster + 实例 obj_gaster_room(0,0)'),
    'ut_muffet':       ('room_fire_spidershop', 'original',
                        '房间名 room_fire_spidershop（Muffet 的蜘蛛甜品店＝她的住处兼店面）'),
    'ut_mettaton':     ('room_fire_hotellobby', 'derived',
                        'M6 旅馆大堂 room_fire_hotellobby（Mettaton 的演出主场馆；原作无"他的家"）'),
    'ut_alphys':       ('room_fire_lab2', 'derived',
                        'Alphys 的实验室 room_fire_lab2（她在原作常驻处；原作无"她的家"）'),
    'ut_flowey':       ('room_floweyx', 'derived',
                        'Flowey 无家（原作无居所）⇒ 归到其登场房之一 room_floweyx'),
    'ut_monster_kid':  ('room_water_bird', 'derived',
                        'Monster Kid 无家（原作无居所）⇒ 归到其常驻区 room_water_bird（obj_mkid_goner 在 room_water7 / obj_mkid_shadow 在 room_water_waterfall3）'),
    'ut_chara':        ('room_end_myroom', 'derived',
                        'Chara 无现世家（原作仅回忆）⇒ 归到 room_end_myroom（结局"我的房间"）'),
}

# ---------------------------------------------------------------------------
# 黄魂（UTY）家表
# ---------------------------------------------------------------------------
UTY_HOMES = {
    'hy_dalv':              ('rm_dalvshouse', 'original',
                             '房间名 rm_dalvshouse + 实例 obj_doorway_blocker_dalvshouse(200,50)；邻房 rm_dalvsroom'),
    'hy_ceroba_ketsukane':  ('rm_mansion_kanakos_room', 'original',
                             'Ketsukane 宅邸：rm_mansion_kanakos_room 有 obj_mansion_kanako_bed(136,95)（女儿房）＋ rm_mansion_hallway_east_2 的 obj_mansion_hall_bedroom_door(122,490)'),
    'hy_clover':            ('rm_dunes_01', 'derived',
                             'Clover 从 rm_dunes_01 开局（原作起点）⇒ 视作其归属地；原作无"他的家"'),
    'hy_martlet':           ('rm_snowdin_06_yellow', 'original',
                             'Snowdin 段：rm_snowdin_06_yellow 有 obj_martlet_snowdin_06（Martlet 常驻）'),
    'hy_starlo':            ('rm_dunes_37', 'original',
                             'Wild East 镇：rm_dunes_37 有 obj_wild_east_feisty_house(232,309) / obj_wild_east_house_1(519,619)；Starlo 是镇长'),
    'hy_axis':              ('rm_steamworks_27', 'derived',
                             'Steamworks 机器人：rm_steamworks_27 有 obj_guardener_bot_3（同区机器人）；Axis 原作在 Steamworks 当班'),
    'hy_guardener':         ('rm_steamworks_29', 'original',
                             'rm_steamworks_29 有 obj_guardener_bot_1(92 实例) 明确落点'),
    'hy_sousborg':          ('rm_steamworks_chem_03', 'derived',
                             'Steamworks 化学区 rm_steamworks_chem_03（Sousborg 的蒸汽厨区）'),
    'hy_bowll':             ('rm_dunes_24', 'original',
                             'rm_dunes_24 有 obj_bowll_overworld 明确落点'),
    'hy_chujin_ketsukane':  ('rm_steamworks_11', 'derived',
                             'Chujin（Ceroba 亡夫）生前在 Steamworks 工作 ⇒ 归其工位区；另见 obj_mansion_chujin_grave'),
    'hy_ace':               ('rm_dunes_38', 'derived',
                             'rm_dunes_38 属 Wild East 镇区（Ace 为镇民）'),
    'hy_ed':                ('rm_dunes_37_feistyhouse', 'original',
                             'rm_dunes_37_feistyhouse 有 obj_wild_east_feisty_house_controller / obj_fesityhouse_dynamic_music'),
    'hy_mooch':             ('rm_dunes_30_house_1', 'authored',
                             '证据不足：原作未给 Mooch 明确居所 ⇒ 按"矿区住户"分布规律安置（house_1）'),
    'hy_moray':             ('rm_dunes_30_house_2', 'authored',
                             '证据不足：原作未给 Moray 明确居所 ⇒ 按"矿区住户"分布规律安置（house_2）'),
    'hy_flowey':            ('rm_dunes_01', 'derived',
                             'Flowey 无家（原作无居所）⇒ 归到开局区 rm_dunes_01'),
}

# ---------------------------------------------------------------------------
# OneShot：用户裁定 —— 全部安置在**最后那道光门之后**，世界入口用原作门
# ---------------------------------------------------------------------------
OS_HOME = ('FINALE', 'authored',
           '★用户逐字裁定：「oneshot那个就放在他游戏最后那个光门后面（原作最后出现他回家要跨过的拿到门，'
           '就安置在那里面，相当于没有，然后oneshot世界的入口你就用原作里的门就好）」')


def main():
    by_room = build_index()
    reg = L(os.path.join(NPC, '_registry.json'))
    ids = [n['id'] for n in reg['npcs']]

    rows, miss, nohome, ot_pending = [], [], [], []
    for nid in ids:
        spec = None
        if nid in UT_HOMES:
            spec = ('ut',) + UT_HOMES[nid]
        elif nid in UTY_HOMES:
            spec = ('uty',) + UTY_HOMES[nid]
        elif nid.startswith('os_'):
            spec = ('oneshot',) + OS_HOME
        if spec is None:
            if nid.startswith('ot_'):
                # ★ 第87轮新发现：_registry.json 注册了 11 个 Outertale NPC（sprite 也已抽，
            #   sprites/ot=150），但 **_index.json 没有 outertale 章** ⇒ 无处可安家。
                # 如实记录，不硬安（待 Outertale 迁入）。
                ot_pending.append(nid)
            else:
                nohome.append(nid)
            continue
        ch, room, src, why = spec
        sid = by_room.get((ch, room))
        if sid is None:
            miss.append((nid, ch, room))
            continue
        rows.append({'id': nid, 'scene': sid, 'chapter': ch, 'room': room,
                     'source': src, 'why': why})

    out = {'round': 87, 'homes': rows, 'miss': miss, 'nohome': nohome,
           'outertale_pending': ot_pending,
           'counts': {'homes': len(rows), 'miss': len(miss),
                      'nohome_deltarune': len(nohome), 'outertale_pending': len(ot_pending)}}
    p = r'E:/_tmp87/build/homes87.json'
    with io.open(p, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print('homes=%d miss=%d nohome(dr)=%d outertale_pending=%d' % (len(rows), len(miss), len(nohome), len(ot_pending)))
    if miss:
        print('MISS:', miss)
    from collections import Counter
    print('by source=', dict(Counter(r['source'] for r in rows)))
    print('write ->', p)


if __name__ == '__main__':
    main()
