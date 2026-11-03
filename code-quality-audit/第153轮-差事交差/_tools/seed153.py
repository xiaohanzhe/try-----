# -*- coding: utf-8 -*-
u"""第153轮 · **一条差事的收尾** —— 用产品真方法把它从"派出去"跑到"回来交差"。

用户口径（逐字）：
> 「我让 ralsei 去 oneshot 里干什么事情，**他能去，干，然后产生结果**，
>    甚至**我中途进去的时候也能看到过程**」

第150轮跑了前半段（派得出去、有过程），第152轮跑了"叫得回来"。
这一段跑的是**正面收尾**：办完 → 回家 → 记住 → **交代一句**。

这个脚本不写死期望值、不 mock 逻辑 —— 把产品里那几个真函数
（`assign_errand` / `_npc_errand_tick` / `_npc_errand_commit` / `_errand_report_ack`）
挂在轻宿主上，按 派出 → 到达 → 办完 → 再推 1000 秒 各推一拍，**如实打印**每一拍发生了什么。

★ **台词不冒充**：`chat_with_ai` 是桩（本机 7B 不在这一环），它只**记账**，
  不回调任何编出来的句子。脚本打出来的是"**发出去的 brief**"，
  真正那句由模型生成 —— 这里既不该也不能替它写。

跑法（在仓库根）：
    C:\\Python311\\python.exe "code-quality-audit/第153轮-差事交差/_tools/seed153.py"

★ 它**不改产品配置**、**不碰盘**：没有 `data_store`、没有 Qt、没有临时文件。
★ 判定：七步全对 ⇒ 退出码 0；任何一步不对 ⇒ 退出码 1 并打出那一步的实况。
"""
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')

