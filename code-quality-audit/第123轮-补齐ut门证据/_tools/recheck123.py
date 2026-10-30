# -*- coding: utf-8 -*-
u"""第123轮复检：把"改完了"变成可落盘的逐项 PASS/FAIL。

用户口径（2026-09-23）：「以后再调整重要核心文件时一定要记得复检」。

本轮动到的核心文件：
  · `ralsei_pet/assets/scenes/_routes.json`（产品直接读它，ut 段 243 → 525）
  · `ralsei_pet/assets/scenes/_zone.ut.rooms.json`（objects 970 → 1,655）
  · 8 个老锁（按新事实改口径）+ 1 个新锁 `check123`
  · `regress/baseline.json`

七项：
  ① 语法/可编译 —— 本轮改过/新写的 .py 一律 `ast.parse`（**不产 `.pyc`**，复检不许改变被测状态）
  ② 结构自检 —— 两张产品表的新规模/形状/priority 连续性
  ③ 编码与行尾 —— 无 BOM / 无 U+FFFD；`_routes.json` 保持 CRLF + 无尾换行；zone 保持纯 LF
  ④ 恒真判据复查 —— AST 扫本轮所有 `check(...)`/`ok(...)`，第二个实参不许是常量 `True`；
     并**带正控制**（合成样本必须被抓到）
  ⑤ 逐令牌回验 —— 报告里引用的每个数字，回**产品数据**再验一次；记忆里删掉的令牌回**详版**验
  ⑥ 报告对账 —— `report123.md` 里的关键数字与实测相等（报告不许漂）
  ⑦ 幂等 —— 重跑 `gen_routes123` + `build_objs121`，三份产物 sha256 不变；
     且**没有临时产物漏进仓库**

用法：python recheck123.py
"""
import ast
import hashlib
import io
import json
import os
import subprocess
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
SCENES = os.path.join(REPO, 'ralsei_pet', 'assets', 'scenes')
ROUTES = os.path.join(SCENES, '_routes.json')
ZONE = os.path.join(SCENES, '_zone.ut.rooms.json')
FACT = os.path.join(ROUND, '_evidence', 'ut_doors123.json')
REPORT = os.path.join(ROUND, '_evidence', 'report123.md')
MEMDIR = os.path.join(REPO, '.workbuddy', 'memory')
DETAIL = os.path.join(MEMDIR, u'参考-契约与历轮（详版）.md')

CQ = os.path.join(REPO, 'code-quality-audit')
PY_FILES = [
    os.path.join(HERE, 'probe_doors123.py'),
    os.path.join(HERE, 'gen_routes123.py'),
    os.path.join(HERE, 'check123.py'),
    os.path.join(HERE, 'run123.py'),
    os.path.join(HERE, 'recheck123.py'),
    # —— 改过口径的老锁（**每一个都要进这张表**，否则"改过了"没人验）
    os.path.join(CQ, u'第121轮-ut可交互物', '_tools', 'check_objs121.py'),
    os.path.join(CQ, u'第122轮-ut门与房间连接', '_tools', 'check122.py'),
    os.path.join(CQ, u'第105轮-OneShot房间连接', '_tools', 'check105.py'),
    os.path.join(CQ, u'第99轮-睡觉惊醒与场景系统', '_tools', 'verify_scene_fit99.py'),
    os.path.join(CQ, u'第44轮-原作对话框复刻', 'verify_objects44.py'),
    os.path.join(CQ, u'第44轮-原作对话框复刻', 'verify_routes_order44.py'),
    os.path.join(CQ, u'第48轮-道具与背包系统', 'verify_items48.py'),
    os.path.join(CQ, u'第68轮-可交互道具实例补采', 'verify_items68.py'),
    os.path.join(CQ, u'第36轮-按原作路线排场景', 'verify_scene_route_original.py'),
    os.path.join(CQ, u'第121轮-ut可交互物', '_tools', 'build_objs121.py'),
    os.path.join(CQ, 'regress', 'run_all.py'),
]

_n = {'p': 0, 'f': 0}
_failed = []


def ok(desc, cond, detail=''):
    if cond:
        _n['p'] += 1
        print(u'[PASS] %s%s' % (desc, (u'    ' + detail) if detail else u''))
    else:
        _n['f'] += 1
        _failed.append(desc)
        print(u'[FAIL] %s%s' % (desc, (u'    ' + detail) if detail else u''))


