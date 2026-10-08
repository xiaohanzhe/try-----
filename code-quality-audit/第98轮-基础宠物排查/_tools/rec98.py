# -*- coding: utf-8 -*-
u"""rec97.py —— 第96轮「跑 10 分钟 + 录视频 + 逐帧分析」的**录制端**（v2）。

用户指令（原话）
----------------
「你先让程序跑10分钟，你录视频然后逐帧分析，查看用户视角下他究竟对不对，
  尤其是我之前提到过的问题」

★ v1 踩过的坑（实测数据，记下来免得后人再犯）
------------------------------------------------
  · `QPixmap.save(..., 'PNG')` 在 2560×1600 上要 **20,410 ms** 一次！
    ⇒ 挂在事件循环里逐帧存 PNG = **把被测对象彻底堵死**（v1 实测 30 s 只出 19 帧）
    ⇒ 这是"测量严重干扰被测物"，必须避免。
  · `grabWindow(0)` = 65 ms；再加 `toImage()/bits()` 取像素 = **56 ms/帧**，可接受。
  · 编码器实测（2560×1600，每帧）：FFV1 无损 57 ms · XVID 14 ms · mp4v 11 ms。
  · **不能把帧全存内存**：16,384,000 B/帧 × 2400 帧 = **37 GB**。

v2 架构
-------
  录制期（跑在**产品自身事件循环**的 QTimer 上）：
     每 TICK(默认 250 ms) → `grabWindow(0)` → `toImage()` → `bytes` → ndarray(BGR)
     → **立刻写进 FFV1 无损 AVI**（内存恒定）；同时写一行状态到 CSV。
     ⇒ 单帧 56+57 = 113 ms / 250 ms ⇒ 占用率约 45%，"看着像在录但不太重影"。
  录制结束后（离线，不再影响产品）：
     · 从 FFV1 AVI 转出一份 **mp4v MP4**（体积小，供人眼直接看）；
     · 把**状态变化帧**导出 PNG（肉眼可查的证据）；
     · 写 meta。

★ 为什么抓屏必须在产品进程内：宠物是 `Qt.Tool` **非置顶透明分层窗口**，
  外部进程 `BitBlt` 抓不到（记忆铁律：看不见≠不存在）。本进程 `grabWindow(0)`
  拿的是**合成后的桌面** ⇒ 看到的＝用户看到的。

产物（落 `_evidence/`）
----------------------
  rec97_meta.txt        参数与统计
  rec97_frames.csv      每帧：帧号/时刻/窗口矩形/动画/方向/移动/速度/目标/尺寸
  rec97_moves.txt       窗口矩形变化事件（与 95 轮同格式）
  rec97_anim.txt        `change_animation` 被拒事件
  rec97_state.txt       1 Hz 内部状态快照
  rec97_raw.avi         FFV1 无损全程录像
  rec97_video.mp4       转码后的 MP4（供人眼）
  frames/*.png          状态变化帧的 PNG

跑法
----
  set REC97_SECS=600
  C:\\Python311\\python.exe code-quality-audit\\第96轮-用户视角录制复核\\_tools\\rec97.py
"""
import csv
import io
import os
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.normpath(os.path.join(HERE, '..'))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')
SRC = os.path.join(PKG, 'src')
# ★ 第97轮：允许用 `REC97_EVDIR` 指定输出目录 ⇒ 同一会话里可跑"自然录制"与
#   "定向注入录制"两轮而互不覆盖（默认仍为本轮 `_evidence/`）。
EV = os.environ.get('REC97_EVDIR') or os.path.join(ROUND, '_evidence')
FRAMES = os.path.join(EV, 'frames')

SECS = int(os.environ.get('REC97_SECS', '600'))
TICK_MS = int(os.environ.get('REC97_TICK_MS', '500'))
RAW = os.path.join(EV, 'rec97_raw.avi')
MP4 = os.path.join(EV, 'rec97_video.mp4')
# ★ 编码必须选 **快** 的：FFV1 无损实测 173 ms/帧（真实桌面内容比空帧复杂 3 倍）
#   ⇒ 4 Hz 下占用率 58%，对被测对象干扰过大。mp4v 实测约 11 ms/帧。
#   位移/朝向/几何类分析读的是**窗口矩形与状态字段**，不吃像素细节的压缩伪影。
FOURCC = os.environ.get('REC97_FOURCC', 'mp4v')

os.makedirs(FRAMES, exist_ok=True)

