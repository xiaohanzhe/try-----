# -*- coding: utf-8 -*-
u"""rec118.py —— 第118轮**真机录屏**：四门「看得见就点得到」＋ 原作式选择框。

用户口径（逐字，10-19）
----------------------
「**可以，你自己录屏，记住，以人类的视角评价，也就是，你只认图案而非字符，ok？
然后继续推进就好**」

⇒ 两件事决定本文件的样子：

  ① **必须是录像，不是日志**。上一版（`probe118_doors.py`）已经用内省值证明了
     "四门各自进对了世界"，但那是**字符串层面**的证明（`scene_after` 变没变）。
     人类看到的是"屏幕左下角那道门点下去，画面变成了 UT 的坠落处"——
     录像能证这个，日志不能。
  ② **评审口径 = 图案**。所以本文件除了整屏 avi，还会落**1:1 裁图**：
     每扇门（带 40 px 上下文）、选择框（默认态 / 红心下移后）。这些裁图是给
     "人眼"看的，也是 `check118_rec.py` 做像素判据的输入。

录什么（一条 30 s 的连续片子，不分段拼接）
----------------------------------------
  P0  全景          —— 四门各在一条边上（人眼第一眼判断"位置对不对"）
  P1  走到 A 门 → 按 E → 进 OneShot 的坠落处 → 回桌面
  P2  走到 C 门 → 按 E → 进 UT 的坠落处     → 回桌面
  P3  走到 D 门 → 按 E → 进三角符文的小镇中心 → 回桌面
  P4  走到 B 门 → 按 E → **原作式选择框**弹出（黑框/金边/角上宝石/红心）
                     → 停 1.2 s（默认停在「我再考虑考虑」）
                     → ↑（红心移到「我确定」，这里要看它**真的跟着走**）
                     → Esc（取消，彩蛋到此为止，不进场景）
  P5  回桌面收尾

★ 为什么 A/C/D 先、B 最后：B 是彩蛋门，交互会弹**模态**选择框（`exec_()`），
  在它之前把三扇真门测完，片子节奏才不会被一坨模态框打断。

★★ 模态期间的重入（本文件唯一的技术陷阱，真机实测两次才对）
  `interact_scene_prop()` → `_niko_home_egg` → `dr_choice.choose()` → `exec_()`
  会开**嵌套事件循环**。而 Qt **不允许同一个 QTimer 在自己槽函数还没返回时再次触发**
  （`QTimerInfo::activateRef`）——
  ⇒ **第一版把 `interact_scene_prop()` 直接写在 `tick()` 里，结果模态那 8.3 s
     一帧都录不到**（`choice_1to1_*.png` 全缺，判据全部没有输入）。
  ⇒ 现在一律用 `QTimer.singleShot(0, …)` **派发到另一个定时器事件**，
     `tick()` 就能在模态期间继续呼吸。
  ★ 这条是"夹具不保真"，与产品无关：`probe118_egg4.py` 实测框开着时
    `↑` 能让 `_sel` 1→0，用户按键是**真的生效**的。

★ 沙箱三闸（`RALSEI_MEMORY_DIR` / `RALSEI_DATA_DIR` / `RALSEI_DESKTOP`）
  必须在 `import main` **之前**设（第116轮实证：顺序反了等于没设）。
  跑完用 `_shared/vault_guard.py diff` 独立复核用户记忆库。

跑法
----
  C:\\Python311\\python.exe code-quality-audit\\第118轮-桌面门可达性\\_tools\\rec118.py
逐帧判据见 `check118_rec.py`（**独立重读** avi + csv + 裁图，不信本脚本的实时统计）。
"""
import csv
import ctypes
import io
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')
SRC = os.path.join(PKG, 'src')
ASSETS = os.path.join(PKG, 'assets', 'scenes')
OUT = os.environ.get('REC118_OUT', os.path.join(ROUND, '_evidence', 'rec118'))
SECS = float(os.environ.get('REC118_SECS') or '34')
TICK_MS = int(os.environ.get('REC118_TICK_MS') or '100')
os.makedirs(OUT, exist_ok=True)
os.makedirs(os.path.join(OUT, 'shots'), exist_ok=True)

