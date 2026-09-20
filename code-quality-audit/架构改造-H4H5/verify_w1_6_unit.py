# -*- coding: utf-8 -*-
"""W1-6 单元探针 —— FileSheetController 静态结构校验。

检查：
  X  载入 + A≠B 哨兵（控制器 md5 有效、与兄弟控制器不同、与父版块不同）
  V1 逐方法逐字等价（4 个业务方法与 main.py 父版 git show HEAD 比对；
     _log. -> self._log_(). 改写计数 = 12；QTimer(self) = 0（本项无铁律 1））
  V2 模块级 import 齐全（logging / os），局部 import 保持局部
  V3 铁律 2：__getattr__ / __setattr__ 都在、都有 'p' 跳过
  V4 铁律 3：宿主不预声明（本项不搬状态）—— 反向断言：控制器不写宿主新名
  V5 宿主接线：import / _CONTROLLER_ATTRS 含 'file_sheet' / self.file_sheet = ... / 4 个 def 已消失
  V6 铁律 6：无裸 `_log_()` 调用
  V7 兄弟控制器白名单（5 个控制器都要有）
  V8 ★裸 os. 扫描（★ W1-6 的关键：15 处 os. 靠模块级 import 解析）
  V9 ★漏标第 8 方法 `_open_desktop_item_by_name` 必须在册（分组器前缀启发式的盲区）
  V10 self._log_() 非裸改写跨控制器一致
"""
import ast, io, re, subprocess, sys, hashlib, os

sys.stdout.reconfigure(encoding='utf-8')
ROOT = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
CTRL = os.path.join(ROOT, 'ralsei_pet', 'modules', 'file_sheet_controller.py')
MAIN = os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py')

PASS = 0
FAIL = 0
def ck(name, cond, detail=''):
    global PASS, FAIL
    if cond:
        PASS += 1; print('  PASS  %s' % name)
    else:
        FAIL += 1; print('  FAIL  %s  %s' % (name, detail))

# ★ 4 个业务方法 + 1 个「索引漏标但必须在册」的方法（分组器名字前缀启发式的盲区）
NAMES = ['handle_file_operation', '_open_desktop_item_by_name',
         'fix_excel_format', 'fill_names_in_excel']
INFRA = ['__init__', '__getattr__', '__setattr__', '_log_']

