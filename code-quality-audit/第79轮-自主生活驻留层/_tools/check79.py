# -*- coding: utf-8 -*-
"""第79轮回归锁：**NPC 自主生活 · 层2 驻留层**（`npc_roam.py`）不许静默漂移。

用户口径（逐字，第77轮）
------------------------
> 「**不会因为缺少一个人哪怕是我他们就不生活了**」
> 「去哪？找谁？干什么？生活规划这类的事也是由**各自的 AI 决定**」

层2 要解决的头号障碍（第78轮定位）
------------------------------------
`_npc_seed_bodies()` **只在两处**被调（`main.py:2182` 启动 / `:2513` **场景切换钩子**）
⇒ 现有模型 =「NPC 是**当前场景的装饰**」⇒ **用户不动，世界就冻住**（与 L2 正相反）。

守什么
------
* **A 零依赖纪律**（AST）：只准标准库、**零函数内 import**、零项目内 import。
* **B ★★★ 零回归（最贵的一条）**：`enabled=False` 时 `step()` **一个字节都不改**
  —— 这不是"大概一样"，是**结构保证**（关掉开关行为必须与现在逐字相同）。
* **C ★★ 驻留语义**：`resident_of()` 无覆盖 ⇒ `None`（**不许**返回默认值
  —— 默认值的真源在 `_placement.json`，复制一份就是"同一份规则两处算"）。
* **D ★★ 不与用户耦合**：`step()` / `leave_probability()` 的形参里**不许有**
  pet/user/player（L2 的结构保证）+ 负控制。
* **E ★★★ L6「禁整点必做」**：离开概率**恒 > 0**（"永远不动"就是另一种整点必做）；
  且待得越久越可能走（单调不减）。
* **F ★★ 桌面闸**：不许**自主**进入 `desktop`（那要走跟随/邀请那条路）。
* **G 时段同源**：`_phase_name()` 与 `npc_intent.phase_of()` 逐时同值（防悄悄漂移）。
* **H 行为**：真能移动；同样输入可复现；异时可变；驻留期不许即到即走。
* **I 序列化 + 判据自身体检**。
* **★ 层3 就寝（第80轮追加）**：见「J」段 —— 旧常量 `BEDTIME_HOME_SCENE` 对 NPC
  **废弃**，改**逐人决策**（`decide_sleep` / `sleep_fn` 注入），且**零回归可证**。

★ 零网络 / 零 UI / 零外部盘 / 不需要显示器。
"""
import ast
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
MODS = os.path.join(ROOT, 'ralsei_pet', 'modules')
MOD = os.path.join(MODS, 'npc_roam.py')
INTENT = os.path.join(MODS, 'npc_intent.py')

PASS = 0
FAIL = 0
FAILED = []
#: ★ 独立计数器：check() **入口** +1（与出口的 PASS+FAIL 分开记，用来交叉核对）。
CALLS = 0


def check(name, cond, detail=''):
    global PASS, FAIL, CALLS
    CALLS += 1
    if cond:
        PASS += 1
        print('[PASS] %s    %s' % (name, detail))
    else:
        FAIL += 1
        FAILED.append(name)
        print('[FAIL] %s    %s' % (name, detail))


def _probe_ledger():
    """I 段自检：造一个失败看它真进账。

    ★★ 绝不许走 `check()` —— 它会往 stdout 打那 6 字符标记，
    而 `regress/run_all.py` 的 `count_results()` 是**正则数字面量**的
    ⇒ 探针会污染套件的 FAIL 计数（第77轮 `check77` 踩过，§69.7）。
    """
    global PASS, FAIL
    p0, f0 = PASS, FAIL
    FAIL += 1
    FAILED.append('__probe__')
    got = (FAIL == f0 + 1 and '__probe__' in FAILED)
    FAIL = f0
    FAILED.remove('__probe__')
    return got and (PASS, FAIL) == (p0, f0)


def _print_points(tree_, marker):
    """AST 层数打印点（认 Constant / JoinedStr / BinOp(%) 三形状）。

    ★★ 不能用 `src.count("print('[PASS]")` —— 判据自己的字面量也含标记（自指），
    第78轮实测数出 4 而不是 1。
    """
    n = 0
    for node in ast.walk(tree_):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == 'print' and node.args):
            continue
        head = node.args[0]
        if isinstance(head, ast.BinOp) and isinstance(head.op, ast.Mod):
            head = head.left
        if isinstance(head, ast.JoinedStr) and head.values:
            head = head.values[0]
        if isinstance(head, ast.Constant) and isinstance(head.value, str) \
                and head.value.lstrip().startswith(marker):
            n += 1
    return n


def read(p):
    with io.open(p, encoding='utf-8') as f:
        return f.read()


_SELF = read(os.path.abspath(__file__))

# ================================================================ A
print('=' * 74)
print('A 零依赖纪律（对齐 npc_intent / npc_placement / companion*）')
print('=' * 74)

src = read(MOD)
tree = ast.parse(src)

ALLOWED_STD = {'collections', 'hashlib', 'random', 'math', 'time', 'json', 'io', 'os'}

tops = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
top_names = []
for n in tops:
    if isinstance(n, ast.Import):
        top_names.extend(a.name.split('.')[0] for a in n.names)
    else:
        top_names.append((n.module or '').split('.')[0])
