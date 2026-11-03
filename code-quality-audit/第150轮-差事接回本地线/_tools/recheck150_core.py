# -*- coding: utf-8 -*-
u"""第150轮 · 核心文件复检（本轮改了 **3 个产品文件 + 新增 1 个**）。

规矩来源（用户口径逐字）：「**以后再调整重要核心文件时一定要记得复检**」。
六项固定形状：① 语法 ② 结构自检 ③ 无 BOM / 无 U+FFFD ④ 恒真判据复查
⑤ 逐令牌回验 ⑥ 工作区干净 ＋ 该跑回归的跑回归。

| 段 | 守什么 |
|---|---|
| H1 | 改动面：**恰好**点名的跟踪文件（多一个少一个都红）+ 未跟踪清单 |
| H2 | 产品足迹：`main.py` +705/−0、`npc_system.py` +77/−3、`dialogue_ui.py` +14/−0 |
| H3 | 语法：4 个产品文件 `ast.parse`（**不**用 `py_compile` —— 会产 `.pyc`，改被测状态） |
| H4 | 编码：无 BOM / 无 U+FFFD / **裸 LF = 0**（四份全 CRLF） |
| H5 | 结构自检：三条关键关系（tick 顺序 / 门控在 assign 前 / 零显示调用） |
| H6 | 逐令牌回验：**新增的与旧的都回验**；记忆里下沉的令牌去详版 `in` 一次 |
| H7 | 恒真判据复查：两套 harness（`check` / `mutate`）都看；`mutate` 的还原在 `finally` |
| H8 | 卫生：`.pyc/.bak/~` 0 个；`_evidence` 无易变物 |

★ 本文件**不进 `SUITES`**：H1/H2 依赖 `git diff`（提交后就变空），它是**提交前**的闸。
  常驻回归由 `check150`（104 条）+ `mutate150`（28 条）承担。
"""
import ast
import io
import os
import subprocess
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')
MAIN = os.path.join(PKG, 'src', 'main.py')
ERRAND = os.path.join(PKG, 'modules', 'npc_errand.py')
NPC_SYS = os.path.join(PKG, 'modules', 'npc_system.py')
DUI = os.path.join(PKG, 'modules', 'dialogue_ui.py')
MEM = os.path.join(ROOT, '.workbuddy', 'memory', 'MEMORY.md')
MEM_LONG = os.path.join(ROOT, '.workbuddy', 'memory', '参考-契约与历轮（详版）.md')

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


