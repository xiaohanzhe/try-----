# -*- coding: utf-8 -*-
"""第十三轮验证：「建楼」——遮挡判定 + 窗口层数 + 渲染层序（按 Windows 原生口径）。

用户报的问题
------------
"他直接走到我的窗口上面了，根本没遮挡关系这类的" —— 宠物会站在"看不见的地板"上，
而且它**永远画在所有窗口之上**。要求原话："我想要的是那种效果，这个遮挡判定这类的，
还有窗口层数这样的你可以直接参考 Windows 本地是怎么判定的"。

对照 `"建楼"要求` 文档定位到三处硬伤
------------------------------------
 1. `_generate_floors` 用 `rect.contains(rect)` 判"被盖住" —— 那是**完全包含**，
    于是"被挡住 90% 的窗口"仍是一整块可站楼板 → 宠物站在看不见的地方。
    要求原文只说"被**完全**盖住才算压下去"，但反过来"被遮住的那部分也不该能站"。
 2. `get_current_floor` 只判 `rect.contains(pos)`，完全不看遮挡 → 站在被盖住的部分也算数。
    要求："站在2楼就看不见1楼""只能跳到没被挡住的那部分边缘"。
 3. `main.py` 在窗口上时用 `Qt.WindowStaysOnTopHint` **强制置顶** → 遮挡关系彻底失效。
    而 floor_manager 里早有正确的机制（`get_insert_after_hwnd` + `set_window_behind`，
    用原生 `SetWindowPos(insertAfter=...)` 把宠物插到"所站楼板之上"）—— 但**零调用**，是死代码。

Windows 原生口径（用户要求"参考 Windows 本地怎么判定"）
--------------------------------------------------------
 · z 序        `GetTopWindow` + `GetWindow(GW_HWNDNEXT)`（顶层窗口从前往后）
 · 这一点谁在最上面 `WindowFromPoint` + `GetAncestor(GA_ROOT)`
 · 可见边框    `DwmGetWindowAttribute(DWMWA_EXTENDED_FRAME_BOUNDS)`（不含 DWM 隐形阴影）
 · 幽灵窗口    `DwmaGetWindowAttribute(DWMWA_CLOAKED)`（挂起的 UWP / 别的虚拟桌面）
 · 自身排除    `GetWindowThreadProcessId` 比对本进程（不是靠标题里有没有 "Ralsei"）
 · 不是地板    排除 `WS_EX_TOOLWINDOW` / `WS_EX_NOACTIVATE`（保留原有的 TRANSPARENT / 半透明过滤）
 · z 序插入    `SetWindowPos(hwnd, insertAfter, SWP_NOMOVE|NOSIZE|NOACTIVATE|NOOWNERZORDER)`

分组
----
  A 可见区域几何（矩形相减的不变量）
  B 楼层生成（完全遮住→不存在 / 名次 / 细缝阈值 / 被压下去的不再遮挡）
  C 查询按可见区域（站立 / 下落 / 跳跃）
  D Windows 原生口径（枚举与 DWM 助手 + 源码级约束）
  E main.py 接线（置顶已去除 / z 序 helper 被接活）
  F floor_manager 契约（失效句柄回落 / is_floor_valid 不再要求四边相等）
  G 存储探测零副作用（G2 自伤的真凶：`.write_probe` 删除配额）

本套件**不依赖任何真实窗口**（全用合成窗口表），因此结果确定可复现。
必须用 C:\\Python311\\python.exe 运行。
"""
import io
import os
import sys
import tokenize

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
MODS = os.path.join(PET, 'modules')
for _p in (os.path.join(PET, 'src'), MODS):
    if _p not in sys.path:
        sys.path.append(_p)

from PyQt5.QtCore import QPoint, QRect                      # noqa: E402
import floor_manager as FM                                   # noqa: E402

PASS, FAIL = [], []


def ok(name, cond, detail=''):
    (PASS if cond else FAIL).append(name)
    print(('[PASS] ' if cond else '[FAIL] ') + name +
          ('' if cond else '   <<< ' + str(detail)))


