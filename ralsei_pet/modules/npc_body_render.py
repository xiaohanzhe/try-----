# -*- coding: utf-8 -*-
"""NPC 本体渲染层（第191轮）—— 让在场的人**真的看得见**。

为什么是「每人一个小窗口」而不是「一张全屏透明画布」
--------------------------------------------------
遮挡契约（第164轮用户裁定 `BBA` / 第178轮落地）是**按屏幕 Y 排序**：
脚底更靠下的人在前。一张全屏画布只有**一个** z 序，要么全体压在所有窗口之上、
要么全在之下 —— 两种都不对。桌宠自己就是「一个窗口 + 按脚底 Y 插进 z 序」
（`main._apply_pet_z_order` → `floor_manager.pick_insert_after_by_foot_y`），
所以 NPC 用**同一条路径**才叫一视同仁：每个人都是一个小窗，各插各的。

本模块只做三件事
----------------
1. `NpcFrameBook` —— 读 `assets/sprites/dr/_npc_frames.json`，把
   `(npc_id, 朝向, 帧号)` 解成 `QPixmap`。**运行时零文件名猜解**：
   素材库有三种命名写法（`spr_x_walk_down_dw_3` / `spr_x_dt_0` / `dalv_down_0`），
   猜解一定会有猜错的那天，而猜错不报错、只画错人。
2. `BodyWindow` —— 一个透明、无边框、不抢焦点、鼠标穿透的小窗（只画一帧）。
3. `NpcBodyLayer` —— 窗口池 + 每帧同步。

刻意的取舍（写在这里，免得以后被当成 bug）
------------------------------------------
· **无立绘就不画**。用户口径「参考原作」⇒ 不编一个假人出来。缺谁由
  `manifest['no_art']` 如实登记。
· **站立的角色不播走路**（`mode=stand` 的人在原作里就是不动）。走路帧只在
  调用方标了 `moving=True` 时才轮播。
· 层不认识相机、不认识场景：`sync()` 收到的是**已算好的屏幕坐标**，
  与 `SceneCanvas.set_plan` 同一条纪律（谁算坐标谁负责验证）。
"""
import json
import logging
import os


def _pet_logger_name(_name):
    """把模块 `__name__` 映射到 `ralsei_pet.` 命名空间（与 floor_manager 同款）。

    ★ 不 import `logger_utils`：模块外独立导入时会 ImportError ⇒ 静默降级成裸
      logger ⇒ INFO 全丢（第75轮踩过）。`logging` 是进程级注册表，拼对名字即可。
    """
    if not _name or _name == '__main__':
        return 'ralsei_pet.main'
    if _name.startswith('ralsei_pet.'):
        return _name
    if _name.startswith('modules.'):
        return 'ralsei_pet.' + _name
    return 'ralsei_pet.' + _name


import ctypes
import time

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QLabel

try:
    from logger_utils import get_logger
    _log = logging.getLogger(_pet_logger_name(__name__))
except ImportError:  # 模块外独立导入时的降级
    _log = logging.getLogger(_pet_logger_name(__name__))

MANIFEST_NAME = '_npc_frames.json'

#: 走路帧间隔（毫秒）。原作 30fps、overworld 走路 4 帧一循环 ⇒ 一圈 120ms 最接近
#: 「一步一顿」的观感；再快会糊成人形风扇，再慢像卡带。
FRAME_MS = 120

#: 同屏最多几个本体窗口。★ 为什么要有上限：房间里可能站 14 个人，每个窗口都要
#: 一次 `SetWindowPos`，DWM 合成成本随窗口数上升；超过上限时按**离相机最近**
#: 截断（远的人本来就被裁在画面外，看不见）。
MAX_BODIES = 24

#: 缺方向时的回落顺序。★ 不写 `left/right` 互转：左右脸不一样，转了就是另一个人。
DIR_FALLBACK = ('down', 'up', 'left', 'right')

#: 走路帧上限（清单里每方向最多存这么多，见 `pick191.MAX_FRAMES_PER_DIR`）
_MAX_FRAMES = 8


def _project_root():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


def manifest_path(root=None):
    """清单路径。`root` 缺省 = `ralsei_pet/`（本模块在 `modules/` 下）。"""
    base = root or _project_root()
    return os.path.join(base, 'assets', 'sprites', 'dr', MANIFEST_NAME)


def load_manifest(root=None):
    """读清单。**任何失败都返回 `{}`**（渲染层不是关键路径，绝不拖垮主循环）。

    ★ 不缓存到这个函数外：清单是**构建期产物**，进程内不会变；
      真要重读用 `NpcFrameBook.reload()`。
    """
    path = manifest_path(root)
    try:
        import io
        with io.open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        _log.warning('NPC 立绘清单读不出（本轮 NPC 不显示）：%s', e)
        return {}
    if not isinstance(data, dict) or not isinstance(data.get('characters'), dict):
        _log.warning('NPC 立绘清单格式不对（缺 characters）：%s', path)
        return {}
    return data


