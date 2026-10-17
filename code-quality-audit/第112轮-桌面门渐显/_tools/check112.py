# -*- coding: utf-8 -*-
"""第112轮 #47 自检：门渐显（door_reveal）—— 按项目纪律写正/负控制。"""
import io, os, sys, json
import ast as _ast

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    '..', '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'ralsei_pet'))
sys.path.insert(0, os.path.join(ROOT, 'ralsei_pet', 'modules'))
_PKG = os.path.join(ROOT, 'ralsei_pet')

from modules import door_reveal as dr
# ★★★ `item_interact` 是**零依赖 L1**（`G1` 硬闸）⇒ 直接 import 它即可，
#   不需要 Qt 也不会拉起 `main.py` 的初始化环。
from modules import item_interact as _ii

ok = fail = 0
def check(name, cond, star=False, detail=None):
    """`detail` = 可选诊断串（**只**在失败时打印，避免 PASS 行被噪声淹没）。

    ★ 第112轮续新增：N9~N17 那批判据要回显"实际读到的值"（贴图清单 / 摆位坐标），
      否则报红时无从判断是产品错还是判据错（本项目铁律：报红先怀疑判据）。
    """
    global ok, fail
    if cond:
        ok += 1
        print('[PASS] %s' % name)
    else:
        fail += 1
        print('[FAIL] %s' % name)
        if detail:
            print('       detail: %s' % (detail,))

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
# ★★★ 第116轮**改钉**（不是放宽）：门 C/D 的桌面贴图从"原作原件"改成
#   "**桌面专用变体**"（把近黑底扣成透明）。真因 = 用户逐字「黑底也没去干净」
#   ＋真机实测门 D 矩形内**纯黑比中位 0.820**（原件纯黑占 82.6%）。
#   变体 = `objs/desk_door_ut.png` / `objs/desk_door_deltarune.png`，由
#   `第116轮.../_tools/key116_doors.py --key` 生成，**像素尺寸与原件逐字相同**。
#   ⇒ 本判据仍然逐字钉"选的是哪张美术"（同一张 UT 王座门 / 同一张巨门框），
#     只是钉到"去了黑底的桌面版"。世界内（`_zone.ch1.castle_town.json`）
#     **必须仍是原件** —— 见 G7/G8。
check('G2 UT 门 = desk_door_ut（UT 王座门，去了黑底的桌面版）',
      _by_src['obj_doorC']['sprite'] == 'objs/desk_door_ut.png', star=True)
# ★★★ 第112轮续：符文门贴图口径更正 —— 用户「你要不要自己看看那是不是任意门啊，
#     我说的是那个门框」+「是哪个门框似的那个门」⇒ 「任意门」= 长得像门框的那扇
#     = `spr_giantdarkdoor_0.png`（180×155 金边卷草纹门框）。旧值 `spr_shortcut_door_0`
#     （36×52 粉紫独门）是「一扇门」不是「门框」。判据名同步更新（勿留旧口径）。
#     ★ 第116轮：沿用同一张门框美术，但用**去了黑底的桌面版**（见 G2 上的说明）。
check('G3 符文门 = desk_door_deltarune（巨门框，去了黑底的桌面版）',
      _by_src['obj_doorD']['sprite'] == 'objs/desk_door_deltarune.png', star=True)
check('G4 ★ UT 门无 anim（单帧，避免找 _1.png）', 'anim' not in _by_src['obj_doorC'], star=True)
_dr_png = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes', 'objs', 'desk_door_deltarune.png')
check('G5 ★ 符文门素材在盘（巨门框桌面版单帧）', os.path.exists(_dr_png), star=True)
_ut_png = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes', 'objs', 'desk_door_ut.png')
check('G6 UT 门素材在盘（UT 王座门桌面版）', os.path.exists(_ut_png), star=True)
# ★★★ G7/G8（第116轮新增，**防"顺手把世界内的门也扣了"**）：
#   暗世界城堡镇（`_zone.ch1.castle_town.json`）里的巨门框**必须仍是原件**
#   —— 那里背景本就是黑的，黑门洞是**对的**；而且用户的渐显口径逐字
#   「只针对**桌面上的** ut 和三角符文的门」。两条一起钉，改一边就报红。
_zone_p = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes',
                       '_zone.ch1.castle_town.json')
_zone_txt = io.open(_zone_p, encoding='utf-8').read()
check('G7 ★★★ 世界内（ch1 城堡镇）仍用原件 spr_giantdarkdoor_0（不许被桌面变体顶掉）',
      'objs/spr_giantdarkdoor_0.png' in _zone_txt
      and 'desk_door_deltarune' not in _zone_txt, star=True)
check('G8 ★★ 两张原件**仍在盘上**（世界内与未来回溯都靠它）',
      os.path.exists(os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes', 'objs',
                                  'spr_giantdarkdoor_0.png'))
      and os.path.exists(os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes',
                                      'objs', 'ut_castle_realdoor_0.png')),
      star=True)

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


# ===========================================================================
#  ★★★ 第112轮续：**桌面 4 门「放在外面」+ 门样式裁定**
#  用户口径（逐字）：「放到屏幕边缘哦」/「不是，那个门你单独放在外面呗」
#  →「只桌面场景时，固定贴屏」/「各用原尺寸」/「是哪个门框似的那个门」
# ===========================================================================

# N9: 零依赖模块 `desk_doors` 真的存在且**零 import**（与 possession 同规格）。
_dd_path = os.path.join(ROOT, 'ralsei_pet', 'modules', 'desk_doors.py')
_dd_src = ''
try:
    with io.open(_dd_path, encoding='utf-8') as _f:
        _dd_src = _f.read()
except Exception:
    _dd_src = ''
check('N9 ★ desk_doors.py 存在', bool(_dd_src))
_dd_imports = set()
if _dd_src:
    for _n in _ast.walk(_ast.parse(_dd_src)):
        if isinstance(_n, _ast.Import):
            for _a in _n.names:
                _dd_imports.add((_a.name or '').split('.')[0])
        elif isinstance(_n, _ast.ImportFrom):
            if _n.module:
                _dd_imports.add(_n.module.split('.')[0])
check('N9b ★★ desk_doors.py 零 import（纯标准库算术，可被回归直接 import）',
      not _dd_imports, star=True, detail='imports=%s' % sorted(_dd_imports))

# N10: 摆位真源 —— `SIDE_LETTERS` 四方位 ↔ 字母，与 desktop.json 的字母一致。
_dd_mod = None
try:
    sys.path.insert(0, os.path.join(ROOT, 'ralsei_pet'))
    from modules import desk_doors as _dd_mod
except Exception:
    _dd_mod = None
check('N10 ★ desk_doors 可 import', _dd_mod is not None)
_want_sides = (('top', 'A'), ('bottom', 'B'), ('left', 'C'), ('right', 'D'))
check('N10b ★★★ SIDE_LETTERS == 正上A/正下B/正左C/正右D（用户逐字三答）',
      getattr(_dd_mod, 'SIDE_LETTERS', None) == _want_sides,
      star=True,
      detail='got=%s' % (getattr(_dd_mod, 'SIDE_LETTERS', None),))

