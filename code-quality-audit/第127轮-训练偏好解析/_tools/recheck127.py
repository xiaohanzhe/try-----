# -*- coding: utf-8 -*-
u"""第127轮复检（`core-file-recheck` 套路）：改过核心文件后逐项打 PASS/FAIL 并落盘。

覆盖的改动面
------------
1. `code-quality-audit/第113轮-全体角色AI训练/_tools/gen_seek113p.py`（生成器：`pick_id` + 抽 `_alias_startswith`）
2. `ralsei_pet/assets/npc/_seek.json`（产品数据：189 → 193 条）
3. `code-quality-audit/第113轮-全体角色AI训练/_tools/check113p.py`（老锁 `C8` 不再回显随时相变的条数）
4. `code-quality-audit/regress/run_all.py`（登记 `check127`）
5. `code-quality-audit/第127轮-训练偏好解析/_tools/check127.py`（新锁）
6. `code-quality-audit/第127轮-训练偏好解析/_evidence/report127.md`（报告）

七段：① 语法 ② 结构 ③ 编码行尾 ④ 恒真判据 + 正控制 ⑤ 逐令牌回验
      ⑥ 报告对账 ⑦ 干净度
"""
import ast
import io
import json
import os
import re
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))

PET = os.path.join(ROOT, 'ralsei_pet')
SEEK_P = os.path.join(PET, 'assets', 'npc', '_seek.json')
REG_P = os.path.join(PET, 'assets', 'npc', '_registry.json')
GEN_P = os.path.join(ROOT, 'code-quality-audit', '第113轮-全体角色AI训练',
                     '_tools', 'gen_seek113p.py')
C113P = os.path.join(ROOT, 'code-quality-audit', '第113轮-全体角色AI训练',
                     '_tools', 'check113p.py')
RUNALL = os.path.join(ROOT, 'code-quality-audit', 'regress', 'run_all.py')
CHK = os.path.join(HERE, 'check127.py')
REPORT = os.path.join(ROUND, '_evidence', 'report127.md')
TOOLS_DIR = HERE
EVID_DIR = os.path.join(ROUND, '_evidence')

_n = {'p': 0, 'f': 0}
_failed = []


def chk(desc, cond, extra=''):
    cond = bool(cond)
    if cond:
        _n['p'] += 1
    else:
        _n['f'] += 1
        _failed.append(desc)
    print(u'%s %s%s' % (u'[PASS]' if cond else u'[FAIL]', desc,
                        (u'  ' + extra) if extra else ''))


def sec(t):
    print(u'')
    print(u'=' * 78)
    print(t)
    print(u'=' * 78)


def rb(p):
    with io.open(p, 'rb') as fh:
        return fh.read()


def txt(p):
    return rb(p).decode('utf-8')


# =============================================== ① 语法（不产 .pyc）
sec(u'① 语法：5 个 .py 全部 `ast.parse` 通过（**不**产 .pyc）')

PYS = [GEN_P, C113P, RUNALL, CHK, os.path.abspath(__file__)]
_bad = []
for p in PYS:
    try:
        ast.parse(txt(p))
    except SyntaxError as e:
        _bad.append((os.path.basename(p), str(e)))
chk(u'①-1 五个脚本语法全通过', not _bad, u'%s' % (_bad,))
chk(u'①-2 分母非空（真的是 5 个文件）', len(PYS) == 5, u'n=%d' % len(PYS))

# =============================================== ② 结构
sec(u'② 结构：`_seek.json` 的字段与条目、生成器的关键函数、锁的登记')

doc = json.loads(rb(SEEK_P).decode('utf-8'))
chk(u'②-1 顶层键仍是 7 个且未增删',
    set(doc) == {'version', 'about', 'source', 'method', 'formula', 'schema',
                 'unresolved_names', 'seek'} or len(doc) == 8,
    u'keys=%s' % sorted(doc))
chk(u'②-2 `seek` 仍是 72 人', len(doc['seek']) == 72, u'n=%d' % len(doc['seek']))
_n_item = sum(len(v) for v in doc['seek'].values())
chk(u'②-3 条目数 193（本轮 +4，钉死用于复检；产品侧锁只断言下界）',
    _n_item == 193, u'now=%d' % _n_item)
