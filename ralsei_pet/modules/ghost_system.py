# -*- coding: utf-8 -*-
u"""幽灵线 · **纯逻辑层**（第67轮；L1，零依赖，可离线回归）。

「零依赖」的口径（回归锁 A2~A5 逐条守着）
--------------------------------------------------
= **只 import 标准库**（`math` / `os` / `io` / `json`）
+ **零项目内 import**（不 import Qt、不 import `data_store`/`memory_*` —— 那是初始化环）
+ **零函数内 import**（函数内 import 会把"本模块依赖什么"变成运行时才知道的事）
★ 首版把 `io`/`json`/`os` 写在 `save_to()` **函数体内**，被 A5 判据逮到并改正。

用户口径（第64轮原话，第66轮补裁定）
--------------------------------------------------
> 「我把 chara 改了一下，就**用红与黄.apk 里面的幽灵**就好，**只有决心强的人能看到幽灵**
>   （**ralsei 是个特例**）」（第64轮）
> N1：「**从上轮 N1 开始，用和 kris 等人接触的时间算吧**」
>     —— ★ 用户**改了口径**：原建议是"Ralsei↔用户信任度"，改成**与 Kris 等人接触的时间**。
> N2：「**N2 定点距离**」⇒ 幽灵 alpha 照抄原作的**定点距离式**。
> N3：「`sprites/ghost/` 接线时机**你来看就好**」⇒ 我定：**本轮就接线**。

这个模块只回答两件事
--------------------------------------------------
1. **幽灵有多清楚**（alpha）——★ **逐字照抄**《红与黄》`obj_ghostint2` 的 `Step_1`
   （证据：`第64轮…/_evidence/gml64/gml_Object_obj_ghostint2_Step_1.gml`）。
2. **谁能看得见**（门槛 + 亮/暗档）——★ **本项目扩展**，因为原作的轴是 LV/杀戮，
   而用户把"决心"重新定义成**与 Kris 等人接触的时间**。

★ 与原作**方向不一致**的一处，必须记住（第67轮查证；**首版曾写错，见下**）
--------------------------------------------------
**两只**定点幽灵都带销毁门槛，而且**都是"杀戮 / LV"方向**的：

`obj_ghostint2.Create_0`（Chara，本项目照抄的那只）：
```gml
if (instance_exists(obj_mainchara)) { if (obj_mainchara.kill == 1) { instance_destroy(); } }
if (room == room_area1 && global.flag[19] > 0) { instance_destroy(); }
if (room == room_fire_restaurant) { if (!instance_exists(obj_sansdate3)) { instance_destroy(); } }
```

`obj_ghostint.Create_0`（Clover）在以上几条之外，还有一条更直白的：
```gml
if (global.flag[7] == 1 || scr_murderlv() >= 12) { instance_destroy(); }
```

⇒ 原作轴统一是「**杀过人 / LV 高 ⇒ 幽灵消失**」，而用户要的是
「**决心强 ⇒ 看得见**」（正向）。两者**方向相反**。⇒ 处置：**机制形状照抄、
轴换成用户口径**，并在报告里如实标注为本项目扩展（记忆 §9：用户口径优先于我
的技术判断）。

❗ **首版 docstring 曾写「Chara 的 `obj_ghostint2` 在 Create 里没有任何门槛」——
这是假事实**（凭印象写的，没回原文核）。第67轮做回归锁 B 段、逐条回
`_evidence/gml64/gml_Object_obj_ghostint2_Create_0.gml` 时被自己的判据逮到。
⇒ 记在这里：**照抄清单里的每个"没有/恒为"都要有原文行号**，否则不许写。

照抄清单（每个数字都能回原文，回归锁 D 段逐条验）
--------------------------------------------------
| 量 | 值 | 原文出处 |
|---|---|---|
| 看得见的距离 | `dist < 100` | `Step_1` |
| 距离式 alpha | `10 / (dist + 1)`，封顶 `0.9` | `Step_1` |
| 走远淡出 | 每帧 `-0.05` | `Step_1` |
| 亮档 / 暗档 | `0.9` / `0.6` | `Step_1`（cutscene 分支） |
| 上下浮动 | 每帧 `0.1`，范围 `starty ± 2` | `Step_1` |
| 定点幽灵不播动画 | `image_speed = 0` | `Create_0` |
| 表情帧默认值 | `0`（"其余 → 0"） | `Step_1` 表情映射的兜底分支 |

★ 为什么用**固定帧 0**：`obj_ghostint2` 的 8 个 `image_index` 由 `obj_face_chara`
（Chara 的表情对象）映射而来 —— 本项目**没有这套表情系统**，所以取**原文自己的兜底分支**
（"其余 → 0"）而不是自造一个帧；
`image_speed = 0` 也说明**定点幽灵本来就不播放动画**（这与"随便循环 8 帧"是两回事）。
"""
import io
import json
import math
import os

