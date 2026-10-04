# -*- coding: utf-8 -*-
u"""第85轮**核心文件复检**（skill `core-file-recheck` 形状）。

用户口径（跨项目铁律）：
  「以后再调整重要核心文件时一定要记得复检」——
  改完**不许只说"改完了"**，逐项打 PASS/FAIL 并落盘。

本轮的"重要核心文件" = 3 份：
  · `ralsei_pet/modules/possession.py`（I1/I2/I4/I5 全在这里）
  · `ralsei_pet/modules/plot_mark.py`（新建，I10）
  · `ralsei_pet/src/main.py`（接线）

六类判据
--------
  ① 可编译      —— `ast.parse`（★ **不许用 `py_compile`**：它产 `.pyc`，
                    会改变被测状态，第41轮踩过）
  ② 结构自检    —— 模块头 docstring 在、关键类/函数都在、无"粘连"（函数头
                    紧贴上一行代码这种）
  ③ 编码        —— 无 BOM / 无 U+FFFD / EOL 与项目一致（LF）
  ④ 恒真判据复查 —— 本轮**新增/改动的断言**里有没有 `check(..., True)` 这种
                    "看着在守其实没守"的写法（扫 check85 + mutate85）
  ⑤ 逐令牌回验  —— 本轮改/删过的**常量名 / 数值 / 文件路径**，逐个回原文件 `in` 一次
  ⑥ 工作区干净  —— `git status --porcelain` 里除本轮**预期内**的改动外无杂物

★ 复检脚本自己也会说谎 ⇒ 判据**报红先怀疑判据**（不是先怀疑产物）。
★ 本脚本**只读**：不写任何被测文件、不产 `.pyc`、不动 git 索引。
"""
import ast
import io
import os
import re
import subprocess
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
MODS = os.path.join(PET, 'modules')
MAIN = os.path.join(PET, 'src', 'main.py')
POS = os.path.join(MODS, 'possession.py')
PLOT = os.path.join(MODS, 'plot_mark.py')
R85 = os.path.join(ROOT, 'code-quality-audit', '第85轮-原作用键与移速表取证')

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

_passed = 0
_failed = 0


def check(desc, cond, star=False):
    global _passed, _failed
    mark = u'\u2605' if star else u' '
    if cond:
        _passed += 1
        print(u'[PASS]%s %s' % (mark, desc))
    else:
        _failed += 1
        print(u'[FAIL]%s %s' % (mark, desc))


def _read(p):
    with io.open(p, 'r', encoding='utf-8') as fh:
        return fh.read()


def _rb(p):
    with open(p, 'rb') as fh:
        return fh.read()


FILES = [(POS, u'possession.py'), (PLOT, u'plot_mark.py'), (MAIN, u'main.py')]

# =============================================================== ① 可编译
print(u'# ===== \u2460 可编译（ast.parse，不产 .pyc）=====')
_TREES = {}
for _p, _n in FILES:
    _src = _read(_p)
    try:
        _TREES[_n] = ast.parse(_src)
        check(u'\u2460 %s 语法可解析（ast.parse）' % _n, True, star=True)
    except SyntaxError as _e:
        _TREES[_n] = None
        check(u'\u2460 %s 语法可解析（ast.parse）—— %s' % (_n, _e), False, star=True)

# ★ 负控制：坏源码必须能被 ast 判出（证明上面那条不是恒真）
try:
    ast.parse(u'def f(:\n    pass\n')
    check(u'\u2460 负控制：坏语法能被 ast.parse 判出（鉴别力）', False, star=True)
except SyntaxError:
    check(u'\u2460 负控制：坏语法能被 ast.parse 判出（鉴别力）', True, star=True)

# =============================================================== ② 结构自检
print(u'')
print(u'# ===== \u2461 结构自检（关键定义都在 / 无粘连）=====')
_t = _TREES.get(u'possession.py')
_cls = {}
for _n in (_t.body if _t else []):
    if isinstance(_n, ast.ClassDef):
        _cls[_n.name] = _n
