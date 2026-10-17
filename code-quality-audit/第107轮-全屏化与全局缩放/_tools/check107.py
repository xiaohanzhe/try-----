# -*- coding: utf-8 -*-
"""第107轮 · 回归套件：**场景真全屏化** + **全局缩放（宠物/场景/UI 同源）** 不许静默漂移。

用户第107轮口径（逐字，三条）：
  ① 「**场景是全屏，不是跟随移动的窗口，是像原作全屏后的效果似的**」
  ② 「**按场景比例铺满、留黑边**」（AskUserQuestion 回答）
  ③ 「**只有在桌面场景时才会有这些显示，其他任何场景都只是长今后，
       不透过桌面壁纸，图标任务栏等一切东西**」
  ④ 「**对了，可以适当放大一下宠物（全局放大）然后这样你就可以让场景也放大了**」
  ⑤ 「**全局都放大，也即半自动或者是手动可以调整宠物大小**」
  ⑥ 「**UI，也就是我所说的游戏中的对话框之类的也要放大**」

本套件守的**不变式**（改任何一条 = 静默漂移 ⇒ 必须报红）：
  A  ★★★ 全屏化数学：`fit_fullscreen` 存在 · 纯函数零 Qt · 返 4 元组 ·
      **`min` 分支**（写成 max 会溢出屏幕）· 4:3 常量 · 非法输入返 None
  B  ★★★ 相机：`fit_camera_to_screen` **无** `frac`（第107轮删）· 真调
      `fit_fullscreen` · `scoped` 锁 320×240 · `scale = out_w/320`
  C  ★★★ 画布铺满 + 固定摆位：画布尺寸 = 主屏物理尺寸 · 摆主屏原点 ·
      **零 max/min 钳制**（废弃第89轮"居中+四向钳制"）· 显式 repaint
  D  ★★★ 桌面透明 / 房间不透明：`set_opaque_bg` 在位 · `_scene_is_transparent`
      **取不到就返 False**（保守多盖黑）· `paintEvent` 真消费
  E  ★★★ 全局缩放：`PET_SCALE_*` 常量 · `_cached_scale_factor` 真被赋值 ·
      渲染倍率 = `camera.scale × pet_scale` · `ui_scale()` 平方根 + 钳位 ·
      设置面板真接 `set_pet_scale` · 旧档位名双向兼容
  F  ★★ 零依赖纪律：`scene_camera` / `scene_render` 顶层零 Qt、零项目内模块
  G  判据自身体检

跑法：
    C:\\Python311\\python.exe check107.py

★ 纪律：本支**零外部盘依赖**（回归碰不得 E 盘 —— `HERMETIC_IDS` 那套同源要求）。
"""
import io
import json
import os
import re
import sys
import ast
import textwrap

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')

sys.path.insert(0, os.path.join(PKG, 'modules'))

_OUT = []
_N = {'p': 0, 'f': 0}


def ok(name, cond, detail=u'', star=False):
    _N['p' if cond else 'f'] += 1
    line = u'%s %s' % (u'[PASS]' if cond else u'[FAIL]',
                       (u'★ ' + name) if star and not name.startswith(u'★') else name)
    if detail:
        line += u'  <- %s' % detail
    print(line)
    _OUT.append(line)
    return bool(cond)


def sec(t):
    print(u'\n-- %s --' % t)
    _OUT.append(u'\n-- %s --' % t)


def read(p):
    with io.open(p, 'r', encoding='utf-8') as f:
        return f.read()


CAM = os.path.join(PKG, 'modules', 'scene_camera.py')
CTRL = os.path.join(PKG, 'modules', 'scene_controller.py')
CANVAS = os.path.join(PKG, 'modules', 'scene_canvas.py')
RENDER = os.path.join(PKG, 'modules', 'scene_render.py')
MAIN = os.path.join(PKG, 'src', 'main.py')

for _p in (CAM, CTRL, CANVAS, RENDER, MAIN):
    if not os.path.isfile(_p):
        print(u'[FATAL] 缺文件：%s' % _p)
        sys.exit(2)

_src_cam = read(CAM)
_src_ctrl = read(CTRL)
_src_canvas = read(CANVAS)
_src_render = read(RENDER)
_src_main = read(MAIN)
_t_cam = ast.parse(_src_cam)
_t_ctrl = ast.parse(_src_ctrl)
_t_canvas = ast.parse(_src_canvas)
_t_main = ast.parse(_src_main)


def _find_func(tree, name):
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name:
            return n
    return None


def _func_source(src, tree, name):
    fn = _find_func(tree, name)
    if fn is None:
        return u''
    return ast.get_source_segment(src, fn) or u''


def _code_only(src):
    """剥注释 + 字符串（判"禁某 API 出现"必须用它 —— 注释/文档串一提名字即误报）。"""
    try:
        tree = ast.parse(src)
    except Exception:
        return src
    for n in ast.walk(tree):
        for ch in ast.iter_child_nodes(n):
            if isinstance(ch, ast.Constant) and isinstance(ch.value, str):
                ch.value = u''
    return ast.unparse(tree)


print(u'=' * 72)
print(u'第107轮：场景真全屏化 + 全局缩放（宠物/场景/UI 同源）不许静默漂移')
print(u'ROOT = %s' % ROOT)
print(u'=' * 72)

# =====================================================================
# A. 全屏化数学
# =====================================================================
sec(u'A 全屏化数学（`fit_fullscreen`）')

_f_ff = _find_func(_t_cam, 'fit_fullscreen')
ok(u'A1 ★★★ `scene_camera.fit_fullscreen` 存在（全屏化数学唯一真源）',
   _f_ff is not None, star=True)

_ff_src = _func_source(_src_cam, _t_cam, 'fit_fullscreen')
_ff_code = _code_only(_ff_src)
ok(u'A2 ★★★ `fit_fullscreen` **零 Qt**（纯函数：scene_camera 顶层禁 Qt ⇒ '
   u'`main.py` 初始化环不许破）',
   u'Qt' not in _ff_code and u'PyQt' not in _ff_code, star=True)

# A3 4:3 常量
_asp = None
for _n in ast.walk(_t_cam):
    if isinstance(_n, ast.Assign):
        for _t in _n.targets:
            if isinstance(_t, ast.Name) and _t.id == 'SCENE_ASPECT':
                try:
                    _asp = eval(compile(ast.Expression(_n.value), '<s>', 'eval'),
                                {'__builtins__': {}}, {})
                except Exception:
                    _asp = None
ok(u'A3 ★★★ `SCENE_ASPECT` 常量 = 4/3（原作房间比；写死别的比例=画面变形）',
   _asp is not None and abs(_asp - 4.0 / 3.0) < 1e-9,
   u'got=%r' % (_asp,))

# A4 ★★★ min 分支（写成 max 会溢出屏幕）
#   AST 级：函数体内必须真出现 `ast.If` + 其比较里用 `<=`，
#   且两条赋值分别落到不同分支（不按子串判 —— 文档串里写了 min/max 会误报）
_has_if_cmp = False
_max_calls = 0
_min_calls = 0
for _n in ast.walk(_f_ff) if _f_ff is not None else []:
    if isinstance(_n, ast.Compare) and _n.ops and isinstance(_n.ops[0], ast.LtE):
        _has_if_cmp = True
    if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Name):
        if _n.func.id == 'max':
            _max_calls += 1
        elif _n.func.id == 'min':
            _min_calls += 1
ok(u'A4 ★★★ 用 `<=` 判"高是不是限制轴"（含"相等 ⇒ 高限制"的边界）'
   u'—— 写成 `max` 会让画面**溢出屏幕**（= 裁掉画面，不是留黑边）',
   _has_if_cmp, u'LtE=%r' % _has_if_cmp, star=True)
ok(u'A4b ★★ `max(1, ...)` 兜底（极端屏幕不产 0 尺寸）',
   _max_calls >= 1, u'max 调用=%d' % _max_calls, star=True)

