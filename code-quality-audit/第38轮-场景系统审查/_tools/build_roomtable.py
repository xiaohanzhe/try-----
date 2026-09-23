# -*- coding: utf-8 -*-
"""第 38 轮：构建原作权威房间表（1,251 room）+ 区域映射 + 87 点回归校验。

只读原始素材；产物落 _evidence/。

★ 关键校验（不靠拍脑袋）：已有的 87 个场景在 _index.json 里都带
  `original_room_id` + `area_id`。⇒ 我的区域规则必须能把每个 (chapter, room_index)
  **映射回它原来的 area_id**。87 个真实数据点即规则表的回归锁。
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

out = []
RES = []


def w(s=''):
    out.append(str(s))
    print(s)


def ck(name, ok, detail=''):
    RES.append((bool(ok), name, str(detail)))
    w('%s %s%s' % ('[PASS]' if ok else '[FAIL]', name,
                   ('  <- ' + str(detail)) if detail else ''))


# ===========================================================================
#  分类（沿用第 38 轮已验证的规则）
# ===========================================================================
NONSCENE = [re.compile(r'^ROOM_INITIALIZE$'), re.compile(r'^PLACE_'),
            re.compile(r'debug|failsafe', re.I), re.compile(r'test', re.I),
            re.compile(r'title_placeholder', re.I),
            re.compile(r'^(room_empty|room_DARKempty)$')]
MAYBE = [re.compile(r'^(room_legend|room_chapter_continue)$'),
         re.compile(r'^(room_shop1|room_shop2|room_shop_\w+)$'),
         re.compile(r'unusedroom', re.I), re.compile(r'room_myroom_dark')]


def classify(n):
    for rx in NONSCENE:
        if rx.search(n):
            return 'nonscene'
    for rx in MAYBE:
        if rx.search(n):
            return 'maybe'
    return 'scene'


# ===========================================================================
#  区域规则表（有序，首个匹配胜出）—— 数据即规则
# ===========================================================================
AREA_RULES = [
    # ---------- 跨章共享：系统 / 演出 ----------
    (r'^room_(gameover|ed|man|splashscreen|chapter_continue)$', 'system', '系统与演出'),
    (r'^room_legend(_neo)?$', 'system', '系统与演出'),
    (r'^room_intro(_ch\d)?$', 'system', '系统与演出'),
    (r'^room_transformation_sequence$', 'system', '系统与演出'),
    (r'^room_shop1$|^room_shop\d?$|^room_shop_music$|^room_shop_ch\d_\w+$',
     'system', '系统与演出'),
    (r'^room_quiet\w*$', 'system', '系统与演出'),
    (r'^room_rhythmgame_editor$', 'system', '系统与演出'),
    (r'^room_teacup_\w+$', 'system', '系统与演出'),
    (r'^room_shaun_\w+$', 'system', '系统与演出'),
    (r'^room_CHEFS$|^room_gacharoom_\w+$', 'system', '系统与演出'),
    # ---------- 光世界 ----------
    (r'^room_lw_', 'light_world', '光世界'),
    # ---------- 拉尔赛的城堡 ----------
    (r'^room_dw_ralsei_castle', 'ralsei_room', '拉尔赛的城堡'),
    # ---------- 纸牌城堡（ch2+ 残留的 3 间 → 也是纸牌城堡） ----------
    (r'^room_(dw_)?cc_', 'card_castle', '纸牌城堡'),
    # ---------- 家 ----------
    (r'^room_krisroom$', 'kris_room', '克里斯的房间'),
    (r'^room_(krisroom_dark|krishallway|torroom|torhouse|torhouse_sepia|torbathroom)$',
     'home', '克里斯的家'),
    # ---------- 家乡 ----------
    (r'^room_(town_krisyard|town_northwest|town_north$|town_mid|town_apartments|'
     r'town_south|town_school|town_church|town_shelter|beach$|graveyard$|diner$|'
     r'townhall$|library$|alphysalley$|torielclass$|schoollobby$|alphysclass$|'
     r'schooldoor$|insidecloset$|school_unusedroom$|hospital_\w+|flowershop_\w+)$',
     'hometown', '家乡'),
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
    (r'^room_dw_teevie_', 'tv_world', '电视世界'),
    (r'^room_dw_b3bs_', 'b3bs_world', '三只小熊的节目'),
    (r'^room_board', 'board_world', '冒险棋盘'),
    (r'^room_dw_couch_', 'couch_world', '沙发世界'),
    (r'^room_dw_ranking_', 'ranking_world', '排行榜世界'),
    (r'^room_dw_puzzlecloset_', 'puzzle_closet', '谜题柜'),
    (r'^room_dw_snow_', 'cold_place', '冰寒之地'),
    (r'^room_dw_green_room$', 'green_room', '绿房间'),
    (r'^room_dw_(nondescript|susiezilla|chef|shadowmantle|backstage|'
     r'changing_room|console_room|inbetween|inbetweenhall|tv_|rhythm|'
     r'green_world)', 'tv_backstage', '电视世界后台'),
    (r'^room_(susiezilla|shadowmantle|shootout|ch3_gameshowroom|ch3_\w+)',
     'tv_backstage', '电视世界后台'),
    # ---------- ch4 ----------
    (r'^room_dw_church_', 'dark_sanctuary', '暗之圣域'),
    (r'^room_dw_churchb_', 'second_sanctuary', '第二圣域'),
    (r'^room_dw_churchc_', 'third_sanctuary', '第三圣域'),
    (r'^room_(overworld|darkness)_|^room_dw_overworld|^room_dw_darkmaku|'
     r'^room_(dw_)?rotating_tower', 'mike_zone', '麦克地带'),
    # ---------- ch5 ----------
    (r'^room_dw_garden_', 'garden', '希望之园'),
    (r'^room_dw_cliff_', 'cliffs', '崖边'),
    (r'^room_dw_fcastle_', 'flower_castle', '花之城堡'),
    (r'^room_(post|plat|pink|flowery|dogplatforming|dogballoon)_\w+',
     'misc_5', '零星房间'),
    # ---------- 城堡镇（通用：room_castle_town / room_dw_castle_*） ----------
    (r'^room_dw_castle_town$|^room_dw_castle_(?!town|area_)', 'my_castle_town',
     '我的城堡镇'),
    (r'^room_dw_castle_area_\w+$', 'my_castle_town', '我的城堡镇'),
]
AREA_RULES = [(re.compile(p), a, n) for p, a, n in AREA_RULES]


def map_area(name):
    for rx, aid, aname in AREA_RULES:
        if rx.search(name):
            return aid, aname
    return None, None


# ===========================================================================
#  1. 已有的 87 个场景（用于保留 + 回归校验）
# ===========================================================================
with io.open(os.path.join(SCENES, '_index.json'), 'r', encoding='utf-8') as fh:
    idx_raw = json.load(fh)
existing = {}          # (chapter, room_index) -> {scene_id, name, area_id, file, bg...}
existing_by_room = {}
area_name_of = {}
for cid, c in (idx_raw.get('chapters') or {}).items():
    for aid, a in (c.get('areas') or {}).items():
        area_name_of[(cid, aid)] = a.get('name')
        for sid, s in (a.get('scenes') or {}).items():
            rid = s.get('original_room_id')
            if rid is not None:
                existing[(cid, int(rid))] = (sid, s, aid, a.get('name'))
n_existing = len(existing)
w('已有场景（带 original_room_id）= %d' % n_existing)
w('')

# ===========================================================================
#  2. 逐章建表
# ===========================================================================
table = {}
reg_match, reg_miss = [], []
unmatched_names = {}
for ch, folder in PAIRS:
    d = json.loads(io.open(os.path.join(DR, folder, 'rooms_map.json'),
                           'r', encoding='utf-8').read())
    rooms = d.get('rooms') if isinstance(d, dict) else d
    rooms = [r for r in rooms if isinstance(r, dict)]
    txt = io.open(os.path.join(DRW, folder, '_roomname_code.txt'),
                  'r', encoding='utf-8').read()
    official = {}
    # scr_roomname: id -> 该分支里的字面量（第一个非 lang-key 的字符串）
    blocks = re.split(r'if \(arg0 == (\d+)\)', txt)
    for i in range(1, len(blocks) - 1, 2):
        rid = int(blocks[i])
        body = blocks[i + 1]
        lits = [x for x in re.findall(r'"([^"]{1,60})"', body)
                if not x.startswith('scr_roomname')]
        official[rid] = lits[0] if lits else None

    recs = []
    for i, r in enumerate(rooms):
        nm = str(r.get('name') or '')
        cls = classify(nm)
        aid, aname = map_area(nm)
        rec = {
            'chapter': ch, 'room_index': i, 'resource': nm, 'cls': cls,
            'official_name': official.get(i),
            'area_id': aid, 'area_name': aname,
        }
        e = existing.get((ch, i))
        if e:
            rec['keep_scene_id'] = e[0]
            rec['keep_name'] = e[1].get('name')
            rec['keep_area_id'] = e[2]
            rec['keep_area_name'] = e[3]
            if aid == e[2]:
                reg_match.append((ch, i, aid))
            else:
                reg_miss.append((ch, i, nm, e[2], aid))
        recs.append(rec)
    table[ch] = recs

    for rec in recs:
        if rec['cls'] == 'scene' and rec['area_id'] is None:
            nm = rec['resource']
            tok = re.sub(r'^(room_|dw_)', '', re.sub(r'^room_', '', nm))
            unmatched_names.setdefault(tok.split('_')[0], []).append('%s:%s' % (ch, nm))

w('=== 87 点回归校验（区域规则 vs 已有 area_id）===')
ck('R1 区域规则能复现全部 %d 个已有场景的 area_id' % n_existing,
   not reg_miss, reg_miss[:12])
w('  一致 %d 个' % len(reg_match))
w('')

w('=== 未匹配区域规则的房间（必须为 0 才算规则表完成）===')
tot_un = sum(len(v) for v in unmatched_names.values())
ck('R2 所有"可当场景"的房间都匹配到了区域', tot_un == 0,
   '未匹配 %d 个' % tot_un)
for k, v in sorted(unmatched_names.items(), key=lambda kv: -len(kv[1])):
    w('  [%s] %d 个: %s' % (k, len(v), v[:6]))
w('')

# ===========================================================================
#  3. 计数汇总
# ===========================================================================
tot = {'scene': 0, 'maybe': 0, 'nonscene': 0}
for ch, recs in table.items():
    c = {'scene': 0, 'maybe': 0, 'nonscene': 0}
    for rec in recs:
        c[rec['cls']] += 1
        tot[rec['cls']] += 1
    w('%-4s room=%-4d scene=%-4d maybe=%-3d nonscene=%-3d  区域数=%d'
      % (ch, len(recs), c['scene'], c['maybe'], c['nonscene'],
         len(set(r['area_id'] for r in recs if r['area_id']))))
w('')
w('合计 room=%d  scene=%d  maybe=%d  nonscene=%d'
  % (sum(len(v) for v in table.values()), tot['scene'], tot['maybe'],
     tot['nonscene']))
allareas = sorted(set(r['area_id'] for recs in table.values() for r in recs
                      if r['area_id']))
w('全部区域 %d 个: %s' % (len(allareas), allareas))
w('')
ck('R3 可当场景数 = 1032', tot['scene'] == 1032, tot['scene'])
ck('R4 maybe = 22', tot['maybe'] == 22, tot['maybe'])
ck('R5 nonscene = 197', tot['nonscene'] == 197, tot['nonscene'])

os.makedirs(EV, exist_ok=True)
with io.open(os.path.join(EV, '房间表_全量.json'), 'w', encoding='utf-8') as fh:
    json.dump(table, fh, ensure_ascii=False, indent=1)
with io.open(os.path.join(EV, '区域映射_复核.txt'), 'w', encoding='utf-8') as fh:
    fh.write('\n'.join(out) + '\n\n')
    for ch in table:
        by = {}
        for rec in table[ch]:
            if rec['cls'] != 'scene':
                continue
            by.setdefault((rec['area_id'], rec['area_name']), []).append(rec)
        fh.write('=' * 66 + '\n%s\n' % ch)
        for (aid, aname), recs in by.items():
            fh.write('  -- %s / %s   (%d 间)\n' % (aid, aname, len(recs)))
            for rec in recs:
                flags = []
                if rec['official_name']:
                    flags.append('★官方:' + rec['official_name'])
                if rec.get('keep_scene_id'):
                    flags.append('已登记')
                fh.write('       [%3d] %-38s %s\n'
                         % (rec['room_index'], rec['resource'], ' '.join(flags)))

fails = [r for r in RES if not r[0]]
print('')
print('校验：合计 %d 项 PASS=%d FAIL=%d' % (len(RES), len(RES) - len(fails), len(fails)))
for _, n, d in fails:
    print('  FAIL:', n, d)
print('written')