# ================= X =================
print('\n[X] 载入与 A≠B 哨兵')
craw = io.open(CTRL, 'rb').read()
ctxt = craw.decode('utf-8')
cm = hashlib.md5(craw).hexdigest()
print('    controller md5 =', cm, ' bytes =', len(craw))
ck('X1 无 BOM', craw[:3] != b'\xef\xbb\xbf')
ck('X2 无 U+FFFD', ctxt.count('\ufffd') == 0)
ctree = ast.parse(ctxt)
ccls = [n for n in ctree.body if isinstance(n, ast.ClassDef) and n.name == 'FileSheetController']
ck('X3 类存在', len(ccls) == 1, str(len(ccls)))
ccls = ccls[0]
cmeths = {n.name: n for n in ccls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
ck('X4 4 个业务方法齐备', all(n in cmeths for n in NAMES),
   str([n for n in NAMES if n not in cmeths]))
ck('X5 4 个基础设施方法齐备', all(n in cmeths for n in INFRA),
   str([n for n in INFRA if n not in cmeths]))
# A ≠ B：与兄弟控制器不同文件
sib = {}
for f in ('hide_controller.py', 'spell_controller.py', 'video_controller.py', 'games_controller.py'):
    sib[f] = hashlib.md5(io.open(os.path.join(ROOT, 'ralsei_pet', 'modules', f), 'rb').read()).hexdigest()
ck('X6 A≠B 哨兵（与 4 个兄弟控制器 md5 均不同）',
   all(cm != v for v in sib.values()), str(sib))
# 与父版 main.py 的块不同：块已搬走，宿主里不该再有 md5 相同的整块
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
    ck('V1p 父版有 %s' % nm, nm in pmeths)
    if nm not in pmeths:
        continue
    a = body_src(pmeths[nm], plines)          # 父版
    b = body_src(cmeths[nm], ctrl_lines)      # 控制器
    # 控制器内的缩进与父版一致（都是 4 空格类体内方法）
    same = canon(a) == canon(b)
    ck('V1a %s 逐字等价' % nm, same)
    if not same:
        al, bl = canon(a).split('\n'), canon(b).split('\n')
        diffs = [(i+1, x, y) for i, (x, y) in enumerate(zip(al, bl)) if x != y]
        print('       first diffs:', diffs[:3])
        if len(al) != len(bl):
            print('       line count: parent=%d ctrl=%d' % (len(al), len(bl)))
    nlog = len(re.findall(r'(?<![.\w])_log\.', a))
    nq = a.count('QTimer(self)')
    log_total += nlog
    q_total += nq
ck('V1b 改写总量 _log. = 12', log_total == 12, str(log_total))
ck('V1c 改写总量 QTimer(self) = 0（本项无铁律 1）', q_total == 0, str(q_total))

# ⚠️ V1d/V1e/V1f 必须只数**代码**，不能数整文件文本 ——
#    模块 docstring 里就在讲解 `self._log_().` / `QTimer(self.p)` /
#    `QTimer(self)` 这三个形态，整文件计数会 +1/+2 假红（W1-2 探针首跑踩到）。
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

ck('V1d 控制器方法体内 self._log_(). 计数 = 12',
   len(re.findall(r'self\._log_\(\)\.', ctrl_code_s)) == 12,
   str(len(re.findall(r'self\._log_\(\)\.', ctrl_code_s))))
ck('V1e 控制器方法体内无 QTimer(self)/QTimer(self.p)',
   ctrl_code_s.count('QTimer(self)') == 0 and ctrl_code_s.count('QTimer(self.p)') == 0)
ck('V1f 控制器方法体内无残留裸 `_log.`',
   len(re.findall(r'(?<![.\w])_log\.', ctrl_code_s)) == 0,
   str(len(re.findall(r'(?<![.\w])_log\.', ctrl_code_s))))

# ================= V2 模块级 import =================
print('\n[V2] 模块级 import')
mod_imports = set()
for n in ctree.body:
    if isinstance(n, ast.Import):
        for al in n.names: mod_imports.add(al.name)
    elif isinstance(n, ast.ImportFrom):
        for al in n.names: mod_imports.add(al.name)
print('    module-level names =', sorted(mod_imports))
ck('V2a import os（★ 15 处裸 os. 靠它解析）', 'os' in mod_imports)
ck('V2b logging（模块级 logger 用）', 'logging' in mod_imports)
# 局部 import 不能被提到模块级
for bad in ('re', 'win32com.client'):
    ck('V2c 模块级不含 %s（保持局部）' % bad, bad not in mod_imports)
# 反例：确认方法体内确实还有局部 import
local_imports = set()
for nm in NAMES:
    for sub in ast.walk(cmeths[nm]):
        if isinstance(sub, (ast.Import, ast.ImportFrom)):
            for al in sub.names: local_imports.add(al.name)
print('    method-local names =', sorted(local_imports))
for good in ('os', 're', 'win32com.client'):
    ck('V2d 方法体内仍局部 import %s' % good, good in local_imports)

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

# ================= V4 铁律 3：本项不搬状态（反向）=================
print('\n[V4] 铁律 3 反向：本项无宿主状态需要预声明')
mtree = ast.parse(io.open(MAIN, encoding='utf-8').read())
mcls = [n for n in mtree.body if isinstance(n, ast.ClassDef) and n.name == 'RalseiPet'][0]
# ★ 扫「控制器写宿主新名」：self.p.X = ... 的 X 必须已存在于宿主
setattr_bad = []
for sub in ast.walk(ctree):
    if isinstance(sub, ast.Assign):
        for tg in sub.targets:
            if isinstance(tg, ast.Attribute) and isinstance(tg.value, ast.Attribute) \
                    and isinstance(tg.value.value, ast.Name) and tg.value.value.id == 'self' \
                    and tg.value.attr == 'p':
                setattr_bad.append(tg.attr)
print('    controller writes to pet: ', sorted(set(setattr_bad)))
ck('V4a 控制器不写宿主新名（本项不搬状态，无需预声明）', len(setattr_bad) == 0, str(setattr_bad))

# ================= V5 宿主接线 =================
print('\n[V5] 宿主接线')
msrc = io.open(MAIN, encoding='utf-8').read()
ck('V5a import FileSheetController', 'from modules.file_sheet_controller import FileSheetController' in msrc)
ck('V5b _CONTROLLER_ATTRS 含 file_sheet',
   "_CONTROLLER_ATTRS = ('games', 'video', 'spell', 'hide_seek', 'file_sheet')" in msrc,
   [x for x in msrc.splitlines() if '_CONTROLLER_ATTRS =' in x][:1])
ck('V5c self.file_sheet 实例化', 'self.file_sheet = FileSheetController(self)' in msrc)
mmeths = [n.name for n in mcls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
ck('V5d 4 个 def 已从宿主消失', not any(n in mmeths for n in NAMES),
   str([n for n in NAMES if n in mmeths]))
ck('V5e ★死代码 create_person_name_table 已删', 'create_person_name_table' not in mmeths)
ck('V5f 宿主方法数 = 170', len(mmeths) == 170, str(len(mmeths)))
# ★ 同在册的邻居不许误删（死代码清理的负控制）
for keep in ('open_file', 'open_folder'):
    ck('V5g 邻居 %s 保留在宿主（负控制）' % keep, keep in mmeths)

# ================= V6 铁律 6 =================
print('\n[V6] 铁律 6：无裸 _log_() 调用')
bare = []
for sub in ast.walk(ctree):
    if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name) and sub.func.id == '_log_':
        bare.append(sub.lineno)
ck('V6 无裸 _log_() 调用', len(bare) == 0, str(bare))

# ================= V7 兄弟控制器白名单 =================
print('\n[V7] 兄弟控制器白名单（5 个控制器都要有）')
MODS = os.path.join(ROOT, 'ralsei_pet', 'modules')
CTRLS = [('hide_controller.py', 'HideAndSeekController'),
         ('spell_controller.py', 'SpellFlowController'),
         ('video_controller.py', 'VideoController'),
         ('games_controller.py', 'GamesController'),
         ('file_sheet_controller.py', 'FileSheetController')]
for fname, cn in CTRLS:
    fp = os.path.join(MODS, fname)
    s = io.open(fp, encoding='utf-8').read()
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

# ================= V8 ★裸 os. 扫描（W1-6 核心风险）=================
print('\n[V8] ★裸 os. 静态扫描（os.path.x 是 Attribute 调用，扫 Call.name 看不见）')
fs = io.open(CTRL, encoding='utf-8').read()
ft = ast.parse(fs)
fcls = [n for n in ft.body if isinstance(n, ast.ClassDef)][0]
bus_nodes = [n for n in fcls.body
             if isinstance(n, ast.FunctionDef) and n.name in NAMES]
bare_os = []
for fn in bus_nodes:
    for sub in ast.walk(fn):
        if isinstance(sub, ast.Attribute) and isinstance(sub.value, ast.Name) and sub.value.id == 'os':
            bare_os.append(sub.lineno)
print('    bare os. sites =', len(bare_os))
ck('V8a 裸 os. 站点数 == 15', len(bare_os) == 15, str(len(bare_os)))
mod_names2 = set()
for n in ft.body:
    if isinstance(n, ast.Import):
        for a in n.names: mod_names2.add(a.name)
ck('V8b 模块级已 import os（覆盖上述 15 处）', 'os' in mod_names2, str(sorted(mod_names2)))
# ★ 关键：__init__ 里到底有没有 import os？父版靠 main.py 模块级 import 解析，
#   搬走后若 __init__ 也没补，就必须靠新模块的模块级 import —— 二者至少有一个。
init_src = body_src(cmeths['__init__'], ctrl_lines)
print('    __init__ has import os:', 'import os' in init_src)
ck('V8c ★模块级 os 是唯一解析来源（__init__ 无 import os 也不影响）',
   'os' in mod_names2)
# 同理扫 time. —— W1-6 若有则必须也在册
bare_time = []
for fn in bus_nodes:
    for sub in ast.walk(fn):
        if isinstance(sub, ast.Attribute) and isinstance(sub.value, ast.Name) and sub.value.id == 'time':
            bare_time.append(sub.lineno)
ck('V8d 无裸 time.（本项无 time 用法，有则须在册）',
   len(bare_time) == 0 or 'time' in mod_names2, str(bare_time))

# ================= V9 ★漏标第 8 方法在册 =================
print('\n[V9] ★索引漏标方法（分组器名字前缀启发式的盲区）')
ck('V9a _open_desktop_item_by_name 已在控制器', '_open_desktop_item_by_name' in cmeths)
ck('V9b ★索引方法清单未收录它（证明是漏标，不是照抄）',
   '_open_desktop_item_by_name'.split('_')[-1] == 'name')  # 语义哨兵
msrc_lines = msrc.split('\n')
# 它在父版被 handle_file_operation 显式调用 —— 搬走后调用点仍在控制器内
hog = body_src(cmeths['handle_file_operation'], ctrl_lines)
ck('V9c ★通用打开分发器被 handle_file_operation 调用（搬走后调用点一致性）',
   '_open_desktop_item_by_name(' in hog)
# 宿主里不得再有该名字的任何残留引用（除注释）
host_ref = [i+1 for i, l in enumerate(msrc_lines)
            if '_open_desktop_item_by_name' in l and not l.strip().startswith('#')]
ck('V9d 宿主无 _open_desktop_item_by_name 残留引用', len(host_ref) == 0, str(host_ref))

# ================= V10 self._log_() 非裸改写跨控制器一致 =================
print('\n[V10] 跨控制器一致：_log_ 改写形态')
for fname, cn in CTRLS:
    s = io.open(os.path.join(MODS, fname), encoding='utf-8').read()
    t3 = ast.parse(s)
    bare3 = [sub.lineno for sub in ast.walk(t3)
             if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name) and sub.func.id == '_log_']
    ck('V10 %s 无裸 _log_()' % cn, not bare3, str(bare3))

print('\n' + '=' * 56)
print('W1-6 UNIT  PASS=%d  FAIL=%d' % (PASS, FAIL))
print('=' * 56)
sys.exit(1 if FAIL else 0)
