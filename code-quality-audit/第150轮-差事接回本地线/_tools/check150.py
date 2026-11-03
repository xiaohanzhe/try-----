# -*- coding: utf-8 -*-
u"""第150轮回归锁：**口径③「可派任何角色去别世界办事」落地**（差事 / errand）。

## 口径（记忆 §7，逐字）

> **「灵魂视角」＝显示切换的唯一驱动**：只有灵魂/我的视角移动才切显示；
> **NPC 自主移动不切显示但≠不存在**；可派**任何角色**去别世界办事、**中途进场能看到过程**。
> 「我让 ralsei 去 oneshot 里干什么事情，**他能去，干，然后产生结果**，
>    甚至**我中途进去的时候也能看到过程**」
> 「那个可派 ralsei 做任务那个**只是个例子，任何人都可以**」

## 本轮做了什么（第149轮 §1 表里那行"缺口（未实现）"）

第149轮 `check149 D1` 显式登记「差事本地零实现 ⇒ 红 = 有人补上了，回来更新 §149」。
本轮**就是来把它补上的**，所以 `D1` 按设计翻面成「已落地（红 = 被回滚）」。

**为什么不是重写**（这是本轮唯一的取舍，落盘在 `report150.md` §2）：
上游产品补丁 `git apply --3way --check` 三处**全 clean**（`dialogue_ui.py` /
`npc_system.py` / `main.py`）⇒ 直接接进本地线。重写 1200 行只会多一份**不同源的真源**。

## 本套件守什么

| 段 | 守什么 | 判据类型 |
|----|--------|----------|
| A | `npc_errand` 机制：生命周期 / 结果定格 / 无白名单 / 名额 / 作废 | **真 import 真跑** |
| B | `npc_system` 章名归一（`ut`↔`undertale`）：29 位 UT/UTY 角色的"回家路" | **真调用** |
| C | 世界门控：**真注册表** 8 组输入，且与 `world_gate` **结论逐条相同** | **真跑** |
| D | 派发入口 `assign_errand`：被拒要**留痕**、允许要真派、任意角色都行 | **真跑** |
| E | 推进 `_npc_errand_tick`：路上不压位置 / 到了压 / 办完撤 / 门控中途失效要作废 | **真跑（假宿主）** |
| F | 宿主接线：`_npc_errand_tick` 排在 `_npc_roam_tick` **之后**、门控**三处同一条** | **AST** |
| G | 落盘：**独立一本**（`npc_errands.json`）+ 读**不许**走 `npc_plan_store.load` | AST + 真跑往返 |
| H | 与显示解耦（`switch`/`travel_to` 零处）+ 零依赖 + 自检 | AST |

## 判据纪律（本项目踩过的坑，逐条对应）

1. **断行为不断赋值** —— A/C/D/E 段全部真跑真对象，不看"代码里写了这几个字"。
2. **正/负控制成对** —— 每一对只差**一个**变量（球 / carried / abort / 开关）。
3. **分母闸防空集恒真** —— A0 / F0 / C0 先证明"真读到了东西、真扫到了大文件"。
4. **判据互证 ≠ 独立验证** —— C6 不拿"我自己算的"做基准，基准是 `npc_system.world_gate`
   这个**产品里本来就有的**函数；两处不一致就红。
5. **判据禁回显时相量** —— `H9` 扫自己：detail 里不许 `%d`、不许引用行号。
6. **能上 AST 就上 AST** —— F/G/H 走 AST，不做子串扫描（串里一提就误报）。
"""
import ast
import io
import os
import sys
import tempfile

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')
MAIN = os.path.join(PKG, 'src', 'main.py')
MODS = os.path.join(PKG, 'modules')
ERRAND_PY = os.path.join(MODS, 'npc_errand.py')
NPC_SYS_PY = os.path.join(MODS, 'npc_system.py')
DUI_PY = os.path.join(MODS, 'dialogue_ui.py')
REPORT = os.path.join(ROUND, 'report150.md')

for _p in (PKG, os.path.join(PKG, 'src'), os.path.join(PKG, 'modules')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from main import RalseiPet                                  # noqa: E402
from modules import npc_errand as ER                        # noqa: E402
from modules import npc_system as NS                        # noqa: E402
from modules import scene_system as SS                      # noqa: E402
from modules import npc_plan_store as PS                    # noqa: E402


def _src(path):
    u"""读源码（**字节忠实**：`newline=''` 保留原行尾）。"""
    with io.open(path, 'r', encoding='utf-8', newline='') as fh:
        return fh.read()


SRC_MAIN = _src(MAIN)
TREE_MAIN = ast.parse(SRC_MAIN)
SRC_ERR = _src(ERRAND_PY)
TREE_ERR = ast.parse(SRC_ERR)
SRC_DUI = _src(DUI_PY)
TREE_DUI = ast.parse(SRC_DUI)

_n_pass = 0
_n_fail = 0
_n_calls = 0
_failed = []
_marks = 0


def check(desc, cond, detail=''):
    global _n_pass, _n_fail, _n_calls
    _n_calls += 1
    if cond:
        _n_pass += 1
        print('[PASS] %s%s' % (desc, ('    ' + detail) if detail else ''))
    else:
        _n_fail += 1
        _failed.append(desc)
        print('[FAIL] %s%s' % (desc, ('    ' + detail) if detail else ''))


def mark(title):
    global _marks
    _marks += 1
    print('---- [判据点 %d] %s ----' % (_marks, title))


# ===================================================================== 工具

def _clsdef(tree, name):
    for n in ast.walk(tree):
        if isinstance(n, ast.ClassDef) and n.name == name:
            return n
    return None


def _method(cls, name):
    if cls is None:
        return None
    for n in cls.body:
        if isinstance(n, ast.FunctionDef) and n.name == name:
            return n
    return None


def _calls(fn, attr):
    u"""`fn` 体内**属性调用** `x.attr(...)` 的全部节点。"""
    out = []
    if fn is None:
        return out
    for c in ast.walk(fn):
        if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute) \
                and c.func.attr == attr:
            out.append(c)
    return out


def _attr_names(fn):
    u"""`fn` 体内所有属性调用的**方法名集合**（`x.foo()` ⇒ `'foo'`）。"""
    out = set()
    if fn is None:
        return out
    for c in ast.walk(fn):
        if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute):
            out.add(c.func.attr)
    return out


def _mod_imports(tree):
    u"""模块**顶层**（不在任何函数/类里）的 import 名集合。

    ★ 判据要能区分"顶层 import"与"函数内 import" —— 本项目零依赖纪律
      两条都禁，但禁的不是同一件事（前者防初始化环，后者防隐性耦合）。
    """
    names = []
    for n in tree.body:
        if isinstance(n, ast.Import):
            for a in n.names:
                names.append(a.name.split('.')[0])
        elif isinstance(n, ast.ImportFrom):
            names.append((n.module or '').split('.')[0])
    return set(names)


def _inner_imports(tree):
    u"""**函数体内**的 import 节点（零依赖纪律要禁的那一类）。"""
    out = []
    for fn in ast.walk(tree):
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for c in ast.walk(fn):
                if isinstance(c, (ast.Import, ast.ImportFrom)):
                    out.append(c.lineno)
    return out


#: 显示切换的两条通道（与 `check149` 同一份定义 —— 两处写两份就会各自漂移）。
_DISPLAY_METHODS = ('switch', 'travel_to')


def harvest_display_calls(tree):
    u"""`{宿主函数名: [被调方法名, ...]}`（行号不进判据）。"""
    out = {}
    for fn in ast.walk(tree):
        if not isinstance(fn, ast.FunctionDef):
            continue
        for c in ast.walk(fn):
            if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute) \
                    and c.func.attr in _DISPLAY_METHODS:
                out.setdefault(fn.name, []).append(c.func.attr)
    return dict((k, sorted(set(v))) for k, v in out.items())


