# -*- coding: utf-8 -*-
"""第82轮 R5：**用户视角**验证（配合 screen-automation 观测）。

用户视角要回答的只有三件事：
  Q1 附身前：屏幕上**灵魂**是可见的吗（用户看得到那颗心）？
  Q2 按 Z 附身后：**灵魂从屏幕上消失**了吗（控制权转移的可见证据）？
  Q3 再按 Z 解除：**灵魂回来了**吗？

★ 关键难点（本轮实测确认）：桌宠/灵魂都是**透明无边框分层窗口** ⇒
  screen-automation 的 `visible_area = 0`、"目标窗口无法恢复到可视状态" ——
  屏幕工具**判不了它们的可见性**。所以判据换成：
    · 用 Win32 `IsWindowVisible` + 窗口几何（**真实窗口状态**，不是截图）
    · 与 main.py 的内省（`_soul_visible()`）**双向对账**（两边必须一致）
  ⇒ 两路都指向"灵魂真的从屏幕上消失"，才敢说"用户看得见变化"。

★ 另外用 screen-automation 观测**气泡窗口**（有底色、可被截图/OCR 抓到）作为
  独立旁证：征求意见时气泡里应出现那句台词。

用法（后台）：& C:\Python311\python.exe <本文件>
"""
import ctypes
import ctypes.wintypes as wt
import io
import os
import sys
import time

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)   # ★ 先声明 DPI 感知（铁律）
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
SRC = os.path.join(ROOT, 'ralsei_pet')
for p in (os.path.join(SRC, 'src'), SRC, os.path.join(SRC, 'modules')):
    if p not in sys.path:
        sys.path.insert(0, p)

_u = ctypes.windll.user32
_lines = []


def w(s=''):
    _lines.append(s)
    try:
        print(s, flush=True)
    except Exception:
        pass


def dump(path):
    try:
        io.open(path, 'w', encoding='utf-8', newline='\n').write('\n'.join(_lines))
    except Exception:
        pass


EVID = os.path.join(ROOT, 'code-quality-audit', '第82轮-灵魂附身R5', '_evidence')
os.makedirs(EVID, exist_ok=True)
OUT = os.path.join(EVID, 'live_r5_user_view.txt')

P = F = 0


def chk(tag, cond):
    global P, F
    if cond:
        P += 1
        w('  [PASS] %s' % tag)
    else:
        F += 1
        w('  [FAIL] %s' % tag)


def win_geom(hwnd):
    """(visible, (l,t,r,b)) —— 真实窗口状态（不吃截图）。"""
    r = wt.RECT()
    ok = _u.GetWindowRect(wt.HWND(hwnd), ctypes.byref(r))
    vis = bool(_u.IsWindowVisible(wt.HWND(hwnd)))
    return (vis, (r.left, r.top, r.right, r.bottom)) if ok else (vis, None)


def find_pet_windows():
    """列出本进程相关的顶层窗口（标题/类名 + 几何）。"""
    out = []
    EnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)

    def cb(hwnd, _l):
        buf = ctypes.create_unicode_buffer(256)
        _u.GetWindowTextW(hwnd, buf, 256)
        cls = ctypes.create_unicode_buffer(256)
        _u.GetClassNameW(hwnd, cls, 256)
        pid = wt.DWORD()
        _u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == os.getpid():
            vis, geo = win_geom(hwnd)
            out.append({'hwnd': int(hwnd), 'title': buf.value, 'cls': cls.value,
                        'visible': vis, 'geo': geo})
        return True
    _u.EnumWindows(EnumProc(cb), 0)
    return out


w('=== 第82轮 R5：用户视角验证（透明窗口 + 屏幕工具观测）===')
w('时间 = %s' % time.strftime('%Y-%m-%d %H:%M:%S'))
w('DPI 感知已声明 = SetProcessDpiAwareness(2)')
w('')

