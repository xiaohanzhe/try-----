# -*- coding: utf-8 -*-
"""第94轮 · 真机全功能验收（基础宠物）：移动 / 睡眠 / 跳跃 / 拖拽 / 甩飞 / 托盘。

为什么必须真机（离线锁覆盖不到的部分）：
  · 离线套件（`check92/93` 等）钉的是**算法/表达式**，而"这段算法真的被产品的
    事件循环驱动起来了吗"只有把 `RalseiPet()` 真建出来、真跑定时器才能回答 ——
    本项目最贵的坑就是「**函数写对了 ≠ 产品用上了**」（89 轮血泪）。
  · 用户本次口径：「确保功能实现完全且符合要求」。

做法（同进程，`live_r4_76.py` 范式）：
  1) 先声明 DPI 感知（铁律）；
  2) `QApplication` + `RalseiPet()` 真建（**不是**离屏 mock）；
  3) **复刻真启动路径**（`main.py` 的 `__main__` 是 `window = RalseiPet()` +
     `window.show()`）—— 探针也必须 `show()`，否则 `IsWindowVisible` 恒 False、
     且许多"只在显示后才成立"的行为（z 序 / 可见性 / 分辨率适配）全都测不到；
  4) 每个功能：走**产品自己的入口**（`enter_sleep_mode` / `start_jump` /
     `start_falling` / `mousePressEvent`…），再用事件循环真跑一段时间；
  5) 断言读**状态 + 几何**（`current_animation` / `pos()` / `_fall_reason` …），
     不靠"看起来对"。

★ 判据纪律：正/负控制成对；每段独立 try，单段失败不拖垮其余段；
  全程记录窗口尺寸（本机约定：`46x82`=sleep / `42x82`=walk_down / `38x80`=walk_left）。

★★ 第94轮加固（针对"探针自己硬死"）：
  · `w()` **每次都 flush 落盘** ⇒ C 层崩溃也能看到最后活到哪一步；
  · **看门狗线程** + `faulthandler.dump_traceback()` ⇒ 真卡死时能拿到
    **全线程栈**（卡在 Qt 事件循环 / 锁 / GIL 一目了然），而不是事后猜。

★★ 第94轮夹具修复（都属于"探针自身缺陷"，不是产品 bug）：
  · S1.1 —— 漏 `show()` ⇒ 可见性判据恒假；
  · S3  —— `enter_sleep_mode()` 前没把 `last_interaction_time` 推远 ⇒
            落进"被吵醒"分支（`look_up` → 30ms 后 `wake_up()`），**夹具不保真**；
  · S4  —— `start_jump` 的 `target_window` 要**裸 dict**（不是 QRect），
            且给了 `target_pos` 就走"落点已定"的正路；
  · S5  —— 拖拽全程保留 `move` 劫持会污染"跟随"判据，拖拽前**还原真 `move`**。
"""
import ctypes
import faulthandler
import io
import os
import sys
import threading
import time

# ---------- ① 先声明 DPI 感知（必须在任何几何 / QApplication 之前） ----------
DPI = 'n/a'
try:
    if ctypes.windll.shcore.SetProcessDpiAwareness(2) == 0:
        DPI = 'PER_MONITOR_AWARE'
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
SRC = os.path.join(ROOT, 'ralsei_pet')
MODS = os.path.join(SRC, 'modules')
SRCDIR = os.path.join(SRC, 'src')
for _p in (SRCDIR, SRC, MODS):
    if _p not in sys.path:
        sys.path.insert(0, _p)

EVID = os.path.join(ROOT, 'code-quality-audit', '第94轮-基础宠物真机全功能验收', '_evidence')
try:
    os.makedirs(EVID, exist_ok=True)
except Exception:
    EVID = os.path.join(os.environ.get('TEMP', '.'), 'p94')
    os.makedirs(EVID, exist_ok=True)
OUT = os.path.join(EVID, 'probe94_full.txt')
FHFILE = os.path.join(EVID, 'probe94_full_faulthandler.txt')

_lines = []
_stats = {'pass': 0, 'fail': 0, 'skip': 0}
_progress = [time.time()]


