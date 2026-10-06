# -*- coding: utf-8 -*-
u"""第67轮 · 幽灵线接线回归锁（A~F 六组，**每组配负控制**）。

一句话：把「幽灵有多清楚」这件事**钉回原作原文**，把「谁能看见」这件事
钉回**用户口径**，并证明它**真的接在桌宠上**。

分组
----
  A 零依赖纪律（AST）      —— `ghost_system` 是 L1 纯逻辑（只有 `math`、零函数内 import）
  B 照抄锚点回原文（AST+正则）—— 每个数字都从 `_evidence/gml64/*.gml` **重新解析**出来再比，
                              不是拿模块里的字面量跟自己比（那是恒真判据）。
                              ★ **第74轮 B5 追加**：`obj_ghostbuds.Draw_0`（停走式）的
                              `0.5 / 0.3`（过场档）与 `0.9 / 0.6`（非过场档）**也回原文解析**
                              —— 这两组数长得像、含义不同，抄错一处就是"看着在照抄、
                              其实抄了另一只的数"。
  C 行为（真实量级）正·负·对照 —— 距离用真实像素、接触用真实秒数，不用 0.001 这种玩具量级。
                              ★ **第74轮 B5 追加** C32~C49：停走式纯函数（站住升 / 走动降 /
                              下限 0 / **走动与档位无关** / 过场档对照）+ 两种模式**互不串味**
                              + 跟飘位置 + **浮动偏移不被吃掉**（含坏写法负控制）
  D 素材对账             —— 帧数/原生尺寸/45 个 PNG 的 sha256 逐个对 `_source.json`
  E 接线（AST + 真机）     —— `GHOST_ENABLED` 真被读、`_ghost_tick` 真被调**且在早退分支之前**、
                              真机起得来、**不置顶**、不吃鼠标事件。
                              ★ **第74轮 B5 追加** E19a~E41：产品模式 == `GHOST_MODE`、
                              "走没走"真透传、产品侧**不碰**过场档、跟飘时位置与浮动都真动
  F 判据自身体检          —— 负控制成对 + 正则未命中必须**报红**（不许静默 None 混过去）
                              ★ F 是**元**判据，打印在最后一位：它的 F6 要总账
                                "它之前打印的每一行各恰好一个标记"，所以不许往它后面再塞组

纪律（第67轮特别强调，因为本轮已经栽过）
----------------------------------------
★ 「判据本身也是被测物」。本轮**已实测栽过 1 次**：首版 docstring 写
  「Chara 的 `obj_ghostint2` 在 Create 里**没有任何门槛**」—— 是凭印象写的假事实，
  逐条回原文时被 B 段逮到。**所以 B 段必须从原文解析**，而不是抄常量。

★ 只 `ast.parse`，不产 `.pyc`；**不改变任何被测状态**。
★ 不联网；需要 QApplication 时走 offscreen；`RALSEI_MEMORY_DIR` 用 `setdefault`
  （run_all 的 hermetic 环境优先），所以本套件**不会写用户真实数据**。

必须用 C:\\Python311\\python.exe 运行。
"""
import ast
import contextlib
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')


# ---------------------------------------------------------------- 路径
def _find_root(start):
    u"""往上找"含 `ralsei_pet` 的那一层" = 仓库根。

    ★ 为什么**不写死** `os.path.join(HERE, '..', '..')`：
      本脚本放在 `<轮次>/_tools/` 下（与第60~66轮的交付同形），层数与会放在
      `<轮次>/` 下的脚本**不一样**。写死层数就是一条"改个位置就静默失效"的判据
      —— 而它失效时**不会报红**，只会去找另一个目录、然后断言全绿。
      ⇒ 用目录特征定位，并在找不到时**报红**（见 A0）。
    """
    p = os.path.abspath(start)
    for _ in range(8):
        if os.path.isdir(os.path.join(p, 'ralsei_pet')):
            return p
        nxt = os.path.dirname(p)
        if nxt == p:
            break
        p = nxt
    return None


HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = _find_root(HERE)
AUD = os.path.join(ROOT, 'code-quality-audit') if ROOT else None
PET = os.path.join(ROOT, 'ralsei_pet') if ROOT else None
SRC = os.path.join(PET, 'src') if PET else None
MODS = os.path.join(PET, 'modules') if PET else None
GHOST_DIR = os.path.join(PET, 'assets', 'sprites', 'ghost') if PET else None
GML64 = os.path.join(AUD, u'第64轮-人设原文重抽与红黄勘查', '_evidence', 'gml64') if AUD else None

_QT_TOP = {'PyQt5', 'PyQt6', 'PySide2', 'PySide6'}
_BUSINESS = {'data_store', 'memory_store', 'memory_system', 'config_manager',
             'relationship', 'npc_system', 'npc_persona', 'scene_controller',
             'soul_overlay', 'ghost_overlay', 'logger_utils', 'lazy_log'}

#: 本仓库 `modules/*.py` 的真实文件名（去扩展名）—— `_project_imports` 用它过滤，
#: 免得把 `os` / `logging` 这种标准库也当成"项目内依赖"（首版就误报了）。
_REPO_MODS = frozenset(
    f[:-3] for f in os.listdir(MODS) if f.endswith('.py')
) if (MODS and os.path.isdir(MODS)) else frozenset()

# ★ 必须在读文件之前把两个目录挂上 path —— 否则 `import ghost_system` 直接
#   ModuleNotFoundError（第67轮首跑就栽在这里：A/B 段读文件走绝对路径没事，
#   一到 `import ghost_system as GS` 就炸）。
for _p in (MODS, SRC):
    if _p and _p not in sys.path:
        sys.path.insert(0, _p)

PASS, FAIL = [], []
#: 每条判据**实际打印出来的那一行**（F 组用它做"标记数不许被自己的判据名带歪"的自检）。
#: ★ 这不是多余：首版 F1 的**判据名里**写了方括号标记字面量，于是
#:   `run_all.count_results` 的正则在同一行数到 2 个 PASS + 1 个 FAIL
#:   —— 套件全绿却会被算成"有 FAIL"。**判据名也会被计数**。
_LINES = []


def _record(name, cond):
    u"""(PASS/FAIL) 的**记账**部分 —— 不打印。用于 F 组体检报告口本身。"""
    (PASS if cond else FAIL).append(name)
    return bool(cond)


def _mask(t):
    u"""把失败详情里可能出现的**标记字面量**遮掉。

    ★ 为什么：`run_all.count_results` 是**全文正则计数** —— 只要某条判据的
      detail 里带了标记字面量（比如"实测到的输出行"），计数就会被带歪。
      本套件已经栽过一次（F1 的判据名），所以这里做一道**结构性**防线：
      详情的来源再脏也污染不到计数。
    """
    return (str(t).replace('[PASS]', '(P)').replace('[FAIL]', '(F)')
            .replace('[ OK ]', '(OK)'))


def ok(name, cond, detail=''):
    u"""统一报告口。★ 打印的是方括号标记的**字面量** —— `run_all.py`
    的 `count_results()` 只认它们（以及方括号 OK 那一种）；写成别的形状 ⇒ PASS 恒 0
    （本项目踩过，见记忆 §3）。"""
    line = ('[PASS] ' if cond else '[FAIL] ') + name + \
        ('' if cond else '   <<< ' + _mask(detail))
    _record(name, cond)
    _LINES.append(line)
    print(line)
    return bool(cond)


def section(title):
    print('')
    print('=== %s ===' % title)


def _read(p):
    with io.open(p, encoding='utf-8') as fh:
        return fh.read()


# ---------------------------------------------------------------- AST 工具
def _imports_of(src):
    u"""源码里 import 出的模块名集合。

    ★ `from X import a as b` 必须同时记 `X` 与 `X.a` —— 只记 `X` 会让
      `from modules import ghost_system` 这种写法**判不出来**（第67轮首轮就踩到：
      A9 会报红，而真相是判据漏了别名）。
    """
    out = set()
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, ast.Import):
            for a in n.names:
                out.add(a.name)
                out.add(a.name.split('.')[0])
        elif isinstance(n, ast.ImportFrom):
            if n.level:
                out.add('.' * n.level + (n.module or ''))
            elif n.module:
                out.add(n.module)
                out.add(n.module.split('.')[0])
                for a in n.names:
                    out.add(n.module + '.' + a.name)
    return out


def _roots_of(src):
    u"""源码 import 的**顶层名**集合（`PyQt5.QtCore` → `PyQt5`；`modules.x` → `modules`）。

    ★ 为什么另开一个：`_imports_of` 会同时给出 `X` 与 `X.a` 两种粒度，用它做
      "白名单差集"会把 `X.a` 全判成越界（第67轮首跑就栽在这里：A6 报了 6 条
      `modules.*` / `logger_utils.get_logger` 的假越界）。**粒度要对上用途** ——
      查 Qt/存储层用顶层名，查"允许哪些姐妹们"用 `_project_imports`。
    """
    return {n.split('.')[0] for n in _imports_of(src)}


def _project_imports(src):
    u"""源码 import 的**本仓库模块名**集合（`from modules import x` ⇒ `x`；
    `from modules.soul_overlay import y` ⇒ `soul_overlay`；`import ghost_system` ⇒ 同名）。

    ★ 必须用 `_REPO_MODS`（`modules/*.py` 的真实文件名）**过滤**：
      首版没过滤 ⇒ `import os` 也被算成"项目内依赖"，A4（ghost_system 零项目内 import）
      与 A7（ghost_overlay 的上游白名单）双双**误报**。
      ⇒ 教训：**判据的粒度/取值域必须与"事实"对齐**（记忆 §4：报红先怀疑判据本身）。
    """
    out = set()
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, ast.Import):
            for a in n.names:
                out.add(a.name.split('.')[0])
        elif isinstance(n, ast.ImportFrom):
            mod = n.module or ''
            if mod in ('', 'modules'):
                for a in n.names:
                    out.add(a.name)
            else:
                out.add(mod.split('.')[-1] if mod.startswith('modules.') else mod)
    return {c for c in out if c in _REPO_MODS}


def _func_level_imports(src):
    u"""函数体内的 import（L1 零依赖模块不许有 —— 它让"这个模块依赖什么"
    变成运行时才知道的事，静态检查就没意义了）。"""
    hits = []
    for fn in ast.walk(ast.parse(src)):
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for n in ast.walk(fn):
                if isinstance(n, (ast.Import, ast.ImportFrom)):
                    hits.append((fn.name, n.lineno))
    return hits


def _attrs_of(src):
    u"""源码里**作为代码**出现的属性名集合（`Qt.WindowStaysOnTopHint` ⇒ 记下它）。

    ★ 为什么用 AST 而不是 `'WindowStaysOnTopHint' not in src`：
      后者会被**注释和 docstring** 命中 —— `ghost_overlay.py` 的注释里写着
      "不加 WindowStaysOnTopHint"，朴素子串检查会把这条判据**判成红的**
      （= 判据过窄导致误报，记忆 §4）。AST 只看代码。
    """
    out = set()
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, ast.Attribute):
            out.add(n.attr)
        elif isinstance(n, ast.Name):
            out.add(n.id)
    return out


def _find_func(src, name, cls_name=None):
    tree = ast.parse(src)
    scope = tree
    if cls_name:
        for n in tree.body:
            if isinstance(n, ast.ClassDef) and n.name == cls_name:
                scope = n
                break
    for n in ast.walk(scope):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name:
            return n
    return None


