# -*- coding: utf-8 -*-
u"""rec106.py —— 第106轮「非瞬移 + 全屏化」的**真机录制端**。

用户口径
--------
「**一定要看录像而不是只读后台输出**」＋本批原话
「**完整的走过去**，记住，如果我对里面任何一个人说马上回桌面，那他们顶多是
带着我一起**非常快地按原路线返回**，也不是瞬移（相当于加快速度跑回来，
也要全程）」＋「我要的是**类似游戏全屏**的那种场景效果」。

本批要录到的一幕
----------------
与第105轮**同一段**注入（`INIT → S1`，桌面→OneShot 实测 18 跳），但这次
要看的不一样：
  · ★ **中间每一间房都要出现**（第105轮录屏**证明它没出现** —— HOP 行
    `INIT → S1` 一步到位）。这才是本轮的靶心：判据从 FAIL 转 PASS。
  · ★ **相机输出变大**：CSV 每帧记 `cw/chh`（画布尺寸）与 `cam_scale`；
    改前 640×480 @ scale 2.0 ⇒ 改后 680×510 @ scale 2.125（2560×1600 屏）。
  · ★ **人物等比放大**：`cam_scale` 单调升 ⇒ `to_output` 的乘法放大
    （背景/物件/人物**同一条**换算 ⇒ 不需要特判，但要在录像里看得见）。

★ 为什么必须"产品进程内抓屏"
---------------------------
宠物是 `Qt.Tool` **非置顶 + 透明分层窗口** ⇒ 外部进程 `BitBlt`/`PrintWindow`
抓不到（记忆铁律：看不见 ≠ 不存在）。本进程 `QScreen.grabWindow(0)` 拿的是
**合成后的桌面** ⇒ 看到的＝用户看到的。

★ 复用 rec105/rec99 已踩实的坑（**别再犯**）
-----------------------------------------
  · `QPixmap.save(..., 'PNG')` 2560×1600 要 ~20 s ⇒ 只对**状态变化帧**落小图。
  · 编码选 **mp4v**（~11 ms/帧）；FFV1 要 173 ms/帧，干扰太大。
  · `csv.writer` 默认 `\\r\\n` ⇒ 统一 `lineterminator='\\n'`（分析端按字节忠实读）。
  · `cv2.imwrite()` 在**中文路径**下**静默返回 False** ⇒ `imencode` + 手写。
  · 清旧产物用**整目录改名归档**（删除守卫按累计路径数计账，阈值 50）。
  · **绝不 remove `rec106_stdout.txt`**（shell 重定向目标，删掉会丢 stdout）。

★ 注入序列（`REC106_INJECT=1`，默认关）
--------------------------------------
只调产品**已有**的公开入口，**不新增行为、不改产品代码**：
  · `window.travel_to_scene(scene_id)` —— 第76轮 R0-1 的用户可见入口
    （右键菜单/聊天走的就是它）。★ 本轮它内部**应**走 `walk_steps` 逐跳。
  · `window.scene.switch(sid)` —— 把起点摆好（走产品自己的 `switch`，不绕门禁）。
  ⚠️ 属"定向覆盖"（自然状态下宠物不会自己跑去 OneShot）⇒ 报告里必须如实标注。

★ 观察量全部由**产品代码自己**填
------------------------------
`current_scene` / `_scene_chapter_id` / `_scene_state.original_room_id`
/ `scene_camera` 的 `size`+`scale` / `scene_canvas` 的 `width()`+`height()`
—— 不从像素里"猜"状态；像素只用来给人眼看。

产物（落本轮 `_evidence/`）
--------------------------
  rec106_meta.txt / rec106_frames.csv / rec106_hops.txt / rec106_inject.txt
  rec106_state.txt / rec106_raw.avi / frames/*.png（场景/画布变化帧）

跑法
----
  cd <ralsei_pet 包目录>
  set REC106_SECS=110
  set REC106_INJECT=1
  C:\\Python311\\python.exe <仓库根>\\code-quality-audit\\第106轮-非瞬移与全屏化\\_tools\\rec106.py
"""
import csv
import io
import json
import os
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.normpath(os.path.join(HERE, '..'))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')
SRC = os.path.join(PKG, 'src')
EV = os.environ.get('REC106_EVDIR') or os.path.join(ROUND, '_evidence')
FRAMES = os.path.join(EV, 'frames')

