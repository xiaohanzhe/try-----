# -*- coding: utf-8 -*-
u"""第156轮回归锁：**欠账** —— 被改派挤掉、还没办完的那几件事，得记在**状态**里。

## 为什么（第155轮 §9 第 1 条遗留）

用户口径还是那句「**按照人类的逻辑来就好**」。

连着被改派三次的人，会说"我本来要擦柜台、收杯子，都没办完，又被叫去扫地" ——
而第155轮的行为是：**每条痕迹只提"上一件"**（A→B 说 A，B→C 说 B），
最早那件只在**更早那条**痕迹里。

**改前实测**（本轮探针 P1）：

| 量 | 改前 | 后果 |
|---|---|---|
| 三次改派（A→B→C）后的**最后一条**痕迹 | 只含 B、C | 问"柜台擦了吗"，得翻更早那条 |
| 该痕迹进 prompt 的机会 | 记忆只有**最后 12 条**会进 prompt（`history_block(max_lines=12)`） | 2 条痕迹 + 12 句闲聊 ⇒ **整段出窗**，一件都不剩 |

第二条是关键：**欠账是"当前状态"，不是"历史事件"**。历史会被窗口裁掉，状态不会。

## 改后

1. `assign_errand` 改派时把旧那件记进 `self._errand_given_up`，**痕迹写全量**
   （"我本来要 A、B，都没办完，又被派去 C 了"）—— 一条痕迹带三件 > 三条各带一件。
2. `_errand_backlog_brief()` 把欠账折成**一句**系统提示，挂进
   `_build_npc_context`（NPC 线）与 Ralsei 主链的 system 尾部（Ralsei 线）。
   ★ 空账 ⇒ 返回 `''`，调用方**一个字都不加** ⇒ 没被派过差事的人 prompt 逐字不变。
3. 欠账只存**内存**、只提**一天内**的（`ERRAND_GIVEN_UP_TTL`）、最多 8 件
   （`ERRAND_GIVEN_UP_MAX`）、同一件事**去重**。

## 本套件守什么

| 段 | 守什么 |
|---|---|
| A | **真跑**：三次改派 ⇒ 最后一条痕迹含 A/B/C 且**只一条** · 首次派活零痕迹 · 同一件事重说（第155轮短路）**不动**欠账 · 换人互不影响 · 去重 · 上限 8 · TTL 正负成对（23 小时还提 / 25 小时不提）· TTL 不影响已写下的**记忆原话** · 门控拦下（去不了）**不算**被改派 · **办完不清欠账**（正控制）· 空事由退"走一趟" |
| B | **prompt**：brief 有件数与事由 · **空账返回 `''`**（零回归）· `_build_npc_context` 有则加、无则**逐字不变** · Ralsei 链的调用点在 `if _ctx:` 里 · 只陈述事实不写死台词 |
| C | **AST**：欠账只在**派成之后**加 · 在门控拒分支**之外** · 三个函数是**模块级**（本轮第一版写成方法，轻宿主当场 `AttributeError`）· NPC 线用 `npc_id`、Ralsei 线用 `'ralsei'` · `assign_errand` 里**没有** `self._errand_given_up*` 这类方法调用 · 状态只在宿主侧（机制层 `npc_errand.py` 零改动） |
| D | 自检：判据名非空字面量 · 只用 `check()` 不用 `ok()` · 无 BOM 全 LF · 零外部盘 |

★ 判据纪律：`print('[PASS] %s')` 字面量；断行为不断赋值；正/负控制成对；
  零网络 / 零 UI / 零显示器 / 零外部盘。
"""
import ast
import io
import os
import sys
import time as _time

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')
MAIN = os.path.join(PKG, 'src', 'main.py')
ERRAND_MOD = os.path.join(PKG, 'modules', 'npc_errand.py')