bad = [t for t in top_names if t not in ALLOWED_STD]
check('A1 顶层 import 全部是标准库', not bad,
      '越界=%s 全量=%s' % (bad or '无', top_names))

inner = [n for n in ast.walk(tree)
         if isinstance(n, (ast.Import, ast.ImportFrom)) and n not in tops]
check('A2 ★ 零函数内 import（零依赖模块的硬纪律）', not inner,
      '函数内=%d' % len(inner))

proj = [t for t in top_names
        if t in ('npc_intent', 'npc_life', 'npc_placement', 'companion',
                 'data_store', 'scene_controller', 'npc_system')]
check('A3 不 import 任何项目内模块（决策从 decide_fn 注入）', not proj,
      '项目内=%s' % (proj or '无'))

sys.path.insert(0, MODS)
import npc_roam as R          # noqa: E402
import npc_intent as NI       # noqa: E402

check('A4 模块真能 import（AST 过 ≠ 可加载）',
      hasattr(R, 'step') and hasattr(R, 'RoamState'), '')

# ================================================================ B
print()
print('=' * 74)
print('B ★★★ 零回归：关掉开关时 step() 一个字节都不改')
print('=' * 74)

_never = lambda nid, now, **kw: ('room_zzz', 'x')
st_off = R.RoamState(enabled=False)
_before = st_off.to_dict()
_out = R.step(st_off, 1000.0, roster=['a', 'b'], decide_fn=_never)
_after = st_off.to_dict()
check('B1 ★★★ enabled=False ⇒ 返回空结果且状态零变化',
      _out == {'decided': [], 'expired': [], 'moved': []} and _before == _after,
      'out=%s 状态变=%s' % (_out, _before != _after))

check('B2 默认 enabled = False（产品默认关）',
      R.DEFAULT_ROAM_ENABLED is False and R.RoamState().enabled is False, '')

# ★ 负控制：打开开关后同样的调用**必须**产生变化（否则 B1 是恒真）
st_on = R.RoamState(enabled=True)
_out_on = R.step(st_on, 1000.0, roster=['a'], decide_fn=_never)
check('B2n 负控制：同样调用在 enabled=True 时**必须**有变化（证明 B1 非恒真）',
      bool(_out_on['moved']), 'on_out=%s' % _out_on)

# ================================================================ C
print()
print('=' * 74)
print('C ★★ 驻留语义：无覆盖 ⇒ None（不许返回默认值）')
print('=' * 74)

check('C1 ★ 空表 resident_of() ⇒ None（默认值真源在 _placement.json，不复制）',
      R.RoamState().resident_of('somebody') is None, '')

st_c = R.RoamState(enabled=True)
st_c.put('p', 'room_p', 500.0)
check('C2 有覆盖 ⇒ 返回覆盖值', st_c.resident_of('p') == 'room_p', '')
check('C3 ★ 未覆盖的人仍返回 None（不是"别人的值"）',
      st_c.resident_of('q') is None, '')

st_c.drop('p')
check('C4 drop() ⇒ 回落 None（= "他回家了 / 不该被管了"）',
      st_c.resident_of('p') is None, '')

check('C5 snapshot() 形状正确',
      R.RoamState(enabled=True, stays=[R.Stay('m', 'room_m')]
                  ).snapshot() == {'m': 'room_m'}, '')

# ================================================================ D
print()
print('=' * 74)
print('D ★★ 不与用户耦合：step/leave_probability 形参里不许有"用户"')
print('=' * 74)

BANNED = ('pet', 'user', 'player', 'host', 'me')


def _args_of(name):
    for n in tree.body:
        if isinstance(n, ast.FunctionDef) and n.name == name:
            return [a.arg for a in n.args.args] + [a.arg for a in n.args.kwonlyargs]
    return None


for fn_name in ('step', 'leave_probability'):
    got = _args_of(fn_name)
    check('D-%s 是模块级函数' % fn_name, got is not None, 'args=%s' % got)
    if got is not None:
        viol = [a for a in got if a.lower() in BANNED]
        check('D-%s ★★ 形参里没有 pet/user/player/host/me（L2 结构保证）' % fn_name,
              not viol, '形参=%s 违规=%s' % (got, viol or '无'))

# ★ 负控制：同样的检测喂一个"真有 user"的签名必须判违规
_fake = ast.parse('def step(state, now, user=None): pass').body[0]
_fa = [a.arg for a in _fake.args.args] + [a.arg for a in _fake.args.kwonlyargs]
check('D-n 负控制：检测喂 `step(state, now, user=None)` 必须判违规（否则判据恒真）',
      bool([a for a in _fa if a.lower() in BANNED]), '')

# ================================================================ E
print()
print('=' * 74)
print('E ★★★ L6「禁整点必做」：离开概率恒 > 0，且待越久越想走')
print('=' * 74)

st_e = R.Stay('e', 'room_e', since=0.0, until=1000.0)
probs = []
for frac in (0.0, 0.1, 0.3, 0.5, 0.7, 0.9, 1.0):
    probs.append(R.leave_probability(st_e, frac * 1000.0))
check('E1 ★★★ 离开概率恒 > 0（"永远不动"就是另一种整点必做）',
      all(p > 0 for p in probs), '概率序列=%s' % ['%.4f' % p for p in probs])

check('E2 ★ 待得越久越可能走（单调不减）',
      all(probs[i] <= probs[i + 1] + 1e-12 for i in range(len(probs) - 1)),
      '')

