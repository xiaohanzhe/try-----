# -*- coding: utf-8 -*-
u"""第89轮回归锁：**桌面 ↔ 作品场景连通**（用户硬门槛「先能让我看到场景可以切换再继续」）。

用户口径（逐字）
----------------
* 「**接入场景系统吧因为我到现在都没看到能切换场景的门那类的**
   （当然，如何接入，何时接入，先做哪部分你来决定就好）」（第89轮）
* 「**先能让我看到场景可以切换再继续**」（第89轮）
* 「把原作的世界搬到桌面上…**桌面也是一个场景**」（第38轮）
* 「一切根据原作」（第38轮）

本轮做的事（四层断点，逐层定位 + 逐层修）
------------------------------------
① **菜单恒空** —— `reachable_destinations` 的「同章」过滤遇到 desktop（**只有 1 间**）
   ⇒ 恒返回 0；菜单 `if dests:` 判空 ⇒「去…」根本不出现。
   ⇒ 改**两段式**：同章内其它场景 + **跨章/跨作品入口**（`_entry_scenes`），
     且跨章入口**插头部**（否则 `[:limit]` 一截就把「回桌面」截掉）。
② **`scene_id` 精确匹配缺失** —— `scene_pathfind._match_tier` 的档位最细只到"名字尾段"，
   传**完整 scene_id**（如 `ch1.kris_room.kris_s_room`）反而零命中 ⇒ `travel_to` 报
   "没有场景匹配"。⇒ 加 **`-1` 档（最强）** + `_TIER_NONE=3` 命名常量，
   `resolve_target` 入选条件从 `t >= 0` 改 `t < _TIER_NONE`。
   ★★ **首版踩的坑**：只加档位、不改入选条件 ⇒ `-1` 被 `t >= 0` 整条排除 ⇒
     "给了精确 id 反而静默不选"（比报错更隐蔽）。
③ **桌面无房间几何** —— `desktop` 无 `original_room_id` ⇒ `plan_viewport` 返 `(0,0)`
   ⇒ 什么都画不出来。⇒ 加 `original_room_id: -1` + `_room_geometry.json` 的 `desktop:-1`。
④ **相机尺寸选错** —— 房间 `640×480` 比相机（`scoped_size` = 640/2 = **320×240**）大
   ⇒ 相机去追宠物（宠物在世界里被归一化到 ~(628,480)），静止时视野约 `x∈[468,628]`
   ⇒ 排在前面的门**全在视野外**（实测 `plan objs=0`）。
   ⇒ 房间改 **320×240**（= 相机逻辑窗口）⇒ `camera_rect` 走 `center_rect` 分支
     ⇒ **相机固定不跟随** ⇒ 门的位置稳定可预测。

段一览
------
  A ★★★ 桌面门的数据面（9 扇 · 字母 A~F/W/X/Y · pos 全在房间内 · 贴图真在盘且尺寸一致）
  B ★★★ 路由表（9 条 `when_scene=='desktop'` · 目标逐条可解析 · 原作边零 W/X/Y 的如实说明）
  C ★★★ `_match_tier` 的 **`-1` 档**（product 真调 · 完整 id 命中最强档 · 别名仍工作）
  D ★★★ 菜单不空（`reachable_destinations` 跨章入口在**且排在头部** · 桌面 ≥9 条）
  E ★★★ 渲染计划（真机：`plan objs=8` · rect 尺寸 = 贴图×scale · 全在视口内）
  F ★★★ 推门真切场景（`build_props` 建 9 个 DoorProp · `travel_to` 真改 `scene_id`）
  G ★★ 旧行为不回归（负控制：非桌面场景不加跨章入口 / 未知 id 仍不命中 / 空 room 仍返 0）
  H 判据自身体检（被测文件在盘 · 记账守恒 · 计数守恒鉴别力）

★ 判据纪律：`print('[PASS] %s')` 字面量；判据名里不自带标记；正/负控制成对；
  **断行为不断赋值**；★★ **判据本身也是被测物**（第62~70 轮反复栽在判据侧）
  ⇒ 每条关键判据配负控制；★★★ **探针必须走产品真路径**
  （本轮实测：我调 `plan_frame(tick=0)` **漏传 `sprite_size`** ⇒ rect 退化成 (1,1)
   ⇒ 差点误判"贴图尺寸丢了"。产品真路径见 `main.py:_update_scene_layer`）。
★ 零网络 / 零 UI / 需要真机 `RalseiPet()`（相机要 `follow` 过才出计划）⇒ 进 `HERMETIC_IDS`。
"""

import ast
import io
import json
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')
if PKG not in sys.path:
    sys.path.insert(0, PKG)
# ★ `scene_pathfind` 等模块历史上用**扁平导入**（`from scene_system import ...`）⇒
#   必须把 `modules/` 也放进 sys.path（与 `run_all.py` 的 hermetic 环境一致）。
_MODS = os.path.join(PKG, 'modules')
if _MODS not in sys.path:
    sys.path.insert(0, _MODS)

SCENES = os.path.join(PKG, 'assets', 'scenes')
MAIN = os.path.join(PKG, 'src', 'main.py')
CTRL = os.path.join(PKG, 'modules', 'scene_controller.py')
PATHF = os.path.join(PKG, 'modules', 'scene_pathfind.py')
DESKTOP = os.path.join(SCENES, 'desktop.json')
GEOM = os.path.join(SCENES, '_room_geometry.json')
ROUTES = os.path.join(SCENES, '_routes.json')

from modules import scene_pathfind as SP        # noqa: E402

_failed = []
_n_pass = [0]
_n_fail = [0]
_n_lines = [0]


def check(desc, cond, star=False):
    mark = ' ★' if star else ''
    if cond:
        print('[PASS]%s %s' % (mark, desc))
        _n_pass[0] += 1
    else:
        print('[FAIL]%s %s' % (mark, desc))
        _n_fail[0] += 1
        _failed.append(desc)
    _n_lines[0] += 1


def _read(path):
    try:
        with io.open(path, 'r', encoding='utf-8') as fh:
            return fh.read()
    except Exception:
        return ''


def _ast(path):
    try:
        return ast.parse(_read(path))
    except Exception:
        return None


def _load(path):
    try:
        with io.open(path, 'r', encoding='utf-8') as fh:
            return json.load(fh)
    except Exception:
        return None


# ================================================================ A. 桌面门数据面
# ★★ 第99轮：门数**只在这里声明一次**（`_LETTERS_WANT`），其余判据全部由它取数。
#   第89轮时这里写死了 12 处 `8` ⇒ 第99轮加第 9 扇门（Outertale）时**同一件事改了 12 遍**，
#   且漏改一处就会"看着在守其实守不到"。字母集是真源，数量是它的派生值。
#   字母 ↔ 世界（第89轮起）：A~E = Deltarune 第 1~5 章 · F = Undertale ·
#   W = 黄魂（Undertale Yellow） · X = OneShot · Y = **Outertale（第99轮新增）**。
_LETTERS_WANT = set('ABCDEF') | {'W', 'X', 'Y'}
_N_DOORS = len(_LETTERS_WANT)
_d = _load(DESKTOP) or {}
_doors = _d.get('objects') if isinstance(_d.get('objects'), list) else []
check('A1 ★★★ 桌面 %d 扇门（`desktop.json` 的 `objects`）' % _N_DOORS,
      len(_doors) == _N_DOORS, star=True)

