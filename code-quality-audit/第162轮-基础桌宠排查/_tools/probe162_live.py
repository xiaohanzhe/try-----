# -*- coding: utf-8 -*-
"""第162轮 · 基础桌宠真机演练（离屏，沙箱副本）。

为什么在 D 盘副本里跑：
  · 产品的 `data_store` 会优先写 `E:\\RalseiMemory\\`，而 E 盘是坏盘（读卡死）；
  · 同目录跑会改 `config.json` / `animation_history.json` / `logs/`，弄脏工作区
    （`git add -A` 会把这些当改动）；第107轮离屏测试把用户金库写脏过一次。
  所以先 robocopy 一份到 `D:\\_tmp\\pet162`，只在那里跑。

本支只做**事实收集**，不下结论：
  F1 构造 + show + 空转 6 秒：有没有异常、有没有 WARNING/ERROR
  F2 窗口事实：flags / 透明 / 几何 / 当前动画 / 精灵矩形 / 虚拟屏
  F3 空转 CPU 与 RSS（桌宠最容易被投诉的是"啥也没干就占 CPU"）
  F4 拖拽跟手：窗口位移是否 1:1 跟随鼠标
  F5 甩飞：松手后 2.5 秒必须落回虚拟屏内，且 `_fall_reason` 为 None
  F6 点身体：`pet_ai` 是否有反应（点击事件真的落到产品分支）
  F7 隐藏 / 托盘恢复往返
  F8 右键菜单：条目清单 + 每条是否连着槽（有没有"点了没反应"的项）
  F9 退出清理：`cleanup_on_exit()` 不抛

跑法：
    C:\\Python311\\python.exe probe162_live.py
"""
import os
import sys
import time
import json
import logging
import traceback

SANDBOX = r"D:\_tmp\pet162"
DATA = r"D:\_tmp\pet162_data"
LOG = r"D:\_tmp\pet162_probe.log"

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
os.environ['RALSEI_DATA_DIR'] = DATA
for _d in (DATA,):
    try:
        os.makedirs(_d, exist_ok=True)
    except Exception:
        pass

sys.path.insert(0, os.path.join(SANDBOX, 'modules'))
sys.path.insert(0, os.path.join(SANDBOX, 'src'))

# 绝不碰 E 盘：把"最终存储"这条路整体掐掉，只留 D 盘 staging
try:
    import memory_store as _ms
    _ms.find_device_dir = lambda create=True: None
except Exception as _e:
    print('[WARN] 打桩 memory_store 失败: %s' % _e, flush=True)
try:
    import data_store as _ds
    _ds.vault_root = lambda create=True: None
except Exception as _e:
    print('[WARN] 打桩 data_store 失败: %s' % _e, flush=True)

_FACTS = []


def fact(k, v):
    _FACTS.append((k, v))
    print('[FACT] %-28s = %s' % (k, v), flush=True)


def note(k, v):
    print('[NOTE] %-28s = %s' % (k, v), flush=True)


# ---- 日志捕获（WARNING 以上）----
_CAP = []


class _Sink(logging.Handler):
    def emit(self, rec):
        try:
            if rec.levelno >= logging.WARNING:
                _CAP.append('%-8s %s — %s' % (
                    rec.levelname, rec.name, rec.getMessage()))
        except Exception:
            pass


logging.getLogger().addHandler(_Sink())

_EXC = []


def _hook(t, v, tb):
    _EXC.append(''.join(traceback.format_exception(t, v, tb)))


sys.excepthook = _hook

from PyQt5.QtWidgets import QApplication            # noqa: E402
from PyQt5.QtCore import Qt, QPoint, QEvent, QTimer  # noqa: E402
from PyQt5.QtGui import QMouseEvent, QWheelEvent     # noqa: E402

app = QApplication(sys.argv)


def pump(ms):
    """跑真实事件循环 ms 毫秒（定时器 / 动画 / 物理都真转）。"""
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.005)


def cpu_rss():
    import psutil
    p = psutil.Process()
    return p.cpu_percent(interval=0.0), p.memory_info().rss / 1048576.0


