# -*- coding: utf-8 -*-
u"""第113轮n回归锁：**「你还记得这些地方」接上了** —— 1 跳邻居来自原作门连接图。

用户口径（2026-10-26 逐字，第113轮j 引过、这一轮才落地）
--------------------------------------------------------
「对了，方便的话可以训练一下他们**寻路**的能力（**包括地方偏好，特定事件时去的
地方**等等）」

前几轮各管一块
--------------
· 113k = 「特定事件时去的地方」（吃饭/活动/休息/办事 ⇒ 建议去哪一家）
· 113j = 【你现在在哪】【你的归属地】—— 坐标事实
· **113n（本套件）= 【你还记得这些地方】**
  ★ 这一块从 113j 起就写着"预留，当前调用方没传" —— `place_hint(near=)`
    有这个形参、有文案、有判据（113j C5/C6），但产品**一次都没传过**。
    这正是本项目最贵的坑：形状齐了、没人接线、指标全绿。

真源
----
`_room_graph.json`（第42轮反汇编取证 + 第105轮补 OneShot 章，共 1,202 条边）。
**不是**我们编的"附近"，也**不按落点坐标算近** —— 房间坐标是各自的局部系，
跨房比距离在原理上不成立（第44轮已证伪，见 `shortest_path` 的注释）。

本套件守什么
------------
A `scene_pathfind.neighbor_rooms()` 纯函数：只取 **1 跳且方向正确**、自环丢掉、
   **升序去重**（确定性）、坏输入返 `[]` 不抛。
B `_npc_place_near()` 真跑（**AST 从 `main.py` 抽出产品代码**，不是复刻）：
   标签取**原作房间 id 整形后的英文**，不是 `_scene_place_label()` ——
   后者对 `name_derived=True` 的场景只吐区名，5 个邻居全叫「家乡」（实测）。
   过滤调试/演出区与容器区；无图章节（ut / uty / outertale / desktop）返 `[]` 不崩。
C `place_hint` 的 near 文案：说得出「就在这一带，走过去能到」——
   只说"我记得有这些地方"，模型不会拿它当路线依据。
D AST 接线：`_npc_life_blocks` 里 `place_hint` **真的**带 `near=`，值真的是
   `self._npc_place_near(...)`；且那条链真的走到 `load_room_graph()`。
   ★ 一律 AST，禁纯文本扫 —— "提到某名字"类恒真判据已发作过五次。
E 破坏性负控制：把 `neighbor_rooms` 打回 `[]`、把 `place_hint` 的 near 分支拆掉，
   对应判据必须**真的变红**（证明通过不是恒真）。
F 本轮脚本自检（语法 / 无 BOM / 行尾不混 / 无恒真判据 / 记账守恒）。

稳定性（G2 要逐字节比对）
------------------------
★ **不打印随数据规模变化的绝对数**（场景数 / 能产出 near 的场景数都会随素材变），
  只打布尔与失败条数；覆盖率用**只增不减**的下界，失败时才回显实际值。
★ 抽样全部**写死 sid**，不用 `sorted()[0]`。

零网络、零 Qt、零 E 盘依赖。
"""
import ast
import io
import json
import logging
import os
import sys
import textwrap

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))

PET = os.path.join(ROOT, 'ralsei_pet')
MAIN = os.path.join(PET, 'src', 'main.py')
IDX = os.path.join(PET, 'assets', 'scenes', '_index.json')
REG = os.path.join(PET, 'assets', 'npc', '_registry.json')

sys.path.insert(0, os.path.join(PET, 'modules'))
import npc_life as L                                        # noqa: E402
import scene_pathfind as SP                                 # noqa: E402

logging.getLogger('ralsei_pet.npc_placement').setLevel(logging.ERROR)

_failed = []
_n_pass = 0
_n_fail = 0
_n_check = 0


def check(desc, cond, detail=''):
    global _n_pass, _n_fail, _n_check
    _n_check += 1
    if cond:
        _n_pass += 1
        print('[PASS] %s%s' % (desc, ('    ' + detail) if detail else ''))
    else:
        _n_fail += 1
        _failed.append(desc)
        print('[FAIL] %s%s' % (desc, ('    ' + detail) if detail else ''))


