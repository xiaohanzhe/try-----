# -*- coding: utf-8 -*-
"""桌面 4 扇世界门的**屏幕层**摆位（第112轮续）。

用户口径（逐字）
----------------
「**放到屏幕边缘哦**」
「**不是，那个门你单独放在外面呗**」（追问「门和场景画面的关系」时的回答）
「**只桌面场景时，固定贴屏**」（追问「具体是哪种」时的回答）
「**各用原尺寸**」（追问「四扇门大小怎么定」时的回答）

⇒ 由此确定的产品口径
--------------------
1. **门不参与房间画面的缩放**。房间画面由 `fit_fraction` 决定（第110轮「砍半」= 0.5），
   门的贴图**按自己的原始像素尺寸**直接画在**屏幕坐标**上（用户「各用原尺寸」）。
   ★ 为什么必须这样：第110轮把画面砍半后，门的「房间边缘」落到了屏幕「中间」
   （2560×1600 屏上画面只占 1066×800、居中于 (747,400)）—— 用户看到的正是这个。
   把门从房间图层里**拿出来**，它才可能真贴屏幕边框。
2. **只在桌面场景显示**（用户「只桌面场景时，固定贴屏」）。
3. **四扇门贴屏幕四边中点**：正上 OneShot、正下 Niko 的家、正左 UT、正右 三角符文。
   ★ 与 `desktop.json` 的房间坐标摆位**同一套字母 ↔ 方位映射**（A 上 / B 下 / C 左 / D 右），
     只是换算到屏幕坐标后**不再乘房间缩放**。

零依赖
------
只用标准库。可被回归套件直接 import（同 `door_reveal` / `possession` 规格）。
★ 本模块**不读文件、不认识 Qt**：贴图尺寸由调用方（宿主经 `assets.sprite_size`）
   送进来 —— 保证「尺寸唯一真源」仍在资产缓存那一处。

屏幕坐标口径
------------
返回的矩形是**画布（= 整块屏幕）坐标**的 `(x, y, w, h)`，`x/y` = **左上角**。
★ 与 `scene_camera.fit_fraction` 返回的 `(w, h, ox, oy)` 不同：那里 `(ox, oy)` 是
  **偏移**，这里是**绝对左上角**。两种口径混用是本项目最贵的一类错，故函数名与
  返回键都写明 `_rect`。
"""

#: 四个方位 → 门字母（与 `desktop.json` 的房间摆位、`_routes.json` 的 `when_door` 同源）。
#: ★ 改这里等于改"门在哪条边"，**别在调用点另写一份映射**。
SIDE_LETTERS = (
    ('top', 'A'),      # OneShot
    ('bottom', 'B'),   # Niko 的家
    ('left', 'C'),     # UT
    ('right', 'D'),    # 三角符文
)

#: 门与**屏幕物理边缘**的留白（像素）。★ 默认 0 = 真贴边。
#: 用户「挨着屏幕边框」⇒ 0 是最忠实的读法；留白只作为"贴边太生硬"时的可调项。
EDGE_MARGIN = 0

#: 四扇门**共同**的缩放系数（1.0 = 各用原尺寸，用户「各用原尺寸」）。
#: ★ 保留这个旋钮是为了"万一贴边后显得太大"能一处收敛，而不是散落魔法数。
#: ★★ 第112轮续二：这是**兜底**倍率 —— 传了 `pet_box` 时走 `fit_door_scale()`
#:    逐门重算（门对齐 Ralsei 量级），这里的值只在"拿不到宠物盒"时生效。
DOOR_SCALE = 1.0

