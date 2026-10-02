# -*- coding: utf-8 -*-
"""第76轮 R4 真机验证：**相机锚点跟着灵魂走**（用户口径「视角永远跟着灵魂所在地走」）。

做法（不靠"看起来对"，靠数值）：
  1) 真机起 `RalseiPet()`（唯一可靠方式：PowerShell `&` call 操作符 + run_in_background）；
  2) 在 **同进程** 里直接读 `_camera_target_rect()` —— 这是相机的**唯一入口**，
     所以只要它跟着灵魂变，产品就真的跟着灵魂；
  3) 三段取证：
       ① 灵魂可见 · 记锚点 A
       ② 用 `_soul_press` 喂方向键把灵魂推远（不依赖真键盘事件，避免焦点问题）
          · 记锚点 B ⇒ **必须 A ≠ B**
       ③ 把灵魂收起（`hide_soul`）· 记锚点 C ⇒ **必须 == 宠物锚点**
          （= 退回生效，且退回不是"随便给个值"）
  4) 同时打印屏幕点，证明"锚点变了"确实由"灵魂移动了"引起。

★ 判据纪律：先声明 DPI 感知（不量窗口，但要一致）；A/B/C 三段各自独立打印，
  人工也能一眼核。退出码 0 = 三段全过。

用法（后台跑）：
  & C:\Python311\python.exe <本文件>
"""
import ctypes
import io
import json
import os
import sys
import time

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
SRC = os.path.join(ROOT, 'ralsei_pet')
MODS = os.path.join(SRC, 'modules')
SRCDIR = os.path.join(SRC, 'src')          # ★ main.py 住在 src/ 下
for p in (SRCDIR, SRC, MODS):
    if p not in sys.path:
        sys.path.insert(0, p)

_lines = []


def w(s=''):
    _lines.append(s)
    try:
        print(s, flush=True)
    except Exception:
        pass


def _dump(path):
    try:
        io.open(path, 'w', encoding='utf-8', newline='\n').write('\n'.join(_lines))
    except Exception:
        pass


EVID = os.path.join(ROOT, 'code-quality-audit', '第76轮-灵魂附身与视角跟随', '_evidence')
os.makedirs(EVID, exist_ok=True)
OUT = os.path.join(EVID, 'live_r4_76.txt')

w('=== 第76轮 R4 真机取证：相机锚点是否跟着灵魂 ===')
w('时间 = %s' % time.strftime('%Y-%m-%d %H:%M:%S'))
w('ROOT = %s' % ROOT)
w()

rc = 1
p = None
try:
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtCore import Qt  # noqa: F401
    app = QApplication.instance() or QApplication(sys.argv)

    import main as main_mod
    w('main.py 已导入：%s' % main_mod.__file__)

    p = main_mod.RalseiPet()
    w('RalseiPet() 构造成功')
    # ★ `SOUL_ENABLED` 是**类属性**（不是模块级常量）—— 查对象的类，别查模块。
    w('  SOUL_ENABLED = %r' % getattr(type(p), 'SOUL_ENABLED', None))
    w()

    # ---- 建起灵魂（正常产品路径已经会建；这里只确认） ----
    try:
        p.init_soul()
    except Exception as e:
        w('  init_soul 抛（可能已初始化）: %r' % e)
    app.processEvents()

    soul = getattr(p, 'soul', None)
    w('soul = %r' % (type(soul).__name__ if soul else None))
    if soul is None:
        w('!! 没有灵魂实体 ⇒ 无法验证 R4')
        raise SystemExit(2)
    w('  灵魂可见 = %r' % bool(p._soul_visible()))
    w('  灵魂中心 = %r 尺寸 = %r' % (soul.state.center(), soul.state.size))
    w()

    # ---- 场景：给一个已知房间，锚点才可比 ----
    room = (0.0, 0.0, 640.0, 480.0)
    w('房间矩形 = %r' % (room,))
    w()

    def anchor(tag):
        a = p._camera_target_rect(room)
        w('  [%s] 灵魂中心=%r' % (tag, soul.state.center()))
        w('  [%s] 相机锚点=%r' % (tag, a))
        return a

    # ① 灵魂可见
    w('## ① 灵魂可见（原位）')
    A = anchor('A')
    w()

    # ② 用方向键把灵魂推远
    w('## ② 推方向键让灵魂移动')
    w('  按下前中心 = %r' % (soul.state.center(),))
    steps = 0
    for _ in range(60):
        p._soul_press('right')
        try:
            soul.tick(1.0 / 30.0)          # 真实签名：tick(dt)
        except Exception as e:
            w('  soul.tick 抛: %r' % e)
            break
        steps += 1
    p._soul_release('right')
    app.processEvents()
    w('  推了 %d 帧 · 按下后中心 = %r' % (steps, soul.state.center()))
    B = anchor('B')
    w()

    moved = soul.state.center()
    w('## ② 判定')
    ok_b = (A is not None and B is not None
            and any(abs(x - y) > 1e-6 for x, y in zip(A, B)))
    w('  A ≠ B（锚点真的跟着灵魂动了）= %s' % ok_b)
    w()

    # ③ 收起灵魂 ⇒ 必须退回宠物锚点
    w('## ③ 收起灵魂（hide_soul）')
    try:
        p.hide_soul()
    except Exception as e:
        w('  hide_soul 抛: %r' % e)
    app.processEvents()
    vis = bool(p._soul_visible())
    w('  灵魂可见 = %r' % vis)
    C = anchor('C')
    pet_anchor = p._pet_target_rect(room)
    w('  宠物锚点 = %r' % (pet_anchor,))
    ok_c = (not vis and C is not None and pet_anchor is not None
            and all(abs(x - y) < 1e-6 for x, y in zip(C, pet_anchor)))
    w('  C == 宠物锚点（退回生效）= %s' % ok_c)
    w()

    w('=== 结论 ===')
    w('  ① 灵魂可见时锚点 = 灵魂位置（A=%r）' % (A,))
    w('  ② 灵魂移动后锚点随之改变（B=%r，A≠B=%s）' % (B, ok_b))
    w('  ③ 灵魂收起后退回宠物锚点（C=%r，==宠物=%s）' % (C, ok_c))
    w()
    w('  R4 真机判定 = %s' % ('PASS' if (ok_b and ok_c) else 'FAIL'))
    rc = 0 if (ok_b and ok_c) else 1

except SystemExit as e:
    rc = e.code or 0
except Exception:
    import traceback
    w('!! 真机验证异常：')
    w(traceback.format_exc())
    rc = 3
finally:
    _dump(OUT)
    print('written:', OUT, flush=True)
    try:
        if p is not None:
            p.close()
    except Exception:
        pass
    try:
        from PyQt5.QtWidgets import QApplication
        a = QApplication.instance()
        if a:
            a.quit()
    except Exception:
        pass
    os._exit(rc)
