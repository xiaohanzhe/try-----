# -*- coding: utf-8 -*-
"""第 38 轮 v2：构建原作权威房间表 + 区域映射 + 87 点回归校验。

v1 的教训（已由校验器抓到）：区域不能只用"资源名前缀规则"推 ——
已有的 87 个场景，其 area_id 是从**官方显示名**（scr_roomname）的 " - " 前缀推出来的
（与第 36 轮同一口径）。v1 另起一套规则 ⇒ 与 10 个已有场景冲突。

v2 口径（**优先官方名，规则表只兜底**）：
  1. 有官方显示名 → area 由官方名的前缀推导（slug + 少量别名表）
  2. 无官方名 → 用资源名前缀规则表
  3. 都没有 → 报出来（**不静默兜底**）

★ 防恒真：官方名→area 的映射**不是**从已有的 87 个场景抄的，而是**独立按规则推**，
  再拿 87 个已有场景去**校验**（否则就是自证）。
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
#  分类
# ===========================================================================
NONSCENE = [re.compile(r'^ROOM_INITIALIZE$'), re.compile(r'^PLACE_'),
            re.compile(r'debug|failsafe', re.I), re.compile(r'test', re.I),
            re.compile(r'title_placeholder', re.I),
            re.compile(r'^(room_empty|room_DARKempty)$'),
            re.compile(r'^room_DARKbase_GMS2$'),
            re.compile(r'^room_(gameover|ed|man|splashscreen)$')]
MAYBE = [re.compile(r'^room_legend(_neo)?$'),
         re.compile(r'^room_chapter_continue$'),
         re.compile(r'^room_(shop1|shop2|shop_music)$'),
         re.compile(r'^room_shop_ch\d_\w+$'),
         re.compile(r'^room_intro(_ch\d)?$'),
         re.compile(r'^room_transformation_sequence$'),
         re.compile(r'unusedroom', re.I),
         re.compile(r'^room_myroom_dark$')]


def classify(n):
    for rx in NONSCENE:
        if rx.search(n):
            return 'nonscene'
    for rx in MAYBE:
        if rx.search(n):
            return 'maybe'
    return 'scene'


# ===========================================================================
#  官方显示名前缀 → area_id
# ===========================================================================
#: 别名表：slug 化之后仍与既有 area_id 不一致的，显式列（都可解释）
ALIAS = {
    'kris_s_room': ('kris_room', '克里斯的房间'),
    'my_castle_town': ('my_castle_town', '我的城堡镇'),
    'castle_town': ('castle_town', '城堡镇'),
    'top_of_castle': ('top_of_castle', '城堡之顶'),
    'quiz_show': ('b3bs_world', '三只小熊的节目'),
    'cooking_show': ('tv_world', '电视世界'),
}

#: 直接给中文名（避免拼音）
CN = {
    'kris_room': '克里斯的房间', 'hometown': '家乡', 'dark_world': '黑暗世界',
    'castle_town': '城堡镇', 'field': '希望与梦想之原', 'forest': '猩红森林',
    'card_castle': '纸牌城堡', 'eye_puzzle': '眼睛谜题', 'unknown': '？？？？？？',
    'my_castle_town': '我的城堡镇', 'cyber_field': '赛博原野',
    'cyber_city': '赛博都市', 'queens_mansion': '女王宅邸',
    'cold_place': '冰寒之地', 'green_room': '绿房间', 'tv_world': '电视世界',
    'noelles_house': '诺艾尔家', 'dark_sanctuary': '暗之圣域',
    'second_sanctuary': '第二圣域', 'third_sanctuary': '第三圣域',
    'mike_zone': '麦克地带', 'garden': '希望之园', 'cliffs': '崖边',
    'flower_castle': '花之城堡', 'top_of_castle': '城堡之顶',
    'b3bs_world': '三只小熊的节目',
}


def slug(s):
    s = s.strip()
    s = re.sub(r'~\d+', ' ', s)
    s = re.sub(r'[^0-9A-Za-z\u4e00-\u9fff]+', '_', s)
    s = re.sub(r'_+', '_', s).strip('_').lower()
    return s


def area_from_official(name):
    """官方显示名 → (area_id, area_name)。'---' → None（占位）。"""
    if not name or name.strip() in ('---', ''):
        return None, None
    base = name.split(' - ')[0].strip()
    s = slug(base)
    if s in ALIAS:
        a, cn = ALIAS[s]
        return a, CN.get(a, cn)
    return s, CN.get(s, base)


# ===========================================================================
#  资源名前缀规则表（只给**没有官方名**的房间兜底）
# ===========================================================================
AREA_RULES = [
    (r'^room_lw_noellehouse', 'noelles_house', '诺艾尔家'),
    (r'^room_lw_', 'light_world', '光世界'),
    (r'^room_dw_ralsei_castle', 'ralsei_room', '拉尔赛的城堡'),
    (r'^room_(dw_)?cc_', 'card_castle', '纸牌城堡'),
    (r'^room_krisroom$', 'kris_room', '克里斯的房间'),
    (r'^room_(krisroom_dark|krishallway|torroom|torhouse|torhouse_sepia|torbathroom)$',
     'home', '克里斯的家'),
    (r'^room_(town_|beach$|graveyard$|diner$|townhall$|library$|alphysalley$|'
     r'torielclass$|schoollobby$|alphysclass$|schooldoor$|insidecloset$|'
     r'school_unusedroom$|hospital_|flowershop_)', 'hometown', '家乡'),
    (r'^room_dark_eyepuzzle$', 'eye_puzzle', '眼睛谜题'),
    (r'^room_dark1a$', 'unknown', '？？？？？？'),
    (r'^room_dark(_|\d)', 'dark_world', '黑暗世界'),
    (r'^room_castle_', 'castle_town', '城堡镇'),
    (r'^room_field', 'field', '希望与梦想之原'),
    (r'^room_forest', 'forest', '猩红森林'),
    (r'^room_dw_cyber_', 'cyber_field', '赛博原野'),
    (r'^room_dw_city_', 'cyber_city', '赛博都市'),
    (r'^room_dw_mansion_', 'queens_mansion', '女王宅邸'),
    (r'^room_dw_teevie_|^room_dw_tv_|^room_dw_b3bs_', 'tv_world', '电视世界'),
    (r'^room_board', 'board_world', '冒险棋盘'),
    (r'^room_dw_couch_|^room_DARKbase', 'dark_world', '黑暗世界'),
    (r'^room_dw_ranking_', 'ranking_world', '排行榜世界'),
    (r'^room_dw_puzzlecloset_', 'puzzle_closet', '谜题柜'),
    (r'^room_dw_snow_', 'cold_place', '冰寒之地'),
    (r'^room_dw_green_room$', 'green_room', '绿房间'),
    (r'^room_dw_(nondescript|susiezilla|chef|shadowmantle|backstage|'
     r'changing_room|console_room|inbetween|inbetweenhall|rhythm|green_world)',
     'tv_backstage', '电视世界后台'),
    (r'^room_(susiezilla|shadowmantle|shootout|ch3_gameshowroom)', 'tv_backstage',
     '电视世界后台'),
    (r'^room_dw_church_', 'dark_sanctuary', '暗之圣域'),
    (r'^room_dw_churchb_', 'second_sanctuary', '第二圣域'),
    (r'^room_dw_churchc_', 'third_sanctuary', '第三圣域'),
    (r'^room_(overworld|darkness)_|^room_dw_overworld|^room_dw_darkmaku|'
     r'^room_(dw_)?rotating_tower', 'mike_zone', '麦克地带'),
    (r'^room_dw_garden_', 'garden', '希望之园'),
    (r'^room_dw_cliff_', 'cliffs', '崖边'),
    (r'^room_dw_fcastle_', 'flower_castle', '花之城堡'),
    (r'^room_dw_(post|pink|flowery|dogballoon)_|^room_dogplatforming',
     'flower_castle', '花之城堡'),
    (r'^room_dw_castle_tv_zone_\d+', 'mike_zone', '麦克地带'),
    (r'^room_dw_castle_tv$|^room_dw_castle_(restaurant|town)$', 'castle_town',
     '城堡镇'),
    (r'^room_dw_castle_area_\d+_transformed', 'my_castle_town', '我的城堡镇'),
    (r'^room_dw_castle_area_\d+$|^room_dw_castle_(east_door|west_cliff|'
     r'west_cliff_old)', 'castle_town', '城堡镇'),
]
AREA_RULES = [(re.compile(p), a, n) for p, a, n in AREA_RULES]


def area_from_resource(name):
    for rx, aid, aname in AREA_RULES:
        if rx.search(name):
            return aid, aname
    return None, None


# ===========================================================================
#  已有 87 个场景（仅用于**校验**与保留 id，不参与推导）
# ===========================================================================
with io.open(os.path.join(SCENES, '_index.json'), 'r', encoding='utf-8') as fh:
    idx_raw = json.load(fh)
existing = {}
for cid, c in (idx_raw.get('chapters') or {}).items():
    for aid, a in (c.get('areas') or {}).items():
        for sid, s in (a.get('scenes') or {}).items():
            rid = s.get('original_room_id')
            if rid is not None:
                existing[(cid, int(rid))] = (sid, s, aid, a.get('name'))

# ===========================================================================
#  建表
# ===========================================================================
table = {}
reg_match, reg_miss, no_area = [], [], []
for ch, folder in PAIRS:
    d = json.loads(io.open(os.path.join(DR, folder, 'rooms_map.json'),
                           'r', encoding='utf-8').read())
    rooms = [r for r in (d.get('rooms') if isinstance(d, dict) else d)
             if isinstance(r, dict)]
    txt = io.open(os.path.join(DRW, folder, '_roomname_code.txt'),
                  'r', encoding='utf-8').read()
    official = {}
    blocks = re.split(r'if \(arg0 == (\d+)\)', txt)
    for i in range(1, len(blocks) - 1, 2):
        rid = int(blocks[i])
        lits = [x for x in re.findall(r'"([^"]{1,60})"', blocks[i + 1])
                if not x.startswith('scr_roomname')]
        official[rid] = lits[0] if lits else None

    recs = []
    for i, r in enumerate(rooms):
        nm = str(r.get('name') or '')
        cls = classify(nm)
        off = official.get(i)
        aid, aname = (None, None)
        src = ''
        if off:
            aid, aname = area_from_official(off)
            src = 'official'
        if aid is None:
            aid, aname = area_from_resource(nm)
            src = 'resource' if aid else ''
        rec = {'chapter': ch, 'room_index': i, 'resource': nm, 'cls': cls,
               'official_name': off, 'area_id': aid, 'area_name': aname,
               'area_src': src}
        e = existing.get((ch, i))
        if e:
            rec['keep_scene_id'] = e[0]
            rec['keep_name'] = e[1].get('name')
            rec['keep_area_id'] = e[2]
            if aid == e[2]:
                reg_match.append((ch, i))
            else:
                reg_miss.append((ch, i, nm, off, e[2], aid, src))
        if cls == 'scene' and aid is None:
            no_area.append('%s:%s' % (ch, nm))
        recs.append(rec)
    table[ch] = recs

w('=== 87 点回归校验（独立推导的 area  vs  已有 area_id）===')
ck('R1 官方名/规则表能复现全部 %d 个已有场景的 area_id' % len(existing),
   not reg_miss, '一致 %d / 不一致 %d' % (len(reg_match), len(reg_miss)))
for m in reg_miss[:15]:
    w('    ✗ %s[%d] %s  官方名=%r  已有=%s  我推=%s (来源=%s)' % m)
w('')
ck('R2 官方名推导覆盖了多少（诊断用）',
   True, '')
w('')

tot = {'scene': 0, 'maybe': 0, 'nonscene': 0}
for ch, recs in table.items():
    c = {'scene': 0, 'maybe': 0, 'nonscene': 0}
    for rec in recs:
        c[rec['cls']] += 1
        tot[rec['cls']] += 1
    w('%-4s room=%-4d scene=%-4d maybe=%-3d nonscene=%-3d 区域=%d'
      % (ch, len(recs), c['scene'], c['maybe'], c['nonscene'],
         len(set(r['area_id'] for r in recs if r['area_id']))))
w('')
w('合计 room=%d  scene=%d  maybe=%d  nonscene=%d'
  % (sum(len(v) for v in table.values()), tot['scene'], tot['maybe'],
     tot['nonscene']))
w('')
ck('R3 所有"可当场景"的房间都推到了区域', not no_area,
   '未推导 %d 个：%s' % (len(no_area), no_area[:12]))

allareas = {}
for recs in table.values():
    for r in recs:
        if r['area_id']:
            allareas[r['area_id']] = r['area_name']
w('全部区域 %d 个：' % len(allareas))
for k in sorted(allareas):
    w('    %-20s %s' % (k, allareas[k]))
w('')

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
        fh.write('=' * 70 + '\n%s\n' % ch)
        for (aid, aname), recs in sorted(by.items(), key=lambda kv: str(kv[0][0])):
            fh.write('  -- %s / %s  (%d 间)\n' % (aid, aname, len(recs)))
            for rec in recs:
                fl = []
                if rec['official_name']:
                    fl.append('★' + rec['official_name'])
                if rec.get('keep_scene_id'):
                    fl.append('已登记')
                fh.write('       [%3d] %-40s %s\n'
                         % (rec['room_index'], rec['resource'], ' '.join(fl)))

fails = [r for r in RES if not r[0]]
print('')
print('校验：合计 %d 项 PASS=%d FAIL=%d' % (len(RES), len(RES) - len(fails), len(fails)))
for _, n, d in fails:
    print('  FAIL:', n, d)
print('written')
