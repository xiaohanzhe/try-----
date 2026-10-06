# -*- coding: utf-8 -*-
u"""第94轮复检：改过"重要核心文件"后的逐项自证（可落盘，不是口头"改完了"）。

复检对象（本轮动过的文件）
--------------------------
  改：`ralsei_pet/modules/pet_ai.py`（睡眠守卫 A）
  改：`ralsei_pet/src/main.py`（自愈 B + 拖拽锚点 C；**CRLF**，只能字节级补丁）
  改：`code-quality-audit/regress/run_all.py`（SUITES 追加 check94；**CRLF**）
  改：`code-quality-audit/regress/baseline.json`（--only check94 --update 合并写入）
  新：`第94轮…/_tools/check94.py` · `_tools/mutate94.py`

六类判据（见 skill `core-file-recheck`）
----------------------------------------
  A 语法/可编译        —— 用 `ast.parse`（⚠️ 不用 `py_compile`：会产 `.pyc` 污染工作区）
  B 结构自检          —— check94 判据条数 / 段落标题 / 编号连续
  C 编码              —— 无 BOM · 无 U+FFFD · **行尾纯度**（CRLF 文件不许混裸 LF，反之亦然）
  D 恒真判据复查      —— `check(..., <常量>)` 一处都不许有；`_use_force` 不许有第二处赋值
  E 逐令牌回验        —— 报告里点名的每一串代码/数字，逐个回原文件 `in` 一次
  F 工作区干净        —— `git status --porcelain` 只允许出现本轮预期文件

★ 只读：不改任何被测状态（不用 py_compile、不写文件、不跑 App）。
"""
import ast
import hashlib
import importlib.util
import io
import json
import os
import re
import subprocess
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet', 'modules', 'pet_ai.py')
MAIN = os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py')
RUNALL = os.path.join(ROOT, 'code-quality-audit', 'regress', 'run_all.py')
BASELINE = os.path.join(ROOT, 'code-quality-audit', 'regress', 'baseline.json')
CK94 = os.path.join(HERE, 'check94.py')
MU94 = os.path.join(HERE, 'mutate94.py')
EV_CK94 = os.path.join(ROOT, 'code-quality-audit',
                       u'第94轮-基础宠物真机全功能验收', '_evidence', 'check94.txt')

_n = _ok = _bad = 0


def chk(desc, cond, detail=''):
    global _n, _ok, _bad
    _n += 1
    if cond:
        _ok += 1
        print(u'[PASS] %s%s' % (desc, (u'    ' + detail) if detail else u''))
    else:
        _bad += 1
        print(u'[FAIL] %s%s' % (desc, (u'    ' + detail) if detail else u''))


def b(path):
    with open(path, 'rb') as fh:
        return fh.read()


def t(path):
    return b(path).decode('utf-8')


print(u'=' * 78)
print(u'第94轮复检 —— 改过重要核心文件后的逐项自证')
print(u'ROOT = %s' % ROOT)
print(u'=' * 78)

# ============================================================ A 语法/可编译
print(u'')
print(u'---- A. 语法/可编译（ast.parse，不产 .pyc）----')
TARGETS = [(u'pet_ai.py', PET), (u'main.py', MAIN), (u'run_all.py', RUNALL),
           (u'baseline.json', BASELINE), (u'check94.py', CK94), (u'mutate94.py', MU94)]
for name, path in TARGETS:
    if not os.path.isfile(path):
        chk(u'A 存在：%s' % name, False, path)
        continue
    try:
        if name.endswith('.json'):
            json.loads(t(path))
        else:
            ast.parse(t(path))
        chk(u'A 语法 OK：%s' % name, True, u'%d B' % os.path.getsize(path))
    except Exception as e:
        chk(u'A 语法 OK：%s' % name, False, repr(e))

# ============================================================ B 结构自检
print(u'')
print(u'---- B. 结构自检 ----')
ck_tree = ast.parse(t(CK94))