# ---------------------------------------------------------------- 抽取工具
def _method_src(src, name, indent_ok=True):
    """从 `main.py` 取出类方法源码（dedent 后可直接 exec）。找不到返 (None, None)。"""
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            for fn in node.body:
                if isinstance(fn, ast.FunctionDef) and fn.name == name:
                    return textwrap.dedent(ast.get_source_segment(src, fn)), fn
    return None, None


def _index_tables():
    """与 `main._scene_label_map()` **同口径**读索引（5 元组 + 房间下标两张表）。

    ★ 桩比产品旧 = 假红（第107轮踩过）。产品那边元组是 5 位，这里也必须是 5 位。
    """
    idx = json.loads(io.open(IDX, encoding='utf-8').read())
    labels, room_of, room_by = {}, {}, {}
    for _cid, ch in (idx.get('chapters') or {}).items():
        ch_name = str((ch or {}).get('name') or '')
        for _aid, ar in ((ch or {}).get('areas') or {}).items():
            area_name = str((ar or {}).get('name') or '')
            for sid, sc in ((ar or {}).get('scenes') or {}).items():
                sc = sc or {}
                labels[str(sid)] = (ch_name, area_name,
                                    str(sc.get('name') or ''),
                                    bool(sc.get('name_derived')),
                                    str(sc.get('name_raw') or ''))
                rid = sc.get('original_room_id')
                if isinstance(rid, int):
                    room_of[str(sid)] = rid
                    room_by.setdefault((str(_cid), rid), str(sid))
    return labels, room_of, room_by


def _proper_set():
    """与产品 `_place_proper()` 同口径：`npc_registry` 每个 id 的末段（小写）。"""
    out = set()
    try:
        reg = json.loads(io.open(REG, encoding='utf-8').read())
        for row in (reg.get('npcs') or []):
            seg = str((row or {}).get('id') or '').rsplit('.', 1)[-1].strip().lower()
            if seg:
                out.add(seg)
    except Exception as _e:                                 # noqa: BLE001
        print('  registry 读取失败（人名集合按空处理）：%s' % _e)
    return out


_SRC = io.open(MAIN, encoding='utf-8', newline='').read()
_LABELS, _ROOM_OF, _ROOM_BY = _index_tables()
_PROPER = _proper_set()

_NEAR_CODE, _NEAR_FN = _method_src(_SRC, '_npc_place_near')
_EDGES_CODE, _EDGES_FN = _method_src(_SRC, '_room_graph_edges')


class _Stub(object):
    """只给**数据**，不给被测算法：`_npc_place_near` / `_room_graph_edges`
    是 AST 抽出来的产品代码，跑到这里来取索引和人名集合。"""

    npc_life_mod = L
    scene_pathfind_mod = SP

    def _scene_label_map(self):
        return _LABELS

    def _scene_rooms(self):
        return _ROOM_OF

    def _scene_by_room(self):
        return _ROOM_BY

    def _place_proper(self):
        return _PROPER


_ns = {'npc_life_mod': L, 'scene_pathfind_mod': SP,
       '_log': logging.getLogger('check113n')}
for _name, _code in (('_room_graph_edges', _EDGES_CODE),
                     ('_npc_place_near', _NEAR_CODE)):
    if _code:
        exec(compile(_code, '<%s>' % _name, 'exec'), _ns)
for _name in ('_room_graph_edges', '_npc_place_near'):
    if _name in _ns:
        setattr(_Stub, _name, _ns[_name])

_ST = _Stub()
_EDGES = _ns['_room_graph_edges'](_ST) if '_room_graph_edges' in _ns else {}


def near(sid, limit=3):
    fn = _ns.get('_npc_place_near')
    return fn(_ST, sid, limit) if fn else ['<no-method>']


# ================================================================ A
print('--- A `neighbor_rooms` 纯函数 ---')

check('A0 `scene_pathfind.neighbor_rooms` 存在', callable(getattr(SP, 'neighbor_rooms', None)))

# ★ 夹具要**保真**：边表形状与 `load_room_graph()` 的输出一致（src/dst 都是 int）。
_G = {'ch1': [{'src': 2, 'dst': 3}, {'src': 3, 'dst': 2},
              {'src': 3, 'dst': 5}, {'src': 5, 'dst': 2},
              {'src': 5, 'dst': 5}]}

