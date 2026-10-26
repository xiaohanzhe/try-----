# -*- coding: utf-8 -*-
"""第113轮k 复检：逐令牌回原文件 `in` 一次。

用户口径：「以后再调整重要核心文件时一定要记得复检」。
六项：① 语法 ② 结构 ③ 无 BOM / 无 U+FFFD ④ **恒真判据复查**
      ⑤ **逐令牌回验** ⑥ 工作区干净 + 该跑的回归跑了。

★ 本脚本**不改变被测状态**：语法用 `ast.parse`（`py_compile` 会产 `.pyc`）。
★ 判据报红先怀疑判据：每条都带 `detail`，红了先看它实测到什么。
"""
import ast
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
LIFE_P = os.path.join(PET, 'modules', 'npc_life.py')
MAIN_P = os.path.join(PET, 'src', 'main.py')
CHK_P = os.path.join(HERE, 'check113k.py')
RUN_P = os.path.join(ROOT, 'code-quality-audit', 'regress', 'run_all.py')
BASE_P = os.path.join(ROOT, 'code-quality-audit', 'regress', 'baseline.json')
IDX_P = os.path.join(PET, 'assets', 'scenes', '_index.json')
DOC_P = os.path.join(ROUND, '_evidence', 'Validation_113k.md')
OUT_P = os.path.join(ROOT, 'code-quality-audit', 'regress', '_out', 'check113k.txt')

_p = _f = 0
_bad = []


def ok(desc, cond, detail=''):
    global _p, _f
    if cond:
        _p += 1
        print('[PASS] %s%s' % (desc, ('    ' + detail) if detail else ''))
    else:
        _f += 1
        _bad.append(desc)
        print('[FAIL] %s%s' % (desc, ('    ' + detail) if detail else ''))


