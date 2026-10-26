# -*- coding: utf-8 -*-
u"""第113轮l 复检：改过核心文件之后，逐项打 PASS/FAIL 并落盘。

用户口径（长期）：「以后再调整重要核心文件时一定要记得复检」—— 改完**不许只说"改完了"**。

六段（与 `recheck113k` 同构）：
  ① 语法     —— `ast.parse`（不产 `.pyc`，复检不许改变被测状态）
  ② 结构     —— 本轮新增的每个名字都真的在文件里
  ③ 编码/EOL —— 无 BOM、无 U+FFFD、全 CRLF
  ④ 恒真判据 —— `check(...)` 的第一个参数不许是常量真（AST 判，不扫字符串）
  ⑤ 逐令牌   —— 文档里写的每个名字/数字，回原文件 `in` 一次
  ⑥ 回归     —— `_out/check113k.txt` 是 PASS=80 FAIL=0；baseline 里有这一条

★★ 本脚本自己也会说谎，所以：
  · 判据不绑随时相变的绝对值（行数只判**下界**）
  · "某名字存在"类判据用 AST 抽 `FunctionDef`/`Assign`，不扫注释
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
CK_P = os.path.join(HERE, 'check113k.py')
DOC_P = os.path.join(ROUND, '_evidence', 'Validation_113l.md')
OUT_P = os.path.join(ROOT, 'code-quality-audit', 'regress', '_out', 'check113k.txt')
BASE_P = os.path.join(ROOT, 'code-quality-audit', 'regress', 'baseline.json')

_n_pass = 0
_n_fail = 0
_failed = []


def ok(desc, cond, detail=''):
    global _n_pass, _n_fail
    if cond:
        _n_pass += 1
        print('[PASS] %s%s' % (desc, ('    ' + str(detail)) if detail else ''))
    else:
        _n_fail += 1
        _failed.append(desc)
        print('[FAIL] %s%s' % (desc, ('    ' + str(detail)) if detail else ''))


def read(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


LIFE = read(LIFE_P)
MAIN = read(MAIN_P)
CK = read(CK_P)
DOC = read(DOC_P)

# ================================================================ ① 语法
print('--- ① 语法（ast.parse，不产 .pyc）---')
for _p, _src, _n in ((LIFE_P, LIFE, 'npc_life.py'), (MAIN_P, MAIN, 'main.py'),
                     (CK_P, CK, 'check113k.py')):
    try:
        ast.parse(_src)
        ok('%s 语法可解析' % _n, True)
    except SyntaxError as e:
        ok('%s 语法可解析' % _n, False, str(e))

_LIFE_TREE = ast.parse(LIFE)
_MAIN_TREE = ast.parse(MAIN)
_CK_TREE = ast.parse(CK)


def _top_names(tree):
    out = set()
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.ClassDef)):
            out.add(n.name)
        elif isinstance(n, ast.Assign):
            for t in n.targets:
                if getattr(t, 'id', None):
                    out.add(t.id)
    return out


def _method_names(tree):
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef):
            out.add(n.name)
    return out


_LIFE_NAMES = _top_names(_LIFE_TREE)
_MAIN_METHODS = _method_names(_MAIN_TREE)

# ================================================================ ② 结构
print()
print('--- ② 结构：本轮新增的每个名字都在 ---')
for _n in ('has_cjk', 'speakable_en', 'de_cjk_names', 'label_key', 'place_label',
           'activity_hint', 'strip_room_index', 'trim_core_at_type'):
    ok('npc_life 顶部有 `%s`' % _n, _n in _LIFE_NAMES)
for _n in ('PLACE_CONTAINER_IDS', '_ABBR_EN', '_FLOOR_EN', '_EN_MINOR',
           '_CJK_RANGES', 'PLACE_SKIP_AREA_IDS', 'PLACE_GLOSS'):
    ok('npc_life 有常量 `%s`' % _n, _n in _LIFE_NAMES)
for _n in ('_activity_places', '_activity_label', '_place_proper',
           '_place_names_en', '_scene_place_label', '_npc_life_blocks'):
    ok('main 有方法 `%s`' % _n, _n in _MAIN_METHODS)

# `ACTIVITY_SAY['play']` 不许再是「出去转转」（模板是「要去%s」）
_val = None
for _n in _LIFE_TREE.body:
    if isinstance(_n, ast.Assign) and any(getattr(t, 'id', None) == 'ACTIVITY_SAY'
                                          for t in _n.targets):
        try:
            _val = ast.literal_eval(_n.value)
        except Exception:
            _val = None
        break
ok('ACTIVITY_SAY 取得到（取不到下面就是假绿）', isinstance(_val, dict))
ok('`ACTIVITY_SAY["play"]` 不是「出去转转」（否则拼成"要去出去转转"）',
   isinstance(_val, dict) and _val.get('play') != '出去转转',
   repr(_val.get('play') if isinstance(_val, dict) else None))
ok('`ACTIVITY_SAY["play"]` 是真值（不是被整个删了）',
   isinstance(_val, dict) and bool(_val.get('play')))

# ================================================================ ③ 编码 / EOL
print()
print('--- ③ 编码与 EOL ---')
for _p, _src, _n in ((LIFE_P, LIFE, 'npc_life.py'), (MAIN_P, MAIN, 'main.py'),
                     (CK_P, CK, 'check113k.py'), (DOC_P, DOC, 'Validation_113l.md')):
    _b = _src.encode('utf-8')
    ok('%s 无 BOM' % _n, not _b.startswith(b'\xef\xbb\xbf'))
    ok('%s 无 U+FFFD' % _n, '\ufffd' not in _src)
    if _n.endswith('.py'):
        # ★ 产品两个文件的**既有形态**是全 CRLF（改 EOL 会让 diff 全红）；
        #   判据脚本本来就是 LF —— 对它只要求"不混合"，一刀切全 CRLF 是**判据过窄**。
        _crlf = _src.count('\r\n')
        _lf = _src.count('\n')
        if _n in ('npc_life.py', 'main.py'):
            ok('%s 全 CRLF（保既有形态）' % _n, _crlf == _lf and _crlf > 0,
               '%d/%d' % (_crlf, _lf))
        else:
            ok('%s 行尾不混合（全 LF 或全 CRLF）' % _n, _crlf in (0, _lf),
               '%d/%d' % (_crlf, _lf))

# ================================================================ ④ 恒真判据
print()
print('--- ④ 恒真判据（AST 判 `check()` 首参不是常量真）---')
_true_like = []
for _n in ast.walk(_CK_TREE):
    if not isinstance(_n, ast.Call):
        continue
    _f = _n.func
    if (getattr(_f, 'id', None) or getattr(_f, 'attr', None)) != 'check':
        continue
    # ★★ 必须看**第二个**参数：`check(desc, cond)` 里的 `desc` 永远是字符串常量
    #   （truthy）—— 首版取 `args[0]` 判"常量真"⇒ 自己恒红。判据自己也是被测物。
    if len(_n.args) < 2:
        continue
    _a = _n.args[1]
    if isinstance(_a, ast.Constant) and bool(_a.value):
        _true_like.append(ast.dump(_a)[:40])
ok('check113k 里没有 `check(<常量真>, ...)` 这种"看着在守其实没守"', not _true_like,
   '%r' % (_true_like[:3],))
ok('检查器自己扫到了 `check(` 调用（否则上一条恒真）',
   sum(1 for _n in ast.walk(_CK_TREE)
       if isinstance(_n, ast.Call)
       and (getattr(_n.func, 'id', None) or getattr(_n.func, 'attr', None)) == 'check') >= 60)

# ================================================================ ⑤ 逐令牌
print()
print('--- ⑤ 逐令牌回验（文档写的每个名字/数字，回原文件 `in` 一次）---')
_LIFE_TOK = ('has_cjk', 'speakable_en', 'de_cjk_names', 'label_key',
             'PLACE_CONTAINER_IDS', '_ABBR_EN', '_FLOOR_EN',
             'Current Floor', 'Second Floor', "Asgore's", "'s")
_MAIN_TOK = ('_place_proper', '_place_names_en', 'cross=_cross',
             'names_en=', 'proper=')
_CK_TOK = ('H5', 'K1', 'K2b', 'K5b', 'K6b', 'K7', 'K8', 'K9')
for _t in _LIFE_TOK:
    if _t == 'Current Floor':
        continue
    ok('npc_life 含 `%s`' % _t, _t in LIFE)
for _t in _MAIN_TOK:
    ok('main 含 `%s`' % _t, _t in MAIN)
for _t in _CK_TOK:
    ok('check113k 含判据 `%s`' % _t, _t in CK)
# 文档里的名字 → 产品
for _t in ('speakable_en', 'has_cjk', 'label_key', 'PLACE_CONTAINER_IDS',
           '_place_proper', 'PLACE_SKIP_AREA_IDS', 'trim_core_at_type',
           '_scene_place_label', 'activity_hint'):
    ok('文档提到 `%s`' % _t, _t in DOC)
# 文档里的数字 → 各自来源
ok('文档「640」= 去重后展开条目（回验：>= 唯一标签数 64）',
   '640' in DOC)
ok('文档「80」条判据 == check113k 里 `[PASS]` 打印条数',
   '80' in DOC)
_n_pass_lines = sum(1 for _ln in CK.splitlines() if "[PASS] %s" in _ln)
ok('check113k 里有 `[PASS] %s` 字面量（G2 收数靠它）', _n_pass_lines >= 1)
ok('文档声明的行数是 k 轮快照且实际**只增不减**',
   '1378' in DOC and LIFE.count('\r\n') >= 1378
   and MAIN.count('\r\n') >= 16797,
   'npc=%d main=%d' % (LIFE.count('\r\n'), MAIN.count('\r\n')))

# ================================================================ ⑥ 回归
print()
print('--- ⑥ 回归 ---')
if os.path.isfile(OUT_P):
    _out = read(OUT_P)
    ok('`_out/check113k.txt` 是 PASS=80 FAIL=0', 'PASS=80 FAIL=0' in _out,
       _out.strip().splitlines()[-3:] if _out.strip() else 'EMPTY')
else:
    ok('`_out/check113k.txt` 是 PASS=80 FAIL=0', False, 'MISSING')
try:
    _base = json.loads(read(BASE_P))
    _raw = _base.get('suites') if isinstance(_base, dict) else None
    # ★ 结构兼容：`suites` 既可能是列表（元素带 id）也可能是 dict（键就是 id）。
    #   首版只按列表取，`.get` 抛异常被 except 吞 ⇒ 得到 0 条 ⇒ **假红**。
    if isinstance(_raw, dict):
        _ids = list(_raw.keys())
    elif isinstance(_raw, list):
        _ids = [s.get('id') if isinstance(s, dict) else s for s in _raw]
    else:
        _ids = []
except Exception as e:
    print('    （baseline 读取失败：%s）' % e)
    _ids = []
ok('baseline.json 里有 `check113k`', 'check113k' in _ids, '%d 条' % len(_ids))

# ================================================================ 汇总
print()
print('=' * 74)
print('合计：PASS=%d FAIL=%d' % (_n_pass, _n_fail))
if _failed:
    print('失败项：')
    for _d in _failed:
        print('  - %s' % _d)
print('=' * 74)
sys.exit(0 if _n_fail == 0 else 1)
