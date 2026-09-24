# -*- coding: utf-8 -*-
"""相机 —— 「人物走到中间后一直居中，背景相对运动」。

用户原话（第44轮裁定）
----------------------
    「操控效果是游戏里那种人物走到中间后一直居中然后背景相对运动
      还是背景固定？我更倾向原作的那种，代码用原作的参考就好」

⇒ 答案是**前者**：原作就是「居中式相机跟随 + 背景/瓦片/实例同坐标系反向运动」。
  本模块就是它的落地。

★★★ 原作依据（第43轮已实证，见 第43轮-原作门与相机取证）
----------------------------------------------------------------------
原作**不是视差（parallax）**，是**相机平移**：

  · ch1 的 1,014 个房间图层里，`HSpeed` / `VSpeed` 非零 = **0 个**，
    `Layer.EffectType` 恒 `null` ⇒ 背景层与瓦片层与实例**共用一个坐标系**，
    没有"背景动得慢一点"这回事。
  · 相机用 GMS2 **原生相机系统**（`camera_create` / `camera_set_view_target` /
    `camera_set_view_border` / `camera_set_view_pos` / `camera_set_view_size`），
    全部包在 `gml_GlobalScript___view_set_internal` 里（该脚本 ins=0，
    是 GMS 内建包装；真正的逐帧跟随在 `obj_mainchara` 的 Step）。
  · 相机尺寸：**暗世界 640×480**（1:1）；**现实世界 320×240**（再 ×2 输出）。
  · `GMS2FPS = 30` ⇒ 跟随是**每帧硬跟随**（无插值平滑），配四向边界钳制。

本模块的语义 = 这三条的直接翻译
--------------------------------
  `Camera.follow(target_rect, room_rect)` 给出「要画哪一块」：
    1. **目标居中**（`camera_set_view_target` 的默认行为）；
    2. **四向钳制**（相机不得越过房间边界 ⇒ 贴边时角色不再居中，
       这正是原作里"走到地图边缘人物就偏离中心"的真实表现）；
    3. **房间比相机小 → 居中显示**（原作里小房间不抖动，直接摆中间）。

零依赖纪律（🔴 与 scene_system / scene_routing 同源，违反会崩在 import 期）
--------------------------------------------------------------------------
本模块**禁 import Qt、禁 import 任何项目内模块**（只准标准库）。
原因见 `scene_system.py` 的模块 docstring：`main.py` 在 import 期就要
`from modules.scene_controller import SceneController`，控制器会 import 本模块；
回头 import 项目内模块就会把「初始化环」接上（已踩 4 次）。

三条设计律（与 scene_system 同源）
----------------------------------
1. **算不出 → 返回 `None`，不伪装成"(0,0)"** —— 静默降级是本项目头号敌人。
2. **越界一律钳，不报错** —— 房间比相机小是合法情形（原作里到处是）。
3. **纯函数优先** —— `camera_rect()` / `clamp()` 不持有状态，可单独测；
   只有 `Camera` 这个薄壳持有"当前值"，供渲染层读。
"""
import logging

_log = logging.getLogger(__name__)

#: 暗世界相机尺寸（原作 1:1）。现实世界是 320×240（再 ×2 输出，见 §43）。
DEFAULT_CAMERA_SIZE = (640, 480)

#: 死区（deadzone）= 0 ⇒ **目标永远居中**（不是"走进死区才推相机"）。
#: 原作 `camera_set_view_border` 在普通房间用 0；这条常量是那个 0 的名字，
#: 写出来是为了让"为什么角色总在正中间"这句话在代码里有出处。
DEFAULT_BORDER = 0


def clamp(value, low, high):
    """把 `value` 钳进 `[low, high]`。

    `high < low` 时返回 `low`（而非报错）—— 对应"房间比相机小"这种**合法**情形，
    此时相机位置没有自由度，只能贴住一侧；调用方随后会用 `center_rect` 覆盖它。
    """
    if high < low:
        return low
    if value < low:
        return low
    if value > high:
        return high
    return value


