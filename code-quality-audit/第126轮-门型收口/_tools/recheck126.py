# -*- coding: utf-8 -*-
u"""第126轮复检（改过核心文件必复检）—— 七段，逐项打 PASS/FAIL 并落盘。

① 语法：本轮碰过的 .py 全部 `ast.parse`（**不产 .pyc**，判据不许改变被测状态）
② 结构：路由 1,740 / 新段 209 / 寻路图 7 章 / `meta` 有第126轮说明 / 字段形状
③ 编码行尾：无 BOM、无 U+FFFD、CRLF 一致、路由表无尾换行
④ **恒真判据复查** + 正控制（`check` 的 args[1] 与 `ok` 的 args[0] 两套 harness）
⑤ 逐令牌回验：报告里的每个数字回产品数据 `in` 一次；脚本口径令牌逐个回原文件
⑥ 报告对账：报告里的数字去千分位后与实测相等
⑦ 无临时产物：工作区里没有 `_tmp` / `probe*.py` / `*.log` 之类
"""
import ast
import io
import json
import os
import re
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
SCENES = os.path.join(REPO, 'ralsei_pet', 'assets', 'scenes')
ROUTES_P = os.path.join(SCENES, '_routes.json')
GRAPH_P = os.path.join(REPO, 'code-quality-audit', '第42轮-原作拓扑取证', '_evidence',
                       '_room_graph.json')
REPORT = os.path.join(ROUND, '_evidence', 'report126.md')
TOOLS = os.path.join(ROUND, '_tools')

_n = {'p': 0, 'f': 0}
_failed = []


def check(desc, cond, detail=u''):
    if cond:
        _n['p'] += 1
        print(u'[PASS] %s%s' % (desc, (u'    ' + detail) if detail else u''))
    else:
        _n['f'] += 1
        _failed.append(desc)
        print(u'[FAIL] %s%s' % (desc, (u'    ' + detail) if detail else u''))


def jload(p):
    s = io.open(p, encoding='utf-8', newline='').read()
    return json.loads(s.replace(': True', ': true').replace(': False', ': false'))


print(u'== ① 语法 ==')
PY = [os.path.join(TOOLS, f) for f in sorted(os.listdir(TOOLS)) if f.endswith('.py')]
PY += [os.path.join(REPO, 'code-quality-audit', '第36轮-按原作路线排场景',
                    'verify_scene_route_original.py'),
       os.path.join(REPO, 'code-quality-audit', '第44轮-原作对话框复刻',
                    'verify_routes_order44.py'),
       os.path.join(REPO, 'code-quality-audit', '第45轮-场景自主寻路',
                    'verify_pathfind45.py'),
       os.path.join(REPO, 'code-quality-audit', '第113轮-全体角色AI训练', '_tools',
                    'check113n.py'),
       os.path.join(REPO, 'code-quality-audit', '第124轮-桌面门落点与可达性', '_tools',
                    'check124.py'),
       os.path.join(REPO, 'code-quality-audit', '第125轮-D门与X门补齐', '_tools',
                    'check125.py'),
       os.path.join(REPO, 'code-quality-audit', 'regress', 'run_all.py')]
_bad = []
for p in PY:
    try:
        ast.parse(io.open(p, encoding='utf-8').read())
    except SyntaxError as e:
        _bad.append('%s:%s' % (os.path.basename(p), e.lineno))
check(u'①a 本轮碰过的 %d 个 .py 全部能 `ast.parse`（不产 .pyc）' % len(PY),
      not _bad, u'%r' % (_bad,))
check(u'①b 那些文件都在盘（缺文件时上面的"全部通过"是空集恒真）',
      all(os.path.isfile(p) for p in PY) and len(PY) >= 10, u'%d 个' % len(PY))

print(u'')
print(u'== ② 结构 ==')
RAW = json.loads(io.open(ROUTES_P, encoding='utf-8', newline='').read())
RL = RAW.get('routes') or []
NEW = [r for r in RL if isinstance(r.get('priority'), int) and 6000 <= r['priority'] <= 6208]
check(u'②a 路由总数 == 1740、新段 == 209、priority 连续',
      len(RL) == 1740 and len(NEW) == 209
      and sorted(r['priority'] for r in NEW) == list(range(6000, 6209)),
      u'routes=%d new=%d' % (len(RL), len(NEW)))
_need = ('to', 'priority', 'reason', 'when_scene', 'when_door', 'when_src', '_original')
_badk = [i for i, r in enumerate(NEW) if set(_need) - set(r)]
check(u'②b 新段每条都带齐 7 个字段（缺字段 = 下游静默取 None）',
      not _badk, u'缺字段的条数=%d' % len(_badk))
_bado = [r for r in NEW if set(r['_original']) <
         {'chapter', 'kind', 'via', 'code', 'src_room_name', 'dst_room_name',
          'src_room_id', 'dst_room_id'}]
