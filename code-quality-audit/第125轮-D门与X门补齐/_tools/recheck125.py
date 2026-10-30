# -*- coding: utf-8 -*-
u"""第125轮 · 改过核心文件后的**逐项复检**（可落盘、可重跑）。

按用户口径「以后再调整重要核心文件时一定要记得复检」：
    ① 语法/可编译  ② 结构自检  ③ 无 BOM / 无 U+FFFD / 行尾
    ④ **恒真判据复查**  ⑤ **逐令牌回验**（改过的数字逐个回原文件 `in` 一次）
    ⑥ 报告对账  ⑦ 工作区没有本轮临时产物

★ 复检脚本自己也会说谎 ⇒ 判据报红**先怀疑判据**。
   本文件里每条"回验"都要求令牌真的出现在**产品数据/源码**里，
   不是"报告里写了就算"。
"""
import ast
import collections
import io
import json
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
PKG = os.path.join(REPO, 'ralsei_pet')
SCENES = os.path.join(PKG, 'assets', 'scenes')
ROUTES = os.path.join(SCENES, '_routes.json')
EV42 = os.path.join(REPO, 'code-quality-audit', '第42轮-原作拓扑取证', '_evidence')
REPORT = os.path.join(ROUND, '_evidence', 'report125.md')

FILES = [
    os.path.join(HERE, 'gen_routes125.py'),
    os.path.join(HERE, 'check125.py'),
    os.path.join(REPO, 'code-quality-audit', '第124轮-桌面门落点与可达性',
                 '_tools', 'check124.py'),
    os.path.join(REPO, 'code-quality-audit', '第105轮-OneShot房间连接',
                 '_tools', 'check105.py'),
    os.path.join(REPO, 'code-quality-audit', '第36轮-按原作路线排场景',
                 'verify_scene_route_original.py'),
    os.path.join(REPO, 'code-quality-audit', '第44轮-原作对话框复刻',
                 'verify_routes_order44.py'),
    os.path.join(REPO, 'code-quality-audit', 'regress', 'run_all.py'),
]

_n = {'p': 0, 'f': 0}
_failed = []


def ok(desc, cond, detail=u''):
    if cond:
        _n['p'] += 1
        print(u'[PASS] %s%s' % (desc, (u'    ' + detail) if detail else u''))
    else:
        _n['f'] += 1
        _failed.append(desc)
        print(u'[FAIL] %s%s' % (desc, (u'    ' + detail) if detail else u''))


def rd(p):
    return io.open(p, encoding='utf-8', newline='').read()


def jload(p):
    s = rd(p)
    return json.loads(s.replace(': True', ': true').replace(': False', ': false'))


# ===========================================================================
print(u'== ① 语法 / 可编译（AST 解析，不产 .pyc —— 复检不许改变被测状态）==')
# ===========================================================================
_bad = []
for p in FILES:
    try:
        ast.parse(rd(p))
    except SyntaxError as e:
        _bad.append(u'%s: %s' % (os.path.basename(p), e))
ok(u'① 7 个改动过的 .py 全部 AST 可解析', not _bad, u'%r' % (_bad,))

# ===========================================================================
print(u'')
print(u'== ② 结构自检（产品数据面）==')
# ===========================================================================
RAW = json.loads(rd(ROUTES))
RL = RAW.get('routes') or []
NEW = [r for r in RL if isinstance(r.get('priority'), int) and r['priority'] >= 5000]
ok(u'②a 路由表 %d 条，其中第125轮新段 %d 条' % (len(RL), len(NEW)),
   len(RL) == 1531 and len(NEW) == 139, u'routes=%d new=%d' % (len(RL), len(NEW)))

_desk = [r for r in RL if r.get('when_scene') == 'desktop']
ok(u'②b 桌面 4 扇门仍在（A~D）且 C 门是 `room_area1`',
   sorted(str(r.get('when_door')) for r in _desk) == ['A', 'B', 'C', 'D']
   and [r.get('to') for r in _desk if r.get('when_door') == 'C']
   == [u'ut.rooms.room_area1'],
   u'%r' % ([(r.get('when_door'), r.get('to')) for r in _desk],))

_keys = collections.Counter()
for r in NEW:
    for k in r:
        _keys[k] += 1
ok(u'②c 新段字段形状统一（每条都恰好有 to/priority/reason/when_scene/when_door/_original）',
   all(v == len(NEW) for v in _keys.values()) and len(_keys) == 6,
   u'%r' % (dict(_keys),))

_note = (RAW.get('meta') or {}).get('note') or u''
ok(u'②d `meta.note` 追加了第125轮说明（写明 W 门拒收的理由）',
   u'第125轮' in _note and u'obj_doorD' in _note and u'W 门不收' in _note)

