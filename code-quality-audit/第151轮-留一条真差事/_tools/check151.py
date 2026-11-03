# -*- coding: utf-8 -*-
u"""第151轮回归锁：**开机示范差事** —— 一条"留给他去做"的真差事。

## 为什么要这个口子（用户口径逐字）

> 「**先留一个差事确保他们能做出来再说吧**」

上一轮（150）把差事整条链接进来了，但产品的默认行为是 **"没人派就恒空"** ——
这既是零回归的保证，也意味着**开箱看不到任何东西**。
本轮补的就是这个落差：给一处**可开的口子**（填一行就开机派一条），
让"他们真能办出来"变成**一眼能看见、且可复现**的事。

## 这一次**不改**什么（重要）

用户这句里没有要"取消入口"——那是第150轮报告 §6 遗留 3。
本轮**只加种子，不加新交互**：`NPC_ERRAND_DEMO` 是**配置**，不是 UI，也不是指令。

## 本套件守什么

| 段 | 守什么 |
|---|---|
| A | 口子本身（**真跑**）：默认不派 / **文档里那个例子真派得出** / 看板非空不重派 / **门控照样拦**（示范差事不是特权）/ 配置不合法不抛 / 三种"没就位"都不派 / **整条链路真能办到 done 并产出结果** |
| B | 接线（AST）：方法在、`init_npc_systems` 里**恰好一次**调用、**排在依赖之后**、体内**只走 `assign_errand`**、类属性默认 `None` |
| C | 零回归：默认配置下看板恒空、记忆恒空；体内**没有**绕过门控的 `board.assign(` |
| D | 自检：判据名非空字面量 / 无 BOM / 零外部盘 / **detail 不回显时相量** |

★ 判据纪律：`print('[PASS] %s')` 字面量；断行为不断赋值；正/负控制成对；
  A/C 走**真跑**（产品那几个真函数挂在轻宿主上），B 走 **AST**；
  零网络 / 零 UI / 不需要显示器 / 零外部盘。
"""
import ast
import io
import os
import re
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')
MAIN = os.path.join(PKG, 'src', 'main.py')
REPORT = os.path.join(ROUND, 'report151.md')

for _p in (PKG, os.path.join(PKG, 'src'), os.path.join(PKG, 'modules')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from main import RalseiPet                                  # noqa: E402
from modules import npc_errand as ER                        # noqa: E402
from modules import npc_system as NS                        # noqa: E402

with io.open(MAIN, 'r', encoding='utf-8', newline='') as _fh:
    SRC = _fh.read()
TREE = ast.parse(SRC)

_n_pass = 0
_n_fail = 0
_failed = []
_marks = 0


def check(desc, cond, detail=''):
    global _n_pass, _n_fail
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
    out = []
    if fn is None:
        return out
    for c in ast.walk(fn):
        if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute) \
                and c.func.attr == attr:
            out.append(c)
    return out


class _Mem(object):
    def __init__(self):
        self.log = []

    def remember(self, nid, text, who=None):
        self.log.append((nid, text, who))

    def save(self, nid):
        pass


class _Cur(object):
    def __init__(self, scene):
        self.scene = scene


