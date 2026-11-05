# -*- coding: utf-8 -*-
"""第162轮 · 数据根不可用时产品怎么走（不打桩，模拟真实环境）。

E 盘实测：`os.listdir('E:\\RalseiMemory')` → `OSError(22, '函数不正确。')`。
真实启动时产品会走 `data_store.data_root()`；本支不拦它，看三件事：
  ① 启动会不会卡住/抛异常；
  ② 最终落在哪个根（vault 还是 staging）；
  ③ 记记忆 / 读记忆能不能成。
只读探查 + 一次写测（写到产品自己选的根，不额外造文件在仓库里）。
"""
import os
import sys
import time
import traceback

SANDBOX = r"D:\_tmp\pet162"
os.environ.pop('RALSEI_DATA_DIR', None)
os.environ.pop('QT_QPA_PLATFORM', None)
sys.path.insert(0, os.path.join(SANDBOX, 'modules'))
sys.path.insert(0, os.path.join(SANDBOX, 'src'))

from PyQt5.QtWidgets import QApplication
app = QApplication(sys.argv)

import data_store

t0 = time.time()
print('[ROOT] describe() = %s' % (data_store.describe(),), flush=True)
print('[ROOT] 耗时 %.2fs' % (time.time() - t0), flush=True)

t0 = time.time()
root, kind = data_store.data_root()
print('[ROOT] data_root = %r  kind=%s  耗时 %.2fs' % (root, kind, time.time() - t0), flush=True)

try:
    import memory_store as ms
    t0 = time.time()
    d = ms.find_device_dir(create=True)
    print('[MEM] find_device_dir = %r  耗时 %.2fs' % (d, time.time() - t0), flush=True)
    print('[MEM] 常量 = %r' % (getattr(ms, 'DEVICE_SUBDIR', '?'),), flush=True)
except Exception:
    print('[MEM] find_device_dir 抛异常:\n%s' % traceback.format_exc(), flush=True)

try:
    from main import RalseiPet
    t0 = time.time()
    w = RalseiPet()
    w.show()
    print('[APP] 构造完成 耗时 %.1fs' % (time.time() - t0), flush=True)
    end = time.time() + 3
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)
    print('[APP] 记忆条数 = %s' % (len(getattr(w, 'memory', []) or []),), flush=True)
    for attr in ('memory_system', 'data_root', '_data_root'):
        if hasattr(w, attr):
            v = getattr(w, attr)
            print('[APP] %s = %r' % (attr, v if not isinstance(v, dict) else list(v)[:6]), flush=True)
except Exception:
    print('[APP] 构造异常:\n%s' % traceback.format_exc(), flush=True)
    sys.exit(3)

# 写一次记忆，看它落哪儿、成不成
try:
    t0 = time.time()
    ok = None
    for name in ('remember', 'add_memory', 'save_memory'):
        fn = getattr(ms, name, None)
        if callable(fn):
            try:
                fn(u'第162轮探针：今天桌面宠物的脚好像压到任务栏了')
                ok = name
            except Exception:
                print('[MEM] %s 抛异常:\n%s' % (name, traceback.format_exc()), flush=True)
            break
    print('[MEM] 写入接口 = %s  耗时 %.2fs' % (ok, time.time() - t0), flush=True)
except Exception:
    print('[MEM] 写入异常:\n%s' % traceback.format_exc(), flush=True)

try:
    w.cleanup_on_exit()
except Exception:
    pass
app.quit()
print('[DONE]', flush=True)