def w(s=''):
    _lines.append(str(s))
    _progress[0] = time.time()
    try:
        print(s, flush=True)
    except Exception:
        pass
    # ★ 每次落盘：C 层硬崩也不丢"最后活到哪一步"
    try:
        io.open(OUT, 'w', encoding='utf-8', newline='\n').write('\n'.join(_lines))
    except Exception:
        pass


def check(name, cond, detail=''):
    """正/负控制成对：调用方必须给出"真的会发生"的 detail，否则红也说不清。"""
    tag = '[PASS]' if cond else '[FAIL]'
    if cond:
        _stats['pass'] += 1
    else:
        _stats['fail'] += 1
    w('%s %s%s' % (tag, name, ('  | ' + detail) if detail else ''))
    return bool(cond)


def skip(name, why):
    _stats['skip'] += 1
    w('[SKIP] %s  | %s' % (name, why))


def dump():
    try:
        io.open(OUT, 'w', encoding='utf-8', newline='\n').write('\n'.join(_lines))
    except Exception:
        pass


# ---------- 看门狗：真卡死时拿全线程栈（而不是"进程硬死，无输出"） ----------
_fh = None
try:
    _fh = io.open(FHFILE, 'w', encoding='utf-8')
    faulthandler.enable(file=_fh)
except Exception:
    _fh = None

_WD_LIMIT = 30.0


def _watchdog():
    while True:
        time.sleep(2.0)
        idle = time.time() - _progress[0]
        if idle > _WD_LIMIT:
            msg = '\n!!! 看门狗：主线程 %.1fs 无进展，转储全线程栈 !!!\n' % idle
            try:
                print(msg, flush=True)
                if _fh:
                    _fh.write(msg)
                    _fh.flush()
                faulthandler.dump_traceback(file=_fh if _fh else sys.stderr, all_threads=True)
                if _fh:
                    _fh.flush()
            except Exception:
                pass
            try:
                io.open(os.path.join(EVID, 'probe94_full_WATCHDOG.txt'),
                        'w', encoding='utf-8').write(msg)
            except Exception:
                pass
            os._exit(9)


try:
    threading.Thread(target=_watchdog, daemon=True, name='p94-watchdog').start()
except Exception:
    pass

_u = ctypes.windll.user32
_u.IsWindowVisible.argtypes = [ctypes.c_void_p]


def visible(hwnd):
    try:
        return bool(_u.IsWindowVisible(ctypes.c_void_p(int(hwnd))))
    except Exception:
        return None


w('=== 第94轮 · 真机全功能验收（基础宠物）===')
w('时间 = %s' % time.strftime('%Y-%m-%d %H:%M:%S'))
w('DPI  = %s' % DPI)
w('ROOT = %s' % ROOT)
w('看门狗阈值 = %.0fs（超时转储全线程栈）' % _WD_LIMIT)
w()