def camera_rect(room_rect, cam_size, target_rect=None, border=DEFAULT_BORDER,
                prev_cam=None):
    """算「相机该对准哪一块房间」→ `(left, top, width, height)`；算不出 → `None`。

    :param room_rect: 房间矩形 `(left, top, right, bottom)`（原作房可以是负坐标）。
    :param cam_size: 相机尺寸 `(w, h)`。
    :param target_rect: 跟随目标矩形（角色的包围盒）。`None` = 只做居中/钳制。
    :param border: 死区半宽。0 = 目标永远居中（原作普通房间口径）。
    :param prev_cam: **上一帧**的相机矩形。给死区用 —— 死区的定义是"相机保持
        不动直到目标偏出"，所以必须知道相机现在在哪。`border>0` 而不给
        `prev_cam` 时退化为"直接居中"（无死区），这是安全的默认：
        宁可多动，不要漏动。

    语义（逐条对应原作调用）
    ------------------------
    1. 相机尺寸不小于 1×1（`cam_size` 非法 → `None`，不伪装）。
    2. 有目标：相机中心对准目标中心（`camera_set_view_target`）。
       给了 `prev_cam` 且 `border>0` → **死区语义**：目标中心在
       「上一帧相机中心 ± border」内时相机**不动**；偏出才推到死区边缘。
    3. **四向钳制**：相机不得越出房间。房间比相机窄/矮 → 该轴**居中**摆放
       （`center_rect` 分支，原作小房间的表现）。
    """
    if not room_rect or len(room_rect) != 4:
        return None
    rl, rt, rr, rb = [float(v) for v in room_rect]
    if rr < rl or rb < rt:
        return None
    if not cam_size or len(cam_size) != 2:
        return None
    cw, ch = float(cam_size[0]), float(cam_size[1])
    if cw < 1 or ch < 1:
        return None

    room_w = rr - rl
    room_h = rb - rt

    # --- 该轴：房间比相机小 → 居中（原作小房间不抖动）---
    def _axis(room_lo, room_len, cam_len, target_lo, target_len, prev_lo):
        if room_len <= cam_len:
            return room_lo + (room_len - cam_len) / 2.0
        if target_lo is None:
            # 没目标：默认贴房间左上（调用方通常会传 target）
            return room_lo
        t_center = target_lo + target_len / 2.0
        want = t_center - cam_len / 2.0          # 目标居中
        if border > 0 and prev_lo is not None:
            # ★ 死区（`camera_set_view_border`）的正确语义：
            #   相机**保持不动**，直到目标中心偏出「相机中心 ± border」——
            #   偏出了才把相机推到刚好把目标收进死区边缘。
            #   ⚠️ 不能用"重算出的中心"去比（那等于每帧都居中，死区恒不生效 ——
            #      本套件 B7 首跑就是这样抓到 bug 的：border=50 仍移动了 5px）。
            prev_center = prev_lo + cam_len / 2.0
            if t_center < prev_center - border:
                want = (t_center + border) - cam_len / 2.0
            elif t_center > prev_center + border:
                want = (t_center - border) - cam_len / 2.0
            else:
                want = prev_lo                     # 死区内 → 相机不动
        return clamp(want, room_lo, room_lo + room_len - cam_len)

    tl = tt = None
    if target_rect and len(target_rect) == 4:
        tl, tt = float(target_rect[0]), float(target_rect[1])
        tw = float(target_rect[2]) - tl
        th = float(target_rect[3]) - tt
    else:
        tw = th = 0.0

    cam_left = cam_top = None
    if prev_cam and len(prev_cam) == 4:
        cam_left, cam_top = float(prev_cam[0]), float(prev_cam[1])

    new_left = _axis(rl, room_w, cw, tl, tw, cam_left)
    new_top = _axis(rt, room_h, ch, tt, th, cam_top)
    return (new_left, new_top, cw, ch)


def world_to_view(point, cam):
    """把房间坐标 `(x, y)` 翻成**视口坐标**（相对相机左上角）。

    这就是"背景相对运动"的实现：角色在世界里走，相机跟着走，
    于是**房间里的东西在屏幕上的位置 = 世界坐标 − 相机坐标**。
    背景与瓦片与实例都用这一个变换 ⇒ 三者天然同步（原作零视差的算术表达）。
    """
    if not point or len(point) < 2 or not cam:
        return None
    return (float(point[0]) - float(cam[0]), float(point[1]) - float(cam[1]))


def view_rect_in_world(cam):
    """相机覆盖的世界矩形 `(left, top, right, bottom)` —— 渲染层的裁剪框。"""
    if not cam or len(cam) != 4:
        return None
    return (cam[0], cam[1], cam[0] + cam[2], cam[1] + cam[3])


def scale_rect(rect, factor):
    """把矩形按 `factor` 等比放大（用户要的「房间放大些」）。

    以矩形**左上角**为锚点放大：因为房间左上是世界的原点，
    照此放大后 `world_to_view` 仍然成立（相机同步放大即可）。
    `factor <= 0` → 原样返回（不静默改成 1.0 以外的值，避免"看着生效其实没生效"）。
    """
    if not rect or len(rect) != 4:
        return rect
    try:
        f = float(factor)
    except (TypeError, ValueError):
        return rect
    if f <= 0:
        return rect
    l, t, r, b = rect
    return (l * f, t * f, r * f, b * f)


