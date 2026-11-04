# -*- coding: utf-8 -*-
u"""第158轮探针：**状态真变了，盘上是不是也变了**。

用法：
    python probe158.py --before   # 改前基线（断言"没写" —— 证明口子真的存在）
    python probe158.py            # 改后（断言"写了"）

## 量什么

| # | 场景 | 改前 | 改后 |
|---|---|---|---|
| P1 | 连派三次（A→B→C）后**什么都不做**就重启 | 差事 0 条 / 欠账 0 件（**全丢**） | 1 条 / 2 件 |
| P2 | 派 A → 落过一次盘 → 30 秒内叫停 → 重启 | A **复活**（还在办） | 没了 |
| P3 | 派 / 催 / 改派各一次，数落盘次数 | 0 次 | 2 次（催不写） |
| P4 | 显式 `force` 之后读回 | 对（正控制） | 对 |
| P5 | 派活 → 到岗（已写过一次盘）→ 1.5 秒内办完 → 重启 | 在办 1 条 / 结果空（**又出门**） | 已办 1 条 / 结果在 |
| P6 | 只压位置（无结构变化） | 不强写 | 不强写（两边都守"别乱写"） |

P1 是本轮的核心：`assign_errand` **完全没有落盘调用**（`grep` 只有 tick / 叫停 / 退出三处），
而 tick 那处是 120 秒节流 ⇒ **"点完就关" 或崩溃，三次改派一件都不剩**。
P2 是同一枚硬币的另一面：**叫停没落盘 ⇒ 重启后差事"复活"**，人会再次出门。
P3 守"别乱写"：催（同一件事重说）与门控拒**一次都不该写**。

★ 纪律：临时文件只落系统 temp（用完即删）；零网络 / 零 UI / 零显示器；
  时间基准一律用 `_time.time()`（从 0 起算会被 TTL 当陈年旧账，第156轮踩过）。
"""
import io
import json
import os
import shutil
import sys
import tempfile
import time as _time

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')

