import ctypes
try:
    from logger_utils import get_logger
    _log = get_logger(__name__)
except ImportError:  # 模块外独立导入时的降级
    import logging
    _log = logging.getLogger(__name__)

import time
import win32gui
from PyQt5.QtCore import QRect, QPoint

SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SWP_NOOWNERZORDER = 0x0200

HWND_TOP = 0
HWND_BOTTOM = 1
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2

_user32 = ctypes.windll.user32
_user32.SendMessageTimeoutW.restype = ctypes.c_void_p
_user32.SendMessageTimeoutW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint, ctypes.POINTER(ctypes.c_void_p)]


class FloorManager:
    def __init__(self, parent=None):
        self.parent = parent
        self.floors = []
        self.underlying_windows = []
        self.desktop_floor = {
            'type': 'desktop',
            'rect': QRect(0, 0, 0, 0),
            'z_order': 0,
            'platform_height': 0
        }
        self._workerw_hwnd = None
        self._workerw_find_time = 0

    def update_floors(self):
        # 始终更新桌面层的屏幕尺寸（窗口列表更新失败时也能保底）
        try:
            import win32api
            # 使用虚拟屏幕 API 获取多屏总区域（主屏+副屏）
            # SM_XVIRTUALSCREEN=76, SM_YVIRTUALSCREEN=77,
            # SM_CXVIRTUALSCREEN=78, SM_CYVIRTUALSCREEN=79
            vx = win32api.GetSystemMetrics(76)
            vy = win32api.GetSystemMetrics(77)
            vw = win32api.GetSystemMetrics(78)
            vh = win32api.GetSystemMetrics(79)
            self.desktop_floor['rect'] = QRect(vx, vy, vw, vh)
        except Exception:
            # fallback: 用 Qt 的多屏几何
            try:
                from PyQt5.QtWidgets import QApplication
                import functools
                app = QApplication.instance()
                if app:
                    union = None
                    for screen in app.screens():
                        sg = screen.geometry()
                        union = sg if union is None else union.united(sg)
                    if union:
                        self.desktop_floor['rect'] = union
            except Exception as e:
                _log.debug("floor_manager 防御性异常（已忽略）: %s", e)
        self._update_underlying_windows()
        self._generate_floors()

    def _update_underlying_windows(self):
        if not self.parent or not hasattr(self.parent, 'desktop_interaction'):
            return
        try:
            raw_windows = self.parent.desktop_interaction.get_all_visible_windows()
        except Exception:
            return
        visible_windows = []
        for w in raw_windows:
            rect = w['rect']
            width = rect[2] - rect[0]
            height = rect[3] - rect[1]
            class_name = ''
            try:
                class_name = win32gui.GetClassName(w['hwnd'])
            except Exception as e:
                _log.debug("floor_manager 防御性异常（已忽略）: %s", e)
            visible_windows.append({
                'hwnd': w['hwnd'],
                'title': w['title'],
                'class_name': class_name,
                'rect': QRect(rect[0], rect[1], width, height),
                'z_order': w.get('z_order', 0),
            })
        visible_windows.sort(key=lambda x: x['z_order'])
        self.underlying_windows = visible_windows

    def _generate_floors(self):
        self.floors = []

        for i, window in enumerate(self.underlying_windows):
            is_covered = False
            for j in range(i):
                if self.underlying_windows[j]['rect'].contains(window['rect']):
                    is_covered = True
                    break

            if not is_covered:
                platform_height = (len(self.underlying_windows) - i) * 5

                floor = {
                    'type': 'window',
                    'window': window,
                    'rect': window['rect'],
                    'z_order': window['z_order'],
                    'platform_height': platform_height,
                    'window_hwnd': window['hwnd']
                }
                self.floors.append(floor)

        self.floors.sort(key=lambda x: x['platform_height'])

    # ------------------------------------------------------------------
    # Z-order helpers (Mineradio-inspired: SetWindowPos with insertAfter)
    # ------------------------------------------------------------------

    @staticmethod
    def find_desktop_workerw_hwnd():
        """Find the WorkerW window that sits behind desktop icons.
        Pet placed after WorkerW will appear on top of desktop but below
        all normal windows — perfect for the "desktop floor" z-order."""
        try:
            progman = win32gui.FindWindow("Progman", "Program Manager")
            if progman:
                # Mineradio trick: send 0x052C to Progman to force-create WorkerW
                _user32.SendMessageTimeoutW(
                    ctypes.c_void_p(progman), 0x052C,
                    ctypes.c_void_p(0), ctypes.c_void_p(0),
                    0, 1000, None
                )
        except Exception as e:
            _log.debug("floor_manager 防御性异常（已忽略）: %s", e)

        workerw = 0

        def callback(hwnd, _):
            nonlocal workerw
            if win32gui.IsWindowVisible(hwnd):
                shell = win32gui.FindWindowEx(hwnd, 0, "SHELLDLL_DefView", None)
                if shell:
                    candidate = win32gui.FindWindowEx(0, hwnd, "WorkerW", None)
                    if candidate:
                        workerw = candidate
            return True

        try:
            win32gui.EnumWindows(callback, None)
        except Exception as e:
            _log.debug("floor_manager 防御性异常（已忽略）: %s", e)

        if not workerw:
            try:
                workerw = win32gui.FindWindowEx(0, 0, "WorkerW", None)
            except Exception as e:
                _log.debug("floor_manager 防御性异常（已忽略）: %s", e)

        return workerw

    def get_insert_after_hwnd(self, floor):
        """Return the HWND that Ralsei should be placed directly ABOVE.
        - desktop floor → WorkerW (pet on top of desktop, below all apps)
        - window floor → that window's HWND (pet on top of this window,
          but naturally hidden by any window higher in z-order)"""
        if floor is None or floor.get('type') == 'desktop':
            now = time.time()
            if (self._workerw_hwnd is None
                    or not win32gui.IsWindow(self._workerw_hwnd)
                    or now - self._workerw_find_time > 300):
                self._workerw_hwnd = self.find_desktop_workerw_hwnd()
                self._workerw_find_time = now
            return self._workerw_hwnd or HWND_BOTTOM
        return floor.get('window_hwnd', HWND_BOTTOM)

    @staticmethod
    def set_window_behind(hwnd_target, hwnd_after):
        """Use SetWindowPos to place hwnd_target directly above hwnd_after
        in Z order. Flags: SWP_NOMOVE|SWP_NOSIZE|SWP_NOACTIVATE|SWP_NOOWNERZORDER
        so we only touch the z-order, nothing else. Uses win32gui which
        handles 64-bit HWNDs correctly."""
        if not hwnd_target or not win32gui.IsWindow(hwnd_target):
            return False
        flags = SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_NOOWNERZORDER
        insert = hwnd_after if hwnd_after else HWND_BOTTOM
        try:
            win32gui.SetWindowPos(hwnd_target, insert, 0, 0, 0, 0, flags)
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Floor queries
    # ------------------------------------------------------------------

    def get_current_floor(self, pos):
        all_floors = sorted(self.floors + [self.desktop_floor], key=lambda x: x['platform_height'], reverse=True)

        for floor in all_floors:
            if floor['rect'].contains(pos):
                return floor

        return self.desktop_floor

    def get_floors_above(self, current_floor):
        above_floors = []
        for floor in self.floors:
            if floor['platform_height'] > current_floor['platform_height']:
                above_floors.append(floor)
        return above_floors

    def get_drop_destination(self, pos, current_floor):
        all_floors = sorted(self.floors + [self.desktop_floor], key=lambda x: x['platform_height'], reverse=True)

        current_index = -1
        for i, floor in enumerate(all_floors):
            if floor == current_floor:
                current_index = i
                break

        for i in range(current_index + 1, len(all_floors)):
            floor = all_floors[i]
            if floor['rect'].contains(pos):
                return floor, pos

        return self.desktop_floor, pos

    def get_jump_destinations(self, current_floor, current_pos):
        jump_destinations = []

        jump_destinations.append((current_floor, current_pos))

        above_floors = sorted(self.get_floors_above(current_floor),
                             key=lambda x: x['platform_height'])

        for floor in above_floors:
            rect = floor['rect']

            is_visible = True
            for higher_floor in above_floors:
                if higher_floor['platform_height'] > floor['platform_height']:
                    if higher_floor['rect'].contains(rect):
                        is_visible = False
                        break

            if is_visible and (current_pos.x() >= rect.left() and
                current_pos.x() <= rect.right() and
                current_pos.y() >= rect.bottom()):
                jump_pos = QPoint(current_pos.x(), rect.top() + 10)
                jump_destinations.append((floor, jump_pos))

        all_floors = sorted(self.floors + [self.desktop_floor],
                          key=lambda x: x['platform_height'], reverse=True)

        current_index = -1
        for i, floor in enumerate(all_floors):
            if floor == current_floor:
                current_index = i
                break

        if current_index + 1 < len(all_floors):
            next_floor = all_floors[current_index + 1]
            if (current_pos.x() >= next_floor['rect'].left() and
                current_pos.x() <= next_floor['rect'].right()):
                jump_pos = QPoint(current_pos.x(), next_floor['rect'].top() + 10)
                jump_destinations.append((next_floor, jump_pos))

        return jump_destinations

    def is_floor_valid(self, floor):
        if floor['type'] == 'desktop':
            return True

        for window in self.underlying_windows:
            if window['hwnd'] == floor['window_hwnd']:
                if (window['rect'].left() == floor['rect'].left() and
                    window['rect'].top() == floor['rect'].top() and
                    window['rect'].width() == floor['rect'].width() and
                    window['rect'].height() == floor['rect'].height()):
                    return True
        return False

    def get_all_floors(self):
        return self.floors + [self.desktop_floor]

    def get_floor_by_window(self, window_hwnd):
        for floor in self.floors:
            if floor['type'] == 'window' and floor['window']['hwnd'] == window_hwnd:
                return floor
        return None

    # ------------------------------------------------------------------
    # Boundary: detect when pet walks off a floor edge
    # ------------------------------------------------------------------

    @staticmethod
    def is_on_floor_edge(pos, floor, margin=6):
        """Return True if pos is within `margin` pixels of the floor's
        outer edge AND outside the floor rect itself (pet walked off)."""
        rect = floor['rect']
        if rect.contains(pos):
            return False
        expanded = rect.adjusted(-margin, -margin, margin, margin)
        return expanded.contains(pos)

    def find_support_below(self, pos, z_below=None):
        """Find the nearest floor below pos that actually contains pos.
        Used when pet walks off an edge — gravity drops to next solid floor."""
        all_floors = sorted(self.floors + [self.desktop_floor],
                            key=lambda x: x['platform_height'], reverse=True)
        if z_below is not None:
            all_floors = [f for f in all_floors if f['platform_height'] <= z_below]
        for floor in all_floors:
            if floor['rect'].contains(pos):
                return floor
        return self.desktop_floor
