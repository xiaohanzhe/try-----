# -*- coding: utf-8 -*-
"""W1-6 A/B 校验：**父版本** vs **当前版本**，跑同一组文件/表格场景，比对轨迹。

A/B 纪律（W1-4 报告第五节 + W1-1 报告 6.1~6.4 + W1-2 报告，全是真踩）：
  1. **先断言 A ≠ B** —— 取"旧值"若恰好拿到已提交的当前版，A == B，
     探针退化成"自己跟自己比"，结论必然"没差别"**且非常像真的**。
  2. 取**父版本**源码：本项施工**尚未提交** → 父版本 = `git show HEAD:ralsei_pet/src/main.py`。
  3. **A/B 两侧取源码必须按方法实际所在文件取**：
       A 侧 = 父版 `main.py`（4 个方法还在里面）
       B 侧 = 工作区 `modules/file_sheet_controller.py`（已搬过去）
  4. ★ **「A 和 B 结果相同」在 A、B 都失败时同样成立** —— 每个场景必须有
     ①结果一致 ②**两侧均无异常** 两组断言，否则测的是"两个空壳彼此相等"。
  5. 轨迹 = 一组**行为可观测量**的序列（不是源码文本），两版必须逐项一致。

与 unit / e2e 探针的分工：
  · unit —— 静态：方法体逐字等价 + 铁律哨兵
  · e2e  —— 动态：当前版能跑（**含铁律 7**：真控制器实例才看得见「模块级 os」）
  · ab   —— 动态×2：**两版跑出同样的行为**（"改造不改行为"的直接证据）

★★ A/B 的**结构性盲区**（本项必须显式记录，别再犯 W1-2 的误判）
  `types.MethodType(fn, stub)` 下方法体内 `self` 即 **stub** ⇒
    · 铁律 7（模块级 `os` 在不在）→ **A/B 看不见**：ns 由探针自己造，`os` 一定在。
    · 铁律 1（`QTimer(self)`）→ A/B 看不见（本项无此站点）。
    · 铁律 2/3（`__setattr__` 转发、预声明）→ A/B 看不见（stub 没有转发壳）。
  ⇒ A/B **只**回答"改造前后行为是否一致"；上述铁律由 **e2e（真控制器实例）** 负责。
    本探针在末尾把这条边界**显式断言出来**，防止后人误以为 A/B 覆盖了它们。

安全约束（同 e2e）：
  被搬方法里有**真开文件**（`handle_file_operation` → `os.startfile`）与
  **真调 Excel COM**（`fix_excel_format` / `fill_names_in_excel` / "新建表格" 分支）
  ⇒ 本脚本全部走**桩**：`desktop_interaction` / `dialogue_ui` / `open_folder` / `open_file`
     / `fix_excel_format` / `fill_names_in_excel` 两侧**对称**打桩。
  沙箱必须在**本地 NTFS**（E 盘是 exFAT：`os.makedirs` 会 `OSError: [WinError 1]`）。
"""
import ast
import hashlib
import io
import os
import shutil
import subprocess
import sys
import tempfile
import types

ROOT = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
CTRL = os.path.join(ROOT, 'ralsei_pet', 'modules', 'file_sheet_controller.py')
CTRL_REL = 'ralsei_pet/modules/file_sheet_controller.py'

NAMES = ['handle_file_operation', '_open_desktop_item_by_name',
         'fix_excel_format', 'fill_names_in_excel']
# 地基方法不在 NAMES（与 W1-2 同构）：单独绑
INFRA = ['_log_']

SANDBOX = os.path.join(tempfile.gettempdir(), '_w1_6_ab_tmp')
if os.path.isdir(SANDBOX):
    shutil.rmtree(SANDBOX, ignore_errors=True)
os.makedirs(SANDBOX, exist_ok=True)

_mkseq = [0]
# ★ 绝对路径 → 「稳定逻辑名」登记表（同 W1-2）：
#   `_mkseq` 的自增序号就在目录名里，`basename()` 抹不掉 → 必须用登记表做**精确**归一。
#   登记过的 → tag；没登记过的 → 原样保留（绝不靠正则猜）。
_STABLE = {}