check('A1 正例：房间 2 的邻居 = [3]（只认 `src==2` 而 5→2 是**反向**边，不算）',
      SP.neighbor_rooms(_G, 'ch1', 2) == [3],
      '%r' % (SP.neighbor_rooms(_G, 'ch1', 2),))
check('A2 自环丢掉（`5→5` 不许出现在 5 的邻居里）',
      SP.neighbor_rooms(_G, 'ch1', 5) == [2],
      '%r' % (SP.neighbor_rooms(_G, 'ch1', 5),))

# ★ 确定性：把边表**倒序**，结果必须一样（升序去重，不按边表顺序）
_G2 = {'ch1': list(reversed(_G['ch1']))}
check('A3 边表倒序 ⇒ 结果逐值相同（不按边表顺序出标签，否则换一份图就假 DIFF）',
      SP.neighbor_rooms(_G2, 'ch1', 3) == SP.neighbor_rooms(_G, 'ch1', 3) == [2, 5],
      '%r vs %r' % (SP.neighbor_rooms(_G2, 'ch1', 3), SP.neighbor_rooms(_G, 'ch1', 3)))

check('A4 limit 生效且取**小的那几个**（升序后截断）',
      SP.neighbor_rooms(_G, 'ch1', 3, limit=1) == [2],
      '%r' % (SP.neighbor_rooms(_G, 'ch1', 3, limit=1),))

_bad = [
    SP.neighbor_rooms(None, 'ch1', 2),
    SP.neighbor_rooms({'ch1': 'not-a-list'}, 'ch1', 2),
    SP.neighbor_rooms(_G, 'ch9', 2),
    SP.neighbor_rooms(_G, 'ch1', 'x'),
    SP.neighbor_rooms(_G, 'ch1', None),
    SP.neighbor_rooms({}, 'ch1', 2),
]
check('A5 坏输入一律 `[]` 且不抛（图不是 dict / 边表不是 list / 章不存在 / 房间非 int）',
      all(x == [] for x in _bad), '%r' % (_bad,))

_c_yes = (SP.neighbor_rooms([], 'ch1', 2) == [])
check('A6 负控制：空图 ⇒ 空（不是"就近凑一个"）', _c_yes)


# ================================================================ B
print()
print('--- B 真图 + `_npc_place_near` 真跑（产品代码，AST 抽出）---')

check('B0 抽到产品里的 `_npc_place_near`（抽不到 ⇒ 后面全无意义）',
      callable(_ns.get('_npc_place_near')))

_g = SP.load_room_graph()
_n_edges = _g.get('n_edges') if isinstance(_g, dict) else None
# ★ 房间图是**运行时数据**（`room_graph_path()` 定位置）。它读不到时整块会静默不产
#   —— 那正是本套件要挡住的事，所以这里必须**报红**，不能 SKIP。
check('B1 原作门连接图可读（读不到 ⇒ 邻居块会静默消失，必须报红）',
      bool(isinstance(_g, dict) and _g.get('ok')),
      '' if (isinstance(_g, dict) and _g.get('ok'))
      else str((_g or {}).get('error') if isinstance(_g, dict) else _g))
check('B2 图里六章齐全（ch1~ch5 + oneshot）',
      isinstance(_EDGES, dict)
      and set(('ch1', 'ch2', 'ch3', 'ch4', 'ch5', 'oneshot')) <= set(_EDGES),
      '%r' % (sorted(_EDGES) if isinstance(_EDGES, dict) else None,))

# ★ 写死 sid 抽样：`diner` 只有 `town_mid` 一扇门（人眼核过原作：餐厅在镇中心西侧）
check('B3 `ch1.hometown.diner` ⇒ 邻居含 `Town Mid`（原作里餐厅就在那儿）',
      'Town Mid' in near('ch1.hometown.diner'),
      '%r' % (near('ch1.hometown.diner'),))

_nt = near('ch1.hometown.town_north')
check('B4 `town_north` 有多个邻居，且每条都非空、互不相同',
      len(_nt) >= 2 and all(_nt) and len(set(x.casefold() for x in _nt)) == len(_nt),
      '%r' % (_nt,))

check('B5 邻居里**不含自己**（`town_north` 的列表里不许出现 `Town North`）',
      not any(x.casefold() == 'town north' for x in _nt), '%r' % (_nt,))

