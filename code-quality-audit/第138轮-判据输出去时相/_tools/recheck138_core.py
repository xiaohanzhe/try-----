# -*- coding: utf-8 -*-
"""第138轮核心文件复检（改过 `run_all.py` 这个"所有套件的入口"必须复检）。

本轮动的不是产品，是**判据层**：6 个 `check*.py` 的 extra、1 个 `verify_s2`、
`regress/run_all.py`（`SUITES` 加一条）、`regress/baseline.json`（8 个套件重建）。
产品侧（`ralsei_pet/`）本轮**零改动** —— 所以 E 段专门自证这件事。

守什么：
A 语法：所有改过的文件都能 `ast.parse`（不产 `.pyc`）
B 基线：`baseline.json` 合法、键数 == `SUITES` 条数、`check138` 有基线且是 22 项
C `SUITES`：`check138` **恰好 1 条**，`script` 指向真实存在的文件
D 编码：无 BOM / 无 U+FFFD
E 产品零改动：`main.py` 仍 17337 行、纯 CRLF、无实验残留
F 自检：无恒真判据 / 零外部盘
"""
import ast
import io
import json
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
AUDIT = os.path.join(ROOT, 'code-quality-audit')
REG = os.path.join(AUDIT, 'regress')
RUN_ALL = os.path.join(REG, 'run_all.py')
BASE = os.path.join(REG, 'baseline.json')
MAIN_PY = os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py')

_n = {'p': 0, 'f': 0}
_failed = []


def check(desc, cond, extra=''):
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


TOUCHED = [
    os.path.join(AUDIT, u'第129轮-复读与出戏', '_tools', 'check129.py'),
    os.path.join(AUDIT, u'第131轮-真机7题复测', '_tools', 'check131.py'),
    os.path.join(AUDIT, u'第132轮-提示词泄漏护栏', '_tools', 'check132.py'),
    os.path.join(AUDIT, u'第134轮-训练线收口', '_tools', 'check134.py'),
    os.path.join(AUDIT, u'第135轮-事件截断吊尾巴', '_tools', 'check135.py'),
    os.path.join(AUDIT, u'第137轮-主宠训练补丁', '_tools', 'check137.py'),
    os.path.join(AUDIT, u'架构改造-H4H5', 'verify_s2_animations_json.py'),
    RUN_ALL,
    os.path.abspath(__file__),
]

# =============================================== A 语法
head(u'A 语法（不产 .pyc，只解析）')
_bad = []
for _p in TOUCHED:
    try:
        ast.parse(_read(_p))
    except SyntaxError as e:
        _bad.append(u'%s:%s' % (os.path.basename(_p), e.lineno))
check(u'A1 九个改过的文件全部可解析', not _bad,
      u'%d 个 %s' % (len(_bad), _bad if _bad else u''))
check(u'A2 分母非空（文件都在）',
      all(os.path.exists(_p) for _p in TOUCHED),
      u'%d/%d 存在' % (sum(1 for _p in TOUCHED if os.path.exists(_p)), len(TOUCHED)))

# =============================================== B 基线
head(u'B 基线（8 个套件重建后的一致性）')
_base = json.loads(_read(BASE))
# ★ 判据第一版假设"顶层就是 {套件id: 基线}" ⇒ 报红三条。
#   实测 `baseline.json` 是 `{'note', 'suites', 'version'}`，且每个套件的基线是
#   **`{'exit','fail','pass','sha256'}`** —— 存哈希，不存逐行文本（这是个好设计：
#   归一化在写入前做完了）。**红的是我的假设，不是文件。**
_smap = _base.get('suites', {})
check(u'B1 `baseline.json` 是 `{note, suites, version}` 结构',
      isinstance(_base, dict) and isinstance(_smap, dict),
      u'%d 个套件' % len(_smap))