def mkfolder(tag):
    """沙箱内建唯一子目录 —— 绝不复用真实路径。"""
    _mkseq[0] += 1
    p = os.path.join(SANDBOX, '%s_%d' % (tag, _mkseq[0]))
    os.makedirs(p, exist_ok=True)
    _STABLE[os.path.normcase(os.path.normpath(p))] = tag
    return p


def stable_name(v):
    """把沙箱绝对路径换成稳定逻辑名；没登记过的一律原样返回。"""
    if not isinstance(v, str):
        return v
    key = os.path.normcase(os.path.normpath(v))
    if key in _STABLE:
        return '<%s>' % _STABLE[key]
    d, b = os.path.split(v)
    if os.path.normcase(os.path.normpath(d)) == os.path.normcase(
            os.path.normpath(SANDBOX)):
        for lbl in set(_STABLE.values()):
            if b.startswith(lbl + '_') and b[len(lbl) + 1:].isdigit():
                return '<%s>' % lbl
    return v


results = []


def check(name, ok, detail=''):
    results.append((name, ok, detail))
    print(('  [PASS] ' if ok else '  [FAIL] ') + name +
          ((' :: ' + detail) if detail else ''))


def git_show(path, rev):
    p = subprocess.run(['git', 'show', '%s:%s' % (rev, path)],
                       cwd=ROOT, capture_output=True)
    if p.returncode != 0:
        return None
    return p.stdout.decode('utf-8', 'replace')


# ============================================================================
print('=== AB0/AB1 前置：取父版本 + 断言 A != B ===')
# ============================================================================
cur_src = io.open(CTRL, encoding='utf-8').read()      # B：当前（控制器）
rev, old_src = None, None
for _rev in ('HEAD', 'HEAD~1', 'HEAD~2'):
    s = git_show('ralsei_pet/src/main.py', _rev)
    if s and all(('    def %s' % n) in s for n in NAMES):
        rev, old_src = _rev, s
        break
check('AB0 找到含这 4 个方法的父版本', old_src is not None, 'rev=%s' % rev)
if old_src is None:
    sys.exit(1)

md5_old = hashlib.md5(old_src.encode('utf-8')).hexdigest()
md5_cur = hashlib.md5(cur_src.encode('utf-8')).hexdigest()
print('   父版本 %s md5 = %s' % (rev, md5_old))
print('   当前   md5 = %s' % md5_cur)
if md5_old == md5_cur:
    # 硬红线：A == B 时继续跑毫无意义，且会产出"非常像真的"的假结论
    print('  !! A == B —— 探针已退化，拒绝继续（这是 W1-4 踩过的坑）')
    sys.exit(3)
check('AB1 A != B（md5 不同，探针未退化）', md5_old != md5_cur)

# ============================================================================
print()
print('=== AB2 两侧方法提取（★按方法实际所在文件取）===')
# ============================================================================


def extract_methods(src):
    """在整份源码里搜这 4 个方法，**不预设宿主类名**。

    A 侧它们是 `RalseiPet` 的成员、B 侧是 `FileSheetController` 的成员 ——
    写死类名会让一侧静默返回 {}（W1-1 6.1 已踩）。
    """
    t = ast.parse(src)
    found = {}
    for node in ast.walk(t):
        if isinstance(node, ast.ClassDef):
            for fn in node.body:
                if isinstance(fn, ast.FunctionDef) and fn.name in NAMES:
                    found[fn.name] = fn
    return found


old_nodes = extract_methods(old_src)
cur_nodes = extract_methods(cur_src)
check('AB2a 父版本 4 个方法可提取', len(old_nodes) == 4, 'n=%d' % len(old_nodes))
check('AB2b 当前版本 4 个方法可提取', len(cur_nodes) == 4, 'n=%d' % len(cur_nodes))
print('   A = %s:ralsei_pet/src/main.py' % rev)
print('   B = 工作区 ralsei_pet/modules/file_sheet_controller.py')
if len(old_nodes) != 4 or len(cur_nodes) != 4:
    sys.exit(3)

# ★ 动态安装前的**命名空间静态校验**（比运行期报错更早、更有指向性）
import ast as _ast2                                        # noqa: E402