_lo = min(probs)
check('E2n 负控制：概率序列不是常量（否则 E2 是恒真）',
      max(probs) - min(probs) > 1e-6, 'min=%.4f max=%.4f' % (min(probs), max(probs)))

# 夜里更恋栈（概率更低），但仍 > 0
p_night = R.leave_probability(st_e, 1000.0, phase='night')
check('E3 ★ 夜里更恋栈（≤ 白天）但仍 > 0',
      p_night > 0 and p_night <= R.leave_probability(st_e, 1000.0, phase='day') + 1e-12,
      'night=%.4f day=%.4f' % (p_night, R.leave_probability(st_e, 1000.0, phase='day')))

# 上限不许越界
_pmax = R.leave_probability(R.Stay('x', 's', 0.0, 1.0), 1e9)
check('E4 概率封顶 ≤ LEAVE_P_MAX（不会变成"必然走"）',
      _pmax <= R.LEAVE_P_MAX + 1e-12, 'p=%.4f cap=%.4f' % (_pmax, R.LEAVE_P_MAX))

# 非法输入不抛
_ok = True
try:
    R.leave_probability(R.Stay('x', 's', 0.0, 100.0), None)
    R.leave_probability(R.Stay('x', 's', 0.0, 100.0), 'abc', familiar='zz')
except Exception:
    _ok = False
check('E5 非法输入（now=None/"abc"、familiar 非法）不抛', _ok, '')

# ================================================================ F
print()
print('=' * 74)
print('F ★★ 桌面闸：不许"自主"进入 desktop')
print('=' * 74)

st_f = R.RoamState(enabled=True)
_rf = R.step(st_f, 5000.0, roster=['z'],
             decide_fn=lambda nid, now, **kw: ('desktop', 'x'))
check('F1 ★★ 决策返回 desktop ⇒ 不记驻留（自主进不去桌面）',
      not _rf['moved'] and st_f.resident_of('z') is None, 'out=%s' % _rf)

check('F2 ★ 正控制：决策返回普通场景 ⇒ **会**记驻留（证明 F1 不是"什么都不记"）',
      bool(R.step(R.RoamState(enabled=True), 5000.0, roster=['z'],
                  decide_fn=lambda nid, now, **kw: ('room_ok', 'x'))['moved']), '')

check('F3 DESKTOP_SCENE 常量 == "desktop"（与 npc_system 口径一致）',
      R.DESKTOP_SCENE == 'desktop', '')

# ================================================================ G
print()
print('=' * 74)
print('G 时段同源：_phase_name() 与 npc_intent.phase_of() 逐时同值')
print('=' * 74)

_DAY = 86400.0
_diffs = []
for h in range(24):
    _now = _DAY + h * 3600.0
    a, b = R._phase_name(_now), NI.phase_of(h)
    if a != b:
        _diffs.append((h, a, b))
check('G1 ★ 24 个整点逐时同值（防悄悄漂移）', not _diffs, '差异=%s' % (_diffs[:5] or '无'))

# ★ 负控制：故意错一小时的写法必须被判不同
_now5 = _DAY + 5 * 3600.0
check('G1n 负控制：把 5 点错当成 day 必须与人设层判"不同"',
      R._phase_name(_now5) != 'day', '5点=%s' % R._phase_name(_now5))

check('G2 PHASES 覆盖四个时段且与 intent 同名',
      set(R._phase_name(_DAY + h * 3600.0) for h in range(24))
      == set(NI.PHASES.keys()), '')

# ================================================================ H
print()
print('=' * 74)
print('H 行为：真能移动 / 可复现 / 异时可变 / 驻留期不许即到即走')
print('=' * 74)


def _run(seed_roster=('a',), n=400, salt=''):
    st = R.RoamState(enabled=True)
    mv = []
    for i in range(n):
        now = 1000.0 + i * 60.0
        r = R.step(st, now, roster=list(seed_roster), salt=salt,
                   decide_fn=lambda nid, now, **kw: ('room_x', 'wander'))
        if r['moved']:
            mv.append((now, r['moved']))
    return st, mv


_st1, _mv1 = _run()
check('H1 ★★ 打开开关后真会发生移动（不是空转）', bool(_mv1), '移动次数=%d' % len(_mv1))

_st2, _mv2 = _run()
check('H2 同样输入可复现（确定性）', _mv1 == _mv2, '')

_st3, _mv3 = _run(salt='other')
# ★ 负控制必须**真能失败**：断言"salt 变了，摇号源就变了"（直接比同一时刻的 `_unit`）
_u_a = R._unit('a', 1234.5, '')
_u_b = R._unit('a', 1234.5, 'other')
check('H3n 负控制：换 salt ⇒ 摇号值必须变（证明 H2 的确定性不是"忽略 salt"）',
      _u_a != _u_b, 'salt=""→%.6f salt="other"→%.6f' % (_u_a, _u_b))

# 驻留期：一次移动后，MIN_DWELL 之内不许再被"决策"挪走
_st4 = R.RoamState(enabled=True)
_r1 = R.step(_st4, 10000.0, roster=['a'],
             decide_fn=lambda nid, now, **kw: ('room_x', 'w'))
_t1 = _st4.get('a')
check('H4 ★ 驻留期 = MIN_DWELL_SECONDS（不许即到即走）',
      _t1 is not None and abs(_t1.remaining(10000.0) - R.MIN_DWELL_SECONDS) < 1e-6,
      'remaining=%.1f min_dwell=%.1f' % (_t1.remaining(10000.0) if _t1 else -1,
                                         R.MIN_DWELL_SECONDS))