check('B6 `limit` 真的生效（`limit=1` 只给 1 条）',
      len(near('ch1.hometown.town_north', limit=1)) == 1,
      '%r' % (near('ch1.hometown.town_north', limit=1),))

# ★ 负控制：调试 / 演出区不是"地方"，`ch2.system` 的三个调试房不许被报成邻居
check('B7 调试/演出区被剔掉（`shaun_puzzle`（ch2.system）⇒ 空）',
      near('ch2.system.shaun_puzzle') == [],
      '%r' % (near('ch2.system.shaun_puzzle'),))

# ★ 无图章节：章节 id 不在图里 ⇒ `[]`，且**不抛**
# ★★ 第126轮：`outertale` **从这份名单里移出去了** —— 它现在**有图了**
#   （`chapters.outertale` 209 条边）。留着它就成了"判据在描述过去的时相"，
#   而下面的 B8b 正是那个新事实的正控制（有图 ⇒ 必须真有邻居）。
_no_graph = ['ut.rooms.room_town', 'uty.rooms.rm_steamworks_29', 'desktop']
check('B8 无连接图的章（ut / uty / desktop）⇒ `[]`，不抛',
      all(near(s) == [] for s in _no_graph),
      '%r' % ([(s, near(s)) for s in _no_graph if near(s)],))
check('B8b ★★ 第126轮正控制：有图的章（outertale）必须**真有**邻居'
      '（此前它是"无图章"，B8 把它和 ut 当同一类 —— 加了图就该翻面）',
      len(near('outertale.starton.s_beddinng')) >= 1,
      '%r' % (near('outertale.starton.s_beddinng'),))

check('B9 空 sid / None ⇒ `[]`（不产"附近有某个地方"这种废话）',
      near('') == [] and near(None) == [], '%r' % (near(''),))

check('B10 `limit<=0` ⇒ `[]`（负控制：别把"不限"当"0 条"的漏洞）',
      near('ch1.hometown.diner', limit=0) == [], '%r' % (near('ch1.hometown.diner', 0),))

# ★ 确定性：连调两次逐值相同（提示词不许自己漂）
check('B11 确定性：同一场景连调两次结果逐值相同',
      near('ch2.hometown.town_mid') == near('ch2.hometown.town_mid'),
      '%r' % (near('ch2.hometown.town_mid'),))

# ★ 全量普查：空标签 / 内部令牌 / 重复
_LEAK = ('_', 'rm ', 'room ', 'dw ', 'lw ', 'None', 'NoneType')
_empty_lbl, _leak_lbl, _dup, _n_has, _n_tot = [], [], [], 0, 0
for _sid in _LABELS:
    _n_tot += 1
    _got = near(_sid)
    if not _got:
        continue
    _n_has += 1
    for _w in _got:
        if not str(_w or '').strip():
            _empty_lbl.append(_sid)
        low = str(_w).lower()
        for _t in _LEAK:
            if _t in low:
                _leak_lbl.append((_sid, _w))
                break
    if len({x.casefold() for x in _got}) != len(_got):
        _dup.append((_sid, _got))

check('B12 全量：有邻居的场景，标签**零空串**', not _empty_lbl, '%r' % (_empty_lbl[:3],))
check('B13 全量：标签里**零内部结构**（下划线 / `rm ` / `room ` / `None`）',
      not _leak_lbl, '%r' % (_leak_lbl[:3],))
check('B14 全量：同一个场景的邻居**不重复**（不分大小写）', not _dup, '%r' % (_dup[:3],))

# ★★ 覆盖率用**只增不减**的下界：素材/图只会越补越全，掉下去就是真回归。
#   ⚠️ 绝不把实际值打进 detail —— 那会让"加了素材"变成假 DIFF。
_COVER_MIN = 500
_cov_ok = _n_has >= _COVER_MIN
check('B15 全量：能产出邻居的场景数 ≥ %d（只增不减的下界）' % _COVER_MIN,
      _cov_ok, '' if _cov_ok else '实际=%d/%d' % (_n_has, _n_tot))


# ================================================================ C
print()
print('--- C `place_hint` 的 near 文案 ---')