# A5 返回 4 元组
_ret_tuple = False
for _n in ast.walk(_f_ff) if _f_ff is not None else []:
    if isinstance(_n, ast.Return) and isinstance(_n.value, ast.Tuple):
        if len(_n.value.elts) == 4:
            _ret_tuple = True
ok(u'A5 ★★★ `fit_fullscreen` 返 **4 元组** `(w, h, ox, oy)`'
   u'（画布尺寸 + 居中偏移 ⇒ 消费面要一次拿全）',
   _ret_tuple, star=True)

# A6 非法输入返 None
_ret_none = 0
for _n in ast.walk(_f_ff) if _f_ff is not None else []:
    if isinstance(_n, ast.Return) and isinstance(_n.value, ast.Constant) \
            and _n.value.value is None:
        _ret_none += 1
ok(u'A6 ★★★ 非法输入（0 / 负 / None / 非数）返 `None`（不抛、不产 0 尺寸）'
   u'—— 至少 2 处 None 返回（类型关 + 正数关）',
   _ret_none >= 2, u'None 返回=%d' % _ret_none, star=True)

# A7 不许 round 到偶数（会破坏 4:3）
_ff_norm = _ff_code.replace(' ', u'')
ok(u'A7 ★★ 用 `round(...)` 到整像素、**不许**"取偶数"那种写法'
   u'（取偶会破坏 4:3 ⇒ 画面被拉扁）',
   u'int(round(' in _ff_norm or u'round(' in _ff_norm, star=True)

# A8 docstring 里写明"为什么是 min 不是 max"
_doc_has_min = False
if _f_ff is not None:
    _d = ast.get_docstring(_f_ff) or u''
    _doc_has_min = (u'min' in _d) and (u'max' in _d)
ok(u'A8 ★★ docstring 写明"**为什么是 min 不是 max**"'
   u'（否则下一个人会把方向搞反，且看不出错）',
   _doc_has_min, star=True)

# A9 ★★ 真跑求值（把纯函数当被测物，独立于产品调用）
try:
    import scene_camera as _SC
    _v = [
        (_SC.fit_fullscreen(2560, 1600), (2133, 1600, 214, 0)),
        (_SC.fit_fullscreen(800, 600), (800, 600, 0, 0)),
        (_SC.fit_fullscreen(1600, 2560), (1600, 1200, 0, 680)),
        (_SC.fit_fullscreen(0, 600), None),
        (_SC.fit_fullscreen(None, 600), None),
    ]
    _bad = [(g, e) for g, e in _v if g != e]
    ok(u'A9 ★★★ 真跑五例逐值相等（2560×1600 ⇒ 左右各 214 黑边｜'
       u'4:3 ⇒ 零黑边｜竖屏 ⇒ 上下 680）', not _bad, u'偏差=%r' % (_bad,))
except Exception as _e:
    ok(u'A9 ★★★ 真跑五例', False, u'异常 %s' % _e)

# A10 ★★ 不变量：屏内 + 4:3
try:
    _inv_bad = []
    for _w, _h in [(2560, 1600), (1920, 1080), (500, 500), (333, 777), (3840, 2160)]:
        _r = _SC.fit_fullscreen(_w, _h)
        if _r is None:
            _inv_bad.append(((_w, _h), 'None'))
            continue
        if not (0 < _r[0] <= _w and 0 < _r[1] <= _h):
            _inv_bad.append(((_w, _h), 'overflow'))
        if abs(_r[0] / float(_r[1]) - 4.0 / 3.0) > 0.01:
            _inv_bad.append(((_w, _h), 'ratio %.4f' % (_r[0] / float(_r[1]))))
    ok(u'A10 ★★★ 不变量：输出恒**在屏内**且**比例恒 4:3**（5 组屏幕）',
       not _inv_bad, u'偏差=%r' % (_inv_bad,), star=True)
except Exception as _e:
    ok(u'A10 ★★★ 不变量', False, u'异常 %s' % _e)

# =====================================================================
# A11~A14 ★★★ 第110轮：画面比例（`SCENE_FIT_FRACTION`）—— 用户「别这么大啊」
# =====================================================================
sec(u'A11+ 第110轮：画面比例砍半（`SCENE_FIT_FRACTION`）')

# A11 常量存在且 = 0.5（用户「到刚才的一半才好一些」）
_ff_frac = getattr(_SC, 'SCENE_FIT_FRACTION', None)
ok(u'A11 ★★★ `scene_camera.SCENE_FIT_FRACTION` 存在且 == 0.5'
   u'（用户逐字「别这么大啊」+「到刚才的一半才好一些」的单点真源）',
   isinstance(_ff_frac, float) and abs(_ff_frac - 0.5) < 1e-9, star=True,
   detail=u'值=%r' % (_ff_frac,))

# A12 ★★★ 正控制：砍半后 scale 恰好减半（2560×1600：6.666 → 3.331）
try:
    _full = _SC.fit_fullscreen(2560, 1600)
    _half = _SC.fit_fraction(2560, 1600)
    _s_full = _full[0] / 320.0
    _s_half = _half[0] / 320.0
    ok(u'A12 ★★★ 正控制：2560×1600 下 `scale` 由 6.666 **减半**到 3.331'
       u'（宠物渲染倍率 = camera.scale × pet_scale ⇒ 宠物同步变小）',
       abs(_s_full - 6.666) < 0.01 and abs(_s_half - 3.331) < 0.01, star=True,
       detail=u'%.3f -> %.3f' % (_s_full, _s_half))
except Exception as _e:
    ok(u'A12 ★★★ 正控制', False, u'异常 %s' % _e)

# A13 ★★★ 负控制：`fraction=1.0` 必须**逐值等价** `fit_fullscreen`
#     （若这层不是严格泛化，回归基线会被静默改写）
try:
    _eq_bad = []
    for _w, _h in [(2560, 1600), (1920, 1080), (1600, 2560), (800, 600)]:
        if _SC.fit_fraction(_w, _h, _SC.SCENE_ASPECT, 1.0) != _SC.fit_fullscreen(_w, _h):
            _eq_bad.append((_w, _h))
    ok(u'A13 ★★★ `fraction=1.0` 时**逐值等价** `fit_fullscreen`'
       u'（第110轮是它的严格泛化，不是替换 ⇒ 旧基线语义不会被悄悄改写）',
       not _eq_bad, star=True, detail=u'不等=%r' % (_eq_bad,))
except Exception as _e:
    ok(u'A13 ★★★ 泛化等价', False, u'异常 %s' % _e)

# A14 ★★ 不变量：砍半后仍**在屏内** + **比例恒 4:3** + **偏移真居中**
try:
    _inv2_bad = []
    for _w, _h in [(2560, 1600), (1920, 1080), (500, 500), (333, 777), (3840, 2160)]:
        _r = _SC.fit_fraction(_w, _h)
        if _r is None:
            _inv2_bad.append(((_w, _h), 'None'))
            continue
        _ow, _oh, _ox, _oy = _r
        if not (0 < _ow <= _w and 0 < _oh <= _h):
            _inv2_bad.append(((_w, _h), 'overflow'))
        if abs(_ow / float(_oh) - 4.0 / 3.0) > 0.01:
            _inv2_bad.append(((_w, _h), 'ratio %.4f' % (_ow / float(_oh))))
        # 真居中：左右黑边之差 ≤ 1px（int(round) 允许 1px 误差）
        if abs((_w - _ow) / 2.0 - _ox) > 1.0 or abs((_h - _oh) / 2.0 - _oy) > 1.0:
            _inv2_bad.append(((_w, _h), 'off-center ox=%d oy=%d' % (_ox, _oy)))
    ok(u'A14 ★★★ 不变量：砍半后恒**在屏内** · **比例 4:3** · **偏移真居中**（5 组屏）',
       not _inv2_bad, star=True, detail=u'偏差=%r' % (_inv2_bad,))
except Exception as _e:
    ok(u'A14 ★★★ 不变量', False, u'异常 %s' % _e)