# ---------------------------------------------------------------- 常量：照抄原作
#: `dist < 100` 才开始显形 —— 照抄 `obj_ghostint2.Step_1`。
GHOST_NEAR_DIST = 100.0
#: 距离式的封顶 alpha —— 照抄 `if (disto > 0.9) disto = 0.9;`。
GHOST_DIST_ALPHA_MAX = 0.9
#: 走远时每帧淡出的步长 —— 照抄 `image_alpha -= 0.05`。
GHOST_FADE_STEP = 0.05
#: 亮档 / 暗档 —— 照抄 cutscene 分支里的 `0.9` 与 `0.6`。
GHOST_BRIGHT_ALPHA = 0.9
GHOST_DIM_ALPHA = 0.6
#: 上下浮动：每帧 0.1、范围 `starty ± 2` —— 照抄 `Step_1`。
GHOST_LEVITATE_STEP = 0.1
GHOST_LEVITATE_RANGE = 2.0
#: 定点幽灵**不播放动画** —— 照抄 `Create_0` 的 `image_speed = 0`。
GHOST_IMAGE_SPEED = 0.0
#: 表情帧的兜底值 —— 照抄 `Step_1` 表情映射（先 `image_index = 0` 再逐条覆盖）。
GHOST_FRAME_DEFAULT = 0
#: dt 上限（与 `soul_entity.MAX_DT` 同口径：本模块被别处调用时也不会被大 dt 放大）。
MAX_DT = 0.1

# ---------------------------------------------------------------- 常量：本项目扩展（N1）
#: 「决心」满值所需接触秒数 —— ★ **自创**。取 3 小时：幽灵该是**长期相处的产物**，
#: 不是装上就能看见的背景物；同时它是"亮档"的门槛（见 `gate`）。
CONTACT_BRIGHT_SECONDS = 3.0 * 3600.0
#: 非特例"开始看得见"所需接触秒数 —— ★ **自创**。取 30 分钟 = 满值的 1/6，
#: 让"看不见 → 暗 → 亮"三档在时间轴上分布得不均匀（前松后紧，符合"越到后面越难"）。
CONTACT_SEE_SECONDS = 30.0 * 60.0
#: 「Ralsei 是个特例」—— 他不是靠决心，**始终至少看得见暗档**。
#: ★★ **本项目扩展**（原作里没有 Ralsei，`幽灵机制64.md` §3 已标注）。
RALSEI_SPECIAL = True

#: 「和 Kris 等人接触」里的"等人"= Deltarune 主角团（Ralsei 自己是宠物，不算）。
#: 只认 id，不认显示名 —— 与 `npc_system` 的 id 体系一致。
CONTACT_IDS = ('kris', 'susie', 'lancer')

_GATES = ('hidden', 'dim', 'bright')


# ---------------------------------------------------------------- 1. 距离式 alpha（照抄）


def _safe_float(v, default=0.0):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return float(default)
    if math.isnan(f) or math.isinf(f):
        return float(default)
    return f


def alpha_for_distance(dist):
    u"""`dist < 100` 时的 alpha = `min(10/(dist+1), 0.9)` —— 逐字照抄 `Step_1`。

    `dist` 非法/为负 ⇒ 按 0 处理（= 贴脸，返回封顶值），**不抛**。
    """
    d = _safe_float(dist, 0.0)
    if d < 0.0:
        d = 0.0
    v = 10.0 / (d + 1.0)
    if v > GHOST_DIST_ALPHA_MAX:
        v = GHOST_DIST_ALPHA_MAX
    return v