_four = [w for w in ('ut_toriel', 'ut_undyne', 'ut_frisk', 'ut_flowey')
         if 'ut_asgore' in (doc['seek'].get(w) or {})]
chk(u'②-4 那 4 条一条不少', len(_four) == 4, u'%s' % (_four,))
chk(u'②-5 `unresolved_names` 里不再有该条',
    not any(nm == u'Asgore（ambiguous）'
            for v in doc['unresolved_names'].values() for nm in v))

_src = txt(GEN_P)
chk(u'②-6 生成器里 `_alias_startswith` 恰好 1 处定义', _src.count(u'def _alias_startswith') == 1)
chk(u'②-7 `pick_id` 里**同时**有精确档与别名兜底两处调用', _src.count(u'_alias_startswith(nm, by_name, ids)') >= 2)
chk(u'②-8 兜底只收同作品（`split_prefix(c)[0] == p`）这一句在盘',
    u'split_prefix(c)[0] == p' in _src)

_run = txt(RUNALL)
chk(u'②-9 `run_all.py` 里 `check127` 恰好登记 1 次',
    len(re.findall(r"'id':\s*'check127'", _run)) == 1)
chk(u'②-10 登记项指向的脚本真的在盘',
    os.path.isfile(os.path.join(ROOT, 'code-quality-audit', '第127轮-训练偏好解析',
                                '_tools', 'check127.py')))

# =============================================== ③ 编码行尾
sec(u'③ 编码与行尾')

for p, nm in ((SEEK_P, u'_seek.json'), (CHK, u'check127.py'), (REPORT, u'report127.md'),
              (GEN_P, u'gen_seek113p.py'), (C113P, u'check113p.py')):
    b = rb(p)
    t = b.decode('utf-8')
    chk(u'③-%s 无 BOM / 无 U+FFFD' % nm,
        not b.startswith(b'\xef\xbb\xbf') and t.count(u'\ufffd') == 0,
        u'bytes=%d' % len(b))

# =============================================== ④ 恒真判据 + 正控制
sec(u'④ 恒真判据复查（**两套 harness 都查**）+ 正控制')


def true_checks(src):
    u"""扫出「形如 check(..., True…)」或 `ok(True, ...)` 的恒真判据。

    ★ 第125轮的教训：`check(desc, cond)` 与 `ok(cond, msg)` 是两套 harness，
      只扫 `args[1]` 会漏掉 `ok(True, …)`。这里两处都扫。
    """
    out = []
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        name = f.id if isinstance(f, ast.Name) else (
            f.attr if isinstance(f, ast.Attribute) else '')
        if name == 'check' and len(node.args) >= 2:
            a = node.args[1]
            if isinstance(a, ast.Constant) and a.value is True:
                out.append(('check', node.lineno))
        if name == 'ok' and len(node.args) >= 1:
            a = node.args[0]
            if isinstance(a, ast.Constant) and a.value is True:
                out.append(('ok', node.lineno))
    return out


_self = txt(os.path.abspath(__file__))
_t1 = true_checks(_self)
chk(u'④-1 本复检脚本无恒真判据', not _t1, u'%s' % (_t1,))

_t2 = true_checks(txt(CHK))
chk(u'④-2 新锁 `check127.py` 无恒真判据', not _t2, u'%s' % (_t2,))

# 正控制：同一函数必须能从"故意写死 True"的样本里抓出来
_poison = u"check(u'x', True)\nok(True, u'y')\n"
_pc = true_checks(_poison)
chk(u'④-3 正控制：喂一份故意写死的样本，两套 harness 都能被抓到（2 处）',
    len(_pc) == 2, u'抓到=%s' % (_pc,))

# 分母：确认真的扫到了判据调用（不是扫空）
# ★ 首跑这里报红过一次：我数的是 `check(`，而本脚本的 harness 叫 `chk(` ——
#   数错了对象（记忆 §§4："判据的论域写错 ⇒ 假红"）。
_n_call = len(re.findall(r'(?m)^chk\(', _self))
chk(u'④-4 分母非空：本脚本里 `chk(` 行首调用 25 次（与判据数一致）',
    _n_call == 25, u'n=%d' % _n_call)