def _str_arg(node):
    """取 `check(<标题>, …)` 的第一个参数（字符串字面量）。约束到 str，
    避免依赖已弃用的 `ast.Str`。"""
    if not node.args:
        return None
    a0 = node.args[0]
    if isinstance(a0, ast.Constant) and isinstance(a0.value, str):
        return a0.value
    return None


# `check(...)` 也可能出现在 if 体内 —— 全部计入（与运行时口径一致）
ck_calls = [n for n in ast.walk(ck_tree)
            if isinstance(n, ast.Call) and getattr(n.func, 'id', None) == 'check']
chk(u'B1 check94 判据条数 == 21（与文档头、与真机输出三方一致）',
    len(ck_calls) == 21, u'AST 实得 %d' % len(ck_calls))
_titles = [x for x in (_str_arg(c) for c in ck_calls) if x is not None]
_seg_letters = sorted({x[0] for x in _titles if re.match(u'^[ABCD]\\d', x)})
chk(u'B2 四段判据齐全（A pet_ai 守卫 / B 自愈 / C 拖拽锚点 / D 自检）',
    _seg_letters == [u'A', u'B', u'C', u'D'], u'段字母=%r' % (_seg_letters,))
_bad_num = [x for x in _titles if not re.match(u'^[ABCD]\\d', x)]
chk(u'B3 每条判据标题以「段字母+编号」开头（防标题粘连/漏编号）',
    not _bad_num, u'异常=%r' % (_bad_num[:3],))
chk(u'B4 没有空标题判据',
    len(_titles) == len(ck_calls) and all(x.strip() for x in _titles),
    u'取到标题 %d / 判据 %d' % (len(_titles), len(ck_calls)))
# mutate94 的变异条数
mu_tree = ast.parse(t(MU94))
_n_mut = None
for node in mu_tree.body:
    if isinstance(node, ast.Assign) and any(
            getattr(x, 'id', None) == 'MUTS' for x in node.targets):
        _n_mut = len(node.value.elts)
chk(u'B5 mutate94 变异条数 == 10（含 1 个 M0 负控制）', _n_mut == 10, u'实得 %r' % (_n_mut,))

# ============================================================ C 编码/行尾
print(u'')
print(u'---- C. 编码与行尾纯度 ----')
for name, path in TARGETS:
    raw = b(path)
    has_bom = raw.startswith(b'\xef\xbb\xbf')
    has_fffd = u'\ufffd' in raw.decode('utf-8', 'replace')
    chk(u'C 无 BOM 且无 U+FFFD：%s' % name, (not has_bom) and (not has_fffd),
        u'BOM=%s FFFD=%s' % (has_bom, has_fffd))

_C_EOL = [
    (u'main.py（必须 CRLF：本树检出形态）', MAIN, u'crlf'),
    (u'run_all.py（必须 CRLF）', RUNALL, u'crlf'),
    (u'baseline.json（必须 LF：run_all 用 newline=\'\\n\' 写）', BASELINE, u'lf'),
    (u'pet_ai.py（必须 LF）', PET, u'lf'),
    (u'check94.py（新文件，必须 LF）', CK94, u'lf'),
    (u'mutate94.py（新文件，必须 LF）', MU94, u'lf'),
]
for desc, path, want in _C_EOL:
    raw = b(path)
    crlf = raw.count(b'\r\n')
    bare = raw.count(b'\n') - crlf
    bad_cr = raw.count(b'\r') - crlf
    if want == u'crlf':
        good = (bare == 0) and (bad_cr == 0)
    else:
        good = (crlf == 0) and (bad_cr == 0)
    chk(u'C 行尾纯度：%s' % desc, good,
        u'CRLF=%d 裸LF=%d 裸CR=%d' % (crlf, bare, bad_cr))

# ============================================================ D 恒真判据复查
print(u'')
print(u'---- D. 恒真判据复查 ----')
_self = ast.parse(t(CK94))
_consts = []
for c in ck_calls:
    if len(c.args) >= 2 and isinstance(c.args[1], ast.Constant):
        _consts.append(ast.dump(c.args[1])[:40])