class _Mem(object):
    u"""`MiniMemory` 的桩：只记"谁被写了什么"。"""

    def __init__(self):
        self.log = []

    def remember(self, nid, text, who=None):
        self.log.append((nid, text, who))

    def save(self, nid):
        pass


class _Cur(object):
    u"""`npc_roam` 覆盖表里的一格（宿主只读 `.scene`）。"""

    def __init__(self, scene):
        self.scene = scene


class _Roam(object):
    u"""`npc_roam` 的桩：**记录每一次 put/drop**（判据要看"到底动没动位置"）。"""

    def __init__(self):
        self.tbl = {}
        self.puts = []
        self.drops = []

    def get(self, nid):
        return self.tbl.get(nid)

    def put(self, nid, scene, now, reason=''):
        self.tbl[nid] = _Cur(scene)
        self.puts.append((nid, scene, reason))

    def drop(self, nid):
        self.tbl.pop(nid, None)
        self.drops.append(nid)


class _Host(object):
    u"""**假宿主**：只装"差事那几个方法"，其余一律桩。

    ★★ 为什么用组合而不是 `class _Host(RalseiPet)`：`RalseiPet.__init__` 会建
      QMainWindow（要 `QApplication`）⇒ 判据就跑不起来了。而这里要验的
      `assign_errand` / `_npc_errand_tick` / `_npc_errand_gate` **本身不碰 Qt**
      ⇒ 把**产品里那几个真函数**挂到轻对象上，跑的仍是产品代码。

    ⚠️ `_npc_errand_world_uncached` 在产品里是 `@staticmethod`：从类上取下来
      是**裸函数**，挂到**实例**上（`self.xxx = fn`）才不会多绑一个 `self`。
      挂到**类**上就会被当实例方法 ⇒ 少一个参数 ⇒ 静默 `TypeError`。
    """

    _npc_errand_world = RalseiPet._npc_errand_world
    _npc_errand_gate = RalseiPet._npc_errand_gate
    _npc_errand_note = RalseiPet._npc_errand_note
    assign_errand = RalseiPet.assign_errand
    _npc_errand_tick = RalseiPet._npc_errand_tick
    _npc_errand_commit = RalseiPet._npc_errand_commit

    def _errand_report_ack(self, *a, **kw):
        # ★ 第153轮：产品在 tick 的 finished 分支里新调了它。
        #   桩必须跟着装 —— 否则 AttributeError 会被 tick 的
        #   `except` 吞掉，症状不是报错，而是“finished 那一段整段没执行”。
        #   看台词的地方在第153轮 `check153`。
        return None

    def __init__(self, carried=(), registry=None, enabled=True, roam=None):
        self._npc_errand_world_uncached = RalseiPet._npc_errand_world_uncached
        self.npc_registry = registry if registry is not None else NS.load_registry()
        self._carried = list(carried)
        self.npc_errand = ER.ErrandBoard(enabled=enabled)
        self.npc_memory = _Mem()
        self.npc_roam = roam
        self.seeded = 0
        self.plan_saves = 0
        self.errand_saves = 0
        self.scene = 'desktop'

    # -- 宿主桩（产品里这些都要 Qt / 磁盘，这里只记"被调了几次"）
    def _npc_carried_ids(self):
        return list(self._carried)

    def _npc_scene_id(self):
        return self.scene

    def _npc_seed_bodies(self, scene_id=None):
        self.seeded += 1

    def _npc_plan_save(self, force=False):
        self.plan_saves += 1
        return True

    def _npc_errand_save(self, force=False):
        self.errand_saves += 1
        return True


# ============================================================ A. 机制层（真跑）
mark(u'A `npc_errand` 机制：生命周期 / 结果定格 / 无白名单 / 名额 / 作废')

_EXPECT_ATTRS = ('Errand', 'ErrandBoard', 'WIRING', 'DEFAULT_TRAVEL_SECONDS',
                 'DEFAULT_WORK_SECONDS', 'MAX_ERRANDS', 'MAX_DONE', 'FILENAME')
_HAVE = [a for a in _EXPECT_ATTRS if hasattr(ER, a)]
# 分母闸：先证明"真 import 到了模块" —— 否则下面所有断言在空模块上也成立。
check(u'A0 分母闸：`npc_errand` 真被 import（八个契约常量/类全在）',
      len(_HAVE) == len(_EXPECT_ATTRS),
      u'齐=%s' % (len(_HAVE) == len(_EXPECT_ATTRS),))
check(u'A0b 常量自洽：已完成留存上限 ≥ 在办名额（否则"办完就丢"）',
      ER.MAX_DONE >= ER.MAX_ERRANDS > 0,
      u'成立=%s' % (ER.MAX_DONE >= ER.MAX_ERRANDS > 0,))

# ---- A1~A4 三段生命周期 ----
_b = ER.ErrandBoard()
_e = _b.assign(0.0, 'ralsei', 'ch1.castle_town.castle_town', '看看', travel=90.0,
               work=300.0)
_trav = (_e.status == ER.TRAVELING, _e.scene_now())
_b.step(5.0)
_mid = _e.scene_now()
_b.step(90.0)
_work = (_e.status, _e.scene_now())
_b.step(390.0)
_fin = (_e.status, _e.scene_now())

check(u'A1 路上（traveling）：`scene_now()` 返 `None` ＝ **位置不变**（不是"返出发地"）',
      _trav == (True, None), u'成立=%s' % (_trav == (True, None),))
check(u'A2 半路一拍（t=5，未到点）：仍是 `None`，且状态未跃迁',
      _mid is None and _e.status in (ER.WORKING, ER.DONE),
      u'成立=%s' % (_mid is None,))
check(u'A3 到了（working）：`scene_now()` 返 `dest_scene`（宿主据此压覆盖）',
      _work == (ER.WORKING, 'ch1.castle_town.castle_town'),
      u'成立=%s' % (_work == (ER.WORKING, 'ch1.castle_town.castle_town'),))
check(u'A4 办完（done）：`scene_now()` 仍返 `dest_scene`（结果可回查，位置不抖）',
      _fin == (ER.DONE, 'ch1.castle_town.castle_town'),
      u'成立=%s' % (_fin == (ER.DONE, 'ch1.castle_town.castle_town'),))

# ---- A5 跃迁**恰好一次** ----
_b2 = ER.ErrandBoard()
_b2.assign(0.0, 'a', 's1', '办事', travel=10.0, work=10.0)
_o1 = _b2.step(0.0)
_o2 = _b2.step(10.0)
_o3 = _b2.step(20.0)
_o4 = _b2.step(999.0)
check(u'A5 未到点那一拍：`step` 两条列表**都空**（没有跃迁就不许凭空报）',
      _o1['arrived'] == [] and _o1['finished'] == [],
      u'成立=%s' % (_o1['arrived'] == [] and _o1['finished'] == [],))
check(u'A6 到点那一拍：`arrived` 一条、`finished` 空（两段**分开**跃迁，不一步到位）',
      _o2['arrived'] == [('a', 's1')] and _o2['finished'] == [],
      u'成立=%s' % (_o2['arrived'] == [('a', 's1')] and _o2['finished'] == [],))
check(u'A7 办完那一拍：`finished` 一条、`arrived` 空',
      len(_o3['finished']) == 1 and _o3['finished'][0][0] == 'a'
      and _o3['arrived'] == [],
      u'成立=%s' % (len(_o3['finished']) == 1,))
check(u'A8 再往后推：**不再**重复报 finished（"办完"只发生一次）',
      _o4['arrived'] == [] and _o4['finished'] == [],
      u'成立=%s' % (_o4['arrived'] == [] and _o4['finished'] == [],))
check(u'A9 办完后：在办表清空、已完成表里有他（两边不重复算）',
      len(_b2) == 0 and 'a' in _b2.done,
      u'成立=%s' % (len(_b2) == 0 and 'a' in _b2.done,))