def _read(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def _raw(p):
    with io.open(p, 'rb') as f:
        return f.read()


SRC_MAIN = _read(MAIN)
SRC_ERR = _read(ERRAND)
SRC_NS = _read(NPC_SYS)
SRC_DUI = _read(DUI)
SRC_MEM = _read(MEM)
SRC_LONG = _read(MEM_LONG)

# =============================================== H1 改动面
head(u'H1 改动面：点名核对（多一个少一个都红）')

_num, _err, _ = _git('-c', 'core.quotepath=false', 'diff', '--numstat')
_rows = [ln for ln in _num.splitlines() if ln.strip()]
_NS = dict((ln.split(u'\t')[2], (ln.split(u'\t')[0], ln.split(u'\t')[1]))
           for ln in _rows)

#: ★ 点名而不是"只许动 N 个文件" —— 第146轮栽过：登记新套件本来就要改 `run_all.py`。
_EXPECT = set([
    u'ralsei_pet/src/main.py',
    u'ralsei_pet/modules/npc_system.py',
    u'ralsei_pet/modules/dialogue_ui.py',
    u'code-quality-audit/regress/run_all.py',
    u'code-quality-audit/regress/baseline.json',
    # 第149轮的时相量回填与判据翻面（随本轮一起提交）
    u'code-quality-audit/\u7b2c149\u8f6e-\u663e\u793a\u53ea\u8ddf\u7075\u9b42'
    u'/_tools/check149.py',
    u'code-quality-audit/\u7b2c149\u8f6e-\u663e\u793a\u53ea\u8ddf\u7075\u9b42'
    u'/report149.md',
    u'code-quality-audit/\u7b2c57\u8f6e-\u6a21\u578b\u5e76\u53d1\u5b9e\u6d4b/check57.py',
    u'code-quality-audit/\u7b2c72\u8f6e-\u8de8\u4e16\u754c\u673a\u5236/_tools/check72.py',
    u'.workbuddy/memory/MEMORY.md',
    u'.workbuddy/memory/2026-11-03.md',
    u'.workbuddy/memory/\u53c2\u8003-\u5951\u7ea6\u4e0e\u5386\u8f6e\uff08\u8be6\u7248\uff09.md',
])
check(u'H1 被改的跟踪文件**恰好**是本轮那 12 个（产品 3 + 审计 6 + 记忆 3）',
      set(_NS) == _EXPECT,
      u'多=%s 少=%s' % (sorted(set(_NS) - _EXPECT), sorted(_EXPECT - set(_NS))))

_st, _, _ = _git('-c', 'core.quotepath=false', 'status', '--porcelain')
_untracked = [ln[3:] for ln in _st.splitlines() if ln.startswith(u'?? ')]
_untracked_norm = [u.rstrip(u'/') for u in _untracked]
check(u'H1b 未跟踪的只有**本轮新增的两处**（`第150轮…/` 与 `npc_errand.py`）',
      set(_untracked_norm) == set([u'code-quality-audit/\u7b2c150\u8f6e-'
                                   u'\u5dee\u4e8b\u63a5\u56de\u672c\u5730\u7ebf',
                                   u'ralsei_pet/modules/npc_errand.py']),
      u'%s' % (_untracked_norm,))

# =============================================== H2 产品足迹
head(u'H2 产品足迹：三个改动文件的行数对账')
check(u'H2 `main.py` **+705 / −0**（纯新增：接线 + 宿主侧七件事，零删除）',
      _NS.get(u'ralsei_pet/src/main.py') == (u'705', u'0'),
      u'%s' % (_NS.get(u'ralsei_pet/src/main.py'),))
check(u'H2b `npc_system.py` **+77 / −3**（章名归一：三处逐字比改成 `chapter_matches`）',
      _NS.get(u'ralsei_pet/modules/npc_system.py') == (u'77', u'3'),
      u'%s' % (_NS.get(u'ralsei_pet/modules/npc_system.py'),))
check(u'H2c `dialogue_ui.py` **+14 / −0**（只插了派活入口那一块，零删除）',
      _NS.get(u'ralsei_pet/modules/dialogue_ui.py') == (u'14', u'0'),
      u'%s' % (_NS.get(u'ralsei_pet/modules/dialogue_ui.py'),))
check(u'H2d 速查本改动**等量**（`+3/−3`：改 3 处旧口径，不借机膨胀）',
      _NS.get(u'.workbuddy/memory/MEMORY.md') == (u'3', u'3'),
      u'%s' % (_NS.get(u'.workbuddy/memory/MEMORY.md'),))

# =============================================== H3 语法
head(u'H3 语法：ast.parse（不产 .pyc）')
_FILES = ((u'main.py', SRC_MAIN), (u'npc_errand.py', SRC_ERR),
          (u'npc_system.py', SRC_NS), (u'dialogue_ui.py', SRC_DUI))
_parsed = {}
_syn_bad = []
for _name, _src in _FILES:
    try:
        _parsed[_name] = ast.parse(_src)
    except SyntaxError as _e:
        _syn_bad.append((_name, str(_e)))
check(u'H3 四个产品文件**全部可解析**（含新建的 `npc_errand.py`）',
      not _syn_bad, u'%s' % (_syn_bad,))
check(u'H3b 分母闸：`main.py` 真解析出了大文件（函数数 ≥ 300，空串也能 parse）',
      len([n for n in ast.walk(_parsed.get(u'main.py', ast.Module(body=[], type_ignores=[])))
           if isinstance(n, ast.FunctionDef)]) >= 300,
      u'成立=%s' % (u'main.py' in _parsed,))
check(u'H3c `npc_errand.py` 解析出的函数数 ≥ 10（不是空文件冒充）',
      len([n for n in ast.walk(_parsed.get(u'npc_errand.py', ast.Module(body=[], type_ignores=[])))
           if isinstance(n, ast.FunctionDef)]) >= 10,
      u'成立=%s' % (u'npc_errand.py' in _parsed,))

_SELF_T = ast.parse(_read(os.path.abspath(__file__)))
_SELF_FN = set(n.name for n in ast.walk(_SELF_T) if isinstance(n, ast.FunctionDef))
check(u'H3d **本模块自己**也可解析，且 `check`/`head`/`_git` 都在'
      u'（复检脚本自己坏了就不该报绿）',
      set([u'check', u'head', u'_git']) <= _SELF_FN,
      u'缺 %s' % (sorted(set([u'check', u'head', u'_git']) - _SELF_FN),))

# =============================================== H4 编码
head(u'H4 编码：无 BOM / 无 U+FFFD / 裸 LF = 0')
for _name, _path, _src in ((u'main.py', MAIN, SRC_MAIN),
                           (u'npc_errand.py', ERRAND, SRC_ERR),
                           (u'npc_system.py', NPC_SYS, SRC_NS),
                           (u'dialogue_ui.py', DUI, SRC_DUI)):
    _b = _raw(_path)
    _crlf = _b.count(b'\r\n')
    _bare = _b.count(b'\n') - _crlf
    check(u'H4 %s：无 BOM / 无 U+FFFD / 全 CRLF（裸 LF = 0）' % _name,
          not _b.startswith(b'\xef\xbb\xbf') and u'\ufffd' not in _src
          and _bare == 0 and _crlf > 100,
          u'成立=%s' % (_bare == 0 and _crlf > 100,))

# =============================================== H5 结构自检
head(u'H5 结构自检：三条关键关系（顺序 / 前置 / 解耦）')


def _cls(tree, name):
    for n in ast.walk(tree):
        if isinstance(n, ast.ClassDef) and n.name == name:
            return n
    return None


def _m(cls, name):
    if cls is None:
        return None
    for n in cls.body:
        if isinstance(n, ast.FunctionDef) and n.name == name:
            return n
    return None


def _calls(fn, attr):
    out = []
    if fn is None:
        return out
    for c in ast.walk(fn):
        if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute) \
                and c.func.attr == attr:
            out.append(c)
    return out


