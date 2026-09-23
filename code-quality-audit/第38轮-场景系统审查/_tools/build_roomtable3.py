# -*- coding: utf-8 -*-
"""第 38 轮 v3：全量 1,251 房间 → 区域映射。

口径（定稿）
------------
· **87 个已有场景 = 权威锚点**（第 36 轮独立产出，来源是官方显示名的 " - " 前缀协议，
  不是本脚本的规则造的）⇒ 规则表必须**复现**它们，复现不了就是规则错了。
  ⇒ 这是**回归锁**，不是恒真判据。
· 其余房间走资源名前缀规则表。
· 官方显示名只用于**展示**（且只有 90 个房间有；其中 87 个已有中文名，
  另 5 个 ch5 的已知：Top of Castle - Beginning 等）。
· 分类：nonscene = 引擎占位/测试/调试/空房/系统屏/空基座；maybe = 待裁。
"""
import io
import json
import os
import re

ROOT = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
DR = r'E:\Download\_tmp\dr_out'
DRW = r'E:\Download\_tmp\drw'
SCENES = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes')
EV = os.path.join(ROOT, 'code-quality-audit', '第38轮-场景系统审查', '_evidence')
PAIRS = [('ch1', 'chapter1_windows'), ('ch2', 'chapter2_windows'),
         ('ch3', 'chapter3_windows'), ('ch4', 'chapter4_windows'),
         ('ch5', 'chapter5_windows')]

out, RES = [], []


def w(s=''):
    out.append(str(s))
    print(s)


def ck(name, ok, detail=''):
    RES.append((bool(ok), name, str(detail)))
    w('%s %s%s' % ('[PASS]' if ok else '[FAIL]', name,
                   ('  <- ' + str(detail)) if detail else ''))


NONSCENE = [re.compile(r'^ROOM_INITIALIZE$'), re.compile(r'^PLACE_'),
            re.compile(r'debug|failsafe', re.I), re.compile(r'test', re.I),
            re.compile(r'title_placeholder', re.I),
            re.compile(r'^(room_empty|room_DARKempty)$'),
            re.compile(r'^room_DARKbase_GMS2$'),
            re.compile(r'^room_(gameover|ed|man|splashscreen)$')]
MAYBE = [re.compile(r'^room_legend(_neo)?$'), re.compile(r'^room_chapter_continue$'),
         re.compile(r'^room_(shop1|shop2|shop_music)$'),
         re.compile(r'^room_shop_ch\d_\w+$'), re.compile(r'^room_intro(_ch\d)?$'),
         re.compile(r'^room_transformation_sequence$'),
         re.compile(r'unusedroom', re.I), re.compile(r'^room_myroom_dark$')]


def classify(n):
    for rx in NONSCENE:
        if rx.search(n):
            return 'nonscene'
    for rx in MAYBE:
        if rx.search(n):
            return 'maybe'
    return 'scene'


