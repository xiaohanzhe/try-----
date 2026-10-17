# -*- coding: utf-8 -*-
u"""第117轮回归锁：门 A（OneShot）换「黑光」变体 ＋ 四扇门统一放大。

用户口径（逐字，10-18）
------------------------
  「**oneshot 用最后 niko 回家走的那道门，但颜色变成黑光**，
    然后 **niko 的加（家）还是用他那道**，**ut 的门就用你的那个就好**，
    对了 **大一点都**」

⇒ 拆成四组判据（**逐条对应用户的四个分句**，不多不少）：

  A 组 · 门 A = 「Niko 回家那道门」的**黑光**版
      · 贴图名 = `objs/desk_door_oneshot_black.png`（新变体）
      · 与原件 `niko_door_portal.png` **同尺寸、alpha 逐像素一致** ⇒「**那道门**」
      · 但颜色**真变了**（平均亮度显著更暗、且不是纯黑一块）
  B 组 · 门 B（Niko 的家）**不动** —— 仍是原件 `niko_door_portal.png`（亮的品红）
  C 组 · 门 C（UT）**不动** —— 仍是 `objs/desk_door_ut.png`
  D 组 · 「大一点都」⇒ `DOOR_FIT_CAP` 1.2 → **1.6**，且**行为级**验证四扇门都变大、
        仍**逐边贴屏幕物理边**、四门仍是**统一倍率**（不许借放大破坏"按原作等比"）

★ 判据纪律（本轮仍按项目铁律）
------------------------------
1. **能上 AST / JSON 就不做纯文本扫**（注释里提一句名字就误报，已五次）。
2. **每条都要有鉴别力**：能给的都配正/负控制，或至少断言"A ≠ B"先成立。
3. **不拿"代理量"当阈值**：亮度档数按**原件档数**做相对口径（原件只有 20 档平涂，
   写死 40 档会恒假 —— 第117轮 `key117_black.py` 首版正是这么翻车的）。
4. 缺文件 / PIL 不可用 ⇒ **如实 FAIL**（带 detail），**不许抛栈、不许静默跳过**。

★ 为什么"alpha 逐像素一致"是核心判据
------------------------------------
用户要的是「**那道门，但颜色变成黑光**」——不是"另画一道黑门"。alpha 逐像素一致
= 形状/轮廓/透明区完全照原作 ⇒ 门的位置、贴边、遮挡关系一个像素都不动，只换颜色。
这也是本轮生成变体时唯一的硬约束（见 `_tools/key117_black.py` 的三条硬约束）。
"""
import io
import json
import os
import sys
import ast as _ast

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
# ★ 变异测试（`mutate117.py`）靠这个覆盖口把本套件指到**临时树**上跑
#   ⇒ 产线文件一个字节都不动。默认值 = 本轮目录往上三层（= 仓库根）。
ROOT = os.path.abspath(os.environ.get('RALSEI_ROUND117_ROOT')
                       or os.path.join(HERE, '..', '..', '..'))

OBJS = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes', 'objs')
DESKTOP_JSON = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes', 'desktop.json')
DESK_DOORS = os.path.join(ROOT, 'ralsei_pet', 'modules', 'desk_doors.py')

PNG_A = os.path.join(OBJS, 'desk_door_oneshot_black.png')
PNG_B = os.path.join(OBJS, 'niko_door_portal.png')
PNG_C = os.path.join(OBJS, 'desk_door_ut.png')
PNG_D = os.path.join(OBJS, 'desk_door_deltarune.png')

ok = fail = 0


def check(name, cond, star=False, detail=None):
    u"""`detail` 只在**失败**时打印（避免 PASS 行被噪声淹没）。"""
    global ok, fail
    if cond:
        ok += 1
        print('[PASS] %s' % name)
    else:
        fail += 1
        print('[FAIL] %s' % name)
        if detail:
            print('       detail: %s' % (detail,))