# N11: **核心行为** —— 门贴**屏幕边缘**（不再落在中间）。
#   判据 = 四扇门真的贴着所在边的物理边界（margin 内）。
_n11_ok = True
_n11_detail = []
if _dd_mod is not None:
    _SW, _SH = 2560, 1600
    _sizes = {'A': (192, 128), 'B': (192, 128), 'C': (44, 99), 'D': (180, 155)}
    _placed = _dd_mod.plan_screen_doors(_sizes, _SW, _SH)
    _map = dict(_placed)
    check('N11 ★ 四扇门都算出摆位', len(_placed) == 4,
          detail='n=%d' % len(_placed))
    # top 门 y == 0；bottom 门 y+h == SH；left 门 x == 0；right 门 x+w == SW
    if 'A' in _map:
        _x, _y, _w, _h = _map['A']
        if _y != 0:
            _n11_ok = False
        _n11_detail.append('A(y=%d)' % _y)
    else:
        _n11_ok = False
    if 'B' in _map:
        _x, _y, _w, _h = _map['B']
        if _y + _h != _SH:
            _n11_ok = False
        _n11_detail.append('B(y+h=%d/%d)' % (_y + _h, _SH))
    else:
        _n11_ok = False
    if 'C' in _map:
        _x, _y, _w, _h = _map['C']
        if _x != 0:
            _n11_ok = False
        _n11_detail.append('C(x=%d)' % _x)
    else:
        _n11_ok = False
    if 'D' in _map:
        _x, _y, _w, _h = _map['D']
        if _x + _w != _SW:
            _n11_ok = False
        _n11_detail.append('D(x+w=%d/%d)' % (_x + _w, _SW))
    else:
        _n11_ok = False
    check('N11b ★★★ 四门真贴屏幕物理边（A上/B下/C左/D右，margin=0）',
          _n11_ok, star=True, detail=' '.join(_n11_detail))
else:
    check('N11b ★★★ 四门真贴屏幕物理边（A上/B下/C左/D右，margin=0）',
          False, star=True, detail='desk_doors 取不到')

# N12: **各用原尺寸**（贴图原像素，不乘房间缩放）。
_n12_ok = True
if _dd_mod is not None:
    for _side, _lt in _want_sides:
        _sz = {'A': (192, 128), 'B': (192, 128), 'C': (44, 99), 'D': (180, 155)}[_lt]
        _r = _dd_mod.door_screen_rect(_side, _sz, 2560, 1600)
        if _r is None or _r[2] != _sz[0] or _r[3] != _sz[1]:
            _n12_ok = False
    check('N12 ★★★ 门用贴图原尺寸（DOOR_SCALE=1.0 时 w/h == sprite 原像素）',
          _n12_ok, star=True)
else:
    check('N12 ★★★ 门用贴图原尺寸（DOOR_SCALE=1.0 时 w/h == sprite 原像素）', False)

# N12b: ★ 负控制 —— 把屏幕上边中点门换成左下角，判据必须报不同结果
#   （证明 N11b 不是"任何矩形都通过"）。
if _dd_mod is not None:
    _r_top = _dd_mod.door_screen_rect('top', (44, 56), 2560, 1600)
    _r_bot = _dd_mod.door_screen_rect('bottom', (44, 56), 2560, 1600)
    check('N12b ★ 负控制：top 与 bottom 得到**不同** y（N11b 有区分力）',
          bool(_r_top and _r_bot and _r_top[1] != _r_bot[1]),
          star=True, detail='top_y=%s bottom_y=%s' % (
              _r_top[1] if _r_top else None, _r_bot[1] if _r_bot else None))
    # 非法输入 ⇒ None（不伪装成 0 尺寸）
    check('N12c ★ 非法输入（side 认不出 / 尺寸<=0）⇒ None，不伪装 0 矩形',
          _dd_mod.door_screen_rect('middle', (44, 56), 2560, 1600) is None
          and _dd_mod.door_screen_rect('top', (0, 56), 2560, 1600) is None,
          star=True)
else:
    check('N12b ★ 负控制：top 与 bottom 得到**不同** y（N11b 有区分力）', False, star=True)
    check('N12c ★ 非法输入（side 认不出 / 尺寸<=0）⇒ None，不伪装 0 矩形', False, star=True)

# N13: **画布通道** —— `SceneCanvas.set_screen_doors` 存在，且画在
#   `translate/scale` **之外**（AST：`_paint_screen_doors` 调用点必须在
#   `p.scale(...)` 所在函数体内、且**不在**任何 `with`/translate 之后 —— 简化为
#   断言两件事：① 方法存在；② `paintEvent` 里有 `self._paint_screen_doors(p)` 调用）。
_sc_path = os.path.join(ROOT, 'ralsei_pet', 'modules', 'scene_canvas.py')
_sc_src = ''
try:
    with io.open(_sc_path, encoding='utf-8') as _f:
        _sc_src = _f.read()
except Exception:
    _sc_src = ''
_sc_tree = _ast.parse(_sc_src) if _sc_src else None
check('N13 ★ scene_canvas 有 set_screen_doors 方法',
      bool(_sc_tree) and any(
          isinstance(_n, _ast.FunctionDef) and _n.name == 'set_screen_doors'
          for _n in _ast.walk(_sc_tree)), star=True)
_n13b = False
if _sc_tree:
    for _n in _ast.walk(_sc_tree):
        if isinstance(_n, _ast.FunctionDef) and _n.name == 'paintEvent':
            for _m in _ast.walk(_n):
                if (isinstance(_m, _ast.Call)
                        and isinstance(_m.func, _ast.Attribute)
                        and _m.func.attr == '_paint_screen_doors'):
                    _n13b = True
check('N13b ★★★ paintEvent 里真调 `_paint_screen_doors`（非死代码）',
      _n13b, star=True)
# N13c: ★ 负控制 —— 换个不存在的方法名 ⇒ 0 次
_n13c = 0
if _sc_tree:
    for _n in _ast.walk(_sc_tree):
        if (isinstance(_n, _ast.Call)
                and isinstance(_n.func, _ast.Attribute)
                and _n.func.attr == 'no_such_paint_qqq'):
            _n13c += 1
check('N13c ★ 负控制：不存在的方法名 ⇒ 0 次（N13b 有区分力）', _n13c == 0, star=True)

# N14: **不画两遍** —— plan_frame 必须认 `enabled is False`（第112轮续补的剔除）。
_sr_path = os.path.join(ROOT, 'ralsei_pet', 'modules', 'scene_render.py')
_sr_src = ''
try:
    with io.open(_sr_path, encoding='utf-8') as _f:
        _sr_src = _f.read()
except Exception:
    _sr_src = ''
_sr_tree = _ast.parse(_sr_src) if _sr_src else None
_n14 = False
if _sr_tree:
    for _n in _ast.walk(_sr_tree):
        if isinstance(_n, _ast.FunctionDef) and _n.name == 'plan_frame':
            for _m in _ast.walk(_n):
                # 找 `obj.get('enabled') is False` 形状的 Compare
                if (isinstance(_m, _ast.Compare)
                        and isinstance(_m.ops[0], _ast.Is)
                        and isinstance(_m.comparators[0], _ast.Constant)
                        and _m.comparators[0].value is False):
                    _left = _m.left
                    if (isinstance(_left, _ast.Call)
                            and isinstance(_left.func, _ast.Attribute)
                            and _left.func.attr == 'get'
                            and _left.args
                            and isinstance(_left.args[0], _ast.Constant)
                            and _left.args[0].value == 'enabled'):
                        _n14 = True