# ===========================================================================
#  区域规则表（有序；首匹配胜出）
#  ★ 每条都为"要复现 87 个锚点"服务过 —— 见文件尾的 R1 校验
# ===========================================================================
RULES = [
    # ---------- 跨章共享：系统与演出 ----------
    (r'^room_(legend|legend_neo|chapter_continue|intro|intro_ch\d|'
     r'transformation_sequence|gameover|ed|man|splashscreen)$', 'system',
     '系统与演出'),
    (r'^room_(shop1|shop2|shop_music)$|^room_shop_ch\d+(_\w+)?$|^room_rhythmgame_editor$|'
     r'^room_teacup_\w+$|^room_shaun_\w+$|^room_CHEFS$|^room_ch3_gacharoom_\w+$|'
     r'^room_gacharoom_\w+$|^room_dw_ch3_man$|^room_plat_\w+$|^room_shop_ch\d+$',
     'system', '系统与演出'),
    # ---------- 光世界 ----------
    (r'^room_lw_noellehouse', 'noelles_house', '诺艾尔家'),
    (r'^room_lw_', 'light_world', '光世界'),
    # ---------- 拉尔赛的城堡 / 纸牌城堡 ----------
    (r'^room_dw_ralsei_castle', 'ralsei_room', '拉尔赛的城堡'),
    (r'^room_(dw_)?cc_', 'card_castle', '纸牌城堡'),
    # ---------- 家 ----------
    (r'^room_krisroom$', 'kris_room', '克里斯的房间'),
    (r'^room_(krisroom_dark|krishallway|torroom|torhouse|torhouse_sepia|'
     r'torbathroom)$', 'home', '克里斯的家'),
    # ---------- 家乡 ----------
    # ⚠️ 上一版在这里翻过车：`$` 写在**整个分支组**末尾（`(A|B|beach$|…)$`），
    #    于是 `town_krisyard` 这类必须"以 town_ 结尾"才匹配 ⇒ 全灭。
    #    ⇒ `$` 只能写在需要精确匹配的单个分支里，或者整组去掉、改用 `\w+`。
    (r'^room_(town_\w+|beach|graveyard|diner|townhall|library|alphysalley|'
     r'torielclass|schoollobby|alphysclass|schooldoor|insidecloset|'
     r'school_unusedroom|hospital_\w+|flowershop_\w+)$', 'hometown', '家乡'),
    # ---------- ch1 ----------
    (r'^room_dark_eyepuzzle$', 'eye_puzzle', '眼睛谜题'),
    (r'^room_dark1a$', 'unknown', '？？？？？？'),
    (r'^room_dark(_|\d)', 'dark_world', '黑暗世界'),
    (r'^room_castle_', 'castle_town', '城堡镇'),
    (r'^room_field', 'field', '希望与梦想之原'),
    (r'^room_forest', 'forest', '猩红森林'),
    # ---------- ch2 ----------
    (r'^room_dw_cyber_', 'cyber_field', '赛博原野'),
    (r'^room_dw_city_', 'cyber_city', '赛博都市'),
    (r'^room_dw_mansion_', 'queens_mansion', '女王宅邸'),
    # ---------- ch3 ----------
    (r'^room_dw_teevie_|^room_dw_tv_|^room_dw_b3bs_', 'tv_world', '电视世界'),
    (r'^room_board', 'board_world', '冒险棋盘'),
    (r'^room_dw_couch_', 'dark_world', '黑暗世界'),      # 锚点 ch3[98] = dark_world
    (r'^room_dw_ranking_', 'ranking_world', '排行榜世界'),
    (r'^room_dw_puzzlecloset_', 'puzzle_closet', '谜题柜'),
    (r'^room_dw_snow_', 'cold_place', '冰寒之地'),
    (r'^room_dw_green_room$', 'green_room', '绿房间'),
    (r'^room_dw_(nondescript|susiezilla|chef|shadowmantle|backstage|'
     r'changing_room|console_room|inbetween|inbetweenhall|rhythm|green_world)',
     'tv_backstage', '电视世界后台'),
    (r'^room_(susiezilla|shadowmantle|shootout|ch3_gameshowroom)', 'tv_backstage',
     '电视世界后台'),
    # ---------- ch4 ----------
    (r'^room_dw_church_', 'dark_sanctuary', '暗之圣域'),
    (r'^room_dw_churchb_', 'second_sanctuary', '第二圣域'),
    (r'^room_dw_churchc_', 'third_sanctuary', '第三圣域'),
    (r'^room_(overworld|darkness)_|^room_dw_overworld|^room_dw_darkmaku|'
     r'^room_(dw_)?rotating_tower', 'mike_zone', '麦克地带'),
    # ---------- ch5 ----------
    (r'^room_dw_garden_intro$', 'dark_world', '黑暗世界'),   # 锚点 ch5[120]
    (r'^room_dw_garden_cliffexit$', 'cliffs', '崖边'),        # 锚点 ch5[144]
    (r'^room_dw_garden_', 'garden', '希望之园'),
    (r'^room_dw_cliff_', 'cliffs', '崖边'),
    (r'^room_dw_fcastle_', 'flower_castle', '花之城堡'),
    (r'^room_dw_(post|pink|flowery|dogballoon)(_|$)|^room_dogplatforming',
     'flower_castle', '花之城堡'),
    # ---------- 城堡镇族（最后处理，规则最细） ----------
    (r'^room_dw_castle_tv_zone_\d+', 'mike_zone', '麦克地带'),        # 锚点 ch4[322]
    (r'^room_dw_castle_tv$', 'castle_town', '城堡镇'),                # 锚点 ch4[298]/ch5[112]
    (r'^room_dw_castle_area_2$', 'castle_town', '城堡镇'),            # 锚点 ch2[61]
    (r'^room_dw_castle_(area_\d+_transformed|town|restaurant)', 'my_castle_town',
     '我的城堡镇'),                                                    # 锚点 ch2[62]
    (r'^room_dw_castle_', 'my_castle_town', '我的城堡镇'),
]
RULES = [(re.compile(p), a, n) for p, a, n in RULES]


def map_area(name):
    for rx, aid, aname in RULES:
        if rx.search(name):
            return aid, aname
    return None, None