# ===========================================================================
print(u'')
print(u'== ③ 编码 / 行尾（逐字节，不许漂）==')
# ===========================================================================
b = io.open(ROUTES, 'rb').read()
txt = b.decode('utf-8')
ok(u'③a `_routes.json` 无 BOM、无 U+FFFD', not b.startswith(b'\xef\xbb\xbf')
   and u'\ufffd' not in txt, u'bytes=%d' % len(b))
ok(u'③b CRLF 统一、裸 LF = 0、**无尾换行**（尾字节 `}\\r\\n}`）',
   u'\r\n' in txt and txt.count(u'\n') == txt.count(u'\r\n')
   and not txt.endswith(u'\n') and txt.endswith(u'}\r\n}'),
   u'crlf=%d bare=%d tail=%r' % (txt.count(u'\r\n'),
                                 txt.count(u'\n') - txt.count(u'\r\n'), txt[-6:]))

# ===========================================================================
print(u'')
print(u'== ④ 恒真判据复查（AST 判，不扫注释）==')
# ===========================================================================


def true_checks(path):
    u"""找出"看着在守其实没守"的恒真判据。

    ★★★ 这里踩过一次（**判据自己也是被测物**）：本项目有两套 harness 约定 ——
      · `ok(cond, msg)`        → 条件是 **args[0]**（check105 / 本文件）
      · `check(desc, cond, …)` → 条件是 **args[1]**（check124 / check125 / verify_*）
    第一版只查 args[1]，于是 `ok(True, u"x")` 这种恒真**一条都抓不到**，
    而 ④a 还会因为"没命中"显示绿色 —— 是 ④b 的**正控制**把它逮住的。
    ⇒ 两个位置都查。assumption 安全：消息参数永远不会是字面量 `True`。
    """
    out = []
    for node in ast.walk(ast.parse(rd(path))):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        nm = fn.id if isinstance(fn, ast.Name) else None
        if nm not in ('ok', 'check'):
            continue
        for _i in (0, 1):
            if len(node.args) > _i and isinstance(node.args[_i], ast.Constant) \
                    and node.args[_i].value is True:
                out.append(node.lineno)
                break
    return out


_truth = {}
for p in FILES:
    hits = true_checks(p)
    if hits:
        _truth[os.path.basename(p)] = hits
ok(u'④a 7 个文件里没有 `ok(x, True)` / `check(x, True)` 恒真判据', not _truth,
   u'%r' % (_truth,))

# 正控制：合成四条（两套 harness 各一真一假），同一个函数必须判出**恰好两条**
_synth = os.path.join(os.environ.get('TEMP', '.'), '_rc125_synth.py')
try:
    io.open(_synth, 'w', encoding='utf-8', newline='\n').write(
        u'ok(True, u"x")\n'            # 1 → 恒真（ok 型，条件是 args[0]）
        u'check(u"d", True)\n'          # 2 → 恒真（check 型，条件是 args[1]）
        u'ok(1 == 1, u"y")\n'          # 3 → 不是字面 True，不算（避免误报）
        u'check(u"d", 1 == 1)\n')      # 4 → 同上
    _got = true_checks(_synth)
finally:
    if os.path.isfile(_synth):
        os.remove(_synth)
ok(u'④b 正控制：`ok(True,…)` 与 `check(…, True)` 两套写法都被抓出、`1 == 1` 不算'
   u'（证明 ④a 不是恒真，且没漏掉 ok 型）',
   _got == [1, 2], u'got=%r' % (_got,))

# ===========================================================================
print(u'')
print(u'== ⑤ 逐令牌回验（每个数字都回**产品数据**查一遍，不是"报告里写了就算"）==')
# ===========================================================================
G = (jload(os.path.join(EV42, '_room_graph.json')).get('chapters') or {})
_edges = sum(len(((G.get(c) or {}).get('edges') or [])) for c in
             ('ch1', 'ch2', 'ch3', 'ch4', 'ch5'))
_w_edges = sum(1 for c in ('ch1', 'ch2', 'ch3', 'ch4', 'ch5')
               for e in ((G.get(c) or {}).get('edges') or [])
               if e.get('door') in ('obj_doorW', 'obj_doorw_musfade'))
_old_ch = [r for r in RL
           if isinstance(r.get('priority'), int) and r['priority'] < 3000
           and r.get('when_scene') != 'desktop']
_pairs = collections.Counter((r.get('when_scene'), r.get('to')) for r in RL)
_dup = len(RL) - len(_pairs)