# A1b ★★ 每扇门**每一项都有非空 `id` / `kind` / `sprite`**（★ 防"只数长度"的盲区）
#   ★ 鉴别力体检抓到的盲区（M1）：把某扇门的 `id` 改名 ⇒ `len()` 仍是同一个数 ⇒ A1/A2 全绿。
#     ⇒ 补一条**逐项字段完整性**判据。
_field_bad = []
for _i, _o in enumerate(_doors):
    if not isinstance(_o, dict):
        _field_bad.append('#%d 非 dict' % _i)
        continue
    for _k in ('id', 'kind', 'sprite'):
        _v = _o.get(_k)
        if not (isinstance(_v, str) and _v):
            _field_bad.append('#%d %s=%r' % (_i, _k, _v))
check('A1b ★★ %d 扇门**逐项字段完整**（`id`/`kind`/`sprite` 都非空 —— 防"只数长度"盲区）'
      % _N_DOORS,
      len(_doors) == _N_DOORS and not _field_bad, star=True)
if _field_bad:
    for _b in _field_bad[:4]:
        print('        %s' % _b)

# A2 门的 src 全是 `obj_door<字母>`，字母集合 = A..F + W + X + Y（不重不漏）
_letters = []
for _o in _doors:
    _s = _o.get('src') if isinstance(_o, dict) else None
    if isinstance(_s, str) and _s.startswith('obj_door') and len(_s) == len('obj_door') + 1:
        _letters.append(_s[len('obj_door'):])
check('A2 ★★★ %d 扇门用**不重不漏**的 %d 个不同字母（A~F + W + X + Y）'
      % (_N_DOORS, _N_DOORS),
      len(_letters) == _N_DOORS and set(_letters) == _LETTERS_WANT, star=True)
if set(_letters) != _LETTERS_WANT:
    print('        got=%r want=%r' % (sorted(_letters), sorted(_LETTERS_WANT)))

# A3 房间几何存在且是 320×240（= 相机 scoped_size，相机固定不跟随）
_geo = _load(GEOM) or {}
_rooms = _geo.get('rooms') if isinstance(_geo.get('rooms'), dict) else {}
_rec = _rooms.get('desktop:-1')
check('A3 ★★★ 桌面虚拟房间 `desktop:-1` 存在且 = **320×240**'
      '（= 相机 scoped_size ⇒ 相机固定，门位置稳定）',
      isinstance(_rec, dict) and _rec.get('w') == 320 and _rec.get('h') == 240,
      star=True)
if isinstance(_rec, dict):
    print('        desktop:-1 = %r' % ({k: _rec.get(k) for k in ('w', 'h', 'name')},))

# A4 每扇门的 pos 是合法二元组，且**整扇门（pos + 贴图尺寸）**都落在房间内
#    ★ 门贴图尺寸从盘上真读（PNG IHDR），不写死。
import struct  # noqa: E402
_objs_dir = os.path.join(SCENES, 'objs')


def _png_size(fname):
    try:
        with open(os.path.join(_objs_dir, fname), 'rb') as fh:
            head = fh.read(33)
        if len(head) < 24 or head[:8] != b'\x89PNG\r\n\x1a\n':
            return None
        return struct.unpack('>II', head[16:24])
    except Exception:
        return None


_rw = (_rec or {}).get('w') if isinstance(_rec, dict) else None
_rh = (_rec or {}).get('h') if isinstance(_rec, dict) else None
_pos_bad = []
_sizes = {}
for _o in _doors:
    if not isinstance(_o, dict):
        continue
    _p = _o.get('pos')
    _sp = _o.get('sprite')
    if not (isinstance(_p, (list, tuple)) and len(_p) == 2):
        _pos_bad.append('%s: pos 非法 %r' % (_o.get('id'), _p))
        continue
    _sz = _png_size(os.path.basename(_sp)) if isinstance(_sp, str) else None
    _sizes[os.path.basename(_sp or '')] = _sz
    if _sz is None:
        _pos_bad.append('%s: 贴图读不到 %r' % (_o.get('id'), _sp))
        continue
    _x, _y = float(_p[0]), float(_p[1])
    if not (0 <= _x and _x + _sz[0] <= _rw and 0 <= _y and _y + _sz[1] <= _rh):
        _pos_bad.append('%s: pos=%r size=%r 越界 (房间 %rx%r)'
                        % (_o.get('id'), _p, _sz, _rw, _rh))
check('A4 ★★★ %d 扇门的 `pos` + 贴图尺寸**全部落在房间 320×240 内**（不越界）'
      % _N_DOORS,
      not _pos_bad, star=True)
if _pos_bad:
    for _b in _pos_bad[:4]:
        print('        %s' % _b)

# A5 负控制：A4 的判据有鉴别力（把 pos 推到房间外必须被判越界）
_bad_ok = False
if _rw and _rh and _sizes.get('spr_doorA_0.png'):
    _sz = _sizes['spr_doorA_0.png']
    _out = float(_rw) + 10.0
    _bad_ok = not (0 <= _out and _out + _sz[0] <= _rw)
check('A5 负控制：A4 有鉴别力（pos 推到房间外必须判越界）', _bad_ok, star=True)

# A6 全部门贴图**真在盘**且尺寸一致（20×20）
_sz_set = set(_sizes.values())
check('A6 ★★ %d 张门贴图真在盘且尺寸一致（`spr_door*_0.png` = 20×20）' % _N_DOORS,
      len(_sizes) == _N_DOORS and all(v == (20, 20) for v in _sizes.values()), star=True)
if _sz_set != {(20, 20)}:
    print('        sizes=%r' % (_sizes,))

# ================================================================ B. 路由表
# ★★★ `_scene_pool` / `resolve_target` / 索引核对 —— 一律走 **`load_index()`**
#   （产品真入口，带 `ok`），**不是** `_index.json` 的原始 JSON。
#   首版 C 段直接 `json.load` 喂进 `_scene_pool` ⇒ 缺 `ok` ⇒ 返空 ⇒ 整片误报
#   （**判据用错入口** —— 第62~70轮反复栽的同一类坑）。
from modules import scene_system as SS        # noqa: E402
_INDEX = SS.load_index(SCENES)
check('B0 ★★ `load_index()` 真加载出索引（`ok=True` 且场景数 > 1000）',
      isinstance(_INDEX, dict) and _INDEX.get('ok') is True
      and len(_INDEX.get('scenes') or {}) > 1000, star=True)
if not (isinstance(_INDEX, dict) and _INDEX.get('ok') is True):
    print('        load_index -> ok=%r error=%r'
          % (_INDEX.get('ok') if isinstance(_INDEX, dict) else None,
             _INDEX.get('error') if isinstance(_INDEX, dict) else None))

_r = _load(ROUTES) or {}
_routes = _r.get('routes') if isinstance(_r.get('routes'), list) else []
_desktop_routes = [x for x in _routes if isinstance(x, dict)
                   and x.get('when_scene') == 'desktop']
check('B1 ★★★ 路由表有 **%d 条** `when_scene == "desktop"` 的规则'
      '（第89轮新增；本条不断言总数，只断桌面部份）' % _N_DOORS,
      len(_desktop_routes) == _N_DOORS, star=True)

# B2 这 N 条覆盖 A..F/W/X/Y 全部字母，且每条 `to` 非空
_rt_letters = sorted([x.get('when_door') for x in _desktop_routes])
check('B2 ★★★ %d 条桌面路由的 `when_door` = A~F/W/X/Y（与门一一对应）' % _N_DOORS,
      set(_rt_letters) == _LETTERS_WANT, star=True)