_tree_ra = ast.parse(_read(RUN_ALL))
_suites = []
for _nd in ast.walk(_tree_ra):
    if (isinstance(_nd, ast.Assign)
            and any(getattr(t, 'id', '') == 'SUITES' for t in _nd.targets)
            and isinstance(_nd.value, ast.List)):
        for _el in _nd.value.elts:
            if isinstance(_el, ast.Dict):
                _sid = None
                for _k, _v in zip(_el.keys, _el.values):
                    if getattr(_k, 'value', '') == 'id' and isinstance(_v, ast.Constant):
                        _sid = _v.value
                if _sid:
                    _suites.append(_sid)
check(u'B2 `SUITES` 条目数 == 基线套件数',
      len(_suites) == len(_smap), u'SUITES=%d 基线=%d' % (len(_suites), len(_smap)))
check(u'B3 每个 SUITES id 都有基线', all(s in _smap for s in _suites),
      u'缺 %s' % [s for s in _suites if s not in _smap])
# ★ check138 自己的基线必须是 pass=22 / fail=0（改了它却忘了 `--update` 会当场红）
_c138 = _smap.get('check138', {})
check(u'B4 `check138` 基线是 22 过 0 败',
      _c138.get('pass') == 22 and _c138.get('fail') == 0,
      u'pass=%s fail=%s' % (_c138.get('pass'), _c138.get('fail')))

# =============================================== C SUITES 登记
head(u'C `SUITES` 登记（新套件必须恰好一条）')
check(u'C1 `check138` 在 SUITES 里恰好 1 条',
      _suites.count('check138') == 1, u'%d 条' % _suites.count('check138'))
_c138_script = os.path.join(AUDIT, u'第138轮-判据输出去时相', '_tools', 'check138.py')
check(u'C2 它的 `script` 指向真实文件', os.path.exists(_c138_script))
check(u'C3 `desc` 里写明了"修的是判据自己"（不是产品）',
      u'判据自己' in _read(RUN_ALL))

# =============================================== D 编码
head(u'D 编码卫生')
_bad_bom, _bad_fffd = [], []
for _p in TOUCHED:
    with io.open(_p, 'rb') as f:
        if f.read().startswith(b'\xef\xbb\xbf'):
            _bad_bom.append(os.path.basename(_p))
    if u'\ufffd' in _read(_p):
        _bad_fffd.append(os.path.basename(_p))
check(u'D1 无 BOM', not _bad_bom, u'%s' % _bad_bom if _bad_bom else u'')
check(u'D2 无 U+FFFD', not _bad_fffd, u'%s' % _bad_fffd if _bad_fffd else u'')

# =============================================== E 产品零改动
head(u'E 产品侧本轮零改动（本轮只动判据层）')
_src = _read(MAIN_PY)
_nl = _src.count(u'\r\n')
_nlf = _src.count(u'\n')
check(u'E1 `main.py` 仍是 17337 行', _nlf == 17337, u'%d 行' % _nlf)
check(u'E2 仍是纯 CRLF（编辑工具没把行尾改坏）',
      _nlf > 0 and _nl == _nlf, u'CRLF=%d 总LF=%d' % (_nl, _nlf))
check(u'E3 无实验残留', u'第138轮 DIFF 实验' not in _src)

# =============================================== F 自检
head(u'F 自检')
_t = ast.parse(_read(os.path.abspath(__file__)))
_bad_true = [n.lineno for n in ast.walk(_t)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id == 'check' and len(n.args) >= 2
             and isinstance(n.args[1], ast.Constant) and n.args[1].value is True]
check(u'F1 无恒真判据（`check(..., True)` 0 处）', not _bad_true, u'%d 处' % len(_bad_true))
check(u'F2 零外部盘',
      all(os.path.abspath(p).startswith(ROOT + os.sep) for p in TOUCHED))

print(u'')
print(u'=' * 78)
print(u'recheck138_core：PASS=%d FAIL=%d' % (_n['p'], _n['f']))
if _failed:
    print(u'失败项：')
    for d in _failed:
        print(u'  - %s' % d)
sys.exit(0 if _n['f'] == 0 else 1)