SECS = int(os.environ.get('REC106_SECS', '110'))
TICK_MS = int(os.environ.get('REC106_TICK_MS', '250'))
RAW = os.path.join(EV, 'rec106_raw.avi')
FOURCC = os.environ.get('REC106_FOURCC', 'mp4v')

os.makedirs(FRAMES, exist_ok=True)

# ---- 自清旧产物：整目录改名归档（删除守卫按累计路径数计账）----
if os.environ.get('REC106_PURGE', '1') == '1':
    _ts = time.strftime('%Y%m%d_%H%M%S')
    _prev = os.path.join(EV, 'frames_prev_%s' % _ts)
    try:
        if os.path.isdir(FRAMES) and os.listdir(FRAMES):
            os.rename(FRAMES, _prev)
            os.makedirs(FRAMES)
            print('[rec106] 上一轮关键帧已整目录归档到 %s' % os.path.basename(_prev))
    except Exception as _e:
        print('[rec106] 归档上一轮关键帧失败（忽略）：%r' % (_e,))
    for _f in ('rec106_frames.csv', 'rec106_hops.txt', 'rec106_inject.txt',
               'rec106_state.txt', 'rec106_meta.txt', 'rec106_raw.avi'):
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
print('[rec106] shown pid=%d title=%r' % (os.getpid(), window.windowTitle()))
sys.stdout.flush()

try:
    import ctypes
    ctypes.windll.user32.SetProcessDPIAware()
except Exception:
    pass

# ★ 关掉无关的墙钟逻辑，把变量收敛到"换场景"这一条链上（同 rec105 的做法）
for _attr, _val in (('BEDTIME_ENABLED', False),):
    try:
        setattr(window, _attr, _val)
    except Exception:
        pass

_scr = app.primaryScreen()
_geo = _scr.geometry()
_W, _H = _geo.width(), _geo.height()

_t0 = time.time()
_fcsv = io.open(os.path.join(EV, 'rec106_frames.csv'), 'w', encoding='utf-8', newline='')
_csvw = csv.writer(_fcsv, lineterminator='\n')
# ★ 这些列**全部是产品字段**：当前场景 / 章 / 房间下标 / 玩家位置 /
#   画布尺寸 / 相机 scale（全屏化的唯一证据面）
_csvw.writerow(['frame', 't', 'scene', 'chapter', 'rid', 'has_state',
                'wx', 'wy', 'ww', 'wh', 'anim', 'dir', 'moving',
                'canvas_vis', 'cw', 'chh', 'cam_w', 'cam_h', 'cam_scale',
                'cam_scoped_w', 'cam_scoped_h', 'spdx', 'spdy'])
_fhops = io.open(os.path.join(EV, 'rec106_hops.txt'), 'w', encoding='utf-8', newline='\n')
_fsta = io.open(os.path.join(EV, 'rec106_state.txt'), 'w', encoding='utf-8', newline='\n')
_finj = io.open(os.path.join(EV, 'rec106_inject.txt'), 'w', encoding='utf-8', newline='\n')

_vw = cv2.VideoWriter(RAW, cv2.VideoWriter_fourcc(*FOURCC), 1000.0 / TICK_MS, (_W, _H))
if not _vw.isOpened():
    print('[rec106] FATAL: VideoWriter(%s) 打不开' % FOURCC)
    sys.exit(2)

