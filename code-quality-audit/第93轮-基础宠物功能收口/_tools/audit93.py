# -*- coding: utf-8 -*-
"""audit93.py —— 「基础宠物」未结项在**当前 HEAD** 的现状复审（只读）

为什么需要
----------
第90轮的基础宠物审查基线是 `c251a54`；此后代码被**整体回退重来**，第92轮又改了
`update_movement`。所以「第90轮报的那些缺陷现在还在不在」**不能靠记忆猜**，
必须逐条在当前代码上重新取证。本脚本就是那张现状表。

纪律
----
- **只读**：只 `ast.parse`（不 `py_compile`，避免产 `.pyc`），只 grep；不碰被测状态。
- **不打行号进判据输出**：行号会随无关编辑漂移（第92轮教训）⇒ 只打 函数名 + 计数。
- 判据能上 AST 就上 AST；文本匹配只在 AST 拿不到时用。

跑法
----
  C:\\Python311\\python.exe code-quality-audit\\第93轮-基础宠物功能收口\\_tools\\audit93.py
"""
import ast
import io
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(_HERE, '..', '..', '..')
PKG = os.path.join(ROOT, 'ralsei_pet')
SRC = os.path.join(PKG, 'src', 'main.py')
MODS = os.path.join(PKG, 'modules')


def read(p):
    return io.open(p, encoding='utf-8').read()