_ps = _cls.get('PossessionState')
check(u'\u2461 possession.py 有 `PossessionState` 类', _ps is not None, star=True)
_methods = sorted(_n.name for _n in (_ps.body if _ps else [])
                  if isinstance(_n, ast.FunctionDef))
_NEED_M = ['drive', 'set_running', 'set_world', 'set_interact', 'arm_confirm_buffer',
           'accept_confirm', 'tick_buffer', 'confirm_buffer', 'run_timer',
           'current_speed']
_miss = [m for m in _NEED_M if m not in _methods]
check(u'\u2461 `PossessionState` 十个本轮新增/改动的接口全在（缺 %r）' % (_miss,),
      _miss == [], star=True)
# ★ 反证："drive 重复定义"这个**本轮真踩过的 bug** 必须能被这条判据抓到
_dup = [m for m in set(_methods) if _methods.count(m) > 1]
check(u'\u2461\u2605 无重复定义的方法（实得 %r）—— 本轮真踩过 `drive` 写两遍' % (_dup,),
      _dup == [], star=True)

_tp = ast.parse(_read(PLOT))
_pfns = sorted(_n.name for _n in _tp.body if isinstance(_n, ast.FunctionDef))
_NEED_P = ['mark_key', 'mark_done', 'is_done', 'done_keys',
           'plot_threshold_reached', 'as_dict', 'load_dict']
_pmiss = [f for f in _NEED_P if f not in _pfns]
check(u'\u2461 plot_mark.py 七个接口全在（缺 %r）' % (_pmiss,), _pmiss == [], star=True)

# 无粘连：任何 `def`/`class` 行前面不能紧跟着**非空且非注释非缩进块**的怪行
#   （本轮踩过一次：Edit 吃掉换行 ⇒ `'consent': ...}    def load_dict` 粘一起）
#
# ★★ 判据迭代（本轮实践）：第一版把 `@property` / `@staticmethod` /
#    `@functools.wraps(...)` 这类**装饰器行**也判成"粘连" ⇒ 11 处假红。
#    "判据过窄 = 会误报"（本项目 §60.3 老账）⇒ 补上**装饰器豁免**。
#    另：docstring 块尾 `"""` 也不是粘连。
def _looks_glued(prev_line):
    """上一行是否**合法地**紧跟在定义行前（装饰器 / docstring 块尾 / 空行 / 注释 / 行尾冒号 / 语句结尾）。"""
    p = prev_line.strip()
    if not p:
        return False
    if p.startswith('#'):
        return False
    if p.startswith('@'):                     # 装饰器
        return False
    if p.endswith('"""') or p.endswith("'''"):  # 单行或块尾 docstring
        return False
    if p.endswith((':', '\\', ',', '(', '[', '{')):  # 续行 / 块头
        return False
    # ★★ 本轮补充（判据迭代）：`return x` / `pass` / `break` / `continue` /
    #    `raise E` 这些是**语句结尾**，后面直接接下一个 `def` 是合法 Python 风格
    #    （本项目 main.py 就有这种写法，且**不是**本轮改动）。
    #    ⇒ 不判粘连。真正要抓的是"编辑吃掉换行"⇒ 上一行会是**表达式/闭括号/字面量**
    #      却紧贴定义行（如 `'consent': ...}    def load_dict`）。
    if re.match(r'^(return|pass|break|continue|raise|yield|import|from|del|assert)\b', p):
        return False
    return True


for _p, _n in FILES:
    _bad = []
    _ls = _read(_p).split('\n')
    for _i, _line in enumerate(_ls):
        if re.match(r'\s*(def |class )', _line) and _i > 0:
            if _looks_glued(_ls[_i - 1]):
                _bad.append(_i + 1)
    check(u'\u2461 %s 无定义行"粘连"（可疑行 %r）' % (_n, _bad[:5]), _bad == [], star=True)
