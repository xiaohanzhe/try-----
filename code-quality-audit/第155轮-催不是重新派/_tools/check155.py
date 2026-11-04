# -*- coding: utf-8 -*-
u"""第155轮回归锁：**「催」不是「重新派」** —— 已经在办的人，被催一句不该被打回起点。

## 为什么要这个口子（用户口径逐字）

> 「**按照人类的逻辑来就好**」

你让人去擦柜台，他走到那儿、已经擦了一会儿；你**又说了一遍**同一句话
（"让 ralsei 去 oneshot 擦柜台"）—— 这是**催**，不是**重新派**。
人不会因为被催一句就放下抹布往回走。

## 改前实测（`probe155` 的「改前」一半，数值都在）

`ErrandBoard.assign` 对同一人是**覆盖**：每次都 `Errand(...)` 造一条新的，
`start=now`、`arrive_at=now+travel`、`finish_at=now+travel+work`。同一句话
在 `t=100`（他已到点、正在办）再说一遍：

| 量 | 改前 | 后果 |
|---|---|---|
| `status` | `working` → `traveling` | **进度清零**，被打回起点 |
| `arrive_at` | 90 → 190（+100 秒） | 又要"再走一趟" |
| `finish_at` | 390 → 490（+100 秒） | 办完时间整体推后 |
| `working_positions()` | `[('ralsei', 'oneshot…')]` → `[]` | **位置钉住资格被撤** ⇒ 下一拍 `roam` 就把他从目的地撤走（用户看到"我催了一句，他反倒掉头往回走"） |
| 返回对象 | 新的（`is` 旧条 = False） | 宿主手里那份引用成了孤儿 |
| ack 的 brief | 与第一次**一字不差**（118 字，都写「他已经在路上了」） | 模型照着说"好，我让他去了"，而他其实已经干了一会儿 |

## 本轮补的两处

| 位置 | 补什么 |
|---|---|
| `assign_errand` | 同一件事（地点 + 事由都不变）⇒ **原样返回手上那条**，不覆盖、不重计时、不清进度；★ 而且**在门控之前**（没重新派 ⇒ 不需要新许可，否则会写下"我本来要去 X 但去不了"而他**人就在 X**） |
| `_errand_ack` | 催有**自己的一句 brief**：说清"他已经在办、这次没有重新出发也没有重新计时"，并按 `prev.status` 分"还在去的路上 / 已经到了正在办" |

## 本套件守什么

| 段 | 守什么 |
|---|---|
| A | **真跑**：已到后重说 ⇒ 同一个对象 · `status` 仍 `working` · 到达/完成时间**没被推后** · 位置钉住资格**还在** · 看板里仍是那条 · 零记忆 · **路上**（未到）重说也不重启 · 同地换事由 / 换地点 ⇒ **真的重新派**（正控制，别把真改派吃掉） · 看板关掉 ⇒ 仍返 `None`（守 `NPC_ERRAND_ENABLED=False` 契约） · **催不问门控**（门控拒时同一件事仍返旧条、零记忆） · 负控制：门控拒时**真改派**照样 `None` + 一条"去不了" · 催时传入的 `travel/work/result` **被忽略** |
| B | **对话层**：同一句话重说 ⇒ `ok` 仍为真、`prev` 就是看板里那条 · 催的 brief 与首次 brief **不同** · 催 brief 说"已经在办 / 没有重新计时" · 催 brief **不再**说"已经在路上了" · 首次 brief **仍然**说（负控制） · 状态真的读了（`working` 说"到了那里"、`traveling` 说"还在去的路上"） · 真改派 brief 仍带"作废"（第154轮没被吃掉） · 催 brief 不带"作废" |
| C | **AST**：短路的 `return _prev` 在 `board.assign` **之前**（催根本不调 `assign`）· 在门控调用**之前** · 短路带 `enabled` 闸 · `_errand_same_job` 在两侧各**只调一次** · `active_of` 仍只有一处 · 读状态走 `npc_errand_mod.WORKING`（不写字面量 `'working'`）· 催与首次是**两处不同赋值** · `_errand_same_job` 仍是**模块级**（写成方法会让轻宿主 `AttributeError`） |
| D | 自检：判据名非空字面量 · 只用 `check()` 不用 `ok()` · 无 BOM 且全 LF · 零外部盘 |

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
_WHAT = u'\u64e6\u67dc\u53f0'
_WHAT2 = u'\u53bb\u770b\u770b'


class _Mem(object):
    def __init__(self):
        self.log = []

    def remember(self, nid, text, who=None, **kw):
        self.log.append((nid, text, who))

    def save(self, nid):
        pass


class _Host(object):
    u"""轻宿主：挂**产品真函数**（`assign_errand` / `_npc_errand_note` / 三个解析 / 派发入口）。

    ★ 只有外围是桩：门控（要真注册表，用 `gate_ok` 开关）、`chat_with_ai`
      （会连 7B）、`_errand_ack`（B 段要看它拼的 brief ⇒ 用 `_AckHost` 换成真货）。
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
        self._npc_talking = 'ralsei'
        self.gate_ok = True
        self.acks = []
        self.chats = []

    # ---- 外围桩 ----
    def _npc_errand_gate(self, npc_id, dest):
        return (self.gate_ok, u'' if self.gate_ok else u'\u8fdb\u4e0d\u53bb')

    def _errand_scene_in(self, prefix):
        return {'oneshot': _DEST, 'desktop': 'desktop',
                'ut': _DEST2}.get(prefix)

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
        self.acks.append({'asker': asker, 'target': target, 'dest': dest,
                          'what': what, 'ok': ok, 'why': why, 'prev': prev})

    def _errand_cancel_ack(self, *a, **kw):
        pass

    def _errand_show_reply(self, who, reply):
        pass