def _direct_returns(fn_node):
    u"""函数体里**非嵌套**的 `return` 行号（不下钻进内层 def，否则会拿到别人的 return）。
    这是"调用点必须在所有早退分支之前"这条判据的**唯一**依据。"""
    out = []

    def walk(node):
        for ch in ast.iter_child_nodes(node):
            if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                continue
            if isinstance(ch, ast.Return):
                out.append(ch.lineno)
            walk(ch)

    walk(fn_node)
    return sorted(out)


def _calls_in(fn_node, names):
    u"""函数体里（不含嵌套 def）对 `names` 之一的调用 ⇒ `[(lineno, name)]`。"""
    out = []

    def walk(node):
        for ch in ast.iter_child_nodes(node):
            if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if isinstance(ch, ast.Call):
                f = ch.func
                nm = f.attr if isinstance(f, ast.Attribute) else (
                    f.id if isinstance(f, ast.Name) else None)
                if nm in names:
                    out.append((ch.lineno, nm))
            walk(ch)

    walk(fn_node)
    return sorted(out)


def _call_kwarg_source(src, fn_node, call_attr, kw):
    u"""在 `fn_node` 内部找 `….call_attr(..., kw=…)`，返回该实参的**源码片段**列表。

    ★ 为什么返回"源码片段"而不是"有没有这个关键字"：这样"真把产品开关传下去"与
      "传了个写死的常量"能分辨 —— 本项目要钉的正是前者（传了 `mode='follow'` 也是接线，
      但 `GHOST_MODE` 就变成死常量了，那是另一个 bug）。
    ★ 为什么不能自己去 `ast.walk` 就完事：`fn_node` 必须是**已经 parse 过的树**
      （本套件里统一从 `ast.parse(src)` 取），不能拿源码片段重新 parse ——
      `ast.get_source_segment` 给的是**带缩进**的原文，`ast.parse` 会 IndentationError。
    """
    out = []
    if fn_node is None:
        return out
    for n in ast.walk(fn_node):
        if isinstance(n, ast.Call):
            f = n.func
            nm = f.attr if isinstance(f, ast.Attribute) else (
                f.id if isinstance(f, ast.Name) else None)
            if nm == call_attr:
                for k in n.keywords:
                    if k.arg == kw:
                        out.append(ast.get_source_segment(src, k.value) or '')
    return out


def _args_of(fn_node):
    u"""函数的全部形参名（含 `*args`/`**kwargs`/仅关键字参数）。"""
    if fn_node is None:
        return []
    a = fn_node.args
    out = [x.arg for x in list(a.args) + list(a.kwonlyargs)]
    if a.vararg:
        out.append(a.vararg.arg)
    if a.kwarg:
        out.append(a.kwarg.arg)
    return out


def _kwarg_true_calls(src, kw):
    u"""源码里 `….kw=True`（**字面量真值**）的调用 ⇒ 行号列表。

    ★ 为什么要专门一个"字面量真值"探针：`cutscene=cutscene` 这种**透传**是合法的
      （默认 `None` ⇒ 状态保持 `False`），而 `cutscene=True` 是"真的把过场档打开了"。
      只看"有没有这个关键字"会把透传也判红（本条首版就这么误报的）；
      只判"有没有真值"才对准事实。
    """
    out = []
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, ast.Call):
            for k in n.keywords:
                if k.arg == kw and isinstance(k.value, ast.Constant) \
                        and k.value.value is True:
                    out.append(getattr(n, 'lineno', -1))
    return out


# ===========================================================================
#  A  零依赖纪律（AST）
# ===========================================================================
def group_a():
    section(u'A 零依赖纪律（AST）')
    ok('A0 仓库根已定位（找到含 ralsei_pet 的那一层）',
       bool(ROOT) and os.path.isdir(MODS or ''), 'ROOT=%r' % (ROOT,))

    gs_py = os.path.join(MODS, 'ghost_system.py')
    go_py = os.path.join(MODS, 'ghost_overlay.py')
    ok('A1 两个模块文件都在', os.path.isfile(gs_py) and os.path.isfile(go_py),
       'gs=%s go=%s' % (os.path.isfile(gs_py), os.path.isfile(go_py)))
    if not (os.path.isfile(gs_py) and os.path.isfile(go_py)):
        return

    gs_src = _read(gs_py)
    go_src = _read(go_py)
    gs_roots = _roots_of(gs_src)
    go_roots = _roots_of(go_src)
    gs_proj = _project_imports(gs_src)
    go_proj = _project_imports(go_src)

    ok('A2 ghost_system（L1）只 import 标准库（math / os / io / json）',
       gs_roots <= {'math', 'os', 'io', 'json'}, 'imports=%s' % sorted(gs_roots))
    ok('A3 ghost_system 不 import 任何 PyQt',
       not (gs_roots & _QT_TOP), '命中=%s' % sorted(gs_roots & _QT_TOP))
    ok('A4 ghost_system 零项目内 import（初始化环）',
       not gs_proj, '命中=%s' % sorted(gs_proj))
    _fl = _func_level_imports(gs_src)
    ok('A5 ghost_system 零函数内 import（L1 铁律）', not _fl, '命中=%s' % (_fl[:5],))

    # ghost_overlay 是 L2（Qt），允许：标准库 + PyQt5 + 三个明确的上游
    _go_std = {'logging', 'os', 'math', 'sys', 'time', 'io', 'json'}
    _go_up = {'ghost_system', 'soul_overlay', 'logger_utils'}
    _go_roots_bad = go_roots - _go_std - _go_up - _QT_TOP - {'modules'}
    _go_proj_bad = go_proj - _go_up
    ok('A6 ghost_overlay（L2）顶层名只在 标准库 / PyQt5 / modules / 三个上游 之内',
       not _go_roots_bad, '越界=%s' % sorted(_go_roots_bad))
    ok('A7 ghost_overlay 的项目内依赖 ⊆ {ghost_system, soul_overlay, logger_utils}',
       not _go_proj_bad, '越界=%s' % sorted(_go_proj_bad))
    ok('A8 ghost_overlay **不** import 存储层（data_store / memory_*）',
       not (go_roots & {'data_store', 'memory_store', 'memory_system'}),
       '命中=%s' % sorted(go_roots & {'data_store', 'memory_store', 'memory_system'}))
    ok('A9 ghost_overlay 复用 soul_overlay.virtual_screen_rect（唯一实现，不重写）',
       'virtual_screen_rect' in go_src and 'soul_overlay' in go_proj, '未复用')

    main_src = _read(os.path.join(SRC, 'main.py'))
    main_proj = _project_imports(main_src)
    ok('A10 main.py 真导入了两个幽灵模块',
       {'ghost_system', 'ghost_overlay'} <= main_proj,
       '导入的幽灵相关=%s' % sorted(x for x in main_proj if 'ghost' in x))

    # ---- 负控制：判据真能抓到"Qt / 业务模块 / 函数内 import" ----
    ok('A11 负控制 · 判据能抓到 Qt / 业务模块 / 函数内 import',
       bool(_roots_of('import PyQt5.QtCore\n') & _QT_TOP)
       and bool(_project_imports('from data_store import x\n') & _BUSINESS)
       and bool(_func_level_imports('def f():\n    import os\n    return os\n')),
       '三项里至少一项没抓到')