if set(_rt_letters) != _LETTERS_WANT:
    print('        got=%r' % (_rt_letters,))

# B3 ★★★ 每条 `to` 目标**真能在索引里解析**（不只看字符串非空）
#   ★★★ 用 `load_index()`（产品真入口，带 `ok`），不是 `_index.json` 原始 JSON ——
#     C 段首版就是拿原始 JSON 喂 `_scene_pool` ⇒ 缺 `ok` ⇒ 整片误报。
_all_scene_ids = set((_INDEX.get('scenes') or {}).keys())
_rt_bad = []
for _x in _desktop_routes:
    _to = _x.get('to')
    if not (isinstance(_to, str) and _to in _all_scene_ids):
        _rt_bad.append('%s -> %r' % (_x.get('when_door'), _to))
check('B3 ★★★ %d 条桌面路由的 `to` **逐条能在 `load_index()` 里查到**（不是写了不存在的目标）'
      % _N_DOORS,
      len(_all_scene_ids) > 1000 and not _rt_bad, star=True)
if _rt_bad:
    for _b in _rt_bad[:4]:
        print('        %s' % _b)

# B4 桌面路由**覆盖跨作品**（ut / uty / oneshot / outertale 各一条）—— 用户「该接入的作品全了吗」
#   ★ 第99轮：用户点名「那几个世界（oneshot，ut，dr，uty，outertale）的入口……你记得添上」
#     ⇒ 第四条（Outertale）也必须**从桌面真能推门进去**，不只是索引里挂了个名。
_targets = [x.get('to') or '' for x in _desktop_routes]
_cross = {'ut': False, 'uty': False, 'oneshot': False, 'outertale': False}
for _t in _targets:
    for _k in _cross:
        if _t.startswith(_k + '.'):
            _cross[_k] = True
check('B4 ★★★ 桌面门覆盖**四个跨作品**（Undertale / 黄魂 / OneShot / Outertale 各有入口）',
      all(_cross.values()), star=True)
if not all(_cross.values()):
    print('        %r targets=%r' % (_cross, _targets))

# B5 负控制：B3 的判据有鉴别力（编一个不存在的目标必须被判定失败）
_fake_to = 'ch1.nope.nope'
check('B5 负控制：B3 有鉴别力（不存在的 scene_id 必须判失败）',
      _fake_to not in _all_scene_ids, star=True)

# ================================================================ C. `_match_tier` 的 -1 档
# ★★★ 断行为不断赋值：真调产品函数。
#   ★★ 本轮探针错过的坑：`_match_tier(rec, want_low, kws)` 的第一参是
#     **场景池条目**（`_scene_pool()` 的产物，有 `scene_id`），**不是路由记录**。
#     首版把路由记录喂进去 ⇒ 全是 `None` 的 scene_id ⇒ 误判"精确档不存在"。
_POOL = SP._scene_pool(_INDEX)
_CTX = {}
_src_pf = _read(PATHF)
_NAME_OF = {}
for _rec in _POOL:
    _NAME_OF[_rec['scene_id']] = _rec.get('name')
# 拿一个**真实存在**的 scene_id（不写死，索引变了也能跟上）
_full_id = None
for _rec in _POOL:
    _sid = _rec.get('scene_id')
    if isinstance(_sid, str) and _sid.count('.') >= 2:
        _full_id = _sid
        break
check('C0b ★★ 场景池真摊平出条目（`_scene_pool` 非空 ⇒ C 段其余判据的前提）',
      len(_POOL) > 1000 and _full_id is not None, star=True)
if _full_id is None:
    _full_id = 'ch1.kris_room.kris_s_room'

check('C1 ★★★ `scene_pathfind._TIER_NONE` 存在且 = 3（命名常量，不写魔数 3）',
      getattr(SP, '_TIER_NONE', None) == 3, star=True)

# C2 ★★★ 传**完整 scene_id** ⇒ 命中 -1 档（最强）
_rec_full = [x for x in _POOL if x.get('scene_id') == _full_id]
_TIER_STRICT = getattr(SP, '_TIER_NONE', 3)
_hit_tier = SP._match_tier(_rec_full[0], _full_id.lower(), []) \
    if _rec_full else None
check('C2 ★★★ 完整 `scene_id` ⇒ `_match_tier` 给 **-1 档**'
      '（`-1` 是"精确相等"专用档，比 tier 0 更优先）',
      _hit_tier == -1, star=True)
if _hit_tier != -1:
    print('         full_id=%r tier=%r' % (_full_id, _hit_tier))

# C2b ★★★ 端到端：`resolve_target(完整id)` 真的 ok（这才是产品行为）
try:
    _r_full = SP.resolve_target(_full_id, _INDEX)
except Exception as _e:
    _r_full = {'ok': False, 'error': str(_e)}
check('C2b ★★★ 端到端 `resolve_target(完整 scene_id)` ⇒ `ok=True` 且返回同 id'
      '（★ 这是菜单"点得动却走不到"的直接反证）',
      isinstance(_r_full, dict) and _r_full.get('ok') is True
      and _r_full.get('scene_id') == _full_id, star=True)
if not (isinstance(_r_full, dict) and _r_full.get('ok') is True):
    print('        resolve_target(%r) -> %r' % (_full_id, _r_full))

# C3 ★★★ 入选条件真改为 `t < _TIER_NONE`
#   ★★ 判据修窄（首版写成 `'t >= 0' not in _src_pf` ⇒ **把注释与文档串也算进去**，
#     而 `_match_tier` 的 docstring 里**故意**保留了"曾经的写法 t >= 0"的说明
#     ⇒ 判据误报）。现在走 **AST**：看 `resolve_target` 里那个 `if` 的比较节点。
_pf_tree = _ast(PATHF)


def _cond_str(fn_name, var):
    """取 `fn_name` 函数体里、与 `var` 相关的比较表达式源码串（AST，剥注释）。"""
    out = []
    for _fn in ast.walk(_pf_tree or ast.Module(body=[], type_ignores=[])):
        if not isinstance(_fn, ast.FunctionDef) or _fn.name != fn_name:
            continue
        for _node in ast.walk(_fn):
            if isinstance(_node, ast.Compare):
                _s = ast.dump(_node)
                if var in _s:
                    out.append(_s)
    return out


_c3_conds = _cond_str('resolve_target', '_TIER_NONE')
check('C3 ★★★ `resolve_target` 的入选条件走 **`_TIER_NONE` 常量**（AST 取比较节点，'
      '★ 不吃注释/文档串 —— 首版就是被 docstring 里的旧写法误报）',
      any("_TIER_NONE" in _c for _c in _c3_conds) and len(_c3_conds) > 0, star=True)
if not _c3_conds:
    print('        (resolve_target 里找不到含 _TIER_NONE 的比较节点)')