class _AckHost(_Host):
    u"""把 `_errand_ack` 换成**真**的 —— B 段要看它拼出来的 brief。

    ★ 不能写 `host._errand_ack = RalseiPet._errand_ack`（实例属性不绑定 `self`，
      调起来 first-arg 会错位成 `asker_id`）⇒ 必须挂在**类**上。
    """
    _errand_ack = RalseiPet._errand_ack


_CLS = _clsdef(TREE, 'RalseiPet')
_ASSIGN = _method(_CLS, 'assign_errand')
_ACK = _method(_CLS, '_errand_ack')


def _notes(h):
    return [row[1] for row in h.npc_memory.log]


# ================================================ A 真跑
mark(u'A 真跑：已到后重说 ⇒ 不重启 / 不清进度 / 不撤位置 / 零记忆；'
     u'真改派仍然重启；关闸仍 None；催不问门控')

check(u'A0 分母闸：`assign_errand` / `_errand_ack` / `RalseiPet` **都在**'
      u'（缺一个后面全是空断言）',
      _ASSIGN is not None and _ACK is not None and _CLS is not None,
      u'成立=%s/%s' % (_ASSIGN is not None, _ACK is not None))

_h = _Host()
_r1 = _h.assign_errand('ralsei', _DEST, _WHAT, now=0.0)
_h.npc_errand.step(100.0)
_arr0 = _r1.arrive_at
_fin0 = _r1.finish_at
_wp0 = _h.npc_errand.working_positions()
_r2 = _h.assign_errand('ralsei', _DEST, _WHAT, now=100.0)
_n_after = len(_notes(_h))

check(u'A1 ★★ 已到（`working`）之后同一件事再说一遍 ⇒ **返回同一个对象**'
      u'（改前：新的，旧引用成孤儿）',
      _r2 is _r1, u'同一对象=%s' % (_r2 is _r1,))