# ===========================================================================
#  B  照抄锚点回原文（数字从 GML **重新解析**，不与模块字面量自比）
# ===========================================================================
def group_b():
    section(u'B 照抄锚点回原文（从 _evidence/gml64 重新解析）')
    step = os.path.join(GML64, 'gml_Object_obj_ghostint2_Step_1.gml')
    cr_chara = os.path.join(GML64, 'gml_Object_obj_ghostint2_Create_0.gml')
    cr_clover = os.path.join(GML64, 'gml_Object_obj_ghostint_Create_0.gml')
    ok('B0 三份原文物证都在',
       os.path.isfile(step) and os.path.isfile(cr_chara) and os.path.isfile(cr_clover),
       'step=%s' % os.path.isfile(step))
    if not (os.path.isfile(step) and os.path.isfile(cr_chara)
            and os.path.isfile(cr_clover)):
        return
    S = _read(step)
    CC = _read(cr_chara)
    CV = _read(cr_clover)

    # ---- 每个正则都必须**命中**；未命中一律报红（不许静默 None 混过去）----
    PATS = {
        'near_dist':   (S, r'else\s+if\s*\(\s*dist\s*<\s*(\d+)\s*\)'),
        'num':         (S, r'(\d+(?:\.\d+)?)\s*/\s*\(\s*dist\s*\+\s*1\s*\)'),
        'dist_max':    (S, r'disto\s*>\s*([\d.]+)'),
        'fade':        (S, r'image_alpha\s*-=\s*([\d.]+)'),
        'bright':      (S, r'image_alpha\s*<\s*([\d.]+)'),
        'dim':         (S, r'image_alpha\s*>\s*([\d.]+)'),
        'lev_step':    (S, r'y\s*\+=\s*([\d.]+)'),
        'lev_span':    (S, r'starty\s*\+\s*(\d+)'),
        'image_speed': (CC, r'image_speed\s*=\s*([\d.]+)'),
        'goup0':       (CC, r'goup\s*=\s*(\d+)'),
        'simp1':       (CC, r'simplecheck\s*=\s*(\d+)'),
        'frame_def':   (S, r'image_index\s*=\s*(\d+)'),
        'murderlv':    (CV, r'scr_murderlv\(\)\s*>=\s*(\d+)'),
    }
    got, miss = {}, []
    for k, (txt, pat) in PATS.items():
        m = re.search(pat, txt)
        if m is None:
            miss.append(k)
        else:
            got[k] = m.group(1)
    ok('B1 原文正则全部命中（未命中 = 判据失效，必须报红）', not miss,
       '未命中=%s' % miss)
    print('    [info] 从原文解析出的量: %s' % json.dumps(got, sort_keys=True))
    if miss:
        return

    import ghost_system as GS

    ok('B2 看得见的距离 == 原文 `dist < %s`' % got['near_dist'],
       GS.GHOST_NEAR_DIST == float(got['near_dist']),
       '模块=%r 原文=%r' % (GS.GHOST_NEAR_DIST, got['near_dist']))
    _num = float(got['num'])
    ok('B3 距离式 alpha == 原文 `%s / (dist + 1)`（用 dist=49 ⇒ 真实量级）' % got['num'],
       abs(GS.alpha_for_distance(49.0) - _num / 50.0) < 1e-9,
       '模块算出=%r 原文算出=%r' % (GS.alpha_for_distance(49.0), _num / 50.0))
    ok('B4 封顶 == 原文 `disto > %s`' % got['dist_max'],
       abs(GS.GHOST_DIST_ALPHA_MAX - float(got['dist_max'])) < 1e-9,
       '模块=%r' % GS.GHOST_DIST_ALPHA_MAX)
    ok('B5 淡出步长 == 原文 `image_alpha -= %s`' % got['fade'],
       abs(GS.GHOST_FADE_STEP - float(got['fade'])) < 1e-9,
       '模块=%r' % GS.GHOST_FADE_STEP)
    ok('B6 亮档 == 原文 cutscene 上界 `image_alpha < %s`' % got['bright'],
       abs(GS.GHOST_BRIGHT_ALPHA - float(got['bright'])) < 1e-9,
       '模块=%r' % GS.GHOST_BRIGHT_ALPHA)
    ok('B7 暗档 == 原文 cutscene `image_alpha > %s`' % got['dim'],
       abs(GS.GHOST_DIM_ALPHA - float(got['dim'])) < 1e-9,
       '模块=%r' % GS.GHOST_DIM_ALPHA)
    ok('B8 浮动步长 == 原文 `y += %s`' % got['lev_step'],
       abs(GS.GHOST_LEVITATE_STEP - float(got['lev_step'])) < 1e-9,
       '模块=%r' % GS.GHOST_LEVITATE_STEP)
    ok('B9 浮动范围 == 原文 `starty + %s`' % got['lev_span'],
       abs(GS.GHOST_LEVITATE_RANGE - float(got['lev_span'])) < 1e-9,
       '模块=%r' % GS.GHOST_LEVITATE_RANGE)
    ok('B10 定点幽灵不播动画 == 原文 `image_speed = %s`' % got['image_speed'],
       abs(GS.GHOST_IMAGE_SPEED - float(got['image_speed'])) < 1e-9,
       '模块=%r' % GS.GHOST_IMAGE_SPEED)
    ok('B11 帧兜底值 == 原文 `image_index = %s`（表情映射的起始赋值）' % got['frame_def'],
       GS.GHOST_FRAME_DEFAULT == int(got['frame_def']),
       '模块=%r' % GS.GHOST_FRAME_DEFAULT)
    _st = GS.GhostState()
    ok('B12 浮动初值 == 原文 Create `goup = %s; simplecheck = %s`'
       % (got['goup0'], got['simp1']),
       _st.goup == int(got['goup0']) and _st.simplecheck == int(got['simp1']),
       '模块=(%r,%r)' % (_st.goup, _st.simplecheck))
    ok('B13 `starty = y` 被照抄（出生时 starty == home_y）',
       abs(GS.GhostState(home_x=1.0, home_y=777.0).starty - 777.0) < 1e-9)

    # ---- ★ 本轮自纠的那条：门槛**两只都有**，且都是"杀戮/LV"方向 ----
    ok('B14 Chara 的定点幽灵**也有**销毁门槛（`obj_mainchara.kill == 1`）'
       u' —— 首版 docstring 曾写"没有任何门槛"，是假事实',
       'obj_mainchara.kill == 1' in CC, '原文里没找到 kill 门槛')
    ok('B15 Clover 的销毁门槛 == 原文 `scr_murderlv() >= %s`' % got['murderlv'],
       ('global.flag[7] == 1' in CV)
       and (('scr_murderlv() >= %s' % got['murderlv']) in CV),
       '原文里没找到 murderlv 门槛')
    ok('B16 门槛方向与用户口径**相反**这件事已被正文写明（不许静默改语义）',
       (u'方向相反' in _read(os.path.join(MODS, 'ghost_system.py')))
       and (u'方向相反' in _read(os.path.join(SRC, 'main.py'))),
       '模块/主机有一处没写')

    # ---- 负控制：改了原文数字，判据必须能分辨 ----
    tampered = S.replace('10 / (dist + 1)', '8 / (dist + 1)')
    m2 = re.search(PATS['num'][1], tampered)
    ok('B17 负控制 · 篡改原文分子 10→8 后解析值随之变（判据有鉴别力）',
       (m2 is not None) and (m2.group(1) != got['num']) and (float(m2.group(1)) != _num),
       '解析到 %r' % (m2.group(1) if m2 else None))
    ok('B18 负控制 · 拿掉 kill 门槛后 B14 的判据会翻假',
       'obj_mainchara.kill == 1' not in
       CC.replace('obj_mainchara.kill == 1', 'obj_mainchara.kill == 0'))

    # ==================================================================
    #  B5 追加：**停走式**（`obj_ghostbuds.Draw_0`）的锚点也**回原文重新解析**
    #  ------------------------------------------------------------------
    #  为什么单开一段：这一段的四个数（0.5 / 0.3 / 0.9 / 0.6）与 `obj_ghostint2`
    #  那组**长得像但含义不同** —— 同一个词「过场」在两只对象里对应两组不同的数。
    #  抄错一处就会变成"看着在照抄、其实抄了另一只的数"，所以必须回**buds 自己的原文**解析。
    # ==================================================================
    buds = os.path.join(GML64, 'gml_Object_obj_ghostbuds_Draw_0.gml')
    ok('B19 停走式原文物证在（obj_ghostbuds.Draw_0）', os.path.isfile(buds), buds)
    if not os.path.isfile(buds):
        return
    BU = _read(buds)
    _ic = BU.find('instance_exists(obj_starker)')
    _in = BU.find('else if (obj_mainchara.moving == 0)')
    _im = BU.find('if (obj_mainchara.moving == 1)')
    ok('B20 三个分支的锚点都定位到了（防"切片切错 ⇒ 后面全部静默变绿"）',
       -1 < _ic < _in < _im,
       'cut=%s non=%s mov=%s' % (_ic, _in, _im))
    if not (-1 < _ic < _in < _im):
        return
    _cut, _non, _mov = BU[_ic:_in], BU[_in:_im], BU[_im:]

    def _one(txt, pat, label):
        u"""单值解析 —— **未命中返回 None**（调用处一律要求非 None，不许静默混过去）。"""
        m = re.search(pat, txt)
        return None if m is None else m.group(1)

    _cut_br = _one(_cut, r'juandice\s*>\s*0\s*&&\s*clover_alpha\s*<\s*([\d.]+)', 'cutscene.bright')
    _cut_dm = _one(_cut, r'juandice\s*==\s*-1\s*&&\s*clover_alpha\s*<\s*([\d.]+)', 'cutscene.dim')
    _non_br = _one(_non, r'clover_alpha\s*<\s*([\d.]+)\s*&&\s*juandice\s*>\s*0', 'plain.bright')
    _non_dm = _one(_non, r'clover_alpha\s*<\s*([\d.]+)\s*&&\s*juandice\s*==\s*-1', 'plain.dim')
    _rise = _one(_non, r'clover_alpha\s*\+=\s*([\d.]+)', 'rise.step')
    _fall = _one(_mov, r'clover_alpha\s*-=\s*([\d.]+)', 'walk.step')
    _lv = _one(BU, r'scr_murderlv\(\)\s*<\s*(\d+)', 'murderlv.lt')
    ok('B21 停走式四个上界 + 步长 + 暗档轴 全部解析成功（未命中 = 判据失效，必须报红）',
       all(v is not None for v in (_cut_br, _cut_dm, _non_br, _non_dm, _rise, _fall, _lv)),
       u'cut=(%s,%s) non=(%s,%s) rise=%s fall=%s lv=%s'
       % (_cut_br, _cut_dm, _non_br, _non_dm, _rise, _fall, _lv))
    if not all(v is not None for v in (_cut_br, _cut_dm, _non_br, _non_dm, _rise, _fall, _lv)):
        return
    print('    [info] 从 buds 原文解析出的量: 过场=%s/%s 非过场=%s/%s 步长=%s/%s 暗档轴=murderlv<%s'
          % (_cut_br, _cut_dm, _non_br, _non_dm, _rise, _fall, _lv))

    ok('B22 停走式**过场**档 == 原文 `%s` / `%s`（亮 / 暗）'
       % (_cut_br, _cut_dm),
       abs(GS.GHOST_BUDS_CUTSCENE_BRIGHT_ALPHA - float(_cut_br)) < 1e-9
       and abs(GS.GHOST_BUDS_CUTSCENE_DIM_ALPHA - float(_cut_dm)) < 1e-9,
       '模块=%r/%r' % (GS.GHOST_BUDS_CUTSCENE_BRIGHT_ALPHA,
                      GS.GHOST_BUDS_CUTSCENE_DIM_ALPHA))
    ok('B23 停走式**非过场**档 == 原文 `%s` / `%s`，且**复用的就是** `GHOST_BRIGHT_ALPHA`/'
       '`GHOST_DIM_ALPHA`（不另立一份 = 不造第二份真相）' % (_non_br, _non_dm),
       abs(GS.GHOST_BRIGHT_ALPHA - float(_non_br)) < 1e-9
       and abs(GS.GHOST_DIM_ALPHA - float(_non_dm)) < 1e-9,
       '模块=%r/%r 原文=%s/%s' % (GS.GHOST_BRIGHT_ALPHA, GS.GHOST_DIM_ALPHA,
                                _non_br, _non_dm))
    ok('B24 ★ 两组数**确实不同**（若有人把四者合并成一组常量，这里报红 —— '
       '这正是"同一个词两处含义"的守门判据）',
       float(_cut_br) != float(_non_br) and float(_cut_dm) != float(_non_dm)
       and GS.GHOST_BUDS_CUTSCENE_BRIGHT_ALPHA != GS.GHOST_BRIGHT_ALPHA
       and GS.GHOST_BUDS_CUTSCENE_DIM_ALPHA != GS.GHOST_DIM_ALPHA)
    ok('B25 停走式步长 == 原文 `+= %s` / `-= %s`，且与 `GHOST_FADE_STEP` 同值'
       % (_rise, _fall),
       abs(float(_rise) - float(_fall)) < 1e-9
       and abs(GS.GHOST_FADE_STEP - float(_rise)) < 1e-9,
       '模块=%r 原文=%s/%s' % (GS.GHOST_FADE_STEP, _rise, _fall))
    ok('B26 「暗档」这条轴的原作出处 == `scr_murderlv() < %s` ⇒ `juandice = -1`'
       '（证明 0.5/0.3 是**低杀戮 = 暗档**，不是我们另立的机制）' % _lv,
       ('juandice = -1' in BU) and (('scr_murderlv() < %s' % _lv) in BU),
       '原文里没找到这条轴')
    ok('B27 负控制 · 把 buds 原文的过场亮档 %s 改成 %s 后解析值随之变（判据有鉴别力）'
       % (_cut_br, _non_br),
       _one(_cut.replace('clover_alpha < %s' % _cut_br,
                         'clover_alpha < %s' % _non_br),
            r'juandice\s*>\s*0\s*&&\s*clover_alpha\s*<\s*([\d.]+)', 'x') == _non_br)