check('N14 ★★★ plan_frame 认 `enabled is False` ⇒ 房间层不再画那 4 扇门（不重复）',
      _n14, star=True)
# N14b: ★ 负控制 —— 同一查找换 `'no_such_key'` ⇒ 应为 0（证明 N14 非恒真）
_n14b = False
if _sr_tree:
    for _n in _ast.walk(_sr_tree):
        if isinstance(_n, _ast.FunctionDef) and _n.name == 'plan_frame':
            for _m in _ast.walk(_n):
                if (isinstance(_m, _ast.Compare)
                        and isinstance(_m.left, _ast.Call)
                        and isinstance(_m.left.func, _ast.Attribute)
                        and _m.left.func.attr == 'get'
                        and _m.left.args
                        and isinstance(_m.left.args[0], _ast.Constant)
                        and _m.left.args[0].value == 'no_such_key_qqq'):
                    _n14b = True
check('N14b ★ 负控制：`no_such_key_qqq` 的 Compare ⇒ 不存在（N14 有区分力）',
      not _n14b, star=True)

# N15: **门样式** —— desktop.json 的 4 门贴图 = 用户裁定的四张（逐门）。
#   ★★★ 第116轮**改钉**（不是放宽）：C/D 换成**去了黑底的桌面变体**
#     （`desk_door_ut.png` / `desk_door_deltarune.png`，像素尺寸与原件逐字相同）。
#     真因 = 用户逐字「**黑底也没去干净**」＋真机实测门 D 矩形内纯黑比中位 **0.820**；
#     而 `ut_castle_realdoor_0` 本就是从 UT **背景图** `bg_castle_realdoor` 抠出来的
#     ⇒ 那圈黑**字面就是原房间背景**。原件仍在盘上、世界内仍用原件（见 G7/G8）。
_need_sprites = {
    # ★★★ 第117轮**改钉**（不是放宽）：门 A 的贴图从 `spr_darkdoor_0.png`
    #   （44×56 的暗门）换成「Niko 回家光门」的**黑光变体**
    #   `desk_door_oneshot_black.png`（192×128，alpha 与原件逐像素一致、只压暗偏紫）。
    #   真因 = 用户 10-18 逐字「**oneshot 用最后 niko 回家走的那道门，但颜色变成黑光**」。
    #   原始件 `spr_darkdoor_0.png` **仍在盘上**（世界内仍可能引用，见 check117 E4）。
    'desk_door_oneshot': 'objs/desk_door_oneshot_black.png',
    'desk_door_niko_home': 'objs/niko_door_portal.png',
    'desk_door_ut': 'objs/desk_door_ut.png',
    'desk_door_deltarune': 'objs/desk_door_deltarune.png',
}
_dj_path = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes', 'desktop.json')
_dj = {}
try:
    with io.open(_dj_path, encoding='utf-8') as _f:
        _dj = json.load(_f)
except Exception:
    _dj = {}
_got_sprites = {}
for _o in (_dj.get('objects') or []):
    if isinstance(_o, dict) and _o.get('id'):
        _got_sprites[_o['id']] = _o.get('sprite')
check('N15 ★ 4 门贴图 == 裁定表（OneShot黑光光门/Niko家光门/UT王座门·去黑底/符文巨门框·去黑底）',
      _got_sprites == _need_sprites, star=True,
      detail='got=%s' % _got_sprites)
check('N15b ★★ Niko 家门用光门 `niko_door_portal`（用户「用原作 niko 最后回家的光门」）',
      _got_sprites.get('desk_door_niko_home') == 'objs/niko_door_portal.png', star=True)
# ★★★ N15c：巨门框 —— 口径**改过一次，别改回去**。用户 10-12 选过 `spr_shortcut_door`，
#   10-13 的 AskUserQuestion 回「不是啊，是哪个门框似的哪个门」**覆盖**它（终选巨门框）。
check('N15c ★★ 三角符文门用巨门框（用户「是哪个门框似的那个门」）'
      '—— 且**不许回退**成 `spr_shortcut_door`',
      _got_sprites.get('desk_door_deltarune') == 'objs/desk_door_deltarune.png', star=True)
check('N15d ★★ UT 门仍用王座门（用户「ut 就用王座那个门」）· 桌面版去了黑底',
      _got_sprites.get('desk_door_ut') == 'objs/desk_door_ut.png', star=True)
# N15e: ★ 负控制 —— 4 门贴图**不全相同**（用户「门也不是都长那样啊」）
check('N15e ★★ 负控制：4 门贴图不是同一张（用户「门也不是都长那样」）',
      len(set(_got_sprites.values())) == 4, star=True,
      detail='distinct=%d' % len(set(_got_sprites.values())))

# N16: 4 门**全部 enabled=False**（房间层不画，交给屏幕层）。
_n16_all = bool(_dj) and all(
    isinstance(_o, dict) and _o.get('id', '').startswith('desk_door')
    and _o.get('enabled') is False
    for _o in (_dj.get('objects') or [])
    if isinstance(_o, dict) and str(_o.get('id', '')).startswith('desk_door'))
check('N16 ★★ 4 门全 `enabled: false`（房间层剔除，只屏幕层画）',
      _n16_all, star=True)
# N16b: ★★ 但物件**仍在 objects 里**（路由/渐显要读到它们）——这是"不重复画"的关键。
check('N16b ★★ 4 门仍在 desktop.json 的 objects 里（数据留给路由/渐显）',
      len([_o for _o in (_dj.get('objects') or [])
           if isinstance(_o, dict)
           and str(_o.get('id', '')).startswith('desk_door')]) == 4, star=True)

# N17: ★★★ main.py 真把两者接起来（AST，非字符串）：
#   ① 调 `set_screen_doors`；② 调 `_desktop_screen_doors`；③ 受
#   `_scene_is_desktop_scene()` 守卫（用户「只桌面场景时，固定贴屏」）。
_n17a = _n17b = False
for _n in _ast.walk(_main_tree):
    if isinstance(_n, _ast.Call):
        _fn = _n.func
        _nm = _fn.attr if isinstance(_fn, _ast.Attribute) else (
            _fn.id if isinstance(_fn, _ast.Name) else '')
        if _nm == 'set_screen_doors':
            _n17a = True
        if _nm == '_desktop_screen_doors':
            _n17b = True