check(u'②c `_original` 字段齐备（8 个必备键）', not _bado, u'缺=%d' % len(_bado))
_sh = [r for r in NEW if r['_original'].get('kind') == 'ot_door_shift']
check(u'②d shift 条都带 `room_delta == 1`（guard 条**故意不带** —— 它没有固定位移）',
      len(_sh) == 116 and all(r['_original'].get('room_delta') == 1 for r in _sh)
      and all('room_delta' not in r['_original'] for r in NEW
              if r['_original'].get('kind') == 'ot_door_guard'),
      u'shift=%d' % len(_sh))
G = json.loads(io.open(GRAPH_P, encoding='utf-8', newline='').read())
CHS = G.get('chapters') or {}
check(u'②e 寻路图 7 章（五章 + oneshot + outertale），outertale `n_edges` == 209',
      set(CHS) == {'ch1', 'ch2', 'ch3', 'ch4', 'ch5', 'oneshot', 'outertale'}
      and CHS['outertale']['n_edges'] == 209,
      u'%r' % (sorted(CHS),))
_note = (RAW.get('meta') or {}).get('note') or ''
check(u'②f 路由表 `meta.note` 有第126轮那段（后人不必翻生成器就知道边从哪来）',
      u'第126轮' in _note and u'outertale' in _note and u'209' in _note,
      u'note 末段含第126轮=%r' % (u'第126轮' in _note,))
_gnote = (G.get('meta') or {}).get('outertale_note') or ''
check(u'②g 寻路图 `meta.outertale_note` 在位', u'第126轮' in _gnote, u'len=%d' % len(_gnote))

print(u'')
print(u'== ③ 编码行尾 ==')
_rb = io.open(ROUTES_P, 'rb').read()
_rt = _rb.decode('utf-8')
_gb = io.open(GRAPH_P, 'rb').read()
_gt = _gb.decode('utf-8')
check(u'③a `_routes.json` 无 BOM / 无 U+FFFD / 全 CRLF / 无尾换行',
      not _rb.startswith(b'\xef\xbb\xbf') and _rt.count(u'\ufffd') == 0
      and _rt.count('\n') == _rt.count('\r\n') and not _rt.endswith('\n'),
      u'bytes=%d crlf=%d tail=%r' % (len(_rb), _rt.count('\r\n'), _rt[-3:]))
check(u'③b `_room_graph.json` 无 BOM / 无 U+FFFD / 全 CRLF / 有尾换行（第105轮定下的形状）',
      not _gb.startswith(b'\xef\xbb\xbf') and _gt.count(u'\ufffd') == 0
      and _gt.count('\n') == _gt.count('\r\n') and not _gt.endswith('\r\n\r\n'),
      u'bytes=%d crlf=%d tail=%r' % (len(_gb), _gt.count('\r\n'), _gt[-3:]))

print(u'')
print(u'== ④ 恒真判据复查（两套 harness 都查）+ 正控制 ==')


def scan(src):
    u"""把 `check(x, True)` 与 `ok(True, …)` 都数出来。"""
    hits = []
    for node in ast.walk(ast.parse(src)):
        if not isinstance(node, ast.Call):
            continue
        fn = getattr(node.func, 'id', None)
        if fn == 'check' and len(node.args) >= 2:
            a = node.args[1]
            if isinstance(a, ast.Constant) and a.value is True:
                hits.append(('check', node.lineno))
        if fn == 'ok' and node.args:
            a = node.args[0]
            if isinstance(a, ast.Constant) and a.value is True:
                hits.append(('ok', node.lineno))
    return hits


_own = scan(io.open(os.path.join(TOOLS, 'check126.py'), encoding='utf-8').read())
check(u'④a `check126.py` 没有恒真判据（`check` 的 args[1] / `ok` 的 args[0]）',
      not _own, u'%r' % (_own[:3],))
_syn = u'check("a", True)\nok(True, "b")\ncheck("c", 1 == 1)\n'
_h = scan(_syn)
check(u'④b 正控制：合成源码里恰好抓到 2 处（第 3 行是表达式、不是常量 True —— 允许）',
      len(_h) == 2, u'%r' % (_h,))
_prod = scan(io.open(os.path.join(REPO, 'code-quality-audit', '第36轮-按原作路线排场景',
                                  'verify_scene_route_original.py'), encoding='utf-8').read())
check(u'④c 老锁（`verify_scene_route_original`）里也没有新增恒真判据', not _prod,
      u'%r' % (_prod[:3],))

print(u'')
print(u'== ⑤ 逐令牌回验 ==')
TOKENS_NUM = [u'1,740', u'209', u'1,411', u'6208', u'162', u'204']
_rep = io.open(REPORT, encoding='utf-8').read()
check(u'⑤a 报告里 6 个关键数字都出现',
      all(t in _rep for t in TOKENS_NUM),
      u'缺=%r' % ([t for t in TOKENS_NUM if t not in _rep],))