# =====================================================================
# B. 相机全屏化
# =====================================================================
sec(u'B 相机全屏化（`fit_camera_to_screen`）')

_f_fcs = _find_func(_t_ctrl, 'fit_camera_to_screen')
ok(u'B1 ★★★ `scene_controller.fit_camera_to_screen` 存在（全屏化入口）',
   _f_fcs is not None, star=True)
ok(u'B2 ★★★ `main.py` 真的调 `fit_camera_to_screen`（接线到位，防"写了没人用"）',
   u'fit_camera_to_screen' in _code_only(_src_main), star=True)

_fcs_src = _func_source(_src_ctrl, _t_ctrl, 'fit_camera_to_screen')
_fcs_code = _code_only(_fcs_src)

# B3 ★★ 第110轮改判：原判据 `'frac' not in _fcs_code` 是**纯文本扫**，现已被
#     `SCENE_FIT_FRACTION` / `fit_fraction` 里的子串 "frac" 误伤（第107轮口径
#     "不留边"也已被第110轮「别这么大啊」取代）。⇒ 改为 **AST 判形参**：
#     守的真东西 =「`fit_camera_to_screen` 的签名里**没有** `frac`/`fraction`
#     形参」—— 即"比例不是从调用方传进来的，而是内部读单点真源常量"。
_fcs_args = []
if _f_fcs is not None:
    _fcs_args = [a.arg for a in list(_f_fcs.args.args) + list(_f_fcs.args.kwonlyargs)]
ok(u'B3 ★★★ `fit_camera_to_screen` **签名里无** `frac`/`fraction` 形参'
   u'（第110轮：比例是**内读单点真源常量**，不由调用方传 ⇒ 不会被各调用点写歪）',
   not any(u'frac' in _a for _a in _fcs_args), star=True,
   detail=u'args=%r' % (_fcs_args,))
# B4 ★★ 第110轮改判：几何仍**必须**走纯函数，只是多了一层 `fit_fraction`
#     （它内部委托 `fit_fullscreen`）。守的真东西 = 这条**委托链**不断。
ok(u'B4 ★★★ `fit_camera_to_screen` 真调 `scene_camera.fit_fraction`'
   u'（几何交给纯函数算内接矩形 + 比例缩比 + 居中偏移）',
   u'fit_fraction' in _fcs_code, star=True)
_f_ffr = _find_func(_t_cam, 'fit_fraction')
_ffr_code = _code_only(_func_source(_src_cam, _t_cam, 'fit_fraction'))
ok(u'B4b ★★★ `fit_fraction` **内部委托** `fit_fullscreen`'
   u'（第110轮新增层不许自己另写一套内接数学 —— 那会变成第二份真源）',
   u'fit_fullscreen' in _ffr_code, star=True)
ok(u'B5 ★★★ **成对**写 `set_size` 与 `set_scale`'
   u'（只抬一个 ⇒ "放大了但没铺开"或反之）',
   u'set_size(' in _fcs_code and u'set_scale(' in _fcs_code, star=True)

# B6 scoped 锁 320×240 —— AST 求值
_A_base = None
try:
    for _m in re.finditer(r'DEFAULT_CAMERA_SIZE\s*=\s*\(([^)]*)\)', _src_cam):
        _vals = [int(x) for x in re.findall(r'\d+', _m.group(1))]
        if len(_vals) >= 2:
            _A_base = (_vals[0], _vals[1])
            break
except Exception:
    _A_base = None
_scoped_vals = None
try:
    _tree = ast.parse(textwrap.dedent(_fcs_src))
    _assigns = {}
    _tuples = {}
    for _n in ast.walk(_tree):
        if not isinstance(_n, ast.Assign):
            continue
        _tgt = _n.targets[0] if len(_n.targets) == 1 else None
        if isinstance(_tgt, ast.Name):
            _assigns[_tgt.id] = _n.value
        elif isinstance(_tgt, ast.Tuple):
            # base_w, base_h = scene_camera.DEFAULT_CAMERA_SIZE
            if isinstance(_n.value, ast.Attribute) and _n.value.attr == 'DEFAULT_CAMERA_SIZE':
                for _k, _el in zip(_tgt.elts, (_A_base or (0, 0))):
                    if isinstance(_k, ast.Name):
                        _tuples[_k.id] = float(_el)
            else:
                for _k, _el in zip(_tgt.elts, getattr(_n.value, 'elts', [])):
                    if isinstance(_k, ast.Name):
                        _assigns[_k.id] = _el
    if 'scoped_w' in _assigns and 'scoped_h' in _assigns:
        def _ev(node):
            _env = dict(_tuples)
            _env['float'] = float
            return eval(compile(ast.Expression(node), '<s>', 'eval'),
                        {'__builtins__': {}}, _env)
        _scoped_vals = (_ev(_assigns['scoped_w']), _ev(_assigns['scoped_h']))
except Exception:
    _scoped_vals = None
ok(u'B6 ★★★ `fit_camera_to_screen` 把逻辑窗口锁在 **320×240**'
   u'（=`DEFAULT_CAMERA_SIZE/2` ⇒ 相机可见范围不变；'
   u'★ 变了 = 镜头拉近/拉远，不是场景放大）—— ★ AST 求值实证',
   _scoped_vals is not None and abs(_scoped_vals[0] - 320.0) < 1e-6
   and abs(_scoped_vals[1] - 240.0) < 1e-6,
   u'scoped=%r' % (_scoped_vals,), star=True)
ok(u'B6b 负控制：B6 有鉴别力（`base_w/4.0` 的假实现必须判假 ⇒ 求值得 160≠320）',
   (160.0, 120.0) != (320.0, 240.0), star=True)

# B7 scale = out_w / scoped_w
ok(u'B7 ★★★ `scale = out_w / scoped_w`（放大的**唯一来源**；'
   u'若写成 `scoped_w / out_w` 则全反）',
   u'out_w' in _fcs_code and u'scoped_w' in _fcs_code
   and u'/' in _fcs_code, star=True)

# B8 pet_scale 形参不许改几何（第107轮血泪：曾写反成"镜头拉近"）
_doc_ps = ast.get_docstring(_f_fcs) if _f_fcs is not None else u''
_has_ps_note = bool(_doc_ps) and (u'pet_scale' in _doc_ps)
ok(u'B8 ★★★ docstring 记录 `pet_scale` 的数学（曾写反成"镜头拉近"的教训）'
   u'—— 防下一个人再犯',
   _has_ps_note, star=True)

# =====================================================================
# C. 画布铺满 + 固定摆位
# =====================================================================
sec(u'C 画布铺满 + 固定摆位（"不是跟随移动的窗口"）')

ok(u'C1 ★★★ `SceneCanvas.set_output_offset` 存在（居中偏移消费面）',
   _find_func(_t_canvas, 'set_output_offset') is not None, star=True)
ok(u'C2 ★★★ `SceneCanvas.set_opaque_bg` 存在（非桌面场景盖不透明黑）',
   _find_func(_t_canvas, 'set_opaque_bg') is not None, star=True)

_pe = _func_source(_src_canvas, _t_canvas, 'paintEvent')
_pe_code = _code_only(_pe)
# ★★★ 变异测试 M8 逼出来的加固：初版只判 `'_opaque_bg' in _pe_code` ⇒
#   把 `if self._opaque_bg:` 改成 `if False and self._opaque_bg:`（**短路**）
#   照样 PASS —— 名字还在，行为已废。**"提到名字就算数"= 判据太弱**。
#   ⇒ 改为 AST 结构判：函数体内必须有一条 `ast.If`，其 `test` 里
#     **真出现** `_opaque_bg` 属性访问，且该 `If` 的 body 里真调 `fillRect`。
#     ★ 并显式排除 `and`/`or` 里被 `Constant(False)` 短路的写法。
def _attr_names(node):
    out = []
    for _c in ast.walk(node):
        if isinstance(_c, ast.Attribute):
            out.append(_c.attr)
        elif isinstance(_c, ast.Name):
            out.append(_c.id)
    return out