class _Roam(object):
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
    u"""轻宿主：把**产品里那几个真函数**挂上来跑（不启 Qt）。

    ⚠️ `_npc_errand_world_uncached` 在产品里是 `@staticmethod`：从类上取下来是
      **裸函数**，挂到**实例**上才不会多绑一个 `self`（挂类上会被当实例方法）。
    """

    _npc_errand_world = RalseiPet._npc_errand_world
    _npc_errand_gate = RalseiPet._npc_errand_gate
    _npc_errand_note = RalseiPet._npc_errand_note
    _npc_errand_demo = RalseiPet._npc_errand_demo
    _npc_errand_tick = RalseiPet._npc_errand_tick
    _npc_errand_commit = RalseiPet._npc_errand_commit

    def _errand_report_ack(self, *a, **kw):
        # ★ 第153轮：产品在 tick 的 finished 分支里新调了它。
        #   桩必须跟着装 —— 否则 AttributeError 会被 tick 的
        #   `except` 吞掉，症状不是报错，而是“finished 那一段整段没执行”。
        #   看台词的地方在第153轮 `check153`。
        return None
    assign_errand = RalseiPet.assign_errand

    def __init__(self, enabled=True, roam=None):
        self._npc_errand_world_uncached = RalseiPet._npc_errand_world_uncached
        self.npc_registry = NS.load_registry()
        self.npc_errand = ER.ErrandBoard(enabled=enabled)
        self.npc_memory = _Mem()
        self.npc_roam = roam
        self.seeded = 0

    def _npc_carried_ids(self):
        return []

    def _npc_scene_id(self):
        return 'desktop'

    def _npc_seed_bodies(self, scene_id=None):
        self.seeded += 1

    def _npc_plan_save(self, force=False):
        return True

    def _npc_errand_save(self, force=False):
        return True


class _CountHost(_Host):
    u"""数一数"到底有没有真去调 `assign_errand`"。

    ★★ 为什么需要这个：`A9`（看板 `enabled=False`）如果只断"返 None、看板空"，
      它是**恒真**的 —— `ErrandBoard.assign` 自己就会因为 `enabled` 拒绝，
      所以哪怕 demo 根本没做那个判断，结果也一样。
      ⇒ 改成数调用次数：**提前返回**必须是"根本不去问门控"，不是"问了被拒"。
      这是"观察量须由产品代码判"那条铁律的用法。
    """

    def __init__(self, **kw):
        _Host.__init__(self, **kw)
        self.assign_calls = 0

    def assign_errand(self, *a, **k):
        self.assign_calls += 1
        return _Host.assign_errand(self, *a, **k)


_OLD_DEMO = RalseiPet.NPC_ERRAND_DEMO

#: ★★ 文档（类属性注释）里写的那一行例子 —— **从源码注释里解析出来**，不是我另写一份。
#:
#: 为什么非要解析：第 150 轮我吃过"判据自己另写一个样本"的亏（`C4` 拿 `os_niko`
#: 当"进不去暗世界"的样本，而他恰是唯一该放行的）。同一条道理 ——
#: 如果判据里 hardcode 一个"我觉得能用"的元组，那么**文档写成什么样都不会被验到**：
#: 注释改成 `('os_niko', 'desktop', …)`（门控必拒）也照样全绿。
#: ⇒ 判据必须嚼**文档里那一行**，才算"文档与行为同源"。
_DOC_RE = re.compile(r"`\(\s*'([^']+)'\s*,\s*'([^']+)'\s*,\s*'([^']*)'\s*\)`")
_DOC_HIT = _DOC_RE.search(SRC)
_DOC_SPEC = (_DOC_HIT.group(1), _DOC_HIT.group(2), _DOC_HIT.group(3)) \
    if _DOC_HIT else None


# ================================================ A 口子本身（真跑）
mark(u'A 口子本身：默认不派 / 例子真派得出 / 非空不重派 / 门控照样拦 / 能办到 done')

_CLS = _clsdef(TREE, 'RalseiPet')
check(u'A0 分母闸：类属性与方法**都在**（缺一个后面全是空断言）',
      _CLS is not None
      and any(isinstance(n, ast.Assign)
              and any(isinstance(t, ast.Name) and t.id == 'NPC_ERRAND_DEMO'
                      for t in n.targets) for n in (_CLS.body if _CLS else []))
      and _method(_CLS, '_npc_errand_demo') is not None,
      u'成立=%s' % (_CLS is not None,))

check(u'A1 出厂默认 **`None`**（= 不派；零回归靠"恒空看板"这个结构，不靠它）',
      RalseiPet.NPC_ERRAND_DEMO is None,
      u'成立=%s' % (RalseiPet.NPC_ERRAND_DEMO is None,))

