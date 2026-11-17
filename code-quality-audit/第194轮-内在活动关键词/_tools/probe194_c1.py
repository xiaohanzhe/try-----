# -*- coding: utf-8 -*-
r"""probe194_c1.py —— 观测 `_trim_inner` 在灌满 85 条之后**到底删了谁**。

第194轮收口时用它查出「单跑 28/28、全量 25/28」的真因：
`check194` 的 B6 灌 85 条 `note_inner` 把库冲爆，`_trim_inner` 按
`(last_at, count)` **升序**删最老的，而「教室」是最先写入的那条 ——
它死不死取决于 85 条是否落在同一个 `time.time()` 刻度：
  · 机器快 ⇒ `last_at` 全等 ⇒ 退化成按 `count` 排 ⇒ `count=2` 侥幸活；
  · 机器慢 ⇒ `last_at` 被 `autosave()` 的写盘拉开 ⇒ 真 LRU ⇒ 排第一被裁。

现在 C1/D1/D2 已改成各自起干净库，这个坑在套件里不会再出现；
本脚本保留下来，供以后怀疑"限额 + 排序"类问题时直接观测。

用法：python probe194_c1.py            # 默认灌 85 条
      python probe194_c1.py 20         # 自定义条数（不超限时不裁，用来看基线）

★ 只读观测：不改被测状态、不碰真实记忆库（`RALSEI_MEMORY_DIR` 指临时目录）。
"""
import io
import os
import sys
import tempfile

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
PET = os.path.join(REPO, 'ralsei_pet')
MODS = os.path.join(PET, 'modules')

N = int(sys.argv[1]) if len(sys.argv) > 1 else 85

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
# ★ 必须在 import memory_system 之前设，否则会读到真实记忆库
_VAULT = tempfile.mkdtemp(prefix='probe194_')
os.environ['RALSEI_MEMORY_DIR'] = _VAULT
for _p in (os.path.join(PET, 'src'), MODS):
    if _p not in sys.path:
        sys.path.append(_p)

import memory_system as MSYS  # noqa: E402


class _P(object):
    api_enabled = False


ms = MSYS.MemorySystem(_P())
ms.keys = []           # 不继承盘上任何东西（否则观测到的是"继承 + 新建"的混合）

print(u'VAULT          = %s' % _VAULT)
print(u'INNER_KEYS_MAX = %r' % getattr(MSYS.MemorySystem, 'INNER_KEYS_MAX', '<缺>'))

ms.note_inner(u'盘算', who='ralsei', where=u'教室')
ms.note_inner(u'盘算', who='ralsei', where=u'教室')   # 2h 内重复 ⇒ 只加 count
ms.note_inner(u'盘算', who='ralsei', where=u'走廊')
print(u'写 2+1 条后 inner = %d' % len([k for k in ms.keys
                                       if k.get('kind') == 'inner']))

# ★ 先记住这 3 条初建条的 id，灌满后看谁不见了 —— 这才是"到底删了谁"
_seed = {}
for _k in ms.keys:
    if _k.get('kind') == 'inner':
        _seed[_k.get('id')] = str((_k.get('meta') or {}).get('where') or '')

for _i in range(N):
    ms.note_inner(u'想', who='ralsei', where=u'地点%d' % _i)

_inners = [k for k in ms.keys if k.get('kind') == 'inner']
_wheres = [str((k.get('meta') or {}).get('where')) for k in _inners]
_ts = [k.get('last_at') for k in _inners]
_alive = set(k.get('id') for k in _inners)
_dead_seed = [_w for _id, _w in _seed.items() if _id not in _alive]

print(u'灌 %d 条后 inner = %d' % (N, len(_inners)))
print(u'含「教室」= %d   含「走廊」= %d' % (_wheres.count(u'教室'),
                                            _wheres.count(u'走廊')))
print(u'keys 顺序前 3 = %r' % (_wheres[:3],))
print(u'keys 顺序后 3 = %r' % (_wheres[-3:],))
print(u'★ 初建 3 条里被裁掉的 = %r' % (_dead_seed,))
print(u'last_at 去重后档数 = %d（剩余 %d 条）' % (len(set(_ts)), len(_ts)))

# 最早的刻度档里有多少条、其中 count=1 的多少条 —— 决定「教室」会不会轮到被裁
if _ts:
    _t0 = min(_ts)
    _tier0 = [k for k in _inners if float(k.get('last_at') or 0) == float(_t0)]
    _tier0_c1 = [k for k in _tier0 if int(k.get('count') or 1) == 1]
    print(u'最早刻度档：共 %d 条，其中 count=1 的 %d 条'
          % (len(_tier0), len(_tier0_c1)))

print(u'机制：`_trim_inner` 按 (last_at, count) 升序取前 N 条删。')
print(u'  · 同刻度的条目里 count=1 的排在 count=2 的**前面** ⇒ 「教室」(count=2) 更安全；')
print(u'  · 但一旦 `autosave()` 把 `last_at` 拉开成逐条一档（机器慢 / 全量跑），')
print(u'    最早那一档里的 count=1 条目不够填满名额，就会轮到「教室」被裁。')

_hit = [h for h in ms.recall(u'教室', limit=6, reinforce=False)
        if h.get('kind') == 'inner']
print(u'此时 recall(教室) 命中 inner = %d' % len(_hit))