_CLS = _cls(_parsed.get(u'main.py'), u'RalseiPet')
_UM = _m(_CLS, u'update_movement')
_r = _calls(_UM, u'_npc_roam_tick')
_e = _calls(_UM, u'_npc_errand_tick')
check(u'H5 `update_movement` 里 `_npc_errand_tick` 排在 `_npc_roam_tick` **之后**'
      u'（顺序即优先级）',
      len(_r) == 1 and len(_e) == 1 and _e[0].lineno > _r[0].lineno,
      u'成立=%s' % (len(_r) == 1 and len(_e) == 1,))

_ASG = _m(_CLS, u'assign_errand')
_g = _calls(_ASG, u'_npc_errand_gate')
_a = _calls(_ASG, u'assign')
check(u'H5b `assign_errand` 里门控在 `board.assign` **之前**',
      len(_g) == 1 and len(_a) == 1 and _g[0].lineno < _a[0].lineno,
      u'成立=%s' % (len(_g) == 1 and len(_a) == 1,))

_TREE_ERR = _parsed.get(u'npc_errand.py')
_disp = []
for _fn in ast.walk(_TREE_ERR) if _TREE_ERR is not None else []:
    if isinstance(_fn, ast.FunctionDef):
        for _c in ast.walk(_fn):
            if isinstance(_c, ast.Call) and isinstance(_c.func, ast.Attribute) \
                    and _c.func.attr in (u'switch', u'travel_to'):
                _disp.append(_c.func.attr)
check(u'H5c `npc_errand.py` **零处碰显示**（`switch` / `travel_to` 0 个）',
      _disp == [], u'零处=%s' % (_disp == [],))

# =============================================== H6 逐令牌回验
head(u'H6 逐令牌回验：新增的与**旧的**都逐个回验')
_NEW = [
    u'npc_errand', u'assign_errand', u'_npc_errand_gate', u'_npc_errand_tick',
    u'_npc_errand_commit', u'_npc_errand_load', u'_npc_errand_save',
    u'NPC_ERRAND_ENABLED', u'npc_errands.json', u'handle_errand_command',
    u'_errand_parse_intent',
]
_NEW_BAD = [t for t in _NEW if (t not in SRC_MAIN and t not in SRC_ERR)]
check(u'H6 本轮新增的 11 个令牌**逐个**都在主链路或机制层里',
      not _NEW_BAD, u'缺=%s' % (_NEW_BAD,))

_NS_TOK = [u'CHAPTER_ALIASES', u'chapter_names', u'same_chapter', u'chapter_matches']
_NS_BAD = [t for t in _NS_TOK if t not in SRC_NS]
check(u'H6b 章名归一的 4 个令牌在 `npc_system.py` 里逐个都在',
      not _NS_BAD, u'缺=%s' % (_NS_BAD,))

_OLD = [u'def _npc_roam_tick', u'def _npc_plan_save', u'def go_to_bed',
        u'self._bedtime_defer_logged', u'npc_plan_store_mod.save']
_OLD_BAD = [t for t in _OLD if SRC_MAIN.count(t) < 1]
check(u'H6c 旧令牌也逐个回验（差事没把自主移动/存档/就寝整条链挤掉）',
      not _OLD_BAD, u'缺=%s' % (_OLD_BAD,))