_ha = _CountHost()
_e_a = _ha._npc_errand_demo()
check(u'A2 默认配置下：**根本不去调 `assign_errand`**、看板空、记忆空'
      u'（开箱行为与第150轮逐字相同）',
      _e_a is None and _ha.assign_calls == 0 and len(_ha.npc_errand) == 0
      and _ha.npc_memory.log == [],
      u'成立=%s' % (_e_a is None and _ha.assign_calls == 0,))

try:
    check(u'A2b 注释里那行例子是**可被机器解析的三元组**（文档不许写成散文）',
          _DOC_SPEC is not None and len(_DOC_SPEC) == 3,
          u'成立=%s' % (_DOC_SPEC is not None,))
    RalseiPet.NPC_ERRAND_DEMO = _DOC_SPEC
    _hb = _Host()
    _e_b = _hb._npc_errand_demo()
    check(u'A3 ★ **注释里那个例子真能派出去**（写好看但跑不通 = 假文档）',
          _e_b is not None and _e_b.npc_id == _DOC_SPEC[0]
          and _e_b.dest_scene == _DOC_SPEC[1],
          u'派出=%s' % (_e_b is not None,))
    check(u'A4 派出即 `traveling`，时长取默认（90 秒到 / 300 秒办完）',
          _e_b is not None and _e_b.status == ER.TRAVELING
          and int(_e_b.arrive_at - _e_b.start) == int(ER.DEFAULT_TRAVEL_SECONDS)
          and int(_e_b.finish_at - _e_b.arrive_at) == int(ER.DEFAULT_WORK_SECONDS),
          u'成立=%s' % (_e_b is not None and _e_b.status == ER.TRAVELING,))
    _e_b2 = _hb._npc_errand_demo()
    check(u'A5 看板**非空就不重派**（它是种子，不是"每次开机重派一遍"）',
          _e_b2 is None and len(_hb.npc_errand) == 1,
          u'成立=%s' % (_e_b2 is None and len(_hb.npc_errand) == 1,))

    # ---- A6 门控：示范差事**不是特权** ----
    RalseiPet.NPC_ERRAND_DEMO = ('os_niko', 'desktop', u'去看看')
    _hc = _Host()
    _e_c = _hc._npc_errand_demo()
    check(u'A6 ★ 门控该拒的照样拒：`os_niko` 去桌面 ⇒ 派不出、看板空',
          _e_c is None and len(_hc.npc_errand) == 0,
          u'成立=%s' % (_e_c is None and len(_hc.npc_errand) == 0,))
    check(u'A7 被拒时**留了一条"去不了"的记忆**（示范差事也不许静默消失）',
          len(_hc.npc_memory.log) == 1
          and u'去不了' in _hc.npc_memory.log[0][1],
          u'成立=%s' % (len(_hc.npc_memory.log) == 1,))

    # ---- A8 配置不合法 ----
    _BAD_SPECS = ('ralsei', ('ralsei', 'x'), ('a', 'b', 'c', 'd'), 123)
    _bad_res = []
    for _s in _BAD_SPECS:
        RalseiPet.NPC_ERRAND_DEMO = _s
        _hd = _Host()
        _bad_res.append(_hd._npc_errand_demo() is None)
    check(u'A8 配置不合法（字符串 / 两元组 / 四元组 / 整数）⇒ 一律不派、**不抛**',
          all(_bad_res), u'全不派=%s' % (all(_bad_res),))

    # ---- A9 三种"没就位"：必须**提前返回**，不是"问了被拒" ----
    RalseiPet.NPC_ERRAND_DEMO = _DOC_SPEC
    _he = _CountHost(enabled=False)
    _r_off = _he._npc_errand_demo()
    _hf = _CountHost()
    _hf.npc_errand = None
    _r_none = _hf._npc_errand_demo()
    check(u'A9 看板 `enabled=False` / 看板 `None` ⇒ 都不派，且**一次都没去调** '
          u'`assign_errand`（提前返回；靠 `npc_errand` 兜底不算数，那是恒真）',
          _r_off is None and _r_none is None
          and _he.assign_calls == 0 and _hf.assign_calls == 0,
          u'成立=%s' % (_r_off is None and _r_none is None
                        and _he.assign_calls == 0,))

    # ---- A10 整条链路真能办到 done ----
    _hg = _Host(roam=_Roam())
    _e_g = _hg._npc_errand_demo()
    _tick1 = _hg._npc_errand_tick(float(_e_g.arrive_at) - 1.0)
    _put_mid = list(_hg.npc_roam.puts)
    _tick2 = _hg._npc_errand_tick(float(_e_g.arrive_at))
    _put_at = list(_hg.npc_roam.puts)
    _tick3 = _hg._npc_errand_tick(float(_e_g.finish_at))
    check(u'A10 ★ 它能**真的办出来**：路上不压位置 → 到点压在目的地 → 办完撤覆盖',
          _put_mid == [] and len(_put_at) == 1
          and _hg.npc_roam.drops == ['ralsei'],
          u'成立=%s' % (_put_mid == [] and len(_put_at) == 1,))
    check(u'A11 办完产出**结果**并落进他的记忆（「下次进场能观察到」）',
          len(_hg.npc_memory.log) == 1
          and bool(_hg.npc_memory.log[0][1])
          and len(_tick3.get('finished') or ()) == 1,
          u'成立=%s' % (len(_hg.npc_memory.log) == 1,))
    check(u'A12 三个阶段各报一次跃迁（`arrived` 一条、`finished` 一条，不重复）',
          len(_tick2.get('arrived') or ()) == 1
          and len(_tick1.get('arrived') or ()) == 0
          and len(_tick3.get('arrived') or ()) == 0,
          u'成立=%s' % (len(_tick2.get('arrived') or ()) == 1,))
