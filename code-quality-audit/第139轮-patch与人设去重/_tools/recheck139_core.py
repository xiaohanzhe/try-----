# -*- coding: utf-8 -*-
"""第139轮 · 改过核心文件后的复检（可落盘、逐项 PASS/FAIL）。

## 这一轮动到的"核心文件"

| 文件 | 动了什么 | 为什么算核心 |
|---|---|---|
| `assets/npc/_training/_index.json` | `patches["ralsei"]` 与 `cards["ralsei"]["patch"]` 各去掉 ① | 96 位角色的训练产物总索引，`training_patch()` 只读它 |
| `assets/npc/_training/cards/ralsei.json` | 同上（第三份副本） | `build_card()` 每次重建都会重写它 |
| `立../第137轮/.../check137.py` | A1 翻面 + 4 处 extra 去时相量 | 回归锁 |
| `regress/run_all.py` | 登记 `check139`、改 `check137` 的 desc | 回归总闸 |

## 复检的六件事（用户口径：改过核心文件必须复检）

① 语法可解析（★ 用 `ast.parse`，**不用 `py_compile`** —— 后者会产 `.pyc`，
   而复检**不许改变被测状态**）
② 结构自检（JSON 顶层键没多没少、条数没变、三份副本一致）
③ 无 BOM / 无 U+FFFD
④ **恒真判据复查**（`check(..., True)` 这类"看着在守其实没守"的写法）
⑤ **逐令牌回验**（本轮删/改过的每个可检索令牌，逐个回原文件 `in` 一次）
⑥ 工作区干净 + 产品零改动（本轮**一行产品代码都没动**）
"""
import ast
import io
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
TRAIN = os.path.join(PET, 'assets', 'npc', '_training')
INDEX_JSON = os.path.join(TRAIN, '_index.json')
CARD_JSON = os.path.join(TRAIN, 'cards', 'ralsei.json')
PERSONA_PY = os.path.join(PET, 'assets', 'ralsei_persona.md')
MAIN_PY = os.path.join(PET, 'src', 'main.py')
CHECK139 = os.path.join(HERE, 'check139.py')
PROBE139 = os.path.join(HERE, 'probe139_ab.py')
MUTATE139 = os.path.join(HERE, 'mutate139.py')
CHECK137 = os.path.join(ROOT, 'code-quality-audit', u'第137轮-主宠训练补丁', '_tools', 'check137.py')
RUN_ALL = os.path.join(ROOT, 'code-quality-audit', 'regress', 'run_all.py')
REPORT = os.path.join(ROUND, u'_evidence', 'report139.md')

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


PY_FILES = [CHECK139, PROBE139, MUTATE139, CHECK137, RUN_ALL]
JSON_FILES = [INDEX_JSON, CARD_JSON]

# =============================================== A 语法
head(u'A. 语法可解析（ast.parse，不产 .pyc）')

for _p in PY_FILES:
    _ok = True
    _err = ''
    try:
        ast.parse(_read(_p))
    except SyntaxError as e:
        _ok = False
        _err = str(e)
    ok(u'A %s 可解析' % os.path.basename(_p), _ok, _err)

# =============================================== B 结构
head(u'B. 结构自检（键、条数、三份副本）')

_idx = json.loads(_read(INDEX_JSON))
_card = json.loads(_read(CARD_JSON))
_keys = ['schema_version', 'model', 'built_from', 'counts', 'gaps', 'cards', 'patches', 'trained']
ok(u'B1 `_index.json` 顶层键一个不多一个不少（没塞新字段）',
   list(_idx.keys()) == _keys, u'%d 个' % len(_idx.keys()))
_cnt = _idx.get('counts') or {}
ok(u'B2 `counts` 四个记账字段一个没变，且总数 = cards 条数 = persona+canned+gap',
   _cnt.get('total') == 96 and _cnt.get('persona') == 77
   and _cnt.get('canned') == 18 and _cnt.get('gap') == 1
   and _cnt.get('total') == len(_idx.get('cards') or {})
   and _cnt.get('persona', 0) + _cnt.get('canned', 0) + _cnt.get('gap', 0) == _cnt.get('total'),
   u'total=%s cards=%d' % (_cnt.get('total'), len(_idx.get('cards') or {})))