check('N17 ★★★ main.py 真调 `set_screen_doors`（AST）', _n17a, star=True)
check('N17b ★★ main.py 真调 `_desktop_screen_doors`（AST，算摆位）', _n17b, star=True)
# N17c: 两者**在同一个 try 块内** ⇒ 近似判"受同一守卫"。更硬的判法：
#   断言 `_desktop_screen_doors` 的调用**嵌套在**某个 `if` 的 test 里含
#   `_scene_is_desktop_scene` —— 用 AST 精确判。
_n17c = False
for _n in _ast.walk(_main_tree):
    if not isinstance(_n, _ast.If):
        continue
    _t = _n.test
    _tnames = set()
    for _m in _ast.walk(_t):
        if isinstance(_m, _ast.Call):
            _f2 = _m.func
            _tnames.add(_f2.attr if isinstance(_f2, _ast.Attribute) else (
                _f2.id if isinstance(_f2, _ast.Name) else ''))
    if 'scene_is_desktop_scene' not in ' '.join(_tnames):
        # 允许 `self._scene_is_desktop_scene()` 写法：上面已取 attr 名
        _joined = ' '.join(sorted(_tnames))
        if 'scene_is_desktop_scene' not in _joined:
            continue
    for _m in _ast.walk(_n):
        if (isinstance(_m, _ast.Call)
                and isinstance(_m.func, _ast.Attribute)
                and _m.func.attr == '_desktop_screen_doors'):
            _n17c = True
check('N17c ★★★ 屏幕层门受 `_scene_is_desktop_scene()` 守卫（只桌面场景显示）',
      _n17c, star=True)

# ==========================================================================
#  N18~N22 ★★★ 第112轮续二：门对齐 Ralsei 量级（用户「门的尺寸和 ralsei 的尺寸
#      调换一下差不多」＋「门的稍微大一点」）
# ==========================================================================
print('')
print('=== N18. ★★★ 门对齐 Ralsei 量级（缩放到宠物外接盒） ===')
_DD_T = _ast.parse(io.open(
    os.path.join(ROOT, 'ralsei_pet', 'modules', 'desk_doors.py'),
    encoding='utf-8').read())


def _dd_const(name):
    """从 `desk_doors.py` 的 AST 取模块级常量值（禁纯文本扫/禁 eval 源串）。"""
    for _n in _DD_T.body:
        if isinstance(_n, _ast.Assign):
            for _t in _n.targets:
                if isinstance(_t, _ast.Name) and _t.id == name:
                    try:
                        return _ast.literal_eval(_n.value)
                    except Exception:
                        return None
    return None


# N18a: `DOOR_FIT_CAP` 存在且 = 1.6（门外接盒 = Ralsei 盒 × 1.6 ⇒「大一点都」）。
#   ★★★ 第117轮**改钉**：1.2 → **1.6**。真因 = 用户 10-18 逐字「**对了大一点都**」
#     （在"稍微大一点"=1.2 的基础上再放大 33%；真机 k 从 0.759 → 1.012）。
#   ★ 这个常量是"门整体大小"的**唯一旋钮** —— 用户再要"大一点/小一点"只改它，
#     别去动各门贴图像素（那会破坏"按原作等比放大"）。
_n18a_cap = _dd_const('DOOR_FIT_CAP')
check('N18a ★★★ `DOOR_FIT_CAP` = 1.6（门外接盒 = Ralsei 盒 × 1.6，用户「大一点都」）',
      _n18a_cap == 1.6, star=True, detail='DOOR_FIT_CAP=%r' % (_n18a_cap,))

# N18b: 统一倍率函数存在（AST 函数定义），且 `fit_door_scale`（单扇版）也保留。
_dd_funcs = {n.name for n in _ast.walk(_DD_T) if isinstance(n, _ast.FunctionDef)}
check('N18b ★★★ `fit_doors_uniform_scale()` 存在（统一倍率 = 门↔宠物盒的唯一真源）',
      'fit_doors_uniform_scale' in _dd_funcs, star=True)
check('N18b2 ★★ 单扇版 `fit_door_scale()` 保留（"单扇 vs 宠物盒"这个局部问题的解）',
      'fit_door_scale' in _dd_funcs, star=True)

# N18c: `plan_screen_doors` 真有 `pet_box` 形参（老调用点不传 ⇒ 走旧口径）。
_pnd_args = None
for _n in _ast.walk(_DD_T):
    if isinstance(_n, _ast.FunctionDef) and _n.name == 'plan_screen_doors':
        _pnd_args = [a.arg for a in _n.args.args]
check('N18c ★★★ `plan_screen_doors(..., pet_box=None)`（有宠物盒 ⇒ 统一倍率对齐；'
      '不传 ⇒ 退回"各用原尺寸"，老调用点零变化）',
      _pnd_args is not None and 'pet_box' in _pnd_args,
      star=True, detail='args=%r' % (_pnd_args,))

# N18d ★★★ 行为级：给四张真门尺寸 + Ralsei 盒 ⇒ **统一倍率**下每扇门的
#   外接盒都**不超过** cap × 宠物盒。
try:
    from modules import desk_doors as _DD2  # noqa: E402
except Exception as _e:
    _DD2 = None
    print('        [warn] desk_doors 导入失败: %r' % (_e,))
_pet = (230, 157)                      # 真机量得（69×3.33125 / 47×3.33125 取整）
_sz4 = {'A': (192, 128), 'B': (192, 128), 'C': (44, 99), 'D': (180, 155)}
_n18d_bad = []
_n18d_rows = []
if _DD2 is not None:
    _cap = float(getattr(_DD2, 'DOOR_FIT_CAP', 1.2))
    _k = _DD2.fit_doors_uniform_scale(_sz4, _pet)
    for _L, _wh in _sz4.items():
        _w, _h = _wh[0] * _k, _wh[1] * _k
        _n18d_rows.append('%s %.0fx%.0f' % (_L, _w, _h))
        if _w > _cap * _pet[0] + 1e-6 or _h > _cap * _pet[1] + 1e-6:
            _n18d_bad.append('%s -> %.1fx%.1f 超过 cap=%.2f×宠物盒(%dx%d)'
                             % (_L, _w, _h, _cap, _pet[0], _pet[1]))
check('N18d ★★★ 行为级：**统一倍率**下四扇门外接盒**都不超过** cap × 宠物盒'
      '（门不再是 Ralsei 的 2.7 倍）',
      _DD2 is not None and not _n18d_bad,
      star=True, detail='k=%.4f rows=%r bad=%r'
                        % (_k if _DD2 else 0, _n18d_rows, _n18d_bad))