# ---------------------------------------------------------------- F1 构造
try:
    from main import RalseiPet
    w = RalseiPet()
    w.show()
    t0 = time.time()
    pump(6000)
    fact('F1 构造+空转 6s', 'ok，耗时 %.1fs，异常 %d 条' % (time.time() - t0, len(_EXC)))
except Exception:
    print('[FATAL] 构造期崩溃:\n%s' % traceback.format_exc(), flush=True)
    sys.exit(2)

# ---------------------------------------------------------------- F2 事实
geo = w.geometry()
fact('F2 geometry', 'x=%d y=%d w=%d h=%d' % (geo.x(), geo.y(), geo.width(), geo.height()))
fact('F2 flags', '0x%x' % int(w.windowFlags()))
fact('F2 透明背景', bool(w.testAttribute(Qt.WA_TranslucentBackground)))
fact('F2 置顶标志', bool(w.windowFlags() & Qt.WindowStaysOnTopHint))
fact('F2 isVisible', w.isVisible())
fact('F2 current_animation', getattr(w, 'current_animation', '?'))
sl = getattr(w, 'sprite_label', None)
if sl is not None:
    sg = sl.geometry()
    fact('F2 sprite_label', 'x=%d y=%d w=%d h=%d' % (sg.x(), sg.y(), sg.width(), sg.height()))
    fact('F2 sprite->window 包含', w.rect().contains(sl.geometry()))
scr = app.primaryScreen()
fact('F2 screen', 'avail=%s geom=%s dpr=%s' % (
    scr.availableGeometry().getRect(), scr.geometry().getRect(), scr.devicePixelRatio()))
try:
    vr = w._virtual_screen_rect()
    fact('F2 virtual_rect', vr.getRect())
except Exception as e:
    fact('F2 virtual_rect', '不可用: %s' % e)

# ---------------------------------------------------------------- F3 空转开销
cpu_rss()
pump(1500)
cpu, rss = cpu_rss()
fact('F3 空转 CPU', '%.1f%%' % cpu)
fact('F3 RSS', '%.1f MB' % rss)
fact('F3 活动定时器', len([c for c in w.findChildren(QTimer) if c.isActive()]))

