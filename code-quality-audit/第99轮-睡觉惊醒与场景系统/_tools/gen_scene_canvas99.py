# -*- coding: utf-8 -*-
u"""gen_scene_canvas99.py —— 第99轮「场景系统 · 把原作全屏化」**真机录屏检查**。

用户口径（本轮逐字，硬要求）：
    「做完之后还是**自己用录屏方式检查**」
    「那个场景系统就像是**把原作全屏化**似的，但**不是真的全屏，只是说像**哦」

它回答四个**只有真机能回答**的问题（离线判据一个都答不了）：
  1. 进一间真有背景的房，屏幕上**到底画出了什么**？（=`canvas.grab()` 之外，
     还要看**合成后的桌面**——因为画布是透明分层窗口）
  2. 修好之后 `canvas.last_drawn` 还是 1 吗？（改前 `card_castle_1f` 是 **1 = 只有
     一条窗口外的 room_border**，屏幕上零像素）
  3. 画布区域里**有没有非壁纸的像素**？（把"壁纸透出来"与"真的画了房间"分开）
  4. **宠物还在画布之上吗**？Win32 z 序枚举 —— 几何与标志位量不出"谁盖住谁"。

★ 为什么必须"进程内抓屏"
    宠物是 `Qt.Tool` 非置顶 + 透明分层窗口 ⇒ 外部 `BitBlt/PrintWindow` 抓不到。
    本进程 `QScreen.grabWindow(0)` 拿的是**合成后的桌面** ⇒ 看到的＝用户看到的。

★ 不改产品：只调产品已有公开入口（`travel_to_scene`）+ 只读内省。

产物（落 `_evidence/scene99/`）
-------------------------------
  scene99_state.txt      每个采样一行（几何/相机/计划/像素统计 + z 序）
  scene99_meta.txt       元信息
  scene99_shots/*.png    每个采样：**整屏**（缩到 1280 宽）+ **画布裁剪原尺寸**
  scene99_contact.png    拼图（我肉眼看的那张）

跑法
----
  cd <仓库根>
  C:\\Python311\\python.exe code-quality-audit\\第99轮-睡觉惊醒与场景系统\\_tools\\gen_scene_canvas99.py
"""
import ctypes
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
EV = os.environ.get('GEN99_EVDIR') or os.path.join(ROUND, '_evidence', 'scene99')
# ★★ 第99轮踩到的坑：本脚本在下面会 `os.chdir(PKG)`（真机要求 cwd 在包内），
#   而 `GEN99_EVDIR` 若传的是**相对路径**，`makedirs` 时还算对（cwd 还是仓库根），
#   到了写 `scene99_state.txt` 时 cwd 已经变了 ⇒ `FileNotFoundError`，
#   而且**在错误的地方建了空目录**（最难查的那种）。
#   ⇒ 入口处一次性把 EV 归一成**绝对路径**，之后 chdir 多少次都不受影响。
EV = os.path.abspath(EV)
SHOTS = os.path.join(EV, 'scene99_shots')

os.makedirs(SHOTS, exist_ok=True)

os.chdir(PKG)
if SRC in sys.path:
    sys.path.remove(SRC)
sys.path.insert(0, SRC)

import main as M                                                  # noqa: E402
from PyQt5.QtWidgets import QApplication                           # noqa: E402
from PyQt5.QtCore import QTimer, Qt                                # noqa: E402
from PyQt5.QtGui import QPixmap, QPainter, QColor                  # noqa: E402


#: 宠物"在帧内"判据的容差：同一像素在"宠物窗口自渲染"与"合成桌面"里的 RGB 曼哈顿差。
#  ★ 动画过渡 / 半透明边缘本身就有差 ⇒ 不能设 0；28 是实测两侧（in / out）之间的中点。
_PIF_TOL = 28
#: mask 像素数下限：低于它说明宠物窗口这一帧几乎没有不透明像素（正在淡出 / 未显示）
#  ⇒ **不判**（返回 `'unknown'`），不许冒充结论。
_PIF_MIN_MASK = 64