# 到期：直到 until 之后才必然可被重决策（这里用超长时距证明"到期后会重决策"）
_st5 = R.RoamState(enabled=True)
R.step(_st5, 20000.0, roster=['a'], decide_fn=lambda nid, now, **kw: ('room_x', 'w'))
_r5 = R.step(_st5, 20000.0 + R.MAX_DWELL_SECONDS + 10.0, roster=['a'],
             decide_fn=lambda nid, now, **kw: ('room_y', 'w'))
check('H5 ★ 到期后被"撤掉覆盖"（回落站位表，由宿主重新决策）',
      'a' in _r5['expired'] or _st5.resident_of('a') == 'room_y',
      'expired=%s now=%s' % (_r5['expired'], _st5.resident_of('a')))

# 非法 now 不抛
_ok2 = True
try:
    R.step(R.RoamState(enabled=True), None)
    R.step(R.RoamState(enabled=True), 'abc')
except Exception:
    _ok2 = False
check('H6 非法 now（None/"abc"）不抛', _ok2, '')

# decide_fn 返回 None / 坏形状 ⇒ 不产生驻留
st_h = R.RoamState(enabled=True)
R.step(st_h, 30000.0, roster=['a'], decide_fn=lambda nid, now, **kw: None)
R.step(st_h, 31000.0, roster=['b'], decide_fn=lambda nid, now, **kw: 12345)
check('H7 decide_fn 返回 None / 坏形状 ⇒ 不记驻留（不抛）',
      st_h.resident_of('a') is None and st_h.resident_of('b') is None, '')

# 无 decide_fn ⇒ 不抛（roster 给了也不动）
st_h2 = R.RoamState(enabled=True)
_r7 = R.step(st_h2, 40000.0, roster=['a'], decide_fn=None)
check('H8 无 decide_fn ⇒ 安静不动（不抛）', not _r7['moved'], '')

# ================================================================ W
print()
print('=' * 74)
print('W ★★★ 产品接线（"函数写对了" ≠ "产品用上了" —— 本项目最贵的坑）')
print('=' * 74)

MAIN = os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py')
_msrc = read(MAIN)
_mtree = ast.parse(_msrc)

_cls = None
for _n in _mtree.body:
    if isinstance(_n, ast.ClassDef) and _n.name == 'RalseiPet':
        _cls = _n
        break
check('W1 main.py 可编译且找得到 RalseiPet 类', _cls is not None, '')

_consts = {}
for _n in _cls.body:
    if isinstance(_n, ast.Assign) and len(_n.targets) == 1 \
            and isinstance(_n.targets[0], ast.Name):
        _consts[_n.targets[0].id] = _n.value
_am = _consts.get('NPC_AUTONOMOUS_MOVE')
check('W2 ★★★ NPC_AUTONOMOUS_MOVE 在位且默认 **True**（第80轮按用户裁决打开）',
      isinstance(_am, ast.Constant) and _am.value is True,
      'value=%s' % getattr(_am, 'value', None))

_imp = []
for _n in _mtree.body:
    if isinstance(_n, ast.ImportFrom):
        _imp += [a.asname or a.name for a in _n.names]
check('W3 npc_intent / npc_roam 真被 main import',
      'npc_intent_mod' in _imp and 'npc_roam_mod' in _imp,
      '缺=%s' % [x for x in ('npc_intent_mod', 'npc_roam_mod') if x not in _imp])

_meths = set()
for _n in ast.walk(_cls):
    if isinstance(_n, ast.FunctionDef):
        _meths.add(_n.name)
_need = ['_npc_roam_tick', '_npc_roam_reachable', '_npc_roam_traits',
         '_npc_roam_familiar', '_npc_roam_friends', '_npc_roam_scene_of',
         '_npc_roam_decide', '_npc_roam_sleep']
check('W4 八个接线方法全部在位（第80轮 +`_npc_roam_sleep`）',
      not [m for m in _need if m not in _meths],
      '缺=%s' % ([m for m in _need if m not in _meths] or '无'))

# ★★ 最贵的一条：`_npc_scene_roster` **真读** resident_of（否则层2 = 死代码）
_roster = [n for n in ast.walk(_cls)
           if isinstance(n, ast.FunctionDef) and n.name == '_npc_scene_roster']
_r_calls = set()
for _n in ast.walk(_roster[0]) if _roster else []:
    if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Attribute):
        _r_calls.add(_n.func.attr)
check('W5 ★★★ `_npc_scene_roster` 真调 `resident_of()`（层2 不是死代码）',
      'resident_of' in _r_calls, 'calls=%s' % sorted(_r_calls))
# ★ 且**同时**回落 `scene_of()`（覆盖模式：没覆盖要回站位表）
check('W5b ★ 同时保留 `scene_of()` 回落（覆盖模式，不是替换）',
      'scene_of' in _r_calls, '')

# ★★ `_npc_roam_tick` 真调 `npc_roam_mod.step`
_tick = [n for n in ast.walk(_cls)
         if isinstance(n, ast.FunctionDef) and n.name == '_npc_roam_tick']