class NpcFrameBook(object):
    """`(npc_id, 朝向, 帧号)` → `QPixmap`。清单驱动，零猜解。"""

    def __init__(self, root=None, manifest=None):
        self._root = root
        self._manifest = manifest if manifest is not None else load_manifest(root)
        self._dir = os.path.join(root or _project_root(),
                                 'assets', 'sprites', 'dr')
        self._pm_cache = {}          # (npc_id, dir, idx) -> QPixmap（原始尺寸）
        self._scaled_cache = {}      # (npc_id, dir, idx, 千分比) -> QPixmap
        self._missing_warned = set()

    # -- 查询
    def reload(self, manifest=None):
        self._manifest = manifest if manifest is not None else load_manifest(self._root)
        self._pm_cache.clear()
        self._scaled_cache.clear()
        return self

    def ids(self):
        return sorted((self._manifest.get('characters') or {}).keys())

    def has_art(self, npc_id):
        e = (self._manifest.get('characters') or {}).get(npc_id)
        return bool(e and e.get('frames'))

    def no_art(self):
        """清单里被如实登记为"没有立绘"的人（供自省/报告用）。"""
        v = self._manifest.get('no_art')
        return list(v) if isinstance(v, (list, tuple)) else []

    def dirs(self, npc_id):
        e = (self._manifest.get('characters') or {}).get(npc_id) or {}
        return sorted((e.get('frames') or {}).keys())

    def dir_of(self, npc_id, facing):
        """实际用哪个方向的帧：有该方向就用，没有就按 `DIR_FALLBACK` 回落。

        ★ 返回 `None` 表示"这个人没有立绘"，调用方据此**不画**（不是画空窗）。
        """
        have = self.dirs(npc_id)
        if not have:
            return None
        f = facing if facing in have else None
        if f is not None:
            return f
        for d in DIR_FALLBACK:
            if d in have:
                return d
        return have[0]

    def frame_count(self, npc_id, facing):
        e = (self._manifest.get('characters') or {}).get(npc_id) or {}
        d = self.dir_of(npc_id, facing)
        if d is None:
            return 0
        rows = (e.get('frames') or {}).get(d) or []
        return min(len(rows), _MAX_FRAMES)

    def frame_name(self, npc_id, facing, index):
        e = (self._manifest.get('characters') or {}).get(npc_id) or {}
        d = self.dir_of(npc_id, facing)
        if d is None:
            return None
        rows = (e.get('frames') or {}).get(d) or []
        if not rows:
            return None
        return rows[int(index) % len(rows)].get('f')

    # -- 取图
    def frame(self, npc_id, facing, index=0):
        """原始尺寸的 `QPixmap`；缺图 ⇒ `None`（**不造假帧**）。"""
        name = self.frame_name(npc_id, facing, index)
        if not name:
            return None
        key = (npc_id, name)
        pm = self._pm_cache.get(key)
        if pm is not None:
            return pm
        path = os.path.join(self._dir, npc_id, name)
        pm = QPixmap(path)
        if pm.isNull():
            if key not in self._missing_warned:
                self._missing_warned.add(key)
                _log.warning('NPC 帧文件读不出（清单与磁盘不一致）：%s', path)
            return None
        self._pm_cache[key] = pm
        return pm

    def scaled(self, npc_id, facing, index, scale):
        """按 `scale` 缩放后的帧（带缓存）。`scale` 按**千分比**取整做键 ——

        ★ 为什么用千分比而不是 float 原值：相机每帧算出来的 `scale` 带浮点噪声
          （6.666666…），拿原值当键会让缓存**永不命中**，30fps × 24 人 × 每帧
          `scaled()` 足够把主线程拖垮。
        """
        pm = self.frame(npc_id, facing, index)
        if pm is None:
            return None
        try:
            s = float(scale)
        except (TypeError, ValueError):
            s = 1.0
        if s <= 0:
            s = 1.0
        k = int(round(s * 1000))
        name = self.frame_name(npc_id, facing, index)
        ck = (npc_id, name, k)
        out = self._scaled_cache.get(ck)
        if out is not None:
            return out
        w = max(1, int(round(pm.width() * s)))
        h = max(1, int(round(pm.height() * s)))
        out = pm.scaled(w, h, Qt.KeepAspectRatio, Qt.FastTransformation)
        # 上限：24 人 × 4 向 × 4 帧 ≈ 384，留一倍余量
        if len(self._scaled_cache) > 800:
            self._scaled_cache.clear()
        self._scaled_cache[ck] = out
        return out


