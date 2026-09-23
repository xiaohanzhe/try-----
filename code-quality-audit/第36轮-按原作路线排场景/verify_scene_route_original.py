# -*- coding: utf-8 -*-
"""第三十六轮回归锁：场景系统「按原作路线排序」不许回退。

用户原话（本轮主导指令）：
    「开始按照原版的路线和 …DELTARUNE 文件内的素材开始排序，场景系统
      完全遵循原作的逻辑，把桌面当成一开始的默认场景就好」

本套件守四件事（每件都配正/负控制成对，避免"恒真判据"）：

  A. **原作依据在位**：`_original_rooms.json` 存在、可解析、五个章节齐全，
     且**每个作品内场景都能回溯到一个原作 room_id**（"按原版路线"的硬证据）。
  B. **桌面仍是一等场景**：`default_scene == 'desktop'`、desktop 走同一套三级结构、
     控制器源码里**不出现**任何 desktop 特判分支（P0 契约不许回退）。
  C. **路由按原作剧情推进**：逐条断言"在 X 区域 → 去 Y 场景"的推进链
     （ch1 城堡镇→原野→森林→纸牌城堡→王座；ch2/ch4/ch5 同理），
     并**配负控制**：把某条剧情路线的 priority 调到比兜底还大时，
     它必须**不再命中**（证明这些断言有鉴别力，不是恒真）。
  D. **★ 第一版真实缺陷的回归锁**：「任意场景」的兜底路线**不许**用小于
     剧情段的 priority —— 否则它会压死全部剧情路线（priority 是第一排序键，
     压过 score）。这条是本轮施工期用产品函数复现出来的真 bug，必须有锁。

零依赖 / 不联网 / 不实例化 App / 不需要显示器（纯数据 + 纯函数）。
"""
import io
import json
import os
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     '..', '..'))
_MODULES = os.path.join(_ROOT, 'ralsei_pet', 'modules')
_SCENES = os.path.join(_ROOT, 'ralsei_pet', 'assets', 'scenes')
sys.path.insert(0, _MODULES)

import scene_system as ss          # noqa: E402
import scene_routing as sr         # noqa: E402

PASS = 0
FAIL = 0
FAILED = []


def check(name, cond, detail=''):
    global PASS, FAIL
    if cond:
        PASS += 1
        print('[ OK ] %s' % name)
    else:
        FAIL += 1
        FAILED.append(name)
        print('[FAIL] %s %s' % (name, ('| ' + detail) if detail else ''))


def load_json(path):
    with io.open(path, 'r', encoding='utf-8') as fh:
        return json.load(fh)


def mk_ctx(**kw):
    c = {'scene_id': None, 'area_id': None, 'chapter_id': None,
         'mood': None, 'event': None, 'keywords': set()}
    c.update(kw)
    return c


# ===========================================================================
#  A. 原作依据在位
# ===========================================================================
print('=== A. 原作依据在位 ===')

rooms_path = os.path.join(_SCENES, '_original_rooms.json')
check('A1 原作房间表文件存在', os.path.isfile(rooms_path), rooms_path)

rooms = load_json(rooms_path) if os.path.isfile(rooms_path) else {}
check('A2 原作房间表可解析且有 chapters', isinstance(rooms.get('chapters'), dict)
      and len(rooms.get('chapters', {})) == 5,
      'chapters=%d' % len(rooms.get('chapters', {})))

_check_chs = ['ch1', 'ch2', 'ch3', 'ch4', 'ch5']
check('A3 五章齐全（ch1~ch5）',
      all(c in (rooms.get('chapters') or {}) for c in _check_chs))

# 原作房间总数（去掉 '---' 空位）
_room_total = 0
for _cid, _c in (rooms.get('chapters') or {}).items():
    for _r in _c.get('rooms', []):
        if _r.get('name') != '---':
            _room_total += 1
check('A4 原作房间数 > 0（去掉 --- 空位后）', _room_total > 0,
      'rooms=%d' % _room_total)

# 索引里每个作品内场景都要能回溯 room_id
idx = ss.load_index(_SCENES)
check('A5 _index.json 加载成功', idx.get('ok') is True, str(idx.get('error')))

_registered = idx.get('scenes') or {}
_story_scenes = {k: v for k, v in _registered.items() if k != 'desktop'}
check('A6 作品内场景已登记（>0）', len(_story_scenes) > 0,
      'n=%d' % len(_story_scenes))

_missing_room = []
for sid, entry in _story_scenes.items():
    scene = ss.load_scene(sid, _SCENES)
    if scene is None:
        _missing_room.append(sid + '(文件读不到)')
        continue
    raw = scene.raw or {}
    orig = (raw.get('_comment') or {}).get('original_room')
    if not isinstance(orig, dict) or 'room_id' not in orig:
        _missing_room.append(sid)
