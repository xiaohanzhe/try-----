# -*- coding: utf-8 -*-
"""场景路由层验证 —— 「什么语境下走哪条路、去哪个场景」的接口与纯函数。

背景
----
用户在 P0 之后追加的需求原话：
  「根据场景系统，你也得给模型训练在什么语境下怎么走路线，去哪个场景。
    当然，你只需要留好拓展的接口，等咱开始做场景系统你才能真正根据地图线路
    来规划，当然，一切根据原作，所以如果你可以看到原作的地图线路那你就可以
    先进行第一版规划，不行就后面再看。」

拆成三条硬要求：
  1. **要有"语境 → 路线 → 场景"这层**，而不是只有 switch(scene_id) 这个原语。
  2. **接口优先，规划其次** —— 地图线路的精确规划要等场景真正开始做；现在
     能做的是把路由的**数据格式 + 匹配语义 + 拓展点**定下来。
  3. **一切根据原作** —— 原作房间表已抄进 `原作场景线路研究_2026-09-22.md`
     （实证来源 `code.deltarune.wiki` 的 `scr_roomname` 反编译）。本套件
     守住"研究记录里的房间数与实际抄来的一致"，防止以后有人手抖改坏。

与 P0 的关系
------------
P0 的判据是「不切场景时零行为变化」。路由层**同样遵守**：
`pick_route()` / `follow_route()` 在 P0 阶段**没有自动调用方**
（不注册定时器、不挂在事件链路上），所以行为变化依然为零。
本套件额外守住"路由层同样没有偷偷接线"。

分组
----
  A 模块存在与零依赖纪律
  B _routes.json 数据契约
  C match 的匹配语义（各 when_* 键 + AND/OR + 优先级）
  D **设计律三连**（返回 None 不伪装 / 坏规则跳过 / 未知键放行）
  E destinations 自省（过滤未登记场景 / 空→空串）
  F 控制器接线（load_routes 幂等 / pick_route / follow_route 幂等）
  G main.py 预声明（路由状态字段必须在宿主）
  H 零行为变化（路由层不得注册定时器 / 不得自己播动画）
  J 原作房间表研究记录完整性

本套件**不联网、不实例化 App、不需要显示器**（纯数据 + 桩宿主）。
必须用 C:\\Python311\\python.exe 运行。
"""
import ast
import io
import json
import os
import sys
import tokenize

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
SRC = os.path.join(PET, 'src')
MODS = os.path.join(PET, 'modules')
for _p in (PET, SRC, MODS):
    if _p not in sys.path:
        sys.path.append(_p)

PASS, FAIL = [], []


def ok(name, cond, detail=''):
    (PASS if cond else FAIL).append(name)
    print(('[PASS] ' if cond else '[FAIL] ') + name +
          ('' if cond else '   <<< ' + str(detail)))


def section(title):
    print('')
    print('=== %s ===' % title)


def _read(path):
    with io.open(path, encoding='utf-8') as fh:
        return fh.read()


ROUTING_PY = os.path.join(MODS, 'scene_routing.py')
CTL_PY = os.path.join(MODS, 'scene_controller.py')
MAIN_PY = os.path.join(SRC, 'main.py')
ROUTES_JSON = os.path.join(PET, 'assets', 'scenes', '_routes.json')
INDEX_JSON = os.path.join(PET, 'assets', 'scenes', '_index.json')
RESEARCH_MD = os.path.join(ROOT, '原作场景线路研究_2026-09-22.md')

ROUTING_TEXT = _read(ROUTING_PY)
CTL_TEXT = _read(CTL_PY)
MAIN_TEXT = _read(MAIN_PY)

# 工具：剥注释/字符串（只为断言**标识符/运算符**；断言字面量一律走 AST）
_DROP = (tokenize.COMMENT, tokenize.STRING, tokenize.NL, tokenize.NEWLINE,
         tokenize.INDENT, tokenize.DEDENT)


def code_only_src(src):
    out = []
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type in _DROP:
            continue
        out.append(tok.string)
    import re as _re
    return _re.sub(r'\s+', '', ' '.join(out))


CODE_ROUTING = code_only_src(ROUTING_TEXT)
CODE_CTL = code_only_src(CTL_TEXT)
CODE_MAIN = code_only_src(MAIN_TEXT)


def _string_constants(src):
    """源码里出现过的全部字符串字面量（AST 口径）。

    ⚠️ 为什么不用 `'"x" in src'` / `code_only_src`：字符串字面量在
    `code_only_src` 里**会被整个剥掉**（它 drop STRING token），于是
    `'desktop' in CODE` 恒假。本项目已因此踩坑 5 次（第 28 轮 P0 一次踩俩）。
    """
    tree = ast.parse(src)
    return {n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)}


import scene_routing as R          # noqa: E402
import scene_controller as C       # noqa: E402
import scene_system as S           # noqa: E402

# ===========================================================================
#  A  模块存在与零依赖纪律
# ===========================================================================
section('A 模块存在与零依赖纪律')