_t_calls = set()
for _n in ast.walk(_tick[0]) if _tick else []:
    if isinstance(_n, ast.Call):
        if isinstance(_n.func, ast.Attribute):
            _t_calls.add(_n.func.attr)
        elif isinstance(_n.func, ast.Name):
            _t_calls.add(_n.func.id)
check('W6 ★★ `_npc_roam_tick` 真调 `step()`（推进真发生）',
      'step' in _t_calls, 'calls=%s' % sorted(_t_calls))

# ★★ update_movement 真调 _npc_roam_tick，且排在所有 return 之前
_um = [n for n in ast.walk(_cls)
       if isinstance(n, ast.FunctionDef) and n.name == 'update_movement']
_um_calls_ln = []
_um_rets = []
for _n in ast.walk(_um[0]) if _um else []:
    if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Attribute) \
            and _n.func.attr == '_npc_roam_tick':
        _um_calls_ln.append(_n.lineno)
    if isinstance(_n, ast.Return):
        _um_rets.append(_n.lineno)
# ⚠️ 第92轮：输出**不再打印行号** —— 行号会随任何一次"上面插了几行注释"而漂移，
#    于是本判据每轮都报假 DIFF（第92轮实测：基线记 6699、实际 6347，差 352 行）。
#    判据本身（"有调用点" / "调用点早于第一个 return"）**逐字未改**，只把**证据形态**
#    从"行号"换成"计数 + 布尔"（同样可判、且不漂）。
check('W7 ★★ `update_movement` 真调 `_npc_roam_tick`（挂在主循环上）',
      bool(_um_calls_ln), '调用点数=%d' % len(_um_calls_ln))
check('W7b ★★ 且排在**所有 `return`（早退分支）之前** —— 宠物睡着时世界照样转',
      bool(_um_calls_ln) and bool(_um_rets) and min(_um_calls_ln) < min(_um_rets),
      'call_before_first_return=%s (calls=%d returns=%d)'
      % (bool(_um_calls_ln and _um_rets and min(_um_calls_ln) < min(_um_rets)),
         len(_um_calls_ln), len(_um_rets)))

# ★ 开关判据：`_npc_roam_tick` 必须**读** NPC_AUTONOMOUS_MOVE（否则开关是摆设）
_tick_src = ast.get_source_segment(_msrc, _tick[0]) if _tick else ''
check('W8 ★ `_npc_roam_tick` 真读 `NPC_AUTONOMOUS_MOVE`（开关不是摆设）',
      'NPC_AUTONOMOUS_MOVE' in (_tick_src or ''), '')

# ================================================================ I
print()
print('=' * 74)
print('I 序列化 + 判据自身体检')
print('=' * 74)

st_i = R.RoamState(enabled=True)
st_i.put('q', 'room_q', 12345.0, reason='wander')
_rt = R.RoamState.from_dict(st_i.to_dict())
check('I1 序列化往返（resident_of + enabled 都保住）',
      _rt.resident_of('q') == 'room_q' and _rt.enabled is True, '')

check('I2 坏数据 from_dict 不抛',
      R.RoamState.from_dict({'stays': [None, 123, {'npc_id': 'x'}]}) is not None, '')

# ★★★ I3 接线台账诚实 —— **第81轮改**（判据随事实改，不弱化鉴别力）
#   第79轮口径：`not_yet` 必须**非空**（那时层3/层4 确实还没做）。
#   第81轮层4 存档**已完成** ⇒ `not_yet` 真的空了 ⇒ 旧判据变成"过窄"（会误报）。
#   ★ 但**不许**简单删掉 `not_yet` 那一半（那会留下"偷偷清空 `not_yet` 却没接线"
#     的漏洞）。改法是换成**有鉴别力的**：`wired=True` ⇒ ① `used_by` 非空（谁在用
#     要说清）；② 若 `not_yet` 为空，则 `wired_how` 必须**写明层4 的落盘接线**
#     （`npc_plan_store` = 本模块唯一的层4 兑现证据）——既证"真做完了"，
#     又挡住"没做却把 `not_yet` 清空"。
#   （同规先例：第70轮 `check57` A9 上限随事实改 / §60.3「判据过窄 = 会误报」。）
_w = R.WIRING
_w_how = _w.get('wired_how') or ''
_w_done4 = '层4' in _w_how and 'npc_plan_store' in _w_how
check('I3 ★ 接线台账诚实（wired=True ⇒ used_by 非空；not_yet 空时须 wired_how '
      '写明层4 落盘接线 —— 防"没做却清空 not_yet"）',
      _w.get('wired') is True and bool(_w.get('used_by'))
      and (bool(_w.get('not_yet')) or _w_done4),
      'wired=%s used_by=%d not_yet=%d 层4证据=%s' % (
          _w.get('wired'), len(_w.get('used_by') or []),
          len(_w.get('not_yet') or []), _w_done4))

_self_tree = ast.parse(_SELF)
# ★★ I4 的打印点数：只该有 `check()` 本体那 1 处。
#    ★ 不能用 `_SELF.count("print('[PASS]")` —— 判据自己的字面量也含标记（自指）。
_N_PRINT_PASS = _print_points(_self_tree, '[PASS]')
_N_PRINT_OK = _print_points(_self_tree, '[OK]')
# ★ I4n 负控制：真造一份"带**两处**标记字面量"的假源码，同样的检测**必须**数出 2。
#    ★ 夹具必须与真源码**同量级**（真源码恰 1 处 = check() 本体）；
#      只放 1 处 ⇒ 数出 1 ⇒ 判据"恒真"（第一版就是这么写错的）。
_FAKE_SRC = ("def f():\n"
             "    print('[PASS] x')\n"
             "def g():\n"
             "    print('[PASS] y')\n")