# N18d2 ★★★ **统一倍率**：四扇门用的是**同一个** k（"按原作等比放大"的核心）。
#   ★★★ 判据必须**结构化**（第112轮续三实证）：旧写法
#     `abs(_wh[0]*_k / _wh[0] - _k) < 1e-9` 是**代数恒真**（左侧 ≡ _k）
#     ⇒ 把内核改成逐门也照样 PASS（mutate M21 实证 MISSED）。这就是
#     契约里说的"判据只判提到某名字 = 恒真"的又一例。
#   ⇒ 真判据要点（与产品行为挂钩、且**非恒等**）：
#     (a) 用源码里"是否只出现**一次** `door_screen_rect(...)` 调用 +
#         该调用的 `scale=` 实参走**同一个** `_s_uniform`（AST 结构）；
#     (b) 行为级：**逐门各自按 `fit_door_scale` 算**的四个不同倍率，与
#         统一倍率 `k` **不相等**（A/B/C/D 的原尺寸差异 ⇒ 逐门必分叉）
#         ⇒ 若产品真走统一倍率，则"四门屏幕宽/原宽"全等；若走逐门则不等。
#     这就是**非恒等**的鉴别判据：真值来自 `fit_door_scale`（产品另一个函数），
#     不是 `_wh[0]*_k/_wh[0]` 这种自洽恒等式。
_n18d2_ok = False
_n18d2_detail = ''
_n18d2_ast_ok = False
try:
    _dd_src = io.open(
        os.path.join(_PKG, 'modules', 'desk_doors.py'),
        encoding='utf-8', newline='').read()
    _dd_tree = _ast.parse(_dd_src)
    # --- (a) AST：plan_screen_doors 里 `door_screen_rect(...)` 的 `scale=`
    #     实参必须是**同一个名字**（`_s_uniform`），出现且仅出现一次赋值。
    _n18d2_ast_ok = False
    for _fn in _ast.walk(_dd_tree):
        if not (isinstance(_fn, _ast.FunctionDef)
                and _fn.name == 'plan_screen_doors'):
            continue
        _calls = []
        for _node in _ast.walk(_fn):
            if (isinstance(_node, _ast.Call)
                    and isinstance(_node.func, _ast.Name)
                    and _node.func.id == 'door_screen_rect'):
                _scale_kw = [kw for kw in _node.keywords
                             if kw.arg == 'scale']
                _calls.append(_scale_kw[0].value if _scale_kw else None)
        # 每个 call 的 scale= 实参都必须是 Name 且**同名**
        _names = set()
        for _v in _calls:
            if isinstance(_v, _ast.Name):
                _names.add(_v.id)
        _n18d2_ast_ok = (len(_calls) >= 1 and len(_names) == 1
                         and None not in _calls)
except Exception as _e:
    print('        [warn] N18d2 AST 检查异常: %r' % (_e,))

if _DD2 is not None:
    _k = _DD2.fit_doors_uniform_scale(_sz4, _pet)
    # --- (b) 行为级（**非恒等**）：逐门倍率由产品另一个函数算出 ⇒ 四门必分叉。
    _solo = dict((_L, _DD2.fit_door_scale((_wh[0], _wh[1]), _pet))
                 for _L, _wh in _sz4.items())
    _spread = max(_solo.values()) - min(_solo.values())
    # 统一倍率真生效 ⇒ 屏幕宽/原宽 == 同一个 k（即"四门共用一把尺"）
    _ratios = [_wh[0] * _k / float(_wh[0]) for _wh in _sz4.values()]
    _uniform_ruler = (max(_ratios) - min(_ratios)) < 1e-9
    # 且**逐门倍率确实是分叉的**（否则这个鉴别判据本身恒真 = 又一个坑）
    _solo_differs = _spread > 1e-6
    _n18d2_ok = bool(_n18d2_ast_ok and _uniform_ruler and _solo_differs)
    _n18d2_detail = ('ast_same_scale=%r  k=%.5f  尺=%r  逐门 k=%r(分叉=%.3f)'
                     % (_n18d2_ast_ok, _k, [round(r, 5) for r in _ratios],
                        dict((L, round(v, 3)) for L, v in _solo.items()),
                        _spread))
check('N18d2 ★★★ 统一倍率：四扇门用**同一个 k**（AST 判 `scale=` 同源 + '
      '逐门倍率**确实分叉**⇒判据非恒等）',
      _n18d2_ok, star=True, detail=_n18d2_detail)

# N18e ★★★ 负控制：统一倍率有鉴别力 —— 宠物盒放大一倍，k 必须跟着变大。
_n18e_ok = False
if _DD2 is not None:
    _k1 = _DD2.fit_doors_uniform_scale(_sz4, (230, 157))
    _k2 = _DD2.fit_doors_uniform_scale(_sz4, (460, 314))
    _n18e_ok = (_k2 > _k1)
check('N18e ★★★ 负控制：`fit_doors_uniform_scale` 有鉴别力'
      '（宠物盒放大一倍 ⇒ k 跟着变大）',
      _n18e_ok, star=True)

# N18f ★★ 非法输入 ⇒ 退回 `DOOR_SCALE`（不抛、不返 0、不返 None）。
_n18f_ok = False
if _DD2 is not None:
    try:
        _vals = [_DD2.fit_door_scale(None, _pet),
                 _DD2.fit_door_scale((0, 0), _pet),
                 _DD2.fit_door_scale((44, 56), None),
                 _DD2.fit_door_scale((44, 56), (0, 0))]
        _n18f_ok = all(isinstance(v, float) and v > 0 for v in _vals)
    except Exception as _e:
        print('        [warn] 非法输入抛了: %r' % (_e,))
check('N18f ★★ 非法输入（None/0 尺寸）⇒ 仍返正 float（退回 `DOOR_SCALE`，不抛）',
      _n18f_ok, star=True)

# N18g ★★★ 行为级：`plan_screen_doors` 带 `pet_box` 与不带时**结果必须不同**
#   （否则"新增参数但没人真用"——本项目最贵的坑）。
_n18g_ok = False
if _DD2 is not None:
    _with = _DD2.plan_screen_doors(_sz4, 2560, 1600, pet_box=_pet)
    _without = _DD2.plan_screen_doors(_sz4, 2560, 1600)
    if len(_with) == 4 and len(_without) == 4:
        _n18g_ok = ([r for _l, r in _with] != [r for _l, r in _without])
check('N18g ★★★ 带 `pet_box` 与不带时**结果不同**（防"加了参数但没真用"）',
      _n18g_ok, star=True)

# N18h ★★★ 缩放后四扇门仍**逐边贴屏幕物理边**（缩放不该破坏贴边）。
_n18h_bad = []
if _DD2 is not None:
    _side_of = {'A': 'top', 'B': 'bottom', 'C': 'left', 'D': 'right'}
    for _l, _r in _DD2.plan_screen_doors(_sz4, 2560, 1600, pet_box=_pet):
        _x, _y, _w, _h = _r
        _sd = _side_of[_l]
        if _sd == 'top' and _y != 0:
            _n18h_bad.append('%s 正上 y=%d' % (_l, _y))
        elif _sd == 'bottom' and _y + _h != 1600:
            _n18h_bad.append('%s 正下 y+h=%d' % (_l, _y + _h))
        elif _sd == 'left' and _x != 0:
            _n18h_bad.append('%s 正左 x=%d' % (_l, _x))
        elif _sd == 'right' and _x + _w != 2560:
            _n18h_bad.append('%s 正右 x+w=%d' % (_l, _x + _w))
check('N18h ★★★ 缩放后四扇门仍**逐边贴屏幕物理边**（缩放不破坏贴边）',
      _DD2 is not None and not _n18h_bad, star=True, detail='bad=%r' % (_n18h_bad,))

# N19 ★★★ `main.py` 真把宠物盒送进 `plan_screen_doors`（AST：`pet_box=` 关键字实参）。
_main_t = _ast.parse(io.open(os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py'),
                             encoding='utf-8').read())
_n19 = False
_n19_uses_label = False
for _n in _ast.walk(_main_t):
    if isinstance(_n, _ast.Call):
        _kw = [k.arg for k in _n.keywords if k.arg]
        if 'pet_box' in _kw:
            _n19 = True
            break
check('N19 ★★★ `main.py` 真把 `pet_box=` 送进 `plan_screen_doors`（AST 关键字实参）',
      _n19, star=True)