def section(title):
    print('')
    print('=== %s ===' % title)


def code_only(path):
    """剥注释与字符串的源码（needle 里若含字符串字面量请用 code_no_comment）。"""
    out = []
    try:
        with io.open(path, 'rb') as fh:
            for tok in tokenize.tokenize(fh.readline):
                if tok.type in (tokenize.COMMENT, tokenize.STRING):
                    continue
                out.append(tok.string)
    except Exception:
        return ''
    # tokenize 不产空白 token → 必须用 ' '.join 保分隔（''.join 会把 import x 粘成 importx）
    return ' '.join(out)


def code_no_comment(path):
    out = []
    try:
        with io.open(path, 'rb') as fh:
            for tok in tokenize.tokenize(fh.readline):
                if tok.type == tokenize.COMMENT:
                    continue
                out.append(tok.string)
    except Exception:
        return ''
    return ' '.join(out)


def flat(src):
    import re
    return re.sub(r'\s+', '', src)


def has(src, needle):
    return flat(needle) in flat(src)


def mk_window(hwnd, x, y, w, h, z, title='w'):
    return {'hwnd': hwnd, 'title': title, 'class_name': 'C',
            'rect': QRect(x, y, w, h), 'z_order': z}


def fm_with(windows):
    fm = FM.FloorManager(parent=None)
    fm.underlying_windows = list(windows)
    # 桌面层矩形：真机由 update_floors() 用虚拟屏尺寸填，这里显式给一个 1920x1080，
    # 否则它是构造时的 (0,0,0,0) 退化矩形，"落到桌面"的判定会被整片排除。
    fm.desktop_floor['rect'] = QRect(0, 0, 1920, 1080)
    fm._generate_floors()
    return fm


def covered_area_oracle(target, blockers, step=10):
    """**独立实现**的"被遮挡面积"：采样网格逐点判归属。

    存在的意义：给解析法（visible_subrects）算期望值时必须用另一条路子，
    否则就是"拿被测函数自己验证自己"。要求所有坐标都是 step 的倍数，
    这样格心落在哪个矩形里是精确的（坐标全用 100 的倍数 → 严谨）。
    """
    l, t, r, b = target
    covered = 0
    y = t
    while y < b:
        x = l
        while x < r:
            cx, cy = x + step / 2.0, y + step / 2.0
            if any(bl <= cx < br and bt <= cy < bb for bl, bt, br, bb in blockers):
                covered += step * step
            x += step
        y += step
    return covered


def rects_of(floor):
    return [(r.left(), r.top(), r.left() + r.width(), r.top() + r.height())
            for r in floor['visible_rects']]


# ============================================================ A 可见区域几何
section('A 可见区域几何（矩形相减的不变量）')

A = (0, 0, 1000, 800)
B = (600, 100, 900, 400)
pieces = FM.visible_subrects(A, [B])
expect_area = 1000 * 800 - covered_area_oracle(A, [B])
ok('A1 挖洞后面积正确（与独立采样网格 oracle 一致）',
   sum(FM._area(p) for p in pieces) == expect_area,
   'sum=%d oracle=%d' % (sum(FM._area(p) for p in pieces), expect_area))

_overlap = [(pieces[i], pieces[j]) for i in range(len(pieces)) for j in range(i + 1, len(pieces))
            if (pieces[i][0] < pieces[j][2] and pieces[j][0] < pieces[i][2]
                and pieces[i][1] < pieces[j][3] and pieces[j][1] < pieces[i][3])]
ok('A2 返回的矩形两两不重叠（面积可直接求和的前提）', not _overlap, _overlap)

_in_hole = [p for p in pieces if p[0] <= 700 < p[2] and p[1] <= 150 < p[3]]
ok('A3 洞内的点不在任何可见矩形里', not _in_hole, _in_hole)
_outside = [p for p in pieces if p[2] > A[2] or p[3] > A[3] or p[0] < A[0] or p[1] < A[1]]
ok('A4 可见矩形不会跑到自身矩形之外', not _outside, _outside)

