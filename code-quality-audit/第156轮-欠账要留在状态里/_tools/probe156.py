# -*- coding: utf-8 -*-
u"""第156轮探针：把"欠账为什么必须留在状态里"量出来。

和 `check156` 的分工：`check156` 守行为（会不会红），本探针**打印数值**给报告当证据。

## 四个量

| # | 量 | 改前 | 改后 |
|---|---|---|---|
| P1 | 三次改派后，**最后一条痕迹**里出现几件"被挤掉的事"（共 2 件） | 1 | 2 |
| P2 | 同一批记忆里，**最早那件**能不能被 `history_block` 取到 | 不能 | 不能（记忆仍会出窗） |
| P3 | 同一状态下 `_build_npc_context()` 里还有没有那 2 件 | 无（改前没挂） | **有** |
| P4 | 没被派过差事的人：`brief` 与 NPC 上下文 | — | `''` / 逐字不变 |

P1 的"改前"是**模型复算**（只写"上一件"的旧格式），对应 `mutate156 M12`；
P2/P3 是对**真实产品**的观测 —— P2 证明"只写记忆不够"（`history_block` 只取最后
12 条，2 条痕迹 + 12 句闲聊就整段出窗），P3 证明旁路真的生效。

★ 纪律：零网络 / 零 UI / 零显示器 / 零外部盘；时间一律用**真实时间基准**（`_T`），
  不许从 0 起算 —— TTL 会把 1970 年的账当陈年旧账全滤掉（本轮踩过）。
"""
import io
import os
import sys
import time as _time

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')