for _p in (PKG, os.path.join(PKG, 'src'), os.path.join(PKG, 'modules')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from main import RalseiPet                                  # noqa: E402
from modules import npc_errand as ER                        # noqa: E402
from modules import npc_persona as NP                       # noqa: E402
from modules import npc_system as NS                        # noqa: E402

#: 这条差事：谁 / 去哪 / 干什么 / 办成了什么。
NPC_ID = u'ralsei'
DEST = u'oneshot.barrens.Blue'
WHAT = u'\u53bb\u770b\u770b'
RESULT = u'\u90a3\u8fb9\u7684\u706f\u5854\u8fd8\u5728\u5de5\u4f5c\uff0c\u6ca1\u4eba\u53d7\u4f24\u3002'

_n_bad = 0


def stage(no, title, ok, detail):
    global _n_bad
    if not ok:
        _n_bad += 1
    print(u'  %d. %-10s %s  %s' % (no, title, u'OK  ' if ok else u'BAD ',
                                   detail))


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
    _npc_errand_world = RalseiPet._npc_errand_world
    _npc_errand_gate = RalseiPet._npc_errand_gate
    _npc_errand_note = RalseiPet._npc_errand_note
    _npc_errand_tick = RalseiPet._npc_errand_tick
    _npc_errand_commit = RalseiPet._npc_errand_commit
    _errand_report_ack = RalseiPet._errand_report_ack
    assign_errand = RalseiPet.assign_errand

    def __init__(self):
        self._npc_errand_world_uncached = RalseiPet._npc_errand_world_uncached
        self.npc_registry = NS.load_registry()
        self._npc_aliases = NP.address_aliases(
            [(n.id, n.name, n.name_cn) for n in self.npc_registry.all()])
        self.npc_errand = ER.ErrandBoard()
        self.npc_memory = _Mem()
        self.npc_roam = _Roam()
        self.chats = []

    # ---- 外围（真产品里由 Qt / data_store / 场景系统提供）----
    def chat_with_ai(self, text, on_reply, on_delta=None, speaker=None,
                     remember=True, model=None):
        # ★ 只记账：**不**回调任何句子（本脚本不替模型写台词）
        self.chats.append({'text': text, 'speaker': speaker,
                           'remember': remember})
        return True

    def _npc_ai_available(self):
        return True

    def npc_persona_of(self, npc_id):
        # ralsei 的主链路本来就走 `assets/ralsei_persona.md`（speaker=None）
        return None if npc_id == 'ralsei' else u'\u88c5\u4e86\u8bbe\u5b9a'

    def npc_label(self, npc_id):
        return u'Ralsei' if npc_id == 'ralsei' else npc_id

    def _npc_model(self, npc_id):
        return None

    def _errand_place_label(self, scene_id):
        return scene_id or u''

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


print(u'=' * 78)
print(u'\u4e00\u6761\u5dee\u4e8b\u7684\u6536\u5c3e\uff1a%s \u2192 %s \u529e\u300c%s\u300d\uff0c'
      u'\u529e\u5b8c\u56de\u6765\u4ea4\u5f85' % (NPC_ID, DEST, WHAT))
print(u'\uff08\u7528\u4ea7\u54c1\u771f\u65b9\u6cd5\u8dd1\uff1aassign_errand / _npc_errand_tick / '
      u'_npc_errand_commit / _errand_report_ack\uff09')
print(u'=' * 78)

h = _Host()
# ★ 用短时长把"办完"压缩到几拍内（默认 90s/300s 在这里没有信息量）
e = h.assign_errand(NPC_ID, DEST, WHAT, now=0.0, travel=10.0, work=100.0,
                    result=RESULT)
if e is None:
    print(u'  !! \u6d3e\u4e0d\u51fa\u53bb \u2014\u2014 \u5148\u770b `_npc_errand_gate` \u7684\u7406\u7531\uff1a')
    print(u'     %s' % (h._npc_errand_gate(NPC_ID, DEST),))
    sys.exit(1)

stage(1, u'\u6d3e\u51fa', e.status == ER.TRAVELING,
      u'\u72b6\u6001=%s\uff0c%d \u79d2\u5230 / %d \u79d2\u529e\u5b8c'
      % (e.status, int(e.arrive_at - e.start), int(e.finish_at - e.arrive_at)))

# ---- 到达：位置被压到目的地（"我中途进去能看到他"靠这个）----
h._npc_errand_tick(e.arrive_at)
_cur = h.npc_roam.get(NPC_ID)
stage(2, u'\u5230\u8fbe', e.status == ER.WORKING and _cur is not None
      and _cur.scene == DEST,
      u'\u72b6\u6001=%s\uff0c\u4f4d\u7f6e\u5df2\u538b\u5230 %s'
      % (e.status, getattr(_cur, 'scene', None)))

# ---- 办完：到点产出结果 ----
_out = h._npc_errand_tick(e.finish_at)
_fin = (_out.get('finished') or [])
stage(3, u'\u529e\u5b8c', e.status == ER.DONE
      and h.npc_errand.result_of(NPC_ID) == RESULT,
      u'\u72b6\u6001=%s\uff0c\u7ed3\u679c\u300c%s\u300d'
      % (e.status, h.npc_errand.result_of(NPC_ID)))

# ---- 回家：位置覆盖撤掉（他不在外面漂着）----
stage(4, u'\u56de\u5bb6', h.npc_roam.get(NPC_ID) is None
      and h.npc_roam.drops == [NPC_ID],
      u'drop %d \u6b21 \u21d2 \u56de\u843d\u9759\u6001\u5f52\u5c5e' % len(h.npc_roam.drops))

# ---- 记忆：结果落进**他自己**的记忆（"下次进场他也记得"）----
_mem = h.npc_memory.log
_has = bool(_mem) and any(RESULT in (row[1] or u'') for row in _mem)
stage(5, u'\u8bb0\u5fc6', _has,
      u'%d \u6761 \u21d2 \u300c%s\u300d'
      % (len(_mem), (_mem[0][1] if _mem else u'\uff08\u7a7a\uff09')))

# ---- 交差：一句带结果的交代被**发起**（台词由模型生成，这里不冒充）----
_c = h.chats[0] if h.chats else {}
stage(6, u'\u4ea4\u5dee', len(h.chats) == 1
      and _c.get('speaker', 'x') is None
      and _c.get('remember', 'x') is False
      and RESULT in (_c.get('text') or u''),
      u'\u53d1\u8d77 1 \u6b21\uff08speaker=%r / remember=%r\uff09\uff1b'
      u'brief \u91cc\u5e26\u4e86\u7ed3\u679c'
      % (_c.get('speaker', 'x'), _c.get('remember', 'x')))

# ---- 不重复：再推 1000 秒，不该再交代一遍 ----
h._npc_errand_tick(e.finish_at + 1000.0)
stage(7, u'\u4e0d\u91cd\u590d', len(h.chats) == 1 and len(h.npc_roam.drops) == 1,
      u'\u518d\u63a8 1000 \u79d2\uff1a\u53d1\u8d77\u4ecd %d \u6b21\u3001drop \u4ecd %d \u6b21'
      % (len(h.chats), len(h.npc_roam.drops)))

print(u'')
print(u'  \u2500\u2500 \u53d1\u7ed9\u6a21\u578b\u7684 brief\uff08\u539f\u6587\uff0c\u2014\u2014 \u771f\u6b63\u90a3\u53e5\u53f0\u8bcd\u7531 7B \u751f\u6210\uff09\u2500\u2500')
for _ln in (_c.get('text') or u'').splitlines():
    print(u'  | %s' % _ln)

print(u'')
print(u'=' * 78)
if _n_bad == 0:
    print(u'\u7ed3\u8bba\uff1a\u8fd9\u6761\u5dee\u4e8b**\u529e\u5b8c\u6709\u4ea4\u4ee3**\uff087 \u6b65\u5168 OK\uff09\u2014\u2014 '
          u'\u4eba\u56de\u6765\u4e86\u3001\u7ed3\u679c\u8bb0\u4f4f\u4e86\u3001'
          u'\u5e76\u4e14**\u628a\u7ed3\u679c\u8bf4\u5230\u4e86\u7528\u6237\u773c\u524d**\uff0c'
          u'\u4e14\u53ea\u8bf4\u4e00\u6b21\u3002')
    sys.exit(0)
print(u'\u7ed3\u8bba\uff1a\u6709 %d \u6b65\u4e0d\u5bf9\uff0c\u89c1\u4e0a\u9762\u7684 BAD \u884c\u3002' % _n_bad)
sys.exit(1)