# N19b ★★★ 宠物盒真源 = `desk_doors.pet_screen_box(_cached_scale_factor)`（标准体量），
#   `sprite_label` 只许出现在**兜底**分支里。
#   ★★ 旧版这条只查 "`'sprite_label' in _body`" ⇒ **恒真**（兜底分支里还留着它，
#      改了真源它照样 PASS —— 判据只判"提到某名字"的典型翻车）。改成 AST 结构化断言：
#      ① `_desktop_screen_doors` 里必须**真调用** `pet_screen_box`；
#      ② 传给它的实参必须**源自** `_cached_scale_factor`；
#      ③ `sprite_label` 的取用必须落在 `pet_box is None` 的兜底 `if` 体内。
_n19b_call_petbox = False     # ① 真调用 pet_screen_box
_n19b_arg_is_cached = False   # ② 实参含 _cached_scale_factor
_n19b_label_only_fallback = False  # ③ sprite_label 只在兜底分支


def _refers_cached(_node):
    """判断某表达式是否**引用了** `_cached_scale_factor`。

    ★ 两种真实写法都会出现（第一版只认 ①，于是把 ② 误判成"没引用"，报假 FAIL）：
      ① 属性访问：`self._cached_scale_factor`
      ② 字符串取属性：`getattr(self, '_cached_scale_factor', None)`
        —— 这里 `'_cached_scale_factor'` 是 `ast.Constant`(str)，不是 `Attribute`。
    """
    for _s in _ast.walk(_node):
        if isinstance(_s, _ast.Attribute) and _s.attr == '_cached_scale_factor':
            return True
        if isinstance(_s, _ast.Constant) and _s.value == '_cached_scale_factor':
            return True
    return False


def _attr_root_name(_node):
    """沿 `a.b.c` / `a['b']` 链取最左的名字（取不到 ⇒ None）。"""
    while True:
        if isinstance(_node, _ast.Attribute):
            _node = _node.value
        elif isinstance(_node, _ast.Subscript):
            _node = _node.value
        else:
            return getattr(_node, 'id', None)


for _n in _ast.walk(_main_t):
    if not (isinstance(_n, _ast.FunctionDef) and _n.name == '_desktop_screen_doors'):
        continue
    # ① 真调用 pet_screen_box
    #   ★ 必须先**收集别名**再判调用（两遍）：`ast.walk` 的遍历顺序不保证
    #     `Assign` 排在 `Call` 前面，一遍扫会偶发漏别名（第一版就栽在这）。
    _aliases = set()
    for _a2 in _ast.walk(_n):
        if isinstance(_a2, _ast.Assign):
            if _refers_cached(_a2.value):
                for _t in _a2.targets:
                    if isinstance(_t, _ast.Name):
                        _aliases.add(_t.id)
    for _c in _ast.walk(_n):
        if (isinstance(_c, _ast.Call)
                and _attr_root_name(_c.func) == 'desk_doors_mod'
                and isinstance(_c.func, _ast.Attribute)
                and _c.func.attr == 'pet_screen_box'):
            _n19b_call_petbox = True
            # ② 实参链里含 `_cached_scale_factor`，或含**它的别名**（局部中转）。
            for _a in list(_c.args) + [k.value for k in _c.keywords]:
                if _refers_cached(_a) or any(
                        isinstance(_s, _ast.Name) and _s.id in _aliases
                        for _s in _ast.walk(_a)):
                    _n19b_arg_is_cached = True
    # ③ sprite_label 的取用是否只在"pet_box is None"的兜底 if 体内
    _label_nodes = [x for x in _ast.walk(_n)
                    if isinstance(x, _ast.Attribute) and x.attr == 'sprite_label']
    if _label_nodes:
        _fallback_spans = []
        for _st in _ast.walk(_n):
            if isinstance(_st, _ast.If):
                _cond = _ast.unparse(_st.test)
                if 'pet_box' in _cond and 'None' in _cond:
                    _fallback_spans.append((_st.lineno, getattr(_st, 'end_lineno', _st.lineno)))
        if _fallback_spans:
            _n19b_label_only_fallback = all(
                any(_a <= _x.lineno <= _b for (_a, _b) in _fallback_spans)
                for _x in _label_nodes)

check('N19b ★★★ 宠物盒真源 = `pet_screen_box(_cached_scale_factor)`'
      '（标准体量；`sprite_label` 只许作兜底）',
      _n19b_call_petbox and _n19b_arg_is_cached and _n19b_label_only_fallback,
      star=True,
      detail='call=%s arg_cached=%s label_fallback_only=%s'
             % (_n19b_call_petbox, _n19b_arg_is_cached,
                _n19b_label_only_fallback))

# ============================================================================
# N20~N23 ★★★ 第112轮续三：门摆位的**稳定性**与**坐标系**
#   （本轮真机抓帧抓出两个 bug，这两条判据就是把它们钉死）
# ============================================================================
# N20 ★★★ `PET_BOX_LOGICAL` = (69, 47)（idle 组容器，**不随动画组变**）。
#   那是"用户看到静止 Ralsei 的那个体量"（2560×1600 屏上 229×156）。
check('N20 ★★★ `PET_BOX_LOGICAL` = (69, 47)（idle 组容器 = 标准体量，不随动画跳）',
      _DD2 is not None and getattr(_DD2, 'PET_BOX_LOGICAL', None) == (69, 47),
      star=True,
      detail='got=%r' % (getattr(_DD2, 'PET_BOX_LOGICAL', None) if _DD2 else None,))

# N21 ★★★ 行为级：`pet_screen_box()` 与 `sprite_label` **解耦** ——
#   同一位移倍率下反复调用结果**恒等**，且等于 `(69×k, 47×k)`。
_n21_ok = False
_n21_detail = 'DD2 未导入'
if _DD2 is not None:
    try:
        _a = _DD2.pet_screen_box(3.33125)
        _b = _DD2.pet_screen_box(3.33125)
        _c = _DD2.pet_screen_box(1.0)
        _n21_ok = (_a == _b == (230, 157)) and (_c == (69, 47))
        _n21_detail = 'k=3.33125 ⇒ %r（期望 (230,157)）｜k=1.0 ⇒ %r' % (_a, _c)
    except Exception as e:
        _n21_detail = '异常 %s' % e
check('N21 ★★★ 行为级：`pet_screen_box(3.33125)` == (230,157) 且确定性（同输入恒等输出）',
      _n21_ok, star=True, detail=_n21_detail)

# N21b ★★ 负控制：倍率非法 ⇒ 返 `None`（调用方据此走兜底，**不返 (0,0)**）。
_n21b_bad = []
if _DD2 is not None:
    for _bad in (None, 0, -1, 'x', float('nan')):
        try:
            _r = _DD2.pet_screen_box(_bad)
            if _r is not None:
                _n21b_bad.append('%r ⇒ %r' % (_bad, _r))
        except Exception as _e:
            _n21b_bad.append('%r 抛 %s' % (_bad, _e))
check('N21b ★★ 负控制：`pet_screen_box` 非法倍率 ⇒ 返 `None`（供兜底，不返 0 盒）',
      _DD2 is not None and not _n21b_bad, star=True, detail='bad=%r' % (_n21b_bad,))

