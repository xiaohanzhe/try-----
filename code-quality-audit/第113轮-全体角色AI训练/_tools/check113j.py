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
REG = os.path.join(PET, 'assets', 'npc', '_registry.json')

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


def _place_proper():
    """与产品 `_place_proper()` **同口径**：`npc_registry` 里每个 id 的末段（小写）。

    ★ 为什么桩必须有它（第113轮m）：`_scene_place_label` 的 ⑥ 英文整形要传
      `proper=self._place_proper()`，桩不提供 ⇒ `AttributeError` 直接崩。
    ★ 为什么不在这写死 `{'asgore', ...}`：产品是从**角色登记册现取**的，写死
      一份就等于给"人名集合"另立一个真源，96 张卡一改这里就悄悄过期。
      这里读同一个 `_registry.json`，只跳过 Qt 那套 `npc_registry` 包装。
    """
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
_CODE, _FN = _method_src(_SRC, '_scene_place_label')
_IDX = _scene_index()
_PROPER = _place_proper()


class _LabelStub(object):
    npc_life_mod = L

    def _scene_label_map(self):
        return _IDX

    def _place_proper(self):
        return _PROPER


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
    # ★ 第113轮m 起位置块也要整形 ⇒ 这里跟着变成 `Steamworks 29`。
    #   不是"迁就实现"：真名 `steamworks 29` 一个字母没少，只是首字母大写。
    ('uty.rooms.rm_steamworks_29', 'Steamworks 29'),
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


print()
print('--- A5~A8 地名整形（第113轮m：口语化 / 复合词 / 中文无副作用）---')

# ★ 取模块常量一律 `getattr`（第106轮以来的铁律）：直接点属性，将来改名就是
#   `AttributeError` 把整个套件炸掉，而 G2 只看到"这轮红了"，看不出是测试自己的问题。
_MINOR = set(getattr(L, '_EN_MINOR', ()) or ())
check('A5a 虚词表可读（读不到 ⇒ A7/B6 白名单为空，会误报正确输出）', bool(_MINOR))

# ★★ A5 `Bed_room` 曾输出成 `Barrens · Bed` —— 类型词 `bed` 在首位就截断，
#    "房间"丢了。根因是 `room_word` 把 `Bed_room` 拼成 `bed room` 后逐词判类型词。
#    正/负成对：复合词必须合成（`Bedroom`），但**单个** `bed` 仍要按原样截断。
_bed_b = label('oneshot.barrens.Bed_room')
_bed_g = label('oneshot.glen.Bed_room')
check('A5 复合类型词合成：`Bed_room` ⇒ `Bedroom`，不许截成 `Bed`',
      'Bedroom' in _bed_b and 'Bedroom' in _bed_g
      and 'Bed room' not in _bed_b and 'Bed room' not in _bed_g,
      '%r / %r' % (_bed_b, _bed_g))

# ★ A6 负控制：整形**不许**把"本来就短的名字"也拉长。
#   真有单间就叫 `Bed`（`place_type_name` 判它时只该留 `Bed`），
#   若合并函数写成"见到 bed+任意词就拼"，这里会把它变成 `Bedroom`。
_merge_neg = L._merge_type_compounds(['bed', 'xyz'])
check('A6 负控制：拼起来不是词就不许合并（`bed xyz` 原样保留）',
      _merge_neg == ['bed', 'xyz'], '%r' % (_merge_neg,))

# ★★ A5b **破坏性负控制**：把合并函数换成恒等，A5 的判据必须真的变红。
#    只写 A5（"结果里有 Bedroom"）证明不了它是**因为合并**才过的 ——
#    万一哪天别的环节也顺手拼了个 Bedroom，A5 会一直绿而合并早被删掉。
_orig_merge = getattr(L, '_merge_type_compounds', None)
_mut_bed = None
try:
    L._merge_type_compounds = lambda toks: list(toks)
    _mut_bed = label('oneshot.barrens.Bed_room')
finally:
    if _orig_merge is not None:
        L._merge_type_compounds = _orig_merge
check('A5b 破坏性负控制：合并函数换成恒等 ⇒ `Bedroom` 必须消失（证明 A5 不是恒真）',
      bool(_orig_merge) and _mut_bed is not None
      and 'Bedroom' not in _mut_bed and 'Bed Room' in _mut_bed,
      '%r' % (_mut_bed,))