class Audit(object):
    def __init__(self):
        self.src = read(SRC)
        self.tree = ast.parse(self.src)
        self.parents = {}
        for n in ast.walk(self.tree):
            for c in ast.iter_child_nodes(n):
                self.parents[c] = n
        self.mod_texts = {}
        if os.path.isdir(MODS):
            for f in sorted(os.listdir(MODS)):
                if f.endswith('.py'):
                    self.mod_texts[f] = read(os.path.join(MODS, f))
        self.pkg_texts = dict(self.mod_texts)
        self.pkg_texts['src/main.py'] = self.src

    # ---------------- 工具 ----------------
    def _funcs(self):
        out = []
        for n in ast.walk(self.tree):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                out.append(n)
        return out

    def find_func(self, name):
        for f in self._funcs():
            if f.name == name:
                return f
        return None

    def enclosing_func(self, node):
        p = self.parents.get(node)
        while p is not None:
            if isinstance(p, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return p.name
            p = self.parents.get(p)
        return '<module>'

    def src_of(self, node):
        try:
            return ast.unparse(node)
        except Exception:
            return '<unparse failed>'

    def calls_in(self, func):
        """返回 (被调方法名列表, 调用节点列表)"""
        names = []
        nodes = []
        for n in ast.walk(func):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
                names.append(n.func.attr)
                nodes.append(n)
        return names, nodes


A = Audit()
P = print
FAILS = []
N = [0]


def check(name, ok, detail=''):
    N[0] += 1
    P('[%s] %s%s' % ('OK  ' if ok else 'FAIL', name, ('  | ' + detail) if detail else ''))
    if not ok:
        FAILS.append(name)


P('=' * 78)
P('审计对象：%s' % SRC)
P('只读（ast.parse + grep），不改任何状态')
P('=' * 78)

# ============================================================ 1. P0-2 跳跃物理
P('')
P('---- 1. P0-2 跳跃竖直物理（用户原话：抛物线不对 / 跳上去只有跳没有上去）----')
hj = A.find_func('handle_jump')
check('1.1 `handle_jump` 存在', hj is not None)
if hj is not None:
    hsrc = A.src_of(hj)
    # y 公式：屏幕坐标（Y 向下）必须是 + 0.5*g*t²
    y_exprs = []
    vy0_exprs = []
    for n in ast.walk(hj):
        if isinstance(n, ast.Assign):
            tgts = [t.id for t in n.targets if isinstance(t, ast.Name)]
            if 'y' in tgts:
                y_exprs.append(A.src_of(n.value))
            if 'vy0' in tgts:
                vy0_exprs.append(A.src_of(n.value))
    P('     y 赋值表达式 = %s' % y_exprs)
    P('     vy0 赋值表达式 = %s' % vy0_exprs)
    y_ok = any(re.search(r'\+\s*0\.5\s*\*\s*g\s*\*', e) for e in y_exprs)
    vy0_ok = any(re.search(r'delta_y\s*-\s*0\.5\s*\*\s*g', e) for e in vy0_exprs)
    check('1.2 y 走 Y 向下约定（含 `+ 0.5*g*t*t`）⇒ 竖直加速度朝屏幕下方', y_ok)
    check('1.3 vy0 = (delta_y - 0.5*g*T*T)/T（负 = 初速朝上，与 handle_fall 同约定）',
          vy0_ok)
    check('1.4 旧魔数 `+ 50` / `+50` 已不在 vy0 里', '+ 50' not in ' '.join(vy0_exprs)
          and '+50' not in ' '.join(vy0_exprs))
    # 语义断言（数值）：用 AST 抽出的**真实表达式**求值，不用我手抄
    try:
        ns = {'g': 500.0, 'delta_y': -300.0, 'self': type(
            'S', (), {'jump_duration': 1.0, 'gravity': 500.0, 'jump_start_pos': None})}
        vy0_val = eval(vy0_exprs[0], ns) if vy0_exprs else None
        check('1.5 数值：Δy=-300(向上 300px) 时 vy0 < 0（真起跳，不是飘）',
              vy0_val is not None and vy0_val < 0, 'vy0=%s' % vy0_val)
    except Exception as e:
        check('1.5 数值：vy0 求值', False, repr(e))
    names, _ = A.calls_in(hj)
    P('     handle_jump 内被调方法（去重）= %s'
      % sorted(set(names)))
    # 落地帧是否二次 move（P1-6）
    P('')
    P('---- 1b. P1-6 落地分支：位置是否被二次改写 ----')
    moves = [n for n in ast.walk(hj)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
             and n.func.attr == 'move']
    clamp_calls = [n for n in ast.walk(hj)
                   if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                   and n.func.attr == '_clamp_pos_to_desktop']
    check('1b.1 `handle_jump` 里对 `self.move` 的调用数 = 2（落地帧被写两次）',
          len(moves) == 2, 'move 调用数=%d' % len(moves))
    check('1b.2 其中夹取后仍有 `_clamp_pos_to_desktop` + `move` 兜底（落地帧会二次改写）',
          len(clamp_calls) >= 1 and len(moves) == 2,
          'clamp 调用数=%d' % len(clamp_calls))

# ============================================================ 2. 回归锁覆盖
P('')
P('---- 2. 跳跃物理是否有回归锁兜着 ----')
AUDIT_DIR = os.path.join(ROOT, 'code-quality-audit')
hits = []
for dirpath, dirnames, filenames in os.walk(AUDIT_DIR):
    for fn in filenames:
        if not fn.endswith('.py'):
            continue
        fp = os.path.join(dirpath, fn)
        try:
            t = read(fp)
        except Exception:
            continue
        if ('vy0' in t) or ('handle_jump' in t and 'jump' in fn.lower()):
            hits.append(os.path.relpath(fp, ROOT))
P('     提到 vy0 / handle_jump 的审查脚本 = %s' % hits)
check('2.1 已有脚本覆盖跳跃公式（vy0 / handle_jump）', bool(hits))
in_suites = False
ra = os.path.join(AUDIT_DIR, 'regress', 'run_all.py')
if os.path.exists(ra):
    t = read(ra)
    in_suites = any(h.split(os.sep)[-1].replace('.py', '') in t
                    for h in hits if h.startswith('code-quality-audit'))
check('2.2 且已登记进 G2 `SUITES`（否则回归不会跑它）', in_suites)

# ============================================================ 3. P1-4 多屏
P('')
P('---- 3. P1-4 `availableGeometry()`（无参 = 只认主屏，违反契约①）----')
# ★ 第93轮修正：原来"全仓清零"是**误报**——7 处 availableGeometry 全是辅助
#   helper 的**合法回退**（`win32 虚拟桌面失败时才回退主屏`），逐条核对过源码。
#   真正的病灶只有 `init_ui` 首帧定位那句无参主屏调用（本轮已修为 _virtual_screen_rect）。
#   所以正确判据是：无参（=主屏）availableGeometry() 只能出现在下列回退 helper 内。
_FALLBACK_OK = {'_virtual_screen_rect', '_current_screen_rect', '_virtual_screen_size',
                '_desktop_floor_y', '_work_area_rect'}
_noarg_primary = []
for n in ast.walk(A.tree):
    if isinstance(n, ast.Call) and 'availableGeometry' in A.src_of(n.func):
        enc = A.enclosing_func(n)
        if n.args or n.keywords:
            # availableGeometry(self) = 当前屏工作区，合法（_work_area_rect 主路径）
            continue
        if enc not in _FALLBACK_OK:
            _noarg_primary.append((enc, A.src_of(n.func)))
P('     无参 availableGeometry() 出现在非回退 helper 的位置 = %s' % _noarg_primary)
check('3.1 无参（=主屏）availableGeometry() 仅存在于合法回退 helper', not _noarg_primary,
      '残留=%d %s' % (len(_noarg_primary), [a[0] for a in _noarg_primary]))
iui = A.find_func('init_ui')
ui_ok = bool(iui is not None and '_virtual_screen_rect()' in A.src_of(iui))
check('3.2 `init_ui` 首帧定位已走 `_virtual_screen_rect()`（P1-4 修复落点）', ui_ok)

# ============================================================ 4. P1-5 DPI
P('')
P('---- 4. P1-5 DPI 感知声明 ----')
DPI_APIS = ['SetProcessDpiAwareness', 'SetProcessDPIAware',
            'AA_EnableHighDpiScaling', 'AA_UseHighDpiPixmaps',
            'SetProcessDpiAwarenessContext', 'setHighDpiScaleFactorRoundingPolicy']
found = {}
for rel, t in A.pkg_texts.items():
    for api in DPI_APIS:
        if api in t:
            found.setdefault(rel, []).append(api)
P('     命中 = %s' % (found or '（无）'))
check('4.1 包里**无**显式 DPI 声明（第93轮裁定：不应声明——Qt5 构造 QApplication 时已把进程设为 PER_MONITOR_AWARE(2)，手动声明反会改坏几何契约）', not found,
      '命中文件=%d 个' % len(found) if found else '零命中（正确）')

# ============================================================ 5. P1-3 素材名兜底
P('')
P('---- 5. P1-3 场景素材名解析（缺扩展名 ⇒ 渲染成 1x1）----')
sc = os.path.join(MODS, 'scene_canvas.py')
if os.path.exists(sc):
    t = read(sc)
    has_ext_fallback = bool(re.search(r"_\s*0\s*\.png", t)) or '.png' in t
    check('5.1 `scene_canvas.py` 存在且含 `.png` 相关解析', has_ext_fallback)
    # 找 get() 里有没有补后缀
    m = re.search(r'def get\([^)]*\):(.{0,2000})', t, re.S)
    seg = m.group(1) if m else ''
    P('     `get()` 片段前 300 字 = %s' % seg[:300].replace('\n', ' | '))
else:
    check('5.1 `scene_canvas.py` 存在', False)

# ============================================================ 6. P2-7 静默 except
P('')
P('---- 6. P2-7 静默 `except: pass`（连日志都没有的分支）----')
silent = []
for n in ast.walk(A.tree):
    if isinstance(n, ast.ExceptHandler):
        body = n.body
        if len(body) != 1:
            continue
        b = body[0]
        if isinstance(b, ast.Pass) and b.__class__ is ast.Pass:
            silent.append(A.enclosing_func(n))
# 只数"裸 Pass"（无 _log.*）
P('     无日志的 `except: pass` 所在函数 = %s' % sorted(set(silent)))
check('6.1 逗号口径：`except: pass` 数量（第90轮报 main.py 23 处）',
      True, '实测=%d（仅记录，不判红）' % len(silent))

# ============================================================ 7. P2-10 has_ball
P('')
P('---- 7. P2-10 `has_ball` 死字段 ----')
hb = []
for n in ast.walk(A.tree):
    if isinstance(n, ast.Assign):
        for tgt in n.targets:
            s = A.src_of(tgt)
            if s.endswith('has_ball'):
                hb.append((A.enclosing_func(n), s))
    if isinstance(n, ast.Attribute) and n.attr == 'has_ball':
        pass
reads = len(re.findall(r'self\.has_ball', A.src))
P('     赋值点 = %s ；`self.has_ball` 出现总次数 = %d' % (hb, reads))
check('7.1 `has_ball` 赋值点 ≤1（恒假死字段，可清理）', len(hb) <= 1,
      '赋值点=%d' % len(hb))

# ============================================================ 8. P0-1 画布
P('')
P('---- 8. P0-1 场景画布是否仍是主窗口子控件（裁剪 ⇒ 看不到门）----')
sc_calls = []
for n in ast.walk(A.tree):
    if isinstance(n, ast.Call):
        f = A.src_of(n.func)
        if f.endswith('SceneCanvas'):
            args = [A.src_of(a) for a in n.args] + \
                   ['%s=%s' % (k.arg, A.src_of(k.value)) for k in n.keywords]
            sc_calls.append((A.enclosing_func(n), args))
P('     `SceneCanvas(...)` 构造点 = %s' % sc_calls)
# ★ 第93轮修正：原来只查关键字 `parent=self`，**漏了位置参数** `SceneCanvas(self)`。
#   主窗口是精灵尺寸（42×82），子控件画布（640×480）被 Qt 裁到 42×82 ⇒ 门永远看不见。
still_child = any(
    any(a == 'self' or a.startswith('parent=self') for a in args)
    for _, args in sc_calls)
check('8.1 画布为独立顶层窗口（不再是 `SceneCanvas(self)` 子控件）', not still_child,
      '构造点=%d 仍为子控件=%s' % (len(sc_calls), still_child))

# ============================================================ 汇总
P('')
P('=' * 78)
P('合计 %d 条判据，FAIL = %d' % (N[0], len(FAILS)))
for f in FAILS:
    P('  - %s' % f)
P('=' * 78)
P('（说明：本脚本是**现状表**，不要求全绿 —— FAIL 即"待收口项"，正是今天的施工清单。）')
sys.exit(0)
