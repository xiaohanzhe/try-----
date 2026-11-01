# -*- coding: utf-8 -*-
"""第134轮核心文件复检（六项）。

复检对象：本轮新增/改动的三处
  1. `code-quality-audit/第134轮-训练线收口/_tools/check134.py`（新建，回归锁）
  2. `code-quality-audit/regress/run_all.py`（SUITES 追加 check134）
  3. `code-quality-audit/第134轮-训练线收口/_evidence/report134.md`（新建，报告）

★ 纪律（踩过的坑，逐条对应）：
  · 语法用 `ast.parse`，**不用** `py_compile` —— 复检本身不许改变被测状态（产 `.pyc`）。
  · 恒真判据**必须带正控制**：塞一条假 `check(..., True)` 进去，判据不报红就说明判据本身是摆设。
  · 逐令牌回验用"宽式"（`§` 可选），但**必须逐条打印**，不许只报一个总数。
  · 行尾只查"不混用"，不强制 CRLF —— 本套件是新建脚本，LF 是它的原样。
"""
import ast
import io
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))

CHECK = os.path.join(HERE, 'check134.py')
RUNALL = os.path.join(ROOT, 'code-quality-audit', 'regress', 'run_all.py')
REPORT = os.path.join(ROUND, '_evidence', 'report134.md')
MAIN_PY = os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py')
NP_PY = os.path.join(ROOT, 'ralsei_pet', 'modules', 'npc_persona.py')
IDX = os.path.join(ROOT, 'ralsei_pet', 'assets', 'npc', '_training', '_index.json')

_n = {'p': 0, 'f': 0}
_failed = []


def ok(desc, cond, extra=''):
    cond = bool(cond)
    if cond:
        _n['p'] += 1
    else:
        _n['f'] += 1
        _failed.append(desc)
    print(u'%s %s%s' % (u'[PASS]' if cond else u'[FAIL]', desc,
                        (u'  ' + extra) if extra else ''))


def head(t):
    print(u'')
    print(u'=' * 78)
    print(t)


def _read(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def _bytes(p):
    with io.open(p, 'rb') as f:
        return f.read()


# =============================================== 1 语法
head(u'1. 语法（ast.parse，不产 .pyc）')

_src_check = _read(CHECK)
_src_runall = _read(RUNALL)
try:
    _t_check = ast.parse(_src_check)
    ok(u'1.1 check134.py 可解析', True, u'%d 行' % len(_src_check.splitlines()))
except SyntaxError as e:
    _t_check = None
    ok(u'1.1 check134.py 可解析', False, repr(e))
try:
    _t_runall = ast.parse(_src_runall)
    ok(u'1.2 run_all.py 可解析', True)
except SyntaxError as e:
    _t_runall = None
    ok(u'1.2 run_all.py 可解析', False, repr(e))

_report = _read(REPORT)
ok(u'1.3 report134.md 存在且非空', len(_report) > 2000, u'%d 字节' % len(_report.encode('utf-8')))

# =============================================== 2 结构
head(u'2. 结构（段标题 / 判据 / 假结论已撤）')

for seg in ('A. 数据面', 'B. 端到端', 'C. 接线', 'D. 空人设', 'E. `Twinkly`', 'F. 本套件自检'):
    ok(u'2.1 段标题在位：%s' % seg, seg in _src_check)

_calls = [n for n in ast.walk(_t_check)
          if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
          and n.func.id == 'check']
# ★ 37 = 静态调用数；实跑 36 = 少的那一条是 `C3b` 的 if/else **两支互斥**
#   （变异能定位时走一支、不能时走 else 的 `check(..., False)`）。
#   第一版这里写 `== 36` ⇒ 报红，红的是**这条断言**（静态数 ≠ 运行数）。
ok(u'2.2 判据静态调用 37 处（C3b 两支互斥 ⇒ 实跑 36）', len(_calls) == 37,
   u'%d 处' % len(_calls))

# ★ 关键：本轮的四条"钉住 ralsei 现状"的判据必须都在
for tag in (u'B0b', u'B1b', u'B1c ', u'B1c2'):
    ok(u'2.3 判据在位：%s' % tag.strip(),
       any(isinstance(a, ast.Constant) and tag in str(a.value)
           for c in _calls for a in c.args[:1]))

# ★ 假结论不许留在报告里（断"措辞"，不断"提到某名字" —— 禁词法必然误伤）
ok(u'2.4 报告里没有把训练线写成"实测有效"',
   u'实测有效' not in _report)
ok(u'2.5 报告里明写"产品代码改动：零"', u'产品代码改动' in _report and u'零' in _report)

# =============================================== 3 编码
head(u'3. 编码（BOM / U+FFFD / 行尾不混用）')

for p in (CHECK, RUNALL, REPORT):
    b = _bytes(p)
    s = b.decode('utf-8')
    name = os.path.basename(p)
    ok(u'3.1 %s 无 BOM' % name, not b.startswith(b'\xef\xbb\xbf'))
    ok(u'3.2 %s 无 U+FFFD' % name, u'\ufffd' not in s)
    crlf = b.count(b'\r\n')
    lf = b.count(b'\n') - crlf
    ok(u'3.3 %s 行尾不混用（CRLF=%d / 裸 LF=%d）' % (name, crlf, lf),
       crlf == 0 or lf == 0)

# =============================================== 4 恒真判据 + 正控制
head(u'4. 恒真判据复查（含正控制：塞一条假的必须被抓到）')


def _find_true_calls(tree):
    """`check(desc, True)` 形状 —— 第二实参是字面量 True。"""
    out = []
    for n in ast.walk(tree):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id == 'check' and len(n.args) >= 2
                and isinstance(n.args[1], ast.Constant) and n.args[1].value is True):
            out.append(n.lineno)
    return out


