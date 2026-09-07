"""诊断脚本：启动Ralsei，模拟躲猫猫流程，每帧记录关键状态并截图。
运行后观察 log.txt 和 diag_frames3/ 目录。"""
import os, sys, time, json, traceback

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'modules'))

LOG_FILE = os.path.join(os.path.dirname(__file__), 'diag_spell_log.txt')
FRAME_DIR = os.path.join(os.path.dirname(__file__), 'diag_frames3')
os.makedirs(FRAME_DIR, exist_ok=True)
_log_f = open(LOG_FILE, 'w', encoding='utf-8')
def log(msg):
    ts = f"[{time.strftime('%H:%M:%S')}.{int(time.time()*1000)%1000:03d}]"
    line = f"{ts} {msg}\n"
    _log_f.write(line)
    _log_f.flush()
    print(line, end='')

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer, QRect
from PyQt5.QtGui import QPixmap, QPainter

app = QApplication(sys.argv)
log("QApp created")

# 先杀掉已在运行的ralsei实例，避免单实例互斥锁冲突
import subprocess
try:
    subprocess.run(['taskkill', '/F', '/IM', 'python.exe', '/FI', 'WINDOWTITLE eq *Ralsei*'], capture_output=True, timeout=5)
except Exception:
    pass

from src.main import RalseiPet
log("imported main")

w = RalseiPet()
log("RalseiPet constructed")
w.show()
log("w.show() done")

t0 = time.time()
frame_idx = [0]

def capture_state():
    try:
        state = {
            't': round(time.time()-t0, 3),
            'spell_stage': getattr(w, '_spell_stage', None),
            'hide_stage': getattr(w, '_hide_stage', None),
            'current_anim': w.current_animation,
            'current_dir': getattr(w, 'current_direction', None),
            'spell_tgt_dir': getattr(w, '_spell_target_direction', None),
            'spell_frames_seen': getattr(w, '_spell_frames_seen', None),
            'spell_touched': getattr(w, '_spell_touched_flag', None),
            'spell_auto_sus': getattr(w, '_spell_auto_suspended', None),
            'is_moving': w.is_moving,
            'pos': (w.x(), w.y()),
            'spell_interrupt_reason': w._spell_interrupted_reason() if hasattr(w,'_spell_interrupted_reason') else None,
        }
        log("STATE: " + json.dumps(state, ensure_ascii=False))
        # 截图
        screen = QApplication.primaryScreen()
        if screen:
            pix = screen.grabWindow(0)
            if not pix.isNull():
                out = pix.copy(QRect(w.x()-50, w.y()-50, w.width()+200, w.height()+200).intersected(pix.rect()))
                out.save(os.path.join(FRAME_DIR, f"frame_{frame_idx[0]:03d}.png"))
        frame_idx[0] += 1
    except Exception as e:
        log("CAPTURE ERR: "+traceback.format_exc())

# 每 500ms 捕获一次
cap_timer = QTimer()
cap_timer.timeout.connect(capture_state)
cap_timer.start(500)

# 5s 后触发躲猫猫
def step1():
    log("=== step1: start_hide_and_seek_game() ===")
    try:
        w.start_hide_and_seek_game()
        log("step1 ok")
    except Exception:
        log("step1 ERR: "+traceback.format_exc())
QTimer.singleShot(5000, step1)

# 30s 后退出
def exit_app():
    log("=== timeout, exiting ===")
    _log_f.close()
    app.quit()
QTimer.singleShot(30000, exit_app)

log("entering app.exec_()")
sys.exit(app.exec_())
