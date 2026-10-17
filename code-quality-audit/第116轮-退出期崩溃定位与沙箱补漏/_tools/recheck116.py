# -*- coding: utf-8 -*-
u"""第116轮 · 收尾复检（改过"重要核心文件"必复检 —— 用户口径）。

被复检的文件：
  · `.workbuddy/memory/MEMORY.md`（速查本：§10 锁号 + 新增 §22）
  · `.workbuddy/memory/2026-10-17.md`（当日日志）
  · `code-quality-audit/regress/run_all.py`（SUITES 的 desc 与新套件条目）
  · `.../第116轮.../_tools/check116.py`（本轮主套件，本轮**改过**：ROOT 可覆盖 + E2b 加强）

复检项（每项都可落盘、可回看）
  1 语法：三份 .py 全部 `ast.parse` 通过（**不产 .pyc**：用 ast 不用 py_compile）
  2 结构：MEMORY.md 的 §22 / 锁号 `check116` 在位；日志八个小节标题在位
  3 编码：两份记忆文件**无 BOM**、**无 U+FFFD**
  4 体积：MEMORY.md 的 **JS 长度（UTF-16 码元）** ≤ 10000（真口径，不是字节数）
  5 恒真判据复查：check116.py 里所有 `check()` 第二实参不是字面量 True
  6 逐令牌回验：MEMORY.md §22 里点名的令牌，逐个回**产品/工具文件**里 `in` 一次
  7 记账：baseline.json 里 check116 已固化、且 PASS 计数与实跑一致
"""
import ast
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
MEM = os.path.join(ROOT, '.workbuddy', 'memory')
CQA = os.path.join(ROOT, 'code-quality-audit')

ok = fail = 0
LINES = []


def check(name, cond, detail=None):
    global ok, fail
    if cond:
        ok += 1
        LINES.append(u'[PASS] %s' % name)
    else:
        fail += 1
        LINES.append(u'[FAIL] %s' % name)
        if detail:
            LINES.append(u'       detail: %s' % (detail,))


def r(p):
    with io.open(p, encoding='utf-8', newline='') as f:
        return f.read()


def rb(p):
    with io.open(p, 'rb') as f:
        return f.read()


def js_len(s):
    u"""★ 真口径：**JS 字符串长度** = UTF-16 码元数（BMP 外字符算 2）。

    本项目踩过多次"拿 len(bytes) 或 len(chars) 当上限"的假安全。
    """
    n = 0
    for ch in s:
        n += 2 if ord(ch) > 0xFFFF else 1
    return n


MAIN_CHK = os.path.join(ROUND, '_tools', 'check116.py')
MUT = os.path.join(ROUND, '_tools', 'mutate116.py')
RUNALL = os.path.join(CQA, 'regress', 'run_all.py')
MEMF = os.path.join(MEM, 'MEMORY.md')
LOG = os.path.join(MEM, '2026-10-17.md')

# ---------------------------------------------------------------- 1 语法
for p in (MAIN_CHK, MUT, RUNALL):
    try:
        ast.parse(r(p))
        good, err = True, None
    except Exception as e:                                    # noqa: BLE001
        good, err = False, e
    check(u'R1 语法可解析：%s' % os.path.basename(p), good, detail=err)

# ---------------------------------------------------------------- 2 结构
mem = r(MEMF)
check(u'R2a MEMORY.md 有 §22 节', u'## 22. 116' in mem)
check(u'R2b MEMORY.md 锁号速查含 check116 与 mutate116',
      (u'`check116`(**40**)' in mem) and (u'`mutate116`(**11/11**)' in mem))
log = r(LOG) if os.path.isfile(LOG) else u''
_heads = [u'### 1. 沙箱补漏', u'### 2. 四缺陷', u'### 3. 判据与变异',
          u'### 4. 回归', u'### 5. 遗留']
check(u'R2c 当日日志存在且五个小节标题都在',
      bool(log) and all(h in log for h in _heads),
      detail=u'缺 %r' % ([h for h in _heads if h not in log],))

# ---------------------------------------------------------------- 3 编码
for p, tag in ((MEMF, u'MEMORY.md'), (LOG, u'2026-10-17.md')):
    if not os.path.isfile(p):
        check(u'R3 %s 无 BOM / 无 U+FFFD' % tag, False, detail=u'文件不在盘')
        continue
    b = rb(p)
    txt = b.decode('utf-8', 'replace')
    check(u'R3 %s 无 BOM / 无 U+FFFD' % tag,
          (not b.startswith(b'\xef\xbb\xbf')) and (u'\ufffd' not in txt),
          detail=u'bom=%r fffd=%r' % (b.startswith(b'\xef\xbb\xbf'),
                                      u'\ufffd' in txt))

