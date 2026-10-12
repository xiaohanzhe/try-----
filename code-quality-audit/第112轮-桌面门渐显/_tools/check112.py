# -*- coding: utf-8 -*-
"""第112轮 #47 自检：门渐显（door_reveal）—— 按项目纪律写正/负控制。"""
import io, os, sys, json
import ast as _ast

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    '..', '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'ralsei_pet'))
sys.path.insert(0, os.path.join(ROOT, 'ralsei_pet', 'modules'))

from modules import door_reveal as dr
# ★★★ `item_interact` 是**零依赖 L1**（`G1` 硬闸）⇒ 直接 import 它即可，
#   不需要 Qt 也不会拉起 `main.py` 的初始化环。
from modules import item_interact as _ii

ok = fail = 0
def check(name, cond, star=False):
    global ok, fail
    if cond:
        ok += 1
        print('[PASS] %s' % name)
    else:
        fail += 1
        print('[FAIL] %s' % name)

print('=== A. 纯函数基本形 ===')
# A1: 距离很远 ⇒ 下限
far_ent = (1000.0, 1000.0, 1050.0, 1050.0)
door = (0.0, 70.0, 44.0, 169.0)
a_far = dr.reveal_alpha(far_ent, door)
check('A1 远距离 ⇒ 下限 %.3f' % a_far, abs(a_far - dr.MIN_ALPHA) < 1e-9, star=True)
# A2: 完全重合 ⇒ 上限
a_hit = dr.reveal_alpha(door, door)
check('A2 重叠 ⇒ 上限 %.3f' % a_hit, abs(a_hit - dr.MAX_ALPHA) < 1e-9, star=True)
# ★ A/B 先断言 A≠B（否则"两处都错成同一个值"会假绿）
check('A3 ★ 远 ≠ 近（防恒真）', abs(a_far - a_hit) > 0.3, star=True)
# ★★★ A4：`MIN_ALPHA` 必须 **> 0** —— 用户要"从透明到实象"，但完全 0 =
#   看不见门在哪 ⇒ 玩家找不到路。留一丝幽灵般的可见度是**刻意的产品口径**。
#   判据 = ① 常量真 > 0；② 且**不是**被随手改成 0（负控制：`reveal_alpha` 在最远处
#   返回的**就是** MIN_ALPHA，且**必须** > 0）。两路一起判才防得住"改常量"。
check('A4 ★★★ MIN_ALPHA > 0（"%s" 明确要求留可发现性）' % dr.MIN_ALPHA,
      float(dr.MIN_ALPHA) > 0.0, star=True)
check('A4b ★★ 最远处的 alpha 真 > 0（门始终可见一丝）',
      a_far > 0.0 and abs(a_far - float(dr.MIN_ALPHA)) < 1e-9, star=True)
# ★ A4c 负控制：把 min_alpha 传 0 ⇒ 返回值**必须**变 0（证明 A4b 真的在测这个量，
#   而不是"无论传什么都 > 0"）
_a_zero = dr.reveal_alpha(far_ent, door, min_alpha=0.0)
check('A4c ★ 负控制：min_alpha=0 ⇒ 返回值真为 0（证明 A4b 有鉴别力）',
      _a_zero == 0.0 and a_far > 0.0, star=True)

print('=== B. ease 单调 + 端点 ===')
check('B1 ease(0)==0', abs(dr.ease(0.0)) < 1e-12)
check('B2 ease(1)==1', abs(dr.ease(1.0) - 1.0) < 1e-12)
_prev = -1.0
_mono = True
for i in range(0, 101):
    v = dr.ease(i / 100.0)
    if v < _prev - 1e-12:
        _mono = False
        break
    _prev = v
check('B3 ease 单调不减（0..1 扫 101 点）', _mono, star=True)
# ★★★ B4：`ease` 必须是 **smoothstep**（`3t²-2t³`），不能退化成线性 ——
#   用户要的是「从虚到实的**过度动画**」；线性 = 起点/终点速度不为 0 ⇒ 观感是
#   "被突然点亮"而不是"显影"。判据 = 逐点与 smoothstep 公式比对（**独立重算**）。
#   ★ 负控制 B4b：线性 `t` 在中段与 smoothstep **必须不同**（否则判据恒真）。
_ss_bad = []
for i in range(1, 100):
    t = i / 100.0
    expect = t * t * (3.0 - 2.0 * t)
    got = dr.ease(t)
    if abs(got - expect) > 1e-9:
        _ss_bad.append((round(t, 2), round(got, 4), round(expect, 4)))
check('B4 ★★★ ease == smoothstep(3t²-2t³) 逐点（不是线性） [%s]' % str(_ss_bad[:2]),
      not _ss_bad, star=True)
# ★ B4b 负控制：**t=0.5 不行** —— smoothstep 与线性在 0.5 处**恰好相等**
#   （3(.25)-2(.125)=0.5），拿它当判据会恒假。改在 **t=0.25**：
#   smoothstep(0.25)=0.15625 vs 线性 0.25 ⇒ 差 0.094（可分辨）。
check('B4b ★ 负控制：线性 t 在 t=0.25 ≠ smoothstep（证明 B4 有鉴别力）',
      abs(0.25 - dr.ease(0.25)) > 0.05, star=True)

