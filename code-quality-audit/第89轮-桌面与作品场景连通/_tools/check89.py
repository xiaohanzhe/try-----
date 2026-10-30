# -*- coding: utf-8 -*-
u"""第89轮回归锁：**桌面 ↔ 作品场景连通**（用户硬门槛「先能让我看到场景可以切换再继续」）。

用户口径（逐字）
----------------
* 「**接入场景系统吧因为我到现在都没看到能切换场景的门那类的**
   （当然，如何接入，何时接入，先做哪部分你来决定就好）」（第89轮）
* 「**先能让我看到场景可以切换再继续**」（第89轮）
* 「把原作的世界搬到桌面上…**桌面也是一个场景**」（第38轮）
* 「一切根据原作」（第38轮）

本轮做的事（四层断点，逐层定位 + 逐层修）
------------------------------------
① **菜单恒空** —— `reachable_destinations` 的「同章」过滤遇到 desktop（**只有 1 间**）
   ⇒ 恒返回 0；菜单 `if dests:` 判空 ⇒「去…」根本不出现。
   ⇒ 改**两段式**：同章内其它场景 + **跨章/跨作品入口**（`_entry_scenes`），
     且跨章入口**插头部**（否则 `[:limit]` 一截就把「回桌面」截掉）。
② **`scene_id` 精确匹配缺失** —— `scene_pathfind._match_tier` 的档位最细只到"名字尾段"，
   传**完整 scene_id**（如 `ch1.kris_room.kris_s_room`）反而零命中 ⇒ `travel_to` 报
   "没有场景匹配"。⇒ 加 **`-1` 档（最强）** + `_TIER_NONE=3` 命名常量，
   `resolve_target` 入选条件从 `t >= 0` 改 `t < _TIER_NONE`。
   ★★ **首版踩的坑**：只加档位、不改入选条件 ⇒ `-1` 被 `t >= 0` 整条排除 ⇒
     "给了精确 id 反而静默不选"（比报错更隐蔽）。
③ **桌面无房间几何** —— `desktop` 无 `original_room_id` ⇒ `plan_viewport` 返 `(0,0)`
   ⇒ 什么都画不出来。⇒ 加 `original_room_id: -1` + `_room_geometry.json` 的 `desktop:-1`。
④ **相机尺寸选错** —— 房间 `640×480` 比相机（`scoped_size` = 640/2 = **320×240**）大
   ⇒ 相机去追宠物（宠物在世界里被归一化到 ~(628,480)），静止时视野约 `x∈[468,628]`
   ⇒ 排在前面的门**全在视野外**（实测 `plan objs=0`）。
   ⇒ 房间改 **320×240**（= 相机逻辑窗口）⇒ `camera_rect` 走 `center_rect` 分支
     ⇒ **相机固定不跟随** ⇒ 门的位置稳定可预测。

段一览（★ 计数随轮次变，以**当前真源**为准）
------
  A ★★★ 桌面门的数据面（**第109轮起 4 扇 · 字母 A~D**（OneShot/Niko家/UT/Deltarune）· pos 全在房间内 · 贴图真在盘且尺寸一致）
  B ★★★ 路由表（4 条 `when_scene=='desktop'` · 目标逐条可解析）
  C ★★★ `_match_tier` 的 **`-1` 档**（product 真调 · 完整 id 命中最强档 · 别名仍工作）
  D ★★★ 菜单不空（`reachable_destinations` 跨章入口在**且排在头部** · 桌面 ≥4 条）
  E ★★★ 渲染计划（真机：`plan objs=4` · rect 尺寸 = 贴图×scale · 全在视口内）
  F ★★★ 推门真切场景（`build_props` 建 **4 个门道具** = 第111轮起 **3 `DoorProp` + 1 `NikoHomeDoorProp`（Niko 的家 · 彩蛋 · 永远进不去）** ·
    F1a 总数 / F1b 类名分解 / **按门字母推 A 与 D 门** ⇒ `travel_to` 真改 `scene_id`）
  G ★★ 旧行为不回归（负控制：非桌面场景不加跨章入口 / 未知 id 仍不命中 / 空 room 仍返 0）
  H 判据自身体检（被测文件在盘 · 记账守恒 · 计数守恒鉴别力）

★ 轮次变更记录（判据随口径演进，**不是漂移而是同步**）
  * **第109轮**：桌面门从 **9 扇（A~F/W/X/Y）** 重做为 **4 扇（A~D）**——A=OneShot(正上) ·
    B=Niko 的家(正下) · C=UT(正左) · D=Deltarune(正右)。判据全部改成从 `_A_DOOR_WORLD` 现推。
  * **第111轮**：4 扇门里 **B（Niko 的家）变成彩蛋门** —— 产品侧 `build_props` 收到 `on_egg`
    时建的是 `NikoHomeDoorProp`（`target_scene` 恒 `None` ⇒ **结构上永不切场景**），
    收不到 `on_egg` 时**根本不建**（"不造假门"）。
    ⇒ F 段拆 F1a（总数）/ F1b（**恰好 1 扇彩蛋门 + 其余普通门**）；
    ⇒ 探针 `build_props` **必须镜像产品调用点**（传 `on_egg` 只观测桩），否则只能看到 3 扇（夹具不保真）；
    ⇒ `_push` 从**按下标**改为**按门字母**（彩蛋门 `target_scene=None` ⇒ 旧下标假设失效）。
  * **第124轮**：桌面 C 门（UT）落点 `ut.rooms.room_start` → **`ut.rooms.room_area1`**。
    `room_start` 是原作下标 0 的**空壳/标题房**（无门、无物、出边 0）⇒ 从桌面进 ut
    **一间接不到**（实测可达 1 间）；`room_area1`（原作下标 **4**）可达 33 间。
    ⇒ `_A_DOOR_WORLD['C']` 与 `B4b` 的描述改 `room_area1`；
    ⇒ **`B4c` 的 `_room_want['C']` 由 0 改正为 4**（0 是标题屏，从来不是"坠落处"）。

★ 判据纪律：`print('[PASS] %s')` 字面量；判据名里不自带标记；正/负控制成对；
  **断行为不断赋值**；★★ **判据本身也是被测物**（第62~70 轮反复栽在判据侧）
  ⇒ 每条关键判据配负控制；★★★ **探针必须走产品真路径**
  （本轮实测：我调 `plan_frame(tick=0)` **漏传 `sprite_size`** ⇒ rect 退化成 (1,1)
   ⇒ 差点误判"贴图尺寸丢了"。产品真路径见 `main.py:_update_scene_layer`）。
★ 零网络 / 零 UI / 需要真机 `RalseiPet()`（相机要 `follow` 过才出计划）⇒ 进 `HERMETIC_IDS`。
"""

import ast
import io
import json
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')
if PKG not in sys.path:
    sys.path.insert(0, PKG)
# ★ `scene_pathfind` 等模块历史上用**扁平导入**（`from scene_system import ...`）⇒
#   必须把 `modules/` 也放进 sys.path（与 `run_all.py` 的 hermetic 环境一致）。
_MODS = os.path.join(PKG, 'modules')
if _MODS not in sys.path:
    sys.path.insert(0, _MODS)

SCENES = os.path.join(PKG, 'assets', 'scenes')
MAIN = os.path.join(PKG, 'src', 'main.py')
CTRL = os.path.join(PKG, 'modules', 'scene_controller.py')
PATHF = os.path.join(PKG, 'modules', 'scene_pathfind.py')
DESKTOP = os.path.join(SCENES, 'desktop.json')
GEOM = os.path.join(SCENES, '_room_geometry.json')
ROUTES = os.path.join(SCENES, '_routes.json')

from modules import scene_pathfind as SP        # noqa: E402

_failed = []
_n_pass = [0]
_n_fail = [0]
_n_lines = [0]


def check(desc, cond, star=False):
    mark = ' ★' if star else ''
    if cond:
        print('[PASS]%s %s' % (mark, desc))
        _n_pass[0] += 1
    else:
        print('[FAIL]%s %s' % (mark, desc))
        _n_fail[0] += 1
        _failed.append(desc)
    _n_lines[0] += 1


def _read(path):
    try:
        with io.open(path, 'r', encoding='utf-8') as fh:
            return fh.read()
    except Exception:
        return ''


def _ast(path):
    try:
        return ast.parse(_read(path))
    except Exception:
        return None


def _load(path):
    try:
        with io.open(path, 'r', encoding='utf-8') as fh:
            return json.load(fh)
    except Exception:
        return None


# ================================================================ A. 桌面门数据面
# ★★ 第99轮：门数**只在这里声明一次**（`_LETTERS_WANT`），其余判据全部由它取数。
#   第89轮时这里写死了 12 处 `8` ⇒ 第99轮加第 9 扇门（Outertale）时**同一件事改了 12 遍**，
#   且漏改一处就会"看着在守其实守不到"。字母集是真源，数量是它的派生值。
#
# ★★★ 第109轮重做（**推翻第89/99轮的 9 扇**）：用户口径
#   「**不是桌面只有一扇门，是只有连接各个游戏也就是三角符文，oneshot，ut的门，
#    对了，有个例外，niko的家也在（记住这4个门挨着屏幕边框）**」
#   ＋ 10-10 原话「**桌面连通光世界小镇中心，oneshot中niko第一次出现的房子下方的
#    那个车厢，ut中人类坠落的地方**」＋ 10-11 三答「**正上（oneshot），正下（niko家），
#    正左（ut），正右（三角符文）**」。
#   ⇒ 桌面**只 4 扇门**：A=OneShot · B=Niko 的家 · C=UT · D=三角符文（Deltarune）。
#   字母 ↔ 世界（第109轮起，**这是唯一真源**）：
_A_DOOR_WORLD = {
    'A': ('oneshot', 'oneshot.mainline.INIT'),   # 正上：Niko 第一次出现的房子下方的车厢（原作 room 1）
    'B': ('oneshot', 'oneshot.mainline.Start'),  # 正下：Niko 的家（★ 彩蛋门，永远进不去）
    # ★★★ 第124轮修：C 门落点 `room_start` → **`room_area1`**。
    #   `room_start` 是原作**下标 0 的空壳/标题房**（实例只有 `obj_time` / `obj_layerchecker`，
    #   一个门都没有 ⇒ 出边 0）⇒ 从桌面进 ut 只能站着，**整个 UT 一间接不到**（实测可达 1 间）。
    #   真正的"人类坠落的地方"是 `room_area1`（出边 1 ⇒ ut 可达 33 间）。
    #   证据：`第115轮/_tools/graph115.py`「入口＝`room_area1` 非 `room_start`」·
    #        `第71轮/_tools/check71.py` D4「为什么不是 room_start」·
    #        `第120轮/check_bg120.py` 的 `BLANK` 集合含 `room_start`。
    #   ★★★ 第124轮重要更正：`room_area1` 的原作下标是 **4**（不是 0！）。
    #     实测 `ut_rooms.json`：0=room_start · 1=room_introstory · 2=room_introimage ·
    #     3=room_intromenu · **4=room_area1**（680×260，开局那片草地）。
    #     也就是说 **0~3 全是开场/标题屏**，`room_start` 从来不是"坠落处"。
    #     ⇒ 下面 `B4c` 的 `_room_want['C']` 必须从 0 改成 **4**。
    'C': ('ut', 'ut.rooms.room_area1'),          # 正左：人类坠落的地方（原作 room 4）
    'D': ('ch1', 'ch1.hometown.town_mid'),       # 正右：光世界小镇中心（原作 room 11）
}
_LETTERS_WANT = set(_A_DOOR_WORLD.keys())
_N_DOORS = len(_LETTERS_WANT)
_d = _load(DESKTOP) or {}
_doors = _d.get('objects') if isinstance(_d.get('objects'), list) else []
check('A1 ★★★ 桌面 %d 扇门（`desktop.json` 的 `objects`）' % _N_DOORS,
      len(_doors) == _N_DOORS, star=True)