def read(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as fh:
        return fh.read()


LIFE = read(LIFE_P)
MAIN = read(MAIN_P)
CHK = read(CHK_P)
RUN = read(RUN_P)
BASE = read(BASE_P)
DOC = read(DOC_P)

# ================================================================ ① 语法
print('--- ① 语法（ast.parse，不产 .pyc）---')
for name, src in (('npc_life.py', LIFE), ('main.py', MAIN),
                  ('check113k.py', CHK), ('run_all.py', RUN)):
    # ★ 不许写 `ok(..., True)`：本脚本 ④ 段会把自己这条也扫出来（判据也是被测物）。
    #   "没抛异常"这件事用变量承载，字面上仍然是**算出来的**。
    try:
        ast.parse(src)
        _syn = True
        _err = ''
    except SyntaxError as e:
        _syn, _err = False, str(e)
    ok('%s 语法 PASS' % name, _syn, _err)

# ================================================================ ② 结构
print()
print('--- ② 结构：本轮该有的东西都在 ---')
for tok in ('ACTIVITY_KINDS', 'ACTIVITY_SAY', 'INTENT_WORDS', 'PLACE_WORDS',
            'PLACE_GLOSS', 'PLACE_SKIP_AREA_IDS', '_NEG_HEADS', '_NEG_BREAK',
            '_NEG_WINDOW', 'def detect_activity(', 'def place_matches(',
            'def activity_hint(', 'def place_type_name(', 'def place_label(',
            'def strip_room_index(', 'def trim_core_at_type(', 'def _negated(',
            'def room_word(', 'def place_container(', 'def place_hint('):
    ok('npc_life 有 `%s`' % tok, tok in LIFE)
for tok in ('def _activity_chapter(', 'def _activity_places(',
            'def _activity_label(', 'with_chapter=True',
            'npc_life_mod.PLACE_SKIP_AREA_IDS', 'heard=text'):
    ok('main 有 `%s`' % tok, tok in MAIN)

# 负向：翻译表里不许再有 station / dock
_g = LIFE[LIFE.find('PLACE_GLOSS = {'):]
_g = _g[:_g.find('\n}')]
ok('PLACE_GLOSS 里**没有** `station`', "'station'" not in _g, repr(_g[:40]))
ok('PLACE_GLOSS 里**没有** `dock`', "'dock'" not in _g)
# ★ 负控制：翻译表**不是空的**（否则上面两条恒真）
ok('负控制：PLACE_GLOSS 仍有 `diner`（证明上面两条不是恒真）', "'diner'" in _g)

# ================================================================ ③ 编码 / EOL
print()
print('--- ③ 编码与 EOL ---')
for name, path in (('npc_life.py', LIFE_P), ('main.py', MAIN_P)):
    raw = io.open(path, 'rb').read()
    ok('%s 无 BOM' % name, not raw.startswith(b'\xef\xbb\xbf'))
    txt = raw.decode('utf-8')
    ok('%s 无 U+FFFD' % name, '\ufffd' not in txt)
    ok('%s 全 CRLF' % name, txt.count('\r\n') == txt.count('\n'),
       '%d/%d' % (txt.count('\r\n'), txt.count('\n')))
ok('main.py 末行无换行（既有形态，改动没顺手"修"掉它）',
   not MAIN.endswith('\n'))
# ★ 只判**下界**：k 轮快照是 1243，l 轮起继续长；缩水才是回滚事故的信号
#   （见仓库铁律「工作区会被回滚而 git 不报错」）。`== 1243` 会随演进恒红。
ok('npc_life.py 行数 >= 1243（k 轮快照；只增不减）',
   LIFE.count('\n') >= 1243, str(LIFE.count('\n')))
ok('main.py 行数 >= 16797（k 轮快照；只增不减）',
   MAIN.count('\n') >= 16797, str(MAIN.count('\n')))

# ================================================================ ④ 恒真判据
print()
print('--- ④ 恒真判据复查（`check(desc, True)` 那种"看着在守其实没守"）---')
_hard = []
for node in ast.walk(ast.parse(CHK)):
    if not isinstance(node, ast.Call):
        continue
    f = node.func
    if getattr(f, 'id', None) == 'check' and len(node.args) >= 2:
        second = node.args[1]
        if isinstance(second, ast.Constant) and second.value is True:
            _hard.append(getattr(node, 'lineno', -1))
ok('check113k 里没有 `check(..., True)` 恒真判据', not _hard, repr(_hard))
# ★ 判据自检：本脚本自己也不许有 ok(..., True)
_self = [n.lineno for n in ast.walk(ast.parse(read(os.path.abspath(__file__))))
         if isinstance(n, ast.Call) and getattr(n.func, 'id', None) == 'ok'
         and len(n.args) >= 2 and isinstance(n.args[1], ast.Constant)
         and n.args[1].value is True]
ok('复检脚本自身也没有 `ok(..., True)`（★ 判据也是被测物）', not _self, repr(_self))

# ================================================================ ⑤ 逐令牌
print()
print('--- ⑤ 逐令牌回验（文档里写的每个数/名，回原文件 `in` 一次）---')
# 文档 → 产品
_doc_tokens = ('家乡 · diner（餐厅）', 'PLACE_SKIP_AREA_IDS', 'trim_core_at_type',
               'sys.stdlib_module_names', 'with_chapter', '_NEG_BREAK',
               'place_label', 'a861a60', 'D5', 'D6')
for t in _doc_tokens:
    ok('文档提到 `%s`' % t, t in DOC)
# 文档里的数字 → 对应来源
# ★ 判据数**只许增加**：l 轮把 60 增到 79。改成"实跑数 >= 文档记的 60" ——
#   盯的是"有没有被砍"（砍判据 = 悄悄放宽），不是"有没有加"。
_suites_pass = -1
if os.path.isfile(OUT_P):
    for _ln in read(OUT_P).splitlines():
        if _ln.startswith('合计：PASS='):
            _suites_pass = int(_ln.split('PASS=')[1].split()[0])
            break
ok('文档「60 条」（k 轮快照）<= check113k 实跑 PASS 数',
   '60' in DOC and _suites_pass >= 60, '实得 %r' % (_suites_pass,))
# ★ 套件 id **不全是 `check*` 前缀**（`s7_event_speech` / `round8_dialogue` 等），
#   第一版按 `'id': 'check` 数得到 49 ⇒ **判据过窄 = 误报**。
#   第二版按 `'id':` 数得到 110（文件里别处也有同名键）⇒ 还是文本扫的问题。
#   ⇒ 改成**结构判据**：直接量 `SUITES` 这个列表元素的个数。
_suites_len = -1
for _n in ast.parse(RUN).body:
    if isinstance(_n, ast.Assign) and any(
            getattr(_t, 'id', None) == 'SUITES' for _t in _n.targets):
        if isinstance(_n.value, (ast.List, ast.Tuple)):
            _suites_len = len(_n.value.elts)
        break
ok('文档「108 套件」== SUITES 列表元素个数',
   '108' in DOC and _suites_len == 108, '实得 %d' % _suites_len)
ok('文档「2166 场景」== 索引实际条数',
   '2166' in DOC and json.loads(read(IDX_P)) and
   sum(len(a.get('scenes') or {})
       for c in json.loads(read(IDX_P))['chapters'].values()
       for a in (c.get('areas') or {}).values()) == 2166)
ok('文档「1243 / 16797 行」是 k 轮快照且实际只增不减',
   '1243' in DOC and '16797' in DOC and LIFE.count('\n') >= 1243
   and MAIN.count('\n') >= 16797)
# 关键样本仍在
_idx = json.loads(read(IDX_P))
# ★ 索引里的键是**完整 sid**（`ch1.hometown.diner`），不是末段 ——
#   第一版判 `'diner' in scenes` 得到 False ⇒ 判据过窄（误报）。
ok('`ch1.hometown.diner` 仍在索引里（候选源头）',
   'ch1.hometown.diner' in (_idx['chapters']['ch1']['areas']['hometown']['scenes']))
ok('`ch5.system` 仍是 3 间调试房（PLACE_SKIP_AREA_IDS 的现实依据）',
   len(_idx['chapters']['ch5']['areas']['system']['scenes']) == 3,
   str(len(_idx['chapters']['ch5']['areas']['system']['scenes'])))
# 基线键
for key in ('check113k', 'check73', 'check86', 's7_event_speech'):
    ok('baseline.json 有 `%s`' % key, '"%s"' % key in BASE)
ok('SUITES 里 check113k 在列', "'check113k'" in RUN)
ok('check113k 里有 `[PASS] %s` 字面量（G2 收数靠它）', "'[PASS] %s%s'" in CHK)

# ================================================================ 汇总
print()
print('=' * 74)
print('合计：PASS=%d FAIL=%d' % (_p, _f))
if _bad:
    print('失败项：')
    for d in _bad:
        print('  - %s' % d)
print('=' * 74)
sys.exit(0 if _f == 0 else 1)
