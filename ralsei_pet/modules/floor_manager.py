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

# GetWindow 的 z 序步进方向（win32con.GW_HWNDNEXT 的值；本模块不引入 win32con）
GW_HWNDNEXT = 2

_user32 = ctypes.windll.user32
_user32.SendMessageTimeoutW.restype = ctypes.c_void_p
_user32.SendMessageTimeoutW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint, ctypes.POINTER(ctypes.c_void_p)]

# --------------------------------------------------------------------- 建楼：遮挡与分层
# 「建楼」要求原文：
#   · 楼层关系："哪个窗口在最前面，哪个就是最高楼层。后面的窗口如果被前面的**完全盖住**，
#     那就相当于被压在下面了，暂时'不存在'。"
#   · 视野限制："ralsei 眼里只有两种东西：它正站着的这块楼板，以及比当前这块楼板更高的、
#     **没有被完全挡住**的'悬崖边'。它看不到脚下楼板下面的东西。"
#   · 不透明原则："窗口就是实心地板，绝不允许穿透、看穿。"
#
# 于是楼层的判定口径必须从"窗口矩形"升级为"**可见区域**"：
#   可见区域 = 自身矩形 − 所有比它更高的窗口矩形之并
# 第十四轮之前只判 `higher.rect.contains(me.rect)`（**完全包含**才算被盖住），
# 于是"被挡住 90% 的窗口"仍然算一块完整楼板 —— 宠物会站在那块根本看不见的地板上。
#
# 阈值：可见面积低于这个值就不算楼层（"被压下去，暂时不存在"）。
# 取 40×40 ≈ 宠物脚下能站稳的一小块；比它更细的缝站不住，也没法让用户看见宠物站在哪。
MIN_FLOOR_VISIBLE_AREA = 40 * 40

# 桌面层的固定标识（与 _floor_identity 保持一致）
DESKTOP_IDENTITY = 'desktop'


def _rect_tuple(rect):
    """QRect → 半开区间元组 (left, top, right, bottom)。

    半开区间（right/bottom 不含）能让"相减"的边界算术保持整数且不重叠，
    避免 QRect.right() = x + w - 1 这种左右闭区间带来的差一错误。
    """
    return (rect.left(), rect.top(), rect.left() + rect.width(),
            rect.top() + rect.height())


def _qr(t):
    """半开区间元组 → QRect。"""
    l, t0, r, b = t
    return QRect(l, t0, max(0, r - l), max(0, b - t0))


def _area(t):
    l, t0, r, b = t
    return max(0, r - l) * max(0, b - t0)


def _cut(rect, hole):
    """从 rect 里挖掉 hole，返回 ≤4 个**互不重叠**的矩形（可能为空）。"""
    l, t, r, b = rect
    hl, ht, hr, hb = hole
    if hr <= l or hl >= r or hb <= t or ht >= b:
        return [rect]                     # 不相交，原样返回
    if hl <= l and hr >= r and ht <= t and hb >= b:
        return []                         # 全被挖掉
    out = []
    if ht > t:                            # 上横条
        out.append((l, t, r, ht))
    if hb < b:                            # 下横条
        out.append((l, hb, r, b))
    mid_t, mid_b = max(t, ht), min(b, hb)
    if hl > l and mid_b > mid_t:          # 左竖条（只占 hole 的纵向范围）
        out.append((l, mid_t, hl, mid_b))
    if hr < r and mid_b > mid_t:          # 右竖条
        out.append((hr, mid_t, r, mid_b))
    return out


def visible_subrects(target, blockers):
    """target 挖掉 blockers 之并后剩下的矩形列表。

    不变量：返回的矩形**两两不重叠**，且并集恰好 = target − ⋃blockers。
    实现说明：初始只有一个矩形，每次 `_cut` 把"一个矩形"换成"它减去洞之后的一个划分"，
    所以不重叠这一条是构造性成立的 —— 因此可见面积可以直接求和，不会重复计算。
    """
    pieces = [target]
    for hole in blockers:
        if not pieces:
            break
        nxt = []
        for p in pieces:
            nxt.extend(_cut(p, hole))
        pieces = [p for p in nxt if _area(p) > 0]
    return pieces