_N = [0]
_KEY = [0]
_ENC_MS = [0.0]
_GRAB_MS = [0.0]
_LASTKEY = [None]
_LASTSCENE = [None]


def _g(o, n, d=None):
    try:
        return getattr(o, n, d)
    except Exception:
        return d


def _scene_fields():
    """当前场景的三元组（**全部读产品状态**，不猜）。"""
    sid = window.__dict__.get('current_scene')
    ch = window.__dict__.get('_scene_chapter_id')
    st = window.__dict__.get('_scene_state')
    rid = getattr(st, 'original_room_id', None) if st is not None else None
    return sid, ch, rid, (st is not None)


def _cam_fields():
    """相机字段（**全屏化的证据面**，读产品对象，不猜）。

    ★ 坑（第106轮实测改正）：相机**不在** `window.scene_camera`（没有这个属性），
      真源是 `pet._scene_camera`，且它就是 `scene_camera.Camera` **本身**
      （不是包装 —— 见 `scene_controller.init_camera` L357~366）。
      第一版按 `window.scene_camera.camera` 取 ⇒ 恒得 `-1/-1/None`，
      全屏化判据 B1~B7 全部假红（**判据错，不是产品错**；产品日志明明写着
      `全屏化：相机输出 1732x1299 … scale=5.412`）。
    """
    cam = window.__dict__.get('_scene_camera')
    if cam is None:
        sc = getattr(window, 'scene', None)
        cam = getattr(sc, 'camera', None) if sc is not None else None
    if cam is None:
        return (-1, -1, None, -1, -1)
    try:
        w, h = cam.size
    except Exception:
        w, h = -1, -1
    try:
        scale = float(cam.scale)
    except Exception:
        scale = None
    try:
        sw, sh = cam.scoped_size()
    except Exception:
        sw, sh = -1, -1
    return (w, h, scale, sw, sh)