# ---- 沙箱三闸（必须在 import main 之前）----
_SB = tempfile.mkdtemp(prefix='rec118_')
for _s in ('vault', 'staging', 'desktop'):
    os.makedirs(os.path.join(_SB, _s), exist_ok=True)
os.environ['RALSEI_MEMORY_DIR'] = os.path.join(_SB, 'vault')
os.environ['RALSEI_DATA_DIR'] = os.path.join(_SB, 'staging')
os.environ['RALSEI_DESKTOP'] = os.path.join(_SB, 'desktop')
os.environ.setdefault('QT_QPA_PLATFORM', 'windows')

os.chdir(PKG)
if SRC in sys.path:
    sys.path.remove(SRC)
sys.path.insert(0, SRC)

import cv2                                                       # noqa: E402
import numpy as np                                               # noqa: E402
from PIL import Image                                            # noqa: E402
import main as M                                                 # noqa: E402
from PyQt5.QtCore import Qt, QTimer                              # noqa: E402
from PyQt5.QtGui import QKeyEvent                                # noqa: E402
from PyQt5.QtWidgets import QApplication                         # noqa: E402


def say(m):
    sys.stdout.write('[rec118] %s\n' % m)
    sys.stdout.flush()


M.check_single_instance()
M.install_crash_guard()
try:
    import data_store
    data_store.vault_root = lambda create=True: None
    data_store.migrate_from_staging()
except Exception:
    pass

app = QApplication(sys.argv)
window = M.RalseiPet()
window.show()
try:
    ctypes.windll.user32.SetProcessDPIAware()
except Exception:
    pass

_scr = app.primaryScreen()
_SCR_W, _SCR_H = _scr.geometry().width(), _scr.geometry().height()
# ★★★ 画布尺寸必须问产品（= 工作区，扣掉任务栏）；拿整屏会让门 B 落到任务栏里，
#   那是第117轮已经踩过一次的"夹具不保真"。
_W, _H = window._desktop_layer_size()
_W, _H = int(_W), int(_H)
say('shown pid=%d 整屏=%dx%d 画布=%dx%d' % (os.getpid(), _SCR_W, _SCR_H, _W, _H))
if (_SCR_W, _SCR_H) == (_W, _H):
    say('!! 警告：画布 == 整屏（任务栏没扣掉？）')

d = getattr(window, 'dialogue_ui', None)

_PREFIX = [('oneshot_black', 'A'), ('niko_door_portal', 'B'),
           ('desk_door_ut', 'C'), ('desk_door_deltarune', 'D')]
_FACE = {'A': 'up', 'B': 'down', 'C': 'left', 'D': 'right'}
SCENE_WANT = {'A': 'oneshot', 'C': 'ut', 'D': 'ch1'}


# ----------------------------------------------------------------- 产品内省
def _door_rects():
    u"""`{字母: (x,y,w,h)}` —— 直接问产品（`_desktop_screen_doors`），不自己算。"""
    out = {}
    try:
        for it in (window._desktop_screen_doors(_W, _H) or []):
            nm = str(it[0])
            for k, L in _PREFIX:
                if k in nm:
                    out[L] = tuple(it[1])
    except Exception as e:                                       # noqa: BLE001
        say('取门矩形失败 %r' % (e,))
    return out


def _door_alphas():
    out = {}
    try:
        for it in (window._desktop_screen_doors(_W, _H) or []):
            nm = str(it[0])
            for k, L in _PREFIX:
                if k in nm:
                    out[L] = float(it[2])
    except Exception:                                            # noqa: BLE001
        pass
    return out


def _scene_now():
    try:
        return str(getattr(window, 'current_scene', '') or '')
    except Exception:                                            # noqa: BLE001
        return ''


def _pet_box():
    try:
        fg = window.frameGeometry()
        return (fg.x(), fg.y(), fg.width(), fg.height())
    except Exception:                                            # noqa: BLE001
        return (0, 0, 0, 0)