chk(u'D1 check94 里没有 `check(..., <常量>)` 的死判据（看着在守其实没守）',
    not _consts, u'常量判据=%r' % (_consts,))

main_text = t(MAIN)
_main_tree = ast.parse(main_text)
_u_node = None
for n in _main_tree.body:
    if isinstance(n, ast.ClassDef) and n.name == 'RalseiPet':
        for m in n.body:
            if isinstance(m, ast.FunctionDef) and m.name == 'update_animation':
                _u_node = m
_use_force_lines = []
if _u_node is not None:
    for nd in ast.walk(_u_node):
        if isinstance(nd, ast.Assign) and any(
                (isinstance(x, ast.Attribute) and x.attr == '_use_force')
                or (isinstance(x, ast.Name) and x.id == '_use_force')
                for x in nd.targets):
            _use_force_lines.append(nd.lineno)
chk(u'D2 `_use_force` 在 `update_animation` 内**恰一处**赋值（没有"改了两份只改一份"）',
    len(_use_force_lines) == 1, u'行号=%r' % (_use_force_lines,))

# 与 check94 证据互证：证据里打印的行号 == AST 现算的行号
_ev = t(EV_CK94) if os.path.isfile(EV_CK94) else u''
_m = re.search(r'抽出表达式（main\.py:(\d+)）', _ev)
chk(u'D3 逐证据互证：`_evidence/check94.txt` 里记的 `_use_force` 行号 == 现算行号',
    bool(_m) and bool(_use_force_lines) and int(_m.group(1)) == _use_force_lines[0],
    u'证据=%s 现算=%r' % (_m.group(1) if _m else None, _use_force_lines))

# check81 G5 那条自指判据的键集：baseline 套件集 == SUITES 集
ra = ast.parse(t(RUNALL))
_ids = []
for node in ra.body:
    if isinstance(node, ast.Assign) and any(
            getattr(x, 'id', None) == 'SUITES' for x in node.targets):
        for elt in node.value.elts:
            for k, v in zip(elt.keys, elt.values):
                if getattr(k, 'value', None) == 'id':
                    _ids.append(getattr(v, 'value', None))
_base = json.loads(t(BASELINE))
_bset = set(_base.get('suites', {}))
chk(u'D4 ★ check81 G5 的口径成立：SUITES 集 == 基线套件集（26 轮铁律：新套件必 --update）',
    set(_ids) == _bset, u'SUITES=%d baseline=%d 差集=%r'
    % (len(set(_ids)), len(_bset), sorted(set(_ids) ^ _bset)[:5]))
chk(u'D5 baseline 里 check94 是**真值**而非 `PENDING_UPDATE` 哨兵',
    _base['suites'].get('check94', {}).get('sha256', '') not in ('', 'PENDING_UPDATE'),
    u'sha=%s…' % _base['suites'].get('check94', {}).get('sha256', '')[:16])
chk(u'D6 baseline 里 check94 记的 pass == 21（与判据条数一致）',
    _base['suites'].get('check94', {}).get('pass') == 21,
    u'pass=%r' % (_base['suites'].get('check94', {}).get('pass'),))