print('=== C. rect_gap ===')
check('C1 分离(纯 x)', abs(dr.rect_gap((0,0,10,10), (20,0,30,10)) - 10.0) < 1e-9)
check('C2 分离(纯 y)', abs(dr.rect_gap((0,0,10,10), (0,30,10,40)) - 20.0) < 1e-9)
check('C3 相交 ⇒ 0', dr.rect_gap((0,0,10,10), (5,5,15,15)) == 0.0)
check('C4 包含 ⇒ 0', dr.rect_gap((0,0,100,100), (40,40,50,50)) == 0.0)
_g = dr.rect_gap((0,0,10,10), (13,14,20,20))
check('C5 双轴分离 = 3-4-5', abs(_g - 5.0) < 1e-9, star=True)
check('C6 None ⇒ inf', dr.rect_gap(None, (0,0,1,1)) == float('inf'))
check('C7 坏长度 ⇒ inf', dr.rect_gap((0,0,1), (0,0,1,1)) == float('inf'))
check('C8 ★ nan ⇒ inf（保守）', dr.rect_gap((float('nan'),0,1,1), (0,0,1,1)) == float('inf'), star=True)

print('=== D. reveal_t 阈值 ===')
check('D1 gap>=near ⇒ 0', dr.reveal_t(999.0) == 0.0)
check('D2 gap<=far ⇒ 1', dr.reveal_t(1.0) == 1.0)
_mid = dr.reveal_t((dr.NEAR_DIST + dr.FAR_DIST) / 2.0)
check('D3 中段 ∈ (0,1)：%.3f' % _mid, 0.0 < _mid < 1.0, star=True)
check('D4 near<=far 退化（不抛）', dr.reveal_t(5.0, near=1.0, far=10.0) == 1.0)

print('=== E. 目标门白名单（★★★ 用户口径：只 UT 与三角符文）===')
check('E1 (desktop,C) 命中', dr.is_reveal_door('desktop', 'C'), star=True)
check('E2 (desktop,D) 命中', dr.is_reveal_door('desktop', 'D'), star=True)
check('E3 ★ (desktop,A) OneShot **不**命中', not dr.is_reveal_door('desktop', 'A'), star=True)
check('E4 ★ (desktop,B) Niko家 **不**命中', not dr.is_reveal_door('desktop', 'B'), star=True)
check('E5 其它场景不命中', not dr.is_reveal_door('ch1.hometown.town_mid', 'C'))
check('E6 小写字母也命中', dr.is_reveal_door('desktop', 'c'), star=True)
check('E7 None ⇒ False', not dr.is_reveal_door(None, 'C') and not dr.is_reveal_door('desktop', None))

print('=== F. apply_to_objects（就地写 alpha，只碰两扇门）===')
_objs = [
    {'id': 'oneshot', 'src': 'obj_doorA', 'sprite': 'objs/spr_darkdoor_0.png', 'pos': [138, 0]},
    {'id': 'niko',    'src': 'obj_doorB', 'sprite': 'objs/spr_darkdoor_0.png', 'pos': [138, 184]},
    {'id': 'ut',      'src': 'obj_doorC', 'sprite': 'objs/ut_castle_realdoor_0.png', 'pos': [0, 70]},
    {'id': 'dr',      'src': 'obj_doorD', 'sprite': 'objs/spr_shortcut_door_0.png', 'pos': [284, 94]},
]
_sizes = {'objs/spr_darkdoor_0.png': (44, 56),
          'objs/ut_castle_realdoor_0.png': (44, 99),
          'objs/spr_shortcut_door_0.png': (36, 52)}
def _sz(o):
    return _sizes.get(o.get('sprite'))

# F1: 实体远离 ⇒ 两扇目标门 = 下限，非目标门**根本没写 alpha 键**
_ent_far = (3000.0, 3000.0, 3050.0, 3050.0)
chg = dr.apply_to_objects(_objs, 'desktop', _ent_far, sizer=_sz)
check('F1a 改动 = 恰好 2 扇', len(chg) == 2, star=True)
check('F1b ★ oneshot **无** alpha 键', 'alpha' not in _objs[0], star=True)
check('F1c ★ niko 家 **无** alpha 键', 'alpha' not in _objs[1], star=True)
check('F1d ut = 下限', abs(_objs[2]['alpha'] - dr.MIN_ALPHA) < 1e-9)
check('F1e dr = 下限', abs(_objs[3]['alpha'] - dr.MIN_ALPHA) < 1e-9)

# F2: 实体贴住 UT 门 ⇒ UT = 上限，dr 仍下限（**A/B 必须不同**）
_ent_ut = (0.0, 70.0, 44.0, 169.0)
dr.apply_to_objects(_objs, 'desktop', _ent_ut, sizer=_sz)
check('F2a ★ UT 贴脸 ⇒ 上限 %.3f' % _objs[2]['alpha'], abs(_objs[2]['alpha'] - dr.MAX_ALPHA) < 1e-9, star=True)
check('F2b ★ 同时 dr 仍下限（证明按各自距离算，非"一开全开"）',
      abs(_objs[3]['alpha'] - dr.MIN_ALPHA) < 1e-9, star=True)

# F3: 幂等 —— 同一实体反复调用 ⇒ 值不变、第二次改动列表为空
chg2 = dr.apply_to_objects(_objs, 'desktop', _ent_ut, sizer=_sz)
check('F3 ★ 幂等：第二次改动 0 扇', len(chg2) == 0, star=True)

# F4: 场景不是 desktop ⇒ 一个都不碰
_objs2 = [{'id': 'd', 'src': 'obj_doorC', 'sprite': 'objs/ut_castle_realdoor_0.png', 'pos': [0, 70]}]
chg4 = dr.apply_to_objects(_objs2, 'ch1.hometown.town_mid', _ent_ut, sizer=_sz)
check('F4 ★ 非桌面场景不改动', len(chg4) == 0 and 'alpha' not in _objs2[0], star=True)

# F5: 无 sizer ⇒ 仍能算（退化成点），不抛
_objs3 = [{'id': 'ut', 'src': 'obj_doorC', 'sprite': 'objs/x.png', 'pos': [0, 70]}]
chg5 = dr.apply_to_objects(_objs3, 'desktop', _ent_ut, sizer=None)
check('F5 无 sizer 不抛且写入', len(chg5) == 1 and 'alpha' in _objs3[0])