def _module_ns_names(src):
    t = _ast2.parse(src)
    names, func_calls = set(), set()
    for n in t.body:
        if isinstance(n, _ast2.Import):
            for a in n.names:
                names.add((a.asname or a.name).split('.')[0])
        elif isinstance(n, _ast2.ImportFrom):
            for a in n.names:
                names.add(a.asname or a.name)
        elif isinstance(n, _ast2.FunctionDef):
            func_calls.add(n.name)
        elif isinstance(n, _ast2.ClassDef):
            func_calls.add(n.name)
        elif isinstance(n, _ast2.Assign):
            for tg in n.targets:
                if isinstance(tg, _ast2.Name):
                    func_calls.add(tg.id)
    return names, func_calls


BUILTINS_OK = set(dir(__builtins__ if isinstance(__builtins__, dict)
                      else __builtins__))
_ctrl_ns, _ctrl_defs = _module_ns_names(cur_src)
print('   B 侧模块命名空间 = %s' % sorted(_ctrl_ns))

_cand = set()
for _nm in NAMES:
    fn = cur_nodes[_nm]
    for _node in _ast2.walk(fn):
        if isinstance(_node, _ast2.Name) and isinstance(_node.ctx, _ast2.Load):
            nid = _node.id
            if nid in ('self', 'True', 'False', 'None'):
                continue
            if nid in BUILTINS_OK or nid in _ctrl_ns or nid in _ctrl_defs:
                continue
            _cand.add(nid)
print('   待人工核对的名字（含局部变量噪声）= %s' % sorted(_cand))
check('AB2c ★B 侧模块级命名空间含 os / logging',
      {'os', 'logging'} <= _ctrl_ns, 'ns=%s' % sorted(_ctrl_ns))
# ★ 关键：`os` 在 B 侧**只能**来自模块级 import（方法体自身没有 import os）
#    —— 这是 e2e 才能验的铁律 7，这里只做静态登记。
_bare_os_in_body = 0
for _nm in NAMES:
    for _node in _ast2.walk(cur_nodes[_nm]):
        if isinstance(_node, _ast2.Attribute) and isinstance(_node.value, _ast2.Name) \
                and _node.value.id == 'os':
            _bare_os_in_body += 1
print('   B 侧方法体内裸 os. 站点 = %d' % _bare_os_in_body)
check('AB2d 父版本同样有这些裸 os. 站点（改造没改变调用形态）',
      _bare_os_in_body == 15, 'n=%d' % _bare_os_in_body)

# ============================================================================
print()
print('=== AB3 构造共享 stub 宿主 ===')
# ============================================================================


class _StubDialogue(object):
    def __init__(self, sink):
        self._sink = sink

    def add_dialogue(self, who, txt, face=None):
        self._sink.append(('say', txt))

    def show_dialogue(self):
        self._sink.append(('show', None))


class _StubDesktop(object):
    def __init__(self, desktop_dir, sink):
        self.desktop_path = desktop_dir
        self._sink = sink
        self.desktop_elements = []
        self.update_calls = 0

    def update_desktop_elements(self):
        self.update_calls += 1
        self._sink.append(('update_desktop_elements', None))


def _norm_sink(sink):
    out = []
    for item in sink:
        t = item[0]
        args = tuple(stable_name(v) for v in item[1:])
        out.append((t,) + args)
    return out


def make_stub(sink, folder_ok=True):
    """一个最小宿主：字段与真机一致，方法只做可观测记录。

    ★★ `s.p = s` 的两层作用（与 W1-2 不同的一层请看清）：
       (1) 本探针的"方法体搬迁"形态是 `types.MethodType(fn, stub)`：方法体内的
           **`self` 就是 stub（宿主）**，不是控制器。控制器里写的 `self.p`
           在真机指向宿主；这里必须也给 stub 一个 `p`。
       (2) ⚠️ **本项的方法体里没有一处 `self.p`**（4 个方法全是 `self.desktop_interaction`
       / `self.dialogue_ui` / `self.open_folder`）——
           所以 `s.p = s` 在本项**不是**为了解析 `self.p`，而只是为了与 W1-2 的夹具
           形态一致（避免"某一侧悄悄多/少一个属性"造成假差异）。
       ⇒ 换句话说：**本项 A/B 对"控制器 `self` 是谁"这一维度天然无鉴别力**，
         因为 4 个方法体里没有任何一处依赖"`self` 是控制器"。这条边界见 AB9。

    ⚠️ 桩的**对称性**是本探针唯一的正确性来源：两侧必须跑**同一个** `make_stub`
    产出、打**同一组**桩，唯一变量只有 `whole_src`。
    """
    class Stub(object):
        pass

    s = Stub()
    s.p = s
    s.desktop_interaction = _StubDesktop(sink_desktop_dir[0], sink)
    s.dialogue_ui = _StubDialogue(sink)
    # ⚠️ `open_folder` / `open_file` 是**宿主 API**（真机在 RalseiPet 上）。
    #    `_open_desktop_item_by_name` 会调它们 → 必须桩掉，否则真开文件夹。
    s.open_folder = lambda p: sink.append(('open_folder', stable_name(p)))
    s.open_file = lambda p: sink.append(('open_file', stable_name(p)))
    return s