def _modal():
    u"""当前可见的原作式选择框；没有 ⇒ `None`。

    ★ 不用 `QApplication.activeModalWidget()`：它在**隔离实验**里能用，
      但真机上依赖"谁是活动窗口"，宠物窗口是无边框半透明的、活动窗口未必是它。
      直接扫 `topLevelWidgets()` + `isVisible()`，**与 Qt 的模态簿记解耦**，
      两种情况下都成立。
    ★ 必须判 `isVisible()`：`accept()`/`reject()` 之后对象还在（只是隐藏），
      只按类名找会把"已关闭"误判成"还开着"（`probe118_egg4.py` 第一版踩到）。
    """
    try:
        for w in QApplication.topLevelWidgets():
            if type(w).__name__ == 'DrChoiceBox' and w.isVisible():
                return w
    except Exception:                                            # noqa: BLE001
        pass
    return None


# ----------------------------------------------------------------- 动作
def _stand_on(letter):
    r = _door_rects().get(letter)
    if not r:
        say('!! 缺门 %s 的矩形' % letter)
        return False
    fg = window.frameGeometry()
    cx = int(r[0] + r[2] // 2)
    cy = int(r[1] + r[3] // 2)
    window.move(cx - fg.width() // 2, cy - fg.height() // 2)
    try:
        window._interact_facing = _FACE[letter]
    except Exception:                                            # noqa: BLE001
        pass
    app.processEvents()
    say('站到门 %s：门矩形=%r 宠物中心=(%d,%d)' % (letter, r, cx, cy))
    return True


def _grab_arr():
    pm = _scr.grabWindow(0)
    img = pm.toImage()
    ptr = img.bits()
    ptr.setsize(img.byteCount())
    a = np.frombuffer(bytes(ptr), np.uint8).reshape(
        img.height(), img.bytesPerLine() // 4, 4)
    return np.ascontiguousarray(a[:, :img.width(), :3])


def _shot(name, arr, box=None, max_w=1400):
    u"""落一张图：`box` 给了就 1:1 裁（**不缩放**，人眼看形状就靠它）。

    ★★★ `arr` 是 **BGR**：`QImage.grabWindow()` 拿到的是 `Format_RGB32`，
      内存里是 BGRA、小端字节序 ⇒ `arr[y, x] = (B, G, R)`。
        · 喂 `cv2.VideoWriter` 要的就是 BGR ⇒ **原样写，对**；
        · 喂 `PIL.Image.fromarray` 会当 RGB 用 ⇒ **红蓝颠倒**。
      第118轮第一版就踩了：素材 `spr_heart_0.png` 是纯红 `(255,0,0)`
      （188 个不透明像素全红），裁图里那颗心量出来却是纯蓝 `(0,0,255)`
      —— 我差一步就报了"红心画成蓝的"这个**假 bug**。
      ⇒ 存图前必须 `[:, :, ::-1]`。（第117轮的裁图**也有这个错**，只是当时
      判的是"亮度/ΔE"，通道颠倒不改亮度，所以没暴露出来。）
    """
    try:
        sub = arr
        if box is not None:
            x, y, w, h = [int(v) for v in box]
            hh, ww = arr.shape[0], arr.shape[1]
            x0, y0 = max(0, x), max(0, y)
            x1, y1 = min(ww, x + w), min(hh, y + h)
            if x1 > x0 and y1 > y0:
                sub = arr[y0:y1, x0:x1]
        im = Image.fromarray(np.ascontiguousarray(sub[:, :, ::-1]))   # BGR → RGB
        if box is None and im.width > max_w:
            im = im.resize((max_w, int(im.height * max_w / float(im.width))),
                           Image.LANCZOS)
        p = os.path.join(OUT, 'shots', name + '.png')
        im.save(p)
        say('  shot → %s (%dx%d)' % (p, im.width, im.height))
        return p
    except Exception as e:                                       # noqa: BLE001
        say('  !! shot %s 失败 %r' % (name, e))
        return None


def _install_choice_spy():
    u"""给选择框每个"能让它结束"的入口装记录器。

    ★ 为什么需要：`probe118_egg2.py` 那一轮里，**我一次键都没发**，
      三轮对话却全部返回"选了「我确定！！！」"。到底是"代码里有人 accept"、
      "真按键"、还是"窗口被关"，不装记录器就只能猜 —— 而按第118轮自己的教训，
      **猜出来的根因比不写还危险**。
    """
    try:
        from modules import dr_choice as _dc
    except Exception as e:                                       # noqa: BLE001
        say('!! 装选择框记录器失败 %r' % (e,))
        return
    for name in ('keyPressEvent', 'mousePressEvent', 'mouseDoubleClickEvent',
                 'accept', 'reject', 'closeEvent'):
        orig = getattr(_dc.DrChoiceBox, name, None)
        if orig is None:
            continue

        def make(orig=orig, name=name):
            def f(self, *a, **kw):
                ev = a[0] if a else None
                extra = ''
                try:
                    if name == 'keyPressEvent' and ev is not None:
                        extra = ' key=%s' % (ev.key(),)
                    elif ev is not None and hasattr(ev, 'pos'):
                        extra = ' pos=%r' % (ev.pos(),)
                except Exception:                                # noqa: BLE001
                    pass
                say('  ● 框.%s%s sel=%r picked=%r'
                    % (name, extra, getattr(self, '_sel', None),
                       getattr(self, 'picked', None)))
                return orig(self, *a, **kw)
            return f
        try:
            setattr(_dc.DrChoiceBox, name, make())
        except Exception:                                        # noqa: BLE001
            pass


_install_choice_spy()


def _ctx(box, margin=40):
    x, y, w, h = [int(v) for v in box]
    return (x - margin, y - margin, w + margin * 2, h + margin * 2)


def _key(widget, k):
    u"""给控件喂一次真按键（走 `keyPressEvent`，不直接改内部状态）。

    ★ 用 `postEvent` 而不是 `QTest.keyClick`：后者要求控件有焦点；
      模态框在真机上焦点可能还没落下来。`postEvent` 直接投递到控件队列，
      实测（`probe118_egg4.py`）`↑` 能让 `_sel` 1 → 0，即**真的走到了 `keyPressEvent`**。
    """
    try:
        ev = QKeyEvent(QKeyEvent.KeyPress, k, Qt.NoModifier)
        QApplication.postEvent(widget, ev)
        app.processEvents()
        return True
    except Exception as e:                                       # noqa: BLE001
        say('  !! 喂键失败 %r' % (e,))
        return False


def _do_interact(letter):
    u"""真正调交互 —— **只能从 `singleShot` 里进来**（理由见 `_enter_step` 的长注释）。"""
    if _ST.get('interacting'):
        return
    _ST['interacting'] = True
    try:
        say('  调 interact_scene_prop()（门 %s）' % letter)
        ok = bool(window.interact_scene_prop())
    except Exception as e:                                       # noqa: BLE001
        say('  !! 门 %s 交互抛异常 %r' % (letter, e))
        ok = None
    finally:
        _ST['interacting'] = False
    say('  门 %s 交互返回 %r ⇒ 场景 = %s' % (letter, ok, _scene_now()))
    _ST['go_ret'] = (letter, ok)


# ----------------------------------------------------------------- 分镜
#: `(名字, 时长s, 进入动作)`；`进入动作` 只在**踏进这一步的那一帧**跑一次。
STEPS = [
    ('P0_pano', 3.4, None),
    ('P1_A_stand', 0.6, lambda: _stand_on('A')),
    ('P1_A_hold', 1.3, None),
    ('P1_A_go', 2.4, 'go:A'),
    ('P1_A_back', 1.4, 'back'),
    ('P2_C_stand', 0.6, lambda: _stand_on('C')),
    ('P2_C_hold', 1.3, None),
    ('P2_C_go', 2.4, 'go:C'),
    ('P2_C_back', 1.4, 'back'),
    ('P3_D_stand', 0.6, lambda: _stand_on('D')),
    ('P3_D_hold', 1.3, None),
    ('P3_D_go', 2.4, 'go:D'),
    ('P3_D_back', 1.4, 'back'),
    ('P4_B_stand', 0.6, lambda: _stand_on('B')),
    ('P4_B_hold', 1.3, None),
    ('P4_B_ask', 5.6, 'go:B'),
    ('P5_end', 1.2, None),
]
_SI = [-1]
_ST = {'t0': 0.0, 'interacting': False, 'egg_t': 0.0, 'egg_keys': 0,
       'egg_seen_at': None, 'egg_closed': False, 'back_t': 0.0,
       'shot': set(), 'go_ret': None, 'n': 0}


def _step_name():
    i = _SI[0]
    return STEPS[i][0] if 0 <= i < len(STEPS) else 'end'


def _enter_step(i):
    name, dur, act = STEPS[i]
    say('== %s（%.1f s）' % (name, dur))
    _ST['shot_ok'] = False
    if act is None:
        return
    if callable(act):
        act()
        return
    if isinstance(act, str) and act.startswith('go:'):
        letter = act.split(':', 1)[1]
        _ST['egg_t'] = time.time()
        _ST['egg_keys'] = 0
        _ST['egg_seen_at'] = None
        _ST['egg_closed'] = False
        # ★★★ 第118轮取证（真机实测，不是猜）：**绝不能在本 tick 里直接调**
        #   `interact_scene_prop()`。彩蛋门会开 `exec_()` 嵌套事件循环，而 Qt
        #   **不允许同一个 QTimer 在自己槽函数还没返回时再次触发**
        #   （`QTimerInfo::activateRef`）⇒ 第一版录屏在模态期间 **8.3 s 一帧都没有**，
        #   我的"抓默认态 / 发 ↑ / 发 Esc"一次都没机会跑（`choice_1to1_*.png` 全缺）。
        #   隔离实验 `probe118_modal.py` 里 `choose()` 是从**另一个** singleShot 起的，
        #   所以那边定时器照跑（2.6 s 涨 21 次）—— 差异就在这儿。
        #   ⇒ 派发到 `singleShot(0)`（另一个定时器事件），tick 就能继续呼吸。
        QTimer.singleShot(0, lambda L=letter: _do_interact(L))
        return
    if isinstance(act, str) and act == 'back':
        try:
            if _scene_now() != 'desktop':
                window.travel_to_scene('desktop')
        except Exception as e:                                   # noqa: BLE001
            say('  !! 回桌面失败 %r' % (e,))
        return


# ----------------------------------------------------------------- 主循环
RAW = os.path.join(OUT, 'rec118.avi')
_vw = cv2.VideoWriter(RAW, cv2.VideoWriter_fourcc(*'mp4v'),
                      max(1.0, 1000.0 / TICK_MS), (_SCR_W, _SCR_H))
if not _vw.isOpened():
    say('FATAL VideoWriter 打不开')
    sys.exit(2)

_csv = io.open(os.path.join(OUT, 'rec118_frames.csv'), 'w',
               encoding='utf-8', newline='')
_cw = csv.writer(_csv, lineterminator='\n')
COLS = ['i', 't', 'step', 'scene', 'pet_x', 'pet_y', 'pet_w', 'pet_h',
        'pet_cx', 'pet_cy', 'modal', 'dlg_x', 'dlg_y', 'dlg_w', 'dlg_h']
for L in 'ABCD':
    COLS += ['%s_alpha' % L, '%s_x' % L, '%s_y' % L, '%s_w' % L, '%s_h' % L]
_cw.writerow(COLS)

_t0 = time.time()


def tick():
    el = time.time() - _t0
    i = _SI[0]

    # ---- 推进分镜 ----
    if i < 0:
        _SI[0] = 0
        _ST['t0'] = el
        _enter_step(0)
    elif i < len(STEPS):
        if el - _ST['t0'] >= STEPS[i][1]:
            # 本步的"收尾抓图"（只在 hold 步抓，且只抓一次）
            _SI[0] = i + 1
            _ST['t0'] = el
            if _SI[0] < len(STEPS):
                _enter_step(_SI[0])

    # ---- 抓帧（无论 busy 与否都抓）----
    arr = _grab_arr()
    _vw.write(arr)

    step = _step_name()
    row = {'i': _ST['n'], 't': '%.3f' % el, 'step': step, 'scene': _scene_now()}
    px, py, pw, ph = _pet_box()
    row['pet_x'], row['pet_y'], row['pet_w'], row['pet_h'] = px, py, pw, ph
    row['pet_cx'], row['pet_cy'] = px + pw // 2, py + ph // 2
    al = _door_alphas()
    for L, r in _door_rects().items():
        row['%s_alpha' % L] = '%.4f' % al.get(L, -1.0)
        row['%s_x' % L], row['%s_y' % L] = r[0], r[1]
        row['%s_w' % L], row['%s_h' % L] = r[2], r[3]
    mw = _modal()
    row['modal'] = int(bool(mw is not None and mw.isVisible()))
    if mw is not None and mw.isVisible():
        g = mw.frameGeometry()
        row['dlg_x'], row['dlg_y'] = g.x(), g.y()
        row['dlg_w'], row['dlg_h'] = g.width(), g.height()
    _cw.writerow([row.get(c, '') for c in COLS])

    # ---- 到点抓图 ----
    if step.endswith('_hold') and step not in _ST['shot']:
        L = step.split('_')[1]
        r = _door_rects().get(L)
        if r:
            _ST['shot'].add(step)
            _shot('door_%s_1to1' % L, arr, _ctx(r))
    if step == 'P0_pano' and 'pano' not in _ST['shot']:
        if el > 1.6:
            _ST['shot'].add('pano')
            _shot('pano_%dx%d' % (_SCR_W, _SCR_H), arr)

    # ---- 模态框（原作式选择框）：抓"默认态" → ↑ → 抓"移动后" → Esc ----
    #   ★★★ 为什么**不按分镜步名**驱动：`exec_()` 开的是**嵌套事件循环**，
    #     我们自己的 tick 在里面照样触发 ⇒ 分镜可能先走完、框还开着。
    #     用步名当闸 = "框没人关 ⇒ 永久卡死"。⇒ 只看"框还在不在" + `egg_keys` 状态机。
    mw = _modal()
    if mw is not None and mw.isVisible():
        if _ST['egg_seen_at'] is None:
            _ST['egg_seen_at'] = time.time()
            say('选择框出现（几何=%r）' % (mw.frameGeometry(),))
        dt = time.time() - _ST['egg_seen_at']
        g = mw.frameGeometry()
        if _ST['egg_keys'] == 0 and dt > 1.2:
            _shot('choice_1to1_default', arr,
                  (g.x() - 30, g.y() - 30, g.width() + 60, g.height() + 60))
            say('  抓默认态（红心应停在第二行「我再考虑考虑」）')
            _key(mw, Qt.Key_Up)
            _ST['egg_keys'] = 1
        elif _ST['egg_keys'] == 1 and dt > 2.4:
            _shot('choice_1to1_moved', arr,
                  (g.x() - 30, g.y() - 30, g.width() + 60, g.height() + 60))
            say('  ↑ 已发送 ⇒ 抓移动后（红心应移到第一行「我确定」）')
            _key(mw, Qt.Key_Escape)
            _ST['egg_keys'] = 2
    elif _ST['egg_keys'] == 2 and not _ST.get('egg_closed'):
        _ST['egg_closed'] = True
        say('  选择框已关闭（Esc 生效）⇒ 彩蛋到此为止，场景仍是 %s' % _scene_now())

    # ---- 回桌面：`travel_to_scene` 可能要走几跳 ⇒ 在本步内**重试**（每 0.5 s 一次），
    #      不重试的话 1.4 s 一到就进下一步，下一步 `_stand_on` 会在世界场景里摆位 ⇒ 全乱。
    if step.endswith('_back') and _scene_now() != 'desktop':
        if time.time() - _ST.get('back_t', 0.0) > 0.5:
            _ST['back_t'] = time.time()
            try:
                window.travel_to_scene('desktop')
            except Exception as e:                               # noqa: BLE001
                say('  !! 重试回桌面失败 %r' % (e,))

    _ST['n'] += 1
    if el >= SECS:
        return _finish()


def _finish():
    try:
        _csv.flush()
        _csv.close()
    except Exception:                                            # noqa: BLE001
        pass
    try:
        _vw.release()
    except Exception:                                            # noqa: BLE001
        pass
    el = time.time() - _t0
    say('录完 %d 帧 / %.2f s ⇒ **实测 %.2f Hz**' % (_ST['n'], el,
                                                    _ST['n'] / max(1e-6, el)))
    say('avi = %s (%.1f MB)' % (RAW, os.path.getsize(RAW) / 1048576.0))
    say('最终场景 = %s' % _scene_now())
    try:
        window.close()
    except Exception:                                            # noqa: BLE001
        pass
    app.quit()


_tm = QTimer()
_tm.timeout.connect(tick)
_tm.start(TICK_MS)
app.exec_()
say('done')