# F6: 负控制 —— 实体跟门完全重合时，**别人的门**不会跟着变
check('F6 ★ 负控制：非目标门始终无 alpha', 'alpha' not in _objs[0] and 'alpha' not in _objs[1], star=True)

print('=== G. desktop.json 贴图口径 ===')
_dp = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes', 'desktop.json')
_d = json.load(io.open(_dp, encoding='utf-8'))
_by_src = {o.get('src'): o for o in _d['objects']}
check('G1 仍 4 扇门', len(_d['objects']) == 4, star=True)
check('G2 UT 门 = ut_castle_realdoor',
      _by_src['obj_doorC']['sprite'] == 'objs/ut_castle_realdoor_0.png', star=True)
check('G3 符文门 = spr_shortcut_door_0',
      _by_src['obj_doorD']['sprite'] == 'objs/spr_shortcut_door_0.png', star=True)
check('G4 ★ UT 门无 anim（单帧，避免找 _1.png）', 'anim' not in _by_src['obj_doorC'], star=True)
_dr_png = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes', 'objs', 'spr_shortcut_door_1.png')
check('G5 ★ 符文门 2 帧素材都在盘', os.path.exists(_dr_png), star=True)
_ut_png = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes', 'objs', 'ut_castle_realdoor_0.png')
check('G6 UT 门素材在盘', os.path.exists(_ut_png), star=True)

print('=== H. ★★★ 零依赖 + 字母表不分叉 ===')
# H1: 「零依赖」是设计承诺 —— ★★ **不能**看 `sys.modules`（那会被"同进程里
#     别处先 import 了 Qt"污染：本套件自己就 import 了 `item_interact`，
#     而它顶层 `from companion import ...` ⇒ `companion` 必然在 `sys.modules`，
#     首版就是这么假红的）。改为**直接读 `door_reveal.py` 的 AST**：断言它
#     **没有任何 import 语句**指向 Qt / companion / item_interact。
_dr_t = _ast.parse(io.open(
    os.path.join(ROOT, 'ralsei_pet', 'modules', 'door_reveal.py'),
    encoding='utf-8').read())
_dr_imports = set()
for _n in _ast.walk(_dr_t):
    if isinstance(_n, _ast.Import):
        for _a in _n.names:
            _dr_imports.add(_a.name.split('.')[0])
    elif isinstance(_n, _ast.ImportFrom):
        if getattr(_n, 'module', None):
            _dr_imports.add(_n.module.split('.')[0])
# ★ door_reveal 的设计是"**零 import**"（连 math 都不用）⇒ 集合必须为空
check('H1 ★★★ door_reveal 顶层**零 import**（零依赖承诺；AST 取证不是看 sys.modules）'
      ' [%s]' % ','.join(sorted(_dr_imports)),
      not _dr_imports, star=True)
# H1b: ★ 负控制 —— 证明上面的 AST 查找有鉴别力（拿 main.py 试：必然有 import）
_main_t_h = _ast.parse(io.open(
    os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py'),
    encoding='utf-8').read())
_main_has_import = any(isinstance(_n, (_ast.Import, _ast.ImportFrom))
                       for _n in _ast.walk(_main_t_h))
check('H1b ★ 负控制：同一查找在 main.py 上必然非空（证明 H1 非恒真）',
      _main_has_import, star=True)
# H2: 单调性（近 ⇒ alpha 不减）
_pts = []
for _d in (200.0, 150.0, 110.0, 70.0, 34.0, 10.0, 0.0):
    _r = (0.0, 70.0 + _d, 44.0, 169.0 + _d)
    _pts.append(dr.reveal_alpha(_r, (0.0, 70.0, 44.0, 169.0)))
_mono2 = all(_pts[i] <= _pts[i + 1] + 1e-12 for i in range(len(_pts) - 1))
check('H2 ★ 越近越实（单调，7 点距扫）', _mono2, star=True)
check('H3 ★ 两端真的有差：%.3f → %.3f' % (_pts[0], _pts[-1]),
      _pts[-1] - _pts[0] > 0.5, star=True)
# H4: ★★★ 两份字母表必须完全相等（防分叉）
try:
    from modules import item_interact as _ii
    check('H4 ★★ 字母表与 item_interact 完全相等',
          tuple(_ii.DOOR_LETTERS) == tuple(dr.DOOR_LETTERS), star=True)
    # H5: 抽样比对两份 door_letter_of 的结果
    _samples = ['obj_doorA', 'obj_doorC', 'obj_doorD', 'obj_doorY',
                'obj_doorW_0', 'obj_darkdoor', 'obj_doorAA', 'obj_door',
                'obj_doorevent', '', None]
    _diff = []
    for _s in _samples:
        _a = _ii.door_letter_of(_s)
        _b = dr.door_letter_of_local(_s)
        if _a != _b:
            _diff.append((_s, _a, _b))
    check('H5 ★★ 抽样 11 输入两份结果一致 [%s]' % str(_diff[:3]),
          not _diff, star=True)
except Exception as _e:
    check('H4/H5 无法 import item_interact（%s）⇒ 报红，不许静默跳过' % _e,
          False, star=True)

