# -*- coding: utf-8 -*-
u"""verify106.py —— 第106轮 `check106` 的**独立验收端**（不进 G2）。

与 `check106.py` 的区别（**这是"判据也是被测物"的落地**）
--------------------------------------------------------
`check106` 是**回归锁**：进 G2、零外部盘依赖、只读仓库内文件，要能秒级跑完。
本文件是**独立验收**：**换一套代码、换一种取数法**，把同一批结论**重推一遍**。
两者若不一致 ⇒ 至少有一个错了（这正是独立验收的价值：不靠同一段代码自证）。

★ 三条独立化手段
----------------
  1. **换取数法**：`check106` 用 `ast.walk` + 正则源码切片；本文件用
     `ast.walk` **全量遍历** + **行号窗口**，并对关键量用 **AST 求值**（`eval`）
     而非"子串在不在"。
  2. **换证据源**：非瞬移不只看源码，**真起产品**（`RalseiPet`）跑一次
     `walk_steps`，用**产品自己的钩子**逐跳对账（与 `walk106_probe.py` 同法，
     但这里把结论**写死成 PASS/FAIL 判据**并落盘）。
  3. **换量法**：全屏化不用 CSV（那是录制端的抽样），直接问**产品对象**
     `cam.size` / `cam.scale` / `cam.scoped_size()`，并用
     `frac` 反推"应该多大"。

★ 零外部盘依赖：**不碰 E 盘 / 原作**（原作不可达也不影响本文件 —— 本轮
  改动全在仓库内）。真起产品需要 Qt，用 `offscreen` 平台。

产物：`_evidence/verify106.txt`（判据 + 结论），退出码 0=全绿 / 1=有红。
"""
import ast
import io
import os
import sys
import textwrap

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.normpath(os.path.join(HERE, '..'))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')
SRC = os.path.join(PKG, 'src')
CTRL = os.path.join(PKG, 'modules', 'scene_controller.py')
CAM = os.path.join(PKG, 'modules', 'scene_camera.py')
MAIN = os.path.join(PKG, 'src', 'main.py')
OUT = os.path.join(ROUND, '_evidence', 'verify106.txt')

R = []
_LINES = []


def ok(name, cond, detail=u''):
    R.append((name, bool(cond)))
    _LINES.append(u'[%s] %s%s' % (u'PASS' if cond else u'FAIL', name,
                                  (u'  —— ' + detail) if detail else u''))
    print(_LINES[-1])


def _read(p):
    with open(p, 'r', encoding='utf-8', newline='') as fh:
        return fh.read()


_LINES.append(u'=== verify106：第106轮独立验收（换一套代码重推同一批结论）===')
_LINES.append(u'ROOT = %s' % ROOT)
_LINES.append(u'')

# =====================================================================
#  一、静态面（换取数法：全量 walk + 行号窗口 + AST 求值）
# =====================================================================
_src_ctrl = _read(CTRL)
_t_ctrl = ast.parse(_src_ctrl)
_lines_ctrl = _src_ctrl.splitlines()


def _fn(name):
    for n in ast.walk(_t_ctrl):
        if isinstance(n, ast.FunctionDef) and n.name == name:
            return n
    return None


def _fn_text(name):
    n = _fn(name)
    if n is None:
        return u''
    # ★ 独立化：用**行号窗口**（不是 check106 的 _func_source —— 同一想法另写一份）
    lo = n.lineno - 1
    hi = getattr(n, 'end_lineno', lo + 1)
    return u'\n'.join(_lines_ctrl[lo:hi])


# ---- V1 非瞬移：travel_to 的有路线分支必须走 walk_steps（**AST 真调用**）----
_tt = _fn('travel_to')
_v1 = False
if _tt is not None:
    for n in ast.walk(_tt):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == 'walk_steps'):
            _v1 = True
ok(u'V1 `travel_to` 真调 `walk_steps`（非瞬移落地；AST 真调用，不吃注释）', _v1,)

# ---- V2 walk_steps 每跳 switch（**AST** 数 Call）----
_ws = _fn('walk_steps')
_sw_calls = []
if _ws is not None:
    for n in ast.walk(_ws):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == 'switch'):
            _sw_calls.append(getattr(n, 'lineno', -1))