for _p in (PKG, os.path.join(PKG, 'src'), os.path.join(PKG, 'modules')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from main import RalseiPet                                  # noqa: E402
from main import (                                          # noqa: E402
    _errand_given_up_add, _errand_given_up_of, _errand_backlog_brief,
    _errand_item_txt, ERRAND_GIVEN_UP_MAX, ERRAND_GIVEN_UP_TTL)
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


def _calls_name(fn, name):
    out = []
    if fn is None:
        return out
    for c in ast.walk(fn):
        if isinstance(c, ast.Call) and isinstance(c.func, ast.Name) \
                and c.func.id == name:
            out.append(c)
    return out


_DEST = 'oneshot.barrens.Blue'
_DEST2 = 'ut.rooms.room_area1'
_DEST3 = 'ch1.hometown.town_mid'
_WHAT = u'\u64e6\u67dc\u53f0'        # 擦柜台
_WHAT2 = u'\u6536\u676f\u5b50'       # 收杯子
_WHAT3 = u'\u6253\u626b\u524d\u9662'  # 打扫前院


class _Mem(object):
    def __init__(self):
        self.log = []

    def remember(self, nid, text, who=None, **kw):
        self.log.append((nid, text, who))

    def save(self, nid):
        pass


class _Host(object):
    u"""轻宿主：挂**产品真函数**（`assign_errand` / `_npc_errand_note` / `_build_npc_context`）。

    ★ 本轮第一版把欠账的三个帮手写成 `RalseiPet` 的**方法** ⇒ 本类（只挂产品函数）
      当场 `AttributeError`（第152轮同款，第 4 次）。现在是**模块级**函数 ⇒ 宿主
      一行都不用改。`C3` 就是钉这件事的。
    """

    _npc_errand_note = RalseiPet._npc_errand_note
    _errand_note = RalseiPet._npc_errand_note
    assign_errand = RalseiPet.assign_errand
    _build_npc_context = RalseiPet._build_npc_context
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
        self._errand_given_up = {}
        self._npc_talking = 'ralsei'
        self.gate_ok = True
        self.acks = []
        self.chats = []

    # ---- 外围桩 ----
    def _npc_errand_gate(self, npc_id, dest):
        return (self.gate_ok, u'' if self.gate_ok else u'\u8fdb\u4e0d\u53bb')

    def _errand_scene_in(self, prefix):
        return {'oneshot': _DEST, 'desktop': 'desktop', 'ut': _DEST2,
                'ch1': _DEST3}.get(prefix)

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


_CLS = _clsdef(TREE, 'RalseiPet')
_ASSIGN = _method(_CLS, 'assign_errand')
_NPCCTX = _method(_CLS, '_build_npc_context')
_TOP = [n.name for n in TREE.body if isinstance(n, ast.FunctionDef)]

_T = _time.time()


def _notes(h):
    return [row[1] for row in h.npc_memory.log]


# ================================================ A 真跑
mark(u'A 真跑：三次改派的痕迹含全部欠账 / 只一条 / 首次零条 / '
     u'重说不动 / 换人隔离 / 去重 / 上限 / TTL / 门控不算 / 办完不清')

check(u'A0 分母闸：`assign_errand` / `_build_npc_context` / 欠账三个函数**都在**'
      u'（缺一个后面全是空断言）',
      _ASSIGN is not None and _NPCCTX is not None
      and '_errand_given_up_add' in _TOP
      and '_errand_given_up_of' in _TOP
      and '_errand_backlog_brief' in _TOP,
      u'缺=%d 个' % (len([n for n in ('_errand_given_up_add',
                                     '_errand_given_up_of',
                                     '_errand_backlog_brief')
                                    if n not in _TOP]),))

_h = _Host()
_h.assign_errand('ralsei', _DEST, _WHAT, now=_T)
_h.assign_errand('ralsei', _DEST2, _WHAT2, now=_T + 10)
_h.assign_errand('ralsei', _DEST3, _WHAT3, now=_T + 20)
_n1 = _notes(_h)
_t1 = _n1[-1] if _n1 else u''

check(u'A1 ★★ 三次改派之后，**最后一条**痕迹把三件事全写进去了'
      u'（改前只写"上一件 + 新一件" ⇒ 最早那件得翻更早的那条痕迹）',
      len(_n1) == 2 and all(x in _t1 for x in (_DEST, _WHAT, _DEST2, _WHAT2,
                                               _DEST3, _WHAT3)),
      u'条数=%d 含三件=%s' % (len(_n1), all(x in _t1 for x in (_WHAT, _WHAT2, _WHAT3))))
check(u'A2 一次改派仍然只留**一条**痕迹（别为了"写全"变成一次写三条）',
      len(_n1) == 2, u'条数=%d（3 次派活 = 1 次首次 + 2 次改派）' % (len(_n1),))
check(u'A3 欠账里现在有 **2 件**（A 与 B；C 还在办，不算欠账）',
      len(_errand_given_up_of(_h, 'ralsei', now=_T + 30)) == 2,
      u'件数=%d' % (len(_errand_given_up_of(_h, 'ralsei', now=_T + 30)),))

_h3 = _Host()
_h3.assign_errand('ralsei', _DEST, _WHAT, now=_T)
check(u'A4 首次派活 ⇒ **零痕迹**、欠账为空（负控制：别把"当前这件"也算成欠账）',
      len(_notes(_h3)) == 0
      and _errand_given_up_of(_h3, 'ralsei', now=_T + 1) == [],
      u'痕迹=%d' % (len(_notes(_h3)),))

# ---- A5 第155轮的"催"不许动欠账 ----
_h5 = _Host()
_h5.assign_errand('ralsei', _DEST, _WHAT, now=_T)
_h5.assign_errand('ralsei', _DEST2, _WHAT2, now=_T + 10)
_before5 = _errand_given_up_of(_h5, 'ralsei', now=_T + 11)
_h5.assign_errand('ralsei', _DEST2, _WHAT2, now=_T + 12)      # 同一件事重说 = 催
_after5 = _errand_given_up_of(_h5, 'ralsei', now=_T + 13)
check(u'A5 ★ **同一件事重说（催）不动欠账**（不加也不减）—— '
      u'第155轮的短路在这里必须仍然有效',
      _before5 == _after5 and len(_after5) == 1,
      u'前=%d 后=%d' % (len(_before5), len(_after5)))

# ---- A6 换人互不影响 ----
_h6 = _Host()
_h6.assign_errand('ralsei', _DEST, _WHAT, now=_T)
_h6.assign_errand('ralsei', _DEST2, _WHAT2, now=_T + 10)
_h6.assign_errand('susie', _DEST3, _WHAT3, now=_T + 20)
check(u'A6 换一个人派活 ⇒ **别人一条、他一堆**（记忆与欠账都不串味）',
      _errand_given_up_of(_h6, 'ralsei', now=_T + 30) != []
      and _errand_given_up_of(_h6, 'susie', now=_T + 30) == [],
      u'ralsei=%d susie=%d'
      % (len(_errand_given_up_of(_h6, 'ralsei', now=_T + 30)),
         len(_errand_given_up_of(_h6, 'susie', now=_T + 30))))

# ---- A7 去重：派回同一件事不该记两笔 ----
#
# ★ 为什么是 **4 次**派活（A→B→A→B）而不是 3 次：
#   欠账记的是"**被挤掉**的那件"，所以 A→B→A 只发生 2 次改派 ⇒ 欠账天然是
#   `[A（被 B 挤掉）, B（被 A 挤掉）]`，末项就该是 **B**（第一版判据写成 A，
#   是判据自己算错了）。真要验"派回同一件事不记两笔"，得让 A 被挤掉**两次**。
_h7 = _Host()
_h7.assign_errand('ralsei', _DEST, _WHAT, now=_T)
_h7.assign_errand('ralsei', _DEST2, _WHAT2, now=_T + 10)   # A 被挤掉 → 欠账 [A]
_h7.assign_errand('ralsei', _DEST, _WHAT, now=_T + 20)     # B 被挤掉 → 欠账 [A,B]
_h7.assign_errand('ralsei', _DEST2, _WHAT2, now=_T + 30)   # A 又被挤掉 → 去重仍 [B,A]
_item7 = _errand_given_up_of(_h7, 'ralsei', now=_T + 40)
check(u'A7 **去重**：A 被挤掉两次之后只出现一次，且挪到最后（最近一次为准）',
      len(_item7) == 2 and _item7[0] == (_DEST2, _WHAT2)
      and _item7[-1] == (_DEST, _WHAT),
      u'件数=%d 末项对=%s' % (len(_item7),
                             bool(_item7) and _item7[-1] == (_DEST, _WHAT)))

# ---- A8 上限 ----
_h8 = _Host()
_h8.assign_errand('ralsei', _DEST, _WHAT, now=_T)
for i in range(10):
    _h8.assign_errand('ralsei', '%s#%d' % (_DEST2, i), u'\u7b2c%d\u4ef6' % (i,),
                      now=_T + 10 + i)
_n8 = len(_errand_given_up_of(_h8, 'ralsei', now=_T + 100))
# ★ 为什么是 `==` 而不是 `<=`：第一版写 `_n8 <= ERRAND_GIVEN_UP_MAX` ——
#   分子分母都是同一个常量 ⇒ 把上限从 8 调到 20，`_n8`（10）照样 <= 20 **还是绿**。
#   那是一条"看着在守截断、其实没守"的判据（第85/134/136轮同族）。
#   ⇒ 改成"恰好等于上限"（10 件被截到 8）+ "少于 10"（截断真的发生了）。
check(u'A8 连改 10 次 ⇒ 欠账**恰好被截到上限**（不截就是 10 件，多到不是人话）',
      _n8 == ERRAND_GIVEN_UP_MAX and _n8 < 10,
      u'件数=%d 上限=%d' % (_n8, ERRAND_GIVEN_UP_MAX))

# ---- A9 TTL 正负成对 ----
_h9 = _Host()
_h9.assign_errand('ralsei', _DEST, _WHAT, now=_T)
_h9.assign_errand('ralsei', _DEST2, _WHAT2, now=_T + 10)
_in9 = _errand_given_up_of(_h9, 'ralsei', now=_T + 10 + 82800)   # 23 小时
_out9 = _errand_given_up_of(_h9, 'ralsei', now=_T + 10 + 90000)  # 25 小时
check(u'A9 ★ TTL 正负成对：**23 小时内**还提得到、**25 小时**就不再提'
      u'（陈年旧账挂在嘴边是噪声）',
      len(_in9) == 1 and _out9 == [],
      u'23h=%d 25h=%d TTL=%.0f' % (len(_in9), len(_out9), ERRAND_GIVEN_UP_TTL))
check(u'A9b TTL 只影响**提不提**，不动已经写下的**记忆原话**'
      u'（记忆是"当时发生的事"，不按 TTL 删）',
      len(_notes(_h9)) == 1 and _WHAT in _notes(_h9)[0],
      u'痕迹=%d' % (len(_notes(_h9)),))

# ---- A10 门控拦下（去不了）不算"被改派" ----
_h10 = _Host()
_h10.assign_errand('ralsei', _DEST, _WHAT, now=_T)
_h10.assign_errand('ralsei', _DEST2, _WHAT2, now=_T + 10)
_h10.gate_ok = False
_r10 = _h10.assign_errand('ralsei', _DEST3, _WHAT3, now=_T + 20)
check(u'A10 门控拒（"去不了"）⇒ **不加**欠账（他不是被改派，是被拦下）'
      u'且不写"被改派"的痕迹',
      _r10 is None
      and len(_errand_given_up_of(_h10, 'ralsei', now=_T + 30)) == 1
      and len(_notes(_h10)) == 2,
      u'欠账=%d 痕迹=%d'
      % (len(_errand_given_up_of(_h10, 'ralsei', now=_T + 30)), len(_notes(_h10))))

# ---- A11 办完不清欠账（正控制）----
_h11 = _Host()
_h11.assign_errand('ralsei', _DEST, _WHAT, now=_T)
_h11.assign_errand('ralsei', _DEST2, _WHAT2, now=_T + 10)
_h11.npc_errand.step(_T + 10 + 400)     # 到点 + 办完
_after11 = _errand_given_up_of(_h11, 'ralsei', now=_T + 500)
check(u'A11 ★ 他把手上这件**办完**了，欠的那几件**照样欠着**'
      u'（正控制：别用"这轮结束"把旧账一笔勾销）',
      len(_h11.npc_errand.done) == 1 and len(_after11) == 1,
      u'done=%d 欠账=%d' % (len(_h11.npc_errand.done), len(_after11)))

# ---- A12 空事由退"走一趟" ----
_h12 = _Host()
_h12.assign_errand('ralsei', _DEST, u'', now=_T)
_h12.assign_errand('ralsei', _DEST2, u'', now=_T + 10)
_t12 = (_notes(_h12)[-1] if _notes(_h12) else u'')
check(u'A12 事由为空 ⇒ 文案退成人话「走一趟」，**不许**出现「办「」」这种空壳',
      _t12 and u'\u8d70\u4e00\u8d9f' in _t12 and u'\u529e\u300c\u300d' not in _t12,
      u'含走一趟=%s' % (u'\u8d70\u4e00\u8d9f' in _t12,))

# ================================================ B prompt
mark(u'B prompt：brief 有件数与事由 / 空账返回空串（零回归）/ NPC 上下文有则加、'
     u'无则逐字不变 / Ralsei 链挂在 if _ctx 里')

_hb = _Host()
_hb.assign_errand('ralsei', _DEST, _WHAT, now=_T)
_hb.assign_errand('ralsei', _DEST2, _WHAT2, now=_T + 10)
# ★ 必须派**三次**：欠账记"被挤掉的那件"，两次派活只有 1 件欠账 ——
#   第一版只派两次却断言"2 件"，是判据自己数错（A3 就是三次派活得 2 件）。
_hb.assign_errand('ralsei', _DEST3, _WHAT3, now=_T + 20)
_b1 = _errand_backlog_brief(_hb, 'ralsei', now=_T + 30)
check(u'B0 分母闸：有欠账时 brief **非空**（否则 B1/B2 全是空断言）',
      bool(_b1), u'长度=%d' % (len(_b1),))
check(u'B1 ★ brief 里写明**件数**与**每一件事由**（"2 件" + 两件都在）',
      u'2 \u4ef6' in _b1 and _WHAT in _b1 and _WHAT2 in _b1,
      u'含2件=%s' % (u'2 \u4ef6' in _b1,))
check(u'B2 ★★ **没欠账 ⇒ 返回空串**（零回归的根：返回 "" 时调用方一个字都不加）',
      _errand_backlog_brief(_Host(), 'ralsei', now=_T) == u'',
      u'空=%s' % (_errand_backlog_brief(_Host(), 'ralsei', now=_T) == u'',))
check(u'B3 brief 只给**事实**，把"提不提"交回模型（不许写死一句台词）',
      u'\u7531\u4f60\u81ea\u5df1\u51b3\u5b9a' in _b1,
      u'含"由你自己决定"=%s' % (u'\u7531\u4f60\u81ea\u5df1\u51b3\u5b9a' in _b1,))

_ctx_have = _hb._build_npc_context('ralsei')
_ctx_none = _Host()._build_npc_context('ralsei')
check(u'B4a 分母闸：两份上下文都非空、且**确实不同**'
      u'（否则"有没有那句"就是恒真）',
      bool(_ctx_have) and bool(_ctx_none) and _ctx_have != _ctx_none,
      u'同值=%s' % (_ctx_have == _ctx_none,))
check(u'B4 ★ 有欠账时 NPC 上下文里**带上了**它（问"柜台擦了吗"时他读得到）',
      u'\u6ca1\u529e\u5b8c\u5c31\u88ab\u53eb\u8d70' in _ctx_have
      and _WHAT in _ctx_have,
      u'含欠账=%s' % (u'\u6ca1\u529e\u5b8c\u5c31\u88ab\u53eb\u8d70' in _ctx_have,))
check(u'B5 ★★ 没欠账时 NPC 上下文**只有【此刻】那一段**（逐字不变 ⇒ 零回归）',
      _ctx_none.startswith(u'\u3010\u6b64\u523b\u3011')
      and u'\u6b20' not in _ctx_none
      and len(_ctx_none.splitlines()) == 1,
      u'行数=%d' % (len(_ctx_none.splitlines()),))

# ---- B6 Ralsei 链：调用点在 `if _ctx:` 里 ----
_leaf = None
for n in ast.walk(TREE):
    if isinstance(n, ast.If):
        for c in ast.walk(n):
            if isinstance(c, ast.Call) and isinstance(c.func, ast.Name) \
                    and c.func.id == '_errand_backlog_brief':
                _leaf = n
check(u'B6 ★ Ralsei 主链的欠账挂在 `if _ctx:` **里面**'
      u'（lean / `_sys_fixed` 走不进来 ⇒ 事件台词逐字节稳定、缓存不被打掉）',
      _leaf is not None,
      u'找到挂点=%s' % (_leaf is not None,))

# ================================================ C AST
mark(u'C AST：只在派成之后加 · 在门控拒分支之外 · 三个函数是模块级 · '
     u'两条线各用各的 id · 宿主侧无方法调用 · 机制层零改动')

_ln_add = [c.lineno for c in _calls_name(_ASSIGN, '_errand_given_up_add')]
_ln_assign = [c.lineno for c in _calls(_ASSIGN, 'assign')]
check(u'C0 分母闸：`assign_errand` 里找得到 `_errand_given_up_add` 与 `board.assign`',
      bool(_ln_add) and bool(_ln_assign),
      u'add=%d assign=%d' % (len(_ln_add), len(_ln_assign)))
check(u'C1 ★ 欠账只在**派成之后**加（`board.assign` 之前加 = 派发失败也记一笔"被挤掉"）',
      bool(_ln_add) and bool(_ln_assign) and min(_ln_add) > min(_ln_assign),
      u'之前=%s' % (bool(_ln_add) and bool(_ln_assign)
                   and min(_ln_add) < min(_ln_assign),))

# ★ 门控那一支在产品里的形状：
#     ok, why = self._npc_errand_gate(npc_id, dest_scene)   ← 门控调用在**赋值**里
#     if not ok:                                           ← test 只是 `Not(Name)`
#         ... 写「我本来要去 X，但去不了」...
#         return None
#   ⇒ 第一版判据在 `If.test` 里找 `_npc_errand_gate`，**永远找不到**（判据写窄，
#     不是产品错 —— 报红先怀疑判据）。改成：先定位门控调用，再取它**之后第一个**
#     顶层 `If`；并用"这一支里真的 `return`"当分母闸，防止取到别的 `If` 还以为在守。
_gate_call = None
for _c in _calls(_ASSIGN, '_npc_errand_gate'):
    _gate_call = _c
    break
_gate_if = None
if _gate_call is not None:
    _cand = [n for n in _ASSIGN.body
             if isinstance(n, ast.If) and n.lineno >= _gate_call.lineno]
    if _cand:
        _gate_if = min(_cand, key=lambda n: n.lineno)
_gate_returns = bool(
    _gate_if is not None
    and any(isinstance(s, ast.Return) for s in _gate_if.body))
_in_gate = False
if _gate_if is not None:
    for c in ast.walk(_gate_if):
        if isinstance(c, ast.Call) and isinstance(c.func, ast.Name) \
                and c.func.id == '_errand_given_up_add':
            _in_gate = True
check(u'C2 ★ 欠账**不在**门控拒那一支里（"去不了"不是"被改派"）',
      _gate_if is not None and _gate_returns and not _in_gate,
      u'定位到拒支=%s 确是拒支=%s 支内=%s'
      % (_gate_if is not None, _gate_returns, _in_gate))

check(u'C3 ★★ 三个欠账函数是**模块级**（第一版写成方法 ⇒ 第150~155轮的轻宿主'
      u'当场 `AttributeError`，第152轮同款第 4 次）',
      all(n in _TOP for n in ('_errand_given_up_add', '_errand_given_up_of',
                              '_errand_backlog_brief', '_errand_item_txt')),
      u'模块级=%s' % (all(n in _TOP for n in (
          '_errand_given_up_add', '_errand_given_up_of',
          '_errand_backlog_brief', '_errand_item_txt')),))

_args_ctx = []
for c in _calls_name(_NPCCTX, '_errand_backlog_brief'):
    for a in c.args[1:]:
        _args_ctx.append(getattr(a, 'id', None))
check(u'C4 NPC 线用的是**传进来的 `npc_id`**（写死成某个人 = 串味）',
      _args_ctx == ['npc_id'], u'实参=%r' % (_args_ctx,))

_sel_ralsei = []
for n in ast.walk(TREE):
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) \
            and n.func.id == '_errand_backlog_brief':
        for a in n.args[1:]:
            if isinstance(a, ast.Constant) and isinstance(a.value, str):
                _sel_ralsei.append(a.value)
