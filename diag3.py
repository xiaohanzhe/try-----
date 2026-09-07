"""30秒诊断（无截屏，避免 ImageGrab 崩溃）"""
import sys, os, time
sys.path.insert(0, r'c:\Users\23002\Desktop\项目文件夹\try - 副本')

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer

app = QApplication(sys.argv)
from ralsei_pet.src.main import RalseiPet
pet = RalseiPet()
pet.show()

start_time = time.time()
header = f"{'t':>5s} {'pos':>22s} {'target':>18s} {'anim':>14s} {'dir':>6s} {'move':>5s} {'speed_x':>8s} {'speed_y':>8s} {'fl':>8s}"
print(header, flush=True)

def tick():
    elapsed = time.time() - start_time
    pos = pet.pos()
    tgt = pet.target_pos
    ft = pet.current_floor.get('type', '?') if pet.current_floor else 'None'
    print(f"{elapsed:5.1f} ({pos.x():5d},{pos.y():5d}) ({tgt.x():5d},{tgt.y():5d}) "
          f"{pet.current_animation:>14s} {pet.current_direction:>6s} "
          f"{'T' if pet.is_moving else 'F':>5s} {pet.current_speed_x:8.2f} {pet.current_speed_y:8.2f} {ft:>8s}", flush=True)

def stop():
    print("\n诊断结束。", flush=True)
    app.quit()

for i in range(31):
    QTimer.singleShot(i * 1000, tick)
QTimer.singleShot(31000, stop)

app.exec_()