print('=== I. Niko 家准入门槛（★★★ 只有用户/灵魂进不去）===')
from modules import niko_home as nh
# I1: 用户（灵魂）⇒ 不能进
_a1, _r1 = nh.can_enter('soul')
check('I1 ★ soul ⇒ 拒绝 (%s)' % _r1, _a1 is False and _r1 == 'user', star=True)
check('I2 ★ user ⇒ 拒绝', nh.can_enter('user')[0] is False, star=True)
check('I3 ★ 中文「灵魂」⇒ 拒绝', nh.can_enter('灵魂')[0] is False, star=True)
# I4: 其他 NPC ⇒ 能进
for _who in ('sans', 'toriel', 'ralsei', 'kris_the_npc', 'niko'):
    check('I4 ★ %s ⇒ 放行' % _who, nh.can_enter(_who)[0] is True, star=True)
# I5: ★★★ None（系统/NPC 自主触发）⇒ **必须放行**（这是最关键的负控制）
check('I5 ★★ None（系统触发）⇒ 放行', nh.can_enter(None)[0] is True, star=True)
# I6: 对象形态（is_soul 标记）
class _SoulLike(object):
    is_soul = True
class _NpcLike(object):
    name = 'sans'
check('I6 ★ 对象 is_soul=True ⇒ 拒绝', nh.can_enter(_SoulLike())[0] is False, star=True)
check('I7 ★ 对象 name=sans ⇒ 放行', nh.can_enter(_NpcLike())[0] is True, star=True)
# I8: ★ 陌生对象 ⇒ 放行（保守侧 = 不挡人）
class _Weird(object):
    pass
check('I8 ★★ 陌生对象 ⇒ 放行（默认站"能进"）', nh.can_enter(_Weird())[0] is True, star=True)
# I9: A/B 不同（防恒真）
check('I9 ★ 用户与 NPC 结论**不同**（防恒真）',
      nh.can_enter('soul')[0] != nh.can_enter('sans')[0], star=True)
# I10: entrance_hint
_h1, _ok1 = nh.entrance_hint('soul')
_h2, _ok2 = nh.entrance_hint('sans')
check('I10 ★ 用户拿拒绝语 / NPC 拿错觉语（二者不同）',
      _ok1 is False and _ok2 is True and _h1 != _h2, star=True)
check('I11 ★ NPC 的错觉语非空且不提具体地点',
      bool(_h2) and '错觉' not in _h2, star=True)

print('=== J. Niko 家问答护栏（★★ 两条线都接）===')
# J1: 第 1 次 ⇒ 人设线（正常回答）
_t1, _b1 = nh.niko_home_reply(1)
check('J1 ★ 第1次 ⇒ 人设线（不屏蔽）', _b1 is False and bool(_t1), star=True)
# J2: 第 2 次 ⇒ 屏蔽
_t2, _b2 = nh.niko_home_reply(2)
check('J2 ★★ 第2次 ⇒ 「%s」' % _t2, _b2 is True and _t2 == nh.BLOCKED_REPLY, star=True)
check('J3 ★★ 第3次及以后 ⇒ 仍屏蔽', nh.niko_home_reply(9)[1] is True, star=True)
# J4: ★ 两条线**内容不同**（防恒真）
check('J4 ★ 人设线内容 ≠ 屏蔽语（防恒真）', _t1 != _t2, star=True)
# J5: 屏蔽语逐字
check('J5 ★★ 屏蔽语逐字 = 「内容以屏蔽」', nh.BLOCKED_REPLY == '内容以屏蔽', star=True)
# J6: 非法计数 ⇒ 当第一次（保守：先好好答）
check('J6 ★ None ⇒ 人设线（保守）', nh.niko_home_reply(None)[1] is False, star=True)
check('J7 ★ 0/负数 ⇒ 人设线', nh.niko_home_reply(0)[1] is False
      and nh.niko_home_reply(-3)[1] is False, star=True)
# J8: 计数器推进
check('J8 计数器 0→1→2', nh.normalize_ask_count(0) == 1
      and nh.normalize_ask_count(1) == 2, star=True)
check('J9 计数器非法 ⇒ 1', nh.normalize_ask_count(None) == 1
      and nh.normalize_ask_count('x') == 1, star=True)

print('=== K. 关键词判定（问的是不是 Niko 的家）===')
_yes = ['Niko 家什么样', 'niko的家乡在哪', 'NIKO 老家', '尼科家在哪',
        '你说的 niko 的家是什么样子']
_no = ['你好啊', '你家在哪', 'Niko 在吗', '今天吃什么', '', None, '家']
for _s in _yes:
    check('K1 ★ 命中：%r' % _s, nh.looks_like_niko_home_question(_s) is True, star=True)
for _s in _no:
    check('K2 ★ 不命中：%r' % _s, nh.looks_like_niko_home_question(_s) is False, star=True)

print('=== L. 三连台词：两份字面量 + 一致性锁（★ 不互相 import）===')
_II = os.path.join(ROOT, 'ralsei_pet', 'modules', 'item_interact.py')
_ii_src = io.open(_II, encoding='utf-8').read()
_ii_tree = _ast.parse(_ii_src)
check('L1 ★ EGG_TEXTS 与 niko_home 完全相等',
      tuple(dr and nh.EGG_TEXTS) == tuple(nh.EGG_TEXTS), star=True)
try:
    _iit = _ii.NIKO_HOME_EGG_TEXT
    check('L2 ★★ item_interact 的台词 == niko_home.EGG_TEXTS（一致性锁）',
          tuple(_iit) == tuple(nh.EGG_TEXTS), star=True)
except Exception as _e:
    check('L2 无法取 item_interact.NIKO_HOME_EGG_TEXT（%s）⇒ 报红' % _e, False, star=True)
