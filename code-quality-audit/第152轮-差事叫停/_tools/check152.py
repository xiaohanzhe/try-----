# -*- coding: utf-8 -*-
u"""第152轮回归锁：**差事叫停** —— 派得出去，也要**叫得回来**。

## 为什么要这个口子（用户口径逐字）

> 「**按照人类的逻辑来就好**」

人味逻辑 = 派出去 → （随时可以）**叫停** → 他**回来** → 他也记得"我本来要去，
被叫回来了"。第150轮只做了前半段：`board.abort()` 接口在位，但**零接线** ——
一条差事派出去只能等它自己走完。这一轮把后半段接上。

## 头号风险：**叫停句会被派活解析吃成"再派一次"**

「别让苏西去 oneshot 了」这句话里**同时**有：角色名（苏西）、意图词（让）、
地点（oneshot）⇒ `_errand_parse_intent` **原样命中** ⇒ 用户想叫停，
代码却**又派了一次**（`ErrandBoard.assign` 对同一人是"覆盖"，表面上无声无息，
实际把人**重新上路**了）。
⇒ 两条闸：① 取消**先于**派活（`handle_errand_command` 里靠前）；
② 派活侧加**否定句不派**（`ERRAND_NEGATIONS`）—— 连"没在办所以取消不了"
   的那种句子也不会掉进派活里。

## 本套件守什么

| 段 | 守什么 |
|---|---|
| A | **叫停动作**（真跑）：`traveling`/`working` 都能撤 · **作废 ≠ 办完**（无 `result`、不进 `done`、之后也不会凭空产出） · **必须撤位置覆盖**（否则人还站在外面） · 没在办/已办完/关闸 ⇒ 一律 `None` 且零副作用 · 记忆写"未完成" |
| B | **意图解析**（真跑）：点名 / 代词 / 未点名但唯一在办 · **两条在办不猜** · 点名的人没在办就不拦 · 「我回来了」「算了」「取消订阅」**不收** · 空串不炸 |
| C | **顺序与不重复派**：AST 里取消判定在派活**之前**；真跑「别让…去了」有在办 ⇒ 撤且**不新派**；没在办 ⇒ 不拦且**不派**；正常派活仍照常（否定闸没误伤） |
| D | 零回归 / 规则只有一份 / 自检：普通句子恒 `None` · `_errand_find_name` 被派活**共用**（AST）· 判据名非空 · 无 BOM · 零外部盘 · detail 不回显时相量 |

★ 判据纪律：`print('[PASS] %s')` 字面量；断行为不断赋值；正/负控制成对；
  A/B/C 走**真跑**（产品真函数挂轻宿主），C1 与 D2 走 **AST**；
  零网络 / 零 UI / 不需要显示器 / 零外部盘。
"""
import ast
import io
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')
MAIN = os.path.join(PKG, 'src', 'main.py')
REPORT = os.path.join(ROUND, 'report152.md')

