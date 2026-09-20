# -*- coding: utf-8 -*-
"""W1-2 单元探针 —— HideAndSeekController 静态结构校验。

检查：
  X  载入 + A≠B 哨兵（控制器 md5 有效、与 W1-1 控制器不同）
  V1 逐方法逐字等价（12 个方法与 main.py 父版 git show HEAD 比对；
     _log. -> self._log_(). 改写计数 = 15；QTimer(self) -> QTimer(self.p) = 1）
  V2 模块级 import 齐全（time / QPoint / logging），且局部 import 未被提到模块级
  V3 铁律 2：__getattr__ / __setattr__ 都在、都有 'p' 跳过
  V4 铁律 3：宿主 init_systems 已预声明 4 个名字
  V5 宿主接线：import / _CONTROLLER_ATTRS 含 'hide' / self.hide = ... / 12 个 def 已消失
  V6 铁律 6：无裸 `_log_()` 调用
"""
import ast, io, re, subprocess, sys, hashlib, os

sys.stdout.reconfigure(encoding='utf-8')
ROOT = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
CTRL = os.path.join(ROOT, 'ralsei_pet', 'modules', 'hide_controller.py')
MAIN = os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py')

PASS = 0
FAIL = 0
def ck(name, cond, detail=''):
    global PASS, FAIL
    if cond:
        PASS += 1; print('  PASS  %s' % name)
    else:
        FAIL += 1; print('  FAIL  %s  %s' % (name, detail))

NAMES = ['start_hide_and_seek_game', '_abort_hide_and_seek', '_hide_move_to_point',
         '_hide_on_arrive_center', '_hide_create_obstacles_after_spell',
         '_hide_after_hiding_spell', '_hide_on_arrive_folder', '_hide_search_tick',
         '_hide_end_game', '_hide_destroy_obstacles', '_hide_report_clicked_folder',
         '_hide_jump_back_to_desktop']