# A1b ★★ 每扇门**每一项都有非空 `id` / `kind` / `sprite`**（★ 防"只数长度"的盲区）
#   ★ 鉴别力体检抓到的盲区（M1）：把某扇门的 `id` 改名 ⇒ `len()` 仍是同一个数 ⇒ A1/A2 全绿。
#     ⇒ 补一条**逐项字段完整性**判据。
_field_bad = []
for _i, _o in enumerate(_doors):
    if not isinstance(_o, dict):
        _field_bad.append('#%d 非 dict' % _i)
        continue
    for _k in ('id', 'kind', 'sprite'):
        _v = _o.get(_k)
        if not (isinstance(_v, str) and _v):
            _field_bad.append('#%d %s=%r' % (_i, _k, _v))
check('A1b ★★ %d 扇门**逐项字段完整**（`id`/`kind`/`sprite` 都非空 —— 防"只数长度"盲区）'
      % _N_DOORS,
      len(_doors) == _N_DOORS and not _field_bad, star=True)
if _field_bad:
    for _b in _field_bad[:4]:
        print('        %s' % _b)

# A2 门的 src 全是 `obj_door<字母>`，字母集合 = A~D（第109轮：4 扇，不重不漏）
_letters = []
for _o in _doors:
    _s = _o.get('src') if isinstance(_o, dict) else None
    if isinstance(_s, str) and _s.startswith('obj_door') and len(_s) == len('obj_door') + 1:
        _letters.append(_s[len('obj_door'):])
check('A2 ★★★ %d 扇门用**不重不漏**的 %d 个不同字母（第109轮起 = A~D：OneShot/Niko家/UT/Deltarune）'
      % (_N_DOORS, _N_DOORS),
      len(_letters) == _N_DOORS and set(_letters) == _LETTERS_WANT, star=True)
if set(_letters) != _LETTERS_WANT:
    print('        got=%r want=%r' % (sorted(_letters), sorted(_LETTERS_WANT)))

# A2b ★★★ 门 ↔ 世界 的映射与用户口径逐条对齐。
#   ★★★ 第112轮改版（用户逐字）：
#     「门也不是都长那样啊，而且摆放的位置也不在屏幕四周啊」
#     「ut 就用王座那个门」（终选 `bg_castle_realdoor`）
#     「三角符文门 → `spr_shortcut_door`」
#   ⇒ 口径从"4 扇同贴图、四边正中"改为"**各门各自贴图 + 各自位置**"。
#     A=OneShot（正上，spr_darkdoor 44×56）
#     B=Niko的家（正下，spr_darkdoor 44×56）
#     C=UT     （正左，ut_castle_realdoor 44×99 ⇒ 纵向居中 y=70）
#     D=三角符文（正右，spr_shortcut_door 36×52 ⇒ 纵向居中 y=94、横向贴右 284）
#   ★ 位置**仍是"贴屏幕四边"**（左/右/上/下各一），只是不再强求"同一 y/x 正中"
#     —— 高度不同的门要各自居中才"贴边且不越界"。
_pos_rule = {'A': (138, 0), 'B': (138, 184), 'C': (0, 70), 'D': (284, 94)}
#: ★ 每扇门各自的贴图（用户逐字指认）。None ⇒ 用通用 `spr_darkdoor_0.png`。
_sprite_rule = {
    'A': 'spr_darkdoor_0.png',
    'B': 'spr_darkdoor_0.png',
    'C': 'ut_castle_realdoor_0.png',
    'D': 'spr_shortcut_door_0.png',
}
_map_bad = []
for _o in _doors:
    if not isinstance(_o, dict):
        continue
    _s = _o.get('src') or ''
    _L = _s[len('obj_door'):] if _s.startswith('obj_door') else None
    _want_pos = _pos_rule.get(_L)
    _p = _o.get('pos')
    if _want_pos is None:
        _map_bad.append('字母 %r 不在 A~D 里' % _L)
        continue
    if not (isinstance(_p, (list, tuple)) and len(_p) == 2
            and (int(_p[0]), int(_p[1])) == _want_pos):
        _map_bad.append('%s 位置=%r 期望=%r' % (_L, _p, _want_pos))
check('A2b ★★★ 4 扇门的**字母 ↔ 位置**逐条等于口径'
      '（A 正上138,0/B 正下138,184/C 正左0,70/D 正右284,94）',
      not _map_bad, star=True)
if _map_bad:
    for _b in _map_bad[:4]:
        print('        %s' % _b)

# A2c ★★★ 每扇门的**贴图各自正确**（第112轮新增；防"位置对了但贴图还是同一张"）
_sp_bad = []
for _o in _doors:
    if not isinstance(_o, dict):
        continue
    _s = _o.get('src') or ''
    _L = _s[len('obj_door'):] if _s.startswith('obj_door') else None
    _want = _sprite_rule.get(_L)
    if _want is None:
        continue
    _got = _o.get('sprite')
    _anim = _o.get('anim') if isinstance(_o.get('anim'), dict) else None
    if _anim is not None:
        _got = os.path.basename(str(_anim.get('base') or '')) + '_0.png'
    if os.path.basename(str(_got or '')) != _want:
        _sp_bad.append('%s 贴图=%r 期望=%r' % (_L, _got, _want))
check('A2c ★★★ 每扇门的贴图各自等于指认（UT=王座门 / 三角符文=shortcut_door）',
      not _sp_bad, star=True)
if _sp_bad:
    for _b in _sp_bad[:4]:
        print('        %s' % _b)

# A3 房间几何存在且是 320×240（= 相机 scoped_size，相机固定不跟随）
_geo = _load(GEOM) or {}
_rooms = _geo.get('rooms') if isinstance(_geo.get('rooms'), dict) else {}
_rec = _rooms.get('desktop:-1')
check('A3 ★★★ 桌面虚拟房间 `desktop:-1` 存在且 = **320×240**'
      '（= 相机 scoped_size ⇒ 相机固定，门位置稳定）',
      isinstance(_rec, dict) and _rec.get('w') == 320 and _rec.get('h') == 240,
      star=True)
if isinstance(_rec, dict):
    print('        desktop:-1 = %r' % ({k: _rec.get(k) for k in ('w', 'h', 'name')},))

# A4 每扇门的 pos 是合法二元组，且**整扇门（pos + 贴图尺寸）**都落在房间内
#    ★ 门贴图尺寸从盘上真读（PNG IHDR），不写死。
import struct  # noqa: E402
_objs_dir = os.path.join(SCENES, 'objs')


def _png_size(fname):
    try:
        with open(os.path.join(_objs_dir, fname), 'rb') as fh:
            head = fh.read(33)
        if len(head) < 24 or head[:8] != b'\x89PNG\r\n\x1a\n':
            return None
        return struct.unpack('>II', head[16:24])
    except Exception:
        return None


_rw = (_rec or {}).get('w') if isinstance(_rec, dict) else None
_rh = (_rec or {}).get('h') if isinstance(_rec, dict) else None
_pos_bad = []
_sizes = {}
for _o in _doors:
    if not isinstance(_o, dict):
        continue
    _p = _o.get('pos')
    _sp = _o.get('sprite')
    if not (isinstance(_p, (list, tuple)) and len(_p) == 2):
        _pos_bad.append('%s: pos 非法 %r' % (_o.get('id'), _p))
        continue
    _sz = _png_size(os.path.basename(_sp)) if isinstance(_sp, str) else None
    _sizes[os.path.basename(_sp or '')] = _sz
    if _sz is None:
        _pos_bad.append('%s: 贴图读不到 %r' % (_o.get('id'), _sp))
        continue
    _x, _y = float(_p[0]), float(_p[1])
    if not (0 <= _x and _x + _sz[0] <= _rw and 0 <= _y and _y + _sz[1] <= _rh):
        _pos_bad.append('%s: pos=%r size=%r 越界 (房间 %rx%r)'
                        % (_o.get('id'), _p, _sz, _rw, _rh))
check('A4 ★★★ %d 扇门的 `pos` + 贴图尺寸**全部落在房间 320×240 内**（不越界）'
      % _N_DOORS,
      not _pos_bad, star=True)
if _pos_bad:
    for _b in _pos_bad[:4]:
        print('        %s' % _b)

# A5 负控制：A4 的判据有鉴别力（把 pos 推到房间外必须被判越界）
#   ★ 第109轮：锚点贴图名**由数据取**（`_sizes` 的第一项），不写死 —— 4 扇门
#     现在共用 `spr_darkdoor_0.png`（44×56），写死 `spr_doorA_0.png` 会取不到。
_sz_any = next(iter(_sizes.values()), None)
_bad_ok = False
if _rw and _rh and _sz_any:
    _out = float(_rw) + 10.0
    _bad_ok = not (0 <= _out and _out + _sz_any[0] <= _rw)
check('A5 负控制：A4 有鉴别力（pos 推到房间外必须判越界）', _bad_ok, star=True)

