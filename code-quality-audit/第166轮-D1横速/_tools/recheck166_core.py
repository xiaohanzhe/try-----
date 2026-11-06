# -*- coding: utf-8 -*-
u"""第166轮 · 核心文件复检（`recheck166_core`）。

## 为什么"动过核心文件"的轮次都要单独跑这一遍

`check166` 全绿只说明"我写的那些判据没红"，**不说明我改过的东西本身是干净的**：
语法被改坏、行尾被换成混合、常量被顺手改掉、基线丢了键（`run_all` 静默跳过）、
文件被回滚成旧版（第113轮：静态自洽 ⇒ 跑起来不报错）。
本工具**不复用任何套件判据**，只对"这一轮动过的文件"做七项体检。

| 段 | 查什么 |
|---|---|
| ① | 语法：动过的 `.py` 都能 `ast.parse`（**不产 `.pyc`** —— 复检不许改变被测状态） |
| ② | 结构：新方法/常量/接线点都在，且**各恰一处**（重复定义 = 静默覆盖） |
| ③ | 编码/换行：无 BOM；main.py 仍全 CRLF；其余行尾不混 |
| ④ | 恒真复查：判据第二参不是恒真常量；判据名不重复、带段号、条数够 |
| ⑤ | 逐令牌：设计里的每个数字都还是那个数字（12 / 320 / 600 / 40 / 500 / 250） |
| ⑥ | 工作区/基线：`SUITES` 里恰登记一次、脚本在、基线里有 `check166` 且是绿的 |
| ⑦ | 反回滚：文件不许比记录缩水（第113轮闸），关键内容必须还在 |

⚠️ 本工具**只读**：不改任何文件、不写盘、不联网、不需要显示器、不构造 `RalseiPet()`。
"""
import ast
import io
import json
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
MAIN = os.path.join(PET, 'src', 'main.py')
M2 = os.path.join(PET, 'modules', 'motion2d.py')
RUN_ALL = os.path.join(ROOT, 'code-quality-audit', 'regress', 'run_all.py')
BASELINE = os.path.join(ROOT, 'code-quality-audit', 'regress', 'baseline.json')
CHECK166 = os.path.join(HERE, 'check166.py')
MUT = os.path.join(HERE, 'mutate166.py')
PROBE = os.path.join(HERE, 'probe166_full.py')

_p = _f = 0
_bad = []


def check(desc, cond, extra=''):
    global _p, _f
    if cond:
        _p += 1
        print('[PASS] %s%s' % (desc, ('    ' + extra) if extra else ''))
    else:
        _f += 1
        _bad.append(desc)
        print('[FAIL] %s%s' % (desc, ('    ' + extra) if extra else ''))


def read_raw(path):
    with open(path, 'rb') as fh:
        return fh.read()


def read_txt(path):
    u"""按字节忠实读（`newline=''`：别让 Python 替我们改行尾）。"""
    with io.open(path, 'r', encoding='utf-8', newline='') as fh:
        return fh.read()


def ast_of(path):
    try:
        return ast.parse(read_txt(path))
    except SyntaxError as e:
        print('  (ast 失败 %s: %s)' % (os.path.basename(path), e))
        return None


def module_const(tree, name):
    u"""取模块级 `NAME = <常量>` 的值；找不到返回 `None`（并**不**回退成默认值）。"""
    if tree is None:
        return None
    for n in tree.body:
        if isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name) and t.id == name:
                    if isinstance(n.value, ast.Constant):
                        return n.value.value
    return None


def class_method(tree, cls_name, meth):
    for n in ast.walk(tree):
        if isinstance(n, ast.ClassDef) and n.name == cls_name:
            for b in n.body:
                if isinstance(b, ast.FunctionDef) and b.name == meth:
                    return b
    return None


# ============================================================ ① 语法
print('=' * 66)
print(u'① 语法（不产 .pyc：复检不许改变被测状态）')
print('=' * 66)