for _p in (PKG, os.path.join(PKG, 'src'), os.path.join(PKG, 'modules')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from main import RalseiPet                                  # noqa: E402
from main import _errand_given_up_of                        # noqa: E402
from modules import npc_errand as ER                        # noqa: E402
from modules import npc_system as NS                        # noqa: E402

BEFORE = '--before' in sys.argv

_DEST = 'oneshot.barrens.Blue'
_DEST2 = 'ut.rooms.room_area1'
_DEST3 = 'ch1.hometown.town_mid'
_WHAT = u'\u64e6\u67dc\u53f0'
_WHAT2 = u'\u6536\u676f\u5b50'
_WHAT3 = u'\u6253\u626b\u524d\u9662'

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


class _Pos(object):
    __slots__ = ('scene',)

    def __init__(self, scene):
        self.scene = scene


class _Roam(object):
    u"""驻留表替身：只实现 `_npc_errand_tick` 真会用到的那四个动作。"""

    def __init__(self):
        self._t = {}

    def get(self, nid):
        return self._t.get(nid)

    def put(self, nid, scene, now, reason=None):
        self._t[nid] = _Pos(scene)

    def drop(self, nid):
        self._t.pop(nid, None)


class _Host(object):
    u"""轻宿主：挂产品函数（含 save/load），并把每次落盘记进 `saves`。

    ★ `saves` 里存的是 `force` 的值：`True` = 立即落盘（force），`False` = 走节流那次。
    """

    _npc_errand_note = RalseiPet._npc_errand_note
    _errand_note = RalseiPet._npc_errand_note
    assign_errand = RalseiPet.assign_errand
    cancel_errand = RalseiPet.cancel_errand
    _npc_errand_load = RalseiPet._npc_errand_load
    _npc_errand_tick = RalseiPet._npc_errand_tick
    _npc_errand_commit = RalseiPet._npc_errand_commit

    def __init__(self, path):
        self._path = path
        self.npc_registry = NS.load_registry()
        self.npc_memory = _Mem()
        self.npc_roam = _Roam()
        self._npc_talking = 'ralsei'
        self._errand_given_up = {}
        self._npc_errand_last_save = 0.0
        self.saves = []
        # ★★ 第158轮踩到：**不能**写 `self._npc_errand_load() or ER.ErrandBoard()`。
        #   `ErrandBoard.__len__` 只数**在办** ⇒ 一个"只剩已办记录"的看板
        #   `len()==0` 为假 ⇒ 整本被换成空板，重启后"已办 + 结果"全没。
        #   那会让 P5 出现**假红**（看着像产品没落盘，其实是夹具把档丢了）。
        #   产品侧走的是 `if _er is not None:`（`init_npc_systems` 行 3704）—— 照抄它。
        _er = self._npc_errand_load()
        self.npc_errand = _er if _er is not None else ER.ErrandBoard()

    def _npc_errand_file(self):
        return self._path

    def _npc_errand_save(self, force=False):
        self.saves.append(bool(force))
        return RalseiPet._npc_errand_save(self, force)

    def _npc_errand_gate(self, npc_id, dest):
        return (True, u'')

    def _errand_report_ack(self, *a, **kw):
        # ★ 交差那句话要模型 ⇒ 探针里**不测这一环**（第153轮有专门的套件），
        #   否则会去碰网络/线程池，把"落盘"这个观察量淹掉。
        return None

    def _npc_seed_bodies(self, scene_id=None):
        pass

    # ★★ 第158轮必补：`cancel_errand` 的落盘排在这两个调用**之后**、
    #   且整段包在 `try/except` 里 ⇒ 宿主少一个方法就会 `AttributeError`，
    #   被 `except Exception` 吞掉、**落盘那行永远不执行**。
    #   第一版就是这个坑：P2 改前改后都"复活"，看着像产品没修，其实是夹具缺件。
    def _npc_scene_id(self):
        return 'ch1.hometown.town_mid'

    def _npc_plan_save(self, force=False):
        return True

    def npc_label(self, npc_id):
        return npc_id


_tmp = tempfile.mkdtemp(prefix='probe158_')
_P1 = os.path.join(_tmp, 'p1.json')
_P2 = os.path.join(_tmp, 'p2.json')
_P3 = os.path.join(_tmp, 'p3.json')
_P4 = os.path.join(_tmp, 'p4.json')
_P5 = os.path.join(_tmp, 'p5.json')
_P6 = os.path.join(_tmp, 'p6.json')
_T = _time.time()

try:
    print(u'== 改前基线 ==' if BEFORE else u'== 改后 ==')

    # ------------------------------------------------ P1 连派三次，什么都不做就重启
    _h1 = _Host(_P1)
    _h1.assign_errand('ralsei', _DEST, _WHAT, now=_T)
    _h1.assign_errand('ralsei', _DEST2, _WHAT2, now=_T + 10)
    _h1.assign_errand('ralsei', _DEST3, _WHAT3, now=_T + 20)
    _h1b = _Host(_P1)          # ← 模拟"崩溃/强杀后重启"
    _n_act = len(_h1b.npc_errand)
    _n_gu = len(_errand_given_up_of(_h1b, 'ralsei', now=_T + 30))
    print(u'P1 连派三次后**不调任何 save** 就重启：在办 %d 条 / 欠账 %d 件'
          % (_n_act, _n_gu))
    if BEFORE:
        ok(u'P1 ★★★ 改前：点了就走 ⇒ **差事与欠账一件都不剩**（`assign_errand` 从不落盘）',
           _n_act == 0 and _n_gu == 0, u'在办=%d 欠账=%d' % (_n_act, _n_gu))
    else:
        ok(u'P1 ★★★ 派活当场就落盘：重启后**在办 1 条 + 欠账 2 件**都在',
           _n_act == 1 and _n_gu == 2, u'在办=%d 欠账=%d' % (_n_act, _n_gu))

    # ------------------------------------------------ P2 叫停后重启（120 秒窗口内）
    _h2 = _Host(_P2)
    _h2.assign_errand('ralsei', _DEST, _WHAT, now=_T)
    _h2._npc_errand_save(force=True)      # ← 模拟"过一会儿 tick 落过一次盘"
    _h2.cancel_errand('ralsei')           # ← 用户 30 秒内叫停
    _h2b = _Host(_P2)                     # ← 崩溃重启
    _n2 = len(_h2b.npc_errand)
    print(u'P2 派活 → 落过一次盘 → 叫停 → 重启：在办 %d 条' % (_n2,))
    if BEFORE:
        ok(u'P2 ★★ 改前：叫停被 120s 节流挡住 ⇒ 重启后差事**复活**（他又出门了）',
           _n2 == 1, u'在办=%d' % (_n2,))
    else:
        ok(u'P2 ★★ 叫停当场落盘 ⇒ 重启后**不会复活**',
           _n2 == 0, u'在办=%d' % (_n2,))

    # ------------------------------------------------ P3 数落盘次数
    _h3 = _Host(_P3)
    _h3.saves.clear()
    _h3.assign_errand('susie', _DEST, _WHAT, now=_T)          # ① 真派
    _h3.assign_errand('susie', _DEST, _WHAT, now=_T + 1)      # ② 催（同一件事）
    _h3.assign_errand('susie', _DEST2, _WHAT2, now=_T + 2)    # ③ 真改派
    _n3 = len(_h3.saves)
    print(u'P3 派 / 催 / 改派 各一次 ⇒ 落盘 %d 次：%r' % (_n3, _h3.saves))
    if BEFORE:
        ok(u'P3 改前：**一次都不写**（`assign_errand` 里根本没有落盘调用）',
           _n3 == 0, u'次数=%d' % (_n3,))
    else:
        ok(u'P3 派与改派各写一次、**催不写**（没变化就别写盘）',
           _n3 == 2 and all(_h3.saves), u'次数=%d' % (_n3,))

    # ------------------------------------------------ P4 正控制：显式 force 两边都对
    # ★ 必须用**独立干净档**与**没在本探针里出现过的人**：借用 _P1 会让"改前一次都不写"
    #   这个前提反噬 —— 改前 _P1 压根没被创建，_h4 拿到的是空看板，于是这次派活属**新增**
    #   而非改派、given_up 恒 0 件，正控制会红在一条与本轮无关的断言上（夹具越界）。
    #   正控制只考一件事：显式 force 能把状态写进去、再读回来。
    _h4 = _Host(_P4)
    _h4.assign_errand('susie', _DEST, _WHAT, now=_T + 40)
    _ok4 = _h4._npc_errand_save(force=True)
    _h4b = _Host(_P4)
    _nid4 = list(_h4b.npc_errand._active.keys())
    ok(u'P4 正控制：显式 `force` 落盘两边都成立（证明不是"连写盘都坏了"）',
       _ok4 is True and len(_h4b.npc_errand) == 1 and _nid4 == ['susie'],
       u'写入=%s 在办=%d 是谁=%s' % (_ok4 is True, len(_h4b.npc_errand), _nid4))

    # ------------------------------------------------ P5 办完那一拍（结构性变化）
    # ★ 夹具：`work=1.0` 让他 1 秒就干完；中间**真跑一拍 tick**（`_T+0.5`，到岗 + 压位置）
    #   —— 那一拍会**真写一次盘**，于是"上一次落盘"就在半秒前，正是真实稳态
    #   （人在外头时 tick 每 ≤120s 写一次）。这半秒内他办完 ⇒ 节流窗口里发生了**结构性变化**。
    _h5 = _Host(_P5)
    _h5.assign_errand('ralsei', _DEST, _WHAT, now=_T, travel=0.0, work=1.0)
    _h5._npc_errand_tick(_T + 0.5)          # 到岗（traveling→working），压位置 ⇒ 写一次盘
    _h5._npc_errand_tick(_T + 2.0)          # 办完（working→done）—— 距上次落盘 1.5 秒
    _h5b = _Host(_P5)
    _n5_act = len(_h5b.npc_errand)
    _n5_done = len(_h5b.npc_errand.done)
    _r5 = _h5b.npc_errand.result_of('ralsei')
    print(u'P5 派活 → 到岗（写盘一次）→ 1.5 秒内办完 → 崩溃重启：在办 %d 条 / 已办 %d 条 / 结果 %r'
          % (_n5_act, _n5_done, _r5[:12]))
    if BEFORE:
        ok(u'P5 ★★ 改前：办完那一拍被节流挡住 ⇒ 重启后他**又出门一次**（在办 1 条、结果为空）',
           _n5_act == 1 and _n5_done == 0 and not _r5,
           u'在办=%d 已办=%d' % (_n5_act, _n5_done))
    else:
        ok(u'P5 ★★ 结构性变化立刻落盘 ⇒ 重启后**已办 1 条、结果一字不差、不会再出门**',
           _n5_act == 0 and _n5_done == 1 and bool(_r5),
           u'在办=%d 已办=%d' % (_n5_act, _n5_done))

    # ------------------------------------------------ P6 只压位置 ⇒ **不**强写（别乱写）
    # 这一条两边都该成立：改前压根不写，改后也必须**保持节流**。
    # 它的价值在负控制里 —— 把 tick 写成 `force=touched`（每拍写盘）时，这里必须变红。
    _h6 = _Host(_P6)
    _h6.assign_errand('susie', _DEST, _WHAT, now=_T, travel=0.0, work=300.0)
    _h6.saves.clear()
    _h6._npc_errand_tick(_T + 1.0)          # 到岗 + 压位置：没有结构变化
    _n6_force = _h6.saves.count(True)
    ok(u'P6 ★ 只把他压在目的地（无结构变化）⇒ **不**强写盘（节流保持，每拍写盘会拖垮主循环）',
       _n6_force == 0, u'强写=%d 次 / 总调用=%d 次' % (_n6_force, len(_h6.saves)))
finally:
    try:
        shutil.rmtree(_tmp, ignore_errors=True)
    except Exception:
        pass

print(u'')
if _n_fail:
    print(u'probe158（%s）：FAIL %d / PASS %d'
          % (u'改前基线' if BEFORE else u'改后', _n_fail, _n_pass))
    sys.exit(1)
print(u'probe158（%s）：%d 项全过' % (u'改前基线' if BEFORE else u'改后', _n_pass))
sys.exit(0)