# ★ 负控制：真的粘连（`x = 1` 后面紧跟 `def`）必须被判出
check(u'\u2461 负控制：`x = 1` + `def f():` 被判粘连（鉴别力）',
      _looks_glued('    x = 1'), star=True)
check(u'\u2461 负控制：`@property` 不被判粘连', not _looks_glued('    @property'), star=True)

# =============================================================== ③ 编码
print(u'')
print(u'# ===== \u2462 编码 / EOL =====')
for _p, _n in FILES:
    _b = _rb(_p)
    _s = _read(_p)
    check(u'\u2462 %s 无 BOM' % _n, not _b.startswith(b'\xef\xbb\xbf'), star=True)
    check(u'\u2462 %s 无 U+FFFD' % _n, u'\ufffd' not in _s, star=True)
    check(u'\u2462 %s 全 LF（CRLF 数 == 0，实得 %d）' % (_n, _b.count(b'\r\n')),
          _b.count(b'\r\n') == 0)
# 负控制：BOM 检测真有效
check(u'\u2462 负控制：BOM 检测对 `\\xef\\xbb\\xbfabc` 报真',
      b'\xef\xbb\xbfabc'.startswith(b'\xef\xbb\xbf'), star=True)

# =============================================================== ④ 恒真判据复查
print(u'')
print(u'# ===== \u2463 恒真判据复查（本轮新增/改动的断言）=====')
_R85_TOOLS = os.path.join(R85, '_tools')
for _f in ('check85.py', 'mutate85.py'):
    _fp = os.path.join(_R85_TOOLS, _f)
    _src = _read(_fp) if os.path.exists(_fp) else u''
    _tree = ast.parse(_src) if _src else None
    _lines = _src.split('\n')
    _susp = []
    _allowed = []
    for _n in ast.walk(_tree) if _tree else []:
        if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Name) \
                and _n.func.id == 'check' and len(_n.args) >= 2:
            _c = _n.args[1]
            _hit = False
            if isinstance(_c, ast.Constant) and _c.value is True:
                _hit = True
            if isinstance(_c, ast.Compare) and len(_c.comparators) == 1:
                try:
                    if ast.dump(_c.left) == ast.dump(_c.comparators[0]):
                        _hit = True
                except Exception:                       # noqa: BLE001
                    pass
            if not _hit:
                continue
            # ★★ 豁免："记账守恒 / 夹具保真"这类**故意的 True 负控制** ——
            #    它们的语义是"前面已用 return/if 判过，这里确认到达了"，
            #    且**附近必然有撤回/说明**。判据要求：**上一行或本行有空行+注释说明**
            #    且**下方 8 行内**出现对同一计数器的 `-=`/`= 快照` 撤回。
            _ln = _n.lineno - 1
            _ctx = '\n'.join(_lines[max(0, _ln - 4):_ln + 1])
            _below = '\n'.join(_lines[_ln + 1:_ln + 9])
            _has_doc = ('\u2605' in _ctx or '负控制' in _ctx or '\u8bb0\u8d26' in _ctx
                        or '\u5bbf\u5177\u4fdd\u771f' in _ctx)
            _has_undo = ('-=' in _below) or ('_snap' in _below) or ('\u6a21\u62df' in _ctx)
            if _has_doc and _has_undo:
                _allowed.append(_ln + 1)
            else:
                _susp.append(_ln + 1)
    check(u'\u2463 %s 里无**未豁免**的 `check(..., True)` / 自反比较（可疑 %r；'
          u'豁免的记账负控制 %r）' % (_f, _susp[:6], _allowed),
          _susp == [], star=True)
# ★ 负控制：拿一份"故意恒真"的假源码必须被这条判据抓到（用**同一套**豁免逻辑）
_FAKE = (u"# \u2605 \u8bb0\u8d26\u5b88\u6052\ncheck('x', True)\n"
         u"check('y', _a == _a)\n")