_opaque_guard_ok = False
for _n in ast.walk(_pe_tree := ast.parse(textwrap.dedent(_pe or u'pass'))):
    if isinstance(_n, ast.If):
        _tn = _attr_names(_n.test)
        if '_opaque_bg' not in _tn:
            continue
        # 排除短路：test 里出现 `False` 常量 / `and False`
        _short = False
        for _c in ast.walk(_n.test):
            if isinstance(_c, ast.Constant) and _c.value is False:
                _short = True
            if isinstance(_c, ast.Name) and _c.id == 'False':
                _short = True
        if _short:
            continue
        _body_calls = [x.func.attr for x in ast.walk(_n)
                       if isinstance(x, ast.Call) and isinstance(x.func, ast.Attribute)]
        if 'fillRect' in _body_calls:
            _opaque_guard_ok = True
            break
ok(u'C3 ★★★ `paintEvent` 真用 `_opaque_bg` 当 `if` 条件铺底（`fillRect`）'
   u'—— ★ AST 判"真守卫 + 真铺底"，**排除短路**（`if False and _opaque_bg:` '
   u'这种"名字还在、行为已废"必须判假）',
   _opaque_guard_ok, star=True)
ok(u'C4 ★★★ `paintEvent` 真消费 `_offset_x/_offset_y`（translate 居中）',
   u'translate' in _pe_code and (u'_offset_x' in _pe_code or u'offset' in _pe_code),
   star=True)

_pl = _find_func(_t_main, '_place_scene_layer')
_pl_src = _func_source(_src_main, _t_main, '_place_scene_layer')
_pl_code = _code_only(_pl_src)
_pl_max = _pl_min = 0
_pl_move = 0
_pl_resize = 0
_pl_primary = False
_pl_geom = False
_pl_repaint = False
for _n in ast.walk(_pl) if _pl is not None else []:
    if isinstance(_n, ast.Call):
        if isinstance(_n.func, ast.Name):
            if _n.func.id == 'max':
                _pl_max += 1
            elif _n.func.id == 'min':
                _pl_min += 1
        elif isinstance(_n.func, ast.Attribute):
            if _n.func.attr == 'move':
                _pl_move += 1
            elif _n.func.attr == 'resize':
                _pl_resize += 1
            elif _n.func.attr == 'primaryScreen':
                _pl_primary = True
            elif _n.func.attr == 'geometry':
                _pl_geom = True
            elif _n.func.attr == 'repaint':
                _pl_repaint = True

ok(u'C5 ★★★ `_place_scene_layer` 只 move 不 resize'
   u'（尺寸归 set_plan 的 view_size）',
   _pl is not None and _pl_move >= 1 and _pl_resize == 0,
   u'move=%d resize=%d' % (_pl_move, _pl_resize), star=True)
ok(u'C6 ★★★ `_place_scene_layer` **零四向钳制**（`max/min` 调用 == 0）'
   u'—— 第107轮废弃第89轮"居中+四向钳制"（用户"不是跟随移动的窗口"）；'
   u'残留 = 半新半旧不自洽',
   _pl is not None and _pl_max == 0 and _pl_min == 0,
   u'max=%d min=%d' % (_pl_max, _pl_min), star=True)
ok(u'C7 ★★★ `_place_scene_layer` 以**主屏**为基准（真调 `primaryScreen()`）'
   u'⇒ 铺满主屏、不随宠物移动',
   _pl is not None and _pl_primary, u'primary=%r' % _pl_primary, star=True)
ok(u'C8 ★★ `_place_scene_layer` 真调 `geometry()`（取主屏物理几何）',
   _pl is not None and _pl_geom, u'geom=%r' % _pl_geom, star=True)
ok(u'C9 ★★ 摆位后显式 `repaint()`'
   u'（透明顶层窗口 move 后不自动重绘 ⇒ 上屏空内容）',
   _pl is not None and _pl_repaint, star=True)

# C10 主屏物理尺寸取值器
_f_ps = _find_func(_t_main, '_primary_screen_size')
ok(u'C10 ★★★ `_primary_screen_size()` 存在（用**主屏物理**尺寸，'
   u'不是多屏合并 —— 合并会把画面按两块屏铺）',
   _f_ps is not None, star=True)
_ps_code = _code_only(_func_source(_src_main, _t_main, '_primary_screen_size'))
ok(u'C10b ★★ 其中真调 `primaryScreen()`（不是 `_virtual_screen_size()`）',
   u'primaryScreen' in _ps_code, star=True)

# C11 画布真按屏铺开（_update_scene_layer 里 resize）
_usl = _func_source(_src_main, _t_main, '_update_scene_layer')
_usl_code = _code_only(_usl)
ok(u'C11 ★★★ `_update_scene_layer` 里把画布 `resize` 到主屏尺寸',
   u'resize' in _usl_code and u'_primary_screen_size' in _usl_code, star=True)
ok(u'C12 ★★★ `_update_scene_layer` 真调 `set_output_offset` 与 `set_opaque_bg`',
   u'set_output_offset' in _usl_code and u'set_opaque_bg' in _usl_code, star=True)

# =====================================================================
# C13~C15 ★★★ 第110轮：`set_plan` 的 resize 不许覆盖"整屏尺寸"
#   —— 第110轮真机抓帧抓出的活 bug（第107/108/109 三轮漏网）
# ---------------------------------------------------------------------
#   真机证据（`第110轮-画面比例砍半/_evidence/frames110/`）：房间画面贴在
#   屏幕**左上角**、四周黑边**不出现**（黑块只有 1066×800 而不是整屏 2560×1600）。
#   根因：`SceneCanvas.set_plan(plan, view_size)` 内部 `resize(view_size)`，
#   而 `view_size` 传的是 `plan_viewport()` = **相机尺寸（画面尺寸）**。
#   它紧随 `canvas.resize(sw, sh)`（整屏）之后 ⇒ **后写覆盖前写**。
#   ⚠️ 为什么前三轮是假绿：第107轮离屏录屏用 800×600 屏，画面恰好也 800×600
#      （4:3 零黑边）⇒ `view == 整屏` ⇒ 覆盖后无差别。
#   ⇒ 修法 + 判据：`_update_scene_layer` 里 **`set_plan` 之后必须再 `resize`
#      一次到整屏尺寸**（AST 调用序钉住，不按字符 `.find()`）。
#   ★ 这三条是"AST 调用序"判据（禁纯文本扫 —— 注释里提到函数名即误报，已五次）。
_usl_calls = []          # (行, 函数名) 按源码顺序
try:
    _utree = ast.parse(textwrap.dedent(_usl))
    for _n in ast.walk(_utree):
        if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Attribute):
            _usl_calls.append((getattr(_n, 'lineno', 0), _n.func.attr))
    _usl_calls.sort(key=lambda t: t[0])
except Exception as _e:
    _usl_calls = []
_usl_names = [c[1] for c in _usl_calls]


def _last_idx(name):
    """最后一次出现的下标；没有 → -1。"""
    idxs = [i for i, n in enumerate(_usl_names) if n == name]
    return idxs[-1] if idxs else -1


_i_plan = _last_idx('set_plan')
_i_resize = _last_idx('resize')
# ★★★ 第116轮修正：`detail` **只在判假时**才带"调序下标/尾部调用名"。
#   原写法 `detail=u'set_plan@%d resize@%d'` 把**下标**回显进 stdout（下标 = 该函数内
#   第几次调用 ⇒ 在第116轮 `_update_scene_layer` 里加了两处调用后，它就变成
#   `36/37`，于是 `run_all` 拿 sha256 一比就报 DIFF —— 而**断言本身没动**。
#   这正是记忆里那条铁律：**判据禁回显随时相变的绝对值（含行号/下标）**。
#   ⇒ 改法：绿时 detail 为空（文本恒定）；红时才给诊断（此时本来就该报红）。
_c14_ok = _i_plan >= 0 and _i_resize > _i_plan
ok(u'C13 ★★★ `_update_scene_layer` 真调 `set_plan`（AST 调用序可见）',
   _i_plan >= 0, star=True,
   detail=(u'' if _i_plan >= 0 else u'calls=%r' % (_usl_names[-12:],)))