ok(u'4.1 真文件里 `check(..., True)` 0 处', not _find_true_calls(_t_check),
   u'%r' % (_find_true_calls(_t_check),))

# ★ 正控制：造一份带假判据的副本，同一函数必须报出来（证明 4.1 不是恒真）
_fake = _src_check + u'\n\ncheck(u\'假的恒真判据\', True)\n'
try:
    _fake_true = _find_true_calls(ast.parse(_fake))
    ok(u'4.2 正控制：塞一条 `check(..., True)` 必须被抓到', len(_fake_true) == 1,
       u'%r' % (_fake_true,))
except SyntaxError as e:
    ok(u'4.2 正控制：塞一条 `check(..., True)` 必须被抓到', False, repr(e))

# ★ 反向：本轮修掉的那条（`nid not in REL`）不许回来
ok(u'4.3 自查修过的那条没回退（`nid not in REL` 不再出现）',
   u'nid not in REL and' not in _src_check and u'nid not in REL:' not in _src_check)

# ★ 每条负控制都要打印分母：B4/B5 的 desc 里必须带 `%d`
ok(u'4.4 B4/B5 的分母进 desc（负控制不许"空集里没有"）',
   u'无 patch 的 %d 个角色' in _src_check and u'无 relation 的 %d 个角色' in _src_check)

# =============================================== 5 逐令牌回验
head(u'5. 逐令牌回验（每条回原文件 `in` 一次，不只看总数）')

_idx_src = _read(IDX)
_main_src = _read(MAIN_PY)
_np_src = _read(NP_PY)

_pairs = [
    (u'59', u'"patches"', _idx_src),
    (u'"counts"', u'96', _idx_src),
    (u'"persona": 77', u'77', _idx_src),
    (u'"gap": 1', u'1', _idx_src),
    (u'gaps', u'knight', _idx_src),
]
for a, b, src in _pairs:
    ok(u'5.1 索引里 %r 与 %r 都在' % (a, b), a in src and b in src)

ok(u'5.2 `main.py` 里 `patch=npc_persona_mod.training_patch(` 真在',
   u'patch=npc_persona_mod.training_patch(' in _main_src)
ok(u'5.3 `main.py` 里 `speaker != \'ralsei\'` 真在（B1c 的依据）',
   u"speaker != 'ralsei'" in _main_src)
ok(u'5.4 `npc_persona.py` 里 `self.npc_personas` 的真源是 `load_personas`（不在这个文件）',
   u'def load_personas' in _np_src and u'def build_system_prompt' in _np_src)
ok(u'5.5 报告里引用的 6387 / 133 两个数与 G2 一致',
   u'6387' in _report and u'133' in _report)

# ★ 负控制：编造的令牌必须判"不在"（证明 5.1 那组不是恒真）
#   第一版写 `'37'` —— 索引里有的是数字，这条负控制**自己选错了样本**（与 §133 D2 同型）。
for fake in (u'"patches__nonexistent"', u'zzz_not_in_index', u'zzz_37_not_here'):
    ok(u'5.6 负控制：编造的令牌 %r 必须判不在' % fake,
       fake not in _idx_src)

# =============================================== 6 工作区
head(u'6. 本轮只动该动的路径')

_ev = os.path.join(ROUND, '_evidence', 'train134.json')
ok(u'6.1 证据文件落盘', os.path.isfile(_ev), _ev)
ok(u'6.2 本套件所有读取路径都在仓库内（零外部盘）',
   all(os.path.abspath(p).startswith(ROOT + os.sep)
       for p in (CHECK, RUNALL, REPORT, MAIN_PY, NP_PY, IDX, _ev)))

# =============================================== 落盘
_txt = [u'[PASS]', u'[FAIL]']
print(u'')
print(u'=' * 78)
print(u'recheck134_core：PASS=%d FAIL=%d' % (_n['p'], _n['f']))
if _failed:
    print(u'失败项：')
    for d in _failed:
        print(u'  - %s' % d)
sys.exit(0 if _n['f'] == 0 else 1)