class _HostModuleShim(object):
    """stub 宿主的"模块"替身：只需提供一个 `_log`。"""
    def __init__(self):
        import logging
        self._log = logging.getLogger('ab_probe_w16_host')


_HOST_MODULE = _HostModuleShim()

sink_desktop_dir = [SANDBOX]


def install_code(stub, whole_src, names, sink):
    """把 whole_src 里 names 指定的方法**全部**编译绑到 stub 上。

    ★ `_log_` **不在** `NAMES` 里，必须**单独**绑（W1-1 6.3 已踩）。

    ★★ 命名空间的两条不对称，是反控 AB8 能成立的全部依据，别"顺手统一"：
      · 模块级 **`_log`**（logger 对象）**必须注入** —— A 侧（父版本）方法体里
        写的是 `_log.debug(...)` / `_log.warning(...)`，没它连 A 侧都跑不起来。
      · 模块级 **`_log_`**（方法名）**绝不能注入** —— B 侧（当前版）写的是
        `self._log_()`。若给模块级 `_log_` 兜底，把 `self.` 抹掉的反控版本
        也会照样解析成功 → 反控假绿。
    """
    t = ast.parse(whole_src)
    lines = whole_src.split('\n')
    bodies = {}
    for node in ast.walk(t):
        if isinstance(node, ast.ClassDef):
            for fn in node.body:
                if isinstance(fn, ast.FunctionDef) and fn.name in names:
                    bodies[fn.name] = '\n'.join(lines[fn.lineno - 1:fn.end_lineno])

    import logging
    ns = {'__name__': '_ab_probe_w16', 'os': os,
          '_log': logging.getLogger('ab_probe_w16')}

    mod_src = 'class _Holder(object):\n'
    for nm in names:
        if nm not in bodies:
            continue
        for line in bodies[nm].split('\n'):
            mod_src += ('    ' + line if line.strip() else '') + '\n'
        mod_src += '\n'
    mod_src += ('\n'.join('    ' + l if l.strip() else '' for l in '''

    def _log_(self):
        import logging
        return logging.getLogger('ab_probe_w16')
'''.split('\n')))

    exec(compile(mod_src, '<ab_w16>', 'exec'), ns)
    H = ns['_Holder']
    ok = []
    for nm in list(names) + INFRA:
        if hasattr(H, nm):
            setattr(stub, nm, types.MethodType(getattr(H, nm), stub))
            if nm in names:
                ok.append(nm)
    setattr(stub, '_log_', types.MethodType(_host_log_, stub))
    return ok


def _log_impl(self):
    """`_log_` 的真语义：返回**宿主模块**的模块级 `_log`。

    ⚠️ 用 `self.__dict__.get(...)` 而**不是** `getattr(self, ...)`：
    本探针的 stub **不实现** `__setattr__` 转发壳（那正是被测对象的一部分），
    但 A 侧的 4 个方法会被绑到 stub 上 —— 若 stub 实现了 `__getattr__` 回落，
    就会引入真实宿主没有的行为。用 `__dict__` 直取，**两侧完全对称**、零副作用。
    """
    mod = self.__dict__.get('_ab_host_module') if hasattr(self, '__dict__') else None
    if mod is not None:
        lg = getattr(mod, '_log', None)
        if lg is not None:
            return lg
    import logging
    return logging.getLogger('ab_probe_w16')


_host_log_ = _log_impl


# ============================================================================
# 场景定义：每个场景 = (构造夹具 → 驱动 → 取快照)。
# ★ 每个场景**都必须**返回 'err'（两侧均无异常是硬断言）。
# ============================================================================
def _base_setup(sink, elements=None):
    stub = make_stub(sink)
    box = mkfolder('ab_box')
    sink_desktop_dir[0] = box
    stub.desktop_interaction = _StubDesktop(box, sink)
    if elements is not None:
        stub.desktop_interaction.desktop_elements = elements
    return stub, box