# ★ 自清旧产物：走 Python 的 os.remove，**不经过 shell 的删除守卫**
#   （守卫按"本轮累计删除路径数"计数，阈值 50；`rm -rf frames` 一次就超
#    ⇒ 被 `SAFE_DELETE_BULK_CONFIRM_REQUIRED` 拦下，整条命令 rc=1 什么都不做）
if os.environ.get('REC97_PURGE', '1') == '1':
    # ★★★ 第96轮实测教训：**删除通道会被"安全删除守卫"按"本轮累计删除路径数"计账
    #   （阈值 50）拦下** —— 连脚本内部的 `os.remove` 也审计，159 张关键帧 PNG
    #   一次就超 ⇒ 第二次录制直接在启动期被拦（rc 非 0、零输出）。
    #   守卫本身是**正常工作**，不许绕过。
    #   ⇒ 改成**整目录改名归档**（**1 次文件操作**，远低于阈值）：
    #     把上一轮 `frames/` 整体改名成 `frames_prev_<时间戳>/`，再新建空目录。
    #     ★ 不用逐文件 `os.replace` —— 那仍是 159 次操作、照样超阈值。
    import shutil as _sh
    _ts = time.strftime('%Y%m%d_%H%M%S')
    _prev = os.path.join(EV, 'frames_prev_%s' % _ts)
    try:
        if os.path.isdir(FRAMES) and os.listdir(FRAMES):
            os.rename(FRAMES, _prev)
            os.makedirs(FRAMES)
            print('[rec97] 上一轮关键帧已整目录归档到 %s'
                  % os.path.basename(_prev))
    except Exception as _e:
        print('[rec97] 归档上一轮关键帧失败（忽略）：%r' % (_e,))
    # ★ 删掉 `rec97_stdout.txt` 是**明令禁止的**：它是 shell 重定向目标，
    #   脚本再 remove 会把 inode 摘掉 ⇒ 之后所有 stdout 都写进"已删除文件"，
    #   磁盘上永远看不到（这正是第一版 F3 判"自检行不在场"的根因）。
    for _f in ('rec97_frames.csv', 'rec97_moves.txt', 'rec97_anim.txt',
               'rec97_state.txt', 'rec97_meta.txt',
               'rec97_raw.avi', 'rec97_video.mp4'):
        _p = os.path.join(EV, _f)
        if os.path.exists(_p):
            try:
                os.remove(_p)
            except Exception:
                pass

os.chdir(PKG)
if SRC in sys.path:
    sys.path.remove(SRC)
sys.path.insert(0, SRC)

import cv2                                                  # noqa: E402
import numpy as np                                          # noqa: E402
import main as M                                            # noqa: E402
from PyQt5.QtWidgets import QApplication                    # noqa: E402
from PyQt5.QtCore import QTimer                             # noqa: E402

# ---- 复刻 __main__ 启动序列（顺序逐条一致）----
M.check_single_instance()
M.install_crash_guard()
try:
    import text_segmenter
    text_segmenter.install()
except Exception as e:
    print('text_segmenter fail: %r' % (e,))
try:
    import data_store
    data_store.migrate_from_staging()
except Exception as e:
    print('data_store fail: %r' % (e,))

app = QApplication(sys.argv)
window = M.RalseiPet()
window.show()
print('[rec97] shown pid=%d title=%r' % (os.getpid(), window.windowTitle()))
sys.stdout.flush()

# ★ 声明 DPI 感知（记忆铁律）：本机 150% 缩放，不声明则 win32 读到逻辑像素 1707×1067，
#   拿它核对产品窗口坐标必然误报越界（第35轮踩过）。
try:
    import ctypes
    ctypes.windll.user32.SetProcessDPIAware()
except Exception:
    pass

_scr = app.primaryScreen()
_geo = _scr.geometry()
_W, _H = _geo.width(), _geo.height()

_t0 = time.time()
_fcsv = io.open(os.path.join(EV, 'rec97_frames.csv'), 'w', encoding='utf-8', newline='')
# ★★★ 第96轮修：`csv.writer` 默认 `lineterminator='\r\n'`，
#   而分析端 `rd()` 是**字节忠实读取**（`newline=''`，保留 `\r`）
#   ⇒ 表头最后一项会变成 `'spdy\r'`，`d['spdy']` 永远缺键
#   ⇒ **速度向量判据静默拿到 0 个样本**（症状：C2v 报「仅 0 个 ⇒ 无法判定」）。
#   与本文件其余 csv/txt 产出一致，统一用 `\n`。
_csvw = csv.writer(_fcsv, lineterminator='\n')
# ★ 第97轮新增 `gfall`（`is_gravity_falling`）：产品把"**重力坠落**"记在这个
#   标志上，而 `is_falling` 只覆盖"**原地摔**"（`start_fall`）⇒ 旧观测面
#   **看不到任何重力坠落**（第96轮 F7 的判据缺口，正是"判据也是被测物"再一例）。
_csvw.writerow(['frame', 't', 'wx', 'wy', 'ww', 'wh', 'anim', 'dir',
                'moving', 'falling', 'gfall', 'sleeping', 'swalk', 'spd',
                'tx', 'ty', 'spdx', 'spdy'])
_fmov = io.open(os.path.join(EV, 'rec97_moves.txt'), 'w', encoding='utf-8', newline='\n')
_fani = io.open(os.path.join(EV, 'rec97_anim.txt'), 'w', encoding='utf-8', newline='\n')
_fsta = io.open(os.path.join(EV, 'rec97_state.txt'), 'w', encoding='utf-8', newline='\n')

