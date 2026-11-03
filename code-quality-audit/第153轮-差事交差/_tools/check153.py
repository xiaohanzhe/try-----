# -*- coding: utf-8 -*-
u"""第153轮回归锁：**办完交差** —— 差事要闭环（派得出去 · 叫得回来 · **办完有交代**）。

## 为什么要这个口子（用户口径逐字）

> 「我让 ralsei 去 oneshot 里干什么事情，**他能去，干，然后产生结果**，
>    甚至**我中途进去的时候也能看到过程**」

第150轮做了「派得出去、路上有过程」，第152轮做了「叫得回来」。
但**办完那一端是断的**：`_npc_errand_tick` 的 `finished` 分支只做两件事 ——
`roam.drop()`（回家）+ `_npc_errand_commit()`（把结果写进**他自己**的记忆）。
而 `board.result_of()` / `board.take_results()` 在**整个仓库里零调用**

⇒ 结果只存在于他脑子里：他"办完了"，**用户永远等不到一句交代**。
「产生结果」在用户那边看起来就是"人没了，然后回来，什么也没说"。

## 本轮补的那一句（`_errand_report_ack`）

| 要点 | 为什么 |
|---|---|
| 走 `chat_with_ai(brief, …)` + `_errand_show_reply`（与两条既有 ack 同规） | **不用** `npc_speak()`：它的入参是"对方说的那句话"，会以 `who='player'` 记进记忆，没有"系统提示"通道 ⇒ 塞 brief 进去等于伪造一句玩家发言 |
| `remember=False` | 结果已由 `_npc_errand_commit` 记过 ⇒ 再记一次就是同一件事两条 |
| 说话人只能是**办事的那个人**；没装人设 ⇒ **不开口** | **不许**像 `_errand_ack` 那样回落成 Ralsei：那会让 Ralsei 用第一人称替别人汇报（串味比沉默坏得多） |
| `result` 为空 ⇒ 不开口 | 没结果就没得交差（"办完了"这种空话，正是第152轮明令不许造的假结果） |
| brief 里带"用户此刻在哪" | 用户不在他刚去过的地方时，模型自己会说人话（不必强塞"我回来了"） |

## 本套件守什么

| 段 | 守什么 |
|---|---|
| A | **tick 真跑**：办完 ⇒ 交代**恰好一次** · 再推不重复 · 没办完/被叫停/被门控拦下 ⇒ **零交代** · 顺序 `drop → commit → report` · 关总开关 ⇒ 零交代 |
| B | **交差本身**（真跑 `_errand_report_ack`）：`speaker`/`remember=False` 对 · 没 persona 不开口 · 空结果不开口 · 模型不可用不开口 · brief 随"用户在哪"变 · 显示用**办事人**的 id |
| C | **AST**：`drop < commit < report` · 不走 `npc_speak` · 体内**无** `remember(` · 全仓只有**一**处调用 · 两道闸（`_npc_ai_available` / `npc_persona_of`）在体内 |
| D | 自检：判据名非空字面量 · 无 BOM · 裸 LF=0 · 零外部盘 · 只用 `check()` 不用 `ok()` |

★ 判据纪律：`print('[PASS] %s')` 字面量；断行为不断赋值；正/负控制成对；
  零网络 / 零 UI / 零显示器 / 零外部盘；`chat_with_ai` 与 `dialogue_ui` 都是**桩**。
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
_PLACES = {_DEST: u'oneshot 的荒漠', 'desktop': u'桌面', 'ut.rooms.room_area1': u'遗迹'}


class _Mem(object):
    u"""`npc_memory` 的最小替身：**记下每次 remember**（= 结果进记忆的行为证据）。"""

    def __init__(self, events=None):
        self.log = []
        self.events = events

    def remember(self, nid, text, who=None, **kw):
        self.log.append((nid, text, who))
        if self.events is not None:
            self.events.append('commit')

    def save(self, nid):
        pass


class _Cur(object):
    def __init__(self, scene):
        self.scene = scene


class _Roam(object):
    def __init__(self, events=None):
        self.tbl = {}
        self.puts = []
        self.drops = []
        self.events = events

    def get(self, nid):
        return self.tbl.get(nid)

    def put(self, nid, scene, now, reason=''):
        self.tbl[nid] = _Cur(scene)
        self.puts.append((nid, scene, reason))

    def drop(self, nid):
        self.tbl.pop(nid, None)
        self.drops.append(nid)
        if self.events is not None:
            self.events.append('drop')


class _UI(object):
    def __init__(self):
        self.calls = []

    def add_dialogue(self, who, text, kind='normal'):
        self.calls.append((who, text, kind))

    def show_dialogue(self):
        pass


class _Host(object):
    u"""轻宿主：把**产品里那几个真函数**挂上来跑（不启 Qt、不联网）。

    ★ `_errand_report_ack` / `_errand_show_reply` 用**真**的 —— 本轮就是给它写锁，
      拿桩替掉等于自己给自己盖章。桩只打在外围：`chat_with_ai`（会连 7B）、
      `dialogue_ui`（要 QMainWindow）、`npc_persona_of`（要读 assets）。
    """

    _npc_errand_tick = RalseiPet._npc_errand_tick
    _npc_errand_commit = RalseiPet._npc_errand_commit
    _errand_report_ack = RalseiPet._errand_report_ack
    _errand_show_reply = RalseiPet._errand_show_reply
    assign_errand = RalseiPet.assign_errand
    cancel_errand = RalseiPet.cancel_errand
    _npc_errand_note = RalseiPet._npc_errand_note

    def __init__(self, enabled=True, events=None):
        self.npc_registry = NS.load_registry()
        self._npc_aliases = NP.address_aliases(
            [(n.id, n.name, n.name_cn) for n in self.npc_registry.all()])
        self.npc_errand = ER.ErrandBoard(enabled=enabled)
        self.npc_memory = _Mem(events)
        self.npc_roam = _Roam(events)
        self.dialogue_ui = _UI()
        self.events = events
        self.chats = []
        self.ai_ok = True
        self.gate_ok = True
        self.cur_scene = 'desktop'
        self.personas = {'susie': u'\u4f60\u662f\u82cf\u897f', 'ralsei': None}
        self.models = {}
        self._npc_talking = 'ralsei'

    # ---- 外围桩 ----
    def chat_with_ai(self, text, on_reply, on_delta=None, speaker=None,
                     remember=True, model=None):
        self.chats.append({'text': text, 'speaker': speaker,
                           'remember': remember, 'model': model})
        if self.events is not None:
            self.events.append('report')
        if on_reply is not None:
            on_reply(u'\u56de\u6765\u4e86\uff0c\u4e8b\u513f\u529e\u5b8c\u4e86\u3002')
        return True

    def _npc_ai_available(self):
        return self.ai_ok

    def npc_persona_of(self, npc_id):
        return self.personas.get(npc_id)

    def npc_label(self, npc_id):
        return {'susie': u'\u82cf\u897f', 'ralsei': u'Ralsei',
                'os_niko': u'Niko'}.get(npc_id, npc_id)

    def _npc_model(self, npc_id):
        return self.models.get(npc_id)

    def _errand_place_label(self, scene_id):
        # ★ 与产品同形：**查不到就原样回**（取不到场景时回 `None`，不是空串）——
        #   第一版写成 `scene_id or u''` 把 `None` 变成了空串，于是
        #   `M14`（去掉兜底）**不报红**：桩把要测的那个值提前吃掉了（夹具不保真）。
        return _PLACES.get(scene_id, scene_id)

    def _npc_scene_id(self):
        return self.cur_scene

    def _npc_errand_gate(self, npc_id, dest):
        return (self.gate_ok, u'' if self.gate_ok else u'进不去')

    def _npc_carried_ids(self):
        return []

    def _npc_seed_bodies(self, scene_id=None):
        pass

    def _npc_plan_save(self, force=False):
        return True

    def _npc_errand_save(self, force=False):
        return True


_CLS = _clsdef(TREE, 'RalseiPet')
_TICK = _method(_CLS, '_npc_errand_tick')
_REPORT = _method(_CLS, '_errand_report_ack')

_u_what = u'\u64e6\u67dc\u53f0'
_u_result = u'\u67dc\u53f0\u64e6\u5e72\u51c0\u4e86\uff0c\u8d26\u672c\u4e5f\u5bf9\u4e0a\u4e86\u3002'

# ================================================ A tick 真跑：办完才有交代
mark(u'A tick：办完 ⇒ 交代**恰好一次**；没办完 / 被叫停 / 被门控 / 关闸 ⇒ 零交代')

check(u'A0 分母闸：`_npc_errand_tick` 与 `_errand_report_ack` **都在**（缺一个后面全是空断言）',
      _TICK is not None and _REPORT is not None,
      u'成立=%s' % (_TICK is not None and _REPORT is not None,))

# ---- A1 正控制：办完 ⇒ 交代一句，且**先回家** ----
_ev1 = []
_h1 = _Host(events=_ev1)
_h1.assign_errand('ralsei', _DEST, _u_what, now=0.0, travel=10.0, work=100.0,
                  result=_u_result)
_h1._npc_errand_tick(10.0)
_mid = len(_h1.chats)                       # 刚到达：还没办完
_h1._npc_errand_tick(110.0)
check(u'A1 ★ 办完 ⇒ **交代一句**（正控制：不交代就说明这轮等于没做）',
      _mid == 0 and len(_h1.chats) == 1,
      u'到达时=%d / 办完后=%d' % (_mid, len(_h1.chats)))
check(u'A1b 交代的话里**带着结果**（不是"我回来了"这种没有信息量的空话）',
      bool(_h1.chats) and _h1.chats[0]['text'].find(_u_result) >= 0,
      u'含结果=%s' % (bool(_h1.chats) and _h1.chats[0]['text'].find(_u_result) >= 0,))
check(u'A1c 交代**之前**先回家（位置覆盖已撤）',
      _h1.npc_roam.drops == ['ralsei'] and _h1.npc_roam.get('ralsei') is None,
      u'drops=%s' % (_h1.npc_roam.drops,))

# ---- A2 再推两拍 ⇒ 不重复交代 ----
#   ★ 断言的是"**没有新增**"，不是"总数等于 1"：后者会把 A1 的失败也算到 A2 头上，
#     两条判据就变成同一条信号的两种写法（第134轮的教训：分母混了就测不出东西）。
_n_before_a2 = len(_h1.chats)
_h1._npc_errand_tick(200.0)
_h1._npc_errand_tick(400.0)
check(u'A2 ★ 再推两拍**不重复交代**（`finished` 只在跃迁那一拍出现 ⇒ 天然一次性）',
      len(_h1.chats) == _n_before_a2,
      u'新增=%d' % (len(_h1.chats) - _n_before_a2,))

# ---- A3 负控制：叫停的差事**不许**交差 ----
_h3 = _Host()
_h3.assign_errand('ralsei', _DEST, _u_what, now=0.0, travel=10.0, work=100.0)
_h3._npc_errand_tick(10.0)
_h3.cancel_errand('ralsei')
_h3._npc_errand_tick(999.0)
check(u'A3 ★ 被**叫停**的差事零交代（作废 ≠ 办完，不许凭空说"办完了"）',
      len(_h3.chats) == 0 and _h3.npc_errand.result_of('ralsei') == '',
      u'交代=%d / 结果=%r' % (len(_h3.chats), _h3.npc_errand.result_of('ralsei')))

# ---- A4 负控制：还在路上 ⇒ 零交代（只到"到达"也不够） ----
_h4 = _Host()
_h4.assign_errand('ralsei', _DEST, _u_what, now=0.0, travel=10.0, work=100.0)
_h4._npc_errand_tick(5.0)
check(u'A4 还在路上 ⇒ 零交代（没办完就没得交差）',
      len(_h4.chats) == 0, u'交代=%d' % (len(_h4.chats),))

# ---- A5 顺序定死：drop → commit → report ----
check(u'A5 ★★ 顺序 `回家 → 记住 → 开口`（反了就是"话先到、人还在外头、他自己还没记住"）',
      _ev1[:3] == ['drop', 'commit', 'report'],
      u'实得=%s' % (_ev1[:3],))

# ---- A6 被门控拦下 ⇒ 零交代（走 abort，不进 done） ----
_h6 = _Host()
_h6.assign_errand('ralsei', _DEST, _u_what, now=0.0, travel=10.0, work=100.0)
_h6._npc_errand_tick(10.0)
_h6.gate_ok = False
_h6._npc_errand_tick(20.0)
check(u'A6 ★ 中途被门控拦下 ⇒ **零交代**（去不了要留"去不了"，不是"办完了"）',
      len(_h6.chats) == 0 and len(_h6.npc_errand) == 0,
      u'交代=%d / 在办=%d' % (len(_h6.chats), len(_h6.npc_errand)))

# ---- A7 关总开关 ⇒ tick 根本不跑 ----
_h7 = _Host()
_h7.assign_errand('ralsei', _DEST, _u_what, now=0.0, travel=10.0, work=100.0)
_old_sw = RalseiPet.NPC_ERRAND_ENABLED
try:
    RalseiPet.NPC_ERRAND_ENABLED = False
    _h7._npc_errand_tick(999.0)
finally:
    RalseiPet.NPC_ERRAND_ENABLED = _old_sw
check(u'A7 总开关关掉 ⇒ 零交代且差事原地不动（关闸不是"静默办完"）',
      len(_h7.chats) == 0 and len(_h7.npc_errand) == 1,
      u'交代=%d / 在办=%d / 开关已还原=%s'
      % (len(_h7.chats), len(_h7.npc_errand),
         RalseiPet.NPC_ERRAND_ENABLED is _old_sw))

# ================================================ B 交差本身
mark(u'B 交差本身：说话人对 / 不重复记 / 没设定就不许借别人的口气 / 空结果与模型闸')


def _fresh(**kw):
    h = _Host()
    for k, v in kw.items():
        setattr(h, k, v)
    return h


# ---- B0 正控制：真函数确实会发起一次生成 ----
_b0 = _fresh()
_b0._errand_report_ack('ralsei', _DEST, _u_what, _u_result)
check(u'B0 正控制：`ralsei` ⇒ 发起**一次**生成',
      len(_b0.chats) == 1, u'发起=%d' % (len(_b0.chats),))

# ---- B1 说话人与记忆 ----
_c = _b0.chats[0] if _b0.chats else {}
check(u'B1 ★ `ralsei` ⇒ `speaker=None`（主链路用人设文件，不能硬传 id）',
      _c.get('speaker', 'x') is None, u'speaker=%r' % (_c.get('speaker', 'x'),))
check(u'B1b ★ `remember=False`（结果已由 commit 记过 ⇒ 不许同一件事记两条）',
      _c.get('remember', 'x') is False, u'remember=%r' % (_c.get('remember', 'x'),))

# ---- B2 有设定的 NPC：说话人就是他自己 ----
_b2 = _fresh()
_b2.models = {'susie': 'susie:v1'}
_b2._errand_report_ack('susie', _DEST, _u_what, _u_result)
_c2 = _b2.chats[0] if _b2.chats else {}
check(u'B2 装了设定的 NPC ⇒ `speaker=他自己` 且用**他自己的模型**',
      len(_b2.chats) == 1 and _c2.get('speaker') == 'susie'
      and _c2.get('model') == 'susie:v1',
      u'speaker=%r / model=%r' % (_c2.get('speaker'), _c2.get('model')))

# ---- B3 ★ 没设定 ⇒ 不开口（不许借 Ralsei 的口气） ----
_b3 = _fresh()
_b3._errand_report_ack('nobody_xyz', _DEST, _u_what, _u_result)
check(u'B3 ★★ 没装设定的 NPC ⇒ **一个字都不说**'
      u'（回落成 Ralsei 会让"我办完了"出现在 Ralsei 嘴里 = 串味）',
      len(_b3.chats) == 0, u'发起=%d' % (len(_b3.chats),))

# ---- B4 空结果 ⇒ 不开口 ----
_b4 = _fresh()
_b4._errand_report_ack('ralsei', _DEST, _u_what, u'')
_b4._errand_report_ack('ralsei', _DEST, _u_what, u'   ')
check(u'B4 结果为空/全空白 ⇒ 不开口（"办完了"这种没有内容的交代 = 假结果）',
      len(_b4.chats) == 0, u'发起=%d' % (len(_b4.chats),))

# ---- B5 模型不可用 ⇒ 不开口 ----
_b5 = _fresh()
_b5.ai_ok = False
_b5._errand_report_ack('ralsei', _DEST, _u_what, _u_result)
check(u'B5 模型不可用 ⇒ 不发起（不是"发了一个不会回来的请求"）',
      len(_b5.chats) == 0, u'发起=%d' % (len(_b5.chats),))

# ---- B6 brief 随"用户此刻在哪"变（A/B 先断言 A≠B） ----
_ba = _fresh()
_ba.cur_scene = 'desktop'
_ba._errand_report_ack('ralsei', _DEST, _u_what, _u_result)
_bb = _fresh()
_bb.cur_scene = 'ut.rooms.room_area1'
_bb._errand_report_ack('ralsei', _DEST, _u_what, _u_result)
_ta = _ba.chats[0]['text'] if _ba.chats else u'<A>'
_tb = _bb.chats[0]['text'] if _bb.chats else u'<B>'
check(u'B6 两组输入先证明**确实不同**（否则下面的"跟着变"就是恒真）',
      _ta != _tb, u'同值=%s' % (_ta == _tb,))
check(u'B6b ★ brief 里带了"用户此刻在哪"（用户不在场时，模型才能自己决定不说"我回来了"）',
      _ta.find(_PLACES['desktop']) >= 0
      and _tb.find(_PLACES['ut.rooms.room_area1']) >= 0,
      u'A含=%s / B含=%s' % (_ta.find(_PLACES['desktop']) >= 0,
                           _tb.find(_PLACES['ut.rooms.room_area1']) >= 0))

# ---- B7 显示：谁办的就显示成谁说的 ----
_b7 = _fresh()
_b7.personas = {'susie': u'\u4f60\u662f\u82cf\u897f'}
_b7._errand_report_ack('susie', _DEST, _u_what, _u_result)
check(u'B7 气泡挂在**办事的人**名下（不是派活的人，也不是 Ralsei）',
      bool(_b7.dialogue_ui.calls) and _b7.dialogue_ui.calls[0][0] == 'susie',
      u'who=%r' % ((_b7.dialogue_ui.calls[0][0] if _b7.dialogue_ui.calls else None),))

# ---- B8 brief 三要素齐全 ----
_ok8 = bool(_ba.chats) and all(k in _ta for k in (_PLACES[_DEST], _u_what, _u_result))
check(u'B8 brief 里地点 / 事由 / 结果**三样都在**（少一样模型就只能瞎猜）',
      _ok8, u'成立=%s' % (_ok8,))

# ---- B9 当前场景取不到 ⇒ 不许把「None」写进提示词 ----
#   ★ `_npc_scene_id()` 是**明确**"取不到就 `None`、不编一个"的；直接 `%s` 进去
#     会让 brief 出现「用户此刻在「None」」—— 模型只能瞎猜。
#     ★ 只断"没有 `None`"，**不**断"必须有「桌面」"：否则 `M10`（整句去掉）会连带红，
#       两条判据又变成同一条信号（§5.① 的同一个坑）。
_b9 = _fresh()
_b9.cur_scene = None
_b9._errand_report_ack('ralsei', _DEST, _u_what, _u_result)
_t9 = _b9.chats[0]['text'] if _b9.chats else u''
check(u'B9 当前场景取不到 ⇒ brief 里**不许**出现「None」'
      u'（"不编一个"是 `_npc_scene_id` 的纪律，兜底要在这里做）',
      bool(_t9) and u'None' not in _t9,
      u'发起=%d' % (len(_b9.chats),))

# ================================================ C AST
mark(u'C AST：顺序 · 不走 npc_speak · 体内不写记忆 · 只有一处调用 · 两道闸在位')


def _lineno(fn, attr):
    for c in _calls(fn, attr):
        return c.lineno
    return None


_ln_drop = _lineno(_TICK, 'drop')
_ln_commit = _lineno(_TICK, '_npc_errand_commit')
_ln_report = _lineno(_TICK, '_errand_report_ack')
check(u'C1 ★★ tick 体内 `drop` 在 `commit` 之前、`commit` 在 `report` 之前'
      u'（顺序即语义：先回家、再记住、最后开口）',
      None not in (_ln_drop, _ln_commit, _ln_report)
      and _ln_drop < _ln_commit < _ln_report,
      u'三者都找到=%s' % (None not in (_ln_drop, _ln_commit, _ln_report),))

check(u'C2 ★ 交差**不走** `npc_speak()`（它的入参是"对方说的那句话"，会以 who=player 污染记忆）',
      _REPORT is not None and not _calls(_REPORT, 'npc_speak'),
      u'npc_speak 调用数=%d' % (len(_calls(_REPORT, 'npc_speak')),))

check(u'C3 ★ 交差体内**不写记忆**（结果只由 `_npc_errand_commit` 记一次）',
      _REPORT is not None and not _calls(_REPORT, 'remember'),
      u'remember 调用数=%d' % (len(_calls(_REPORT, 'remember')),))

_kw_remember = None
for _c in (_calls(_REPORT, 'chat_with_ai') or []):
    for _k in _c.keywords:
        if _k.arg == 'remember' and isinstance(_k.value, ast.Constant):
            _kw_remember = _k.value.value
check(u'C3b `chat_with_ai(..., remember=False)` 是**字面量**写死的（不是变量，不会被改着改着变 True）',
      _kw_remember is False, u'实得=%r' % (_kw_remember,))

_n_call_global = 0
for _n in ast.walk(TREE):
    if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Attribute) \
            and _n.func.attr == '_errand_report_ack':
        _n_call_global += 1
check(u'C4 全仓 `_errand_report_ack` 只有**一处**调用（就 tick 里那一处；别处偷偷调 = 再说一遍）',
      _n_call_global == 1, u'调用点=%d' % (_n_call_global,))

check(u'C5 ★ 两道闸都在体内：`_npc_ai_available()`（模型）+ `npc_persona_of()`（人设）',
      _REPORT is not None and _calls(_REPORT, '_npc_ai_available')
      and _calls(_REPORT, 'npc_persona_of'),
      u'模型闸=%d / 人设闸=%d'
      % (len(_calls(_REPORT, '_npc_ai_available')),
         len(_calls(_REPORT, 'npc_persona_of'))))

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
      bool(_names) and all(s.strip() for s in _names) and len(_names) >= 20,
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