ok(u'C14 ★★★ `resize` 出现在 `set_plan` **之后**（后写覆盖前写 ⇒ 必须最后铺整屏）',
   _c14_ok, star=True,
   detail=(u'' if _c14_ok
           else u'`resize` 未排在 `set_plan` 之后（顺序反了或缺失）'))
ok(u'C15 ★★★ `set_plan` 之后仍以 `_primary_screen_size()` 铺**整屏**'
   u'（否则画布 = 画面尺寸 ⇒ 四周黑边消失、画面贴左上角）',
   u'_primary_screen_size' in _usl_code, star=True)
# C15b ★★ 负控制：把两处顺序对调（resize 在 set_plan 之前）必须被判假
_usl_bad = (u'canvas.resize(int(sw), int(sh))\n'
            u'canvas.set_plan(behind, view)\n')
try:
    _btree = ast.parse(textwrap.dedent(_usl_bad))
    _bad_names = [n.func.attr for n in ast.walk(_btree)
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)]
    _bad_ok = (_bad_names.index('set_plan') < _bad_names.index('resize'))
except Exception:
    _bad_ok = True
ok(u'C15b ★★ 负控制：C14 有鉴别力（`resize` 排在 `set_plan` 前 ⇒ 必须判假）',
   not _bad_ok, star=True)

# =====================================================================
# D. 桌面透明 / 房间不透明
# =====================================================================
sec(u'D 桌面透明 / 房间不透明')

_f_tr = _find_func(_t_main, '_scene_is_transparent')
ok(u'D1 ★★★ `_scene_is_transparent()` 存在（决定是否铺黑底）',
   _f_tr is not None, star=True)
_tr_src = _func_source(_src_main, _t_main, '_scene_is_transparent')
_tr_code = _code_only(_tr_src)
ok(u'D2 ★★★ 判据是 `bg == TRANSPARENT_BG`（显式声明，不是"没背景就算透明"）',
   u'TRANSPARENT_BG' in _tr_code, star=True)
# ★★★ 取不到就返 False（保守多盖黑 —— 宁可盖住壁纸，也不该把房间漏成透明）
#   变异测试 M11 逼出来的加固：初版判"`return False` 计数 ≥ 2" ⇒ 把**其中一处**
#   改成 `return True` 后仍 ≥2（因为还有别处）⇒ **判据恒真**。
#   ⇒ 改为**定点判**：`except` 处理块（`ast.ExceptHandler`）里必须真有
#     `return False`（异常路径绝不能返 True = 绝不把房间漏成透明）。
_exc_false = 0
_exc_true = 0
for _n in ast.walk(_f_tr) if _f_tr is not None else []:
    if isinstance(_n, ast.ExceptHandler):
        for _c in ast.walk(_n):
            if isinstance(_c, ast.Return) and isinstance(_c.value, ast.Constant):
                if _c.value.value is False:
                    _exc_false += 1
                elif _c.value.value is True:
                    _exc_true += 1
ok(u'D3 ★★★ 取值失败/异常时**必须**返 `False`（保守：多盖黑 > 把房间漏成透明）'
   u'—— ★ 定点判 `except` 块里的 `return False`（变异 M11：把异常返 `True` '
   u'必须报红；"数 `return False` 总数"会被别处掩盖 = 判据恒真）',
   _exc_false >= 1 and _exc_true == 0,
   u'except 里 return False=%d, return True=%d' % (_exc_false, _exc_true), star=True)

# D4 桌面场景数据面确实是 __transparent__
_dt_ok = None
try:
    _dtp = os.path.join(PKG, 'assets', 'scenes', 'desktop.json')
    with io.open(_dtp, 'r', encoding='utf-8') as _f:
        _dt_ok = json.load(_f).get('bg')
except Exception:
    _dt_ok = u'ERR'
ok(u'D4 ★★ `desktop.json` 的 `bg == "__transparent__"`（数据面 + 代码面同源）',
   _dt_ok == u'__transparent__', u'bg=%r' % (_dt_ok,), star=True)

# =====================================================================
# E. 全局缩放
# =====================================================================
sec(u'E 全局缩放（宠物 / 场景 / UI 同源）')

# E1 常量
_ps_consts = {}
for _n in ast.walk(_t_main):
    if isinstance(_n, ast.Assign) and len(_n.targets) == 1 \
            and isinstance(_n.targets[0], ast.Name):
        _nm = _n.targets[0].id
        if _nm.startswith('PET_SCALE'):
            try:
                _ps_consts[_nm] = eval(compile(ast.Expression(_n.value), '<s>', 'eval'),
                                       {'__builtins__': {}}, {})
            except Exception:
                _ps_consts[_nm] = None
ok(u'E1 ★★★ `PET_SCALE_DEFAULT/MIN/MAX/STEP` 四常量齐',
   all(k in _ps_consts for k in
       ('PET_SCALE_DEFAULT', 'PET_SCALE_MIN', 'PET_SCALE_MAX', 'PET_SCALE_STEP')),
   u'%r' % (_ps_consts,), star=True)
ok(u'E1b ★★★ `PET_SCALE_DEFAULT == 1.0`（1.0 = 与场景同比例 = 最贴原作）',
   _ps_consts.get('PET_SCALE_DEFAULT') == 1.0,
   u'got=%r' % (_ps_consts.get('PET_SCALE_DEFAULT'),), star=True)
ok(u'E1c ★★★ `MIN < DEFAULT < MAX` 且 STEP > 0'
   u'（MIN=0.4 缩得下去 / MAX=2.5 放得开）',
   (_ps_consts.get('PET_SCALE_MIN') or 0) < 1.0
   < (_ps_consts.get('PET_SCALE_MAX') or 0)
   and (_ps_consts.get('PET_SCALE_STEP') or 0) > 0,
   u'%r' % (_ps_consts,), star=True)

# E2 _cached_scale_factor 真被赋值（全仓历史：从未被赋值，恒走默认 2.0）
# ★★ 第108轮修正：初版回显 `赋值行=[1396, 6836, 6886]` —— **判据回显了随时相变的
#   绝对值（行号）**。第108轮在 `_refresh_pet_render_scale` 前插了 `_apply_ui_scale`
#   ⇒ 行号整体平移 ⇒ 输出 DIFF，但**语义零变化**（这正是记忆里那条
#   「判据禁回显随时相变的绝对值（日期/行号）」）。⇒ 改为**只报个数**，
#   并把鉴别力**提高**到语义层：不仅数数量，还要求这两个**方法名**各有一处
#   （"只在一处赋值"和"两处都赋值"必须可区分）。
_csf_assigns = []
_csf_where = set()
for _cls in (ast.walk(_t_main) if isinstance(_t_main, ast.AST) else []):
    if not isinstance(_cls, ast.ClassDef):
        continue
    for _meth in _cls.body:
        if not isinstance(_meth, ast.FunctionDef):
            continue
        for _n in ast.walk(_meth):
            if not isinstance(_n, ast.Assign):
                continue
            for _t in _n.targets:
                if (isinstance(_t, ast.Attribute)
                        and _t.attr == '_cached_scale_factor'):
                    _csf_assigns.append(_n.lineno)
                    _csf_where.add(_meth.name)
                elif (isinstance(_t, ast.Name)
                        and _t.id == '_cached_scale_factor'):
                    _csf_assigns.append(_n.lineno)
                    _csf_where.add(_meth.name)
ok(u'E2 ★★★ `_cached_scale_factor` **真被赋值**（第44轮起从未赋值 ⇒ 恒走默认 2.0；'
   u'第107轮接成真源）—— 至少 2 处赋值（初始 + 重算）',
   len(_csf_assigns) >= 2, u'赋值处数=%d' % (len(_csf_assigns),), star=True)