check(u'A2 ★★ 进度**没被清零**：`status` 仍是 `working`（改前：退回 `traveling`）',
      getattr(_r2, 'status', None) == ER.WORKING,
      u'status=%r' % (getattr(_r2, 'status', None),))
check(u'A3 ★★ 到达 / 完成时间**没被推后**'
      u'（改前：`arrive_at` 90→190、`finish_at` 390→490）',
      # ★ 用 `getattr` 取：万一上一处破坏让这里拿到 `None`，要**判红**而不是
      #   `AttributeError` 把整个套件炸掉（炸掉 = 后面的判据根本没跑，看不出红在哪）。
      getattr(_r2, 'arrive_at', None) == _arr0
      and getattr(_r2, 'finish_at', None) == _fin0,
      u'arrive %s→%s finish %s→%s'
      % (_arr0, getattr(_r2, 'arrive_at', None),
         _fin0, getattr(_r2, 'finish_at', None)))
check(u'A4 ★★ **位置钉住资格还在**：`working_positions()` 里仍有他'
      u'（改前：这条消失 ⇒ 下一拍 `roam` 把他从目的地撤走）',
      bool(_wp0) and _h.npc_errand.working_positions() == _wp0,
      u'前=%r 后=%r' % (_wp0, _h.npc_errand.working_positions()))
check(u'A5 看板里仍是**那一条**（没被替换），在办=1、`done`=0',
      _h.npc_errand.active_of('ralsei') is _r1
      and len(_h.npc_errand) == 1 and len(_h.npc_errand.done) == 0,
      u'在办=%d done=%d' % (len(_h.npc_errand), len(_h.npc_errand.done)))
check(u'A6 催**不写记忆**（一件都没丢 ⇒ 不需要留痕；第154轮口径不变）',
      _n_after == 0, u'条数=%d' % (_n_after,))

# ---- A7 正控制：同地换事由 ⇒ 真的重新派（别把真改派吃掉）----
_h7 = _Host()
_e7a = _h7.assign_errand('ralsei', _DEST, _WHAT, now=0.0)
_h7.npc_errand.step(100.0)
_e7b = _h7.assign_errand('ralsei', _DEST, _WHAT2, now=100.0)
check(u'A7 ★ 同一地点、**换了事由** ⇒ **真的重新派**（新对象、退回 `traveling`、'
      u'到达时间推后）—— 正控制：判据不许宽成"同一个地方就都算催"',
      _e7b is not _e7a and getattr(_e7b, 'status', None) == ER.TRAVELING
      and getattr(_e7b, 'arrive_at', 0.0) > _e7a.arrive_at,
      u'新对象=%s status=%s arrive %s→%s'
      % (_e7b is not _e7a, getattr(_e7b, 'status', None),
         _e7a.arrive_at, getattr(_e7b, 'arrive_at', None)))

# ---- A8 正控制：换地点 ⇒ 重新派 ----
_h8 = _Host()
_e8a = _h8.assign_errand('ralsei', _DEST, _WHAT, now=0.0)
_h8.npc_errand.step(100.0)
_e8b = _h8.assign_errand('ralsei', _DEST2, _WHAT, now=100.0)
check(u'A8 ★ **换了地点**、事由不变 ⇒ 也**真的重新派**（人是被派去别处，不是催）',
      _e8b is not _e8a
      and getattr(_e8b, 'dest_scene', None) == _DEST2
      and getattr(_e8b, 'arrive_at', 0.0) > _e8a.arrive_at,
      u'新对象=%s 地点=%s'
      % (_e8b is not _e8a, getattr(_e8b, 'dest_scene', None)))

