# -*- coding: utf-8 -*-
"""第三十六轮回归锁：场景系统「按原作路线排序」不许回退。

用户原话（本轮主导指令）：
    「开始按照原版的路线和 …DELTARUNE 文件内的素材开始排序，场景系统
      完全遵循原作的逻辑，把桌面当成一开始的默认场景就好」

本套件守四件事（每件都配正/负控制成对，避免"恒真判据"）：

  A. **原作依据在位**：`_original_rooms.json` 存在、可解析、五个章节齐全，
     且**每个作品内场景都能回溯到一个原作 room_id**（"按原版路线"的硬证据）。
     ★ 第38轮加锁 A4b/A4c：逐章条数必须 == `scr_roomname` 的分支数
     （20/20/9/20/26 —— 一手事实，不是会漂的计数），且每章 id 唯一。
  B. **桌面仍是一等场景**：`default_scene == 'desktop'`、desktop 走同一套三级结构、
     控制器源码里**不出现**任何 desktop 特判分支（P0 契约不许回退）。
  C. **路由按原作连接推进**：第36~38轮断言的是"区域级剧情链"（26 条手工规则）；
     ★第44轮用户裁定「所有 room 排序/连接都按照原作」+「路由重建你自己判断」，
     路由表换成**由原作门机制生成**的 443 条规则（obj_doorA +1 / obj_doorB -1 /
     obj_doorC +2，且目标房必须有同字母落点作独立验证）⇒ C 段改锁**机制自洽** +
     **三个已知真值锚点**（krisroom↔krishallway 双向 + torhouse 出边）+ 覆盖面。
     守的东西没变（"路由真的按原作走"），换的是"从哪拿期望值"。
  D. **★ 真实缺陷的回归锁**：priority 是第一排序键、压过 score ⇒「任意场景」的
     兜底路线**不许**用小于剧情段的 priority（否则压死全部剧情路线）。
     第36轮用产品函数复现过这个真 bug。第44轮路由表已无通配兜底，
     故 D1/D3 换成对当前表的结构/行为断言；D4/D5（合成坏写法 + 正控制）
     与数据版本无关，**原样保留** —— 它们是这条坑的永恒证明。

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
         'mood': None, 'event': None, 'keywords': set(), 'door': None}
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

# A4b —— ★ 第38轮新增：逐章条数必须 == scr_roomname 的**分支数**。
# 这几个数字**不是"会漂的计数"**，而是原作脚本 `gml_GlobalScript_scr_roomname`
# 里 if/else 分支的个数 —— 是不变的一手事实。第38轮正是靠它们抓出了
# "ch2 多录 2 条（199/200）/ ch5 漏录 5 条（205/222/224/225/230）"。
# 依据：code-quality-audit/第38轮-场景系统审查/_evidence/scr_roomname_覆盖核对.txt
_SCR_BRANCHES = {'ch1': 20, 'ch2': 20, 'ch3': 9, 'ch4': 20, 'ch5': 26}
_bad_cnt = []
for _cid, _exp in _SCR_BRANCHES.items():
    _got = len((((rooms.get('chapters') or {}).get(_cid)) or {}).get('rooms') or [])
    if _got != _exp:
        _bad_cnt.append('%s=%d(期望%d)' % (_cid, _got, _exp))
check('A4b 逐章条数 == scr_roomname 分支数（ch1 20 / ch2 20 / ch3 9 / ch4 20 / ch5 26）',
      not _bad_cnt, '不一致: %s' % _bad_cnt)

# A4c 每章 id 必须唯一 —— 重录最典型的症状就是同名重复条目
#     （ch2 的 199/200 两条同名 "Queen's Mansion - Rooftop" 就是这么来的）。
_dup_ids = []
for _cid, _c in (rooms.get('chapters') or {}).items():
    _ids = [r.get('id') for r in _c.get('rooms', [])]
    if len(_ids) != len(set(_ids)):
        _dup_ids.append(_cid)
check('A4c 每章房间 id 唯一（防重复录入）', not _dup_ids, '重复: %s' % _dup_ids)

# 索引里每个作品内场景都要能回溯 room_id
idx = ss.load_index(_SCENES)
check('A5 _index.json 加载成功', idx.get('ok') is True, str(idx.get('error')))

_registered = idx.get('scenes') or {}
_story_scenes = {k: v for k, v in _registered.items() if k != 'desktop'}
check('A6 作品内场景已登记（>0）', len(_story_scenes) > 0,
      'n=%d' % len(_story_scenes))

_missing_room = []
for sid, entry in _story_scenes.items():
    # ★ 第38轮更新：场景数据有两个来源（独立文件 / 区域分片），一律用产品函数
    #   并**把登记行传下去**（分片场景靠它才知道该读哪一片）。
    scene = ss.load_scene(sid, _SCENES, entry=entry)
    if scene is None:
        _missing_room.append(sid + '(加载失败)')
        continue
    raw = scene.raw or {}
    orig = (raw.get('_comment') or {}).get('original_room')
    if isinstance(orig, dict) and 'room_id' in orig:
        continue
    # 分片场景的可回溯载体在**登记行**上（第38轮生成器写进去的 original_room_id）
    if entry.get('original_room_id') is not None:
        continue
    _missing_room.append(sid)
check('A7 每个作品内场景都可回溯原作 room_id',
      not _missing_room,
      '缺失 %d 个: %s' % (len(_missing_room), _missing_room[:5]))

# A8 —— ★ 第38轮换判据。旧判据是「场景数与官方命名地点数量级一致（差 ≤5）」，
# 它把 `_original_rooms.json` 里的 87 个**官方命名地点**当成了「房间全集」。
# 第38轮实测：原作五章共 1,251 个 room，其中 1,013 个可当场景 —— user 口径
# 「把所有都拿出来啊，别就拿87个」。旧判据随新数据失效，换成**更强的逐条覆盖**判据。
_rooms_tbl_path = os.path.join(_ROOT, 'code-quality-audit',
                               '第38轮-场景系统审查', '_evidence',
                               '房间表_全量.json')
_reg_keys = set()
for _sid, _e in _story_scenes.items():
    _rid = _e.get('original_room_id')
    if _rid is not None:
        _reg_keys.add((_e.get('chapter_id'), int(_rid)))

_tbl = load_json(_rooms_tbl_path) if os.path.isfile(_rooms_tbl_path) else None
_uncovered = []
if isinstance(_tbl, dict):
    for _ch in _tbl:
        for _r in _tbl[_ch]:
            if _r.get('cls') != 'scene':
                continue
            if (_ch, int(_r['room_index'])) not in _reg_keys:
                _uncovered.append('%s:%s' % (_ch, _r['resource']))
check('A8 原作房间表里每个 scene 类房间都已登记为场景（「把所有都拿出来」）',
      isinstance(_tbl, dict) and not _uncovered,
      ('房间表读不到: %s' % _rooms_tbl_path) if not isinstance(_tbl, dict)
      else '未登记 %d 个: %s' % (len(_uncovered), _uncovered[:4]))

# A8b 负控制：从登记键里挖掉一个，判据必须报红（证明 A8 不是恒真）
if isinstance(_tbl, dict):
    _neg_keys = set(_reg_keys)
    for _ch in _tbl:
        for _r in _tbl[_ch]:
            if _r.get('cls') == 'scene' and (_ch, int(_r['room_index'])) in _neg_keys:
                _neg_keys.discard((_ch, int(_r['room_index'])))
                break
        else:
            continue
        break
    _neg_uncov = 0
    for _ch in _tbl:
        for _r in _tbl[_ch]:
            if _r.get('cls') != 'scene':
                continue
            if (_ch, int(_r['room_index'])) not in _neg_keys:
                _neg_uncov += 1
    check('A8b 负控制：挖掉一个登记键后 A8 确实报红（有鉴别力）',
          _neg_uncov == 1, 'got=%d' % _neg_uncov)

# --- 负控制：把 room_id 抹掉必须被抓 ---
_neg = dict(_story_scenes)
_sample_sid = sorted(_story_scenes.keys())[0]
_sample = ss.load_scene(_sample_sid, _SCENES, entry=_story_scenes.get(_sample_sid))
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
#  C. 路由按原作连接推进
#
#  ★ 第44轮换判据（路由表 v1 → v2）
#  ------------------------------------------------------------------------
#  v1 是**手工按区域写死的 26 条剧情链**（"在 castle_town 区域 → 去 field 大门"），
#  断言的是"区域级推进"。第44轮用户裁定「路由重建我也不懂，你自己判断」+
#  「所有 room 排序/连接都按照原作」，于是改成**由原作门机制生成**的 443 条规则
#  （when_scene 级精确连接）。旧断言的**前提对象消失**（没有 when_area 规则了），
#  但**要守的东西没变**：路由必须真的按原作连接走、且真有鉴别力。
#  ⇒ 换的是"从哪拿期望值"，不是降低强度：新期望值来自**原作门的下标位移机制**
#     （obj_doorA +1 / obj_doorB -1 / obj_doorC +2，五章命中率 80~100%），
#     这比 v1 的手工链更硬（v1 的链是人写的，v2 的边是数据生成的 + 锚点校验过）。
# ===========================================================================
print()
print('=== C. 路由按原作连接推进 ===')

routes = sr.load_routes(_SCENES)
check('C1 路由表加载成功', routes.get('ok') is True, str(routes.get('error')))
check('C2 路由条数 > 100（由原作连接生成，不再是 26 条手工链）',
      len(routes.get('routes') or []) > 100,
      'n=%d' % len(routes.get('routes') or []))

# --- C3：机制级断言 —— 每条规则的 _original 必须自洽于门的下标位移表 ---
#     （这是 v2 的核心不变量：规则不是"编"的，是"推"出来的。）
_DOOR_DELTA = {'A': 1, 'B': -1, 'C': 2}
_struct_bad = []
for _r in (routes.get('routes') or []):
    _o = _r.get('_original')
    if not isinstance(_o, dict):
        _struct_bad.append('%s(无_original)' % _r.get('to'))
        continue
    _L = _o.get('door_letter')
    if _L not in _DOOR_DELTA:
        _struct_bad.append('%s(字母=%r)' % (_r.get('to'), _L))
        continue
    if _o.get('room_delta') != _DOOR_DELTA[_L]:
        _struct_bad.append('%s(位移=%r≠%d)' % (_r.get('to'), _o.get('room_delta'),
                                              _DOOR_DELTA[_L]))
check('C3 每条规则的 _original 自洽于门的下标位移表（A+1 / B-1 / C+2）',
      not _struct_bad,
      '不自洽 %d 条: %s' % (len(_struct_bad), _struct_bad[:4]))

# C3b 规则只用了「已实证」的三种字母门 —— 不许悄悄混进 D/E/F/W/X
_LETTERS = sorted(set((r.get('_original') or {}).get('door_letter')
                      for r in (routes.get('routes') or [])))
check('C3b 只用 A/B/C 三种已实证字母门（D/E/F/W/X 一律不编边）',
      set(_LETTERS) <= set(_DOOR_DELTA), '实际字母=%s' % _LETTERS)

# --- C4：锚点 —— krisroom 的 doorA 必须落到 krishallway（第44轮实证的真值）---
#     这是「解析器输出必须先过已知真值锚点」在产品侧的固化。
_anchor_ctx = mk_ctx(chapter_id='ch1', scene_id='ch1.kris_room.kris_s_room')
_hit = sr.match(routes, _anchor_ctx)
check('C4 锚点：克里斯的房间（doorA）→ 克里斯的走廊',
      sr.route_target(_hit) == 'ch1.home.krishallway',
      'got=%r' % sr.route_target(_hit))

# C4b 反向锚点：krishallway 的 doorB(-1) 必须回到 krisroom
#     ★ 注意：krishallway 有**两个出口**（doorB 回卧房 / doorC 去浴室），
#     这是用户点名的「共同卡口」。不指定 door 时走 priority 最小者（字母序 B<C）； 
#     要精确走 B 就必须在 context 里给 door —— 这正是 when_door 的用途。
_hit_b = sr.match(routes, mk_ctx(chapter_id='ch1',
                                 scene_id='ch1.home.krishallway', door='B'))
check('C4b 反向锚点：克里斯的走廊（指定 door=B）→ 克里斯的房间（位移 -1 回退）',
      sr.route_target(_hit_b) == 'ch1.kris_room.kris_s_room',
      'got=%r' % sr.route_target(_hit_b))

# C4b2 —— ★第44轮新机制：共同卡口的两个出口都必须可达且互不串味
_hit_c = sr.match(routes, mk_ctx(chapter_id='ch1',
                                 scene_id='ch1.home.krishallway', door='C'))
check('C4b2 指定 door=C 时同一场景分流去另一个出口（torhouse）',
      sr.route_target(_hit_c) == 'ch1.home.torhouse',
      'got=%r' % sr.route_target(_hit_c))

# C4b3 —— 负控制：给了**不存在的门**时不许乱走（必须判不匹配 → 落兜底）
_hit_bad_door = sr.match(routes, mk_ctx(chapter_id='ch1',
                                       scene_id='ch1.home.krishallway',
                                       door='Z'))
check('C4b3 负控制：指定不存在的门 Z 时不命中任何出口规则',
      sr.route_target(_hit_bad_door) in (None, 'desktop'),
      'got=%r' % sr.route_target(_hit_bad_door))

# C4c 第三锚点：torhouse 有 1 条出边（doorD/D 不编边，故只有 doorA 生效）
_hit_c = sr.match(routes, mk_ctx(chapter_id='ch1', scene_id='ch1.home.torhouse'))
check('C4c 锚点：托丽尔家（doorA）有出边且不是兜底',
      sr.route_target(_hit_c) not in (None, 'desktop'),
      'got=%r' % sr.route_target(_hit_c))

# C5 覆盖度：不再是 2%（26 条手工链），而是覆盖绝大部分原作连接
_reached = set(r.get('to') for r in (routes.get('routes') or []))
check('C5 可达场景数 > 250（原作连接生成后应大幅超过旧的 20 个）',
      len(_reached) > 250, '可达=%d' % len(_reached))

# ===========================================================================
#  D. ★ 真实缺陷的回归锁（兜底不许压死剧情）
#
#  第44轮更新：v2 已**没有**「when_scene == '*'」的通配兜底路线（那是 v1 的写法）。
#  但**这条坑本身不过时** —— 它守的是「priority 是第一排序键、压过 score」这个
#  匹配语义，任何一版路由表都可能再犯。所以：
#    · D1/D2/D3 换成对**当前表**的真实结构性断言（不再找通配规则）；
#    · D4/D5 原样保留（合成坏写法 + 正控制）—— 这两条与数据版本无关，永远有效；
#    · D6/D7 保留留痕与语义断言。
# ===========================================================================
print()
print('=== D. 兜底不许压死剧情（真实缺陷回归锁）===')

# D1 —— ★ 换判据：当前表里**不许有** priority 小于 100 的规则。
#     第44轮生成器把规则排在 110~309；若有人手写一条 priority<100 的
#     "任意场景"规则，它会把后面 443 条全部挡死。这条把该风险钉住。
_low_prio = [r.get('to') for r in (routes.get('routes') or [])
             if isinstance(r.get('priority'), int) and r['priority'] < 100]
check('D1 不存在 priority < 100 的规则（防"压死式"兜底混入）',
      not _low_prio, '越界 %d 条: %s' % (len(_low_prio), _low_prio[:4]))

# D2 兜底本身走独立分支（_fallback），且目标已登记
_fb = routes.get('fallback')
check('D2 兜底走 _fallback 独立分支（不参与 priority 排序）',
      isinstance(_fb, dict) and isinstance(_fb.get('to'), str),
      'fallback=%r' % (_fb,))

# D3 —— ★ 换判据：行为级证明"剧情规则真的赢过兜底"。
#     站在 5 个原作连接起点上，match 必须返回**具体规则**而不是 desktop。
_wired = {}
for _r in (routes.get('routes') or []):
    _wired.setdefault(_r.get('when_scene'), _r['to'])
_d3_bad = []
for _sid in list(_wired.keys())[:5]:
    _e = _registered.get(_sid) or {}
    _h = sr.match(routes, mk_ctx(chapter_id=_e.get('chapter_id'), scene_id=_sid))
    if sr.route_target(_h) in (None, 'desktop'):
        _d3_bad.append(_sid)
check('D3 站在原作连接起点时命中的是具体剧情规则（不是兜底回桌面）',
      not _d3_bad, '落回兜底: %s' % _d3_bad)

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

# D7 —— ★ 第44轮新增：机制必须写进 meta（否则后人不知道边是怎么来的）
check('D7 _routes.json 的 meta 写明门的下标位移机制与"不编边"口径',
      'mechanism' in _meta and 'coverage_policy' in _meta
      and 'obj_doorA' in _meta)

# ===========================================================================
#  E. 背景素材口径 —— 第37轮已由反编译补齐，故升级为真判据
#     （原 E3 是 check(..., True) 的恒真占位：当时素材确实还没到位。
#       恒真判据比不写还危险 —— 它看着像在守，其实什么都没守。）
# ===========================================================================
print()
print('=== E. 背景素材口径 ===')

# E1 —— ★ 第38轮换判据。旧判据「每个作品内场景都声明了 bg 路径」建立在
#     「场景只有 88 个、且第37轮已给每个都反编译出背景」之上。第38轮之后场景变
#     1,013 个，其中 926 个**原作本来就没有背景精灵**（实测 147 个房间里只有 40 层带
#     bg_sprite）⇒ 旧判据无法满足。**不编造"区域代表素材"来让它继续绿**：那是把
#     "我没有这张图"伪装成"就是这张图"，违反本项目「算不出 → None，绝不伪装」铁律。
#     新判据保留原强度（锚点必须有真 bg），并把"没有 bg"这件事变成**必须显式声明**。
_bg_missing_key, _bg_null_undeclared, _anchor_no_bg = [], [], []
_anchor_total = 0
for sid in sorted(_story_scenes.keys()):
    entry = _story_scenes[sid]
    scene = ss.load_scene(sid, _SCENES, entry=entry)
    if scene is None:
        _bg_missing_key.append(sid + '(加载失败)')
        continue
    raw = scene.raw or {}
    if 'bg' not in raw:
        _bg_missing_key.append(sid)
        continue
    if not scene.bg:
        if raw.get('bg_source') != 'none':
            _bg_null_undeclared.append(sid)
    if entry.get('file'):
        _anchor_total += 1
        if not scene.bg:
            _anchor_no_bg.append(sid)
check('E1a 每个场景条目都显式声明了 bg 键（null 也算「声明」）',
      not _bg_missing_key,
      '缺 %d: %s' % (len(_bg_missing_key), _bg_missing_key[:5]))
check('E1b 没有 bg 的场景必须显式声明 bg_source="none"',
      not _bg_null_undeclared,
      '未声明 %d: %s' % (len(_bg_null_undeclared), _bg_null_undeclared[:5]))
check('E1c 有独立文件的锚点场景全部有非空 bg（原 E1 的强度保留在锚点上）',
      _anchor_total > 0 and not _anchor_no_bg,
      '锚点 %d 个，其中没 bg 的 %d: %s'
      % (_anchor_total, len(_anchor_no_bg), _anchor_no_bg[:5]))

_bg_dir_ok = True
for sid in sorted(_story_scenes.keys()):
    scene = ss.load_scene(sid, _SCENES, entry=_story_scenes[sid])
    if scene and scene.bg and not scene.bg.startswith('bg/'):
        _bg_dir_ok = False
check('E2 bg 路径统一走 bg/ 子目录（约定文件名）', _bg_dir_ok)

# bg 文件在第37轮已由反编译补齐 —— 此处升级为真判据
_bg_base = os.path.join(_SCENES)


def _bg_health_pairs(pairs):
    """pairs=[(sid, abs_path)] -> (missing, not_png)。判据内核，正负控制共用。"""
    miss, bad = [], []
    for sid, fp in pairs:
        if not os.path.isfile(fp):
            miss.append(sid)
            continue
        with open(fp, 'rb') as fh:
            if fh.read(8) != b'\x89PNG\r\n\x1a\n':
                bad.append(sid)
    return miss, bad


_scan = []
for sid in sorted(_story_scenes.keys()):
    scene = ss.load_scene(sid, _SCENES, entry=_story_scenes[sid])
    if scene and scene.bg:
        _scan.append((sid, os.path.join(_bg_base, scene.bg)))
_miss, _notpng = _bg_health_pairs(_scan)
check('E3 每个场景声明的 bg 都指向真实存在的 PNG（第37轮素材已反编译就位）',
      (not _miss) and (not _notpng) and len(_scan) > 0,
      '扫描 %d 个；缺失 %d %s；非PNG %d %s'
      % (len(_scan), len(_miss), _miss[:4], len(_notpng), _notpng[:4]))

_neg1, _ = _bg_health_pairs([('bogus', os.path.join(_bg_base, 'bg', '__no_such__.png'))])
check('E3b 负控制：判据抓得住"bg 文件不存在"（有鉴别力）',
      _neg1 == ['bogus'], 'got=%r' % _neg1)

_, _neg2 = _bg_health_pairs([('json', os.path.join(_SCENES, '_index.json'))])
check('E3c 负控制：判据抓得住"文件存在但不是 PNG"',
      _neg2 == ['json'], 'got=%r' % _neg2)

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
