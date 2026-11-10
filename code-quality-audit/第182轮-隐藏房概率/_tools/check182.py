# -*- coding: utf-8 -*-
u"""第182轮 · 「隐藏房按原作概率出现、进过一次就锁」回归锁。

## 本轮做了什么

原作在**门对象的 `Alarm_2`** 里掷骰子：

    ch1  obj_doorX_musfade : if (room == room_forest_area5) {
                                 ch = ceil(random(50));
                                 if (ch == 50 && global.flag[910] == 0) room_goto(room_man);
                                 else room_goto(room_forest_starwalker); }
    ch2  obj_doorw_musfade : man_room = ... && ceil(random(50)) == 50;
                             if (man_room) room_goto(room_dw_city_man);
                             else room_goto(room_dw_city_moss);

`ceil(random(50)) == 50` 正好是 **1/50 = 0.02**，所以概率写在数据里
（`_hidden_rooms[].probability`），**不在代码里写死**。

本轮落了四件事：
  ① `scene_routing.pick_hidden()` —— 纯函数，`roll` 可注入（判据靠它把掷骰变确定）；
  ② `main._maybe_divert_to_hidden()` —— **出门那一拍**掷一次，命中就改目标；
  ③ `main._commit_hidden_seen()` —— **真站进去了**才写 `hidden_rooms_seen.json`（永久锁）；
  ④ `_hidden_rooms` 里**只启用 ch2**（其余三间：目标未登记 / 无入边 / 条件未解）。

## ★★★ 三条不能写错的口径

1. **掷骰的主语是"从哪儿出发"（`from_scene`），不是"原本要去哪"** —— 原作的条件是
   `room == room_xxx`，那个 `room` 是你**正站着**的房间。D3 会把这条钉住。
2. **`match()` 一个字没动**。它至今**零调用方**（真正换房走
   `travel_to_scene → _resolve_travel_target → scene.switch()`），而它的「完全确定性」
   被 20+ 个老判据依赖 —— 把随机塞进去等于同时坏两件事。C1 钉"掷骰挂在走动入口"。
3. **"掷中"≠"已发现"**。`switch` 可能失败、过渡可能被取消；只有当前场景**真的等于**
   隐藏房才记账（C3）。否则没去成的房会被记成已发现 ⇒ 那扇门永远消失且**不报错**。

## 判据分段

- A 数据（5） · B 纯函数行为（11） · C 接线（6） · D 自检（5）

★ 环境变量口子（只给 `mutate182.py` 用，判据本身一行不改）
  `CQ_ROUTES_182` / `CQ_MAIN_182` / `CQ_MODS_182`
"""
import ast
import io
import json
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))

PET = os.path.join(REPO, 'ralsei_pet')
SCENES = os.path.join(PET, 'assets', 'scenes')
MODS = os.environ.get('CQ_MODS_182') or os.path.join(PET, 'modules')
MAIN_SRC = os.environ.get('CQ_MAIN_182') or os.path.join(PET, 'src', 'main.py')
ROUTES = os.environ.get('CQ_ROUTES_182') or os.path.join(SCENES, '_routes.json')

_n = {'p': 0, 'f': 0}
_bad = []


def check(desc, cond, extra=u''):
    if cond:
        _n['p'] += 1
        print('[PASS] %s%s' % (desc, (u'    ' + extra) if extra else u''))
    else:
        _n['f'] += 1
        _bad.append(desc)
        print('[FAIL] %s%s' % (desc, (u'    ' + extra) if extra else u''))