# ============================================================ E 逐令牌回验
print(u'')
print(u'---- E. 逐令牌回验（报告/锁里点名的每一串，回原文件 in 一次）----')
PET_TEXT = t(PET)
RUNALL_TEXT = t(RUNALL)
TOKENS = [
    (u'pet_ai.py', PET_TEXT, u"if getattr(self.parent, 'is_sleeping', False):", 2,
     u'两处守卫（_skip_if_critical 返 True / trigger_action 返 None）'),
    (u'pet_ai.py', PET_TEXT, u'第94轮修复', 2, u'两处修复注释'),
    (u'main.py', main_text,
     u"_use_force = is_same_category or (new_animation in ('idle', 'sleep'))", 1,
     u'修复 B 的表达式原文'),
    (u'main.py', main_text,
     u'self.change_animation(new_animation, force=_use_force)', 1, u'force 真被消费'),
    (u'main.py', main_text, u'elif self.is_sleeping:', 2, u'第91轮那条睡眠分支'
     u'（★ 原文 2 次：1 处真代码 + 1 处在 L9775 **注释**里 —— 见下面 E-AST 两条）'),
    (u'main.py', main_text, u'new_animation = "sleep"', 2, u'睡眠分支赋值'
     u'（★ 原文 2 次：1 处真代码 + 1 处在 L9775 **注释**里 —— 见下面 E-AST 两条）'),
    (u'main.py', main_text, u"getattr(self, 'drag_position', None) is not None", 2,
     u'修复 C 的两处守卫后半句'),
    (u'main.py', main_text,
     u'from PyQt5.QtCore import Qt, QTimer, QPoint, QRect, pyqtSignal', 1, u'QPoint 真已导入'),
    (u'run_all.py', RUNALL_TEXT, u"'id': 'check94'", 1, u'SUITES 里真有 check94'),
    (u'baseline.json', t(BASELINE), u'"check94"', 1, u'基线里真有 check94'),
]
for fname, text, tok, want, note in TOKENS:
    got = text.count(tok)
    chk(u'E %s ×%d：%s' % (fname, want, note), got == want,
        u'实得 %d 次' % got)

# ★★ 两条**注释免疫**的 AST 回验（本项目铁律「能上 AST 就上 AST」）。
#    上面两条原文计数是 2 —— 因为 L9775 那条注释里**抄了**同一片段。
#    "真代码是否唯一"只能靠 AST 断；这正是 check94 的 B5 首版被判**恒真**的原因
#    （`mutate94` 的 M5 变异：删掉真代码后，正则仍被注释喂饱 ⇒ FAIL=0）。
#
# ⚠️ 口径必须与 `check94.B5` **一致**（限定在 `update_animation` 函数体内）。
#    全文件口径会数到 3 处 —— 另两处是**既有的、与本次修复无关**的正确睡眠感知点：
#      L6878  `update_behavior` 的「睡眠状态处理」（current_activity = "sleeping"）
#      L10127 `_can_speak_now()` 的「睡着时不开口」闸
#    （首版把口径写成全文件 ⇒ 假红。判据过宽/过窄都会误报。）
def _ifs_in(node):
    out = []
    for _nd in ast.walk(node):
        if isinstance(_nd, ast.If) and ast.unparse(_nd.test) == 'self.is_sleeping':
            out.append(_nd.lineno)
    return sorted(out)


_e_all = _ifs_in(_main_tree)
_e_in_u = _ifs_in(_u_node) if _u_node is not None else []
chk(u'E-AST 在 `update_animation` 内 `elif self.is_sleeping:` 恰 1 处'
    u'（与 check94 B5 同口径；注释天然不进 AST）',
    len(_e_in_u) == 1,
    u'函数内=%r；全文件 %d 处 %r（另两处为既有的正确睡眠感知点 L6878/L10127）'
    % (_e_in_u, len(_e_all), _e_all))
_e_asg_in_u = []
if _u_node is not None:
    for _nd in ast.walk(_u_node):
        if (isinstance(_nd, ast.Assign)
                and any(getattr(x, 'id', None) == 'new_animation' for x in _nd.targets)
                and ast.unparse(_nd.value) in ('"sleep"', "'sleep'")):
            _e_asg_in_u.append(_nd.lineno)
chk(u'E-AST 在 `update_animation` 内 `new_animation = "sleep"` 恰 1 处（同上）',
    len(_e_asg_in_u) == 1,
    u'函数内=%r（原文计数=%d）'
    % (_e_asg_in_u, main_text.count('new_animation = "sleep"')))

