# -*- coding: utf-8 -*-
u"""第154轮 · 两条"假记忆"的实测探针（**改后复验**，可跑，不改任何东西）。

## 这份东西为什么存在

`check154` 是**锁**，`mutate154` 是**负控制**；两者都只能证明"现在的代码守住了"。
但本轮真正的发现不是"补了个功能"，而是**第一版会写下假话**——

| # | 场景 | 第一版写下的记忆 | 事实 |
|---|---|---|---|
| P1 | 同一件事重说一遍（地点、事由都一样） | 「又被派去 **oneshot** 办**「擦柜台」**了」 | 本来就是去那儿擦柜台 —— 自相矛盾 |
| P2 | 派发**失败**（看板在派发前被关掉，`assign` 返 `None`） | 「又被派去 **ut** 办了」 | 他**还在去 oneshot 的路上** |

⇒ 这份探针把三条场景**摆出来跑**：P1/P2 必须 0 条痕迹，P3（同地换事由）必须 1 条。
把这三条跑出来的结果贴在报告里，比"我改了"三个字有用。

## 做法

宿主从 `check154` 里**借**（`_Host` 是同一份桩）—— 不让探针和判据各有一套宿主，
否则两边不一致时代码没错、人先看晕。

⚠️ `check154` 结尾会 `sys.exit(1)`（它可能因为别的判据红），而这里只要它的**宿主**
⇒ 临时把 `sys.exit` 变成 no-op。**这会顺带打印出成功汇总行**（失败分支后面就是它），
所以本文件只取 `_Host`，不解析它的输出 —— 别拿那段输出当结论。
"""
import io
import os
import runpy
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
CHECK = os.path.join(HERE, 'check154.py')

_buf = io.StringIO()
_old_out, _old_exit = sys.stdout, sys.exit
sys.exit = lambda *a, **k: None
sys.stdout = _buf
try:
    NS = runpy.run_path(CHECK, run_name='__probe154__')
finally:
    sys.stdout = _old_out
    sys.exit = _old_exit

Host = NS['_Host']
DEST = NS['_DEST']
DEST2 = NS['_DEST2']
WHAT = NS['_WHAT']
WHAT2 = NS['_WHAT2']

_n_bad = 0


def check(desc, cond, extra=u''):
    global _n_bad
    if not cond:
        _n_bad += 1
    print(u'%s %s%s' % (u'[PASS]' if cond else u'[FAIL]', desc,
                        (u'  ' + extra) if extra else u''))


def notes(h):
    return [row[1] for row in h.npc_memory.log]


# ---- P1 同一件事重说一遍 ----
h1 = Host()
h1.assign_errand('ralsei', DEST, WHAT, now=0.0)
h1.assign_errand('ralsei', DEST, WHAT, now=1.0)
check(u'P1 同一件事重说一遍 ⇒ **零条**留痕（改前：1 条"又被派去同一个地方办同一件事了"）',
      len(notes(h1)) == 0, u'条数=%d' % (len(notes(h1)),))

# ---- P2 派发失败 ----
h2 = Host()
h2.assign_errand('ralsei', DEST, WHAT, now=0.0)
h2.npc_errand.enabled = False          # 派发那一刻看板被关 ⇒ assign 返 None
_r2 = h2.assign_errand('ralsei', DEST2, WHAT, now=1.0)
_act2 = getattr(h2.npc_errand.active_of('ralsei'), 'dest_scene', None)
check(u'P2 派发**失败** ⇒ **零条**留痕，且他实际还在原来那条（改前：写着"被派去 ut 了"）',
      _r2 is None and len(notes(h2)) == 0 and _act2 == DEST,
      u'返回=%r 条数=%d 在办=%s' % (_r2, len(notes(h2)), _act2))

# ---- P3 同地换事由（正控制：别把真改派一起吃掉）----
h3 = Host()
h3.assign_errand('ralsei', DEST, WHAT, now=0.0)
h3.assign_errand('ralsei', DEST, WHAT2, now=1.0)
_n3 = notes(h3)
check(u'P3 同一地点、**换了事由** ⇒ **仍留一条**（真改派，不能被判据吃掉）',
      len(_n3) == 1 and WHAT2 in _n3[0],
      u'条数=%d' % (len(_n3),))
if _n3:
    print(u'     实际写下的记忆：%s' % (_n3[0],))

print(u'')
print(u'probe154：%s' % (u'三项全对' if not _n_bad else u'有 %d 项不对' % _n_bad))
sys.exit(0 if _n_bad == 0 else 1)