# ===========================================================================
#  C  行为（真实量级）正 · 负 · 对照
# ===========================================================================
def group_c():
    section(u'C 行为（真实量级：真实像素 / 真实秒数）')
    import ghost_system as GS

    # ---- 距离式：正控制（真实像素量级）----
    ok('C1 贴脸（dist=0）⇒ 顶到封顶 0.9',
       abs(GS.alpha_for_distance(0.0) - 0.9) < 1e-9, GS.alpha_for_distance(0.0))
    ok('C2 半程（dist=49）⇒ 0.2 = 10/50（真实量级，不是 0.001 这种玩具量级）',
       abs(GS.alpha_for_distance(49.0) - 0.2) < 1e-9, GS.alpha_for_distance(49.0))
    ok('C3 边缘（dist=99，仍在 <100 内）⇒ 0.1',
       abs(GS.alpha_for_distance(99.0) - 0.1) < 1e-9, GS.alpha_for_distance(99.0))

    # ---- 三分支：正 / 负 / 对照 ----
    # ⚠️ dist 取 **49**（不是 50）：`alpha_for_distance(49) = 10/50 = 0.2` 是整数结果，
    #    好读好核对；首版写成 50 ⇒ 真值 10/51=0.196，判据自己算错了（**判据侧失手**）。
    ok('C4 正分支：近 ⇒ 直接赋值（不是插值/平滑）',
       abs(GS.step_alpha(0.0, 49.0, cap=0.9) - 0.2) < 1e-9,
       GS.step_alpha(0.0, 49.0, cap=0.9))
    ok('C5 正分支：近且现值很大 ⇒ **往下调到距离值**',
       abs(GS.step_alpha(0.9, 49.0, cap=0.9) - 0.2) < 1e-9,
       GS.step_alpha(0.9, 49.0, cap=0.9))
    ok('C6 负分支：远且 alpha>0 ⇒ 每帧 -0.05（真实帧率量级）',
       abs(GS.step_alpha(0.9, 5000.0, cap=0.9) - 0.85) < 1e-9,
       GS.step_alpha(0.9, 5000.0, cap=0.9))
    ok('C7 兜底分支：远且 alpha==0 ⇒ 恒 0（不是 -0.05 掉进负数）',
       GS.step_alpha(0.0, 5000.0, cap=0.9) == 0.0)
    ok('C8 负控制 · 远距离**不会**涨（0.85 再走一帧仍是 0.80）',
       abs(GS.step_alpha(0.85, 5000.0, cap=0.9) - 0.80) < 1e-9)
    ok('C9 对照控制 · 同输入只翻 cap ⇒ 输出必须不同（"档位真的接到 cap 上"）',
       abs(GS.step_alpha(0.0, 0.0, cap=0.9) - 0.9) < 1e-9
       and abs(GS.step_alpha(0.0, 0.0, cap=0.6) - 0.6) < 1e-9
       and GS.step_alpha(0.0, 0.0, cap=0.0) == 0.0)

    # ---- 浮动：真跑 400 帧，量真实区间 ----
    y, up, sc = 0.0, 0, 1
    ys = []
    for _ in range(400):
        y, up, sc = GS.step_levitate(y, 0.0, up, sc)
        ys.append(y)
    mn, mx = min(ys), max(ys)
    ok('C10 浮动区间 = [starty-2.0, starty+1.9]（★ 不对称，是原文语句顺序的产物）',
       abs(mn + 2.0) < 1e-6 and abs(mx - 1.9) < 1e-6,
       u'实测 min=%.6f max=%.6f' % (mn, mx))
    ok('C11 对照控制 · 振幅**不是** 4.0（有人"顺手修对称"会在这里报红）',
       abs((mx - mn) - 4.0) > 0.05, u'实测振幅=%.6f' % (mx - mn))
    ok('C12 不变量 · 永不出界 |y - starty| <= 2（长跑 400 帧后仍成立）',
       mn >= -2.0 - 1e-9 and mx <= 2.0 + 1e-9, u'min=%.6f max=%.6f' % (mn, mx))

    # ---- 决心 / 门槛：真实秒数 ----
    ok('C13 决心 0s ⇒ 0；3h ⇒ 1.0；6h ⇒ 仍 1.0（饱和，不许涨到无穷）',
       GS.determination(0.0) == 0.0
       and abs(GS.determination(3 * 3600.0) - 1.0) < 1e-9
       and abs(GS.determination(6 * 3600.0) - 1.0) < 1e-9)
    ok('C14 门槛表（Ralsei 特例）：0s⇒dim，29min⇒dim，30min⇒dim，3h⇒bright',
       GS.gate(0.0) == 'dim' and GS.gate(29 * 60.0) == 'dim'
       and GS.gate(30 * 60.0) == 'dim' and GS.gate(3 * 3600.0) == 'bright')
    ok('C15 门槛表（非特例）：0s⇒hidden，29min⇒hidden，30min⇒dim，3h⇒bright',
       GS.gate(0.0, ralsei_special=False) == 'hidden'
       and GS.gate(29 * 60.0, ralsei_special=False) == 'hidden'
       and GS.gate(30 * 60.0, ralsei_special=False) == 'dim'
       and GS.gate(3 * 3600.0, ralsei_special=False) == 'bright')
    ok('C16 对照控制 · 同输入只翻"特例"开关 ⇒ 门槛必须不同（否则"特例"测不到）',
       GS.gate(0.0) != GS.gate(0.0, ralsei_special=False))
    ok('C17 负控制 · 非法输入不抛且退到最保守（负时长 / None / NaN ⇒ hidden）',
       GS.gate(-5.0, ralsei_special=False) == 'hidden'
       and GS.gate(None, ralsei_special=False) == 'hidden'
       and GS.gate(float('nan'), ralsei_special=False) == 'hidden')
    ok('C18 alpha_cap：bright⇒0.9 / dim⇒0.6 / hidden⇒0 / 未知⇒0',
       GS.alpha_cap('bright') == 0.9 and GS.alpha_cap('dim') == 0.6
       and GS.alpha_cap('hidden') == 0.0 and GS.alpha_cap('??') == 0.0)

    # ---- 接触时钟：真实量级 + 正负控制 ----
    clk = GS.ContactClock()
    clk.tick(0.1, contact=False)
    clk.tick(0.1, contact=False)
    ok('C19 负控制 · contact=False 时**完全不计**（宠物独自待着不涨决心）',
       clk.total == 0.0, clk.total)
    clk.tick(0.1, contact=True)
    clk.tick(0.1, contact=True)
    ok('C20 正控制 · contact=True 时按 dt 累加', abs(clk.total - 0.2) < 1e-9, clk.total)
    clk.tick(5.0, contact=True)
    ok('C21 dt 防呆 · 超大 dt 被钳到 MAX_DT=0.1（不许一口气把 5s 全算进去）',
       abs(clk.total - 0.3) < 1e-9, clk.total)
    clk2 = GS.ContactClock()
    clk2.tick(0.1, contact=True)
    clk3 = GS.ContactClock(seconds=999.0).load(clk2.to_dict())
    ok('C22 存取往返：to_dict → load 后 total 回到原值（原来的 999 被覆盖）',
       abs(clk3.total - clk2.total) < 1e-9, 'to=%r after=%r' % (clk2.total, clk3.total))
    ok('C23 负控制 · load 非法数据**保持现值**（不清零、不抛）',
       abs(GS.ContactClock(seconds=42.0).load({'contact_seconds': 'x'}).total - 42.0) < 1e-9
       and abs(GS.ContactClock(seconds=42.0).load(None).total - 42.0) < 1e-9
       and abs(GS.ContactClock(seconds=42.0).load(
           {'contact_seconds': -1}).total - 42.0) < 1e-9)

    # ---- 在场判据 ----
    ok('C24 在场判据：kris/susie/lancer 都算；ralsei / 路人 / None 不算',
       GS.is_contact_npc('kris') and GS.is_contact_npc(' susie ')
       and GS.is_contact_npc('Lancer')
       and not GS.is_contact_npc('ralsei') and not GS.is_contact_npc('noelle')
       and not GS.is_contact_npc(None) and not GS.is_contact_npc(''))
    ok('C25 在场判据 · 空集合 ⇒ False；负控制：只有 ralsei ⇒ False',
       GS.contact_from_npcs([]) is False
       and GS.contact_from_npcs(['ralsei']) is False
       and GS.contact_from_npcs(['ralsei', 'susie']) is True)

    # ---- GhostState 整体推进：真实量级 + 对照 ----
    a = GS.GhostState(home_x=0.0, home_y=0.0, contact_seconds=0.0, ralsei_special=True)
    b = GS.GhostState(home_x=0.0, home_y=0.0, contact_seconds=0.0, ralsei_special=False)
    for _ in range(20):
        a.step(1.0 / 30.0, px=0.0, py=0.0, contact=True)
        b.step(1.0 / 30.0, px=0.0, py=0.0, contact=True)
    ok('C26 对照控制 · 同为"贴脸 + 零接触"，只翻特例开关 ⇒ alpha 0.6 vs 0.0',
       abs(a.alpha - 0.6) < 1e-9 and abs(b.alpha - 0.0) < 1e-9,
       'ralsei=%r 非特例=%r' % (a.alpha, b.alpha))
    hid = GS.GhostState(home_x=0.0, home_y=0.0, contact_seconds=0.0,
                        ralsei_special=False)
    for _ in range(50):
        hid.step(1.0 / 30.0, px=0.0, py=0.0)
    ok('C27 hidden 档 ⇒ 贴脸 50 帧后 alpha 仍恒 0（"看不见"是真的看不见）',
       hid.alpha == 0.0, hid.alpha)
    full = GS.GhostState(home_x=0.0, home_y=0.0, contact_seconds=3 * 3600.0)
    for _ in range(20):
        full.step(1.0 / 30.0, px=0.0, py=0.0, contact=True)
    ok('C28 正控制 · 满决心 + 贴脸 ⇒ 顶到亮档 0.9（与 C26 的 0.6 形成对照）',
       abs(full.alpha - 0.9) < 1e-9, full.alpha)
    ok('C29 正控制 · 从贴脸走远后 alpha 逐帧掉（一帧 -0.05）',
       full.step(1.0 / 30.0, px=99999.0, py=0.0) is True
       and abs(full.alpha - 0.85) < 1e-9, full.alpha)
    for _ in range(200):
        full.step(1.0 / 30.0, px=99999.0, py=0.0)
    ok('C30 负控制 · 走远足够多帧后 alpha 恰好 0（不剩负数、不卡在 0.05）',
       full.alpha == 0.0, full.alpha)
    nf = GS.GhostState(home_x=0.0, home_y=0.0, contact_seconds=3 * 3600.0)
    for _ in range(20):
        nf.step(1.0 / 30.0, px=0.0, py=0.0, contact=True)
    nf.step(1.0 / 30.0, px=None, py=None)
    ok('C31 坐标缺失 ⇒ 视为"无穷远"（alpha 只减不增，且不抛）',
       abs(nf.alpha - 0.85) < 1e-9, nf.alpha)

    # ==================================================================
    #  B5 追加：**停走式**（`MODE_FOLLOW`）的行为 —— 正 / 负 / 对照成对
    # ==================================================================
    # ---- 纯函数：`step_stopgo` ----
    ok('C32 站住 ⇒ 每帧 +0.05 且封顶（cap=0.6：0.55→0.6 不越顶；已在顶 ⇒ 不动）',
       abs(GS.step_stopgo(0.0, False, 0.6) - 0.05) < 1e-9
       and abs(GS.step_stopgo(0.55, False, 0.6) - 0.6) < 1e-9
       and abs(GS.step_stopgo(0.6, False, 0.6) - 0.6) < 1e-9)
    ok('C33 走动 ⇒ 每帧 -0.05（真实帧率量级）',
       abs(GS.step_stopgo(0.6, True, 0.6) - 0.55) < 1e-9,
       GS.step_stopgo(0.6, True, 0.6))
    ok('C34 走动 · 下限钳在 0（★ 这是与原文**故意不同**的一处：原文到 0 就 '
       '`instance_destroy()`，桌面版没有那套重生器 ⇒ 只归零不销毁）',
       GS.step_stopgo(0.02, True, 0.6) == 0.0 and GS.step_stopgo(0.0, True, 0.6) == 0.0)
    ok('C35 ★ 走动**与档位无关**（原文那句话是独立的 `if`，不在过场/非过场分支里）'
       '：同 alpha 下 cap=0.9 与 cap=0.0 走一帧结果**相同**',
       abs(GS.step_stopgo(0.6, True, 0.9) - GS.step_stopgo(0.6, True, 0.0)) < 1e-9
       and abs(GS.step_stopgo(0.6, True, 0.9) - 0.55) < 1e-9,
       'cap0.9=%r cap0.0=%r' % (GS.step_stopgo(0.6, True, 0.9),
                                GS.step_stopgo(0.6, True, 0.0)))
    ok('C36 站住但**高于**档位封顶 ⇒ 每帧 -0.05 收回到 cap（原文暗档那一支那条回落）',
       abs(GS.step_stopgo(0.9, False, 0.6) - 0.85) < 1e-9,
       GS.step_stopgo(0.9, False, 0.6))
    ok('C37 对照控制 · 同输入只翻 `moving` ⇒ 输出**方向相反**（停=升 / 走=降）',
       GS.step_stopgo(0.6, False, 0.9) > 0.6 and GS.step_stopgo(0.6, True, 0.9) < 0.6,
       '停=%r 走=%r' % (GS.step_stopgo(0.6, False, 0.9),
                        GS.step_stopgo(0.6, True, 0.9)))
    ok('C38 对照控制 · 同输入只翻"过场" ⇒ 封顶必须不同（0.9/0.6 vs 0.5/0.3），'
       '而 hidden 两档都 0（`hidden` 优先于过场）',
       GS.alpha_cap('bright') == 0.9 and GS.alpha_cap('bright', cutscene=True) == 0.5
       and GS.alpha_cap('dim') == 0.6 and GS.alpha_cap('dim', cutscene=True) == 0.3
       and GS.alpha_cap('hidden', cutscene=True) == 0.0)
    _conv = 0.0
    for _ in range(12):
        _conv = GS.step_stopgo(_conv, False, 0.6)
    _conv13 = GS.step_stopgo(_conv, False, 0.6)
    ok('C39 收敛性 · 从 0 一直站住 ⇒ 第 12 帧**恰好**到 cap=0.6，再走一帧仍是 0.6'
       '（不是"接近 0.6"，也不振荡）',
       abs(_conv - 0.6) < 1e-9 and abs(_conv13 - 0.6) < 1e-9,
       '12帧=%r 13帧=%r' % (_conv, _conv13))
    # ---- 不变量：走走停停 400 帧，alpha 永不为负、永不越顶 ----
    _a, _mv = 0.3, False
    _mn, _mx = 1.0, 0.0
    for _i in range(400):
        _mv = (_i % 7) < 3                      # 真实的"走走停停"节律
        _a = GS.step_stopgo(_a, _mv, 0.6)
        _mn, _mx = min(_mn, _a), max(_mx, _a)
    ok('C40 不变量 · 走走停停 400 帧后 alpha ∈ [0, cap]（不出现负数、不越顶）',
       _mn >= 0.0 and _mx <= 0.6 + 1e-9,
       u'实测区间=[%.6f, %.6f]' % (_mn, _mx))

    # ---- GhostState：两种模式互不串味 ----
    _fx = GS.GhostState(home_x=0.0, home_y=0.0, contact_seconds=3 * 3600.0,
                        mode=GS.MODE_FIXED)
    _fl = GS.GhostState(home_x=0.0, home_y=0.0, contact_seconds=3 * 3600.0,
                        mode=GS.MODE_FOLLOW)
    ok('C41 默认模式 == MODE_FIXED（模块默认不改，回归锁 B/C 段守着的通路一字不动）',
       GS.GhostState().mode == GS.MODE_FIXED and GS.MODE_FIXED == 'fixed'
       and GS.MODE_FOLLOW == 'follow', GS.GhostState().mode)
    ok('C42 负控制 · 非法模式值 ⇒ 退回 MODE_FIXED（不留半懂状态）',
       GS.GhostState(mode='walky').mode == GS.MODE_FIXED
       and GS.GhostState(mode=None).mode == GS.MODE_FIXED)
    for _ in range(6):
        _fx.step(1.0 / 30.0, px=0.0, py=0.0, moving=True)     # 定点：贴脸 + "在走"
        _fl.step(1.0 / 30.0, px=0.0, py=0.0, moving=True)     # 跟飘：贴脸 + "在走"
    ok('C43 ★ 两种模式**互不串味**：同样"贴脸 + 在走" ⇒ 定点那只照样顶到 0.9、'
       '跟飘那只一路淡到 0（定点那只的 alpha **只认距离**，`moving` 传进去也不该有影响）',
       abs(_fx.alpha - 0.9) < 1e-9 and _fl.alpha == 0.0,
       '定点=%r 跟飘=%r' % (_fx.alpha, _fl.alpha))
    _cs = GS.GhostState(home_x=0.0, home_y=0.0, contact_seconds=3 * 3600.0,
                        mode=GS.MODE_FOLLOW)
    _cs2 = GS.GhostState(home_x=0.0, home_y=0.0, contact_seconds=3 * 3600.0,
                         mode=GS.MODE_FOLLOW)
    for _ in range(20):
        _cs.step(1.0 / 30.0, px=0.0, py=0.0, moving=False)
        _cs2.step(1.0 / 30.0, px=0.0, py=0.0, moving=False, cutscene=True)
    ok('C44 对照控制 · 同输入只翻"过场" ⇒ 跟飘那只顶到 0.9 vs 0.5'
       '（过场档真的**接到了** alpha 上，不是常量摆着没人用）',
       abs(_cs.alpha - 0.9) < 1e-9 and abs(_cs2.alpha - 0.5) < 1e-9,
       '非过场=%r 过场=%r' % (_cs.alpha, _cs2.alpha))

    # ---- 跟飘：位置 + ★ 浮动偏移不被吃掉 ----
    _fw = GS.GhostState(home_x=999.0, home_y=999.0, contact_seconds=0.0,
                        ralsei_special=True, mode=GS.MODE_FOLLOW)
    for _ in range(3):
        _fw.step(1.0 / 30.0, px=400.0, py=300.0, moving=False)
    ok('C45 跟飘 ⇒ 锚点 x == 宠物中心 x + GHOST_FOLLOW_OFFSET_X（不是停在出生的 999）',
       abs(_fw.x - (400.0 + GS.GHOST_FOLLOW_OFFSET_X)) < 1e-9
       and abs(_fw.starty - (300.0 + GS.GHOST_FOLLOW_OFFSET_Y)) < 1e-9,
       'x=%r starty=%r' % (_fw.x, _fw.starty))
    # ⚠️ 要看全三角波的一个来回：39 帧下 + 39 帧上 ⇒ **至少 130 帧**。
    #    首版只跑 40 帧，实测区间是 [-2.0, +0.2]，判据却按 [-2.0, +1.9] 比 ⇒ **判据侧失手**
    #    （记忆 §4：报红先怀疑判据；这里是"会误报"的那一类）。
    _offs = []
    for _ in range(130):
        _fw.step(1.0 / 30.0, px=400.0, py=300.0, moving=False)
        _offs.append(_fw.y - _fw.starty)
    _omn, _omx = min(_offs), max(_offs)
    ok('C46 ★★ 跟飘时**浮动偏移仍然在动**（130 帧内看全一个来回 ⇒ 区间恰好 [-2.0, 1.9]）'
       '—— 这条就是 `_follow_to` "先量偏移、再搬基准、再把偏移还回去"存在的全部理由',
       abs(_omn + 2.0) < 1e-6 and abs(_omx - 1.9) < 1e-6,
       u'实测偏移区间=[%.6f, %.6f]' % (_omn, _omx))
    # 负控制：把 `_follow_to` 写成"每帧 y = 目标值"（最像的抄法），偏移会退化成常数
    _by, _bs, _bup, _bsc = 0.0, 0.0, 0, 1
    _boffs = []
    for _ in range(130):
        _by = _bs                                  # ← 坏实现的那一行
        _by, _bup, _bsc = GS.step_levitate(_by, _bs, _bup, _bsc)
        _boffs.append(_by - _bs)
    ok('C47 负控制 · "每帧 y = 目标值"的坏写法 ⇒ 偏移退化成常数（C46 真的有鉴别力）',
       (max(_boffs) - min(_boffs)) < 0.05 and (max(_offs) - min(_offs)) > 1.0,
       u'坏实现振幅=%.6f 好实现振幅=%.6f'
       % (max(_boffs) - min(_boffs), max(_offs) - min(_offs)))
    _bx, _bsy = _fw.x, _fw.starty
    _fw.step(1.0 / 30.0, px=None, py=None, moving=False)
    ok('C48 负控制 · 跟飘模式下 `px=None` ⇒ **不挪窝**（位置与基准都不动、且不抛）',
       (_fw.x, _fw.starty) == (_bx, _bsy),
       '前=(%r,%r) 后=(%r,%r)' % (_bx, _bsy, _fw.x, _fw.starty))
    _hid2 = GS.GhostState(home_x=0.0, home_y=0.0, contact_seconds=0.0,
                          ralsei_special=False, mode=GS.MODE_FOLLOW)
    for _ in range(30):
        _hid2.step(1.0 / 30.0, px=0.0, py=0.0, moving=False)
    ok('C49 hidden 档 + 跟飘 ⇒ 站住 30 帧 alpha 仍恒 0（"看不见"是真的看不见，'
       '不是"停走式把它点亮了"）',
       _hid2.alpha == 0.0, _hid2.alpha)