ok('A5 完全被挖掉返回空列表', FM.visible_subrects((0, 0, 10, 10), [(0, 0, 10, 10)]) == [],
   FM.visible_subrects((0, 0, 10, 10), [(0, 0, 10, 10)]))
ok('A6 不相交的洞不影响面积',
   FM._area(FM.visible_subrects(A, [(2000, 2000, 2100, 2100)])[0]) == 1000 * 800, None)

# ============================================================ B 楼层生成
section('B 楼层生成（遮挡判定）')

fm = fm_with([mk_window(2001, 600, 100, 300, 300, 0),      # 记事本（最前）
              mk_window(2002, 0, 0, 1000, 800, 1)])        # 浏览器（在后）
ok('B1 两层都在 → 生成 2 块楼板', len(fm.floors) == 2, len(fm.floors))

b_floor = fm.get_floor_by_window(2001)
a_floor = fm.get_floor_by_window(2002)
ok('B2 最前的窗口是最高楼层（名次编号：最前 = 数值最大）',
   b_floor['platform_height'] > a_floor['platform_height'],
   'note=%s browser=%s' % (b_floor['platform_height'], a_floor['platform_height']))
ok('B3 桌面恒为 0 层（1楼）', fm.desktop_floor['platform_height'] == 0, None)
ok('B4 被部分遮挡的窗口：可见面积 = 自身 − 遮挡部分',
   a_floor['visible_area'] == 1000 * 800 - 300 * 300, a_floor['visible_area'])
ok('B5 被遮挡那部分的点不在可见区域里（不能站上去）',
   not any(r.contains(QPoint(700, 150)) for r in a_floor['visible_rects']),
   rects_of(a_floor))
ok('B6 没被遮挡那部分的点在可见区域里', FM.FloorManager.floor_visible_contains(a_floor, QPoint(100, 400)),
   rects_of(a_floor))

fm_full = fm_with([mk_window(3001, 0, 0, 1920, 1080, 0),    # 全屏窗口在最前
                   mk_window(3002, 100, 100, 400, 300, 1)])  # 被完全盖住
ok('B7 被完全盖住的窗口"暂时不存在"（不成楼板）', len(fm_full.floors) == 1, len(fm_full.floors))
ok('B8 被压下去的窗口不参与遮挡更低窗口（它自己也不存在）',
   fm_full.get_floor_by_window(3002) is None, None)

# 三层：第 1 层在前、第 2 层被第 1 层压住一大半（但仍露出一截）、第 3 层在最下。
# 坐标全是 100 的倍数 → 可以拿采样网格 oracle 精确交叉验证解析法。
W1 = (0, 0, 1000, 500)
W2 = (200, 400, 600, 700)
W3 = (0, 0, 1000, 1000)
fm3 = fm_with([mk_window(1, 0, 0, 1000, 500, 0),
               mk_window(2, 200, 400, 400, 300, 1),
               mk_window(3, 0, 0, 1000, 1000, 2)])
ok('B9 上层只压住下层重叠的部分，下层仍有可见区域 → 仍是楼板',
   len(fm3.floors) == 3, [f['window_hwnd'] for f in fm3.floors])
f2_3 = fm3.get_floor_by_window(2)
ok('B9b 被压住大半的窗口：可见面积只算露出来的那截（解析法 vs 网格 oracle）',
   f2_3['visible_area'] == (400 * 300) - covered_area_oracle(W2, [W1]),
   'analytic=%s oracle=%s' % (f2_3['visible_area'], (400 * 300) - covered_area_oracle(W2, [W1])))
f3 = fm3.get_floor_by_window(3)
ok('B10 最底层被两层遮挡后的可见面积正确（两个遮挡者互相重叠也不重复扣）',
   f3['visible_area'] == (1000 * 1000) - covered_area_oracle(W3, [W1, W2]),
   'analytic=%s oracle=%s' % (f3['visible_area'],
                              (1000 * 1000) - covered_area_oracle(W3, [W1, W2])))