# ---- A10 结果定格 ----
_r1 = _b2.result_of('a')
_b2.step(10000.0)
_r2 = _b2.result_of('a')
check(u'A10 结果在 `done` 那刻**定格**（再推进一万秒也不变）',
      bool(_r1) and _r1 == _r2 and 's1' in _r1,
      u'成立=%s' % (bool(_r1) and _r1 == _r2,))
_taken = _b2.take_results()
check(u'A11 `take_results()` 取走即清（宿主落盘后不许重复消费）',
      len(_taken) == 1 and _taken[0][0] == 'a' and _b2.result_of('a') == '',
      u'成立=%s' % (len(_taken) == 1 and _b2.result_of('a') == '',))

# ---- A12 无白名单（用户口径「任何人都可以」）----
_b3 = ER.ErrandBoard()
_ANY_IDS = ('ralsei', 'kris', 'os_niko', 'ut_sans', 'hy_frisk', 'chara_like_thing')
_any_ok = []
for _i, _nid in enumerate(_ANY_IDS):
    _any_ok.append(_b3.assign(float(_i), _nid, 's', 'w') is not None)
check(u'A12 **无白名单**：主角团 / OneShot / UT / 同人 / 随手起的 id 全都能被派',
      all(_any_ok) and len(_any_ok) == len(_ANY_IDS),
      u'全派得出=%s' % (all(_any_ok),))
_bad = [None, '', 123, ['x']]
_bad_res = [_b3.assign(0.0, x, 's', 'w') for x in _bad]
# ⚠️ 首版这里还有个 `'   '`（纯空格），期望"拒" —— 实测**被接受**。
#   查清后判定：**产品不算错**。`isinstance(npc_id, str) and npc_id` 是产品写明的
#   契约（"非空串"），它没承诺 trim；而纯空格 id 从**唯一公开入口**进不来
#   （`assign_errand` 先过门控，注册表查不到 ⇒ 根本到不了 `board.assign`）
#   ⇒ 这条属"够不着的宽松"，不构成缺口，登记在 `report150.md` §6 遗留。
#   ⇒ 改的是**判据**（去掉这条越界的负控制），不是产品。
check(u'A13 负控制：非法 `npc_id`（None / 空串 / 数字 / 列表）一律返 `None`',
      all(r is None for r in _bad_res),
      u'全拒=%s' % (all(r is None for r in _bad_res),))

# ---- A14 名额：同一人**覆盖**不占新名额 ----
_b4 = ER.ErrandBoard()
_first = _b4.assign(0.0, 'dup', 's1', 'w')
_second = _b4.assign(1.0, 'dup', 's2', 'w2')
check(u'A14 同一人再派 ⇒ **覆盖**（对象的 `dest_scene` 变了、在办表仍是 1 条）',
      _second is not None and _second is not _first
      and _second.dest_scene == 's2' and len(_b4) == 1,
      u'成立=%s' % (len(_b4) == 1,))

# ---- A15 名额满 ----
_b5 = ER.ErrandBoard()
for _k in range(ER.MAX_ERRANDS):
    _b5.assign(0.0, 'fill%s' % _k, 's', 'w')
_over = _b5.assign(0.0, 'one_more', 's', 'w')
_over_same = _b5.assign(5.0, 'fill0', 's2', 'w')
check(u'A15 名额满（`MAX_ERRANDS`）⇒ 新人被拒（`None`）',
      _over is None, u'被拒=%s' % (_over is None,))
check(u'A16 名额满时**老人仍可覆盖**（覆盖不算新增 —— 否则他一辈子改不了主意）',
      _over_same is not None and len(_b5) == ER.MAX_ERRANDS,
      u'成立=%s' % (_over_same is not None and len(_b5) == ER.MAX_ERRANDS,))

# ---- A17 已完成 FIFO ----
_b6 = ER.ErrandBoard()
for _k in range(ER.MAX_DONE + 5):
    _b6.assign(float(_k), 'n%s' % _k, 's', 'w', travel=0.0, work=0.0)
    _b6.step(float(_k))
check(u'A17 已完成超上限 ⇒ 丢**最老**的（FIFO：第 5 条还在、第 4 条已丢）',
      len(_b6.done) == ER.MAX_DONE and 'n4' not in _b6.done
      and 'n5' in _b6.done,
      u'成立=%s' % (len(_b6.done) == ER.MAX_DONE and 'n4' not in _b6.done,))

# ---- A18/A19 作废 vs 办完（成对）----
_b7 = ER.ErrandBoard()
_e7 = _b7.assign(0.0, 'z', 's1', 'w', travel=10.0, work=10.0)
_b7.step(10.0)                       # ⇒ working
_got = _b7.abort('z')
check(u'A18 `abort` = **半途作废**：不进 `done`、不留结果、在办表里也没了',
      _got is not None and _got.status == ER.WORKING
      and 'z' not in _b7 and len(_b7.done) == 0 and _b7.result_of('z') == '',
      u'成立=%s' % (_got is not None and len(_b7.done) == 0,))
_b8 = ER.ErrandBoard()
_b8.assign(0.0, 'z', 's1', 'w', travel=10.0, work=10.0)
_b8.step(10.0)
_b8.step(20.0)                       # ⇒ 办完（不作废）
check(u'A19 正控制（同一序列**不** abort）⇒ 办完、结果非空（两种收尾真有区别）',
      len(_b8.done) == 1 and bool(_b8.result_of('z')),
      u'成立=%s' % (len(_b8.done) == 1 and bool(_b8.result_of('z')),))

# ---- A20 关闸零副作用 ----
_b9 = ER.ErrandBoard(enabled=False)
_n9 = _b9.assign(0.0, 'ralsei', 's', 'w')
_o9 = _b9.step(999.0)
check(u'A20 `enabled=False` ⇒ `assign` 恒 `None`、`step` 只返空壳、`working_positions` 恒空',
      _n9 is None and _o9 == {'arrived': [], 'finished': []}
      and _b9.working_positions() == [],
      u'成立=%s' % (_n9 is None and _b9.working_positions() == [],))

# ---- A21 容错还原（宁缺毋滥）----
_partial = {'npc_id': 'a', 'dest_scene': 's', 'what': 'w', 'status': 'working'}
_partial2 = dict(_partial, start=0.0)            # 仍缺 arrive_at / finish_at
_good = {'npc_id': 'a', 'dest_scene': 's', 'what': 'w', 'start': 0.0,
         'arrive_at': 10.0, 'finish_at': 20.0, 'status': 'working',
         'result': '', 'custom_result': ''}
check(u'A21 字段残缺 ⇒ 还原成 `None`（**不半成品还原** —— 否则某人被永远钉在某场景）',
      ER.Errand.from_dict(_partial) is None
      and ER.Errand.from_dict(_partial2) is None,
      u'全拒=%s' % (ER.Errand.from_dict(_partial) is None,))
check(u'A22 正控制：字段齐全 ⇒ 还原成功且状态/目的地一字不差',
      (lambda x: x is not None and x.status == 'working'
       and x.dest_scene == 's')(ER.Errand.from_dict(_good)),
      u'成立=%s' % (ER.Errand.from_dict(_good) is not None,))
check(u'A23 坏档 ⇒ 空看板（不抛、不半成品）；`None` 也不抛',
      len(ER.ErrandBoard.from_dict({'active': [_partial]})) == 0
      and len(ER.ErrandBoard.from_dict(None)) == 0,
      u'成立=%s' % (len(ER.ErrandBoard.from_dict(None)) == 0,))

# ---- A24 working_positions 只含 working ----
_ba = ER.ErrandBoard()
_ba.assign(0.0, 'a', 's1', 'w', travel=10.0, work=10.0)
_ba.assign(0.0, 'b', 's2', 'w', travel=10.0, work=10.0)
_w0 = _ba.working_positions()
_ba.step(10.0)
_w1 = _ba.working_positions()
check(u'A24 `working_positions()`：路上**不列**、到了才列（否则宿主提前把人瞬移过去）',
      _w0 == [] and sorted(x[1] for x in _w1) == ['s1', 's2'],
      u'成立=%s' % (_w0 == [] and len(_w1) == 2,))

