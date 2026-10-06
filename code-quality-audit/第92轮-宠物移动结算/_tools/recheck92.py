# -*- coding: utf-8 -*-
u"""第92轮复检：改过**重要核心文件**（`main.py` / `run_all.py` / `baseline.json` /
`check92.py`）之后的六项自证（用户口径：「以后再调整重要核心文件时一定要记得复检」）。

六项（缺一不可）
----------------
  ① 语法/可编译（用 `ast.parse`，**不产 `.pyc`** —— 复检不许改变被测状态）
  ② 结构自检（改到的函数/条目都还在，且没粘连、没丢标题）
  ③ 无 BOM / 无 U+FFFD
  ④ **恒真判据复查**（有没有 `check(…, True)` 这种"看着在守其实没守"的写法）
  ⑤ **逐令牌回验**（改/删过的标识符、数字、路径 —— 逐个回原文件 `in` 一次；
     同时验证**被删掉的旧写法真的没了**）
  ⑥ 工作区状态 + 回归套件登记（`SUITES` 与 `baseline['suites']` 双向零差异）

★ 判据自己也会说谎 ⇒ 本脚本每条都打印**实测值**，不做"只报结论"的断言。
"""
import ast
import json
import os
import subprocess
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')
MAIN = os.path.join(PKG, 'src', 'main.py')
RUNALL = os.path.join(ROOT, 'code-quality-audit', 'regress', 'run_all.py')
BASE = os.path.join(ROOT, 'code-quality-audit', 'regress', 'baseline.json')
CHECK = os.path.join(HERE, 'check92.py')
MUTATE = os.path.join(HERE, 'mutate92.py')
PROBE = os.path.join(HERE, 'probe92.py')

_failed = []
_n = 0


def ck(desc, cond, detail=''):
    global _n
    _n += 1
    tag = '[PASS]' if cond else '[FAIL]'
    if not cond:
        _failed.append(desc)
    print('%s %s%s' % (tag, desc, ('    ' + detail) if detail else ''))


def read(p):
    with open(p, encoding='utf-8') as fh:
        return fh.read()


print('=' * 74)
print('第92轮复检：位移结算修复（"走不动/站桩"）')
print('=' * 74)

# ---------------------------------------------------------------- ① 语法
SRC = read(MAIN)
TREE = None
try:
    TREE = ast.parse(SRC)
    ok1 = True
    err = ''
except SyntaxError as e:
    ok1, err = False, str(e)
ck('① 语法：`main.py` 可被 AST 解析（用 ast.parse，不写 .pyc）', ok1, err)
for _p in (RUNALL, CHECK, MUTATE, PROBE):
    try:
        ast.parse(read(_p))
        ok = True
        e2 = ''
    except SyntaxError as e:
        ok, e2 = False, str(e)
    ck('① 语法：`%s` 可被 AST 解析' % os.path.basename(_p), ok, e2)

# ---------------------------------------------------------------- ② 结构
_funcs = {n.name for n in ast.walk(TREE) if isinstance(n, ast.FunctionDef)}
for _fn in ('update_movement', 'generate_new_move_target', 'init_movement',
            'handle_jump', '_virtual_screen_rect'):
    ck('② 结构：`main.py` 里 `%s` 仍在' % _fn, _fn in _funcs)

_lines = SRC.splitlines()
_dups = [l for l in _lines if l.strip().startswith('def ') and l.strip().endswith('):')]
ck('② 结构：文件行数 = %d（未出现"粘连成一行"）' % len(_lines), len(_lines) > 14000)
ck('② 结构：`main.py` 顶层 `class` 数量 = %d（≥1）'
   % sum(1 for n in TREE.body if isinstance(n, ast.ClassDef)),
   sum(1 for n in TREE.body if isinstance(n, ast.ClassDef)) >= 1)

_rt = read(RUNALL)
ck('② 结构：`run_all.py` 里 `check92` 已登记进 SUITES',
   "'id': 'check92'" in _rt)
_rt_tree = ast.parse(_rt)
_n_suites = 0
for _n2 in ast.walk(_rt_tree):
    if isinstance(_n2, ast.Assign) and len(_n2.targets) == 1 \
            and isinstance(_n2.targets[0], ast.Name) and _n2.targets[0].id == 'SUITES' \
            and isinstance(_n2.value, ast.List):
        _n_suites = len(_n2.value.elts)
ck('② 结构：SUITES 条目数 = %d（应为 82 = 81 + check92）' % _n_suites, _n_suites == 82,
   'n=%d' % _n_suites)

