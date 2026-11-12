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

- A 数据（6） · B 纯函数行为（14） · C 接线（6） · D 自检（5）

★ 第185轮引账：A2/A4 从"恰好一条启用"改成"两间在账"；B 段每条调用补 `door=`；
  B5 换负控制；新增 B12/B13/B14 钉门字母语义（缺门不掷 / 门不对不掷 / ch1 只认 X）。

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


def _by_scene(sid):
    u"""按 scene id 取登记（★ 不要用 `_ENABLED[0]` —— 下标会随登记顺序变）。"""
    for _h in HIDDEN:
        if isinstance(_h, dict) and _h.get('scene') == sid:
            return _h
    return {}

check(u'A1 顶层仍有 `_hidden_rooms`，且条数与第181轮登记一致（4 条）',
      isinstance(HIDDEN, list) and len(HIDDEN) == 4, u'实测 %d 条' % len(HIDDEN))

#: ★★★ 第185轮引账：原本是"启用的**恰好一条**，且是 ch2"。第185轮投用了 ch1
#:   `room_man`（`第185轮-森林1of50隐藏房`）⇒ 启用的变成两间。断言改成**集合相等**：
#:   多启一间要报红、少启一间也要报红，比"数条数"更难糊弄过去。
_ENABLED_LEDGER = {
    'ch1.forest.room_man',           # 第185轮：area5 推 X 门掷 1/50
    'ch2.cyber_city.dw_city_man',    # 第182轮：出城时掷 1/50
}
check(u'A2 ★★★ 已启用集合 == 账上登记的两间（多启一间要报红，登记了没启用也报红）：%r'
      % (sorted(_ENABLED_LEDGER),),
      {h.get('scene') for h in _ENABLED} == _ENABLED_LEDGER,
      u'启用 %r' % sorted(h.get('scene') for h in _ENABLED))

_ch2 = _by_scene('ch2.cyber_city.dw_city_man')
_ch1 = _by_scene('ch1.forest.room_man')
check(u'A3 ★ 启用那条的概率 == 1/50（原作 `ceil(random(50)) == 50`），且 `once` 为真',
      abs(float(_ch2.get('probability') or 0) - 0.02) < 1e-9
      and _ch2.get('once') is True,
      u'probability=%r once=%r' % (_ch2.get('probability'), _ch2.get('once')))

#: ★ 第185轮：启用两间后，剩下的就只有 ch3 / ch4 两间；理由仍须**互不相同**
#:   （不许两条都写"待解"糊过去）。
_off = [h for h in HIDDEN if isinstance(h, dict) and h.get('enabled') is not True]
check(u'A4 其余两条都是 `enabled: false`，且各自写明**为什么不能启用**（两种不同理由）',
      len(_off) == 2
      and all(h.get('enabled') is False for h in _off)
      and len({h.get('status') for h in _off}) == 2,
      u'status=%r' % [h.get('status') for h in _off])

#: ★★★ 第185轮新增（A6）：两间启用的都必须"概率 1/50 + once + 指定门字母"三件齐全。
#:   A3 只钉 ch2，ch1 是本轮新投用的 —— 不补一条，等于新投用的那间没人看守。
check(u'A6 ★★ 两间已启用的都齐了「probability==1/50 + once + when_door」'
      u'（ch1=X 门 / ch2=W 门，缺一个都不算投用）',
      len(_ENABLED) >= 1
      and all(abs(float(h.get('probability') or 0) - 0.02) < 1e-9
              and h.get('once') is True
              and isinstance(h.get('when_door'), str) and h.get('when_door')
              for h in _ENABLED)
      and [_ch1.get('when_door'), _ch2.get('when_door')] == ['X', 'W'],
      u'%r' % ([(h.get('scene'), h.get('probability'), h.get('once'), h.get('when_door'))
                for h in _ENABLED],))

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
    for _k in range(14):
        check(u'B%d （跳过：模块 import 失败）' % (_k + 1), False, u'见 B0')