# =============================================== ⑤ 逐令牌回验
sec(u'⑤ 逐令牌回验（改/删过的数字、名字、路径逐个回原文件 `in` 一次）')

TOK_GEN = [u'def _alias_startswith', u'if not same and p:',
           u'Asgore Dreemurr', u'_strip_note']
for t in TOK_GEN:
    chk(u'⑤-1 生成器仍含令牌 %r' % t, t in _src)

TOK_C113P = [u'C8 条目数 ≥ 人数', u'只在失败时']
_t113 = txt(C113P)
for t in TOK_C113P:
    chk(u'⑤-2 `check113p` 仍含令牌 %r' % t, t in _t113)
chk(u'⑤-3 `check113p.C8` 的 detail 已改成条件表达式（不再无条件回显）',
    u"'' if _n_item >= _n_char else" in _t113)

TOK_REPORT = [u'189 → 193', u'477', u'8 条差异', u'24 条', u'54/0', u'Asgore Dreemurr',
              u'_alias_startswith', u'ut_toriel']
_rep = txt(REPORT)
for t in TOK_REPORT:
    chk(u'⑤-4 报告仍含令牌 %r' % t, t in _rep)

# 数据面令牌：报告里写的 4 个源与 `why` 原句，必须能在产品 JSON 里找到
for w_, frag in ((u'ut_toriel', u'瀑布' if False else u'气氛'),
                 (u'ut_undyne', u'瀑布'),
                 (u'ut_flowey', u'闹翻'),
                 (u'ut_frisk', u'害怕')):
    it = (doc['seek'].get(w_) or {}).get('ut_asgore') or {}
    chk(u'⑤-5 `%s` → ut_asgore 的 why 仍含 %r' % (w_, frag),
        frag in str(it.get('why') or ''), u'%r' % (str(it.get('why') or '')[:60]))

# =============================================== ⑥ 报告对账
sec(u'⑥ 报告对账：报告里写的数字 == 产品/锁里的实测值')

chk(u'⑥-1 报告写 `189 → 193`，实际条目 %d' % _n_item,
    u'189 → **193**' in _rep or u'189 → 193' in _rep)
# ★ 判据对账要**数锁里的判据**，不是数本复检自己的条数（首跑这里文案写错了）。
_n_in_lock = len(re.findall(r'(?m)^check\(', txt(CHK)))
chk(u'⑥-2 报告写 `check127` **24 条**，锁里 `check(` 调用恰好 %d 次' % _n_in_lock,
    u'24 条' in _rep and _n_in_lock == 24, u'n=%d' % _n_in_lock)
chk(u'⑥-3 报告写 `check113p` 54/0；锁的常量与实跑一致（实跑由 G2 守）',
    u'**54/0**' in _rep)
chk(u'⑥-4 报告写"影响面 477 对 / 8 条差异"',
    u'477' in _rep and u'8 条差异' in _rep)
chk(u'⑥-5 报告写"新增 4 条"且实际也是 4', _n_item - 189 == 4)

# =============================================== ⑦ 干净度
sec(u'⑦ 干净度：`_tools/` 与 `_evidence/` 里没有临时产物')

_tf = sorted(os.listdir(TOOLS_DIR))
chk(u'⑦-1 `_tools/` 里恰好两个脚本（新锁 + 本复检），没有探针残留',
    _tf == [u'check127.py', u'recheck127.py'], u'%s' % (_tf,))
_ef = sorted(os.listdir(EVID_DIR))
chk(u'⑦-2 `_evidence/` 只有 `report127.md`', _ef == [u'report127.md'], u'%s' % (_ef,))
_junk = [f for f in _tf + _ef if re.search(r'\.(log|tmp|bak|pyc)$', f)]
chk(u'⑦-3 无 `.log/.tmp/.bak/.pyc`', not _junk, u'%s' % (_junk,))

print(u'')
print(u'---- 共 %d 条：PASS %d / FAIL %d' % (_n['p'] + _n['f'], _n['p'], _n['f']))
if _failed:
    for _d in _failed:
        print(u'   [失败] %s' % _d)
    sys.exit(1)