# ---- A9 路上（还没到）重说 ⇒ 也不重启 ----
_h9 = _Host()
_e9a = _h9.assign_errand('ralsei', _DEST, _WHAT, now=0.0)
_e9b = _h9.assign_errand('ralsei', _DEST, _WHAT, now=10.0)
check(u'A9 **还在路上**（`traveling`）时重说 ⇒ 不重启：'
      u'`arrive_at` 仍是 90 而不是 100',
      _e9b is _e9a and getattr(_e9b, 'status', None) == ER.TRAVELING
      and getattr(_e9b, 'arrive_at', None) == _e9a.arrive_at
      and getattr(_e9b, 'start', None) == 0.0,
      u'arrive=%s start=%s'
      % (getattr(_e9b, 'arrive_at', None), getattr(_e9b, 'start', None)))

# ---- A10 看板关掉 ⇒ 同一件事也返 None ----
_h10 = _Host()
_h10.assign_errand('ralsei', _DEST, _WHAT, now=0.0)
_h10.npc_errand.enabled = False
_r10 = _h10.assign_errand('ralsei', _DEST, _WHAT, now=1.0)
check(u'A10 看板**关掉** ⇒ 同一件事也返 `None`（守 `NPC_ERRAND_ENABLED=False` '
      u'的契约「`assign_errand()` 恒 `None`」：看板不推进时不许回报"已派出"）',
      _r10 is None, u'返回=%r' % (_r10,))

# ---- A11 催不问门控 ----
_h11 = _Host()
_h11.assign_errand('ralsei', _DEST, _WHAT, now=0.0)
_h11.npc_errand.step(100.0)
_h11.gate_ok = False
_r11 = _h11.assign_errand('ralsei', _DEST, _WHAT, now=100.0)
check(u'A11 ★★ 门控**拒**时，同一件事重说 ⇒ **仍返旧条、零记忆**'
      u'（他**人就在那儿**；改前这一支会写下"我本来要去 X 但去不了"）',
      _r11 is not None and _r11.status == ER.WORKING
      and len(_notes(_h11)) == 0,
      u'返回=%r 条数=%d' % (_r11 is not None, len(_notes(_h11))))

# ---- A12 负控制：门控拒 + 真改派 ⇒ 照旧 None + 一条"去不了" ----
_h12 = _Host()
_h12.assign_errand('ralsei', _DEST, _WHAT, now=0.0)
_h12.npc_errand.step(100.0)
_h12.gate_ok = False
_r12 = _h12.assign_errand('ralsei', _DEST2, _WHAT2, now=100.0)
_n12 = _notes(_h12)
check(u'A12 负控制：门控拒 + **真改派** ⇒ 仍是 `None` + 一条"去不了"'
      u'（说明 A11 不是"门控整个失效了"）',
      _r12 is None and len(_n12) == 1 and u'\u53bb\u4e0d\u4e86' in _n12[0],
      u'返回=%r 条数=%d' % (_r12, len(_n12)))

# ---- A13 催时传进来的 travel/work/result 被忽略 ----
_h13 = _Host()
_e13a = _h13.assign_errand('ralsei', _DEST, _WHAT, now=0.0)
_e13b = _h13.assign_errand('ralsei', _DEST, _WHAT, now=0.0,
                           travel=5.0, work=5.0, result=u'\u81ea\u5b9a\u4e49')
check(u'A13 催时传入的 `travel` / `work` / `result` **被忽略**'
      u'（真有新要求 ⇒ 先叫停再派；否则一条差事会有两套时间）',
      _e13b is _e13a
      and getattr(_e13b, 'finish_at', None) == _e13a.finish_at
      and getattr(_e13b, 'custom_result', None) == u'',
      u'finish=%s custom=%r'
      % (getattr(_e13b, 'finish_at', None),
         getattr(_e13b, 'custom_result', None)))

# ================================================ B 对话层
mark(u'B 对话层：同一句话重说 ⇒ prev 就是那条 · 催 brief 与首次不同 · '
     u'说"已经在办 / 没有重新计时" · 首次仍说"已经在路上了" · 状态真的读了')