# ★★★ 第98轮新增：**"为什么没动"分诊探针**（`REC98_PROBE_BLOCK=1`，默认关）
#   动机 = 用户第98轮口径第 3 条「他还有**原地踏步**的问题，你自己看看」。
#   「原地踏步」= 走路动画在播（`is_moving=True`）而屏幕位置不变。但**光看位置**
#   只能知道"没动"，不知道是**谁**把这一 tick 的移动吞了 —— `update_movement`
#   在 `_special_anim_locked()` / `_is_being_dragged` / `is_dragging_mouse` /
#   `is_following_mouse`（追鼠标超时）/ 物理三态（jumping/falling/gravity）等处
#   都会**提前 return**（其中前两处还会把速度显式清零 ⇒ CSV 里看到 `|v|=0`）。
#   ⇒ 把这一串判据逐帧记下来，才分得清"产品卡住"与"这一 tick 被正常分支接管"。
#   ★ 另写一个文件（不动 `rec97_frames.csv` 的表头）⇒ 既有分析脚本完全不受影响。
_PROBE_BLOCK = os.environ.get('REC98_PROBE_BLOCK', '0') == '1'
_fblk = (io.open(os.path.join(EV, 'rec98_block_probe.txt'), 'w',
                 encoding='utf-8', newline='\n') if _PROBE_BLOCK else None)

_vw = cv2.VideoWriter(RAW, cv2.VideoWriter_fourcc(*FOURCC), 1000.0 / TICK_MS, (_W, _H))
if not _vw.isOpened():
    print('[rec97] FATAL: VideoWriter(%s) 打不开' % FOURCC)
    sys.exit(2)

_N = [0]
_KEY = [0]
_ENC_MS = [0.0]
_GRAB_MS = [0.0]
_LASTGEO = [None]
_COLORS = [None]        # 存第一帧的宠物区域像素，用于整段"是否真的在动"的像素级判据


def _g(o, n, d=None):
    try:
        return getattr(o, n, d)
    except Exception:
        return d


# ---- 劫持 move（与 95 轮同格式，便于复用已写好的分析工具）----
_orig_move = window.move
_lastpos = [None]


def _move_wrap(x, y=None):
    if y is None:
        pt = x
        x, y = pt.x(), pt.y()
    if (x, y) != _lastpos[0]:
        _lastpos[0] = (x, y)
        _fmov.write('t=%.3f x=%d y=%d anim=%r dir=%r moving=%r spd=%r tgt=%r sz=%dx%d\n'
                    % (time.time() - _t0, x, y,
                       _g(window, 'current_animation'), _g(window, 'current_direction'),
                       _g(window, 'is_moving'), _g(window, 'speed'),
                       _g(window, 'target_pos'),
                       window.width(), window.height()))
        _fmov.flush()
    return _orig_move(x, y)


window.move = _move_wrap

_orig_change = window.change_animation

# ★★ 第98轮（取证探针，env 门控，默认关闭）：
#   记录 `change_animation` 的**每一次调用**（含被接受的）＋**调用方栈**。
#   为什么必须记栈：残留的"重力坠落期播 walk_up"是 `force=True` 调用，
#   而不带 force 的那条 REJECT 日志**只记被拒的**，抓不到它 ⇒ 只能从
#   **调用点**定位（"谁在坠落期把动画换成走路"）。
#   ⇒ 探针只读、不改产品；`REC98_PROBE_CHANGE=0`（默认）时零开销。
_PROBE = os.environ.get('REC98_PROBE_CHANGE', '0') == '1'
_fprobe = None
if _PROBE:
    _fprobe = open(os.path.join(EV, 'rec98_change_probe.txt'), 'w',
                   encoding='utf-8')
    print('[rec97] 探针已开启：%s' % os.path.join(EV, 'rec98_change_probe.txt'))


def _change_wrap(name, *a, **kw):
    r = _orig_change(name, *a, **kw)
    if not r:
        _fani.write('t=%.3f REJECT %r (cur=%r) args=%r kw=%r\n'
                    % (time.time() - _t0, name, _g(window, 'current_animation'), a, kw))
        _fani.flush()
    if _fprobe is not None:
        try:
            import traceback as _tb
            # 去掉探针自身那几帧，只留"产品侧调用点"
            _st = [f for f in _tb.extract_stack()[:-1]
                   if os.path.basename(f.filename) != 'rec98.py']
            _top = ' < '.join('%s:%d' % (os.path.basename(f.filename), f.lineno)
                              for f in _st[-4:])
            _fprobe.write('t=%.3f call=%r force=%r gfall=%r ok=%r cur=%r | %s\n'
                          % (time.time() - _t0, name, kw.get('force'),
                             _g(window, 'is_gravity_falling'), bool(r),
                             _g(window, 'current_animation'), _top))
            _fprobe.flush()
        except Exception:
            pass
    return r


window.change_animation = _change_wrap