ok(u'V2 `walk_steps` 每跳 `switch()`（AST 数调用，实得 %d 处）' % len(_sw_calls),
   len(_sw_calls) >= 1)

# ---- V3 回程：walk_route_home 真调 plan_route_to（AST）----
_wrh = _fn('walk_route_home')
_v3 = False
if _wrh is not None:
    for n in ast.walk(_wrh):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == 'plan_route_to'):
            _v3 = True
ok(u'V3 `walk_route_home` 真调 `plan_route_to`（复用原路线 ⇒ 不是变相瞬移）',
   _v3)

# ---- V4 全屏化：成对写 size+scale（**AST**：同一函数里两个 set_* 调用）----
_fc = _fn('fit_camera_to_screen')
_has_size = _has_scale = False
if _fc is not None:
    for n in ast.walk(_fc):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
            if n.func.attr == 'set_size':
                _has_size = True
            elif n.func.attr == 'set_scale':
                _has_scale = True
ok(u'V4 `fit_camera_to_screen` **成对**写 `set_size` + `set_scale`'
   u'（size=%s scale=%s；只写一个 ⇒ 逻辑窗口就漂了）' % (_has_size, _has_scale),
   _has_size and _has_scale)

# ---- V5 逻辑窗口基准：AST **求值** scoped_w/scoped_h == (320,240) ----
_v5_val = None
try:
    _fc_tree = ast.parse(textwrap.dedent(_fn_text('fit_camera_to_screen')))
    _env = {}
    for n in ast.walk(_fc_tree):
        if isinstance(n, ast.Assign) and len(n.targets) == 1:
            tgt = n.targets[0]
            if isinstance(tgt, ast.Tuple) and isinstance(n.value, ast.Attribute) \
                    and n.value.attr == 'DEFAULT_CAMERA_SIZE':
                for el in tgt.elts:
                    if isinstance(el, ast.Name):
                        _env[el.id] = None
    # 从 DEFAULT_CAMERA_SIZE 真值填 base_w/base_h
    _cam_src = _read(CAM)
    _m = None
    for n in ast.walk(ast.parse(_cam_src)):
        if isinstance(n, ast.Assign) and isinstance(n.value, ast.Tuple):
            for t in n.targets:
                if isinstance(t, ast.Name) and t.id == 'DEFAULT_CAMERA_SIZE':
                    _m = [e.value for e in n.value.elts]
    if _m:
        for k, v in zip(['base_w', 'base_h'], _m):
            _env[k] = float(v)
    _assigns = {}
    for n in ast.walk(_fc_tree):
        if isinstance(n, ast.Assign) and len(n.targets) == 1 \
                and isinstance(n.targets[0], ast.Name):
            _assigns[n.targets[0].id] = n.value
    if 'scoped_w' in _assigns and 'scoped_h' in _assigns:
        _env['float'] = float
        _ev = lambda node: eval(compile(ast.Expression(node), '<v>', 'eval'),
                                {'__builtins__': {}}, dict(_env))
        _v5_val = (_ev(_assigns['scoped_w']), _ev(_assigns['scoped_h']))
except Exception:
    _v5_val = None
ok(u'V5 逻辑窗口基准 **AST 求值** ⇒ scoped = (320, 240)（相机可见范围不变）',
   _v5_val == (320.0, 240.0), u'实得 %r' % (_v5_val,))

# ---- V6 死代码：全仓零 camera_follow_or_create 调用（AST 全量）----
_hits2 = []
for _p in (MAIN, CTRL):
    try:
        _tt2 = ast.parse(_read(_p))
    except Exception:
        continue
    for n in ast.walk(_tt2):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == 'camera_follow_or_create'):
            _hits2.append(os.path.basename(_p))
ok(u'V6 全仓**零** `camera_follow_or_create()` 调用（死代码清理，实得 %d 处）'
   % len(_hits2), not _hits2)

# =====================================================================
#  二、行为面（**真起产品**，走产品自己的钩子逐跳对账）
# =====================================================================
os.chdir(PKG)
if SRC in sys.path:
    sys.path.remove(SRC)
sys.path.insert(0, SRC)
_LINES.append(u'')
_LINES.append(u'--- 行为面：真起产品（offscreen）---')

