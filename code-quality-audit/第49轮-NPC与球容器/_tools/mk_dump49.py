# -*- coding: utf-8 -*-
"""第49轮 · 从 names49 关键词命中里挑出「目标对象/脚本的全部事件 code」，
写成 dump_names49.txt（供 dump49.csx 反编译）。

用法: C:\\Python311\\python.exe mk_dump49.py
"""
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
HITS = os.path.join(ROUND, '_evidence', 'names49')
DRW = r'E:\Download\_tmp\drw'

# 每章要取的对象（含全部事件）与脚本（GlobalScript + Script 双写）
TARGETS = {
    1: (
        ['obj_npc_toriel', 'obj_darklancer', 'obj_lancerguide', 'obj_lancerboss',
         'obj_lancerboss2', 'obj_lancerboss3', 'obj_king_boss',
         'obj_thrashafter_follow', 'obj_npc_hammerguy', 'obj_npc_sign',
         'obj_npc_room', 'obj_npc_facing', 'obj_npc_room_animated',
         'obj_npc_puzzlemaster1', 'obj_npc_puzzlemaster2', 'obj_npc_susiedark',
         'obj_herosusie', 'obj_herokris', 'obj_heroralsei'],
        ['scr_setparty', 'scr_makecaterpillar'],
    ),
    2: (
        ['obj_ch2_capsule', 'obj_following_silhouette', 'obj_npc_toriel',
         'obj_npc_king', 'obj_npc_rudy', 'obj_npc_catti', 'obj_npc_conbini',
         'obj_npc_police', 'obj_npc_hammerguy', 'obj_npc_sign', 'obj_npc_dumpster',
         'obj_npc_addison_tea', 'obj_npc_mansion_room', 'obj_npc_susiedark',
         'obj_darklancer', 'obj_pushable_lancer', 'obj_spamton_enemy',
         'obj_spamton_neo_enemy', 'obj_berdlyb_enemy', 'obj_berdlyb2_enemy',
         'obj_herosusie', 'obj_herokris', 'obj_heroralsei', 'obj_heronoelle'],
        ['scr_draw_in_mask', 'scr_draw_set_mask', 'scr_maskdraw_start',
         'scr_maskdraw_end', 'scr_setparty', 'scr_makecaterpillar'],
    ),
    3: (
        ['obj_ch3_ballcon', 'obj_ch3_gachapon', 'obj_ch3_gachaunknown',
         'obj_ch3_GSC07_gacha', 'obj_tenna_board4_gacha', 'obj_ilovetv',
         'obj_heart_follower', 'obj_heart_follower_overshoot',
         'obj_actor_tenna', 'obj_tenna_enemy', 'obj_tenna_marker',
         'obj_b1lancer', 'obj_board_lancermoat', 'obj_board_lancerswitch',
         'obj_npc_toriel', 'obj_npc_king', 'obj_npc_susiedark',
         'obj_kris_putonheadobj', 'obj_kris_headobj',
         'obj_herosusie', 'obj_herokris', 'obj_heroralsei'],
        ['scr_draw_in_mask', 'scr_draw_in_mask_begin', 'scr_draw_in_mask_end',
         'scr_draw_mask_reset', 'scr_maskdraw_start', 'scr_maskdraw_end',
         'chromakey_mask_begin', 'chromakey_mask_end',
         'scr_draw_self_silhouette_plus_mask_start',
         'scr_draw_self_silhouette_plus_mask_end', 'scr_setparty'],
    ),
    4: (
        ['obj_followinglight', 'obj_light_following', 'obj_followinglight_shrinking',
         'obj_dw_church_gerson_follow', 'obj_follow_spear', 'obj_npc_gerson',
         'obj_npc_toriel', 'obj_npc_king', 'obj_multiboss_controller',
         'obj_mike_lancer', 'obj_room_castle_lancer', 'obj_room_castle_tenna',
         'obj_room_castle_queen', 'obj_light_area_mask',
         'obj_herosusie', 'obj_herokris', 'obj_heroralsei'],
        ['scr_draw_in_mask', 'scr_maskdraw_start', 'scr_maskdraw_end', 'scr_setparty'],
    ),
    5: (
        ['obj_ch5_DW30_asgore', 'obj_dw_fcastle_asgore', 'obj_town_north_asgore',
         'obj_flowery_throwkris', 'obj_flowery_kristhrown', 'obj_plat_follower',
         'obj_plat_followercue', 'obj_npc_toriel', 'obj_npc_doubter',
         'obj_npc_castle_cafe', 'obj_npc_rabbits', 'obj_npc_wrapper',
         'obj_herosusie', 'obj_herokris', 'obj_heroralsei'],
        ['scr_draw_in_mask', 'scr_maskdraw_start', 'scr_maskdraw_end', 'scr_bitmask',
         'scr_setparty'],
    ),
}


def safe_write(path, text, tries=6):
    import time
    for _ in range(tries):
        try:
            with io.open(path, 'w', encoding='utf-8', newline='\n') as fh:
                fh.write(text)
            return True
        except OSError:
            time.sleep(0.6)
    print('   !! 写入失败', path)
    return False


for idx, (objs, scripts) in TARGETS.items():
    hp = os.path.join(HITS, 'ch%d_hits.txt' % idx)
    if not os.path.isfile(hp):
        print('缺 %s' % hp)
        continue
    lines = [l.strip() for l in io.open(hp, encoding='utf-8').read().splitlines()
             if l.startswith('CODE\t')]
    names = set()
    # 1) 对象：gml_Object_<obj>_<Event>_<n>
    for o in objs:
        pre = 'gml_Object_' + o + '_'
        for l in lines:
            n = l.split('\t', 1)[1]
            if n.startswith(pre):
                names.add(n)
    # 2) 脚本：gml_GlobalScript_X（真体）+ gml_Script_X（桩）
    for s in scripts:
        for pre in ('gml_GlobalScript_', 'gml_Script_'):
            names.add(pre + s)
    ordered = sorted(names)
    d = os.path.join(DRW, 'chapter%d_windows' % idx)
    ok = os.path.isdir(d) and safe_write(os.path.join(d, 'dump_names49.txt'),
                                         '\n'.join(ordered) + '\n')
    safe_write(os.path.join(HITS, 'dump_list_ch%d.txt' % idx),
               '# chapter%d 目标 code %d 条\n%s\n' % (idx, len(ordered), '\n'.join(ordered)))
    print('ch%d  目标 code %d 条  ->drw:%s' % (idx, len(ordered), ok))
