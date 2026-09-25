# -*- coding: utf-8 -*-
"""第49轮：建目录 + 生成 UTMT 名字清单。"""
import io
import os
import time

HERE = os.path.dirname(os.path.abspath(__file__))          # .../第49轮-NPC与球容器/_tools
ROUND = os.path.abspath(os.path.join(HERE, '..'))          # .../第49轮-NPC与球容器
for sub in ('', '_tools', '_evidence', '_evidence/gml'):
    d = os.path.join(ROUND, sub) if sub else ROUND
    if not os.path.isdir(d):
        os.makedirs(d)

# 各章要反编译的 code 名（对象事件 + 脚本）
NAMES = {
    'chapter1_windows': [
        # 球/容器 类
        'obj_ch2_capsule',
        # 跟随机制
        'obj_thrashafter_follow', 'obj_following_silhouette',
        # 关键 NPC
        'obj_npc_toriel', 'obj_darklancer', 'obj_lancerguide',
        'obj_lancerboss', 'obj_lancerboss2', 'obj_lancerboss3', 'obj_king_boss',
        'obj_npc_hammerguy', 'obj_npc_puzzlemaster1', 'obj_npc_puzzlemaster2',
        'obj_npc_sign', 'obj_npc_room', 'obj_npc_facing', 'obj_npc_room_animated',
        'obj_npc_susiedark',
        # 队伍
        'obj_herosusie', 'obj_herokris', 'obj_heroralsei',
    ],
    'chapter2_windows': [
        'obj_ch2_capsule',
        'obj_following_silhouette', 'obj_maus_cursor_follow',
        'obj_npc_toriel', 'obj_npc_king', 'obj_npc_rudy', 'obj_npc_catti',
        'obj_npc_conbini', 'obj_npc_police', 'obj_npc_hammerguy',
        'obj_npc_sign', 'obj_npc_dumpster', 'obj_npc_addison_tea',
        'obj_npc_mansion_room', 'obj_npc_susiedark',
        'obj_darklancer', 'obj_lancer_mixtape', 'obj_pushable_lancer',
        'obj_queen_ralseithrown', 'obj_queen_throwkris',
        'obj_spamton_enemy', 'obj_spamton_neo_enemy',
        'obj_berdlyb_enemy', 'obj_berdlyb2_enemy', 'obj_berdlyb2_postBattle_noelle',
        'obj_herosusie', 'obj_herokris', 'obj_heroralsei', 'obj_heronoelle',
    ],
    'chapter3_windows': [
        # ★ 球的主要候选（用户所指「第3章很多扭蛋的那个球」）
        'obj_ch3_gachapon', 'obj_ch3_ballcon', 'obj_ch3_gachaunknown',
        'obj_ch3_GSC07_gacha', 'obj_tenna_board4_gacha',
        'obj_ilovetv',
        # 跟随
        'obj_heart_follower', 'obj_heart_follower_overshoot',
        # 关键角色
        'obj_actor_tenna', 'obj_tenna_enemy', 'obj_tenna_marker',
        'obj_dw_tv_curtain_tennanpc', 'obj_ch3_PTB02_toriel',
        'obj_b1lancer', 'obj_board_lancermoat', 'obj_board_lancerswitch',
        'obj_npc_toriel', 'obj_npc_king', 'obj_npc_susiedark',
        'obj_kris_putonheadobj', 'obj_kris_headobj',
        'obj_herosusie', 'obj_herokris', 'obj_heroralsei',
    ],
    'chapter4_windows': [
        'obj_followinglight', 'obj_light_following', 'obj_followinglight_shrinking',
        'obj_dw_church_gerson_follow', 'obj_follow_spear',
        'obj_npc_gerson', 'obj_npc_toriel', 'obj_npc_king',
        'obj_multiboss_controller', 'obj_mike_lancer',
        'obj_room_castle_lancer', 'obj_room_castle_tenna', 'obj_room_castle_queen',
        'obj_herosusie', 'obj_herokris', 'obj_heroralsei',
    ],
    'chapter5_windows': [
        'obj_ch5_DW30_asgore', 'obj_dw_fcastle_asgore', 'obj_town_north_asgore',
        'obj_flowery_throwkris', 'obj_plat_follower', 'obj_plat_followercue',
        'obj_npc_toriel', 'obj_npc_doubter', 'obj_npc_castle_cafe',
        'obj_npc_rabbits', 'obj_npc_wrapper',
        'obj_herosusie', 'obj_herokris', 'obj_heroralsei',
    ],
}

# 全局脚本（每章都取一份）
SCRIPTS = [
    'scr_setparty', 'scr_makecaterpillar', 'scr_resetparty',
]

out = r'E:\Download\_tmp\drw'
REPO_COPY = os.path.join(ROUND, '_evidence', 'names49')
if not os.path.isdir(REPO_COPY):
    os.makedirs(REPO_COPY)


def _write(path, text, tries=6):
    """E:\\Download 侧偶发 OSError 22/13（已知间歇故障）⇒ 重试；仓库侧必写。"""
    last = None
    for i in range(tries):
        try:
            with io.open(path, 'w', encoding='utf-8', newline='\n') as fh:
                fh.write(text)
            return True
        except OSError as e:
            last = e
            time.sleep(0.6)
    print('   !! 写入失败 %s : %s' % (path, last))
    return False


for ch, objs in NAMES.items():
    names = []
    for o in objs:
        if o not in names:
            names.append(o)
    for s in SCRIPTS:
        for pre in ('gml_GlobalScript_', 'gml_Script_'):
            n = pre + s
            if n not in names:
                names.append(n)
    text = '\n'.join(names) + '\n'
    _write(os.path.join(REPO_COPY, ch + '.txt'), text)
    d = os.path.join(out, ch)
    if not os.path.isdir(d):
        print('SKIP(no dir)', ch)
        continue
    ok = _write(os.path.join(d, 'dump_names49.txt'), text)
    print('%-20s %d 条  ->drw:%s' % (ch, len(names), ok))