TOKENS = [
    (u'证据边 782', _edges, 782),
    (u'既有 ch1~ch5 段 443', len(_old_ch), 443),
    (u'新段 139', len(NEW), 139),
    (u'D 条 56', sum(1 for r in NEW if r.get('when_door') == 'D'), 56),
    (u'X 条 83', sum(1 for r in NEW if r.get('when_door') == 'X'), 83),
    (u'W 门证据边 98（拒收）', _w_edges, 98),
    (u'合法重复边 5', _dup, 5),
]
_bad_tok = [u'%s 实测 %r' % (k, v) for k, v, want in TOKENS if v != want]
ok(u'⑤a 7 个关键数字回产品数据全部对上',
   not _bad_tok, u'%r' % (_bad_tok or [u'%s=%d' % (k, v) for k, v, _w in TOKENS],))

# 密度回验（逐章"有出边的场景数"）
_OUT = collections.defaultdict(set)
for r in RL:
    s = r.get('when_scene')
    if isinstance(s, str) and s:
        _OUT[s.split('.')[0]].add(s)
DENS = {c: len(_OUT.get(c, ())) for c in ('ch1', 'ch2', 'ch3', 'ch4', 'ch5')}
ok(u'⑤b 五章密度 == 116/137/35/32/31（第124轮基线 105/127/23/22/20）',
   DENS == {'ch1': 116, 'ch2': 137, 'ch3': 35, 'ch4': 32, 'ch5': 31},
   u'%r' % (DENS,))

# 源码令牌：三个改过的判据脚本里"关键口径"必须真在（防止被静默回退）
_SRC = {
    'verify_scene_route_original.py': (u"'D': -2", u'_KIND_TABLE', u'_table_self_ok'),
    'verify_routes_order44.py': (u"'D': -2", u'C1c', u'_DELTA_LETTERS'),
    'check105.py': (u"priority'] < 3000", u'第125轮'),
    'check124.py': (u'EXPECT_ROUTES = 1531', u'EXPECT_DUP_EDGES'),
    'check125.py': (u'EXPECT_ADD = 139', u'EXPECT_REFUSED_W = 98'),
}
_miss_src = []
for _f, _toks in _SRC.items():
    _p = [x for x in FILES if os.path.basename(x) == _f]
    if not _p:
        _miss_src.append(u'%s 不在 FILES 里' % _f)
        continue
    _s = rd(_p[0])
    for _t in _toks:
        if _t not in _s:
            _miss_src.append(u'%s 缺 %r' % (_f, _t))
ok(u'⑤c 5 个判据脚本里的关键口径令牌逐个在位（防静默回退）', not _miss_src,
   u'%r' % (_miss_src or [u'全部命中'],))

# ===========================================================================
print(u'')
print(u'== ⑥ 报告对账（报告里的数字必须在产品侧成立；允许千分位写法）==')
# ===========================================================================
ok(u'⑥a 报告文件在盘', os.path.isfile(REPORT), REPORT)
_rep = rd(REPORT) if os.path.isfile(REPORT) else u''
_rep_nc = _rep.replace(u',', u'')
_need = [u'782', u'443', u'139', u'56', u'83', u'98', u'1531',
         u'116', u'137', u'35', u'32', u'31']
_miss_rep = [t for t in _need if t not in _rep_nc]
ok(u'⑥b 报告的 12 个关键数字都在（**去掉千分位后再比** —— 判据太窄会误报）',
   not _miss_rep, u'缺=%r' % (_miss_rep,))
ok(u'⑥c 报告写明了"W 门拒收"与"3 条 no_marker 例外"这两件事',
   u'W 门' in _rep and u'no_marker' in _rep)

# ===========================================================================
print(u'')
print(u'== ⑦ 工作区没留本轮临时产物 ==')
# ===========================================================================
_round_files = sorted(os.listdir(HERE)) + sorted(os.listdir(ROUND))
_junk = [f for f in set(_round_files)
         if f.endswith(('.pyc', '.tmp', '.bak', '.log', '.orig'))
         or f.startswith(('probe', 'restore', '__pycache__'))]
ok(u'⑦ 本轮目录与轮次目录里没有临时/备份产物', not _junk, u'%r' % (_junk,))
ok(u'⑦b 生成器与锁都在盘（gen_routes125.py / check125.py）',
   os.path.isfile(os.path.join(HERE, 'gen_routes125.py'))
   and os.path.isfile(os.path.join(HERE, 'check125.py')))

print(u'')
print(u'---- 共 %d 条：PASS %d / FAIL %d' % (_n['p'] + _n['f'], _n['p'], _n['f']))
if _failed:
    print(u'失败项：')
    for _d in _failed:
        print(u'  - %s' % _d)
sys.exit(1 if _failed else 0)