for _p in (PKG, os.path.join(PKG, 'src'), os.path.join(PKG, 'modules')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from main import RalseiPet                                  # noqa: E402
from main import _errand_backlog_brief, _errand_given_up_of  # noqa: E402
from modules import npc_errand as ER                        # noqa: E402
from modules import npc_persona as NP                       # noqa: E402
from modules import npc_system as NS                        # noqa: E402

assert os.path.isfile(os.path.join(PKG, 'src', 'main.py'))
assert os.path.isfile(os.path.join(PKG, 'modules', 'npc_persona.py'))

_DEST = 'oneshot.barrens.Blue'
_DEST2 = 'ut.rooms.room_area1'
_DEST3 = 'ch1.hometown.town_mid'
_WHAT = u'\u64e6\u67dc\u53f0'         # 擦柜台
_WHAT2 = u'\u6536\u676f\u5b50'        # 收杯子
_WHAT3 = u'\u6253\u626b\u524d\u9662'  # 打扫前院

_n_pass = 0
_n_fail = 0


def ok(desc, cond, detail=''):
    global _n_pass, _n_fail
    if cond:
        _n_pass += 1
        print(u'[PASS] %s%s' % (desc, (u'    ' + detail) if detail else u''))
    else:
        _n_fail += 1
        print(u'[FAIL] %s%s' % (desc, (u'    ' + detail) if detail else u''))


class _Mem(object):
    def __init__(self):
        self.log = []

    def remember(self, nid, text, who=None, **kw):
        self.log.append((nid, text, who))

    def save(self, nid):
        pass


class _Host(object):
    u"""轻宿主：与 `check156._Host` 同一套（只挂**产品**函数 + 外围桩）。"""

    _npc_errand_note = RalseiPet._npc_errand_note
    _errand_note = RalseiPet._npc_errand_note
    assign_errand = RalseiPet.assign_errand
    _build_npc_context = RalseiPet._build_npc_context

    def __init__(self):
        self.npc_registry = NS.load_registry()
        self._npc_aliases = NP.address_aliases(
            [(n.id, n.name, n.name_cn) for n in self.npc_registry.all()])
        self.npc_errand = ER.ErrandBoard(enabled=True)
        self.npc_memory = _Mem()
        self._errand_given_up = {}
        self._npc_talking = 'ralsei'

    def _npc_errand_gate(self, npc_id, dest):
        return (True, u'')

    def _npc_ai_available(self):
        return True

    def npc_persona_of(self, npc_id):
        return u'\u4f60\u662f%s' % npc_id

    def npc_label(self, npc_id):
        return npc_id


_T = _time.time()

_h = _Host()
_h.assign_errand('ralsei', _DEST, _WHAT, now=_T)
_h.assign_errand('ralsei', _DEST2, _WHAT2, now=_T + 10)
_h.assign_errand('ralsei', _DEST3, _WHAT3, now=_T + 20)
_notes = [row[1] for row in _h.npc_memory.log]
_last = _notes[-1] if _notes else u''

print(u'== 现场：三次改派（A→B→C）之后就写了 %d 条痕迹 ==' % (len(_notes),))
for _i, _t in enumerate(_notes):
    print(u'  [%d] %s' % (_i + 1, _t))
print(u'')

# ---------------------------------------------------------------- P1
# 改前模型：第154轮那句只写"上一件"（`_p_txt`），不含更早的欠账。
_OLD = u'\u6211\u672c\u6765\u8981%s\uff0c\u8fd8\u6ca1\u529e\u5b8c\uff0c\u53c8\u88ab\u6d3e\u53bb %s %s\u4e86'
_old_last = _OLD % (u'\u529e\u300c%s\u300d' % (_WHAT2,), _DEST3,
                    u'\u529e\u300c%s\u300d' % (_WHAT3,))
_n_old = len([x for x in (_WHAT, _WHAT2) if x in _old_last])
_n_new = len([x for x in (_WHAT, _WHAT2) if x in _last])
print(u'P1 最后一条痕迹里出现的"被挤掉的事"件数（共 2 件：擦柜台 / 收杯子）')
print(u'   改前（模型）= %d 件  ⇒ %s' % (_n_old, _old_last))
print(u'   改后（实测）= %d 件  ⇒ %s' % (_n_new, _last))
ok(u'P1 ★ 改后最后一条痕迹**自己就能答上**两件欠账（改前只带一件，'
   u'问最早那件得往回翻一条）',
   _n_old == 1 and _n_new == 2, u'改前=%d 改后=%d' % (_n_old, _n_new))

# ---------------------------------------------------------------- P2
# 真实出窗：2 条痕迹后面跟 12 句闲聊 ⇒ `history_block(max_lines=12)` 只剩闲聊。
_entries = ([{'text': t, 'who': 'ralsei'} for t in _notes]
            + [{'text': u'\u95f2\u804a%d' % (i,), 'who': 'player'}
               for i in range(12)])
_blk = NP.history_block(_entries, 'ralsei', max_lines=12)
_n_hit = len([x for x in (_WHAT, _WHAT2) if x in (_blk or u'')])
print(u'P2 记忆窗口（最后 12 条）：痕迹 %d 条 + 闲聊 12 句 ⇒ 段落 %d 字'
      % (len(_notes), len(_blk or u'')))
ok(u'P2 ★★ 只靠记忆**保不住**：最早那件（擦柜台）已经出窗'
   u'（这就是"欠账必须挂进状态"的原因）',
   _WHAT not in (_blk or u''), u'命中件数=%d' % (_n_hit,))
ok(u'P2b 分母闸：窗口里确实还有内容（不是"整段空 ⇒ 当然没有"）',
   bool(_blk) and u'\u95f2\u804a' in _blk, u'段落非空=%s' % (bool(_blk),))

# ---------------------------------------------------------------- P3
_brief = _errand_backlog_brief(_h, 'ralsei', now=_T + 30)
_ctx = _h._build_npc_context('ralsei')
print(u'P3 欠账 brief = %s' % (_brief or u'(空)'))
print(u'P3 NPC 上下文 = %s' % (_ctx.replace('\n', ' | ') if _ctx else u'(空)'))
ok(u'P3 ★★ 同一时刻，**状态**里那 2 件还在（窗口裁不掉它）',
   _WHAT in _brief and _WHAT2 in _brief
   and u'2 \u4ef6' in _brief,
   u'件数串=%s' % (u'2 \u4ef6' in _brief,))
ok(u'P3b `_build_npc_context()` 真的把它挂上了（旁路生效，不只是个函数）',
   bool(_ctx) and _WHAT in _ctx and _WHAT2 in _ctx,
   u'上下文含欠账=%s' % (_WHAT in (_ctx or u''),))

# ---------------------------------------------------------------- P4
_h0 = _Host()
_b0 = _errand_backlog_brief(_h0, 'ralsei', now=_T)
_c0 = _h0._build_npc_context('ralsei')
print(u'P4 没被派过差事的人：brief=%r 上下文行数=%d'
      % (_b0, len((_c0 or u'').splitlines())))
ok(u'P4 ★ 空账 ⇒ `brief` 返回 `\'\'`、NPC 上下文**一个字都不多**（零回归的根）',
   _b0 == u'' and u'\u6b20' not in (_c0 or u'')
   and len((_c0 or u'').splitlines()) <= 1,
   u'brief空=%s 行数=%d' % (_b0 == u'', len((_c0 or u'').splitlines())))
ok(u'P4b 正控制：同一函数在**有账**时返回非空（否则 P4 是"函数恒返回空"的假绿）',
   bool(_brief), u'长度=%d' % (len(_brief),))

print(u'')
if _n_fail:
    print(u'probe156：FAIL %d / PASS %d' % (_n_fail, _n_pass))
    sys.exit(1)
print(u'probe156：%d 项全过' % (_n_pass,))
sys.exit(0)