#: Win32 扩展样式（鼠标穿透 + 不抢焦点 + 工具窗不进 Alt-Tab）
_GWL_EXSTYLE = -20
_WS_EX_TRANSPARENT = 0x00000020
_WS_EX_NOACTIVATE = 0x08000000
_WS_EX_TOOLWINDOW = 0x00000080


class BodyWindow(QLabel):
    """一个 NPC 的本体小窗：只画一帧，透明、无边框、不抢焦点、鼠标穿透。

    ★ 为什么是 `Qt.Tool` 而不是普通顶层窗：`Tool` 不进任务栏、不参与 Alt-Tab，
      切换应用时不会把一排小人带到前台。
    ★ 为什么**不**加 `WindowStaysOnTopHint`：那会让 NPC 永远压在所有窗口之上，
      遮挡关系彻底失效 —— 与第167轮 `_apply_pet_z_order` 里踩过的坑同一个。
    """

    def __init__(self, parent=None):
        super(BodyWindow, self).__init__(parent)
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint
                            | Qt.WindowDoesNotAcceptFocus
                            | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        # ★ 关掉系统背景：否则透明区在某些驱动上会画成黑块
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.setScaledContents(False)
        self._clickthrough_done = False
        self._foot = None

    # -- 外观
    def set_frame(self, pm):
        """换一帧并**把窗口调整到该帧的尺寸**（不做任何居中/留白）。"""
        if pm is None or pm.isNull():
            return False
        if self.pixmap() is None or self.pixmap().size() != pm.size():
            self.setFixedSize(pm.size())
        self.setPixmap(pm)
        return True

    def place_foot(self, foot_x, foot_y):
        """把**脚底中心**放到屏幕点 `(foot_x, foot_y)`。

        ★ 为什么锚脚底而不是中心：遮挡按 Y 排序的锚点就是脚底
          （`floor_manager.pick_insert_after_by_foot_y`），窗口 bottom == 脚底
          才能让"站得靠下的人在前面"和窗口 z 序给出同一个答案。
        """
        w = self.width()
        h = self.height()
        self.move(int(round(foot_x - w / 2.0)), int(round(foot_y - h)))
        self._foot = (float(foot_x), float(foot_y))

    def foot(self):
        return self._foot

    # -- 上屏
    def show_passive(self):
        if not self.isVisible():
            self.show()
        self._make_clickthrough()
        # ★ 透明顶层窗 move/resize 后必须显式重绘：Windows 合成依赖 backing store，
        #   `move()` 不会触发全窗重绘 ⇒ 屏幕上还是上一帧/空（第89轮 `grab()` 能看见、
        #   屏幕看不见的那个坑）。
        self.repaint()

    def _make_clickthrough(self):
        """补 Win32 扩展样式（Qt 的 `WA_TransparentForMouseEvents` 只管 Qt 内部）。

        ★ 必须让点击**落到下面的窗口**：NPC 的交互走"E 键 + 射线"
          （`main._npc_interact_pick`），不靠点身体。若这里不穿透，站在图标上的人
          会把桌面点击吃掉。
        """
        if self._clickthrough_done:
            return True
        try:
            hwnd = int(self.winId())
            if not hwnd:
                return False
            user32 = ctypes.windll.user32
            ex = user32.GetWindowLongW(hwnd, _GWL_EXSTYLE)
            user32.SetWindowLongW(hwnd, _GWL_EXSTYLE,
                                  ex | _WS_EX_TRANSPARENT | _WS_EX_NOACTIVATE
                                  | _WS_EX_TOOLWINDOW)
            self._clickthrough_done = True
            return True
        except Exception as e:
            _log.debug('NPC 窗口鼠标穿透设置失败（不影响显示）: %s', e)
            return False


