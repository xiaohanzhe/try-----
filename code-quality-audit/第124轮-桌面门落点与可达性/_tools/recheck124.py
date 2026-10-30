# -*- coding: utf-8 -*-
u"""第124轮复检：把"改完了"变成可落盘的逐项 PASS/FAIL。

用户口径（2026-09-23）：「以后再调整重要核心文件时一定要记得复检」。

## 本轮动到的核心文件

  · `ralsei_pet/assets/scenes/_routes.json` —— 桌面 C 门的 `to`
    `ut.rooms.room_start` → **`ut.rooms.room_area1`**（+ `reason` 重写）
  · `第89轮/check89.py` —— `_A_DOOR_WORLD['C']` 落点 ·
    **`B4c` 的 `_room_want['C']` 0 → 4**（这条是纠错，不是放宽）
  · `第105轮/check105.py` —— `OLD_FP` 指纹锚点（+ 变更范围说明）
  · `第44轮/verify_routes_order44.py` —— `C2` 断链数 60 → 59 的归因注释
  · 新锁 `check124` + `regress/run_all.py` 登记 + `baseline.json`

## 六项

  ① 语法 —— 本轮改过/新写的 .py 一律 `ast.parse`
     （**不产 `.pyc`**：复检不许改变被测状态）
  ② 结构 —— 桌面 4 条路由字段完整 · C 门落点 == `room_area1` ·
     落点能真读出场景（bg 在盘）· **既有段守恒**（非 desktop 的 443 条指纹仍是
     `f4e3d7d0…`，证明改动**只落在 1 条**上）
  ③ 编码与行尾 —— 无 BOM / 无 U+FFFD；`_routes.json` 保持 CRLF +
     0 个裸 LF + 无尾换行（尾是 `\\r\\n}`）；routes 仍 1,392 条
  ④ 恒真判据复查 —— AST 扫本轮所有 `check(...)`/`ok(...)`，
     第二个实参不许是常量 `True`；**带正控制**（合成样本必须被抓到）
  ⑤ 逐令牌回验 —— 报告/记忆里引用的每个数字，回**产品数据**再验一次
  ⑥ 报告对账 + 无临时产物 —— `report124.md` 的关键数字与实测相等；
     `第124轮` 目录里只许有 `_tools/check124.py`·`_tools/recheck124.py`·
     `_evidence/report124.md`

用法：python recheck124.py
"""
import ast
import hashlib
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
REPORT = os.path.join(ROUND, '_evidence', 'report124.md')
MEMDIR = os.path.join(REPO, '.workbuddy', 'memory')
DETAIL = os.path.join(MEMDIR, u'参考-契约与历轮（详版）.md')
CQ = os.path.join(REPO, 'code-quality-audit')