#: ★★★ 第112轮续三：门相对**宠物外接盒**的尺寸上限（用户「门的尺寸和 ralsei 的尺寸
#: **调换一下差不多**」＋「**门的稍微大一点**」）。
#: 口径：**统一倍率** —— 四扇门用**同一个 `k`** 等比放大（用户「**按原作等比放大**」），
#:   `k` 取"让**最大的那扇**恰好落进 `Ralsei 盒 × DOOR_FIT_CAP`"的值。
#:   · `1.0` = 最大的门与 Ralsei 一样大
#:   · `1.2` = 最大的门比 Ralsei 略大一圈（用户补的「稍微大一点」）
#: ★★ 为什么**必须统一倍率**（这一版的核心修正）：
#:   上一个版本是**逐门**算倍率（`min(cap·Rw/dw, cap·Rh/dh)`）⇒ 每扇门都顶到
#:   "高度 = Ralsei×1.2" ⇒ **四扇门全变成 188 高** ⇒ 原作里"OneShot 门小、
#:   三角符文门巨大"的**大小关系被磨平**。用户要的恰恰是「**按原作**等比放大」：
#:   门与 Ralsei 的**比例关系**、以及门**彼此之间**的大小关系，都要照原作。
#:   ⇒ 统一 `k` 是唯一能同时满足这两条的取法（逐门算必然破坏后者）。
#: ★ 为什么用"最宽者/最高者取较小"来定 `k`：这样**没有任何一扇**越出
#:   `Ralsei 盒 × cap`（外接盒口径），而所有门之间的关系仍是原作关系。
DOOR_FIT_CAP = 1.2

#: ★★★ 第112轮续三：Ralsei **标准体量**的逻辑盒（单位 = 原作逻辑像素）。
#: 口径 = **idle 动画组的容器尺寸**（= 该组所有帧的最大尺寸），真机实测 = **69×47**
#: （`deltarune_ralsei/spr_ralsei_idle_*.png` 5 帧全是 69×47）。
#: ★ 为什么取 idle 组而不是行走帧（21×41）：
#:   产品里宠物的**屏幕显示尺寸** = `动画组容器 × scale_factor`（`main.py`
#:   L15280-15289 的 `_anim_container_size`）。idle 组容器 69×47 ⇒ 2560×1600 屏上
#:   **229×156**；用户「两个尺寸调换一下差不多」看的就是**静止的 Ralsei**，
#:   所以基准必须是他**实际看到的那个体量**，而不是行走帧的 21×41。
#: ★ 为什么需要这个常量（**本轮抓到的真 bug**）：原来宠物盒取 `sprite_label.width()`
#:   —— 那是**当前动画组**的尺寸，运行期在 **229×156（idle 69×47）↔ 63×133
#:   （19×40 的帧）** 之间跳 ⇒ **门跟着一跳一跳变大小**。门尺寸该由"宠物**标准
#:   体量**"决定，不该由"此刻在播哪一组动画"决定。
PET_BOX_LOGICAL = (69, 47)

#: ★★★ 第112轮续四：Ralsei **在屏幕上最长边的硬上限**（像素）。
#: 用户口径（逐字）：「**宠物最多 1.5 个文件夹大小**」。
#: 追问后确认口径 ⇒ **1.5 × 桌面图标本体 96px = 144px**（用户选"按图标本体 96"）。
#: ★ 本机实测（2560×1600 @150%，`SPI_GETICONMETRICS` / `WindowMetrics`）：
#:   · 桌面图标**格子** = 113×113（`IconSpacing=-1130` twips ÷15 ×1.5）
#:   · 桌面图标**本体** ≈ 96px（Explorer 大图标 @150%）
#:   ⇒ 用户选了"图标本体"这一档 ⇒ **144px**。
#: ★ 为什么写成"最长边"而不是宽/高各自上限：
#:   不同动画组的宽高比不同（idle 69×47 = 1.47 宽扁；walk_down 30×40 = 0.75 竖长），
#:   统一约束**最长边**才能保证"任何动画下宠物都不会大过 1.5 个文件夹"。
#: ★ 为什么这是**屏幕像素**而非逻辑像素：用户看的是桌面上的观感
#:   （和桌面图标比大小），所以必须在"屏幕像素"这个空间比较。
PET_MAX_LONG_SIDE_PX = 144