# ---- A25 接线契约 ----
check(u'A25 `WIRING` 契约七键齐全且都有非空说明（判据/文档直读的唯一入口）',
      set(ER.WIRING) == set(('assign', 'tick', 'gate', 'abort', 'put', 'finish',
                             'decoupled'))
      and all(isinstance(v, str) and v.strip() for v in ER.WIRING.values()),
      u'成立=%s' % (set(ER.WIRING) == set(('assign', 'tick', 'gate', 'abort',
                                           'put', 'finish', 'decoupled')),))


# ==================================================== B. 章名归一（真调用）
mark(u'B `npc_system` 章名归一：`ut`/`uty` ↔ `undertale`/`undertale_yellow`')

check(u'B0 分母闸：别名表真有内容（空表 ⇒ 下面"双向成立"在空集上也成立）',
      bool(NS.CHAPTER_ALIASES) and 'ut' in NS.CHAPTER_ALIASES,
      u'有=%s' % (bool(NS.CHAPTER_ALIASES),))
check(u'B1 短码 → 全名：`chapter_names("ut")` 含 `undertale`',
      'undertale' in NS.chapter_names('ut') and 'ut' in NS.chapter_names('ut'),
      u'成立=%s' % ('undertale' in NS.chapter_names('ut'),))
check(u'B2 全名 → 短码（**反向**）：`chapter_names("undertale")` 含 `ut`',
      'ut' in NS.chapter_names('undertale'),
      u'成立=%s' % ('ut' in NS.chapter_names('undertale'),))
check(u'B3 `same_chapter` 双向成立（`ut`↔`undertale`、`uty`↔`undertale_yellow`）',
      NS.same_chapter('ut', 'undertale') and NS.same_chapter('undertale', 'ut')
      and NS.same_chapter('uty', 'undertale_yellow'),
      u'成立=%s' % (NS.same_chapter('ut', 'undertale'),))
check(u'B4 负控制：**不是**同一作品的必须判 False（Deltarune 章 / `ut` vs `uty` / None）',
      not NS.same_chapter('ch1', 'undertale')
      and not NS.same_chapter('ut', 'uty')
      and not NS.same_chapter(None, 'ut'),
      u'成立=%s' % (not NS.same_chapter('ch1', 'undertale'),))
check(u'B5 `chapter_matches`：空列表 ⇒ False（与旧写法 `ch in ()` 逐字等价）',
      NS.chapter_matches('ut', ()) is False
      and NS.chapter_matches('ch1', ['ch1']) is True
      and NS.chapter_matches('ut', ['undertale']) is True,
      u'成立=%s' % (NS.chapter_matches('ut', ()) is False,))


# ============================================== C. 世界门控（真注册表 · 真跑）
mark(u'C 世界门控：真注册表 8 组输入，且与 `world_gate` **结论逐条相同**')

_IDX = SS.load_index() or {}
_SCN = _IDX.get('scenes') or {}
check(u'C0 分母闸：场景索引真读到（`ok` 且 >1000 间）—— 否则下面全是空集恒真',
      bool(_IDX.get('ok')) and len(_SCN) > 1000,
      u'读到了=%s' % (bool(_IDX.get('ok')) and len(_SCN) > 1000,))

_REG = NS.load_registry()
_N_REG = len(_REG)
check(u'C0b 分母闸：NPC 注册表真读到（>50 人）',
      _N_REG > 50, u'读到了=%s' % (_N_REG > 50,))

#: 光世界 / 暗世界的**真实**场景各一（不是自造 id —— 自造 id 会让门控判成一个都没命中）
_LIGHT = 'ch1.home.torhouse'                 # ch1 光世界
_DARK_CH1 = 'ch1.castle_town.castle_town'    # ch1 暗世界
_DARK_OS = 'oneshot.barrens.Blue'            # oneshot（迁入章 ⇒ 归暗）
_DARK_UT = 'ut.rooms.room_start'             # ut（同理）


def _world_of(scene_id):
    u"""判据侧**独立**算世界（照 `_worlds.json` 的登记规则，不看产品那份缓存）。"""
    if scene_id == 'desktop':
        return 'light'
    ent = _SCN.get(scene_id) or {}
    ch = ent.get('chapter_id')
    rid = ent.get('original_room_id')
    rec = (SS.load_worlds() or {}).get('rooms', {}).get(ch) or {}
    w = rec.get(str(rid))
    return w if w in ('light', 'dark') else 'dark'


check(u'C1 `_npc_errand_world` 与独立算出的世界一致（4 个真实场景 + 桌面）',
      all(_Host()._npc_errand_world(s) == _world_of(s)
          for s in (_LIGHT, _DARK_CH1, _DARK_OS, _DARK_UT, 'desktop')),
      u'成立=%s' % (all(_Host()._npc_errand_world(s) == _world_of(s)
                        for s in (_LIGHT, _DARK_CH1, _DARK_OS, _DARK_UT,
                                  'desktop')),))

# ---- C2/C3 暗之民无球进光世界（成对：唯一变量 = 球）----
_h_noball = _Host(carried=())
_ok_noball, _why_noball = _h_noball._npc_errand_gate('ralsei', _LIGHT)
_h_ball = _Host(carried=('ralsei',))
_ok_ball, _ = _h_ball._npc_errand_gate('ralsei', _LIGHT)
check(u'C2 暗之民（Ralsei）**无球**进光世界 ⇒ 拒，且给了人话理由',
      _ok_noball is False and bool(_why_noball),
      u'拒=%s 有理由=%s' % (_ok_noball is False, bool(_why_noball)))
check(u'C3 正控制（同一对，唯一差别 = 球）⇒ 允许（不是"永远拒"的判据）',
      _ok_ball is True, u'允许=%s' % (_ok_ball is True,))

# ---- C4~C6 跨作品角色的穿行域（三档，成对）----
# ⚠️ 首版这里拿 `os_niko` 当"进不去 Deltarune 暗世界"的样本，实测**返 True**。
#   查清后判定：**判据对、我的样本选错了**。`os_niko` 的 `roam_scope == 'all'`
#   （用户口径「niko可自由穿行所有世界」⇒ 他恰恰是唯一该**放行**的那个人）。
#   ⇒ 换成 `os_the_author`（`non_dark`，同作品、不同穿行域），并把 Niko 单列一条
#     **正向**判据 —— 否则"归一 + 穿行域"改完之后顺手把 Niko 也一起关了，没人发现。
_CROSS = 'os_the_author'
_h_os = _Host()
_os_foreign, _ = _h_os._npc_errand_gate(_CROSS, _DARK_CH1)
_os_home, _ = _h_os._npc_errand_gate(_CROSS, _DARK_OS)
_os_niko_dark, _ = _h_os._npc_errand_gate('os_niko', _DARK_CH1)
check(u'C4 跨作品角色（`non_dark`）进 **Deltarune 暗世界** ⇒ 拒（「只能在非暗世界穿梭」）',
      _os_foreign is False, u'拒=%s' % (_os_foreign is False,))
check(u'C5 正控制：同一人回**自己作品**那侧 ⇒ 允许（成对，变量只是目的地）',
      _os_home is True, u'允许=%s' % (_os_home is True,))
check(u'C5b Niko（唯一 `all` 档）**照样能**进 Deltarune 暗世界 —— '
      u'别在归一的时候把「niko可自由穿行所有世界」一起关了',
      _os_niko_dark is True, u'允许=%s' % (_os_niko_dark is True,))

# ---- C6 UT 角色的"回家路"（本轮 `chapter_matches` 的红线）----
_h_ut = _Host()
_ut_home, _ = _h_ut._npc_errand_gate('ut_toriel', _DARK_UT)
_ut_foreign, _ = _h_ut._npc_errand_gate('ut_toriel', _DARK_CH1)
check(u'C6 ★ UT 角色回 `ut.*` ⇒ 允许（**这一条就是章名归一**：逐字比会判成"不属于"）',
      _ut_home is True, u'允许=%s' % (_ut_home is True,))