for _p in (PKG, os.path.join(PKG, 'modules')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

PY_FILES = [
    os.path.join(HERE, 'check124.py'),
    os.path.join(HERE, 'recheck124.py'),
    # —— 改过口径的老锁（每一个都要进这张表，否则"改过了"没人验）
    os.path.join(CQ, u'第89轮-桌面与作品场景连通', '_tools', 'check89.py'),
    os.path.join(CQ, u'第105轮-OneShot房间连接', '_tools', 'check105.py'),
    os.path.join(CQ, u'第44轮-原作对话框复刻', 'verify_routes_order44.py'),
    os.path.join(CQ, 'regress', 'run_all.py'),
]

#: 既有段（非 desktop / 非 oneshot / 非 ut）在**第105轮**就确定了的指纹。
#: 本轮只改了 desktop 的 1 条 ⇒ 这个值**必须一位不变**，否则说明改到了别处。
OLD_NO_DESK_FP_105 = 'f4e3d7d00f36d90fb9fa9c79018d146da8edc9e944b33e811c054ae2265232f8'

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


def _read(p):
    with io.open(p, encoding='utf-8', newline='') as fh:
        return fh.read()


def _json(p):
    return json.loads(_read(p))


def _fp(rows):
    """与 `check105.fp` 同一口径（键排序 + 逐条 + 换行分隔的 sha256）。"""
    h = hashlib.sha256()
    for r in rows:
        h.update(json.dumps(r, ensure_ascii=False, sort_keys=True).encode('utf-8'))
        h.update(b'\n')
    return h.hexdigest()


# ===========================================================================
print(u'')
print(u'== ① 语法 ==')
# ===========================================================================
_bad = []
for _p in PY_FILES:
    rel = os.path.relpath(_p, REPO)
    if not os.path.isfile(_p):
        _bad.append(u'%s 不存在' % rel)
        continue
    try:
        ast.parse(_read(_p))          # ★ 不写 .pyc，不改变被测状态
    except SyntaxError as exc:
        _bad.append(u'%s: %s' % (rel, exc))
ok(u'① 本轮改过/新写的 %d 个 .py 全部能 `ast.parse`' % len(PY_FILES), not _bad,
   u'%r' % (_bad[:3],))

# ===========================================================================
print(u'')
print(u'== ② 结构 ==')
# ===========================================================================
from modules import scene_system as SS       # noqa: E402

_raw = _json(ROUTES) or {}
RL = _raw.get('routes') or []
IDX = SS.load_index(SCENES)
SC = IDX.get('scenes') or {}

_desk = sorted([r for r in RL if r.get('when_scene') == 'desktop'],
               key=lambda r: str(r.get('when_door')))
ok(u'②a 桌面段仍 4 条、字母 A~D、`to` 与 `reason` 都非空',
   len(_desk) == 4 and sorted(r.get('when_door') for r in _desk) == ['A', 'B', 'C', 'D']
   and all(r.get('to') and r.get('reason') for r in _desk),
   u'%r' % ([r.get('when_door') for r in _desk],))

_m = {r.get('when_door'): r.get('to') for r in _desk}
ok(u'②b C 门落点 == `ut.rooms.room_area1`（不是 `room_start`）',
   _m.get('C') == 'ut.rooms.room_area1',
   u'C -> %r' % (_m.get('C'),))

_sc = SS.load_scene('ut.rooms.room_area1', SCENES, SC.get('ut.rooms.room_area1'))
_bg = getattr(_sc, 'bg', None) if _sc is not None else None
_bgp = os.path.join(SCENES, _bg.replace('/', os.sep)) if isinstance(_bg, str) and _bg else u''
ok(u'②c 落点能真读出场景：`load_scene` 非空 · bg 非空 · 文件在盘',
   _sc is not None and isinstance(_bg, str) and bool(_bg) and os.path.isfile(_bgp),
   u'bg=%r' % (_bg,))

# ★★★ 守恒：本轮**只许动 desktop 那 1 条**。
_OLD = [r for r in RL if not str((r or {}).get('when_scene') or '').startswith(('oneshot', 'ut.'))]
_NODESK = [r for r in _OLD if r.get('when_scene') != 'desktop']
ok(u'②d 既有段守恒：非 desktop 的 %d 条指纹仍是第105轮值 `f4e3d7d0…`'
   u'（证明改动只落在 desktop 段）' % len(_NODESK),
   len(_NODESK) == 443 and _fp(_NODESK) == OLD_NO_DESK_FP_105,
   u'n=%d fp=%s…' % (len(_NODESK), _fp(_NODESK)[:16]))

# ===========================================================================
print(u'')
print(u'== ③ 编码与行尾 ==')
# ===========================================================================
with io.open(ROUTES, 'rb') as _fh:
    _rb = _fh.read()
_crlf = _rb.count(b'\r\n')
_bare = _rb.count(b'\n') - _crlf
ok(u'③a `_routes.json`：CRLF %d / 裸 LF %d（后者必须 0）' % (_crlf, _bare), _bare == 0,
   u'tail=%r' % (_rb[-6:],))
ok(u'③b `_routes.json` 无尾换行（文件尾是 `\\r\\n}`）', _rb.endswith(b'\r\n}'),
   u'tail=%r' % (_rb[-4:],))
_text = _rb.decode('utf-8')
ok(u'③c `_routes.json` 无 BOM / 无 U+FFFD',
   not _text.startswith(u'\ufeff') and u'\ufffd' not in _text)
ok(u'③d routes 仍 %d 条（改字段不改条数）' % len(RL), len(RL) == 1392, u'%d' % len(RL))

# ===========================================================================
print(u'')
print(u'== ④ 恒真判据复查 ==')
# ===========================================================================
CHECKED = [
    os.path.join(HERE, 'check124.py'),
    os.path.join(CQ, u'第89轮-桌面与作品场景连通', '_tools', 'check89.py'),
    os.path.join(CQ, u'第105轮-OneShot房间连接', '_tools', 'check105.py'),
    os.path.join(CQ, u'第44轮-原作对话框复刻', 'verify_routes_order44.py'),
]


def _true_checks(path):
    out = []
    for node in ast.walk(ast.parse(_read(path))):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        name = fn.id if isinstance(fn, ast.Name) else None
        if name not in ('check', 'ok'):
            continue
        if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant) \
                and node.args[1].value is True:
            out.append((os.path.basename(path), node.lineno))
    return out


_hits = []
for _p in CHECKED:
    _hits.extend(_true_checks(_p))
ok(u'④a %d 个判据文件里没有 `check(x, True)` 恒真写法（AST 判，不扫注释）' % len(CHECKED),
   not _hits, u'%r' % (_hits[:4],))

# 正控制：合成样本必须被抓到（否则 ④a 可能是把 AST 扫歪了才"全清"）
_neg = ast.parse(u'check("x", True)\nok("y", 1 == 1)\ncheck("z", False)\n')
_neg_hit = [n.lineno for n in ast.walk(_neg)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name) and n.func.id in ('check', 'ok')
            and len(n.args) >= 2 and isinstance(n.args[1], ast.Constant)
            and n.args[1].value is True]