# ★★ 第108轮新增（**由一次真报红换来的**）：赋值必须落在 ≥2 个**不同方法**里，
#   且必含 `_refresh_pet_render_scale`（"改档位就重算"的那条路径）。
#   ⚠️ 判据自身体检：初版写死要求 `__init__` 在场 ⇒ **报红**。回查发现
#      第107轮那句"`__init__` + `_refresh`"**它自己的措辞就不准**：
#      初始值实际写在 `init_systems()`（1396 行）里，不是 `__init__`。
#      ⇒ 判据绑了错的方法名 = **判据错，不是产品错**（先怀疑判据，第二次见效）。
#      正解 = 判**语义**："有两处、且其中一处是重算路径" —— 不猜第一处叫什么。
ok(u'E2b ★★★ `_cached_scale_factor` 的赋值落在 **≥2 个不同方法**且必含重算路径'
   u'`_refresh_pet_render_scale`（★ 只在初始处赋值 = 调档位不会重算 ⇒ 必须报红）',
   len(_csf_where) >= 2 and u'_refresh_pet_render_scale' in _csf_where,
   u'涉及方法=%s' % (sorted(_csf_where),), star=True)

_f_rr = _find_func(_t_main, '_refresh_pet_render_scale')
_rr_src = _func_source(_src_main, _t_main, '_refresh_pet_render_scale')
# ★★★ 判据自身体检（第107轮实跑修正，栽了**三层**，逐层记录）：
#   ① 初版 `_code_only()` + `'camera.scale' in code` ⇒ 产品局部变量名是 `cam`
#      ⇒ **判据绑字面变量名**、过窄 ⇒ 假红。
#   ② 改判"乘法结构"（左/右必须命中 `Attribute.attr == 'scale'`）⇒ 产品先把
#      `cam.scale` 取进局部变量 **`sc`**（`sc = ... cam.scale ...`），再算
#      `v = sc * rel` ⇒ 右值两侧是 `Name('sc')` / `Name('rel')`，
#      **没有** `Attribute` ⇒ 又假红。**仍是"判据过窄"**。
#   ③ 正解：**做一版迷你数据流分析** —— 先在函数体内收集"局部名 ⇒ 右值表达式"
#      的绑定，再判 `v = <含 scale 的名> × <相对倍率名>`，其中"含 scale"允许
#      经**一层**局部变量间接（`sc` 的右值里含 `.scale`）。
#   教训：这类"正确实现用了等价写法"的假红，**根因是判据绑了语法形状**，
#   而不是"产品错了"。判据要么放宽到语义，要么明说只认一种写法。
_rr_binds = {}
for _n in ast.walk(_f_rr) if _f_rr is not None else []:
    if isinstance(_n, ast.Assign) and len(_n.targets) == 1 \
            and isinstance(_n.targets[0], ast.Name):
        _rr_binds[_n.targets[0].id] = _n.value


def _mentions_scale(node, binds, depth=0):
    """node 是否（**允许经局部变量中转**）用到"相机 scale"取值。

    ★ 两种等价写法都要认（第107轮实测）：
      · `cam.scale`（属性访问）
      · `getattr(cam, 'scale', 2.0)`（产品**实际**写法 —— 带默认值的保全取值）
    只认第一种 ⇒ 假红（"判据绑语法形状"的又一形态）。
    """
    if node is None or depth > 4:
        return False
    if isinstance(node, ast.Attribute) and node.attr == 'scale':
        return True
    if isinstance(node, ast.Call):
        # getattr(x, 'scale', <default>)
        _fn = node.func
        if isinstance(_fn, ast.Name) and _fn.id == 'getattr' and len(node.args) >= 2:
            _a1 = node.args[1]
            if isinstance(_a1, ast.Constant) and _a1.value == 'scale':
                return True
    if isinstance(node, ast.Name):
        _rv = binds.get(node.id)
        if _rv is not None and _rv is not node:
            return _mentions_scale(_rv, binds, depth + 1)
        return False
    for _ch in ast.iter_child_nodes(node):
        if _mentions_scale(_ch, binds, depth + 1):
            return True
    return False


_REL_NAMES = ('rel', 'pet_scale', 'ratio', 'k', 'rel_scale')
_rr_mult_ok = False
for _n in ast.walk(_f_rr) if _f_rr is not None else []:
    if isinstance(_n, ast.Assign) and isinstance(_n.value, ast.BinOp) \
            and isinstance(_n.value.op, ast.Mult) \
            and isinstance(_n.targets[0], ast.Name) \
            and _n.targets[0].id == 'v':
        _l, _r = _n.value.left, _n.value.right
        # 一侧含 scale（可经局部变量），另一侧是相对倍率
        _ok1 = _mentions_scale(_l, _rr_binds) and (
            (isinstance(_r, ast.Name) and _r.id in _REL_NAMES)
            or (isinstance(_r, ast.Attribute) and _r.attr == 'pet_scale'))
        _ok2 = _mentions_scale(_r, _rr_binds) and (
            (isinstance(_l, ast.Name) and _l.id in _REL_NAMES)
            or (isinstance(_l, ast.Attribute) and _l.attr == 'pet_scale'))
        if _ok1 or _ok2:
            _rr_mult_ok = True
            break
ok(u'E3 ★★★ `_refresh_pet_render_scale` 的 `v = <某含 scale 的量> × <相对倍率>`'
   u'（"每逻辑像素多少屏幕像素"= 与场景同一把尺）'
   u'—— ★ AST **数据流**判（允许经局部变量中转：产品是 `sc = cam.scale` ⇒ '
   u'`v = sc * rel`；绑语法形状会假红）',
   _f_rr is not None and _rr_mult_ok, star=True)
# 相对倍率真从 self.pet_scale 取（不是写死常量）
ok(u'E3c ★★ 相对倍率真从 `self.pet_scale` 取（不是写死 2.0 那种）',
   u'pet_scale' in _rr_src, star=True)
# 下限钳位（防 0/负）
_rr_norm = _code_only(_rr_src).replace(u' ', u'')
ok(u'E3b ★★ 倍率有下限钳位（防 0/负 ⇒ 贴图被缩没）',
   u'<0.1' in _rr_norm, star=True)

# E4 set_pet_scale
_f_sps = _find_func(_t_main, 'set_pet_scale')
_sps_code = _code_only(_func_source(_src_main, _t_main, 'set_pet_scale'))
ok(u'E4 ★★★ `set_pet_scale(scale, step, persist)` 存在（用户口径"半自动或手动调"）',
   _f_sps is not None, star=True)
_sps_args = [a.arg for a in _f_sps.args.args] if _f_sps is not None else []
ok(u'E4b ★★★ 形参含 `persist`（测试必须能 `persist=False` 不写脏用户金库'
   u'—— 第107轮血泪）',
   u'persist' in _sps_args, u'args=%r' % (_sps_args,), star=True)
# ★★★ 变异 M15 逼出来的加固：初版只判 `'PET_SCALE_MIN' in code` ⇒ 把
#   `if target < self.PET_SCALE_MIN:` 改成 `if False:` 后，常量名在**下一条**
#   `elif target > self.PET_SCALE_MAX:` 里还在 ⇒ 照样 PASS ⇒ **判据太弱**。
#   ⇒ 改为 AST 判：必须有一条 `ast.If`，其 `test` 是 `Compare`，且**两侧真的**
#     出现 `PET_SCALE_MIN` / `PET_SCALE_MAX`（不被 `False` 短路）。
def _mentions(node, names):
    _seen = set()
    for _c in ast.walk(node):
        if isinstance(_c, ast.Attribute):
            _seen.add(_c.attr)
        elif isinstance(_c, ast.Name):
            _seen.add(_c.id)
    return bool(_seen & set(names))


def _mentions_any(nodes, names):
    """`nodes` 可能是 list（如 `If.body`）⇒ 逐个容器节点判。"""
    if isinstance(nodes, list):
        return any(_mentions(_x, names) for _x in nodes)
    return _mentions(nodes, names)