_N_FAKE = _print_points(ast.parse(_FAKE_SRC), '[PASS]')

check('I4 ★ 判据名里不含计数标记字样（免得自指污染 run_all 计数）',
      _N_PRINT_PASS + _N_PRINT_OK == 1,
      '打印点=%d（应恰 1 = check() 本体）' % (_N_PRINT_PASS + _N_PRINT_OK))

check('I4n 负控制：同样的检测喂"额外打标记"的源码必须数出 > 1（证明 I4 非恒真）',
      _N_FAKE > 1, '假源码数出=%d' % _N_FAKE)

check('I5 ★★ 记账口非 no-op（造失败真进账，且不打标记到 stdout）', _probe_ledger(), '')

# ★★ 负控制：真做一个 **no-op 记账口**，喂同样的"造失败"，必须判否。
#    ★ 第一版写成 `lambda: (f0 == f0) or True` —— 恒真，等于没控制（本项目最贵的坑）。
def _noop_ledger():
    """no-op 版：**什么都不动**，却宣称成功。"""
    p0, f0 = PASS, FAIL
    got = (FAIL == f0 + 1)          # 没动 FAIL ⇒ 必然 False
    return got and (PASS, FAIL) == (p0, f0)


check('I5n 负控制：no-op 版记账口喂同一个"造失败"必须判否',
      not _noop_ledger(), '')

# ★★ I6 记账守恒：**用独立计数器交叉核对**（不数 AST —— 循环会让调用点数 ≠ 执行数）。
#    `CALLS` 在 check() 入口 +1；`PASS+FAIL` 在出口 +1。
#    真判据 = 两者必须**永远相等** ⇒ 抓"某条分支进了 check 却没进账 / 没进 check 却进了账"。
_N_SO_FAR = PASS + FAIL
check('I6 ★ 记账守恒（独立计数器 CALLS == PASS+FAIL，抓漏记/错记）',
      CALLS == PASS + FAIL,
      'CALLS=%d PASS+FAIL=%d' % (CALLS, PASS + FAIL))

# ★★ I6n 负控制：造一个**只加 CALLS 不加 PASS/FAIL**的假入口，守恒必须被破坏。
def _broken_entry():
    """模拟"进了 check 却漏记"：CALLS +1，PASS/FAIL 不动。"""
    global CALLS
    CALLS += 1
    return CALLS


_c0, _p0, _f0 = CALLS, PASS, FAIL
_broken = _broken_entry()
_breaks = (_broken != PASS + FAIL)
CALLS, PASS, FAIL = _c0, _p0, _f0          # 精确还原，不留痕
check('I6n 负控制：漏记一格的假入口必须破坏守恒（证明 I6 有鉴别力）',
      _breaks, '')

# ================================================================ J
# ★★★ 第80轮追加：**层3 就寝**（用户裁决 ③「**废除**」=
#     NPC 就寝不再用常量 `BEDTIME_HOME_SCENE`，改**逐人决策**）。
#     ★ 只断言**结构 / 行为**，不断言实现细节：真源仍由 `npc_intent` 持有。
print()
print('=' * 74)
print('J 层3 就寝（第80轮：旧常量 → 逐人决策）')
print('=' * 74)

# ---- J1：`decide_sleep` 在位且零依赖（AST 核"只调标准库"）----
_ds = [n for n in ast.walk(tree)
       if isinstance(n, ast.FunctionDef) and n.name == 'decide_sleep']
check('J1 `decide_sleep()` 在位（层3 的纯逻辑入口）', bool(_ds), '')

# ★ 结构保证：`decide_sleep` **不许**自己 import 任何东西（零依赖纪律的硬形态）。
_ds_inner_imp = []
for _n in ast.walk(_ds[0]) if _ds else []:
    if isinstance(_n, (ast.Import, ast.ImportFrom)):
        _ds_inner_imp.append(getattr(_n, 'lineno', '?'))
check('J1b ★ `decide_sleep` 里零 import（决策器是**注入**的，不是 import 的）',
      not _ds_inner_imp, 'import@%s' % (_ds_inner_imp or '无'))

# ---- J2：白天不问（`SLEEP_PHASE` 之外一律不决策）----
_j_day = R.decide_sleep(0.0, phase='day',
                        sleep_fn=lambda *a, **k: ('room_b', 'x'), npc_id='a')
_j_day2 = R.decide_sleep(0.0, phase='dusk',
                         sleep_fn=lambda *a, **k: ('room_b', 'x'), npc_id='a')
check('J2 ★ 白天/黄昏不问"今晚睡哪"（`SLEEP_PHASE` 闸：不许白天把人赶去睡）',
      _j_day == (None, 'day') and _j_day2 == (None, 'day'),
      'day=%s dusk=%s' % (_j_day, _j_day2))
# ★ J2n 负控制：同样输入、只把 phase 换成 night ⇒ **必须**给出场景（证明 J2 非恒真）
_j_night = R.decide_sleep(0.0, phase='night',
                          sleep_fn=lambda *a, **k: ('room_b', 'x'), npc_id='a')
check('J2n 负控制：换成 night 后必须真给出场景（证明 J2 有鉴别力）',
      _j_night == ('room_b', 'x'), 'night=%s' % (_j_night,))