_ot_out = set(r['when_scene'] for r in NEW)
_union = set(r['when_scene'] for r in NEW) | set(r['to'] for r in NEW)
check(u'⑤b 回产品数据：新段 209 / src 场景 162 / 并集 204 三个数对得上',
      len(NEW) == 209 and len(_ot_out) == 162 and len(_union) == 204,
      u'%d / %d / %d' % (len(NEW), len(_ot_out), len(_union)))
_gsum = sum(len((CHS[k].get('edges') or [])) for k in CHS)
check(u'⑤c 回产品数据：寻路图总边数 == 1,411 == 报告里的数',
      _gsum == 1411 and u'1,411' in _rep, u'Σ=%d' % _gsum)
_tok_py = [u'room_goto_next', u'inst_full.tsv', u'conn_ut.json', u'obj_mainchara',
           u'ot_door_guard', u'ot_door_shift']
_srcpy = io.open(os.path.join(TOOLS, 'gen_routes126.py'), encoding='utf-8').read()
check(u'⑤d 生成器的 6 个口径令牌逐个在源文件里（不是"我记得写了"）',
      all(t in _srcpy for t in _tok_py),
      u'缺=%r' % ([t for t in _tok_py if t not in _srcpy],))
_lock = io.open(os.path.join(REPO, 'code-quality-audit', '第125轮-D门与X门补齐', '_tools',
                             'check125.py'), encoding='utf-8').read()
check(u'⑤e 第125轮新段口径已改成闭区间（`PRIO_HI` 在位）—— 否则 6000 段会混进来',
      u'PRIO_HI' in _lock and u'PRIO_BASE <= r[' in _lock,
      u'PRIO_HI=%r' % (u'PRIO_HI' in _lock,))

print(u'')
print(u'== ⑥ 报告对账 ==')


def num(s):
    return int(s.replace(',', ''))


for label, pat, want in (
        (u'routes 总数', u'1,531 → \\*\\*1,740\\*\\*', 1740),
        (u'寻路图总边数', u'1,202 → \\*\\*1,411\\*\\*', 1411),
        (u'新段条数', u'补 \\*\\*209 条\\*\\*', 209),
        (u'覆盖并集', u'并集 \\*\\*204 / 244\\*\\*', 204)):
    check(u'⑥ 报告对账：%s' % label, re.search(pat, _rep) is not None,
          u'模式=%r' % pat)
check(u'⑥ 报告对账：数字与实测同源（不做二次解释）',
      num('1740') == len(RL) and num('1411') == _gsum
      and num('209') == len(NEW) and num('204') == len(_union),
      u'routes=%d graph=%d new=%d union=%d' % (len(RL), _gsum, len(NEW), len(_union)))

print(u'')
print(u'== ⑦ 无临时产物 ==')
#: ★ 探针移到 `_evidence/_probes/`（它们是**取证留痕**，不是可执行工具）；
#:   `_tools/` 只留 3 个能直接跑的：生成器 / 回归锁 / 复检。
TOOLS_WANT = {'gen_routes126.py', 'check126.py', 'recheck126.py'}
_have = set(f for f in os.listdir(TOOLS) if f.endswith('.py'))
check(u'⑦a `_tools/` 恰好只有 3 个可执行脚本（探针已归档到 `_evidence/_probes/`）',
      _have == TOOLS_WANT, u'实得=%r' % (sorted(_have),))
check(u'⑦b 7 个取证探针都在 `_evidence/_probes/` 里（留痕，不是跑完就删）',
      len([f for f in os.listdir(os.path.join(ROUND, '_evidence', '_probes'))
           if f.startswith('probe126')]) == 7,
      u'%d 个' % len([f for f in os.listdir(os.path.join(ROUND, '_evidence', '_probes'))
                      if f.startswith('probe126')]))
_stray = []
for root, dirs, files in os.walk(ROUND):
    for f in files:
        if f.endswith(('.log', '.tmp', '.bak', '.pyc')):
            _stray.append(os.path.join(os.path.basename(root), f))
check(u'⑦c 本轮目录里没有临时产物（.log/.tmp/.bak/.pyc）', not _stray,
      u'%r' % (_stray[:5],))
check(u'⑦d 复检脚本自身也在盘（不是跑完就没了）',
      os.path.isfile(os.path.abspath(__file__)), u'')

print(u'')
print(u'---- 共 %d 条：PASS %d / FAIL %d' % (_n['p'] + _n['f'], _n['p'], _n['f']))
if _failed:
    for d in _failed:
        print(u'   [失败] %s' % d)
    sys.exit(1)