class Camera(object):
    """相机薄壳 —— 只持有"当前值"，算法全在上面三个纯函数里。

    ⚠️ 与 `SceneController` 同一条纪律：**本类不注册定时器、不做插值动画**。
       原作是每帧硬跟随（`GMS2FPS=30`、无平滑），所以这里也**不做缓动** ——
       加缓动会让桌面宠物"飘"，且与原作手感不符。
    """

    def __init__(self, size=DEFAULT_CAMERA_SIZE, border=DEFAULT_BORDER, scale=1.0):
        self._size = (int(size[0]), int(size[1]))
        self._border = int(border)
        self._scale = float(scale) if scale and scale > 0 else 1.0
        self._cam = None          # 最近一次 camera_rect() 的结果

    # ---- 只读属性 ----
    @property
    def size(self):
        return self._size

    @property
    def border(self):
        return self._border

    @property
    def scale(self):
        """房间放大系数（用户要的「房间放大些」）。1.0 = 原始尺寸。"""
        return self._scale

    @property
    def rect(self):
        """当前相机矩形；从未 follow 过 → `None`（不伪装成 (0,0,..)）。"""
        return self._cam

    def set_size(self, size):
        if size and len(size) == 2 and size[0] >= 1 and size[1] >= 1:
            self._size = (int(size[0]), int(size[1]))

    def set_border(self, border):
        try:
            self._border = int(border)
        except (TypeError, ValueError):
            pass

    def set_scale(self, scale):
        try:
            f = float(scale)
        except (TypeError, ValueError):
            return
        if f > 0:
            self._scale = f

    def scoped_size(self):
        """相机**在逻辑坐标里**的窗口尺寸 = `size ÷ scale`。

        ★★★ 第 44 轮的坐标系推导（本模块唯一容易写错的地方）
        --------------------------------------------------
        约定：**世界 / 相机 / 物件 —— 全部逻辑坐标；放大只发生在输出那一步。**

            `像素 = 逻辑 × scale`

        那么"屏幕上要铺满 `size` 像素"意味着相机要看到多少**逻辑**范围？

            `逻辑范围 = size / scale`

        ⇒ 相机窗口（逻辑） = `size / scale`。

        举例（本项目的实际取值，极易验证）：
          · 输出想占 640×480 像素、scale = 2.0
            → 相机逻辑窗口 = 320×240
            → 现实世界房间正好也是 320×240 → **房间恰好铺满一屏**，相机不需要移动。
            这与第 43 轮"现实世界 320×240 逻辑，×2 输出 = 640×480"**完全吻合**。

        曾经写错的两个版本（记录在此防回退）：
          (a) `size × scale` —— 相机逻辑窗口变成 1280×960，比房间还大 ⇒
              相机"居中"到房间外，物件坐标算出界，被剔除（本套件 D5a 抓到的 bug）。
          (b) 让 `scale` 同时乘世界与相机 —— 两者同比，scale 约掉，
              "放大"在屏幕上**毫无变化**。

        ⚠️ `scale` 非法（≤0 / 非数）时不放大，按 1.0 处理（`__init__` 已归一）。
        """
        s = self._scale if self._scale > 0 else 1.0
        return (int(round(self._size[0] / s)), int(round(self._size[1] / s)))

    def follow(self, room_rect, target_rect):
        """更新相机：跟随 `target_rect`，钳在 `room_rect` 内。返回新相机矩形或 `None`。

        调用方（渲染层）在**每帧**调它 —— 与 `obj_mainchara` 的 Step 同频。
        `self._cam`（上一帧结果）会作为死区基准传下去。

        ★ 全程**逻辑坐标**（不乘 scale）—— 见 `scoped_size()` 的修正说明。
        """
        self._cam = camera_rect(room_rect, self.scoped_size(), target_rect,
                                self._border, prev_cam=self._cam)
        return self._cam

    def to_view(self, point):
        """逻辑坐标 → **视口逻辑坐标**（相对相机左上角）。相机未 follow → `None`。

        这就是「背景相对运动」：`视口 = 世界 − 相机`。渲染壳再乘 `scale` 得像素。
        """
        if self._cam is None:
            return None
        return world_to_view(point, self._cam)

    def to_view_rect(self, rect):
        """逻辑矩形 → **视口逻辑矩形** `(l, t, r, b)`（给背景/瓦片/实例用）。"""
        if self._cam is None or not rect or len(rect) != 4:
            return None
        l = rect[0] - self._cam[0]
        t = rect[1] - self._cam[1]
        return (l, t, l + (rect[2] - rect[0]), t + (rect[3] - rect[1]))

    def visible_world_rect(self):
        """相机当前覆盖的**逻辑**世界矩形 —— 裁剪用。"""
        return view_rect_in_world(self._cam)

    def describe(self):
        """单行中文摘要（日志/自省用）。没 follow 过 → 说清"还没跟随"。"""
        if self._cam is None:
            return '相机未跟随（追随者尚未给出目标）'
        return ('相机 (%.0f, %.0f) %dx%d%s'
                % (self._cam[0], self._cam[1], self._cam[2], self._cam[3],
                   '（放大 ×%.2f）' % self._scale if self._scale != 1.0 else ''))