# ---- J3：没注入决策器 ⇒ 降级为"不作决策"（不抛、不编地点）----
_j_nofn = R.decide_sleep(0.0, phase='night', sleep_fn=None, npc_id='a')
check('J3 ★ 未注入 `sleep_fn` ⇒ `(None, \'no_fn\')`（降级不抛，也不编一个地点）',
      _j_nofn == (None, 'no_fn'), '%s' % (_j_nofn,))

# ---- J4：决策器抛异常 ⇒ 吞掉（一条 NPC 的 bug 不许带崩整拍）----
def _boom(*a, **k):
    raise RuntimeError('boom')


_j_boom = R.decide_sleep(0.0, phase='night', sleep_fn=_boom, npc_id='a')
check('J4 ★ 决策器抛异常被吞（单点故障不带崩整拍）', _j_boom == (None, 'no_fn'),
      '%s' % (_j_boom,))

# ---- J5：桌面闸 —— 睡觉也不许把 NPC 放进桌面（与 `step()` 同一条闸）----
_j_desk = R.decide_sleep(0.0, phase='night',
                         sleep_fn=lambda *a, **k: ('desktop', 'own_home'),
                         npc_id='a', cur_scene='room_x')
check('J5 ★★ 桌面闸：睡觉也不许自主进 `desktop`（与 `step()` 同一条闸）',
      _j_desk == (None, 'desktop_blocked'), '%s' % (_j_desk,))

# ---- J6：已在正确的地方 ⇒ 不记（避免"刷表"，也避免无意义重建身体）----
_j_same = R.decide_sleep(0.0, phase='night',
                         sleep_fn=lambda *a, **k: ('room_x', 'own_home'),
                         npc_id='a', cur_scene='room_x')
check('J6 ★ 决策结果 = 他现在待的地方 ⇒ `(None, \'already\')`（不刷表）',
      _j_same == (None, 'already'), '%s' % (_j_same,))

# ---- J7 ★★★ 零回归：`enabled=False` 时**就寝也一个字节都不改** ----
_DAY = 86400.0
_NIGHT = _DAY * 3 + 22 * 3600.0            # 冻时段：第3天 22:00（`night`）
check('J7p 前置：冻的那个时刻确实是 `night`（否则 J7 测的不是就寝路径）',
      R._phase_name(_NIGHT) == 'night', 'phase=%s' % R._phase_name(_NIGHT))

_st_off = R.RoamState(enabled=False)
_out_off = R.step(_st_off, _NIGHT, roster=['a'],
                  decide_fn=lambda *a, **k: None,
                  home_of=lambda n: 'room_a',
                  reachable_of=lambda n: ['room_a', 'room_b'],
                  sleep_fn=lambda *a, **k: ('room_b', 'own_home'))
check('J7 ★★★ 零回归：`enabled=False` ⇒ 就寝也**零副作用**（表空、last_step 不动）',
      _out_off == {'decided': [], 'expired': [], 'moved': []}
      and _st_off.resident_of('a') is None and _st_off.last_step == 0.0,
      'out=%s last_step=%s' % (_out_off, _st_off.last_step))

# ★ J7n 负控制：同样输入、只把 enabled 改 True ⇒ **必须**真落表（证明 J7 非恒真）
_st_on = R.RoamState(enabled=True)
_out_on = R.step(_st_on, _NIGHT, roster=['a'],
                 decide_fn=lambda *a, **k: None,
                 home_of=lambda n: 'room_a',
                 reachable_of=lambda n: ['room_a', 'room_b'],
                 sleep_fn=lambda *a, **k: ('room_b', 'own_home'))
check('J7n 负控制：打开后必须真落表（证明 J7 的零回归不是"因为什么都没做"）',
      _st_on.resident_of('a') == 'room_b'
      and any(m[0] == 'a' for m in _out_on['moved']),
      'resident=%s out=%s' % (_st_on.resident_of('a'), _out_on))

# ---- J8：就寝走**长驻留**（不是 3 分钟就被摇走）----
_st_l = R.RoamState(enabled=True)
R.step(_st_l, _NIGHT, roster=['a'], decide_fn=lambda *a, **k: None,
       home_of=lambda n: 'room_a', reachable_of=lambda n: ['room_a', 'room_b'],
       sleep_fn=lambda *a, **k: ('room_b', 'own_home'))
_stay_l = _st_l.get('a')
check('J8 ★ 就寝按**长驻留**落表（`SLEEP_DWELL_SECONDS`，不是 `MIN_DWELL`）',
      _stay_l is not None
      and (_stay_l.until - _stay_l.since) >= R.SLEEP_DWELL_SECONDS - 1e-6
      and (_stay_l.until - _stay_l.since) > R.MIN_DWELL_SECONDS,
      'dwell=%.0f min_dwell=%.0f' % ((_stay_l.until - _stay_l.since),
                                     R.MIN_DWELL_SECONDS))
check('J8b ★ 就寝的 `reason` 带 `sleep:` 前缀（可区分"睡"与"逛"，便于诊断/存档）',
      _stay_l is not None and str(_stay_l.reason).startswith('sleep:'),
      'reason=%s' % (getattr(_stay_l, 'reason', None),))