_U_SAME = u'\u8ba9\u82cf\u897f\u53bb oneshot \u64e6\u67dc\u53f0'
# ★ B0/B1 用**桩 ack** 的宿主：这两条考的是"派发入口传了什么进去"
#   （`_AckHost` 把 ack 换成真货，`acks` 就不再记账了 —— 第一版这么写，
#     B0 当场 red「acks=0」，那不是产品坏了，是**观测点选错了宿主**）。
_hb = _Host()
_ok1 = _hb.handle_errand_command(_U_SAME)
_ok2 = _hb.handle_errand_command(_U_SAME)
_a2 = _hb.acks[-1] if len(_hb.acks) >= 2 else {}
check(u'B0 分母闸：同一句话两次都被认成派活（否则 B 段全是空断言）',
      _ok1 is True and _ok2 is True and len(_hb.acks) == 2,
      u'ok=%s/%s acks=%d' % (_ok1, _ok2, len(_hb.acks)))
check(u'B1 ★ 催那次 ack 的 `prev` **就是看板里那条**（没被替换），且 `ok` 仍为真',
      _a2.get('ok') is True and _a2.get('prev') is not None
      and _a2.get('prev') is _hb.npc_errand.active_of('susie'),
      u'ok=%r 同一对象=%s'
      % (_a2.get('ok'),
         _a2.get('prev') is _hb.npc_errand.active_of('susie')))

# ---- B2~B5 催 brief vs 首次 brief（确定性：自己摆状态，不靠墙上时钟）----
_hb2 = _AckHost()
_hb2.assign_errand('susie', _DEST, _WHAT, now=0.0)
_hb2.npc_errand.step(100.0)
_prev_w = _hb2.npc_errand.active_of('susie')
_hb2._errand_ack('ralsei', 'susie', _DEST, _WHAT, True, u'', prev=_prev_w)
_brief_nudge = _hb2.chats[-1] if _hb2.chats else u''
_hb2._errand_ack('ralsei', 'susie', _DEST, _WHAT, True, u'', prev=None)
_brief_first = _hb2.chats[-1] if len(_hb2.chats) > 1 else u''

check(u'B2a 分母闸：两条 brief 都真产出、且**确实不同**'
      u'（改前两者一字不差，都是 118 字 ⇒ 这条就是那个病的观测面）',
      bool(_brief_nudge) and bool(_brief_first)
      and _brief_nudge != _brief_first,
      u'同值=%s' % (_brief_nudge == _brief_first,))
check(u'B3 ★ 催的 brief 明说"**已经在办**"且"**没有重新计时**"'
      u'（不说 ⇒ 模型只会说"好，我让他去了"）',
      u'\u5df2\u7ecf\u5728\u529e' in _brief_nudge
      and u'\u6ca1\u6709\u91cd\u65b0\u8ba1\u65f6' in _brief_nudge,
      u'含在办=%s 含没重计时=%s'
      % (u'\u5df2\u7ecf\u5728\u529e' in _brief_nudge,
         u'\u6ca1\u6709\u91cd\u65b0\u8ba1\u65f6' in _brief_nudge))
check(u'B4 ★ 催的 brief **不再**说"他已经在路上了"（改前正是这一句）',
      u'\u5df2\u7ecf\u5728\u8def\u4e0a\u4e86' not in _brief_nudge,
      u'含在路上了=%s'
      % (u'\u5df2\u7ecf\u5728\u8def\u4e0a\u4e86' in _brief_nudge,))
check(u'B5 负控制：**首次派活**（`prev=None`）的 brief **仍然**说"他已经在路上了"'
      u'（别把首次也改成催）',
      u'\u5df2\u7ecf\u5728\u8def\u4e0a\u4e86' in _brief_first,
      u'含在路上了=%s'
      % (u'\u5df2\u7ecf\u5728\u8def\u4e0a\u4e86' in _brief_first,))