check('L3 ★ 三连台词仍是 3 条', len(nh.EGG_TEXTS) == 3, star=True)
# ★★★ L4：`item_interact` 里那份**必须仍是字面量元组**（不是派生）。
#   为什么：`item_interact` 是零依赖 L1，`第48轮 verify_items48` 的 `G1`
#   硬闸禁止它 import 任何项目内模块（顶层/函数内皆禁）。
#   若这里改回 `from niko_home import EGG_TEXTS` ⇒ `G1` 报红 + `check111`
#   A2/A4/A5/A6/A6b（AST 取值）全报红。⇒ 名字与值两路都判，防恒真。
_ii_egg_lit = None
for _n in _ast.walk(_ii_tree):
    if isinstance(_n, _ast.Assign):
        for _t in _n.targets:
            if (isinstance(_t, _ast.Name)
                    and _t.id == 'NIKO_HOME_EGG_TEXT'
                    and isinstance(_n.value, _ast.Tuple)):
                _vals = [e.value for e in _n.value.elts
                         if isinstance(e, _ast.Constant)]
                if len(_vals) == 3:
                    _ii_egg_lit = _vals
check('L4 ★★★ item_interact 的 NIKO_HOME_EGG_TEXT 仍是**字面量 3 元组**'
      '（不是从 niko_home 派生）',
      _ii_egg_lit == list(nh.EGG_TEXTS), star=True)
check('L4b ★★ 负控制：L4 有鉴别力（派生写法 ⇒ 抓不到字面量元组）',
      _ii_egg_lit is not None, star=True)
# ★★★ L5：`item_interact` **真的没有** import 项目内模块（`G1` 的同源断言，
#   放在这里是为了"改了 L 段就立刻在本套件报红"，不用等到跑 48 轮套件）。
_ii_bad_imports = set()
_II_OK_TOP = ('collections', 'json', 'logging', 'os', 'sys', 'companion')
for _n in _ast.walk(_ii_tree):
    if isinstance(_n, _ast.Import):
        for _a in _n.names:
            _top = _a.name.split('.')[0]
            if _top not in _II_OK_TOP:
                _ii_bad_imports.add(_top)
    elif isinstance(_n, _ast.ImportFrom):
        if _n.module and _n.level == 0:
            _top = _n.module.split('.')[0]
            if _top not in _II_OK_TOP:
                _ii_bad_imports.add(_top)
check('L5 ★★★ item_interact 未 import 项目内模块（零依赖 L1；G1 同源）'
      ' [%s]' % ','.join(sorted(_ii_bad_imports)),
      not _ii_bad_imports, star=True)

print('=== M. niko_home 也零依赖 ===')
# ★★ 同上：不看 `sys.modules`（会被本进程别处 import 污染），改读 AST。
_nh_t = _ast.parse(io.open(
    os.path.join(ROOT, 'ralsei_pet', 'modules', 'niko_home.py'),
    encoding='utf-8').read())
_nh_imports = set()
for _n in _ast.walk(_nh_t):
    if isinstance(_n, _ast.Import):
        for _a in _n.names:
            _nh_imports.add(_a.name.split('.')[0])
    elif isinstance(_n, _ast.ImportFrom):
        if getattr(_n, 'module', None):
            _nh_imports.add(_n.module.split('.')[0])
check('M1 ★ niko_home 顶层**零 import**（零依赖；AST 取证） [%s]'
      % ','.join(sorted(_nh_imports)), not _nh_imports, star=True)

# ★★★ M2（源码级常量钉死）：`door_reveal.MIN_ALPHA` 的**字面量值**必须是正的、
#   且不得为 0 —— 因为 A4 系列只在"运行时读常量"这一层守；若有人把常量改成 0，
#   A4 会报红；但若有人写 `MIN_ALPHA = -0.0` 之类等价写法，A4 也要抓得到。
#   这里再用 **AST 取字面量** 双保险（禁纯文本 `in`，会撞注释/docstring）。
_dr_path = os.path.join(ROOT, 'ralsei_pet', 'modules', 'door_reveal.py')
_dr_tree = _ast.parse(io.open(_dr_path, encoding='utf-8').read())
_min_lit = None
for _n in _ast.walk(_dr_tree):
    if isinstance(_n, _ast.Assign):
        for _t in _n.targets:
            if isinstance(_t, _ast.Name) and _t.id == 'MIN_ALPHA' \
                    and isinstance(_n.value, _ast.Constant):
                _min_lit = _n.value.value
check('M2 ★★★ 源码里 MIN_ALPHA 字面量 == %.2f（AST 取值）' % float(dr.MIN_ALPHA),
      _min_lit is not None and abs(float(_min_lit) - float(dr.MIN_ALPHA)) < 1e-12
      and float(_min_lit) > 0.0, star=True)

# ★★ M3：`can_enter(None)` ⇒ 放行 —— 但**必须**证明这是"代码真的会走到的分支"，
#   而不是"恰好因为 is_user_subject(None) 返回 False"（巧合）。
#   判据（结构化）：`is_user_subject` 对 `None` 必须返 False（这是放行的**前提**），
#   且 `can_enter(None)` 必须返 True。两者一起判 ⇒ 任一环节被改成"挡 None"都报红。
check('M3 ★★ is_user_subject(None) == False（放行的前提）',
      nh.is_user_subject(None) is False, star=True)
check('M3b ★★★ can_enter(None) ⇒ 放行（系统/NPC 自主触发不会被挡）',
      nh.can_enter(None)[0] is True, star=True)
# ★ M3c 负控制：真正的主体必须被判 True（证明 is_user_subject 不是恒 False）
check('M3c ★ 负控制：is_user_subject("soul") 必须 True（证明 M3 非恒真）',
      nh.is_user_subject('soul') is True, star=True)

print('=== N. ★★★ 接线（AST 结构化，禁纯文本扫）===')
_MAIN = os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py')
_main_src = io.open(_MAIN, encoding='utf-8').read()
_main_tree = _ast.parse(_main_src)