_h = L.place_hint(here='家乡', near=['Diner', 'Library'])
check('C1 near 非空 ⇒ 产【你还记得这些地方】并列出来',
      '【你还记得这些地方】' in _h and 'Diner' in _h and 'Library' in _h,
      '%r' % _h[:60])
check('C2 文案要说明**可达**（"走过去能到"）—— 只说"记得"模型不会当路线依据',
      '走过去能到' in _h, '%r' % _h[-40:])

_h2 = L.place_hint(here='家乡', near=())
check('C3 负控制：near 为空 ⇒ **不产**该块（不写"你还记得这些地方：。"）',
      '【你还记得这些地方】' not in _h2, '%r' % _h2[:40])

_h3 = L.place_hint(here='家乡', near=['Diner', '', None, 'Library'])
check('C4 near 里的空值 / None 被滤掉（不产 `Diner、、Library`）',
      '、、' not in _h3 and 'None' not in _h3 and 'Diner' in _h3 and 'Library' in _h3,
      '%r' % _h3[:70])

_h4 = L.place_hint(near=['Diner'])
check('C5 只有 near 时也成块（三个都空才返 `\'\'`）',
      _h4.startswith('【你还记得这些地方】'), '%r' % _h4[:40])


# ================================================================ D
print()
print('--- D AST 接线（禁纯文本扫）---')

# ★ 从真实数据里取出 `_npc_life_blocks` 的 AST
_BLK_CODE, _BLK = _method_src(_SRC, '_npc_life_blocks')
check('D0 `_npc_life_blocks` 存在', _BLK is not None)

_near_kw = None
_has_call = False
if _BLK is not None:
    for _n in ast.walk(_BLK):
        if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Attribute) \
                and _n.func.attr == 'place_hint':
            _has_call = True
            for _kw in _n.keywords:
                if _kw.arg == 'near':
                    _near_kw = _kw.value

check('D1 `_npc_life_blocks` 里**真的**调了 `place_hint`', _has_call)
check('D2 那次调用**带 `near=` 关键字**（不带 ⇒ 又回到"有形状没人接线"）',
      _near_kw is not None)

# ★ 值必须是 `self._npc_place_near(...)` 的**调用**，不是常量 / 空列表。
#   ★ 允许**局部变量中转**（`near_txt = self._npc_place_near(sid)` 再传）——
#     那不是"没接线"，是为了同一份结果既进条件又进调用，少算一次。
#     ⇒ 判据走**一步数据流**：先看直接调用，再看这个 Name 是不是被那样赋过值。
#     （同 check107 的变异 M13 教训：只认"直接调用"会把正确写法判红。）
def _is_near_call(node):
    if not isinstance(node, ast.Call):
        return False
    f = node.func
    return (isinstance(f, ast.Attribute) and f.attr == '_npc_place_near'
            and isinstance(f.value, ast.Name) and f.value.id == 'self')


def _assigned_from_near(fn, name):
    """`name = self._npc_place_near(...)` 这种赋值在这个方法体里存在吗？"""
    if fn is None or not name:
        return False
    for n in ast.walk(fn):
        if not isinstance(n, ast.Assign):
            continue
        if not any(isinstance(t, ast.Name) and t.id == name for t in n.targets):
            continue
        if _is_near_call(n.value):
            return True
    return False


_near_val_ok = _is_near_call(_near_kw)
if not _near_val_ok and isinstance(_near_kw, ast.Name):
    _near_val_ok = _assigned_from_near(_BLK, _near_kw.id)
check('D3 `near` 的值最终来自 `self._npc_place_near(...)`（AST 判调用/一步数据流，非字面量）',
      _near_val_ok, ast.dump(_near_kw)[:60] if _near_kw is not None else 'None')

_near_calls_sp = []
if _NEAR_FN is not None:
    for _n in ast.walk(_NEAR_FN):
        if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Attribute):
            _base = _n.func.value
            _bn = (_base.id if isinstance(_base, ast.Name)
                   else (_base.attr if isinstance(_base, ast.Attribute) else ''))
            _near_calls_sp.append('%s.%s' % (_bn, _n.func.attr))
check('D4 `_npc_place_near` 真走 `scene_pathfind_mod.neighbor_rooms`（不自己重算图）',
      'scene_pathfind_mod.neighbor_rooms' in _near_calls_sp,
      '%r' % (_near_calls_sp[:6],))