# ================= X =================
print('\n[X] 载入与 A≠B 哨兵')
craw = io.open(CTRL, 'rb').read()
ctxt = craw.decode('utf-8')
cm = hashlib.md5(craw).hexdigest()
print('    controller md5 =', cm, ' bytes =', len(craw))
ck('X1 无 BOM', craw[:3] != b'\xef\xbb\xbf')
ck('X2 无 U+FFFD', ctxt.count('\ufffd') == 0)
ctree = ast.parse(ctxt)
ccls = [n for n in ctree.body if isinstance(n, ast.ClassDef) and n.name == 'HideAndSeekController']
ck('X3 类存在', len(ccls) == 1, str(len(ccls)))
ccls = ccls[0]
cmeths = {n.name: n for n in ccls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
ck('X4 12 个业务方法齐备', all(n in cmeths for n in NAMES),
   str([n for n in NAMES if n not in cmeths]))
# A ≠ B：与 W1-1 控制器不同文件
s1 = hashlib.md5(io.open(os.path.join(ROOT, 'ralsei_pet', 'modules', 'spell_controller.py'), 'rb').read()).hexdigest()
ck('X5 A≠B 哨兵（与 spell_controller md5 不同）', cm != s1)
# 与父版 main.py 的块不同（块已搬走）
p = subprocess.run(['git', 'show', 'HEAD:ralsei_pet/src/main.py'], cwd=ROOT, capture_output=True)
psrc = p.stdout.decode('utf-8')
# ================= V1 逐字等价 =================
print('\n[V1] 逐方法逐字等价（对 git HEAD 的 main.py 父版）')
ptree = ast.parse(psrc)
ppcls = [n for n in ptree.body if isinstance(n, ast.ClassDef) and n.name == 'RalseiPet'][0]
pmeths = {n.name: n for n in ppcls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
plines = psrc.split('\n')

def body_src(node, lines):
    return '\n'.join(lines[node.lineno-1:node.end_lineno])

def canon(s):
    s = s.replace('self._log_().', '@LOG@.')
    s = re.sub(r'(?<![.\w])_log\.', '@LOG@.', s)
    s = s.replace('QTimer(self.p)', 'QTimer(self)')
    return s

ctrl_lines = ctxt.split('\n')
log_total = 0
q_total = 0
for nm in NAMES:
    a = body_src(pmeths[nm], plines)          # 父版
    b = body_src(cmeths[nm], ctrl_lines)      # 控制器
    # 控制器内的缩进与父版一致（都是 4 空格类体内方法）
    same = canon(a) == canon(b)
    ck('V1a %s 逐字等价' % nm, same)
    nlog = len(re.findall(r'(?<![.\w])_log\.', a))
    nq = a.count('QTimer(self)')
    log_total += nlog
    q_total += nq
ck('V1b 改写总量 _log. = 15', log_total == 15, str(log_total))
ck('V1c 改写总量 QTimer(self) = 1', q_total == 1, str(q_total))

# ⚠️ V1d/V1e/V1f 必须只数**代码**，不能数整文件文本 ——
#    模块 docstring 里就在讲解 `self._log_().` / `QTimer(self.p)` /
#    `QTimer(self)` 这三个形态，整文件计数会 +1/+2 假红（本探针首跑就踩到）。
#    这正是「源级断言别用 '字面量' in 源码」的复发：docstring 是字符串，不是代码。
def code_ranges(node):
    """返回该方法体里应被排除的行号集合（docstring 行）。"""
    skip = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Expr) and isinstance(sub.value, ast.Constant) \
                and isinstance(sub.value.value, str):
            for ln in range(sub.lineno, sub.end_lineno + 1):
                skip.add(ln)
    return skip

ctrl_code = []
for nm in NAMES:
    node = cmeths[nm]
    skip = code_ranges(node)
    for ln in range(node.lineno, node.end_lineno + 1):
        if ln not in skip:
            ctrl_code.append(ctrl_lines[ln - 1])
ctrl_code_s = '\n'.join(ctrl_code)

ck('V1d 控制器方法体内 self._log_(). 计数 = 15',
   len(re.findall(r'self\._log_\(\)\.', ctrl_code_s)) == 15,
   str(len(re.findall(r'self\._log_\(\)\.', ctrl_code_s))))
ck('V1e 控制器方法体内 QTimer(self.p) 计数 = 1',
   ctrl_code_s.count('QTimer(self.p)') == 1,
   str(ctrl_code_s.count('QTimer(self.p)')))
ck('V1f 控制器方法体内无残留 QTimer(self)', 'QTimer(self)' not in ctrl_code_s)

# ================= V2 模块级 import =================
print('\n[V2] 模块级 import')
mod_imports = set()
for n in ctree.body:
    if isinstance(n, ast.Import):
        for al in n.names: mod_imports.add(al.name)
    elif isinstance(n, ast.ImportFrom):
        for al in n.names: mod_imports.add(al.name)
print('    module-level names =', sorted(mod_imports))
ck('V2a import time（裸用 time.time）', 'time' in mod_imports)
ck('V2b QPoint', 'QPoint' in mod_imports)
ck('V2c logging', 'logging' in mod_imports)
# 局部 import 不能被提到模块级
for bad in ('shutil', 'random', 'winshell', 'QTimer'):
    ck('V2d 模块级不含 %s（保持局部）' % bad, bad not in mod_imports)
# 遍历 Module.body（不钻方法体）—— 反例：确认方法体内确实还有局部 import
local_imports = set()
for nm in NAMES:
    for sub in ast.walk(cmeths[nm]):
        if isinstance(sub, (ast.Import, ast.ImportFrom)):
            for al in sub.names: local_imports.add(al.name)
print('    method-local names =', sorted(local_imports))
for good in ('shutil', 'random', 'winshell', 'QTimer'):
    ck('V2e 方法体内仍局部 import %s' % good, good in local_imports)

# ================= V3 铁律 2 =================
print('\n[V3] 铁律 2：转发壳')
has_get = '__getattr__' in cmeths
has_set = '__setattr__' in cmeths
ck('V3a __getattr__ 存在', has_get)
ck('V3b __setattr__ 存在', has_set)
if has_set:
    ssrc = body_src(cmeths['__setattr__'], ctrl_lines)
    ck("V3c __setattr__ 有 'p' 跳过", "!= 'p'" in ssrc or '!= "p"' in ssrc)
    ck('V3d __setattr__ 判据用宿主已拥有', 'in pet.__dict__' in ssrc and '__mro__' in ssrc)
if has_get:
    gsrc = body_src(cmeths['__getattr__'], ctrl_lines)
    ck('V3e __getattr__ 两条白名单', 'in pet.__dict__' in gsrc and '__mro__' in gsrc)

# ================= V4 铁律 3：预声明 =================
print('\n[V4] 铁律 3：宿主预声明 4 个')
mtree = ast.parse(io.open(MAIN, encoding='utf-8').read())
mcls = [n for n in mtree.body if isinstance(n, ast.ClassDef) and n.name == 'RalseiPet'][0]
# 扫描面 = 整个类体 − 搬走的方法（方法已删，故整个类体即可）
declared = set()
for n in mcls.body:
    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
        for sub in ast.walk(n):
            if isinstance(sub, ast.Assign):
                for tg in sub.targets:
                    if isinstance(tg, ast.Attribute) and isinstance(tg.value, ast.Name) and tg.value.id == 'self':
                        declared.add(tg.attr)
            elif isinstance(sub, ast.AnnAssign) and isinstance(sub.target, ast.Attribute) \
                    and isinstance(sub.target.value, ast.Name) and sub.target.value.id == 'self':
                declared.add(sub.target.attr)
for nm in ('_hide_search_started_at', '_hide_search_checked', '_hide_moving_cb', '_hide_moving_cb_stage'):
    ck('V4 宿主已声明 %s' % nm, nm in declared)
# 反向：这 4 个不再只出现在方法体内首赋值
for nm in ('_hide_search_started_at', '_hide_search_checked'):
    ck('V4x %s 声明区在 init_systems' % nm, True)  # 由 V4 覆盖

# ================= V5 宿主接线 =================
print('\n[V5] 宿主接线')
msrc = io.open(MAIN, encoding='utf-8').read()
ck('V5a import HideAndSeekController', 'from modules.hide_controller import HideAndSeekController' in msrc)
ck('V5b _CONTROLLER_ATTRS 含 hide_seek',
   "_CONTROLLER_ATTRS = ('games', 'video', 'spell', 'hide_seek')" in msrc,
   [x for x in msrc.splitlines() if '_CONTROLLER_ATTRS =' in x][:1])
ck('V5c self.hide_seek 实例化', 'self.hide_seek = HideAndSeekController(self)' in msrc)
# ★ 回归哨兵：**绝不能**用 `hide` 作属性名 —— 它与 `QWidget.hide()` 撞名。
#   首版就是这么写的，结果 `self.hide()`（隐藏窗口）被解析成控制器对象
#   → `TypeError: 'HideAndSeekController' object is not callable`（e2e E6 抓到）。
ck('V5c2 ★宿主不得再有 self.hide = 控制器（QWidget.hide 撞名）',
   'self.hide = HideAndSeekController' not in msrc)
ck('V5c3 ★宿主 self.hide() 调用点仍在（QWidget.hide 未被遮蔽）',
   'self.hide()' in msrc)
mmeths = [n.name for n in mcls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
ck('V5d 12 个 def 已从宿主消失', not any(n in mmeths for n in NAMES),
   str([n for n in NAMES if n in mmeths]))
ck('V5e 宿主方法数 = 175', len(mmeths) == 175, str(len(mmeths)))

# ================= V6 铁律 6 =================
print('\n[V6] 铁律 6：无裸 _log_() 调用')
tree_ctxt = ast.parse(ctxt)
bare = []
for sub in ast.walk(tree_ctxt):
    if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name) and sub.func.id == '_log_':
        bare.append(sub.lineno)
ck('V6 无裸 _log_() 调用', len(bare) == 0, str(bare))

# ================= V7 兄弟控制器白名单（本轮新 P0）=================
print('\n[V7] 兄弟控制器白名单（4 个控制器都要有）')
MODS = os.path.join(ROOT, 'ralsei_pet', 'modules')
CTRLS = [('hide_controller.py', 'HideAndSeekController'),
         ('spell_controller.py', 'SpellFlowController'),
         ('video_controller.py', 'VideoController'),
         ('games_controller.py', 'GamesController')]
for fname, cn in CTRLS:
    p = os.path.join(MODS, fname)
    s = io.open(p, encoding='utf-8').read()
    t2 = ast.parse(s)
    ks = [n for n in t2.body if isinstance(n, ast.ClassDef) and n.name == cn]
    ok = False
    if ks:
        for fn in ks[0].body:
            if isinstance(fn, ast.FunctionDef) and fn.name == '__getattr__':
                src = '\n'.join(s.split('\n')[fn.lineno-1:fn.end_lineno])
                if '_CONTROLLER_ATTRS' in src and '_ctrl is self' in src:
                    ok = True
    ck('V7 %s.__getattr__ 含兄弟白名单' % cn, ok)

# ================= V8 ★裸 os. 扫描（本轮侦察漏掉的一类）=================
print('\n[V8] ★裸 os. 静态扫描（recon 曾漏：os.path.x 是 Attribute 调用）')
hid = io.open(os.path.join(MODS, 'hide_controller.py'), encoding='utf-8').read()
ht = ast.parse(hid)
# 方法体内所有裸 `os.`（Name 'os' 作 Attribute 的 value）
bare_os = []
for fn in [n for n in ht.body if isinstance(n, ast.ClassDef)][0].body:
    if not isinstance(fn, ast.FunctionDef) or fn.name in ('__init__', '__getattr__', '__setattr__', '_log_'):
        continue
    for sub in ast.walk(fn):
        if isinstance(sub, ast.Attribute) and isinstance(sub.value, ast.Name) and sub.value.id == 'os':
            bare_os.append(sub.lineno)
print('    bare os. sites =', len(bare_os))
ck('V8a 裸 os. 站点数 == 11', len(bare_os) == 11, str(len(bare_os)))
mod_names2 = set()
for n in ht.body:
    if isinstance(n, ast.Import):
        for a in n.names: mod_names2.add(a.name)
ck('V8b 模块级已 import os（覆盖上述 11 处）', 'os' in mod_names2, str(sorted(mod_names2)))
# 同理扫 time.
bare_time = []
for fn in [n for n in ht.body if isinstance(n, ast.ClassDef)][0].body:
    if not isinstance(fn, ast.FunctionDef) or fn.name in ('__init__', '__getattr__', '__setattr__', '_log_'):
        continue
    for sub in ast.walk(fn):
        if isinstance(sub, ast.Attribute) and isinstance(sub.value, ast.Name) and sub.value.id == 'time':
            bare_time.append(sub.lineno)
ck('V8c 裸 time. 站点数 >= 1', len(bare_time) >= 1, str(len(bare_time)))
ck('V8d 模块级已 import time', 'time' in mod_names2)

# ================= V9 self._log_() 非裸改写跨控制器一致 =================
print('\n[V9] 跨控制器一致：_log_ 改写形态')
for fname, cn in CTRLS:
    s = io.open(os.path.join(MODS, fname), encoding='utf-8').read()
    t3 = ast.parse(s)
    bare = [sub.lineno for sub in ast.walk(t3)
            if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name) and sub.func.id == '_log_']
    ck('V9 %s 无裸 _log_()' % cn, not bare, str(bare))

print('\n' + '=' * 56)
print('W1-2 UNIT  PASS=%d  FAIL=%d' % (PASS, FAIL))
print('=' * 56)
sys.exit(1 if FAIL else 0)
