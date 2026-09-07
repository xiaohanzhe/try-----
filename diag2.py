"""持续诊断：每秒打印 Ralsei 状态，持续 15 秒，并截屏。"""
import sys, os, time
sys.path.insert(0, r'c:\Users\23002\Desktop\项目文件夹\try - 副本')

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer

app = QApplication(sys.argv)
from ralsei_pet.src.main import RalseiPet
pet = RalseiPet()
pet.show()

start_time = time.time()
print(f"{'t':>5s} {'pos':>22s} {'target':>18s} {'anim':>14s} {'dir':>6s} {'move':>5s} {'speed_x':>8s} {'speed_y':>8s} {'frame':>5s}")

def tick():
    elapsed = time.time() - start_time
    pos = pet.pos()
    tgt = pet.target_pos
    print(f"{elapsed:5.1f} "
          f"({pos.x():5d},{pos.y():5d}) "
          f"({tgt.x():5d},{tgt.y():5d}) "
          f"{pet.current_animation:>14s} "
          f"{pet.current_direction:>6s} "
          f"{'T' if pet.is_moving else 'F':>5s} "
          f"{pet.current_speed_x:8.2f} "
          f"{pet.current_speed_y:8.2f} "
          f"{pet.current_frame:5d}")

def stop():
    # 截屏
    try:
        from PIL import ImageGrab
        img = ImageGrab.grab()
        img.save(r'c:\Users\23002\Desktop\项目文件夹\try - 副本\screenshot2.png')
        print(f"\n📸 截屏完成")
    except Exception as e:
        print(f"截屏失败: {e}")
    print("\n诊断结束。")
    app.quit()

for i in range(16):
    QTimer.singleShot(i * 1000, tick)
QTimer.singleShot(16000, stop)

app.exec_()