def step_alpha(alpha, dist, cap=GHOST_DIST_ALPHA_MAX, step=GHOST_FADE_STEP):
    u"""推进一帧 alpha，**逐字照抄** `obj_ghostint2.Step_1` 的三分支：

    ```gml
    else if (dist < 100) { disto = 10/(dist+1); if (disto > 0.9) disto = 0.9; image_alpha = disto; }
    else if (image_alpha > 0) { image_alpha -= 0.05; }
    else { image_alpha = 0; }
    ```

    ★ 与原作的**唯一**差别 = `cap`：原文把封顶写死 `0.9`，这里由**档位**给
    （`0.9` 亮 / `0.6` 暗 / `0.0` 看不见）。这不是自造 —— 原文的 `0.9` 本来就是
    "亮档"那个常量（`幽灵机制64.md` §1 已实证 `0.9 = 亮 / 0.6 = 暗`），
    所以"把封顶换成档位"是把**同一个常量**接到了决心的轴上。
    """
    a = _safe_float(alpha, 0.0)
    d = _safe_float(dist, 1e9)
    c = _safe_float(cap, GHOST_DIST_ALPHA_MAX)
    st = abs(_safe_float(step, GHOST_FADE_STEP))
    if c < 0.0:
        c = 0.0
    if d < GHOST_NEAR_DIST:
        return min(alpha_for_distance(d), c)      # 原文：直接赋值，不插值
    if a > 0.0:
        return max(0.0, min(c, a - st))           # 原文：每帧 -0.05
    return 0.0                                    # 原文：else image_alpha = 0


# ---------------------------------------------------------------- 2. 上下浮动（照抄）


def step_levitate(y, starty, goup, simplecheck,
                  step=GHOST_LEVITATE_STEP, span=GHOST_LEVITATE_RANGE):
    u"""上下浮动一帧，**逐字照抄** `Step_1` 的四行（含 `goup` / `simplecheck` 的翻转）。

    ★ 原文的判定顺序**不能调换**（先 `y += 0.1`、再判上界、再 `y -= 0.1`、再判下界）。
    ★★ **实测结果是不对称的**：`y ∈ [starty-2.0, starty+1.9]`，活动区间 **3.9** 而不是 4.0。
    原因就在这个顺序里 —— 到顶那一帧刚 `+0.1` 触到 `+2.0`，紧接着的 `if (goup == 0) y -= 0.1`
    又在**同一帧**把它减回 `+1.9`；而到底那一帧的 `-0.1` 恰好落在 `-2.0` 上，不会被回补。
    ⇒ 这是**原文语句顺序的产物**，不是我们的 bug。按「一切根据原作」**照抄、不"修正"**，
    但必须写在这里 —— 否则下一个人会把它当缺陷去"修"，反而破坏等价性。
    （首版注释曾写成"实测振幅恰 4.0"，是**凭印象写的假事实**，第67轮探针实测后改正。）

    :return: `(y, goup, simplecheck)`
    """
    yy = _safe_float(y, 0.0)
    sy = _safe_float(starty, 0.0)
    up = 1 if _safe_float(goup, 0) else 0
    sc = 1 if _safe_float(simplecheck, 1) else 0
    st = abs(_safe_float(step, GHOST_LEVITATE_STEP))
    sp = abs(_safe_float(span, GHOST_LEVITATE_RANGE))

    if up == 1:
        yy += st
    if yy >= (sy + sp) and not sc:
        up = 0
        sc = 1
    if up == 0:
        yy -= st
    if yy <= (sy - sp) and sc:
        up = 1
        sc = 0
    return yy, up, sc


# ---------------------------------------------------------------- 3. 决心（N1，本项目扩展）


def determination(contact_seconds):
    u"""接触时长 → 决心 `0.0 ~ 1.0`。★★ **本项目扩展**（原作没有"接触时间"这个量）。

    线性、饱和在 `CONTACT_BRIGHT_SECONDS`：满值之后不再涨（否则长期挂机会把
    数值推到无穷，日志和调试都没法看）。负值/非法一律按 0。
    """
    s = _safe_float(contact_seconds, 0.0)
    if s <= 0.0:
        return 0.0
    if CONTACT_BRIGHT_SECONDS <= 0.0:
        return 1.0
    return max(0.0, min(1.0, s / CONTACT_BRIGHT_SECONDS))