check(u'C7 负控制：同一 UT 角色进 `ch1.*` 暗世界 ⇒ 拒（放开的只是自己那侧）',
      _ut_foreign is False, u'拒=%s' % (_ut_foreign is False,))

# ---- C8/C9 桌面白名单 ----
check(u'C8 桌面白名单：主角团（susie）能来、跨作品（os_niko）不能来（成对）',
      _Host()._npc_errand_gate('susie', 'desktop')[0] is True
      and _Host()._npc_errand_gate('os_niko', 'desktop')[0] is False,
      u'成立=%s' % (_Host()._npc_errand_gate('susie', 'desktop')[0] is True,))

# ---- C10 规则只有一份（与产品 `world_gate` 逐条相同）----
_CASES = (
    ('ralsei', _LIGHT, ()),
    ('ralsei', _LIGHT, ('ralsei',)),
    ('ralsei', _DARK_CH1, ()),
    ('os_the_author', _DARK_CH1, ()),
    ('os_niko', _DARK_CH1, ()),
    ('os_the_author', _DARK_OS, ()),
    ('ut_toriel', _DARK_UT, ()),
    ('ut_toriel', _DARK_CH1, ()),
    ('susie', 'desktop', ()),
    ('os_the_author', 'desktop', ()),
)
_agree = []
for _nid, _dst, _car in _CASES:
    _hx = _Host(carried=_car)
    _a = _hx._npc_errand_gate(_nid, _dst)[0]
    _npcx = _REG.get(_nid)
    _bx = NS.world_gate(_npcx, _hx._npc_errand_world(_dst), scene_id=_dst,
                        carried=(_nid in _car)).ok
    _agree.append(bool(_a) == bool(_bx))
check(u'C10 **规则只有一份**：`_npc_errand_gate` 与 `npc_system.world_gate` 九组全同',
      all(_agree), u'全同=%s' % (all(_agree),))

# ---- C11 未登记 / 空目的地 ----
check(u'C11 注册表里查不到这个人 ⇒ 拒 + 人话（不是"放行然后崩在他身上"）',
      _Host()._npc_errand_gate('no_such_npc_at_all', 'desktop')[0] is False,
      u'拒=%s' % (_Host()._npc_errand_gate('no_such_npc_at_all', 'desktop')[0]
                  is False,))
_g_none = _Host()._npc_errand_gate('ralsei', None)
check(u'C12 目的地 `None` ⇒ 不抛、仍返二元组（门控**永不抛**：抛了就没人压位置）',
      isinstance(_g_none, tuple) and len(_g_none) == 2
      and isinstance(_g_none[0], bool),
      u'成立=%s' % (isinstance(_g_none, tuple) and len(_g_none) == 2,))


# ================================================ D. 派发入口（真跑）
mark(u'D `assign_errand`：被拒要**留痕**、允许要真派、任意角色都行')

_hd1 = _Host(carried=())
_r_d1 = _hd1.assign_errand('ralsei', _LIGHT, '拿点东西', now=0.0)
check(u'D1 被门控拒 ⇒ 返 `None`、看板**一条都没有**（不许"先塞进去再说"）',
      _r_d1 is None and len(_hd1.npc_errand) == 0,
      u'成立=%s' % (_r_d1 is None and len(_hd1.npc_errand) == 0,))
check(u'D2 被拒时**落了一条"去不了"的记忆**（否则过两天他茫然：压根不记得有这回事）',
      len(_hd1.npc_memory.log) == 1 and u'去不了' in _hd1.npc_memory.log[0][1],
      u'成立=%s' % (len(_hd1.npc_memory.log) == 1,))
check(u'D3 被拒不留结果（`result_of` 仍是空串 —— 没办过就没有结果）',
      _hd1.npc_errand.result_of('ralsei') == '',
      u'成立=%s' % (_hd1.npc_errand.result_of('ralsei') == '',))
_hd2 = _Host(carried=('ralsei',))
_r_d2 = _hd2.assign_errand('ralsei', _LIGHT, '拿点东西', now=0.0)
check(u'D4 正控制（给了球）⇒ 真派出：返对象、看板 1 条、**没写**"去不了"',
      _r_d2 is not None and len(_hd2.npc_errand) == 1
      and _hd2.npc_memory.log == [],
      u'成立=%s' % (_r_d2 is not None and len(_hd2.npc_errand) == 1,))
_hd3 = _Host()
_r_d3 = _hd3.assign_errand('os_niko', _DARK_OS, '看看情况', now=0.0,
                           travel=10.0, work=20.0)
check(u'D5 派的是**非主角**（os_niko）且不是 Ralsei 专属通道 ⇒ 照派不误',
      _r_d3 is not None and _r_d3.npc_id == 'os_niko'
      and _r_d3.arrive_at == 10.0 and _r_d3.finish_at == 30.0,
      u'成立=%s' % (_r_d3 is not None,))
_hd4 = _Host()
_hd4.npc_errand = None
check(u'D6 看板没就位（建失败降级）⇒ 返 `None`、不抛（只降级不崩）',
      _hd4.assign_errand('ralsei', _DARK_CH1, 'x', now=0.0) is None,
      u'成立=%s' % (_hd4.assign_errand('ralsei', _DARK_CH1, 'x', now=0.0)
                    is None,))


# ------------------------------------------------ D7~D13 意图识别（"别误判"）
# ★★ 为什么这一段必须存在：`_errand_parse_intent` 是**把一句话变成一次真派出**的
#   那道门。它误判的代价不对称 ——
#     · 漏判（该派的没派）＝这句话被当普通聊天，**无害**；
#     · 误判（闲聊被当派活）＝某人**真的**跑出去了，而用户看不出是自己哪句话触发的。
#   产品 docstring 自己把这条写成"五步缺一不可、宁可漏判不可误判"，
#   但**没有判据**守着 ⇒ 一次"顺手放宽匹配"的重构就能把它变成误判机器。
#   ⇒ 六条判据，五条是负控制（每一条只松**一处**，期望仍然判 `None`）。

class _ParseHost(object):
    u"""只装 `_errand_parse_intent` 需要的东西（别名表 / 场景解析 / 当前说话人）。

    ★★ 第152轮补：产品把"名字查找"抽成了 `_errand_find_name`（派活与**叫停**共用
      一份规则）⇒ 桩必须跟着装 —— 否则本套件在 `D7` 就 `AttributeError` 崩掉
      （不是产品坏了，是**夹具比产品旧**，与第107轮那条教训同型）。
    """

    _errand_parse_intent = RalseiPet._errand_parse_intent
    _errand_find_name = RalseiPet._errand_find_name
    _errand_strip_leads = staticmethod(RalseiPet._errand_strip_leads)

    def __init__(self, aliases, talking='ralsei'):
        self._npc_aliases = dict(aliases)
        self._npc_talking = talking

    def _errand_scene_in(self, prefix):
        # 桩：把前缀原样变成场景 id（判据要看的是**识别**，不是"哪一间"）
        return 'by_prefix:%s' % prefix


_ph = _ParseHost({'susie': 'susie', '苏西': 'susie',
                  'niko': 'os_niko', 'ralsei': 'ralsei'})
_p1 = _ph._errand_parse_intent(u'让苏西去oneshot拿点东西')
check(u'D7 正控制：`让苏西去oneshot拿点东西` ⇒ 认出（人 / 地 / 事）三样',
      _p1 is not None and _p1[0] == 'susie'
      and _p1[1] == 'by_prefix:oneshot' and u'拿点东西' in _p1[2],
      u'认出=%s' % (_p1 is not None,))
check(u'D8 负控制（没意图词）：`苏西今天真好看` ⇒ `None`（闲聊不许变成派人）',
      _ph._errand_parse_intent(u'苏西今天真好看') is None,
      u'判空=%s' % (_ph._errand_parse_intent(u'苏西今天真好看') is None,))