# A6 ★★★ 门贴图**每扇各自正确**（第112轮改版）。
#   用户逐字（第112轮）：「门也不是都长那样啊」「ut 就用王座那个门」
#     + 「三角符文门 → `spr_shortcut_door`」。
#   第109轮口径「4 扇都用 44×56 任意门」已被用户否定 ⇒ 本判据随之改成
#   **四张不同贴图，各自的真尺寸与盘上一致**（防回退成"四扇同图"）。
#   ★ 判据从"集合等于某个单元素字典"改为"每条 src→贴图 的尺寸都对得上"。
_A_DOOR_SPRITE_PX = _sizes.get('spr_darkdoor_0.png') or (44, 56)
_A_UT_SPRITE_PX = _sizes.get('ut_castle_realdoor_0.png') or (44, 99)
_A_SHORTCUT_SPRITE_PX = _sizes.get('spr_shortcut_door_0.png') or (36, 52)
#: 期望：字母 → (贴图真尺寸)。真尺寸从盘上 PNG IHDR 现读（`_sizes`），不写死。
_expect_px = {
    'A': _A_DOOR_SPRITE_PX,
    'B': _A_DOOR_SPRITE_PX,
    'C': _A_UT_SPRITE_PX,
    'D': _A_SHORTCUT_SPRITE_PX,
}
#: ★ 反向强断言：四张贴图**至少有两张不同**（否则"全都一样"能蒙混过关）。
_used_sprites = set()
for _o in _doors:
    if not isinstance(_o, dict):
        continue
    _s = str(_o.get('src') or '')
    _L = _s[len('obj_door'):] if _s.startswith('obj_door') else None
    _want = _sprite_rule.get(_L)
    if _want:
        _used_sprites.add(_want)
_px_bad = []
for _f, _want_px in (('spr_darkdoor_0.png', _A_DOOR_SPRITE_PX),
                     ('ut_castle_realdoor_0.png', _A_UT_SPRITE_PX),
                     ('spr_shortcut_door_0.png', _A_SHORTCUT_SPRITE_PX)):
    _got = _sizes.get(_f)
    if _got is None:
        _px_bad.append('%s 不在盘上' % _f)
    elif tuple(_got) != tuple(_want_px):
        _px_bad.append('%s 尺寸 %r != 期望 %r' % (_f, _got, _want_px))
check('A6 ★★★ 三张门贴图真在盘且尺寸正确'
      '（任意门 %s / UT 王座门 %s / 三角符文 shortcut_door %s）'
      % (_A_DOOR_SPRITE_PX, _A_UT_SPRITE_PX, _A_SHORTCUT_SPRITE_PX),
      not _px_bad, star=True)
if _px_bad:
    for _b in _px_bad[:4]:
        print('        %s' % _b)
check('A6c ★★★ 4 扇门**不再共用同一张贴图**（贴图种类 ≥ 3：用户「门也不是都长那样」）',
      len(_used_sprites) >= 3, star=True)
if len(_used_sprites) < 3:
    print('        实际上用到的贴图 = %r' % (sorted(_used_sprites),))

# A6b ★★ 反向：4 扇门**都不许**再用 20×20 的 `spr_door<字母>_0.png` 贴图
#   （那是"编辑器视角"的蓝框绿字母，原作玩家看不到 —— 见详版 §109.2 的 UTMT 实证）
_old_spr = [o.get('sprite') for o in _doors
            if isinstance(o, dict) and str(o.get('sprite') or '').startswith('objs/spr_door')]
check('A6b ★★ 4 扇门都不许再用 20×20 的 `spr_door<字母>_0.png`（蓝框绿字母已按原作隐藏）',
      not _old_spr, star=True)
if _old_spr:
    print('        仍在使用: %r' % (_old_spr,))

# ================================================================ B. 路由表
# ★★★ `_scene_pool` / `resolve_target` / 索引核对 —— 一律走 **`load_index()`**
#   （产品真入口，带 `ok`），**不是** `_index.json` 的原始 JSON。
#   首版 C 段直接 `json.load` 喂进 `_scene_pool` ⇒ 缺 `ok` ⇒ 返空 ⇒ 整片误报
#   （**判据用错入口** —— 第62~70轮反复栽的同一类坑）。
from modules import scene_system as SS        # noqa: E402
_INDEX = SS.load_index(SCENES)
check('B0 ★★ `load_index()` 真加载出索引（`ok=True` 且场景数 > 1000）',
      isinstance(_INDEX, dict) and _INDEX.get('ok') is True
      and len(_INDEX.get('scenes') or {}) > 1000, star=True)
if not (isinstance(_INDEX, dict) and _INDEX.get('ok') is True):
    print('        load_index -> ok=%r error=%r'
          % (_INDEX.get('ok') if isinstance(_INDEX, dict) else None,
             _INDEX.get('error') if isinstance(_INDEX, dict) else None))

_r = _load(ROUTES) or {}
_routes = _r.get('routes') if isinstance(_r.get('routes'), list) else []
_desktop_routes = [x for x in _routes if isinstance(x, dict)
                   and x.get('when_scene') == 'desktop']
check('B1 ★★★ 路由表有 **%d 条** `when_scene == "desktop"` 的规则'
      '（第89轮新增；本条不断言总数，只断桌面部份）' % _N_DOORS,
      len(_desktop_routes) == _N_DOORS, star=True)

# B2 这 N 条覆盖 A..F/W/X/Y 全部字母，且每条 `to` 非空
_rt_letters = sorted([x.get('when_door') for x in _desktop_routes])
check('B2 ★★★ %d 条桌面路由的 `when_door` = A~F/W/X/Y（与门一一对应）' % _N_DOORS,
      set(_rt_letters) == _LETTERS_WANT, star=True)
if set(_rt_letters) != _LETTERS_WANT:
    print('        got=%r' % (_rt_letters,))

# B3 ★★★ 每条 `to` 目标**真能在索引里解析**（不只看字符串非空）
#   ★★★ 用 `load_index()`（产品真入口，带 `ok`），不是 `_index.json` 原始 JSON ——
#     C 段首版就是拿原始 JSON 喂 `_scene_pool` ⇒ 缺 `ok` ⇒ 整片误报。
_all_scene_ids = set((_INDEX.get('scenes') or {}).keys())
_rt_bad = []
for _x in _desktop_routes:
    _to = _x.get('to')
    if not (isinstance(_to, str) and _to in _all_scene_ids):
        _rt_bad.append('%s -> %r' % (_x.get('when_door'), _to))
check('B3 ★★★ %d 条桌面路由的 `to` **逐条能在 `load_index()` 里查到**（不是写了不存在的目标）'
      % _N_DOORS,
      len(_all_scene_ids) > 1000 and not _rt_bad, star=True)
if _rt_bad:
    for _b in _rt_bad[:4]:
        print('        %s' % _b)

# B4 ★★★ 桌面门覆盖**三个世界** + Niko 的家（第109轮口径）
#   ★ 第89轮口径是"ut / uty / oneshot / outertale 各一条"（9 扇门的时代）；
#     第109轮用户把桌面收窄成 4 扇 ⇒ 覆盖变为 **Deltarune（ch1）/ OneShot / UT**
#     三门 + **Niko 的家**（既是 OneShot 世界、又是一扇**彩蛋门**）。
_targets = [x.get('to') or '' for x in _desktop_routes]
_cross = {'ch1': False, 'oneshot': False, 'ut': False}
for _t in _targets:
    for _k in _cross:
        if _t.startswith(_k + '.'):
            _cross[_k] = True
check('B4 ★★★ 桌面门覆盖**三个世界**（Deltarune 三角符文 / OneShot / Undertale）',
      all(_cross.values()), star=True)
if not all(_cross.values()):
    print('        %r targets=%r' % (_cross, _targets))

# B4b ★★★ 4 条路由的 `to` **逐条等于口径目标**（不只是"前缀对得上"）
#   ★ 防"把 C/D 的目标对调也能全绿"：把字母 ↔ 目标写死在这里比对。
_tgt_map = {L: v[1] for L, v in _A_DOOR_WORLD.items()}
_got_map = {}
for _x in _desktop_routes:
    _got_map[_x.get('when_door')] = _x.get('to')
_tgt_bad = {L: (_got_map.get(L), _tgt_map[L]) for L in _tgt_map if _got_map.get(L) != _tgt_map[L]}
check('B4b ★★★ 4 条桌面路由的字母 ↔ 目标**逐条等于口径**'
      '（A→oneshot.mainline.INIT · B→oneshot.mainline.Start · C→ut.rooms.room_area1 · D→ch1.hometown.town_mid）',
      not _tgt_bad, star=True)
if _tgt_bad:
    print('        不符: %r' % (_tgt_bad,))

# B4c ★★ "三个世界各自的起点"这一层也对齐（第109轮新口径的证据锚：
#   OneShot 门进的是**车厢** room 1 · UT 门进的是**坠落处** room 4 ·
#   三角符文门进的是**光世界小镇中心** room 11）
#   ★★★ 第124轮更正：`_room_want['C']` 原为 **0**，那是**错的** ——
#     `ut_rooms.json` 实测 0=room_start / 1=room_introstory / 2=room_introimage /
#     3=room_intromenu（**0~3 全是开场与标题屏**）· **4=room_area1**（680×260，真正第一间）。
#     ⇒ 改成 4。**这条判据此前一直绿，是因为它和 B4b 共享同一个错误假设**
#     （B4b 把落点写成 `room_start`，B4c 就把期望下标写成 0）——
#     **两条判据互证 ≠ 独立验证**，这是本项目第 124 轮最值得记的一条教训。
_room_want = {'A': 1, 'B': 2, 'C': 4, 'D': 11}
_room_bad = []
_SID2ROOM = {}
for _sid, _sv in (_INDEX.get('scenes') or {}).items():
    if isinstance(_sv, dict):
        _SID2ROOM[_sid] = _sv.get('original_room_id')
for _L, _want in _room_want.items():
    _sid = _tgt_map.get(_L)
    _got = _SID2ROOM.get(_sid)
    if _got != _want:
        _room_bad.append('%s %s room=%r 期望=%r' % (_L, _sid, _got, _want))
check('B4c ★★ 三个世界的落点房间号 = 原作真值（OneShot 车厢=1 · UT 坠落处=4 · 小镇中心=11）',
      not _room_bad, star=True)
if _room_bad:
    print('        %r' % (_room_bad,))

# B5 负控制：B3 的判据有鉴别力（编一个不存在的目标必须被判定失败）
_fake_to = 'ch1.nope.nope'
check('B5 负控制：B3 有鉴别力（不存在的 scene_id 必须判失败）',
      _fake_to not in _all_scene_ids, star=True)

# ================================================================ C. `_match_tier` 的 -1 档
# ★★★ 断行为不断赋值：真调产品函数。
#   ★★ 本轮探针错过的坑：`_match_tier(rec, want_low, kws)` 的第一参是
#     **场景池条目**（`_scene_pool()` 的产物，有 `scene_id`），**不是路由记录**。
#     首版把路由记录喂进去 ⇒ 全是 `None` 的 scene_id ⇒ 误判"精确档不存在"。
_POOL = SP._scene_pool(_INDEX)
_CTX = {}
_src_pf = _read(PATHF)
_NAME_OF = {}
for _rec in _POOL:
    _NAME_OF[_rec['scene_id']] = _rec.get('name')