class NpcBodyLayer(object):
    """窗口池 + 每帧同步。**不认识相机/场景**，只吃算好的屏幕坐标。"""

    def __init__(self, book=None, host=None):
        self.book = book or NpcFrameBook()
        self.host = host
        self._wins = {}                 # npc_id -> BodyWindow
        self._z_last = {}               # npc_id -> (foot_y, wall_time)
        self._visible = set()

    # -- 自省
    def count_windows(self):
        return len(self._wins)

    def visible_ids(self):
        return sorted(self._visible)

    def window_of(self, npc_id):
        return self._wins.get(npc_id)

    def visible_windows(self):
        """`[(npc_id, hwnd, foot_y)]`，按**脚底 Y 升序**（= 从后到前）。

        ★ 给"成组置顶"用（`main._scene_topmost_targets`）：置顶带内的前后关系
          没法靠"插入到某人之后"表达，只能**按顺序依次提升** ⇒ 谁先设谁在下面。
          排序口径与桌面模式**同一条**（脚底 Y），否则全屏和窗口两种模式下
          前后关系会给出两个答案。
        """
        out = []
        for nid in self._visible:
            win = self._wins.get(nid)
            if win is None:
                continue
            try:
                if not win.isVisible():
                    continue
                hwnd = int(win.winId())
            except Exception:
                continue
            if not hwnd:
                continue
            foot = win.foot() or (0.0, 0.0)
            out.append((nid, hwnd, float(foot[1])))
        out.sort(key=lambda t: (t[2], t[0]))
        return out

    # -- 主循环
    def sync(self, items, scale=1.0, now_ms=None, zorder=None,
             z_throttle_s=0.5, z_eps_px=2.0, anchor='foot'):
        """按 `items` 更新所有本体窗。

        :param items: `[{'id','x','y','facing','moving'}]`。`x/y` 的含义由 `anchor`
                      决定（见下），**顺序无所谓**（按 id 建池）。
        :param scale: 每逻辑像素多少屏幕像素（与场景物件同一把尺）。
        :param now_ms: 墙钟毫秒（决定走路帧号）；`None` ⇒ 用 `time.time()`。
        :param zorder: `callable(hwnd, foot_y)`，由宿主注入
                       （`main` 传 `floor_manager` 那条路径）。`None` ⇒ 不动 z 序。
        :param anchor: `'foot'` ⇒ `x/y` 就是脚底中心；
                       `'center'` ⇒ `x/y` 是身体中心（= 全项目对 `Body.x/y` 的既有
                       口径，见 `main._npc_interact_candidates`），本函数**自己**加
                       `半高` 换成脚底。
                       ★ 半高只有这里知道（要先取到帧），所以换算**只在这里做一次**；
                         让调用方也减一遍就是"同一件事两处算"。
        :return: 实际显示的条数。
        """
        if now_ms is None:
            now_ms = int(time.time() * 1000)
        # ---- 上限：超出按调用方给的顺序截断（调用方已按"离相机最近"排过）----
        want = []
        seen = set()
        for it in (items or []):
            nid = it.get('id')
            if not nid or nid in seen:
                continue
            if not self.book.has_art(nid):
                # 无立绘 ⇒ **不画**（不造假人）；如实留痕但不刷屏
                continue
            seen.add(nid)
            want.append(it)
            if len(want) >= MAX_BODIES:
                break

        now_s = time.time()
        shown = 0
        for it in want:
            nid = it['id']
            facing = it.get('facing') or 'down'
            moving = bool(it.get('moving'))
            n = self.book.frame_count(nid, facing)
            if n <= 0:
                continue
            idx = 0
            if moving and n > 1:
                idx = int(now_ms // FRAME_MS) % n
            pm = self.book.scaled(nid, facing, idx, scale)
            if pm is None:
                continue
            win = self._wins.get(nid)
            if win is None:
                win = BodyWindow()
                self._wins[nid] = win
            if not win.set_frame(pm):
                continue
            # ---- 中心/脚底换算（**只此一处**）----
            foot_x = float(it.get('x', 0.0))
            foot_y = float(it.get('y', 0.0))
            if anchor == 'center':
                foot_y += win.height() / 2.0
            win.place_foot(foot_x, foot_y)
            win.show_passive()
            shown += 1
            # ---- z 序：**节流**（脚底没动就不重排）----
            if zorder is not None:
                prev = self._z_last.get(nid)
                if (prev is None
                        or abs(prev[0] - foot_y) >= z_eps_px
                        or (now_s - prev[1]) >= z_throttle_s):
                    try:
                        zorder(int(win.winId()), foot_y)
                        self._z_last[nid] = (foot_y, now_s)
                    except Exception as e:
                        _log.debug('NPC z 序设置失败（本帧跳过）: %s', e)

        # ---- 不在列表里的：隐藏（不销毁，留着下次复用）----
        for nid, win in self._wins.items():
            if nid not in seen:
                try:
                    if win.isVisible():
                        win.hide()
                except Exception:
                    pass
                self._z_last.pop(nid, None)
        self._visible = set(w['id'] for w in want)
        return shown

    def hide_all(self):
        for win in self._wins.values():
            try:
                win.hide()
            except Exception:
                pass
        self._visible = set()

    def destroy_all(self):
        for win in self._wins.values():
            try:
                win.hide()
                win.deleteLater()
            except Exception:
                pass
        self._wins.clear()
        self._visible = set()
        self._z_last.clear()