_FILES = [MAIN, M2, CHECK166, MUT, PROBE, RUN_ALL]
_ast_maps = {}
for _pth in _FILES:
    check(u'① 可解析：%s' % os.path.basename(_pth),
          os.path.isfile(_pth) and ast_of(_pth) is not None, _pth)
    if os.path.isfile(_pth):
        _ast_maps[_pth] = ast_of(_pth)

_T_MAIN = _ast_maps.get(MAIN)
_T_M2 = _ast_maps.get(M2)
_T_CHECK = _ast_maps.get(CHECK166)
_src_main = read_txt(MAIN) if os.path.isfile(MAIN) else ''

# ============================================================ ② 结构
print('')
print('=' * 66)
print(u'② 结构：常量/方法/接线点都在，且各恰一处（重复定义 = 静默覆盖）')
print('=' * 66)

_METHODS = [u'def _lock_jump_velocity']
for _n in _METHODS:
    check(u'② 方法各恰一处：`%s`' % _n.replace(u'def ', u''),
          _src_main.count(_n) == 1, u'实得 %d 处' % _src_main.count(_n))

_SNAP_DEFS = 0
for _n in (_T_MAIN.body if _T_MAIN is not None else []):
    if isinstance(_n, ast.Assign):
        for _t in _n.targets:
            if isinstance(_t, ast.Name) and _t.id == 'JUMP_SNAP_PX':
                _SNAP_DEFS += 1
check(u'② `JUMP_SNAP_PX` 模块级只定义一次（单一真源）', _SNAP_DEFS == 1,
      u'实得 %d 处' % _SNAP_DEFS)

_hj = class_method(_T_MAIN, 'RalseiPet', 'handle_jump')

# ★ 逐点核对（**不是估的**，第一版按"8 次"估，实测 6 次）：
#   `init_movement` 置 None 1 / `start_jump` 元组解包 1 / `start_jump` 回落分支置 None 1 /
#   落空分支清 1 / 正常落地清 1 / 惊讶小跳置 0 1 = **6**。
#   ⚠️ `handle_jump` 读的是 `getattr(self, '_jump_vx0', None)` —— 那是**字符串**，
#   不计入 `self._jump_vx0` 的出现（这条差别正是 D3 判据栽过的那个坑）。
_WIRE = [
    (u'self._jump_vx0', 6, u'锁存位**赋值**点（初始化 1 / 起跳 2 / 清 2 / 小跳 1）'),
]
for _needle, _want, _why in _WIRE:
    _got = _src_main.count(_needle)
    check(u'② 出现 %d 次：%s' % (_want, _why), _got == _want, u'实得 %d 处' % _got)

# ★ 旧口径：文本计数是 2（另一处在注释 `旧写法 vx = delta_x / ...` 里）
#   ⇒ 语句级用下面的 AST 判（`_vx_assigns`），别被注释骗。
_legacy_txt = _src_main.count(u'vx = delta_x / self.jump_duration')
check(u'② 旧口径文本出现 2 次（1 条语句 + 1 处注释引用；多一处就要问"哪来的"）',
      _legacy_txt == 2, u'实得 %d 处' % _legacy_txt)

# ★ `JUMP_SNAP_PX` 的**代码**使用点用 AST 数（文本会把注释里的也算进去，第一版就数成 5）
_hj_snap = 0
for _n in ast.walk(_hj or ast.Module(body=[], type_ignores=[])):
    if isinstance(_n, ast.Name) and _n.id == 'JUMP_SNAP_PX':
        _hj_snap += 1
check(u'② ★ AST：`handle_jump` 里真的用了 `JUMP_SNAP_PX` **2 处**（吸附判定 + 落空判定）',
      _hj_snap == 2, u'实得 %d 处' % _hj_snap)

_vx_assigns = 0
for _n in ast.walk(_hj or ast.Module(body=[], type_ignores=[])):
    if isinstance(_n, ast.Assign):
        for _t in _n.targets:
            if isinstance(_t, ast.Name) and _t.id == 'vx':
                _vx_assigns += 1