def rd(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def jload(p):
    return json.loads(rd(p))


# ---------------------------------------------------------------------------
#  A 数据：隐藏房登记
# ---------------------------------------------------------------------------
ROUTEDATA = jload(ROUTES)
HIDDEN = ROUTEDATA.get('_hidden_rooms') or []
_ENABLED = [h for h in HIDDEN if isinstance(h, dict) and h.get('enabled') is True]

check(u'A1 顶层仍有 `_hidden_rooms`，且条数与第181轮登记一致（4 条）',
      isinstance(HIDDEN, list) and len(HIDDEN) == 4, u'实测 %d 条' % len(HIDDEN))

check(u'A2 ★ 启用的**恰好一条**，且是 ch2 的 `dw_city_man`（本轮只投用这一间）',
      len(_ENABLED) == 1
      and _ENABLED[0].get('scene') == 'ch2.cyber_city.dw_city_man',
      u'启用 %r' % [h.get('scene') for h in _ENABLED])

_ch2 = _ENABLED[0] if _ENABLED else {}
check(u'A3 ★ 启用那条的概率 == 1/50（原作 `ceil(random(50)) == 50`），且 `once` 为真',
      abs(float(_ch2.get('probability') or 0) - 0.02) < 1e-9
      and _ch2.get('once') is True,
      u'probability=%r once=%r' % (_ch2.get('probability'), _ch2.get('once')))

_off = [h for h in HIDDEN if isinstance(h, dict) and h.get('enabled') is not True]
check(u'A4 其余三条都是 `enabled: false`，且各自写明**为什么不能启用**（三种不同理由）',
      len(_off) == 3
      and all(h.get('enabled') is False for h in _off)
      and len({h.get('status') for h in _off}) == 3,
      u'status=%r' % [h.get('status') for h in _off])

check(u'A5 四条都带 `evidence`（没有取证就不许登记 —— 第181轮口径）',
      all(isinstance(h.get('evidence'), str) and h.get('evidence') for h in HIDDEN),
      u'缺 %r' % [h.get('scene') for h in HIDDEN
                  if not (isinstance(h.get('evidence'), str) and h.get('evidence'))])

# ---------------------------------------------------------------------------
#  B 纯函数行为（真 import `scene_routing`，不吃 main）
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.join(PET, 'modules'))   # 真身兜底（scene_system 等仍从真身取）
sys.path.insert(0, MODS)                          # 可覆盖副本**优先**（变异只换 scene_routing.py）
try:
    import scene_routing as SR
    _imp = None
except Exception as e:                              # noqa: BLE001
    SR = None
    _imp = '%s: %s' % (type(e).__name__, e)

check(u'B0 `scene_routing` 可 import（零 Qt 依赖；失败则下面整段如实红）',
      SR is not None, _imp or u'')

if SR is None:
    # 不静默跳过：11 条全部如实记 FAIL，避免"段缺失但总数凑上了"。
    for _k in range(11):
        check(u'B%d （跳过：模块 import 失败）' % (_k + 1), False, u'见 B0')