# ===========================================================================
#  D  素材对账
# ===========================================================================
def group_d():
    section(u'D 素材对账（45 PNG 的 sha256 逐个对 _source.json）')
    src_json = os.path.join(GHOST_DIR, '_source.json')
    ok('D0 幽灵素材目录 + _source.json 都在',
       os.path.isfile(src_json or ''), GHOST_DIR)
    if not os.path.isfile(src_json or ''):
        return
    meta = json.load(io.open(src_json, encoding='utf-8'))
    files = meta.get('files') or {}
    names = sorted(f for f in os.listdir(GHOST_DIR) if f.lower().endswith('.png'))
    ok('D1 磁盘 PNG 数 == _source.json 登记数（%d）' % len(files),
       len(names) == len(files) and len(files) == 45,
       'disk=%d json=%d' % (len(names), len(files)))
    ok('D2 磁盘文件名集合 == 登记键集合（防"多一张 / 少一张"）',
       set(names) == set(files.keys()),
       'diff=%s' % sorted(set(names) ^ set(files.keys()))[:5])

    import ghost_overlay as GO
    ok('D3 模块写的精灵名 == 登记里真有的那只',
       GO.GHOST_SPRITE == 'spr_ghost_chara_down'
       and any(v.get('sprite') == GO.GHOST_SPRITE for v in files.values()),
       GO.GHOST_SPRITE)
    e0 = files.get('%s_0.png' % GO.GHOST_SPRITE) or {}
    m0 = e0.get('meta') or {}
    ok('D4 帧数 == 登记 meta.frames（%s）' % m0.get('frames'),
       GO.GHOST_FRAMES == int(m0.get('frames') or -1),
       '模块=%r 登记=%r' % (GO.GHOST_FRAMES, m0.get('frames')))
    ok('D5 原生尺寸 == 登记 meta.w/h（%s×%s）' % (m0.get('w'), m0.get('h')),
       abs(GO.GHOST_NATIVE_W - float(m0.get('w') or -1)) < 1e-9
       and abs(GO.GHOST_NATIVE_H - float(m0.get('h') or -1)) < 1e-9,
       '模块=(%r,%r)' % (GO.GHOST_NATIVE_W, GO.GHOST_NATIVE_H))
    ok('D6 `ghost_frame_names()` 推出的 %d 个名字全在登记里' % GO.GHOST_FRAMES,
       set(GO.ghost_frame_names()) <= set(files.keys()),
       '缺=%s' % sorted(set(GO.ghost_frame_names()) - set(files.keys())))

    bad = []
    for n in names:
        rec = files.get(n) or {}
        p = os.path.join(GHOST_DIR, n)
        h = hashlib.sha256(io.open(p, 'rb').read()).hexdigest()
        if h != rec.get('sha256') or os.path.getsize(p) != rec.get('bytes'):
            bad.append((n, h[:8], str(rec.get('sha256'))[:8],
                        os.path.getsize(p), rec.get('bytes')))
    ok('D7 全部 PNG 的 sha256 + 字节数逐个对上（这不是"文件在"，是"内容一模一样"）',
       not bad, '不一致=%s' % bad[:3])
    ok('D8 负控制 · 判据能抓到内容被改（真文件的 sha256 对一条假值必须不等）',
       bool(names) and files.get(names[0], {}).get('sha256') != '0' * 64)

    from PyQt5.QtWidgets import QApplication
    _app = QApplication.instance() or QApplication([])
    pm = GO.load_ghost_sprites()
    ok('D9 load_ghost_sprites() 真加载出 %d 帧且全非空' % GO.GHOST_FRAMES,
       len(pm) == GO.GHOST_FRAMES and all(p is not None and not p.isNull() for p in pm),
       '非空=%d/%d' % (sum(1 for p in pm if p is not None), len(pm)))
    if pm and pm[0] is not None:
        ok('D10 帧的真实像素尺寸 == 原生 22×29',
           pm[0].width() == 22 and pm[0].height() == 29,
           '%d×%d' % (pm[0].width(), pm[0].height()))
    bad_pm = GO.load_ghost_sprites(dir_path=os.path.join(GHOST_DIR, '__nope__'))
    ok('D11 负控制 · 目录不存在 ⇒ 返回 None 帧（**不伪造**、不抛）',
       len(bad_pm) == GO.GHOST_FRAMES and all(p is None for p in bad_pm),
       '非 None 数=%d' % sum(1 for p in bad_pm if p is not None))