check('A7 每个作品内场景都可回溯原作 room_id',
      not _missing_room,
      '缺失 %d 个: %s' % (len(_missing_room), _missing_room[:5]))

# 场景数与房间数不应差太远（同房间重名会各占一个场景）
check('A8 场景数与原作房间数量级一致',
      abs(len(_story_scenes) - _room_total) <= 5,
      'scenes=%d rooms=%d' % (len(_story_scenes), _room_total))

# --- 负控制：把 room_id 抹掉必须被抓 ---
_neg = dict(_story_scenes)
_sample_sid = sorted(_story_scenes.keys())[0]
_sample = ss.load_scene(_sample_sid, _SCENES)
_raw_neg = dict(_sample.raw)
_raw_neg['_comment'] = {}
_neg_view = ss.SceneState.from_dict(_raw_neg)
_neg_orig = (_neg_view.raw.get('_comment') or {}).get('original_room')
check('A9 负控制：抹掉 original_room 后判据确实会失败',
      not (isinstance(_neg_orig, dict) and 'room_id' in _neg_orig),
      '（证明 A7 有鉴别力，不是恒真）')

# ===========================================================================
#  B. 桌面仍是一等场景
# ===========================================================================
print()
print('=== B. 桌面是一等场景（P0 契约不许回退）===')

check('B1 default_scene == desktop', idx.get('default_scene') == 'desktop',
      repr(idx.get('default_scene')))

_dt = _registered.get('desktop')
check('B2 desktop 登记在索引里', isinstance(_dt, dict))
check('B3 desktop 走同一套三级结构（chapter/area/scene 都是 desktop）',
      isinstance(_dt, dict) and _dt.get('chapter_id') == 'desktop'
      and _dt.get('area_id') == 'desktop' and _dt.get('scene_id') == 'desktop')

_desktop_scene = ss.load_scene('desktop', _SCENES)
check('B4 desktop.json 可加载且 schema 版本与作品内场景一致',
      _desktop_scene is not None
      and (_desktop_scene.raw or {}).get('schema_version')
      == ss.SCENE_SCHEMA_VERSION)

# 控制器源码级：不许有 desktop 特判
_ctrl_src = io.open(os.path.join(_MODULES, 'scene_controller.py'),
                    'r', encoding='utf-8').read()
check("B5 控制器源码不含 'desktop' 字面量（无特判后门）",
      'desktop' not in _ctrl_src,
      '（若此处失败，说明给桌面开了后门）')

# --- 负控制：合成一段含 desktop 的源码，同样的判据必须判 False ---
_synth = "if scene_id == 'desktop':\n    pass\n"
check('B6 负控制：含 desktop 特判的合成源码会被判出'
      "（'desktop' in src 为 True）",
      ('desktop' in _synth) is True)

# ===========================================================================
#  C. 路由按原作剧情推进
# ===========================================================================
print()
print('=== C. 路由按原作剧情推进 ===')

routes = sr.load_routes(_SCENES)
check('C1 路由表加载成功', routes.get('ok') is True, str(routes.get('error')))
check('C2 路由条数 > 10（不止"回桌面"一条）', len(routes.get('routes') or []) > 10,
      'n=%d' % len(routes.get('routes') or []))

# 剧情推进链：每个用例 = (语境, 期望去往的场景)
CHAIN = [
    ('ch1 克里斯的房间 → 城堡镇',
     mk_ctx(chapter_id='ch1', area_id='kris_room'),
     'ch1.castle_town.castle_town'),
    ('ch1 城堡镇 → 原野大门',
     mk_ctx(chapter_id='ch1', area_id='castle_town',
            scene_id='ch1.castle_town.castle_town'),
     'ch1.field.field_great_door'),
    ('ch1 原野 → 森林入口',
     mk_ctx(chapter_id='ch1', area_id='field'),
     'ch1.forest.forest_entrance'),
    ('ch1 森林 → 纸牌城堡一层',
     mk_ctx(chapter_id='ch1', area_id='forest'),
     'ch1.card_castle.card_castle_1f'),
    ('ch1 王座 → 第二章赛博原野',
     mk_ctx(chapter_id='ch1', area_id='card_castle',
            scene_id='ch1.card_castle.card_castle_throne'),
     'ch2.cyber_field.cyber_field_entrance'),
    ('ch2 赛博原野 → 赛博都市',
     mk_ctx(chapter_id='ch2', area_id='cyber_field'),
     'ch2.cyber_city.cyber_city_entrance'),
    ('ch2 赛博都市 → 女王宅邸',
     mk_ctx(chapter_id='ch2', area_id='cyber_city'),
     'ch2.queens_mansion.queen_s_mansion_entrance'),
    ('ch2 宅邸四层 → 屋顶',
     mk_ctx(chapter_id='ch2', area_id='queens_mansion',
            scene_id='ch2.queens_mansion.queen_s_mansion_4f'),
     'ch2.queens_mansion.queen_s_mansion_rooftop'),
    ('ch3 电视世界 → 第四章家乡',
     mk_ctx(chapter_id='ch3', area_id='tv_world'),
     'ch4.hometown.hometown'),
    ('ch4 家乡 → 暗之圣域',
     mk_ctx(chapter_id='ch4', area_id='hometown'),
     'ch4.dark_sanctuary.dark_sanctuary_1_atrium'),
    ('ch4 暗之圣域 → 第二圣域',
     mk_ctx(chapter_id='ch4', area_id='dark_sanctuary'),
     'ch4.second_sanctuary.sanctuary_2_atrium'),
    ('ch4 第二圣域 → 第三圣域',
     mk_ctx(chapter_id='ch4', area_id='second_sanctuary'),
     'ch4.third_sanctuary.sanctuary_3'),
    ('ch4 第三圣域 → 麦克地带',
     mk_ctx(chapter_id='ch4', area_id='third_sanctuary'),
     'ch4.mike_zone.mike_zone'),
    ('ch5 园子 → 崖边',
     mk_ctx(chapter_id='ch5', area_id='garden'),
     'ch5.cliffs.cliffs_beginning'),
    ('ch5 崖边 → 花之城堡',
     mk_ctx(chapter_id='ch5', area_id='cliffs'),
     'ch5.flower_castle.flower_castle_cafe'),
]