# ---- J9 ★★ 本拍已挪窝的人**不被就寝覆盖**（两件事不许互相踩）----
_st_m = R.RoamState(enabled=True)
_out_m = R.step(_st_m, _NIGHT, roster=['a'],
                decide_fn=lambda *a, **k: ('room_c', 'wander'),
                home_of=lambda n: 'room_a',
                reachable_of=lambda n: ['room_a', 'room_b', 'room_c'],
                sleep_fn=lambda *a, **k: ('room_b', 'own_home'))
check('J9 ★★ 本拍已经"逛到别处"的人 ⇒ 不被就寝覆盖（两件事不互相踩）',
      _st_m.resident_of('a') == 'room_c', 'resident=%s' % _st_m.resident_of('a'))

# ---- J10 ★★ 产品接线：`main._npc_roam_sleep` 真被造出 + 真被注入 + 真调真源 ----
_sleep_m = [n for n in ast.walk(_cls)
            if isinstance(n, ast.FunctionDef) and n.name == '_npc_roam_sleep']
check('J10 ★★ `main._npc_roam_sleep` 在位（层3 的宿主侧接线）', bool(_sleep_m), '')
_sl_calls = set()
for _n in ast.walk(_sleep_m[0]) if _sleep_m else []:
    if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Attribute):
        _sl_calls.add(_n.func.attr)
check('J10b ★★★ `_npc_roam_sleep` 真调 `choose_sleep_scene`（真源，不是自己另编一套）',
      'choose_sleep_scene' in _sl_calls, 'calls=%s' % sorted(_sl_calls))
# ★ 且 `step()` 调用点真注入 `sleep_fn=self._npc_roam_sleep`
_sf_injected = False
for _n in ast.walk(_tick[0]) if _tick else []:
    if isinstance(_n, ast.Call):
        for _kw in _n.keywords:
            if _kw.arg == 'sleep_fn':
                _sf_injected = True
check('J10c ★★★ `_npc_roam_tick` 真把 `sleep_fn` 注入 `step()`（否则层3 = 死代码）',
      _sf_injected, '')
# ★ 负控制：**未注入**的同一次调用必须被抓到（证明 J10c 有鉴别力）
_sf_neg = False
for _kw in (ast.Call(func=ast.Name(id='step'), args=[], keywords=[])).keywords:
    if _kw.arg == 'sleep_fn':
        _sf_neg = True
check('J10n 负控制：不带 `sleep_fn` 的调用形状必须判否（证明 J10c 非恒真）',
      not _sf_neg, '')

# ---- J11 ★★ 旧口径**对 NPC 已废弃**：`BEDTIME_HOME_SCENE` 处有废弃声明 ----
# ★ 判据侧教训（第80轮现场踩到）：第一版写死 `'NPC 不适用'`**过窄**
#   —— 真源写的是「NPC 完全不适用」⇒ 整条被丢（报了个假红）。
#   ⇒ 改判「**声明与 NPC 相关 + 明确废弃**」两个语义条件，**不锁具体措辞**。
#     ★★ 仍然要**锚在真实注释**上：只认带 `#` 的注释行，不认代码里的标识符。
_bhs = _msrc.count('BEDTIME_HOME_SCENE')
_has_npc_depre = False
for _ln in _msrc.splitlines():
    _s = _ln.strip()
    if not _s.startswith('#'):
        continue
    if 'NPC' in _s and ('不适用' in _s or '废弃' in _s or '无关' in _s):
        _has_npc_depre = True
        break
check('J11 ★★ `BEDTIME_HOME_SCENE` ∈ main.py 且**注释里**有"NPC 不适用/已废弃"声明'
      '（用户裁决 ③「废除」落在**注释真源**上）',
      _bhs >= 1 and _has_npc_depre,
      'occurrences=%d 有NPC废弃声明=%s' % (_bhs, _has_npc_depre))
# ★ J11n 负控制：把**所有注释**抹掉后，同样的检测必须判否
#   （证明 J11 真在读注释，不是被代码里的标识符蒙对）
_stripped = '\n'.join(
    ('' if ln.strip().startswith('#') else ln) for ln in _msrc.splitlines())
_has2 = any(('NPC' in s and ('不适用' in s or '废弃' in s or '无关' in s))
            for s in (l.strip() for l in _stripped.splitlines())
            if s.startswith('#'))
check('J11n 负控制：抹掉注释后检测必须判否（证明 J11 锚在注释上、非恒真）',
      not _has2, '')

# ---- J12 ★★★ 就寝**不与用户耦合**（L2 的结构保证，与 D 段同口径）----
_ds_args = set()
for _n in ast.walk(_ds[0]) if _ds else []:
    if isinstance(_n, ast.arg):
        _ds_args.add(_n.arg)
_banned = [a for a in _ds_args if a.lower() in
           ('pet', 'user', 'player', 'host', 'me', 'owner')]
check('J12 ★★★ `decide_sleep` 形参里无 pet/user/player（就寝不依赖用户，L2）',
      not _banned, 'args=%s' % sorted(_ds_args))
check('J12n 负控制：同样的检测喂一个带 `user` 的假签名必须判否',
      bool([a for a in (set(_ds_args) | {'user'}) if a.lower() in
            ('pet', 'user', 'player', 'host', 'me', 'owner')]), '')

print()
print('=' * 74)
print('结果：PASS=%d FAIL=%d' % (PASS, FAIL))
if FAILED:
    print('失败项：%s' % FAILED)
print('=' * 74)
sys.exit(1 if FAIL else 0)