else:
    _HP = SR.pick_hidden
    _FR = 'ch2.cyber_city.dw_city_traffic_3'

    # ---- B1 成对正/负控制：先断言两者不同（A/B 先断言 A≠B）
    _hit = _HP(HIDDEN, _FR, {}, roll=lambda: 0.0)
    _miss = _HP(HIDDEN, _FR, {}, roll=lambda: 0.5)
    check(u'B1 ★ 成对控制：roll=0.0 命中、roll=0.5 不中，且两者**结果不同**',
          SR.hidden_key(_hit) == 'ch2.cyber_city.dw_city_man' and _miss is None
          and _hit is not _miss,
          u'hit=%r miss=%r' % (SR.hidden_key(_hit), _miss))

    # ---- B2 边界：`r < p` 严格小于
    check(u'B2 边界精确：`r = p−ε` 命中、`r = p` **不中**（严格小于，不是小于等于）',
          SR.hidden_key(_HP(HIDDEN, _FR, {}, roll=lambda: 0.02 - 1e-9))
          == 'ch2.cyber_city.dw_city_man'
          and _HP(HIDDEN, _FR, {}, roll=lambda: 0.02) is None,
          u'p=0.02')

    # ---- B3 已发现 ⇒ 锁（用真数据）
    _seen = {'ch2.cyber_city.dw_city_man': {'at': 'x'}}
    check(u'B3 ★ `once` 且已发现过 ⇒ **再也不会**命中（这就是"进过一次就锁"）',
          _HP(HIDDEN, _FR, _seen, roll=lambda: 0.0) is None)

    # ---- B4 对偶：`once: false` 的登记即使已发现也仍能命中
    _nofree = [dict(_ch2, once=False, _order=0)]
    check(u'B4 对偶控制：同一条改成 `once: false` ⇒ 已发现**仍能**命中（证明 B3 锁的是 once 不是别的）',
          SR.hidden_key(_HP(_nofree, _FR, _seen, roll=lambda: 0.0))
          == 'ch2.cyber_city.dw_city_man')

    # ---- B5 disabled 永不命中（ch1 那条真数据：目标未登记）
    check(u'B5 `enabled` 不为 True ⇒ 永不命中（ch1 那间目标未登记，roll=0.0 也不许中）',
          _HP(HIDDEN, 'ch1.forest.forest_area5', {}, roll=lambda: 0.0) is None)

    # ---- B6 概率非法四类都跳过
    _badp = [dict(_ch2, probability=v, _order=0) for v in (0, 0.0, 1.5, 'x', None)]
    check(u'B6 ★ 概率非法（0 / 1.5 / "x" / None）一律跳过 —— 不猜、不纠偏（设计律 2）',
          all(_HP([e], _FR, {}, roll=lambda: 0.0) is None for e in _badp))

    # ---- B7 from_scene 不匹配 ⇒ 不中（主语是"从哪儿出发"）
    check(u'B7 ★ 只认 `from_scene`：站在别的房间掷骰**一律不中**（原作条件是 `room == 源房`）',
          _HP(HIDDEN, 'ch2.cyber_city.dw_city_moss', {}, roll=lambda: 0.0) is None)

    # ---- B8 多条同源：按 `_order` 先命中先得
    _two = [dict(_ch2, scene='A', _order=1), dict(_ch2, scene='B', _order=0)]
    check(u'B8 同一 `from_scene` 多条登记 ⇒ 按声明序逐条掷，**写在前面的优先**',
          SR.hidden_key(_HP(_two, _FR, {}, roll=lambda: 0.0)) == 'B',
          u'得 %r' % SR.hidden_key(_HP(_two, _FR, {}, roll=lambda: 0.0)))

    # ---- B9 随机源抛异常 ⇒ 不崩、当作没中
    def _boom():
        raise RuntimeError('rng broken')
    try:
        _r9 = _HP(HIDDEN, _FR, {}, roll=_boom)
        _ok9 = _r9 is None
    except Exception:                               # noqa: BLE001
        _ok9 = False
    check(u'B9 随机源抛异常 ⇒ 当作"没掷中"、**不向上抛**（走动不能因为骰子坏了就崩）', _ok9)

    # ---- B10 p = 1.0 恒命中
    check(u'B10 边界：p = 1.0 ⇒ `r = 0.999…` 也命中（否则 p=1 与 p=0 不可区分）',
          SR.hidden_key(_HP([dict(_ch2, probability=1.0, _order=0)], _FR, {},
                            roll=lambda: 0.999999)) == 'ch2.cyber_city.dw_city_man')

    # ---- B11 频率交叉验证：注入口径之外，用**真随机**独立量一次
    import random as _random
    _random.seed(182)
    _N = 100000
    _cnt = 0
    for _i in range(_N):
        if _HP(HIDDEN, _FR, {}) is not None:
            _cnt += 1
    # 1/50 期望 2000；sd≈44 ⇒ [1700, 2300] 是 ±6.8sd，稳且能打掉 0 与 5%
    check(u'B11 ★★ 频率独立验证：真随机 %d 次，命中数落在 1/50 的合理区间 [1700, 2300]' % _N,
          1700 <= _cnt <= 2300, u'实测 %d（%.3f%%）' % (_cnt, 100.0 * _cnt / _N))

# ---------------------------------------------------------------------------
#  C 接线（AST 扫 `main.py`，不 import —— import 会构造真机）
# ---------------------------------------------------------------------------
MAIN = rd(MAIN_SRC)
_MT = ast.parse(MAIN)


def _fn(name):
    for n in ast.walk(_MT):
        if isinstance(n, ast.FunctionDef) and n.name == name:
            return n
    return None


def _calls(fn, attr):
    return [n.lineno for n in ast.walk(fn)
            if isinstance(n, ast.Call)
            and getattr(n.func, 'attr', None) == attr]