finally:
    RalseiPet.NPC_ERRAND_DEMO = _OLD_DEMO


# ================================================ B 接线（AST）
mark(u'B 接线：方法在、调用恰好一次、排在依赖之后、只走 `assign_errand`')

_INIT = _method(_CLS, 'init_npc_systems')
_DEMO = _method(_CLS, '_npc_errand_demo')
check(u'B0 分母闸：`init_npc_systems` 与 `_npc_errand_demo` 都定位到了',
      _INIT is not None and _DEMO is not None,
      u'成立=%s' % (_INIT is not None and _DEMO is not None,))

_demo_calls = _calls(_INIT, '_npc_errand_demo')
check(u'B1 `init_npc_systems` 里**恰好一次**调 `_npc_errand_demo`',
      len(_demo_calls) == 1, u'成立=%s' % (len(_demo_calls) == 1,))

_seed_calls = _calls(_INIT, '_npc_seed_bodies')
_demo_after_seed = (bool(_seed_calls) and bool(_demo_calls)
                    and _demo_calls[0].lineno > _seed_calls[0].lineno)
check(u'B2 ★ 调用**排在 `_npc_seed_bodies` 之后**（它要用 registry/memory/看板三样，'
      u'挪到前面 ⇒ 拿到 None ⇒ 静默不派）',
      _demo_after_seed, u'顺序对=%s' % (_demo_after_seed,))

check(u'B3 方法体内走的是 **`assign_errand`**（公开入口），不是 `board.assign`',
      bool(_calls(_DEMO, 'assign_errand')) and not _calls(_DEMO, 'assign'),
      u'成立=%s' % (bool(_calls(_DEMO, 'assign_errand'))
                    and not _calls(_DEMO, 'assign'),))

_n_sites = 0
for _c in ast.walk(TREE):
    if isinstance(_c, ast.Call) and isinstance(_c.func, ast.Attribute) \
            and _c.func.attr == '_npc_errand_demo':
        _n_sites += 1