# ---- B6 状态真的读了：traveling 与 working 两句话不同 ----
_hb6 = _AckHost()
_hb6.assign_errand('susie', _DEST, _WHAT, now=0.0)
_prev_t = _hb6.npc_errand.active_of('susie')          # 还没到
_hb6._errand_ack('ralsei', 'susie', _DEST, _WHAT, True, u'', prev=_prev_t)
_brief_travel = _hb6.chats[-1] if _hb6.chats else u''
check(u'B6 ★ 催的 brief 按**真实状态**分岔：还在路上 ⇒ 说"还在去的路上"、'
      u'不说"到了那里"；且与"已到"那句**不同**',
      u'\u8fd8\u5728\u53bb\u7684\u8def\u4e0a' in _brief_travel
      and u'\u5230\u4e86\u90a3\u91cc' not in _brief_travel
      and _brief_travel != _brief_nudge,
      u'含还在去=%s 同值=%s'
      % (u'\u8fd8\u5728\u53bb\u7684\u8def\u4e0a' in _brief_travel,
         _brief_travel == _brief_nudge))

# ---- B7/B8 第154轮的"作废"事实没被这轮吃掉 ----
_hb7 = _AckHost()
_hb7.assign_errand('susie', _DEST, _WHAT, now=0.0)
_p7 = _hb7.npc_errand.active_of('susie')
_hb7._errand_ack('ralsei', 'susie', _DEST2, _WHAT2, True, u'', prev=_p7)
_brief_diff = _hb7.chats[-1] if _hb7.chats else u''
check(u'B7 真改派的 brief **仍带**"作废"这条事实（第154轮的成果没被这轮吃掉）',
      u'\u4f5c\u5e9f' in _brief_diff and _DEST in _brief_diff,
      u'含作废=%s 含旧地=%s'
      % (u'\u4f5c\u5e9f' in _brief_diff, _DEST in _brief_diff))
check(u'B8 催的 brief **不带**"作废"（一件都没被作废，说"被作废了"是无中生有）',
      u'\u4f5c\u5e9f' not in _brief_nudge,
      u'含作废=%s' % (u'\u4f5c\u5e9f' in _brief_nudge,))

# ================================================ C AST
mark(u'C AST：短路在 assign 之前、也在门控之前 · 带 enabled 闸 · 各只调一次 · '
     u'读写走常量 · 两处不同赋值 · 仍是模块级函数')

_ln_assign = [c.lineno for c in _calls(_ASSIGN, 'assign')]
_ln_gate = [c.lineno for c in _calls(_ASSIGN, '_npc_errand_gate')]
_ret_prev = []
for n in ast.walk(_ASSIGN):
    if isinstance(n, ast.Return) and isinstance(n.value, ast.Name) \
            and n.value.id == '_prev':
        _ret_prev.append(n.lineno)

check(u'C0 分母闸：`assign` / 门控 / `return _prev` 三样在 `assign_errand` 里**都找得到**'
      u'（缺一样后面就是空断言）',
      bool(_ln_assign) and bool(_ln_gate) and bool(_ret_prev),
      u'assign=%d 门控=%d 返回=%d'
      % (len(_ln_assign), len(_ln_gate), len(_ret_prev)))
check(u'C1 ★★ 短路 `return _prev` 在 `board.assign` **之前**'
      u'（催根本**不调** `assign` —— 调了就必然重新计时）',
      bool(_ret_prev) and bool(_ln_assign)
      and min(_ret_prev) < min(_ln_assign),
      u'返回在 assign 之前=%s'
      % (bool(_ret_prev) and bool(_ln_assign)
         and min(_ret_prev) < min(_ln_assign),))
check(u'C2 ★★ 短路在**门控调用之前**（没重新派 ⇒ 不问路；'
      u'否则"他人在目的地"时会被写成"去不了"）',
      bool(_ret_prev) and bool(_ln_gate) and min(_ret_prev) < min(_ln_gate),
      u'返回在门控之前=%s'
      % (bool(_ret_prev) and bool(_ln_gate) and min(_ret_prev) < min(_ln_gate),))

