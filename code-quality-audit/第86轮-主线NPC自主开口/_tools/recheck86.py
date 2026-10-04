# -*- coding: utf-8 -*-
u"""第86轮**核心文件复检**（skill `core-file-recheck` 形状）。

用户口径（跨项目铁律）：
  「以后再调整重要核心文件时一定要记得复检」——
  改完**不许只说"改完了"**，逐项打 PASS/FAIL 并落盘。

本轮的"重要核心文件" = 2 份：
  · `ralsei_pet/modules/npc_life.py`（新增 `where_of` / `presence_hint`；修纯竖直档）
  · `ralsei_pet/src/main.py`（主线自主开口接线）

六类判据
--------
  ① 可编译      —— `ast.parse`（★ **不许用 `py_compile`**：它产 `.pyc`，
                    会改变被测状态，第41轮踩过）
  ② 结构自检    —— 关键定义都在、无"粘连"、★ **无重复方法定义**（本项目踩过多次）
  ③ 编码        —— 无 BOM / 无 U+FFFD / EOL 与项目一致（LF）
  ④ 恒真判据复查 —— 本轮**新增/改动的断言**里有没有 `check(..., True)` 这种
                    "看着在守其实没守"的写法（扫 check86 + mutate86）
  ⑤ 逐令牌回验  —— 本轮改/删过的**常量名 / 数值 / 判据关键词**，逐个回原文件 `in` 一次
  ⑥ 工作区干净  —— `git status --porcelain` 里除本轮**预期内**的改动外无杂物

★ 复检脚本自己也会说谎 ⇒ 判据**报红先怀疑判据**（不是先怀疑产物）。
  第85轮实测：⑥ 原判据要求"三份文件同时改" = 按**未提交工作区**判 ⇒ **过窄**，
  本轮直接写成"**任一**在本轮改动或第86轮目录里"。
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
NLP = os.path.join(MODS, 'npc_life.py')
R86 = os.path.join(ROOT, 'code-quality-audit', u'\u7b2c86\u8f6e-\u4e3b\u7ebfNPC\u81ea\u4e3b\u5f00\u53e3')

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


FILES = [(NLP, u'npc_life.py'), (MAIN, u'main.py')]

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
print(u'# ===== \u2461 结构自检（关键定义都在 / 无粘连 / 无重复方法）=====')
_tn = _TREES.get(u'npc_life.py')
_nbody = _tn.body if _tn else []
_nfs = sorted(_n.name for _n in _nbody
              if isinstance(_n, (ast.FunctionDef, ast.AsyncFunctionDef)))
# ★ 判据迭代（本轮踩的坑）：`familiarity_of` / `meet` 不是**顶层函数**，
#   而是 `Bonds` 类的方法 ⇒ 顶层名列表里当然找不到（判据侧错，不是产物错）。
#   ⇒ 顶层按**实际**接口列；类方法另查。
_NEED_N = ['where_of', 'presence_hint', 'trait_hint', 'transmit', 'pick_line',
           'pair_key', 'scene_traits', 'trait_hits', 'banned_tokens']
_nmiss = [f for f in _NEED_N if f not in _nfs]
check(u'\u2461 npc_life.py 九个本轮相关**顶层**接口全在（缺 %r）' % (_nmiss,),
      _nmiss == [], star=True)
_ncls = {c.name: c for c in _nbody if isinstance(c, ast.ClassDef)}
check(u'\u2461 npc_life.py 有 `Bonds` / `LifeLoop` 两个类',
      'Bonds' in _ncls and 'LifeLoop' in _ncls, star=True)
_bond_m = sorted(_n.name for _n in _ncls.get('Bonds', ast.ClassDef()).body
                 if isinstance(_n, (ast.FunctionDef, ast.AsyncFunctionDef)))
_bmiss = [m for m in ('meet', 'tick', 'to_dict', 'from_dict') if m not in _bond_m]
check(u'\u2461 `Bonds` 有 meet/tick/存盘四接口（缺 %r）' % (_bmiss,), _bmiss == [],
      star=True)
_ndup = [m for m in set(_nfs) if _nfs.count(m) > 1]
check(u'\u2461 npc_life.py 顶层无重复定义函数（实得 %r）' % (_ndup,), _ndup == [],
      star=True)
check(u'\u2461 npc_life.py 有 `LifeLoop` 类',
      any(isinstance(_n, ast.ClassDef) and _n.name == 'LifeLoop'
          for _n in (_tn.body if _tn else [])), star=True)

_tm = _TREES.get(u'main.py')
_mcls = {}
for _n in (_tm.body if _tm else []):
    if isinstance(_n, ast.ClassDef):
        _mcls[_n.name] = _n
_pet = _mcls.get('RalseiPet')
check(u'\u2461 main.py 有 `RalseiPet` 类', _pet is not None, star=True)
_mmethods = [_n.name for _n in (_pet.body if _pet else [])
             if isinstance(_n, (ast.FunctionDef, ast.AsyncFunctionDef))]
_NEED_M = ['_npc_life_tick', '_npc_life_speak_plain', '_npc_life_speak_main',
           '_npc_main_ids', '_npc_plain_ids', '_npc_life_gate',
           '_npc_life_blocks', '_npc_display_label', '_npc_relative_positions',
           '_npc_body_center']
_mmiss = [m for m in _NEED_M if m not in _mmethods]
check(u'\u2461 `RalseiPet` 十个本轮相关方法全在（缺 %r）' % (_mmiss,),
      _mmiss == [], star=True)
# ★★★ 无重复定义 —— 本项目踩过多次（同一方法名写两遍 ⇒ 后者静默覆盖前者）
_mdup = sorted(m for m in set(_mmethods) if _mmethods.count(m) > 1)
check(u'\u2461\u2605 `RalseiPet` 无重复定义的方法（实得 %r）' % (_mdup,),
      _mdup == [], star=True)
# ★ 负控制：重复定义必须能被抓到
_fake_dup = u'class X:\n    def a(self): pass\n    def a(self): pass\n'
_ft = ast.parse(_fake_dup)
_fm = [_n.name for _c in _ft.body if isinstance(_c, ast.ClassDef)
       for _n in _c.body if isinstance(_n, ast.FunctionDef)]
check(u'\u2461 负控制：重复方法名能被本判据抓到（实得 %r）'
      % ([m for m in set(_fm) if _fm.count(m) > 1],),
      [m for m in set(_fm) if _fm.count(m) > 1] == ['a'], star=True)

# 无粘连（本轮踩过：Edit 吞换行 ⇒ 两行粘一起）
def _looks_glued(prev_line):
    p = prev_line.strip()
    if not p or p.startswith('#') or p.startswith('@'):
        return False
    if p.endswith('"""') or p.endswith("'''"):
        return False
    if p.endswith((':', '\\', ',', '(', '[', '{')):
        return False
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
    check(u'\u2461 %s 无定义行"粘连"（可疑行 %r）' % (_n, _bad[:5]), _bad == [],
          star=True)