# 细缝阈值
fm_sliver1 = fm_with([mk_window(11, 0, 0, 1000, 199, 0),
                      mk_window(12, 0, 0, 1000, 200, 1)])
fm_sliver4 = fm_with([mk_window(11, 0, 0, 1000, 196, 0),
                      mk_window(12, 0, 0, 1000, 200, 1)])
ok('B11 只剩 1px 缝（< MIN_FLOOR_VISIBLE_AREA）→ 站不住，不算楼层',
   len(fm_sliver1.floors) == 1, [f['window_hwnd'] for f in fm_sliver1.floors])
ok('B12 缝放宽到 4px（> 阈值）→ 恢复成楼层（阈值是"够不够站"，不是"有没有缝"）',
   len(fm_sliver4.floors) == 2, [f['window_hwnd'] for f in fm_sliver4.floors])
ok('B13 阈值常量存在且有据可依（约宠物脚下 40x40）',
   isinstance(FM.MIN_FLOOR_VISIBLE_AREA, int) and FM.MIN_FLOOR_VISIBLE_AREA > 0,
   FM.MIN_FLOOR_VISIBLE_AREA)
ok('B14 同一窗口在前时自身可见面积 = 全矩形（没东西挡它）',
   fm.get_floor_by_window(2001)['visible_area'] == 300 * 300, None)

# ============================================================ C 查询按可见区域
section('C 查询按可见区域（站立 / 下落 / 跳跃）')

ok('C1 站立：重叠区里取最上面那层（记事本）',
   fm.get_current_floor(QPoint(700, 150)).get('window_hwnd') == 2001, None)
ok('C2 站立：只有浏览器的地方 → 浏览器',
   fm.get_current_floor(QPoint(100, 400)).get('window_hwnd') == 2002, None)
ok('C3 站立：全都在外面 → 桌面',
   fm.get_current_floor(QPoint(5000, 5000)).get('type') == 'desktop', None)

dest, _ = fm.get_drop_destination(QPoint(700, 150), b_floor)
ok('C4 从记事本往下掉：浏览器在那里被记事本自己盖住 → 接不住，落到桌面',
   dest.get('type') == 'desktop', dest.get('type'))
dest2, _ = fm.get_drop_destination(QPoint(700, 700), b_floor)
ok('C5 从记事本往下掉：浏览器在那里可见 → 被浏览器接住',
   dest2.get('window_hwnd') == 2002, dest2.get('window_hwnd'))
ok('C6 find_support_below 同样按可见区域：记事本下方那块地板在被遮处接不住',
   fm.find_support_below(QPoint(700, 150),
                         z_below=b_floor['platform_height'] - 1).get('type') == 'desktop',
   fm.find_support_below(QPoint(700, 150),
                         z_below=b_floor['platform_height'] - 1).get('type'))

# 向上跳的两个前提：① 宠物水平位置在目标层横向范围内 ② 落点在目标层可见区域
_jumps = fm.get_jump_destinations(a_floor, QPoint(700, 500))
ok('C7 向上跳：落点必须落在目标层的可见区域（记事本可见 → 可跳）',
   any(f.get('window_hwnd') == 2001 for f, _p in _jumps),
   [(f.get('window_hwnd'), p.x(), p.y()) for f, p in _jumps])
_jumps_off = fm.get_jump_destinations(a_floor, QPoint(300, 500))
ok('C7b 水平位置不在目标层范围内 → 不产生该跳跃目标（沿用力学规则）',
   not any(f.get('window_hwnd') == 2001 for f, _p in _jumps_off),
   [(f.get('window_hwnd'), p.x(), p.y()) for f, p in _jumps_off])

# 目标层顶部被更高窗口盖住 → 不允许跳上去
fm_cover = fm_with([mk_window(21, 0, 0, 1000, 60, 0),        # 盖住 22 的顶部
                    mk_window(22, 0, 0, 1000, 600, 1)])