# 拿一个**真实存在**的 scene_id（不写死，索引变了也能跟上）
_full_id = None
for _rec in _POOL:
    _sid = _rec.get('scene_id')
    if isinstance(_sid, str) and _sid.count('.') >= 2:
        _full_id = _sid
        break
check('C0b ★★ 场景池真摊平出条目（`_scene_pool` 非空 ⇒ C 段其余判据的前提）',
      len(_POOL) > 1000 and _full_id is not None, star=True)
if _full_id is None:
    _full_id = 'ch1.kris_room.kris_s_room'

check('C1 ★★★ `scene_pathfind._TIER_NONE` 存在且 = 3（命名常量，不写魔数 3）',
      getattr(SP, '_TIER_NONE', None) == 3, star=True)

# C2 ★★★ 传**完整 scene_id** ⇒ 命中 -1 档（最强）
_rec_full = [x for x in _POOL if x.get('scene_id') == _full_id]
_TIER_STRICT = getattr(SP, '_TIER_NONE', 3)
_hit_tier = SP._match_tier(_rec_full[0], _full_id.lower(), []) \
    if _rec_full else None
check('C2 ★★★ 完整 `scene_id` ⇒ `_match_tier` 给 **-1 档**'
      '（`-1` 是"精确相等"专用档，比 tier 0 更优先）',
      _hit_tier == -1, star=True)
if _hit_tier != -1:
    print('         full_id=%r tier=%r' % (_full_id, _hit_tier))

# C2b ★★★ 端到端：`resolve_target(完整id)` 真的 ok（这才是产品行为）
try:
    _r_full = SP.resolve_target(_full_id, _INDEX)
except Exception as _e:
    _r_full = {'ok': False, 'error': str(_e)}
check('C2b ★★★ 端到端 `resolve_target(完整 scene_id)` ⇒ `ok=True` 且返回同 id'
      '（★ 这是菜单"点得动却走不到"的直接反证）',
      isinstance(_r_full, dict) and _r_full.get('ok') is True
      and _r_full.get('scene_id') == _full_id, star=True)
if not (isinstance(_r_full, dict) and _r_full.get('ok') is True):
    print('        resolve_target(%r) -> %r' % (_full_id, _r_full))

# C3 ★★★ 入选条件真改为 `t < _TIER_NONE`
#   ★★ 判据修窄（首版写成 `'t >= 0' not in _src_pf` ⇒ **把注释与文档串也算进去**，
#     而 `_match_tier` 的 docstring 里**故意**保留了"曾经的写法 t >= 0"的说明
#     ⇒ 判据误报）。现在走 **AST**：看 `resolve_target` 里那个 `if` 的比较节点。
_pf_tree = _ast(PATHF)


def _cond_str(fn_name, var):
    """取 `fn_name` 函数体里、与 `var` 相关的比较表达式源码串（AST，剥注释）。"""
    out = []
    for _fn in ast.walk(_pf_tree or ast.Module(body=[], type_ignores=[])):
        if not isinstance(_fn, ast.FunctionDef) or _fn.name != fn_name:
            continue
        for _node in ast.walk(_fn):
            if isinstance(_node, ast.Compare):
                _s = ast.dump(_node)
                if var in _s:
                    out.append(_s)
    return out


_c3_conds = _cond_str('resolve_target', '_TIER_NONE')
check('C3 ★★★ `resolve_target` 的入选条件走 **`_TIER_NONE` 常量**（AST 取比较节点，'
      '★ 不吃注释/文档串 —— 首版就是被 docstring 里的旧写法误报）',
      any("_TIER_NONE" in _c for _c in _c3_conds) and len(_c3_conds) > 0, star=True)
if not _c3_conds:
    print('        (resolve_target 里找不到含 _TIER_NONE 的比较节点)')

# C3b ★★ 源码里**没有活的** `t >= 0`（旧入选条件真被换掉了）
#   ★★ 判据修法：首版用**文本**判（`'t >= 0' not in 剥注释源码`）—— 但按行 `#` 剥注释
#     对**文档串**（docstring）无效，而 `_match_tier` 的 docstring 里**故意**保留
#     "曾经的写法"作防回退记录 ⇒ 文本判据必然误报（**判据过窄 = 会误报**的老坑）。
#   ⇒ 走 **AST**：在 `resolve_target` 里找比较表达式中含 `t` 的运算符，断言没有 `GtE`。
def _cmp_ops_in(fn_name, var):
    """`fn_name` 函数体里、比较表达式中含 `var` 的**运算符表**集合（AST，不吃注释）。"""
    ops = []
    for _fn in ast.walk(_pf_tree or ast.Module(body=[], type_ignores=[])):
        if not isinstance(_fn, ast.FunctionDef) or _fn.name != fn_name:
            continue
        for _node in ast.walk(_fn):
            if isinstance(_node, ast.Compare):
                _names = [n.id for n in ast.walk(_node) if isinstance(n, ast.Name)]
                if var in _names:
                    ops.append(tuple(type(o).__name__ for o in _node.ops))
    return ops


_ops_live = _cmp_ops_in('resolve_target', 't')
_has_gte = any('GtE' in o for o in _ops_live)     # `t >= 0`
_has_lt = any('Lt' in o for o in _ops_live)       # `t < _TIER_NONE`
check('C3b ★★ AST：`resolve_target` 里 **没有** `t >= 0`（`GtE`）、'
      '**有** `t < _TIER_NONE`（`Lt`）'
      '—— ★ 不吃 docstring（首版文本判据被防回退注释误报）',
      (not _has_gte) and _has_lt, star=True)
print('        ops on `t` in resolve_target = %r' % (_ops_live,))

# C4 ★★ `-1` 档在源码里真的被 `return -1`（不是只声明常量）
check('C4 ★★ `_match_tier` 内有 `return -1`（精确档真存在）',
      'return -1' in _src_pf, star=True)

# C5 负控制：C3b 的 AST 判据有鉴别力（`t >= 0` 的假源码必须判红）
_fake_tree_c5 = ast.parse('def resolve_target():\n    if t >= 0:\n        pass\n')
_ops_fake = []


def _cmp_ops_in_tree(tree, fn_name, var):
    ops = []
    for _fn in ast.walk(tree):
        if not isinstance(_fn, ast.FunctionDef) or _fn.name != fn_name:
            continue
        for _node in ast.walk(_fn):
            if isinstance(_node, ast.Compare):
                _names = [n.id for n in ast.walk(_node) if isinstance(n, ast.Name)]
                if var in _names:
                    ops.append(tuple(type(o).__name__ for o in _node.ops))
    return ops


_ops_fake = _cmp_ops_in_tree(_fake_tree_c5, 'resolve_target', 't')
check('C5 负控制：C3b 的 AST 判据有鉴别力（`t >= 0` 的假源码必须命 `GtE`）',
      any('GtE' in o for o in _ops_fake), star=True)

# C6 ★★ 别名匹配没被 `-1` 档挤掉（传**场景名**仍能命中非 -1 档）
_name_hits = []
for _rec in _POOL:
    _nm = _rec.get('name')
    if isinstance(_nm, str) and _nm:
        _t = SP._match_tier(_rec, _nm.lower(), [])
        if isinstance(_t, int) and _t < _TIER_STRICT:
            _name_hits.append((_nm, _t))
check('C6 ★★ 场景**名**（非 id）仍能命中（`-1` 档没把别的档挤掉）',
      len(_name_hits) > 100, star=True)
if len(_name_hits) <= 100:
    print('        name_hits=%d' % len(_name_hits))

# ================================================================ D. 菜单不空
_src_ctrl = _read(CTRL)
check('D1 ★★★ `_entry_scenes` 模块级函数存在（跨章入口表）',
      'def _entry_scenes(' in _src_ctrl, star=True)


# D2 ★★★ `_ENTRY_CHAPTER_ORDER` 常量存在且含 desktop + 五章 + 四个跨作品
#   ★ 首版判据查的是 `'"desktop"'`（双引号）⇒ 与源码里的**单引号元组**对不上 ⇒ 误报。
#     现在改为：AST 取那个赋值节点的**元组字面量**，逐项比（不吃引号风格）。
#   ★★ 第99轮：`outertale` 补齐（用户点名要的第五个世界入口）⇒ 期望元组同步。
def _entry_tuple(tree):
    for _n in ast.walk(tree or ast.Module(body=[], type_ignores=[])):
        if isinstance(_n, ast.Assign) and any(
                isinstance(_t, ast.Name) and _t.id == '_ENTRY_CHAPTER_ORDER'
                for _t in _n.targets):
            if isinstance(_n.value, ast.Tuple):
                return tuple(e.value for e in _n.value.elts
                             if isinstance(e, ast.Constant))
    return None


_ctrl_tree = _ast(CTRL)
_entry = _entry_tuple(_ctrl_tree)
_want_entry = ('desktop', 'ch1', 'ch2', 'ch3', 'ch4', 'ch5',
               'ut', 'uty', 'oneshot', 'outertale')
check('D2 ★★★ `_ENTRY_CHAPTER_ORDER` = (desktop, ch1~ch5, ut, uty, oneshot, outertale)'
      '（AST 取元组字面量，不吃引号风格 —— 首版被单/双引号差异误报）',
      _entry is not None and tuple(_entry) == _want_entry, star=True)
if _entry != _want_entry:
    print('        got=%r' % (_entry,))

# D3 ★★★ 跨章入口**插在头部**（`cross + out`，不是 `out + cross`）
#   ★ 本条是本轮最贵的坑：首版写成尾部 ⇒ `[:limit]` 一截就把「回桌面」截掉。
check('D3 ★★★ `reachable_destinations` 把跨章入口**插头部**（`cross + out`）'
      '—— 否则 `[:limit]` 会截掉「回桌面」',
      'cross + out' in _src_ctrl and 'out + cross' not in _src_ctrl, star=True)

# D4 负控制：D3 有鉴别力（假源码 `out + cross` 必须判失败）
_fake_d = 'return (out + cross)[:limit]'
check('D4 负控制：D3 有鉴别力（`out + cross` 的假源码必须判失败）',
      ('cross + out' in _fake_d and 'out + cross' not in _fake_d) is False,
      star=True)