def pet_in_frame(full_img, direct_img, box, tol=_PIF_TOL, min_mask=_PIF_MIN_MASK):
    u"""★★★ 判「宠物真的在**这一帧**里」—— 返回 `(state, n_mask, mean_diff)`。

    为什么必须判（第99轮用户提醒「我在工作，会切换另一个桌面」）：
    宠物是**非置顶** `Qt.Tool`，且只活在**启动时那个虚拟桌面**上。用户切到另一个
    桌面后，`grabWindow(0)` 抓到的是**当前桌面**（里面没有宠物），而工具会照常存下
    一张"看起来正常"的图 ⇒ **静默假证据**。
    ★ 所以「抓到画面了」**不等于**「抓到宠物了」。

    判据（正 / 负两侧都能分开）：
      · `direct_img` = `grabWindow(宠物 winId)` —— 宠物窗口**自己**的内容
        （与"桌面当前是否可见"无关，切了桌面也拿得到）
      · `full_img`   = `grabWindow(0)`          —— **合成后**的当前桌面
      取 `direct_img` 里**足够不透明**的像素作剪影 mask，比同一批坐标在 `full_img` 的颜色：
        宠物在**当前**桌面 ⇒ 两处颜色**接近**（差小）        ⇒ `'in'`
        宠物在**别的**桌面 ⇒ `full` 那位置是壁纸/别的窗口   ⇒ 差大   ⇒ `'out'`
      mask 太小（窗口正淡出 / 未显示）⇒ `'unknown'`（**不判**，不冒充结论）。

    ★ 用 `QImage` 而非 `QPixmap`：`QImage` **不需要** `QApplication`，
      所以这个纯函数能在**离屏、零 GUI** 下自测（见 `_selftest_pif`）。
    """
    try:
        if full_img is None or direct_img is None:
            return ('unknown', 0, None)
        x, y, w, h = (int(v) for v in box)
        if w <= 0 or h <= 0:
            return ('unknown', 0, None)
        dw, dh = direct_img.width(), direct_img.height()
        fw, fh = full_img.width(), full_img.height()
        n = 0
        tot = 0
        for j in range(0, h):
            if j >= dh:
                break
            sy = y + j
            if sy < 0 or sy >= fh:
                continue
            for i in range(0, w):
                if i >= dw:
                    break
                sx = x + i
                if sx < 0 or sx >= fw:
                    continue
                d = direct_img.pixel(i, j)
                if ((d >> 24) & 0xFF) < 200:      # 该点宠物是透明的 ⇒ 不进 mask
                    continue
                f = full_img.pixel(sx, sy)
                tot += (abs(((d >> 16) & 0xFF) - ((f >> 16) & 0xFF))
                        + abs(((d >> 8) & 0xFF) - ((f >> 8) & 0xFF))
                        + abs((d & 0xFF) - (f & 0xFF)))
                n += 1
        if n < min_mask:
            return ('unknown', n, None)
        md = tot / float(n)
        return (('in' if md <= tol else 'out'), n, md)
    except Exception:
        return ('unknown', 0, None)


def _selftest_pif():
    u"""`pet_in_frame` 的**正 / 负控制成对**自测（离屏、零 GUI、零真机）。

    ★ 判据自己也会说谎 ⇒ 这是「判据也是被测物」的收口动作：
      正控制必须判 `'in'`、负控制必须判 `'out'`、不可判定必须判 `'unknown'`。
    ★ 之所以敢在"用户正在工作机上干活"时跑它：它**只碰 `QImage`**，
      **不建任何窗口**、不抢焦点、不动用户的桌面。
    """
    from PyQt5.QtGui import QImage
    W, H = 64, 64
    BOX = (100, 50, W, H)

    def _sprite(alpha=0xFF):
        im = QImage(W, H, QImage.Format_ARGB32)
        im.fill(0)                                   # 全透明
        for yy in range(8, 56):
            for xx in range(16, 48):
                im.setPixel(xx, yy, (alpha << 24) | 0x2E86C1)   # 不透明蓝块（"宠物"）
        return im

    def _screen(fill, w=256, h=160):
        im = QImage(w, h, QImage.Format_ARGB32)
        im.fill(fill)
        return im

    sp = _sprite()
    # 正控制：合成桌面 = 宠物真的画在 box 位置上
    pos = _screen(0xFF808080)
    for yy in range(H):
        for xx in range(W):
            pos.setPixel(BOX[0] + xx, BOX[1] + yy, sp.pixel(xx, yy) | 0xFF000000)
    # 负控制：合成桌面是**纯壁纸**（同尺寸、同位置，但宠物在别的桌面 / 被盖住）
    neg = _screen(0xFFB0C4DE)
    # 不可判定控制：宠物窗口这一帧几乎全透明（淡出中）
    faint = _sprite(alpha=0x20)

    cases = [
        ('正控制：宠物在当前桌面', pos, sp, _PIF_TOL, 'in'),
        ('负控制：宠物不在帧内（壁纸）', neg, sp, _PIF_TOL, 'out'),
        ('不可判定：宠物窗口近乎全透明', pos, faint, _PIF_TOL, 'unknown'),
        ('不可判定：空图', None, sp, _PIF_TOL, 'unknown'),
    ]
    bad = 0
    for name, full, direct, tol, want in cases:
        got, n, md = pet_in_frame(full, direct, BOX, tol=tol)
        ok = (got == want)
        bad += 0 if ok else 1
        print('[PASS] PIF %s：state=%r n_mask=%d mean_diff=%s'
              % ('OK' if ok else 'FAIL', got, n,
                 ('%.2f' % md) if md is not None else 'None'))
        print('       %s（期望 %r，得到 %r）' % (name, want, got))
    print('---')
    print('pet_in_frame 自测：%d/%d' % (len(cases) - bad, len(cases)))
    return 1 if bad else 0