def _imports_of(src):
    tree = ast.parse(src)
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                names.add((a.name or '').split('.')[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                names.add('.' * node.level)
            elif node.module:
                names.add(node.module.split('.')[0])
    return names


ROUTING_IMPORTS = _imports_of(ROUTING_TEXT)

ok('A1 scene_routing.py 存在且可 import（拿到 ROUTES_SCHEMA_VERSION）',
   hasattr(R, 'ROUTES_SCHEMA_VERSION') and isinstance(R.ROUTES_SCHEMA_VERSION, int),
   'ROUTES_SCHEMA_VERSION=%r' % getattr(R, 'ROUTES_SCHEMA_VERSION', None))

_PROJECT_INTERNAL = {
    'logger_utils', 'data_store', 'memory_store', 'lazy_log', 'sprite_loader',
    'dialogue_ui', 'dialogue_system', 'emotion_system', 'config_manager',
    'floor_manager', 'ai_driver', 'event_speech', 'relationship',
    'search_summarizer', 'autonomous_agent', 'sound_manager', 'pet_ai',
    'desktop_interaction', 'command_manager', 'api_client', 'main',
    'customization_system',
}
_QT_MODULES = {'PyQt5', 'PyQt6', 'PySide2', 'PySide6'}

ok('A2 scene_routing.py 不 import 任何 Qt 模块',
   not (ROUTING_IMPORTS & _QT_MODULES),
   'imports=%s' % sorted(ROUTING_IMPORTS))

ok('A3 scene_routing.py 不 import 任何项目内业务模块（初始化环纪律）',
   not (ROUTING_IMPORTS & _PROJECT_INTERNAL),
   '越界=%s' % sorted(ROUTING_IMPORTS & _PROJECT_INTERNAL))

# 它允许 import scene_system（同为零依赖的姊妹模块）—— 显式声明这条白名单，
# 免得以后有人"顺手清理"掉它（删了会 NameError，不是静默失败，但仍值得锁）。
ok('A4 scene_routing.py 只从 scene_system 借 _read_json / scenes_dir',
   'scene_system' in ROUTING_IMPORTS,
   'imports=%s' % sorted(ROUTING_IMPORTS))

# 负控制：A2/A3 的判据真能抓人。
_FAKE_BAD = ('import sys\nfrom PyQt5.QtCore import QTimer\n'
             'from data_store import get_store\n')
_FB_IMPORTS = _imports_of(_FAKE_BAD)
ok('A5 负控制：A2/A3 的判据真能抓到越界 import（合成样本）',
   bool(_FB_IMPORTS & _QT_MODULES) and bool(_FB_IMPORTS & _PROJECT_INTERNAL),
   'qt=%s internal=%s' % (sorted(_FB_IMPORTS & _QT_MODULES),
                          sorted(_FB_IMPORTS & _PROJECT_INTERNAL)))

# 函数面齐备
for _fn in ('load_routes', 'match', 'route_target', 'route_reason',
            'describe_route', 'destinations', 'describe_destinations',
            'routes_path'):
    ok('A6 scene_routing 暴露 %s()' % _fn, callable(getattr(R, _fn, None)),
       '%r' % getattr(R, _fn, None))

# ===========================================================================
#  B  _routes.json 数据契约
# ===========================================================================
section('B _routes.json 数据契约')

ok('B1 _routes.json 存在', os.path.isfile(ROUTES_JSON))

with io.open(ROUTES_JSON, encoding='utf-8') as fh:
    ROUTES_RAW = json.load(fh)

ok('B2 schema_version == ROUTES_SCHEMA_VERSION',
   ROUTES_RAW.get('schema_version') == R.ROUTES_SCHEMA_VERSION,
   'json=%r py=%r' % (ROUTES_RAW.get('schema_version'), R.ROUTES_SCHEMA_VERSION))

ok('B3 routes 是数组', isinstance(ROUTES_RAW.get('routes'), list))

ok('B4 每条规则都有合法的 to（非空字符串）',
   all(isinstance(r, dict) and isinstance(r.get('to'), str) and r.get('to')
       for r in ROUTES_RAW.get('routes', [])),
   [r.get('to') for r in ROUTES_RAW.get('routes', []) if isinstance(r, dict)])

ok('B5 _fallback 存在且 to 合法（"匹配不到时回哪"必须有明确答案）',
   isinstance(ROUTES_RAW.get('_fallback'), dict)
   and isinstance(ROUTES_RAW['_fallback'].get('to'), str)
   and bool(ROUTES_RAW['_fallback'].get('to')),
   ROUTES_RAW.get('_fallback'))

# 加载器口径
_LOADED = R.load_routes()

ok('B6 load_routes() 成功且 ok=True', _LOADED.get('ok') is True,
   _LOADED.get('error'))
ok('B7 load_routes() 条数与 JSON 一致',
   len(_LOADED.get('routes') or []) == len(ROUTES_RAW.get('routes') or []),
   '%d vs %d' % (len(_LOADED.get('routes') or []),
                 len(ROUTES_RAW.get('routes') or [])))

# 路由目标必须**真实存在**于索引 —— 否则 follow_route 会把宠物送进空场景。
with io.open(INDEX_JSON, encoding='utf-8') as fh:
    IDX_RAW = json.load(fh)

_known_scenes = set()
for _ch in (IDX_RAW.get('chapters') or {}).values():
    for _ar in (_ch.get('areas') or {}).values():
        _known_scenes |= set((_ar.get('scenes') or {}).keys())

_all_targets = {r.get('to') for r in ROUTES_RAW.get('routes', [])}
_all_targets.add(ROUTES_RAW.get('_fallback', {}).get('to'))
_orphan = {t for t in _all_targets if t and t not in _known_scenes}
ok('B8 路由表里每个目标场景都登记在 _index.json（无孤儿目标）',
   not _orphan, '孤儿=%s  已知=%s' % (sorted(_orphan), sorted(_known_scenes)))

# 缺失文件时不得抛 —— 拿一个不存在的目录试。
_missing = R.load_routes(scene_dir_path=os.path.join(ROOT, '__no_such_dir__'))
ok('B9 目录不存在 → ok=False 且不抛（返回固定形状的 dict）',
   _missing.get('ok') is False
   and isinstance(_missing.get('routes'), list)
   and _missing.get('routes') == []
   and isinstance(_missing.get('error'), str),
   _missing)

# 负控制：schema 版本不符必须**明确拒绝**，不许"尽力解析"。
import tempfile as _tf
with _tf.TemporaryDirectory() as _td:
    with io.open(os.path.join(_td, '_routes.json'), 'w', encoding='utf-8') as _fh:
        json.dump({'schema_version': 999, 'routes': [{'to': 'desktop'}]}, _fh)
    _badver = R.load_routes(scene_dir_path=_td)
    ok('B10 负控制：schema_version 不符 → 明确拒绝（不"尽力解析"）',
       _badver.get('ok') is False and _badver.get('routes') == [],
       'ok=%r routes=%r err=%r' % (_badver.get('ok'), _badver.get('routes'),
                                   _badver.get('error')))

    # 坏规则跳过、好规则留下（设计律 2）
    with io.open(os.path.join(_td, '_routes.json'), 'w', encoding='utf-8') as _fh:
        json.dump({'schema_version': 1, 'routes': [
            {'to': 'desktop', 'reason': 'good'},
            'not-a-dict',
            {'reason': 'no-to-field'},
            {'to': '', 'reason': 'empty-to'},
            {'to': 'desktop2', 'reason': 'good2'},
        ]}, _fh)
    _skip = R.load_routes(scene_dir_path=_td)
    ok('B11 坏规则跳过、好规则留下（3 条坏的被跳过）',
       _skip.get('ok') is True
       and [r.get('to') for r in _skip['routes']] == ['desktop', 'desktop2'],
       [r.get('to') for r in _skip['routes']])

# ===========================================================================
#  C  match 的匹配语义
# ===========================================================================
section('C match 的匹配语义')


def _tbl(routes, fallback=None):
    """造一张测试用路由表（绕过磁盘）。"""
    return {'ok': True, 'routes': routes, 'fallback': fallback,
            'schema_version': 1, 'error': None}


def _r(to, priority=None, order=0, **kw):
    d = {'to': to, '_order': order}
    if priority is not None:
        d['priority'] = priority
    d.update(kw)
    return d


# C1 when_scene 精确命中
_m = R.match(_tbl([_r('a', 10, when_scene='s1')]), {'scene_id': 's1'})
ok('C1 when_scene 命中时返回该规则', R.route_target(_m) == 'a', _m)

# C2 when_scene 不匹配 → None
_m = R.match(_tbl([_r('a', 10, when_scene='s1')]), {'scene_id': 'zzz'})
ok('C2 when_scene 不匹配 → None（不是"随便挑一个"）', _m is None, _m)

# C3 when_scene='*' 通配任意场景
_m = R.match(_tbl([_r('a', 10, when_scene='*')]), {'scene_id': 'anything'})
ok('C3 when_scene="*" 通配任意场景', R.route_target(_m) == 'a', _m)

# C4 通配也要能在 scene_id 为 None 时命中（"没有当前场景"也是一种语境）
_m = R.match(_tbl([_r('a', 10, when_scene='*')]), {'scene_id': None})
ok('C4 when_scene="*" 在 current_scene 为 None 时仍命中', R.route_target(_m) == 'a', _m)

# C5 priority 小的先命中
_m = R.match(_tbl([_r('low', 100), _r('high', 1)]), {'scene_id': 'x'})
ok('C5 priority 小的先命中', R.route_target(_m) == 'high', _m)

# C6 同 priority：命中条件多的赢（更具体）
_m = R.match(_tbl([
    _r('generic', 50, order=0),
    _r('specific', 50, order=1, when_mood='happy', when_event='e1'),
]), {'scene_id': 'x', 'mood': 'happy', 'event': 'e1'})
ok('C6 同 priority 时"命中条件更多"的规则赢', R.route_target(_m) == 'specific', _m)

# C7 同 priority 同 score：声明序在前者赢（稳定排序）
_m = R.match(_tbl([_r('first', 50, order=0), _r('second', 50, order=1)]),
             {'scene_id': 'x'})
ok('C7 同 priority 同 score → 声明序在前者赢', R.route_target(_m) == 'first', _m)

# C8 不同条件之间是 AND
_m = R.match(_tbl([_r('a', 10, when_scene='s1', when_mood='happy')]),
             {'scene_id': 's1', 'mood': 'sad'})
ok('C8 不同 when_* 键之间是 AND（一个不满足就整体不匹配）', _m is None, _m)

# C9 when_mood 支持数组（命中任一即可）
_m = R.match(_tbl([_r('a', 10, when_mood=['happy', 'excited'])]),
             {'mood': 'excited'})
ok('C9 when_mood 是数组时命中任一即可（OR）', R.route_target(_m) == 'a', _m)

# C10 when_event 同上
_m = R.match(_tbl([_r('a', 10, when_event=['e1', 'e2'])]), {'event': 'e2'})
ok('C10 when_event 数组命中任一即可', R.route_target(_m) == 'a', _m)

# C11 when_keywords 是 OR 语义
_m = R.match(_tbl([_r('castle', 10, when_keywords=['城堡', '黑暗'])]),
             {'keywords': {'黑暗'}})
ok('C11 when_keywords 命中任一关键词即匹配', R.route_target(_m) == 'castle', _m)

# C12 关键词一个都不中 → None
_m = R.match(_tbl([_r('castle', 10, when_keywords=['城堡'])]),
             {'keywords': {'天气'}})
ok('C12 when_keywords 全不中 → None', _m is None, _m)

# C13 字符串标量不得被当字符集合拆开（`set("abc")` 那个坑）
_m = R.match(_tbl([_r('a', 10, when_mood='happy')]), {'mood': 'h'})
ok('C13 负控制：字符串条件不得被拆成单字符（"happy" 不该匹配 "h"）',
   _m is None, _m)

# C14 when_area / when_chapter
_m = R.match(_tbl([_r('a', 10, when_area='ar1', when_chapter='ch1')]),
             {'area_id': 'ar1', 'chapter_id': 'ch1'})
ok('C14 when_area + when_chapter 联合命中', R.route_target(_m) == 'a', _m)

# ===========================================================================
#  D  设计律三连
# ===========================================================================
section('D 设计律三连')

# 律 1：匹配不到 → None（不伪装）
_m = R.match(_tbl([]), {'scene_id': 'x'})
ok('D1 律1：空路由表且无兜底 → None（不伪造一条默认路线）', _m is None, _m)

# 有兜底时才给兜底，并**标记**它
_m = R.match(_tbl([], {'to': 'desktop', 'reason': 'fallback-reason'}),
             {'scene_id': 'x'})
ok('D2 有兜底时才用兜底，且标记 _fallback=True（可分辨"命中"与"兜底"）',
   R.route_target(_m) == 'desktop' and _m.get('_fallback') is True, _m)

# 兜底不得抢走显式命中
_m = R.match(_tbl([_r('explicit', 5000)], {'to': 'desktop'}),
             {'scene_id': 'x'})
ok('D3 显式规则（哪怕 priority 很大）也优先于兜底',
   R.route_target(_m) == 'explicit' and not _m.get('_fallback'), _m)

# 律 3：未知条件键一律**放行**（渐进增强）
_m = R.match(_tbl([_r('a', 10, when_weather='rain')]), {'scene_id': 'x'})
ok('D4 律3：未知 when_* 键一律放行（老版本读到新规则不应判不匹配）',
   R.route_target(_m) == 'a', _m)

# 负控制：已认识的键**不能**被当成未知放行
_m = R.match(_tbl([_r('a', 10, when_scene='s1')]), {'scene_id': 's2'})
ok('D5 负控制：已识别的 when_scene 不满足时必须拒绝（不是"全都放行"）',
   _m is None, _m)

# 律 3 反向：未知键放行了，但**已知键仍须满足**
_m = R.match(_tbl([_r('a', 10, when_weather='rain', when_scene='s1')]),
             {'scene_id': 's2'})
ok('D6 未知键放行 ≠ 整条规则放行（已知键仍须满足）', _m is None, _m)

# ===========================================================================
#  D2  when_door —— 多出口「共同卡口」（第44轮新增机制）
#
#  原作一个房间常有多个门（实测 297 个起点里 125 个有多于 1 条出边）。
#  when_door 的语义**故意与其它键相反**：context 没给 door 时**放行**
#  （这样"随便走一个门"仍有个确定归宿），给了 door 才精确分流。
#  四条语义 + 三条负控制 + 一条共同卡口行为级。
# ===========================================================================
section('D2 when_door 多出口分流（第44轮）')

# 语义 1：context 没给 door → 带 when_door 的规则**放行**
_m = R.match(_tbl([_r('a', 10, when_door='A')]), {'scene_id': 'x'})
ok('D2a when_door 有值但 context 没给 door → 放行（"没指定就走它"）',
   R.route_target(_m) == 'a', _m)

# 语义 2：给了 door 且相等 → 命中
_m = R.match(_tbl([_r('a', 10, when_door='A')]), {'scene_id': 'x', 'door': 'A'})
ok('D2b door 相等 → 命中', R.route_target(_m) == 'a', _m)

# 语义 3：给了 door 且不等 → **拒绝**（这是分流的关键）
_m = R.match(_tbl([_r('a', 10, when_door='A')]), {'scene_id': 'x', 'door': 'B'})
ok('D2c 负控制：door 不等 → 拒绝（否则多出口无法分流）', _m is None, _m)

# 语义 4：when_door='*' = 指定了任意门都行
_m = R.match(_tbl([_r('a', 10, when_door='*')]), {'scene_id': 'x', 'door': 'Z'})
ok('D2d when_door="*" → 指定任意门都命中', R.route_target(_m) == 'a', _m)

# 共同卡口行为级：同一场景两个门 → 不指定走 priority 小者；指定则精确分流
_hall = _tbl([_r('to_bedroom', 249, when_scene='hall', when_door='B'),
              _r('to_bath', 248, when_scene='hall', when_door='C')])
ok('D2e 共同卡口：不指定 door → 走 priority 最小者（结果确定、可复现）',
   R.route_target(R.match(_hall, {'scene_id': 'hall'})) == 'to_bath',
   R.route_target(R.match(_hall, {'scene_id': 'hall'})))
ok('D2f 共同卡口：指定 door=B → 精确分流（不再被 priority 决定）',
   R.route_target(R.match(_hall, {'scene_id': 'hall', 'door': 'B'})) == 'to_bedroom',
   R.route_target(R.match(_hall, {'scene_id': 'hall', 'door': 'B'})))
ok('D2g 共同卡口：指定 door=C → 另一出口',
   R.route_target(R.match(_hall, {'scene_id': 'hall', 'door': 'C'})) == 'to_bath',
   R.route_target(R.match(_hall, {'scene_id': 'hall', 'door': 'C'})))

# 负控制：指定了不存在的门 → 不许"随便挑一个"（必须 None / 兜底）
ok('D2h 负控制：指定不存在的门 → 不命中任何出口规则（不伪造）',
   R.match(_hall, {'scene_id': 'hall', 'door': 'Z'}) is None,
   R.match(_hall, {'scene_id': 'hall', 'door': 'Z'}))

# 坏规则不得作废整表（律 2 的行为面 —— B11 是数据面）
_m = R.match(_tbl([{'bogus': 1}, _r('good', 10)]), {'scene_id': 'x'})
ok('D7 律2：表里混进畸形规则，好规则照样能命中',
   R.route_target(_m) == 'good', _m)

# context 允许是对象而非 dict
class _Ctx(object):
    scene_id = 's1'
    mood = 'happy'


_m = R.match(_tbl([_r('a', 10, when_scene='s1', when_mood='happy')]), _Ctx())
ok('D8 context 可以是带属性的对象（不必非得是 dict）',
   R.route_target(_m) == 'a', _m)

# routes 直接传 list 也能用
_m = R.match([_r('a', 10, when_scene='s1')], {'scene_id': 's1'})
ok('D9 match() 也接受裸 list（调用方图省事时不强迫先 load_routes）',
   R.route_target(_m) == 'a', _m)

# ===========================================================================
#  E  destinations 自省
# ===========================================================================
section('E destinations 自省')

_FAKE_IDX = {'ok': True, 'scenes': {
    'a': {'name': '甲地', 'chapter_name': '第一章', 'area_name': '子区'},
    'b': {'name': '乙地', 'chapter_name': '第一章', 'area_name': '子区'},
}}

_d = R.destinations(_tbl([_r('a', 10), _r('b', 20), _r('ghost', 30)]), _FAKE_IDX)
ok('E1 destinations 过滤掉未登记的场景（防止 AI 被送往空场景）',
   [x['scene_id'] for x in _d] == ['a', 'b'],
   [x['scene_id'] for x in _d])

_d = R.destinations(_tbl([_r('a', 10), _r('b', 20)]), _FAKE_IDX)
ok('E2 destinations 去重（同一场景只在清单里出现一次）',
   len(_d) == len({x['scene_id'] for x in _d}), _d)

ok('E3 destinations 带出 name / chapter_name / area_name（供 AI 理解"那是哪"）',
   _d[0].get('name') == '甲地' and _d[0].get('chapter_name') == '第一章',
   _d[0] if _d else None)

# 不传 index → 按路由表原样列（包含"还未登记"的）
_d = R.destinations(_tbl([_r('a', 10), _r('ghost', 30)]))
ok('E4 不传 scene_index 时按路由表原样列（不静默过滤）',
   sorted(x['scene_id'] for x in _d) == ['a', 'ghost'],
   [x['scene_id'] for x in _d])

# 空 → 空串（调用方应整段不注入）
_txt = R.describe_destinations(_tbl([]))
ok('E5 无可达场景 → describe_destinations 返回空串（不硬说一句）',
   _txt == '', repr(_txt))

# 负控制：有场景时必须**非空**
_txt = R.describe_destinations(_tbl([_r('a', 10, reason='因为聊到了')]), _FAKE_IDX)
ok('E6 负控制：有可达场景时 describe_destinations 必须非空',
   isinstance(_txt, str) and _txt.strip() != '', repr(_txt))

ok('E7 注入文本含 scene_id 原样（AI 要能把它当参数吐回来）',
   _txt.startswith('- a ='), repr(_txt[:60]))

ok('E8 注入文本含 reason（AI 才知道"为什么值得去"）',
   '因为聊到了' in _txt, repr(_txt))

# ===========================================================================
#  F  控制器接线
# ===========================================================================
section('F 控制器接线')


class _StubHost(object):
    """桩宿主：只放被测代码会摸到的字段。

    ⚠️ 桩必须**跟着真实方法面走**（本项目踩过 4 次）。这里刻意只声明
    scene_controller 路由方法真正读写的名字，多一个都会掩盖"状态劈裂"。
    """
    _CONTROLLER_ATTRS = ('scene',)

    def __init__(self):
        self._scene_index = None
        self._scene_state = None
        self.current_scene = None
        self.scene_objects = []
        self._scene_anchors = {}
        self._scene_loaded = False
        self._scene_routes = None
        self._routes_loaded = False
        self._scene_route_reason = ''


_host = _StubHost()
_ctl = C.SceneController(_host)
_host.scene = _ctl

_loaded_ok = _ctl.load_routes()
ok('F1 load_routes() 在真实数据上返回 True', _loaded_ok is True, _loaded_ok)

ok('F2 load_routes 是幂等的（第二次调用不再 IO，结果一致）',
   _ctl.load_routes() is True)

# 幂等守卫真的落到宿主（而不是控制器自己的字典）
ok('F3 幂等守卫 _routes_loaded 落在**宿主**上（不在控制器）',
   _host.__dict__.get('_routes_loaded') is True
   and '_routes_loaded' not in _ctl.__dict__,
   'host=%r ctl=%r' % (_host.__dict__.get('_routes_loaded'),
                       _ctl.__dict__.get('_routes_loaded')))

ok('F4 路由表数据 _scene_routes 落在**宿主**上',
   isinstance(_host.__dict__.get('_scene_routes'), dict)
   and '_scene_routes' not in _ctl.__dict__,
   'host has=%r ctl has=%r' % (isinstance(_host.__dict__.get('_scene_routes'), dict),
                               '_scene_routes' in _ctl.__dict__))

# context_snapshot 的形状
_ctx = _ctl.context_snapshot()
ok('F5 context_snapshot 含全部约定的键',
   {'scene_id', 'area_id', 'chapter_id', 'mood', 'event', 'keywords'} <= set(_ctx),
   sorted(_ctx))

ok('F6 无当前场景时 scene_id 为 None（不伪造）',
   _ctx.get('scene_id') is None, _ctx.get('scene_id'))

ok('F7 mood 取不到时为 None（**不伪造 neutral** —— 否则会静默匹配上 neutral 规则）',
   _ctx.get('mood') is None, _ctx.get('mood'))

ok('F8 keywords 取不到时是空集合（不是 None）',
   isinstance(_ctx.get('keywords'), set) and not _ctx.get('keywords'),
   _ctx.get('keywords'))

# extra 覆盖
_ctx = _ctl.context_snapshot({'mood': 'happy', 'keywords': {'城堡'}})
ok('F9 extra 覆盖推导出来的值',
   _ctx.get('mood') == 'happy' and _ctx.get('keywords') == {'城堡'}, _ctx)

# extra 里的 None 不得覆盖掉已推导的值（否则调用方传个 None 就把真实语境抹了）
_host.current_scene = None
_ctx = _ctl.context_snapshot({'mood': None})
ok('F10 extra 里的 None **不覆盖**已推导的值（防"传个 None 抹掉真实语境"）',
   _ctx.get('mood') is None and 'mood' in _ctx, _ctx)

# pick_route 在真实数据上能命中
_host.current_scene = 'desktop'
_route = _ctl.pick_route()
ok('F11 pick_route() 在当前数据上能命中一条规则',
   isinstance(_route, dict) and R.route_target(_route) == 'desktop', _route)

# follow_route：已站在目标场景 → 返回 None（不"切到自己"）
_res = _ctl.follow_route()
ok('F12 follow_route 在"已站在目标场景"时返回 None（不原地重播转场）',
   _res is None, _res)

# follow_route 指向未登记场景 → 保持原地
_ctl2_host = _StubHost()
_ctl2 = C.SceneController(_ctl2_host)
_ctl2_host.scene = _ctl2
import tempfile as _tf2
with _tf2.TemporaryDirectory() as _td2:
    with io.open(os.path.join(_td2, '_routes.json'), 'w', encoding='utf-8') as _fh:
        json.dump({'schema_version': 1,
                   'routes': [{'to': 'ghost_scene', 'priority': 1}]}, _fh)
    _res = _ctl2.follow_route()
    ok('F13 follow_route 指向未登记场景 → 返回 None 且保持当前场景',
       _res is None and _ctl2_host.current_scene is None,
       'res=%r cur=%r' % (_res, _ctl2_host.current_scene))

# destinations / destinations_text 在真实数据上可用
_ds = _ctl.destinations()
ok('F14 destinations() 在真实数据上非空且只含已登记场景',
   isinstance(_ds, list) and all(d['scene_id'] in _known_scenes for d in _ds) and _ds,
   _ds)

_txt = _ctl.destinations_text()
ok('F15 destinations_text() 返回可注入的中文清单',
   isinstance(_txt, str) and _txt.strip() != '', repr(_txt[:80]))

# route_reason 默认空串
ok('F16 route_reason() 默认空串（没有路由发生时不该有理由）',
   _ctl2.route_reason() == '', repr(_ctl2.route_reason()))

# 状态不劈裂总检：路由用到的 3 个名字一个都不许出现在控制器字典里
_leak = {'_scene_routes', '_routes_loaded', '_scene_route_reason'} & set(_ctl.__dict__)
ok('F17 状态不劈裂：路由 3 个字段一个都没漏进控制器 __dict__',
   not _leak, '泄漏=%s' % sorted(_leak))

# 缺失属性仍应抛 AttributeError（转发不能变成"什么都答得上来"）
try:
    _ctl.__getattr__('definitely_not_a_real_attribute_xyz')
    _raised = False
except AttributeError:
    _raised = True
except Exception:
    _raised = False
ok('F18 转发壳对"宿主也没有"的名字仍抛 AttributeError（不静默返回 None）',
   _raised)

# ===========================================================================
#  G  main.py 预声明
# ===========================================================================
section('G main.py 预声明')

_MAIN_STRINGS = _string_constants(MAIN_TEXT)

ok('G1 scene_routing 的"语境键"在 main.py 里没有硬编码（路由是数据驱动）',
   'when_keywords' not in _MAIN_STRINGS,
   sorted(s for s in _MAIN_STRINGS if s.startswith('when_')))

# 三个路由状态字段必须在宿主 init_systems 里预声明
for _fld in ('_scene_routes', '_routes_loaded', '_scene_route_reason'):
    ok('G2 main.py 预声明了 %s（否则状态劈两份，G2 看不见）' % _fld,
       _fld in CODE_MAIN, '%s not in main.py' % _fld)

# 用 AST 取宿主类里对这三个字段的赋值（确认是"预声明"而不是"某处赋值"）
_main_tree = ast.parse(MAIN_TEXT)
_self_assigns = set()
for _node in ast.walk(_main_tree):
    if isinstance(_node, ast.Assign):
        for _t in _node.targets:
            if (isinstance(_t, ast.Attribute)
                    and isinstance(_t.value, ast.Name)
                    and _t.value.id == 'self'):
                _self_assigns.add(_t.attr)

for _fld in ('_scene_routes', '_routes_loaded', '_scene_route_reason'):
    ok('G3 main.py 用 `self.%s = ...` 真的赋过值（不是只写在注释里）' % _fld,
       _fld in _self_assigns, sorted(a for a in _self_assigns if 'scene' in a or 'route' in a))

# 负控制：AST 口径真能区分"赋值"与"仅在注释里提到"
_FAKE_SRC = 'class X:\n    def f(self):\n        # self._scene_routes = None\n        pass\n'
_ft = ast.parse(_FAKE_SRC)
_fake_assigns = set()
for _n in ast.walk(_ft):
    if isinstance(_n, ast.Assign):
        for _t in _n.targets:
            if (isinstance(_t, ast.Attribute)
                    and isinstance(_t.value, ast.Name) and _t.value.id == 'self'):
                _fake_assigns.add(_t.attr)
ok('G4 负控制：G3 的 AST 口径不会被"仅注释里提到"骗过',
   '_scene_routes' not in _fake_assigns, _fake_assigns)

# scene_controller 必须 import scene_routing（否则方法体里的 R.xxx 全 NameError）
ok('G5 scene_controller.py import 了 scene_routing',
   'scene_routing' in _imports_of(CTL_TEXT),
   sorted(_imports_of(CTL_TEXT)))

ok('G6 scene_controller.py 仍未 import 任何 Qt / 项目内业务模块',
   not (_imports_of(CTL_TEXT) & _QT_MODULES)
   and not (_imports_of(CTL_TEXT) & _PROJECT_INTERNAL),
   'qt=%s internal=%s' % (sorted(_imports_of(CTL_TEXT) & _QT_MODULES),
                          sorted(_imports_of(CTL_TEXT) & _PROJECT_INTERNAL)))

# ===========================================================================
#  H  零行为变化（路由层不许自己动起来）
# ===========================================================================
section('H 零行为变化')

# 路由层不得注册定时器 / 不得自己播动画 —— 否则 P0 的"零行为变化"判据失效。
ok('H1 scene_routing.py 不注册任何定时器（无 QTimer / start() 调用）',
   'QTimer' not in CODE_ROUTING, 'QTimer found in scene_routing')

# 用 AST 找 scene_controller 里对 QTimer/play_animation 的引用
_ctl_tree = ast.parse(CTL_TEXT)
_ctl_names = {n.id for n in ast.walk(_ctl_tree) if isinstance(n, ast.Name)}
_ctl_attrs = {n.attr for n in ast.walk(_ctl_tree) if isinstance(n, ast.Attribute)}

ok('H2 scene_controller 的**新路由段**不得引用 QTimer',
   'QTimer' not in _ctl_names and 'QTimer' not in _ctl_attrs,
   'names=%s attrs=%s' % (sorted(_ctl_names & {'QTimer'}),
                          sorted(_ctl_attrs & {'QTimer'})))

# ★ 关键：路由不得自己播动画（本项目铁律：特殊动画只有三类来源）
_anim_calls = _ctl_attrs & {'play_animation_once', 'play_special_animation',
                            'start_autonomous_speech'}
ok('H3 scene_controller 不得自己播动画 / 自主开口（动画三源铁律）',
   not _anim_calls, '越界调用=%s' % sorted(_anim_calls))

# 负控制：H2/H3 的判据真能抓人
_FAKE_CTL = ('import logging\n'
             'from PyQt5.QtCore import QTimer\n'
             'class X:\n'
             '    def f(self):\n'
             '        self.p.play_animation_once("x")\n'
             '        QTimer(self.p)\n')
_ft2 = ast.parse(_FAKE_CTL)
_fn = {n.id for n in ast.walk(_ft2) if isinstance(n, ast.Name)}
_fa = {n.attr for n in ast.walk(_ft2) if isinstance(n, ast.Attribute)}
ok('H4 负控制：H2/H3 的判据真能抓到 QTimer 与 play_animation_once（合成样本）',
   'QTimer' in _fn
   and bool(_fa & {'play_animation_once', 'play_special_animation',
                   'start_autonomous_speech'}),
   'names=%s attrs=%s' % (sorted(_fn), sorted(_fa)))

# 路由方法里不得直接调用 switch（那是 follow_route 的职责，且必须经登记检查）
# —— 用 AST 找"新路由段"的函数体里 switch 的调用点。
_route_fns = {'load_routes', 'context_snapshot', 'pick_route', 'follow_route',
              'destinations', 'destinations_text', 'route_reason'}
_switch_in_route = []
for _node in ast.walk(_ctl_tree):
    if isinstance(_node, ast.FunctionDef) and _node.name in _route_fns:
        for _sub in ast.walk(_node):
            if isinstance(_sub, ast.Call) and isinstance(_sub.func, ast.Attribute) \
                    and _sub.func.attr == 'switch':
                _switch_in_route.append(_node.name)

ok('H5 只有 follow_route 允许调 switch（其余路由方法不得自己切场景）',
   set(_switch_in_route) <= {'follow_route'},
   '调用点=%s' % sorted(set(_switch_in_route)))

# ===========================================================================
#  J  原作房间表研究记录
# ===========================================================================
section('J 原作房间表研究记录')

ok('J1 原作场景线路研究记录存在', os.path.isfile(RESEARCH_MD))

_research = _read(RESEARCH_MD)

# 五章都要在（用户说"一切根据原作"）
for _ch in ('Chapter 1', 'Chapter 2', 'Chapter 3', 'Chapter 4', 'Chapter 5'):
    ok('J2 研究记录含 %s 的房间表' % _ch, _ch in _research, _ch)

# 关键房间必须在（抽几条有代表性的，确认不是空表）
# ⚠️ 撇号口径：研究记录里写的是**直撇号** `'`（从我抓的源文照抄），不是
#    弯撇号 `\u2019`。用弯撇号做断言会恒假 —— 这是探针自身的坑，不是数据问题。
#    所以这里统一用直撇号。
for _room in ('Castle Town', 'Cyber City', 'Card Castle', "Queen's Mansion",
              'Flower Castle', 'TV World'):
    ok('J3 研究记录含房间 %s' % _room, _room in _research, _room)

# 机制要点必须写清（这是"抄原作"的依据，不是随便列的名单）
for _key in ('scr_roomname', 'room_goto', 'stringsetsubloc', 'obj_dw_transition'):
    ok('J4 研究记录含原作机制 %s' % _key, _key in _research, _key)

ok('J5 研究记录写明"一屏一房间不抄"（避免后人误抄）',
   '不抄' in _research, 'missing 不抄')

# 与 _index.json 的联动说明必须在
ok('J6 研究记录指向 _index.json（说清"登记在哪"）',
   '_index.json' in _research, 'missing _index.json')

# ===========================================================================
#  汇总
# ===========================================================================
print('')
print('=' * 66)
print('场景路由层：PASS=%d FAIL=%d' % (len(PASS), len(FAIL)))
if FAIL:
    print('失败项：')
    for _f in FAIL:
        print('  - %s' % _f)
print('=' * 66)
sys.exit(1 if FAIL else 0)