ok(u'④b 正控制：合成样本里的 `check("x", True)` 会被抓到（口径有鉴别力）',
   _neg_hit == [1], u'%r' % (_neg_hit,))

# ===========================================================================
print(u'')
print(u'== ⑤ 逐令牌回验（回产品数据） ==')
# ===========================================================================
OUT = {}
for _r in RL:
    _s, _t = _r.get('when_scene'), _r.get('to')
    if _s and _t:
        OUT.setdefault(_s, set()).add(_t)

_RID_A1 = (SC.get('ut.rooms.room_area1') or {}).get('original_room_id')
_RID_ST = (SC.get('ut.rooms.room_start') or {}).get('original_room_id')
_NOOUT_ST = len(OUT.get('ut.rooms.room_start', ()))
_OUT_A1 = len(OUT.get('ut.rooms.room_area1', ()))
_NOOUT_ALL = sum(1 for _s in SC if not OUT.get(_s))

_CHECKS = [
    (1392, len(RL), u'routes 总条数'),
    (2166, len(SC), u'场景总数'),
    (4, len(_desk), u'桌面门数'),
    (4, _RID_A1, u'room_area1 原作下标'),
    (0, _RID_ST, u'room_start 原作下标'),
    (0, _NOOUT_ST, u'room_start 出边'),
    (1, _OUT_A1, u'room_area1 出边'),
    (1402, _NOOUT_ALL, u'完全无出边的场景数'),
]
_tok_bad = [(w, g, why) for (w, g, why) in _CHECKS if w != g]
for _w, _g, _why in _CHECKS:
    print(u'    %-22s 期望 %-6r 实测 %-6r %s' % (_why, _w, _g, u'OK' if _w == _g else u'**不符**'))
ok(u'⑤a 报告/记忆引用的 %d 个数字逐个回产品数据验过' % len(_CHECKS), not _tok_bad,
   u'%r' % (_tok_bad,))

# ⑤b 记忆侧：本轮新增进记忆的令牌必须真的在（防"写了但没落盘"）
_MEM_TOKENS = [u'check124', u'room_area1', u'199']
_mem_txt = _read(DETAIL) if os.path.isfile(DETAIL) else u''
_mem_miss = [_t for _t in _MEM_TOKENS if _t not in _mem_txt]
ok(u'⑤b 详版里含本轮令牌 %r（记忆确实落了盘）' % (_MEM_TOKENS,), not _mem_miss,
   u'缺 %r' % (_mem_miss,))

# ===========================================================================
print(u'')
print(u'== ⑥ 报告对账 + 无临时产物 ==')
# ===========================================================================
if os.path.isfile(REPORT):
    _rep = _read(REPORT)
    # ★★ 令牌允许**等价写法**：报告里写的是 `2,166` / `1,392`（带千分位），
    #   令牌是 `2166` / `1392`。两边都把逗号归一后再比 ——
    #   **判据太窄 = 误报**（本条第一版就这么报了假红，正是记忆里"token 回验允许
    #   等价写法"那条）。不是放宽语义：命中仍然要求这个数真的出现。
    _rep_nc = _rep.replace(u',', u'')
    _need = [u'199', u'167', u'33', u'2166', u'1392', u'1,391', u'6027',
             u'room_area1', u'room_start', u'check124']
    _miss = [_t for _t in _need
             if _t not in _rep and _t.replace(u',', u'') not in _rep_nc]
    ok(u'⑥a `report124.md` 的关键数字/令牌全在（%d 个，允许千分位写法）' % len(_need),
       not _miss, u'缺 %r' % (_miss,))
else:
    ok(u'⑥a `report124.md` 在盘', False, u'缺文件')

_ALLOW = {
    os.path.join('_tools', 'check124.py'),
    os.path.join('_tools', 'recheck124.py'),
    os.path.join('_evidence', 'report124.md'),
}
_found = []
for _root, _dirs, _files in os.walk(ROUND):
    _dirs[:] = [d for d in _dirs if d != '__pycache__']
    for _f in _files:
        _found.append(os.path.relpath(os.path.join(_root, _f), ROUND))
_extra = sorted(set(_found) - _ALLOW)
ok(u'⑥b `第124轮` 目录里没有临时产物（只 %d 个允许文件）' % len(_ALLOW), not _extra,
   u'多出 %r' % (_extra[:5],))

# ===========================================================================
print(u'')
print(u'---- 共 %d 条：PASS %d / FAIL %d' % (_n['p'] + _n['f'], _n['p'], _n['f']))
if _failed:
    print(u'失败项：')
    for _d in _failed:
        print(u'  - %s' % _d)
sys.exit(1 if _failed else 0)