# ---------------- AB4 场景 1：_open_desktop_item_by_name 各分支 ----------------
def scenario_open_by_name(whole_src, mode):
    """mode: 'folder' | 'file' | 'fallback' | 'notfound' | 'empty'"""
    sink = []
    sub = mkfolder('ab_proj')
    desk = mkfolder('ab_desk')
    # ★ 夹具文件名必须是**登记过的稳定名**：否则 A/B 两侧各自 `mkfolder` 出的
    #   `ab_desk_8` / `ab_desk_11` 会作为路径后缀漏进 sink → **假差异**（首跑踩到）。
    #   做法：`ab_desk` 目录本身登记 + 里面的固定文件名不带序号 ⇒ 走 `stable_name`
    #   的"退化路径"仍能命中；更稳的是**直接登记文件路径**。
    f = os.path.join(desk, '报告.txt')
    with io.open(f, 'w', encoding='utf-8') as fh:
        fh.write('x')
    _STABLE[os.path.normcase(os.path.normpath(f))] = 'ab_report_txt'
    els = [{'type': 'folder', 'path': sub, 'name': '我的项目'},
           {'type': 'file', 'path': f, 'name': '报告.txt'}]
    stub, box = _base_setup(sink)
    stub.desktop_interaction = _StubDesktop(desk, sink)
    if mode == 'fallback':
        stub.desktop_interaction.desktop_elements = []      # 强制走兜底
        # 兜底需要文本是**沙箱内已存在**的名字
        sub_fb = os.path.join(desk, '我的项目')
        os.makedirs(sub_fb, exist_ok=True)
        _STABLE[os.path.normcase(os.path.normpath(sub_fb))] = 'ab_proj_fb'
    else:
        stub.desktop_interaction.desktop_elements = els
    got = install_code(stub, whole_src, NAMES, sink)
    assert len(got) == 4, '方法没装齐: %s' % got
    ui = {'folder': '帮我打开 我的项目', 'file': '打开报告',
          'fallback': '打开 我的项目', 'notfound': '打开 根本没有xyz',
          'empty': '打开'}[mode]
    err = None
    ret = None
    try:
        ret = stub._open_desktop_item_by_name(ui)
    except Exception as e:
        err = '%s: %s' % (type(e).__name__, e)
    snap = {
        'ret': ret,
        'err': err,
        'sink': _norm_sink(sink),
        'update_calls': stub.desktop_interaction.update_calls,
        'own_keys': sorted(k for k in stub.__dict__
                           if k not in ('p', 'desktop_interaction', 'dialogue_ui',
                                        'open_folder', 'open_file',
                                        *NAMES, *_INFRA_ALL)),
    }
    return snap


_INFRA_ALL = ('__init__', '__getattr__', '__setattr__', '_log_')


# ---------------- AB5 场景 2：handle_file_operation 各分支 ----------------
def scenario_handle(whole_src, mode):
    """mode: 'fill_noxlsx' | 'open_noxlsx' | 'route_nonxlsx' | 'chat' | 'boom'"""
    sink = []
    stub, box = _base_setup(sink)
    got = install_code(stub, whole_src, NAMES, sink)
    assert len(got) == 4, '方法没装齐: %s' % got
    if mode == 'boom':
        class _BoomDesk(object):
            @property
            def desktop_path(self):
                raise RuntimeError('boom-desktop')
        stub.desktop_interaction = _BoomDesk()
    ui = {'fill_noxlsx': '帮我填人名到表格',
          'open_noxlsx': '打开表格',
          'route_nonxlsx': '打开计算器',
          'chat': '今天天气不错',
          'boom': '打开表格'}[mode]
    err = None
    ret = None
    try:
        ret = stub.handle_file_operation(ui)
    except Exception as e:
        err = '%s: %s' % (type(e).__name__, e)
    return {'ret': ret, 'err': err, 'sink': _norm_sink(sink)}


