# -*- coding: utf-8 -*-
"""审查用冒烟测试：构造 RalseiPet 并运行，捕获所有未处理异常与异常日志。"""
import sys, os, traceback, io

ROOT = r"C:\Users\23002\Desktop\项目文件夹\try - 副本\ralsei_pet"
os.chdir(ROOT)
for p in (os.path.join(ROOT, 'src'), os.path.join(ROOT, 'modules'), ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

ERRORS = []
def hook(t, v, tb):
    ERRORS.append("".join(traceback.format_exception(t, v, tb)))
    print("[UNHANDLED]", t.__name__, v, flush=True)
    traceback.print_tb(tb)
sys.excepthook = hook

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer

import main as M

app = QApplication(sys.argv)
print("[SMOKE] 构造 RalseiPet ...", flush=True)
pet = M.RalseiPet()
print("[SMOKE] 构造完成", flush=True)
pet.show()

state = {'ticks': 0, 'anims': set()}
def probe():
    state['ticks'] += 1
    try:
        state['anims'].add(pet.current_animation)
        if state['ticks'] % 10 == 0:
            print(f"[PROBE {state['ticks']}] pos={pet.pos().x()},{pet.pos().y()} anim={pet.current_animation} "
                  f"floor={pet.current_floor.get('type') if pet.current_floor else None} "
                  f"jumping={pet.is_jumping} falling={pet.is_falling}/{pet.is_gravity_falling} "
                  f"energy={getattr(pet.energy_hunger,'energy',None)}", flush=True)
    except Exception as e:
        print("[PROBE-ERR]", repr(e), flush=True)
t = QTimer(); t.timeout.connect(probe); t.start(1000)

def finish():
    print("[SMOKE] 结束时动画集合:", sorted(a for a in state['anims'] if a), flush=True)
    print("[SMOKE] 未处理异常数:", len(ERRORS), flush=True)
    for e in ERRORS[:5]:
        print(e, flush=True)
    app.quit()

QTimer.singleShot(int(sys.argv[1]) if len(sys.argv) > 1 else 60000, finish)
app.exec_()
print("[SMOKE] 退出码 =", 0 if not ERRORS else 1, flush=True)
sys.exit(0 if not ERRORS else 1)