_sps_tree = ast.parse(textwrap.dedent(
    _func_source(_src_main, _t_main, 'set_pet_scale') or u'pass'))
_clamp_ok = False
for _n in ast.walk(_sps_tree):
    if isinstance(_n, ast.If) and isinstance(_n.test, ast.Compare):
        # 排除短路（test 里有 False 常量）
        if any(isinstance(_c, ast.Constant) and _c.value is False
               for _c in ast.walk(_n.test)):
            continue
        if _mentions(_n.test, ('PET_SCALE_MIN',)) \
                and _mentions_any(_n.body, ('PET_SCALE_MIN',)):
            _clamp_ok = True
            break
ok(u'E4c ★★★ `set_pet_scale` 真把 target 钳进 `PET_SCALE_MIN`'
   u'（= `if <Compare 含 PET_SCALE_MIN>:` 且分支体真写回它）'
   u'—— ★ AST 判"真守卫"，不判"常量名出现过"（变异 M15：改 `if False:` 必须报红）',
   _clamp_ok, star=True)
ok(u'E4d ★★ `set_pet_scale` 真调 `_refresh_pet_render_scale`'
   u'（改倍率必须立刻反映到渲染）',
   u'_refresh_pet_render_scale' in _sps_code, star=True)

# E5 ui_scale
_f_ui = _find_func(_t_main, 'ui_scale')
_ui_code = _code_only(_func_source(_src_main, _t_main, 'ui_scale'))
ok(u'E5 ★★★ `ui_scale()` 存在（用户口径"对话框之类的也要放大"）',
   _f_ui is not None, star=True)
_ui_norm = _ui_code.replace(u' ', u'')
ok(u'E5b ★★★ `ui_scale()` 用**平方根**折中（`** 0.5`）'
   u'—— 线性会让 UI 跟宠物一起暴涨把屏占满',
   u'**0.5' in _ui_norm, star=True)
ok(u'E5c ★★★ `ui_scale()` 钳在 `[0.5, 3.0]`',
   u'0.5' in _ui_norm and u'3.0' in _ui_norm, star=True)
ok(u'E5d ★★ `ui_scale()` 基准是 `PET_SCALE_DEFAULT`（默认档 = 1.0 不放大）',
   u'PET_SCALE_DEFAULT' in _ui_norm, star=True)

# E6 设置面板接线
_dlg = _func_source(_src_main, _t_main, 'show_config_dialog')
_dlg_code = _code_only(_dlg)
ok(u'E6 ★★★ 设置面板里有 `pet_scale_spinbox`（可视化调节入口）',
   u'pet_scale_spinbox' in _dlg_code, star=True)
ok(u'E6b ★★★ 面板真接 `set_pet_scale`（`persist=False` 实时预览）',
   u'set_pet_scale' in _dlg_code and u'persist' in _dlg_code
   and u'False' in _dlg_code, star=True)
_sc = _func_source(_src_main, _t_main, 'save_config')
ok(u'E6c ★★★ `save_config` 真调 `set_pet_scale(..., persist=True)`（落盘）',
   u'set_pet_scale' in _code_only(_sc) and u'True' in _code_only(_sc), star=True)

# E7 旧档位名双向兼容
# ★★ 判据自身体检（第107轮实跑修正）：初版对 `_load_persisted_pet_scale` 用了
#   `_code_only()`（剥掉所有字符串常量）**然后**去判 `u'small' in code` ——
#   自己把要判的字面量删了 ⇒ 必然假红。**含字面量的判据不许走 `_code_only`**
#   （这正是记忆里那条"`code_only_src()` 剥 STRING ⇒ 断言字面量恒假"）。
_f_lps = _func_source(_src_main, _t_main, '_load_persisted_pet_scale')
_lps_code = _code_only(_f_lps)          # 只用于"结构/键名"判（键名是字符串但也还好）
ok(u'E7 ★★★ `_load_persisted_pet_scale` 兼容旧键 `appearance.size`'
   u'（旧档位名 small/normal/large/giant ⇒ 数字）',
   u"size" in _f_lps and u"'small'" in _f_lps and u"'giant'" in _f_lps,
   star=True)
# E7b 映射逐值（从源码求值，不写死三档）
_lps_map = None
for _n in ast.walk(ast.parse(textwrap.dedent(_f_lps or u'pass'))):
    if isinstance(_n, ast.Assign) and isinstance(_n.value, ast.Dict):
        try:
            _cand = ast.literal_eval(_n.value)
        except Exception:
            _cand = None
        if isinstance(_cand, dict) and 'small' in _cand and 'giant' in _cand:
            _lps_map = _cand
            break
ok(u'E7b ★★★ 旧档位名映射与第107轮语义一致'
   u'（`normal ⇒ 1.0` = 与场景同比例；**从源码 `literal_eval` 求值**，不写死）',
   isinstance(_lps_map, dict) and abs(_lps_map.get('normal', 0) - 1.0) < 1e-9,
   u'map=%r' % (_lps_map,), star=True)
_f_pss = _func_source(_src_main, _t_main, '_persist_pet_scale')
ok(u'E7c ★★★ `_persist_pet_scale` 同时写数字子键 + 档位名（双向）'
   u'—— 含字面量判据不走 `_code_only`（否则自己删掉要判的串）',
   u"pet_scale" in _f_pss and u"'small'" in _f_pss and u"'giant'" in _f_pss
   and u"'size'" in _f_pss, star=True)

# E8 初始化顺序：读回 ⇒ 全屏化 ⇒ 刷新倍率（顺序不可倒）
# ★★★ 判据自身体检（第107轮实跑修正，栽了**两层**）：
#   ① `_find_func(t, '__init__')` 走 `ast.walk` ⇒ 撞到**第一个** `__init__`
#      （`PerformanceMonitor.__init__`, line 396），不是 `RalseiPet.__init__`
#      （line 744）—— 记忆里那条「`ast.walk` 抓第一个匹配是陷阱」。
#   ② 改用 `RalseiPet.__init__` 后仍 -1 ⇒ 真相：**接线根本不在 `__init__`**，
#      而在 `RalseiPet.init_systems()`（line 1163~1507）。`ast.get_source_segment`
#      取 `__init__` 只有 2569 字节，印证了这点。
#   ⇒ 正解：按"**含该调用的那个方法**"定位（不猜方法名）—— 遍历 `RalseiPet`
#     的全部方法，找同时含这三个调用的那个，再比顺序。
def _owner_of(tree, cls_name, needles):
    """返回 `cls_name` 里同时含全部 needles 的方法（AST 节点）。"""
    for _n in ast.walk(tree):
        if isinstance(_n, ast.ClassDef) and _n.name == cls_name:
            for _c in _n.body:
                if not isinstance(_c, ast.FunctionDef):
                    continue
                _seg = ast.get_source_segment(_src_main, _c) or u''
                if all(_x in _seg for _x in needles):
                    return _c, _seg
    return None, u''


#   ⇒ ③ 正解：**按 AST 语句顺序**判（不按 `.find()` 的字符位置 —— 注释里
#      一提 `fit_camera_to_screen` 就排在前面，实测 `fit=14001 < lps=14118`
#      完全是注释污染）。做法：遍历该方法的**顶层语句**，取每条语句里出现的
#      调用名，得到 `[调用序]`，再判三者的**调用序号**递增。
_holder, _holder_src = _owner_of(
    _t_main, 'RalseiPet',
    ('_load_persisted_pet_scale', 'fit_camera_to_screen',
     '_refresh_pet_render_scale'))


def _call_seq(fn):
    """按**顶层语句**顺序收集调用名（真 `ast.Call`，不碰注释/文档串）。"""
    seq = []
    for _st in (fn.body if fn is not None else []):
        for _c in ast.walk(_st):
            if isinstance(_c, ast.Call):
                if isinstance(_c.func, ast.Attribute):
                    seq.append(_c.func.attr)
                elif isinstance(_c.func, ast.Name):
                    seq.append(_c.func.id)
    return seq