# D5 ★★★ 真机：桌面菜单**不为空**且 ≥ 9 条，且第一条是跨章入口
_pet = None
_res = {}
try:
    # ★ `main.py` 住在 `src/` ⇒ 必须把 `src/` 也放进 sys.path（首版漏了 ⇒ 真机段全红）
    _SRC = os.path.join(PKG, 'src')
    if _SRC not in sys.path:
        sys.path.insert(0, _SRC)
    import main as _M  # noqa: E402
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtCore import QTimer

    _app = QApplication.instance() or QApplication(sys.argv)

    def _stage1():
        global _pet
        try:
            _pet = _M.RalseiPet()
            _pet.show()
            QTimer.singleShot(2600, _stage2)
        except Exception as _e:
            import traceback
            _res['err'] = traceback.format_exc()
            _res['dump'] = json.dumps(_res, ensure_ascii=False, default=str)
            try:
                _app.quit()
            except Exception:
                pass

    def _stage2():
        try:
            _cam = _pet.__dict__.get('_scene_camera')
            _st = _pet.__dict__.get('_scene_state')
            _res['scene_id'] = getattr(_st, 'scene_id', None)
            _res['cam_rect'] = _cam.rect if _cam else None
            # ★ 第106轮：把相机的**真实 scale**也报出来 —— E3 的期望 rect 尺寸
            #   由它现推（贴图 20 × scale），不再写死 40（全屏化会改它）。
            _res['scale'] = _cam.scale if _cam else None
            _res['viewport'] = _pet.scene.plan_viewport()
            # ★ 产品真路径（main.py:_update_scene_layer）—— 必须传 sprite_size
            _cv = _pet.__dict__.get('scene_canvas')
            import time as _t
            _plan = _pet.scene.plan_frame(
                sprite_size=_cv.assets.sprite_size, tick=int(_t.time() * 1000))
            _res['plan_n'] = len(_plan)

            # ★★★ 第109轮：桌面门现在是**动画**（`spr_darkdoor` 3 帧），`plan_frame`
            #   按 `tick=int(time()*1000)` 取当前帧 ⇒ 名字里的 `_N` **随墙钟变**
            #   （实测连跑 3 次得 `_1` / `_0` / `_2`）。把帧号原样 dump 进 G2 基线
            #   = 偶发假 DIFF（正是「判据禁回显随时相变绝对值」那条）。
            #   这里**只对 dump 去帧号**（`spr_darkdoor_2.png` → `spr_darkdoor.png`），
            #   帧动画本身由 `anim_round44` 专测；rect 与 obj 条数不受影响。
            def _norm_name(_n):
                import re as _re
                return _re.sub(r'_\d+\.png$', '.png', str(_n or ''))

            _res['objs'] = [(_norm_name(it.get('name')), tuple(it.get('rect') or ()))
                            for it in _plan if it.get('kind') == 'obj']
            _res['canvas_visible'] = bool(_cv.isVisible())
            # 菜单
            try:
                _res['dests'] = _pet.scene.reachable_destinations()
            except Exception as _e:
                _res['dests'] = 'ERR %s' % _e
            # ---- 推门（真推 A 与 W 两扇）----
            try:
                import item_interact as _II
                import scene_routing as _SRT
                _stt = _pet.__dict__.get('_scene_state')
                _ch = getattr(_stt, 'chapter_id', None)
                _world = (_pet._current_world()
                          if hasattr(_pet, '_current_world') else 'light')
                _routes2 = _SRT.load_routes() if hasattr(_SRT, 'load_routes') else None
                # ★★★ 第111轮：**必须镜像产品的调用点**（`main.py` L4890 传了 `on_egg`）。
                #   不传 `on_egg` ⇒ 彩蛋门按产品契约**根本不建**（日志 `没接 on_egg ⇒ 不建`）
                #   ⇒ 探针只能看到 3 个普通门，`props_n == 4` 恒假红（= 夹具不保真）。
                #   这里给一个**只观测、不动作**的桩：被调用就记一笔，绝不弹窗/切场景。
                _egg_calls = []
                _egg_stub = (lambda _p: (_egg_calls.append(getattr(_p, 'key', None)),
                                         False)[1])
                _props = _II.build_props(_stt, _ch, _world, routes=_routes2,
                                         on_egg=_egg_stub)
                _res['props_n'] = len(_props)
                # ★★★ 第111轮：桌面 4 扇门里 **1 扇是彩蛋门（Niko 的家）**
                #   ⇒ 除总数外还要记类名分解，F1b 用它断言"恰好 1 扇彩蛋门"。
                _res['props_cls'] = [type(p).__name__ for p in _props]
                _targets = [getattr(p, 'target_scene', None) for p in _props]
                _res['prop_targets'] = _targets

                # ★★★ 第111轮：**按门字母选目标**（不再按下标）。
                #   起因：桌面门顺序是 A/B/C/D，而 **B 是彩蛋门（`target_scene=None`）**
                #   ⇒ 旧 `_push(3, …)` 依赖"A~D 恰好按序、且都有 target"，
                #     彩蛋门一进来这条假设就碎（`_targets[3]` 取到 B 的 None）。
                #   按字母解析 = 判**语义**（"推 A 门 ⇒ 去 A 门声明的目标"）而非**位置**。
                def _target_of_letter(_letter):
                    for _p, _t in zip(_props, _targets):
                        if (getattr(_p, 'door_letter', None) == _letter
                                and _t is not None):
                            return _t
                    return None

                def _push(letter, tag):
                    _before = getattr(_pet.__dict__.get('_scene_state'),
                                      'scene_id', None)
                    _tgt = _target_of_letter(letter)
                    _ok = (_pet.scene.travel_to(_tgt)
                           if (hasattr(_pet.scene, 'travel_to') and _tgt) else None)
                    _after = getattr(_pet.__dict__.get('_scene_state'),
                                     'scene_id', None)
                    _res[tag + '_before'] = _before
                    _res[tag + '_ok'] = _ok
                    _res[tag + '_after'] = _after
                    _pet.scene.switch('desktop')

                _push('A', 'push0')
                _push('D', 'push3')
            except Exception as _e:
                _res['push_err'] = str(_e)
        except Exception as _e:
            import traceback
            _res['err'] = traceback.format_exc()
        finally:
            try:
                _pet.close()
            except Exception:
                pass
            _res['dump'] = json.dumps(_res, ensure_ascii=False, default=str)
            try:
                _app.quit()
            except Exception:
                pass

    QTimer.singleShot(300, _stage1)
    _app.exec_()
except Exception as _e:
    import traceback
    _res = {'dump': traceback.format_exc()}

print('        [probe] %s' % (_res.get('dump') or _res.get('err') or '<空>')[:1800])
if _res.get('err'):
    print('        [probe-err] %s' % str(_res.get('err'))[:1200])
if _res.get('push_err'):
    print('        [probe-push-err] %s' % str(_res.get('push_err'))[:600])

_dests = _res.get('dests') if isinstance(_res.get('dests'), list) else []
check('D5 ★★★ 真机：桌面「去…」菜单**不为空**且 ≥ %d 条'
      '（用户「我到现在都没看到能切场景的门」的直接反证）' % _N_DOORS,
      len(_dests) >= _N_DOORS, star=True)

_dest_first = _dests[0] if _dests else None
_dest_ids = [ (x.get('scene_id') if isinstance(x, dict) else x) for x in _dests ]
check('D6 ★★★ 真机：菜单**第一条**是跨章/跨作品入口（`坐头部`生效的反证）',
      bool(_dest_ids) and not str(_dest_ids[0] or '').startswith('desktop.'),
      star=True)
if _dest_ids:
    print('        dests[:6] = %r' % (_dest_ids[:6],))

# D7 ★★ 桌面菜单里**含「回桌面」以外的跨界目标**（第109轮起 = 三世界各一）
#   ★ 原口径「ut / uty / oneshot / outertale 至少各一」已随 4 门重做**失效**
#     （W/X/Y 不再建门 ⇒ 无 uty/outertale）。
#   ★★ 但**判据不能直接断门目标**：`reachable_destinations()` 是**章级**入口清单
#      （每章只取一个代表场景，H1 的 docstring 写死了这条语义），而 4 个门目标是
#      **门级**机制（由 `DoorProp` / `travel_to` 消费，F2/F4 已覆盖）。
#     ⇒ D7 该断的是「三世界在章级菜单里都有一扇可回的门」——
#        `ch1`（三角符文）/ `ut`（Undertale）/ `oneshot`（OneShot）各至少一条。
_joined = ' | '.join([str(x) for x in _dest_ids])
_want_prefixes = ['ch1.', 'ut.', 'oneshot.']
check('D7 ★★ 真机菜单含三世界章级入口（ch1 三角符文 / ut / oneshot 各至少一条'
      '—— 「任何场景下都有路可走」的兜底）',
      all(p in _joined for p in _want_prefixes), star=True)

# ================================================================ E. 渲染计划（真机）
check('E1 ★★★ 真机：相机已 follow 且**固定**在 (0,0,320,240)'
      '（房间=相机 ⇒ 不跟随，门位置稳定）',
      isinstance(_res.get('cam_rect'), (list, tuple))
      and tuple(_res['cam_rect']) == (0.0, 0.0, 320.0, 240.0), star=True)

check('E2 ★★★ 真机：`plan_frame` 产出 **%d 条 obj**（%d 扇门真的进绘制计划）'
      % (_N_DOORS, _N_DOORS),
      _res.get('objs') is not None and len(_res['objs']) == _N_DOORS, star=True)