else:
    _HP = SR.pick_hidden
    _FR = 'ch2.cyber_city.dw_city_traffic_3'
    #: ★★★ 第185轮：`pick_hidden` 新增 `door=`，且**登记指定了 `when_door` 却没给门
    #:   ⇒ 不掷**（fail-closed，与 `gate_for` 同口径）。所以下面每一处调用都必须显式
    #:   说明走的是哪扇门 —— 这也正是真机上的调用方式（门字母从 `DoorProp` 传进来）。
    _DOOR_W = 'W'      # ch2 那扇是 `obj_doorw_musfade`

    # ---- B1 成对正/负控制：先断言两者不同（A/B 先断言 A≠B）
    _hit = _HP(HIDDEN, _FR, {}, door=_DOOR_W, roll=lambda: 0.0)
    _miss = _HP(HIDDEN, _FR, {}, door=_DOOR_W, roll=lambda: 0.5)
    check(u'B1 ★ 成对控制：roll=0.0 命中、roll=0.5 不中，且两者**结果不同**',
          SR.hidden_key(_hit) == 'ch2.cyber_city.dw_city_man' and _miss is None
          and _hit is not _miss,
          u'hit=%r miss=%r' % (SR.hidden_key(_hit), _miss))

    # ---- B2 边界：`r < p` 严格小于
    check(u'B2 边界精确：`r = p−ε` 命中、`r = p` **不中**（严格小于，不是小于等于）',
          SR.hidden_key(_HP(HIDDEN, _FR, {}, door=_DOOR_W, roll=lambda: 0.02 - 1e-9))
          == 'ch2.cyber_city.dw_city_man'
          and _HP(HIDDEN, _FR, {}, door=_DOOR_W, roll=lambda: 0.02) is None,
          u'p=0.02')

    # ---- B3 已发现 ⇒ 锁（用真数据）
    _seen = {'ch2.cyber_city.dw_city_man': {'at': 'x'}}
    check(u'B3 ★ `once` 且已发现过 ⇒ **再也不会**命中（这就是"进过一次就锁"）',
          _HP(HIDDEN, _FR, _seen, door=_DOOR_W, roll=lambda: 0.0) is None)

    # ---- B4 对偶：`once: false` 的登记即使已发现也仍能命中
    _nofree = [dict(_ch2, once=False, _order=0)]
    check(u'B4 对偶控制：同一条改成 `once: false` ⇒ 已发现**仍能**命中（证明 B3 锁的是 once 不是别的）',
          SR.hidden_key(_HP(_nofree, _FR, _seen, door=_DOOR_W, roll=lambda: 0.0))
          == 'ch2.cyber_city.dw_city_man')

    # ---- B5 disabled 永不命中
    # ★★★ 第185轮改写：原措辞是"ch1 那条真数据：目标未登记"，而 ch1 `room_man`
    #   本轮**已投用** —— 那句前提被推翻了，再拿它当负控制会变成正控制（假绿）。
    #   现在分两拍：① 真数据里那两间 disabled 的一律掷不中；
    #             ② 合成夹具把一条**合法**登记翻成 `enabled=False`，roll≈0 仍不中
    #               ⇒ 闸确实在 `enabled` 上，不是"碰巧没登记"。
    _off_hits = [_HP([h], h.get('from_scene') or _FR, {}, door=_DOOR_W,
                     roll=lambda: 1e-12)
                 for h in HIDDEN if h.get('enabled') is not True]
    check(u'B5 ★ `enabled` 不为 True ⇒ 永不命中：真数据 disabled 的 %d 间 roll≈0 也不中，'
          u'且合成夹具翻 `enabled=False` 后照样不中' % len(_off_hits),
          len(_off_hits) == 2 and all(x is None for x in _off_hits)
          and _HP([dict(_ch2, enabled=False, _order=0)], _FR, {},
                  door=_DOOR_W, roll=lambda: 0.0) is None,
          u'off=%r' % ([SR.hidden_key(x) for x in _off_hits],))

    # ---- B6 概率非法四类都跳过
    _badp = [dict(_ch2, probability=v, _order=0) for v in (0, 0.0, 1.5, 'x', None)]
    check(u'B6 ★ 概率非法（0 / 1.5 / "x" / None）一律跳过 —— 不猜、不纠偏（设计律 2）',
          all(_HP([e], _FR, {}, door=_DOOR_W, roll=lambda: 0.0) is None for e in _badp))

    # ---- B7 from_scene 不匹配 ⇒ 不中（主语是"从哪儿出发"）
    check(u'B7 ★ 只认 `from_scene`：站在别的房间掷骰**一律不中**（原作条件是 `room == 源房`）',
          _HP(HIDDEN, 'ch2.cyber_city.dw_city_moss', {}, door=_DOOR_W, roll=lambda: 0.0) is None)

    # ---- B8 多条同源：按 `_order` 先命中先得
    _two = [dict(_ch2, scene='A', _order=1), dict(_ch2, scene='B', _order=0)]
    check(u'B8 同一 `from_scene` 多条登记 ⇒ 按声明序逐条掷，**写在前面的优先**',
          SR.hidden_key(_HP(_two, _FR, {}, door=_DOOR_W, roll=lambda: 0.0)) == 'B',
          u'得 %r' % SR.hidden_key(_HP(_two, _FR, {}, door=_DOOR_W, roll=lambda: 0.0)))

    # ---- B9 随机源抛异常 ⇒ 不崩、当作没中
    def _boom():
        raise RuntimeError('rng broken')
    try:
        _r9 = _HP(HIDDEN, _FR, {}, door=_DOOR_W, roll=_boom)
        _ok9 = _r9 is None
    except Exception:                               # noqa: BLE001
        _ok9 = False
    check(u'B9 随机源抛异常 ⇒ 当作"没掷中"、**不向上抛**（走动不能因为骰子坏了就崩）', _ok9)

    # ---- B10 p = 1.0 恒命中
    check(u'B10 边界：p = 1.0 ⇒ `r = 0.999…` 也命中（否则 p=1 与 p=0 不可区分）',
          SR.hidden_key(_HP([dict(_ch2, probability=1.0, _order=0)], _FR, {}, door=_DOOR_W,
                            roll=lambda: 0.999999)) == 'ch2.cyber_city.dw_city_man')

    # ---- B11 频率交叉验证：注入口径之外，用**真随机**独立量一次
    import random as _random
    _random.seed(182)
    _N = 100000
    _cnt = 0
    for _i in range(_N):
        if _HP(HIDDEN, _FR, {}, door=_DOOR_W) is not None:
            _cnt += 1
    # 1/50 期望 2000；sd≈44 ⇒ [1700, 2300] 是 ±6.8sd，稳且能打掉 0 与 5%
    check(u'B11 ★★ 频率独立验证：真随机 %d 次，命中数落在 1/50 的合理区间 [1700, 2300]' % _N,
          1700 <= _cnt <= 2300, u'实测 %d（%.3f%%）' % (_cnt, 100.0 * _cnt / _N))

    # ---- B12 ★★★ 缺门 ⇒ 不掷（fail-closed）。本轮最容易被"顺手放宽"的一条口径。
    _nd = _HP(HIDDEN, _FR, {}, roll=lambda: 0.0)
    check(u'B12 ★★★ 门字母 fail-closed：登记写了 `when_door` 但调用方**没给** `door` ⇒ 不掷'
          u'（不知道哪扇门就套用 = "随便哪扇门出去都可能被扔进隐藏房"，比不掷更坏）',
          _nd is None, u'得 %r' % (SR.hidden_key(_nd),))

    # ---- B13 门字母对不上 ⇒ 不掷；对上 ⇒ 照掷（正/负成对，先证明两个结果不同）
    _wrong = _HP(HIDDEN, _FR, {}, door='X', roll=lambda: 0.0)
    _right = _HP(HIDDEN, _FR, {}, door=_DOOR_W, roll=lambda: 0.0)
    check(u'B13 ★ 门字母必须对上：ch2 那间只认 W 门（door="X" ⇒ 不中）、W 门 ⇒ 中，'
          u'且两者结果不同（否则 B12 的 None 可能只是"永远返 None"）',
          _wrong is None and SR.hidden_key(_right) == 'ch2.cyber_city.dw_city_man'
          and SR.hidden_key(_wrong) != SR.hidden_key(_right),
          u'X→%r W→%r' % (SR.hidden_key(_wrong), SR.hidden_key(_right)))

    # ---- B14 ★★★ ch1 `room_man`：同房有 A / X 两扇门，原作只有 X 门掷
    _ch1_from = _ch1.get('from_scene') or 'ch1.forest.forest_area5'
    _x = _HP(HIDDEN, _ch1_from, {}, door='X', roll=lambda: 0.0)
    _a = _HP(HIDDEN, _ch1_from, {}, door='A', roll=lambda: 0.0)
    check(u'B14 ★★★ ch1 `room_man` 只认 X 门：`%s` 同房还有一扇 A 门（`obj_doorA`），'
          u'原作那扇**不掷骰**（它走的是"下标位移"另一套机制）' % _ch1_from,
          SR.hidden_key(_x) == 'ch1.forest.room_man' and _a is None,
          u'X→%r A→%r' % (SR.hidden_key(_x), SR.hidden_key(_a)))

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

#: ★ 第185轮：28 → **32**（A 段 +1：A6；B 段 +3：B12/B13/B14；C/D 不动）。
#:   分段账：A 6 + B 14 + C 6 + D 5 = 31，再加本条自身 = 32。
check(u'D5 判据条数不随环境变（本文件恒发 32 条断言，含本条自身）',
      _n['p'] + _n['f'] + 1 == 32, u'当前 %d' % (_n['p'] + _n['f'] + 1))

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