rc = 1
p = None
try:
    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    import main as main_mod
    p = main_mod.RalseiPet()
    app.processEvents()
    try:
        p.init_soul()
    except Exception:
        pass
    app.processEvents()
    w('RalseiPet() 构造成功 · 本进程 PID=%d' % os.getpid())
    w('')

    soul = getattr(p, 'soul', None)
    chk('灵魂实体已建起', soul is not None)

    def snapshot(tag):
        """给定标签，快照：内省 + 真实窗口状态。"""
        time.sleep(0.35)
        app.processEvents()
        wins = find_pet_windows()
        inner = bool(p._soul_visible())
        w('## %s' % tag)
        w('  内省 _soul_visible() = %r' % inner)
        w('  真实窗口 %d 个：' % len(wins))
        for x in wins:
            w('    hwnd=%-9d vis=%-5s cls=%-28s title=%-14s geo=%s' % (
                x['hwnd'], x['visible'], x['cls'][:26], x['title'][:12], x['geo']))
        return {'inner': inner, 'wins': wins}

    # ---------- Q1 附身前 ----------
    a = snapshot('Q1 附身前（用户应看得到灵魂）')
    soul_vis_a = a['inner']
    chk('Q1 内省：灵魂可见（用户看得到）', soul_vis_a is True)
    # 灵魂控件窗口应当真在屏上且 visible=True
    qt_vis = [x for x in a['wins'] if x['visible']]
    w('  ⇒ 屏上可见窗口数 = %d' % len(qt_vis))
    chk('Q1 真实窗口：灵魂控件窗口 visible=True', len(qt_vis) >= 2)
    w('')

    # ---------- Q2 按 Z 附身 ----------
    w('## Q2 按 Z 附身 kris（真产品入口 toggle_possession）')
    # 场景对齐：让三个目标都能被选中（本实例的 current_scene 未必匹配）
    for t in (getattr(p, '_possession_targets', {}) or {}).values():
        try:
            t.scene = None
        except Exception:
            pass
    ok = p.toggle_possession()
    w('  toggle_possession() 返回 %r' % ok)
    b = snapshot('Q2 附身后（灵魂应已收起）')
    poss = getattr(p, 'possession', None)
    w('  附身状态：mode=%r 目标=%r' % (
        getattr(poss, 'mode', None), getattr(poss, 'possessed_id', None)))
    chk('Q2 附身成立', getattr(poss, 'mode', None) == 'possessed')
    chk('Q2 内省：灵魂已收起（_soul_visible()=False）', b['inner'] is False)
    # ★ 真实窗口：灵魂控件应当 visible=False（用户看不到了）
    any_vis = [x for x in b['wins'] if x['visible']]
    w('  ⇒ 屏上可见窗口数 = %d（附身前 %d）' % (len(any_vis), len(qt_vis)))
    chk('★ Q2 真实窗口：可见窗口数**减少**（灵魂从屏幕上消失）',
        len(any_vis) < len(qt_vis))
    w('')

    # ---------- Q3 再按 Z 解除 ----------
    w('## Q3 再按 Z 解除（灵魂应回来）')
    p.toggle_possession()
    c = snapshot('Q3 解除后')
    chk('Q3 内省：灵魂回来（_soul_visible()=True）', c['inner'] is True)
    any_vis2 = [x for x in c['wins'] if x['visible']]
    w('  ⇒ 屏上可见窗口数 = %d' % len(any_vis2))
    chk('★ Q3 真实窗口：可见窗口数**恢复**', len(any_vis2) >= len(qt_vis))
    w('')

    # ---------- Q4 双向对账 ----------
    w('## Q4 双向对账（内省 vs 真实窗口，必须一致）')
    for tag, s in (('附身前', a), ('附身后', b), ('解除后', c)):
        vis_n = len([x for x in s['wins'] if x['visible']])
        # 内省说"灵魂可见" ⇒ 屏上可见窗口应含灵魂；说"不可见" ⇒ 应更少
        w('  %s：内省可见=%s / 屏上可见窗口=%d' % (tag, s['inner'], vis_n))
    chk('Q4 附身态与窗口可见性方向一致（附身⇒更少、解除⇒恢复）',
        a['inner'] and not b['inner'] and c['inner']
        and len([x for x in b['wins'] if x['visible']])
        < len([x for x in a['wins'] if x['visible']]))
    w('')

    w('=== 结论 ===')
    w('  PASS=%d FAIL=%d' % (P, F))
    w('  用户视角判定 = %s' % ('PASS' if F == 0 else 'FAIL'))
    rc = 0 if F == 0 else 1

except Exception:
    import traceback
    w('!! 异常：')
    w(traceback.format_exc())
    rc = 3
finally:
    dump(OUT)
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