check(u'\u2461 负控制：`x = 1` + `def f():` 被判粘连（鉴别力）',
      _looks_glued('    x = 1'), star=True)
check(u'\u2461 负控制：`@property` 不被判粘连', not _looks_glued('    @property'),
      star=True)

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
check(u'\u2462 负控制：BOM 检测对 `\\xef\\xbb\\xbfabc` 报真',
      b'\xef\xbb\xbfabc'.startswith(b'\xef\xbb\xbf'), star=True)

# =============================================================== ④ 恒真判据复查
print(u'')
print(u'# ===== \u2463 恒真判据复查（本轮新增/改动的断言）=====')
_R86_TOOLS = os.path.join(R86, '_tools')
for _f in ('check86.py', 'mutate86.py'):
    _fp = os.path.join(_R86_TOOLS, _f)
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
            _ln = _n.lineno - 1
            _ctx = '\n'.join(_lines[max(0, _ln - 5):_ln + 1])
            _below = '\n'.join(_lines[_ln + 1:_ln + 9])
            _has_doc = (u'\u2605' in _ctx or u'负控制' in _ctx or u'记账' in _ctx
                        or u'夹具保真' in _ctx)
            _has_undo = ('-=' in _below) or ('_snap' in _below) or (u'模拟' in _ctx)
            if _has_doc and _has_undo:
                _allowed.append(_ln + 1)
            else:
                _susp.append(_ln + 1)
    check(u'\u2463 %s 里无**未豁免**的 `check(..., True)` / 自反比较（可疑 %r；'
          u'豁免 %r）' % (_f, _susp[:6], _allowed), _susp == [], star=True)