def _lower_toks(s):
    """标签主体里的小写英文**实词**（剥掉章名括注、放过虚词）。"""
    body = s[:(s.rindex('（') if s.endswith('）') and '（' in s else len(s))]
    return [t for t in body.replace('·', ' ').split()
            if t.isascii() and t.isalpha() and t[:1].islower()
            and t not in _MINOR]


# ★★ A7 英文一律 Title Case —— 同一份 prompt 里活动块是 `Town Square`、
#    位置块是 `town square`，模型会挑一个照抄。判据取**产品真实输出**，
#    不用 `speakable_en` 自证（那等于让被测函数自己判自己）。
#    ★ 虚词（`the`/`to`/`in`）本来就该小写（`Snowdin Secret to Everybody`），
#      不排除它们会把这 6 条正确输出判红 —— 判据过宽也是错。
_shaped = label('uty.rooms.rm_steamworks_29')
check('A7 英文地名首字母大写（小写 id 词语不许落进 prompt，虚词除外）',
      not _lower_toks(_shaped), '小写词=%r' % (_lower_toks(_shaped)[:3],))

# ★★ A7b 同样来一次破坏：拿掉整形函数 ⇒ 小写必须重新出现。
_orig_speak = getattr(L, 'speakable_en', None)
_mut_shape = None
try:
    L.speakable_en = lambda text, proper=(): str(text or '')
    _mut_shape = label('uty.rooms.rm_steamworks_29')
finally:
    if _orig_speak is not None:
        L.speakable_en = _orig_speak
check('A7b 破坏性负控制：拿掉整形 ⇒ 小写词重新出现（证明 A7 不是恒真）',
      bool(_orig_speak) and _mut_shape is not None and bool(_lower_toks(_mut_shape)),
      '%r' % (_mut_shape,))

# ★ A8 中文不许被整形动过一个字（负控制：整形的"副作用"边界）
check('A8 负控制：纯中文标签逐字不变（`城堡镇` 不许变成别的）',
      label('ch1.castle_town.castle_town').startswith('城堡镇')
      and label('desktop') == '桌面', '%r' % label('desktop'))


# ================================================================ B
print()
print('--- B 全量普查（一个场景都不落）---')

_LEAK_TOK = ('rm_', 'room_', '全部房间', '未分区', 'unzoned', 'unknown', '.rooms.')

_empty, _leak, _three, _paren = [], [], [], []
_ALL_LABELS = []          # (sid, label) —— B6 整形普查用，不打印条数
for _sid in _IDX:
    _got = label(_sid)
    if not _got:
        _empty.append(_sid)
        continue
    _ALL_LABELS.append((_sid, _got))
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

# ★ B5 容器判据**正负成对**。只判"带括注的容器名要认"会过宽：
#   真地名也有带括注的（`城堡镇（废墟）`），一刀切成容器就等于把地名删了。
#   第113轮j 修 26 条漏判时，第一版就是把 `split('（')[0]` 当唯一判据。
_c_yes = (L.place_container('未分区（废弃/调试/演示）')
          and L.place_container('全部房间')
          and L.place_container('未分区'))
_c_no = (not L.place_container('城堡镇（废墟）')
         and not L.place_container('荒野')
         and not L.place_container('')
         and not L.place_container(None))
check('B5 容器名判据正负成对（`未分区（…）`/`全部房间` 认；`城堡镇（废墟）`/空 不许误杀）',
      _c_yes and _c_no, '认=%s 不认=%s' % (_c_yes, _c_no))

# ★★ B6 全量整形普查（第113轮m）：2166 个标签里**不许**再有小写英文实词。
#    只查一个 `steamworks` 说明不了覆盖面 —— 实测全量里另有 6 条虚词小写
#    （`Snowdin Secret to Everybody`），那是**对的**英文，所以白名单是虚词表本身，
#    而不是"看到小写就报红"（那样 6 条正确输出会被判死，判据比 bug 更吵）。
_lower_all = []
for _sid, _got in _ALL_LABELS:
    _lt = _lower_toks(_got)
    if _lt:
        _lower_all.append((_sid, _lt, _got))
check('B6 全量：小写英文实词 0 条（虚词例外，见注释）',
      not _lower_all, '%r' % (_lower_all[:3],))


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