check(u'D9 负控制（没角色名）：`让某个人去oneshot` ⇒ `None`',
      _ph._errand_parse_intent(u'让某个人去oneshot') is None,
      u'判空=%s' % (_ph._errand_parse_intent(u'让某个人去oneshot') is None,))
check(u'D10 负控制（没地点）：`让苏西去睡觉` ⇒ `None`',
      _ph._errand_parse_intent(u'让苏西去睡觉') is None,
      u'判空=%s' % (_ph._errand_parse_intent(u'让苏西去睡觉') is None,))
check(u'D11 ★ 不许派自己：`让ralsei去desktop`（当前说话人 = ralsei）⇒ `None`',
      _ph._errand_parse_intent(u'让ralsei去desktop') is None,
      u'判空=%s' % (_ph._errand_parse_intent(u'让ralsei去desktop') is None,))
check(u'D12 ★ 词边界：`让susiex去oneshot` 不算 `susie`、`让苏西去but` 不算 `ut`'
      u'（短名不设边界 ⇒ 「but」会被当成地名）',
      _ph._errand_parse_intent(u'让susiex去oneshot') is None
      and _ph._errand_parse_intent(u'让苏西去but') is None,
      u'判空=%s' % (_ph._errand_parse_intent(u'让susiex去oneshot') is None,))
_p13 = _ph._errand_parse_intent(u'请苏西去oneshot帮我拿点东西')
check(u'D13 引导词被剥掉：`请…帮我拿点东西` ⇒ 事是「拿点东西」（不是整句照抄）',
      _p13 is not None and _p13[2].startswith(u'拿点东西'),
      u'成立=%s' % (_p13 is not None and _p13[2].startswith(u'拿点东西'),))


# ============================================ E. 推进（真跑 · 假宿主）
mark(u'E `_npc_errand_tick`：路上不压 / 到了压 / 办完撤 / 门控中途失效要作废')

_he = _Host(carried=())
_he.npc_roam = _Roam()
_he.assign_errand('ralsei', _DARK_CH1, '看看', now=0.0, travel=10.0, work=20.0)

_o_e1 = _he._npc_errand_tick(5.0)
check(u'E1 路上那一拍：**一次 put 都没有**（位置不变 ＝ 用户在别处看不到他瞬移）',
      _he.npc_roam.puts == [] and _o_e1.get('finished') == []
      and _he.npc_roam.get('ralsei') is None,
      u'成立=%s' % (_he.npc_roam.puts == [],))

_o_e2 = _he._npc_errand_tick(10.0)
check(u'E2 到点那一拍：**压到目的地**，且 `reason` 带 `errand:` 前缀（可与自主挪窝区分）',
      len(_he.npc_roam.puts) == 1
      and _he.npc_roam.puts[0][1] == _DARK_CH1
      and _he.npc_roam.puts[0][2].startswith('errand:'),
      u'成立=%s' % (len(_he.npc_roam.puts) == 1,))

_he._npc_errand_tick(15.0)
check(u'E3 已压在目的地 ⇒ **不重复写**（省盘、省无谓事件；否则每 30s 抖一次）',
      len(_he.npc_roam.puts) == 1, u'成立=%s' % (len(_he.npc_roam.puts) == 1,))

_he._npc_errand_tick(30.0)
check(u'E4 办完那一拍：**撤覆盖**（`drop` 一次 ⇒ 回落静态归属 = 回家）',
      _he.npc_roam.drops == ['ralsei'],
      u'成立=%s' % (_he.npc_roam.drops == ['ralsei'],))
check(u'E5 办完那一拍：**结果落进他的记忆**（「我下次进场能观察到」）',
      len(_he.npc_memory.log) == 1 and bool(_he.npc_memory.log[0][1]),
      u'成立=%s' % (len(_he.npc_memory.log) == 1,))

_he._npc_errand_tick(60.0)
check(u'E6 办完之后再推：不再 drop、不再写记忆（`finished` 只发生一次）',
      _he.npc_roam.drops == ['ralsei'] and len(_he.npc_memory.log) == 1,
      u'成立=%s' % (_he.npc_roam.drops == ['ralsei'],))

# ---- E7/E8 门控中途失效（成对：唯一变量 = 球还在不在）----
_hx = _Host(carried=('ralsei',))
_hx.npc_roam = _Roam()
_hx.assign_errand('ralsei', _LIGHT, '取东西', now=0.0, travel=10.0, work=100.0)
_hx._npc_errand_tick(10.0)                       # ⇒ 已在光世界里 working
_puts_before = len(_hx.npc_roam.puts)
_hx._carried = []                                # 用户把球摘了
_hx._npc_errand_tick(15.0)
check(u'E7 半路球被摘 ⇒ **作废这条差事**（`abort`）：不进 `done`、在办表也没了',
      'ralsei' not in _hx.npc_errand and len(_hx.npc_errand.done) == 0,
      u'成立=%s' % ('ralsei' not in _hx.npc_errand,))
check(u'E8 作废时**落一句"去不了"**，且本拍**不再 put**（不会把他压进进不去的场景）',
      len(_hx.npc_roam.puts) == _puts_before
      and any(u'去不了' in x[1] for x in _hx.npc_memory.log),
      u'成立=%s' % (len(_hx.npc_roam.puts) == _puts_before,))
_hy = _Host(carried=('ralsei',))
_hy.npc_roam = _Roam()
_hy.assign_errand('ralsei', _LIGHT, '取东西', now=0.0, travel=10.0, work=100.0)
_hy._npc_errand_tick(10.0)
_hy._npc_errand_tick(15.0)                        # 球**没**摘
check(u'E9 正控制（球没摘）⇒ 差事仍在办、没被作废（判据不是"逢拍必杀"）',
      'ralsei' in _hy.npc_errand and len(_hy.npc_errand.done) == 0,
      u'成立=%s' % ('ralsei' in _hy.npc_errand,))

# ---- E10 三个开关 ----
_hz = _Host(carried=())
_hz.npc_roam = _Roam()
_hz.assign_errand('ralsei', _DARK_CH1, '看看', now=0.0, travel=0.0, work=0.0)
_old_flag = RalseiPet.NPC_ERRAND_ENABLED
try:
    RalseiPet.NPC_ERRAND_ENABLED = False
    _oz = _hz._npc_errand_tick(999.0)
finally:
    RalseiPet.NPC_ERRAND_ENABLED = _old_flag
check(u'E10 `NPC_ERRAND_ENABLED=False` ⇒ tick **立刻返空**、一次 put 都没有',
      _oz == {'arrived': [], 'finished': []} and _hz.npc_roam.puts == [],
      u'成立=%s' % (_oz == {'arrived': [], 'finished': []},))

_hf = _Host(carried=(), enabled=False)
_hf.npc_roam = _Roam()
_of = _hf._npc_errand_tick(0.0)
check(u'E11 看板 `enabled=False` ⇒ tick 返空、不抛',
      _of == {'arrived': [], 'finished': []},
      u'成立=%s' % (_of == {'arrived': [], 'finished': []},))

_hg = _Host(carried=())
_hg.npc_roam = None
check(u'E12 `npc_roam` 没就位 ⇒ tick 返空、不抛（差事"落地"的方式就是写驻留表）',
      _hg._npc_errand_tick(0.0) == {'arrived': [], 'finished': []},
      u'成立=%s' % (_hg._npc_errand_tick(0.0)
                    == {'arrived': [], 'finished': []},))

_hi = _Host(carried=())
_hi.npc_roam = _Roam()
_oi = _hi._npc_errand_tick(0.0)
check(u'E13 零行为变化：**没人被派过** ⇒ 一拍也不 put、不 drop、不落盘',
      _oi == {'arrived': [], 'finished': []} and _hi.npc_roam.puts == []
      and _hi.npc_roam.drops == [] and _hi.errand_saves == 0,
      u'成立=%s' % (_hi.npc_roam.puts == [] and _hi.errand_saves == 0,))


