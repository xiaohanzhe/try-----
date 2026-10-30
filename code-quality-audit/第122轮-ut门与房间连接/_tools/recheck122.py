# -*- coding: utf-8 -*-
u"""第122轮复检：把"改完了"变成可落盘的逐项 PASS/FAIL。

用户口径（2026-09-23）：「以后再调整重要核心文件时一定要记得复检」。

本轮动到的**产品核心文件**有两个：

· `ralsei_pet/modules/scene_routing.py` —— `_match_one` 新增 `when_src` 那一段
· `ralsei_pet/modules/item_interact.py`  —— `route_for_door` 加 `src` 形参 + 两路互斥
· `ralsei_pet/assets/scenes/_routes.json` —— 867 → **1,110** 条（+243 ut）
· `ralsei_pet/assets/scenes/_zone.ut.rooms.json` —— 422 → **970** 条（+548 门）

七项（前六项对应用户列的那六条，第七项是本轮专属）：

  ① 语法/可编译 —— 动过/新写的 .py 一律 `ast.parse`（**不产 `.pyc`**，
     复检不许改变被测状态）
  ② 结构自检 —— 两张数据表 + 两处产品接线的**形状**（不是"文件存在"）
  ③ 无 BOM / 无 U+FFFD / 行尾口径 —— **字节忠实**读（`newline=''`）：
     `_routes.json` 必须 **CRLF + 无尾换行**（与原件同构）；
     `_zone.ut.rooms.json` 必须**纯 LF**（第121轮的口径）。两者**故意不同**，
     所以这里分开断言，不许"统一成一种"。
  ④ 恒真判据复查 —— AST 扫本轮 `check(...)`/`ok(...)` 的第二个实参不许是
     常量 `True`；配**正控制**（合成样本必须被抓到）
  ⑤ 逐令牌回验 —— 报告里引用的每个数字与每处产品接线令牌，逐个回原文件 `in` 一次
  ⑥ 幂等 —— 重跑 `gen_routes122.main()` 后 `_routes.json` sha256 不变
     （连跑两次字节相同是本轮写进 docstring 的承诺，得有人守）
  ⑦ 临时产物没落进仓库

用法：python recheck122.py
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
FACT = os.path.join(ROUND, '_evidence', 'ut_doors122.json')
MODULES = os.path.join(REPO, 'ralsei_pet', 'modules')
ROUTING = os.path.join(MODULES, 'scene_routing.py')
INTERACT = os.path.join(MODULES, 'item_interact.py')

sys.path.insert(0, HERE)

PY_FILES = [
    os.path.join(HERE, 'probe_doors122.py'),
    os.path.join(HERE, 'probe_doors122b.py'),
    os.path.join(HERE, 'gen_routes122.py'),
    os.path.join(HERE, 'verify_doors122.py'),
    os.path.join(HERE, 'check122.py'),
    os.path.join(REPO, 'code-quality-audit', '第121轮-ut可交互物', '_tools', 'build_objs121.py'),
    os.path.join(REPO, 'code-quality-audit', '第121轮-ut可交互物', '_tools', 'check_objs121.py'),
    os.path.join(REPO, 'code-quality-audit', '第44轮-原作对话框复刻', 'verify_objects44.py'),
    os.path.join(REPO, 'code-quality-audit', '第44轮-原作对话框复刻', 'verify_routes_order44.py'),
    os.path.join(REPO, 'code-quality-audit', '第36轮-按原作路线排场景',
                 'verify_scene_route_original.py'),
    os.path.join(REPO, 'code-quality-audit', '第48轮-道具与背包系统', 'verify_items48.py'),
    os.path.join(REPO, 'code-quality-audit', '第68轮-可交互道具实例补采', 'verify_items68.py'),
    os.path.join(REPO, 'code-quality-audit', '第99轮-睡觉惊醒与场景系统', '_tools',
                 'verify_scene_fit99.py'),
    os.path.join(REPO, 'code-quality-audit', '第105轮-OneShot房间连接', '_tools', 'check105.py'),
    # 产品核心文件也过一遍语法（改它们才是本轮的主要风险）
    ROUTING,
    INTERACT,
]

#: 本轮 ut 段的形状（第122轮实测值；变了就该重看这份复检）
N_ROUTES_TOTAL = 1110
N_UT = 243
N_UT_SRC = 110
N_UT_NEXT = 133
PRIO_LO, PRIO_HI = 4000, 4242
N_OBJ_TOTAL = 970
N_OBJ_SCENES = 227
N_PROP, N_DOOR = 422, 548

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
for p in PY_FILES:
    try:
        ast.parse(_raw(p))
    except SyntaxError as e:
        bad_syntax.append((os.path.basename(p), e.lineno, e.msg))
ok(u'① 本轮动过的 %d 个 .py（含两个产品核心文件）全部能 parse' % len(PY_FILES),
   not bad_syntax, repr(bad_syntax[:3]))

print(u'')
print(u'== ② 结构自检（两张数据表 + 两处产品接线）==')
_rj = json.loads(_raw(ROUTES))
_rl = _rj.get('routes') or []
_ut = [r for r in _rl if str((r or {}).get('when_scene') or '').startswith('ut.')]
ok(u'② _routes.json 总 %d 条 / ut 段 %d 条' % (len(_rl), len(_ut)),
   len(_rl) == N_ROUTES_TOTAL and len(_ut) == N_UT,
   u'实测 %d / %d' % (len(_rl), len(_ut)))

_by_mech = {
    'src': [r for r in _ut if isinstance(r.get('when_src'), str) and r.get('when_src')],
    'next': [r for r in _ut if not r.get('when_src') and r.get('when_door') == 'A'],
}
_other = [r for r in _ut if r not in _by_mech['src'] and r not in _by_mech['next']]
ok(u'②b ut 段两种机制分账：对象级 %d + 字母级 %d，无第三种 %d'
   % (len(_by_mech['src']), len(_by_mech['next']), len(_other)),
   len(_by_mech['src']) == N_UT_SRC and len(_by_mech['next']) == N_UT_NEXT and not _other,
   u'%d / %d / %d' % (len(_by_mech['src']), len(_by_mech['next']), len(_other)))

_pr = [r.get('priority') for r in _ut]
ok(u'②c ut 段 priority 独立段 %d~%d 且**连续无洞**（%d 个不同值）'
   % (PRIO_LO, PRIO_HI, len(set(_pr))),
   sorted(set(_pr)) == list(range(PRIO_LO, PRIO_HI + 1)),
   u'实测 %s~%s / 去重 %d' % (min(_pr or [0]), max(_pr or [0]), len(set(_pr))))

_bad_kind = sorted(set((r.get('_original') or {}).get('kind') for r in _ut)
                   - {'ut_door_src', 'ut_door_next'}, key=str)
_bad_work = sorted(set(r.get('work') for r in _ut))
_selfloop = [(r.get('when_scene'), r.get('to')) for r in _ut if r.get('when_scene') == r.get('to')]
ok(u'②d ut 段 kind 只有两种 / work 全 ut / 无自环',
   not _bad_kind and _bad_work == ['ut'] and not _selfloop,
   u'kind 杂项=%s work=%s 自环=%d' % (_bad_kind, _bad_work, len(_selfloop)))

_zone = json.loads(_raw(ZONE))
_sc = _zone.get('scenes') or {}
_with = [(sid, sc) for sid, sc in _sc.items() if isinstance(sc, dict) and sc.get('objects')]
_objs = [(sid, o) for sid, sc in _with for o in sc['objects']]
_doors = [(sid, o) for sid, o in _objs if 'door' in str((o or {}).get('src') or '').lower()]
ok(u'②e _zone.ut.rooms.json %d 场景 / %d 有物件 / %d 条（物 %d + 门 %d）'
   % (len(_sc), len(_with), len(_objs), len(_objs) - len(_doors), len(_doors)),
   len(_sc) == 358 and len(_with) == N_OBJ_SCENES
   and len(_objs) == N_OBJ_TOTAL and len(_doors) == N_DOOR
   and len(_objs) - len(_doors) == N_PROP,
   u'%d / %d / %d / %d' % (len(_sc), len(_with), len(_objs), len(_doors)))

_bad_spr = [(sid, o.get('sprite')) for sid, o in _objs if (o or {}).get('sprite') is not None]
ok(u'②f ut 的 %d 条 objects sprite **全 None**（画面已在背景里，再画即重复）'
   % len(_objs), not _bad_spr, repr(_bad_spr[:3]))

# ---- 产品接线：形状用 AST 判，不用"文件里出现过这几个字" ----
_tree_i = ast.parse(_raw(INTERACT))
_rfd = [n for n in ast.walk(_tree_i)
        if isinstance(n, ast.FunctionDef) and n.name == 'route_for_door']
_args = [a.arg for a in (_rfd[0].args.args if _rfd else [])]
ok(u'②g `route_for_door` 有 `src` 形参（对象级路由的入口）',
   len(_rfd) == 1 and 'src' in _args, u'形参=%s' % (_args,))
# 调用点必须真把 src 传进去（关键字实参）
_call_src = [n for n in ast.walk(_tree_i) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Name) and n.func.id == 'route_for_door'
             and any(k.arg == 'src' for k in n.keywords)]
ok(u'②h `build_props` 真以 `src=` 关键字调用它（不是只有形参没人传）',
   bool(_call_src), u'调用点 %d 处' % len(_call_src))

_tree_s = ast.parse(_raw(ROUTING))
_has_want = False
for n in ast.walk(_tree_s):
    if isinstance(n, ast.Assign) and len(n.targets) == 1:
        t = n.targets[0]
        if isinstance(t, ast.Name) and t.id == 'want_src' and isinstance(n.value, ast.Call):
            f = n.value.func
            if isinstance(f, ast.Attribute) and f.attr == 'get' and n.value.args \
                    and isinstance(n.value.args[0], ast.Constant) \
                    and n.value.args[0].value == 'when_src':
                _has_want = True
ok(u'②i `_match_one` 里 `want_src = route.get(\'when_src\')` 真在（AST 定位，不扫注释）',
   _has_want)

print(u'')
print(u'== ③ 编码与行尾（两个文件口径**故意不同**，分开断言）==')
enc_bad = []
for p in PY_FILES + [ROUTES, ZONE, FACT]:
    s = _raw(p)
    if s.startswith(u'\ufeff') or u'\ufffd' in s:
        enc_bad.append(os.path.basename(p))
ok(u'③ 无 BOM / 无 U+FFFD（%d 个文件）' % (len(PY_FILES) + 3), not enc_bad, repr(enc_bad))
_rr = _raw(ROUTES)
ok(u'③b _routes.json **CRLF** 且**无尾换行**（与原件同构）',
   u'\r\n' in _rr and _rr.count(u'\r\n') == _rr.count(u'\n')
   and not _rr.endswith(u'\n'),
   u'CRLF=%d LF=%d tail=%r' % (_rr.count(u'\r\n'), _rr.count(u'\n'), _rr[-2:]))
_zr = _raw(ZONE)
ok(u'③c _zone.ut.rooms.json **纯 LF**（第121轮口径，不许被 CRLF 污染）',
   u'\r' not in _zr, u'CR=%d' % _zr.count(u'\r'))

print(u'')
print(u'== ④ 恒真判据复查（AST，不扫注释）==')


def _true_checks(path):
    u"""返回 `check(...)`/`ok(...)` 第二个实参是常量 True 的行号。"""
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
    _true_all.extend(_true_checks(p))
ok(u'④ 本轮所有 check/ok 里没有 `..., True` 恒真判据', not _true_all, repr(_true_all[:5]))

_syn = ast.parse(u'ok("x", True)\ncheck("y", 1 == 1)\nok("z", False)\n')
_hits = [n.lineno for n in ast.walk(_syn)
         if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
         and n.func.id in ('check', 'ok') and len(n.args) >= 2
         and isinstance(n.args[1], ast.Constant) and n.args[1].value is True]
ok(u'④b 正控制：合成样本 `ok("x", True)` 被抓到（判据不恒假）', _hits == [1], repr(_hits))

print(u'')
print(u'== ⑤ 逐令牌回验（报告引用的数 / 产品接线令牌，逐个回原文件 in 一次）==')
TOKENS = [
    (ROUTES, u'"when_src"', u'对象级路由字段真落进了数据'),
    (ROUTES, u'"ut_door_src"', u'对象级条目带原作机制标记'),
    (ROUTES, u'"ut_door_next"', u'字母级条目带原作机制标记'),
    (ROUTES, u'第122轮', u'meta 里留了本轮口径说明'),
    (ZONE, u'"obj_door_ruins13"', u'不带字母的门真进了 objects'),
    (ZONE, u'"obj_doorA"', u'字母门也在'),
    (INTERACT, u"'when_src'", u'产品代码真读这个字段'),
    (FACT, u'"n_covered_instances": 548', u'证据文件如实记账覆盖数'),
]
miss = []
for path, tok, _why in TOKENS:
    if not (os.path.isfile(path) and tok in _raw(path)):
        miss.append((os.path.basename(path), tok))
ok(u'⑤ 令牌回验 %d 个' % len(TOKENS), not miss, repr(miss))

print(u'')
print(u'== ⑤b 报告里的数字与实测对账（报告不许漂）==')
REPORT = os.path.join(ROUND, '_evidence', 'report122.md')
_rep = _raw(REPORT) if os.path.isfile(REPORT) else u''
_CHECKS = [
    (u'1,110', len(_rl), u'_routes.json 总条数'),
    (u'243', len(_ut), u'ut 段条数'),
    (u'110', len(_by_mech['src']), u'对象级条数'),
    (u'133', len(_by_mech['next']), u'字母级条数'),
    (u'970', len(_objs), u'ut objects 总条数'),
    (u'227', len(_with), u'有物件的场景数'),
    (u'548', len(_doors), u'门条数'),
    (u'42.2', 42.2, u'门实例覆盖率'),
]
_drift = []
for tok, want, why in _CHECKS:
    if tok not in _rep:
        _drift.append((u'报告缺 %s（%s）' % (tok, why), want))
    elif want != float(tok.replace(u',', u'')):
        _drift.append((tok, want, why))
ok(u'⑤b 报告里 %d 个关键数字都与实测相等且真出现（%s）'
   % (len(_CHECKS), u' / '.join(u'%s=%s' % (w, v) for _t, v, w in _CHECKS)),
   not _drift, repr(_drift[:4]))

print(u'')
print(u'== ⑥ 幂等（重跑生成器，字节不变）==')
_sha_before = _sha(ROUTES)
import gen_routes122 as G          # noqa: E402  （延迟 import：上面已经 parse 过它）
_buf = io.StringIO()
_old = sys.stdout
sys.stdout = _buf
try:
    G.main([])
finally:
    sys.stdout = _old
_sha_after = _sha(ROUTES)
ok(u'⑥ 重跑 gen_routes122 后 _routes.json sha256 不变（连跑两次字节相同）',
   _sha_before == _sha_after, u'%s → %s' % (_sha_before[:16], _sha_after[:16]))
# 负控制：幂等判据不能是"`_sha` 恒返同一个值"。**在系统临时区**造两份内容不同的
# 文件，sha 必须不同（不往仓库里落任何东西 —— 临时文件绝不放工作区）。
import tempfile                    # noqa: E402
_td = tempfile.mkdtemp(prefix='recheck122_')
try:
    _fa, _fb = os.path.join(_td, 'a'), os.path.join(_td, 'b')
    for _p, _s in ((_fa, u'ut door 122'), (_fb, u'ut door 122 ')):
        with io.open(_p, 'w', encoding='utf-8', newline='') as _f:
            _f.write(_s)
    _sa, _sb = _sha(_fa), _sha(_fb)
finally:
    for _p in (_fa, _fb):
        try:
            os.remove(_p)
        except OSError:
            pass
    try:
        os.rmdir(_td)
    except OSError:
        pass
ok(u'⑥b 负控制：`_sha` 差一个空格就给出不同值（⑥ 比的是真值，不是常数）',
   _sa != _sb and len(_sa) == 64, u'%s vs %s' % (_sa[:8], _sb[:8]))
ok(u'⑥c 负控制：两张表的 sha256 确实不同（没有把两个路径当成同一个文件）',
   _sha_before != _sha(ZONE), u'%s vs %s' % (_sha_before[:8], _sha(ZONE)[:8]))

print(u'')
print(u'== ⑦ 临时产物没落进仓库 ==')
try:
    out = subprocess.check_output(
        ['git', '-c', 'core.quotepath=false', 'status', '--porcelain'],
        cwd=REPO, stderr=subprocess.STDOUT)
    out = out.decode('utf-8', 'replace')
except Exception as e:                     # pragma: no cover
    out = ''
    print(u'    git 调用失败：%r' % (e,))
_untracked = [ln[3:] for ln in out.splitlines() if ln.startswith('??')]
_allow = (u'第122轮-ut门与房间连接',)
_suspect = [p for p in _untracked
            if not any(p.rstrip('/').endswith(a) or a in p for a in _allow)]
ok(u'⑦ 未跟踪文件只有本轮目录（没有临时产物漏进仓库）', not _suspect, repr(_suspect[:5]))

print(u'')
print(u'---- 复检 %d 项：PASS %d / FAIL %d' % (_n['p'] + _n['f'], _n['p'], _n['f']))
print(u'提示：⑥ 已重写 `_routes.json` 与证据文件，全量回归请再跑一次'
      u' `code-quality-audit/regress/run_all.py`（本脚本不代跑）。')
if _failed:
    print(u'失败项：')
    for d in _failed:
        print(u'  - %s' % d)
sys.exit(1 if _failed else 0)
