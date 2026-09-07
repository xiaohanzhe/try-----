# -*- coding: utf-8 -*-
"""精简诊断：启动Ralsei，5s后触发躲猫猫，实时打印关键状态，35s退出。
读取输出分析有没有 spell 被 idle 打断、frames 是否达到 11、有没有 facing_mismatch。
"""
import os, sys, time, json, traceback

# sys.path
ROOT = os.path.dirname(os.path.abspath(__file__))
for p in (
    os.path.join(ROOT, 'ralsei_pet', 'src'),
    os.path.join(ROOT, 'ralsei_pet', 'modules'),
    os.path.join(ROOT, 'ralsei_pet'),
):
    if p not in sys.path:
        sys.path.insert(0, p)

LOG = os.path.join(ROOT, 'diag_real_log.txt')
ERR = os.path.join(ROOT, 'diag_real_err.txt')
_log_f = open(LOG, 'w', encoding='utf-8')
_err_f = open(ERR, 'w', encoding='utf-8')
def log(msg):
    ts = f"[{time.strftime('%H:%M:%S')}.{int(time.time()*1000)%1000:03d}]"
    line = f"{ts} {msg}\n"
    _log_f.write(line); _log_f.flush()
    print(line, end='')
def log_err(msg):
    _err_f.write(msg+"\n"); _err_f.flush()

# 重定向 stderr 方便发现任何异常
sys.stderr = _err_f

# 先杀一下可能残留的互斥锁占用的 python 进程
import subprocess
try:
    # 只杀带 cmdline 有 ralsei 的 python 进程，避免误杀：用 wmic 查
    r = subprocess.run(['wmic', 'process', 'where', "name='python.exe'", 'get', 'processid,commandline', '/format:csv'],
                       capture_output=True, text=True, timeout=5)
    for line in r.stdout.strip().splitlines():
        if 'ralsei' in line.lower() or 'diag_spell' in line.lower() or 'diag_real' in line.lower():
            parts = [x.strip() for x in line.split(',')]
            if len(parts) >= 3:
                pid = parts[-1]
                if pid.isdigit():
                    try: subprocess.run(['taskkill', '/F', '/PID', pid], capture_output=True, timeout=3)
                    except Exception: pass
except Exception:
    pass

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer
app = QApplication(sys.argv)
log("QApp ok")

try:
    from main import RalseiPet
    log("import RalseiPet ok")
except Exception:
    log("IMPORT ERR: "+traceback.format_exc())
    sys.exit(1)

try:
    w = RalseiPet()
    log("RalseiPet constructed ok")
    w.show()
    log("show ok")
except Exception:
    log("CONSTRUCT ERR: "+traceback.format_exc())
    sys.exit(1)

t0 = time.time()
hist = {'casting_count': 0, 'idle_during_casting': 0,
        'frames_seen_max': 0, 'reached_11': False,
        'facing_mismatch_ever': False,
        'any_spell_stage_ever': False}

import math
def tick():
    try:
        ss = getattr(w, '_spell_stage', None)
        hs = getattr(w, '_hide_stage', None)
        ca = w.current_animation
        cd = getattr(w, 'current_direction', None)
        tsd = getattr(w, '_spell_target_direction', None)
        fsn = getattr(w, '_spell_frames_seen', 0) or 0
        ir = None
        try:
            ir = w._spell_interrupted_reason()
        except Exception:
            ir = 'err'
        hist['frames_seen_max'] = max(hist['frames_seen_max'], fsn)
        if fsn >= 11:
            hist['reached_11'] = True
        if ss is not None:
            hist['any_spell_stage_ever'] = True
        if ss == 'casting':
            hist['casting_count'] += 1
            if ca not in ('spell', 'spell_left'):
                hist['idle_during_casting'] += 1
        if ir == 'facing_mismatch':
            hist['facing_mismatch_ever'] = True
        # 计算距离和 target_pos
        tgt = getattr(w, 'target_pos', None)
        cur_x, cur_y = w.x(), w.y()
        dst = None
        if tgt is not None:
            dst = int(math.hypot(tgt.x() - cur_x, tgt.y() - cur_y))
        hcb = getattr(w, '_hide_moving_cb', None)
        state = {
            't': round(time.time()-t0, 2),
            'spell_stage': ss,
            'hide_stage': hs,
            'cur_anim': ca,
            'cur_dir': cd,
            'tgt_dir': tsd,
            'frames_seen': fsn,
            'interrupt_reason': ir,
            'is_moving': w.is_moving,
            'game_playing': bool(getattr(w, 'game_state', {}).get('is_playing')),
            'pos': (cur_x, cur_y),
            'target': (tgt.x(), tgt.y()) if tgt else None,
            'dist_px': dst,
            'has_hide_cb': hcb is not None,
        }
        log("STATE " + json.dumps(state, ensure_ascii=False))
    except Exception:
        log("TICK ERR "+traceback.format_exc())

tmr = QTimer(); tmr.timeout.connect(tick); tmr.start(250)

def step1():
    log("=== STEP1: 触发躲猫猫 start_hide_and_seek_game() ===")
    try:
        w.start_hide_and_seek_game()
        log("STEP1 调用成功")
    except Exception:
        log("STEP1 ERR "+traceback.format_exc())
QTimer.singleShot(4000, step1)

def final():
    log("=== FINAL SUMMARY ===")
    log(json.dumps(hist, ensure_ascii=False, indent=2))
    # 障碍物检查
    desktop_dir = os.path.join(os.environ['USERPROFILE'], 'Desktop')
    if os.path.isdir(desktop_dir):
        obstacles = []
        for name in os.listdir(desktop_dir):
            if '障碍物' in name:
                p = os.path.join(desktop_dir, name)
                if os.path.isdir(p):
                    obstacles.append(name)
        log(f"桌面上现存'障碍物'文件夹: {obstacles}")
        # 如果有残留，尝试清理
        for name in obstacles:
            try:
                import shutil
                shutil.rmtree(os.path.join(desktop_dir, name), ignore_errors=True)
                log(f"  清理残留: {name}")
            except Exception: pass
    _log_f.close(); _err_f.close()
    app.quit()
QTimer.singleShot(90000, final)

log("=== START app.exec_(), 总时长 90s ===")
try:
    app.exec_()
except Exception:
    log("EXEC ERR "+traceback.format_exc())
print("诊断完成")