# ★ 负控制：拿一份"故意恒真"的假源码必须被这条判据抓到（用**同一套**豁免逻辑）
_FAKE = (u"check('x', True)\ncheck('y', _a == _a)\n")
_ftree = ast.parse(_FAKE)
_raw = []
for _n in ast.walk(_ftree):
    if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Name) and _n.func.id == 'check':
        _c = _n.args[1]
        if isinstance(_c, ast.Constant) and _c.value is True:
            _raw.append(_n.lineno)
        if isinstance(_c, ast.Compare) and len(_c.comparators) == 1 \
                and ast.dump(_c.left) == ast.dump(_c.comparators[0]):
            _raw.append(_n.lineno)
check(u'\u2463 负控制：恒真判据扫描器真能抓到（实得 %r）' % (_raw,), _raw == [1, 2],
      star=True)

# =============================================================== ⑤ 逐令牌回验
print(u'')
print(u'# ===== \u2464 逐令牌回验（本轮改/删过的名字·数值·关键词）=====')
_NL = _read(NLP)
_MN = _read(MAIN)
_CR = _read(os.path.join(_R86_TOOLS, 'check86.py'))
_MR = _read(os.path.join(_R86_TOOLS, 'mutate86.py'))
_TOKENS = [
    # npc_life.py
    (u'HORIZ_RATIO = 0.5', _NL, u'纯竖直阈值常量'),
    (u"if ax < (ay * HORIZ_RATIO):", _NL, u'纯竖直分支'),
    (u"return 'same'", _NL, u'零位移档'),
    (u"return 'near'", _NL, u'近处档'),
    (u'def where_of(dx, dy=0.0, near_px=120.0)', _NL, u'where_of 签名'),
    (u'def presence_hint(speaker_id, others, positions=None, near_px=120.0,', _NL,
     u'presence_hint 签名'),
    (u"_WHERE_CN = {", _NL, u'方位词表'),
    (u'MAX_CONSECUTIVE_FAILURES', _NL, u'反活锁常量'),
    (u'def tick(self, now, ids)', _NL, u'LifeLoop.tick 签名'),
    (u'def __init__(self, min_gap=DEFAULT_MIN_GAP, max_turns=DEFAULT_MAX_TURNS,', _NL,
     u'LifeLoop 构造签名（判据侧踩过）'),
    # main.py
    (u'NPC_MAIN_TALK_GAP = 180.0', _MN, u'主线限流'),
    (u'self._npc_main_last = 0.0', _MN, u'主线上次开口状态'),
    (u'def _npc_main_ids(self, ids):', _MN, u'主线准入'),
    (u'def _npc_life_speak_main(self, loop, ids, now):', _MN, u'主线开口'),
    (u'def _npc_life_speak_plain(self, loop, speaker, ids, now):', _MN, u'纯 NPC 开口'),
    (u'def _npc_display_label(self, npc_id):', _MN, u'显示名（防泄露）'),
    (u'def _npc_relative_positions(', _MN, u'相对位置'),
    (u'def _npc_body_center(self, npc_id):', _MN, u'身体中心'),
    (u'gate=self._npc_life_gate)', _MN, u'闸注入 loop'),
    (u'life=self._npc_life_blocks(npc_id)', _MN, u'life 进 system'),
    (u'presence_hint(', _MN, u'接线到在场者感知'),
    # 判据关键词（必须与 check86 判据串一致，否则 mutate86 归因失效）
    (u'\u7eaf\u7ad6\u76f4', _CR, u'mutate 归因词「纯竖直」'),
    (u'\u8bf4\u8bdd\u8005', _CR, u'mutate 归因词「说话者」'),
    (u'\u65e0\u522b\u4eba', _CR, u'mutate 归因词「无别人」'),
    (u'npc_speak', _CR, u'mutate 归因词「npc_speak」'),
    (u'abort', _CR, u'mutate 归因词「abort」'),
    (u'\u4eba\u8bbe', _CR, u'mutate 归因词「人设」'),
    (u'\u6a21\u578b\u53ef\u7528', _CR, u'mutate 归因词「模型可用」'),
    (u'\u6ce8\u5165\u5230 loop', _CR, u'mutate 归因词「注入到 loop」'),
    (u'build_system_prompt', _CR, u'mutate 归因词'),
    (u'HORIZ_RATIO', _MR, u'mutate 破坏串用 HORIZ_RATIO'),
]
_tok_bad = []
for _tok, _hay, _why in _TOKENS:
    if _tok not in _hay:
        _tok_bad.append((_why, _tok[:40]))