# ===========================================================================
#  E  接线（AST + 真机）
# ===========================================================================
def group_e():
    section(u'E 接线（AST + 真机）')
    main_src = _read(os.path.join(SRC, 'main.py'))
    cls = 'RalseiPet'

    ok('E1 `GHOST_ENABLED = True` 真的作为**类属性**存在',
       bool(re.search(r'^    GHOST_ENABLED = True$', main_src, re.M)), '没找到')
    _need = ('init_ghost', '_ghost_tick', '_ghost_save', '_ghost_load', '_ghost_respawn')
    ok('E2 五个幽灵方法都定义了',
       all(_find_func(main_src, n, cls) is not None for n in _need),
       '缺=%s' % [n for n in _need if _find_func(main_src, n, cls) is None])
    ok('E3 `init_ghost()` 有**恰好一处**调用点（在初始化链上，不是死方法）',
       len(re.findall(r'^        self\.init_ghost\(\)$', main_src, re.M)) == 1,
       '命中=%d' % len(re.findall(r'^        self\.init_ghost\(\)$', main_src, re.M)))

    um = _find_func(main_src, 'update_movement', cls)
    g_calls = _calls_in(um, {'_ghost_tick'}) if um is not None else []
    ok('E4 `update_movement` 里真调了 `_ghost_tick`',
       any(n == '_ghost_tick' for _, n in g_calls), '调用=%s' % (g_calls,))
    if um is not None:
        g_line = [l for l, n in g_calls if n == '_ghost_tick']
        s_line = [l for l, n in _calls_in(um, {'_soul_tick'}) if n == '_soul_tick']
        rets = _direct_returns(um)
        ok('E5 ★ 调用点在**所有早退分支之前**（幽灵是独立实体，宠物睡着也该按距离显淡）',
           bool(g_line) and bool(rets) and g_line[0] < rets[0] and g_line[0] < um.end_lineno,
           'ghost@%s 首个return@%s 全部return=%s' % (g_line[:1], rets[:1], rets[:4]))
        ok('E6 与灵魂同一节拍（两者都在第一个 return 之前）',
           bool(s_line) and bool(rets) and s_line[0] < rets[0],
           'soul@%s' % (s_line[:1],))
    ce = _find_func(main_src, 'cleanup_on_exit', cls)
    ce_calls = _calls_in(ce, {'_ghost_save', 'hide_ghost', 'close'}) if ce else []
    ok('E7 退出收尾：`_ghost_save` 被调 + 独立顶层窗口被 `hide_ghost`+`close` 收掉',
       {'_ghost_save', 'hide_ghost', 'close'} <= {n for _, n in ce_calls},
       '找到=%s' % sorted({n for _, n in ce_calls}))

    go_src = _read(os.path.join(MODS, 'ghost_overlay.py'))
    go_attrs = _attrs_of(go_src)
    ok('E8 ★ 幽灵**不置顶**（AST 看代码属性，不看注释里那几个字）',
       'WindowStaysOnTopHint' not in go_attrs,
       '代码里出现 WindowStaysOnTopHint')
    ok('E9 幽灵**一个鼠标事件都不吃**（比灵魂更严格）',
       'WA_TransparentForMouseEvents' in go_attrs
       and 'WindowDoesNotAcceptFocus' in go_attrs,
       '缺=%s' % sorted({'WA_TransparentForMouseEvents', 'WindowDoesNotAcceptFocus'}
                        - go_attrs))
    ok('E10 幽灵绘制失败不拖垮进程（存在 `paintEvent`，且内部有 except 兜底）',
       _find_func(go_src, 'paintEvent') is not None and 'except Exception' in go_src)

    # 负控制：E8 的判据必须能抓到真写了置顶的代码（不能因为"注释里有"就糊过去）
    # ⚠️ 比的是**裸属性名**（`_attrs_of` 返回的就是裸名）。首版拿全点号串
    #    `'Qt.WindowStaysOnTopHint'` 去比对 ⇒ 恒假 ⇒ 负控制自己失手。
    ok('E11 负控制 · 判据能抓到真写成 `Qt.WindowStaysOnTopHint` 的代码；'
       '且注释里提它**不会**误报',
       'WindowStaysOnTopHint' in
       _attrs_of('w.setWindowFlags(Qt.WindowStaysOnTopHint)\n')
       and 'WindowStaysOnTopHint' not in
       _attrs_of('# 不要写 WindowStaysOnTopHint\nw.setWindowFlags(Qt.Tool)\n'),
       '鉴别力不足')

    # ---- 真机（offscreen）----
    _tmp = os.path.join(tempfile.gettempdir(), 'ralsei_ghost67')
    os.makedirs(_tmp, exist_ok=True)
    os.environ.setdefault('RALSEI_MEMORY_DIR', _tmp)
    _env_base = os.environ.get('RALSEI_MEMORY_DIR') or _tmp
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import QApplication
    _app = QApplication.instance() or QApplication([])
    import main as M
    pet = M.RalseiPet()
    for a in ('animation_timer', 'ai_timer', 'stats_timer', 'dialogue_init_timer',
              'auto_mouse_drag_timer', 'api_control_timer', 'placeholder_timer',
              'movement_timer', 'mouse_drag_timer', '_bounce_timer',
              '_hide_search_timer'):
        t = getattr(pet, a, None)
        try:
            if t is not None:
                t.stop()
        except Exception:
            pass

    ok('E12 真机：幽灵建起来了（素材 + 状态 + 窗口 + 接触时钟）',
       pet.ghost is not None and pet.ghost_state is not None
       and pet.ghost_contact is not None,
       'ghost=%r state=%r clock=%r' % (pet.ghost is not None,
                                       pet.ghost_state is not None,
                                       pet.ghost_contact is not None))
    if pet.ghost is None:
        return
    gh, st = pet.ghost, pet.ghost_state
    cx = pet.x() + pet.width() / 2.0
    cy = pet.y() + pet.height() / 2.0
    _off = sum(x * x for x in M.RalseiPet.GHOST_SPAWN_OFFSET) ** 0.5
    ok('E13 真机：出生距离 == GHOST_SPAWN_OFFSET 的长度（%.1f）' % _off,
       abs(st.distance_to(cx, cy) - _off) < 2.0,
       '实测=%.2f' % st.distance_to(cx, cy))
    ok('E14 真机：档位 = dim / cap = 0.6（Ralsei 自动是特例）',
       st.gate == 'dim' and abs(st.cap - 0.6) < 1e-9,
       '%s / %r' % (st.gate, st.cap))
    ok('E15 真机：**不置顶**（不是"源码里没写"，是窗口标志真的不带）',
       not bool(gh.windowFlags() & Qt.WindowStaysOnTopHint))
    ok('E16 真机：鼠标穿透属性真的生效',
       bool(gh.testAttribute(Qt.WA_TransparentForMouseEvents)))
    ok('E17 真机：`ghost.state.frame` 恒为 0（定点幽灵不播动画）',
       gh.state.frame == 0)

    ok('E18 真机：开局 alpha==0（不闪一下满亮度）', abs(st.alpha) < 1e-9, st.alpha)
    # ---- B5：产品默认走"跟飘停走式" ⇒ 下面几条（E19/E21/E22）从"距离式"改成"停走式" ----
    # ★ 定点"距离式"在**真机层**的判据没有消失，只是换了层级：C4~C9 / C26~C31（纯函数与
    #   `GhostState`）逐条守着它；`GHOST_MODE='fixed'` 一改，产品立刻回到那条通路。
    import ghost_system as GS
    ok('E19a 真机：幽灵模式 == `GHOST_MODE`（B5 接线真的生效，不是"接口摆着"）',
       st.mode == M.RalseiPet.GHOST_MODE and st.mode == GS.MODE_FOLLOW,
       'state.mode=%r GHOST_MODE=%r' % (st.mode, M.RalseiPet.GHOST_MODE))
    # ⚠️ 「走没走」必须**显式摆好**。靠 pet 构造路径里 `is_moving` 的现值 = 隐式耦合：
    #    将来把 `is_moving` 挪进 `__init__`（或反过来加个默认），判据会**换个结论而不报红**。
    pet.is_moving = False
    # ⚠️ 距离要在 tick **之前**量（`step()` 里的坐标用的是当帧的 x/y，而 tick 顺带把 y
    #    浮动 ±0.1）。这里它的用途变了：当**对照值** —— 证明"停走式在算、距离式没在算"。
    _d = st.distance_to(cx, cy)
    pet._ghost_tick(1.0 / 30.0)
    _dist_formula = min(10.0 / (_d + 1.0), 0.6)
    ok('E19b 真机：站住一帧 ⇒ alpha 由 0 升到 0.05，**且不等于距离式的值**'
       '（A≠B：证明模式切换真生效，不是两套一起算）',
       abs(st.alpha - 0.05) < 1e-9 and abs(st.alpha - _dist_formula) > 1e-3,
       '实测=%.6f 距离式会算出=%.6f' % (st.alpha, _dist_formula))
    ok('E20 真机：alpha>0 ⇒ 窗口**真的显示**（`wants_show` 与窗口同步）',
       gh.wants_show() and gh.isVisible(),
       'wants=%s vis=%s' % (gh.wants_show(), gh.isVisible()))

    # ---- 跟飘：位置真的跟着宠物（"跟飘"这半件事的真机实证）----
    for _ in range(6):
        pet._ghost_tick(1.0 / 30.0)
    _fcx = pet.x() + pet.width() / 2.0
    _fcy = pet.y() + pet.height() / 2.0
    ok('E21a 真机：跟飘 ⇒ 锚点 == 宠物中心 + GHOST_FOLLOW_OFFSET'
       '（x 精确；y 在 ±2 浮动区间内 —— 所以只判"贴着"不判"相等"）',
       abs(st.x - (_fcx + GS.GHOST_FOLLOW_OFFSET_X)) < 1e-6
       and abs(st.y - (_fcy + GS.GHOST_FOLLOW_OFFSET_Y)) <= 2.0 + 1e-6,
       '锚=(%.3f,%.3f) 期望x=%.3f 基准y=%.3f' % (st.x, st.y,
                                                _fcx + GS.GHOST_FOLLOW_OFFSET_X,
                                                _fcy + GS.GHOST_FOLLOW_OFFSET_Y))
    # ---- ★ 真机层再钉一次"浮动没被跟飘吃掉"（与 C46 分层：C46 是纯逻辑、这里过真机）----
    _yo = []
    for _ in range(130):
        pet._ghost_tick(1.0 / 30.0)
        _yo.append(st.y - st.starty)
    ok('E21b ★★ 真机：跟飘 130 帧里浮动偏移**仍在动**（区间恰好 [-2.0, 1.9]）'
       ' —— 若有人把 `_follow_to` 写成"每帧 y = 目标值"，这里会退化成常数',
       abs(min(_yo) + 2.0) < 1e-6 and abs(max(_yo) - 1.9) < 1e-6,
       u'实测=[%.6f, %.6f]' % (min(_yo), max(_yo)))

    pet.is_moving = False
    for _ in range(14):
        pet._ghost_tick(1.0 / 30.0)
    ok('E21 真机：一直站住 ⇒ 顶到**暗档封顶 0.6**（不是 0.9 —— 决心没满）',
       abs(st.alpha - 0.6) < 1e-9, st.alpha)
    pet.is_moving = True
    for _ in range(14):
        pet._ghost_tick(1.0 / 30.0)
    ok('E22 真机：一直走动 ⇒ alpha 归 0，且窗口**自动收掉**（不留隐形空窗口）',
       st.alpha == 0.0 and (not gh.isVisible()),
       'alpha=%r vis=%s' % (st.alpha, gh.isVisible()))
    pet.is_moving = False
    for _ in range(3):
        pet._ghost_tick(1.0 / 30.0)
    ok('E22b 真机：走动归零后**再站住 ⇒ alpha 重新升起**（★ 与原文"到 0 就 '
       'instance_destroy"故意不同的一处：桌面版没有重生器，只归零不销毁）',
       abs(st.alpha - 0.15) < 1e-9 and gh.isVisible(),
       'alpha=%r vis=%s' % (st.alpha, gh.isVisible()))

    # ---- 接触计时真的从 npc_bodies 读 ----
    pet.npc_bodies = {}
    before = pet.ghost_contact.total
    pet._ghost_tick(0.1)
    ok('E23 真机：没人在场 ⇒ 判据 False 且总时长不涨',
       pet._ghost_contact_now() is False and pet.ghost_contact.total == before,
       '%.3f→%.3f' % (before, pet.ghost_contact.total))
    pet.npc_bodies = {'kris': object(), 'susie': object()}
    ok('E24 真机：kris/susie 在场 ⇒ 判据 True（数据源真的接在 npc_bodies 上）',
       pet._ghost_contact_now() is True)
    pet._ghost_tick(0.1)
    pet._ghost_tick(0.1)
    ok('E25 真机：有接触 ⇒ 总时长按帧累加',
       abs(pet.ghost_contact.total - (before + 0.2)) < 1e-9,
       '%.3f 期望 %.3f' % (pet.ghost_contact.total, before + 0.2))
    pet.npc_bodies = {}
    pet._ghost_tick(0.1)
    ok('E26 负控制：清空在场后总时长**停住**（接触是唯一输入）',
       abs(pet.ghost_contact.total - (before + 0.2)) < 1e-9, pet.ghost_contact.total)

    # ---- 落盘（走 data_store）----
    saved = pet._ghost_save(force=True)
    _p = pet._ghost_path or ''
    ok('E27 真机：接触时长落盘成功，且落在 **RALSEI_MEMORY_DIR 隔离目录**内'
       '（不写用户真实 vault）',
       bool(saved) and os.path.isfile(_p)
       and os.path.abspath(_p).lower().startswith(os.path.abspath(_env_base).lower()),
       'path=%r saved=%s env=%r' % (_p, saved, _env_base))
    total_now = pet.ghost_contact.total
    pet.ghost_contact._total = 0.0
    pet._ghost_load()
    ok('E28 真机：回读后总时长 == 落盘前的值（往返一致）',
       abs(pet.ghost_contact.total - total_now) < 1e-6,
       '回读=%r 落盘前=%r' % (pet.ghost_contact.total, total_now))

    # ---- 真跑 update_movement（接线点不许抛）----
    # ★ 第68轮修：真机跑 `update_movement()` 会**连带跑第52轮的就寝判定**，
    #   而它在"当前墙钟已过 23:00±10 分钟窗口"时会多打一行
    #   `[就寝] 今晚（YYYY-MM-DD）窗口 HH:MM~HH:MM 已过，不再补睡`
    #   ⇒ 套件输出**随跑的时刻漂移**（第68轮实测：23:26 跑 ⇒ 基线里没有的那行出现，
    #   判成假 DIFF）。本套件要守的是幽灵线，不是就寝 ⇒ 显式关掉这个开关，
    #   让输出与墙钟无关。（`_bedtime_tick` 第一行就 `if not BEDTIME_ENABLED: return False`。）
    pet.BEDTIME_ENABLED = False
    print('[INFO] 已关闭就寝判定（避免 `update_movement` 真跑时的时间耦合）')
    # ★★ 第89轮修：**第二枚时间炸弹，比就寝更凶** —— NPC 自主挪窝。
    #   `update_movement()` 里还有一句 `self._npc_roam_tick(current_time)`（第79轮层2），
    #   它经 `npc_intent.jitter()` 用**连续墙钟**（`time.time()`，精确到微秒）参与哈希
    #   ⇒ **每一次跑** NPC 落点都不同，打印一二十行
    #       `<TS> ... NPC xxx 自己挪到了 <场景>`
    #   实测：同一份代码、相邻两次运行，`ralsei` 一次去 `uty.rooms.rm_intro`、
    #   另一次去 `ch4.kris_room.kris_s_room` —— 本套件因它长期 DIFF（56 行差异），
    #   而 PASS/FAIL 计数一条没变（假红，真回归会被这堆噪声淹没）。
    #   ⚠️ 这是**夹具的时间耦合**，不是产品缺陷：NPC 生活本就该"每天不同"
    #     （L6「同人同刻不必同行为」），已由第78/79 轮**纯函数级**判据单独锁住。
    #   ⇒ 处置：把节拍闸顶到无穷大（`now - inf < 30` 恒真 ⇒ `_npc_roam_tick` 第一段就早退、
    #     零日志、零副作用）。本套件要守的是幽灵线，不是 NPC 搬家。
    #   ⚠️ 代价：本套件从此看不见"NPC 挪窝会不会绕过幽灵/接触时钟的接线点"。
    #     该风险不在本套件职责内，已在第89轮登记（check79/check80 覆盖挪窝本身）。
    pet._npc_roam_last_tick = float('inf')
    pet.last_update_time = 0.0
    threw = None
    try:
        pet.update_movement()
    except Exception as e:
        threw = e
    ok('E29 真机：`update_movement()` 真跑一遍不抛（接线没把主循环搞坏）',
       threw is None, 'threw=%r' % (threw,))

    pet.cleanup_on_exit()
    ok('E30 真机：退出收尾把幽灵窗口收掉了（独立顶层窗口的代价必须还上）',
       not gh.isVisible())
    ok('E31 退出收尾把 soul / ghost 引用**置 None**'
       '（`cleanup_on_exit` 有"显式退出 + atexit"两个调用点，'
       '第二遍不许再打在已析构的窗口上）',
       pet.ghost is None and getattr(pet, 'soul', None) is None,
       'ghost=%r soul=%r' % (pet.ghost, getattr(pet, 'soul', None)))
    threw2 = None
    try:
        pet.cleanup_on_exit()          # 第二遍 = 模拟 atexit 再收一次
    except Exception as e:
        threw2 = e
    ok('E32 退出收尾可重入（二次调用不抛）', threw2 is None, 'threw=%r' % (threw2,))

    # ---- 日志器接线（本轮真机取证的副产物；但**正是它**让上面那些 INFO 真能落盘）----
    # 背景：`main.py` 顶部 `from logger_utils import get_logger` 若在"把 modules/
    #   挂进 sys.path"**之前**执行，import 期必然失败 ⇒ 落到兜底的
    #   `logging.getLogger(name)`，而 `__name__ == '__main__'` 得到的 logger 名是
    #   **`__main__`** —— 它不在 `ralsei_pet` 树下、没有任何 handler ⇒
    #   **main.py 自己的日志会被全部静默丢弃**（只有 `modules/*` 的能落到文件里）。
    # 真机证据：修之前，日志文件里怎么都查不到 `幽灵就绪`；用 PYTHONPATH 注入
    #   调用点钩子才看到它**确实跑了**、且 logger 名是 `__main__`。修完即可见。
    _lines = main_src.splitlines()
    # ⚠️ 首版这里用 `'from logger_utils import get_logger' in line` 直接扫原文
    #   ⇒ 被**注释里**那句同名字面量命中（本轮真踩：报 logger@7，而那行是注释）
    #   ⇒ 判据必须走 AST 定行号，不看文本。
    _tree = ast.parse(main_src)
    _li_logger = None
    for _n in _tree.body:
        if isinstance(_n, ast.ImportFrom) and _n.module == 'logger_utils':
            _li_logger = _n.lineno
            break
        if isinstance(_n, ast.Try):          # 它在 try: ... except ImportError 里
            for _c in ast.walk(_n):
                if isinstance(_c, ast.ImportFrom) and _c.module == 'logger_utils':
                    _li_logger = _c.lineno
                    break
        if _li_logger:
            break
    # 找第一处 `sys.path.append/insert(...)`，并确认紧邻上方出现了 'modules' 字面量
    _path_calls = []
    _const_lines = []
    for _n in ast.walk(_tree):
        if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Attribute) \
                and _n.func.attr in ('append', 'insert'):
            _v = _n.func.value
            if isinstance(_v, ast.Attribute) and _v.attr == 'path' \
                    and isinstance(_v.value, ast.Name) and _v.value.id == 'sys':
                _path_calls.append(_n.lineno)
        if isinstance(_n, ast.Constant) and _n.value == 'modules':
            _const_lines.append(getattr(_n, 'lineno', -1))
    _li_path = None
    for _ln in sorted(_path_calls):
        if any(_ln - 12 <= _cl <= _ln for _cl in _const_lines):
            _li_path = _ln
            break
    ok('E33 ★ `modules/` 入 sys.path 必须**早于** `from logger_utils import get_logger`'
       '（否则 main 的日志器退化成 `__main__`、main 自身日志全被静默丢弃）'
       '（行号由 AST 定，注释里的同名字面量不会误命中）',
       _li_logger is not None and _li_path is not None and _li_path < _li_logger,
       'logger@%s path@%s 全path调用=%s' % (_li_logger, _li_path, sorted(_path_calls)[:4]))

    # 行为 A/B（成对，缺一不可）：证明"这个顺序是承重的"——不挂 modules/ 时
    # `import logger_utils` **必须失败**，挂了才成功。只写结构断言的话，就无法排除
    # "其实怎么写都能 import"，那样 E33 就成了摆设。
    _code = ('try:\n'
             '    import logger_utils\n'
             '    print("OK", logger_utils.__name__)\n'
             'except Exception as e:\n'
             '    print("FAIL", type(e).__name__)\n')

    def _run_import(extra_path):
        env = dict(os.environ)
        env.pop('PYTHONPATH', None)
        if extra_path:
            env['PYTHONPATH'] = extra_path
        env['PYTHONIOENCODING'] = 'utf-8'
        _r = subprocess.run([sys.executable, '-c', _code], cwd=SRC, env=env,
                            capture_output=True, text=True, timeout=90)
        return (_r.stdout or '').strip()

    _neg = _run_import('')
    _pos = _run_import(MODS)
    ok('E34 负/正控制成对：不挂 `modules/` ⇒ `import logger_utils` 失败；'
       '挂了 ⇒ 成功（E33 那条顺序**确实承重**，不是摆设）',
       _neg.startswith('FAIL') and _pos.startswith('OK'),
       'neg=%r pos=%r' % (_neg, _pos))

    # ==================================================================
    #  B5 接线（AST）：产品真的在跑"跟飘停走式"
    #  ★ 全部走 AST，不看文本 —— 注释里提一句 `moving=` 不算接线。
    # ==================================================================
    import ghost_system as GS

    _ig = _find_func(main_src, 'init_ghost', cls)
    _ig_mode = _call_kwarg_source(main_src, _ig, 'GhostState', 'mode')
    ok('E35 ★ 产品真的用"跟飘停走式"：`GHOST_MODE` 是类属性且 == MODE_FOLLOW，'
       '且 `init_ghost` 把它**显式**传给了 `GhostState`'
       '（传的是产品开关本身，不是写死的字符串 —— 后者会让这个常量变成死的）',
       bool(re.search(r'^    GHOST_MODE = ghost_system_mod\.MODE_FOLLOW$',
                      main_src, re.M))
       and _ig_mode == ['RalseiPet.GHOST_MODE'],
       'GHOST_MODE_FA=%s GhostState.mode 实参=%s'
       % (bool(re.search(r'^    GHOST_MODE = ', main_src, re.M)), _ig_mode))
    ok('E36 对照控制 · `ghost_system` 的**默认**仍是 MODE_FIXED（"靠默认"会露馅：'
       '两者不同这件事本身，就是 E35 那条判据不是摆设的证明）',
       GS.GhostState().mode == GS.MODE_FIXED
       and GS.GhostState().mode != M.RalseiPet.GHOST_MODE,
       '默认=%r 产品=%r' % (GS.GhostState().mode, M.RalseiPet.GHOST_MODE))

    _gt = _find_func(main_src, '_ghost_tick', cls)
    _gt_calls = _calls_in(_gt, {'tick', '_ghost_moving_now'}) if _gt else []
    _gt_moving = _call_kwarg_source(main_src, _gt, 'tick', 'moving')
    ok('E37 ★ `_ghost_tick` 真把"走没走"透传下去（AST 看 `gh.tick(..., moving=…)` '
       '的**关键字实参**，不看注释）',
       _gt_moving == ['moving']
       and any(n == '_ghost_moving_now' for _, n in _gt_calls),
       'tick.moving 实参=%s 调用=%s' % (_gt_moving, [n for _, n in _gt_calls]))
    _gm_fn = _find_func(main_src, '_ghost_moving_now', cls)
    _gm_seg = ast.get_source_segment(main_src, _gm_fn) if _gm_fn is not None else ''
    import textwrap as _tw
    _gm_src = _tw.dedent(_gm_seg) if _gm_seg else ''
    # ★ `is_moving` 在源码里是**字符串字面量**（`getattr(self, 'is_moving', False)`），
    #   不是 `Name`/`Attribute` ⇒ 只看 `_attrs_of` 会**漏掉它**（本条首版就这么误报了，
    #   实测取到的名 = ['Exception','bool','getattr','self']）。
    #   记忆 §4 已经写过这条：「扫属性要同时扫 `ast.Constant`」—— 又踩了一次。
    _gm_strs = {n.value for n in ast.walk(ast.parse(_gm_src))
                if isinstance(n, ast.Constant) and isinstance(n.value, str)} \
        if _gm_src else set()
    ok('E38 ★ "走没走"的来源是宠物的 `is_moving`（**字符串字面量**，故用 AST 扫 Constant），'
       '且走 `getattr(..., False)` 兜底'
       '（`is_moving` **不是** `__init__` 预声明字段 ⇒ 直接 `self.is_moving` 会在早期炸）',
       'is_moving' in _gm_strs and 'getattr' in _attrs_of(_gm_src),
       '字符串=%s 属性=%s' % (sorted(_gm_strs)[:6], sorted(_attrs_of(_gm_src))[:6]))
    _go_src2 = _read(os.path.join(MODS, 'ghost_overlay.py'))
    # ⚠️ 判据口径更正（本条首版也误报了）：`ghost_overlay.tick` 里**允许**出现
    #   `cutscene=cutscene` —— 那是**透传**（默认 `None` ⇒ 状态保持 `False`），
    #   不是"用了过场档"。真正该守的是**没有任何地方把它写成字面量 `True`**。
    #   ⇒ 判据从"不许出现关键字"改成"不许出现**真值**"（更准，也更严：写死 False 也过、
    #     写死 True 必报红）。
    ok('E39 接线 · 产品侧**不碰**过场档：没有任何调用把 `cutscene` 写成字面量 `True`，'
       '且 `main.py` 里根本不出现这个关键字（桌面没有 `obj_starker` / '
       '`obj_backgrounder_*` 那套死亡演出对象 ⇒ 过场档只该由回归锁当对照控制用）',
       not _kwarg_true_calls(main_src, 'cutscene')
       and not _kwarg_true_calls(_go_src2, 'cutscene')
       and not _call_kwarg_source(main_src, ast.parse(main_src), 'tick', 'cutscene'),
       'main 写死 True 的行=%s overlay 写死 True 的行=%s'
       % (_kwarg_true_calls(main_src, 'cutscene'),
          _kwarg_true_calls(_go_src2, 'cutscene')))
    ok('E40 负控制 · 上面两个 AST 探针能抓到"真写了"的版本'
       '（`f(moving=1)` / `f(cutscene=True)` 都必须被检出，否则 E37/E39 是空的）',
       _call_kwarg_source('f(moving=1)\n', ast.parse('f(moving=1)\n'), 'f', 'moving')
       == ['1']
       and _kwarg_true_calls('f(cutscene=True)\n', 'cutscene') == [1],
       '鉴别力不足')
    ok('E41 `ghost_overlay.tick` 的签名真的收 `moving` / `cutscene`'
       '（AST 看形参表，不是只有调用方在传）',
       {'moving', 'cutscene'} <= set(_args_of(_find_func(_go_src2, 'tick'))),
       '形参表=%s' % _args_of(_find_func(_go_src2, 'tick')))


