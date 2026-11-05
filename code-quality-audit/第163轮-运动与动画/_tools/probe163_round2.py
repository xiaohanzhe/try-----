# -*- coding: utf-8 -*-
"""第163轮 · 第二支探针（脚底落点重算 + idle 帧推进 A/B）。

================================ 为什么要重算脚底 ================================
上一支 `probe163_feet.py` 报「跨动画脚底 y 跨度 30px」，但它的公式是
    feet_screen = (BOTTOM - 容器高*scale) + bbox_bottom*scale
即假设「帧在窗口内**左上对齐**」。产品的真实路径是：
    · 窗口尺寸 = 容器(本动画最大帧) x scale
    · `_compose_anchored_sprite` 把该帧画进 canvas(cw,ch)，位置
        dx = (cw - sw)//2 - round(off_x*s)
        dy = (ch - sh)//2 - round(off_y*s)
      off_y = (bb_y0 + bb_y1)/2 - fh/2   （本体中心 - 帧中心）
    ⇒ 代进去，本体下沿在画布内的 y 恒等于
        ch/2 + (本体高*s)/2
      与帧尺寸/锚点无关（锚点精确生效时）。上一支漏了居中项与锚点项，
      所以那 30px 里有一部分是**探针自己造的**。
本支不再自己推公式：直接把每帧交给产品自己的 `_compose_anchored_sprite` 合成，
再对**合成结果**取 alpha 包围盒 —— 观察量由被测代码给出。

================================ idle 为什么要 A/B ================================
上一支报「强制 `_idle_loop_active=True` 后仍 0.00 FPS」，与代码写法不一致。
真因：`update_animation` 在**静止分支**里每个 tick 都会重新计算一次
    self._idle_loop_active = bool(_lounge_since is not None or idle_timer >= 600)
⇒ 探针手动置的 True 会被下一个 tick 覆盖。属**探针假象**，必须先修夹具。
本支改用「让门限条件本身成立」：`idle_timer = 700` + `max_idle_duration = 1e9`
（后者防 `randomize_movement_pattern` 把 idle_timer 清零）。

跑法：C:\\Python311\\python.exe probe163_round2.py
"""
import os
import sys
import time
import tempfile

ROOT = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
os.environ['RALSEI_DATA_DIR'] = os.path.join(tempfile.gettempdir(), 'pet163_data')
os.makedirs(os.environ['RALSEI_DATA_DIR'], exist_ok=True)
sys.path.insert(0, os.path.join(ROOT, 'ralsei_pet', 'modules'))
sys.path.insert(0, os.path.join(ROOT, 'ralsei_pet', 'src'))

import memory_store as _ms
_ms.find_device_dir = lambda create=True: None
# ★★ 只打桩 find_device_dir 不够：`default_memory_dir()` 在设备为 None 时会走
#   `fallback_dir()` = **用户桌面 `Desktop\memory\`**（产品设计如此：U 盘不在时
#   记忆落桌面兜底）。实测有一次运行把用户的 `Desktop\memory\memory.json` 写脏了。
#   ⇒ 探针必须把 default_memory_dir 整体钉到 TEMP。
_MEM_DIR = os.path.join(os.environ['RALSEI_DATA_DIR'], 'memory')
_ms.default_memory_dir = lambda: (_MEM_DIR, False, None)
import data_store as _ds
_ds.vault_root = lambda create=True: None

from PyQt5.QtWidgets import QApplication            # noqa: E402
from PyQt5.QtGui import QImage                       # noqa: E402
from PyQt5.QtCore import Qt, QTimer, QEventLoop      # noqa: E402

app = QApplication(sys.argv[:1])

# 桌面上真会播的那批（静态扫描：字面量 21 个 + walk_/run_ 四方向）
WATCH = ['idle', 'walk_down', 'walk_left', 'walk_right', 'walk_up',
         'run_down', 'run_left', 'run_right', 'run_up',
         'jump', 'jump_ball', 'jump_ready', 'fall', 'fall_back', 'fall_mad',
         'land', 'splat', 'sleep', 'sit', 'sit_rest',
         'spell', 'act', 'dance', 'sing', 'laugh', 'wave', 'pose', 'happy',
         'sad', 'neutral', 'look_up', 'surprised', 'nuzzle', 'cry']