check(u'H6d `npc_system.py` 的 `world_gate` 与 `desktop_allowed` 仍在'
      u'（本轮只改了"怎么比章名"，没动门控本体）',
      u'def world_gate' in SRC_NS and u'def desktop_allowed' in SRC_NS,
      u'成立=%s' % (u'def world_gate' in SRC_NS,))

check(u'H6e 记忆：速查本已写「差事已落地」且索引里有 `150`',
      u'150 \u5dee\u4e8b' in SRC_MEM and u'check150' in SRC_MEM,
      u'成立=%s' % (u'150 \u5dee\u4e8b' in SRC_MEM,))
# ★ 速查本为腾体积把 `check143`/`check144` 从"锁号速查"里挪到了详版全表
#   ⇒ 逐令牌回验必须**去详版 `in` 一次**，不能只看速查本（否则等于静默丢信息）。
_DOWN = [u'check143', u'check144', u'143 \u8865\u70b9', u'144 \u51bb\u7ed3',
         u'check150', u'\u00a7150']
_DOWN_BAD = [t for t in _DOWN if t not in SRC_LONG]
check(u'H6f 从速查本下沉的令牌**在详版里逐个找得到**（下沉 ≠ 丢）',
      not _DOWN_BAD, u'缺=%s' % (_DOWN_BAD,))

# =============================================== H7 恒真判据复查
head(u'H7 恒真判据复查：检查"守人的判据"自己')
_TOOLS = [os.path.join(HERE, u'check150.py'), os.path.join(HERE, u'mutate150.py')]
_bad_true = []
for _p in _TOOLS:
    _t = ast.parse(_read(_p))
    for n in ast.walk(_t):
        if not isinstance(n, ast.Call):
            continue
        f = n.func
        nm = f.id if isinstance(f, ast.Name) else (f.attr if isinstance(f, ast.Attribute) else u'')
        if nm not in (u'check', u'ok', u'mutate'):
            continue
        # `check(desc, cond, …)` / `ok(cond, …)` / `mutate(tag, path, pairs, expect)`
        idx = 1 if nm in (u'check', u'ok') else 3
        if len(n.args) > idx and isinstance(n.args[idx], ast.Constant) \
                and n.args[idx].value is True:
            _bad_true.append((os.path.basename(_p), n.lineno))
check(u'H7 两套 harness（`check` / `mutate`）里 `..., True)` **0 处**',
      not _bad_true, u'%s' % (_bad_true,))

_MC = ast.parse(_read(_TOOLS[1]))
_finally = [n for n in ast.walk(_MC) if isinstance(n, ast.Try) and n.finalbody]
check(u'H7b `mutate150` 的"按字节还原"确实在 `finally` 里（中途抛异常也不留坏文件）',
      len(_finally) >= 1, u'成立=%s' % (len(_finally) >= 1,))

_C150 = ast.parse(_read(_TOOLS[0]))
_call_cnt = len([n for n in ast.walk(_C150)
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                 and n.func.id == u'check'])
check(u'H7c `check150` 的判据条数是**常量**（不随环境增减 ⇒ 换机器不会少数）',
      _call_cnt >= 100, u'过阈=%s' % (_call_cnt >= 100,))
# ★ 反面：`_run150` 里按输出解析的那一段不能把 `[FAIL]` 前缀写错，
#   否则 mutate 永远拿到空集合 ⇒ "恰好变红"变成"恰好没红"也绿。
check(u'H7d `mutate150` 解析失败行时用的是产品那套 `[FAIL] ` 前缀（写错=永久假绿）',
      u"u'[FAIL] '" in _read(_TOOLS[1]),
      u'成立=%s' % (u"u'[FAIL] '" in _read(_TOOLS[1]),))

# =============================================== H8 卫生
head(u'H8 卫生：临时产物 / 证据')
_bad = []
for d, _dirs, files in os.walk(ROUND):
    for fn in files:
        if fn.endswith((u'.pyc', u'.pyo', u'.bak', u'~')):
            _bad.append(os.path.join(d, fn))
check(u'H8 整轮目录**无** `.pyc/.bak/~`', not _bad, u'%s' % (_bad[:3],))
_EV = os.path.join(ROUND, u'_evidence')
check(u'H8b 本轮**没有** `_evidence/`（判据全是活跑，不存易变物）',
      not os.path.isdir(_EV), u'成立=%s' % (not os.path.isdir(_EV),))

print(u'')
print(u'=' * 78)
print(u'recheck150_core：PASS=%d FAIL=%d' % (_n_ok, _n_bad))
if _failed:
    print(u'失败项：')
    for _d in _failed:
        print(u'  - %s' % _d)
sys.exit(0 if _n_bad == 0 else 1)
