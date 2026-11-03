# -*- coding: utf-8 -*-
u"""第149轮 · 核心文件复检（`ralsei_pet/src/main.py` 是产品主链路）。

规矩来源（用户口径逐字）：「**以后再调整重要核心文件时一定要记得复检**」。
六项固定形状：① 语法 ② 结构自检 ③ 无 BOM / 无 U+FFFD ④ 恒真判据复查
⑤ 逐令牌回验 ⑥ 工作区干净 ＋ 该跑回归的跑回归。

| 段 | 守什么 |
|---|---|
| H1 | 改动面：**恰好 1 个**跟踪文件（产品），`+19 / −0` |
| H2 | 语法：`ast.parse`（**不**用 `py_compile` —— 会产 `.pyc`，改被测状态） |
| H3 | 编码：无 BOM / 无 U+FFFD / **裸 LF = 0**（`main.py` 全篇 CRLF） |
| H4 | 结构自检：补丁块 5 行按序各 1 次；声明行与 `_bedtime_fired_date` 同区 |
| H5 | 逐令牌回验：本轮新增的每个令牌逐个 `in`；**旧令牌也逐个回验**（闸没把就寝废掉） |
| H6 | 恒真判据复查：`check(..., True)` 0 处、三段判据 0 处常量、`mutate` 的 `finally` 还原在位 |
| H7 | diff 归类：`-U0` 的加行**逐行**归属（19 行全属本轮补丁，无夹带） |
| H8 | 卫生：`_tools/` 无 `.pyc/.bak/~`；`_evidence/` 只有稳定结论 |

★ 本文件**不进 `SUITES`**：H1/H7 依赖 `git diff`（提交后就变空），它是**提交前**的闸。
  常驻回归由 `check149`（33 条）+ `mutate149`（16 条）承担。
"""
import ast
import io
import os
import subprocess
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
MAIN = os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py')
REL = u'ralsei_pet/src/main.py'

_n_ok = 0
_n_bad = 0
_failed = []
_marks = 0


def check(desc, cond, extra=u''):
    global _n_ok, _n_bad
    cond = bool(cond)
    if cond:
        _n_ok += 1
    else:
        _n_bad += 1
        _failed.append(desc)
    print(u'%s %s%s' % (u'[PASS]' if cond else u'[FAIL]', desc,
                        (u'  ' + extra) if extra else u''))


def head(t):
    global _marks
    _marks += 1
    print(u'---- [复检点 %d] %s ----' % (_marks, t))