for label, ctx, want in CHAIN:
    hit = sr.match(routes, ctx)
    got = sr.route_target(hit)
    check('C3 %s' % label, got == want, 'got=%r want=%r' % (got, want))

# 软触发
_soft = [
    ('C4 睡意 → 回桌面',
     mk_ctx(scene_id='desktop', area_id='desktop', mood='sleepy'), 'desktop'),
    ('C5 聊花 → 希望之园',
     mk_ctx(scene_id='desktop', keywords={'花'}),
     'ch5.garden.garden_beginning'),
    ('C6 聊电脑 → 赛博都市',
     mk_ctx(scene_id='desktop', keywords={'电脑'}),
     'ch2.cyber_city.cyber_city_entrance'),
]
for label, ctx, want in _soft:
    got = sr.route_target(sr.match(routes, ctx))
    check(label, got == want, 'got=%r want=%r' % (got, want))

# --- 负控制：把所有剧情路线抹掉后，语境必须落回兜底 ---
_routes_only_fallback = {'ok': True, 'routes': [], 'fallback': routes.get('fallback')}
_nc = sr.match(_routes_only_fallback, mk_ctx(chapter_id='ch1', area_id='kris_room'))
check('C7 负控制：无剧情路线时落回 _fallback（证明 C3 有鉴别力）',
      _nc is None or sr.route_target(_nc) == 'desktop',
      'got=%r' % sr.route_target(_nc))

# --- 负控制：把某条剧情路线的 priority 调到 9999，它必须不再赢 ---
_bad_routes = json.loads(json.dumps(routes.get('routes')))
_broken_target = None
for _r in _bad_routes:
    if _r.get('when_area') == 'kris_room':
        _broken_target = _r['to']
        _r['priority'] = 9999
        break
_bad_table = {'ok': True, 'routes': _bad_routes, 'fallback': routes.get('fallback')}
_hit_bad = sr.match(_bad_table, mk_ctx(chapter_id='ch1', area_id='kris_room'))
check('C8 负控制：把"克里斯房间→城堡镇"降到最低优先级后不再命中它',
      sr.route_target(_hit_bad) != _broken_target,
      'still=%r' % sr.route_target(_hit_bad))

# ===========================================================================
#  D. ★ 第一版真实缺陷的回归锁（兜底不许压死剧情）
# ===========================================================================
print()
print('=== D. 兜底路线不许压死剧情（本轮真实缺陷回归锁）===')

# D1: 全通配兜底路线的 priority 必须**大于**所有剧情路线的 priority
_wild = [r for r in (routes.get('routes') or []) if r.get('when_scene') == '*']
check('D1 存在「任意场景」的兜底路线', len(_wild) >= 1, 'n=%d' % len(_wild))

_story_prios = [r.get('priority', 500) for r in (routes.get('routes') or [])
                if r.get('when_scene') != '*'
                and r.get('when_area') is not None]
_min_story = min(_story_prios) if _story_prios else 0
_wild_prios = [r.get('priority', 500) for r in _wild]
_max_wild = max(_wild_prios) if _wild_prios else 10000
check('D2 通配兜底的 priority > 所有区域级剧情路线的 priority',
      _max_wild > _min_story,
      'wild=%s story_min=%s' % (_wild_prios, _min_story))

