# -*- coding: utf-8 -*-
u"""第152轮 · **一条差事的叫停** —— 用产品真方法把它从"派出去"跑到"叫回来"。

用户口径（逐字）：
> 「**按照人类的逻辑来就好**」

人味逻辑 = 派出去 → 叫停 → 他**回来** → 他也记得"我本来要去，被叫回来了"。

这个脚本不写死期望值、不 mock 逻辑 —— 把产品里那几个真函数
（`assign_errand` / `_npc_errand_tick` / `cancel_errand`）挂在轻宿主上，
按 派出 → 到达 → 叫停 → 再推 1000 秒 各推一拍，**如实打印**每一拍发生了什么。

跑法（在仓库根）：
    C:\\Python311\\python.exe "code-quality-audit/第152轮-差事叫停/_tools/seed152.py"

★ 它**不改产品配置**、**不碰盘**：没有 `data_store`、没有 Qt、没有临时文件。
★ 判定：六步全对 ⇒ 退出码 0；任何一步不对 ⇒ 退出码 1 并打出那一步的实况。
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

#: 这条差事：谁 / 去哪 / 干什么。★ 与第151轮那条**同一件**（"叫停"是它的后半段）。
NPC_ID = u'ralsei'
DEST = u'oneshot.barrens.Blue'
WHAT = u'\u53bb\u770b\u770b'

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

    def _errand_report_ack(self, *a, **kw):
        # ★ 第153轮：产品在 tick 的 finished 分支里新调了它。
        #   桩必须跟着装 —— 否则 AttributeError 会被 tick 的
        #   `except` 吞掉，症状不是报错，而是“finished 那一段整段没执行”。
        #   看台词的地方在第153轮 `check153`。
        return None
    assign_errand = RalseiPet.assign_errand
    cancel_errand = RalseiPet.cancel_errand

    def __init__(self):
        self._npc_errand_world_uncached = RalseiPet._npc_errand_world_uncached
        self.npc_registry = NS.load_registry()
        self._npc_aliases = NP.address_aliases(
            [(n.id, n.name, n.name_cn) for n in self.npc_registry.all()])
        self.npc_errand = ER.ErrandBoard()
        self.npc_memory = _Mem()
        self.npc_roam = _Roam()

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


print(u'=' * 78)
print(u'\u4e00\u6761\u5dee\u4e8b\u7684\u53eb\u505c\uff1a%s \u2192 %s \u529e\u300c%s\u300d\uff0c\u7136\u540e\u88ab\u53eb\u56de\u6765' % (NPC_ID, DEST, WHAT))
print(u'\uff08\u7528\u4ea7\u54c1\u771f\u65b9\u6cd5\u8dd1\uff1aassign_errand / _npc_errand_tick / cancel_errand\uff09')
print(u'=' * 78)

h = _Host()
# ★ 用短时长把"到达"压缩到几拍内（默认 90s/300s 在这里没有信息量）
e = h.assign_errand(NPC_ID, DEST, WHAT, now=0.0, travel=10.0, work=100.0)
if e is None:
    print(u'  !! \u6d3e\u4e0d\u51fa\u53bb \u2014\u2014 \u5148\u770b `_npc_errand_gate` \u7684\u7406\u7531\uff1a')
    print(u'     %s' % (h._npc_errand_gate(NPC_ID, DEST),))
    sys.exit(1)

stage(1, u'\u6d3e\u51fa', e.status == ER.TRAVELING,
      u'\u72b6\u6001=%s\uff0c%d \u79d2\u5230 / %d \u79d2\u529e\u5b8c'
      % (e.status, int(e.arrive_at - e.start), int(e.finish_at - e.arrive_at)))

# ---- 到达：位置被压到目的地 ----
h._npc_errand_tick(e.arrive_at)
_cur = h.npc_roam.get(NPC_ID)
stage(2, u'\u5230\u8fbe', e.status == ER.WORKING and _cur is not None
      and _cur.scene == DEST,
      u'\u72b6\u6001=%s\uff0c\u4f4d\u7f6e\u5df2\u538b\u5230 %s'
      % (e.status, getattr(_cur, 'scene', None)))

# ---- 叫停 ----
_ret = h.cancel_errand(NPC_ID, reason=u'\u7528\u6237\u53eb\u505c')
stage(3, u'\u53eb\u505c', _ret is not None and len(h.npc_errand) == 0,
      u'\u770b\u677f\u5269 %d \u6761\uff08\u4f5c\u5e9f\u524d\u72b6\u6001=%s\uff09'
      % (len(h.npc_errand), getattr(_ret, 'status', u'?')))

# ---- 位置：覆盖已撤 ⇒ 他回落到静态归属（回家）----
stage(4, u'\u4f4d\u7f6e', h.npc_roam.get(NPC_ID) is None
      and h.npc_roam.drops == [NPC_ID],
      u'drop %d \u6b21 \u21d2 \u8986\u76d6\u5df2\u64a4\uff08\u4ed6\u4e0d\u5728\u76ee\u7684\u5730\u4e86\uff09'
      % len(h.npc_roam.drops))

# ---- 记忆：他知道"被叫回来了" ----
_mem = h.npc_memory.log
stage(5, u'\u8bb0\u5fc6', len(_mem) == 1 and u'\u53eb\u56de\u6765' in (_mem[0][1] if _mem else u''),
      u'\u300c%s\u300d' % (_mem[0][1] if _mem else u'\uff08\u7a7a\uff09'))

# ---- 作废 ≠ 办完：再推 1000 秒也不产出结果 ----
_out = h._npc_errand_tick(e.finish_at + 1000.0)
stage(6, u'\u4f5c\u5e9f', h.npc_errand.result_of(NPC_ID) == ''
      and len(h.npc_errand.done) == 0
      and not (_out.get('finished') or ())
      and len(h.npc_roam.drops) == 1,
      u'\u518d\u63a8 1000 \u79d2\uff1aresult=%r\u3001done=%d\u3001drop \u4ecd %d \u6b21'
      % (h.npc_errand.result_of(NPC_ID), len(h.npc_errand.done),
         len(h.npc_roam.drops)))

print(u'')
print(u'=' * 78)
if _n_bad == 0:
    print(u'\u7ed3\u8bba\uff1a\u8fd9\u6761\u5dee\u4e8b**\u53eb\u5f97\u56de\u6765**\uff08%d \u6b65\u5168 OK\uff09\u2014\u2014 \u4eba\u56de\u6765\u4e86\u3001'
          u'\u4f4d\u7f6e\u64a4\u4e86\u3001\u8bb0\u5fc6\u7559\u4e86\u3001**\u4f46\u6ca1\u6709\u5047\u9020\u4e00\u4e2a\u201c\u529e\u5b8c\u4e86\u201d**\u3002' % 6)
    sys.exit(0)
print(u'\u7ed3\u8bba\uff1a\u6709 %d \u6b65\u4e0d\u5bf9\uff0c\u89c1\u4e0a\u9762\u7684 BAD \u884c\u3002' % _n_bad)
sys.exit(1)