ok(u'B3 `patches` 仍是 59 条（去重不是增删角色）', len(_idx.get('patches') or {}) == 59)
ok(u'B4 `cards`（索引里的摘要）仍是 96 条', len(_idx.get('cards') or {}) == 96)
ok(u'B5 `cards/ralsei.json` 里的 id 仍是 ralsei', _card.get('id') == 'ralsei')

_p_idx = (_idx.get('patches') or {}).get('ralsei') or u''
_p_ic = (((_idx.get('cards') or {}).get('ralsei')) or {}).get('patch') or u''
_p_cf = _card.get('patch') or u''
ok(u'B6 三份副本逐字相同（patches / index.cards / cards/*.json）',
   _p_idx == _p_ic == _p_cf)

# =============================================== C 去重本身
head(u'C. 去重本身：删了哪句、留下哪些')

ok(u'C1 `patches["ralsei"]` 不含 ①（「两三句」/「随口说」）',
   (u'两三句' not in _p_idx) and (u'随口说' not in _p_idx))
ok(u'C2 ②③ 与实测例都在（去重不许顺手删真缺口）',
   all(x in _p_idx for x in (u'只认得原作里真有的名字', u'不要自己造人名', u'凯斯恩')))
ok(u'C3 persona 的「一次只说 1~3 句」还在（规格的人文本）', u'一次只说 1~3 句' in _read(PERSONA_PY))
ok(u'C4 `length_policy` 仍是 200 / 3（规格的机器可读那份）',
   (_card.get('length_policy') or {}).get('max_chars') == 200
   and (_card.get('length_policy') or {}).get('max_sentences') == 3)

# =============================================== D 编码
head(u'D. 无 BOM / 无 U+FFFD')

for _p in PY_FILES + JSON_FILES:
    _raw = io.open(_p, 'rb').read()
    _bom = _raw.startswith(b'\xef\xbb\xbf')
    _fffd = u'\ufffd' in _raw.decode('utf-8', 'replace')
    ok(u'D %s 无 BOM 且无 U+FFFD' % os.path.basename(_p), (not _bom) and (not _fffd),
       u'BOM=%s FFFD=%s' % (_bom, _fffd))

# =============================================== E 恒真判据复查
head(u'E. 恒真判据复查（`check(..., True)` / 判据条数）')

# ★ 两套 harness：`check(desc, cond, extra)` 与 `ok(desc, cond, extra)`。
#   本文件用的是 `ok(...)`，check139/check137 用的是 `check(...)` —— **两处都要看**。
for _p, _fn in ((CHECK139, 'check'), (CHECK137, 'check'), (os.path.abspath(__file__), 'ok')):
    _t = ast.parse(_read(_p))
    _bad = [n.lineno for n in ast.walk(_t)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
            and n.func.id == _fn and len(n.args) >= 2
            and isinstance(n.args[1], ast.Constant) and n.args[1].value is True]
    ok(u'E %s 里 `%s(..., True)` 0 处' % (os.path.basename(_p), _fn), not _bad,
       u'%d 处' % len(_bad))

_t139 = ast.parse(_read(CHECK139))
_n139 = sum(1 for n in ast.walk(_t139) if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name) and n.func.id == 'check')
ok(u'E4 `check139` 的判据条数仍是 38（与基线一致；改了就该重新 --update）',
   _n139 == 38, u'%d 条' % _n139)

# =============================================== F 逐令牌回验
head(u'F. 逐令牌回验（本轮删/改过的令牌，逐个回原文件 `in` 一次）')