f22 = fm_cover.get_floor_by_window(22)
_cover_jumps = fm_cover.get_jump_destinations(fm_cover.desktop_floor, QPoint(500, 900))
ok('C8 向上跳：目标层顶部被盖住 → 不允许跳到那里（原来只判"完全包含"会漏）',
   not any(f.get('window_hwnd') == 22 for f, _p in _cover_jumps),
   [f.get('window_hwnd') for f, _p in _cover_jumps])

_desk_jumps = [(_f, _p) for _f, _p in fm.get_jump_destinations(a_floor, QPoint(300, 500))
               if _f is not a_floor]          # 首个元素恒为"当前楼层自身"，不算跳跃目标
ok('C9 向下跳：只能落到**相邻的下一层**，不能跨越中间楼层',
   len(_desk_jumps) == 1 and _desk_jumps[0][0].get('type') == 'desktop',
   [(f.get('window_hwnd'), f.get('type')) for f, _p in _desk_jumps])

# ============================================================ D Windows 原生口径
section('D Windows 原生口径（枚举与 DWM 助手 + 源码级约束）')

import desktop_interaction as DI                             # noqa: E402

ok('D1 存在 get_frame_rect（DWM 可见边框，替代含阴影的 GetWindowRect）',
   callable(getattr(DI, 'get_frame_rect', None)))
ok('D2 get_frame_rect 契约"绝不抛"：无效句柄返回 (0,0,0,0)',
   DI.get_frame_rect(0) == (0, 0, 0, 0), DI.get_frame_rect(0))
ok('D3 存在 is_cloaked（幽灵窗口：挂起 UWP / 别的虚拟桌面）且不抛',
   callable(getattr(DI, 'is_cloaked', None)) and DI.is_cloaked(0) is False, None)
ok('D4 存在 window_from_point（"这一点上最上面是谁"）且返回 int',
   callable(getattr(DI, 'window_from_point', None))
   and isinstance(DI.window_from_point(0, 0), int), None)
ok('D5 存在 get_root_window（WindowFromPoint 可能返回子窗口）',
   callable(getattr(DI, 'get_root_window', None)))
ok('D6 存在 get_window_pid（按进程排除自身窗口）',
   callable(getattr(DI, 'get_window_pid', None)))

_di_src = code_only(os.path.join(MODS, 'desktop_interaction.py'))
ok('D7 用到 DWMWA_EXTENDED_FRAME_BOUNDS=9（可见边框）',
   has(_di_src, 'DWMWA_EXTENDED_FRAME_BOUNDS = 9'), None)
ok('D8 用到 DWMWA_CLOAKED=14（幽灵窗口判定）', has(_di_src, 'DWMWA_CLOAKED = 14'), None)
ok('D9 用到 WindowFromPoint + GA_ROOT（原生命中测试 + 取顶层）',
   has(_di_src, 'WindowFromPoint') and has(_di_src, 'GA_ROOT = 2'), None)
ok('D10 WindowFromPoint / GetAncestor 的 restype 显式声明为 c_void_p（防 64 位 HWND 截断）',
   has(_di_src, 'user32.WindowFromPoint.restype = ctypes.c_void_p')
   and has(_di_src, 'user32.GetAncestor.restype = ctypes.c_void_p'), None)
ok('D11 枚举按**进程**排除自身窗口（不再只看标题里有没有 Ralsei）',
   has(_di_src, 'get_window_pid(hwnd) == own_pid'), None)
ok('D12 过滤 WS_EX_TOOLWINDOW / WS_EX_NOACTIVATE（浮动覆盖层不是地板）',
   has(_di_src, 'ex_style & win32con.WS_EX_TOOLWINDOW')
   and has(_di_src, 'ex_style & win32con.WS_EX_NOACTIVATE'), None)
ok('D13 保留不透明原则：WS_EX_TRANSPARENT 与半透明分层窗口仍被排除',
   has(_di_src, 'ex_style & win32con.WS_EX_TRANSPARENT')
   and has(_di_src, 'alpha < 255'), None)