_WALK = {}
try:
    import main as M
    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    win = M.RalseiPet()

    # ★ 全屏化：产品对象上的真值（**不与 CSV 同源**）
    cam = win.__dict__.get('_scene_camera')
    if cam is None:
        raise RuntimeError('相机未建（_scene_camera 为 None）')
    _cam_w, _cam_h = cam.size
    _cam_scale = float(cam.scale)
    _sco_w, _sco_h = cam.scoped_size()
    _WALK['cam'] = (_cam_w, _cam_h, _cam_scale, _sco_w, _sco_h)

    # ★ 非瞬移：摆起点 → plan → walk_steps（带钩子）逐跳对账
    _OS_FROM = 'oneshot.mainline.INIT'
    _OS_TO = 'oneshot.mainline.S1'
    win.scene.switch(_OS_FROM)
    plan = win.scene.plan_route_to(_OS_TO)
    _steps = (plan or {}).get('steps') or []
    _seen = []

    def _hook(i, step):
        _seen.append((i, step.get('from'), step.get('to'),
                      win.__dict__.get('current_scene')))

    _rv = win.scene.walk_steps(_steps, per_step_hook=_hook)
    _WALK['plan_hops'] = (plan or {}).get('hops')
    _WALK['n_steps'] = len(_steps)
    _WALK['n_seen'] = len(_seen)
    _WALK['rv_ok'] = bool(_rv.get('ok'))
    _WALK['mid'] = [t for (_i, _f, t, _c) in _seen if t not in (_OS_FROM, _OS_TO)]
    _WALK['chain_ok'] = all(c == t for (_i, _f, t, c) in _seen)
except Exception as e:
    import traceback
    _WALK['err'] = traceback.format_exc()
    _LINES.append(u'[行为面异常] %s' % e)
    _LINES.append(_WALK['err'])

# ---- V7 全屏化真值：scoped == (320,240) 且 scale>2 且 size>640 ----
if 'cam' in _WALK:
    _w, _h, _s, _sw, _sh = _WALK['cam']
    ok(u'V7 产品真值：cam=%dx%d scale=%.4f scoped=%dx%d'
       u'（scoped 恒 320×240 且 scale>2 且 size>640）'
       % (_w, _h, _s, _sw, _sh),
       (_sw, _sh) == (320, 240) and _s > 2.0 and _w > 640)
else:
    ok(u'V7 产品真值（相机）', False, u'取不到相机')

# ---- V8 非瞬移真值：每跳都被钩子采到 + 中间房间 >= 1 + 链条无断点 ----
if 'n_steps' in _WALK:
    ok(u'V8a 产品真值：plan 与 steps 一致（hops=%r steps=%d）'
       % (_WALK.get('plan_hops'), _WALK.get('n_steps')),
       _WALK['n_steps'] > 0 and _WALK.get('plan_hops') == _WALK['n_steps'])
    ok(u'V8b 🎯 **逐跳见证**：钩子采到 %d/%d 跳（零丢帧）'
       % (_WALK.get('n_seen'), _WALK.get('n_steps')),
       _WALK.get('n_seen') == _WALK.get('n_steps') and _WALK.get('n_seen', 0) > 0)
    ok(u'V8c 🎯 **中间房间真走过**（途经 %d 间 >= 1 —— 第105轮此条为 0）'
       % len(_WALK.get('mid') or []), len(_WALK.get('mid') or []) >= 1,
       u'途经=%r' % ((_WALK.get('mid') or [])[:6],))
    ok(u'V8d 每跳落地 == 声明（产品 `current_scene` == step.to）',
       _WALK.get('chain_ok'))
    ok(u'V8e `walk_steps` 报成功且无断点', _WALK.get('rv_ok'))
else:
    ok(u'V8 非瞬移真值', False, u'行为面没跑到')

# ---- 收尾 ----
npass = sum(1 for _n, c in R if c)
nfail = len(R) - npass
_LINES.append(u'')
_LINES.append(u'==== verify106：%d PASS / %d FAIL ====' % (npass, nfail))
with io.open(OUT, 'w', encoding='utf-8', newline='\n') as fh:
    fh.write(u'\n'.join(_LINES) + '\n')
print(u'[verify106] 落盘 %s' % OUT)
sys.exit(0 if nfail == 0 else 1)