def _git(*args):
    p = subprocess.Popen([u'git'] + list(args), cwd=ROOT,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    o, e = p.communicate()
    return (o.decode('utf-8', 'replace'), e.decode('utf-8', 'replace'), p.returncode)


with io.open(MAIN, 'rb') as _f:
    RAW = _f.read()
with io.open(MAIN, 'r', encoding='utf-8', newline='') as _f:
    SRC = _f.read()
TREE = ast.parse(SRC)

# =============================================== H1 改动面
head(u'H1 改动面：7 个跟踪文件，逐个对账')
_num, _, _ = _git('-c', 'core.quotepath=false', 'diff', '--numstat')
_rows = [ln for ln in _num.splitlines() if ln.strip()]
_NS = dict((ln.split(u'\t')[2], (ln.split(u'\t')[0], ln.split(u'\t')[1]))
           for ln in _rows)
# ★ 第一版只允许"1 个跟踪文件"—— 那是**过期前提**（登记套件要改 `run_all.py`、
#   契约变更要改 `check79.py`、记忆与基线也都会动）。第146轮复检栽过同一件事。
#   改成**点名 7 个**：多一个少一个都红，但不再假设"只许动产品"。
_EXPECT_FILES = set([
    u'ralsei_pet/src/main.py',
    u'code-quality-audit/\u7b2c79\u8f6e-\u81ea\u4e3b\u751f\u6d3b\u9a7b\u7559\u5c42/_tools/check79.py',
    u'code-quality-audit/regress/run_all.py',
    u'code-quality-audit/regress/baseline.json',
    u'.workbuddy/memory/MEMORY.md',
    u'.workbuddy/memory/2026-11-03.md',
    u'.workbuddy/memory/\u53c2\u8003-\u5951\u7ea6\u4e0e\u5386\u8f6e\uff08\u8be6\u7248\uff09.md',
])
check(u'H1 被改的跟踪文件**恰好**是本轮那 7 个（产品 1 + 契约锁 1 + 套件登记 1 + 基线 1 + 记忆 3）',
      set(_NS) == _EXPECT_FILES,
      u'多=%s 少=%s' % (sorted(set(_NS) - _EXPECT_FILES),
                       sorted(_EXPECT_FILES - set(_NS))))
check(u'H2 `main.py` 改动面 **+19 / −0**（纯新增：闸 16 行 + 声明 3 行，零删除）',
      _NS.get(REL) == (u'19', u'0'), u'%s' % (_NS.get(REL),))
check(u'H2b `check79.py` 只动 1 行 extra（`+2/−1`：旧的一行拆成两行）',
      _NS.get(u'code-quality-audit/\u7b2c79\u8f6e-\u81ea\u4e3b\u751f\u6d3b\u9a7b\u7559\u5c42'
              u'/_tools/check79.py') == (u'2', u'1'),
      u'%s' % (_NS.get(u'code-quality-audit/\u7b2c79\u8f6e-\u81ea\u4e3b\u751f\u6d3b'
                       u'\u9a7b\u7559\u5c42/_tools/check79.py'),))
check(u'H2c 速查本 `MEMORY.md` 改动**等量**（`+3/−3`：加两句、删一句，不借机膨胀）',
      _NS.get(u'.workbuddy/memory/MEMORY.md') == (u'3', u'3'),
      u'%s' % (_NS.get(u'.workbuddy/memory/MEMORY.md'),))
_st, _, _ = _git('-c', 'core.quotepath=false', 'status', '--porcelain')
_untracked = [ln[3:] for ln in _st.splitlines() if ln.startswith(u'?? ')]
check(u'H1b 除本轮目录外**没有**别的未跟踪垃圾（防临时文件混进工作区）',
      all(u'\u7b2c149\u8f6e' in u for u in _untracked),
      u'%s' % (_untracked,))

# =============================================== H2 语法
head(u'H2 语法：ast.parse（不产 .pyc）')


def _no_pyc():
    bad = []
    for d, _dirs, files in os.walk(os.path.join(ROOT, 'code-quality-audit', ROUND_BASENAME)):
        for fn in files:
            if fn.endswith((u'.pyc', u'.pyo', u'.bak', u'~')):
                bad.append(os.path.join(d, fn))
    return bad


ROUND_BASENAME = os.path.basename(ROUND)
_FN_CNT = len([n for n in ast.walk(TREE) if isinstance(n, ast.FunctionDef)])
check(u'H2 语法：`main.py` 可解析且**真解析出了大文件**（不是空串也能 parse）',
      isinstance(TREE, ast.Module) and _FN_CNT >= 300,
      u'%d 行 / %d 个函数' % (SRC.count(u'\n') + 1, _FN_CNT))
_SELF_T = ast.parse(io.open(os.path.abspath(__file__), 'r', encoding='utf-8').read())
_SELF_FN = set(n.name for n in ast.walk(_SELF_T) if isinstance(n, ast.FunctionDef))
# ★ 第一版写成"函数数 ≥ 5"—— 随手拍的规模闸，实测只有 4 个 ⇒ 假红。
#   换成**点名**：本脚本自己的三个关键工具函数必须在（断行为，不断规模）。
check(u'H2b 语法：**本模块自己**也可解析，且 `check`/`head`/`_git` 都在'
      u'（复检脚本自己坏了就不该报绿）',
      set([u'check', u'head', u'_git']) <= _SELF_FN,
      u'缺 %s' % (sorted(set([u'check', u'head', u'_git']) - _SELF_FN),))

# =============================================== H3 编码
head(u'H3 编码：无 BOM / 无 U+FFFD / 裸 LF = 0')
_crlf = RAW.count(b'\r\n')
_bare = RAW.count(b'\n') - _crlf
check(u'H3 无 BOM', not RAW.startswith(b'\xef\xbb\xbf'))
check(u'H3b 无 U+FFFD（替换符）', u'\ufffd' not in SRC,
      u'%d 处' % SRC.count(u'\ufffd'))
check(u'H3c `main.py` 全篇 CRLF，**裸 LF = 0**（编辑没把 EOL 带跑 —— 第147轮踩过）',
      _bare == 0 and _crlf > 1000, u'CRLF=%d 裸LF=%d' % (_crlf, _bare))
check(u'H3d 合法 UTF-8（严格解码不抛）',
      io.open(MAIN, 'r', encoding='utf-8', errors='strict', newline='').read()
      == SRC)

# =============================================== H4 结构自检
head(u'H4 结构自检：补丁块按序、各 1 次、无粘连')
# ★★ `return False` 那一行**不能**用「16 空格 + return False」当锚点 ——
#   同一函数里 `_bedtime_fired_date` 判断和 `_bedtime_busy()` 判断的 body 也都是
#   同样缩进的 `return False`（共 3 处）。必须带上它的**下一句**才唯一。
_ORDER = [
    (u'取 home', u"            _home = getattr(self, 'BEDTIME_HOME_SCENE', 'desktop')"),
    (u'取 cur', u"            _cur = getattr(self, 'current_scene', None)"),
    (u'闸', u'            if _cur and _cur != _home:'),
    (u'日志去重判断', u"                if getattr(self, '_bedtime_defer_logged', None) != _cur:"),
    (u'写去重位', u'                    self._bedtime_defer_logged = _cur'),
    (u'推迟返回', u'                return False\r\n'
                  u'            self._bedtime_fired_date = today'),
]
_pos = [SRC.find(t) for _label, t in _ORDER]
_cnt = [(lbl, SRC.count(t)) for lbl, t in _ORDER]
check(u'H4 补丁块 6 个锚句**各出现 1 次**',
      all(c == 1 for _l, c in _cnt), u'%s' % (_cnt,))
check(u'H4b 六句**按逻辑顺序**出现（不是散落的碎片）',
      all(p >= 0 for p in _pos) and _pos == sorted(_pos))
check(u'H4c 闸的 `return False` 在「标记 fired」之前（把就寝掐在切显示之前）',
      _pos[-1] < SRC.rfind(u'self._bedtime_fired_date = today'))
check(u'H4d 声明行紧邻 `_bedtime_fired_date = None`（同区集中声明）',
      SRC.count(u'self._bedtime_defer_logged = None') == 1
      and 0 < SRC.find(u'self._bedtime_defer_logged = None')
      - SRC.find(u'self._bedtime_fired_date = None') < 200)

# =============================================== H5 逐令牌回验
head(u'H5 逐令牌回验：新增的与**旧的**都逐个回验')
_NEW_TOKENS = [
    u'_bedtime_defer_logged',
    u'BEDTIME_HOME_SCENE',
    u'current_scene',
    u'\u4e0d\u5207\u663e\u793a\uff0c\u56de\u684c\u9762\u518d\u7761',   # 不切显示，回桌面再睡
    u'\u7b2c149\u8f6e',                                                 # 第149轮
]
_TOK_CNT = [(t, SRC.count(t)) for t in _NEW_TOKENS]
check(u'H5 本轮涉及的 5 个令牌**逐个**都还在源码里（0 次 = 被后续编辑抹掉）',
      all(c > 0 for _t, c in _TOK_CNT), u'%s' % (_TOK_CNT,))
_OLD_TOKENS = [
    u'def go_to_bed(self):',
    u'ok = bool(self.scene.switch(home))',
    u'def _bedtime_busy(self):',
    u'def _bedtime_tick(self, now=None):',
    u'def enter_sleep_mode(self, bedtime=False):',
]
_OLD_CNT = [(t, SRC.count(t)) for t in _OLD_TOKENS]
check(u'H5b 旧令牌也逐个回验（闸没把就寝/入睡整条链废掉）',
      all(c == 1 for _t, c in _OLD_CNT), u'%s' % (_OLD_CNT,))
check(u'H5c `_bedtime_defer_logged` **恰好 3 次**（1 声明 + 1 读 + 1 写）',
      SRC.count(u'_bedtime_defer_logged') == 3,
      u'%d 次' % SRC.count(u'_bedtime_defer_logged'))

# =============================================== H6 恒真判据复查
head(u'H6 恒真判据复查：检查"守人的判据"自己')
_TOOLS = [os.path.join(HERE, f) for f in ('check149.py', 'mutate149.py')]
_bad_true = []
for _p in _TOOLS:
    _t = ast.parse(io.open(_p, 'r', encoding='utf-8').read())
    for n in ast.walk(_t):
        if not isinstance(n, ast.Call):
            continue
        f = n.func
        nm = f.id if isinstance(f, ast.Name) else (f.attr if isinstance(f, ast.Attribute) else u'')
        if nm not in (u'check', u'ok', u'mutate'):
            continue
        args = n.args
        # `check(desc, cond, …)` / `ok(cond, …)` / `mutate(tag, path, pairs, expect)`
        idx = 1 if nm in (u'check', u'ok') else 3
        if len(args) > idx and isinstance(args[idx], ast.Constant) \
                and args[idx].value is True:
            _bad_true.append((os.path.basename(_p), n.lineno))
check(u'H6 两套工具里 `check(desc, True)` / `mutate(..., True)` **0 处**',
      not _bad_true, u'%s' % (_bad_true,))

_MC = ast.parse(io.open(os.path.join(HERE, 'mutate149.py'), 'r', encoding='utf-8').read())
_finally = [n for n in ast.walk(_MC) if isinstance(n, ast.Try) and n.finalbody]
check(u'H6b `mutate149` 的"按字节还原"确实在 `finally` 里（中途抛异常也不会留下坏文件）',
      len(_finally) >= 1, u'%d 个 try/finally' % len(_finally))

_C149 = ast.parse(io.open(os.path.join(HERE, 'check149.py'), 'r', encoding='utf-8').read())
_call_cnt = len([n for n in ast.walk(_C149)
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                 and n.func.id == u'check'])
check(u'H6c `check149` 的判据条数是**常量**（不随环境增减 ⇒ 换机器不会少数）',
      _call_cnt >= 30, u'%d 个 check 调用点' % _call_cnt)

# =============================================== H7 diff 归类
head(u'H7 diff 归类：`-U0` 的加行逐行归属')
_d, _, _ = _git('-c', 'core.quotepath=false', 'diff', '-U0', '--', REL)
_added = [ln[1:] for ln in _d.splitlines() if ln.startswith(u'+') and not ln.startswith(u'+++')]
_removed = [ln[1:] for ln in _d.splitlines() if ln.startswith(u'-') and not ln.startswith(u'---')]
check(u'H7 加行数 == 19、删行数 == 0', len(_added) == 19 and len(_removed) == 0,
      u'+%d −%d' % (len(_added), len(_removed)))
# 每一条加行必须能归到三类之一：注释 / 闸代码 / 声明
_CODE_TOKENS = (u'_home', u'_cur', u'if ', u'self._bedtime_defer_logged',
                u'_log.info', u'return False', u'#')
_unowned = [ln for ln in _added if not any(t in ln for t in _CODE_TOKENS)]
check(u'H7b 19 条加行**逐行**都能归到（注释 / 闸代码 / 声明）—— 无夹带',
      not _unowned, u'无法归类 %d 行' % len(_unowned))
check(u'H7c `-U0` 里**没有** `===` 冲突标记残留',
      u'<<<<<<<' not in SRC and u'>>>>>>>' not in SRC and u'=======' not in _d)

# =============================================== H8 卫生
head(u'H8 卫生：临时产物 / 证据稳定性')
_pyc = _no_pyc()
check(u'H8 `_tools/` 与整轮目录**无** `.pyc/.bak/~`',
      not _pyc, u'%s' % (_pyc[:3],))
_ev = os.path.join(ROUND, '_evidence')
_evf = sorted(os.listdir(_ev)) if os.path.isdir(_ev) else []
check(u'H8b `_evidence/` 只放**稳定结论**（只有 measure149.json，无时间戳/计数类易变物）',
      _evf == [u'measure149.json'], u'%s' % (_evf,))

print(u'')
print(u'=' * 78)
print(u'recheck149_core：PASS=%d FAIL=%d' % (_n_ok, _n_bad))
if _failed:
    print(u'失败项：')
    for _d2 in _failed:
        print(u'  - %s' % _d2)
sys.exit(0 if _n_bad == 0 else 1)