# 注意：找"字符串字面量 needle"必须用 code_no_comment（code_only 会把字面量剥掉 →
# 断言变成恒真，这就是历轮记下的"字符串 needle 陷阱"）。
_di_nc = code_no_comment(os.path.join(MODS, 'desktop_interaction.py'))
ok('D14 窗口表不再自带 platform_height（消除与 floor_manager 并存的第二套编号口径）',
   "window['platform_height']" not in flat(_di_nc), None)
ok('D15 枚举确实改用 get_frame_rect 取矩形', has(_di_src, 'rect = get_frame_rect(hwnd)'), None)

# ============================================================ E main.py 接线
section('E main.py 接线（置顶已去除 / z 序 helper 被接活）')

_main_src = code_only(os.path.join(PET, 'src', 'main.py'))
ok('E1 main.py 代码里已无 Qt.WindowStaysOnTopHint（强制置顶 = 遮挡关系失效）',
   'WindowStaysOnTopHint' not in _main_src, None)
ok('E2 新增 _apply_pet_z_order 且被调用（不只是定义）',
   _main_src.count('_apply_pet_z_order') >= 4, _main_src.count('_apply_pet_z_order'))
ok('E3 接活了 floor_manager 的 z 序 helper（原来全项目零调用）',
   'get_insert_after_hwnd' in _main_src and 'set_window_behind' in _main_src, None)
ok('E4 初始窗口标志仍是"非置顶"的 FramelessWindowHint|Tool',
   has(_main_src, 'setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)'), None)

_fm_src = code_only(os.path.join(MODS, 'floor_manager.py'))
_main_nc = code_no_comment(os.path.join(PET, 'src', 'main.py'))
ok('E5 跳跃目标 Z 不再读裸窗口 dict 的 platform_height（改读楼层，唯一权威编号）',
   "target_window['platform_height']" not in flat(_main_nc), None)

# ============================================================ F floor_manager 契约
section('F floor_manager 契约（失效句柄回落 / 有效性判定）')

# 打桩 find_desktop_workerw_hwnd：真实实现会给 Progman 发 0x052C 消息、
# 在用户桌面上真的创建一个 WorkerW 窗口 —— 回归套件不该有这种副作用。
def _no_workerw():
    return 0


_fm_probe = FM.FloorManager(parent=None)
_fm_probe.find_desktop_workerw_hwnd = _no_workerw
ok('F1 get_insert_after_hwnd：句柄失效的窗口楼板 → 回落到非 0 插入点（不把野句柄交出去）',
   _fm_probe.get_insert_after_hwnd(b_floor) == FM.HWND_BOTTOM,
   _fm_probe.get_insert_after_hwnd(b_floor))
ok('F2 get_insert_after_hwnd：桌面层 → 同样回落到非 0 插入点',
   _fm_probe.get_insert_after_hwnd(None) == FM.HWND_BOTTOM,
   _fm_probe.get_insert_after_hwnd(None))
ok('F3 set_window_behind：无效目标句柄返回 False（不抛）',
   FM.FloorManager.set_window_behind(0, 0) is False, None)
ok('F4 存在 z_order_index / is_above（用原生 z 序链核验插入位置）',
   callable(getattr(FM.FloorManager, 'z_order_index', None))
   and callable(getattr(FM.FloorManager, 'is_above', None)), None)
ok('F5 z_order_index：无效句柄返回 None（不失真）',
   FM.FloorManager.z_order_index(0) is None, None)
ok('F6 存在桌面层插入点回落 _workerw_or_bottom',
   callable(getattr(FM.FloorManager, '_workerw_or_bottom', None)), None)

fm_valid = fm_with([mk_window(31, 0, 0, 400, 400, 0)])
fl = fm_valid.get_floor_by_window(31)
fm_valid.underlying_windows = [mk_window(31, 3, 3, 400, 400, 0)]   # 只是边框抖动
ok('F7 is_floor_valid 不再要求四边完全相等（DWM 边框 1px 抖动不再让楼板"消失"）',
   fm_valid.is_floor_valid(fl) is True, None)
fm_valid.underlying_windows = []
ok('F8 窗口真的不在了 → is_floor_valid False',
   fm_valid.is_floor_valid(fl) is False, None)