# ---- C3 短路带 enabled 闸 ----
_guards_return = []
for n in ast.walk(_ASSIGN):
    if not isinstance(n, ast.If):
        continue
    for sub in ast.walk(n):
        if isinstance(sub, ast.Return) and isinstance(sub.value, ast.Name) \
                and sub.value.id == '_prev':
            _guards_return.append(n)
            break
_has_enabled = False
for g in _guards_return:
    for sub in ast.walk(g.test):
        if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name) \
                and sub.func.id == 'getattr' and len(sub.args) >= 2 \
                and isinstance(sub.args[0], ast.Name) \
                and sub.args[0].id == 'board' \
                and isinstance(sub.args[1], ast.Constant) \
                and sub.args[1].value == 'enabled':
            _has_enabled = True
check(u'C3 ★ 短路的条件里带 `board.enabled` 闸'
      u'（看板关掉时不许返旧条：那时没人推进，回报"已派出"= 骗人）',
      _has_enabled, u'有 enabled 闸=%s 短路分支数=%d'
      % (_has_enabled, len(_guards_return)))

# ---- C4 `_errand_same_job` 两侧各只调一次 ----
_n_assign = 0
for c in ast.walk(_ASSIGN):
    if isinstance(c, ast.Call) and isinstance(c.func, ast.Name) \
            and c.func.id == '_errand_same_job':
        _n_assign += 1
_n_ack = 0
for c in ast.walk(_ACK):
    if isinstance(c, ast.Call) and isinstance(c.func, ast.Name) \
            and c.func.id == '_errand_same_job':
        _n_ack += 1
check(u'C4 `_errand_same_job` 在 `assign_errand` 与 `_errand_ack` 里**各只调一次**'
      u'（同一个判断调两次 = 两条路各算一遍）',
      _n_assign == 1 and _n_ack == 1,
      u'assign=%d ack=%d' % (_n_assign, _n_ack))

# ---- C5 `active_of` 仍只有一处（第154轮 C2b 的延续）----
_ln_active = [c.lineno for c in _calls(_ASSIGN, 'active_of')]
check(u'C5 体内 `active_of` **仍只有一处**（两处取会让"哪一份是快照"变成两说）',
      len(_ln_active) == 1, u'处数=%d' % (len(_ln_active),))

# ---- C6 读状态走常量，不写字面量 ----
_uses_const = []
_str_status = []
for c in ast.walk(_ACK):
    if isinstance(c, ast.Attribute) and isinstance(c.value, ast.Name) \
            and c.value.id == 'npc_errand_mod' \
            and c.attr in ('WORKING', 'DONE', 'TRAVELING'):
        _uses_const.append(c.attr)
    if isinstance(c, ast.Compare) and isinstance(c.left, ast.Attribute) \
            and c.left.attr == 'status':
        for o in c.comparators:
            if isinstance(o, ast.Constant) and isinstance(o.value, str):
                _str_status.append(o.value)
check(u'C6 ★ 读状态走 `npc_errand_mod.WORKING` / `DONE` 常量，'
      u'**不写**字面量 `\'working\'`（同一件事两个真相）',
      bool(_uses_const) and not _str_status,
      u'常量=%r 字面量=%r' % (sorted(set(_uses_const)), _str_status))

# ---- C7 催与首次是两处不同赋值 ----


def _str_of(node):
    u"""取"字符串字面量"—— 兼容 `'...' % (a, b)` 这种（`brief` 就是这种形状）。"""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod) \
            and isinstance(node.left, ast.Constant) \
            and isinstance(node.left.value, str):
        return node.left.value
    return None


_brief_strs = []
for n in ast.walk(_ACK):
    if isinstance(n, ast.Assign):
        if any(isinstance(t, ast.Name) and t.id == 'brief' for t in n.targets):
            _s = _str_of(n.value)
            if _s is not None:
                _brief_strs.append(_s)