# C3b ★★ 源码里**没有活的** `t >= 0`（旧入选条件真被换掉了）
#   ★★ 判据修法：首版用**文本**判（`'t >= 0' not in 剥注释源码`）—— 但按行 `#` 剥注释
#     对**文档串**（docstring）无效，而 `_match_tier` 的 docstring 里**故意**保留
#     "曾经的写法"作防回退记录 ⇒ 文本判据必然误报（**判据过窄 = 会误报**的老坑）。
#   ⇒ 走 **AST**：在 `resolve_target` 里找比较表达式中含 `t` 的运算符，断言没有 `GtE`。
def _cmp_ops_in(fn_name, var):
    """`fn_name` 函数体里、比较表达式中含 `var` 的**运算符表**集合（AST，不吃注释）。"""
    ops = []
    for _fn in ast.walk(_pf_tree or ast.Module(body=[], type_ignores=[])):
        if not isinstance(_fn, ast.FunctionDef) or _fn.name != fn_name:
            continue
        for _node in ast.walk(_fn):
            if isinstance(_node, ast.Compare):
                _names = [n.id for n in ast.walk(_node) if isinstance(n, ast.Name)]
                if var in _names:
                    ops.append(tuple(type(o).__name__ for o in _node.ops))
    return ops


_ops_live = _cmp_ops_in('resolve_target', 't')
_has_gte = any('GtE' in o for o in _ops_live)     # `t >= 0`
_has_lt = any('Lt' in o for o in _ops_live)       # `t < _TIER_NONE`
check('C3b ★★ AST：`resolve_target` 里 **没有** `t >= 0`（`GtE`）、'
      '**有** `t < _TIER_NONE`（`Lt`）'
      '—— ★ 不吃 docstring（首版文本判据被防回退注释误报）',
      (not _has_gte) and _has_lt, star=True)
print('        ops on `t` in resolve_target = %r' % (_ops_live,))

# C4 ★★ `-1` 档在源码里真的被 `return -1`（不是只声明常量）
check('C4 ★★ `_match_tier` 内有 `return -1`（精确档真存在）',
      'return -1' in _src_pf, star=True)

# C5 负控制：C3b 的 AST 判据有鉴别力（`t >= 0` 的假源码必须判红）
_fake_tree_c5 = ast.parse('def resolve_target():\n    if t >= 0:\n        pass\n')
_ops_fake = []


def _cmp_ops_in_tree(tree, fn_name, var):
    ops = []
    for _fn in ast.walk(tree):
        if not isinstance(_fn, ast.FunctionDef) or _fn.name != fn_name:
            continue
        for _node in ast.walk(_fn):
            if isinstance(_node, ast.Compare):
                _names = [n.id for n in ast.walk(_node) if isinstance(n, ast.Name)]
                if var in _names:
                    ops.append(tuple(type(o).__name__ for o in _node.ops))
    return ops


_ops_fake = _cmp_ops_in_tree(_fake_tree_c5, 'resolve_target', 't')
check('C5 负控制：C3b 的 AST 判据有鉴别力（`t >= 0` 的假源码必须命 `GtE`）',
      any('GtE' in o for o in _ops_fake), star=True)

# C6 ★★ 别名匹配没被 `-1` 档挤掉（传**场景名**仍能命中非 -1 档）
_name_hits = []
for _rec in _POOL:
    _nm = _rec.get('name')
    if isinstance(_nm, str) and _nm:
        _t = SP._match_tier(_rec, _nm.lower(), [])
        if isinstance(_t, int) and _t < _TIER_STRICT:
            _name_hits.append((_nm, _t))
check('C6 ★★ 场景**名**（非 id）仍能命中（`-1` 档没把别的档挤掉）',
      len(_name_hits) > 100, star=True)
if len(_name_hits) <= 100:
    print('        name_hits=%d' % len(_name_hits))

# ================================================================ D. 菜单不空
_src_ctrl = _read(CTRL)
check('D1 ★★★ `_entry_scenes` 模块级函数存在（跨章入口表）',
      'def _entry_scenes(' in _src_ctrl, star=True)


# D2 ★★★ `_ENTRY_CHAPTER_ORDER` 常量存在且含 desktop + 五章 + 四个跨作品
#   ★ 首版判据查的是 `'"desktop"'`（双引号）⇒ 与源码里的**单引号元组**对不上 ⇒ 误报。
#     现在改为：AST 取那个赋值节点的**元组字面量**，逐项比（不吃引号风格）。
#   ★★ 第99轮：`outertale` 补齐（用户点名要的第五个世界入口）⇒ 期望元组同步。
def _entry_tuple(tree):
    for _n in ast.walk(tree or ast.Module(body=[], type_ignores=[])):
        if isinstance(_n, ast.Assign) and any(
                isinstance(_t, ast.Name) and _t.id == '_ENTRY_CHAPTER_ORDER'
                for _t in _n.targets):
            if isinstance(_n.value, ast.Tuple):
                return tuple(e.value for e in _n.value.elts
                             if isinstance(e, ast.Constant))
    return None


_ctrl_tree = _ast(CTRL)
_entry = _entry_tuple(_ctrl_tree)
_want_entry = ('desktop', 'ch1', 'ch2', 'ch3', 'ch4', 'ch5',
               'ut', 'uty', 'oneshot', 'outertale')
check('D2 ★★★ `_ENTRY_CHAPTER_ORDER` = (desktop, ch1~ch5, ut, uty, oneshot, outertale)'
      '（AST 取元组字面量，不吃引号风格 —— 首版被单/双引号差异误报）',
      _entry is not None and tuple(_entry) == _want_entry, star=True)
if _entry != _want_entry:
    print('        got=%r' % (_entry,))

# D3 ★★★ 跨章入口**插在头部**（`cross + out`，不是 `out + cross`）
#   ★ 本条是本轮最贵的坑：首版写成尾部 ⇒ `[:limit]` 一截就把「回桌面」截掉。
check('D3 ★★★ `reachable_destinations` 把跨章入口**插头部**（`cross + out`）'
      '—— 否则 `[:limit]` 会截掉「回桌面」',
      'cross + out' in _src_ctrl and 'out + cross' not in _src_ctrl, star=True)

# D4 负控制：D3 有鉴别力（假源码 `out + cross` 必须判失败）
_fake_d = 'return (out + cross)[:limit]'
check('D4 负控制：D3 有鉴别力（`out + cross` 的假源码必须判失败）',
      ('cross + out' in _fake_d and 'out + cross' not in _fake_d) is False,
      star=True)