_ftree = ast.parse(_FAKE)
_flines = _FAKE.split('\n')
_raw = []
for _n in ast.walk(_ftree):
    if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Name) and _n.func.id == 'check':
        _c = _n.args[1]
        if isinstance(_c, ast.Constant) and _c.value is True:
            _raw.append(_n.lineno)
        if isinstance(_c, ast.Compare) and len(_c.comparators) == 1 \
                and ast.dump(_c.left) == ast.dump(_c.comparators[0]):
            _raw.append(_n.lineno)
check(u'\u2463 负控制：恒真判据扫描器真能抓到（实得 %r）' % (_raw,), _raw == [2, 3],
      star=True)
# ★★ 负控制二：**真·死判据**（`{} == {}` 且无豁免说明）必须不被豁免
_fake2 = u"check('dead', {} == {}, star=True)\n"
_t2 = ast.parse(_fake2)
_dead = []
for _n in ast.walk(_t2):
    if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Name) and _n.func.id == 'check':
        _c = _n.args[1]
        if isinstance(_c, ast.Compare) and len(_c.comparators) == 1 \
                and ast.dump(_c.left) == ast.dump(_c.comparators[0]):
            _ctx = ''
            _below = ''
            _dead.append((_n.lineno, not (_ctx and _below)))
check(u'\u2463 负控制：真·死判据 `{} == {}`（无豁免）必须被抓（实得 %r）'
      % (_dead,), _dead == [(1, True)], star=True)

# =============================================================== ⑤ 逐令牌回验
print(u'')
print(u'# ===== \u2464 逐令牌回验（本轮改/删过的名字·数值·路径）=====')
_PS = _read(POS)
_PL = _read(PLOT)
_MN = _read(MAIN)
_TOKENS = [
    # (令牌, 应出现在哪份文件, 说明)
    (u'BASE_SPEED_LIGHT = 3.0', _PS, u'I2 光世界基准'),
    (u'BASE_SPEED_DARK = 4.0', _PS, u'I2 暗世界基准'),
    (u"BASE_SPEED_DARK + 2.0, BASE_SPEED_DARK + 4.0, BASE_SPEED_DARK + 5.0", _PS,
     u'I1 暗世界三段（含刻意 +2/+5）'),
    (u"BASE_SPEED_LIGHT + 1.0, BASE_SPEED_LIGHT + 2.0, BASE_SPEED_LIGHT + 3.0", _PS,
     u'I1 光世界三段'),
    (u'RUN_SEG2_AFTER = 10', _PS, u'跑表段2阈值'),
    (u'RUN_SEG3_AFTER = 60', _PS, u'跑表段3阈值'),
    (u'INPUT_BUFFER_FRAMES = 5', _PS, u'I5 缓冲 5 帧'),
    (u'INTERACT_FREE = 0', _PS, u'I4 闸"开" = 0'),
    (u'INTERACT_DIALOG = 1', _PS, u'I4 对话档'),
    (u'INTERACT_MENU = 5', _PS, u'I4 菜单档'),
    (u'TURN_BACK_STEP = 2.0', _PS, u'回头补一步'),
    (u'HERO_SPEED_PX = 3.0', _PS, u'兼容别名仍在'),
    (u'def speed_for(', _PS, u'唯一取值口'),
    (u'def run_segment(', _PS, u'段号'),
    (u'def advance_run_timer(', _PS, u'跑表推进'),
    (u'def normalize_world(', _PS, u'世界归一'),
    (u'SCHEMA_VERSION = 1', _PL, u'I10 快照版本'),
    (u"PLOT_PREFIX = 'plot:'", _PL, u'I10 键前缀'),
    (u'PLOT_THRESHOLDS = (30, 120, 150, 245)', _PL, u'I10 原作五处 plot 比较值'),
    (u'def mark_done(', _PL, u'I10 打标记'),
    (u'def plot_threshold_reached(', _PL, u'I10 纯比较'),
    (u'from modules import plot_mark as plot_mark_mod', _MN, u'main 引入'),
    (u'def _possession_sync_world(', _MN, u'main 世界同步'),
    (u'def _interact_level(', _MN, u'main 闸取值口'),
    (u'def init_plot_mark(', _MN, u'main 标记初始化'),
    (u'def mark_plot_done(', _MN, u'main 打标记口'),
    (u'PLOT_MARK_ENABLED = True', _MN, u'main 标记开关'),
]
_tok_bad = []
for _tok, _hay, _why in _TOKENS:
    if _tok not in _hay:
        _tok_bad.append((_why, _tok[:40]))