def _native_window_from_point(x, y):
    """Windows 原生口径：这一点上"最上面"的顶层窗口（`WindowFromPoint`）。

    惰性导入 `desktop_interaction`：它已经声明好了 argtypes/restype（64 位 HWND 不截断），
    这里复用即可，避免两处各写一份 Win32 声明。导入失败（独立跑本模块）时返回 0，
    调用方自然回落到几何判定。
    """
    try:
        from desktop_interaction import window_from_point as _wfp
        return _wfp(x, y)
    except Exception:
        return 0



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
            # 修复（性能）：get_all_visible_windows 已在枚举时取得并缓存 class_name，
            # 这里再 GetClassName 是对每个窗口的重复跨进程调用（量级翻倍），直接复用。
            class_name = w.get('class_name', '')
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
        """按"一层压一层"生成楼层表（本模块的核心）。

        口径（对照"建楼"要求）：
          1. `underlying_windows` 已按 z_order 升序 = **从最前面往最后面**；
          2. 从前往后扫，每一层挖掉"前面所有**已经成立的**楼层"所占的矩形 → 得到它的可见区域；
          3. 可见面积不足 MIN_FLOOR_VISIBLE_AREA → 被压下去了，"暂时不存在"，**不是楼层**；
             它也不再遮挡更低的窗口（符合"被压住的就暂时不存在"）；
          4. platform_height 按"有效楼层的名次"编（最前 = 最高 = 数值最大，桌面恒为 0）。

        为什么"只在成立的楼层里累加遮挡者"是对的：
          如果某窗口被压下去（不存在），它对更低的窗口就既不可见、也不该算作地板；
          从前往后一遍扫完即是正确答案，不需要迭代到不动点。
        """
        self.floors = []

        # 防御性排序：本函数的正确性依赖"从最前面往最后面"扫。
        # 调用方（_update_underlying_windows）确实会按 z_order 排好，但这是隐式约定 ——
        # 一旦有人直接赋值 underlying_windows（测试、以后的重构）就会静默算错，
        # 所以这里自己再排一次，把约定变成不变量。
        windows_in_z = sorted(self.underlying_windows,
                              key=lambda w: w.get('z_order', 0))

        valid = []                       # 已经成立的楼层（同时充当"遮挡者"）
        for window in windows_in_z:
            rect = _rect_tuple(window['rect'])
            pieces = visible_subrects(rect, [_rect_tuple(v['rect']) for v in valid])
            vis_area = sum(_area(p) for p in pieces)

            if vis_area < MIN_FLOOR_VISIBLE_AREA:
                # 被前面的窗口盖住了 → 按建楼要求"暂时不存在"
                continue

            window['visible_rects'] = [_qr(p) for p in pieces]
            window['visible_area'] = vis_area
            valid.append(window)

        n = len(valid)
        for i, window in enumerate(valid):
            self.floors.append({
                'type': 'window',
                'window': window,
                'rect': window['rect'],
                # 可见区域（可站的部分）：跳/落/站立判定都用它，不再用整个 rect
                'visible_rects': window['visible_rects'],
                'visible_area': window['visible_area'],
                'z_order': window['z_order'],
                # 最前的有效楼层最高。×5 沿用历轮的量纲（spatial_pos["z"] 消费它）
                'platform_height': (n - i) * 5,
                'window_hwnd': window['hwnd'],
            })

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
        """返回"宠物应该紧贴在谁之上"的 HWND。

        这是"一层压一层"的关键（Windows 原生 `SetWindowPos(insertAfter=...)`）：
          · 站在窗口楼板上 → 插到**那块窗口之上**，于是任何排在它前面的窗口
            都会自然盖住宠物（这就是"前面的窗口压住你"）；
          · 站在桌面上（1楼） → 插到 WorkerW 之后，即"桌面图标之上、所有应用窗口之下"。

        修复（第十三轮）：窗口句柄失效时不再直接把野句柄交给 SetWindowPos
        （窗口可能刚好在这一拍被关掉），改为回落到 WorkerW / HWND_BOTTOM。
        """
        if floor is None or floor.get('type') == 'desktop':
            return self._workerw_or_bottom()

        hwnd = floor.get('window_hwnd')
        try:
            if hwnd and win32gui.IsWindow(hwnd):
                return hwnd
        except Exception:
            pass
        return self._workerw_or_bottom()

    def _workerw_or_bottom(self):
        """桌面层的插入点：WorkerW（桌面图标之上、应用窗口之下），拿不到就 HWND_BOTTOM。"""
        now = time.time()
        try:
            if (self._workerw_hwnd is None
                    or not win32gui.IsWindow(self._workerw_hwnd)
                    or now - self._workerw_find_time > 300):
                self._workerw_hwnd = self.find_desktop_workerw_hwnd()
                self._workerw_find_time = now
        except Exception as e:
            _log.debug("floor_manager 防御性异常（已忽略）: %s", e)
        return self._workerw_hwnd or HWND_BOTTOM

    @staticmethod
    def z_order_index(hwnd):
        """hwnd 在顶层窗口 z 序里的下标（0 = 最前）；不在链上返回 None。

        用的是 Windows 原生的 z 序链（`GetTopWindow` + `GW_HWNDNEXT`）——
        与 `desktop_interaction.get_all_visible_windows` 里算 z_order 是同一套口径。
        用途：核验"宠物确实被插在了所站楼板之上、其余窗口之下"（真机与回归都用它）。
        """
        if not hwnd:
            return None
        try:
            cur = win32gui.GetTopWindow(None)
            i = 0
            while cur:
                if cur == hwnd:
                    return i
                cur = win32gui.GetWindow(cur, GW_HWNDNEXT)
                i += 1
        except Exception:
            return None
        return None

    @classmethod
    def is_above(cls, hwnd_a, hwnd_b):
        """z 序上 hwnd_a 是否在 hwnd_b **前面**（更靠上）。任一句柄不在链上返回 None。"""
        ia = cls.z_order_index(hwnd_a)
        ib = cls.z_order_index(hwnd_b)
        if ia is None or ib is None:
            return None
        return ia < ib


    @staticmethod
    def set_window_behind(hwnd_target, hwnd_after):
        """把 hwnd_target 插到 z 序里 hwnd_after **之上**（紧邻其后）。

        只动 z 序，不动位置/大小/焦点：
        `SWP_NOMOVE|SWP_NOSIZE|SWP_NOACTIVATE|SWP_NOOWNERZORDER`。
        用 win32gui 是为了 64 位 HWND 不被截断。

        `hwnd_after` 失效（窗口刚被关掉）时回落到 HWND_BOTTOM ——
        绝不把野句柄交给 SetWindowPos（那会得到一次无法预期的 z 序跳变）。
        """
        if not hwnd_target or not win32gui.IsWindow(hwnd_target):
            return False
        insert = hwnd_after or HWND_BOTTOM
        try:
            if insert not in (HWND_BOTTOM, HWND_TOP, HWND_TOPMOST, HWND_NOTOPMOST) \
                    and not win32gui.IsWindow(insert):
                insert = HWND_BOTTOM
        except Exception:
            insert = HWND_BOTTOM
        flags = SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_NOOWNERZORDER
        try:
            win32gui.SetWindowPos(hwnd_target, insert, 0, 0, 0, 0, flags)
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Floor queries
    # ------------------------------------------------------------------

    @staticmethod
    def floor_visible_contains(floor, pos):
        """pos 是否落在该楼层的**可见**区域里。

        这是"建楼"的核心判定：站在楼板上时，脚下那一点必须是**看得见的地板**。
        被前面窗口盖住的部分不算 —— 否则宠物会站在根本看不见的地方
        （第十三轮之前只判 `rect.contains(pos)`，于是"被挡住 90% 的窗口"
        仍然是整块可站楼板，这正是用户看到的"没有遮挡关系"）。
        """
        if floor is None:
            return False
        if floor.get('type') == 'desktop':
            return bool(floor['rect'].contains(pos))
        for r in floor.get('visible_rects') or ():
            if r.contains(pos):
                return True
        return False

    def floor_at_native_point(self, pos):
        """Windows 原生口径：`WindowFromPoint` 说"这一点上最上面是谁"。

        返回对应楼层；无法判定时返回 None：
          · 返回 0（该处没有任何窗口 → 桌面）；
          · 返回的句柄不属于任何已知楼层（例如**本程序自己的窗口** —— 宠物窗口就盖在
            自己脚下这一点上，这种情况下原生口径没有参考价值，必须让几何判定说了算）。

        `WS_EX_TRANSPARENT` 的窗口会被系统自动跳过，天然符合"不透明原则"。
        """
        hwnd = _native_window_from_point(pos.x(), pos.y())
        if not hwnd:
            return None
        for floor in self.floors:
            if floor.get('window_hwnd') == hwnd:
                return floor
        return None

    def get_current_floor(self, pos):
        """pos 处宠物应该站的楼板：**可见区域**命中的最高那层。

        判定顺序（为什么这么定）：
          ① 几何口径为主 —— "可见区域 + 从高到低"，与 Windows 的 z 序语义一致，
             而且可以离线复现（回归门禁要的是确定性）；
          ② 原生口径只做**"只升不降"**的兜底 —— 只有当几何判定得出"脚下是桌面"、
             而 Windows 原生 `WindowFromPoint` 明确指到某个已知楼层时才采纳它。
             方向如此限定是为了两件事同时成立：真机上多一层保护（几何算错时仍站得住），
             测试里不可能被外部真实窗口干扰（原生答案只会命中"本就不存在的楼层"→ 不采纳）。
        """
        all_floors = sorted(self.floors + [self.desktop_floor],
                            key=lambda x: x['platform_height'], reverse=True)
        geometric = self.desktop_floor
        for floor in all_floors:
            if self.floor_visible_contains(floor, pos):
                geometric = floor
                break

        if geometric.get('type') == 'desktop':
            native = self.floor_at_native_point(pos)
            if native is not None and native.get('type') != 'desktop':
                return native
        return geometric

    def get_floors_above(self, current_floor):
        above_floors = []
        for floor in self.floors:
            if floor['platform_height'] > current_floor['platform_height']:
                above_floors.append(floor)
        return above_floors

    @staticmethod
    def _floor_identity(floor):
        """楼层的稳定标识：窗口用 hwnd，桌面用固定串。

        修复：原来用 dict 内容相等（floor == current_floor）来定位"当前楼层"在
        all_floors 中的下标，但 floors 每秒由 update_floors 整体重建，
        窗口标题/位置/z 序任一变化都会让旧对象与重建后的对象不相等 →
        current_index 保持 -1 → range(0, len) 就变成"从最顶层窗口开始找落点"，
        宠物从某个窗口边缘掉下时会被判定成落到比它更高的窗口上（凭空被"上吸"）。
        """
        if floor is None:
            return None
        if floor.get('type') == 'desktop':
            return DESKTOP_IDENTITY
        return floor.get('window_hwnd')

    def _index_of_floor(self, all_floors, current_floor):
        """返回 current_floor 在 all_floors（按 platform_height 降序）中的下标。

        找不到时按平台高度退化定位，且保证结果指向"不高于当前楼层"的位置，
        绝不会把搜索起点错误地放到列表头部（最顶层）。

        第三十四轮修复（退化分支的 -1 不是安全哨兵）：
            原写法 `return i - 1` 在本函数语境里表示"**当前楼层高于第 i 层**"，
            但 `i == 0` 时它会返回 **-1** —— 而 -1 的两个消费方都不把它当
            "未找到"，而是当成"**比最高的活楼层还高**"：
              · `get_drop_destination`：`range(current_index+1, n)` 变成
                `range(0, n)` → 从**最高**的活楼层开始向下扫 → 第一块能接住的
                就是最高的那块 → 宠物**被"上吸"到更高的楼层**；
              · `adjacent_lower_floor`：`idx < 0` 直接 `return None`，
                None 的语义是"已在最底层、下面没有楼板了" → **明明有下一层却报"到底了"**。
            `_floor_identity` 的注释里记着同型的"凭空被上吸"历史缺陷，这条是它的复现路径。

            触发条件（真机可达）：宠物站在**当前最高的那个窗口**上，用户把这个窗口
            关掉 → `self.current_floor` 还持有那只已消失窗口的旧 dict（hwnd 已不在
            `underlying_windows` 里），而重建后的 `all_floors` 最高层比它低 →
            按高度找"<= cur_h"的第一项就是 `i == 0` → 返回 -1。

            修法：把"比所有活楼层都高"显式规范成 **0**（落在最高活楼层**之上**，
            于是 `current_index + 1 == 1`，向下扫时从第二高的活楼层开始，
            与"关掉最高的楼板 → 掉到下一个活楼层或桌面"的既有口径一致）。
            ⚠️ 只在 `i == 0` 这一支改变返回值；`i >= 1` 时 `i - 1` 语义本就正确
            （它就是"不高于当前楼层"的最近一项），保持原样以免动到已锁定的路径。
        """
        cur_id = self._floor_identity(current_floor)
        for i, floor in enumerate(all_floors):
            if self._floor_identity(floor) == cur_id:
                return i
        try:
            cur_h = current_floor.get('platform_height', 0)
        except AttributeError:
            cur_h = 0
        for i, floor in enumerate(all_floors):
            if floor['platform_height'] <= cur_h:
                # i == 0：当前楼层比**所有**活楼层都高 → 规范成 0，不留 -1。
                # （-1 会被 range(idx+1, n) 误当成"从最高层开始扫"，见 docstring）
                return 0 if i == 0 else i - 1
        return len(all_floors) - 1

    def get_drop_destination(self, pos, current_floor):
        """向下掉时，pos 正下方第一块**能接住它**的楼板。

        可见区域判定（第十三轮）：被前面窗口盖住的部分接不住宠物 ——
        楼板只在"看得见的地板"上才是实的（对应"不透明原则"）。
        """
        all_floors = sorted(self.floors + [self.desktop_floor], key=lambda x: x['platform_height'], reverse=True)

        current_index = self._index_of_floor(all_floors, current_floor)

        for i in range(current_index + 1, len(all_floors)):
            floor = all_floors[i]
            if self.floor_visible_contains(floor, pos):
                return floor, pos

        return self.desktop_floor, pos

    def get_jump_destinations(self, current_floor, current_pos):
        """可跳的目标：附近同一层的位置、上方**可见**的悬崖边、下方相邻一层。

        对照"建楼"要求：
          · 向上跳只能落到"没被其他东西挡住的那部分边缘" → 落点必须在该层**可见区域**内；
            原来这里又用 `contains` 自己判了一遍"是否可见"，与 _generate_floors 的口径
            不一致（一个判完全包含、一个判可见区域），现在统一由 visible_rects 回答。
          · 向下跳只能跳**相邻的下一层**，不能穿透中间楼层。
        """
        jump_destinations = []

        jump_destinations.append((current_floor, current_pos))

        above_floors = sorted(self.get_floors_above(current_floor),
                             key=lambda x: x['platform_height'])

        for floor in above_floors:
            rect = floor['rect']

            if (current_pos.x() >= rect.left() and
                current_pos.x() <= rect.right() and
                current_pos.y() >= rect.bottom()):
                jump_pos = QPoint(current_pos.x(), rect.top() + 10)
                # 落点必须是看得见的地板（被挡住的部分跳不上去）
                if self.floor_visible_contains(floor, jump_pos):
                    jump_destinations.append((floor, jump_pos))

        all_floors = sorted(self.floors + [self.desktop_floor],
                          key=lambda x: x['platform_height'], reverse=True)

        # 修复：同 get_drop_destination，改用稳定标识定位（见 _floor_identity 注释）
        current_index = self._index_of_floor(all_floors, current_floor)

        if current_index + 1 < len(all_floors):
            next_floor = all_floors[current_index + 1]
            if (current_pos.x() >= next_floor['rect'].left() and
                current_pos.x() <= next_floor['rect'].right()):
                jump_pos = QPoint(current_pos.x(), next_floor['rect'].top() + 10)
                if self.floor_visible_contains(next_floor, jump_pos):
                    jump_destinations.append((next_floor, jump_pos))

        return jump_destinations

    def adjacent_lower_floor(self, current_floor):
        """当前楼板**直接相邻**的那一层（桌面恒为最底层）。

        建楼要求（向下跳的逐层约束）：
          "如果它站在3楼的窗口上，想回桌面（1楼），它必须先跳到2楼（中间层的窗口），
           然后再从2楼跳回1楼。不能直接从3楼穿透2楼跳到1楼！"

        注意"楼层"是**堆叠名次**（platform_height），不是屏幕 y 坐标 ——
        2楼那块楼板在屏幕上可能比 3楼高也可能比它低，但名次上紧挨着它。
        已经是最底层（桌面）时返回 None："桌面下面没有楼板了"。
        """
        all_floors = sorted(self.floors + [self.desktop_floor],
                            key=lambda x: x['platform_height'], reverse=True)
        idx = self._index_of_floor(all_floors, current_floor)
        if idx < 0:
            return None
        if idx + 1 < len(all_floors):
            return all_floors[idx + 1]
        return None

    def nearest_visible_point(self, floor, pos):
        """把落点吸附到该楼层的**可见区域**内（越界就取最近的那块可见子矩形）。

        建楼要求（向上跳的落点约束）：
          "它只能跳到这个浏览器窗口没被其他东西挡住的那部分边缘上。"
        被前面窗口盖住的部分是"看不见的地板"，落上去等于站在虚空里。
        桌面层整片都是可见的，直接原样返回。

        返回 None = 该层没有任何可见区域（理论上不会发生：可见面积不足阈值的
        窗口根本不会成为楼层）→ 调用方据此放弃这次跳跃。
        """
        if floor is None:
            return None
        if floor.get('type') == 'desktop':
            return pos
        rects = floor.get('visible_rects') or []
        if not rects:
            return None
        for r in rects:
            if r.contains(pos):
                return pos
        best, best_d2 = None, None
        for r in rects:
            # 子矩形内的最近点（点在外面时是边界上的投影）
            lx = min(max(pos.x(), r.left()), r.right())
            ly = min(max(pos.y(), r.top()), r.bottom())
            d2 = (pos.x() - lx) ** 2 + (pos.y() - ly) ** 2
            if best_d2 is None or d2 < best_d2:
                best_d2, best = d2, QPoint(lx, ly)
        return best

    def is_floor_valid(self, floor):
        """该楼板引用的窗口是否还在（还活着）。

        修复（第十三轮）：原来要求"四边与缓存完全相等"才判有效 —— 但改用 DWM 可见边框
        后（见 desktop_interaction.get_frame_rect），窗口只要被拖动/缩放/进出全屏，
        边框就会有 1px 级抖动，于是同一块楼板被判"失效"，宠物凭空掉下去。
        现在只判"窗口还在不在"，几何变化交给"跟随楼板移动"逻辑处理。
        """
        if floor['type'] == 'desktop':
            return True

        hwnd = floor.get('window_hwnd')
        for window in self.underlying_windows:
            if window['hwnd'] == hwnd:
                return True
        return False

    def get_all_floors(self):
        return self.floors + [self.desktop_floor]

    def get_floor_by_window(self, window_hwnd):
        for floor in self.floors:
            if floor['type'] == 'window' and floor['window']['hwnd'] == window_hwnd:
                return floor
        return None