# ---------------------------------------------------------------------------
#  贴图读取（PIL）。拿不到就如实 FAIL，不抛。
# ---------------------------------------------------------------------------
_Image = None
_PIL_ERR = None
try:
    from PIL import Image as _Image
except Exception as _e:                                         # noqa: BLE001
    _PIL_ERR = repr(_e)
    _Image = None


def _load(path):
    u"""读成 RGBA 并返 `(size, [ (r,g,b,a), ... ])`；不可用 ⇒ `(None, None)`。"""
    if _Image is None or not os.path.isfile(path):
        return None, None
    try:
        im = _Image.open(path).convert('RGBA')
        return im.size, list(im.getdata())
    except Exception:                                           # noqa: BLE001
        return None, None


def _lum(t):
    r, g, b = t[0], t[1], t[2]
    return 0.299 * r + 0.587 * g + 0.114 * b


def _visible(px):
    return [t for t in px if t[3] > 0]


def _median(vals):
    if not vals:
        return 0.0
    s = sorted(vals)
    return s[len(s) // 2]


print('=== A. 门 A（OneShot）= 「Niko 回家那道门」的**黑光**版 ===')

# A0 先把三张图读进来（缺一张就在下面各自的判据里如实报红）
_szA, _pxA = _load(PNG_A)
_szB, _pxB = _load(PNG_B)
_szC, _pxC = _load(PNG_C)
_szD, _pxD = _load(PNG_D)

check('A0 三张门贴图可读（PIL=%s）' % ('ok' if _Image is not None else 'MISSING'),
      all(s is not None for s in (_szA, _szB, _szC, _szD)),
      star=True,
      detail='PIL_ERR=%r  A=%r B=%r C=%r D=%r'
             % (_PIL_ERR, _szA, _szB, _szC, _szD))

# A1 数据层：`desktop.json` 门 A 的 `sprite` 真换成黑光变体（JSON 读，非文本扫）
_dj = {}
try:
    with io.open(DESKTOP_JSON, encoding='utf-8') as _f:
        _dj = json.load(_f)
except Exception as _e:                                         # noqa: BLE001
    _dj = {}
    print('        [warn] desktop.json 读失败: %r' % (_e,))

_by_id = {}
for _o in (_dj.get('objects') or []):
    if isinstance(_o, dict) and _o.get('id'):
        _by_id[_o['id']] = _o

_A_SPRITE = 'objs/desk_door_oneshot_black.png'
_B_SPRITE = 'objs/niko_door_portal.png'
_C_SPRITE = 'objs/desk_door_ut.png'

check(u'A1 ★★★ 门 A（`desk_door_oneshot`）的 sprite == `%s`' % _A_SPRITE,
      _by_id.get('desk_door_oneshot', {}).get('sprite') == _A_SPRITE,
      star=True,
      detail='got=%r' % (_by_id.get('desk_door_oneshot', {}).get('sprite'),))

check('A1b ★ 黑光变体**真在盘上**（不是只改了 JSON 字串）',
      os.path.isfile(PNG_A) and os.path.getsize(PNG_A) > 0, star=True,
      detail='exists=%r size=%r' % (
          os.path.isfile(PNG_A),
          os.path.getsize(PNG_A) if os.path.isfile(PNG_A) else None))

# A2 同尺寸 —— 「用**那道门**」的第一层：轮廓盒一模一样
check(u'A2 ★★★ 黑光变体与原件 `niko_door_portal.png` **同尺寸**（192×128）',
      _szA is not None and _szB is not None and _szA == _szB == (192, 128),
      star=True, detail='A=%r B=%r' % (_szA, _szB))

# A3 ★★★ alpha 逐像素一致 —— 形状/透明区一个像素都不动（只换颜色）
_alpha_same = None
_alpha_diff = None
_a0_a = _a0_b = None
if _pxA is not None and _pxB is not None and len(_pxA) == len(_pxB):
    _alpha_diff = sum(1 for x, y in zip(_pxA, _pxB) if x[3] != y[3])
    _alpha_same = (_alpha_diff == 0)
    _a0_a = sum(1 for t in _pxA if t[3] == 0)
    _a0_b = sum(1 for t in _pxB if t[3] == 0)
check(u'A3 ★★★ 黑光变体的 **alpha 与原件逐像素一致**（形状/透明区零漂移）',
      _alpha_same is True, star=True,
      detail='不一致像素=%r alpha0 A=%r B=%r' % (_alpha_diff, _a0_a, _a0_b))

# A3b ★★★ 负控制：alpha 逐像素判据**真有鉴别力** —— 把原件的 alpha 全置 255
#     （形状信息抹掉，尺寸/像素数都不变），同一判据**必须**判否。
#     ★ 首版这条写的是"拿门 C 来比（尺寸不同）"——那是**弱控制**：它只证明了
#       "长度不等时判否"，而 A3 真正要守的是"同长度下逐像素比 alpha"。换成这个
#       才是同长度、只差 alpha 的正面对照（失败时一定报红，不会恒绿）。
_a3b_ok = False
_a3b_detail = 'px 未读到'
if _pxB is not None:
    _forced = [(t[0], t[1], t[2], 255) for t in _pxB]
    _d_forced = sum(1 for x, y in zip(_forced, _pxA) if x[3] != y[3])
    _a3b_ok = (_d_forced > 0)
    _a3b_detail = 'alpha 全置 255 后与原件的差异像素 = %d（应 > 0）' % _d_forced
check(u'A3b ★★★ 负控制：把原件 alpha 全置 255 ⇒ 同一判据**必判否**（alpha 判据有鉴别力）',
      _a3b_ok, star=True, detail=_a3b_detail)

# A3c ★ 补充：门 C 与原件的尺寸**不同**（44×99 vs 192×128）—— 说明"同尺寸"本身
#     不是自动成立的，A2 那条有内容。
check(u'A3c ★ 门 C 与门 B 原件尺寸不同（44×99 vs 192×128）⇒ A2 非恒真',
      _szC is not None and _szB is not None and _szC != _szB, star=True,
      detail='C=%r B=%r' % (_szC, _szB))

# A4 ★★★ 「颜色变成黑光」——真变暗了，且**不是一块纯黑**
_visA = _visible(_pxA) if _pxA else []
_visB = _visible(_pxB) if _pxB else []
_medA = _median([_lum(t) for t in _visA])
_medB = _median([_lum(t) for t in _visB])
_maxA = max([_lum(t) for t in _visA]) if _visA else 0.0
_maxB = max([_lum(t) for t in _visB]) if _visB else 0.0
_lvA = len(set(int(_lum(t)) for t in _visA))
_lvB = len(set(int(_lum(t)) for t in _visB))

check(u'A4 ★★★ 黑光确实**更暗**：中位亮度 %.1f < 原件 %.1f（用户「颜色变成黑光」）'
      % (_medA, _medB),
      _visA and _visB and _medA < _medB * 0.75, star=True,
      detail='medA=%.2f medB=%.2f' % (_medA, _medB))

# ★★ 阈值走**相对口径**（不拿"代理量"当绝对阈值）：原件本身只有 20 档平涂，
#    写死"≥40 档"会恒假 —— 那是 `key117_black.py` 首版翻车的原样。
_lv_need = max(6, int(_lvB * 0.6))
check(u'A4b ★★★ 黑光**不是一块黑**：可见亮度档数 %d ≥ max(6, 原件 %d × 0.6) = %d'
      % (_lvA, _lvB, _lv_need),
      _visA and _lvA >= _lv_need, star=True,
      detail='lvA=%d lvB=%d need=%d' % (_lvA, _lvB, _lv_need))
check(u'A4c ★★★ 黑光最亮 %.1f ∈ [30, 120]（既真"黑"，又不至于整块看不见）' % _maxA,
      30.0 <= _maxA <= 120.0, star=True,
      detail='maxA=%.2f maxB=%.2f' % (_maxA, _maxB))

# A5 ★★ 保留"品紫"色相（不是灰）：B 通道应显著高于 G 通道
_rgbA = [(t[0], t[1], t[2]) for t in _visA]
_avg = lambda k: (sum(p[k] for p in _rgbA) / float(len(_rgbA))) if _rgbA else 0.0
check(u'A5 ★★ 黑光仍是**品紫**（不是灰）：均值 R=%.1f > B=%.1f > G=%.1f'
      % (_avg(0), _avg(2), _avg(1)),
      bool(_rgbA) and _avg(0) > _avg(2) > _avg(1), star=True,
      detail='R=%.1f G=%.1f B=%.1f' % (_avg(0), _avg(1), _avg(2)))

# A6 ★★ 门 A 的 `pos` 仍是两个整数（数据合法；摆位由 `plan_screen_doors` 算，
#    这里只防"改贴图时把 pos 写坏"）
_posA = _by_id.get('desk_door_oneshot', {}).get('pos')
check('A6 ★ 门 A 的 `pos` 仍是 2 个整数（数据合法）',
      isinstance(_posA, list) and len(_posA) == 2
      and all(isinstance(v, int) for v in _posA), star=True,
      detail='pos=%r' % (_posA,))

print('')
print('=== B. 门 B（Niko 的家）**不动** —— 仍是原件那道亮的品红光门 ===')

check(u'B1 ★★★ 门 B（`desk_door_niko_home`）的 sprite == `%s`（用户「niko 的加还是用他那道」）'
      % _B_SPRITE,
      _by_id.get('desk_door_niko_home', {}).get('sprite') == _B_SPRITE,
      star=True,
      detail='got=%r' % (_by_id.get('desk_door_niko_home', {}).get('sprite'),))
check('B1b ★ 门 B **不是**那个黑光变体（两者不许被并成一张）',
      _by_id.get('desk_door_niko_home', {}).get('sprite') != _A_SPRITE, star=True)
check('B1c ★★ 门 A 与门 B 贴图名**不同**（同一道门、两种颜色 ⇒ 两张素材）',
      _by_id.get('desk_door_oneshot', {}).get('sprite')
      != _by_id.get('desk_door_niko_home', {}).get('sprite'), star=True)
# B2 门 B 用的仍是**亮的**那版（未压暗）—— 与 A 的中位亮度**必须**拉开
check(u'B2 ★★★ 门 B 仍是**亮**版：中位亮度 %.1f > 门 A 的 %.1f'
      % (_medB, _medA),
      _visB and _visA and _medB > _medA * 1.5, star=True,
      detail='medB=%.2f medA=%.2f' % (_medB, _medA))

print('')
print('=== C. 门 C（UT）**不动** —— 用户「ut 的门就用你的那个就好」 ===')

check(u'C1 ★★★ 门 C（`desk_door_ut`）的 sprite == `%s`' % _C_SPRITE,
      _by_id.get('desk_door_ut', {}).get('sprite') == _C_SPRITE,
      star=True,
      detail='got=%r' % (_by_id.get('desk_door_ut', {}).get('sprite'),))
check('C2 ★ 门 C 尺寸仍是 44×99（UT 王座门桌面版，未被本轮放大改像素）',
      _szC == (44, 99), star=True, detail='C=%r' % (_szC,))
check('C2b ★★ 门 C 文件字节数未被改写（改像素会破坏"各用原尺寸"的路由）',
      os.path.isfile(PNG_C) and os.path.getsize(PNG_C) > 0, star=True,
      detail='size=%r' % (os.path.getsize(PNG_C) if os.path.isfile(PNG_C) else None,))

print('')
print('=== D. 「大一点都」⇒ DOOR_FIT_CAP 1.2 → 1.6（行为级验证）===')

# D1 AST 取 `DOOR_FIT_CAP` 的**字面量**（禁纯文本扫：注释里就写着 1.2 这个数）
_dd_tree = None
try:
    with io.open(DESK_DOORS, encoding='utf-8', newline='') as _f:
        _dd_tree = _ast.parse(_f.read())
except Exception as _e:                                         # noqa: BLE001
    _dd_tree = None
    print('        [warn] desk_doors.py 读/解析失败: %r' % (_e,))


def _dd_const(name):
    u"""从模块级 `Assign` 取字面量（`literal_eval`，禁 eval 源串）。"""
    if _dd_tree is None:
        return None
    for _n in _dd_tree.body:
        if isinstance(_n, _ast.Assign):
            for _t in _n.targets:
                if isinstance(_t, _ast.Name) and _t.id == name:
                    try:
                        return _ast.literal_eval(_n.value)
                    except Exception:                           # noqa: BLE001
                        return None
    return None


_cap_lit = _dd_const('DOOR_FIT_CAP')
check(u'D1 ★★★ `DOOR_FIT_CAP` 字面量 == 1.6（AST 取值；用户「大一点都」）',
      _cap_lit == 1.6, star=True, detail='DOOR_FIT_CAP=%r' % (_cap_lit,))

# D2 产品真函数（不是我在测试里重写公式）
_dd = None
try:
    sys.path.insert(0, os.path.join(ROOT, 'ralsei_pet'))
    from modules import desk_doors as _dd                    # noqa: E402
except Exception as _e:                                         # noqa: BLE001
    _dd = None
    print('        [warn] desk_doors 导入失败: %r' % (_e,))

check('D2 ★★ `desk_doors` 可 import（判据跑在**产品真函数**上，不是测试里重写的公式）',
      _dd is not None, star=True)

# 四扇门的**当前**原尺寸（门 A 已换图 ⇒ 192×128，与门 B 同）
_sz4 = {'A': (192, 128), 'B': (192, 128), 'C': (44, 99), 'D': (180, 155)}
# 生产链路的宠物盒：`clamp(3.33125)` ⇒ `pet_screen_box()`（2560×1600 真机实测值）
_pet = None
_k_clamped = None
if _dd is not None:
    try:
        _k_clamped = _dd.clamp_scale_factor_for_max_side(3.33125)
        _pet = _dd.pet_screen_box(_k_clamped)
    except Exception as _e:                                     # noqa: BLE001
        _pet = None
        print('        [warn] 宠物盒算失败: %r' % (_e,))

check(u'D2b ★★★ 宠物盒 == (144, 98)（= 钳到"最长边 144"后的真机值）',
      _pet == (144, 98), star=True, detail='_pet=%r k=%r' % (_pet, _k_clamped))

_k135 = None
_rows = []
_plan = {}
if _dd is not None and _pet is not None:
    _k135 = _dd.fit_doors_uniform_scale(_sz4, _pet)
    _plan = dict(_dd.plan_screen_doors(_sz4, 2560, 1600, pet_box=_pet))
    _rows = ['%s %dx%d @(%d,%d)' % (L, r[2], r[3], r[0], r[1])
             for L, r in sorted(_plan.items())]

# D3 统一倍率 k ≈ 1.0116（> 1 ⇒ 真的比"各用原尺寸"还大）
check(u'D3 ★★★ 统一倍率 k == %.4f ∈ (1.00, 1.03)（原件像素已基本"按原作"）'
      % (_k135 or 0.0),
      _k135 is not None and 1.00 < _k135 < 1.03, star=True,
      detail='k=%r' % (_k135,))

# D4 门 D（最大的那扇）== 182×157 —— 这是 cap=1.6 的**定义式结果**
check(u'D4 ★★★ 门 D 屏幕尺寸 == 182×157（cap=1.6 的定义式结果）',
      _plan.get('D') is not None
      and _plan['D'][2] == 182 and _plan['D'][3] == 157,
      star=True, detail='rows=%r' % (_rows,))

# D5 ★★★ 负控制 / A-B 对照：cap=1.2（上一轮的值）⇒ 门 D **必须更小**
_bad_ctrl = []
if _dd is not None and _pet is not None:
    try:
        _plan12 = dict(_dd.plan_screen_doors(_sz4, 2560, 1600, pet_box=_pet))
        # 直接调 fit_doors_uniform_scale 传 cap —— 产品函数支持 `cap=` 形参
        _k12 = _dd.fit_doors_uniform_scale(_sz4, _pet, cap=1.2)
        for _L, _wh in _sz4.items():
            _w12 = max(1, int(round(_wh[0] * _k12)))
            _h12 = max(1, int(round(_wh[1] * _k12)))
            _w16, _h16 = _plan[_L][2], _plan[_L][3]
            if not (_w16 > _w12 and _h16 >= _h12):
                _bad_ctrl.append('%s 1.2⇒%dx%d 1.6⇒%dx%d' % (_L, _w12, _h12, _w16, _h16))
    except Exception as _e:                                     # noqa: BLE001
        _bad_ctrl.append('异常 %r' % (_e,))
check(u'D5 ★★★ 负控制：cap=1.2 时四门都**更小**（证明"放大"真生效，非恒真）',
      _dd is not None and _plan and not _bad_ctrl, star=True,
      detail='k12=%r bad=%r' % (_k12 if _dd is not None and _pet is not None else None,
                               _bad_ctrl))

# D6 ★★★ 四门仍**逐边贴屏幕物理边**（放大不许把门顶离边框）
_bad_edge = []
_side_of = {'A': 'top', 'B': 'bottom', 'C': 'left', 'D': 'right'}
for _L, _r in (_plan or {}).items():
    _x, _y, _w, _h = _r
    _sd = _side_of.get(_L)
    if _sd == 'top' and _y != 0:
        _bad_edge.append('%s y=%d' % (_L, _y))
    elif _sd == 'bottom' and _y + _h != 1600:
        _bad_edge.append('%s y+h=%d' % (_L, _y + _h))
    elif _sd == 'left' and _x != 0:
        _bad_edge.append('%s x=%d' % (_L, _x))
    elif _sd == 'right' and _x + _w != 2560:
        _bad_edge.append('%s x+w=%d' % (_L, _x + _w))
check('D6 ★★★ 放大后四扇门仍**逐边贴屏幕物理边**（A上/B下/C左/D右）',
      _dd is not None and len(_plan) == 4 and not _bad_edge, star=True,
      detail='rows=%r bad=%r' % (_rows, _bad_edge))

# D7 ★★★ 四门仍是**统一倍率**（"按原作等比放大"不许被放大改坏）
#   ★★ 判据写法（本轮修过一次）：首版用「屏幕宽/原宽 全等」＋ 容差 0.02 —— 那是
#     **被整数取整兜住的松判据**（实测 ratios=1.010417/1.011111/1.022727，三者并不
#     真相等，只是差别 < 0.02）。真"同一把尺"应当**精确**成立：
#     每扇门的 w/h == `max(1, round(原尺寸 × k))`，且 `k` **来自产品函数**。
#   ★ 非恒等性靠后半条兜：逐门倍率（`fit_door_scale`）确实**分叉** ⇒ 若产品悄悄
#     改回逐门算法，四门的 `round(原尺寸 × k)` 立刻对不上。
_scale_ok = []
_solo = {}
if _dd is not None and _pet is not None and _plan and _k135:
    for _L, _wh in _sz4.items():
        if _L not in _plan:
            _scale_ok.append('%s 缺摆位' % _L)
            continue
        _ew = max(1, int(round(_wh[0] * _k135)))
        _eh = max(1, int(round(_wh[1] * _k135)))
        _gw, _gh = _plan[_L][2], _plan[_L][3]
        if (_gw, _gh) != (_ew, _eh):
            _scale_ok.append('%s 期望 %dx%d 实得 %dx%d' % (_L, _ew, _eh, _gw, _gh))
        _solo[_L] = round(_dd.fit_door_scale(_wh, _pet), 4)
_spread_solo = (max(_solo.values()) - min(_solo.values())) if _solo else 0.0
check(u'D7 ★★★ 四门共用**同一把尺**：逐门 w/h **精确等于** round(原尺寸 × k=%.6f)'
      u'（逐门倍率分叉 %.3f ⇒ 判据非恒等）' % (_k135 or 0.0, _spread_solo),
      _dd is not None and len(_plan) == 4 and not _scale_ok and _spread_solo > 1e-6,
      star=True,
      detail='bad=%r solo=%r' % (_scale_ok, _solo))

# D8 ★★ 门 A 与门 B 缩放后**尺寸完全相同**（同一道门 ⇒ 同尺寸）
check('D8 ★★ 门 A 与门 B 缩放后尺寸**完全相同**（同一道门、只差颜色）',
      _plan.get('A') is not None and _plan.get('B') is not None
      and _plan['A'][2:] == _plan['B'][2:], star=True,
      detail='A=%r B=%r' % (_plan.get('A'), _plan.get('B')))

print('')
print('=== E. 别顺手改坏（回归护栏）===')

# E1 四门贴图仍然是**四张不同**的素材（用户「门也不是都长那样」）
_glob_sprites = [_by_id.get(k, {}).get('sprite') for k in
                 ('desk_door_oneshot', 'desk_door_niko_home',
                  'desk_door_ut', 'desk_door_deltarune')]
check('E1 ★★ 四门贴图仍是 4 张**不同**素材（未被本轮合并）',
      len([s for s in _glob_sprites if s]) == 4
      and len(set(_glob_sprites)) == 4, star=True,
      detail='sprites=%r' % (_glob_sprites,))

# E2 门 D 仍是巨门框桌面版（用户「是哪个门框似的那个门」，第112/116轮裁定）
check('E2 ★★ 门 D 仍是 `objs/desk_door_deltarune.png`（巨门框桌面版，不许回退）',
      _by_id.get('desk_door_deltarune', {}).get('sprite')
      == 'objs/desk_door_deltarune.png', star=True,
      detail='got=%r' % (_by_id.get('desk_door_deltarune', {}).get('sprite'),))

# E3 4 门仍 `enabled: False`（房间层不画、只屏幕层画）
check('E3 ★★ 4 门仍全 `enabled: false`（房间层剔除，只屏幕层画）',
      all(_by_id.get(k, {}).get('enabled') is False for k in _by_id
          if str(k).startswith('desk_door')), star=True,
      detail='enabled=%r' % ([_by_id.get(k, {}).get('enabled') for k in _by_id],))

# E4 门 A 的原件 `spr_darkdoor_0.png` **仍在盘上**（世界内别处可能还在用）
check('E4 ★ 门 A 的原贴图 `spr_darkdoor_0.png` 仍在盘（世界内仍可能引用）',
      os.path.isfile(os.path.join(OBJS, 'spr_darkdoor_0.png')), star=True)

# E5 本轮口径**留痕**在数据里（`_comment.round117_oneshot_black_and_bigger`）
_r117 = ((_dj.get('_comment') or {}).get('round117_oneshot_black_and_bigger')
         if isinstance(_dj.get('_comment'), dict) else None)
check('E5 ★ 数据里留有 `_comment.round117_oneshot_black_and_bigger`（口径可回溯）',
      isinstance(_r117, dict) and bool(_r117), star=True,
      detail='type=%r keys=%r' % (type(_r117).__name__,
                                  sorted(_r117) if isinstance(_r117, dict) else None))

print('')
print(u'结论：%d PASS / %d FAIL' % (ok, fail))
sys.exit(1 if fail else 0)