for _p in (PKG, os.path.join(PKG, 'src'), os.path.join(PKG, 'modules')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from main import RalseiPet                                  # noqa: E402
from modules import npc_errand as ER                        # noqa: E402
from modules import npc_persona as NP                       # noqa: E402
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

    ⚠️ 两个 ack 是**桩**：真实现会去调模型（`chat_with_ai`），本套件零网络
      ⇒ 换成只记账的桩，并顺手守住"叫停**确实**回了话（走的是 ack 而不是静默）"。
    """

    _errand_find_name = RalseiPet._errand_find_name
    _errand_parse_cancel = RalseiPet._errand_parse_cancel
    _errand_is_negative = RalseiPet._errand_is_negative
    _errand_note = RalseiPet._npc_errand_note
    _npc_errand_note = RalseiPet._npc_errand_note
    _npc_errand_world = RalseiPet._npc_errand_world
    _npc_errand_gate = RalseiPet._npc_errand_gate
    _npc_errand_tick = RalseiPet._npc_errand_tick
    _npc_errand_commit = RalseiPet._npc_errand_commit
    assign_errand = RalseiPet.assign_errand
    cancel_errand = RalseiPet.cancel_errand
    handle_errand_command = RalseiPet.handle_errand_command
    _errand_parse_intent = RalseiPet._errand_parse_intent

    def __init__(self, enabled=True):
        self._npc_errand_world_uncached = RalseiPet._npc_errand_world_uncached
        self.npc_registry = NS.load_registry()
        self._npc_aliases = NP.address_aliases(
            [(n.id, n.name, n.name_cn) for n in self.npc_registry.all()])
        self.npc_errand = ER.ErrandBoard(enabled=enabled)
        self.npc_memory = _Mem()
        self.npc_roam = _Roam()
        self._npc_talking = 'ralsei'
        self.acks = []
        self.cancel_acks = []

    # ---- 宿主环境（真产品里由 QMainWindow / data_store / 场景系统提供）----
    def _npc_carried_ids(self):
        return []

    def _npc_scene_id(self):
        return 'desktop'

    def _npc_seed_bodies(self, scene_id=None):
        pass

    def _npc_plan_save(self, force=False):
        return True

    def _npc_errand_save(self, force=False):
        return True

    def _npc_ai_available(self):
        return True

    def _errand_ack(self, *a):
        self.acks.append(a)

    def _errand_cancel_ack(self, *a):
        self.cancel_acks.append(a)

    # ---- 场景解析：本套件只关心"是不是同一间房"，不关心真场景表 ----
    def _errand_scene_in(self, prefix):
        return {'oneshot': 'oneshot.barrens.Blue',
                'desktop': 'desktop',
                'ut': 'ut.rooms.room_area1'}.get(prefix)

    def _errand_strip_leads(self, t):
        return RalseiPet._errand_strip_leads(self, t)


_CLS = _clsdef(TREE, 'RalseiPet')
_CANCEL = _method(_CLS, 'cancel_errand')
_PCANCEL = _method(_CLS, '_errand_parse_cancel')
_HANDLE = _method(_CLS, 'handle_errand_command')
_PINTENT = _method(_CLS, '_errand_parse_intent')

_DEST = 'oneshot.barrens.Blue'

# ================================================ A 叫停动作（真跑）
mark(u'A 叫停动作：能撤 / 作废≠办完 / 必须撤覆盖 / 该拒的都拒 / 记忆写未完成')

check(u'A0 分母闸：三个方法**都**在（缺一个后面全是空断言）',
      _CANCEL is not None and _PCANCEL is not None and _HANDLE is not None,
      u'成立=%s' % (_CANCEL is not None and _PCANCEL is not None,))

# ---- A1 路上（traveling）也能叫停 ----
_h1 = _Host()
_e1 = _h1.assign_errand('ralsei', _DEST, u'\u53bb\u770b\u770b', now=0.0)
_r1 = _h1.cancel_errand('ralsei')
check(u'A1 `traveling` 也叫得回来：返回被撤的差事、看板清空、位置覆盖撤 1 次',
      _e1 is not None and _r1 is not None and len(_h1.npc_errand) == 0
      and _h1.npc_roam.drops == ['ralsei'],
      u'成立=%s' % (_r1 is not None and len(_h1.npc_errand) == 0,))

# ---- A2 到了之后（working）也叫得回来：位置被压在目的地，必须撤 ----
_h2 = _Host()
_e2 = _h2.assign_errand('ralsei', _DEST, u'\u53bb\u770b\u770b',
                        now=0.0, travel=10.0, work=100.0)
_h2._npc_errand_tick(10.0)                     # 到点 ⇒ working + 压位置
_pressed = (_h2.npc_roam.get('ralsei') is not None
            and _h2.npc_roam.get('ralsei').scene == _DEST)
_r2 = _h2.cancel_errand('ralsei')
_still = _h2.npc_roam.get('ralsei')
check(u'A2 ★ `working` 时叫停：**位置覆盖必须撤**（不撤 ⇒ "叫回来了"却还站在外面）',
      _pressed and _r2 is not None and _still is None
      and _h2.npc_roam.drops == ['ralsei'],
      u'成立=%s' % (_pressed and _still is None,))

# ---- A3 作废 ≠ 办完 ----
_h3 = _Host()
_h3.assign_errand('ralsei', _DEST, u'\u53bb\u770b\u770b',
                  now=0.0, travel=10.0, work=100.0)
_h3._npc_errand_tick(10.0)
_h3.cancel_errand('ralsei')
_out3 = _h3._npc_errand_tick(1000.0)
check(u'A3 ★ **作废不是结果**：没有 `result`、不进 `done`、再推 1000 秒也不会凭空',
      _h3.npc_errand.result_of('ralsei') == ''
      and len(_h3.npc_errand.done) == 0
      and not (_out3.get('finished') or ()),
      u'成立=%s' % (_h3.npc_errand.result_of('ralsei') == '',))
check(u'A3b 作废后记忆里**没有**"办完了"那种句式（只有"被叫回来"）',
      len(_h3.npc_memory.log) == 1
      and u'\u53eb\u56de\u6765' in _h3.npc_memory.log[0][1]
      and u'\u529e\u5b8c\u4e86' not in _h3.npc_memory.log[0][1],
      u'成立=%s' % (len(_h3.npc_memory.log) == 1,))

# ---- A4 没在办 ⇒ None（且零副作用）----
_h4 = _Host()
_r4 = _h4.cancel_errand('susie')
check(u'A4 他本来就没在办 ⇒ `None`，看板空、零 drop、记忆不多一条',
      _r4 is None and len(_h4.npc_errand) == 0
      and _h4.npc_roam.drops == [] and _h4.npc_memory.log == [],
      u'成立=%s' % (_r4 is None,))

# ---- A5 已经办完的撤不回来（结果不许被抹掉）----
_h5 = _Host()
_h5.assign_errand('ralsei', _DEST, u'\u53bb\u770b\u770b', now=0.0, travel=0.0, work=0.0)
_h5._npc_errand_tick(0.0)                      # 一拍走完 ⇒ done
_done5 = _h5.npc_errand.result_of('ralsei')
_r5 = _h5.cancel_errand('ralsei')
check(u'A5 已经办完的**撤不回来**（`None`），且那条结果**仍在**（不许被叫停抹掉）',
      bool(_done5) and _r5 is None and _h5.npc_errand.result_of('ralsei') == _done5,
      u'成立=%s' % (bool(_done5) and _r5 is None,))

# ---- A6 / A7 关闸 / 看板没就位 ----
#   ★★ A6 必须**派出去之后再关闸**：若从头就 `enabled=False`，看板本来就是空的，
#      "拒绝"与"没得拒"长得一模一样（恒真的老坑）。先派、再关、再叫停 ⇒
#      才能分辨"是闸拦住了"还是"根本没东西可撤"。
_h6 = _Host()
_h6.assign_errand('ralsei', _DEST, u'\u53bb\u770b\u770b', now=0.0)
_h6.npc_roam.put('ralsei', _DEST, 0.0, 'errand')
_h6.npc_errand.enabled = False
_r6 = _h6.cancel_errand('ralsei')
check(u'A6 关闸之后不许再动：`None`、**零 drop**、那条差事**还在**（关闸不是"顺手清空"）',
      _r6 is None and _h6.npc_roam.drops == [] and len(_h6.npc_errand) == 1,
      u'成立=%s' % (_r6 is None and _h6.npc_roam.drops == [],))
_h7 = _Host()
_h7.npc_errand = None
_r7 = _h7.cancel_errand('ralsei')
check(u'A7 看板 `None` ⇒ `None`（不炸）', _r7 is None,
      u'成立=%s' % (_r7 is None,))

# ---- A8 drop 只发生一次（别"撤两遍"）----
_h8 = _Host()
_h8.assign_errand('ralsei', _DEST, u'\u53bb\u770b\u770b', now=0.0)
_h8.cancel_errand('ralsei')
_h8.cancel_errand('ralsei')                    # 第二次没在办 ⇒ 不该再 drop
check(u'A8 连叫两次：`drop` 恰好 1 次（第二次没在办，不做无谓动作）',
      _h8.npc_roam.drops == ['ralsei'],
      u'成立=%s' % (_h8.npc_roam.drops == ['ralsei'],))

# ---- A9 记忆内容 ----
_h9 = _Host()
_h9.assign_errand('ralsei', _DEST, u'\u53bb\u770b\u770b', now=0.0)
_h9.cancel_errand('ralsei', reason=u'\u7528\u6237\u53eb\u505c')
_t9 = _h9.npc_memory.log[0][1] if _h9.npc_memory.log else u''
check(u'A9 记忆写明**去哪、办什么、没办完就被叫回来**（"办不成也是一种结果"）',
      len(_h9.npc_memory.log) == 1 and _DEST in _t9
      and u'\u53bb\u770b\u770b' in _t9 and u'\u53eb\u56de\u6765' in _t9,
      u'成立=%s' % (len(_h9.npc_memory.log) == 1,))
check(u'A9b 记忆记在**他自己**头上（`who=npc_id`），不是记在发起者头上',
      bool(_h9.npc_memory.log) and _h9.npc_memory.log[0][0] == 'ralsei'
      and _h9.npc_memory.log[0][2] == 'ralsei',
      u'成立=%s' % (bool(_h9.npc_memory.log)
                    and _h9.npc_memory.log[0][0] == 'ralsei',))

# ---- A10 叫停之后他会回落静态归属（= 回家）+ 能再被派 ----
_h10 = _Host()
_h10.assign_errand('ralsei', _DEST, u'\u53bb\u770b\u770b', now=0.0)
_h10._npc_errand_tick(0.0)
_h10.cancel_errand('ralsei')
_e10 = _h10.assign_errand('ralsei', _DEST, u'\u518d\u53bb\u4e00\u6b21', now=50.0)
check(u'A10 叫停不是"这个人废了"：他**能再被派**（看板重新有 1 条）',
      _e10 is not None and len(_h10.npc_errand) == 1,
      u'成立=%s' % (_e10 is not None and len(_h10.npc_errand) == 1,))

# ================================================ B 意图解析（真跑）
mark(u'B 意图解析：点名 / 代词 / 唯一在办 · 两条在办不猜 · 点名没在办不拦 · 口语不收')

_hb = _Host()
_hb.assign_errand('ralsei', _DEST, u'\u53bb\u770b\u770b', now=0.0)


def _pc(text, host=None):
    return (host or _hb)._errand_parse_cancel(text)


_c1 = _pc(u'\u522b\u8ba9 ralsei \u53bb oneshot \u4e86')
check(u'B0 分母闸：一条在办 + 点名取消 ⇒ 真解析出来了（否则后面全是空断言）',
      _c1 is not None and _c1[0] == 'ralsei',
      u'成立=%s' % (_c1 is not None,))
check(u'B1 点名的按点名（`ralsei`），带回的是**那条在办差事**',
      _c1 is not None and _c1[1] is _hb.npc_errand.active_of('ralsei'),
      u'成立=%s' % (_c1 is not None,))

_c2 = _pc(u'\u522b\u8ba9\u4ed6\u53bb\u4e86')
check(u'B2 用代词「他」+ 只有一条在办 ⇒ 认（人话里极少把名字说全）',
      _c2 is not None and _c2[0] == 'ralsei',
      u'成立=%s' % (_c2 is not None,))

_c3 = _pc(u'\u4e0d\u7528\u53bb\u4e86')
check(u'B3 不带任何人称、只有一条在办 ⇒ 认（"不猜"只针对**多条**）',
      _c3 is not None and _c3[0] == 'ralsei',
      u'成立=%s' % (_c3 is not None,))

# ---- B4 ★ 两条在办且没点名 ⇒ 不猜 ----
#   ⚠️ 样本要选**两个都能去同一间房**的人：`susie` 去 oneshot 会被门控拒
#      （"oneshot 不属于 苏西"）⇒ 那样只剩一条在办，B4 就退化成 B3 了（假红）。
_hb4 = _Host()
_hb4.assign_errand('ralsei', _DEST, u'\u53bb\u770b\u770b', now=0.0)
_hb4.assign_errand('os_niko', _DEST, u'\u53bb\u770b\u770b', now=0.0)
_two = len(_hb4.npc_errand)
_c4 = _hb4._errand_parse_cancel(u'\u4e0d\u7528\u53bb\u4e86')
_c4b = _hb4._errand_parse_cancel(u'\u522b\u8ba9 niko \u53bb\u4e86')
check(u'B4 ★ 两条在办、没点名 ⇒ **不猜**（`None`）；点名了就只撤那一个',
      _two == 2 and _c4 is None and _c4b is not None and _c4b[0] == 'os_niko',
      u'在办=%s 未点名=%s' % (_two, _c4 is None))

# ---- B5 点名的人没在办 ⇒ 不拦 ----
_c5 = _hb._errand_parse_cancel(u'\u522b\u8ba9 susie \u53bb\u4e86')
check(u'B5 ★ 点名的人**没在办** ⇒ 不拦（交给普通对话，别替用户"取消"不存在的事）',
      _c5 is None, u'成立=%s' % (_c5 is None,))

# ---- B6 ★ 口语词刻意不收 ----
_WORDS = (u'\u6211\u56de\u6765\u4e86', u'\u7b97\u4e86\u4e0d\u5403\u4e86',
          u'\u53d6\u6d88\u8ba2\u9605', u'\u522b\u8ba9\u4eba\u7b49',
          u'\u4f60\u8fd9\u4e2a\u7279\u522b\u597d')
_bad6 = [w for w in _WORDS if _hb._errand_parse_cancel(w) is not None]
check(u'B6 ★ 「我回来了」「算了」「取消订阅」「别让人等」**一律不拦**'
      u'（收了就会把人凭空叫回来）',
      not _bad6, u'误收=%s' % (_bad6,))

# ---- B7 空/非字符串 ----
_bad7 = []
for _t in (u'', u'   ', None, 123, [], {}):
    try:
        if _hb._errand_parse_cancel(_t) is not None:
            _bad7.append(_t)
    except Exception as _e:
        _bad7.append((_t, type(_e).__name__))
check(u'B7 空串 / 空白 / `None` / 数字 / 容器 ⇒ 一律 `None` 且**不抛**',
      not _bad7, u'异常或误判=%s' % (_bad7,))

# ---- B8 关闸 ⇒ 不拦（★ 先派再关，否则"不拦"和"没事可拦"分不开）----
_hb8 = _Host()
_hb8.assign_errand('ralsei', _DEST, u'\u53bb\u770b\u770b', now=0.0)
_hb8.npc_errand.enabled = False
_c8 = _hb8._errand_parse_cancel(u'\u522b\u8ba9 ralsei \u53bb oneshot \u4e86')
check(u'B8 关闸之后不拦（哪怕看板里还留着一条）—— 关闸就是"这功能停了"',
      _c8 is None and len(_hb8.npc_errand) == 1,
      u'成立=%s' % (_c8 is None,))

# ---- B9 真实别名表（不是自己编的两个词）----
_names = ('ralsei', u'\u82cf\u897f')
_bad9 = [n for n in _names if n.lower() not in _hb._npc_aliases]
check(u'B9 分母闸（真别名表）：`ralsei` 与「苏西」都在登记表里'
      u'（★ 名字里**不写别名总数** —— 那是随注册表变的量）',
      not _bad9, u'缺=%s' % (_bad9,))

# ---- B10 取消词两组都自带"要命中"的正控制 ----
_hit10 = []
for _w in RalseiPet._ERRAND_CANCEL_ANY:
    if _hb._errand_parse_cancel(u'%s' % _w) is not None:
        _hit10.append(_w)
check(u'B10 第二组词（`_ERRAND_CANCEL_ANY`）**每一个**都能单独命中'
      u'（有词写了却永远不命中 = 死词）',
      len(_hit10) == len(RalseiPet._ERRAND_CANCEL_ANY),
      u'成立=%s' % (len(_hit10) == len(RalseiPet._ERRAND_CANCEL_ANY),))

# ================================================ C 顺序与不重复派
mark(u'C 顺序：取消先于派活；「别让…去了」既不重派、也不会被当成新派活')

_cancel_at = _calls(_HANDLE, '_errand_parse_cancel')
_intent_at = _calls(_HANDLE, '_errand_parse_intent')
_order_ok = (len(_cancel_at) == 1 and len(_intent_at) == 1
             and _cancel_at[0].lineno < _intent_at[0].lineno)
check(u'C1 ★ AST：`_errand_parse_cancel` 在 `_errand_parse_intent` **之前**'
      u'（顺序即语义；反了就会"先派一次再撤"）',
      _order_ok, u'顺序对=%s' % (_order_ok,))

# ---- C2 真跑：有在办 ⇒ 撤、且**不新派** ----
_hc = _Host()
_hc.assign_errand('ralsei', _DEST, u'\u53bb\u770b\u770b', now=0.0)
_hc.npc_roam.put('ralsei', _DEST, 0.0, 'errand')
_n_before = len(_hc.npc_errand)
_ok_c2 = _hc.handle_errand_command(u'\u522b\u8ba9 ralsei \u53bb oneshot \u4e86')
check(u'C2 ★ 真跑「别让 ralsei 去 oneshot 了」：认作叫停（`True`）、差事被撤、'
      u'**看板归零**（没有被"再派一次"补上）',
      _ok_c2 is True and _n_before == 1 and len(_hc.npc_errand) == 0,
      u'成立=%s' % (_ok_c2 is True and len(_hc.npc_errand) == 0,))
check(u'C2b 叫停**回了话**（走 `_errand_cancel_ack`，不是静默撤掉）',
      len(_hc.cancel_acks) == 1 and _hc.acks == [],
      u'成立=%s' % (len(_hc.cancel_acks) == 1,))

# ---- C3 没在办 ⇒ 不拦、也**不派**（否定闸）----
#   ★★★ 说话人**必须换成别人**：`_errand_parse_intent` 的 ④ 是"不能派自己"，
#     若说话人还是 `ralsei`，那这句「别让 ralsei 去…」会被 ④ 顺手挡掉 ⇒
#     C3 变成**恒真**（拆掉否定闸也照样绿）。第一版就是这么写的，M4 一把拆穿。
#     ⇒ 让 susie 来说，再问"会不会被派出去"，才是干净地只考否定闸。
_hc3 = _Host()
_hc3._npc_talking = 'susie'
_ok_c3 = _hc3.handle_errand_command(u'\u522b\u8ba9 ralsei \u53bb oneshot \u4e86')
check(u'C3 ★ 同一句、但他没在办 ⇒ 不拦（`False`）**且不许派出去**'
      u'（否定句不是派活 —— 这条靠 `ERRAND_NEGATIONS` 守；说话人换成别人，'
      u'免得被"不能派自己"那条既有规则顺手挡掉）',
      _ok_c3 is False and len(_hc3.npc_errand) == 0,
      u'成立=%s' % (_ok_c3 is False and len(_hc3.npc_errand) == 0,))

# ---- C4 正向控制：正常派活仍照常 ----
#   ★ 说话人换成 `susie`：`_errand_parse_intent` 的 ④ 是"**不能派自己**"，
#     而本宿主默认说话人就是 `ralsei` ⇒ 「让 ralsei 去…」会被那条规则正确拒掉
#     （那是**既有**设计，不是本轮的闸）。换个人说话才是干净的对照。
_hc4 = _Host()
_hc4._npc_talking = 'susie'
_ok_c4 = _hc4.handle_errand_command(u'\u8ba9 ralsei \u53bb oneshot \u770b\u770b')
check(u'C4 正向控制：`让 ralsei 去 oneshot 看看` 仍然**派得出去**'
      u'（否定闸没把正常派活一起关掉）',
      _ok_c4 is True and len(_hc4.npc_errand) == 1,
      u'成立=%s' % (_ok_c4 is True and len(_hc4.npc_errand) == 1,))

# ---- C5 取消分支必须 `return True`（不许"撤完继续往下走"）----
#   ★ 定位方式：找**体内调用了 `_errand_cancel_ack`** 的那个 `if`（取消分支独有）——
#     不能靠 `if` 的 test 里有没有 `_errand_parse_cancel`：那是**上一句赋值**，
#     不在 test 里（第一版就是这么写错的，红的是判据不是产品）。
_ret_ok = False
_branch_found = 0
if _HANDLE is not None:
    for _st in _HANDLE.body:
        if not isinstance(_st, ast.If):
            continue
        _has_ack = any(isinstance(x, ast.Call) and isinstance(x.func, ast.Attribute)
                       and x.func.attr == '_errand_cancel_ack'
                       for x in ast.walk(_st))
        if not _has_ack:
            continue
        _branch_found += 1
        _last = _st.body[-1] if _st.body else None
        _ret_ok = (isinstance(_last, ast.Return)
                   and isinstance(_last.value, ast.Constant)
                   and _last.value.value is True)
check(u'C5 取消那一支的最后一句是 `return True`（撤完就结束，**不许**落到派活逻辑里）',
      _branch_found == 1 and _ret_ok,
      u'分支=%s 结尾正确=%s' % (_branch_found, _ret_ok))

# ---- C6 竞态：从"解析到"到"真撤"之间他刚好办完 ⇒ 不许冒认 ----
#   ★ 为什么要这一条：`cancel_errand` 返 `None` 有**两种**含义 ——
#     "没在办"（解析层已经排掉）与"刚好办完/被别人撤了"（竞态）。
#     若不看返回值就 ack，会回用户一句"他回来了"，而人其实刚办完事还站在那儿。
class _RaceHost(_Host):
    u"""模拟竞态：解析时还在办，真撤时已经没了。"""

    def cancel_errand(self, *a, **k):
        return None


_hc6 = _RaceHost()
_hc6.assign_errand('ralsei', _DEST, u'\u53bb\u770b\u770b', now=0.0)
_ok_c6 = _hc6.handle_errand_command(u'\u522b\u8ba9 ralsei \u53bb oneshot \u4e86')
check(u'C6 ★ 竞态（`cancel_errand` 返 `None`）⇒ **不冒认**、不回话，交回普通对话',
      _ok_c6 is False and _hc6.cancel_acks == [] and len(_hc6.npc_errand) == 1,
      u'成立=%s' % (_ok_c6 is False and _hc6.cancel_acks == [],))

# ================================================ D 零回归 / 自检
mark(u'D 零回归与自检：普通句子恒 None · 规则只有一份 · 判据自身体检')

_PLAIN = (u'\u4f60\u597d', u'\u4eca\u5929\u5929\u6c14\u4e0d\u9519', u'\u8ba9 ralsei \u53bb oneshot \u770b\u770b',
          u'\u6211\u60f3\u53bb\u7761\u4e86', u'\u8c22\u8c22\u4f60')
_hd = _Host()
_hd.assign_errand('ralsei', _DEST, u'\u53bb\u770b\u770b', now=0.0)
_pd = [t for t in _PLAIN if _hd._errand_parse_cancel(t) is not None]
check(u'D1 普通句子**一条都不许**被当成叫停（含"让…去…看看"这种正常派活句）',
      not _pd, u'误判=%s' % (_pd,))

#: ★ 规则只有一份：派活体内**不许**再自己写一遍"遍历别名"的循环
_loop_in_intent = False
if _PINTENT is not None:
    for _n in ast.walk(_PINTENT):
        if isinstance(_n, ast.For) and isinstance(_n.iter, ast.Attribute) \
                and _n.iter.attr == '_npc_aliases':
            _loop_in_intent = True
check(u'D2 ★ 派活**不再自己遍历别名表**（走 `_errand_find_name` —— 取消与派活共用一份规则）',
      _PINTENT is not None and not _loop_in_intent
      and bool(_calls(_PINTENT, '_errand_find_name')),
      u'成立=%s' % (_PINTENT is not None and not _loop_in_intent,))

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
check(u'D3 判据的 detail **不回显时相量**（无 `%d` 格式化、不引用行号）',
      not _VOLATILE, u'命中=%s' % (u'有' if _VOLATILE else u'无',))
check(u'D4 判据名都是非空字面量（防"名字被拼空"）',
      all(isinstance(n.args[0], ast.Constant) and isinstance(n.args[0].value, str)
          and n.args[0].value.strip()
          for n in ast.walk(_SELF)
          if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
          and n.func.id == 'check' and n.args),
      u'成立=%s' % (True,))
with io.open(os.path.abspath(__file__), 'rb') as _f3:
    _raw = _f3.read()
check(u'D5 无 BOM', not _raw.startswith(b'\xef\xbb\xbf'))
check(u'D6 零外部盘（只读仓库内文件）',
      os.path.abspath(MAIN).startswith(ROOT + os.sep)
      and os.path.abspath(REPORT).startswith(ROOT + os.sep),
      u'成立=%s' % (os.path.abspath(MAIN).startswith(ROOT + os.sep),))

print('')
print('=' * 78)
print(u'check152：PASS=%d FAIL=%d' % (_n_pass, _n_fail))
if _failed:
    print(u'失败项：')
    for _d in _failed:
        print(u'  - %s' % _d)
sys.exit(0 if _n_fail == 0 else 1)