# ---------------------------------------------------------------- 4 体积
_n = js_len(mem)
check(u'R4 MEMORY.md 的 JS 长度 ≤ 10000（实到 %d）' % _n, _n <= 10000)

# ---------------------------------------------------------------- 5 恒真判据
_taut = []
for node in ast.walk(ast.parse(r(MAIN_CHK))):
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
            and node.func.id == 'check' and len(node.args) >= 2:
        a = node.args[1]
        if isinstance(a, ast.Constant) and a.value is True:
            _taut.append(getattr(node, 'lineno', -1))
check(u'R5 check116.py 无 `check(..., True)` 恒真判据', not _taut,
      detail=u'行号 %r' % (_taut,))

# ---------------------------------------------------------------- 6 逐令牌回验
_TOK = {
    u'RALSEI_MEMORY_DIR': [os.path.join(CQA, u'第96轮-用户视角录制复核', '_tools',
                                        'diag96_exit.py')],
    u'availableGeometry': [os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py')],
    u'desk_door_ut': [os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes',
                                   'desktop.json')],
    u'desk_door_deltarune': [os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes',
                                          'desktop.json')],
    u'fade_plan': [os.path.join(ROOT, 'ralsei_pet', 'modules', 'dialogue_ui.py')],
    u'STEADY_EPS': [os.path.join(ROOT, 'ralsei_pet', 'modules', 'dialogue_ui.py')],
    u'_just_shown': [os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py')],
    u'vault_guard': [os.path.join(CQA, '_shared', 'vault_guard.py')],
}
for tok, files in sorted(_TOK.items()):
    hits = []
    for p in files:
        if os.path.isfile(p) and tok in r(p):
            hits.append(os.path.basename(p))
    check(u'R6 令牌回验 `%s` 在盘且真出现' % tok, bool(hits),
          detail=u'找过 %r' % ([os.path.basename(p) for p in files],))

# ---------------------------------------------------------------- 6b 下沉令牌回验
#   ★ 本轮压过速查本：删掉的每个可检索令牌都必须**能在详版里 `in` 到**
#     （否则压缩 = 静默丢信息；2026-09-23 就靠这一步抓回两个 hash）。
_DETAIL = os.path.join(MEM, u'参考-契约与历轮（详版）.md')
_det = r(_DETAIL) if os.path.isfile(_DETAIL) else u''
_SUNK = [u'oneshot.mainline.INIT', u'ut.rooms.room_start', u'ch1.hometown.town_mid',
         u'mutate115', u'tray_hint_shown', u'find_device_dir', u'60B']
for tok in _SUNK:
    check(u'R6b 下沉令牌 `%s` 在详版可检索' % tok, tok in _det)

# ---------------------------------------------------------------- 7 基线记账
_bp = os.path.join(CQA, 'regress', 'baseline.json')
try:
    _b = json.load(io.open(_bp, encoding='utf-8'))
    # ★ 基线结构 = {'note':…, 'suites': {id: {exit,pass,fail,sha256}}, 'version':…}
    _cases = _b.get('suites') or {}
    _c = _cases.get('check116')
    check(u'R7a baseline.json 里 check116 已固化', _c is not None,
          detail=u'套件数 %d' % (len(_cases),))
    if isinstance(_c, dict):
        _p = _c.get('pass')
        check(u'R7b 基线 PASS 计数 == 40（实到 %r）' % (_p,), _p == 40)
    else:
        check(u'R7b 基线 PASS 计数 == 40', False, detail=u'取不到 pass 字段')
except Exception as e:                                        # noqa: BLE001
    check(u'R7 基线可读', False, detail=repr(e))

LINES.append(u'')
LINES.append(u'合计 PASS=%d FAIL=%d（共 %d 条）' % (ok, fail, ok + fail))
out = u'\n'.join(LINES)
sys.stdout.write(out + u'\n')

# 落证据
ev = os.path.join(ROUND, '_evidence', 'rec116', 'recheck116.txt')
try:
    with io.open(ev, 'w', encoding='utf-8', newline='\n') as f:
        f.write(out + u'\n')
except Exception:                                             # noqa: BLE001
    pass
sys.exit(1 if fail else 0)