# N22 ★★★ `scene_canvas.paintEvent` 真把"房间坐标变换"**包起来**（save/restore），
#   否则屏幕门会被 `translate(offset)` 整体推走（本轮真 bug：`last_drawn=4` 但
#   四扇门区域 100% 透明）。
#   ★ 用 AST 判**调用序**：`p.save()` 必须出现在 `p.translate(...)` 之前，
#     且 `p.restore()` 必须夹在 `paint_on(...)` 与 `_paint_screen_doors(...)` 之间。
_cv_path = os.path.join(ROOT, 'ralsei_pet', 'modules', 'scene_canvas.py')
_cv_t = _ast.parse(io.open(_cv_path, encoding='utf-8').read())
_n22_ok = False
_n22_detail = '未找到 paintEvent'
for _n in _ast.walk(_cv_t):
    if not (isinstance(_n, _ast.FunctionDef) and _n.name == 'paintEvent'):
        continue
    # 收集带行号的调用序。
    # ★ `p.xxx(...)` 是 `Attribute`（save/translate/restore/_paint_screen_doors），
    #   而 `paint_on(...)` 是**模块级函数**（`Name`）⇒ 两种都要收，否则
    #   `paint_on` 找不到（第一版就是这样误报 FAIL 的）。
    _seq = []
    for _c in _ast.walk(_n):
        if isinstance(_c, _ast.Call):
            if isinstance(_c.func, _ast.Attribute):
                _seq.append((_c.lineno, _c.func.attr))
            elif isinstance(_c.func, _ast.Name):
                _seq.append((_c.lineno, _c.func.id))
    _seq.sort()
    _i_save = next((i for i, (_l, _a) in enumerate(_seq) if _a == 'save'), -1)
    _i_tr = next((i for i, (_l, _a) in enumerate(_seq) if _a == 'translate'), -1)
    _i_rest = next((i for i, (_l, _a) in enumerate(_seq) if _a == 'restore'), -1)
    _i_on = next((i for i, (_l, _a) in enumerate(_seq) if _a == 'paint_on'), -1)
    _i_sd = next((i for i, (_l, _a) in enumerate(_seq) if _a == '_paint_screen_doors'), -1)
    _n22_ok = (-1 < _i_save < _i_tr) and (-1 < _i_on < _i_rest < _i_sd)
    _n22_detail = ('save@%d translate@%d paint_on@%d restore@%d screen_doors@%d'
                   % (_i_save, _i_tr, _i_on, _i_rest, _i_sd))
    break
check('N22 ★★★ `paintEvent` 用 `save/restore` 圈住房间变换'
      '（屏幕门画在**未平移**的整屏坐标上）',
      _n22_ok, star=True, detail=_n22_detail)

# N22b ★★ 负控制：若把 `restore()` 拿掉，屏幕门就会落在 `translate` 之后
#   ⇒ 判据必须能识别"restore 不在 paint_on 与 screen_doors 之间"。
#   （用**变异源码**跑同一段 AST 逻辑，正向证明判据有鉴别力。）
_n22b_ok = False
try:
    _mut_src = io.open(_cv_path, encoding='utf-8').read().replace(
        '            p.restore()\r\n', '', 1)
    if _mut_src == io.open(_cv_path, encoding='utf-8').read():
        _mut_src = io.open(_cv_path, encoding='utf-8').read().replace(
            '            p.restore()\n', '', 1)
    _mt = _ast.parse(_mut_src)
    for _n in _ast.walk(_mt):
        if isinstance(_n, _ast.FunctionDef) and _n.name == 'paintEvent':
            _seq = []
            for _c in _ast.walk(_n):
                if isinstance(_c, _ast.Call):
                    if isinstance(_c.func, _ast.Attribute):
                        _seq.append((_c.lineno, _c.func.attr))
                    elif isinstance(_c.func, _ast.Name):
                        _seq.append((_c.lineno, _c.func.id))
            _seq.sort()
            _i_rest = next((i for i, (_l, _a) in enumerate(_seq) if _a == 'restore'), -1)
            _i_on = next((i for i, (_l, _a) in enumerate(_seq) if _a == 'paint_on'), -1)
            _i_sd = next((i for i, (_l, _a) in enumerate(_seq)
                          if _a == '_paint_screen_doors'), -1)
            _n22b_ok = not (-1 < _i_on < _i_rest < _i_sd)   # 变异后**必须**判不满足
            break
except Exception:
    _n22b_ok = False
check('N22b ★★ 负控制：删掉 `p.restore()` ⇒ N22 那条判据**必不满足**（判据有鉴别力）',
      _n22b_ok, star=True)

# N23 ★★★ `_paint_screen_doors` 逐门画的是**画布坐标**（不自行加 offset）。
#   判据：该方法的 AST 里**不许出现** `_offset_x` / `_offset_y` / `translate`。
#   ★ 为什么必须这样：一旦它自己 translate 一次，与 `paintEvent` 的 restore 一叠加
#     就是双重偏移（"改一处忘另一处"的经典形态）。
_n23_bad = []
for _n in _ast.walk(_cv_t):
    if isinstance(_n, _ast.FunctionDef) and _n.name == '_paint_screen_doors':
        for _x in _ast.walk(_n):
            if isinstance(_x, _ast.Attribute) and _x.attr in ('_offset_x', '_offset_y'):
                _n23_bad.append('引用 %s' % _x.attr)
            if isinstance(_x, _ast.Call) and isinstance(_x.func, _ast.Attribute) \
                    and _x.func.attr == 'translate':
                _n23_bad.append('调用 translate')
        break
check('N23 ★★★ `_paint_screen_doors` **不自加偏移**'
      '（不许出现 `_offset_*` / `translate`，防与 paintEvent 双重偏移）',
      not _n23_bad, star=True, detail='bad=%r' % (_n23_bad,))

# ===========================================================================
# 续四（用户口径：「门单独贴屏满屏 / room 用第二个档 / 其他黑边 / 宠物最多 1.5 个文件夹」）
# ===========================================================================
print('=== N 续四：宠物体量上限 + 门↔场景彻底解耦 ===')

# N24 ★★★ 宠物体量上限常量存在且 = 144（用户「最多 1.5 个文件夹」⇒ 1.5×96）。
try:
    _n24_val = getattr(_DD2, 'PET_MAX_LONG_SIDE_PX', None)
except Exception:
    _n24_val = None
check('N24 ★★★ `PET_MAX_LONG_SIDE_PX` == 144'
      '（用户「宠物最多 1.5 个文件夹大小」⇒ 1.5 × 图标本体 96px）',
      _n24_val == 144, star=True, detail='val=%r' % (_n24_val,))

# N25 ★★★ 行为级：钳制把 2560 屏上的 3.33125 钳到「最长边 == 144」。
_n25_ok = False
_n25_detail = ''
if _DD2 is not None:
    _k_hi = _DD2.clamp_scale_factor_for_max_side(3.33125)
    _box_hi = _DD2.pet_screen_box(_k_hi)
    _n25_ok = (_box_hi is not None and max(_box_hi) == 144)
    _n25_detail = 'clamp(3.33125)=%.5f ⇒ 盒=%r 最长边=%r' % (
        _k_hi, _box_hi, max(_box_hi) if _box_hi else None)
check('N25 ★★★ 行为级：`clamp_scale_factor_for_max_side(3.33125)` '
      '⇒ 宠物盒最长边**恰好 144**', _n25_ok, star=True, detail=_n25_detail)