def union_bbox(pixmap):
    """整张图**所有**不透明像素的包围盒（半开 x0,y0,x1,y1）；空图返回 None。

    与 `_main_component_bbox`（最大连通块）不同：这里要"视觉最下沿"，
    包括贴着脚底的粒子/影子。

    ★ 必须用 `QImage.Format_ARGB32` 的**具名常量**：第一版图省事写成
      `convertToFormat(4)`，而 PyQt5 里 4 是 `Format_RGB32`（**无 alpha**），
      转换后所有像素 alpha 变 255 ⇒ 每张图都"全不透明" ⇒ 本函数恒返回整张画布，
      "脚底恒 = 画布底、跨度 0.0px" 是个**恒真判据**。
      是 `probe163_bbox_selfcheck.py` 的 6 项正负控制把它抓出来的。
    """
    img = pixmap.toImage().convertToFormat(QImage.Format_ARGB32)
    w, h = img.width(), img.height()
    ptr = img.constBits()
    ptr.setsize(img.byteCount())
    raw = bytes(ptr)
    bpl = img.bytesPerLine()
    minx, miny, maxx, maxy = w, h, -1, -1
    for y in range(h):
        alpha = raw[y * bpl: y * bpl + w * 4][3::4]
        if not any(alpha):
            continue
        if y < miny:
            miny = y
        maxy = y
        left = alpha.lstrip(b'\x00')
        x0 = w - len(left)
        x1 = len(alpha.rstrip(b'\x00'))
        if x0 < minx:
            minx = x0
        if x1 > maxx:
            maxx = x1
    if maxx < 0:
        return None
    return (minx, miny, maxx, maxy + 1)