def clamp_scale_factor_for_max_side(scale_factor, logical=PET_BOX_LOGICAL,
                                    max_side=PET_MAX_LONG_SIDE_PX):
    """把宠物渲染倍率**钳到**"最长边 ≤ `max_side`"（第112轮续四）。

    用户口径：「**宠物最多 1.5 个文件夹大小**」⇒ `max_side = 144px`。

    :param scale_factor: 期望倍率（`camera.scale × pet_scale`）。
    :param logical: 宠物逻辑体量 `(w, h)`（默认 `PET_BOX_LOGICAL` = idle 组 69×47）。
    :param max_side: 允许的最大最长边（像素）。
    :return: 钳后的倍率 `float`（**只减不增** —— 本来就小的不放大）；
        非法输入 ⇒ 原样返回 `scale_factor`（不抛，调用方自己兜底）。

    ★ 算法：`cap = max_side / max(logical_w, logical_h)`；返回 `min(scale_factor, cap)`。
      · **只减不增**：宠物本来就小（比如用户把 `pet_scale` 调到 0.4）时不该被"撑大"
        —— 用户要的是**上限**，不是固定值。
    ★ 为什么不做成"直接返回 cap"：那会把宠物锁成固定尺寸，
      用户在设置面板里调小就完全失效（违背 `PET_SCALE_MIN/MAX` 那套已有自由度）。
    """
    try:
        k = float(scale_factor)
        lw = float(logical[0])
        lh = float(logical[1])
        ms = float(max_side)
    except (TypeError, ValueError, IndexError):
        return scale_factor
    if not (k > 0.0) or k != k:          # <=0 / NaN ⇒ 原样（不猜）
        return scale_factor
    if lw <= 0 or lh <= 0 or ms <= 0:
        return scale_factor
    _long = lw if lw > lh else lh
    cap = ms / _long
    return k if k <= cap else cap


def pet_screen_box(scale_factor, logical=PET_BOX_LOGICAL):
    """Ralsei 在屏幕上的**标准**外接盒 `(w, h)`（不随动画组变化）。

    :param scale_factor: 宠物渲染倍率（`main._cached_scale_factor`
        = `camera.scale × pet_scale`）。
    :param logical: 原作的逻辑体量（默认 `PET_BOX_LOGICAL` = **69×47**，= idle 组容器）。
    :return: `(round(69×k), round(47×k))`；非法输入 ⇒ 返回 `None`
        （调用方据此退回 `sprite_label` 兜底，**不抛、不猜**）。
    """
    try:
        k = float(scale_factor)
    except (TypeError, ValueError):
        return None
    if not (k > 0.0) or k != k:          # <=0 / NaN
        return None
    try:
        lw, lh = float(logical[0]), float(logical[1])
    except (TypeError, ValueError, IndexError):
        return None
    if lw <= 0 or lh <= 0:
        return None
    return (int(round(lw * k)), int(round(lh * k)))