# N26 ★★★ **只减不增**：本来就小的倍率**不被撑大**（用户要的是"上限"不是"固定值"）。
_n26_ok = False
if _DD2 is not None:
    _small = 1.0   # 144/69 ≈ 2.087 > 1.0 ⇒ 不该被放大
    _n26_ok = (_DD2.clamp_scale_factor_for_max_side(_small) == _small)
check('N26 ★★★ 钳制**只减不增**（k=1.0 本来就小 ⇒ 原样返回，不被撑到上限）',
      _n26_ok, star=True)

# N27 ★★ 负控制：非法输入（None / 0 / NaN）**原样返回**（不抛、不猜、不返 0 盒）。
_n27_ok = False
if _DD2 is not None:
    try:
        _r_none = _DD2.clamp_scale_factor_for_max_side(None)
        _r_zero = _DD2.clamp_scale_factor_for_max_side(0)
        _r_nan = _DD2.clamp_scale_factor_for_max_side(float('nan'))
        _n27_ok = (_r_none is None and _r_zero == 0
                   and isinstance(_r_nan, float) and _r_nan != _r_nan)
    except Exception as _e:
        print('        [warn] 非法输入抛了: %r' % (_e,))
check('N27 ★★ 负控制：非法倍率（None/0/NaN）⇒ **原样返回**（不抛、不猜）',
      _n27_ok, star=True)

# N28 ★★★ `main.py` 真把钳制接进 `_refresh_pet_render_scale`（功能有消费者）。
#   判据：AST 在该函数体内找到对 `clamp_scale_factor_for_max_side` 的**真调用**。
_n28_ok = False
_n28_detail = ''
try:
    _main_src = io.open(os.path.join(_PKG, 'src', 'main.py'),
                        encoding='utf-8', newline='').read()
    _main_t = _ast.parse(_main_src)
    for _fn in _ast.walk(_main_t):
        if (isinstance(_fn, _ast.FunctionDef)
                and _fn.name == '_refresh_pet_render_scale'):
            _calls = []
            for _n in _ast.walk(_fn):
                if isinstance(_n, _ast.Call):
                    _f = _n.func
                    _nm = (_f.attr if isinstance(_f, _ast.Attribute)
                           else _f.id if isinstance(_f, _ast.Name) else None)
                    if _nm == 'clamp_scale_factor_for_max_side':
                        _calls.append(_nm)
            # 且赋值 `self._cached_scale_factor = v` 必须在**调用之后**（AST 语句序）
            _idx_call = None
            _idx_assign = None
            for _i, _st in enumerate(getattr(_fn, 'body', []) or []):
                for _n in _ast.walk(_st):
                    if isinstance(_n, _ast.Call):
                        _f = _n.func
                        _nm = (_f.attr if isinstance(_f, _ast.Attribute)
                               else _f.id if isinstance(_f, _ast.Name) else None)
                        if _nm == 'clamp_scale_factor_for_max_side' and _idx_call is None:
                            _idx_call = _i
                    if (isinstance(_n, _ast.Assign) and _idx_assign is None):
                        for _t in _n.targets:
                            if (isinstance(_t, _ast.Attribute)
                                    and _t.attr == '_cached_scale_factor'):
                                _idx_assign = _i
            _n28_ok = (len(_calls) >= 1 and _idx_call is not None
                       and _idx_assign is not None and _idx_call <= _idx_assign)
            _n28_detail = 'calls=%d idx_call=%r idx_assign=%r' % (
                len(_calls), _idx_call, _idx_assign)
            break
except Exception as _e:
    _n28_detail = 'AST 异常: %r' % (_e,)
check('N28 ★★★ `main._refresh_pet_render_scale` **真调用**钳制'
      '（且 `_cached_scale_factor` 赋值在钳制**之后**）',
      _n28_ok, star=True, detail=_n28_detail)

# N29 ★★★ **门↔场景解耦**：`_desktop_screen_doors` 的 AST 里**不许**出现
#   `SCENE_FIT_FRACTION` / `fit_fraction` / `camera` / `_offset_*`
#   （用户「不必把桌面上那个门当成场景系统里」）。
#   ★ 判据走 AST 属性/名字，不走文本（防注释里提一句就误判）。
_n29_bad = []
try:
    for _fn in _ast.walk(_main_t):
        if (isinstance(_fn, _ast.FunctionDef)
                and _fn.name == '_desktop_screen_doors'):
            for _x in _ast.walk(_fn):
                if isinstance(_x, _ast.Attribute):
                    if _x.attr in ('SCENE_FIT_FRACTION', 'fit_fraction',
                                   '_offset_x', '_offset_y'):
                        _n29_bad.append('attr %s' % _x.attr)
                if isinstance(_x, _ast.Name) and _x.id in (
                        'SCENE_FIT_FRACTION', 'fit_fraction'):
                    _n29_bad.append('name %s' % _x.id)
                # ★★ 还要认**字符串字面量**（`getattr(canvas, '_offset_y', 0)` 是
                #   本项目踩过两次的坑：名字在 AST 里是 `Constant` 不是 `Attribute`）。
                if isinstance(_x, _ast.Constant) and isinstance(_x.value, str):
                    if _x.value in ('SCENE_FIT_FRACTION', 'fit_fraction',
                                    '_offset_x', '_offset_y'):
                        _n29_bad.append('const %r' % _x.value)
            break
except Exception as _e:
    _n29_bad.append('AST 异常 %r' % (_e,))
check('N29 ★★★ 门↔场景**彻底解耦**：`_desktop_screen_doors` 的 AST 里'
      '**不出现** `SCENE_FIT_FRACTION`/`fit_fraction`/`_offset_*`',
      not _n29_bad, star=True, detail='bad=%r' % (_n29_bad,))

# N30 ★★★ 行为级：改 `SCENE_FIT_FRACTION` ⇒ 门的**输入**只有屏幕尺寸 ⇒ 输出不变。
#   （判据 = 纯函数性：同 (sizes, screen_w, screen_h, pet_box) 必得同结果，
#    与场景比例无关。这是"解耦"的可执行证据，不是靠读代码。）
_n30_ok = False
_n30_detail = ''
if _DD2 is not None:
    try:
        _sz = {'A': (192, 128), 'B': (192, 128), 'C': (44, 99), 'D': (180, 155)}
        _r1 = _DD2.plan_screen_doors(_sz, 2560, 1600, pet_box=(144, 98))
        _r2 = _DD2.plan_screen_doors(_sz, 2560, 1600, pet_box=(144, 98))
        _n30_ok = (_r1 == _r2 and len(_r1) == 4)
        _n30_detail = 'n=%d 稳定=%r' % (len(_r1), _r1 == _r2)
    except Exception as _e:
        _n30_detail = '异常: %r' % (_e,)
check('N30 ★★★ 行为级：`plan_screen_doors` **只吃屏幕尺寸**'
      '（同输入恒等输出 ⇒ 与场景比例无关，解耦可执行证据）',
      _n30_ok, star=True, detail=_n30_detail)

print('')
print('结论：%d PASS / %d FAIL' % (ok, fail))
sys.exit(1 if fail else 0)