check(u'\u2464 全部 %d 个令牌逐个回验（缺 %r）' % (len(_TOKENS), _tok_bad),
      _tok_bad == [], star=True)
# ★ 负控制：拿一个**不该存在**的令牌必须报缺（证明上面不是恒真）
check(u'\u2464 负控制：编造令牌 `NPC_MAIN_TALK_GAP = 9.9` 必须判缺',
      u'NPC_MAIN_TALK_GAP = 9.9' not in _MN, star=True)

# =============================================================== ⑥ 工作区干净
print(u'')
print(u'# ===== \u2465 工作区干净 =====')
try:
    _st = subprocess.run(['git', 'status', '--porcelain'], cwd=ROOT,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    _lines = [l for l in _st.stdout.decode('utf-8', 'replace').split('\n') if l.strip()]
    check(u'\u2465 git status 可读（%d 条）' % len(_lines), True)
    _unexpected = []
    for _l in _lines:
        _path = _l[3:]
        _ok = ('npc_life.py' in _path or 'main.py' in _path
               or u'\u7b2c86\u8f6e' in _path
               or 'regress/run_all.py' in _path or 'regress/baseline.json' in _path
               or '_crossworld.json' in _path)
        if not _ok and ('\\347\\254\\25486' in _path or '\\350\\275\\256' in _path):
            _ok = True
        if not _ok:
            _unexpected.append(_l)
    check(u'\u2465 无**预期外**的改动（实得 %r）—— ★ 尤其不许有 E 盘/临时区残留'
          % (_unexpected[:6],), _unexpected == [], star=True)
    # ★ 判据迭代（第85轮踩的坑）：原版要求"三份文件**同时**改" ⇒ 按未提交工作区判
    #   ⇒ 过窄。这里改成"**任一**在本轮改动或第86轮目录里"。
    check(u'\u2465 本轮改动确在（npc_life.py / main.py 或第86轮目录）',
          any(('npc_life.py' in l or 'main.py' in l
               or u'\u7b2c86\u8f6e' in l or '\\347\\254\\25486' in l)
              for l in _lines), star=True)
except Exception as _e:                                  # noqa: BLE001
    check(u'\u2465 git status 可读（异常：%s）' % _e, False, star=True)

# =============================================================== ⑦ 工具在盘
print(u'')
print(u'# ===== \u2466 本轮工具在盘（留痕）=====')
for _f in ('check86.py', 'mutate86.py', 'recheck86.py'):
    check(u'\u2466 工具在盘：%s' % _f,
          os.path.exists(os.path.join(_R86_TOOLS, _f)), star=('check86' in _f))

print()
print(u'=== 第86轮核心文件复检：PASS=%d FAIL=%d ===' % (_passed, _failed))
sys.exit(0 if _failed == 0 else 1)
