# -*- coding: utf-8 -*-
"""探针 D（只读）：`import main` 在离屏进程里可行吗 + 需要哪些前置。

决定 check114 的写法：
  · 若能 import ⇒ 判据可以**直接绑产品方法**跑（最保真）；
  · 若不能   ⇒ 只能 AST 提取函数体再 exec（次优，但仍是产品代码）。
★ 先建 QApplication（本项目铁律：裸进程脚本必须先建）。
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PROJ = os.path.join(ROOT, 'ralsei_pet')
for p in (os.path.join(PROJ, 'src'), PROJ, os.path.join(PROJ, 'modules')):
    if p not in sys.path:
        sys.path.insert(0, p)

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

t0 = time.time()
try:
    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    print('QApplication ok  %.2fs' % (time.time() - t0))
except Exception as e:
    print('QApplication FAILED: %r' % (e,))
    raise SystemExit(2)

t1 = time.time()
try:
    import main
    print('import main ok  %.2fs' % (time.time() - t1))
except Exception as e:
    import traceback
    print('import main FAILED: %r' % (e,))
    traceback.print_exc()
    raise SystemExit(3)

print('RalseiPet =', main.RalseiPet)
print('有 _npc_errand_gate:', hasattr(main.RalseiPet, '_npc_errand_gate'))
print('有 _npc_errand_world:', hasattr(main.RalseiPet, '_npc_errand_world'))
print('有 _npc_errand_world_uncached:', hasattr(main.RalseiPet, '_npc_errand_world_uncached'))
print('有 _npc_errand_load:', hasattr(main.RalseiPet, '_npc_errand_load'))
print('有 _npc_errand_save:', hasattr(main.RalseiPet, '_npc_errand_save'))
print('有 _npc_errand_note:', hasattr(main.RalseiPet, '_npc_errand_note'))
print('有 assign_errand:', hasattr(main.RalseiPet, 'assign_errand'))

# ---- 直接调 staticmethod 版本（无需实例）----
t2 = time.time()
try:
    f = main.RalseiPet._npc_errand_world_uncached
    for sid in ('desktop', 'oneshot.mainline.INIT', 'ut.rooms.room_start',
                'ch1.hometown.town_mid', 'ch1.card_castle.card_castle_1f',
                '不存在的场景', None, ''):
        print('  world_uncached(%-32r) = %r' % (sid, f(sid)))
    print('  8 次判定耗时 %.3fs' % (time.time() - t2))
except Exception as e:
    import traceback
    print('world_uncached FAILED: %r' % (e,))
    traceback.print_exc()

print('总耗时 %.2fs' % (time.time() - t0))
