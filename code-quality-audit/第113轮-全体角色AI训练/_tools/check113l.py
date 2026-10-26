# -*- coding: utf-8 -*-
u"""第113轮l回归锁：**出戏的元词汇**（自称 AI / "提示词" / "设定"）。

这一轮做了两件事，方向相反，都得锁住：

① **把尺子修准**（加判据）。
   全量扫 `raw30` 的 1956 轮回复：旧 `_AI_RE` 只认「我是 AI / 我是程序」这种**句式**，
   判红 22 条；另外 **48 条 / 25 人**说着「我不是 AI 哦」「我知道这只是个设定」
   一条都没判。换尺子后 34 人 / 75 条。
   ⇒ 这不是"角色变差了"，是**同一批数据换个尺子才看见**。

② **把纠正句撤掉**（也是加判据）。
   原计划给判红的人写一句通用纠正。三轮实测全部指向"更差"：
     · 顺序四臂（各 9 样本）：不加 1 条含禁词、三个候选句 3~4 条；
     · 反向交替对照（各 12 样本，抵消时间漂移）：不加 3/12，极简句 8/12。
   ⇒ `PATCH_RULES` 里**故意不设** `AI_SELF`；改用「判退重采样」。
   本套件 A 组守的就是这个决策 —— 防止以后有人凭直觉把它加回来。

稳定性（G2 要逐字节比对）
------------------------
★ 不打印随数据变化的绝对数（人数 / 条数），只打布尔与失败名单。
  E 组读探针结果时只断言**不等式**，不打印计数 —— 否则重跑一次探针就假 DIFF。

零网络、零 Qt（只 import 产品模块读文件）。
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
sys.path.insert(0, HERE)
sys.path.insert(0, PET)

import common113 as C  # noqa: E402

EVID = os.path.join(ROUND, '_evidence')
RAW30 = os.path.join(EVID, 'raw30')
INDEX = os.path.join(PET, 'assets', 'npc', '_training', '_index.json')
AB4 = os.path.join(EVID, 'ab_aiself113l.json')          # 顺序四臂
ABZ = os.path.join(EVID, 'ab_aiself113l_zigzag.json')   # 反向交替对照
ABR = os.path.join(EVID, 'ab_retry113l.json')           # 判退重采样

_n_pass = 0
_n_fail = 0
_failed = []


def check(desc, cond, detail=''):
    global _n_pass, _n_fail
    if cond:
        _n_pass += 1
    else:
        _n_fail += 1
        _failed.append(desc)
    print('[%s] %s%s' % ('PASS' if cond else 'FAIL', desc,
                         ('    ' + detail) if detail else ''))


def mark(t):
    print('\n--- %s ---' % t)


def load_json(p):
    if not os.path.isfile(p):
        return None
    try:
        return json.load(io.open(p, encoding='utf-8'))
    except Exception:                                   # noqa: BLE001
        return None


# ================================================================ 读数据
idx = json.load(io.open(INDEX, encoding='utf-8'))
patches = idx.get('patches') or {}
cards = idx.get('cards') or {}

raw_ev = set()
if os.path.isdir(RAW30):
    for fn in sorted(os.listdir(RAW30)):
        if not fn.endswith('.jsonl'):
            continue
        for rec in C.read_jsonl(os.path.join(RAW30, fn)):
            nid = rec.get('id') or fn[:-6]
            for t in rec.get('turns') or []:
                if any(c == 'AI_SELF' for c, _ in (t.get('violations') or [])):
                    raw_ev.add(nid)

# ================================================================ A 决策
mark('A 决策：`AI_SELF` 不用纠正句（实测无效且有害），改靠判退重采样')
check('A1 一手记录 `raw30` 读得到（空 ⇒ 下面几条全是恒真）',
      bool(raw_ev), '角色数 %d' % len(raw_ev))
check('A2 `PATCH_RULES` 里**没有** `AI_SELF`（这是实测结论，不是漏写）',
      'AI_SELF' not in C.PATCH_RULES)
check('A2b 负控制：把 `AI_SELF` 塞回 PATCH_RULES ⇒ A2 的判断必须报红',
      'AI_SELF' in dict(list(C.PATCH_RULES.items()) + [('AI_SELF', 'x')]))
check('A2c `build_patch` 对 AI_SELF 违规**不再产出**任何句子',
      C.AI_SELF_PATCH not in C.build_patch([('AI_SELF', 'x')], [], []),
      C.build_patch([('AI_SELF', 'x')], [], [])[:40] or '（空，符合）')
_with = [n for n, p in patches.items() if C.AI_SELF_PATCH in p]
check('A3 训练产物里**没有人**带 AI_SELF 纠正句', not _with,
      '带了：%s' % ','.join(sorted(_with)) or '无')
check('A3b 负控制：产物里塞一条 ⇒ A3 的判断必须报红',
      bool([n for n, p in dict(list(patches.items()) + [('__ghost__',
                                                        C.AI_SELF_PATCH)]).items()
            if C.AI_SELF_PATCH in p]))
check('A4 撤销是干净的：`cards[nid]["patch"]` 也没有残留',
      not [n for n, c in cards.items() if C.AI_SELF_PATCH in (c.get('patch') or '')])

# ================================================================ B 卫生
mark('B 纠正句文本卫生（否决句本身也要干净，防止有人拿它回来）')
_OLD = '你不承认自己是程序或 AI。有人这么问，就照你的性格当成胡话说回去，别解释技术。'
check('B1 被否决的候选句本身不含禁词根（留着复现实验，但不许带脏词）',
      not C.patch_is_clean(C.AI_SELF_PATCH),
      '命中：%s' % (','.join(C.patch_is_clean(C.AI_SELF_PATCH)) or '无'))
check('B1b 正控制：旧句**必须**被判红（证明 B1 不是恒真）',
      bool(C.patch_is_clean(_OLD)), '命中：%s' % ','.join(C.patch_is_clean(_OLD)))
check('B2 放宽后的 `_AI_RE` 现在**能**抓到旧句（"只认整句正则"的缺口已补上）',
      C._AI_RE.search(_OLD) is not None,
      (C._AI_RE.search(_OLD).group(0) if C._AI_RE.search(_OLD) else '没命中'))
check('B2b 负控制：不含禁词的普通句子**不许**被判红（放宽不是乱抓）',
      C._AI_RE.search('今天的风有点凉，你冷不冷？') is None)
check('B3 现存每条 patch 都不含禁词根（别的补丁也不许顺手写脏词）',
      not [n for n, p in patches.items() if C.patch_is_clean(p)],
      '脏：%s' % ','.join(sorted(n for n, p in patches.items()
                                if C.patch_is_clean(p)) or '无'))
check('B4 现存每条 patch ≤ 160 字（不许变成第二份人设）',
      all(len(p) <= 160 for p in patches.values()),
      '最长 %d' % max([len(p) for p in patches.values()] or [0]))

# ================================================================ C 产物
mark('C 产物与产品读取链路一致')
_bad_cards = [n for n in patches if n in cards and cards[n].get('patch') != patches[n]]
check('C1 `patches` 与 `cards[nid]["patch"]` 一致（重建索引会回写这一份）',
      not _bad_cards, '不一致：%s' % (','.join(sorted(_bad_cards)) or '无'))
try:
    from modules import npc_persona as P
    _err = ''
except Exception as e:                                  # noqa: BLE001
    P, _err = None, repr(e)
check('C2 产品模块 `npc_persona` 可导入', P is not None, _err)
if P is not None:
    _read = [n for n, p in patches.items() if P.training_patch(n) != p]
    check('C2b `training_patch()` 对每条 patch 原样返回', not _read,
          '读回不符：%s' % (','.join(sorted(_read)) or '无'))
    check('C2c 负控制：没写过的人 / 未知 id 仍是空串（不许串号、不许给默认句）',
          P.training_patch('flowery') == '' and P.training_patch('__nope__') == '')

# ================================================================ D 尺子
mark('D `_AI_RE` 口径：裸词判红，但"程序"故意不禁（人设内用法）')
check('D1 裸词「我不是 AI 哦」必须判红（48 条漏报的代表形态）',
      C._AI_RE.search('我不是AI哦') is not None)
check('D1b 「我知道这只是个设定」必须判红（承认自己是设定＝出戏）',
      C._AI_RE.search('我知道这只是个设定') is not None)
check('D2 负控制：「不变的步骤」不算出戏（`hy_sousborg` 的厨房工序）',
      C._AI_RE.search('厨房必须保持运作，Crack. Fry. Season. 是不变的步骤。') is None)
check('D2b 负控制：「我的程序允许的」不算（`os_prophetbot` 是机器人，人设内）',
      C._AI_RE.search('我会回答一切——只要那是我的程序允许的。') is None)
check('D3 正常人设内的话不许误报（真实台词当负控制）',
      C._AI_RE.search('我是 Berdly，全班第一的学生！FUAHAHAHAHA！') is None)

# ================================================================ E 实测
mark('E 实测证据（只断言方向，不打印会随数据变的绝对数）')


def _loose(rows, arm):
    return sum(1 for r in rows if r.get('arm') == arm and r.get('loose'))


def _hit(rows, arm):
    return sum(1 for r in rows if r.get('arm') == arm and r.get('hit'))


ab4 = load_json(AB4)
check('E1 顺序四臂数据在（`ab_aiself113l.json`）', ab4 is not None)
if ab4:
    rows, arms = ab4.get('rows') or [], ab4.get('arms') or {}
    base = _loose(rows, 'A')
    others = {k: _loose(rows, k) for k in arms if k != 'A'}
    check('E2 负控制：不加纠正句的基线**必须**复现出戏（为 0 ⇒ 实验没诱导成功）',
          base > 0)
    check('E3 三个候选句**没有一个**比不加更好（这就是撤掉它的依据）',
          all(v >= base for v in others.values()),
          '基线之外的臂：%s' % ','.join(sorted(others)))

abz = load_json(ABZ)
check('E4 反向交替对照数据在（`ab_aiself113l_zigzag.json`，抵消时间漂移）',
      abz is not None)
if abz:
    rows = abz.get('rows') or []
    check('E5 交替对照下结论不变：加了纠正句的含禁词数**不少于**不加的',
          _loose(rows, 'D') >= _loose(rows, 'A'))
    check('E5b 负控制：交替对照里基线也复现了（否则 E5 是在比两堆零）',
          _loose(rows, 'A') > 0)

abr = load_json(ABR)
check('E6 重采样数据在（`ab_retry113l.json`，产品同口径 MAX_RETRIES=2）',
      abr is not None)
if abr:
    rows = abr.get('rows') or []
    _first = sum(1 for r in rows if r.get('first_hit'))
    _final = sum(1 for r in rows if r.get('hit'))
    check('E7 判退重采样**确实**减少了 AI_SELF 残留（这是撤掉纠正句后唯一的防线）',
          _final < _first, '首次判红 %d → 重采样后 %d' % (_first, _final))

# ================================================================ F 自检
mark('F 本轮改过的文件自检（语法 / 编码 / EOL / 恒真判据）')
_TOOLS = os.path.dirname(os.path.abspath(__file__))
_TOUCHED = ['common113.py', 'check113.py', 'check113l.py', 'probe_aiself113l.py',
            'probe_metaword113l.py', 'probe_ab113l.py', 'rescore113l.py',
            'apply_aiself113l.py', 'verify_aiself113l.py']
_bad_syntax, _bad_bom, _bad_eol = [], [], []
for _fn in _TOUCHED:
    _p = os.path.join(_TOOLS, _fn)
    if not os.path.isfile(_p):
        _bad_syntax.append(_fn + '(缺)')
        continue
    _raw = io.open(_p, 'rb').read()
    try:
        ast.parse(_raw.decode('utf-8'))
    except Exception:                                   # noqa: BLE001
        _bad_syntax.append(_fn)
    if _raw[:3] == b'\xef\xbb\xbf' or '\ufffd' in _raw.decode('utf-8', 'replace'):
        _bad_bom.append(_fn)
    # 行尾：允许全 CRLF 或全 LF，**不许混**（混了 git 会把整个文件重写）
    _crlf, _lf = _raw.count(b'\r\n'), _raw.count(b'\n')
    if _crlf and _crlf != _lf:
        _bad_eol.append(_fn)
check('F1 本轮改过的 %d 个脚本都能 `ast.parse`' % len(_TOUCHED),
      not _bad_syntax, '失败：%s' % (','.join(_bad_syntax) or '无'))
check('F2 无 BOM / 无 U+FFFD', not _bad_bom, '有问题：%s' % (','.join(_bad_bom) or '无'))
check('F3 行尾不混用', not _bad_eol, '混用：%s' % (','.join(_bad_eol) or '无'))

# ★ 恒真判据自检：`check(desc, cond)` 的 cond 是 args[1]。写成 `check(..., True)`
#   等于"看着在守、其实没守"（第85轮 `{}=={}` 的同类）。这里扫的就是自己。
_const_true = []
for _fn in ('check113l.py', 'check113.py'):
    _p = os.path.join(_TOOLS, _fn)
    _tree = ast.parse(io.open(_p, encoding='utf-8').read())
    for _node in ast.walk(_tree):
        if not isinstance(_node, ast.Call):
            continue
        _f = _node.func
        _name = getattr(_f, 'id', None) or getattr(_f, 'attr', None)
        if _name not in ('check', 'ok') or len(_node.args) < 2:
            continue
        _cond = _node.args[1]
        if isinstance(_cond, ast.Constant) and bool(_cond.value):
            _const_true.append('%s:%d' % (_fn, _node.lineno))
check('F4 没有"恒真判据"（`check(desc, True)` / `ok(desc, True)`）', not _const_true,
      '可疑：%s' % (','.join(_const_true[:5]) or '无'))


def _count_const_true(tree):
    n = 0
    for _node in ast.walk(tree):
        if isinstance(_node, ast.Call):
            _f = _node.func
            _name = getattr(_f, 'id', None) or getattr(_f, 'attr', None)
            if _name in ('check', 'ok') and len(_node.args) >= 2:
                if isinstance(_node.args[1], ast.Constant) and bool(_node.args[1].value):
                    n += 1
    return n


check('F4b 正控制：夹具里放一个 `check("x", True)` ⇒ 上面的扫描必须数出来',
      _count_const_true(ast.parse('check("x", True)\nok("y", 1)\n')) == 2)

# ================================================================ 汇总
print()
print('=' * 74)
print('合计：PASS=%d FAIL=%d' % (_n_pass, _n_fail))
if _failed:
    print('失败项：')
    for d in _failed:
        print('  - %s' % d)
print('=' * 74)
sys.exit(0 if _n_fail == 0 else 1)