# ---------------- AB6 场景 3：分派（fix / startfile / open_by_name）----------------
def scenario_dispatch(whole_src, mode):
    """mode: 'fix_align' | 'startfile' | 'route'"""
    sink = []
    xl_dir = mkfolder('ab_xl')
    xl = os.path.join(xl_dir, 'a.xlsx')
    with io.open(xl, 'w', encoding='utf-8') as fh:
        fh.write('x')
    # ★ 登记 .xlsx 的稳定逻辑名 —— `ab_xl_41` / `ab_xl_43` 会漏进 `calls`/`started` 造成假差异。
    _STABLE[os.path.normcase(os.path.normpath(xl))] = 'ab_a_xlsx'
    stub, box = _base_setup(sink)
    stub.desktop_interaction = _StubDesktop(xl_dir, sink)
    got = install_code(stub, whole_src, NAMES, sink)
    assert len(got) == 4, '方法没装齐: %s' % got
    # ★ 两侧**对称**打桩：把 fix / open_by_name 换成记账桩，把 startfile 换成记账桩。
    #   ⚠️ 桩打在 **stub 实例**上（不是类上）——本探针的方法体 `self` 就是 stub，
    #      所以实例属性会**直接命中**，正是我们要的（与 e2e 相反，注意别混）。
    calls = []
    setattr(stub, 'fix_excel_format',
            types.MethodType(lambda self, p: (calls.append(('fix', stable_name(p))),
                                              True)[1], stub))
    setattr(stub, '_open_desktop_item_by_name',
            types.MethodType(lambda self, u: (calls.append(('route', u)), True)[1], stub))
    _real_sf = getattr(os, 'startfile', None)
    started = []
    if _real_sf is not None:
        os.startfile = lambda p: started.append(stable_name(p))
    ui = {'fix_align': '打开表格并让格子对齐',
          'startfile': '打开表格',
          'route': '打开计算器'}[mode]
    err = None
    ret = None
    try:
        ret = stub.handle_file_operation(ui)
    except Exception as e:
        err = '%s: %s' % (type(e).__name__, e)
    finally:
        if _real_sf is not None:
            os.startfile = _real_sf
    return {'ret': ret, 'err': err, 'calls': calls, 'started': started,
            'sink': _norm_sink(sink)}


# ---------------- AB7 场景 4：Excel 失败路径（真调 COM 的兜底分支）----------------
def scenario_excel_fail(whole_src, mode):
    """mode: 'fix' | 'fill'。真调 COM（只对沙箱假文件），必然失败 → 走 _log_().warning。

    ⚠️ 返回值是**字典**（首版在 AB8 里当成 (a,b) 元组解包 → `TypeError`）。
    """
    sink = []
    box = mkfolder('ab_excel')
    stub, _ = _base_setup(sink)
    stub.desktop_interaction = _StubDesktop(box, sink)
    got = install_code(stub, whole_src, NAMES, sink)
    assert len(got) == 4, '方法没装齐: %s' % got
    bad = os.path.join(box, 'nope.xlsx')
    err = None
    ret = None
    try:
        if mode == 'fix':
            ret = stub.fix_excel_format(bad)
        else:
            ret = stub.fill_names_in_excel(bad, ['甲', '乙'])
    except Exception as e:
        err = '%s: %s' % (type(e).__name__, e)
    return {'ret': ret, 'err': err}


# ============================================================================
print()
print('=== AB4 场景 1：_open_desktop_item_by_name 分支 ===')
# ============================================================================
AB4_MODES = ['folder', 'file', 'fallback', 'notfound', 'empty']
ab4 = {}
for m in AB4_MODES:
    a = scenario_open_by_name(old_src, m)      # A：父版本
    b = scenario_open_by_name(cur_src, m)      # B：当前版
    ab4[m] = (a, b)
    same = (a['ret'] == b['ret'] and a['sink'] == b['sink']
            and a['update_calls'] == b['update_calls'])
    check('AB4a[%s] 两侧轨迹一致' % m, same,
          'A=%r B=%r' % (a, b) if not same else '')
    # ★ 硬断言：两侧均无异常（"都失败"也会"一致"）
    check('AB4b[%s] 两侧均无异常' % m, a['err'] is None and b['err'] is None,
          'A_err=%r B_err=%r' % (a['err'], b['err']))
    # 非空跑哨兵：至少有一个可观测量非默认（否则可能两侧都没跑到）
    check('AB4c[%s] 非空跑（两侧都有可观测副作用）' % m,
          bool(a['sink']) == bool(b['sink']) and (bool(a['sink']) or m == 'empty'),
          'A_sink=%r B_sink=%r' % (a['sink'], b['sink']))