ok('F9 原生交叉校验接口存在（Windows 口径的诊断入口）',
   callable(getattr(FM.FloorManager, 'floor_at_native_point', None)), None)
ok('F10 floor_visible_contains：桌面层退回整屏矩形判定',
   FM.FloorManager.floor_visible_contains(fm.desktop_floor, QPoint(10, 10)) is True, None)
ok('F11 被完全盖住的窗口不出现在 get_all_floors 里（"暂时不存在"）',
   all(f.get('window_hwnd') != 3002 for f in fm_full.get_all_floors()),
   [f.get('window_hwnd') for f in fm_full.get_all_floors()])
ok('F12 _generate_floors 自己按 z_order 排序（不再依赖调用方已排好）',
   has(code_only(os.path.join(MODS, 'floor_manager.py')),
       'sorted(self.underlying_windows, key=lambda w: w.get'), None)

# ============================================================ G 存储探测零副作用
# 为什么这一组必须存在（第十三轮现场记录）：
#   `memory_store._is_writable_dir` 的老实现每次调用都真的 建/写/删 一个
#   `.write_probe`。`find_device_dir(create=True)` 在一次启动里被调十几次
#   （data_store 要解析记忆库 + 7 类运行时产物），而 G2 一轮跑 17 个套件 ——
#   于是同一路径 `E:\RalseiMemory\.write_probe` 在一轮里被删 50+ 次，累积撞上
#   宿主沙箱的"同一轮内同路径删除配额"守卫（SAFE_DELETE_BULK_CONFIRM_REQUIRED），
#   把一个个套件进程在**开头就掐掉**。症状极具误导性：11 个套件同时报
#   `exit=1 PASS=0` + 假 DIFF，看着像代码全崩，其实是测试自伤。
# 这一组锁住"探针不许再产生删除"，并且把 run_all.py 的隔离清单也一起锁住。
import ast
import re
import shutil
import tempfile

import memory_store as MS

MS_PATH = os.path.join(MODS, 'memory_store.py')


def strip_all_ws(src):
    """剥注释/字符串并按 token 拼回（tokenize 不产空白 token），再去掉全部空白。

    只用于在**函数体内**做"谁先谁后"的顺序断言 —— 全文件 `.index()` 会命中别的
    函数（memory_store 的 migrate 也会 `os.remove`），把结论判反。
    """
    out = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(src).readline):
            if tok.type in (tokenize.COMMENT, tokenize.STRING):
                continue
            out.append(tok.string)
    except Exception:
        return re.sub(r'\s+', '', src)
    return re.sub(r'\s+', '', ' '.join(out))


def func_src_of(path, name):
    src = open(path, encoding='utf-8').read()
    lines = src.splitlines()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return '\n'.join(lines[node.lineno - 1:node.end_lineno])
    return ''


_g_body = strip_all_ws(func_src_of(MS_PATH, '_is_writable_dir'))
ok('G1 _is_writable_dir 内先走 os.access 快路径、再才轮到 os.remove 老探针',
   _g_body.count('os.access') >= 1 and 'os.remove' in _g_body
   and _g_body.index('os.access') < _g_body.index('os.remove'),
   'access@%d remove@%d' % (_g_body.find('os.access'), _g_body.find('os.remove')))

_g_tmp = tempfile.mkdtemp(prefix='ralsei_g13_probe_')
_g_access_hits = []
_saved_access, _saved_remove = os.access, os.remove
_g_verdict = None
try:
    # 健康目录：快路径命中 → 判可写，且**不许留下任何探针文件**
    _g_verdict = MS._is_writable_dir(_g_tmp)
    _g_left = [n for n in os.listdir(_g_tmp) if 'probe' in n]

    # 把 os.access 打桩成"记录并返回 True"，断言快路径确实被咨询过
    os.access = lambda p, m: (_g_access_hits.append((p, m)), True)[1]
    _g_fast = MS._is_writable_dir(_g_tmp)
    os.access = _saved_access

    # 最硬的一条：让 **任何删除都抛异常**。走快路径的实现仍判可写；
    # 老实现会走到 os.remove → 抛 → 返回 False（误判"盘不可写"→ 记忆被搬去兜底）。
    os.access = _saved_access

    def _boom(*a, **k):
        raise OSError('delete blocked by test')

    os.remove = _boom
    _g_no_del = MS._is_writable_dir(_g_tmp)