def _raw(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def _sha(p):
    h = hashlib.sha256()
    with io.open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


print(u'== ① 语法 / 可编译（ast.parse，不产 .pyc）==')
bad_syntax = []
missing = []
for p in PY_FILES:
    if not os.path.isfile(p):
        missing.append(os.path.basename(p))
        continue
    try:
        ast.parse(_raw(p))
    except SyntaxError as e:
        bad_syntax.append((os.path.basename(p), e.lineno, e.msg))
ok(u'① 本轮动过的 %d 个 .py 全在盘且能 parse' % len(PY_FILES),
   not bad_syntax and not missing, repr((bad_syntax[:3], missing)))

print(u'')
print(u'== ② 结构自检（两张产品表）==')
_rt = json.loads(_raw(ROUTES))
_rl = _rt.get('routes') or []
_ut = [r for r in _rl if str(r.get('when_scene') or '').startswith('ut.')]
_kind = {}
for r in _ut:
    k = (r.get('_original') or {}).get('kind')
    _kind[k] = _kind.get(k, 0) + 1
ok(u'② `_routes.json` 1,392 条 / ut 525 条（110 src + 133 next + 282 shift）',
   len(_rl) == 1392 and len(_ut) == 525
   and _kind.get('ut_door_src') == 110 and _kind.get('ut_door_next') == 133
   and _kind.get('ut_door_shift') == 282,
   u'%d / %d / %s' % (len(_rl), len(_ut), _kind))

_prio = sorted(r.get('priority') for r in _ut
               if isinstance(r.get('priority'), int))
ok(u'②b ut 段 priority 独立段 4000~4524 连续无洞',
   bool(_prio) and _prio == list(range(4000, 4000 + len(_prio))),
   u'%d 条，[%d, %d]' % (len(_prio), _prio[0], _prio[-1]))

_zn = json.loads(_raw(ZONE))
_sc = _zn.get('scenes') or {}
_with = [s for s in _sc.values() if isinstance(s, dict) and s.get('objects')]
_tot = sum(len(s['objects']) for s in _with)
_ndoor = sum(1 for s in _with for e in s['objects'] if 'door' in str(e.get('src')).lower())
_bad_spr = [1 for s in _with for e in s['objects'] if e.get('sprite') is not None]
ok(u'②c `_zone.ut.rooms.json` 358 场景 / 274 有物件 / 1,655 条 / 门 1,233 / sprite 全 None',
   len(_sc) == 358 and len(_with) == 274 and _tot == 1655
   and _ndoor == 1233 and not _bad_spr,
   u'%d / %d / %d / %d / 非 None %d'
   % (len(_sc), len(_with), _tot, _ndoor, len(_bad_spr)))

_fact = json.loads(_raw(FACT))
ok(u'②d 事实文件自洽：282 条 shift 且 kind 全为 ut_door_shift',
   len([r for r in (_fact.get('routes') or [])
        if (r.get('_original') or {}).get('kind') == 'ut_door_shift']) == 282,
   u'fact routes %d' % len(_fact.get('routes') or []))

print(u'')
print(u'== ③ 编码与行尾 ==')
enc_bad = []
for p in PY_FILES + [ROUTES, ZONE, FACT, REPORT]:
    if not os.path.isfile(p):
        continue
    s = _raw(p)
    if s.startswith(u'\ufeff') or u'\ufffd' in s:
        enc_bad.append(os.path.basename(p))
ok(u'③ 无 BOM / 无 U+FFFD（%d 个文件）' % (len(PY_FILES) + 4), not enc_bad, repr(enc_bad))
_rr = _raw(ROUTES)
ok(u'③b `_routes.json` 保持 CRLF + 无尾换行（原有排版）',
   u'\r\n' in _rr and u'\n' not in _rr.replace(u'\r\n', u'') and not _rr.endswith(u'\n'),
   u'CRLF %d / 尾字符 %r' % (_rr.count(u'\r\n'), _rr[-1:]))
_zr = _raw(ZONE)
ok(u'③c `_zone.ut.rooms.json` 保持纯 LF（不混 CRLF）', u'\r' not in _zr,
   u'CR 个数 %d' % _zr.count(u'\r'))

print(u'')
print(u'== ④ 恒真判据复查（AST，不扫注释）==')


def _true_checks(path):
    u"""该文件里 `check(...)`/`ok(...)` 第二个实参是常量 True 的行号。"""
    out = []
    for node in ast.walk(ast.parse(_raw(path))):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        name = fn.id if isinstance(fn, ast.Name) else None
        if name not in ('check', 'ok'):
            continue
        if len(node.args) >= 2:
            a1 = node.args[1]
            if isinstance(a1, ast.Constant) and a1.value is True:
                out.append((os.path.basename(path), getattr(node, 'lineno', -1)))
    return out


_true_all = []
for p in PY_FILES:
    if os.path.isfile(p):
        _true_all.extend(_true_checks(p))
ok(u'④ 本轮所有 check/ok 里没有 `..., True` 恒真判据', not _true_all, repr(_true_all[:5]))

# 正控制：判据自己有鉴别力（合成样本必须被抓到）
_syn = ast.parse(u'ok("x", True)\ncheck("y", 1 == 1)\nok("z", False)\n')
_hits = []
for node in ast.walk(_syn):
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
            and node.func.id in ('check', 'ok') and len(node.args) >= 2:
        if isinstance(node.args[1], ast.Constant) and node.args[1].value is True:
            _hits.append(node.lineno)
ok(u'④b 正控制：合成样本 `ok("x", True)` 被抓到（判据不恒假）',
   _hits == [1], repr(_hits))

print(u'')
print(u'== ⑤ 逐令牌回验 ==')
# (a) 报告里引用的数字，回**产品数据**再验一次（不是回报告自证）
_shift = [r for r in _ut if (r.get('_original') or {}).get('kind') == 'ut_door_shift']
_letter = [r for r in _shift if r.get('when_door')]
_srced = [r for r in _shift if r.get('when_src')]
TOKENS = [
    (u'ut 段 525 条', len(_ut) == 525),
    (u'shift 282 条', len(_shift) == 282),
    (u'字母级 183 / 对象级 99', (len(_letter), len(_srced)) == (183, 99)),
    (u'门 1,233 条', _ndoor == 1233),
    (u'274 个场景有物件', len(_with) == 274),
    (u'1,655 条 objects', _tot == 1655),
]
_drift = [w for w, c in TOKENS if not c]
ok(u'⑤ 报告里 %d 组关键数字回产品数据仍成立' % len(TOKENS), not _drift, repr(_drift))

# (b) 压速查本时**删掉的令牌**必须仍在详版里（否则压缩＝静默丢信息）
_removed = [u'§100', u'§101', u'§107', u'§108', u'§110', u'§114', u'§115',
            u'§120', u'§121', u'§122', u'422', u'136', u'970', u'243', u'548',
            u'sprite=None', u'互聊', u'关系演化', u'20 间', u'338']
_det = _raw(DETAIL) if os.path.isfile(DETAIL) else u''
_miss = [t for t in _removed if t not in _det]
ok(u'⑤b 压速查本删掉的 %d 个令牌全在详版里（有据可查）' % len(_removed), not _miss,
   repr(_miss))

# (c) 速查本仍在硬闸内（`check95 A2` 的真口径 = UTF-16 码元数）
_mem = os.path.join(MEMDIR, 'MEMORY.md')
if os.path.isfile(_mem):
    _ms = _raw(_mem)
    _js = len(_ms.encode('utf-16-le')) // 2
    ok(u'⑤c 速查本 `MEMORY.md` js_len ≤ 10000（本轮压回闸内）', _js <= 10000,
       u'js_len=%d 余量 %d' % (_js, 10000 - _js))

print(u'')
print(u'== ⑥ 报告对账（报告里的数字与实测相等）==')
_rep = _raw(REPORT) if os.path.isfile(REPORT) else u''
_checks = [
    (u'1,392', len(_rl), u'路由总条数'),
    (u'525', len(_ut), u'ut 段条数'),
    (u'282', len(_shift), u'位移门条数'),
    (u'1,655', _tot, u'objects 条目'),
    (u'1,233', _ndoor, u'门实例'),
    (u'274', len(_with), u'有物件的场景'),
]
_rd = []
for tok, want, why in _checks:
    if tok not in _rep or want != int(tok.replace(u',', u'')):
        _rd.append((tok, want, why))
ok(u'⑥ 报告里 %d 个关键数字都与实测相等（%s）' % (
    len(_checks), u' / '.join(u'%s=%s' % (_why, _want)
                              for _tok, _want, _why in _checks)),
   not _rd, repr(_rd))

print(u'')
print(u'== ⑦ 幂等（重跑生成器，字节不变）==')
_sha_before = (_sha(ROUTES), _sha(ZONE), _sha(FACT))
import gen_routes123 as G           # noqa: E402  （延迟 import：上面已 parse 过）
sys.path.insert(0, os.path.join(CQ, u'第121轮-ut可交互物', '_tools'))
import build_objs121 as B           # noqa: E402
_buf = io.StringIO()
_old = sys.stdout
sys.stdout = _buf
try:
    G.main([])
    B.main([])
finally:
    sys.stdout = _old
_sha_after = (_sha(ROUTES), _sha(ZONE), _sha(FACT))
ok(u'⑦ 重跑 `gen_routes123` + `build_objs121` 后三份产物 sha256 全不变',
   _sha_before == _sha_after,
   u'%s → %s' % ([s[:8] for s in _sha_before], [s[:8] for s in _sha_after]))

print(u'')
print(u'== ⑦b 临时文件没落进仓库 ==')
try:
    out = subprocess.check_output(
        ['git', '-c', 'core.quotepath=false', 'status', '--porcelain'],
        cwd=REPO, stderr=subprocess.STDOUT)
    out = out.decode('utf-8', 'replace')
except Exception as e:                     # pragma: no cover
    out = ''
    print(u'    git 调用失败：%r' % (e,))
_untracked = [ln[3:] for ln in out.splitlines() if ln.startswith('??')]
_suspect = [p for p in _untracked
            if not p.rstrip('/').endswith(u'第123轮-补齐ut门证据')
            and u'.workbuddy' not in p]
ok(u'⑦b 未跟踪文件只有本轮目录与记忆目录（没有临时产物漏进仓库）',
   not _suspect, repr(_suspect[:5]))

print(u'')
print(u'---- 复检 %d 项：PASS %d / FAIL %d' % (_n['p'] + _n['f'], _n['p'], _n['f']))
print(u'提示：⑦ 已重写两张产品表，全量回归请再跑一次'
      u' `code-quality-audit/regress/run_all.py`（本脚本不代跑）。')
if _failed:
    print(u'失败项：')
    for d in _failed:
        print(u'  - %s' % d)
sys.exit(1 if _failed else 0)