def tick():
    i = _N[0]
    try:
        t = time.time() - _t0
        tg = time.time()
        pm = _scr.grabWindow(0)
        img = pm.toImage()
        ptr = img.bits()
        ptr.setsize(img.byteCount())
        raw = bytes(ptr)
        arr = np.frombuffer(raw, np.uint8).reshape(img.height(),
                                                   img.bytesPerLine() // 4, 4)
        arr = arr[:, :img.width(), :3]                      # BGRA -> BGR
        _GRAB_MS[0] += (time.time() - tg) * 1000.0
        te = time.time()
        _vw.write(np.ascontiguousarray(arr))
        _ENC_MS[0] += (time.time() - te) * 1000.0

        p = window.pos()
        sid, ch, rid, has_st = _scene_fields()
        cam_w, cam_h, cam_scale, sco_w, sco_h = _cam_fields()
        cv_ = getattr(window, 'scene_canvas', None)
        cvis = bool(cv_ is not None and cv_.isVisible())
        cw = cv_.width() if cv_ is not None else -1
        chh = cv_.height() if cv_ is not None else -1
        svx = _g(window, 'current_speed_x')
        svy = _g(window, 'current_speed_y')
        _csvw.writerow([i, '%.3f' % t, sid or '', ch or '', rid if rid is not None else '',
                        has_st, p.x(), p.y(), window.width(), window.height(),
                        _g(window, 'current_animation'), _g(window, 'current_direction'),
                        _g(window, 'is_moving'), cvis, cw, chh,
                        cam_w, cam_h,
                        ('%.6f' % cam_scale) if cam_scale is not None else '',
                        sco_w, sco_h,
                        ('%.6f' % svx) if svx is not None else '',
                        ('%.6f' % svy) if svy is not None else ''])

        # ★ 换场景那一刻 → 记一行"HOP"（产品字段，不是我从像素读的）
        if sid != _LASTSCENE[0]:
            _fhops.write('t=%.3f frame=%d  %r  →  %r   (chapter=%r rid=%r)\n'
                         % (t, i, _LASTSCENE[0], sid, ch, rid))
            _fhops.flush()
            _LASTSCENE[0] = sid

        # ★ 关键帧 PNG：场景/画布可见性/相机尺寸变化时落一张
        key = (sid, cvis, _g(window, 'current_animation'), cam_w, cam_h,
               window.width(), window.height())
        if key != _LASTKEY[0]:
            _LASTKEY[0] = key
            pad = 40
            x0 = max(0, p.x() - pad)
            y0 = max(0, p.y() - pad)
            x1 = min(arr.shape[1], p.x() + window.width() + pad)
            y1 = min(arr.shape[0], p.y() + window.height() + pad)
            crop = np.ascontiguousarray(arr[y0:y1, x0:x1])
            if crop.size:
                # ★★ `cv2.imwrite()` 在中文路径下**静默返回 False** ⇒ imencode + 手写
                _ok, _buf = cv2.imencode('.png', crop)
                if _ok:
                    with open(os.path.join(FRAMES, 'k%06d.png' % _KEY[0]), 'wb') as _fh:
                        _fh.write(_buf.tobytes())
                    _fsta.write('KEY #%d t=%.3f scene=%r cvis=%r anim=%r cw=%d chh=%d '
                                'cam=%dx%d scale=%s scoped=%dx%d\n'
                                % (_KEY[0], t, sid, cvis,
                                   _g(window, 'current_animation'), cw, chh,
                                   cam_w, cam_h, cam_scale, sco_w, sco_h))
                    _fsta.flush()
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
        sid, ch, rid, has_st = _scene_fields()
        cam_w, cam_h, cam_scale, sco_w, sco_h = _cam_fields()
        _fsta.write('t=%.1f scene=%r chapter=%r rid=%r anim=%r dir=%r mv=%r '
                    'pos=(%d,%d) cam=%dx%d scale=%s scoped=%dx%d\n'
                    % (time.time() - _t0, sid, ch, rid,
                       _g(window, 'current_animation'), _g(window, 'current_direction'),
                       _g(window, 'is_moving'), window.pos().x(), window.pos().y(),
                       cam_w, cam_h, cam_scale, sco_w, sco_h))
        _fsta.flush()
    except Exception:
        _fsta.write('ERR\n' + traceback.format_exc() + '\n')
        _fsta.flush()


tm3 = QTimer()
tm3.timeout.connect(snap)
tm3.start(1000)


# ============================================================ 注入序列
# ★ 只调产品**已有**入口。`travel_to_scene` 就是右键菜单/聊天走的那条路。
if os.environ.get('REC106_INJECT', '0') == '1':
    _T_START = int(os.environ.get('REC106_AT_START', '6000'))
    _T_GO_OS = int(os.environ.get('REC106_AT_GO_OS', '12000'))
    _T_GO_DELTA = int(os.environ.get('REC106_AT_GO_DELTA', '60000'))
    _OS_FROM = os.environ.get('REC106_OS_FROM', 'oneshot.mainline.INIT')
    _OS_TO = os.environ.get('REC106_OS_TO', 'oneshot.mainline.S1')
    _DL_FROM = os.environ.get('REC106_DL_FROM', 'ch1.kris_room.kris_s_room')
    _DL_TO = os.environ.get('REC106_DL_TO', u'\u6559\u5802')

    def _log(tag, extra=''):
        sid, ch, rid, _ = _scene_fields()
        _finj.write('t=%.3f %s scene=%r chapter=%r rid=%r %s\n'
                    % (time.time() - _t0, tag, sid, ch, rid, extra))
        _finj.flush()
        print('[rec106][INJECT] %s %s' % (tag, extra))
        sys.stdout.flush()

    def _switch_direct(sid):
        """把起点摆好：**走产品自己的 `scene.switch()`**（不绕门禁）。"""
        try:
            ok = window.scene.switch(sid)
            try:
                window._possession_sync_world()
            except Exception:
                pass
            return ok
        except Exception:
            _finj.write('switch(%r) FAIL\n' % (sid,) + traceback.format_exc() + '\n')
            _finj.flush()
            return False

    def _do_start_os():
        ok = _switch_direct(_OS_FROM)
        _log('SET-START(oneshot)', 'switch_ok=%r to=%r' % (ok, _OS_FROM))

    def _do_go_os():
        t0 = time.time()
        rv = window.travel_to_scene(_OS_TO)
        _log('TRAVEL(oneshot)', 'target=%r ret=%r  wall=%.2fs'
             % (_OS_TO, rv, time.time() - t0))

    def _do_start_delta():
        ok = _switch_direct(_DL_FROM)
        _log('SET-START(delta)', 'switch_ok=%r to=%r' % (ok, _DL_FROM))

    def _do_go_delta():
        t0 = time.time()
        rv = window.travel_to_scene(_DL_TO)
        _log('TRAVEL(delta)', 'target=%r ret=%r  wall=%.2fs'
             % (_DL_TO, rv, time.time() - t0))

    def _do_home():
        """★ 用户口径「非常快地按**原路线**返回」—— 走 `walk_route_home()`。"""
        t0 = time.time()
        try:
            rv = window.scene.walk_route_home()
        except Exception:
            rv = {'ok': False, 'error': traceback.format_exc()}
        _log('WALK-HOME', 'ret=%r  wall=%.2fs' % (rv, time.time() - t0))

    QTimer.singleShot(_T_START, _do_start_os)
    QTimer.singleShot(_T_GO_OS, _do_go_os)
    QTimer.singleShot(_T_GO_DELTA, _do_start_delta)
    QTimer.singleShot(_T_GO_DELTA + 3000, _do_go_delta)
    if os.environ.get('REC106_HOME', '0') == '1':
        _T_HOME = int(os.environ.get('REC106_AT_HOME', '90000'))
        QTimer.singleShot(_T_HOME, _do_home)


def _bye():
    print('[rec106] life=%ds reached, quitting' % SECS)
    sys.stdout.flush()
    app.quit()


QTimer.singleShot(SECS * 1000, _bye)

if __name__ == '__main__':
    rc = app.exec_()
    tm.stop()
    tm3.stop()
    _vw.release()
    for f in (_fcsv, _fhops, _fsta, _finj):
        f.close()

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

    meta = io.open(os.path.join(EV, 'rec106_meta.txt'), 'w', encoding='utf-8', newline='\n')
    dur = time.time() - _t0
    meta.write(u'=== rec106 录制元信息（非瞬移 + 全屏化 · mp4v 边抓边写 · 状态变化帧落小图）===\n')
    meta.write(u'pid                 = %d\n' % os.getpid())
    meta.write(u'时长设定            = %d s\n' % SECS)
    meta.write(u'抓屏周期            = %d ms\n' % TICK_MS)
    meta.write(u'编码 fourcc         = %s\n' % FOURCC)
    meta.write(u'注入                = REC106_INJECT=%s\n' % os.environ.get('REC106_INJECT', '0'))
    meta.write(u'  oneshot 起点/终点 = %r → %r（%ss）\n'
               % (os.environ.get('REC106_OS_FROM'), os.environ.get('REC106_OS_TO'),
                  os.environ.get('REC106_AT_GO_OS')))
    meta.write(u'  delta 起点/终点   = %r → %r（%ss）\n'
               % (os.environ.get('REC106_DL_FROM'), os.environ.get('REC106_DL_TO'),
                  os.environ.get('REC106_AT_GO_DELTA')))
    meta.write(u'  回程 REC106_HOME  = %s（%ss）\n'
               % (os.environ.get('REC106_HOME', '0'),
                  os.environ.get('REC106_AT_HOME')))
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
    print('[rec106] exit rc=%d frames=%d keypng=%d' % (rc, _N[0], _KEY[0]))
    sys.exit(rc)