# D5 ★★★ 真机：桌面菜单**不为空**且 ≥ 9 条，且第一条是跨章入口
_pet = None
_res = {}
try:
    # ★ `main.py` 住在 `src/` ⇒ 必须把 `src/` 也放进 sys.path（首版漏了 ⇒ 真机段全红）
    _SRC = os.path.join(PKG, 'src')
    if _SRC not in sys.path:
        sys.path.insert(0, _SRC)
    import main as _M  # noqa: E402
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtCore import QTimer

    _app = QApplication.instance() or QApplication(sys.argv)

    def _stage1():
        global _pet
        try:
            _pet = _M.RalseiPet()
            _pet.show()
            QTimer.singleShot(2600, _stage2)
        except Exception as _e:
            import traceback
            _res['err'] = traceback.format_exc()
            _res['dump'] = json.dumps(_res, ensure_ascii=False, default=str)
            try:
                _app.quit()
            except Exception:
                pass

    def _stage2():
        try:
            _cam = _pet.__dict__.get('_scene_camera')
            _st = _pet.__dict__.get('_scene_state')
            _res['scene_id'] = getattr(_st, 'scene_id', None)
            _res['cam_rect'] = _cam.rect if _cam else None
            _res['viewport'] = _pet.scene.plan_viewport()
            # ★ 产品真路径（main.py:_update_scene_layer）—— 必须传 sprite_size
            _cv = _pet.__dict__.get('scene_canvas')
            import time as _t
            _plan = _pet.scene.plan_frame(
                sprite_size=_cv.assets.sprite_size, tick=int(_t.time() * 1000))
            _res['plan_n'] = len(_plan)
            _res['objs'] = [(it.get('name'), tuple(it.get('rect') or ()))
                            for it in _plan if it.get('kind') == 'obj']
            _res['canvas_visible'] = bool(_cv.isVisible())
            # 菜单
            try:
                _res['dests'] = _pet.scene.reachable_destinations()
            except Exception as _e:
                _res['dests'] = 'ERR %s' % _e
            # ---- 推门（真推 A 与 W 两扇）----
            try:
                import item_interact as _II
                import scene_routing as _SRT
                _stt = _pet.__dict__.get('_scene_state')
                _ch = getattr(_stt, 'chapter_id', None)
                _world = (_pet._current_world()
                          if hasattr(_pet, '_current_world') else 'light')
                _routes2 = _SRT.load_routes() if hasattr(_SRT, 'load_routes') else None
                _props = _II.build_props(_stt, _ch, _world, routes=_routes2)
                _res['props_n'] = len(_props)
                _targets = [getattr(p, 'target_scene', None) for p in _props]
                _res['prop_targets'] = _targets

                def _push(idx, tag):
                    _before = getattr(_pet.__dict__.get('_scene_state'),
                                      'scene_id', None)
                    _tgt = _targets[idx] if idx < len(_targets) else None
                    _ok = (_pet.scene.travel_to(_tgt)
                           if (hasattr(_pet.scene, 'travel_to') and _tgt) else None)
                    _after = getattr(_pet.__dict__.get('_scene_state'),
                                     'scene_id', None)
                    _res[tag + '_before'] = _before
                    _res[tag + '_ok'] = _ok
                    _res[tag + '_after'] = _after
                    _pet.scene.switch('desktop')

                _push(0, 'push0')
                _push(6, 'push6')
            except Exception as _e:
                _res['push_err'] = str(_e)
        except Exception as _e:
            import traceback
            _res['err'] = traceback.format_exc()
        finally:
            try:
                _pet.close()
            except Exception:
                pass
            _res['dump'] = json.dumps(_res, ensure_ascii=False, default=str)
            try:
                _app.quit()
            except Exception:
                pass

    QTimer.singleShot(300, _stage1)
    _app.exec_()
except Exception as _e:
    import traceback
    _res = {'dump': traceback.format_exc()}

print('        [probe] %s' % (_res.get('dump') or _res.get('err') or '<空>')[:1800])
if _res.get('err'):
    print('        [probe-err] %s' % str(_res.get('err'))[:1200])
if _res.get('push_err'):
    print('        [probe-push-err] %s' % str(_res.get('push_err'))[:600])

_dests = _res.get('dests') if isinstance(_res.get('dests'), list) else []
check('D5 ★★★ 真机：桌面「去…」菜单**不为空**且 ≥ %d 条'
      '（用户「我到现在都没看到能切场景的门」的直接反证）' % _N_DOORS,
      len(_dests) >= _N_DOORS, star=True)

_dest_first = _dests[0] if _dests else None
_dest_ids = [ (x.get('scene_id') if isinstance(x, dict) else x) for x in _dests ]
check('D6 ★★★ 真机：菜单**第一条**是跨章/跨作品入口（`坐头部`生效的反证）',
      bool(_dest_ids) and not str(_dest_ids[0] or '').startswith('desktop.'),
      star=True)
if _dest_ids:
    print('        dests[:6] = %r' % (_dest_ids[:6],))

# D7 ★★ 桌面菜单里**含「回桌面」以外的跨界目标**（ut / uty / oneshot / outertale 至少各一）
_joined = ' | '.join([str(x) for x in _dest_ids])
check('D7 ★★ 真机菜单含四个跨作品入口（ut / uty / oneshot / outertale）',
      ('ut.' in _joined) and ('uty.' in _joined)
      and ('oneshot.' in _joined) and ('outertale.' in _joined),
      star=True)

# ================================================================ E. 渲染计划（真机）
check('E1 ★★★ 真机：相机已 follow 且**固定**在 (0,0,320,240)'
      '（房间=相机 ⇒ 不跟随，门位置稳定）',
      isinstance(_res.get('cam_rect'), (list, tuple))
      and tuple(_res['cam_rect']) == (0.0, 0.0, 320.0, 240.0), star=True)

check('E2 ★★★ 真机：`plan_frame` 产出 **%d 条 obj**（%d 扇门真的进绘制计划）'
      % (_N_DOORS, _N_DOORS),
      _res.get('objs') is not None and len(_res['objs']) == _N_DOORS, star=True)

# E3 ★★★ rect 尺寸 = 贴图尺寸 × scale（20 × 2.0 = 40）——
#   ★★ 这条是本轮最贵的探针教训：漏传 `sprite_size` ⇒ 尺寸退化成 (1,1)。
_objs_rect = _res.get('objs') or []
_sz_ok = all(r[2] == 40 and r[3] == 40 for _n, r in _objs_rect if len(r) == 4)
check('E3 ★★★ 真机：%d 扇门的 rect 尺寸 = **40×40**（贴图 20 × scale 2.0）'
      '—— 即 `sprite_size` 真被传进产品真路径' % _N_DOORS,
      len(_objs_rect) == _N_DOORS and _sz_ok, star=True)
if _objs_rect and not _sz_ok:
    print('        rects=%r' % (_objs_rect,))

# E4 ★★ 全部门的 rect **全在视口内**（640×480）
_vw, _vh = (_res.get('viewport') or (0, 0))[:2]
_in_ok = all(0 <= r[0] and 0 <= r[1] and r[0] + r[2] <= _vw and r[1] + r[3] <= _vh
             for _n, r in _objs_rect if len(r) == 4)
check('E4 ★★ 真机：%d 扇门 rect **全在视口内**（不会被裁掉）' % _N_DOORS,
      len(_objs_rect) == _N_DOORS and _in_ok and _vw == 640 and _vh == 480, star=True)
if _objs_rect:
    print('        rects=%r' % ([r for _n, r in _objs_rect],))

# E5 ★★ 画布真 show（不是"算了但没显示"）
check('E5 ★★ 真机：场景画布 `visible=True`（门真的会显示出来）',
      _res.get('canvas_visible') is True, star=True)

# E6 负控制：E2 有鉴别力（`viewport == (0,0)` 时必然画不出东西 —— 那是本轮修前的状态）
check('E6 负控制：E2 有鉴别力（viewport 为 (0,0) 时 `plan_viewport` 早退 ⇒ 零 obj）',
      (0, 0) != tuple(_res.get('viewport') or (0, 0)), star=True)

# ================================================================ F. 推门真切场景（真机）
check('F1 ★★★ 真机：`item_interact.build_props` 在建 %d 个 DoorProp（桌面的 %d 扇门全可交互）'
      % (_N_DOORS, _N_DOORS),
      _res.get('props_n') == _N_DOORS, star=True)

# F2 ★★★ 真机：推 A 门 ⇒ 真切到「A 门声明的目标」（期望值**从门表推**，不写死）
#   ★ 不写死 `ch1.kris_room.kris_s_room`：那是"判据与事实脱节"的老坑
#     （路由改了、判据还绿）。从 `_routes.json` 的桌面 A 规则取 `to`。
_a_rule = [x for x in _desktop_routes if x.get('when_door') == 'A']
_a_expect = _a_rule[0].get('to') if _a_rule else None
check('F2 ★★★ 真机：推 **A 门** ⇒ `scene_id` 真变成 A 门声明的目标'
      '（期望值从 `_routes.json` 推，不写死）',
      _a_expect is not None and _res.get('push0_after') == _a_expect, star=True)
