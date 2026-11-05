# -*- coding: utf-8 -*-
"""第162轮 · 真图形界面截图（沙箱副本 D:\\_tmp\\pet162）。

离屏跑得出"逻辑对"，看不出"长得对不对"：精灵被裁、背景发黑、缩放糊、
位置离谱这类只有真画出来才看得见。本支开真窗口 → 等 6 秒 → 截屏（只截
宠物窗口外扩 40px 的那一块）→ 落 D 盘 → 自己退出。

跑法：
    C:\\Python311\\python.exe shot162.py
"""
import os
import sys
import time
import traceback

SANDBOX = r"D:\_tmp\pet162"
DATA = r"D:\_tmp\pet162_data"
os.environ['RALSEI_DATA_DIR'] = DATA
os.environ.pop('QT_QPA_PLATFORM', None)      # 真窗口，不走离屏

sys.path.insert(0, os.path.join(SANDBOX, 'modules'))
sys.path.insert(0, os.path.join(SANDBOX, 'src'))

try:
    import memory_store as _ms
    _ms.find_device_dir = lambda create=True: None
except Exception as e:
    print('[WARN] memory_store 打桩失败: %s' % e, flush=True)
try:
    import data_store as _ds
    _ds.vault_root = lambda create=True: None
except Exception as e:
    print('[WARN] data_store 打桩失败: %s' % e, flush=True)

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer

app = QApplication(sys.argv)
try:
    from main import RalseiPet
    w = RalseiPet()
    w.show()
except Exception:
    print('[FATAL] 构造失败:\n%s' % traceback.format_exc(), flush=True)
    sys.exit(2)

_shot = {'done': False}


def grab():
    try:
        g = w.frameGeometry()
        print('[RECT] pet=%d,%d %dx%d' % (g.x(), g.y(), g.width(), g.height()), flush=True)
        from PIL import ImageGrab
        pad = 40
        box = (max(0, g.x() - pad), max(0, g.y() - pad),
               g.x() + g.width() + pad, g.y() + g.height() + pad)
        img = ImageGrab.grab()
        print('[SCREEN] %dx%d' % img.size, flush=True)
        img.crop(box).save(r'D:\_tmp\shot162_pet.png')
        img.save(r'D:\_tmp\shot162_full.png')
        print('[OK] 截图已存 D:\\_tmp\\shot162_pet.png', flush=True)
        _shot['done'] = True
    except Exception:
        print('[FAIL] 截图失败:\n%s' % traceback.format_exc(), flush=True)
    finally:
        try:
            w.cleanup_on_exit()
        except Exception:
            pass
        app.quit()


QTimer.singleShot(6000, grab)
QTimer.singleShot(20000, app.quit)     # 兜底
app.exec_()
print('[DONE] shot done=%s' % _shot['done'], flush=True)
