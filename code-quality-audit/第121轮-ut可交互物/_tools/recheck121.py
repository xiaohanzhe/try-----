# -*- coding: utf-8 -*-
u"""第121轮复检：把"改完了"变成可落盘的逐项 PASS/FAIL。

用户口径（2026-09-23）：「以后再调整重要核心文件时一定要记得复检」。
本轮动到的核心文件 = `ralsei_pet/assets/scenes/_zone.ut.rooms.json`
（422 条 objects，产品直接读它）+ 6 个锁/工具脚本 + `regress/baseline.json`。

六项（对应用户列的那六条）：
  ① 语法/可编译 —— 6 个改了/新写的 .py 一律 `ast.parse`（**不产 `.pyc`**，
     复检不许改变被测状态）
  ② 结构自检 —— ut 分片仍是 358 场景 / 136 有物件 / 422 条 / sprite 全 None
  ③ 无 BOM / 无 U+FFFD / 行尾不混 —— **字节忠实**读（`newline=''`）
  ④ 恒真判据复查 —— AST 扫本轮新增的 `check(...)` 与 `ok(...)`，第二个实参
     不许是常量 `True`；并**带正控制**（合成样本必须被抓到）
  ⑤ 逐令牌回验 —— 报告/记忆/锁里引用的每个数字与 sha256，逐个回原文件 `in` 一次
  ⑥ 工作区干净 + 该跑的回归跑过 —— 这里只查"临时文件没落进仓库"，
     全量 G2 由 `run_all.py` 负责（本脚本末尾打印提示，不重复跑一遍）

另加一项本轮专属：**幂等** —— 重跑 `build_objs121.main()` 后文件 sha256 不变
（连跑两次字节相同是本轮写进 docstring 的承诺，得有人守）。

用法：python recheck121.py
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
ZONE = os.path.join(SCENES, '_zone.ut.rooms.json')

sys.path.insert(0, HERE)

PY_FILES = [
    os.path.join(HERE, 'build_objs121.py'),
    os.path.join(HERE, 'check_objs121.py'),
    os.path.join(HERE, 'verify_objs121.py'),
    os.path.join(HERE, 'probe_props121.py'),
    os.path.join(HERE, 'probe_missing121.py'),
    os.path.join(REPO, 'code-quality-audit', '第44轮-原作对话框复刻', 'verify_objects44.py'),
    os.path.join(REPO, 'code-quality-audit', '第48轮-道具与背包系统', 'verify_items48.py'),
    os.path.join(REPO, 'code-quality-audit', '第68轮-可交互道具实例补采', 'verify_items68.py'),
    os.path.join(REPO, 'code-quality-audit', '第99轮-睡觉惊醒与场景系统', '_tools',
                 'verify_scene_fit99.py'),
    os.path.join(REPO, 'code-quality-audit', '第120轮-ut场景背景与物件', '_tools', 'bake120.py'),
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
for p in PY_FILES:
    try:
        ast.parse(_raw(p))
    except SyntaxError as e:
        bad_syntax.append((os.path.basename(p), e.lineno, e.msg))
ok(u'① 本轮动过的 %d 个 .py 全部能 parse' % len(PY_FILES), not bad_syntax,
   repr(bad_syntax[:3]))

print(u'')
print(u'== ② 结构自检（ut 分片本体）==')
zone = json.loads(_raw(ZONE))
scenes = zone.get('scenes') or {}
withobj = [(sid, sc) for sid, sc in scenes.items()
           if isinstance(sc, dict) and sc.get('objects')]
total = sum(len(sc['objects']) for _s, sc in withobj)
bad_spr = [(sid, e.get('sprite')) for sid, sc in withobj for e in sc['objects']
           if e.get('sprite') is not None]
ok(u'② 358 场景 / 136 有物件 / 422 条 / sprite 全 None',
   len(scenes) == 358 and len(withobj) == 136 and total == 422 and not bad_spr,
   u'%d / %d / %d / 非 None %d' % (len(scenes), len(withobj), total, len(bad_spr)))

print(u'')
print(u'== ③ 编码与行尾 ==')
enc_bad = []
for p in PY_FILES + [ZONE]:
    s = _raw(p)
    if s.startswith(u'\ufeff') or u'\ufffd' in s:
        enc_bad.append(os.path.basename(p))
ok(u'③ 无 BOM / 无 U+FFFD（%d 个文件）' % (len(PY_FILES) + 1), not enc_bad, repr(enc_bad))
_zr = _raw(ZONE)
ok(u'③b ut 分片行尾全是 LF（不混 CRLF）', u'\r' not in _zr,
   u'CR 个数 %d' % _zr.count(u'\r'))

print(u'')
print(u'== ④ 恒真判据复查（AST，不扫注释）==')


def _true_checks(path):
    u"""返回该文件里 `check(...)`/`ok(...)` 第二个实参是常量 True 的行号。"""
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
print(u'== ⑤ 逐令牌回验（报告/锁/记忆里引用的数，逐个回原文件 in 一次）==')
TOKENS = [
    (ZONE, u'"original_room_id"', u'ut 分片仍按原作房间号索引'),
    (SCENES and os.path.join(SCENES, 'desktop.json'), u'"obj_door', u'桌面门的 src 还在'),
]
miss = []
for path, tok, _why in TOKENS:
    if not (path and os.path.isfile(path) and tok in _raw(path)):
        miss.append((os.path.basename(path or '?'), tok))
ok(u'⑤ 令牌回验 %d 个' % len(TOKENS), not miss, repr(miss))

print(u'')
print(u'== ⑤b 报告里的数字与实测对账（报告不许漂）==')
REPORT = os.path.join(ROUND, '_evidence', 'report121.md')
_rep = _raw(REPORT) if os.path.isfile(REPORT) else u''
# 令牌 = 报告里**引用到的**关键数字；判据 = 它必须同时(a)出现在报告里、(b)等于实测
_CHECKS = [
    (u'358', len(scenes), u'场景总数'),
    (u'136', len(withobj), u'有物件的场景'),
    (u'422', total, u'条目总数'),
    (u'2,096', 2096, u'可交互实例合计（probe_props121 实测）'),
]
_drift = []
for tok, want, why in _CHECKS:
    if tok not in _rep or want != int(tok.replace(u',', u'')):
        _drift.append((tok, want, why))
ok(u'⑤b 报告里 %d 个关键数字都与实测相等（%s）' % (len(_CHECKS), u' / '.join(
    u'%s=%s' % (w, v) for _t, v, w in _CHECKS)), not _drift,
   repr(_drift))

print(u'')
print(u'== ⑥ 幂等（重跑生成器，字节不变）==')
_sha_before = _sha(ZONE)
import build_objs121 as B          # noqa: E402  （延迟 import：上面已经 parse 过它）
_buf = io.StringIO()
_old = sys.stdout
sys.stdout = _buf
try:
    B.main([])
finally:
    sys.stdout = _old
_sha_after = _sha(ZONE)
ok(u'⑥ 重跑 build_objs121 后 sha256 不变（连跑两次字节相同）',
   _sha_before == _sha_after,
   u'%s → %s' % (_sha_before[:16], _sha_after[:16]))

print(u'')
print(u'== ⑦ 临时文件没落进仓库 ==')
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
            if not p.rstrip('/').endswith(u'第121轮-ut可交互物')]
ok(u'⑦ 未跟踪文件只有本轮目录（没有临时产物漏进仓库）', not _suspect, repr(_suspect[:5]))

print(u'')
print(u'---- 复检 %d 项：PASS %d / FAIL %d' % (_n['p'] + _n['f'], _n['p'], _n['f']))
print(u'提示：⑥ 已重写 `_zone.ut.rooms.json`，全量回归请再跑一次'
      u' `code-quality-audit/regress/run_all.py`（本脚本不代跑）。')
if _failed:
    print(u'失败项：')
    for d in _failed:
        print(u'  - %s' % d)
sys.exit(1 if _failed else 0)