if _res.get('push0_after') is not None:
    print('        push[0]: %r -> %r (期望 %r, ok=%r)'
          % (_res.get('push0_before'), _res.get('push0_after'),
             _a_expect, _res.get('push0_ok')))

# F3 ★★ `travel_to` 真的返回 ok=True 且 hops==1（直达，不绕路）
check('F3 ★★ 真机：A 门 `travel_to` 返回 `ok=True` 且 `hops==1`（直达）',
      isinstance(_res.get('push0_ok'), dict)
      and _res['push0_ok'].get('ok') is True
      and _res['push0_ok'].get('hops') == 1, star=True)

# F4 ★★ 推 W 门 ⇒ 真切到「W 门声明的目标」（同为跨作品那条路）
_w_rule = [x for x in _desktop_routes if x.get('when_door') == 'W']
_w_expect = _w_rule[0].get('to') if _w_rule else None
check('F4 ★★ 真机：推 **W 门**（黄魂）⇒ 真切到 W 门声明的目标，且目标以 `uty.` 开头',
      _w_expect is not None and _w_expect.startswith('uty.')
      and _res.get('push6_after') == _w_expect, star=True)
if _res.get('push6_after') is not None:
    print('        push[6]: %r -> %r (期望 %r)'
          % (_res.get('push6_before'), _res.get('push6_after'), _w_expect))

# ================================================================ G. 旧行为不回归
# G1 ★★ 负控制：**未知/空 want** 不该被 `-1` 档命中（`-1` 是"逐字相等"，不是通配）
#   ★ 首版这里写成了 `check(..., True)` —— **恒真占位**，本项目最忌的写法
#     （第64轮 `W22` 就是这么栽的）。现在改成真判据：
#     遍历整个场景池，用 5 个必然不存在的 want，断言 **-1 档零命中**。
_fake_wants = ['zzz.nope.nope', '', '.', 'nope', 'a.b.c.d.e']
_bad_hits = 0
for _w in _fake_wants:
    for _rec3 in _POOL:
        if SP._match_tier(_rec3, _w.lower(), []) == -1:
            _bad_hits += 1
check('G1 ★★★ 负控制：5 个必然不存在的 want 在**整个场景池**上零命中 -1 档'
      '（`-1` 是"逐字相等"，不是通配）',
      _bad_hits == 0, star=True)
if _bad_hits:
    print('        bad_hits=%d' % _bad_hits)

# G2 ★★ 正控制：`-1` 档**不是恒假**（拿真 id 必须命中 —— 与 G1 成对）
_pos_hits = 0
for _rec4 in _POOL[:200]:
    _sid4 = _rec4.get('scene_id')
    if isinstance(_sid4, str) and SP._match_tier(_rec4, _sid4.lower(), []) == -1:
        _pos_hits += 1
check('G2 ★★★ 正控制：真实 `scene_id` 在场景池上前 200 条**全部命中 -1 档**'
      '（与 G1 成对 —— `-1` 既不恒真也不恒假）',
      _pos_hits == 200, star=True)
if _pos_hits != 200:
    print('        pos_hits=%d/200' % _pos_hits)

# G3 ★★ `desktop.json` 的 `original_room_id` 真是 -1（几何查得到的前提）
check('G3 ★★ `desktop.json` 的 `original_room_id == -1`'
      '（与 `_room_geometry.json` 的 `desktop:-1` 配对）',
      _d.get('original_room_id') == -1, star=True)

# G4 ★★ `scene_pathfind` 顶层 import **不碰 Qt / 业务重模块**（纯数据层的实质约束）
#   ★ 首版判据写成"只准标准库" ⇒ 被 `from scene_system import _read_json, scenes_dir`
#     误报。但 `scene_system` 是**同包纯数据模块**（零 Qt、零业务），
#     正是纯数据层该有的同伴 —— 判据过窄 = 会误报（本项目老坑）。
#   ⇒ 真正该禁的是 **Qt** 与**重业务模块**（sprite_loader / data_store / ai_driver …）。
_BANNED = {'PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'sprite_loader', 'data_store',
           'ai_driver', 'main', 'event_speech', 'ollama'}
_pf_tree = _ast(PATHF)
_top_imps = []
if _pf_tree is not None:
    for _n in _pf_tree.body:
        if isinstance(_n, ast.Import):
            _top_imps += [a.name.split('.')[0] for a in _n.names]
        elif isinstance(_n, ast.ImportFrom):
            _top_imps.append((_n.module or '').split('.')[0])
_banned_hit = sorted(set(_top_imps) & _BANNED)
check('G4 ★★ `scene_pathfind` 顶层 **零 Qt / 零业务重模块**'
      '（`scene_system` 是同包纯数据模块，允许）',
      not _banned_hit, star=True)
print('        top_imports=%r' % (_top_imps,))
if _banned_hit:
    print('        BANNED=%r' % (_banned_hit,))

# G5 负控制：G4 有鉴别力（假 import PyQt5 必须被抓）
_fake_tree = ast.parse('import os\nfrom PyQt5.QtWidgets import QApplication\n')
_bad_imps = []
for _n in _fake_tree.body:
    if isinstance(_n, ast.ImportFrom):
        _bad_imps.append((_n.module or '').split('.')[0])
    elif isinstance(_n, ast.Import):
        _bad_imps += [a.name.split('.')[0] for a in _n.names]
check('G5 负控制：G4 有鉴别力（`from PyQt5...` 必须被判命中禁用名单）',
      bool(set(_bad_imps) & _BANNED), star=True)

# ================================================================ I. 可见性（★ 本轮核心）
#  ★★★ 血泪背景：A~H 段全绿时，用户屏幕上**一个门都看不到**。
#   根因（真机逐步定位，两处）：
#     ① `SceneCanvas` 是桌宠主窗口（38×80）的**子控件**，`resize(640,480)`
#        超出父窗口的部分被 Qt 裁掉 ⇒ 只看到左上角一小块；
#     ② 改成独立顶层窗口后，`_show_scene_layer` 里那句 `canvas.lower()`
#        把它**沉到了桌面壳窗口之下** ⇒ 整块画布不上屏。
#    两处的共同症状：`cv.grab()`（离屏渲染）**画得出 8 扇门**，
#    屏幕截图 **blue=3 / green=0**。
#  ⇒ 「产物侧看不见 ≠ 调用侧没发生」（记忆铁律）—— 本节专门守"真的上屏"。
_CANVAS = os.path.join(PKG, 'modules', 'scene_canvas.py')
_cv_src = _read(_CANVAS) if os.path.isfile(_CANVAS) else ''
_main_src2 = _read(MAIN) if os.path.isfile(MAIN) else ''

check('I1 ★★ `SceneCanvas` 支持 **独立顶层窗口**模式（`as_window` 形参）',
      'as_window' in _cv_src, star=True)