finally:
    os.access, os.remove = _saved_access, _saved_remove
    shutil.rmtree(_g_tmp, ignore_errors=True)

ok('G2 健康目录：判可写且不留 .write_probe 残留', _g_verdict is True and not _g_left,
   '%s left=%s' % (_g_verdict, _g_left))
ok('G3 快路径确实被咨询（os.access 调用次数 ≥1）', len(_g_access_hits) >= 1,
   len(_g_access_hits))
ok('G4 删除被禁也不会误判不可写（老实现会返回 False → 记忆被错误搬去桌面兜底）',
   _g_no_del is True, _g_no_del)

# ---- G5：强制 RALSEI_MEMORY_DIR 时 find_device_dir 必须**短路**，一个探针都不落
_g_env_saved = {k: os.environ.get(k) for k in (MS.ENV_DIR, MS.ENV_NO_DEVICE)}
_g_forced = tempfile.mkdtemp(prefix='ralsei_g13_forced_')
_g_scan_hits = []
_saved_access2 = os.access
try:
    os.environ[MS.ENV_DIR] = os.path.join(_g_forced, 'RalseiMemory')
    os.access = lambda p, m: (_g_scan_hits.append(p), True)[1]
    _g_dev = MS.find_device_dir(create=True)
    _g_short_circuit = (_g_dev == os.environ[MS.ENV_DIR] and not _g_scan_hits)
finally:
    os.access = _saved_access2
    for _k, _v in _g_env_saved.items():
        if _v is None:
            os.environ.pop(_k, None)
        else:
            os.environ[_k] = _v
    shutil.rmtree(_g_forced, ignore_errors=True)

ok('G5 强制 RALSEI_MEMORY_DIR 时 find_device_dir 短路返回（不扫盘、不落探针）',
   _g_short_circuit, 'access-hits=%d' % len(_g_scan_hits))

# ---- G6：run_all.py 的隔离清单必须存在、且只包含真实套件 id（不许写错名字静默失效）
_run_all_path = os.path.join(ROOT, 'code-quality-audit', 'regress', 'run_all.py')
_g_run_all = strip_all_ws(open(_run_all_path, encoding='utf-8').read())
ok('G6 run_all.py 有 HERMETIC_IDS 且被 run_suite 消费（不是定义了没人用）',
   'HERMETIC_IDS' in _g_run_all and _g_run_all.count('HERMETIC_IDS') >= 2,
   _g_run_all.count('HERMETIC_IDS'))

_g_regress_dir = os.path.dirname(_run_all_path)
if _g_regress_dir not in sys.path:
    sys.path.insert(0, _g_regress_dir)
import run_all as RA                                              # noqa: E402

_g_all_ids = {s['id'] for s in RA.SUITES}
ok('G7 HERMETIC_IDS ⊆ 套件表（写错 id 会静默不隔离 → 又回去删 E 盘）',
   set(RA.HERMETIC_IDS) <= _g_all_ids,
   sorted(set(RA.HERMETIC_IDS) - _g_all_ids))
ok('G8 会实例化 App / 触碰存储的套件都在隔离清单里（round13 自己 + 第八轮三个 + round9_focus）',
   {'round13_build', 'round8_floor', 'round8_fling', 'round8_dialogue',
    'round9_focus'} <= set(RA.HERMETIC_IDS),
   sorted(RA.HERMETIC_IDS))

# ============================================================
print('')
print('-' * 68)
print('第十三轮建楼（遮挡/层数/层序）验证：%d/%d PASS, %d FAIL'
      % (len(PASS), len(PASS) + len(FAIL), len(FAIL)))
for n in FAIL:
    print('  FAIL: %s' % n)
sys.exit(0 if not FAIL else 1)
