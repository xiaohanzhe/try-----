# -*- coding: utf-8 -*-
u"""第154轮回归锁：**改派留痕** —— 覆盖不是"没发生过"。

## 为什么要这个口子（用户口径逐字）

> 「**按照人类的逻辑来就好**」

你刚答应去擦柜台，转头又被叫去别处 ⇒ **人会记得"那件先搁下了"**。
而 `ErrandBoard.assign` 对同一人是**覆盖**：旧差事从 `_active` 里直接消失，
不进 `done`、不留 `result`、也不会走 `_npc_errand_commit`。

⇒ 实测（本轮开头的探针，`probe154`）：改派一次之后
**看板里没有它、`done` 里没有它、记忆里 0 条** —— 他**彻底忘了**。
用户过两天问"柜台擦了吗"，他只会茫然。

这与第152轮「作废 ≠ 办完，必须留一句"没办完就被叫回来了"」是同一条：
**一件差事只要存在过，就不能无声无息地消失**。

## 本轮补的两处

| 位置 | 补什么 |
|---|---|
| `assign_errand` | 门控通过后**先取**旧差事（覆盖之后就取不到了）⇒ **派成之后**再落一条记忆「我本来要去 A 办「甲」，还没办完，又被派去 B 办「乙」了」 |
| `_errand_ack(..., prev=None)` | brief 里补一句"原来那件被作废了"，**提不提由模型决定**（台词不写死） |

## ★★★ 本轮第二刀：这两句什么时候是**假话**

第一版把"写痕"放在 `board.assign` **之前**（理由是"覆盖后旧对象就没了"）。
用"这句话会不会是假话"过一遍，探针实测抓到两条**假记忆**：

| # | 场景 | 第一版写下的记忆 | 事实 |
|---|---|---|---|
| P1 | 同一件事重说一遍（地点、事由都一样） | 「又被派去 **oneshot** 办**「擦柜台」**了」 | 本来就是去那儿擦柜台 —— 自相矛盾 |
| P2 | 派发**失败**（看板在派发前被关掉，`assign` 返 `None`） | 「又被派去 **ut** 办了」 | 他**还在去 oneshot 的路上**（`assign` 什么都没接） |

⇒ 定死两条：

1. **派成之后才写痕**（`_new is not None`）。取旧引用仍必须在 `assign` 之前 ——
   但"取"和"写"是两件事，第一版把它们混成了一件。
2. **同一件事重说一遍 ≠ 改派**（`_errand_same_job`）。`assign` 会重新计时，
   但地点与事由一个字段都没变 ⇒ 一件都没被作废，写"被改派"是**无中生有**。

## 本套件守什么

| 段 | 守什么 |
|---|---|
| A | **留痕本身**（真跑）：改派 ⇒ 恰好一条、旧地点旧事由新地点都在 · 首次派活 ⇒ **零**条（不许凭空说"我本来要去"）· 门控拒 ⇒ 留的是"去不了"**不是**"被派去别处"（且旧差事还在）· 连改两次 ⇒ 两条 · 事由为空时文案不出「办「」」· **派发失败 ⇒ 零条**（假记忆）· **同一件事重说 ⇒ 零条** · 同地换事由 ⇒ **仍留痕**（防判据过宽） |
| B | **对话层**：改派时 ack 拿得到 `prev`（且是**旧那条**对象）· 首次派活 `prev is None` · 门控拒不传 · brief 里带"作废"这条事实 · **同一件事重说 ⇒ brief 里没有"作废"** |
| C | **AST**：`active_of` 在 `board.assign` **之前**且**只有一处** · 留痕在 `assign` **之后**（派成了才写）· 改派那句**不在**门控拒的分支里 · 改派文案与叫停文案**不是同一句** · `prev` 是**可选**参数（否则既有调用全崩） |
| D | 自检：判据名非空字面量 · 只用 `check()` 不用 `ok()` · 无 BOM 裸 LF=0 · 零外部盘 |

★ 判据纪律：`print('[PASS] %s')` 字面量；断行为不断赋值；正/负控制成对；
  零网络 / 零 UI / 零显示器 / 零外部盘。
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


_DEST = 'oneshot.barrens.Blue'
_DEST2 = 'ut.rooms.room_area1'
_DEST3 = 'ch1.hometown.town_mid'
_WHAT = u'\u64e6\u67dc\u53f0'
_WHAT2 = u'\u53bb\u770b\u770b'


class _Mem(object):
    def __init__(self):
        self.log = []

    def remember(self, nid, text, who=None, **kw):
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
    u"""轻宿主：挂**产品真函数**（`assign_errand` / `_npc_errand_note` / 两个解析）。

    ★ 只有外围是桩：门控（要真注册表，用 `gate_ok` 开关）、`chat_with_ai`
      （会连 7B）、`_errand_ack`（本套件把它的**入参**当观测量）。
    """

    _npc_errand_note = RalseiPet._npc_errand_note
    _errand_note = RalseiPet._npc_errand_note
    assign_errand = RalseiPet.assign_errand
    _errand_parse_intent = RalseiPet._errand_parse_intent
    _errand_parse_cancel = RalseiPet._errand_parse_cancel
    _errand_is_negative = RalseiPet._errand_is_negative
    _errand_find_name = RalseiPet._errand_find_name
    _errand_strip_leads = RalseiPet._errand_strip_leads
    handle_errand_command = RalseiPet.handle_errand_command

    def __init__(self, enabled=True):
        self.npc_registry = NS.load_registry()
        self._npc_aliases = NP.address_aliases(
            [(n.id, n.name, n.name_cn) for n in self.npc_registry.all()])
        self.npc_errand = ER.ErrandBoard(enabled=enabled)
        self.npc_memory = _Mem()
        self.npc_roam = _Roam()
        self._npc_talking = 'ralsei'
        self.gate_ok = True
        self.acks = []
        self.chats = []

    # ---- 外围桩 ----
    def _npc_errand_gate(self, npc_id, dest):
        return (self.gate_ok, u'' if self.gate_ok else u'\u8fdb\u4e0d\u53bb')

    def _errand_scene_in(self, prefix):
        # 本套件只关心"是不是那个场景"，不关心真场景表
        return {'oneshot': _DEST, 'desktop': 'desktop',
                'ut': _DEST2, 'ch1': _DEST3}.get(prefix)

    def _npc_ai_available(self):
        return True

    def npc_persona_of(self, npc_id):
        return u'\u4f60\u662f%s' % npc_id

    def npc_label(self, npc_id):
        return npc_id

    def _npc_model(self, npc_id):
        return None

    def _errand_place_label(self, scene_id):
        return scene_id

    def _npc_scene_id(self):
        return 'desktop'

    def _npc_carried_ids(self):
        return []

    def _npc_seed_bodies(self, scene_id=None):
        pass

    def _npc_plan_save(self, force=False):
        return True

    def _npc_errand_save(self, force=False):
        return True

    def chat_with_ai(self, text, on_reply, on_delta=None, speaker=None,
                     remember=True, model=None):
        self.chats.append(text)
        return True

    def _errand_ack(self, asker, target, dest, what, ok, why, prev=None):
        # ★ 把**入参**记下来：B 段考的就是"改派时 ack 拿不拿得到旧差事"。
        self.acks.append({'asker': asker, 'target': target, 'dest': dest,
                          'what': what, 'ok': ok, 'why': why, 'prev': prev})

    def _errand_cancel_ack(self, *a, **kw):
        pass

    def _errand_show_reply(self, who, reply):
        pass


_CLS = _clsdef(TREE, 'RalseiPet')
_ASSIGN = _method(_CLS, 'assign_errand')
_ACK = _method(_CLS, '_errand_ack')
_CANCEL = _method(_CLS, 'cancel_errand')


def _notes(h):
    return [row[1] for row in h.npc_memory.log]


# ================================================ A 留痕本身
mark(u'A 留痕：改派记一条 / 首次不记 / 门控拒记"去不了" / 连改两次两条'
     u' / 派发失败不记 / 同一件事重说不记 / 同地换事由仍记')

check(u'A0 分母闸：`assign_errand` 与 `_npc_errand_note` **都在**（缺一个后面全是空断言）',
      _ASSIGN is not None and _CLS is not None
      and _method(_CLS, '_npc_errand_note') is not None,
      u'成立=%s' % (_ASSIGN is not None,))

# ---- A1 正控制：改派 ⇒ 恰好一条，且旧地点/旧事由/新地点都在 ----
_h1 = _Host()
_h1.assign_errand('ralsei', _DEST, _WHAT, now=0.0)
_h1.assign_errand('ralsei', _DEST2, _WHAT2, now=1.0)
_n1 = _notes(_h1)
_t1 = _n1[0] if _n1 else u''
check(u'A1 ★ 改派 ⇒ 记忆里**恰好一条**（正控制：不记就说明这轮等于没做）',
      len(_n1) == 1, u'条数=%d' % (len(_n1),))
check(u'A1b ★ 那一条把**旧地点 / 旧事由 / 新地点**都写进去了'
      u'（少一样就等于"记了但没用"）',
      _DEST in _t1 and _WHAT in _t1 and _DEST2 in _t1,
      u'旧地=%s 旧事=%s 新地=%s'
      % (_DEST in _t1, _WHAT in _t1, _DEST2 in _t1))

# ---- A1c 覆盖是真的：旧的不在看板、也不在 done ----
check(u'A1c 旧差事**确实被覆盖**（不在表里、不进 `done`）—— '
      u'本轮补的是"留痕"，不是"两件并存"',
      len(_h1.npc_errand) == 1
      and _h1.npc_errand.active_of('ralsei').dest_scene == _DEST2
      and len(_h1.npc_errand.done) == 0,
      u'在办=%d / done=%d'
      % (len(_h1.npc_errand), len(_h1.npc_errand.done)))

# ---- A2 负控制：首次派活 ⇒ 零条 ----
_h2 = _Host()
_h2.assign_errand('ralsei', _DEST, _WHAT, now=0.0)
check(u'A2 ★★ 首次派活（手上没别的）⇒ **零条**留痕'
      u'（不许凭空说"我本来要去"，那是编造记忆）',
      len(_h2.npc_memory.log) == 0, u'条数=%d' % (len(_h2.npc_memory.log),))

# ---- A3 负控制：门控拒 ⇒ 留"去不了"，不是"被派去别处"，且旧差事还在 ----
_h3 = _Host()
_h3.assign_errand('ralsei', _DEST, _WHAT, now=0.0)
_h3.gate_ok = False
_r3 = _h3.assign_errand('ralsei', _DEST2, _WHAT2, now=1.0)
_n3 = _notes(_h3)
_t3 = _n3[-1] if _n3 else u''
check(u'A3 ★★ 门控拒 ⇒ 留的是「**去不了**」那句，**不是**「被派去别处」'
      u'（新差事没派成，说"改派了"就是假话）',
      _r3 is None and u'\u53bb\u4e0d\u4e86' in _t3
      and u'\u53c8\u88ab\u6d3e\u53bb' not in _t3,
      u'返回=%r' % (_r3,))
check(u'A3b 门控拒之后**旧差事还在**（没被换掉）—— 这才是"没派成"的样子',
      _h3.npc_errand.active_of('ralsei') is not None
      and _h3.npc_errand.active_of('ralsei').dest_scene == _DEST,
      u'在办=%s'
      % (getattr(_h3.npc_errand.active_of('ralsei'), 'dest_scene', None),))

# ---- A4 连改两次 ⇒ 两条 ----
_h4 = _Host()
_h4.assign_errand('ralsei', _DEST, _WHAT, now=0.0)
_h4.assign_errand('ralsei', _DEST2, _WHAT2, now=1.0)
_h4.assign_errand('ralsei', _DEST3, _WHAT, now=2.0)
check(u'A4 同一人连改两次 ⇒ **两条**留痕（每件被换掉的都要留，不能只留最后一件）',
      len(_h4.npc_memory.log) == 2,
      u'条数=%d' % (len(_h4.npc_memory.log),))

# ---- A5 边界：事由为空时文案不出「办「」」 ----
_h5 = _Host()
_h5.assign_errand('ralsei', _DEST, u'', now=0.0)
_h5.assign_errand('ralsei', _DEST2, u'', now=1.0)
_n5 = _notes(_h5)
_t5 = _n5[0] if _n5 else u''
check(u'A5 事由为空 ⇒ 文案退成人话（不许出现「办「」」这种空壳）',
      bool(_t5) and u'\u529e\u300c\u300d' not in _t5,
      u'含空壳=%s' % (u'\u529e\u300c\u300d' in _t5,))

# ---- A6 不同人互不干扰（负控制）----
_h6 = _Host()
_h6.assign_errand('ralsei', _DEST, _WHAT, now=0.0)
_h6.assign_errand('susie', _DEST2, _WHAT2, now=1.0)
check(u'A6 派**另一个**人 ⇒ 零条留痕（他手上本来没有东西被换掉）',
      len(_h6.npc_memory.log) == 0,
      u'条数=%d' % (len(_h6.npc_memory.log),))

# ---- A7 ★★ 派发失败 ⇒ 零条（"派不成就别写"，否则是**假记忆**）----
_h7 = _Host()
_h7.assign_errand('ralsei', _DEST, _WHAT, now=0.0)
_h7.npc_errand.enabled = False        # 派发**那一刻**看板被关 ⇒ assign 返 None
_r7 = _h7.assign_errand('ralsei', _DEST2, _WHAT2, now=1.0)
_n7 = _notes(_h7)
check(u'A7 ★★ 派发**失败**（`assign` 返 None）⇒ **零条**留痕，且旧差事还在'
      u'（先写痕 = 他记着"被派去 B 了"，实际仍在去 A 的路上 —— 假记忆）',
      _r7 is None and len(_n7) == 0
      and getattr(_h7.npc_errand.active_of('ralsei'), 'dest_scene', None) == _DEST,
      u'返回=%r 条数=%d 在办=%s'
      % (_r7, len(_n7),
         getattr(_h7.npc_errand.active_of('ralsei'), 'dest_scene', None)))

# ---- A8 ★★ 同一件事重说一遍 ≠ 改派 ----
_h8 = _Host()
_h8.assign_errand('ralsei', _DEST, _WHAT, now=0.0)
_h8.assign_errand('ralsei', _DEST, _WHAT, now=1.0)
_n8 = _notes(_h8)
check(u'A8 ★★ 同一件事重说一遍（地点、事由都一样）⇒ **零条**留痕'
      u'（否则写成"又被派去**同一个地方**办**同一件事**了" —— 自相矛盾）',
      len(_n8) == 0, u'条数=%d' % (len(_n8),))

# ---- A8b 正控制：同地**换事由** ⇒ 仍是真改派，必须留痕（防判据过宽）----
_h8b = _Host()
_h8b.assign_errand('ralsei', _DEST, _WHAT, now=0.0)
_h8b.assign_errand('ralsei', _DEST, _WHAT2, now=1.0)
_n8b = _notes(_h8b)
_t8b = _n8b[0] if _n8b else u''
check(u'A8b 同一地点、**换了事由** ⇒ **仍然留痕**（正控制：说明判据没写成'
      u'"同一个地方就都算同一件"，那会把真改派一起吃掉）',
      len(_n8b) == 1 and _WHAT2 in _t8b,
      u'条数=%d / 含新事由=%s' % (len(_n8b), _WHAT2 in _t8b))

# ================================================ B 对话层
mark(u'B 对话层：ack 拿得到 prev / 首次为 None / 门控拒不传 / brief 带事实'
     u' / 同一件事重说不带"作废"')

# ---- B1 通过对话改派 ⇒ ack 收到旧那条 ----
_hb = _Host()
_u1 = u'\u8ba9\u82cf\u897f\u53bb oneshot \u64e6\u67dc\u53f0'
_u2 = u'\u8ba9\u82cf\u897f\u53bb ut \u53bb\u770b\u770b'
_ok1 = _hb.handle_errand_command(_u1)
_ok2 = _hb.handle_errand_command(_u2)
_a2 = _hb.acks[-1] if _hb.acks else {}
check(u'B0 分母闸：两句话都被认成派活（否则 B 段全是空断言）',
      _ok1 is True and _ok2 is True and len(_hb.acks) == 2,
      u'ok=%s/%s 条数=%d' % (_ok1, _ok2, len(_hb.acks)))
check(u'B1 ★ 改派那次 ack 拿到了 `prev`，且是**旧那条**（地点=第一次的）',
      _a2.get('prev') is not None
      and getattr(_a2.get('prev'), 'dest_scene', None) == _DEST,
      u'prev 地点=%r'
      % (getattr(_a2.get('prev'), 'dest_scene', None),))
check(u'B2 首次派活那次 ack 的 `prev` 是 `None`（负控制：别乱传）',
      bool(_hb.acks) and _hb.acks[0].get('prev') is None,
      u'prev=%r' % ((_hb.acks[0].get('prev') if _hb.acks else 'x'),))

# ---- B3 brief 里带上"作废"这条事实 ----
class _AckHost(_Host):
    u"""把 `_errand_ack` 换成**真**的 —— 要看它拼出来的 brief。

    ★ 不能用 `host._errand_ack = RalseiPet._errand_ack`（实例属性不绑定 `self`，
      调起来 first-arg 会错位成 `asker_id`）⇒ 必须挂在**类**上。
    """
    _errand_ack = RalseiPet._errand_ack


_hb3 = _AckHost()
_hb3.assign_errand('susie', _DEST, _WHAT, now=0.0)
_prev3 = _hb3.npc_errand.active_of('susie')
_hb3._errand_ack('ralsei', 'susie', _DEST2, _WHAT2, True, u'', prev=_prev3)
_brief_with = _hb3.chats[-1] if _hb3.chats else u''
_hb3._errand_ack('ralsei', 'susie', _DEST2, _WHAT2, True, u'', prev=None)
_brief_without = _hb3.chats[-1] if len(_hb3.chats) > 1 else u''
check(u'B3a 两组 brief 先证明**确实不同**（否则下面"有没有那句"就是恒真）',
      bool(_brief_with) and _brief_with != _brief_without,
      u'同值=%s' % (_brief_with == _brief_without,))
check(u'B3 ★ 改派（有 `prev`）的 brief 里**明说了**"原来那件被作废了"，'
      u'且带旧地点（不说 ⇒ 模型没法接这句话）',
      u'\u4f5c\u5e9f' in _brief_with and _DEST in _brief_with,
      u'含作废=%s 含旧地=%s'
      % (u'\u4f5c\u5e9f' in _brief_with, _DEST in _brief_with))
check(u'B3b 首次派活（`prev=None`）的 brief 里**没有**这句'
      u'（负控制：不能凭空多一件"被作废的事"）',
      u'\u4f5c\u5e9f' not in _brief_without,
      u'含作废=%s' % (u'\u4f5c\u5e9f' in _brief_without,))

# ---- B4 门控拒 ⇒ 不传 prev ----
_hb4 = _Host()
_hb4.assign_errand('susie', _DEST, _WHAT, now=0.0)
_hb4.gate_ok = False
_hb4.handle_errand_command(u'\u8ba9\u82cf\u897f\u53bb ut \u53bb\u770b\u770b')
_a4 = _hb4.acks[-1] if _hb4.acks else {}
check(u'B4 ★ 门控拒那次 ack 的 `prev` 是 `None`'
      u'（没派成 ⇒ 不能说"原来那件被改派了"）',
      _a4.get('ok') is False and _a4.get('prev') is None,
      u'ok=%r prev=%r' % (_a4.get('ok'), _a4.get('prev')))

# ---- B5 ★★ 同一件事重说一遍 ⇒ brief 里**不许**出现"作废" ----
_hb5 = _AckHost()
_hb5.assign_errand('susie', _DEST, _WHAT, now=0.0)
_same5 = _hb5.npc_errand.active_of('susie')
_hb5._errand_ack('ralsei', 'susie', _DEST, _WHAT, True, u'', prev=_same5)
_brief5_same = _hb5.chats[-1] if _hb5.chats else u''
_hb5._errand_ack('ralsei', 'susie', _DEST2, _WHAT2, True, u'', prev=_same5)
_brief5_diff = _hb5.chats[-1] if len(_hb5.chats) > 1 else u''
check(u'B5a 两组 brief 先证明**确实不同**（否则下面"有没有那句"就是恒真）',
      bool(_brief5_same) and _brief5_same != _brief5_diff,
      u'同值=%s' % (_brief5_same == _brief5_diff,))
check(u'B5 ★★ 同一件事重说一遍 ⇒ brief 里**没有**"作废"这句'
      u'（一件都没被作废，说"原来那件被作废了"是无中生有 ⇒ 模型会照着重编一遍）',
      u'\u4f5c\u5e9f' not in _brief5_same,
      u'含作废=%s' % (u'\u4f5c\u5e9f' in _brief5_same,))

# ================================================ C AST
mark(u'C AST：取旧在 assign 之前（且只有一处）· 留痕在 assign 之后 · '
     u'不在门控拒分支 · 文案与叫停不同 · prev 可选')


def _lineno(fn, attr):
    got = _calls(fn, attr)
    return got[0].lineno if got else None


_ln_active = _lineno(_ASSIGN, 'active_of')
_ln_assign = _lineno(_ASSIGN, 'assign')
check(u'C1 ★★ `assign_errand` 里**先取旧的**（`active_of`）**再** `board.assign`'
      u'（覆盖之后就取不到了，只能拿到 `None`）',
      None not in (_ln_active, _ln_assign) and _ln_active < _ln_assign,
      u'两者都在=%s' % (None not in (_ln_active, _ln_assign),))

# ★ 注意：`assign_errand` 体内 `_npc_errand_note` 有**两处**（门控拒 / 改派）。
#   第一版取的是 `_lineno()`（=第一处，门控那处）⇒ C2 变成恒真（它当然在 assign 之前）。
#   ⇒ 必须按行号排序，取**最后**那一处才是改派。
_ln_notes = sorted(c.lineno for c in _calls(_ASSIGN, '_npc_errand_note'))
_ln_dispatch = _ln_notes[-1] if _ln_notes else None
check(u'C2 ★★ 改派那次留痕在 `board.assign` **之后**（派成了才写）'
      u'—— 写在之前 ⇒ 派发失败也会留下"被派去 B 了"的假记忆',
      len(_ln_notes) == 2 and _ln_dispatch > _ln_assign,
      u'note 处数=%d 留痕行=%s assign 行=%s'
      % (len(_ln_notes), _ln_dispatch, _ln_assign))

# ★ "取"和"写"是两件事，得各有一条判据（第153轮：一条判据只考一件事）：
#   C2 管"写痕在派成之后"，C2b 管"旧对象只取一次、之后持有引用不重读"。
_ln_active_all = sorted(c.lineno for c in _calls(_ASSIGN, 'active_of'))
check(u'C2b ★ 体内 `active_of` **只有一处**，且在 `assign` 之前'
      u'（覆盖之后重读只能拿到新的那条 ⇒ 旧的必须**持有引用**）',
      len(_ln_active_all) == 1 and _ln_active_all[0] < _ln_assign,
      u'处数=%d' % (len(_ln_active_all),))

# ---- C3 门控拒那一支里的 note 只有一处，改派那次在那一支**之外** ----
_gate_if = None
if _ln_notes:
    # ★ 只走**顶层语句**，并取"第一处 note 之前**最后一个** if" —— 函数开头还有
    #   `if board is None: return None`（那不是门控支），取第一个会拿错。
    _cand = [_s for _s in _ASSIGN.body
             if isinstance(_s, ast.If) and _s.lineno < _ln_notes[0]]
    _gate_if = _cand[-1] if _cand else None
_gate_notes = []
if _gate_if is not None:
    for _x in ast.walk(ast.Module(body=_gate_if.body, type_ignores=[])):
        if isinstance(_x, ast.Call) and isinstance(_x.func, ast.Attribute) \
                and _x.func.attr == '_npc_errand_note':
            _gate_notes.append(_x.lineno)
check(u'C3 ★ 门控拒那一支里**恰好一处** note，且改派那处在它**之外**'
      u'（两件事两个出口，别混成一个）',
      _gate_if is not None and len(_gate_notes) == 1
      and _ln_dispatch > _gate_if.end_lineno,
      u'找到门控支=%s 支内 note=%d 处'
      % (_gate_if is not None, len(_gate_notes)))

# ---- C4 改派文案与叫停文案不是同一句 ----


def _doc_ids(fn):
    out = set()
    if fn is None:
        return out
    for _s in fn.body:
        if isinstance(_s, ast.Expr) and isinstance(_s.value, ast.Constant) \
                and isinstance(_s.value.value, str):
            out.add(id(_s.value))
    return out


_cancel_doc = _doc_ids(_CANCEL)
_dispatch_doc = _doc_ids(_ASSIGN)
_cancel_txt = [c.value for c in ast.walk(_CANCEL)
               if isinstance(c, ast.Constant) and isinstance(c.value, str)
               and u'\u53eb\u56de\u6765' in c.value and id(c) not in _cancel_doc]
_dispatch_txt = [c.value for c in ast.walk(_ASSIGN)
                 if isinstance(c, ast.Constant) and isinstance(c.value, str)
                 and u'\u53c8\u88ab\u6d3e\u53bb' in c.value
                 and id(c) not in _dispatch_doc]
check(u'C4 ★ 改派的记忆（"又被派去…"）与叫停的记忆（"被叫回来…"）**不是同一句**'
      u'（同一句话两处用 = 以后分不清他是被叫回来还是被改派）',
      len(_cancel_txt) == 1 and len(_dispatch_txt) == 1
      and _cancel_txt[0] != _dispatch_txt[0],
      u'叫停=%d 条 / 改派=%d 条' % (len(_cancel_txt), len(_dispatch_txt)))

# ---- C5 prev 是可选参数 ----
_prev_default = None
_has_prev = False
for _a in (_ACK.args.args if _ACK is not None else []):
    if _a.arg == 'prev':
        _has_prev = True
for _d, _v in zip(_ACK.args.args[-len(_ACK.args.defaults):] if _ACK.args.defaults
                  else [], _ACK.args.defaults):
    if _d.arg == 'prev':
        _prev_default = _v
check(u'C5 ★ `_errand_ack(..., prev=None)` 的 `prev` 是**可选参数**'
      u'（不是 `*args` 也不是必填 —— 否则既有调用点全崩）',
      _has_prev and isinstance(_prev_default, ast.Constant)
      and _prev_default.value is None,
      u'有 prev=%s / 默认=%r'
      % (_has_prev, getattr(_prev_default, 'value', 'x')))

# ================================================ D 自检
mark(u'D 自检：判据名 · 编码 · 零外部盘 · harness 单一')

_self_src = None
with io.open(os.path.abspath(__file__), 'r', encoding='utf-8', newline='') as _sf:
    _self_src = _sf.read()
_self_tree = ast.parse(_self_src)
_names = []
_ok_calls = 0
for _n in ast.walk(_self_tree):
    if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Name):
        if _n.func.id == 'check' and _n.args:
            _a0 = _n.args[0]
            if isinstance(_a0, ast.Constant) and isinstance(_a0.value, str):
                _names.append(_a0.value)
        if _n.func.id == 'ok':
            _ok_calls += 1
check(u'D1 判据名都是**非空字符串字面量**（不许回显随环境变的量）',
      bool(_names) and all(s.strip() for s in _names) and len(_names) >= 18,
      u'收集到=%d 条 / 空名=%d' % (len(_names),
                                  len([s for s in _names if not s.strip()])))
check(u'D2 ★ 本套件只用 `check()`，不用 `ok()`（两套 harness 的恒真陷阱在第125轮踩过）',
      _ok_calls == 0, u'ok() 调用=%d' % (_ok_calls,))
check(u'D3 `main.py` 无 BOM 且裸 LF=0（改过就必须还是 CRLF 全篇）',
      not SRC.startswith(u'\ufeff')
      and SRC.count('\n') - SRC.count('\r\n') == 0,
      u'BOM=%s / 裸LF=%d' % (SRC.startswith(u'\ufeff'),
                            SRC.count('\n') - SRC.count('\r\n')))
_needle_a = 'E' + ':' + '/'
_needle_b = 'E' + ':' + '\\'
check(u'D4 零外部盘（判据不碰 E: —— 那是坏盘）',
      _needle_a not in _self_src and _needle_b not in _self_src,
      u'成立=%s' % ((_needle_a not in _self_src
                     and _needle_b not in _self_src),))

print('')
if _n_fail:
    print('==== FAIL %d / PASS %d ====' % (_n_fail, _n_pass))
    for _d in _failed:
        print('  · %s' % _d)
    sys.exit(1)
print('==== PASS %d / FAIL 0 ====' % (_n_pass,))