_edges_calls = []
if _EDGES_FN is not None:
    for _n in ast.walk(_EDGES_FN):
        if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Attribute):
            _base = _n.func.value
            _bn = (_base.id if isinstance(_base, ast.Name)
                   else (_base.attr if isinstance(_base, ast.Attribute) else ''))
            _edges_calls.append('%s.%s' % (_bn, _n.func.attr))
check('D5 `_room_graph_edges` 真走 `scene_pathfind_mod.load_room_graph`（路径只有一处真源）',
      'scene_pathfind_mod.load_room_graph' in _edges_calls,
      '%r' % (_edges_calls[:6],))

# ★ import 本身也走 AST：字符串扫会被注释里的同名提及骗过去（已五次）
_IMP_OK = False
_tree = ast.parse(_SRC)
for _n in ast.walk(_tree):
    if isinstance(_n, ast.ImportFrom) and _n.module == 'modules':
        for _a in _n.names:
            if _a.name == 'scene_pathfind' and _a.asname == 'scene_pathfind_mod':
                _IMP_OK = True
check('D6 `from modules import scene_pathfind as scene_pathfind_mod`（AST ImportFrom）',
      _IMP_OK)


# ================================================================ E
print()
print('--- E 破坏性负控制（通过不是恒真）---')

_orig_nb = getattr(SP, 'neighbor_rooms', None)
_mut_near = None
try:
    SP.neighbor_rooms = lambda *a, **k: []
    _mut_near = near('ch1.hometown.diner')
finally:
    if _orig_nb is not None:
        SP.neighbor_rooms = _orig_nb
check('E1 把 `neighbor_rooms` 打回 `[]` ⇒ 邻居必须消失（B3 不是恒真）',
      _mut_near == [], '%r' % (_mut_near,))

_orig_ph = getattr(L, 'place_hint', None)
_mut_ph = None
try:
    def _ph_no_near(here='', home='', near=(), at_home=False):
        # 只拆 near 这一支，其余照旧 —— "拆干净"才复现，别一次拆所有防线
        return _orig_ph(here=here, home=home, near=(), at_home=at_home)
    L.place_hint = _ph_no_near
    _mut_ph = L.place_hint(here='家乡', near=['Diner', 'Library'])
finally:
    if _orig_ph is not None:
        L.place_hint = _orig_ph
check('E2 只拆 near 分支（其余不动）⇒ C1/C2 的判据必须变红',
      bool(_orig_ph) and _mut_ph is not None
      and '【你还记得这些地方】' not in _mut_ph and '走过去能到' not in _mut_ph,
      '%r' % (_mut_ph[:40] if _mut_ph else None,))


# ================================================================ F
print()
print('--- F 本套件自检 ---')

_self = io.open(os.path.abspath(__file__), encoding='utf-8', newline='').read()
try:
    ast.parse(_self)
    _syn = True
except SyntaxError:
    _syn = False
check('F1 本文件语法可解析（`ast.parse`，不产 .pyc）', _syn)
check('F2 无 BOM / 无 U+FFFD', not _self.startswith(u'\ufeff') and u'\ufffd' not in _self)

_b = io.open(os.path.abspath(__file__), 'rb').read()
check('F3 行尾不混（LF 文件里不许出现 CRLF）',
      b'\r\n' not in _b, 'CRLF=%d' % _b.count(b'\r\n'))

# ★★ 恒真判据体检：扫 `check(...)` 的**第二个实参**是不是常量 True/非空字面量。
#   ★ 为什么看 `args[1]` 而不是 `args[0]`：`args[0]` 是描述串，永远 truthy。
_triv = []
for _n in ast.walk(ast.parse(_self)):
    if (isinstance(_n, ast.Call) and isinstance(_n.func, ast.Name)
            and _n.func.id == 'check' and len(_n.args) >= 2):
        _a = _n.args[1]
        if isinstance(_a, ast.Constant) and bool(_a.value):
            _triv.append(_n.lineno)
check('F4 无恒真判据（`check(desc, True)` 这种"看着在守其实没守"）', not _triv,
      '行=%r' % (_triv,))

