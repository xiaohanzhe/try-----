# -*- coding: utf-8 -*-
u"""第155轮 · **可跑探针**：催一句，他会不会被打回起点（**改后复验**）。

## 为什么既有 `check155` 还要这个

`check155` 是**锁**（37 条），`mutate155` 是**负控制**（12 处破坏）。两者都只在
"现在的代码"上说话。而这个口子的起因是**一组具体数值**——把同一句话在
"他已经到了、正在办"时再说一遍：

| 量 | 改前 | 症状 |
|---|---|---|
| `status` | `working` → `traveling` | 进度清零 |
| `arrive_at` | 90 → 190 | 又要"再走一趟" |
| `finish_at` | 390 → 490 | 办完时间整体推后 |
| `working_positions()` | `[('ralsei', …)]` → `[]` | 位置钉住资格被撤 ⇒ 下一拍 `roam` 把他从目的地撤走 |
| 返回对象 | 新的（`is` 旧条 = False） | 宿主手里那份引用成孤儿 |
| ack 的 brief | 与第一次**一字不差**（118 字） | 模型说"好，我让他去了"，而他早已在那儿 |

⇒ 这份探针把上面每一行**再跑一遍**，把数值打出来。贴数值比"我改了"有用。

## 做法

宿主从 `check155` 里**借**（`runpy`）—— 不让探针和判据各有一套桩，
否则两边不一致时代码没错、人先看晕。
⚠️ `check155` 结尾会 `sys.exit(...)`，这里把它临时变成 no-op；**这会顺带打印
它的汇总行**，所以本文件只取 `_Host` / `_AckHost`，不解析它的输出。
"""
import io
import os
import runpy
import sys
import time as _time

HERE = os.path.abspath(os.path.dirname(__file__))
CHECK = os.path.join(HERE, 'check155.py')

_buf = io.StringIO()
_old_out, _old_exit = sys.stdout, sys.exit
sys.exit = lambda *a, **k: None
sys.stdout = _buf
try:
    NS = runpy.run_path(CHECK, run_name='__probe155__')
finally:
    sys.stdout = _old_out
    sys.exit = _old_exit

Host = NS['_Host']
AckHost = NS['_AckHost']
ER = NS['ER']
DEST = NS['_DEST']
DEST2 = NS['_DEST2']
WHAT = NS['_WHAT']
WHAT2 = NS['_WHAT2']
U_SAME = NS['_U_SAME']

_n_bad = 0


def check(desc, cond, extra=u''):
    global _n_bad
    if not cond:
        _n_bad += 1
    print(u'%s %s%s' % (u'[PASS]' if cond else u'[FAIL]', desc,
                        (u'  ' + extra) if extra else u''))


# ---- P1 已到（working）之后同一件事再说一遍 ----
h1 = Host()
e1 = h1.assign_errand('ralsei', DEST, WHAT, now=0.0)
h1.npc_errand.step(100.0)
_arr, _fin = e1.arrive_at, e1.finish_at
_wp = h1.npc_errand.working_positions()
e2 = h1.assign_errand('ralsei', DEST, WHAT, now=100.0)
print(u'  P1 数值：status=%s  arrive_at=%s  finish_at=%s  working_positions=%r'
      % (getattr(e2, 'status', None), getattr(e2, 'arrive_at', None),
         getattr(e2, 'finish_at', None), h1.npc_errand.working_positions()))
print(u'     改前同一步：status=traveling  arrive_at=190.0  finish_at=490.0  '
      u'working_positions=[]')
check(u'P1 ★ 催不改进度：同一个对象 · `working` · 90 仍是 90、390 仍是 390 · '
      u'位置还在 · 零记忆',
      e2 is e1 and getattr(e2, 'status', None) == ER.WORKING
      and getattr(e2, 'arrive_at', None) == _arr
      and getattr(e2, 'finish_at', None) == _fin
      and h1.npc_errand.working_positions() == _wp and bool(_wp)
      and len(h1.npc_memory.log) == 0)