# 修复 C 的两条同步语句行号（与证据一致）
_sg = []
for nd in ast.walk(_main_tree):
    if isinstance(nd, ast.Call):
        s = ast.unparse(nd)
        if s.startswith('self.setGeometry(') and 'target_width' in s and 'target_height' in s:
            _sg.append(nd.lineno)
chk(u'E 两处渲染分支的 `setGeometry(…target_width…)` 都在（2 处）', len(_sg) == 2,
    u'行号=%r' % (sorted(_sg),))

# check94 的 sha 与基线一致（复现性：锁一旦固化就必须可复现）
try:
    spec = importlib.util.spec_from_file_location('_runall_for_recheck', RUNALL)
    _ra = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(_ra)
    _raw_out = io.open(os.path.join(ROOT, 'code-quality-audit', 'regress', '_out',
                                    'check94.txt'), encoding='utf-8').read()
    _sha = hashlib.sha256(_ra.normalize(_raw_out).encode('utf-8')).hexdigest()
    chk(u'E check94 归一化 sha == 基线 sha（用 run_all 自己的 normalize 复算）',
        _sha == _base['suites'].get('check94', {}).get('sha256'),
        u'now=%s… base=%s…' % (_sha[:16], _base['suites'].get('check94', {}).get('sha256', '')[:16]))
except Exception as e:
    chk(u'E check94 归一化 sha == 基线 sha', False, u'复算异常 %r' % (e,))

# ============================================================ F 工作区干净
print(u'')
print(u'---- F. 工作区 ----')
try:
    # ⚠️ `git status` 默认 `core.quotepath=true` ⇒ 非 ASCII 路径会被**引号 + 八进制转义**
    #    （`"code-quality-audit/\347\254\25494…"`），中文子串匹配必然落空。
    #    ⇒ 必须显式 `-c core.quotepath=false` 拿到可读路径（本轮实测踩过：F1 假红）。
    r = subprocess.run(['git', '-c', 'core.quotepath=false', 'status', '--porcelain'],
                       cwd=ROOT, capture_output=True, timeout=120)
    lines = [l for l in r.stdout.decode('utf-8', 'replace').splitlines() if l.strip()]
    ALLOW = (
        u'ralsei_pet/modules/pet_ai.py',
        u'ralsei_pet/src/main.py',
        u'code-quality-audit/regress/run_all.py',
        u'code-quality-audit/regress/baseline.json',
        u'code-quality-audit/第94轮-基础宠物真机全功能验收/',
        u'code-quality-audit/regress/_out/',
        # 上一窗口做 EOL 还原时重跑的 G2 输出（内容就是一次 G2 运行结果，
        # 刷新它属预期；见 `第94轮/_evidence/eol_rootcause_94.md` §4）。
        u'code-quality-audit/第93轮-基础宠物功能收口/_evidence/g2_after_revert_normalize.txt',
    )
    unexpected = [l for l in lines
                  if not any(a in l for a in ALLOW)]
    deleted = [l for l in lines if l[:2].strip() in ('D', 'AD')]
    print(u'    porcelain 共 %d 条；未预期 %d 条' % (len(lines), len(unexpected)))
    for l in unexpected[:8]:
        print(u'      ? %s' % l[:120])
    chk(u'F1 `git status --porcelain` 无未预期文件（本轮只该动 A 段白名单内的东西）',
        not unexpected, u'未预期=%r' % (unexpected[:5],))
    chk(u'F2 工作区无删除（防"临时/备份放进工作区被记成删除"）', not deleted,
        u'删除=%r' % (deleted[:5],))
    print(u'    本轮预期改动清单：')
    for l in lines:
        print(u'      %s' % l[:120])
except Exception as e:
    chk(u'F git status 可执行', False, repr(e))

print(u'')
print(u'=' * 78)
print(u'复检合计 %d 项：PASS=%d  FAIL=%d' % (_n, _ok, _bad))
print(u'=' * 78)
if _bad:
    print(u'（存在 FAIL ⇒ 本轮某项自证未过，不许宣称"改完了"。）')
sys.exit(0 if not _bad else 1)