check(u'B4 全模块 `_npc_errand_demo` **只有 1 个调用点**（开机一处；别处再调=重派）',
      _n_sites == 1, u'成立=%s' % (_n_sites == 1,))

_attr_assign = [n for n in _CLS.body if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == 'NPC_ERRAND_DEMO'
                        for t in n.targets)]
check(u'B5 类属性 `NPC_ERRAND_DEMO` 赋值形式是 `= None`（不是 `= ()` 之类看着像空的值）',
      len(_attr_assign) == 1
      and isinstance(_attr_assign[0].value, ast.Constant)
      and _attr_assign[0].value.value is None,
      u'成立=%s' % (len(_attr_assign) == 1,))


# ================================================ C 零回归
mark(u'C 零回归：默认配置下什么都不变')

_hz = _Host(roam=_Roam())
_e_z1 = _hz._npc_errand_demo()
_e_z2 = _hz._npc_errand_demo()
check(u'C1 默认配置调两次：看板恒空、记忆恒空、一次 put 都没有',
      _e_z1 is None and _e_z2 is None and len(_hz.npc_errand) == 0
      and _hz.npc_memory.log == [] and _hz.npc_roam.puts == [],
      u'成立=%s' % (_e_z1 is None and _hz.npc_roam.puts == [],))

check(u'C2 口子**没有**绕过门控的第二条写入口（体内无 `board.assign(` 直调）',
      not _calls(_DEMO, 'assign') and not _calls(_DEMO, 'put'),
      u'成立=%s' % (not _calls(_DEMO, 'assign') and not _calls(_DEMO, 'put'),))

#: ★ 给"我自己那个正则"的闸：它必须抓的是**类属性那一段注释**里那行，
#:   而不是全文件里随手某个三元组（否则以后别处出现 `('a','b','c')` 就被选成样本，
#:   A3 验的就不是这条口子的文档了 —— "判据也是被测物"）。
_ATTR_POS = SRC.find(u'NPC_ERRAND_DEMO = None')
_HIT_POS = _DOC_HIT.start() if _DOC_HIT else -1
check(u'C3 解析到的例子**就在 `NPC_ERRAND_DEMO` 那段注释里**（不是别处抓来的）',
      _ATTR_POS > 0 and 0 < _ATTR_POS - _HIT_POS < 2000,
      u'成立=%s' % (_ATTR_POS > 0 and 0 < _ATTR_POS - _HIT_POS < 2000,))


# ================================================ D 自检
mark(u'D 自检')
_SELF_SRC = io.open(os.path.abspath(__file__), 'r', encoding='utf-8').read()
_SELF = ast.parse(_SELF_SRC)


def _echoes_volatile(node):
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
check(u'D1 判据的 detail **不回显时相量**（无 `%d` 格式化、不引用行号）',
      not _VOLATILE, u'命中=%s' % (u'有' if _VOLATILE else u'无',))
check(u'D2 判据名都是非空字面量（防"名字被拼空"）',
      all(isinstance(n.args[0], ast.Constant) and isinstance(n.args[0].value, str)
          and n.args[0].value.strip()
          for n in ast.walk(_SELF)
          if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
          and n.func.id == 'check' and n.args),
      u'成立=%s' % (True,))
with io.open(os.path.abspath(__file__), 'rb') as _f3:
    _raw = _f3.read()
check(u'D3 无 BOM', not _raw.startswith(b'\xef\xbb\xbf'))
check(u'D4 零外部盘（只读仓库内文件）',
      os.path.abspath(MAIN).startswith(ROOT + os.sep)
      and os.path.abspath(REPORT).startswith(ROOT + os.sep),
      u'成立=%s' % (os.path.abspath(MAIN).startswith(ROOT + os.sep),))

print('')
print('=' * 78)
print(u'check151：PASS=%d FAIL=%d' % (_n_pass, _n_fail))
if _failed:
    print(u'失败项：')
    for _d in _failed:
        print(u'  - %s' % _d)
sys.exit(0 if _n_fail == 0 else 1)