_has_nudge = [s for s in _brief_strs if u'\u6ca1\u6709\u91cd\u65b0\u8ba1\u65f6' in s]
_has_first = [s for s in _brief_strs if u'\u5df2\u7ecf\u5728\u8def\u4e0a\u4e86' in s]
check(u'C7 ★ 催与首次是**两处不同赋值**（都在 `brief =` 上）'
      u'—— 写成一处就必然分不出"催"和"刚派"',
      len(_has_nudge) == 1 and len(_has_first) == 1
      and _has_nudge[0] != _has_first[0],
      u'催=%d 首次=%d 同串=%s'
      % (len(_has_nudge), len(_has_first),
         bool(_has_nudge and _has_first
              and _has_nudge[0] == _has_first[0])))

# ---- C8 `_errand_same_job` 仍是模块级函数 ----
_toplevel = [n.name for n in TREE.body if isinstance(n, ast.FunctionDef)]
check(u'C8 ★ `_errand_same_job` 仍是**模块级**函数（不是方法：'
      u'写成方法会让第150~153轮那些只挂产品函数的轻宿主当场 `AttributeError`）',
      '_errand_same_job' in _toplevel,
      u'模块级=%s' % ('_errand_same_job' in _toplevel,))

# ================================================ D 自检
mark(u'D 自检：判据名非空字面量 · 只用 check() · 无 BOM 全 LF · 零外部盘')

with io.open(os.path.abspath(__file__), 'r', encoding='utf-8',
             newline='') as _sf:
    SELF = _sf.read()
SELF_TREE = ast.parse(SELF)

_bad_names = []
_n_check = 0
for n in ast.walk(SELF_TREE):
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) \
            and n.func.id == 'check':
        _n_check += 1
        if not n.args or not isinstance(n.args[0], ast.Constant) \
                or not isinstance(n.args[0].value, str) \
                or not n.args[0].value.strip():
            _bad_names.append(getattr(n, 'lineno', -1))
check(u'D0 分母闸：本文件里 `check(` 调用**非空**（否则 D1 是空断言）',
      _n_check > 0, u'处数=%d' % (_n_check,))
check(u'D1 每条判据的说明都是**非空字面量**（不是变量、不是空串、不夹带计数标记）',
      not _bad_names and _n_check >= 30,
      u'坏的=%d 条数=%d' % (len(_bad_names), _n_check))

_ok_calls = 0
for n in ast.walk(SELF_TREE):
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) \
            and n.func.id == 'ok':
        _ok_calls += 1
check(u'D2 只用 `check()`，不用 `ok()`（两套 harness 混用 ⇒ 查恒真会漏一半）',
      _ok_calls == 0, u'ok 调用=%d' % (_ok_calls,))

_crlf = SELF.count('\r\n')
_bare = SELF.count('\n') - _crlf
check(u'D3 无 BOM 且**全 LF**（与本目录其他套件同构）',
      not SELF.startswith(u'\ufeff') and _crlf == 0 and _bare > 0,
      u'BOM=%s CRLF=%d' % (SELF.startswith(u'\ufeff'), _crlf))

_mark_a = u'D' + u':' + u'\\_tmp'
_mark_b = u'E' + u':' + u'\\'
_mark_c = u'C' + u':' + u'\\Users'
_drive = [d for d in (_mark_a, _mark_b, _mark_c) if d in SELF]
check(u'D4 零外部盘：判据本身不引用工作区外的路径（`ROOT` 由 `__file__` 推出）',
      not _drive and os.path.abspath(ROOT) == ROOT,
      u'命中=%d 处' % (len(_drive),))

# ================================================ 汇总
print('')
if _n_fail:
    print('check155：FAIL %d / PASS %d' % (_n_fail, _n_pass))
    for _d in _failed:
        print('  红：%s' % (_d,))
    sys.exit(1)
print('check155：%d 条全过' % (_n_pass,))
sys.exit(0)