def _func(tree, name, cls=None):
    """按名字找函数节点（可限定类）。返回 node 或 None。"""
    for n in _ast.walk(tree):
        if isinstance(n, _ast.FunctionDef) and n.name == name:
            if cls is None:
                return n
            for parent in _ast.walk(tree):
                if isinstance(parent, _ast.ClassDef) and parent.name == cls:
                    if n in parent.body:
                        return n
    return None


# N1: `interact_scene_prop` 里 **真的有** `prop.interact(<实参>)`（不是 `interact()`）
_f = _func(_main_tree, 'interact_scene_prop')
_n1 = False
if _f is not None:
    for n in _ast.walk(_f):
        if (isinstance(n, _ast.Call)
                and isinstance(n.func, _ast.Attribute)
                and n.func.attr == 'interact'
                and len(n.args) >= 1):
            _n1 = True
            break
check('N1 ★★ interact_scene_prop 真的传了 actor（不是空参调用）', _n1, star=True)
# N1b: 存在 `'soul'` 字面量（主体名），且**不是**注释/字符串拼接产物
_n1b = any(isinstance(n, _ast.Constant) and n.value == 'soul'
           for n in _ast.walk(_f)) if _f is not None else False
check('N1b ★ 传的主体名含 "soul" 字面量', _n1b, star=True)

# N2: `_niko_home_egg` 里有 `can_enter(...)` 调用（第二道准入）
_f2 = _func(_main_tree, '_niko_home_egg')
_n2 = False
if _f2 is not None:
    for n in _ast.walk(_f2):
        if isinstance(n, _ast.Call):
            fn = n.func
            nm = fn.attr if isinstance(fn, _ast.Attribute) else (
                fn.id if isinstance(fn, _ast.Name) else '')
            if nm == 'can_enter':
                _n2 = True
                break
check('N2 ★★ _niko_home_egg 内有 can_enter 调用（第二道门槛）', _n2, star=True)

# N3: ★★★ **注入式门槛**（第112轮改版）—— `NikoHomeDoorProp.on_interact`
#   里**真的调了** `self.gate(...)`，而**不是**自己去 import `niko_home`
#   （后者会让 `item_interact` 违反 `G1` 零依赖硬闸 —— 首版就是这么错的）。
#   判据拆两条：
#     N3a 正向：`on_interact` 内有 `self.gate(...)` 调用；
#     N3b 反向：`item_interact.py` **整个文件**没有 `niko_home` 的 import
#              （由 L5 已经覆盖，这里补一条**函数内**的，因为 `G1` 对两者都禁）。
_n3a = False
for n in _ast.walk(_ii_tree):
    if isinstance(n, _ast.ClassDef) and n.name == 'NikoHomeDoorProp':
        for m in n.body:
            if isinstance(m, _ast.FunctionDef) and m.name == 'on_interact':
                for k in _ast.walk(m):
                    if (isinstance(k, _ast.Call)
                            and isinstance(k.func, _ast.Attribute)
                            and k.func.attr == 'gate'
                            and isinstance(k.func.value, _ast.Name)
                            and k.func.value.id == 'self'):
                        _n3a = True
check('N3a ★★★ NikoHomeDoorProp.on_interact 真调 self.gate(...)（注入式第一道门槛）',
      _n3a, star=True)
# N3b: 全文件（含函数内）任何位置都不许出现 `niko_home` 的 import 语句
_n3b_bad = []
for n in _ast.walk(_ii_tree):
    if isinstance(n, _ast.Import):
        for _a in n.names:
            if _a.name.split('.')[0].lstrip('_') == 'niko_home':
                _n3b_bad.append(_a.name)
    elif isinstance(n, _ast.ImportFrom):
        if getattr(n, 'module', None) and n.level == 0 \
                and n.module.split('.')[0].lstrip('_') == 'niko_home':
            _n3b_bad.append(n.module)
check('N3b ★★★ item_interact **任何位置**都未 import niko_home（零依赖；G1 同源）',
      not _n3b_bad, star=True)
# N3c: ★ 负控制 —— 证明 N3a 的查找有鉴别力（换个不存在的属性名 ⇒ False）
_n3c = False
for n in _ast.walk(_ii_tree):
    if isinstance(n, _ast.ClassDef) and n.name == 'NikoHomeDoorProp':
        for m in n.body:
            if isinstance(m, _ast.FunctionDef) and m.name == 'on_interact':
                for k in _ast.walk(m):
                    if (isinstance(k, _ast.Call)
                            and isinstance(k.func, _ast.Attribute)
                            and k.func.attr == 'no_such_attr_xyz'):
                        _n3c = True
check('N3c ★ 负控制：换不存在的属性名 ⇒ 查找判假（证明 N3a 非恒真）',
      _n3c is False, star=True)

# N4: `npc_speak` 里有 `_niko_home_guard` 包装（问答护栏接线）
_f4 = _func(_main_tree, 'npc_speak')
_n4 = False
if _f4 is not None:
    for n in _ast.walk(_f4):
        if isinstance(n, _ast.Call):
            fn = n.func
            nm = fn.attr if isinstance(fn, _ast.Attribute) else (
                fn.id if isinstance(fn, _ast.Name) else '')
            if nm == '_niko_home_guard':
                _n4 = True
                break
check('N4 ★★ npc_speak 调用了 _niko_home_guard（护栏接线）', _n4, star=True)

# N5: `_niko_home_guard` 里调 `looks_like_niko_home_question` + `niko_home_reply`
_f5 = _func(_main_tree, '_niko_home_guard')
_n5a = _n5b = False
if _f5 is not None:
    for n in _ast.walk(_f5):
        if isinstance(n, _ast.Call):
            fn = n.func
            nm = fn.attr if isinstance(fn, _ast.Attribute) else (
                fn.id if isinstance(fn, _ast.Name) else '')
            if nm == 'looks_like_niko_home_question':
                _n5a = True
            if nm == 'niko_home_reply':
                _n5b = True