# E3 ★★★ rect 尺寸 = 贴图尺寸 × scale ——
#   ★★ 这条是本轮最贵的探针教训：漏传 `sprite_size` ⇒ 尺寸退化成 (1,1)。
#   ★★★ 第106轮改判据：**期望值从相机的真实 scale 推**，不写死 40。
#     起因：第106轮「全屏化」把 camera.scale 由 2.0 抬到 2.125（输出 680×510）
#     ⇒ 门的 rect 由 40×40 变 42×42 —— 老判据写死 40 **假红**。
#     这正是「判据与事实脱节」（路由/参数改了，判据还钉着旧数）的又一例：
#     真正要守的语义是「rect 尺寸 == 贴图原始尺寸 × 相机 scale」，
#     而不是"恰好四个字节是 40"。改成从 `_res['scale']` 现推。
_objs_rect = _res.get('objs') or []
_scale = _res.get('scale')
#   ★★★ 第109轮改判据：桌面门贴图由 **`spr_doorA`（20×20）** 换成
#     **任意门 `spr_darkdoor`（44×56，两轴不等）** ⇒ 旧判据「宽高都 == 20×scale」
#     **假红**（44≠56）。真正要守的语义是「rect 尺寸 == 门贴图原始尺寸 × 相机 scale」，
#     所以期望值改为**从盘上读贴图真尺寸**（`_A_DOOR_SPRITE_PX`，44×56）现推。
#   ★★★ 第112轮改判据：4 扇门**不再是同一张贴图**（用户「门也不是都长那样」）
#     ⇒ E3 由"全部等于 任意门×scale"改为"**逐门**等于各自贴图真尺寸 × scale"。
#     期望贴图名从 plan 出来的 `objs[0]`（路径）里取，再回 `_expect_px` 查真尺寸。
def _expect_px_of(sprite_path):
    """由 plan 出来的贴图路径（`objs/xxx.png`）求期望 (w,h)（原始像素）。"""
    _bn = os.path.basename(str(sprite_path or ''))
    for _f, _px in (('spr_darkdoor', _A_DOOR_SPRITE_PX),
                    ('ut_castle_realdoor', _A_UT_SPRITE_PX),
                    ('spr_shortcut_door', _A_SHORTCUT_SPRITE_PX)):
        if _bn.startswith(_f):
            return _px
    # 动画帧 `xxx_0.png` / `xxx_1.png` ⇒ 去尾号再试
    _stem = _bn.rsplit('_', 1)[0]
    for _f, _px in (('spr_darkdoor', _A_DOOR_SPRITE_PX),
                    ('ut_castle_realdoor', _A_UT_SPRITE_PX),
                    ('spr_shortcut_door', _A_SHORTCUT_SPRITE_PX)):
        if _stem.startswith(_f):
            return _px
    return None


_px_bad_e3 = []
for _n, _r in _objs_rect:
    if len(_r) != 4:
        continue
    _px = _expect_px_of(_n)
    if _px is None:
        _px_bad_e3.append('未知贴图 %r' % (_n,))
        continue
    _ew = int(round(_px[0] * _scale)) if isinstance(_scale, (int, float)) else None
    _eh = int(round(_px[1] * _scale)) if isinstance(_scale, (int, float)) else None
    if _r[2] != _ew or _r[3] != _eh:
        _px_bad_e3.append('%s rect=%s 期望=%s' % (os.path.basename(str(_n)), _r, (_ew, _eh)))
check('E3 ★★★ 真机：每扇门 rect 尺寸 = **各自贴图真尺寸 × 相机 scale(%s)**'
      '—— 即 `sprite_size` 真被传进产品真路径' % (_scale,),
      len(_objs_rect) == _N_DOORS and not _px_bad_e3, star=True)
if _px_bad_e3:
    for _b in _px_bad_e3[:4]:
        print('        %s' % _b)
if _objs_rect and _px_bad_e3:
    print('        rects=%r' % (_objs_rect,))

# E4 ★★ 全部门的 rect **全在视口内**
#   ★★★ 第106轮改判据：视口尺寸**不再写死 640×480**（全屏化后是 680×510，
#     且随屏幕而变）—— 从 `plan_viewport()` 的真实返回值取，只断言
#     "门的 rect 全落在 [0, viewport] 内"（语义），不断言具体数字（事实）。
_vw, _vh = (_res.get('viewport') or (0, 0))[:2]
_in_ok = all(0 <= r[0] and 0 <= r[1] and r[0] + r[2] <= _vw and r[1] + r[3] <= _vh
             for _n, r in _objs_rect if len(r) == 4)
check('E4 ★★ 真机：%d 扇门 rect **全在视口内**（%d×%d，不会被裁掉）'
      % (_N_DOORS, _vw, _vh),
      len(_objs_rect) == _N_DOORS and _in_ok and _vw > 0 and _vh > 0, star=True)
if _objs_rect:
    print('        rects=%r' % ([r for _n, r in _objs_rect],))

# E5 ★★ 画布真 show（不是"算了但没显示"）
check('E5 ★★ 真机：场景画布 `visible=True`（门真的会显示出来）',
      _res.get('canvas_visible') is True, star=True)

# E6 负控制：E2 有鉴别力（`viewport == (0,0)` 时必然画不出东西 —— 那是本轮修前的状态）
check('E6 负控制：E2 有鉴别力（viewport 为 (0,0) 时 `plan_viewport` 早退 ⇒ 零 obj）',
      (0, 0) != tuple(_res.get('viewport') or (0, 0)), star=True)

# ================================================================ F. 推门真切场景（真机）
#   ★★★ 第111轮口径变化：桌面 4 扇门里 **1 扇是彩蛋门**（Niko 的家，永远进不去）
#     ⇒ 总数仍是 `_N_DOORS`(=4)，但**不再是 4 个 `DoorProp`**，
#     而是 **3 个 `DoorProp` + 1 个 `NikoHomeDoorProp`**。F1a/F1b 拆两条判。
check('F1a ★★★ 真机：`item_interact.build_props` 在建 %d 个门道具（桌面的 %d 扇门全可交互）'
      % (_N_DOORS, _N_DOORS),
      _res.get('props_n') == _N_DOORS, star=True)
# F1b ★★★ 其中**恰好 1 扇**是 `NikoHomeDoorProp`（彩蛋门），其余是普通 `DoorProp`
#   ★ 不写死"3 个 DoorProp"是**故意的弱耦合**：门表将来若扩（例如加第 5 扇世界门），
#     只要"总数 - 1 扇彩蛋 = 普通门"这条语义成立，本条仍绿 ⇒ 判**不变量**而非快照。
_cls = _res.get('props_cls') or []
_n_egg = _cls.count('NikoHomeDoorProp')
_n_plain = _cls.count('DoorProp')
check('F1b ★★★ 真机：桌面门里**恰好 1 扇彩蛋门**（`NikoHomeDoorProp`，Niko 的家）'
      '＋**其余全是普通 `DoorProp`**（实际 = %d 彩蛋 / %d 普通 / 共 %d）'
      % (_n_egg, _n_plain, len(_cls)),
      _n_egg == 1 and _n_plain == len(_cls) - 1 and len(_cls) == _N_DOORS, star=True)
if _cls:
    print('        props_cls=%r' % (_cls,))


# F2 ★★★ 真机：推 A 门 ⇒ 真切到「A 门声明的目标」（期望值**从门表推**，不写死）
#   ★ 不写死 `ch1.kris_room.kris_s_room`：那是"判据与事实脱节"的老坑
#     （路由改了、判据还绿）。从 `_routes.json` 的桌面 A 规则取 `to`。
_a_rule = [x for x in _desktop_routes if x.get('when_door') == 'A']
_a_expect = _a_rule[0].get('to') if _a_rule else None
check('F2 ★★★ 真机：推 **A 门** ⇒ `scene_id` 真变成 A 门声明的目标'
      '（期望值从 `_routes.json` 推，不写死）',
      _a_expect is not None and _res.get('push0_after') == _a_expect, star=True)
if _res.get('push0_after') is not None:
    print('        push[0]: %r -> %r (期望 %r, ok=%r)'
          % (_res.get('push0_before'), _res.get('push0_after'),
             _a_expect, _res.get('push0_ok')))

# F3 ★★ `travel_to` 真的返回 ok=True 且 hops==1（直达，不绕路）
check('F3 ★★ 真机：A 门 `travel_to` 返回 `ok=True` 且 `hops==1`（直达）',
      isinstance(_res.get('push0_ok'), dict)
      and _res['push0_ok'].get('ok') is True
      and _res['push0_ok'].get('hops') == 1, star=True)

# F4 ★★ 推 **D 门（三角符文 / Deltarune）** ⇒ 真切到「D 门声明的目标」（跨作品那条路）
#   ★ 第109轮：原推 W 门（黄魂 / outertale）已随 4 门重做**取消**（W/X/Y 不再建门）
#     ⇒ 改推 D 门（正右 = 三角符文），目标应落在 `ch1.`（光世界小镇中心）。
_d_rule = [x for x in _desktop_routes if x.get('when_door') == 'D']
_d_expect = _d_rule[0].get('to') if _d_rule else None
check('F4 ★★ 真机：推 **D 门**（三角符文 / Deltarune）⇒ 真切到 D 门声明的目标，'
      '且目标以 `ch1.` 开头（光世界小镇中心）',
      _d_expect is not None and _d_expect.startswith('ch1.')
      and _res.get('push3_after') == _d_expect, star=True)
if _res.get('push3_after') is not None:
    print('        push[3]: %r -> %r (期望 %r)'
          % (_res.get('push3_before'), _res.get('push3_after'), _d_expect))

# ================================================================ G. 旧行为不回归
# G1 ★★ 负控制：**未知/空 want** 不该被 `-1` 档命中（`-1` 是"逐字相等"，不是通配）
#   ★ 首版这里写成了 `check(..., True)` —— **恒真占位**，本项目最忌的写法
#     （第64轮 `W22` 就是这么栽的）。现在改成真判据：
#     遍历整个场景池，用 5 个必然不存在的 want，断言 **-1 档零命中**。
_fake_wants = ['zzz.nope.nope', '', '.', 'nope', 'a.b.c.d.e']
_bad_hits = 0
for _w in _fake_wants:
    for _rec3 in _POOL:
        if SP._match_tier(_rec3, _w.lower(), []) == -1:
            _bad_hits += 1
check('G1 ★★★ 负控制：5 个必然不存在的 want 在**整个场景池**上零命中 -1 档'
      '（`-1` 是"逐字相等"，不是通配）',
      _bad_hits == 0, star=True)
if _bad_hits:
    print('        bad_hits=%d' % _bad_hits)

# G2 ★★ 正控制：`-1` 档**不是恒假**（拿真 id 必须命中 —— 与 G1 成对）
_pos_hits = 0
for _rec4 in _POOL[:200]:
    _sid4 = _rec4.get('scene_id')
    if isinstance(_sid4, str) and SP._match_tier(_rec4, _sid4.lower(), []) == -1:
        _pos_hits += 1
check('G2 ★★★ 正控制：真实 `scene_id` 在场景池上前 200 条**全部命中 -1 档**'
      '（与 G1 成对 —— `-1` 既不恒真也不恒假）',
      _pos_hits == 200, star=True)
if _pos_hits != 200:
    print('        pos_hits=%d/200' % _pos_hits)

# G3 ★★ `desktop.json` 的 `original_room_id` 真是 -1（几何查得到的前提）
check('G3 ★★ `desktop.json` 的 `original_room_id == -1`'
      '（与 `_room_geometry.json` 的 `desktop:-1` 配对）',
      _d.get('original_room_id') == -1, star=True)

