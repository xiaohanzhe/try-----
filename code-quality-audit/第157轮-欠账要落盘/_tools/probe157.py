# -*- coding: utf-8 -*-
u"""第157轮探针：**重启之后，欠账还在不在**。

用法：
    python probe157.py --before   # 改前基线（断言"丢了"——证明 bug 真的存在）
    python probe157.py            # 改后（断言"回来了"）

## 量什么

| # | 量 | 改前 | 改后 |
|---|---|---|---|
| P1 | 派 3 次（A→B→C）→ 落盘 → **新宿主**读回：欠账还剩几件 | **0** | **2** |
| P2 | 同一时刻，**在办差事**读回几条 | 1 | 1 |
| P3 | 存档 JSON 顶层有没有 `given_up` 这个键 | 无 | 有 |
| P4 | 记忆窗口：重启 + 12 句闲聊之后，两件欠账还能不能取到 | 不能 | 不能 |
| P5 | 正控制：**不重启**时同一进程里欠账几件 | 2 | 2 |

P2 是关键对照：**差事活下来了、欠账死了** —— 说明丢的不是"整个看板"，而是
"欠账这件事从来没进过档"。P4 说明"靠记忆兜底"也不成立（`history_block` 只取最后 12 条）。

★ 纪律：临时文件只落系统 temp（用完即删）；零网络 / 零 UI / 零显示器；
  时间基准一律用 `_time.time()`（从 0 起算会被 TTL 当成陈年旧账全滤掉，第156轮踩过）。
"""
import io
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
from modules import npc_persona as NP                       # noqa: E402
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


class _Host(object):
    u"""轻宿主：**只挂产品函数**（含 save/load），路径注进来（同 `check150 _DiskHost`）。

    ★ 与 check150 同一套顺序：先 `_npc_errand_load()`（它顺手把路径定下来），
      读不到文件也只是返 `None`。这是产品的真实顺序，不是捷径。
    """

    _npc_errand_note = RalseiPet._npc_errand_note
    _errand_note = RalseiPet._npc_errand_note
    assign_errand = RalseiPet.assign_errand
    _npc_errand_save = RalseiPet._npc_errand_save
    _npc_errand_load = RalseiPet._npc_errand_load

    def __init__(self, path):
        self._path = path
        self.npc_registry = NS.load_registry()
        self._npc_aliases = NP.address_aliases(
            [(n.id, n.name, n.name_cn) for n in self.npc_registry.all()])
        self.npc_memory = _Mem()
        self._npc_talking = 'ralsei'
        self._errand_given_up = {}
        self._npc_errand_last_save = 0.0
        self.npc_errand = self._npc_errand_load() or ER.ErrandBoard()

    def _npc_errand_file(self):
        return self._path

    def _npc_errand_gate(self, npc_id, dest):
        return (True, u'')

    def npc_label(self, npc_id):
        return npc_id


_tmp = tempfile.mkdtemp(prefix='probe157_')
_path = os.path.join(_tmp, 'npc_errands.json')
_T = _time.time()

try:
    _h1 = _Host(_path)
    _h1.assign_errand('ralsei', _DEST, _WHAT, now=_T)
    _h1.assign_errand('ralsei', _DEST2, _WHAT2, now=_T + 10)
    _h1.assign_errand('ralsei', _DEST3, _WHAT3, now=_T + 20)

    _in_proc = _errand_given_up_of(_h1, 'ralsei', now=_T + 30)
    print(u'== 改前基线 ==' if BEFORE else u'== 改后 ==')
    print(u'派三次之后（**同一进程、未重启**）：欠账 %d 件 ⇒ %r'
          % (len(_in_proc), _in_proc))
    _saved = _h1._npc_errand_save(force=True)
    print(u'落盘：%s（%s）' % (_saved, _path))
    try:
        with io.open(_path, encoding='utf-8') as _fh:
            _raw = __import__('json').load(_fh)
        _keys = sorted(_raw.keys())
    except Exception as _e:
        _raw, _keys = {}, [u'<读盘失败: %s>' % (_e,)]
    print(u'存档顶层键：%r' % (_keys,))

    # ---- 模拟重启：新对象、从盘上读回 ----
    _h2 = _Host(_path)
    _after = _errand_given_up_of(_h2, 'ralsei', now=_T + 30)
    print(u'重启之后：在办差事 %d 条 / 欠账 %d 件 ⇒ %r'
          % (len(_h2.npc_errand), len(_after), _after))
    print(u'')

    if BEFORE:
        ok(u'P1 ★★★ 改前：重启之后欠账**一件都不剩**（这就是本轮要修的东西）',
           len(_after) == 0, u'件数=%d' % (len(_after),))
    else:
        ok(u'P1 ★★★ 重启之后两件欠账**都回来了**，且顺序仍是"老 → 新"',
           [d for d, _w in _after] == [_DEST, _DEST2],
           u'件数=%d 顺序对=%s' % (len(_after),
                                  [d for d, _w in _after] == [_DEST, _DEST2]))
        ok(u'P1b 事由（`what`）也一字不差地带回来了',
           [w for _d, w in _after] == [_WHAT, _WHAT2],
           u'事由对=%s' % ([w for _d, w in _after] == [_WHAT, _WHAT2],))

    ok(u'P2 ★ 对照：**在办差事**读回 1 条（它本来就落了盘）—— 丢的不是整个看板',
       len(_h2.npc_errand) == 1, u'条数=%d' % (len(_h2.npc_errand),))

    if BEFORE:
        ok(u'P3 改前：存档里**没有** `given_up` 键（欠账从未进档）',
           'given_up' not in _keys, u'键=%r' % (_keys,))
    else:
        ok(u'P3 存档里**有** `given_up` 键，且形状是 {npc_id: [[ts, dest, what], ...]}',
           u'given_up' in _keys and isinstance(_raw.get('given_up'), dict),
           u'键=%r' % (_keys,))

    # ---- P4 记忆兜底也不成立（前后都一样）----
    _notes = [t for _n, t, _w in _h1.npc_memory.log]
    _entries = ([{'text': t, 'who': 'ralsei'} for t in _notes]
                + [{'text': u'\u95f2\u804a%d' % (i,), 'who': 'player'}
                   for i in range(12)])
    _blk = NP.history_block(_entries, 'ralsei', max_lines=12) or u''
    ok(u'P4 ★★ 记忆兜底**不成立**：重启后再聊 12 句，两件欠账都出窗'
       u'（所以必须落盘，不能只靠"他会记得"）',
       _WHAT not in _blk and _WHAT2 not in _blk,
       u'命中=%d 段落非空=%s'
       % (len([x for x in (_WHAT, _WHAT2) if x in _blk]), bool(_blk)))

    ok(u'P5 正控制：**不重启**时欠账确实在（2 件）—— 证明不是"函数本身坏了"',
       len(_in_proc) == 2, u'件数=%d' % (len(_in_proc),))
finally:
    try:
        shutil.rmtree(_tmp, ignore_errors=True)
    except Exception:
        pass

print(u'')
if _n_fail:
    print(u'probe157（%s）：FAIL %d / PASS %d'
          % (u'改前基线' if BEFORE else u'改后', _n_fail, _n_pass))
    sys.exit(1)
print(u'probe157（%s）：%d 项全过' % (u'改前基线' if BEFORE else u'改后', _n_pass))
sys.exit(0)