# ---------------------------------------------------------------- ③ 编码
for _p in (MAIN, RUNALL, CHECK, MUTATE, PROBE, BASE,
           os.path.join(ROOT, 'code-quality-audit', '第92轮-宠物移动结算',
                        '_tools', 'analyze92.py')):
    _b = open(_p, 'rb').read()
    _s = _b.decode('utf-8')
    ck('③ 编码：`%s` 无 BOM / 无 U+FFFD（bytes=%d）'
       % (os.path.basename(_p), len(_b)),
       _b[:3] != b'\xef\xbb\xbf' and '\ufffd' not in _s,
       'BOM=%s FFFD=%d' % (_b[:3] == b'\xef\xbb\xbf', _s.count('\ufffd')))

# ---------------------------------------------------------------- ④ 恒真判据复查
_ct = ast.parse(read(CHECK))
_hard_true = []
for _n3 in ast.walk(_ct):
    if isinstance(_n3, ast.Call) and isinstance(_n3.func, ast.Name) \
            and _n3.func.id == 'check' and len(_n3.args) >= 2:
        _cond = _n3.args[1]
        if isinstance(_cond, ast.Constant):
            _hard_true.append(getattr(_n3.args[0], 'value', '?')[:40])
ck('④ 恒真判据复查：`check92.py` 里没有 `check(..., <常量>)` 形态的裸判据',
   not _hard_true, 'found=%s' % _hard_true)

_mt = ast.parse(read(MUTATE))
_muts = 0
_bad_expect = []
for _n4 in ast.walk(_mt):
    if isinstance(_n4, ast.Assign) and len(_n4.targets) == 1 \
            and isinstance(_n4.targets[0], ast.Name) and _n4.targets[0].id == 'MUTS' \
            and isinstance(_n4.value, ast.List):
        _muts = len(_n4.value.elts)
        for _el in _n4.value.elts:                 # (id, desc, expect, old, new)
            _exp = _el.elts[2]
            if isinstance(_exp, ast.Constant) and _exp.value is None:
                _mid = _el.elts[0].value
                if _mid != 'M0':
                    _bad_expect.append(_mid)
ck('④ 恒真判据复查：变异清单里除负控制 M0 外没有"不指定期望判据"的条目',
   not _bad_expect, 'mutations=%d issues=%s' % (_muts, _bad_expect))
ck('④ 恒真判据复查：变异数 = %d（≥10）' % _muts, _muts >= 10)

# ---------------------------------------------------------------- ⑤ 逐令牌回验
TOKENS = [
    # 新增字段 / 中间量
    ('self._subpixel_x = 0.0', MAIN, 3),
    ('self._subpixel_y = 0.0', MAIN, 3),
    ('_raw_x', MAIN, 1),
    ('_raw_y', MAIN, 1),
    ('_carry_x', MAIN, 1),
    ('_carry_y', MAIN, 1),
    ('_speed_pos', MAIN, 1),
    # 修复锚点
    ('+ self._subpixel_x', MAIN, 1),
    ('new_x = int(round(_raw_x))', MAIN, 1),
    ('new_y = int(round(_raw_y))', MAIN, 1),
    ('self._subpixel_x = _carry_x if -1.0 < _carry_x < 1.0 else 0.0', MAIN, 1),
    ('target_move_speed = max(self.speed * (distance / 50.0), 1.0)', MAIN, 1),
    ('target_final_speed = max(target_move_speed * self._cached_mood_factor, 1.0)',
     MAIN, 1),
    # 判据 / 变异 / 登记
    ('CHECK92_MUTATION_HARNESS', CHECK, 1),
    ("'id': 'check92'", RUNALL, 1),
    ('def _resolve(', CHECK, 1),
    ('def _replay(', CHECK, 1),
    ('_SPEED_MEASURED = 0.91', CHECK, 1),
    ('_MOOD_MEASURED = 0.4', CHECK, 1),
    ('A4b', CHECK, 1),
    ('def _old_ramp_step(', CHECK, 1),
    ('def _new_ramp_step(', CHECK, 1),
    ('PROBE_MODE', PROBE, 1),
    ('_spy_move', PROBE, 1),
    ('A/B 对照', PROBE, 1),
]
for _tok, _path, _mincnt in TOKENS:
    _c = read(_path).count(_tok)
    ck('⑤ 逐令牌回验：`%s` 在 `%s` 里出现 %d 次（≥%d）'
       % (_tok[:52], os.path.basename(_path), _c, _mincnt),
       _c >= _mincnt, 'count=%d' % _c)