check(u'② ★ AST：`handle_jump` 里给 `vx` 赋值的**语句**恰 2 条（锁存读取 if/else 各一）',
      _vx_assigns == 2, u'实得 %d 条（注释里的旧写法不算）' % _vx_assigns)

_hop = class_method(_T_MAIN, 'RalseiPet', '_start_surprised_hop')
_hop_ok = False
for _n in ast.walk(_hop or ast.Module(body=[], type_ignores=[])):
    if isinstance(_n, ast.Assign):
        for _t in _n.targets:
            if (isinstance(_t, ast.Attribute) and _t.attr == '_jump_vx0'
                    and isinstance(_n.value, ast.Constant) and _n.value.value == 0.0):
                _hop_ok = True
check(u'② 惊讶小跳**显式**把 `_jump_vx0` 置 0（它不走 `start_jump`）', _hop_ok)

_initmv = class_method(_T_MAIN, 'RalseiPet', 'init_movement')
_init_none = {}
for _a in ('_jump_vx0', '_jump_vy0', '_jump_dur0'):
    _hit = False
    for _n in ast.walk(_initmv or ast.Module(body=[], type_ignores=[])):
        if isinstance(_n, ast.Assign):
            for _t in _n.targets:
                if (isinstance(_t, ast.Attribute) and _t.attr == _a
                        and isinstance(_n.value, ast.Constant) and _n.value.value is None):
                    _hit = True
    _init_none[_a] = _hit
check(u'② `init_movement` 里三个锁存位都初始化为 `None`',
      all(_init_none.values()), u'%s' % (_init_none,))

check(u'② `motion2d` 仍是零依赖纯函数模块（只 import math）',
      _T_M2 is not None
      and [n.names[0].name for n in _T_M2.body if isinstance(n, ast.Import)] == ['math'],
      u'实得 %s' % ([n.names[0].name for n in _T_M2.body
                    if isinstance(n, ast.Import)] if _T_M2 else None,))

# ============================================================ ③ 编码/换行
print('')
print('=' * 66)
print(u'③ 编码/换行（中文项目最容易毁在这里）')
print('=' * 66)

for _pth in _FILES:
    _raw = read_raw(_pth) if os.path.isfile(_pth) else b''
    _crlf = _raw.count(b'\r\n')
    _lf = _raw.count(b'\n') - _crlf
    check(u'③ 无 BOM：%s' % os.path.basename(_pth),
          not _raw.startswith(b'\xef\xbb\xbf'))
    check(u'③ 行尾不混：%s（CRLF=%d 裸LF=%d）' % (os.path.basename(_pth), _crlf, _lf),
          not (_crlf > 0 and _lf > 0))

_raw_main = read_raw(MAIN)
check(u'③ ★ main.py 仍是全 CRLF（裸 LF 必须为 0）',
      (_raw_main.count(b'\n') - _raw_main.count(b'\r\n')) == 0,
      u'裸LF=%d' % (_raw_main.count(b'\n') - _raw_main.count(b'\r\n')))

# ============================================================ ④ 恒真复查
print('')
print('=' * 66)
print(u'④ 恒真复查（判据的第二参不许是常量；判据名不许重复）')
print('=' * 66)

_names = []
_trivial = []
for _n in ast.walk(_T_CHECK or ast.Module(body=[], type_ignores=[])):
    if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Name) \
            and _n.func.id == 'check' and len(_n.args) >= 2:
        _a0, _a1 = _n.args[0], _n.args[1]
        if isinstance(_a0, ast.Constant) and isinstance(_a0.value, str):
            _names.append(_a0.value)
        # 只抓**恒真**；恒假每次必红、藏不住，且本项目正当用于"前置缺失时显式报红"
        if isinstance(_a1, ast.Constant):
            if _a1.value:
                _trivial.append(_a0.value if isinstance(_a0, ast.Constant) else '?')
        elif isinstance(_a1, (ast.List, ast.Tuple, ast.Set)) and _a1.elts:
            _trivial.append(_a0.value if isinstance(_a0, ast.Constant) else '?')
        elif isinstance(_a1, ast.Dict) and _a1.keys:
            _trivial.append(_a0.value if isinstance(_a0, ast.Constant) else '?')