# ---- P2 同一句话走**对话层**：模型拿到的提示变了 ----
h2 = AckHost()
h2.handle_errand_command(U_SAME)
_first = h2.chats[-1] if h2.chats else u''
_n0 = len(h2.chats)
# ★ 只推到"到点、正在办"（+100 秒），**不能**推到 `finish_at` 之后 ——
#   办完的差事会从 `_active` 移进 `done`，那时再"催"就是**重新派**（`prev=None`）。
#   第一版这里写的是 `step(1e18)`，P2 当场 red：不是产品错了，是**夹具越过了被测分支**。
h2.npc_errand.step(_time.time() + 100.0)
h2.handle_errand_command(U_SAME)
_nudge = h2.chats[-1] if len(h2.chats) > _n0 else u''
print(u'  P2 数值：首次 brief %d 字 / 催 brief %d 字（改前两者都是 118 字、逐字相同）'
      % (len(_first), len(_nudge)))
print(u'     催 brief 里含「已经在办」=%s  含「没有重新计时」=%s  含「已经在路上了」=%s'
      % (u'\u5df2\u7ecf\u5728\u529e' in _nudge,
         u'\u6ca1\u6709\u91cd\u65b0\u8ba1\u65f6' in _nudge,
         u'\u5df2\u7ecf\u5728\u8def\u4e0a\u4e86' in _nudge))
check(u'P2 ★ 催与首次说的不是同一句：催明说"已经在办 / 没有重新计时"，'
      u'不再说"已经在路上了"（改前：两句一字不差）',
      bool(_first) and bool(_nudge) and _nudge != _first
      and u'\u5df2\u7ecf\u5728\u529e' in _nudge
      and u'\u6ca1\u6709\u91cd\u65b0\u8ba1\u65f6' in _nudge
      and u'\u5df2\u7ecf\u5728\u8def\u4e0a\u4e86' not in _nudge)

# ---- P3 正控制：同地换事由 ⇒ 仍是**真的重新派** ----
h3 = Host()
e3a = h3.assign_errand('ralsei', DEST, WHAT, now=0.0)
h3.npc_errand.step(100.0)
e3b = h3.assign_errand('ralsei', DEST, WHAT2, now=100.0)
print(u'  P3 数值：新对象=%s  status=%s  arrive_at=%s（旧 %s）'
      % (e3b is not e3a, getattr(e3b, 'status', None),
         getattr(e3b, 'arrive_at', None), e3a.arrive_at))
check(u'P3 正控制：**换了事由** ⇒ 新对象 + 退回 `traveling` + 到达时间推后'
      u'（判据没宽成"同一个地方就都算催"）',
      e3b is not e3a and getattr(e3b, 'status', None) == ER.TRAVELING
      and getattr(e3b, 'arrive_at', 0.0) > e3a.arrive_at)

# ---- P4 门控拒时"催"⇒ 不写假记忆 ----
h4 = Host()
h4.assign_errand('ralsei', DEST, WHAT, now=0.0)
h4.npc_errand.step(100.0)
h4.gate_ok = False
e4 = h4.assign_errand('ralsei', DEST, WHAT, now=100.0)
print(u'  P4 数值：返回=%r  记忆条数=%d  看板在办地点=%r'
      % (e4 is not None, len(h4.npc_memory.log),
         getattr(h4.npc_errand.active_of('ralsei'), 'dest_scene', None)))
check(u'P4 ★ 门控拒时**同一件事**仍返旧条、**零记忆**（他人在目的地；'
      u'改前这一支会写下"我本来要去 X，但去不了"）',
      e4 is not None and len(h4.npc_memory.log) == 0)

print(u'')
print(u'probe155：%s' % (u'四项全对' if not _n_bad else u'有 %d 项不对' % _n_bad))
sys.exit(0 if _n_bad == 0 else 1)