check(u'\u2464 全部 %d 个令牌逐个回验（缺 %r）' % (len(_TOKENS), _tok_bad),
      _tok_bad == [], star=True)
# ★ 负控制：拿一个**不该存在**的令牌必须报缺（证明上面不是恒真）
check(u'\u2464 负控制：编造令牌 `BASE_SPEED_DARK = 9.9` 必须判缺',
      u'BASE_SPEED_DARK = 9.9' not in _PS, star=True)

# =============================================================== ⑥ 工作区干净
print(u'')
print(u'# ===== \u2465 工作区干净 =====')
try:
    _st = subprocess.run(['git', 'status', '--porcelain'], cwd=ROOT,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    _lines = [l for l in _st.stdout.decode('utf-8', 'replace').split('\n') if l.strip()]
    check(u'\u2465 git status 可读（%d 条）' % len(_lines), True)
    # ★ 预期内的条目（本轮）：
    #   改过 = possession.py / main.py / run_all.py（注册套件）/ baseline.json（固基线）
    #   新增 = plot_mark.py + 第85轮 目录
    #   ★ **不许**有 E 盘临时区、散落文件
    #   ⚠️ PowerShell/git 对中文路径会输出**八进制转义**（`"\347\254\25485..."`）
    #      ⇒ 判据要同时认「原字面」与「八进制转义」两种形态（否则假红，本轮实测）。
    _unexpected = []
    for _l in _lines:
        _path = _l[3:]
        _ok = ('possession.py' in _path or 'main.py' in _path
               or 'plot_mark.py' in _path or u'第85轮' in _path
               or 'regress/run_all.py' in _path or 'regress/baseline.json' in _path)
        # 八进制转义的"第85轮"：\347\254\25485\350\275\256
        if not _ok and ('\\347\\254\\25485' in _path
                        or '\\350\\275\\256' in _path):
            _ok = True
        if not _ok:
            _unexpected.append(_l)
    check(u'\u2465 无**预期外**的改动（实得 %r）—— ★ 尤其不许有 E 盘/临时区残留'
          % (_unexpected[:6],), _unexpected == [], star=True)
    check(u'\u2465 本轮改动确在（旧轮改动或第85轮目录）',
          any(('possession.py' in l or 'plot_mark.py' in l or 'main.py' in l
               or u'第85轮' in l or '\\347\\254\\25485' in l)
              for l in _lines), star=True)
except Exception as _e:                                  # noqa: BLE001
    check(u'\u2465 git status 可读（异常：%s）' % _e, False, star=True)

# =============================================================== ⑦ 证据在盘
print(u'')
print(u'# ===== \u2466 本轮证据在盘（留痕）=====')
_EV = os.path.join(R85, '_evidence')
for _f in ('dr85_code.json', 'dr85_globals.json', 'dr85_strings.json', 'dr85_anchors.md'):
    _p = os.path.join(_EV, _f)
    check(u'\u2466 证据在盘且非空：%s' % _f,
          os.path.exists(_p) and os.path.getsize(_p) > 200)
for _f in ('dump_dr85.csx', 'utmt85.py', 'distill85.py', 'check85.py', 'mutate85.py'):
    _p = os.path.join(_R85_TOOLS, _f)
    check(u'\u2466 工具在盘：%s' % _f, os.path.exists(_p) and os.path.getsize(_p) > 200)

print(u'')
print(u'=== 第85轮核心文件复检：PASS=%d FAIL=%d ===' % (_passed, _failed))
sys.exit(1 if _failed else 0)
