# -*- coding: utf-8 -*-
u"""第92轮真机取证探针："走不动/站桩"的**位移**实测。

为什么需要它（方法论）
----------------------
用户报的是**观感**（"他在这里站桩呢？？？"），唯一可信的判据是**真实位移**。
为此本探针做两件"元操作"（都**不改产品代码**）：

  1. **劫持实例属性 `pet.move`**：产品代码里全部写 `self.move(x, y)`，属性查找走实例
     字典 ⇒ 能拿到**每一次**移动尝试的 (x, y) 与真实 delta，直接量出
     "move() 被调用了但位移是 0"这个致命签名。
  2. **把采样挂在 `movement_timer.timeout` 的现有连接之后**（Qt 按连接顺序触发）
     ⇒ 采到的就是"`update_movement` 刚刚跑完"的瞬间状态。

⚠️ 起进程：**必须用 Bash 工具的 `run_in_background`**。实测
   `subprocess.Popen(DETACHED_PROCESS)` 起 GUI **失败**（秒退、日志 0 字节）。

A/B 对照（同一份代码、同一份配置，只切"位移是否结转余量"）
----------------------------------------------------------
  `PROBE_MODE=fix`    ：不动产品代码（= 修后行为）
  `PROBE_MODE=legacy` ：在每帧 `update_movement` **之前**把 `_subpixel_x/_y` 清零
                        ⇒ 等价于"取整丢掉的余量不结转"（= 修前行为），
                        且产品代码一行都不改（**负控制，不是回滚**）。

用法（Git Bash）
----------------
    PROBE_SECS=150 PROBE_MODE=fix \
    PROBE_OUT=<轮次>/_evidence/probe92_B_fix.tsv \
    C:/Python311/python.exe code-quality-audit/第92轮-宠物移动结算/_tools/probe92.py

配套分析：`analyze92.py`（同一把尺量修前修后）。
"""
import os
import sys
import time

HERE = os.path.abspath(os.path.dirname(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')
SRC = os.path.join(PKG, 'src')

OUT = os.environ.get(
    'PROBE_OUT',
    os.path.join(ROOT, 'code-quality-audit', '第92轮-宠物移动结算',
                 '_evidence', 'probe92_ab.tsv'))
MODE = os.environ.get('PROBE_MODE', 'fix').lower()
DURATION = float(os.environ.get('PROBE_SECS', '150'))

os.chdir(PKG)
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from PyQt5.QtWidgets import QApplication      # noqa: E402
from PyQt5.QtCore import QTimer                # noqa: E402

app = QApplication(sys.argv)

import main as m                               # noqa: E402

pet = m.RalseiPet()
pet.show()

fh = open(OUT, 'w', encoding='utf-8')
fh.write("t\tis_moving\tpos_x\tpos_y\ttgt_x\ttgt_y\tspeed\tvx\tvy\t"
         "anim\tactivity\tlocked\tsleeping\tmove_calls\tdx\tdy\n")
fh.flush()

t0 = time.time()
st = {"calls": 0, "last_x": None, "last_y": None, "dx": 0, "dy": 0,
      "zero": 0, "nonzero": 0}

_orig_move = pet.move


def _spy_move(x, y):
    """★ 核心：数每一次移动尝试，并算出**真实 delta**（零位移即"假走"）。"""
    st["calls"] += 1
    try:
        xi, yi = int(x), int(y)
    except Exception:
        xi, yi = -1, -1
    if st["last_x"] is not None:
        st["dx"] = xi - st["last_x"]
        st["dy"] = yi - st["last_y"]
        if st["dx"] == 0 and st["dy"] == 0:
            st["zero"] += 1
        else:
            st["nonzero"] += 1
    st["last_x"], st["last_y"] = xi, yi
    return _orig_move(x, y)


pet.move = _spy_move


def _locked():
    try:
        return int(bool(pet._special_anim_locked()))
    except Exception:
        return -1


def sample():
    try:
        p = pet.pos()
        tp = pet.target_pos
        row = [
            "%.3f" % (time.time() - t0),
            int(bool(pet.is_moving)),
            p.x(), p.y(), tp.x(), tp.y(),
            "%.2f" % float(pet.speed),
            "%.2f" % float(getattr(pet, "current_speed_x", 0)),
            "%.2f" % float(getattr(pet, "current_speed_y", 0)),
            str(pet.current_animation),
            str(getattr(pet, "current_activity", "")),
            _locked(),
            int(bool(getattr(pet, "is_sleeping", False))),
            st["calls"], st["dx"], st["dy"],
        ]
        fh.write("\t".join(str(c) for c in row) + "\n")
        fh.flush()
    except Exception as e:            # 采样本身出错也要留痕（别静默丢证据）
        try:
            fh.write("ERR\t%r\n" % (e,))
            fh.flush()
        except Exception:
            pass


if MODE == 'legacy':
    # legacy 模式：清余量的回调必须**排在** update_movement 之前（Qt 按连接顺序触发）
    try:
        pet.movement_timer.timeout.disconnect()
    except Exception:
        pass

    def _zero_carry():
        pet._subpixel_x = 0.0
        pet._subpixel_y = 0.0

    pet.movement_timer.timeout.connect(_zero_carry)
    pet.movement_timer.timeout.connect(pet.update_movement)

pet.movement_timer.timeout.connect(sample)


def done():
    try:
        fh.write("# END\t%.3f\tmove_calls=%d zero=%d nonzero=%d mode=%s\n"
                 % (time.time() - t0, st["calls"], st["zero"], st["nonzero"], MODE))
        fh.flush()
        fh.close()
    except Exception:
        pass
    app.quit()


QTimer.singleShot(int(DURATION * 1000), done)
print('PROBE START pid=%d mode=%s secs=%s out=%s' % (os.getpid(), MODE, DURATION, OUT))
sys.stdout.flush()
app.exec_()
print('PROBE DONE mode=%s move_calls=%d zero=%d nonzero=%d'
      % (MODE, st["calls"], st["zero"], st["nonzero"]))