# G4 ★★ `scene_pathfind` 顶层 import **不碰 Qt / 业务重模块**（纯数据层的实质约束）
#   ★ 首版判据写成"只准标准库" ⇒ 被 `from scene_system import _read_json, scenes_dir`
#     误报。但 `scene_system` 是**同包纯数据模块**（零 Qt、零业务），
#     正是纯数据层该有的同伴 —— 判据过窄 = 会误报（本项目老坑）。
#   ⇒ 真正该禁的是 **Qt** 与**重业务模块**（sprite_loader / data_store / ai_driver …）。
_BANNED = {'PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'sprite_loader', 'data_store',
           'ai_driver', 'main', 'event_speech', 'ollama'}
_pf_tree = _ast(PATHF)
_top_imps = []
if _pf_tree is not None:
    for _n in _pf_tree.body:
        if isinstance(_n, ast.Import):
            _top_imps += [a.name.split('.')[0] for a in _n.names]
        elif isinstance(_n, ast.ImportFrom):
            _top_imps.append((_n.module or '').split('.')[0])
_banned_hit = sorted(set(_top_imps) & _BANNED)
check('G4 ★★ `scene_pathfind` 顶层 **零 Qt / 零业务重模块**'
      '（`scene_system` 是同包纯数据模块，允许）',
      not _banned_hit, star=True)
print('        top_imports=%r' % (_top_imps,))
if _banned_hit:
    print('        BANNED=%r' % (_banned_hit,))

# G5 负控制：G4 有鉴别力（假 import PyQt5 必须被抓）
_fake_tree = ast.parse('import os\nfrom PyQt5.QtWidgets import QApplication\n')
_bad_imps = []
for _n in _fake_tree.body:
    if isinstance(_n, ast.ImportFrom):
        _bad_imps.append((_n.module or '').split('.')[0])
    elif isinstance(_n, ast.Import):
        _bad_imps += [a.name.split('.')[0] for a in _n.names]
check('G5 负控制：G4 有鉴别力（`from PyQt5...` 必须被判命中禁用名单）',
      bool(set(_bad_imps) & _BANNED), star=True)

# ================================================================ I. 可见性（★ 本轮核心）
#  ★★★ 血泪背景：A~H 段全绿时，用户屏幕上**一个门都看不到**。
#   根因（真机逐步定位，两处）：
#     ① `SceneCanvas` 是桌宠主窗口（38×80）的**子控件**，`resize(640,480)`
#        超出父窗口的部分被 Qt 裁掉 ⇒ 只看到左上角一小块；
#     ② 改成独立顶层窗口后，`_show_scene_layer` 里那句 `canvas.lower()`
#        把它**沉到了桌面壳窗口之下** ⇒ 整块画布不上屏。
#    两处的共同症状：`cv.grab()`（离屏渲染）**画得出 8 扇门**，
#    屏幕截图 **blue=3 / green=0**。
#  ⇒ 「产物侧看不见 ≠ 调用侧没发生」（记忆铁律）—— 本节专门守"真的上屏"。
_CANVAS = os.path.join(PKG, 'modules', 'scene_canvas.py')
_cv_src = _read(_CANVAS) if os.path.isfile(_CANVAS) else ''
_main_src2 = _read(MAIN) if os.path.isfile(MAIN) else ''

check('I1 ★★ `SceneCanvas` 支持 **独立顶层窗口**模式（`as_window` 形参）',
      'as_window' in _cv_src, star=True)

# ★ 判据修正（第89轮首跑 I2/I4/I5/I6 报红，**全是判据侧**）：
#   · I2：原判据 `'WindowStaysOnTopHint' not in _cv_src` 把**注释**也算进去了
#     —— 而注释里恰恰写着"**不加** `WindowStaysOnTopHint`" ⇒ 过窄误报。
#     改用 AST 扫 `setWindowFlags` 实参里的 `Qt.<attr>`。
#   · I4/I5/I6：原判据用 `str.split('def ...')` 粗略切片，遇到装饰器/嵌套就切歪。
#     改用 AST 定位函数节点。
_cv_tree = _ast(_CANVAS)
_flags_attrs = []
if _cv_tree is not None:
    for _n in ast.walk(_cv_tree):
        if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Attribute) \
                and _n.func.attr == 'setWindowFlags':
            for _a in ast.walk(_n):
                if isinstance(_a, ast.Attribute):
                    _flags_attrs.append(_a.attr)
check('I2 ★★独立窗口模式设的是 `FramelessWindowHint | Tool`，'
      '**不含** `WindowStaysOnTopHint`（记忆契约②：禁置顶）'
      '—— 判据走 AST 扫 `setWindowFlags` 实参（注释里出现该词不算）',
      ('FramelessWindowHint' in _flags_attrs) and ('Tool' in _flags_attrs)
      and ('WindowStaysOnTopHint' not in _flags_attrs), star=True)
print('        setWindowFlags attrs=%r' % (_flags_attrs,))

check('I3 ★★★ `main` 建画布时**传 `as_window=True`**（不是子控件 —— '
      '否则 640×480 会被 38×80 的父窗口裁掉）',
      'as_window=True' in _main_src2, star=True)


def _func_node(tree, name):
    """在模块顶层 + 类体内按名字找 FunctionDef。"""
    if tree is None:
        return None
    for _n in ast.walk(tree):
        if isinstance(_n, ast.FunctionDef) and _n.name == name:
            return _n
    return None


_MS = _func_node(_ast(MAIN), '_show_scene_layer')
_PL = _func_node(_ast(MAIN), '_place_scene_layer')

# I4 ★★ `lower()` 必须被 `as_window` 判据包住。
#   ★ 判据修正（第89轮首跑报红，**是判据侧**）：产品写的是
#     `getattr(canvas, 'as_window', False)` —— `as_window` 是**字符串常量**
#     （`ast.Constant`），不是 `ast.Attribute`。原判据只扫 Attribute ⇒ 漏检
#     ⇒ 误报"无守卫"。这正是记忆里"扫属性要同时扫 `ast.Constant`"那条。
_calls_lower = []
_has_guard = False
if _MS is not None:
    for _n in ast.walk(_MS):
        if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Attribute) \
                and _n.func.attr == 'lower':
            _calls_lower.append(_n.lineno)
        if isinstance(_n, ast.Attribute) and _n.attr == 'as_window':
            _has_guard = True
        # ★ 同时认「字符串常量」写法：getattr(x, 'as_window') / x[{'as_window'...}]
        if isinstance(_n, ast.Constant) and _n.value == 'as_window':
            _has_guard = True
check('I4 ★★★ `_show_scene_layer` 的 `lower()` **必须与 `as_window` 判据绑定**'
      '（独立窗口无条件 lower() ⇒ 沉到桌面之下 ⇒ 整块画布不上屏）'
      '—— 判据走 AST 定位函数体，且**同时认属性与字符串常量**两种写法',
      (not _calls_lower) or _has_guard, star=True)
# ★★★ 第106轮：探针**不打印绝对行号**（只打印条数 + 布尔）。
#   起因：本轮在 main.py 上方插了 16 行注释 ⇒ `_calls_lower=[6664]` 变 `[6680]`
#   ⇒ G2 报**假 DIFF**（计数一条没变，只有行号漂了）。
#   这正是第75轮那条「行号是纯脆性信息」的复演 —— 当时只给 traceback 加了
#   `line <LN>` 归一化，**探针自己打的字面量行号没被覆盖**。与其去改归一化器
#   （会影响所有套件），不如让探针**不产生**脆性信息：判据本身是布尔的，
#   行号对"守没守住"毫无贡献。
print('        lower() 调用数=%d  有 as_window 守卫=%r'
      % (len(_calls_lower), _has_guard))

# I5 ★★ `_place_scene_layer` 存在，且**只 move 不 resize**
_pl_moves = []
_pl_resizes = []
if _PL is not None:
    for _n in ast.walk(_PL):
        if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Attribute):
            if _n.func.attr == 'move':
                _pl_moves.append(_n.lineno)
            if _n.func.attr == 'resize':
                _pl_resizes.append(_n.lineno)
check('I5 ★★ `_place_scene_layer()` 存在，且**只 move 不 resize**'
      '（尺寸归 `set_plan` 的 view_size，否则小房间会被撑回相机尺寸）'
      '—— 判据走 AST（原字符串切片切歪 ⇒ 误报）',
      _PL is not None and bool(_pl_moves) and not _pl_resizes, star=True)
# 同上（第106轮）：只打条数，不打行号 —— 行号漂移会造成假 DIFF。
print('        place move 数=%d  resize 数=%d'
      % (len(_pl_moves), len(_pl_resizes)))

# I6 ★★ `_place_scene_layer` 必须用 **QRect 接口**（无下标取址）
_pl_subscripts = []
if _PL is not None:
    for _n in ast.walk(_PL):
        if isinstance(_n, ast.Subscript):
            _pl_subscripts.append(_n.lineno)
check('I6 ★★ `_place_scene_layer` **不得**对 `_virtual_screen_rect()` 的返回值'
      '下标取址（QRect 不可下标，抛 TypeError 会被 try 静默吞掉 ⇒ '
      '"看起来没报错但其实没生效"）—— 判据走 AST 扫 Subscript 节点',
      _PL is not None and not _pl_subscripts, star=True)
print('        place 下标取址行=%r' % (_pl_subscripts,))

# I7 ★★★ 第107轮口径更正：**废弃四向钳制**，改为「固定摆屏原点」
#   （AST：数 `max/min` 调用 —— 第89轮要求 ≥1，第107轮要求 ==0）
_pl_max = _pl_min = 0
if _PL is not None:
    for _n in ast.walk(_PL):
        if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Name):
            if _n.func.id == 'max':
                _pl_max += 1
            elif _n.func.id == 'min':
                _pl_min += 1
#   ★ 起因：用户第107轮原话「**场景是全屏，不是跟随移动的窗口，是像原作全屏后的效果似的**」
#     + AskUserQuestion「**按场景比例铺满、留黑边**」。
#     ⇒ 第89轮那套「居中 + 四向钳制」（让画布跟着宠物在屏内移动）**已按用户口径废弃**：
#       现在画布尺寸 = **主屏物理尺寸**（铺满屏），摆位 = **主屏原点**（不动），
#       所以既不需要钳制、也不该再有 `max/min`。
#   ⇒ 判据同步更新为**新事实**（两条，成对）：
#       ① 仍**只 move 不 resize**（I5 已守）；
#       ② **不得**再出现 `max/min` 钳制（钳制 = 跟随窗口时代的残留；
#          若还在 ⇒ 说明半新半旧，画布尺寸与摆位不自洽）。
#   ⚠️ 这正是「**判据比产品旧**」的又一例（同 B5）：口径变了，判据必须跟着变，
#      否则事实合法演进 = 假红。
check('I7 ★★★ `_place_scene_layer` **不再**做四向钳制（第107轮口径："不是跟随移动的'
      '窗口" ⇒ 固定摆主屏原点；残留 `max/min` = 半新半旧不自洽）'
      '—— 判据走 AST 数 max/min 调用',
      _PL is not None and _pl_max == 0 and _pl_min == 0, star=True)