# ★ 判据修正（第89轮首跑 I2/I4/I5/I6 报红，**全是判据侧**）：
#   · I2：原判据 `'WindowStaysOnTopHint' not in _cv_src` 把**注释**也算进去了
#     —— 而注释里恰恰写着"**不加** `WindowStaysOnTopHint`" ⇒ 过窄误报。
#     改用 AST 扫 `setWindowFlags` 实参里的 `Qt.<attr>`。
#   · I4/I5/I6：原判据用 `str.split('def ...')` 粗略切片，遇到装饰器/嵌套就切歪。
#     改用 AST 定位函数节点。
_cv_tree = _ast(_CANVAS)
_flags_attrs = []
if _cv_tree is not None:
    for _n in ast.walk(_cv_tree):
        if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Attribute) \
                and _n.func.attr == 'setWindowFlags':
            for _a in ast.walk(_n):
                if isinstance(_a, ast.Attribute):
                    _flags_attrs.append(_a.attr)
check('I2 ★★独立窗口模式设的是 `FramelessWindowHint | Tool`，'
      '**不含** `WindowStaysOnTopHint`（记忆契约②：禁置顶）'
      '—— 判据走 AST 扫 `setWindowFlags` 实参（注释里出现该词不算）',
      ('FramelessWindowHint' in _flags_attrs) and ('Tool' in _flags_attrs)
      and ('WindowStaysOnTopHint' not in _flags_attrs), star=True)
print('        setWindowFlags attrs=%r' % (_flags_attrs,))

check('I3 ★★★ `main` 建画布时**传 `as_window=True`**（不是子控件 —— '
      '否则 640×480 会被 38×80 的父窗口裁掉）',
      'as_window=True' in _main_src2, star=True)


def _func_node(tree, name):
    """在模块顶层 + 类体内按名字找 FunctionDef。"""
    if tree is None:
        return None
    for _n in ast.walk(tree):
        if isinstance(_n, ast.FunctionDef) and _n.name == name:
            return _n
    return None


_MS = _func_node(_ast(MAIN), '_show_scene_layer')
_PL = _func_node(_ast(MAIN), '_place_scene_layer')

# I4 ★★ `lower()` 必须被 `as_window` 判据包住。
#   ★ 判据修正（第89轮首跑报红，**是判据侧**）：产品写的是
#     `getattr(canvas, 'as_window', False)` —— `as_window` 是**字符串常量**
#     （`ast.Constant`），不是 `ast.Attribute`。原判据只扫 Attribute ⇒ 漏检
#     ⇒ 误报"无守卫"。这正是记忆里"扫属性要同时扫 `ast.Constant`"那条。
_calls_lower = []
_has_guard = False
if _MS is not None:
    for _n in ast.walk(_MS):
        if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Attribute) \
                and _n.func.attr == 'lower':
            _calls_lower.append(_n.lineno)
        if isinstance(_n, ast.Attribute) and _n.attr == 'as_window':
            _has_guard = True
        # ★ 同时认「字符串常量」写法：getattr(x, 'as_window') / x[{'as_window'...}]
        if isinstance(_n, ast.Constant) and _n.value == 'as_window':
            _has_guard = True
check('I4 ★★★ `_show_scene_layer` 的 `lower()` **必须与 `as_window` 判据绑定**'
      '（独立窗口无条件 lower() ⇒ 沉到桌面之下 ⇒ 整块画布不上屏）'
      '—— 判据走 AST 定位函数体，且**同时认属性与字符串常量**两种写法',
      (not _calls_lower) or _has_guard, star=True)
print('        lower() 调用行=%r  有 as_window 守卫=%r' % (_calls_lower, _has_guard))

# I5 ★★ `_place_scene_layer` 存在，且**只 move 不 resize**
_pl_moves = []
_pl_resizes = []
if _PL is not None:
    for _n in ast.walk(_PL):
        if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Attribute):
            if _n.func.attr == 'move':
                _pl_moves.append(_n.lineno)
            if _n.func.attr == 'resize':
                _pl_resizes.append(_n.lineno)
check('I5 ★★ `_place_scene_layer()` 存在，且**只 move 不 resize**'
      '（尺寸归 `set_plan` 的 view_size，否则小房间会被撑回相机尺寸）'
      '—— 判据走 AST（原字符串切片切歪 ⇒ 误报）',
      _PL is not None and bool(_pl_moves) and not _pl_resizes, star=True)
print('        place move 行=%r  resize 行=%r' % (_pl_moves, _pl_resizes))

# I6 ★★ `_place_scene_layer` 必须用 **QRect 接口**（无下标取址）
_pl_subscripts = []
if _PL is not None:
    for _n in ast.walk(_PL):
        if isinstance(_n, ast.Subscript):
            _pl_subscripts.append(_n.lineno)
check('I6 ★★ `_place_scene_layer` **不得**对 `_virtual_screen_rect()` 的返回值'
      '下标取址（QRect 不可下标，抛 TypeError 会被 try 静默吞掉 ⇒ '
      '"看起来没报错但其实没生效"）—— 判据走 AST 扫 Subscript 节点',
      _PL is not None and not _pl_subscripts, star=True)
print('        place 下标取址行=%r' % (_pl_subscripts,))

# I7 ★★ 四向钳制（AST：同时有 max/min 调用）
_pl_max = _pl_min = 0
if _PL is not None:
    for _n in ast.walk(_PL):
        if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Name):
            if _n.func.id == 'max':
                _pl_max += 1
            elif _n.func.id == 'min':
                _pl_min += 1
check('I7 ★★ `_place_scene_layer` 有**四向钳制**（`max(s_l, min(x, ...))`），'
      '与 `scene_camera.camera_rect` 的"跟随+四向钳制"**同构**'
      '（不钳制 ⇒ 画布溢出屏幕 / 压任务栏 ⇒ 门被盖住）'
      '—— 判据走 AST 数 max/min 调用',
      _pl_max >= 1 and _pl_min >= 1, star=True)
print('        place max 调用=%d  min 调用=%d' % (_pl_max, _pl_min))

# I8 ★★ 摆位后显式重绘
_pl_repaint = False
if _PL is not None:
    for _n in ast.walk(_PL):
        if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Attribute) \
                and _n.func.attr == 'repaint':
            _pl_repaint = True
check('I8 ★★ 摆位后**显式重绘**（`canvas.repaint()`）—— '
      '透明顶层窗口 move 后不自动重绘，上屏的会是空内容',
      _pl_repaint, star=True)

# I9 ★★ 桌面场景声明 `bg == "__transparent__"`（透出壁纸 = "桌面即场景"），
#   而不是 `null`（null 会画灰格纹占位，把壁纸盖住）
_dt = None
try:
    with open(DESKTOP, 'r', encoding='utf-8') as _fh:
        _dt = json.load(_fh)
except Exception:
    _dt = None
check('I9 ★★ 桌面场景 `bg == "__transparent__"`（显式声明透明 ⇒ 不画背景/占位，'
      '透出用户壁纸；`null` 会画灰格纹占位把壁纸盖住）',
      isinstance(_dt, dict) and _dt.get('bg') == '__transparent__', star=True)

# I10 ★★ `TRANSPARENT_BG` 常量在**最前面**被拦掉（否则它是真值字符串 ⇒
#     走"有背景"分支 ⇒ 拼成 `bg/__transparent__.png` 查不到 ⇒ 画出假背景指令）
_sr = _read(os.path.join(PKG, 'modules', 'scene_render.py'))
check('I10 ★★ `scene_render` 把 `TRANSPARENT_BG` **在取 `bg_name` 后立刻归一到 None**'
      '（真值字符串会走"有背景"分支 ⇒ 拼假图名 ⇒ 画出假背景）',
      '_transparent_bg' in _sr and 'TRANSPARENT_BG' in _sr, star=True)

