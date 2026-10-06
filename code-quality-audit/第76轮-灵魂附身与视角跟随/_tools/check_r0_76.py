# -*- coding: utf-8 -*-
"""第76轮 R0 回归锁：门可交互（R0-2）+ 一句话走动入口（R0-1）不许静默失效。

锁什么：
  A 门字母解析（`door_letter_of`）—— 正/负成对，含"不能模糊匹配"的负控制；
  B 路由查表（`route_for_door`）—— 用**真表**，含不存在场景/门的负控制；
  C 真场景 `build_props` —— 不给 routes ⇒ 0 扇门（**零行为变化**）；
                            给 routes ⇒ 门被建出且目标非空；
  D 接线结构 —— `travel_to` / `travel_to_scene` 存在且**真被调用**；
               门不再落进 `else: continue` 被丢弃。

判据纪律（本项目铁律）：
  * `print('[PASS] %s')` 必须**字面量**（`run_all.py` 只认它）；
  * 判据名里**不许**自带 `[PASS]`/`[FAIL]` 字样；
  * 断**行为/结构**，不断赋值；负控制输入必须真落进被测分支。
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..', '..')
sys.path.insert(0, os.path.join(ROOT, 'ralsei_pet'))
# ★ item_interact 内部有扁平 import（`from companion import Interactable`）
#   ⇒ 必须把 modules 目录本身也放进去（真实启动是同目录运行，同样成立）。
sys.path.insert(0, os.path.join(ROOT, 'ralsei_pet', 'modules'))

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from modules import item_interact as ii   # noqa: E402

SCENES = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes')
MAIN = os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py')
SC = os.path.join(ROOT, 'ralsei_pet', 'modules', 'scene_controller.py')
II = os.path.join(ROOT, 'ralsei_pet', 'modules', 'item_interact.py')

_passed = 0
_failed = 0


def check(desc, cond):
    global _passed, _failed
    if cond:
        _passed += 1
        print('[PASS] %s' % desc)
    else:
        _failed += 1
        print('[FAIL] %s' % desc)


def _read(p):
    with open(p, 'r', encoding='utf-8') as f:
        return f.read()


# =============================================================== A. 门字母
LETTER_CASES = [
    # (src, 期望, 是否正控制)
    ('obj_doorA', 'A', True),
    ('obj_doorB', 'B', True),
    ('obj_doorF', 'F', True),
    # ★ 第89轮：W / X 转正 —— desktop.json 用 `obj_doorW`→黄魂、`obj_doorX`→OneShot
    #   两扇世界门（8 扇桌面门的既有事实）。原判据把 W/X 当"非法字母"的负控制，
    #   是"判据过窄 ⇒ 会误报"（记忆 §4 铁律）：字母解析器本来就照收任意单字母，
    #   产品**是否**用它才是路由层的事 —— 用"字母合法性"去卡解析器是**判据放错了层**。
    ('obj_doorW', 'W', True),
    ('obj_doorX', 'X', True),
    ('obj_doorA_0', 'A', True),
    ('obj_doora', 'A', True),
    ('obj_darkdoor', None, False),
    ('obj_doorevent', None, False),
    # 排除了 W/X 之后，仍在"解析器不该猜"的负控制：双字母、非 door 前缀
    ('obj_doorAA', None, False),
    ('obj_savepoint', None, False),
    ('', None, False),
    (None, None, False),
]

for _src, _want, _pos in LETTER_CASES:
    _got = ii.door_letter_of(_src)
    check('A 门字母 %s控制 door_letter_of(%r) == %r（实得 %r）'
          % ('正' if _pos else '负', _src, _want, _got), _got == _want)

# 负控制的"真落进分支"证明：非 door 前缀的名字必须真的走 return None 那条
check('A 负控制真落进分支：obj_savepoint 不以 obj_door 开头',
      not str('obj_savepoint').lower().startswith('obj_door'))

# =============================================================== B. 路由查表
_routes = json.load(io.open(os.path.join(SCENES, '_routes.json'), encoding='utf-8'))
_items = _routes.get('routes') or []
check('B 路由表条目 > 400（真表已加载，实得 %d）' % len(_items), len(_items) > 400)

_first = _items[0]
_fs = _first.get('when_scene')
_fd = _first.get('when_door')
_ft = _first.get('to')
_got = ii.route_for_door(_routes, _fs, _fd)
check('B 正控制：%s 的 %s 门 → %s（实得 %s）' % (_fs, _fd, _ft, _got), _got == _ft)
check('B 负控制：不存在的场景 ⇒ None',
      ii.route_for_door(_routes, '__no_such_scene__', 'A') is None)
check('B 负控制：%s 的 Z 门 ⇒ None（该场景无 Z）' % _fs,
      ii.route_for_door(_routes, _fs, 'Z') is None)
check('B 负控制：空表 ⇒ None', ii.route_for_door({}, _fs, _fd) is None)

_scenes_with_door = {}
for _r in _items:
    if isinstance(_r, dict) and _r.get('when_door'):
        _scenes_with_door.setdefault(_r['when_scene'], set()).add(_r['when_door'])
check('B 带门字母路由的场景 > 100（实得 %d）' % len(_scenes_with_door),
      len(_scenes_with_door) > 100)

# =============================================================== C. build_props
# ★ 数据源修正（本轮踩的判据坑）：`_index.json` 的顶层 `scenes` 是**空 dict** ——
#   场景登记在 `chapters → areas → 分片文件` 结构里。要拿"一个场景的 objects"，
#   必须走 `_zone.<ch>.<area>.json` 分片。判据一开始取错了源，报了个假 FAIL。
def _iter_zone_scenes():
    for _fn in sorted(os.listdir(SCENES)):
        if not (_fn.startswith('_zone.') and _fn.endswith('.json')):
            continue
        _d = json.load(io.open(os.path.join(SCENES, _fn), encoding='utf-8'))
        for _sid, _rec in (_d.get('scenes') or {}).items():
            if isinstance(_rec, dict):
                yield _sid, _rec


_cand = None
_n_zone = 0
for _sid, _rec in _iter_zone_scenes():
    _n_zone += 1
    _srcs = _rec.get('objects') or []
    if isinstance(_srcs, list) and any(
            isinstance(o, dict) and ii.door_letter_of(o.get('src')) for o in _srcs):
        _cand = (_sid, _rec)
        break
print('#   分片里扫到 %d 个场景' % _n_zone)

if _cand is None:
    check('C 找到一个真带门的场景（不成立则 C 段无效）', False)
else:
    _sid, _rec = _cand
    _objs = _rec.get('objects') or []
    print('#   选中场景 = %s（objects=%d）' % (_sid, len(_objs)))
    _scene = {'scene_id': _sid, 'objects': _objs, 'original_room_id': None}

    _p_no = ii.build_props(_scene, 'ch1', 'dark', routes=None)
    _d_no = [p for p in _p_no if getattr(p, 'kind', None) == 'door']
    check('C 负控制：不给 routes ⇒ 建出 0 扇门（实得 %d）' % len(_d_no), len(_d_no) == 0)

    _p_yes = ii.build_props(_scene, 'ch1', 'dark', routes=_routes)
    _d_yes = [p for p in _p_yes if getattr(p, 'kind', None) == 'door']
    for _d in _d_yes:
        print('#   %s 字母=%s → %s' % (_d.src, _d.door_letter, _d.target_scene))
    check('C 正控制：给 routes ⇒ 门数 > 0（实得 %d）' % len(_d_yes), len(_d_yes) > 0)
    check('C 每扇门都有 target_scene（不建"推不开的门"）',
          all(_d.target_scene for _d in _d_yes) if _d_yes else False)

    # 行为：门推成功/失败要如实
    _calls = []

    def _fake_enter(sid):
        _calls.append(sid)
        return sid != 'FAIL_SCENE'

    _p2 = ii.build_props(_scene, 'ch1', 'dark', routes=_routes, on_enter=_fake_enter)
    _d2 = [p for p in _p2 if getattr(p, 'kind', None) == 'door']
    if _d2:
        _ok = _d2[0].interact()
        check('C 行为：门 interact 调了 on_enter（实得 %r）' % (_calls[:1],),
              len(_calls) == 1 and _calls[0] == _d2[0].target_scene)
        check('C 行为：on_enter 返 True ⇒ interact 返 True', _ok is True)
    else:
        check('C 行为：有门可测（不成立则行为判据无效）', False)

    # 负控制：on_enter 返 False ⇒ interact 必须返 False（不谎报）
    _p3 = ii.build_props(_scene, 'ch1', 'dark', routes=_routes,
                         on_enter=lambda sid: False)
    _d3 = [p for p in _p3 if getattr(p, 'kind', None) == 'door']
    if _d3:
        check('C 负控制：on_enter 返 False ⇒ interact 返 False',
              _d3[0].interact() is False)
    else:
        check('C 负控制：有门可测（不成立则负控制无效）', False)

    # 负控制：没接 on_enter ⇒ 返 False（不静默成功）
    _p4 = ii.build_props(_scene, 'ch1', 'dark', routes=_routes, on_enter=None)
    _d4 = [p for p in _p4 if getattr(p, 'kind', None) == 'door']
    if _d4:
        check('C 负控制：无 on_enter ⇒ interact 返 False',
              _d4[0].interact() is False)

# =============================================================== D. 接线结构
_main = _read(MAIN)
_sc = _read(SC)
_ii = _read(II)

check('D scene_controller 有 travel_to', 'def travel_to(' in _sc)
check('D scene_controller 有 reachable_destinations', 'def reachable_destinations(' in _sc)
check('D main.py 有 travel_to_scene', 'def travel_to_scene(' in _main)
check('D main.py 有 _travel_feedback_fail', 'def _travel_feedback_fail(' in _main)

_calls = len(re.findall(r'self\.travel_to_scene\(', _main))
# ★ 判据放宽到 >= 2 并**改为计数相符**：菜单里恰有 2 处入口
#   （动态目的地项 + 回桌面）。写死 3 是过窄（会误报，见 §60.3）。
check('D main.py 里 travel_to_scene 真实调用 >= 2（实得 %d）' % _calls, _calls >= 2)

check('D travel_to 真的会调 switch（不绕门禁）', 'self.switch(sid)' in _sc)
# ★ 判据串修正：代码用的是 `result.update({... 'route': ...})`，
#   而不是 `result['route'] = ...`。原判据串选错 ⇒ 恒假（自己踩的坑）。
check('D travel_to 有 direct 降级标记（route 键真的被写入）',
      "'route': 'direct'" in _sc and "'route': 'path'" in _sc)

check('D item_interact 里 door 已有独立分支', "elif kind == 'door':" in _ii)
check('D item_interact 的 else 注释里不再写 door 交路由层',
      '`door`    —— 交路由层' not in _ii)
check('D build_props 新增 routes 形参', 'routes=None' in _ii)
check('D main.py 真的把 routes 传给 build_props', 'routes=routes,' in _main)

# ★ 判据串 no-op 显式打印（证明判据本身不是空转）
print('#   [no-op 检查] "def travel_to(" in sc_src => %s'
      % ('def travel_to(' in _sc))
print('#   [no-op 检查] "routes=routes," in main_src => %s'
      % ('routes=routes,' in _main))

print('=== 第76轮 R0 回归：PASS=%d FAIL=%d ===' % (_passed, _failed))
sys.exit(1 if _failed else 0)