# ===========================================================================
#  已有 87 个锚点
# ===========================================================================
idx_raw = json.loads(io.open(os.path.join(SCENES, '_index.json'),
                             'r', encoding='utf-8').read())
anchors = {}
for cid, c in (idx_raw.get('chapters') or {}).items():
    for aid, a in (c.get('areas') or {}).items():
        for sid, s in (a.get('scenes') or {}).items():
            rid = s.get('original_room_id')
            if rid is not None:
                anchors[(cid, int(rid))] = (sid, s.get('name'), aid, a.get('name'))

# ===========================================================================
#  建表
# ===========================================================================
table, ok_pairs, bad_pairs, no_area = {}, [], [], []
for ch, folder in PAIRS:
    d = json.loads(io.open(os.path.join(DR, folder, 'rooms_map.json'),
                           'r', encoding='utf-8').read())
    rooms = [r for r in (d.get('rooms') if isinstance(d, dict) else d)
             if isinstance(r, dict)]
    recs = []
    for i, r in enumerate(rooms):
        nm = str(r.get('name') or '')
        cls = classify(nm)
        aid, aname = map_area(nm)
        rec = {'chapter': ch, 'room_index': i, 'resource': nm, 'cls': cls,
               'area_id': aid, 'area_name': aname}
        a = anchors.get((ch, i))
        if a:
            rec['anchor_scene_id'] = a[0]
            rec['anchor_name'] = a[1]
            rec['anchor_area_id'] = a[2]
            (ok_pairs if aid == a[2] else bad_pairs).append(
                (ch, i, nm, a[2], aid, a[0]))
        if cls == 'scene' and aid is None:
            no_area.append('%s:%s' % (ch, nm))
        recs.append(rec)
    table[ch] = recs

w('=== R1 回归锁：规则表必须复现 87 个锚点的 area_id ===')
ck('R1 全部复现', not bad_pairs,
   '一致 %d / 不一致 %d' % (len(ok_pairs), len(bad_pairs)))
for b in bad_pairs:
    w('    ✗ %s[%d] %-40s 锚点=%s  我推=%s  (%s)' % b)
w('')

sc = {'scene': 0, 'maybe': 0, 'nonscene': 0}
for ch, recs in table.items():
    c = {'scene': 0, 'maybe': 0, 'nonscene': 0}
    for rec in recs:
        c[rec['cls']] += 1
        sc[rec['cls']] += 1
    w('%-4s room=%-4d scene=%-4d maybe=%-3d nonscene=%-3d 区域=%d'
      % (ch, len(recs), c['scene'], c['maybe'], c['nonscene'],
         len(set(r['area_id'] for r in recs if r['area_id']))))
w('')
w('合计 room=%d  scene=%d  maybe=%d  nonscene=%d'
  % (sum(len(v) for v in table.values()), sc['scene'], sc['maybe'],
     sc['nonscene']))
w('')
ck('R2 所有 scene 都推到了区域', not no_area,
   '未推 %d：%s' % (len(no_area), no_area[:12]))

areas = {}
for recs in table.values():
    for r in recs:
        if r['area_id']:
            areas[r['area_id']] = r['area_name']
w('区域共 %d 个：' % len(areas))
for k in sorted(areas):
    w('    %-20s %s' % (k, areas[k]))
w('')

os.makedirs(EV, exist_ok=True)
json.dump(table, io.open(os.path.join(EV, '房间表_全量.json'), 'w',
                         encoding='utf-8'), ensure_ascii=False, indent=1)
with io.open(os.path.join(EV, '区域映射_复核.txt'), 'w', encoding='utf-8') as fh:
    fh.write('\n'.join(out) + '\n\n')
    for ch in table:
        by = {}
        for rec in table[ch]:
            if rec['cls'] != 'scene':
                continue
            by.setdefault((rec['area_id'], rec['area_name']), []).append(rec)
        fh.write('=' * 72 + '\n%s\n' % ch)
        for (aid, aname), recs in sorted(by.items(), key=lambda kv: str(kv[0][0])):
            fh.write('  --- %s / %s  (%d 间)\n' % (aid, aname, len(recs)))
            for rec in recs:
                fh.write('       [%3d] %-42s %s\n'
                         % (rec['room_index'], rec['resource'],
                            ('★已登记 ' + rec['anchor_name'])
                            if rec.get('anchor_scene_id') else ''))

fails = [r for r in RES if not r[0]]
print('')
print('校验：%d 项 PASS=%d FAIL=%d' % (len(RES), len(RES) - len(fails), len(fails)))
for _, n, d in fails:
    print('  FAIL:', n, d)
print('written')
