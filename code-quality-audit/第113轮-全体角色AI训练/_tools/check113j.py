# -*- coding: utf-8 -*-
u"""第113轮j回归锁：**空间认知**（NPC 知道自己在哪 / 归属地在哪 / 记得哪些地方）。

用户口径（2026-10-26 逐字）
--------------------------
「对了，方便的话可以训练一下他们寻路的能力（**包括地方偏好，特定事件时去的地方**等等）」

怎么理解
--------
`npc_roam.step()` 早就是**确定性权重决策**（`npc_intent.action_weights` + 场景特质调权），
模型**完全不参与**寻路。所以"训练寻路"如果理解成"让 7B 做路径搜索"，方向就错了。
真正的缺口是：prompt 里**只有「这地方什么样」没有「你在哪儿」** ——
`trait_hint()` 给的是气氛，角色根本不知道自己在城堡镇还是荒野。

⇒ 本层给的是**坐标事实**：
  · 【你现在在哪】= 当前场景的可读标签
  · 【你的归属地】= `npc_placement.home_of()`（**与"回家/就寝"同一个出口**）
  · 【你还记得这些地方】= 邻近/相关地点（预留，当前调用方没传）

本套件守什么
------------
A `_scene_place_label` 的**输出质量**：真名要留（`FINALE`）、内部 id 要剥
  （`rm_dalvExit` → `dalvExit`）、我们的目录结构一律不露（「全部房间」「未分区」）。
  ★ 用 AST 从 `main.py` 里**取出方法体**再 exec —— 测的是产品那段代码本身，
    不是复刻版（复刻版会和产品一起漂）。

B **全量普查**：2166 个场景一个不落。6 个样本全绿说明不了问题 ——
  第113轮j 就是这么抓到 26 条容器名漏判、4 条混合大小写 id 泄漏的。

C `place_hint` 块行为，其中 **C4「在家不许说想回去」是真错误防线**：
  在自己家里还说"累了会想回去"，模型会答"那我该回家了"。

D AST 接线：`_npc_life_blocks` 里**真的调**了，且排在 `scene_traits` **之前**
  （顺序反了模型会把地名当形容气氛的词），且 `at_home` 是**比较式**不是硬编码。

E 真实数据验收：84 条 `_placement.json` 实际产出的块（桩测不出数据的分布）。

F 方法级端到端：把产品里的 `_npc_life_blocks` **整段**抽出来挂桩跑。

稳定性（G2 要逐字节比对）
------------------------
★ **不打印随数据规模变化的绝对数**（场景数 / NPC 数会随素材新增而变 ⇒ 假 DIFF），
  只打布尔与失败条数；抽样用**写死的 sid**，不用 `sorted()[0]`。

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

sys.path.insert(0, os.path.join(PET, 'modules'))
import npc_life as L                                        # noqa: E402
import npc_placement as P                                   # noqa: E402

# 真实数据缺文件时会往 stderr 打 WARNING ⇒ 污染基线；本套件自己判覆盖，不需要它。
logging.getLogger('ralsei_pet.npc_placement').setLevel(logging.ERROR)

_failed = []
_n_pass = 0
_n_fail = 0


def check(desc, cond, detail=''):
    global _n_pass, _n_fail
    if cond:
        _n_pass += 1
        print('[PASS] %s%s' % (desc, ('    ' + detail) if detail else ''))
    else:
        _n_fail += 1
        _failed.append(desc)
        print('[FAIL] %s%s' % (desc, ('    ' + detail) if detail else ''))


# ---------------------------------------------------------------- 抽取工具
def _method_src(src, name):
    """从 `main.py` 取出类方法源码（dedent 后可直接 exec）。找不到返 None。"""
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            for fn in node.body:
                if isinstance(fn, ast.FunctionDef) and fn.name == name:
                    return textwrap.dedent(ast.get_source_segment(src, fn)), fn
    return None, None


def _scene_index():
    """与 `_scene_label_map()` **同口径**读索引（5 元组，字段顺序必须一致）。

    ★ 桩比产品旧 = 假红（第107轮踩过）。产品改成 5 元组后这里也必须同步，
      否则 `ValueError` 会被当成产品坏了。
    """
    idx = json.loads(io.open(IDX, encoding='utf-8').read())
    m = {}
    for _cid, ch in (idx.get('chapters') or {}).items():
        ch_name = str((ch or {}).get('name') or '')
        for _aid, ar in ((ch or {}).get('areas') or {}).items():
            area_name = str((ar or {}).get('name') or '')
            for scid, sc in ((ar or {}).get('scenes') or {}).items():
                sc = sc or {}
                m[str(scid)] = (ch_name, area_name,
                                str(sc.get('name') or ''),
                                bool(sc.get('name_derived')),
                                str(sc.get('name_raw') or ''))
    return m


_SRC = io.open(MAIN, encoding='utf-8', newline='').read()
_CODE, _FN = _method_src(_SRC, '_scene_place_label')
_IDX = _scene_index()


class _LabelStub(object):
    npc_life_mod = L

    def _scene_label_map(self):
        return _IDX


_ns = {'npc_life_mod': L}
if _CODE:
    exec(compile(_CODE, '<extracted _scene_place_label>', 'exec'), _ns)
_label_fn = _ns.get('_scene_place_label')


def label(sid):
    return _label_fn(_LabelStub(), sid) if _label_fn else '<no-method>'


# ================================================================ A
print('--- A `_scene_place_label` 输出质量 ---')

check('A0 从产品源码里取到 `_scene_place_label`（取不到 ⇒ 后面全无意义）',
      _label_fn is not None)

# ★ 用例固定写死：跟着数据规模漂会制造假 DIFF
_CASES = [
    ('ch1.castle_town.castle_town', '城堡镇'),
    ('uty.rooms.rm_steamworks_29', 'steamworks 29'),
    ('oneshot.mainline.FINALE', 'FINALE'),
    ('ch2.ralsei_room.dw_ralsei_castle_front', '拉尔赛的城堡'),
    ('desktop', '桌面'),
]
_miss = [(s, need, label(s)) for s, need in _CASES if need not in label(s)]
check('A1 有真名的场景保留真名（含 `FINALE` —— 大写真名不许被当内部 id 剥掉）',
      not _miss, '缺=%r' % (_miss[:2],))

# ★ 这条是"修一条丢一条"的防线：j3 曾为了消除三段把 `FINALE` 一起丢了
check('A2 `oneshot.mainline.FINALE` 必须**同时**有区名和末级名，且不用 ` · ` 连（避免三段）',
      ('家/塔/终局' in label('oneshot.mainline.FINALE')
       and 'FINALE' in label('oneshot.mainline.FINALE')
       and L.PLACE_SEP not in label('oneshot.mainline.FINALE').rsplit('（', 1)[0]
       .split('家/塔/终局')[-1]),
      '%r' % label('oneshot.mainline.FINALE'))

check('A3 空串 / None ⇒ `\'\'`（负控制：不产"你在未知地点"这种废话）',
      label('') == '' and label(None) == '')

check('A4 章名与位置同名时不加括注（`桌面（桌面）` 读起来像结巴）',
      '桌面（桌面）' not in label('desktop'))


# ================================================================ B
print()
print('--- B 全量普查（一个场景都不落）---')

_LEAK_TOK = ('rm_', 'room_', '全部房间', '未分区', 'unzoned', 'unknown', '.rooms.')

_empty, _leak, _three, _paren = [], [], [], []
for _sid in _IDX:
    _got = label(_sid)
    if not _got:
        _empty.append(_sid)
        continue
    for _t in _LEAK_TOK:
        if _t in _got:
            _leak.append((_sid, _t, _got))
            break
    # ★ 只数**主体**（剥掉末尾章名括注）。章名自己是 `第一章 · 黑暗世界`，带中点 ——
    #   第一版直接对整串数 ` · `，谎报 320 条。**判据也是被测物**。
    _body = _got[:(_got.rindex('（') if _got.endswith('）') and '（' in _got else len(_got))]
    if _body.count(L.PLACE_SEP) > 1:
        _three.append((_sid, _got))
    if '（（' in _got or '）（' in _got or _got.count('（') != _got.count('）'):
        _paren.append((_sid, _got))

check('B1 每个场景都能说出地名（空标签 0 条）', not _empty, '空=%r' % (_empty[:3],))
check('B2 输出里**零**内部结构（`rm_`/`room_`/「全部房间」/「未分区」）',
      not _leak, '泄漏=%r' % (_leak[:3],))
check('B3 拼接主体不许出现三段（` · ` 在主体里最多 1 次）',
      not _three, '三段=%r' % (_three[:3],))
check('B4 括号成对、不许 `（（` / `）（`', not _paren, '%r' % (_paren[:3],))


# ================================================================ C
print()
print('--- C `place_hint` 块行为 ---')

check('C1 三块全空 ⇒ `\'\'`（不产空块）', L.place_hint() == '')

_h = L.place_hint(here='城堡镇')
check('C2 只有「在哪」时不硬凑「归属地」',
      '【你现在在哪】' in _h and '【你的归属地】' not in _h)

_h = L.place_hint(here='荒野', home='城堡镇', at_home=False)
check('C3 不在家 ⇒ 说「想回去」', '想回去' in _h and '就是这儿' not in _h, '%r' % _h[:40])

# ★★ 真错误防线：在家还说"想回去"，模型会答"那我该回家了" —— 而它就在家
_h = L.place_hint(here='城堡镇', home='城堡镇', at_home=True)
check('C4 **在家** ⇒ 说「就是这儿」，且**不许**说「想回去」',
      '就是这儿' in _h and '想回去' not in _h, '%r' % _h[:40])

_h = L.place_hint(here='甲地', home='乙地', near=['丙地', '丁地'])
check('C5 三块顺序 在哪 → 归属地 → 记得（位置事实先于它们的补充）',
      _h.find('【你现在在哪】') < _h.find('【你的归属地】')
      < _h.find('【你还记得这些地方】'))

_h = L.place_hint(here='甲地', near=['', None, '丙地'])
check('C6 near 里的空值/None 被滤掉（不产 `、、`）',
      '、、' not in _h and '、。' not in _h and '丙地' in _h)


# ================================================================ D
print()
print('--- D AST 接线 ---')

_BCODE, _BLK = _method_src(_SRC, '_npc_life_blocks')
check('D0 `_npc_life_blocks` 存在', _BLK is not None)

_calls = {}
_at_home_ast = None
if _BLK is not None:
    for _n in ast.walk(_BLK):
        if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Attribute):
            _base = _n.func.value
            _bn = (_base.id if isinstance(_base, ast.Name)
                   else (_base.attr if isinstance(_base, ast.Attribute) else ''))
            _calls.setdefault('%s.%s' % (_bn, _n.func.attr), _n.lineno)
            if _n.func.attr == 'place_hint':
                for _kw in _n.keywords:
                    if _kw.arg == 'at_home':
                        _at_home_ast = ast.dump(_kw.value)

_HAS_PH = 'npc_life_mod.place_hint' in _calls
_HAS_TR = 'npc_life_mod.scene_traits' in _calls

check('D1 位置块**真的**接进了 `_npc_life_blocks`', _HAS_PH)
check('D2 位置块排在场景特质**之前**（反了会把地名当形容气氛的词）',
      bool(_HAS_PH and _HAS_TR and _calls['npc_life_mod.place_hint']
           < _calls['npc_life_mod.scene_traits']))
check('D3 归属地走 `npc_placement.home_of()` —— 与"回家/就寝"**同一出口**',
      'npc_placement.home_of' in _calls)
check('D4 `at_home` 是**比较式**（AST `Compare`），不是硬编码 True/False',
      bool(_at_home_ast and 'Compare' in _at_home_ast))


# ================================================================ E
print()
print('--- E 真实数据验收（84 条 `_placement.json`）---')

try:
    # ★ `load_placement(root)` 内部自己拼 `assets/` ⇒ 传 `ralsei_pet/`
    _book = P.load_placement(PET)
    _ids = list(_book.ids())
except Exception as _e:                                    # noqa: BLE001
    print('  placement 读取失败：%s' % _e)
    _book, _ids = None, []

_rows = []
for _nid in _ids:
    try:
        _sid = _book.scene_of(_nid)
        _hid = _book.home_of(_nid)
    except Exception:                                      # noqa: BLE001
        continue
    _rows.append((_nid, _sid, _hid, label(_sid), label(_hid),
                  bool(_sid and _hid and str(_sid) == str(_hid))))

_n_here = sum(1 for r in _rows if r[3])
_n_home = sum(1 for r in _rows if r[4])
_n_at = sum(1 for r in _rows if r[5])

check('E1 有 NPC 能拿到「你现在在哪」（否则等于没接）', _n_here > 0)
check('E2 有 NPC 能拿到「你的归属地」', _n_home > 0)
check('E3 `at_home` 判定自洽：判为在家的，登记场景必须真等于归属地',
      all(str(r[1]) == str(r[2]) for r in _rows if r[5]) and _n_at > 0)
_e_leak = [(r[0], t) for r in _rows for t in (r[3], r[4]) if t
           and any(x in t for x in _LEAK_TOK + ('None',))]
check('E4 真实数据产出的标签里零内部结构', not _e_leak, '%r' % (_e_leak[:3],))


# ================================================================ F
print()
print('--- F 方法级端到端（抽产品 `_npc_life_blocks` 整段跑）---')


class _Place(object):
    def __init__(self, home):
        self._home = home

    def home_of(self, npc_id):
        return self._home


class _Stub(object):
    npc_life_mod = L
    npc_bonds = None

    def __init__(self, sid, home):
        self._sid = sid
        self.npc_placement = _Place(home)

    def _npc_scene_id(self):
        return self._sid

    def _scene_place_label(self, sid):
        return label(sid)

    def _npc_scene_text(self):
        return ''

    def _npc_life_ids(self):
        return []

    def _npc_relative_positions(self, *a, **k):
        return {}

    def _npc_display_label(self, nid):
        return ''


if _BCODE:
    _bns = {'npc_life_mod': L, '_log': logging.getLogger('check113j')}
    exec(compile(_BCODE, '<npc_life_blocks>', 'exec'), _bns)
    _blocks = _bns['_npc_life_blocks']

    _o = _blocks(_Stub('ch1.castle_town.castle_town', 'ch1.castle_town.castle_town'), 'ralsei')
    check('F1 在家（sid == home）⇒ 输出「就是这儿」且不提「想回去」',
          '【你现在在哪】' in _o and '就是这儿' in _o and '想回去' not in _o)

    _o2 = _blocks(_Stub('uty.rooms.rm_steamworks_29', 'ch1.castle_town.castle_town'), 'ralsei')
    check('F2 不在家 ⇒ 输出「想回去」', '【你的归属地】' in _o2 and '想回去' in _o2)

    _o3 = _blocks(_Stub('desktop', None), 'ralsei')
    check('F3 无归属地 ⇒ 只有「在哪」，不硬凑归属地',
          '【你现在在哪】' in _o3 and '【你的归属地】' not in _o3)

    _o4 = _blocks(_Stub('ch1.castle_town.castle_town', 'ch1.castle_town.castle_town'), 'ralsei')
    check('F4 位置块在整段 prompt 的**最前面**（先给坐标，再给描述）',
          _o4.startswith('【你现在在哪】'))

    _o5 = _blocks(_Stub('', None), 'ralsei')
    check('F5 负控制：场景全空 ⇒ 整段为空（不许产出"你在某个地方"的空话）',
          _o5 == '', '%r' % _o5[:40])
else:
    for _k in range(1, 6):
        check('F%d 抽不到 `_npc_life_blocks`，端到端无法验证' % _k, False)


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