# 被删掉的旧写法必须真的没了
GONE = [
    ('self.min_speed * 0.7', MAIN),
    ('self.min_speed * 0.3', MAIN),
    ('self.min_speed * 0.5', MAIN),
    ('self.min_speed * 0.2', MAIN),
    ('self.min_speed * 0.4', MAIN),
    ('self.max_speed * 0.9', MAIN),
    ('self.max_speed * 0.5', MAIN),
    ('self.max_speed * 0.7', MAIN),
    ('self.max_speed * 0.4', MAIN),
    ('self.max_speed * 0.6', MAIN),
    ('new_x = current_pos.x() + direction_x * move_distance', MAIN),
    ('new_y = current_pos.y() + direction_y * move_distance', MAIN),
]
for _tok, _path in GONE:
    _c = read(_path).count(_tok)
    ck('⑤ 逐令牌回验（删除项）：旧写法 `%s` 已归零' % _tok[:52], _c == 0,
       'count=%d' % _c)

# 取位表的 16 个数字逐个回验
for _num in ('0.50, 0.90', '0.35, 0.75', '0.30, 0.70', '0.22, 0.60',
             '0.18, 0.55', '0.08, 0.40', '0.05, 0.35', '0.25, 0.65'):
    ck('⑤ 逐令牌回验：取位对 `(%s)` 在盘' % _num, _num in SRC)

# ---------------------------------------------------------------- ⑥ 登记一致性 + 工作区
_bj = json.loads(read(BASE))
_suites_base = set(_bj.get('suites', {}).keys())
_suites_decl = set()
for _n5 in ast.walk(_rt_tree):
    if isinstance(_n5, ast.Assign) and len(_n5.targets) == 1 \
            and isinstance(_n5.targets[0], ast.Name) and _n5.targets[0].id == 'SUITES' \
            and isinstance(_n5.value, ast.List):
        for _el in _n5.value.elts:
            if isinstance(_el, ast.Dict):
                for _k, _v in zip(_el.keys, _el.values):
                    if isinstance(_k, ast.Constant) and _k.value == 'id':
                        _suites_decl.add(_v.value)
ck('⑥ 登记：`check92` 同时在 SUITES 与 baseline 里',
   'check92' in _suites_decl and 'check92' in _suites_base,
   'decl=%s base=%s' % ('check92' in _suites_decl, 'check92' in _suites_base))
ck('⑥ 登记：SUITES 与 baseline 双向零差异（decl=%d base=%d）'
   % (len(_suites_decl), len(_suites_base)),
   _suites_decl == _suites_base,
   'only_decl=%s only_base=%s'
   % (sorted(_suites_decl - _suites_base)[:5], sorted(_suites_base - _suites_decl)[:5]))


def _git(*a):
    """★ `-c core.quotepath=false`：否则 git 会把中文路径写成 `\\347\\254\\25492...`
    的八进制转义（`"code-quality-audit/\347\254\25492..."`），下面按中文子串匹配会
    **恒假** —— 第一版就是这么误报"有临时/备份混入"的。"""
    try:
        r = subprocess.run(['git', '-c', 'core.quotepath=false'] + list(a),
                           cwd=ROOT, capture_output=True, timeout=60)
        return r.stdout.decode('utf-8', 'replace')
    except Exception as e:
        return 'ERR %s' % e


_por = [l for l in _git('status', '--porcelain').splitlines() if l.strip()]
print('  ⑥ 工作区（`git status --porcelain`）变更条目 = %d' % len(_por))
for _l in _por[:40]:
    print('     %s' % _l)
# 本轮**预期**改动（白名单）：
#   · `ralsei_pet/src/main.py`                —— 四处修复本体
#   · `regress/run_all.py` / `baseline.json`  —— 登记 + 固化 `check92`
#   · `第79轮…/_tools/check79.py`              —— 顺手修掉"输出带行号 ⇒ 每轮假 DIFF"的脆弱判据
#   · `第92轮-宠物移动结算/`（新增）            —— 本轮工具与证据
_ALLOW = ('第92轮-宠物移动结算', 'ralsei_pet/src/main.py',
          'regress/run_all.py', 'regress/baseline.json',
          '第79轮-自主生活驻留层/_tools/check79.py')
ck('⑥ 工作区：只改了本轮预期文件（无临时/备份混入）',
   all(any(a in l for a in _ALLOW) for l in _por),
   'n=%d allow=%s' % (len(_por), list(_ALLOW)))

print('=' * 74)
print('第92轮复检：PASS=%d FAIL=%d' % (_n - len(_failed), len(_failed)))
if _failed:
    print('未通过：')
    for _d in _failed:
        print('  - %s' % _d)
print('=' * 74)
sys.exit(0 if not _failed else 1)