print('        place max 调用=%d  min 调用=%d' % (_pl_max, _pl_min))

# I7b ★★★ 第107轮新事实：摆位基准是**主屏原点**（不是"居中 + 钳制"）
#   语义：`_place_scene_layer` 里同时出现 `primaryScreen()` 与 `geometry()`，
#   且把 geometry 的 x/y 直接喂给 `move`（固定铺满，不随宠物移动）。
#   ★ 用 AST 判"真有 move 调用 + 真取 primaryScreen/geometry"，
#     不扫字符串（文档串/注释一提名字就误报 —— 已四次发作）。
_pl_has_primary = False
_pl_has_geometry = False
if _PL is not None:
    for _n in ast.walk(_PL):
        if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Attribute):
            if _n.func.attr == 'primaryScreen':
                _pl_has_primary = True
            if _n.func.attr == 'geometry':
                _pl_has_geometry = True
check('I7b ★★★ `_place_scene_layer` 以**主屏**为基准摆位'
      '（真调 `primaryScreen()` + `geometry()` ⇒ 铺满主屏、不随宠物移动）',
      _PL is not None and _pl_has_primary and _pl_has_geometry, star=True)
print('        place primaryScreen=%r  geometry=%r'
      % (_pl_has_primary, _pl_has_geometry))

# I8 ★★ 摆位后显式重绘
_pl_repaint = False
if _PL is not None:
    for _n in ast.walk(_PL):
        if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Attribute) \
                and _n.func.attr == 'repaint':
            _pl_repaint = True
check('I8 ★★ 摆位后**显式重绘**（`canvas.repaint()`）—— '
      '透明顶层窗口 move 后不自动重绘，上屏的会是空内容',
      _pl_repaint, star=True)

# I9 ★★ 桌面场景声明 `bg == "__transparent__"`（透出壁纸 = "桌面即场景"），
#   而不是 `null`（null 会画灰格纹占位，把壁纸盖住）
_dt = None
try:
    with open(DESKTOP, 'r', encoding='utf-8') as _fh:
        _dt = json.load(_fh)
except Exception:
    _dt = None
check('I9 ★★ 桌面场景 `bg == "__transparent__"`（显式声明透明 ⇒ 不画背景/占位，'
      '透出用户壁纸；`null` 会画灰格纹占位把壁纸盖住）',
      isinstance(_dt, dict) and _dt.get('bg') == '__transparent__', star=True)

# I10 ★★ `TRANSPARENT_BG` 常量在**最前面**被拦掉（否则它是真值字符串 ⇒
#     走"有背景"分支 ⇒ 拼成 `bg/__transparent__.png` 查不到 ⇒ 画出假背景指令）
_sr = _read(os.path.join(PKG, 'modules', 'scene_render.py'))
check('I10 ★★ `scene_render` 把 `TRANSPARENT_BG` **在取 `bg_name` 后立刻归一到 None**'
      '（真值字符串会走"有背景"分支 ⇒ 拼假图名 ⇒ 画出假背景）',
      '_transparent_bg' in _sr and 'TRANSPARENT_BG' in _sr, star=True)

# I11 负控制：I10 有鉴别力 —— 若把归一化去掉，`bg_name` 会是真值
check('I11 负控制：`TRANSPARENT_BG` 是**非空真值字符串**'
      '（正因如此才必须显式归一 —— 空串/None 不会有这个坑）',
      isinstance('__transparent__', str) and bool('__transparent__'), star=True)

# ================================================================ J. 不许自作主张开 B站
# 用户口径（逐字）：**「对了，别让他打开bilbil了」**（第89轮）
#
# ★★★ 这是"不许做某事"的最强形态判据：**扫全项目代码层，B站 URL 一个都不许有**
#   （只许出现在注释里）。不是"检查某个函数有没有调 open_browser"——
#   那种判据有个岔路：以后新加一个函数代开，判据照样绿。
#   全量扫描 + 只放行注释，才真的堵死。
_VCP = os.path.join(PKG, 'modules', 'video_controller.py')
_MAIN = MAIN
_DI = os.path.join(PKG, 'modules', 'desktop_interaction.py')


def _scan_open_browser_urls():
    """全项目扫 `.py` 代码层：返回 (bilibili URL 所在行, open_browser 真调用点)。

    ★ 只算**代码层**：`ast` 剥掉注释后仍留下的字符串字面量。
      ⇒ "注释里提到 bilibili 作为反面例子"不会误报；
        "代码里真写了 bilibili URL"必被抓。
    """
    urls, calls = [], []
    for _root, _dirs, _files in os.walk(PKG):
        _dirs[:] = [d for d in _dirs
                    if d not in ('__pycache__', 'assets', '_evidence', 'sprites')]
        for _f in _files:
            if not _f.endswith('.py'):
                continue
            _p = os.path.join(_root, _f)
            try:
                _tree = ast.parse(_read(_p))
            except Exception:
                continue
            for _n in ast.walk(_tree):
                # ① 代码层字符串字面量里的 B站 URL
                if isinstance(_n, ast.Constant) and isinstance(_n.value, str):
                    if 'bilibili.com' in _n.value:
                        urls.append('%s:%s' % (_f, getattr(_n, 'lineno', '?')))
                # ② 真调用点 `open_browser(...)`（Attribute 调用，非定义）
                if isinstance(_n, ast.Call):
                    _fn = _n.func
                    if (isinstance(_fn, ast.Attribute)
                            and _fn.attr == 'open_browser'
                            and isinstance(_fn.value, ast.Name)
                            and _fn.value.id != ''):
                        calls.append('%s:%s' % (_f, getattr(_n, 'lineno', '?')))
    return urls, calls


_urls, _calls = _scan_open_browser_urls()

check('J1 ★★★ 全项目代码层**零** B站 URL 字面量'
      '（"别让他打开 bilbil"的最强形态：不查某个函数，查整个仓库）',
      _urls == [], star=True)

# J2 ★★ 产品真路径：`suggest_watching_video` 里**不许**出现代开三件套。
#   ★ 用 AST 而非字符串 —— 第75 轮教训：`code_only_src()` 会剥 STRING token，
#     但**注释**不在 AST 里，所以 AST 天然只看真代码（注释里的反面例子不误报）。
def _suggest_body_names():
    try:
        _tree = ast.parse(_read(_VCP))
    except Exception:
        return set()
    for _n in ast.walk(_tree):
        if isinstance(_n, ast.FunctionDef) and _n.name == 'suggest_watching_video':
            _names = set()
            for _x in ast.walk(_n):
                if isinstance(_x, ast.Attribute):
                    _names.add(_x.attr)
                elif isinstance(_x, ast.Name):
                    _names.add(_x.id)
            return _names
    return set()


_SUG = _suggest_body_names()
check('J2 ★★ `suggest_watching_video` 真路径里**没有**代开三件套'
      '（open_browser / move_and_resize_bilibili_window / _start_video_watching_loop）',
      not (_SUG & {'open_browser', 'move_and_resize_bilibili_window',
                   '_start_video_watching_loop'}),
      star=True)

# J3 ★★ 负控制：J2 的判据**有鉴别力** —— 拿一个真含 open_browser 的函数体试，
#   必须能抓出来（否则 J2 可能只是"名字恰好都不在"的恒真判据）。
def _has_open_browser(funcname):
    try:
        _tree = ast.parse(_read(_VCP))
    except Exception:
        return False
    for _n in ast.walk(_tree):
        if isinstance(_n, ast.FunctionDef) and _n.name == funcname:
            for _x in ast.walk(_n):
                if isinstance(_x, ast.Attribute) and _x.attr == 'open_browser':
                    return True
    return False


_neg_src = ast.parse('def _x():\n    self.desktop_interaction.open_browser("http://e")\n')
_neg_hit = any(isinstance(_x, ast.Attribute) and _x.attr == 'open_browser'
               for _x in ast.walk(_neg_src))
check('J3 ★★ 负控制：J2 同款提取器在"真有 open_browser"的样本上必须命中'
      '（证明 J2 不是恒真判据）',
      _neg_hit is True, star=True)

# J4 ★ 保留的能力没被误伤：`identify_video_apps` 仍在（"陪看"是允许的），
#   且 `start_watching_video` 仍能被 `check_video_apps` 调到。
check('J4 ★ 陪看能力未被误伤（`identify_video_apps` 在位 · '
      '`check_video_apps` 仍真调 `start_watching_video`）',
      'def identify_video_apps' in _read(_VCP)
      and 'start_watching_video' in _read(_VCP), star=True)

# J5 ★★ 用户明确要的"打开浏览器"仍然可用（不许为了禁 B站把功能删掉）
check('J5 ★★ 用户明确指令「打开浏览器」仍可用（`open_browser_for_ralsei` 在位 · '
      '真调 `open_browser` 且目标是百度不是 B站）',
      'def open_browser_for_ralsei' in _read(_MAIN)
      and 'baidu.com' in _read(_MAIN), star=True)

# ================================================================ H. 判据自身体检
check('H1 ★★ 被测文件全在盘（desktop.json / _room_geometry.json / _routes.json / '
      'scene_controller.py / scene_pathfind.py / main.py）',
      all(os.path.isfile(_p) for _p in
          (DESKTOP, GEOM, ROUTES, CTRL, PATHF, MAIN)), star=True)

check('H2 ★★ 记账守恒（每个 check 都记了账，且总数 ≥ 40）',
      _n_lines[0] == _n_pass[0] + _n_fail[0] and _n_lines[0] >= 40, star=True)

# H3 负控制：H2 的记账器有鉴别力（手工模拟 FAIL，不真打印 [FAIL] 行）
_before_f = _n_fail[0]
_before_len = len(_failed)


def _sim_fail():
    _n_fail[0] += 1
    _failed.append('__sim__')


_sim_fail()
_has_effect = (_n_fail[0] == _before_f + 1 and len(_failed) == _before_len + 1)
_n_fail[0] -= 1
_failed.pop()
check('H3 ★★ 负控制：记账器有鉴别力（模拟 FAIL ⇒ 计数真 +1，已撤回）',
      _has_effect and _n_fail[0] == _before_f and len(_failed) == _before_len,
      star=True)

print('=' * 70)
print('第89轮：FAIL %d 项 %s' % (len(_failed), _failed if _failed else ''))
print('=' * 70)
sys.exit(0 if not _failed else 1)