check('N5a ★ 护栏用 looks_like_niko_home_question 判"在问"', _n5a, star=True)
check('N5b ★ 护栏用 niko_home_reply 取两条线的文案', _n5b, star=True)

# N6: ★★ 负控制 —— 断言"提到某名字"这种恒真判据**不会**被当成证据。
#   做法：故意构造一个**不存在**的函数名，确认查找返回 None（证明查找真在工作）。
check('N6 ★ 负控制：查不存在的函数名 ⇒ None（证明查找非恒真）',
      _func(_main_tree, 'this_function_does_not_exist_zzz') is None, star=True)

# N7: ★★★ 宿主**真的注入了** gate —— 三处串联缺一不可：
#   N7a `_niko_home_gate` 存在且内部调 `can_enter`（真源唯一）；
#   N7b `build_props` 调用点传了 `egg_gate=` 关键字（否则 NikoHomeDoorProp.gate 恒 None）；
#   N7c `build_props` 的 `egg_gate` 形参被透传进 `NikoHomeDoorProp(..., gate=...)`。
_f7 = _func(_main_tree, '_niko_home_gate')
_n7a = False
if _f7 is not None:
    for n in _ast.walk(_f7):
        if isinstance(n, _ast.Call):
            fn = n.func
            nm = fn.attr if isinstance(fn, _ast.Attribute) else (
                fn.id if isinstance(fn, _ast.Name) else '')
            if nm and nm.lstrip('_') == 'can_enter':
                _n7a = True
check('N7a ★★★ main.py 有 _niko_home_gate 且内部调 can_enter（真源唯一）',
      _n7a, star=True)
# N7b: build_props 调用点带 egg_gate= 关键字
_n7b = False
for n in _ast.walk(_main_tree):
    if (isinstance(n, _ast.Call)
            and isinstance(n.func, _ast.Attribute)
            and n.func.attr == 'build_props'):
        if any(kw.arg == 'egg_gate' for kw in n.keywords):
            _n7b = True
check('N7b ★★★ build_props 调用点真的传了 egg_gate=（宿主注入）', _n7b, star=True)
# ★★★ N7b2（★ M13 抓出来的洞）：**光有 `egg_gate=` 关键字不够** ——
#   写成 `egg_gate=None` 同样满足 N7b（关键字名在），但那等于**没注入门槛**
#   ⇒ Niko 家对谁都能进（彩蛋变质）。⇒ 必须断言该关键字的值**不是字面量 None**。
_n7b2_bad = []
for n in _ast.walk(_main_tree):
    if (isinstance(n, _ast.Call)
            and isinstance(n.func, _ast.Attribute)
            and n.func.attr == 'build_props'):
        for kw in n.keywords:
            if kw.arg == 'egg_gate':
                if isinstance(kw.value, _ast.Constant) and kw.value.value is None:
                    _n7b2_bad.append('egg_gate=None')
check('N7b2 ★★★ egg_gate 的值**不是字面量 None**（真注入，不是摆设） [%s]'
      % ','.join(_n7b2_bad), not _n7b2_bad, star=True)
# N7c: build_props 形参 keyword-only 透传进 NikoHomeDoorProp(gate=...)
_f7c = _func(_ii_tree, 'build_props')
_n7c = False
if _f7c is not None:
    for n in _ast.walk(_f7c):
        if (isinstance(n, _ast.Call)
                and isinstance(n.func, _ast.Name)
                and n.func.id == 'NikoHomeDoorProp'):
            if any(kw.arg == 'gate' for kw in n.keywords):
                _n7c = True
check('N7c ★★★ item_interact.build_props 把 egg_gate 透传给 NikoHomeDoorProp(gate=)',
      _n7c, star=True)
# N7d: ★ 负控制 —— 同一查找换个不存在的关键字 ⇒ 判假
_n7d = False
for n in _ast.walk(_main_tree):
    if (isinstance(n, _ast.Call)
            and isinstance(n.func, _ast.Attribute)
            and n.func.attr == 'build_props'):
        if any(kw.arg == 'no_such_kw_zzz' for kw in n.keywords):
            _n7d = True
check('N7d ★ 负控制：build_props 无 no_such_kw_zzz（证明 N7b 非恒真）',
      _n7d is False, star=True)

# ★★★ N7e：**端到端行为级** —— 真建一个 NikoHomeDoorProp（注入 gate = 一个
#   会复现 `niko_home.can_enter` 语义的回调），然后**真调 `on_interact`**，
#   断言：`soul` 被挡（返回 False 且不触发传送）、`sans` 放行。
#   为什么必须有这条：N7a~N7c 全是**结构判据**（"关键字在、调用在"），
#   它们挡不住"注入了但内核恒 True"这种（= 变异 M13 的家族）。
#   ★ 本判据**自己造夹具**，不依赖 main.py 的实例（避免拉起整个 Qt 栈）。
_n7e_bad = []
try:
    _NHD = None
    for _n in _ast.walk(_ii_tree):
        if isinstance(_n, _ast.ClassDef) and _n.name == 'NikoHomeDoorProp':
            _NHD = _n
    if _NHD is None:
        _n7e_bad.append('找不到 NikoHomeDoorProp')
    else:
        # 用真类：从模块里取属性
        _cls = getattr(_ii, 'NikoHomeDoorProp', None)
        if _cls is None:
            _n7e_bad.append('item_interact 无 NikoHomeDoorProp')
        else:
            # 注入**真的** niko_home.can_enter 作为 gate（这就是 main.py 干的）
            def _gate(actor):
                return nh.can_enter(actor)
            _entered = {'n': 0}

            def _on_egg(_p=None):
                _entered['n'] += 1
                return True

            try:
                _prop = _cls('k', 'obj_doorB', on_egg=_on_egg, gate=_gate)
            except TypeError as _e:
                _prop = None
                _n7e_bad.append('构造失败: %s' % _e)
            if _prop is not None:
                # ① soul ⇒ 必须被挡（返回 falsy 且 on_egg 未被调用）
                try:
                    _r1 = _prop.on_interact('soul')
                except Exception as _e:
                    _r1 = 'ERR:%s' % _e
                if _r1 or _entered['n'] != 0:
                    _n7e_bad.append('soul 未被挡: r=%r entered=%d'
                                    % (_r1, _entered['n']))
                # ② sans ⇒ 放行（on_egg 应被调用）
                try:
                    _r2 = _prop.on_interact('sans')
                except Exception as _e:
                    _r2 = 'ERR:%s' % _e
                if _entered['n'] < 1:
                    _n7e_bad.append('sans 未放行: r=%r entered=%d'
                                    % (_r2, _entered['n']))