def gate(contact_seconds, ralsei_special=RALSEI_SPECIAL):
    u"""决定"看不看得见、看得多清" ⇒ `'hidden' | 'dim' | 'bright'`。

    | 条件 | 非特例 | Ralsei（特例） |
    |---|---|---|
    | `sec < 30min` | `hidden` | **`dim`**（★ 特例 = 不靠决心也看得见） |
    | `30min ≤ sec < 3h` | `dim` | `dim` |
    | `sec ≥ 3h` | `bright` | `bright` |

    ★★ 「Ralsei 是特例」是**本项目扩展**（原作没有 Ralsei）。
    保留 `ralsei_special=False` 这条通路不是摆设 —— 回归锁用它做**对照控制**
    （同一输入、只有特例开关不同 ⇒ 输出必须不同），否则"特例"这件事**无法被测到**。
    """
    s = _safe_float(contact_seconds, 0.0)
    if ralsei_special:
        if s >= CONTACT_BRIGHT_SECONDS:
            return 'bright'
        return 'dim'
    if s >= CONTACT_BRIGHT_SECONDS:
        return 'bright'
    if s >= CONTACT_SEE_SECONDS:
        return 'dim'
    return 'hidden'


def alpha_cap(gate_key):
    u"""档位 → alpha 封顶。`hidden` 返 `0.0`（= 彻底看不见）。未知档位按 `hidden`。"""
    if gate_key == 'bright':
        return GHOST_BRIGHT_ALPHA
    if gate_key == 'dim':
        return GHOST_DIM_ALPHA
    return 0.0


def is_gate(key):
    return key in _GATES


# ---------------------------------------------------------------- 4. 接触时钟（N1 的输入）


def is_contact_npc(npc_id):
    u"""这个 NPC 算不算「Kris 等人」—— 纯函数，便于回归。

    只认 `CONTACT_IDS`；大小写与空白做宽松归一（用户/上游传 'Kris ' 也不该算错）。
    """
    try:
        s = str(npc_id or '').strip().lower()
    except Exception:
        return False
    return s in CONTACT_IDS


def contact_from_npcs(present_ids):
    u"""桌面上在场的一批 NPC id → 本帧**是否处于接触状态**（任一主角团成员在场即可）。"""
    if not present_ids:
        return False
    try:
        return any(is_contact_npc(i) for i in present_ids)
    except Exception:
        return False


class ContactClock(object):
    u"""累计「与 Kris 等人接触的时间」。**不 import data_store**（调用方注入路径 / 提供字典），
    与 `relationship.Relationship` 同一条纪律：底层模块不反向依赖存储层。

    只认**在场时长**，不认"聊了几句" —— 用户的口径是"**接触的时间**"，
    所以这里是纯计时器：`tick(dt, contact=True/False)`。
    """

    VER = 1

    def __init__(self, seconds=0.0, now=None):
        self._total = max(0.0, _safe_float(seconds, 0.0))
        self._now = None if now is None else _safe_float(now, 0.0)

    # -------- 读口 --------
    @property
    def total(self):
        return self._total

    @property
    def determination(self):
        return determination(self._total)

    def gate(self, ralsei_special=RALSEI_SPECIAL):
        return gate(self._total, ralsei_special=ralsei_special)

    def to_dict(self):
        return {'contact_seconds': round(float(self._total), 3), 'ver': self.VER}

    def load(self, d):
        u"""从字典恢复。非法/缺字段一律**保持现值**，不抛（与 `Relationship.load` 同口径）。"""
        try:
            if isinstance(d, dict):
                v = _safe_float(d.get('contact_seconds'), None)
                if v is not None and v >= 0.0:
                    self._total = v
        except Exception:
            pass
        return self

    def save_to(self, path):
        u"""原子写。失败静默返回 False（**绝不因为"记不上时间"而影响宠物运行**）。

        ★ `io` / `json` / `os` 一律**顶层 import** —— 本模块的纪律是「L1 零依赖 +
          **零函数内 import**」（函数内 import 会把"这个模块依赖什么"变成运行时
          才知道的事，静态检查就失效了）。第67轮回归锁 A2/A5 守着这两条：
          首版把这三个写在函数里，被自己的判据逮到。
        """
        if not path:
            return False
        try:
            d = os.path.dirname(os.path.abspath(path))
            if d and not os.path.isdir(d):
                os.makedirs(d)
            tmp = path + '.tmp'
            with io.open(tmp, 'w', encoding='utf-8') as f:
                f.write(json.dumps(self.to_dict(), ensure_ascii=False, indent=2))
            os.replace(tmp, path)
            return True
        except Exception:
            return False

    # -------- 写口 --------
    def tick(self, dt, contact=True):
        u"""推进一帧。`contact=False` ⇒ **完全不计**（这是它存在的全部意义：
        宠物独自待着的时间不该涨决心）。返回累计秒数。"""
        if not contact:
            return self._total
        d = _safe_float(dt, 0.0)
        if d <= 0.0:
            return self._total
        if d > MAX_DT:
            d = MAX_DT
        self._total += d
        return self._total

    def describe(self):
        u"""**仅供日志/调试**。"""
        g = self.gate()
        return u'接触=%.0fs 决心=%.3f 档位=%s' % (self._total, self.determination, g)