_travel = _fn('travel_to_scene')
_div = _calls(_travel, '_maybe_divert_to_hidden') if _travel else []
_res = _calls(_travel, '_resolve_travel_target') if _travel else []
_com = _calls(_travel, '_travel_commit') if _travel else []
check(u'C1 ★★ 掷骰挂在**走动入口**，且行号早于两个换房分支（命中后目标先被改写，后面全自然）',
      bool(_div)
      and (not _res or min(_div) < min(_res))
      and (not _com or min(_div) < min(_com)),
      u'travel=%r divert=%r resolve=%r commit=%r'
      % (bool(_travel), _div, _res, _com))

_fb = _fn('_travel_feedback_done')
check(u'C2 记账挂在**两条路径共用的收尾**里（`_travel_feedback_done` 调 `_commit_hidden_seen`）',
      _fb is not None and bool(_calls(_fb, '_commit_hidden_seen')),
      u'calls=%r' % ([] if _fb is None else _calls(_fb, '_commit_hidden_seen')))

_commit = _fn('_commit_hidden_seen')
_ne = []
if _commit is not None:
    for n in ast.walk(_commit):
        if not isinstance(n, ast.If):
            continue
        t = n.test
        if (isinstance(t, ast.Compare) and len(t.ops) == 1
                and isinstance(t.ops[0], ast.NotEq)
                and isinstance(t.left, ast.Name) and t.left.id == 'cur'):
            _ne.append(n.lineno)
check(u'C3 ★★ "掷中" ≠ "已发现"：`_commit_hidden_seen` 里必须有一条 `cur != sid` 的提前返回（按真到了判）',
      bool(_ne), u'找到 %d 条' % len(_ne))

_md = _fn('_maybe_divert_to_hidden')
_writes = []
if _md is not None:
    for n in ast.walk(_md):
        if isinstance(n, ast.Call) and getattr(n.func, 'attr', None) in (
                'dump', 'replace', 'makedirs'):
            _writes.append(n.lineno)
check(u'C4 掷骰那一层**不写盘**（`dump`/`replace`/`makedirs` 一个都不许出现）—— 记账只在 C2 那处',
      _md is not None and _writes == [], u'md_ok=%r 命中 %r' % (_md is not None, _writes))

check(u'C5 记账走**原子替换**（`os.replace`）—— 写一半断电也不会留半个 JSON',
      bool(_calls(_commit, 'replace')) if _commit else False)

_pth = _fn('_hidden_seen_path')
check(u'C6 账本路径走 `data_store.app_file`（唯一入口契约，不硬编码数据根）',
      _pth is not None and 'app_file' in ast.dump(_pth))

# ---------------------------------------------------------------------------
#  D 自检
# ---------------------------------------------------------------------------
_raw = io.open(os.path.abspath(__file__), 'rb').read()
check(u'D1 本文件无 BOM 且 UTF-8 可解', not _raw.startswith(b'\xef\xbb\xbf'))
check(u'D2 本文件无 U+FFFD', _raw.decode('utf-8').count('\ufffd') == 0)

_T = ast.parse(_raw.decode('utf-8'))
_CONST_TRUE = [n.lineno for n in ast.walk(_T)
               if isinstance(n, ast.Call) and len(n.args) >= 2
               and getattr(n.func, 'id', None) == 'check'
               and isinstance(n.args[1], ast.Constant) and n.args[1].value is True]
check(u'D3 本文件里没有"常量 True"判据（恒真比不写还危险）', _CONST_TRUE == [],
      u'行号 %r' % _CONST_TRUE)

_EXT = re.findall(r'[D-E]:[\\/]{1,2}[A-Za-z_\u4e00-\u9fff][^\'"\s]{2,}', _raw.decode('utf-8'))
check(u'D4 不依赖外部盘/临时区（源码里没有真实盘符路径，比如 D 盘临时区）', _EXT == [],
      u'命中 %r' % _EXT)

check(u'D5 判据条数不随环境变（本文件恒发 28 条断言，含本条自身）',
      _n['p'] + _n['f'] + 1 == 28, u'当前 %d' % (_n['p'] + _n['f'] + 1))

# ---------------------------------------------------------------------------
print('')
print('=' * 74)
print(u'合计 %d 条判据  PASS=%d  FAIL=%d' % (_n['p'] + _n['f'], _n['p'], _n['f']))
if _bad:
    print(u'FAIL 明细：')
    for d in _bad:
        print(u'  - ' + d)
print('=' * 74)
sys.exit(0 if _n['f'] == 0 else 1)