# ---------------------------------------------------------------- F4 拖拽
def send_press(pt):
    ev = QMouseEvent(QEvent.MouseButtonPress, pt, w.mapToGlobal(pt),
                     Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
    app.sendEvent(w, ev)


def send_move(pt, buttons=Qt.LeftButton):
    ev = QMouseEvent(QEvent.MouseMove, pt, w.mapToGlobal(pt),
                     Qt.NoButton, buttons, Qt.NoModifier)
    app.sendEvent(w, ev)


def send_release(pt):
    ev = QMouseEvent(QEvent.MouseButtonRelease, pt, w.mapToGlobal(pt),
                     Qt.LeftButton, Qt.NoButton, Qt.NoModifier)
    app.sendEvent(w, ev)


try:
    before = w.pos()
    start = w.rect().center()
    send_press(start)
    moved = QPoint(before.x() + 40, before.y() + 25)
    # 逐格移动，模拟真实拖拽（也喂足 _drag_samples）
    for i in range(1, 6):
        send_move(QPoint(start.x() + 8 * i, start.y() + 5 * i))
        pump(20)
    after = w.pos()
    fact('F4 拖拽位移', '期望 (+40,+25) 实际 (%+d,%+d)' % (after.x() - before.x(), after.y() - before.y()))
    send_release(QPoint(start.x() + 40, start.y() + 25))
    pump(300)
except Exception:
    note('F4 拖拽', '异常')
    _EXC.append(traceback.format_exc())

# ---------------------------------------------------------------- F5 甩飞
try:
    before = w.pos()
    start = w.rect().center()
    send_press(start)
    # 6 次 25px / 25ms = 1000 px/s，超过甩飞阈值
    for i in range(1, 7):
        send_move(QPoint(start.x() + 25 * i, start.y()))
        pump(25)
    send_release(QPoint(start.x() + 150, start.y()))
    fact('F5 松手瞬间', '_fall_reason=%r' % getattr(w, '_fall_reason', 'N/A'))
    pump(2500)
    g2 = w.geometry()
    vr = None
    try:
        vr = w._virtual_screen_rect()
    except Exception:
        vr = scr.availableGeometry()
    inside = vr.intersects(g2)
    fact('F5 2.5s 后落点', 'x=%d y=%d 在虚拟屏内=%s（vr=%s）' % (g2.x(), g2.y(), inside, vr.getRect()))
    fact('F5 落地原因', repr(getattr(w, '_fall_reason', 'N/A')))
except Exception:
    note('F5 甩飞', '异常')
    _EXC.append(traceback.format_exc())

# ---------------------------------------------------------------- F6 点击身体
try:
    reacted = {'n': 0}
    if hasattr(w, 'pet_ai'):
        _orig = w.pet_ai.react_to_event

        def _spy(ev, data, _o=_orig):
            reacted['n'] += 1
            return _o(ev, data)
        w.pet_ai.react_to_event = _spy
    c = sl.geometry().center() if sl is not None else w.rect().center()
    send_press(c)
    pump(30)
    send_release(c)
    pump(400)
    fact('F6 点击命中 sprite', 'pet_ai.react_to_event 调用 %d 次' % reacted['n'])
    fact('F6 双击/手势态', 'tracker=%r' % getattr(w, '_pet_tracker', 'N/A'))
except Exception:
    note('F6 点击', '异常')
    _EXC.append(traceback.format_exc())

# ---------------------------------------------------------------- F7 隐藏/恢复
try:
    w._hide_ralsei()
    pump(200)
    fact('F7 隐藏后 isVisible', w.isVisible())
    w._show_from_tray()
    pump(300)
    fact('F7 恢复后 isVisible', '%s pos=%s' % (w.isVisible(), w.pos()))
except Exception:
    note('F7 隐藏/恢复', '异常')
    _EXC.append(traceback.format_exc())

# ---------------------------------------------------------------- F8 右键菜单
try:
    from PyQt5.QtWidgets import QMenu
    holder = {}

    def _spy_exec(pos):
        # 不真的进模态循环，只把菜单抓出来
        holder['menu'] = None
    # 用 addAction 拦截的方式不可靠，这里直接重放构建逻辑：调用产品函数但把 exec_ 换掉
    _orig_exec = QMenu.exec_
    QMenu.exec_ = lambda self, *a, **k: holder.setdefault('menu', self)

    class _M(QMenu):
        pass
    try:
        w.show_interaction_menu(QPoint(w.x() + 10, w.y() + 10))
    finally:
        QMenu.exec_ = _orig_exec
    m = holder.get('menu')
    if m is None:
        fact('F8 右键菜单', '没抓到菜单对象')
    else:
        acts = m.actions()
        fact('F8 右键菜单条目数', len(acts))
        for a in acts:
            kids = a.menu().actions() if a.menu() else []
            txt = a.text() or '(分隔)'
            slots = 0
            try:
                slots = a.receivers(a.triggered) if hasattr(a, 'receivers') else -1
            except Exception:
                slots = -1
            fact('F8   · %s' % txt,
                 'submenu=%d connected=%s' % (len(kids), slots))
except Exception:
    note('F8 右键菜单', '异常')
    _EXC.append(traceback.format_exc())

# ---------------------------------------------------------------- F9 退出
try:
    w.cleanup_on_exit()
    fact('F9 cleanup_on_exit', 'ok')
except Exception:
    note('F9 cleanup_on_exit', '抛异常')
    _EXC.append(traceback.format_exc())

# ---------------------------------------------------------------- 汇总
print('\n===== 异常 %d 条 =====' % len(_EXC), flush=True)
for e in _EXC:
    print(e, flush=True)
print('\n===== 日志 WARNING+ %d 条（去重）=====' % len(_CAP), flush=True)
seen = {}
for c in _CAP:
    seen[c] = seen.get(c, 0) + 1
for c, n in sorted(seen.items(), key=lambda kv: -kv[1])[:20]:
    print('  x%-4d %s' % (n, c), flush=True)

with open(r'D:\_tmp\pet162_facts.json', 'w', encoding='utf-8') as f:
    json.dump(_FACTS, f, ensure_ascii=False, indent=1)
print('\n[DONE] 事实已写入 D:\\_tmp\\pet162_facts.json', flush=True)