check(u'④ ★★★ 没有"第二参是**恒真**常量"的判据（85 `{}=={}` 同族；恒假豁免）',
      not _trivial, u'命中 %s' % (_trivial[:3],))
check(u'④ 判据条数够（≥ 30 条，防"判据被删空还全绿"）',
      len(_names) >= 30, u'实得 %d 条' % len(_names))
_dup = sorted({s for s in _names if _names.count(s) > 1})
check(u'④ 判据名不重复（重名 ⇒ 一条红两条都像红，DIFF 时定位不到）',
      not _dup, u'重复 %s' % (_dup[:3],))
check(u'④ 判据名都带段号（A/B/C/D/E 开头，便于定位）',
      all(s[:1] in 'ABCDE' for s in _names),
      u'例外 %s' % ([s for s in _names if s[:1] not in 'ABCDE'][:3],))

# ============================================================ ⑤ 逐令牌
print('')
print('=' * 66)
print(u'⑤ 逐令牌：设计里的每个数字都还是那个数字')
print('=' * 66)

_SNAP = module_const(_T_MAIN, 'JUMP_SNAP_PX')
check(u'⑤ `JUMP_SNAP_PX` = 12.0（半个身位量级，用户口径"阈值内吸附"）',
      _SNAP == 12.0, u'实得 %r' % (_SNAP,))
check(u'⑤ `RUNUP_SPEED_MAX` = 320（冲刺上限没被顺手调）',
      module_const(_T_MAIN, 'RUNUP_SPEED_MAX') == 320.0,
      u'实得 %r' % (module_const(_T_MAIN, 'RUNUP_SPEED_MAX'),))
check(u'⑤ `RUNUP_ACCEL` = 600（助跑加速度）',
      module_const(_T_MAIN, 'RUNUP_ACCEL') == 600.0,
      u'实得 %r' % (module_const(_T_MAIN, 'RUNUP_ACCEL'),))
check(u'⑤ `RUNUP_MIN_PX` = 40（最短助跑距离 = 近跳那一步半）',
      module_const(_T_MAIN, 'RUNUP_MIN_PX') == 40,
      u'实得 %r' % (module_const(_T_MAIN, 'RUNUP_MIN_PX'),))
check(u'⑤ `motion2d.GRAVITY` = 500 / `JUMP_SPEED` = 250（高度上限的根）',
      module_const(_T_M2, 'GRAVITY') == 500.0
      and module_const(_T_M2, 'JUMP_SPEED') == 250.0,
      u'%r / %r' % (module_const(_T_M2, 'GRAVITY'), module_const(_T_M2, 'JUMP_SPEED')))

try:
    sys.path.insert(0, os.path.join(PET, 'modules'))
    import motion2d as _m2                              # noqa: N816
    _l320 = _m2.runup_distance(320.0, 0.0, 600.0)
    check(u'⑤ `runup_distance(320, 0, 600)` = 320²/(2×600) = 85.333（助跑距离口径）',
          abs(_l320 - 85.3333333) < 1e-4, u'实得 %.4f' % _l320)
    check(u'⑤ `max_jump_height()` = 250²/(2×500) = 62.5（高度硬上限没动）',
          abs(_m2.max_jump_height() - 62.5) < 1e-9, u'实得 %.4f' % _m2.max_jump_height())
    check(u'⑤ `flight_time(0)` = 2×250/500 = 1.0s（与产品 `jump_duration` 默认值一致）',
          abs(_m2.flight_time(0.0) - 1.0) < 1e-9, u'实得 %.4f' % _m2.flight_time(0.0))
except Exception as _e:                                 # noqa: BLE001
    check(u'⑤ `motion2d` 可导入', False, '%s: %s' % (type(_e).__name__, _e))