_persona = _read(PERSONA_PY)
_tokens = [
    (u'一次只说 1~3 句', _persona, u'persona：句数规格（没被一起删）'),
    (u'像真人在聊天框里随手打字', _persona, u'persona：语气规格'),
    (u'只认得原作里真有的名字', _p_idx, u'patch：名字白名单'),
    (u'不要自己造人名', _p_idx, u'patch：造人名'),
    (u'凯斯恩', _p_idx, u'patch：实测例'),
    (u'拿不准名字的时候', _p_idx, u'patch：退回说法'),
    (u'max_sentences', _read(CARD_JSON), u'card：机器可读规格'),
    (u'length_policy', _read(CARD_JSON), u'card：规格键名'),
    (u'check139', _read(RUN_ALL), u'run_all：新套件已登记'),
    (u'第139轮-patch与人设去重', _read(RUN_ALL), u'run_all：脚本路径'),
]
for _tok, _blob, _why in _tokens:
    ok(u'F 「%s」仍在（%s）' % (_tok[:12], _why), _tok in _blob)

# =============================================== G 产品零改动
head(u'G. 产品零改动（本轮只动数据与判据）')

_r = subprocess.run(['git', 'status', '--porcelain'], cwd=ROOT, capture_output=True)
_por = _r.stdout.decode('utf-8', 'surrogateescape')
_touched_src = [ln for ln in _por.splitlines()
                if 'ralsei_pet/src/' in ln or 'ralsei_pet/modules/' in ln]
ok(u'G1 `ralsei_pet/src/` 与 `modules/` 一个文件都没改', not _touched_src,
   u'%d 个' % len(_touched_src))

_main_raw = io.open(MAIN_PY, 'rb').read()
_n_crlf = _main_raw.count(b'\r\n')
_n_lf = _main_raw.count(b'\n')
ok(u'G2 `main.py` 仍是 17337 行、CRLF 17337 / 裸 LF 0（没被工具改写行尾）',
   _main_raw.count(b'\n') == 17337 and _n_crlf == 17337 and (_n_lf - _n_crlf) == 0,
   u'行=%d CRLF=%d 裸LF=%d' % (_n_lf, _n_crlf, _n_lf - _n_crlf))
ok(u'G3 `_with_ralsei_patch` 的拼法没变（persona + 空行 + 标题 + 换行 + patch）',
   u"return base + '\\n\\n' + PATCH_HEADER_RALSEI + '\\n' + patch" in _read(MAIN_PY))
ok(u'G4 报告已落盘', os.path.isfile(REPORT))

# =============================================== H 自检
head(u'H. 本文件自检')

_raw_self = io.open(os.path.abspath(__file__), 'rb').read()
ok(u'H1 无 BOM', not _raw_self.startswith(b'\xef\xbb\xbf'))
ok(u'H2 零外部盘（读的文件全在仓库内）',
   all(os.path.abspath(p).startswith(ROOT + os.sep) for p in PY_FILES + JSON_FILES + [MAIN_PY, REPORT]))
# ★ H3 用 AST 判"本文件有没有写盘"：查所有 `open(...)` 调用的第 2 个实参里有没有 'w'。
#   不用纯文本扫 —— 那样一提这个写法就误报（"禁某 API 出现"类判据的老坑）。
_w_open = []
for _node in ast.walk(ast.parse(_read(os.path.abspath(__file__)))):
    if isinstance(_node, ast.Call) and isinstance(_node.func, ast.Attribute) \
            and _node.func.attr == 'open':
        for _a in _node.args[1:]:
            if isinstance(_a, ast.Constant) and isinstance(_a.value, str) and 'w' in _a.value:
                _w_open.append(_node.lineno)
ok(u'H3 本文件只读不写（没有任何 `open(..., "w")`）', not _w_open,
   u'%d 处' % len(_w_open))

print(u'')
print(u'=' * 78)
print(u'recheck139_core：PASS=%d FAIL=%d' % (_n['p'], _n['f']))
if _failed:
    print(u'失败项：')
    for d in _failed:
        print(u'  - %s' % d)
sys.exit(0 if _n['f'] == 0 else 1)