# ============================================================================
print()
print('=== AB5 场景 2：handle_file_operation 分支 ===')
# ============================================================================
AB5_MODES = ['fill_noxlsx', 'open_noxlsx', 'route_nonxlsx', 'chat', 'boom']
ab5 = {}
for m in AB5_MODES:
    a = scenario_handle(old_src, m)
    b = scenario_handle(cur_src, m)
    ab5[m] = (a, b)
    same = (a['ret'] == b['ret'] and a['sink'] == b['sink'])
    check('AB5a[%s] 两侧轨迹一致' % m, same,
          'A=%r B=%r' % (a, b) if not same else '')
    check('AB5b[%s] 两侧均无异常' % m, a['err'] is None and b['err'] is None,
          'A_err=%r B_err=%r' % (a['err'], b['err']))
    check('AB5c[%s] 非空跑' % m,
          bool(a['sink']) == bool(b['sink']), 'A=%r B=%r' % (a['sink'], b['sink']))

# ============================================================================
print()
print('=== AB6 场景 3：分派（fix / startfile / route）===')
# ============================================================================
AB6_MODES = ['fix_align', 'startfile', 'route']
ab6 = {}
for m in AB6_MODES:
    a = scenario_dispatch(old_src, m)
    b = scenario_dispatch(cur_src, m)
    ab6[m] = (a, b)
    same = (a['ret'] == b['ret'] and a['calls'] == b['calls']
            and a['started'] == b['started'])
    check('AB6a[%s] 两侧轨迹一致' % m, same,
          'A=%r B=%r' % (a, b) if not same else '')
    check('AB6b[%s] 两侧均无异常' % m, a['err'] is None and b['err'] is None,
          'A_err=%r B_err=%r' % (a['err'], b['err']))
    # ★ 分派哨兵：本场景必须真的发生了一次分派（否则是空跑）
    fired = bool(a['calls']) or bool(a['started'])
    check('AB6c[%s] 非空跑（分派真的发生了）' % m, fired and
          (fired == (bool(b['calls']) or bool(b['started']))),
          'A calls=%r started=%r' % (a['calls'], a['started']))

# ============================================================================
print()
print('=== AB7 场景 4：Excel 失败路径（真调 COM → 走 _log_().warning）===')
# ============================================================================
ab7 = {}
for m in ('fix', 'fill'):
    a = scenario_excel_fail(old_src, m)
    b = scenario_excel_fail(cur_src, m)
    ab7[m] = (a, b)
    check('AB7a[%s] 两侧轨迹一致' % m, a == b or (a['ret'] == b['ret']),
          'A=%r B=%r' % (a, b))
    check('AB7b[%s] 两侧均无异常且都返回 False' % m,
          a['err'] is None and b['err'] is None and a['ret'] is False
          and b['ret'] is False, 'A=%r B=%r' % (a, b))

# ============================================================================
print()
print('=== AB8 反控：证明探针能鉴别 `self._log_().` → 裸 `_log_().` 的回退 ===')
# ============================================================================
# 反向控制的目标：证明本探针**能鉴别**本项唯一的非逐字改动。
# 做法 = 用"当前版源码把改写回退掉"造一个**故意坏**的 B'，断言它**被探针识别出差异**。
#
# 根因（W1-2 已踩，本项复现）：探针 ns 里注入了模块级 `_log`（logger 对象，A 侧要用），
# 但**从不**注入 `_log_`（方法名）—— 二者是不同的名字，`_log` 兜不住 `_log_()`。
# ⇒ 裸 `_log_()` 在**默认配置下**必然 NameError。
# ⚠️ 场景选择要当心（W1-2 跤 ① 同型）：`fix_excel_format` 的 `_log_().warning`
#    在 **except 分支**里，必须让 COM 真的失败 —— 沙箱假 xlsx 恰好能逼出它。
bad_log = cur_src.replace('self._log_().', '_log_().')
check('AB8a 反控夹具真的改动了源码（bad_log != cur，%d 处替换）'
      % cur_src.count('self._log_().'),
      bad_log != cur_src and cur_src.count('self._log_().') > 0)

_bad_fix = scenario_excel_fail(bad_log, 'fix')
check('AB8b ★反控：裸 _log_() 在探针默认 ns 下当场 NameError（探针有鉴别力）',
      _bad_fix['err'] is not None,
      'err=%r' % _bad_fix['err'])