# ★ 正控制：上面那个扫描器**真的能**抓到一条恒真判据（否则 F4 自己就是恒真）
_probe_src = 'def check(d, c):\n    pass\ncheck("x", True)\ncheck("y", 1 == 1)\n'
_hit = []
for _n in ast.walk(ast.parse(_probe_src)):
    if (isinstance(_n, ast.Call) and isinstance(_n.func, ast.Name)
            and _n.func.id == 'check' and len(_n.args) >= 2):
        _a = _n.args[1]
        if isinstance(_a, ast.Constant) and bool(_a.value):
            _hit.append(_n.lineno)
check('F5 正控制：扫描器能抓到夹具里的恒真判据（且**不**误报 `1 == 1` 这种比较式）',
      _hit == [3], '%r' % (_hit,))


# ================================================================ G
print()
print('--- G 端到端：整段 prompt 里**真的**出现那块（不只是方法返回了列表）---')

_LBL_CODE, _LBL_FN = _method_src(_SRC, '_scene_place_label')
_BLK_CODE, _BLK_FN = _method_src(_SRC, '_npc_life_blocks')
check('G0 抽到 `_scene_place_label` 与 `_npc_life_blocks`（抽不到 ⇒ 下面全是假绿）',
      bool(_LBL_CODE and _BLK_CODE))


class _Place(object):
    def __init__(self, home):
        self._home = home

    def home_of(self, npc_id):
        return self._home


class _BlockStub(_Stub):
    """只给数据访问器；`_scene_place_label` / `_npc_place_near` /
    `_npc_life_blocks` 都是 AST 抽出来的**产品代码**。"""

    npc_bonds = None

    def __init__(self, sid, home):
        self._sid = sid
        self.npc_placement = _Place(home)

    def _npc_scene_id(self):
        return self._sid

    def _npc_scene_text(self):
        return ''

    def _npc_life_ids(self):
        return []

    def _npc_relative_positions(self, *a, **k):
        return {}

    def _npc_display_label(self, nid):
        return ''


_blocks = None
if _LBL_CODE and _BLK_CODE:
    _bns = {'npc_life_mod': L, 'scene_pathfind_mod': SP,
            '_log': logging.getLogger('check113n')}
    exec(compile(_LBL_CODE, '<extract _scene_place_label>', 'exec'), _bns)
    exec(compile(_BLK_CODE, '<extract _npc_life_blocks>', 'exec'), _bns)
    for _n in ('_scene_place_label', '_npc_place_near', '_room_graph_edges'):
        if _n in _bns:
            setattr(_BlockStub, _n, _bns[_n])
    _blocks = _bns.get('_npc_life_blocks')

_prompt = (_blocks(_BlockStub('ch1.hometown.diner', 'ch1.hometown.diner'), 'ralsei')
           if _blocks else '')
check('G1 端到端：`ch1.hometown.diner` 的整段 prompt 里**真有**【你还记得这些地方】，'
      '且含 `Town Mid`',
      '【你还记得这些地方】' in _prompt and 'Town Mid' in _prompt,
      '%r' % (_prompt[:120],))

_p2 = (_blocks(_BlockStub('ut.rooms.room_town', 'ut.rooms.room_town'), 'ralsei')
       if _blocks else '')
check('G2 负控制：无连接图的章（`ut`）整段 prompt **不含**该块'
      '（不许为了"看起来在做"硬凑）',
      bool(_p2) and '【你还记得这些地方】' not in _p2, '%r' % (_p2[:80],))

_p3 = ''
if _blocks:
    _keep = getattr(SP, 'neighbor_rooms', None)
    try:
        SP.neighbor_rooms = lambda *a, **k: []
        _p3 = _blocks(_BlockStub('ch1.hometown.diner', 'ch1.hometown.diner'), 'ralsei')
    finally:
        if _keep is not None:
            SP.neighbor_rooms = _keep
check('G3 破坏性负控制：把 `neighbor_rooms` 打回 `[]` ⇒ 整段 prompt 里该块消失'
      '（G1 不是恒真）',
      bool(_p3) and '【你还记得这些地方】' not in _p3, '%r' % (_p3[:80],))


# ================================================================ 汇总
print()
print('=' * 74)
print('合计：PASS=%d FAIL=%d' % (_n_pass, _n_fail))
if _failed:
    print('失败项：')
    for d in _failed:
        print('  - %s' % d)
print('=' * 74)
sys.exit(0 if _n_fail == 0 else 1)
