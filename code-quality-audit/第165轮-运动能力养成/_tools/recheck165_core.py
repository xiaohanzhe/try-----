# -*- coding: utf-8 -*-
u"""第165轮 · 核心文件复检（`recheck165_core`）。

## 为什么每个"动过核心文件"的轮次都要单独跑这一遍

`check165` 全绿只说明"我写的那些判据没红"，**不说明我改过的文件本身是干净的**：
语法被改坏（`ast.parse` 过不去）、行尾被换成混合（下次 diff 满屏）、
常量被顺手改掉（谁都没守着）、基线丢了键（`run_all` 静默跳过）、
文件被回滚成旧版（第113轮踩过：静态自洽 ⇒ 跑起来不报错）。
所以本工具不复用任何套件判据，**只对"这一轮动过的文件"做七项体检**。

| 段 | 查什么 |
|---|---|
| ① | 语法：每个动过的 `.py` 都能 `ast.parse`（**不产 `.pyc`** —— 复检不许改变被测状态） |
| ② | 结构：165 的常量/方法/接线点在，且**各恰一处**（重复定义=静默覆盖） |
| ③ | 编码/换行：无 BOM；main.py 仍全 CRLF；motion_profile.py 仍纯 LF；json 可解析 |
| ④ | 恒真复查：本轮的判据里没有"第二参是常量"的恒真/恒假；判据名不重复 |
| ⑤ | 逐令牌：设计里的每个数字都还是那个数字（12:3:4:8 / 240 / 5 / 0.06 / 1200 / 区间） |
| ⑥ | 工作区/基线：`SUITES` 里恰好登记一次、脚本存在、基线里有 `check165` |
| ⑦ | 反回滚：文件不许比记录缩水 >30%，关键内容必须还在（第113轮闸） |

⚠️ 本工具**只读**：不改任何文件、不写盘、不联网、不需要显示器。
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
MPY = os.path.join(PET, 'modules', 'motion_profile.py')
PROFILE = os.path.join(PET, 'assets', 'npc', '_motion_profile.json')
REGISTRY = os.path.join(PET, 'assets', 'npc', '_registry.json')
RUN_ALL = os.path.join(ROOT, 'code-quality-audit', 'regress', 'run_all.py')
BASELINE = os.path.join(ROOT, 'code-quality-audit', 'regress', 'baseline.json')
CHECK165 = os.path.join(HERE, 'check165.py')
GEN = os.path.join(HERE, 'gen165_profiles.py')
MUT = os.path.join(HERE, 'mutate165.py')

# ★ 本轮动过的"别处的套件"（补桩 / 改时相量回显）：只查编码与语法，
#   不查内容 —— 它们各自有 `--only` 跑得通就是最好的证据。
TOUCHED_SUITES = [
    os.path.join(ROOT, 'code-quality-audit', '第十四轮', 'verify_round14_move.py'),
    os.path.join(ROOT, 'code-quality-audit', '第十八轮', 'verify_round18_climb.py'),
    os.path.join(ROOT, 'code-quality-audit', '第56轮-NPC站位与游荡', 'check56.py'),
    os.path.join(ROOT, 'code-quality-audit', '第151轮-留一条真差事', '_tools', 'check151.py'),
    os.path.join(ROOT, 'code-quality-audit', '第153轮-差事交差', '_tools', 'check153.py'),
    os.path.join(ROOT, 'code-quality-audit', '第158轮-状态变了就落盘', '_tools', 'check158.py'),
]

#: ⑦ 反回滚的锚点：文件 → (最小行数, 必须还在的字面量)
REGRESSION_ANCHORS = {
    MAIN: (18000, [u'def _motion_eff', u"self._motion_eff()['jump']",
                   u"RUNUP_SPEED_MAX * self._motion_eff()['run']",
                   u"RUNUP_ACCEL * self._motion_eff()['accel']"]),
    MPY: (150, [u'def apply_exp', u'def effective', u'def validate_entry']),
}

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
    """按字节忠实读（`newline=''`，条款 §11：别让 Python 替我们改行尾）。"""
    with io.open(path, 'r', encoding='utf-8', newline='') as fh:
        return fh.read()


def ast_of(path):
    try:
        return ast.parse(read_txt(path))
    except SyntaxError as e:
        print('  (ast 失败 %s: %s)' % (os.path.basename(path), e))
        return None


# ============================================================ ① 语法
print('=' * 66)
print(u'① 语法（不产 .pyc：复检不许改变被测状态）')
print('=' * 66)

_FILES = [MAIN, MPY, CHECK165, GEN, MUT, RUN_ALL] + TOUCHED_SUITES
_ast = {}
for _pth in _FILES:
    check(u'① 可解析：%s' % os.path.basename(_pth),
          os.path.isfile(_pth) and ast_of(_pth) is not None)
    if os.path.isfile(_pth):
        _ast[_pth] = ast_of(_pth)

# ============================================================ ② 结构
print('')
print('=' * 66)
print(u'② 结构：常量/方法/接线点都在，且各恰一处（重复定义 = 静默覆盖）')
print('=' * 66)

_main_src = read_txt(MAIN) if os.path.isfile(MAIN) else ''
_mpy_mod = None
try:
    sys.path.insert(0, PET)
    from modules import motion_profile as _mpy_mod      # noqa: N816
except Exception as _e:                                 # noqa: BLE001
    print('  (import motion_profile 失败：%s)' % _e)

_METHOD_NEEDLES = [
    u'def _motion_profile_table', u'def _motion_profile_of', u'def _motion_eff',
    u'def _motion_note_practice', u'def _motion_progress_file',
    u'def _motion_progress_ensure', u'def _motion_progress_load',
    u'def _motion_progress_save',
]
for _n in _METHOD_NEEDLES:
    check(u'② 方法各恰一处：`%s`' % _n.replace(u'def ', u''),
          _main_src.count(_n) == 1, u'实得 %d 处' % _main_src.count(_n))

_WIRE = [
    (u"self._motion_eff()['jump']", 1, u'起跳闸门乘 jump'),
    (u"RUNUP_SPEED_MAX * self._motion_eff()['run']", 1, u'冲刺上限乘 run'),
    (u"RUNUP_ACCEL * self._motion_eff()['accel']", 1, u'助跑加速度乘 accel'),
    (u"self._motion_note_practice('jump_ok')", 1, u'成功起跳记账'),
    (u"self._motion_note_practice('jump_fail')", 1, u'失败起跳记账'),
    (u"self._motion_note_practice('errand', npc_id=npc_id)", 2, u'差事办完记账（早退 + finally 各一）'),
    (u'self._motion_progress_save(force=True)', 1, u'退出时兜底落盘'),
]
for _needle, _want, _why in _WIRE:
    _got = _main_src.count(_needle)
    check(u'② 接线恰 %d 处：%s（%s）' % (_want, _why, _needle[:42]),
          _got == _want, u'实得 %d 处' % _got)

if _mpy_mod is not None:
    _fns = [n.name for n in _ast.get(MPY).body
            if isinstance(n, ast.FunctionDef)] if _ast.get(MPY) else []
    for _n in ('default_profile', 'from_dict', 'to_dict', 'level_of', 'progress_of',
               'apply_exp', 'effective', 'effective_tuple', 'validate_entry'):
        check(u'② 纯函数在：`%s`' % _n, _n in _fns)
    # ★ 零依赖纪律：模块内不许出现任何 import（连标准库都不需要）
    _imports = [n for n in ast.walk(_ast[MPY]) if isinstance(n, (ast.Import, ast.ImportFrom))]
    check(u'② ★ `motion_profile` 零依赖（一条 import 都没有）',
          not _imports, u'实得 %d 条' % len(_imports))

# ============================================================ ③ 编码/换行
print('')
print('=' * 66)
print(u'③ 编码/换行（中文项目最容易毁在这里）')
print('=' * 66)

for _pth in [MAIN, MPY, CHECK165, GEN, MUT] + TOUCHED_SUITES:
    _raw = read_raw(_pth) if os.path.isfile(_pth) else b''
    _crlf = _raw.count(b'\r\n')
    _lf = _raw.count(b'\n') - _crlf
    check(u'③ 无 BOM：%s' % os.path.basename(_pth),
          not _raw.startswith(b'\xef\xbb\xbf'))
    check(u'③ 行尾不混：%s（CRLF=%d 裸LF=%d）' % (os.path.basename(_pth), _crlf, _lf),
          not (_crlf > 0 and _lf > 0))

# main.py 必须仍是**全 CRLF**（产品文件的口径，check153 D3 也守着这条）
_raw_main = read_raw(MAIN)
check(u'③ ★ main.py 仍是全 CRLF（裸 LF 必须为 0）',
      (_raw_main.count(b'\n') - _raw_main.count(b'\r\n')) == 0,
      u'裸LF=%d' % (_raw_main.count(b'\n') - _raw_main.count(b'\r\n')))

# ============================================================ ④ 恒真复查
print('')
print('=' * 66)
print(u'④ 恒真复查（判据的第二参不许是常量；判据名不许重复）')
print('=' * 66)

_t = _ast.get(CHECK165)
_names = []
_trivial = []
_no_extra = []
if _t is not None:
    for _n in ast.walk(_t):
        if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Name) \
                and _n.func.id == 'check' and len(_n.args) >= 2:
            _a0, _a1 = _n.args[0], _n.args[1]
            if isinstance(_a0, ast.Constant) and isinstance(_a0.value, str):
                _names.append(_a0.value)
            # ★ 只抓**恒真**（`True` / 非空字符串 / 非零数 / 非空容器）：
            #   恒真会静默地把"没坏"当作"验过"（第85轮 `{} == {}` 同族）。
            #   恒假（`False` / `0` / `''`）**不抓** —— 它每次都红、藏不住，
            #   而且本项目正是在"前置缺失"分支里用它显式报红
            #   （`A0b` / `C0` / `C4` 三处），属于正当写法。
            if isinstance(_a1, ast.Constant):
                if _a1.value:
                    _trivial.append(_a0.value if isinstance(_a0, ast.Constant) else '?')
            elif isinstance(_a1, (ast.List, ast.Tuple, ast.Set)):
                if _a1.elts:
                    _trivial.append(_a0.value if isinstance(_a0, ast.Constant) else '?')
            elif isinstance(_a1, ast.Dict):
                if _a1.keys:
                    _trivial.append(_a0.value if isinstance(_a0, ast.Constant) else '?')
check(u'④ ★★★ 没有"第二参是**恒真**常量"的判据（85 `{}=={}` 同族；恒假豁免，见上）',
      not _trivial, u'命中 %s' % (_trivial[:3],))
check(u'④ 判据条数够（执行面 ≥ 40 条，防"判据被删空还全绿"）',
      len(_names) >= 40, u'实得 %d 条' % len(_names))
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

if _mpy_mod is not None:
    check(u'⑤ EFF_KEYS 顺序固定', _mpy_mod.EFF_KEYS == ('jump', 'run', 'accel'),
          u'%s' % (_mpy_mod.EFF_KEYS,))
    check(u'⑤ 三个倍率区间 [0.4, 2.0]',
          all(_mpy_mod.LIMITS[k] == (0.4, 2.0) for k in _mpy_mod.EFF_KEYS))
    check(u'⑤ growth 区间 [0.3, 2.5]（起点高也练得动）',
          _mpy_mod.LIMITS['growth'] == (0.3, 2.5))
    check(u'⑤ LEVEL_STEP = 240 / MAX_LEVEL = 5 / GAIN = 0.06',
          (_mpy_mod.LEVEL_STEP, _mpy_mod.MAX_LEVEL, _mpy_mod.GAIN_PER_LEVEL) == (240.0, 5, 0.06),
          u'%s' % ((_mpy_mod.LEVEL_STEP, _mpy_mod.MAX_LEVEL, _mpy_mod.GAIN_PER_LEVEL),))
    check(u'⑤ MAX_EXP = LEVEL_STEP × MAX_LEVEL = 1200',
          _mpy_mod.MAX_EXP == 1200.0, u'%s' % _mpy_mod.MAX_EXP)
    check(u'⑤ 记账权重 12 : 3 : 4 : 8（成功远多于失败）',
          (_mpy_mod.EXP_JUMP_OK, _mpy_mod.EXP_JUMP_FAIL,
           _mpy_mod.EXP_MOVE_OK, _mpy_mod.EXP_ERRAND) == (12.0, 3.0, 4.0, 8.0),
          u'%s' % ((_mpy_mod.EXP_JUMP_OK, _mpy_mod.EXP_JUMP_FAIL,
                    _mpy_mod.EXP_MOVE_OK, _mpy_mod.EXP_ERRAND),))
    check(u'⑤ 依据三档（明证/推断/无据）',
          tuple(_mpy_mod.EVIDENCE_LEVELS) == (u'明证', u'推断', u'无据'),
          u'%s' % (_mpy_mod.EVIDENCE_LEVELS,))
    # 行为级：1.0 恒等 + 练满 +30%（growth 1.0）
    _e0 = _mpy_mod.effective(_mpy_mod.default_profile(), 0.0)
    check(u'⑤ ★ 默认档 + 0 经验 = 精确 1.0（零回归的根）',
          all(_e0[k] == 1.0 for k in _mpy_mod.EFF_KEYS), u'%s' % (_e0,))
    _efull = _mpy_mod.effective(
        {'jump': 1.0, 'run': 1.0, 'accel': 1.0, 'growth': 1.0}, _mpy_mod.MAX_EXP)
    check(u'⑤ growth 1.0 练满 = +30%（1.0 → 1.30）',
          abs(_efull['jump'] - 1.30) < 1e-9, u'%.4f' % _efull['jump'])

check(u'⑤ main.py 基准人 id = ralsei', u"MOTION_PROFILE_ID = 'ralsei'" in _main_src)
check(u'⑤ main.py 档名 = motion_progress.json',
      u"MOTION_PROGRESS_FILE = 'motion_progress.json'" in _main_src)

# ============================================================ ⑥ 工作区/基线
print('')
print('=' * 66)
print(u'⑥ 工作区/基线：登记恰好一次、脚本在、基线有键')
print('=' * 66)

_ra_src = read_txt(RUN_ALL)
check(u'⑥ `SUITES` 里 check165 登记**恰好一次**',
      _ra_src.count(u"'id': 'check165'") == 1,
      u'实得 %d 处' % _ra_src.count(u"'id': 'check165'"))
check(u'⑥ 登记的脚本路径存在', os.path.isfile(CHECK165))
check(u'⑥ 登记里带 `offscreen: True`（否则无显示器环境跑不起来）',
      u"'id': 'check165'" in _ra_src
      and u"'offscreen': True" in _ra_src.split(u"'id': 'check165'")[1][:400],
      u'%s' % (_ra_src.split(u"'id': 'check165'")[1][:120].replace('\n', ' '),))

try:
    with io.open(BASELINE, 'r', encoding='utf-8') as fh:
        _bl = json.load(fh)
    _suites = _bl.get('suites') or _bl
    check(u'⑥ 基线里有 check165 的键', 'check165' in _suites,
          u'键数=%d' % len(_suites))
    _ent = _suites.get('check165') or {}
    check(u'⑥ 基线记着这次是绿的（fail=0 / exit=0）',
          (not _ent.get('fail')) and (not _ent.get('exit')),
          u'exit=%s fail=%s pass=%s' % (_ent.get('exit'), _ent.get('fail'), _ent.get('pass')))
except Exception as _e:                                 # noqa: BLE001
    check(u'⑥ 基线可读', False, '%s: %s' % (type(_e).__name__, _e))

# ============================================================ ⑦ 反回滚
print('')
print('=' * 66)
print(u'⑦ 反回滚（第113轮：工作区被换成旧版而 git 不报错，静态自洽跑不红）')
print('=' * 66)

for _pth, (_min_lines, _needles) in REGRESSION_ANCHORS.items():
    _txt = read_txt(_pth)
    _n = _txt.count('\n') + 1
    check(u'⑦ %s 行数没缩水（%d ≥ %d）' % (os.path.basename(_pth), _n, _min_lines),
          _n >= _min_lines)
    for _needle in _needles:
        check(u'⑦ %s 里 `%s` 还在' % (os.path.basename(_pth), _needle[:40]),
              _needle in _txt)

try:
    with io.open(PROFILE, 'r', encoding='utf-8') as fh:
        _prof = json.load(fh)
    with io.open(REGISTRY, 'r', encoding='utf-8') as fh:
        _reg = json.load(fh)
    _ids = [k for k in _prof if k != '_meta']
    _reg_ids = [x['id'] for x in _reg['npcs']]
    check(u'⑦ 档案仍是 96 人且与注册表一一对应',
          len(_ids) == 96 and sorted(_ids) == sorted(_reg_ids),
          u'档案 %d / 注册表 %d' % (len(_ids), len(_reg_ids)))
    check(u'⑦ 基准人 ralsei 三项仍是 1.0（不许被"顺手调一下"）',
          all(abs(float(_prof['ralsei'][k]) - 1.0) < 1e-12
              for k in ('jump', 'run', 'accel')),
          u'%s' % ({k: _prof['ralsei'][k] for k in ('jump', 'run', 'accel')},))
    check(u'⑦ 「无据」的一个都不许超过 1.0',
          not [k for k in _ids
               if _prof[k].get('evidence') == u'无据'
               and max(float(_prof[k][x]) for x in ('jump', 'run', 'accel')) > 1.0 + 1e-12])
except Exception as _e:                                 # noqa: BLE001
    check(u'⑦ 档案/注册表可读', False, '%s: %s' % (type(_e).__name__, _e))

print('')
print('=' * 66)
print('PASS=%d  FAIL=%d' % (_p, _f))
if _f:
    print(u'失败项：')
    for _x in _bad:
        print(u'  - %s' % _x)
    sys.exit(1)
print(u'[PASS] 第165轮核心文件复检全部通过')
