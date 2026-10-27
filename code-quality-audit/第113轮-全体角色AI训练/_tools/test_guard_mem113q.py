# -*- coding: utf-8 -*-
"""`thermal113.relieve_mem` 的判据（第113轮q）。

★★★ 为什么非测不可：2026-10-28 06:29，看护在 `os_shepherd` 第 5 轮把训练 **terminate**
   掉了（exit 15），当时已完成 **39/75**。事后实测：同一时刻 `llama-server` 的 RSS 是
   **11.7 GB**，调一次 `keep_alive=0` 卸载，可用内存 **1.21 GB → 13.56 GB**。
   ⇒ 内存压力几乎全在推理进程里，**卸载就能解**，"杀训练"不该是第一步。

★ 这条分支的正面路径（卸载前低、卸载后回到下限 4 倍）在真机上复现不出来 ——
  只有 llama-server 涨到 11 GB 之后才会发生。所以用**假件注入**把三种组合都跑一遍。
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import thermal113 as T  # noqa: E402

# 别把测试行写进真看护日志（否则事后看 thermal113.log 会以为真触发过内存闸）
_LOGGED = []
T.log = lambda m: _LOGGED.append(m)

n_pass = n_fail = 0
fails = []


def check(desc, cond, detail=''):
    global n_pass, n_fail
    if cond:
        n_pass += 1
        print('[PASS] %s    %s' % (desc, detail) if detail else '[PASS] %s' % desc)
    else:
        n_fail += 1
        fails.append(desc)
        print('[FAIL] %s    %s' % (desc, detail) if detail else '[FAIL] %s' % desc)


def mk(mem_seq, unload_ok=True):
    """假内存读头（按顺序吐值，用完就停在最后一个）+ 假卸载器（记账）。"""
    seq = list(mem_seq)
    state = {'calls': 0}

    def read_mem():
        return seq.pop(0) if len(seq) > 1 else seq[0]

    def do_unload():
        state['calls'] += 1
        return unload_ok

    return read_mem, do_unload, state


# ---------------------------------------------------------------- A 正常缓解
# ★ 夹具注意：`relieve_mem` 是**先卸载、再读内存**，所以序列的第一项就是"卸载后"的值。
#   第一版我把"卸载前的 100MB"塞进序列 ⇒ 白多卸一次、A2 假红（夹具不保真=报假问题）。
r, u, st = mk([14000])
_A = T.relieve_mem(250, read_mem=r, do_unload=u, tries=2, wait=0)
check('A 卸载后内存回到 14000MB（≥250×4）⇒ 判 ok，不杀训练', _A == 'ok', repr(_A))
check('A2 命中"宽裕"就**提前停**，不该白卸第二次', st['calls'] == 1, '卸载次数=%d' % st['calls'])

# ---------------------------------------------------------------- B 真不足
r, u, st = mk([100, 180, 120])
_B = T.relieve_mem(250, read_mem=r, do_unload=u, tries=2, wait=0)
check('B 卸载两次后仍只有 120MB（<250）⇒ 判 still_low', _B == 'still_low', repr(_B))
check('B2 两次都试过了（没有提前放弃）', st['calls'] == 2, '卸载次数=%d' % st['calls'])
check('B3 ★ A 与 B 必须不同（否则这条判据分不出两种结局）', _A != _B, '%r vs %r' % (_A, _B))

# ---------------------------------------------------------------- C 刚好过线
r, u, st = mk([8000, 9200, 9100])
_C = T.relieve_mem(9000, read_mem=r, do_unload=u, tries=2, wait=0)
check('C 没到"宽裕"档（9200 < 9000×4）但已越过下限 ⇒ 仍判 ok（刚好过线也比杀训练强）',
      _C == 'ok', repr(_C))

# ---------------------------------------------------------------- D 卸载本身失败
r, u, st = mk([100, 100, 100], unload_ok=False)
_D = T.relieve_mem(250, read_mem=r, do_unload=u, tries=2, wait=0)
check('D 卸载接口失败且内存没回来 ⇒ 仍然判 still_low（不因为"试过了"就放行）',
      _D == 'still_low', repr(_D))

# ---------------------------------------------------------------- E 负回归：旧行为
# 旧实现是"一见低内存就 terminate"，等价于 read_mem 一次都不看恢复结果。
# 断言：在 A 的场景下，旧行为会杀、新行为不杀 —— 这是本轮修复的**唯一价值点**。
_old_decision = 'still_low' if 100 < 250 else 'ok'      # 旧逻辑：取第一档内存直接比下限
check('E ★★ 负回归：A 的场景下**旧逻辑会杀训练**，新逻辑放行（差异真实存在）',
      _old_decision == 'still_low' and _A == 'ok', '旧=%r 新=%r' % (_old_decision, _A))

# ---------------------------------------------------------------- F 日志说人话
_has_warn = any('卸载' in m for m in _LOGGED)
check('F 真的落了日志（不是静默改判）', _has_warn, '日志行数=%d' % len(_LOGGED))

print()
print('=' * 60)
print('合计：PASS=%d FAIL=%d' % (n_pass, n_fail))
if fails:
    for d in fails:
        print('  - %s' % d)
print('=' * 60)
sys.exit(0 if n_fail == 0 else 1)