# ============================================================ ⑥ 工作区/基线
print('')
print('=' * 66)
print(u'⑥ 工作区/基线：登记恰好一次、脚本在、基线有键')
print('=' * 66)

_ra_src = read_txt(RUN_ALL) if os.path.isfile(RUN_ALL) else ''
check(u'⑥ `SUITES` 里 check166 登记**恰好一次**',
      _ra_src.count(u"'id': 'check166'") == 1,
      u'实得 %d 处' % _ra_src.count(u"'id': 'check166'"))
check(u'⑥ 登记的脚本路径存在', os.path.isfile(CHECK166))
check(u'⑥ 登记里带 `offscreen: True`（否则无显示器环境跑不起来）',
      u"'id': 'check166'" in _ra_src
      and u"'offscreen': True" in _ra_src.split(u"'id': 'check166'")[1][:300],
      u'%s' % (_ra_src.split(u"'id': 'check166'")[1][:100].replace('\n', ' ')
               if u"'id': 'check166'" in _ra_src else '-',))

try:
    with io.open(BASELINE, 'r', encoding='utf-8') as fh:
        _bl = json.load(fh)
    _suites = _bl.get('suites') or _bl
    check(u'⑥ 基线里有 check166 的键', 'check166' in _suites,
          u'键数=%d' % len(_suites))
    _ent = _suites.get('check166') or {}
    # ★ 必须**连"键在不在"一起判**：键缺失时 `_ent == {}`，`not _ent.get('fail')`
    #   会变成 `not None` == True ⇒ 这条判据变成恒真，专门掩护上面那条红。
    check(u'⑥ 基线记着这次是绿的（键在 + fail=0 + exit=0）',
          ('check166' in _suites) and (not _ent.get('fail')) and (not _ent.get('exit')),
          u'键在=%s exit=%s fail=%s pass=%s'
          % ('check166' in _suites, _ent.get('exit'), _ent.get('fail'), _ent.get('pass')))
except Exception as _e:                                 # noqa: BLE001
    check(u'⑥ 基线可读', False, '%s: %s' % (type(_e).__name__, _e))

# ============================================================ ⑦ 反回滚
print('')
print('=' * 66)
print(u'⑦ 反回滚（第113轮：工作区被换成旧版而 git 不报错，静态自洽跑不红）')
print('=' * 66)

#: 文件 → (最小行数, 必须还在的字面量)
REGRESSION_ANCHORS = {
    MAIN: (20000, [u'def _lock_jump_velocity', u'self._jump_vx0 = None',
                   u'_vx_land = getattr(self, \'_jump_vx0\', None)',
                   u'_miss_px = _x_calc - self.jump_target_pos.x()',
                   u'JUMP_SNAP_PX = 12.0']),
    M2: (150, [u'def plan_jump', u'def runup_distance', u'def flight_time']),
    CHECK166: (330, [u'def _lock', u'C2 落点差', u'E5 分母闸']),
}
for _pth, (_min_lines, _needles) in REGRESSION_ANCHORS.items():
    _txt = read_txt(_pth) if os.path.isfile(_pth) else ''
    _n = _txt.count('\n') + 1
    check(u'⑦ %s 行数没缩水（%d ≥ %d）' % (os.path.basename(_pth), _n, _min_lines),
          _n >= _min_lines)
    for _needle in _needles:
        check(u'⑦ %s 里 `%s` 还在' % (os.path.basename(_pth), _needle[:44]),
              _needle in _txt)

check(u'⑦ 产品文件里**没有**第166轮的变异体残留（`（变异体` / `MUTATION`）',
      (u'（变异体' not in _src_main) and (u'MUTATION' not in _src_main))

print('')
print('=' * 66)
print('PASS=%d  FAIL=%d' % (_p, _f))
if _f:
    print(u'失败项：')
    for _x in _bad:
        print(u'  - %s' % _x)
    sys.exit(1)
print('[PASS] 第166轮核心文件复检全部通过')