def tick():
    i = _N[0]
    try:
        t = time.time() - _t0
        tg = time.time()
        pm = _scr.grabWindow(0)
        img = pm.toImage()
        ptr = img.bits()
        ptr.setsize(img.byteCount())
        # ★ 必须 `bytes(...)` 再 `frombuffer`：直接传 sip.voidptr 会得到 memoryview，
        #   而 `QImage(...)` 不接受 memoryview（v2 首跑整段在抛 TypeError，
        #   每 tick 写一次 traceback 本身就是额外负担）。
        raw = bytes(ptr)
        arr = np.frombuffer(raw, np.uint8).reshape(img.height(),
                                                   img.bytesPerLine() // 4, 4)
        arr = arr[:, :img.width(), :3]                      # BGRA -> BGR
        _GRAB_MS[0] += (time.time() - tg) * 1000.0
        te = time.time()
        _vw.write(np.ascontiguousarray(arr))
        _ENC_MS[0] += (time.time() - te) * 1000.0

        p = window.pos()
        sx = _g(window, 'speed')
        tp = _g(window, 'target_pos')
        # ★★★ 第96轮修：**必须同时采集速度向量**（`current_speed_x/y`）。
        #   理由（本轮实证）：产品 L7244 的 `angle = atan2(current_speed_y, current_speed_x)`
        #   **就是**决定朝向的那一个量；而"采样位移"在 0.4s 窗口内会跨过转向边界/含折返，
        #   与"当前瞬时动画"本就不该相等。
        #   实测对照（probe96_walkup，148 个有效样本）：
        #     · 用「采样位移」推方向 ⇒ 4.43% 报"矛盾"（**全是伪影**）
        #     · 用「速度向量」推方向 ⇒ **0.00% 不一致**
        #   ⇒ 判据必须用速度向量，否则会造出假缺陷。
        svx = _g(window, 'current_speed_x')
        svy = _g(window, 'current_speed_y')
        _csvw.writerow([i, '%.3f' % t, p.x(), p.y(), window.width(), window.height(),
                        _g(window, 'current_animation'), _g(window, 'current_direction'),
                        _g(window, 'is_moving'), _g(window, 'is_falling'),
                        _g(window, 'is_gravity_falling'),
                        _g(window, 'is_sleeping'), _g(window, 'is_sleeping_walk'),
                        sx if sx is not None else '',
                        tp.x() if tp is not None else '',
                        tp.y() if tp is not None else '',
                        ('%.6f' % svx) if svx is not None else '',
                        ('%.6f' % svy) if svy is not None else ''])

        # ★ 第98轮分诊探针：把"这一 tick 可能把移动吞掉的分支条件"全记下来。
        #   与产品同进程、同一刻取 ⇒ 与宠物实际经历完全同源。
        if _fblk is not None:
            try:
                _sp = None
                try:
                    _sp = bool(window._special_anim_locked())
                except Exception as _e2:
                    _sp = 'ERR:%s' % type(_e2).__name__
                _fblk.write(
                    't=%.3f anim=%r dir=%r mv=%r wx=%d wy=%d ww=%d wh=%d '
                    'tgt=(%s,%s) spd=%s v=(%s,%s) | drag=%r dmouse=%r fmouse=%r '
                    'ffile=%r special=%r spell=%r hide=%r play=%r brake=%r '
                    'sleep=%r swalk=%r phase=%r freason=%r fspeed=%s\n'
                    % (t, _g(window, 'current_animation'),
                       _g(window, 'current_direction'), _g(window, 'is_moving'),
                       p.x(), p.y(), window.width(), window.height(),
                       tp.x() if tp is not None else '-',
                       tp.y() if tp is not None else '-',
                       sx if sx is not None else '-',
                       svx if svx is not None else '-',
                       svy if svy is not None else '-',
                       _g(window, '_is_being_dragged'),
                       _g(window, 'is_dragging_mouse'),
                       _g(window, 'is_following_mouse'),
                       _g(window, 'is_following_dragged_file'),
                       _sp, _g(window, '_spell_stage'), _g(window, '_hide_stage'),
                       bool(getattr(window, 'game_state', {}).get('is_playing')),
                       getattr(window, '_catch_brake', None) is not None,
                       _g(window, 'is_sleeping'), _g(window, 'is_sleeping_walk'),
                       # ★ 第98轮（坠落语义取证）：补 `_fall_phase` / `_fall_reason` /
                       #   `fall_speed` ⇒ 逐帧就能读出"flying→splat→dazed"的切换点，
                       #   以及"落地那一帧 y 在哪"。追加在**行尾**，既有按 key 取值的
                       #   解析（probe98_block_scan.py）不受影响。
                       _g(window, '_fall_phase'), _g(window, '_fall_reason'),
                       _g(window, 'fall_speed')))
                _fblk.flush()
            except Exception:
                _fblk.write('ERR\n' + traceback.format_exc() + '\n')
                _fblk.flush()

        # ★ 关键帧 PNG：只在"方向/动画/尺寸/睡眠"变化时落一张。
        #   PNG 编码 2560×1600 实测 **20.4 s** 一次 ⇒ 整段只做有限次；
        #   且"明显变化的那一帧"正是人眼要看的证据帧。
        key = (_g(window, 'current_animation'), _g(window, 'current_direction'),
               window.width(), window.height(), bool(_g(window, 'is_sleeping')))
        if key != _LASTGEO[0]:
            _LASTGEO[0] = key
            # ★ 只截**宠物窗口外扩 40px** 的小图 ⇒ 编码面积小得多（也更好看）
            pad = 40
            x0 = max(0, p.x() - pad)
            y0 = max(0, p.y() - pad)
            x1 = min(arr.shape[1], p.x() + window.width() + pad)
            y1 = min(arr.shape[0], p.y() + window.height() + pad)
            crop = np.ascontiguousarray(arr[y0:y1, x0:x1])
            if crop.size:
                # ★★ 必须走 `imencode` + 手动写 bytes：
                #    `cv2.imwrite()` 在**含中文的路径**下会**静默返回 False**
                #    （实测：ASCII 路径 True / 中文路径 False，且不抛异常）
                #    ——本仓库路径全是中文，直接用 imwrite 就是"计数在涨、磁盘没文件"。
                _ok, _buf = cv2.imencode('.png', crop)
                if _ok:
                    with open(os.path.join(FRAMES, 'k%06d.png' % _KEY[0]), 'wb') as _fh:
                        _fh.write(_buf.tobytes())
                    _KEY[0] += 1
        _fcsv.flush()
    except Exception:
        _fsta.write('TICK-ERR frame=%d\n' % i + traceback.format_exc() + '\n')
        _fsta.flush()
    _N[0] = i + 1


tm = QTimer()
tm.timeout.connect(tick)
tm.start(TICK_MS)


def snap():
    try:
        p = window.pos()
        _fsta.write('t=%.1f pos=(%d,%d) sz=%dx%d anim=%r dir=%r mv=%r fall=%r '
                    'swalk=%r sleep=%r tgt=%r\n'
                    % (time.time() - _t0, p.x(), p.y(), window.width(), window.height(),
                       _g(window, 'current_animation'), _g(window, 'current_direction'),
                       _g(window, 'is_moving'), _g(window, 'is_falling'),
                       _g(window, 'is_sleeping_walk'), _g(window, 'is_sleeping'),
                       _g(window, 'target_pos')))
        _fsta.flush()
    except Exception:
        _fsta.write('ERR\n' + traceback.format_exc() + '\n')
        _fsta.flush()


tm2 = QTimer()
tm2.timeout.connect(snap)
tm2.start(1000)


# ★★★ 第96轮新增：**斜向扇区主动驱动器**（`REC97_DRIVE=1` 打开，默认关）
#   动机 = 第95轮报告 §8.4 自己承认的覆盖缺口：
#     「本次 148 s 里目标方向落在 [30,45) 的只有 0 帧、[45,60) 0 帧
#       ⇒ 真机跑根本没有走到原缺陷扇区」⇒ 于是"没看到朝右下反而朝左"**不构成验证**。
#   做法 = 只调产品**已有**的接口（`target_pos` + `is_moving`），把目标轮换设到
#     四个斜向角（**含 -141°/左上、+39°/右下**这两个实测缺陷角），
#     不新增任何行为、不改产品代码。
#   ⚠️ 它会让宠物**主动走向**这四角 ⇒ 记录里该扇区一定有帧，
#      这样 A5b/C4 才可能从"没测到"变成"真的验证了"。
if os.environ.get('REC97_DRIVE', '0') == '1':
    from PyQt5.QtCore import QPoint as _QP
    _CORNERS = [
        (u'左上(-135°附近)', -0.72, -0.70),   # ★ 本轮实测缺陷角 ≈ -141°
        (u'右下(+39°附近)', 0.78, 0.63),      # ★ 第95轮缺陷 B 的角度
        (u'左下(-141°附近)', -0.72, 0.70),
        (u'右上(+39°附近)', 0.78, -0.63),
    ]
    _drv = {'i': -1}

    def _drive():
        _drv['i'] = (_drv['i'] + 1) % len(_CORNERS)
        _label, _ux, _uy = _CORNERS[_drv['i']]
        try:
            _g_rect = window._virtual_screen_rect()
            _cx = (_g_rect.left() + _g_rect.right()) // 2
            _cy = (_g_rect.top() + _g_rect.bottom()) // 2
            _tx = int(_cx + _ux * (_g_rect.width() // 2 - 60))
            _ty = int(_cy + _uy * (_g_rect.height() // 2 - 60))
            window.target_pos = _QP(_tx, _ty)
            window.is_moving = True
            window.is_sleeping = False
            print('[rec97][DRIVE] #%d %s => target=(%d,%d) from=(%d,%d)'
                  % (_drv['i'], _label, _tx, _ty, window.pos().x(), window.pos().y()))
            sys.stdout.flush()
        except Exception:
            print('[rec97][DRIVE] fail\n' + traceback.format_exc())
            sys.stdout.flush()

    _tm3 = QTimer()
    _tm3.timeout.connect(_drive)
    _tm3.start(6000)
    QTimer.singleShot(500, _drive)


# ★★★ 第97轮新增：**坠落/跳跃定向注入**（`REC97_INJECT_FALL=1` 打开，默认关）
#   动机 = 第96轮 F7 的诚实缺口：「10 分钟**没有触发**坠落或跳跃 ⇒ 抛物线这条
#     本次无法验证」。自然漫游里坠落是**低频事件**，靠等几乎等不到。
#   做法 = 只调产品**已有**的公开入口（`start_falling` 重力坠落 / `start_fall`
#     原地摔），**不新增行为、不改产品代码**。
#   ⚠️ 注入属"定向覆盖"，不是自然行为 —— 报告里必须如实标注。
if os.environ.get('REC97_INJECT_FALL', '0') == '1':
    _inj = {'i': 0}

    def _inject_fall():
        _inj['i'] += 1
        try:
            if _inj['i'] % 2 == 1:
                window.start_falling(fall_velocity=180, is_thrown=True,
                                     reason='probe_inject')
                _tag = 'start_falling(180,thrown)'
            else:
                window.start_fall('window_move')
                _tag = "start_fall('window_move')"
            print('[rec97][INJECT] #%d %s at (%d,%d)'
                  % (_inj['i'], _tag, window.pos().x(), window.pos().y()))
            sys.stdout.flush()
        except Exception:
            print('[rec97][INJECT] fail\n' + traceback.format_exc())
            sys.stdout.flush()

    _tm4 = QTimer()
    _tm4.timeout.connect(_inject_fall)
    _tm4.start(15000)
    QTimer.singleShot(6000, _inject_fall)


# ★★★ 第98轮新增：**跳跃定向注入**（`REC98_INJECT_JUMP=1` 打开，默认关）
#   动机 = 用户口径「尤其是之前咱提到过的什么抛物线」；自然漫游里"跳桌面另一点"
#     几乎不发生（沙箱桌面**无窗口** ⇒ `_nearest_floor_jump` 无候选），光等看不到弧线。
#   做法 = 只调产品**已有**公开入口
#         `start_jump(None, 'bottom', target_floor=None, target_pos=QPoint(...))`
#     —— 与 `_start_floor_jump` 同源；落点由 `target_pos` 直接决定
#        （main.py:8123 `self.jump_target_pos = QPoint(target_x, target_y)`）。
#   方向**左右交替** ⇒ 同一段录像里能同时看到"向右弧线"与"向左弧线"，
#     便于人眼判断是否有"边跳边滑"（跳跃期还播走路动画）。
#   ⚠️ 同 REC97_INJECT_FALL：属"定向覆盖"，**报告里必须如实标注**（第97轮教训）。
if os.environ.get('REC98_INJECT_JUMP', '0') == '1':
    _inj2 = {'i': 0}

    def _inject_jump():
        _inj2['i'] += 1
        try:
            from PyQt5.QtCore import QPoint as _QP
            cur = window.pos()
            dx = 320 if _inj2['i'] % 2 == 1 else -320
            tgt = _QP(cur.x() + dx, cur.y())
            window.start_jump(None, 'bottom', target_floor=None, target_pos=tgt)
            print('[rec98][INJECT-JUMP] #%d from (%d,%d) -> (%d,%d)'
                  % (_inj2['i'], cur.x(), cur.y(), tgt.x(), tgt.y()))
            sys.stdout.flush()
        except Exception:
            print('[rec98][INJECT-JUMP] fail\n' + traceback.format_exc())
            sys.stdout.flush()

    _tm5 = QTimer()
    _tm5.timeout.connect(_inject_jump)
    _tm5.start(12000)
    QTimer.singleShot(8000, _inject_jump)


# ★★★ 第98轮新增：**重力坠落定向注入**（`REC98_INJECT_GFALL=1` 打开，默认关）
#   动机 = 自然漫游里重力坠落是**极低频**事件（`run_natural` 596 帧里 0 次；
#     `run_natural_postfix` 偶然抓到 1 次，恰恰暴露出"坠落途中却播 idle 站姿"）。
#   做法 = 只调产品**已有**公开入口：
#     ① `window.move(tx, ty)`（产品自身的窗口移动接口）把宠物抬到屏幕顶部；
#     ② `window.start_falling(fall_velocity=200, is_thrown=True, reason=...)`
#        （"建楼"的重力坠落入口）→ 宠物从屏幕顶部一路掉到桌面底边。
#   这样每轮都能**确定性地**拿到一段 `is_gravity_falling=True` 的窗口。
#   ⚠️ 同 REC97_INJECT_FALL / REC98_INJECT_JUMP：属"定向覆盖"，**报告里必须如实标注**。
if os.environ.get('REC98_INJECT_GFALL', '0') == '1':
    _inj3 = {'i': 0}

    def _inject_gfall():
        _inj3['i'] += 1
        try:
            _r = window._virtual_screen_rect()
            _tx = _r.left() + 120 + (_inj3['i'] % 3) * 320
            _ty = _r.top() + 40
            window.move(_tx, _ty)
            window.start_falling(fall_velocity=200, is_thrown=True,
                                 reason='probe_gfall')
            print('[rec98][INJECT-GFALL] #%d to (%d,%d)'
                  % (_inj3['i'], _tx, _ty))
            sys.stdout.flush()
        except Exception:
            print('[rec98][INJECT-GFALL] fail\n' + traceback.format_exc())
            sys.stdout.flush()

    _tm6 = QTimer()
    _tm6.timeout.connect(_inject_gfall)
    _tm6.start(20000)
    QTimer.singleShot(10000, _inject_gfall)


# ★★★ 第98轮新增：**鞠躬（bow / act）定向注入**（`REC98_INJECT_BOW=1`）
#   动机 = 用户真机反馈「**他在鞠躬那个动画的时候会自身位移**」。
#   `bow`(1 帧) 与 `act`(13 帧 · 容器 58x40 ⇒ 窗口 116x80) 属于**特殊动画**
#   （不在 `_NON_SPECIAL_ANIM_GROUPS` 里），理应"播完为止 + 播放期不移动"。
#   走产品**自己的**调用点（`main.py:5993` 那条 `play_animation_once(_anim,
#   restore_to="idle")` 的回落链 / `7468` 的 `play_animation_once("act")`），
#   并额外注入一次"边走边触发"（先 `is_moving=True` + `target_pos`，再立刻
#   `play_animation_once`），用来检验"特殊动画锁"是否真的挡住位移。
#   ⚠️ 同 REC97_INJECT_FALL / REC98_INJECT_JUMP：属"定向覆盖"，报告里如实标注。
if os.environ.get('REC98_INJECT_BOW', '0') == '1':
    _inj4 = {'i': 0}
    _BOW_SEQ = ('bow', 'act', 'curtsy', 'bow')

    def _inject_bow():
        _inj4['i'] += 1
        try:
            from PyQt5.QtCore import QPoint as _QP
            _name = _BOW_SEQ[_inj4['i'] % len(_BOW_SEQ)]
            _walking = (_inj4['i'] % 2 == 0)
            if _walking:
                # 故意制造"边走路边鞠躬"：给一个远目标并置 is_moving，
                # 再立刻 play_animation_once（模拟 `react_to_desktop_element`
                # 那条"走过去看看图标 → 顺手比划一下"的真实时序）。
                cur = window.pos()
                window.target_pos = _QP(cur.x() + 260, cur.y() - 40)
                window.is_moving = True
            window.play_animation_once(_name, restore_to='idle')
            print('[rec98][INJECT-BOW] #%d anim=%s walking=%s'
                  % (_inj4['i'], _name, _walking))
            sys.stdout.flush()
        except Exception:
            print('[rec98][INJECT-BOW] fail\n' + traceback.format_exc())
            sys.stdout.flush()

    _tm7 = QTimer()
    _tm7.timeout.connect(_inject_bow)
    _tm7.start(12000)
    QTimer.singleShot(6000, _inject_bow)


# ★★★ 第98轮新增：**不可达目标定向注入**（`REC98_INJECT_FAR=1`，默认关）
#   动机 = 用户口径「他还有**原地踏步**的问题」。自然漫游 9 次录制都没扫到，
#     于是做一次**定向覆盖**：把目标直接设到**屏幕右边界外 200px**
#     （模拟"桌面图标落在屏外 / 模块回调 `set_target_pos` 给了越界坐标"——
#      后者在自然录像里实测出现过 `x=-23`）。
#   ★ 这是"卡住兜底"的 A/B 夹具：
#       · 兜底**生效** ⇒ 连续 ~60 帧（≈1.8s）没位移就放弃目标、切 idle；
#       · 兜底**缺失** ⇒ 会一直 `walk_right` 原地踏步（`run_inj_bow` 已有
#         11.0s 的同类实证）。
#   ⚠️ 属"定向覆盖"，报告里如实标注（第97轮教训：夹具造出的现象不许当产品缺陷）。
if os.environ.get('REC98_INJECT_FAR', '0') == '1':
    _inj5 = {'i': 0}

    def _inject_far():
        _inj5['i'] += 1
        try:
            from PyQt5.QtCore import QPoint as _QP
            r = window._virtual_screen_rect()
            cur = window.pos()
            tx = int(r.right()) + 200
            ty = int(min(max(cur.y(), r.top()), r.bottom() - 100))
            window.target_pos = _QP(tx, ty)
            window.is_moving = True
            print('[rec98][INJECT-FAR] #%d from=(%d,%d) -> (%d,%d)'
                  % (_inj5['i'], cur.x(), cur.y(), tx, ty))
            sys.stdout.flush()
        except Exception:
            print('[rec98][INJECT-FAR] fail\n' + traceback.format_exc())
            sys.stdout.flush()

    _tm8 = QTimer()
    _tm8.timeout.connect(_inject_far)
    _tm8.start(18000)
    QTimer.singleShot(7000, _inject_far)


# ★★★ 第98轮新增：**"关窗坠落"定向注入**（`REC98_INJECT_CLOSEWIN=1`，默认关）
#   动机 = 用户口径「他下坠也不是直接下坠到屏幕底下啊，而且不是关掉窗口一瞬间
#     就摔扁，你总得摔到桌面上才能扁吧，是那种偏俯视2D游戏似的效果，不是侧视2D」。
#   沙箱盲区（必须写清楚）：本机桌面**没有窗口** ⇒ `check_window_movement` 永远
#     走不到 `start_falling(reason='floor_removed')`（那条要求 old_floor 是窗口
#     且 `is_floor_valid` 为假）。⇒ 用户在他满桌窗口的机器上看到的那一幕，
#     在沙箱里**结构性不可复现**。
#   ⇒ 夹具只造**产品自己造不出的前置条件**：把 `current_floor` 伪造成"一块
#     platform_height=10 的窗口楼板"（= 屏幕上叠了两层窗口），然后调**产品自己的**
#     `start_falling(reason='floor_removed')`。之后全部由产品逻辑跑 —— 落点、时长、
#     splat 时机都不是夹具定的。
#   ⚠️ 属"定向覆盖"，报告里如实标注为夹具；但**走的是产品真实链路**。
if os.environ.get('REC98_INJECT_CLOSEWIN', '0') == '1':
    _inj6 = {'i': 0}

    def _inject_closewin():
        _inj6['i'] += 1
        try:
            from PyQt5.QtCore import QRect as _QR
            _r = window._virtual_screen_rect()
            _ch = window.height() or 94
            _ty = _r.top() + 300
            # 伪造"站在 10 层高的窗口楼板上"（键名与 floor_manager._generate_floors 一致）
            _fake = {
                'type': 'window',
                'rect': _QR(_r.left(), _ty, _r.width(), _ch),
                'visible_rects': [_QR(_r.left(), _ty, _r.width(), _ch)],
                'visible_area': _r.width() * _ch,
                'z_order': 1,
                'platform_height': 10,
                'window_hwnd': 0,          # 0 = 不存在于 underlying_windows ⇒ is_floor_valid False
            }
            window.current_floor = _fake
            window.current_platform_z = 10
            window.spatial_pos['z'] = 10
            _tx = _r.left() + 200 + (_inj6['i'] % 4) * 260
            window.move(_tx, _ty)
            window.start_falling(fall_velocity=0, is_thrown=False,
                                 reason='floor_removed')
            print('[rec98][INJECT-CLOSEWIN] #%d from (%d,%d) floor_ph=10'
                  % (_inj6['i'], _tx, _ty))
            sys.stdout.flush()
        except Exception:
            print('[rec98][INJECT-CLOSEWIN] fail\n' + traceback.format_exc())
            sys.stdout.flush()

    _tm9 = QTimer()
    _tm9.timeout.connect(_inject_closewin)
    _tm9.start(15000)
    QTimer.singleShot(5000, _inject_closewin)


def _bye():
    print('[rec97] life=%ds reached, quitting' % SECS)
    sys.stdout.flush()
    app.quit()


QTimer.singleShot(SECS * 1000, _bye)

if __name__ == '__main__':
    rc = app.exec_()
    tm.stop()
    tm2.stop()
    _vw.release()
    for f in (_fcsv, _fmov, _fani, _fsta):
        f.close()
    if _fblk is not None:
        _fblk.close()

    # ---- 记录视频统计（RAW 已是可直接播放的 mp4v，无需再转码）----
    vid_msg = ''
    try:
        rd = cv2.VideoCapture(RAW)
        n = 0
        while True:
            ok, _fr = rd.read()
            if not ok:
                break
            n += 1
        rd.release()
        vid_msg = u'OK 可解码帧数=%d' % n
    except Exception:
        vid_msg = 'FAIL ' + traceback.format_exc()

    meta = io.open(os.path.join(EV, 'rec97_meta.txt'), 'w', encoding='utf-8', newline='\n')
    dur = time.time() - _t0
    meta.write(u'=== rec97 录制元信息（v3：mp4v 边抓边写，关键帧落小图 PNG）===\n')
    meta.write(u'pid                 = %d\n' % os.getpid())
    meta.write(u'时长设定            = %d s\n' % SECS)
    meta.write(u'抓屏周期            = %d ms\n' % TICK_MS)
    meta.write(u'编码 fourcc         = %s\n' % FOURCC)
    meta.write(u'实际帧数            = %d\n' % _N[0])
    meta.write(u'有效采集率          = %.2f Hz\n' % (_N[0] / dur if dur else 0))
    meta.write(u'关键帧 PNG 数       = %d\n' % _KEY[0])
    meta.write(u'墙钟耗时            = %.1f s\n' % dur)
    meta.write(u'抓屏累计            = %.1f s（每帧均 %.1f ms）\n'
               % (_GRAB_MS[0] / 1000.0, _GRAB_MS[0] / max(_N[0], 1)))
    meta.write(u'编码累计            = %.1f s（每帧均 %.1f ms）\n'
               % (_ENC_MS[0] / 1000.0, _ENC_MS[0] / max(_N[0], 1)))
    meta.write(u'占用率(抓+编)/墙钟  = %.1f%%\n'
               % (100.0 * (_GRAB_MS[0] + _ENC_MS[0]) / (dur * 1000.0) if dur else 0))
    meta.write(u'屏幕                = %dx%d\n' % (_W, _H))
    # ★★ 自证判据：不拿"计数器"当成功，去**磁盘上数一遍**
    #    （v3 首跑就是"计数器 15 / 磁盘 0" —— imwrite 静默失败）
    _ondisk = sorted(f for f in os.listdir(FRAMES) if f.endswith('.png')) \
        if os.path.isdir(FRAMES) else []
    meta.write(u'frames/ 实际 PNG 数  = %d（计数器 %d）%s\n'
               % (len(_ondisk), _KEY[0],
                  u'' if len(_ondisk) == _KEY[0] else u' ← ★ 不一致！落盘失败'))
    meta.write(u'录像                = %s (%.1f MB)\n'
               % (RAW, os.path.getsize(RAW) / 1048576.0 if os.path.exists(RAW) else -1))
    meta.write(u'录像校验            = %s\n' % vid_msg)
    meta.write(u'退出码              = %d\n' % rc)
    meta.close()
    print('[rec97] exit rc=%d frames=%d keypng=%d' % (rc, _N[0], _KEY[0]))
    sys.exit(rc)