# ===========================================================================
#  F  判据自身体检
# ===========================================================================
def group_f():
    section(u'F 判据自身体检（负控制 + no-op 显式）')
    # ---- F1：报告口输出的行**真的能被 run_all 的正则数到** ----
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        ok('__probe_pass__', True)
        ok('__probe_fail__', False)
    PASS.pop()          # 把探针从记账里摘掉（它只是夹具）
    FAIL.pop()
    del _LINES[-2:]     # 打印流水里也要摘掉 —— 否则 F6 的总账会多出 2 行
    lines = buf.getvalue().strip().split('\n')
    ok('F1 报告口打印的成功/失败标记，能被 run_all.count_results 的正则数到'
       '（每行恰好一个，不多不少）',
       len(lines) == 2
       and bool(re.search(r'\[PASS\]', lines[0]))
       and bool(re.search(r'\[FAIL\]', lines[1]))
       and len(re.findall(r'\[PASS\]|\[FAIL\]', lines[0])) == 1
       and len(re.findall(r'\[PASS\]|\[FAIL\]', lines[1])) == 1,
       'lines=%r' % (lines,))

    # ---- F2：记账真的把 False 记成失败（用不打印的 `_record` 体检，避免污染 stdout）----
    n_fail = len(FAIL)
    _record('__probe__', False)
    recorded = len(FAIL) == n_fail + 1
    if recorded:
        FAIL.pop()
    ok('F2 记账口真的把 False 记成失败（F1/F2 都不是 no-op）', recorded)

    # ---- F3：恒真体检 —— "文件都在 / 文件都不在" 两条判据结论必须不同 ----
    ok('F3 恒真体检 · `存在` 与 `不存在` 两条判据结论不同（不是 `A in rev[B]` 那种恒真）',
       os.path.isfile(os.path.join(MODS, 'ghost_system.py'))
       != os.path.isfile(os.path.join(MODS, '__definitely_not_here__.py')))
    # ---- F4：原文目录真被读到（防路径写错 ⇒ 全走 except ⇒ 静默变绿）----
    _n_gml = len([f for f in os.listdir(GML64) if f.endswith('.gml')]) \
        if os.path.isdir(GML64 or '') else 0
    ok('F4 原文物证目录真的被读到（防路径写错后静默变绿）',
       _n_gml >= 10, 'gml 份数=%d' % _n_gml)
    # ---- F5：负控制 —— 撞两处闸的模块数/白名单不会被本套件静默漏掉 ----
    _mods = sorted(f for f in os.listdir(MODS)
                   if f.endswith('.py') and f != '__init__.py')
    ok('F5 新模块真的在磁盘上（F1 的"模块数"判据才不是空话）',
       'ghost_system.py' in _mods and 'ghost_overlay.py' in _mods,
       'n=%d' % len(_mods))

    # ---- F6：★ 判据名不许自己带标记（否则 run_all 的计数会被带歪）----
    # 实测触发过：首版 F1 的名字里写了方括号标记 ⇒ 同一行被数出 2 个 PASS + 1 个 FAIL，
    # 套件全绿却被算成"有 FAIL"。这里对**已打印的全部行**做一次总账。
    _tok_lines = [l for l in _LINES if ('[PASS]' in l or '[FAIL]' in l)]
    _bad = [l for l in _tok_lines
            if len(re.findall(r'\[PASS\]|\[FAIL\]', l)) != 1]
    ok('F6 已打印的 %d 行里，每行**恰好一个**成功/失败标记（判据名不许自带标记）'
       % len(_tok_lines),
       len(_tok_lines) == len(PASS) + len(FAIL) and not _bad,
       '多标记行=%s' % (_bad[:2],))


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    print('===== 第67轮 · 幽灵线接线回归锁 =====')
    print('ROOT = %s' % ROOT)
    group_a()
    group_b()
    group_c()
    group_d()
    group_e()
    group_f()
    print('')
    print('合计：PASS=%d FAIL=%d' % (len(PASS), len(FAIL)))
    if FAIL:
        print('【失败项】')
        for n in FAIL:
            print('  - %s' % n)
    return 1 if FAIL else 0


if __name__ == '__main__':
    sys.exit(main())