rc = 3
p = None
app = None
_orig_move = None
try:
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtCore import QPoint, QPointF, Qt, QEvent, QRect
    from PyQt5.QtGui import QMouseEvent
    app = QApplication.instance() or QApplication(sys.argv)
    QApplication.processEvents()

    w('---- S0. 屏幕 ----')
    scr = app.primaryScreen()
    w('  primaryScreen geometry = %r  available = %r'
      % (scr.geometry().getRect(), scr.availableGeometry().getRect()))
    w('  screenCount = %d' % len(app.screens()))
    for _i, _s in enumerate(app.screens()):
        w('    screen[%d] geom=%r available=%r dpr=%s'
          % (_i, _s.geometry().getRect(), _s.availableGeometry().getRect(),
             _s.devicePixelRatio()))
    w()

    w('---- S1. 起宠（真机，复刻 __main__ 的 RalseiPet() + show()）----')
    import main as main_mod
    w('  main.py = %s' % main_mod.__file__)
    t0 = time.time()
    p = main_mod.RalseiPet()
    w('  RalseiPet() 构造耗时 = %.2fs' % (time.time() - t0))
    app.processEvents()
    if not p.isVisible():
        p.show()          # ★ main.py:14972 就是这么干的
        w('  已补 show()（复刻真启动路径）')
    app.processEvents()
    time.sleep(0.3)
    app.processEvents()
    hwnd = int(p.winId())
    w('  hwnd = %d  Qt.isVisible = %r  Win32.IsWindowVisible = %r'
      % (hwnd, p.isVisible(), visible(hwnd)))
    w('  pos = (%d,%d)  size = %dx%d  dpr = %s'
      % (p.x(), p.y(), p.width(), p.height(), p.devicePixelRatioF()))
    check('S1.1 桌宠主窗口在真机上**可见**（Qt isVisible 与 Win32 IsWindowVisible 双口径）',
          bool(p.isVisible()) and visible(hwnd) is True,
          'qt=%r win32=%r' % (p.isVisible(), visible(hwnd)))
    # 负控制：拿一个不存在的 hwnd 必须判 False（证明判据不是恒真）
    check('S1.2 负控制：伪造 hwnd=0 判为不可见', visible(0) is False, 'hwnd=0')

    def size_of():
        try:
            return (p.width(), p.height())
        except Exception:
            return None

    def pump(seconds, dt=0.03):
        end = time.time() + seconds
        while time.time() < end:
            app.processEvents()
            time.sleep(dt)

    # ---- 位移监视（第92轮范式：劫持实例属性 move 量真实 delta） ----
    deltas = []
    _orig_move = p.move

    def _spy_move(x, y):
        try:
            ox, oy = p.x(), p.y()
            _orig_move(x, y)
            deltas.append((int(x) - ox, int(y) - oy))
        except Exception:
            _orig_move(x, y)

    p.move = _spy_move
    w()

    # ================================================= S2 移动
    w('---- S2. 移动（走起来）----')
    t_seg = time.time()
    try:
        p.is_sleeping = False
        p.last_interaction_time = time.time()
        p.is_moving = True
        try:
            p.generate_new_move_target()
        except Exception as e:
            w('  generate_new_move_target 抛：%r' % e)
        x0, y0 = p.x(), p.y()
        deltas.clear()
        pump(3.0)
        x1, y1 = p.x(), p.y()
        moved_px = abs(x1 - x0) + abs(y1 - y0)
        zero = sum(1 for d in deltas if d == (0, 0))
        nz = len(deltas) - zero
        w('  3s 内 move() 次数 = %d（零位移 %d / 非零 %d = %.1f%%）'
          % (len(deltas), zero, nz, (100.0 * nz / len(deltas)) if deltas else 0.0))
        w('  位置 (%d,%d) -> (%d,%d)  位移 = %d px' % (x0, y0, x1, y1, moved_px))
        check('S2.1 3s 内宠物发生了**真实位移**（>=5px，第92轮回归的真机复验）',
              moved_px >= 5, 'moved=%dpx' % moved_px)
        check('S2.2 位移不是靠"每帧 0px"堆出来的（非零位移占比 >=50%）',
              (not deltas) or (nz * 100.0 / len(deltas) >= 50.0),
              'nz=%d/%d' % (nz, len(deltas)))
    except Exception as e:
        import traceback
        w(traceback.format_exc())
        check('S2 移动', False, repr(e))
    w('  （S2 耗时 %.1fs）' % (time.time() - t_seg))
    w()

    # ================================================= S3 睡眠
    w('---- S3. 睡眠（第91轮修的点：必须播 sleep，且不被 update_animation 覆盖）----')
    t_seg = time.time()
    try:
        p.wake_up()
        pump(0.3)
        # ★ 夹具保真：`update_movement` 的"被吵醒"分支条件是
        #   `current_time - last_interaction_time < 1.0`。
        #   `wake_up()` 会把 `last_interaction_time = time.time()` ⇒ 若立刻
        #   `enter_sleep_mode()`，走的是"被吵醒"路径（`look_up` → 30ms 后醒来），
        #   `is_sleeping` 必然变回 False —— **那是夹具不保真，不是产品 bug**。
        #   正常入睡路径 = 空闲 `max_sleep_idle_duration` 之后 ⇒ 把互动时间推远。
        p.last_interaction_time = time.time() - 600.0
        for _a in ('_sleep_stir_time', '_sleep_stir_count'):
            if hasattr(p, _a):
                try:
                    delattr(p, _a)
                except Exception:
                    pass
        anim_before = p.current_animation
        p.enter_sleep_mode()
        pump(0.5)
        anims = [p.current_animation]
        sz = [size_of()]
        for _ in range(10):
            pump(0.25)
            anims.append(p.current_animation)
            sz.append(size_of())
        w('  入睡前动画 = %r' % anim_before)
        w('  入睡后动画序列 = %r' % anims)
        w('  窗口尺寸序列 = %r' % sz)
        w('  is_sleeping = %r' % getattr(p, 'is_sleeping', None))
        check('S3.1 enter_sleep_mode() 后 is_sleeping 为真', bool(p.is_sleeping))
        check('S3.2 睡眠动画是 **sleep**（不是 idle）——第91轮修复点',
              'sleep' in anims, 'anims=%r' % anims)
        check('S3.3 睡眠动画**保持稳定**（2.5s 末帧仍是 sleep；负控制：若被 update_animation 覆盖则会是 idle）',
              anims[-1] == 'sleep', 'last=%r' % anims[-1])
        p.wake_up()
        pump(0.3)
        check('S3.4 wake_up() 后 is_sleeping 为假且动画不是 sleep',
              (not p.is_sleeping) and p.current_animation != 'sleep',
              'anim=%r' % p.current_animation)

        # ---- S3.5 负控制①：守卫函数对 is_sleeping 的响应（正/负成对）----
        #   第94轮修复点 A：`pet_ai._skip_if_critical()` 原先把睡眠**漏**在守卫之外，
        #   于是 pet_ai 每 3 秒照常 trigger_action('idle') 把 sleep 顶成 idle。
        _ai = getattr(p, 'pet_ai', None)
        if _ai is None:
            skip('S3.5 pet_ai 守卫', '无 pet_ai 属性')
        else:
            _was = p.is_sleeping
            p.is_sleeping = True
            _a = _ai._skip_if_critical()
            p.is_sleeping = False
            _b = _ai._skip_if_critical()
            p.is_sleeping = _was
            w('  守卫 _skip_if_critical(): is_sleeping=True -> %r ; False -> %r' % (_a, _b))
            check('S3.5 负控制：pet_ai 守卫在睡眠时判 True（拦下 AI 动作）、清醒时判 False',
                  _a is True and _b is False, 'sleep=%r awake=%r' % (_a, _b))

        # ---- S3.6 负控制②：B 修复（force）的独立验证 —— 顶掉 sleep 后能否自愈 ----
        #   为什么必须独立测：A 修好后 pet_ai 不再触发 ⇒ B 那条 `force=True` 不会被走到，
        #   不给它一个入口，"写了但没验"。这里模拟任何外部系统把 sleep 顶掉。
        p.last_interaction_time = time.time() - 600.0
        p.enter_sleep_mode()
        pump(0.3)
        _orig_ca = p.change_animation          # 真函数（S3 未劫持，取到的就是原方法）
        _orig_ca('idle', force=True)
        app.processEvents()
        _h = None
        for _i in range(40):                   # 最多 4s
            pump(0.1)
            if p.current_animation == 'sleep':
                _h = (_i + 1) * 0.1
                break
        check('S3.6 睡眠中被顶成 idle 后能**自愈**回 sleep（force=True 生效；未修则被跨组冷却挡住）',
              _h is not None, '自愈耗时=%s 末态=%r'
              % (('%0.1fs' % _h) if _h is not None else '未自愈', p.current_animation))
        p.wake_up()
        pump(0.2)
    except Exception as e:
        import traceback
        w(traceback.format_exc())
        check('S3 睡眠', False, repr(e))
    w('  （S3 耗时 %.1fs）' % (time.time() - t_seg))
    w()

    # ================================================= S4 跳跃
    w('---- S4. 跳跃（真机轨迹：先升后降）----')
    t_seg = time.time()
    try:
        p.is_jumping = False
        p._jump_anim_override = None
        p.is_falling = False
        p.is_gravity_falling = False
        p._is_being_dragged = False
        p.wake_up()
        pump(0.2)
        # ★ 参数契约（main.py:7908）：`target_window` 是**裸 dict**（要 ['title'] /
        #   ['hwnd'] / ['x','y','width','height']），**不是 QRect** ——
        #   上一版传 QRect ⇒ `target_window['title']` 抛 TypeError（探针 bug）。
        #   这里走"原地弹跳"这条正路：`target_window=None`（跳桌面）+ 显式 `target_floor`
        #   + 显式 `target_pos`（落点已定，跳过启发式），Δy=0 ⇒ 干净的先升后降弧线。
        #   物理：gravity=500、jump_duration=1.0 ⇒ vy0 = -250px/s、顶点 ≈ -62px。
        sx4, sy4 = p.x(), p.y()
        p.start_jump(None, 'left',
                     target_floor=p.floor_manager.desktop_floor,
                     target_pos=QPoint(sx4, sy4))
        app.processEvents()
        if not getattr(p, 'is_jumping', False):
            skip('S4 跳跃', 'start_jump 未进入 is_jumping')
        else:
            w('  jump_duration=%.2f  gravity=%.0f  target_pos=(%d,%d)'
              % (getattr(p, 'jump_duration', -1), getattr(p, 'gravity', -1), sx4, sy4))
            ybase = p.y()
            y_series = []
            for _ in range(44):
                pump(0.05)
                y_series.append(p.y() - ybase)
            w('  y 相对偏移序列 = %r' % y_series)
            miny = min(y_series) if y_series else 0
            check('S4.1 起跳后**向上**（y 变小，负偏移）', miny < -5, 'min_dy=%d' % miny)
            check('S4.2 之后回落（末帧 y 回到基准附近）',
                  bool(y_series) and abs(y_series[-1]) <= max(5, abs(miny) * 0.6),
                  'last_dy=%r' % (y_series[-1] if y_series else None))
    except Exception as e:
        import traceback
        w(traceback.format_exc())
        check('S4 跳跃', False, repr(e))
    finally:
        # ★ 收口：无论 S4 走哪条分支，都必须把跳跃状态清干净，
        #   否则 `update_movement` 恒走 handle_jump 分支、拖拽/甩飞全被污染。
        try:
            p.is_jumping = False
            p._jump_anim_override = None
            app.processEvents()
        except Exception:
            pass
    w('  （S4 耗时 %.1fs）' % (time.time() - t_seg))
    w()

    # ================================================= S5 拖拽
    w('---- S5. 拖拽（鼠标按住拖走，宠物跟随）----')
    t_seg = time.time()
    try:
        # ★ 还原真 `move`：劫持版会把 S2 的位移记录混进来，且"跟随"判据
        #   应该量**产品自己**的 move 结果，不该经过探针包装。
        if _orig_move is not None:
            p.move = _orig_move
        p.wake_up()
        p.is_jumping = False
        p.is_falling = False
        p.is_gravity_falling = False
        p._is_being_dragged = False
        app.processEvents()
        # ★ 先摆到屏幕中央：桌宠默认在右下角，往 +x/+y 拖会被 `_clamp_pos_to_desktop`
        #   钳住（那是**正确**行为），会让"跟随"这条判据假红。
        _g = app.primaryScreen().availableGeometry()
        p.move(_g.center().x() - p.width() // 2, _g.center().y() - p.height() // 2)
        pump(0.4)
        sxp, syp = p.x(), p.y()
        sw0, sh0 = p.width(), p.height()
        w('  起点 = (%d,%d)  size=%dx%d' % (sxp, syp, sw0, sh0))
        local = QPointF(20.0, 20.0)
        g0 = QPointF(float(sxp + 20), float(syp + 20))
        ev_press = QMouseEvent(QEvent.MouseButtonPress, local, g0,
                               Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
        p.mousePressEvent(ev_press)
        app.processEvents()
        w('  press 后 drag_position=%r  _is_being_dragged=%r'
          % (getattr(p, 'drag_position', 'NA'), getattr(p, '_is_being_dragged', 'NA')))
        step = 0
        trail = []
        # ★ 中心基线 = **按下前**的真实中心；把 press 瞬间的尺寸跳变（walk 38x80 →
        #   idle 138x94）也纳入"中心必须连续"这条判据，否则会漏掉拖拽起手那一下。
        centers = [(sxp + sw0 // 2, syp + sh0 // 2, sw0)]
        for i in range(1, 21):
            gx = QPointF(float(sxp + 20 + i * 8), float(syp + 20 + i * 4))
            ev_move = QMouseEvent(QEvent.MouseMove, local, gx,
                                  Qt.NoButton, Qt.LeftButton, Qt.NoModifier)
            p.mouseMoveEvent(ev_move)
            app.processEvents()
            # ★★ 关键夹具保真：合成事件之间必须**睡眠**。
            #   不睡的话 20 个事件落在同一毫秒里 ⇒ `mouseReleaseEvent` 的
            #   "最近 120ms 窗口速度"算出 160px/0.001s = 160000px/s ⇒ 判成**甩飞**，
            #   宠物会飞出去 380px（上一版 S5.1 的 540 vs 160 就是**夹具不保真**，
            #   不是产品 bug）。真机鼠标事件间隔约 8~16ms，这里取 30ms 更稳
            #   （8px/0.03s ≈ 267px/s < 400 ⇒ 也不触发 run_* 切换）。
            time.sleep(0.03)
            trail.append((i, p.x() - sxp, p.y() - syp))
            centers.append((p.x() + p.width() // 2, p.y() + p.height() // 2, p.width()))
            step = i
        ev_rel = QMouseEvent(QEvent.MouseButtonRelease, local,
                             QPointF(float(sxp + 20 + step * 8), float(syp + 20 + step * 4)),
                             Qt.LeftButton, Qt.NoButton, Qt.NoModifier)
        p.mouseReleaseEvent(ev_rel)
        pump(0.3)
        exp_dx, exp_dy = step * 8, step * 4
        # ★ S5.1 量**角色中心**（= 窗口中心）而不是窗口左上角：放下后动画切回 `idle`
        #   （容器 69x47 → 138x94）会按中心重排窗口 ⇒ `p.x()` 变 -37px，但角色没动。
        _c0 = (sxp + sw0 // 2, syp + sh0 // 2)
        _c1 = (p.x() + p.width() // 2, p.y() + p.height() // 2)
        act_dx, act_dy = _c1[0] - _c0[0], _c1[1] - _c0[1]
        w('  鼠标移动 (%d,%d) -> 角色中心位移 (%d,%d)   [窗口左上角位移 (%d,%d)]'
          % (exp_dx, exp_dy, act_dx, act_dy, p.x() - sxp, p.y() - syp))
        w('  逐步轨迹 (i,dx,dy) = %r' % trail)
        check('S5.1 拖拽时宠物**跟随鼠标**（位移方向一致且量级相当）',
              act_dx > 0 and act_dy > 0 and abs(act_dx - exp_dx) <= 8,
              'dx=%d(exp %d) dy=%d(exp %d)' % (act_dx, exp_dx, act_dy, exp_dy))
        # ★★ S5.2 判据（第94轮修正 + 第94轮 C 修复后收紧）：
        #   原来量的是**窗口左上角**偏差（报 37px 红）—— 那是"刻意的设计取舍"，不是缺陷：
        #     · 动画切换时容器尺寸变化（`idle` 69x47 → 窗口 138x94；`walk_*` 19x40 → 38x80），
        #       渲染路径用 `setGeometry(按**中心**回算)` 缩放；
        #     · `_compose_anchored_sprite` 把角色 alpha 包围盒中心钉在画布中心、
        #       `sprite_label` 又是 AlignCenter ⇒ **窗口中心 = 角色中心**。
        #       所以"保中心"恰好保证角色在屏幕上不跳。
        #   真正的不变量 = **窗口中心（= 角色中心）随鼠标步长连续推进**。
        #   ⚠️ 修复前这里测到 11px：拖拽中窗口尺寸变化时，`drag_position` 是旧值 ⇒
        #      下一个 mouseMoveEvent 把左上角按旧偏移拽回 ⇒ 先窜后弹（实测约 44/18px）。
        #      C 修复（`drag_position` 同步平移同一个量）后**应为 0**，容差取 2。
        #   代价（设计取舍，非缺陷）：抓取偏移会随窗口尺寸变化而漂移 ——
        #      左上角不再恒等于"鼠标 − 初始 drag_position"，但角色中心始终钉在鼠标上。
        _worst_c = 0
        for _k in range(1, len(centers)):
            _dcx = centers[_k][0] - centers[_k - 1][0]
            _dcy = centers[_k][1] - centers[_k - 1][1]
            _worst_c = max(_worst_c, abs(_dcx - 8), abs(_dcy - 4))
        w('  左上角单步最大偏差 = %d px（抓取偏移漂移，设计取舍，非缺陷）'
          % max((abs(dx - i * 8) for (i, dx, dy) in trail), default=0))
        w('  窗口中心单步最大偏差 = %d px（期望 0；容器 38x80…138x94）' % _worst_c)
        check('S5.2 拖拽期间**窗口中心随鼠标连续推进**（角色在屏幕上不跳位；容差 2px）',
              _worst_c <= 2, 'worst_center_dev=%dpx' % _worst_c)
    except Exception as e:
        import traceback
        w(traceback.format_exc())
        check('S5 拖拽', False, repr(e))
    finally:
        try:
            p._is_being_dragged = False
            if hasattr(p, '_drag_speed'):
                delattr(p, '_drag_speed')
        except Exception:
            pass
    w('  （S5 耗时 %.1fs）' % (time.time() - t_seg))
    w()

    # ================================================= S6 甩飞
    w('---- S6. 甩飞 / 重力掉落（抛物线 + `_fall_reason is None`）----')
    t_seg = time.time()
    try:
        p.wake_up()
        p.is_jumping = False
        p._jump_anim_override = None
        p.is_falling = False
        p.is_gravity_falling = False
        p._is_being_dragged = False
        app.processEvents()
        try:
            p.move(p.x(), 80)          # 抬到屏幕上方，留出下落空间
        except Exception:
            pass
        app.processEvents()
        y_start = p.y()
        p.start_falling(fall_velocity=300, is_thrown=True, reason=None)
        app.processEvents()
        w('  start_falling 后：is_gravity_falling=%r  _is_thrown=%r  _fall_reason=%r'
          % (getattr(p, 'is_gravity_falling', None),
             getattr(p, '_is_thrown', None), getattr(p, '_fall_reason', None)))
        if not getattr(p, 'is_gravity_falling', False):
            skip('S6 甩飞', 'start_falling 被早退守卫拦下（拖拽/跳跃/施法/游戏中）')
        else:
            ys = [p.y()]
            for _ in range(30):
                pump(0.05)
                ys.append(p.y())
            w('  y 轨迹 = %r' % ys)
            check('S6.1 甩飞后确实**下落**（y 单调增大到停止）',
                  max(ys) - y_start >= 5, 'dy=%d' % (max(ys) - y_start))
            check('S6.2 「甩飞必 `_fall_reason=None`」契约未被破坏',
                  getattr(p, '_fall_reason', 'MISSING') is None,
                  '_fall_reason=%r' % getattr(p, '_fall_reason', 'MISSING'))
    except Exception as e:
        import traceback
        w(traceback.format_exc())
        check('S6 甩飞', False, repr(e))
    w('  （S6 耗时 %.1fs）' % (time.time() - t_seg))
    w()

    # ================================================= S7 托盘
    w('---- S7. 托盘（后台运行的唯一退出入口）----')
    t_seg = time.time()
    try:
        from PyQt5.QtWidgets import QSystemTrayIcon
        tray = getattr(p, '_tray', None)
        avail = QSystemTrayIcon.isSystemTrayAvailable()
        w('  系统托盘可用 = %r   _tray = %r' % (avail, type(tray).__name__ if tray else None))
        check('S7.1 `_tray` 已建', tray is not None)
        if tray is not None:
            check('S7.2 托盘图标**可见**（第51轮修的点：建了必须 show）', tray.isVisible())
            acts = []
            try:
                acts = [a.text() for a in tray.contextMenu().actions() if a.text()]
            except Exception as e:
                w('  读菜单失败：%r' % e)
            w('  菜单项 = %r' % acts)
            check('S7.3 菜单含"退出"入口', any(('退出' in t) for t in acts), 'acts=%r' % acts)
    except Exception as e:
        import traceback
        w(traceback.format_exc())
        check('S7 托盘', False, repr(e))
    w('  （S7 耗时 %.1fs）' % (time.time() - t_seg))
    w()

    w('=== 汇总 ===')
    w('  PASS=%d  FAIL=%d  SKIP=%d' % (_stats['pass'], _stats['fail'], _stats['skip']))
    rc = 0 if _stats['fail'] == 0 else 1

except SystemExit as e:
    rc = e.code or 0
except Exception:
    import traceback
    w('!! 真机验收异常：')
    w(traceback.format_exc())
    rc = 3
finally:
    dump()
    print('written:', OUT, flush=True)
    try:
        if p is not None:
            p.close()
    except Exception:
        pass
    try:
        a = QApplication.instance()
        if a:
            a.quit()
    except Exception:
        pass
    os._exit(rc)