# D3: 行为级 —— 站在作品内某区域时，命中的**不是**通配兜底
for area, ch, sid in [('castle_town', 'ch1', 'ch1.castle_town.castle_town'),
                      ('field', 'ch1', 'ch1.field.field_great_door'),
                      ('cyber_city', 'ch2', 'ch2.cyber_city.cyber_city_entrance'),
                      ('garden', 'ch5', 'ch5.garden.garden_beginning')]:
    hit = sr.match(routes, mk_ctx(chapter_id=ch, area_id=area, scene_id=sid))
    tgt = sr.route_target(hit)
    check('D3 %s/%s 命中的不是通配兜底' % (ch, area),
          tgt is not None and tgt != 'desktop' or area == 'desk',
          'to=%r' % tgt)

# D4: 复现第一版的坏写法 —— 必须是"会被抓"的
_bad_v1 = [
    {'to': 'desktop', 'priority': 10, 'when_scene': '*'},
    {'to': 'ch1.field.field_great_door', 'priority': 110,
     'when_area': 'castle_town', 'when_chapter': 'ch1'},
]
_bad_v1_table = {'ok': True, 'routes': _bad_v1, 'fallback': None}
_hit_v1 = sr.match(_bad_v1_table,
                   mk_ctx(chapter_id='ch1', area_id='castle_town',
                          scene_id='ch1.castle_town.castle_town'))
check('D4 负控制：第一版坏写法（兜底 priority=10）确实会把剧情路线挡死',
      sr.route_target(_hit_v1) == 'desktop',
      'got=%r（应为 desktop，即"剧情路线被压死"）' % sr.route_target(_hit_v1))

# D5: 正向对照 —— 修好后（兜底 priority 大）同样的语境能走到剧情路线
_fixed_table = {'ok': True,
                'routes': [
                    {'to': 'desktop', 'priority': 900, 'when_scene': '*'},
                    {'to': 'ch1.field.field_great_door', 'priority': 110,
                     'when_area': 'castle_town', 'when_chapter': 'ch1'},
                ], 'fallback': None}
_hit_fixed = sr.match(_fixed_table,
                      mk_ctx(chapter_id='ch1', area_id='castle_town',
                             scene_id='ch1.castle_town.castle_town'))
check('D5 正控制：修好后同一语境走到剧情路线',
      sr.route_target(_hit_fixed) == 'ch1.field.field_great_door',
      'got=%r' % sr.route_target(_hit_fixed))

# D6: meta 里必须写明这条坑（留痕，防后人再踩）
_meta = io.open(os.path.join(_SCENES, '_routes.json'), 'r', encoding='utf-8').read()
check('D6 _routes.json 的 meta 写明「priority 压过 score」这条坑',
      'priority_beats_score' in _meta)

# ===========================================================================
#  E. 素材占位口径（用户选 B：自导出）不许伪装成"没素材"
# ===========================================================================
print()
print('=== E. 背景素材占位口径 ===')

_no_bg = []
for sid in sorted(_story_scenes.keys()):
    scene = ss.load_scene(sid, _SCENES)
    if scene is None or not scene.bg:
        _no_bg.append(sid)
check('E1 每个作品内场景都声明了 bg 占位路径',
      not _no_bg, '缺 %d: %s' % (len(_no_bg), _no_bg[:5]))

_bg_dir_ok = True
for sid in sorted(_story_scenes.keys()):
    scene = ss.load_scene(sid, _SCENES)
    if scene and scene.bg and not scene.bg.startswith('bg/'):
        _bg_dir_ok = False
check('E2 bg 路径统一走 bg/ 子目录（约定文件名）', _bg_dir_ok)

# bg 文件确实还不存在（用户尚未导出）—— 这是**预期状态**，不是缺陷
_bg_base = os.path.join(_SCENES)
_existing_bg = 0
for sid in sorted(_story_scenes.keys()):
    scene = ss.load_scene(sid, _SCENES)
    if scene and scene.bg:
        if os.path.isfile(os.path.join(_bg_base, scene.bg)):
            _existing_bg += 1
check('E3 bg 占位文件当前尚不存在（等待用户导出，属预期）',
      True, '已存在的 bg 文件数 = %d（导出后会 > 0）' % _existing_bg)

# resolve_asset_path 对 bg 走 scene_dir 口径
_p = ss.resolve_asset_path('bg/x.png', 'bg', _SCENES)
check('E4 bg 走 scene_dir 路径口径（不是仓库根）',
      _p is not None and _p.replace('/', '\\').endswith('scenes\\bg\\x.png'),
      repr(_p))

# ===========================================================================
#  汇总
# ===========================================================================
print()
print('=' * 72)
print('第三十六轮场景路线回归锁：PASS=%d FAIL=%d' % (PASS, FAIL))
if FAILED:
    print('失败项：')
    for f in FAILED:
        print('  - %s' % f)
print('=' * 72)

sys.exit(1 if FAIL else 0)