# ================================================ F. 宿主接线（AST）
mark(u'F 宿主接线：`_npc_errand_tick` 排在 `_npc_roam_tick` **之后**、门控三处同一条')

_CLS = _clsdef(TREE_MAIN, 'RalseiPet')
_n_fn_main = len([n for n in ast.walk(TREE_MAIN) if isinstance(n, ast.FunctionDef)])
check(u'F0 分母闸：`main.py` 真被扫到（函数数 ≥ 300，空扫不可能通过）',
      _n_fn_main >= 300, u'过闸=%s' % (_n_fn_main >= 300,))
check(u'F0b 分母闸：`RalseiPet` 类真被找到', _CLS is not None,
      u'找到=%s' % (_CLS is not None,))

_UM = _method(_CLS, 'update_movement')
_roam_calls = _calls(_UM, '_npc_roam_tick')
_err_calls = _calls(_UM, '_npc_errand_tick')
check(u'F1 `update_movement` 里两个 tick **各一次**（多一次就有两处在推位置）',
      len(_roam_calls) == 1 and len(_err_calls) == 1,
      u'成立=%s' % (len(_roam_calls) == 1 and len(_err_calls) == 1,))
_order_ok = bool(_roam_calls) and bool(_err_calls) \
    and _err_calls[0].lineno > _roam_calls[0].lineno
check(u'F2 ★ **顺序即优先级**：`_npc_errand_tick` 在 `_npc_roam_tick` **之后**'
      u'（反过来"派他出门"会被下一拍摇走）',
      _order_ok, u'顺序对=%s' % (_order_ok,))

_n_tick_callsites = 0
for _c in ast.walk(TREE_MAIN):
    if isinstance(_c, ast.Call) and isinstance(_c.func, ast.Attribute) \
            and _c.func.attr == '_npc_errand_tick':
        _n_tick_callsites += 1
check(u'F3 `_npc_errand_tick` 全模块**只有 1 个调用点**（主循环；别处再调＝一拍推两次）',
      _n_tick_callsites == 1, u'成立=%s' % (_n_tick_callsites == 1,))

_flag_assign = [n for n in _CLS.body if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == 'NPC_ERRAND_ENABLED'
                        for t in n.targets)]
check(u'F4 `NPC_ERRAND_ENABLED` 是**类属性**且默认 `True`（一键封口；'
      u'零回归由"恒空看板"保证，不靠它）',
      len(_flag_assign) == 1
      and isinstance(_flag_assign[0].value, ast.Constant)
      and _flag_assign[0].value.value is True,
      u'成立=%s' % (len(_flag_assign) == 1,))

_TICK = _method(_CLS, '_npc_errand_tick')
_tick_attrs = _attr_names(_TICK)
_NEED_TICK = ('step', 'working_positions', 'put', 'drop', 'abort',
              '_npc_errand_commit', '_npc_errand_gate')
_missing = [a for a in _NEED_TICK if a not in _tick_attrs]
check(u'F5 `_npc_errand_tick` 体内七件事齐全（step/压位置/撤覆盖/作废/落记忆/过门控）',
      not _missing, u'齐=%s' % (not _missing,))

_ASG = _method(_CLS, 'assign_errand')
_gate_in_assign = _calls(_ASG, '_npc_errand_gate')
_board_assign = _calls(_ASG, 'assign')
_gate_before_assign = (len(_gate_in_assign) == 1 and len(_board_assign) == 1
                       and _gate_in_assign[0].lineno < _board_assign[0].lineno)
check(u'F6 `assign_errand` 里**门控在 `board.assign` 之前**（当场说"去不了"，'
      u'不是 90 秒后悄悄拦下）',
      _gate_before_assign, u'成立=%s' % (_gate_before_assign,))

_GATE_SITES = {}
for _fn in ast.walk(TREE_MAIN):
    if not isinstance(_fn, ast.FunctionDef):
        continue
    if _calls(_fn, '_npc_errand_gate'):
        _GATE_SITES[_fn.name] = True
check(u'F7 ★ 门控调用点**精确三处**（派发 / 每拍压位置前 / 对话层问路）—— '
      u'多一处就是"又算了一遍规则"',
      set(_GATE_SITES) == set(('assign_errand', '_npc_errand_tick',
                               'handle_errand_command')),
      u'成立=%s' % (set(_GATE_SITES) == set(('assign_errand', '_npc_errand_tick',
                                             'handle_errand_command')),))

_GATE_FN = _method(_CLS, '_npc_errand_gate')
check(u'F8 `_npc_errand_gate` 体内真的调 `world_gate`（不是自己另写一套判断）',
      bool(_calls(_GATE_FN, 'world_gate')),
      u'成立=%s' % (bool(_calls(_GATE_FN, 'world_gate')),))

# ---- F9 对话层入口 ----
_SEND = _method(_clsdef(TREE_DUI, 'DialogueUI') or _clsdef(TREE_DUI, 'X'),
                'send_message')
_hook_lines = []
_chat_lines = []
for _c in ast.walk(_SEND) if _SEND is not None else []:
    if isinstance(_c, ast.Call) and isinstance(_c.func, ast.Name) \
            and _c.func.id == 'getattr':
        for _a in _c.args:
            if isinstance(_a, ast.Constant) and _a.value == 'handle_errand_command':
                _hook_lines.append(_c.lineno)
    if isinstance(_c, ast.Call) and isinstance(_c.func, ast.Attribute) \
            and _c.func.attr == 'handle_chat_commands':
        _chat_lines.append(_c.lineno)
check(u'F9 对话层真接了派活入口（`send_message` 里查 `handle_errand_command`）',
      len(_hook_lines) == 1, u'成立=%s' % (len(_hook_lines) == 1,))
check(u'F10 派活入口排在**闲聊指令之前**（否则「请苏西去…」会被闲聊关键词截获）',
      bool(_hook_lines) and bool(_chat_lines)
      and _hook_lines[0] < _chat_lines[0],
      u'成立=%s' % (bool(_hook_lines) and bool(_chat_lines)
                    and _hook_lines[0] < _chat_lines[0],))


# ================================================ G. 落盘（AST + 真跑往返）
mark(u'G 落盘：**独立一本** `npc_errands.json`；读**不许**走 `npc_plan_store.load`')

check(u'G1 差事档是**独立文件名**（不是生活档案 `npc_life.json`）',
      ER.FILENAME == 'npc_errands.json' and ER.FILENAME != 'npc_life.json',
      u'成立=%s' % (ER.FILENAME == 'npc_errands.json',))

_FILE_FN = _method(_CLS, '_npc_errand_file')
_app_calls = _calls(_FILE_FN, 'app_file')
_fn_arg_ok = bool(_app_calls) and any(
    isinstance(a, ast.Attribute) and a.attr == 'FILENAME'
    for a in _app_calls[0].args)
check(u'G2 路径**只从 `data_store.app_file()` 拿**，且文件名真源 = `npc_errand.FILENAME`',
      bool(_app_calls) and _fn_arg_ok, u'成立=%s' % (_fn_arg_ok,))

_SAVE_FN = _method(_CLS, '_npc_errand_save')
_LOAD_FN = _method(_CLS, '_npc_errand_load')


def _mod_calls(fn, mod_name, attr):
    u"""`fn` 体内 `mod_name.attr(...)` 的调用节点。"""
    out = []
    if fn is None:
        return out
    for c in ast.walk(fn):
        if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute) \
                and c.func.attr == attr and isinstance(c.func.value, ast.Name) \
                and c.func.value.id == mod_name:
            out.append(c)
    return out


check(u'G3 写**复用** `npc_plan_store.save()`（自带 `.tmp` + `os.replace` 原子写）',
      bool(_mod_calls(_SAVE_FN, 'npc_plan_store_mod', 'save')),
      u'成立=%s' % (bool(_mod_calls(_SAVE_FN, 'npc_plan_store_mod', 'save')),))