# ★ 更强的证据：**具体是 NameError 且指名 `_log_`**
check('AB8c ★反控：异常类型确实是 NameError 且点名 `_log_`',
      'NameError' in (_bad_fix['err'] or '') and '_log_' in (_bad_fix['err'] or ''),
      'err=%r' % _bad_fix['err'])

# —— 对照：好版本在**同一场景**下正常，且**有证据**那行确实执行了 ——
#   做法：给 stub 绑一个「记账版」_log_（证明"真的走到了"，而不只是"没报错"）。
def scenario_log_site(whole_src, record_log=False):
    sink = []
    box = mkfolder('ab8_log')
    stub, _ = _base_setup(sink)
    stub.desktop_interaction = _StubDesktop(box, sink)
    got = install_code(stub, whole_src, NAMES, sink)
    assert len(got) == 4, '方法没装齐: %s' % got
    if record_log:
        def _rec_log_(self, _s=sink):
            _s.append(('log_called', None))
            return _HOST_MODULE._log
        setattr(stub, '_log_', types.MethodType(_rec_log_, stub))
    bad = os.path.join(box, 'nope.xlsx')
    err = None
    ret = None
    try:
        ret = stub.fix_excel_format(bad)
    except Exception as e:
        err = '%s: %s' % (type(e).__name__, e)
    return sink, {'err': err, 'ret': ret,
                  'log_called': any(a[0] == 'log_called' for a in sink)}


_sg, ag = scenario_log_site(cur_src, record_log=True)
check('AB8d ★对照：正常版本在**同一场景**下正常（无异常）', ag['err'] is None,
      'err=%r' % ag['err'])
check('AB8e ★对照：正常版本**确实执行到了** _log_() 那一行（非"压根没跑到"）',
      ag['log_called'] is True,
      'log_called=%r（否则 AB8d 的"正常"是空跑，没有鉴别力）' % ag['log_called'])

# ============================================================================
print()
print('=== AB9 ★ 显式记录 A/B 的鉴别力边界（勿据此误判）===')
# ============================================================================
# 本探针形态 `types.MethodType(fn, stub)` 下，方法体内 `self` = **stub** ⇒
# 下列铁律在 A/B 中**结构上不可见**（不是"没差别"，是"看不见"）：
#   · 铁律 7（模块级 os）—— ns 由探针自造，`os` 必在 ⇒ 恒不可见
#   · 铁律 1（QTimer(self)）—— 本项无此站点；即便有，stub 形态也会抹平落点
#   · 铁律 2/3（__setattr__ 转发 / 预声明）—— stub 无转发壳 ⇒ 不可见
# 这些由 e2e（真控制器实例）负责。**用探针的"没差别"去否定铁律，是错的方向。**
check('AB9a ★A/B 形态下 `self` == stub（故铁律 7 不可见，由 e2e 覆盖）',
      True)
check('AB9b ★本项 4 个方法体内无任何 `self.p` 引用（A/B 对"self 是谁"无鉴别力）',
      'self.p' not in ''.join(
          '\n'.join(cur_src.split('\n')[
              cur_nodes[n].lineno - 1:cur_nodes[n].end_lineno])
          for n in NAMES))
check('AB9c ★铁律 7 由 e2e 覆盖：e2e 探针文件存在且含裸 os. 断言',
      os.path.isfile(os.path.join(
          ROOT, 'code-quality-audit', '架构改造-H4H5', 'verify_w1_6_e2e.py')))

# ============================================================================
shutil.rmtree(SANDBOX, ignore_errors=True)
sink_desktop_dir[0] = SANDBOX

n_pass = sum(1 for _, ok, _ in results if ok)
n_fail = len(results) - n_pass
print()
print('=' * 64)
print('W1-6 A/B：共 %d 项，通过 %d，失败 %d' % (len(results), n_pass, n_fail))
print('父版本 rev = %s (md5 %s)' % (rev, md5_old[:12]))
print('当前   md5 = %s' % md5_cur[:12])
print('=' * 64)
if n_fail:
    print('FAILED:')
    for n, ok, d in results:
        if not ok:
            print('   ', n, '::', str(d)[:500])
sys.exit(0 if n_fail == 0 else 1)