def fit_doors_uniform_scale(sizes, pet_box, cap=DOOR_FIT_CAP):
    """四扇门共用的**统一**等比缩放系数（第112轮续三）。

    用户口径（逐字）：「**门的尺寸和 ralsei 的尺寸调换一下差不多**」＋
    「**门的稍微大一点**」＋「**按原作等比放大**」。

    :param sizes: `{letter: (w, h)}` —— 参与的门（只含能取到尺寸的）。
    :param pet_box: 宠物在**屏幕上的**标准外接盒 `(w, h)`。
    :param cap: 允许的最大倍数（`1.2` ⇒ 最大的门 = 宠物盒 × 1.2）。
    :return: `float` 统一倍率（> 0）；非法/空输入 ⇒ `DOOR_SCALE`（**不抛、不返 0**）。

    ★★★ 为什么是**统一**倍率而不是逐门算（本轮修正的核心）：
      逐门算 `min(cap·pw/dw, cap·ph/dh)` ⇒ 每扇门都会顶到"高 = 宠物高 × cap"
      ⇒ **四扇门全成同一高度** ⇒ 原作里"OneShot 门小、三角符文门巨大"的
      **大小关系被磨平**。用户要的是「按原作等比放大」——即门与 Ralsei 的比例、
      以及门**彼此之间**的比例，都照原作。只有统一 `k` 能同时满足这两条。

    算法：`k = min( cap·pet_w / max(door_w),  cap·pet_h / max(door_h) )`
      · 两个轴各算"让**最大的那扇**刚好贴到上限"的倍率，取较小者
        ⇒ **没有任何一扇**超出 `宠物盒 × cap`。
      · 刻意**不做上限钳位**（不用 `min(1, k)`）：小的门该长大、大的门该缩下。
    """
    if not isinstance(sizes, dict) or not sizes:
        return DOOR_SCALE
    try:
        pw = float(pet_box[0])
        ph = float(pet_box[1])
        c = float(cap)
    except (TypeError, ValueError, IndexError):
        return DOOR_SCALE
    if pw <= 0 or ph <= 0 or c <= 0 or c != c:
        return DOOR_SCALE
    max_w = 0.0
    max_h = 0.0
    for _sz in sizes.values():
        try:
            dw = float(_sz[0])
            dh = float(_sz[1])
        except (TypeError, ValueError, IndexError):
            continue
        if dw <= 0 or dh <= 0:
            continue
        if dw > max_w:
            max_w = dw
        if dh > max_h:
            max_h = dh
    if max_w <= 0 or max_h <= 0:
        return DOOR_SCALE
    k = min(c * pw / max_w, c * ph / max_h)
    if not (k > 0.0) or k != k:     # <=0 / NaN
        return DOOR_SCALE
    return k


def fit_door_scale(door_size, pet_box, cap=DOOR_FIT_CAP):
    """**单扇门**相对宠物盒的等比缩放系数（保留：`plan_screen_doors` 不传
    `pet_box` 时的逐门口径 / 单独调用场景）。

    ★ 产品主路径已改用 `fit_doors_uniform_scale()`（用户「按原作等比放大」）——
      本函数保留是因为：① 它仍是"单扇门 vs 宠物盒"这个**局部问题**的正确解，
      测试与外部调用可能单独用到；② 删掉会让 `plan_screen_doors(pet_box=...)`
      的语义变模糊。★ 两者的差别**只在于是否统一倍率**，算法内核一致。

    :return: `float`（> 0）；非法输入 ⇒ `DOOR_SCALE`（**不抛、不返 0**）。
    """
    try:
        dw = float(door_size[0])
        dh = float(door_size[1])
        pw = float(pet_box[0])
        ph = float(pet_box[1])
        c = float(cap)
    except (TypeError, ValueError, IndexError):
        return DOOR_SCALE
    if dw <= 0 or dh <= 0 or pw <= 0 or ph <= 0 or c <= 0:
        return DOOR_SCALE
    if c != c:                      # NaN
        return DOOR_SCALE
    s = min(c * pw / dw, c * ph / dh)
    if not (s > 0.0) or s != s:     # <=0 / NaN
        return DOOR_SCALE
    return s