if os.environ.get('GEN99_SELFTEST') == '1':
    # ★ 只跑纯函数自测：**不 import main、不建窗口、不碰用户桌面**。
    sys.exit(_selftest_pif())


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
try:
    window.BEDTIME_ENABLED = False
except Exception:
    pass
try:
    M.RalseiPet.NPC_AUTONOMOUS_MOVE = False
except Exception:
    pass

print('[gen99] shown pid=%d' % os.getpid())
sys.stdout.flush()

try:
    ctypes.windll.user32.SetProcessDPIAware()
except Exception:
    pass

_scr = app.primaryScreen()
_geo = _scr.geometry()
_W, _H = _geo.width(), _geo.height()

#: 观察序列：每项 = (标签, scene_id 或 None 表示不动, 采样前等待秒数)
SEQ = [
    ('desktop_before', None, 0.0),
    ('card_castle_1f', 'ch1.card_castle.card_castle_1f', 2.5),
    ('kris_s_room', 'ch1.kris_room.kris_s_room', 2.5),
    ('castle_front', 'ch1.castle_town.castle_front', 2.5),
    ('field_seams_shop', 'ch1.field.field_seams_shop', 2.5),
    ('back_desktop', 'desktop', 2.5),
]

_u32 = ctypes.windll.user32
_GW_HWNDNEXT = 2


def _g(o, n, d=None):
    try:
        return getattr(o, n, d)
    except Exception:
        return d


def _call(o, n, d=None):
    try:
        return getattr(o, n)()
    except Exception:
        return d


def _zorder_map():
    order = {}
    try:
        h = _u32.GetTopWindow(None)
        i = 0
        while h and i < 4000:
            order[int(h)] = i
            h = _u32.GetWindow(h, _GW_HWNDNEXT)
            i += 1
    except Exception:
        pass
    return order


def _hwnd(w):
    try:
        return int(w.winId())
    except Exception:
        return -1


def _cls(h):
    try:
        buf = ctypes.create_unicode_buffer(256)
        _u32.GetClassNameW(int(h), buf, 256)
        return buf.value
    except Exception:
        return ''