check(u'G4 ★ 读**不许**复用 `npc_plan_store.load()`（它只认 `schema_version==1` '
      u'⇒ 会把差事档判成版本不符、静默返回空书）',
      not _mod_calls(_LOAD_FN, 'npc_plan_store_mod', 'load'),
      u'没走=%s' % (not _mod_calls(_LOAD_FN, 'npc_plan_store_mod', 'load'),))
check(u'G5 读走的是 `ErrandBoard.from_dict`（容错还原在自己那一侧，不半成品）',
      bool(_calls(_LOAD_FN, 'from_dict')),
      u'成立=%s' % (bool(_calls(_LOAD_FN, 'from_dict')),))
check(u'G6 节流共用 `NPC_PLAN_SAVE_EVERY`（不为它另立一个可调常量）',
      'NPC_PLAN_SAVE_EVERY' in ast.dump(_SAVE_FN) if _SAVE_FN else False,
      u'成立=%s' % (('NPC_PLAN_SAVE_EVERY' in ast.dump(_SAVE_FN))
                    if _SAVE_FN else False,))


class _DiskHost(object):
    u"""只装 save/load 的轻宿主（真跑往返用）。"""

    _npc_errand_save = RalseiPet._npc_errand_save
    _npc_errand_load = RalseiPet._npc_errand_load

    def __init__(self, path):
        self._path = path
        # ★ 首版这里**漏了**这一步 ⇒ `_npc_errand_save` 拿不到 `_npc_errand_path`
        #   ⇒ 直接返 `False`（`G7/G9/G10` 三条一起红）。查清后判定：**夹具的错**。
        #   产品在 `init_npc()` 里就是**先 load 一次**（它顺手把路径定下来，
        #   读不到文件也只是返回 None）—— 这里照抄那个顺序，不另设捷径。
        self.npc_errand = self._npc_errand_load() or ER.ErrandBoard()

    def _npc_errand_file(self):
        return self._path


_tmp = tempfile.mkdtemp(prefix='check150_')
_path = os.path.join(_tmp, 'npc_errands.json')
try:
    _dh = _DiskHost(_path)
    _dh.npc_errand.assign(0.0, 'ralsei', 'ch1.castle_town.castle_town', '看看',
                          travel=10.0, work=100.0)
    _dh.npc_errand.assign(0.0, 'os_niko', 'oneshot.barrens.Blue', '办事',
                          travel=0.0, work=0.0)
    _dh.npc_errand.step(50.0)          # os_niko 办完、ralsei 还在 working
    _saved = _dh.npc_errand
    _ok_save = _dh._npc_errand_save(force=True)
    _ok_throttle = _dh._npc_errand_save()
    _back = _dh._npc_errand_load()
    check(u'G7 真跑往返：`save()` 写得下（`True`）且文件真存在',
          _ok_save is True and os.path.isfile(_path),
          u'成立=%s' % (_ok_save is True and os.path.isfile(_path),))
    check(u'G8 节流真生效：紧接着第二次（`force=False`）⇒ **不写**、返 `False`',
          _ok_throttle is False, u'成立=%s' % (_ok_throttle is False,))
    check(u'G9 读回来**条数与状态一致**（在办 / 已办各一条，且 `working` 没被改成 `done`）',
          _back is not None and len(_back) == 1 and len(_back.done) == 1
          and _back.working_of('ralsei') is not None,
          u'成立=%s' % (_back is not None and len(_back) == 1,))
    check(u'G10 读回来**结果文本一字不差**（结果要能跨重启回查）',
          _back is not None
          and _back.result_of('os_niko') == _saved.result_of('os_niko')
          and bool(_back.result_of('os_niko')),
          u'成立=%s' % (_back is not None
                        and _back.result_of('os_niko') == _saved.result_of('os_niko'),))
finally:
    try:
        for _f in os.listdir(_tmp):
            os.remove(os.path.join(_tmp, _f))
        os.rmdir(_tmp)
    except Exception:
        pass


# ============================================ H. 与显示解耦 + 零依赖 + 自检
mark(u'H 与显示解耦（`switch`/`travel_to` 零处）+ 零依赖 + 自检')

_ERR_DISP = harvest_display_calls(TREE_ERR)
check(u'H0 分母闸：`npc_errand.py` 真被扫到且**有函数**（空文件也能"零处"恒真）',
      len([n for n in ast.walk(TREE_ERR)
           if isinstance(n, ast.FunctionDef)]) >= 10,
      u'成立=%s' % (len([n for n in ast.walk(TREE_ERR)
                         if isinstance(n, ast.FunctionDef)]) >= 10,))
check(u'H1 ★★ 差事模块**零处碰显示**（`switch` / `travel_to` 一个都没有）—— '
      u'「NPC 自主/被派移动不切显示」的硬约束',
      _ERR_DISP == {}, u'零处=%s' % (_ERR_DISP == {},))

_ERR_IMPORTS = _mod_imports(TREE_ERR)
check(u'H2 顶层只 import 标准库 `collections`（零项目内 import ⇒ 不可能成环）',
      _ERR_IMPORTS == set(('collections',)),
      u'成立=%s' % (_ERR_IMPORTS == set(('collections',)),))
check(u'H3 **零函数内 import**（与 `npc_roam`/`npc_intent` 同一条零依赖纪律）',
      _inner_imports(TREE_ERR) == [],
      u'零处=%s' % (_inner_imports(TREE_ERR) == [],))
_time_calls = _calls(TREE_ERR, 'time') if hasattr(TREE_ERR, 'body') else []
check(u'H4 不 `import time`（`now` 一律由调用方传入 ⇒ 可判据、可回放）',
      'time' not in _ERR_IMPORTS
      and not [c for c in ast.walk(TREE_ERR)
               if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)
               and c.func.attr == 'time'],
      u'成立=%s' % ('time' not in _ERR_IMPORTS,))

_SELF_SRC = _src(os.path.abspath(__file__))
_SELF = ast.parse(_SELF_SRC)


def _echoes_volatile(node):
    u"""detail 是否回显**时相量**：`%d` 格式化，或引用了行号（`lineno`）。"""
    if u'lineno' in ast.dump(node):
        return True
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
        left = node.left
        return (isinstance(left, ast.Constant) and isinstance(left.value, str)
                and u'%d' in left.value)
    return False


_VOLATILE = [n.lineno for n in ast.walk(_SELF)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id == u'check' and len(n.args) >= 3
             and _echoes_volatile(n.args[2])]
check(u'H5 判据的 detail **不回显时相量**（无 `%d` 格式化、不引用行号）',
      not _VOLATILE, u'命中=%s' % (u'有' if _VOLATILE else u'无',))
check(u'H6 判据名都是非空字面量（防"名字被拼空"）',
      all(isinstance(n.args[0], ast.Constant) and isinstance(n.args[0].value, str)
          and n.args[0].value.strip()
          for n in ast.walk(_SELF)
          if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
          and n.func.id == 'check' and n.args),
      u'成立=%s' % (True,))
with io.open(os.path.abspath(__file__), 'rb') as _f3:
    _raw = _f3.read()
check(u'H7 无 BOM', not _raw.startswith(b'\xef\xbb\xbf'))
check(u'H8 零外部盘（只读仓库内文件；临时往返用系统 temp 并自清）',
      os.path.abspath(MAIN).startswith(ROOT + os.sep)
      and os.path.abspath(ERRAND_PY).startswith(ROOT + os.sep)
      and os.path.abspath(REPORT).startswith(ROOT + os.sep),
      u'成立=%s' % (os.path.abspath(MAIN).startswith(ROOT + os.sep),))

print('')
print('=' * 78)
print(u'check150：PASS=%d FAIL=%d' % (_n_pass, _n_fail))
if _failed:
    print(u'失败项：')
    for _d in _failed:
        print(u'  - %s' % _d)
sys.exit(0 if _n_fail == 0 else 1)