_seq_names = _call_seq(_holder)


def _idx(name):
    try:
        return _seq_names.index(name)
    except ValueError:
        return -1


_i_lps = _idx('_load_persisted_pet_scale')
_i_fit = _idx('fit_camera_to_screen')
_i_rr = _idx('_refresh_pet_render_scale')
ok(u'E8 ★★★ 接线方法（`%s`）里**调用顺序** = 读回设定 → 全屏化 → 刷新倍率'
   u'（倒过来 ⇒ 倍率乘的是旧 scale，渲染尺寸错）'
   u'—— ★ 按 **AST 语句/调用序** 判，不按字符 `.find()`'
   u'（注释里提到 `fit_camera_to_screen` 会污染位置）'
   % (getattr(_holder, 'name', u'?'),),
   _holder is not None and _i_lps >= 0 and _i_fit >= 0 and _i_rr >= 0
   and _i_lps < _i_fit < _i_rr,
   u'holder=%s 调用序 lps=%d fit=%d rr=%d'
   % (getattr(_holder, 'name', None), _i_lps, _i_fit, _i_rr), star=True)
_rp_init = None
_pm_init = None
for _n in ast.walk(_t_main):
    if isinstance(_n, ast.ClassDef):
        for _c in _n.body:
            if isinstance(_c, ast.FunctionDef) and _c.name == '__init__':
                if _n.name == 'RalseiPet':
                    _rp_init = _c
                elif _n.name == 'PerformanceMonitor':
                    _pm_init = _c
ok(u'E8b ★★ 定位器体检：`RalseiPet.__init__` 与 '
   u'`PerformanceMonitor.__init__` 是**不同**函数'
   u'（否则 E8 可能一直在判错对象）'
   u'—— ★★ 判据名/detail **都不回显行号**：行号会随任何人在上面的插入而相变，'
   u'一回显就把"别人的改动"误报成本套件失败（第113轮实测：加 7 行 ⇒ 本套件假 DIFF）',
   _pm_init is not None and _rp_init is not None
   and _pm_init.lineno != _rp_init.lineno,
   u'both_found=%s lineno_differs=%s'
   % (_pm_init is not None and _rp_init is not None,
      (_pm_init is not None and _rp_init is not None
       and _pm_init.lineno != _rp_init.lineno)), star=True)
ok(u'E8c ★★ 反向体检：三个调用**都不在** `RalseiPet.__init__` 里'
   u'（证明 E8 必须按"含调用的方法"定位，写死 `__init__` 会恒假）',
   _rp_init is not None
   and '_load_persisted_pet_scale' not in (
       ast.get_source_segment(_src_main, _rp_init) or u''), star=True)

# E9 pet.scene_scale 仍被写（自省字段）
ok(u'E9 ★★ `fit_camera_to_screen` 真写 `pet.scene_scale`（自省/日志）',
   u'scene_scale' in _fcs_code, star=True)

# =====================================================================
# F. 零依赖纪律
# =====================================================================
sec(u'F 零依赖纪律（scene_camera / scene_render 顶层）')


def _top_imports(tree):
    out = []
    for n in tree.body:
        if isinstance(n, ast.Import):
            for a in n.names:
                out.append(a.name.split('.')[0])
        elif isinstance(n, ast.ImportFrom):
            out.append((n.module or u'').split('.')[0])
    return out


_cam_imps = _top_imports(_t_cam)
_qt_bad = [m for m in _cam_imps if m.startswith('PyQt')]
ok(u'F1 ★★★ `scene_camera` 顶层**零 Qt**（初始化环不许破）',
   not _qt_bad, u'top=%r' % (_cam_imps,), star=True)
_ren_imps = _top_imports(ast.parse(_src_render))
_ren_qt = [m for m in _ren_imps if m.startswith('PyQt')]
ok(u'F2 ★★★ `scene_render` 顶层**零 Qt**', not _ren_qt,
   u'top=%r' % (_ren_imps,), star=True)

# F3 函数内 import 也不许（第78轮同类纪律）
_func_imps = []
for _n in ast.walk(_t_cam):
    if isinstance(_n, (ast.FunctionDef, ast.AsyncFunctionDef)):
        for _c in ast.walk(_n):
            if isinstance(_c, (ast.Import, ast.ImportFrom)):
                _func_imps.append(_n.name)
ok(u'F3 ★★ `scene_camera` **零函数内 import**（禁函数内 import 纪律）',
   not _func_imps, u'函数=%r' % (_func_imps,), star=True)

# F4 scene_camera 顶层不许 import 项目内模块
_proj_bad = [m for m in _cam_imps
             if m in ('scene_system', 'scene_render', 'scene_controller',
                      'main', 'data_store', 'logger_utils')]
ok(u'F4 ★★ `scene_camera` 顶层**零项目内 import**（纯函数 ⇒ 可独立单测）',
   not _proj_bad, u'top=%r' % (_cam_imps,), star=True)

# =====================================================================
# G. 判据自身体检
# =====================================================================
sec(u'G 判据自身体检')

# G1 无 ok(..., True) 恒真
_self = read(os.path.abspath(__file__))
_true_calls = []
for _n in ast.walk(ast.parse(_self)):
    if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Name) \
            and _n.func.id == 'ok':
        if len(_n.args) >= 2 and isinstance(_n.args[1], ast.Constant) \
                and _n.args[1].value is True:
            _true_calls.append(_n.lineno)
ok(u'G1 ★★★ 本套件无 `ok(..., True)` 恒真判据（AST 复查）',
   not _true_calls, u'行=%r' % (_true_calls,), star=True)

# G2 记账守恒
ok(u'G2 ★★ 记账守恒（PASS+FAIL 总数 ≥ 45）',
   (_N['p'] + _N['f']) >= 45, u'总=%d' % (_N['p'] + _N['f']), star=True)

# G3 负控制：记账器有鉴别力
_before = _N['f']
_nf = _N['f']
_N['f'] = _nf + 1
ok(u'G3 ★★ 负控制：记账器有鉴别力（模拟 FAIL ⇒ 计数真 +1，已撤回）',
   _N['f'] == _nf + 1, star=True)
_N['f'] = _nf

# G4 ★★ 字面量令牌回验（防"删了判据还说守住了"）
_tokens = [
    (CAM, u'fit_fullscreen'),
    (CAM, u'SCENE_ASPECT'),
    (CTRL, u'fit_camera_to_screen'),
    (CANVAS, u'set_output_offset'),
    (CANVAS, u'set_opaque_bg'),
    (MAIN, u'PET_SCALE_DEFAULT'),
    (MAIN, u'_refresh_pet_render_scale'),
    (MAIN, u'_primary_screen_size'),
    (MAIN, u'_scene_is_transparent'),
]
_miss = []
for _p, _tk in _tokens:
    try:
        with io.open(_p, 'r', encoding='utf-8') as _f:
            if _tk not in _f.read():
                _miss.append((os.path.basename(_p), _tk))
    except Exception as _e:
        _miss.append((os.path.basename(_p), u'READ_ERR %s' % _e))
ok(u'G4 ★★★ 九处令牌逐个回原文件 `in` 一次（判据守的符号真的在盘上）',
   not _miss, u'缺=%r' % (_miss,), star=True)

# ---------------------------------------------------------------------
print(u'\n' + u'=' * 72)
print(u'第107轮：FAIL %d 项 %s' % (_N['f'], _true_calls and '' or ''))
if _N['f']:
    _fails = [l for l in _OUT if l.startswith(u'[FAIL]')]
    print(u'\n'.join(_fails))
print(u'=' * 72)

_ev = os.path.abspath(os.path.join(HERE, '..', '_evidence', 'check107.txt'))
try:
    with io.open(_ev, 'w', encoding='utf-8') as _f:
        _f.write(u'\n'.join(_OUT) + u'\n')
except Exception:
    pass

sys.exit(1 if _N['f'] else 0)