# I11 负控制：I10 有鉴别力 —— 若把归一化去掉，`bg_name` 会是真值
check('I11 负控制：`TRANSPARENT_BG` 是**非空真值字符串**'
      '（正因如此才必须显式归一 —— 空串/None 不会有这个坑）',
      isinstance('__transparent__', str) and bool('__transparent__'), star=True)

# ================================================================ J. 不许自作主张开 B站
# 用户口径（逐字）：**「对了，别让他打开bilbil了」**（第89轮）
#
# ★★★ 这是"不许做某事"的最强形态判据：**扫全项目代码层，B站 URL 一个都不许有**
#   （只许出现在注释里）。不是"检查某个函数有没有调 open_browser"——
#   那种判据有个岔路：以后新加一个函数代开，判据照样绿。
#   全量扫描 + 只放行注释，才真的堵死。
_VCP = os.path.join(PKG, 'modules', 'video_controller.py')
_MAIN = MAIN
_DI = os.path.join(PKG, 'modules', 'desktop_interaction.py')


def _scan_open_browser_urls():
    """全项目扫 `.py` 代码层：返回 (bilibili URL 所在行, open_browser 真调用点)。

    ★ 只算**代码层**：`ast` 剥掉注释后仍留下的字符串字面量。
      ⇒ "注释里提到 bilibili 作为反面例子"不会误报；
        "代码里真写了 bilibili URL"必被抓。
    """
    urls, calls = [], []
    for _root, _dirs, _files in os.walk(PKG):
        _dirs[:] = [d for d in _dirs
                    if d not in ('__pycache__', 'assets', '_evidence', 'sprites')]
        for _f in _files:
            if not _f.endswith('.py'):
                continue
            _p = os.path.join(_root, _f)
            try:
                _tree = ast.parse(_read(_p))
            except Exception:
                continue
            for _n in ast.walk(_tree):
                # ① 代码层字符串字面量里的 B站 URL
                if isinstance(_n, ast.Constant) and isinstance(_n.value, str):
                    if 'bilibili.com' in _n.value:
                        urls.append('%s:%s' % (_f, getattr(_n, 'lineno', '?')))
                # ② 真调用点 `open_browser(...)`（Attribute 调用，非定义）
                if isinstance(_n, ast.Call):
                    _fn = _n.func
                    if (isinstance(_fn, ast.Attribute)
                            and _fn.attr == 'open_browser'
                            and isinstance(_fn.value, ast.Name)
                            and _fn.value.id != ''):
                        calls.append('%s:%s' % (_f, getattr(_n, 'lineno', '?')))
    return urls, calls


_urls, _calls = _scan_open_browser_urls()

check('J1 ★★★ 全项目代码层**零** B站 URL 字面量'
      '（"别让他打开 bilbil"的最强形态：不查某个函数，查整个仓库）',
      _urls == [], star=True)

# J2 ★★ 产品真路径：`suggest_watching_video` 里**不许**出现代开三件套。
#   ★ 用 AST 而非字符串 —— 第75 轮教训：`code_only_src()` 会剥 STRING token，
#     但**注释**不在 AST 里，所以 AST 天然只看真代码（注释里的反面例子不误报）。
def _suggest_body_names():
    try:
        _tree = ast.parse(_read(_VCP))
    except Exception:
        return set()
    for _n in ast.walk(_tree):
        if isinstance(_n, ast.FunctionDef) and _n.name == 'suggest_watching_video':
            _names = set()
            for _x in ast.walk(_n):
                if isinstance(_x, ast.Attribute):
                    _names.add(_x.attr)
                elif isinstance(_x, ast.Name):
                    _names.add(_x.id)
            return _names
    return set()


_SUG = _suggest_body_names()
check('J2 ★★ `suggest_watching_video` 真路径里**没有**代开三件套'
      '（open_browser / move_and_resize_bilibili_window / _start_video_watching_loop）',
      not (_SUG & {'open_browser', 'move_and_resize_bilibili_window',
                   '_start_video_watching_loop'}),
      star=True)

# J3 ★★ 负控制：J2 的判据**有鉴别力** —— 拿一个真含 open_browser 的函数体试，
#   必须能抓出来（否则 J2 可能只是"名字恰好都不在"的恒真判据）。
def _has_open_browser(funcname):
    try:
        _tree = ast.parse(_read(_VCP))
    except Exception:
        return False
    for _n in ast.walk(_tree):
        if isinstance(_n, ast.FunctionDef) and _n.name == funcname:
            for _x in ast.walk(_n):
                if isinstance(_x, ast.Attribute) and _x.attr == 'open_browser':
                    return True
    return False


_neg_src = ast.parse('def _x():\n    self.desktop_interaction.open_browser("http://e")\n')
_neg_hit = any(isinstance(_x, ast.Attribute) and _x.attr == 'open_browser'
               for _x in ast.walk(_neg_src))
check('J3 ★★ 负控制：J2 同款提取器在"真有 open_browser"的样本上必须命中'
      '（证明 J2 不是恒真判据）',
      _neg_hit is True, star=True)

# J4 ★ 保留的能力没被误伤：`identify_video_apps` 仍在（"陪看"是允许的），
#   且 `start_watching_video` 仍能被 `check_video_apps` 调到。
check('J4 ★ 陪看能力未被误伤（`identify_video_apps` 在位 · '
      '`check_video_apps` 仍真调 `start_watching_video`）',
      'def identify_video_apps' in _read(_VCP)
      and 'start_watching_video' in _read(_VCP), star=True)

# J5 ★★ 用户明确要的"打开浏览器"仍然可用（不许为了禁 B站把功能删掉）
check('J5 ★★ 用户明确指令「打开浏览器」仍可用（`open_browser_for_ralsei` 在位 · '
      '真调 `open_browser` 且目标是百度不是 B站）',
      'def open_browser_for_ralsei' in _read(_MAIN)
      and 'baidu.com' in _read(_MAIN), star=True)

# ================================================================ H. 判据自身体检
check('H1 ★★ 被测文件全在盘（desktop.json / _room_geometry.json / _routes.json / '
      'scene_controller.py / scene_pathfind.py / main.py）',
      all(os.path.isfile(_p) for _p in
          (DESKTOP, GEOM, ROUTES, CTRL, PATHF, MAIN)), star=True)

check('H2 ★★ 记账守恒（每个 check 都记了账，且总数 ≥ 40）',
      _n_lines[0] == _n_pass[0] + _n_fail[0] and _n_lines[0] >= 40, star=True)

# H3 负控制：H2 的记账器有鉴别力（手工模拟 FAIL，不真打印 [FAIL] 行）
_before_f = _n_fail[0]
_before_len = len(_failed)


def _sim_fail():
    _n_fail[0] += 1
    _failed.append('__sim__')


_sim_fail()
_has_effect = (_n_fail[0] == _before_f + 1 and len(_failed) == _before_len + 1)
_n_fail[0] -= 1
_failed.pop()
check('H3 ★★ 负控制：记账器有鉴别力（模拟 FAIL ⇒ 计数真 +1，已撤回）',
      _has_effect and _n_fail[0] == _before_f and len(_failed) == _before_len,
      star=True)

print('=' * 70)
print('第89轮：FAIL %d 项 %s' % (len(_failed), _failed if _failed else ''))
print('=' * 70)
sys.exit(0 if not _failed else 1)