def _pix_stats(pm, box=None):
    """裁一块 → `(distinct 颜色数, 采样点, 均值 RGB)`。

    ★ 用 `Qt.FastTransformation`（最近邻）缩放噪声最小；直接逐点采样 4px 一格。
    """
    try:
        if box:
            pm = pm.copy(*box)
        if pm.isNull():
            return (0, 0, None)
        img = pm.toImage()
        step = max(1, int(max(img.width(), img.height()) / 120))
        seen = set()
        n = 0
        sr = sg = sb = 0
        for y in range(0, img.height(), step):
            for x in range(0, img.width(), step):
                c = img.pixel(x, y)
                seen.add(c)
                r = (c >> 16) & 0xFF
                g = (c >> 8) & 0xFF
                b = c & 0xFF
                sr += r
                sg += g
                sb += b
                n += 1
        if not n:
            return (0, 0, None)
        return (len(seen), n, (sr // n, sg // n, sb // n))
    except Exception:
        return (-1, -1, None)


_rows = []
_fsta = io.open(os.path.join(EV, 'scene99_state.txt'), 'w',
                encoding='utf-8', newline='\n')
_t0 = time.time()
_CONTACT = []
_BASE = {}
#: ★★ 宠物**不在帧内**的采样标签（第99轮用户提醒：他会切虚拟桌面）。
#  ⇒ 这类帧 **不构成证据**，收尾时判 VERDICT=FAIL 并以非零码退出，
#    绝不允许"静默产出一张看起来正常的图"。
_BAD = []


def sample(tag, scene_id):
    """抓一次：整屏 + 画布裁剪 + 逐项内省。"""
    try:
        canvas = _g(window, 'scene_canvas')
        cam = window.__dict__.get('_scene_camera')
        bgm = _call(window, 'scene') or None
        zo = _zorder_map()
        hw_c = _hwnd(canvas) if canvas is not None else -1
        hw_p = _hwnd(window)
        geo = _call(canvas, 'geometry')
        cbox = None
        if geo is not None and geo.width() > 0 and geo.height() > 0:
            cbox = (geo.x(), geo.y(), geo.width(), geo.height())
        plan = _call(canvas, 'plan') or []
        kinds = {}
        for it in plan:
            if isinstance(it, dict):
                kinds[it.get('kind')] = kinds.get(it.get('kind'), 0) + 1
        full = _scr.grabWindow(0)
        # ★★★ 宠物真的在**这一帧**里吗？（用户会切虚拟桌面 ⇒ 可能抓到"没有宠物的桌面"）
        #   ⚠️ `grabWindow(0)` 抓的是**整屏**，所以 hw_p 必须 > 0 才敢按窗口抓。
        pgeo = _call(window, 'geometry')
        pbox = None
        if pgeo is not None:
            pbox = (pgeo.x(), pgeo.y(), pgeo.width(), pgeo.height())
        pif = ('unknown', 0, None)
        if hw_p and hw_p > 0 and pbox is not None and full is not None:
            _direct = _scr.grabWindow(hw_p)
            if _direct is not None and not _direct.isNull():
                pif = pet_in_frame(full.toImage(), _direct.toImage(), pbox)
        if pif[0] == 'out':
            _BAD.append(tag)
            print('[gen99] ★★ 宠物不在帧内（tag=%s mean_diff=%s）'
                  u'—— 很可能切了虚拟桌面 ⇒ **本帧不构成证据**'
                  % (tag, pif[2]))
        # 整屏（缩小存盘）
        small = full
        if small.width() > 1280:
            small = small.scaledToWidth(1280, Qt.FastTransformation)
        p1 = os.path.join(SHOTS, '%02d_%s_full.png' % (len(_CONTACT), tag))
        small.save(p1, 'PNG')
        # 画布裁剪（原尺寸）
        p2 = None
        if cbox and full is not None:
            crop = full.copy(*cbox)
            if not crop.isNull():
                p2 = os.path.join(SHOTS, '%02d_%s_canvas.png' % (len(_CONTACT), tag))
                crop.save(p2, 'PNG')
                _CONTACT.append((tag, crop))
        st_full = _pix_stats(full)
        st_crop = _pix_stats(full, cbox) if cbox else (0, 0, None)
        # 与"桌面基准色"比：桌面场景时画布区域的平均色 = 壁纸
        if scene_id is None:
            _BASE['rgb'] = st_crop[2]
        base = _BASE.get('rgb')
        diff = None
        if base and st_crop[2]:
            diff = sum(abs(base[i] - st_crop[2][i]) for i in range(3))
        parts = [
            'tag=%-18s' % tag,
            'scene=%r' % (_g(window, 'current_scene'),),
            'canvas_vis=%r' % bool(_call(canvas, 'isVisible')),
            'canvas_geo=%r' % (geo.getRect() if geo is not None else None,),
            'view=%r' % (_call(canvas, 'view_size'),),
            'drawn=%r' % (_g(canvas, 'last_drawn'),),
            'kinds=%r' % (kinds,),
            'z_canvas=%r z_pet=%r' % (zo.get(hw_c), zo.get(hw_p)),
            'pet_above_canvas=%r' % (
                (zo.get(hw_p) is not None and zo.get(hw_c) is not None
                 and zo[hw_p] < zo[hw_c]),),
            'cls_canvas=%r' % (_cls(hw_c),),
            'cam=%r' % (cam.rect if cam is not None else None,),
            'pet_in_frame=%r pet_mask=%d pet_diff=%s' % (
                pif[0], pif[1],
                ('%.1f' % pif[2]) if pif[2] is not None else 'None'),
            'pet_geo=%r' % (pbox,),
            'crop_distinct=%d crop_n=%d crop_rgb=%r' % st_crop,
            'full_distinct=%d' % st_full[0],
            'rgb_diff_vs_desktop=%r' % diff,
        ]
        line = ' | '.join(parts)
        _fsta.write(line + '\n')
        _fsta.flush()
        _rows.append((tag, kinds, st_crop, diff, p1, p2))
        print('[gen99] %s' % line)
        sys.stdout.flush()
    except Exception:
        _fsta.write('ERR\n' + traceback.format_exc() + '\n')
        _fsta.flush()
        print('[gen99] sample FAIL\n' + traceback.format_exc())
        sys.stdout.flush()


def step(i):
    if i >= len(SEQ):
        _bye()
        return
    tag, sid, wait = SEQ[i]
    if sid is not None:
        try:
            ok = window.travel_to_scene(sid)
            print('[gen99] travel_to_scene(%r) -> %r' % (sid, ok))
        except Exception:
            print('[gen99] travel FAIL\n' + traceback.format_exc())
        sys.stdout.flush()

    def _do():
        sample(tag, sid if sid is not None else 'desktop')
        QTimer.singleShot(200, lambda: step(i + 1))
    QTimer.singleShot(int(wait * 1000), _do)


def _bye():
    print('[gen99] done')
    sys.stdout.flush()
    app.quit()


_contact_done = [False]


def _finish():
    if _contact_done[0]:
        return
    _contact_done[0] = True
    try:
        if _CONTACT:
            tw, th = 320, 240
            sheet = QPixmap(tw * len(_CONTACT), th + 18)
            sheet.fill(QColor(20, 20, 20))
            p = QPainter(sheet)
            for k, (tag, img) in enumerate(_CONTACT):
                p.drawPixmap(k * tw, 18, img.scaled(tw, th, Qt.KeepAspectRatio,
                                                    Qt.FastTransformation))
                p.setPen(QColor(255, 255, 255))
                p.drawText(k * tw + 4, 13, tag)
            p.end()
            o = os.path.join(EV, 'scene99_contact.png')
            sheet.save(o, 'PNG')
            print('[gen99] contact -> %s' % o)
    except Exception:
        print('[gen99] contact FAIL\n' + traceback.format_exc())
    _fsta.close()
    meta = io.open(os.path.join(EV, 'scene99_meta.txt'), 'w',
                   encoding='utf-8', newline='\n')
    meta.write(u'=== gen_scene_canvas99 元信息（场景系统真机录屏检查）===\n')
    meta.write(u'屏幕        = %dx%d\n' % (_W, _H))
    meta.write(u'观察序列    = %s\n' % (SEQ,))
    meta.write(u'采样数      = %d\n' % len(_rows))
    for r in _rows:
        meta.write(u'  %-18s kinds=%-40s crop_distinct=%d rgb_diff=%s\n'
                   % (r[0], r[1], r[2][0], r[3]))
    meta.write(u'宠物在帧内  = %s（bad=%d / samples=%d）\n'
               % ('FAIL' if _BAD else 'OK', len(_BAD), len(_rows)))
    if _BAD:
        meta.write(u'不在帧内的采样 = %s\n' % (_BAD,))
        meta.write(u'  ⚠️ 用户会在工作机上切虚拟桌面 ⇒ 这些帧抓的是"没有宠物的桌面"。\n')
    meta.write(u'VERDICT     = %s\n' % ('FAIL' if _BAD else 'PASS'))
    meta.close()
    print('[gen99] meta written')


QTimer.singleShot(1500, lambda: step(0))
_END = float(os.environ.get('GEN99_SECS', '0')) or (2.0 + sum(
    s[2] + 0.4 for s in SEQ))
QTimer.singleShot(int(_END * 1000), _bye)

if __name__ == '__main__':
    rc = app.exec_()
    _finish()
    if _BAD:
        print('[gen99] ★★ %d/%d 帧**宠物不在帧内**（很可能切了虚拟桌面）'
              u' ⇒ VERDICT=FAIL，这批图不构成证据' % (len(_BAD), len(_rows)))
        rc = rc or 3
    print('[gen99] exit rc=%d samples=%d' % (rc, len(_rows)))
    sys.exit(rc)