check(u'C5 Ralsei 线用的是 `\'ralsei\'`（主链路那个人）',
      _sel_ralsei == ['ralsei'], u'字面量=%r' % (_sel_ralsei,))

_self_methods = []
for c in ast.walk(_ASSIGN):
    if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute) \
            and getattr(c.func.value, 'id', None) == 'self' \
            and c.func.attr.startswith('_errand_given_up'):
        _self_methods.append(c.func.attr)
check(u'C6 `assign_errand` 里**没有** `self._errand_given_up*` 这种方法调用'
      u'（全走模块级函数）',
      not _self_methods, u'方法调用=%r' % (_self_methods,))

_mod_src = io.open(ERRAND_MOD, 'r', encoding='utf-8').read()
check(u'C7 状态**只在宿主侧**：机制层 `npc_errand.py` 里**不出现** `given_up`'
      u'（差事的存档格式与 `WIRING` 契约都没动）',
      'given_up' not in _mod_src and 'GIVEN_UP' not in _mod_src,
      u'机制层命中=%d' % (_mod_src.count('given_up'),))

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
check(u'D0 分母闸：本文件里 `check(` 调用**非空**',
      _n_check > 0, u'处数=%d' % (_n_check,))
check(u'D1 每条判据的说明都是**非空字面量**（不是变量、不是空串）',
      not _bad_names and _n_check >= 28,
      u'坏的=%d 条数=%d' % (len(_bad_names), _n_check))