# ---------------------------------------------------------------- 5. 定点幽灵状态


class GhostState(object):
    u"""一只**定点**幽灵的全部状态（对应原作 `obj_ghostint2`）。

    它的位置是**固定的**（`home_x/home_y`），只有 `y` 在 `starty ± 2` 里漂——
    这正是"定点"的含义：**不是跟着宠物跑**，而是宠物走近了它才清晰
    （用户 N2 选的就是这条）。
    """

    def __init__(self, home_x=0.0, home_y=0.0, contact_seconds=0.0,
                 ralsei_special=RALSEI_SPECIAL):
        self.home_x = _safe_float(home_x, 0.0)
        self.home_y = _safe_float(home_y, 0.0)
        self.x = self.home_x
        self.y = self.home_y
        #: 浮动的基准点 —— 照抄 `starty = y`（`Create_0`）。
        self.starty = self.home_y
        self.goup = 0
        self.simplecheck = 1
        #: alpha 初值 0（原文 `Create_0` 不设 `image_alpha` ⇒ GameMaker 默认 1，
        #: 但 `Step_1` 的 `else { image_alpha = 0; }` 会在第一帧把远距离的压到 0。
        #: 我们**从 0 起**，避免"刚出现就闪一下满亮度"这个原文里不存在的观感。）
        self.alpha = 0.0
        self.contact = ContactClock(contact_seconds)
        self.ralsei_special = bool(ralsei_special)

    # -------- 读口 --------
    @property
    def gate(self):
        return self.contact.gate(ralsei_special=self.ralsei_special)

    @property
    def cap(self):
        return alpha_cap(self.gate)

    @property
    def visible(self):
        return self.alpha > 0.001 and self.gate != 'hidden'

    @property
    def frame(self):
        u"""定点幽灵**不播动画** ⇒ 恒为 `GHOST_FRAME_DEFAULT`（照抄兜底分支）。"""
        return GHOST_FRAME_DEFAULT

    def distance_to(self, px, py):
        return math.hypot(_safe_float(px) - self.x, _safe_float(py) - self.y)

    def describe(self):
        return u'x=%.1f y=%.1f alpha=%.3f 档=%s | %s' % (
            self.x, self.y, self.alpha, self.gate, self.contact.describe())

    # -------- 写口 --------
    def step(self, dt, px=None, py=None, contact=None):
        u"""推进一帧：先接触计时（可选），再 alpha，再浮动。

        :param dt: 帧时长（秒），内部钳到 `MAX_DT`
        :param px,py: 宠物**中心**坐标；给 `None` ⇒ 视为"无穷远"（alpha 只减不增）
        :param contact: `None` ⇒ 保留调用方在别处 tick 过的状态（不重复计）
        :return: `(alpha, y)` 是否发生变化
        """
        d = _safe_float(dt, 0.0)
        if d > MAX_DT:
            d = MAX_DT
        if contact is not None:
            self.contact.tick(d, contact=bool(contact))

        if px is None or py is None:
            dist = float('inf')
        else:
            dist = self.distance_to(px, py)

        old_a = self.alpha
        self.alpha = step_alpha(self.alpha, dist, cap=self.cap)

        old_y = self.y
        self.y, self.goup, self.simplecheck = step_levitate(
            self.y, self.starty, self.goup, self.simplecheck)
        return (abs(self.alpha - old_a) > 1e-9) or (abs(self.y - old_y) > 1e-9)

    def respawn(self, home_x, home_y):
        u"""重新定点（换屏 / 重新摆放）。**同时重置 `starty`**（照抄 `Create_0`）。"""
        self.home_x = _safe_float(home_x, 0.0)
        self.home_y = _safe_float(home_y, 0.0)
        self.x = self.home_x
        self.y = self.home_y
        self.starty = self.home_y
        self.goup = 0
        self.simplecheck = 1
        self.alpha = 0.0
        return True