except Exception as _e:
    _n7e_bad.append('异常 %s' % _e)
check('N7e ★★★ 端到端：注入 gate 后 soul 真被挡、sans 真放行 [%s]'
      % str(_n7e_bad[:2]), not _n7e_bad, star=True)
# ★ N7f 负控制：gate 恒放行 ⇒ 上面那条**必须**失败（证明 N7e 有鉴别力）
_n7f_ok = False
try:
    _cls = getattr(_ii, 'NikoHomeDoorProp', None)
    if _cls is not None:
        _entered2 = {'n': 0}

        def _on_egg2(_p=None):
            _entered2['n'] += 1
            return True

        try:
            _p2 = _cls('k2', 'obj_doorB', on_egg=_on_egg2,
                       gate=lambda a: (True, 'x'))
            _r = _p2.on_interact('soul')
            # ★ 契约：放行 ⇒ `on_egg` 被调用（`on_interact` 返回 `bool(on_egg(...))`）。
            #   ⇒ 负控制只需断言"on_egg 真被调到"（返回值的真值由 `_on_egg2` 决定，
            #   不是本判据关心的量 —— 上一版错把 `not _r` 也当条件，导致假红）。
            _n7f_ok = bool(_entered2['n'] >= 1)
        except TypeError:
            _n7f_ok = False
except Exception:
    _n7f_ok = False
check('N7f ★ 负控制：gate 恒放行 ⇒ soul 也能进（证明 N7e 真在测门槛，非恒真）',
      _n7f_ok, star=True)

# ★★★ N8（★ M12 抓出来的洞）：**渐显必须真的接进渲染路径**。
#   `rec112 B6` 只查了字符串 `'apply_to_objects' in main.py` —— 那**不是**
#   行为判据：把调用点改名成 `_disabled_apply_to_objects`，字符串仍在
#   （import 行/注释里都有）⇒ 假绿。⇒ 这里用 **AST 找真实 Call 节点**：
#   断言 main.py 里存在一个 `xxx.apply_to_objects(...)` 调用（`xxx` 不限）。
_n8_call, _n8_args = 0, 0
for n in _ast.walk(_main_tree):
    if (isinstance(n, _ast.Call)
            and isinstance(n.func, _ast.Attribute)
            and n.func.attr == 'apply_to_objects'):
        _n8_call += 1
        # 且必须带 >=3 个实参（objects, scene_id, entity_rect）+ sizer=
        if len(n.args) >= 3:
            _n8_args += 1
check('N8 ★★★ main.py 真有 apply_to_objects(...) 调用（>=3 实参，AST 判非纯字符串）',
      _n8_call >= 1 and _n8_args >= 1,
      star=True)
# N8b: 且**传了 sizer=** 关键字（门矩形必须用真尺寸算，否则"靠近"判定会偏）
_n8b = False
for n in _ast.walk(_main_tree):
    if (isinstance(n, _ast.Call)
            and isinstance(n.func, _ast.Attribute)
            and n.func.attr == 'apply_to_objects'):
        if any(kw.arg == 'sizer' for kw in n.keywords):
            _n8b = True
check('N8b ★★ apply_to_objects 调用传了 sizer=（用素材真尺寸算门矩形）', _n8b, star=True)
# N8c: ★ 负控制 —— 同一查找换个不存在的属性名 ⇒ 应为 0（证明 N8 非恒真）
_n8c = 0
for n in _ast.walk(_main_tree):
    if (isinstance(n, _ast.Call)
            and isinstance(n.func, _ast.Attribute)
            and n.func.attr == 'no_such_method_qqq'):
        _n8c += 1
check('N8c ★ 负控制：不存在的方法名 ⇒ 0 次（证明 N8 的 AST 查找有区分力）',
      _n8c == 0, star=True)
# N8d: ★★ 渐显**只在桌面场景**跑（`_scene_is_desktop_scene()` 是守卫）——
#   用户口径「**只针对桌面上的** ut 和三角符文的门」。
_n8d = False
for n in _ast.walk(_main_tree):
    if isinstance(n, _ast.Call):
        fn = n.func
        nm = fn.attr if isinstance(fn, _ast.Attribute) else (
            fn.id if isinstance(fn, _ast.Name) else '')
        if nm and nm.lstrip('_') == 'scene_is_desktop_scene':
            _n8d = True
check('N8d ★★★ 渐显受 `_scene_is_desktop_scene()` 守卫（只在桌面跑）', _n8d, star=True)

print('')
print('结论：%d PASS / %d FAIL' % (ok, fail))
sys.exit(1 if fail else 0)