_n_ok = 0
for n in ast.walk(SELF_TREE):
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) \
            and n.func.id == 'ok':
        _n_ok += 1
check(u'D2 只用 `check()`，不用 `ok()`（两套 harness 混用 ⇒ 查恒真会漏一半）',
      _n_ok == 0, u'ok 调用=%d' % (_n_ok,))

_crlf = SELF.count('\r\n')
check(u'D3 无 BOM 且**全 LF**（与本目录其他套件同构）',
      not SELF.startswith(u'\ufeff') and _crlf == 0,
      u'BOM=%s CRLF=%d' % (SELF.startswith(u'\ufeff'), _crlf))

_mark_a = u'D' + u':' + u'\\_tmp'
_mark_b = u'E' + u':' + u'\\'
_mark_c = u'C' + u':' + u'\\Users'
_drive = [d for d in (_mark_a, _mark_b, _mark_c) if d in SELF]
check(u'D4 零外部盘：判据本身不引用工作区外的路径（`ROOT` 由 `__file__` 推出）',
      not _drive, u'命中=%d 处' % (len(_drive),))

# ================================================ 汇总
print('')
if _n_fail:
    print('check156：FAIL %d / PASS %d' % (_n_fail, _n_pass))
    for _d in _failed:
        print('  红：%s' % (_d,))
    sys.exit(1)
print('check156：%d 条全过' % (_n_pass,))
sys.exit(0)
