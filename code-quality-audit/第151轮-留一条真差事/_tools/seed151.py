# -*- coding: utf-8 -*-
u"""第151轮 · **一条真差事** —— 用产品真方法把它从派出跑到办完，全程打印。

用户口径（逐字）：
> 「先留一个差事确保他们能做出来再说吧」
> 「我让 ralsei 去 oneshot 里干什么事情，**他能去，干，然后产生结果**，
>    甚至**我中途进去的时候也能看到过程**」

这个脚本就是**那条差事**：不写死期望值、不 mock 逻辑 —— 它把产品里那几个真函数
（`assign_errand` / `_npc_errand_tick` / `_npc_errand_commit`）挂在轻宿主上，
按 0 → 路上 → 到达 → 办完 四个时刻各推一拍，**如实打印**每一拍发生了什么。

跑法（在仓库根）：
    C:\\Python311\\python.exe "code-quality-audit/第151轮-留一条真差事/_tools/seed151.py"

★ 它**不改产品配置**：`NPC_ERRAND_DEMO` 只在内存里临时设，跑完复原。
★ 它**不碰盘**：没有 `data_store`、没有 Qt、没有临时文件。
★ 判定：五步全对 ⇒ 退出码 0；任何一步不对 ⇒ 退出码 1 并打出那一步的实况。
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
from modules import npc_system as NS                        # noqa: E402

#: 这条差事：谁 / 去哪 / 干什么。★ 与 `NPC_ERRAND_DEMO` 注释里那行例子的**同一件**。
NPC_ID = u'ralsei'
DEST = u'oneshot.barrens.Blue'
WHAT = u'去看看'

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
    assign_errand = RalseiPet.assign_errand

    def __init__(self):
        self._npc_errand_world_uncached = RalseiPet._npc_errand_world_uncached
        self.npc_registry = NS.load_registry()
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
print(u'一条真差事：%s → %s 办「%s」' % (NPC_ID, DEST, WHAT))
print(u'（用产品真方法跑：assign_errand / _npc_errand_tick / _npc_errand_commit）')
print(u'=' * 78)

h = _Host()
e = h.assign_errand(NPC_ID, DEST, WHAT, now=0.0)
if e is None:
    print(u'  !! 派不出去 —— 门控或看板拒绝了。先看 `_npc_errand_gate` 的理由：')
    ok, why = h._npc_errand_gate(NPC_ID, DEST)
    print(u'     gate.ok=%s why=%s' % (ok, why))
    sys.exit(1)

stage(1, u'派出', e.status == ER.TRAVELING,
      u'状态=%s，%d 秒到 / %d 秒办完'
      % (e.status, int(e.arrive_at - e.start), int(e.finish_at - e.arrive_at)))

# ---- 路上：位置**不该**被改 ----
h._npc_errand_tick(e.arrive_at - 1.0)
stage(2, u'在路上', h.npc_roam.puts == [] and h.npc_roam.get(NPC_ID) is None,
      u't=%d 状态=%s，put %d 次 ⇒ **位置没动**（所以别处看不到他瞬移）'
      % (int(e.arrive_at - 1.0), e.status, len(h.npc_roam.puts)))

# ---- 到达：压在目的地（"我中途进场能看到过程"就靠这条）----
h._npc_errand_tick(e.arrive_at)
_cur = h.npc_roam.get(NPC_ID)
stage(3, u'到达', e.status == ER.WORKING and _cur is not None
      and _cur.scene == DEST and len(h.npc_roam.puts) == 1,
      u't=%d 状态=%s，位置已压到 %s（reason=%s）'
      % (int(e.arrive_at), e.status,
         getattr(_cur, 'scene', None),
         h.npc_roam.puts[0][2] if h.npc_roam.puts else u'-'))

# ---- 办完：撤覆盖 + 结果进记忆 ----
h._npc_errand_tick(e.finish_at)
_mem = h.npc_memory.log
stage(4, u'办完', e.status == ER.DONE and h.npc_roam.drops == [NPC_ID],
      u't=%d 状态=%s，覆盖已撤（drop %d 次 ⇒ 回落静态归属 = 回家）'
      % (int(e.finish_at), e.status, len(h.npc_roam.drops)))

stage(5, u'结果', len(_mem) == 1 and bool(_mem[0][1]),
      u'「%s」⇒ 已写进 %s 的记忆'
      % (_mem[0][1] if _mem else u'（空）', NPC_ID))

# ---- 办完之后再推：不重复 ----
h._npc_errand_tick(e.finish_at + 1000.0)
stage(6, u'不重复', len(h.npc_roam.drops) == 1 and len(h.npc_memory.log) == 1,
      u'再推 1000 秒：drop 仍 %d 次、记忆仍 %d 条（"办完"只发生一次）'
      % (len(h.npc_roam.drops), len(h.npc_memory.log)))

print(u'')
print(u'=' * 78)
if _n_bad == 0:
    print(u'结论：这条差事**从派出到产出结果全链路通了**（%d 步全 OK）。' % 6)
    print(u'      想让它开机就发生：把 `RalseiPet.NPC_ERRAND_DEMO` 设成')
    print(u'      (%r, %r, %r) 即可（默认 None = 不派）。'
          % (NPC_ID, DEST, WHAT))
    sys.exit(0)
print(u'结论：有 %d 步不对，见上面的 BAD 行。' % _n_bad)
sys.exit(1)