def section_feet(w):
    from PyQt5.QtGui import QPixmap
    scale = float(getattr(w, '_cached_scale_factor', 2.0))
    print('scale = %s' % scale)

    BOTTOM = 1000.0
    rows = []
    for a in WATCH:
        frames = w.sprite_loader.sprites.get(a)
        if not frames:
            continue
        cw = max((f.width() for f in frames if f and not f.isNull()), default=0)
        ch = max((f.height() for f in frames if f and not f.isNull()), default=0)
        if cw <= 0 or ch <= 0:
            continue
        container = (cw, ch)
        win_h = int(ch * scale)
        feet_all, feet_main, ctr_main = [], [], []
        for idx, f in enumerate(frames):
            if f is None or f.isNull():
                continue
            sw = int(f.width() * scale)
            sh = int(f.height() * scale)
            scaled = f.scaled(sw, sh, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            canvas = w._compose_anchored_sprite(scaled, container, a, scale, idx)
            ub = union_bbox(canvas)
            if ub is None:
                continue
            feet_all.append(ub[3])
            rows_bits = w._alpha_row_bits(canvas)
            mb = w._main_component_bbox(rows_bits, canvas.width())
            if mb is not None:
                feet_main.append(mb[3])
                ctr_main.append((mb[1] + mb[3]) / 2.0)
            # 合成后画布尺寸必须 = 窗口尺寸，否则下面减 BOTTOM 的口径不成立
            assert canvas.height() == win_h, (a, canvas.height(), win_h)
        if not feet_all:
            continue
        top = BOTTOM - win_h
        rows.append({
            'name': a, 'container': (cw, ch), 'win_h': win_h,
            'feet_all': [top + v for v in feet_all],
            'feet_main': [top + v for v in feet_main],
            'ctr_main': [top + v for v in ctr_main],
            'gap_all': [win_h - v for v in feet_all],
            'gap_main': [win_h - v for v in feet_main],
        })

    print('\n%-12s %-10s %-6s %-16s %-16s %-10s'
          % ('anim', 'container', 'winH', '脚底(含粒子)', '脚底(本体)', '本体中心y'))
    for r in rows:
        print('%-12s %-10s %-6d %-16s %-16s %-10s'
              % (r['name'], '%dx%d' % r['container'], r['win_h'],
                 '%.1f~%.1f' % (min(r['feet_all']), max(r['feet_all'])),
                 ('%.1f~%.1f' % (min(r['feet_main']), max(r['feet_main']))
                  if r['feet_main'] else '-'),
                 ('%.1f~%.1f' % (min(r['ctr_main']), max(r['ctr_main']))
                  if r['ctr_main'] else '-')))

    fa = [v for r in rows for v in r['feet_all']]
    fm = [v for r in rows for v in r['feet_main']]
    print('\n==== 跨动画离散度（BOTTOM=%.0f 固定底边）====' % BOTTOM)
    print('脚底(含粒子) y = %.1f ~ %.1f   跨度 %.1f px'
          % (min(fa), max(fa), max(fa) - min(fa)))
    if fm:
        print('脚底(本体)   y = %.1f ~ %.1f   跨度 %.1f px'
              % (min(fm), max(fm), max(fm) - min(fm)))

    print('\n==== 同一动画内逐帧脚底抖动（本体口径）top 12 ====')
    inner = sorted(((max(r['feet_main']) - min(r['feet_main']), r['name'])
                    for r in rows if r['feet_main']), reverse=True)
    for d, nm in inner[:12]:
        print('  %-12s %.1f px' % (nm, d))
    n_zero = sum(1 for d, _ in inner if d <= 1.0)
    print('  —— 抖动 <=1.0px 的动画：%d / %d' % (n_zero, len(inner)))

    print('\n==== 逐动画「本体距画布底的空隙」（本体口径；保底边 == 保脚底 当且仅当它恒定）====')
    for r in rows:
        print('  %-12s 容器高 %2d  空隙 %s'
              % (r['name'], r['container'][1],
                 '[%s]' % ','.join('%.1f' % v for v in r['gap_main'][:5])))
    return rows


def observe(w, seconds):
    """在真事件循环里采样 current_frame，返回 [(t, frame, anim, idle_active)]。"""
    samples = []
    t0 = time.time()

    def tick():
        samples.append((time.time() - t0, w.current_frame,
                        w.current_animation,
                        bool(getattr(w, '_idle_loop_active', False)),
                        float(getattr(w, 'idle_timer', -1))))
    tm = QTimer()
    tm.timeout.connect(tick)
    tm.start(20)
    loop = QEventLoop()
    QTimer.singleShot(int(seconds * 1000), loop.quit)
    loop.exec_()
    tm.stop()
    return samples


def summarize(tag, samples):
    frames = [s[1] for s in samples]
    advances = sum(1 for i in range(1, len(frames)) if frames[i] != frames[i - 1])
    dur = samples[-1][0] - samples[0][0] if len(samples) > 1 else 0.0
    fps = advances / dur if dur > 0 else 0.0
    anims = sorted(set(s[2] for s in samples))
    idle_act = sum(1 for s in samples if s[3])
    print('  %-10s 时长 %.2fs  采 %d 次  换帧 %d 次  → %.2f fps'
          % (tag, dur, len(samples), advances, fps))
    print('  %-10s current_animation = %s' % ('', anims))
    print('  %-10s _idle_loop_active 为真的采样占比 %.0f%%  idle_timer %s'
          % ('', 100.0 * idle_act / max(1, len(samples)),
             ('%.1f~%.1f' % (min(s[4] for s in samples), max(s[4] for s in samples)))))
    return fps


def section_idle(w):
    print('\n\n======================== idle 帧推进 A/B ========================')
    print('素材事实：idle %d 帧 / sit %d 帧 / sit_rest %d 帧'
          % (len(w.sprite_loader.sprites.get('idle') or []),
             len(w.sprite_loader.sprites.get('sit') or []),
             len(w.sprite_loader.sprites.get('sit_rest') or [])))
    print("'sit_rest' in sprites = %s" % ('sit_rest' in w.sprite_loader.sprites))

    print('\n[A] 自然静止（idle_timer 从 0 起，未窝着）')
    w._lounge_since = None
    w.idle_timer = 0.0
    w.max_idle_duration = 1e9          # 禁随机漫游，隔离变量
    w.current_frame = 0
    summarize('A', observe(w, 2.5))

    print('\n[B] 门限条件成立（idle_timer=700 ≥ 600，未窝着）')
    w._lounge_since = None
    w.idle_timer = 700.0
    w.max_idle_duration = 1e9
    w.current_frame = 0
    summarize('B', observe(w, 2.5))

    print('\n[C] 窝着（_lounge_since 非空）')
    w._lounge_since = time.time()
    w.idle_timer = 0.0
    w.max_idle_duration = 1e9
    summarize('C', observe(w, 2.5))
    w._lounge_since = None

    print('\n[D] 自然运行 20s：idle_timer 实际能涨到多少（不接管 max_idle_duration）')
    w.idle_timer = 0.0
    w.max_idle_duration = 3.0          # 还原成真机量级（真机 2~12s）
    samples = observe(w, 20.0)
    idles = [s[4] for s in samples]
    resets = sum(1 for i in range(1, len(idles)) if idles[i] < idles[i - 1] - 0.05)
    print('  idle_timer 峰值 %.2f s   清零/回落次数 %d   判定门限 600s 可达 = %s'
          % (max(idles), resets, 'YES' if max(idles) >= 600 else 'NO'))
    print('  current_frame 覆盖 %s'
          % sorted(set(s[1] for s in samples))[:8])


def main():
    from main import RalseiPet
    w = RalseiPet()
    only = sys.argv[1] if len(sys.argv) > 1 else 'all'
    if only in ('all', 'feet'):
        section_feet(w)
    if only in ('all', 'idle'):
        section_idle(w)
    try:
        w.cleanup_on_exit()
    except Exception:
        pass


if __name__ == '__main__':
    main()