def door_screen_rect(side, size, screen_w, screen_h,
                     margin=EDGE_MARGIN, scale=DOOR_SCALE):
    """一扇门的**屏幕矩形** `(x, y, w, h)`。

    :param side: `'top'` / `'bottom'` / `'left'` / `'right'`（其它值 ⇒ `None`）。
    :param size: 门的原始像素尺寸 `(w, h)`（来自 `assets.sprite_size`）。
    :param screen_w: 屏幕宽（画布宽）。`:param screen_h:` 屏幕高。
    :param margin: 与屏幕物理边缘的留白（像素，>=0）。
    :param scale: 共同缩放（<=0 / 非数 ⇒ 用 `DOOR_SCALE`）。
    :return: `(x, y, w, h)`；任何非法输入 ⇒ `None`（**不伪装成 0 尺寸矩形**）。

    摆位规则（四边**中点**，即"门的中心与屏幕边的中点对齐"）：
      · top    → 水平居中，`y = margin`
      · bottom → 水平居中，`y = screen_h - h - margin`
      · left   → 垂直居中，`x = margin`
      · right  → 垂直居中，`x = screen_w - w - margin`
    """
    if side not in ('top', 'bottom', 'left', 'right'):
        return None
    try:
        sw = float(screen_w)
        sh = float(screen_h)
        w0 = float(size[0])
        h0 = float(size[1])
        m = float(margin)
    except (TypeError, ValueError, IndexError):
        return None
    if sw <= 0 or sh <= 0 or w0 <= 0 or h0 <= 0:
        return None
    if m != m or m < 0:                     # NaN / 负数
        m = float(EDGE_MARGIN)
    try:
        s = float(scale)
    except (TypeError, ValueError):
        s = DOOR_SCALE
    if not (s > 0.0) or s != s:             # <=0 / NaN
        s = DOOR_SCALE

    w = max(1, int(round(w0 * s)))
    h = max(1, int(round(h0 * s)))
    sw_i = int(round(sw))
    sh_i = int(round(sh))
    m_i = int(round(m))

    if side == 'top':
        x = (sw_i - w) // 2
        y = m_i
    elif side == 'bottom':
        x = (sw_i - w) // 2
        y = sh_i - h - m_i
    elif side == 'left':
        x = m_i
        y = (sh_i - h) // 2
    else:                                   # right
        x = sw_i - w - m_i
        y = (sh_i - h) // 2

    # ★ 钳进屏幕（贴边的门比屏幕还大时**不越界**：宁可缩到屏幕内，也不要画到屏幕外
    #   —— 画到屏幕外的那部分是"用户永远看不见的门"，比"小一点"更糟）。
    if x < 0:
        x = 0
    if y < 0:
        y = 0
    if x + w > sw_i:
        x = max(0, sw_i - w)
    if y + h > sh_i:
        y = max(0, sh_i - h)
    return (x, y, w, h)


def plan_screen_doors(sizes, screen_w, screen_h,
                      margin=EDGE_MARGIN, scale=DOOR_SCALE,
                      letters=None, pet_box=None):
    """四扇门的屏幕摆位清单 ⇒ `[(letter, (x, y, w, h)), ...]`。

    :param sizes: `{letter: (w, h)}` —— 只含**能取到尺寸**的门（取不到的跳过，不猜）。
    :param letters: 收敛到哪几个字母（默认 `SIDE_LETTERS` 的全部）。
        ★ 这是一个**过滤**，不是重排：返回顺序恒为 `SIDE_LETTERS` 的声明序
          （可复现，回归可逐条比对）。
    :param pet_box: ★★★ 第112轮续二/续三 —— 宠物在**屏幕上的**标准外接盒 `(w, h)`。
        给了它就**统一**走 `fit_doors_uniform_scale()`（所有门用**同一个**倍率，
        用户「门的尺寸和 ralsei 的尺寸调换一下差不多」＋「按原作等比放大」）；
        给 `None` 则退回全局 `scale`（= "各用原尺寸"的老行为，老调用点零变化）。
        ★ 为什么是**统一**倍率：逐门算会把"每扇门顶到同一高度"⇒ 原作的
          大小关系被磨平（见 `fit_doors_uniform_scale` 的 docstring）。
    :return: 列表；`sizes` 为空 / 非法 ⇒ `[]`（**不抛**）。
    """
    out = []
    if not isinstance(sizes, dict) or not sizes:
        return out
    try:
        want = set(letters) if letters else None
    except TypeError:
        want = None
    # ★ 统一倍率（所有门共用）；`pet_box` 为 None ⇒ 用传入的全局 `scale`。
    _s_uniform = scale
    if pet_box is not None:
        _s_uniform = fit_doors_uniform_scale(sizes, pet_box)
    for side, letter in SIDE_LETTERS:
        if want is not None and letter not in want:
            continue
        got = sizes.get(letter)
        if not isinstance(got, (list, tuple)) or len(got) != 2:
            continue
        r = door_screen_rect(side, got, screen_w, screen_h,
                             margin=margin, scale=_s_uniform)
        if r:
            out.append((letter, r))
    return out
