# -*- coding: utf-8 -*-
u"""第186轮 · 把 ch1 那 5 间「进得去出不来」的房接出出口（数据侧）。

## 这一轮修的是什么

第185轮末的可达账里，ch1 有 9 间「有入边、零出边」的房。用户点名做其中 **5 间**
（另外 4 间是森林里压根不与主图连通的独立房，本轮不做）：

    room_forest_maze_susie      rid  93
    room_cc_prisonelevator      rid 109
    room_dark_chase2            rid  43
    room_alphysclass            rid  30
    room_cc_fountain            rid 130

根因**不是"路由表缺边"**，而是"房里根本没有能出去的东西"或"边需要的条件我们没表达"。
逐间的原作出处（全部来自本轮自己的反编译语料 `_evidence/codes/*.gml`）：

  1. `maze_susie`  `obj_doorX_Alarm_2` 里那一段：
         if (room == room_forest_maze_susie) {
             if (y >= (room_height / 2)) { flag[292]=0; flag[291]=0; room_goto(room_forest_savepoint_relax); }
             else                        { room_goto(room_forest_maze2); }
         }
     ★ `y` 是**门自己**的 y（不是玩家的）：房高 680 ⇒ 阈值 340。
       实测两扇门 y=665 / y=0 ⇒ 下门去 savepoint_relax、上门回 maze2。
     ⇒ 靠 `_original.axis='y' + door_y` 走第170轮的 `_pick_by_pos` 消歧。

  2. `cc_prisonelevator`  `obj_doorX_musfade_Alarm_2`：
         if (room == room_cc_prisonelevator) {
             flag[239]==0 -> room_cc_prison_to_elevator (rid 107)
             flag[239]==1 -> room_cc_1f                 (rid 114)
             flag[239]==2 -> room_cc_5f                 (rid 123)
             flag[239]==3 -> room_cc_prison_prejoker    (rid 111)
         }                                            ★ 无兜底
     而 `flag[239]` 是**「你从哪层来」**：三个来源房各自在离开时写死它
     （107→0 / 114→1 / 111→3；123 那路由 `obj_doorw_musfade` 写 2）。
     ⇒ 出口语义 = **回程**。用本轮新增的 `when_prev` 表达；flag 未写过（=0）的默认支
       单独一条（priority 更大），与 `global.flag` 缺省 0 一致。

  3. `dark_chase2`  `obj_lancerslideevent_Step_0`：
         if (slidetimer == 540) { ...; room_goto_next(); }
     rid 43 的下一间 = **rid 44 `room_castle_outskirts`**（不是 dark_chase1，
     42 才是 chase1）。⇒ 过场触发器，落到我们这儿等价"一扇门"。

  4. `alphysclass`  `obj_classscene_Create_0`：
         if (global.plot >= 3) { doorb = instance_create(242, 48, obj_doorB); ... }
     而 `obj_doorB_Alarm_2` = `room_goto_previous()` ⇒ rid 29 `room_schoollobby`
     （A 门进来 +1、B 门出去 −1，正好是一对）。
     ★ 这扇门是**运行时创建**的，静态实例表里没有 ⇒ 场景物件要手工补。

  5. `cc_fountain`  `obj_fountainkris_Step_0` con==12 → `instance_create(..., obj_darkfountain_event)`
     → `obj_darkfountain_event_Draw_0` 的 `if (t >= 650) { scr_become_light(); room_goto(room_school_unusedroom); }`
     ⇒ 落点 **rid 33 `room_school_unusedroom`**，而这间房**从来没登记成场景** ⇒
       本轮补登记 `ch1.hometown.school_unusedroom`（它自己还有一扇 D 门 → rid 31 schooldoor）。

## 纪律

  · **幂等**：重复跑不会重复加（第180轮铁律：禁"存在就 assert 退"，要"逐字段核验后覆盖"）。
  · **格式逐字节保持**：先做"空转往返"自证 —— 不改内容 dump 一遍必须与原文**完全相同**
    （`_index.json` / `_routes.json` 尾无换行且全 CRLF；`_zone.*.json` 尾有换行）。
  · **零改 main.py**（本轮数据侧就这些）。
  · 每条新边都带 `_original` 出处（文件名 + 行号上下文），供 `check186` 对账。

用法：
    python apply186.py --check     # 只核验与预演，不写盘
    python apply186.py --write     # 写盘
"""
import argparse
import collections
import io
import json
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
SCENES = os.path.join(REPO, 'ralsei_pet', 'assets', 'scenes')

P_INDEX = os.path.join(SCENES, '_index.json')
P_ROUTES = os.path.join(SCENES, '_routes.json')
P_ZONE_HOMETOWN = os.path.join(SCENES, '_zone.ch1.hometown.json')
P_ZONE_DARKWORLD = os.path.join(SCENES, '_zone.ch1.dark_world.json')

#: 新登记的场景（rid 33）。物件取自本轮 `_evidence/all_rooms186.json` 的一手实例表。
NEW_SID = 'ch1.hometown.school_unusedroom'
#: ★★★ 背景：第一版把 `bg` 留空、`bg_source` 写 `none` —— 那是**谎报**，
#:   `bg_round39.B1` 当场抓住：这间房在原作里 `bg_sprite = bg_unusedclass`
#:   （尺寸 320×240 ≥ 300×200）⇒ 属"真背景"，必须如实登记三元组。
#:   PNG 按第 39 轮口径**原样复制、不缩放**：
#:   `E:\Download\_tmp\dr_out\chapter1_windows\Sprites\bg_unusedclass_0.png`（7,025 B）
#:   → `assets/scenes/bg/ch1_hometown_school_unusedroom.png`。
NEW_NODE = collections.OrderedDict([
    ('name', u'家乡·school_unusedroom'),
    ('name_raw', 'room_school_unusedroom'),
    ('name_derived', True),
    ('original_room_id', 33),
    ('bg', 'bg/ch1_hometown_school_unusedroom.png'),
    ('bg_source', 'room.bg_layer'),
    ('bg_asset', 'bg_unusedclass'),
])
NEW_OBJS = [
    # (pos, sprite, src) —— 顺序 = 原作实例表顺序（与既有分片一致）
    ([140, 180], 'objs/spr_doorD_0.png', 'obj_doorD'),
    ([150, 136], 'objs/spr_markerC_0.png', 'obj_markerC'),
    ([138, 42], 'objs/spr_event_0.png', 'obj_unusedclassevent'),
    ([46, 100], 'objs/spr_interactable_0.png', 'obj_readable_room1'),
    ([110, 94], 'objs/spr_interactable_0.png', 'obj_readable_room1'),
    ([168, 126], 'objs/spr_interactable_0.png', 'obj_readable_room1'),
    ([166, 84], 'objs/spr_interactable_0.png', 'obj_readable_room1'),
    ([226, 90], 'objs/spr_interactable_0.png', 'obj_readable_room1'),
    ([256, 90], 'objs/spr_interactable_0.png', 'obj_readable_room1'),
]

#: 既有场景要补的物件（原作里是运行时创建 / 我们没收进来的触发器）
ADD_OBJS = {
    'ch1.hometown.alphysclass': [
        ([242, 48], 'objs/spr_doorB_0.png', 'obj_doorB'),
    ],
    'ch1.dark_world.dark_chase2': [
        ([280, 160], 'objs/spr_event_0.png', 'obj_lancerslideevent'),
    ],
}

PRIO_BASE = 9100          # ★ 现表最大 priority = 9002，9100 起是干净区间

GML_X = 'gml_Object_obj_doorX_Alarm_2'
GML_XM = 'gml_Object_obj_doorX_musfade_Alarm_2'
GML_SLIDE = 'gml_Object_obj_lancerslideevent_Step_0'
GML_CLASS = 'gml_Object_obj_classscene_Create_0'
GML_FK = 'gml_Object_obj_fountainkris_Step_0'
GML_DFE = 'gml_Object_obj_darkfountain_event_Draw_0'

MAZE = 'ch1.forest.forest_maze_susie'
ELEV = 'ch1.card_castle.cc_prisonelevator'


def _o(**kw):
    d = collections.OrderedDict()
    d['chapter'] = 'ch1'
    for k, v in kw.items():
        d[k] = v
    return d


#: 11 条新边。`kind` 只写在 `_original` 里给人看，产品只认顶层那 6 个键。
ROUTES = [
    # ---- 1/2: maze_susie 两扇 X 门（按门自身 y 分流）----
    dict(to='ch1.forest.forest_before_maze', when_scene=MAZE, when_door='X',
         reason=(u'原作连接：从 猩红森林·maze_susie 的 X 门离开。`%s` 里这一段按'
                 u'**门自身的 y** 分流 —— `if (y >= (room_height / 2))`（房高 680 ⇒ 阈值 340）'
                 u'⇒ 这扇门在 y=665（下半），落到 `room_forest_savepoint_relax`。' % GML_X),
         _original=_o(kind='delta_door_pos', table=GML_X, via='obj_doorX',
                      marker='obj_markerX', axis='y', door_x=280, door_y=665,
                      cond='y >= room_height/2', src_room_name='room_forest_maze_susie',
                      dst_room_name='room_forest_savepoint_relax',
                      src_room_id=93, dst_room_id=90)),
    dict(to='ch1.forest.forest_maze2', when_scene=MAZE, when_door='X',
         reason=(u'原作连接：同一段 `%s` 的**另一支** —— 门 y=0 在下半阈值之上'
                 u'（`else` 分支）⇒ 回 `room_forest_maze2`。两扇门同字母，靠门实例坐标消歧。'
                 % GML_X),
         _original=_o(kind='delta_door_pos', table=GML_X, via='obj_doorX',
                      marker='obj_markerX', axis='y', door_x=280, door_y=0,
                      cond='y < room_height/2', src_room_name='room_forest_maze_susie',
                      dst_room_name='room_forest_maze2',
                      src_room_id=93, dst_room_id=94)),
    # ---- 3~5: prisonelevator 三条「按来路」支 ----
    #: ★★★ 第186轮定稿时**删掉了「来路=牢廊」那一条**：`flag[239]==0` 的落点
    #:   `room_cc_prison_to_elevator` 与下面那条默认支**同门同目标** ⇒ 造出一组
    #:   "同门重复"（check124 D2 / check171 E1 / check172 D1 一起报红）。
    #:   而语义上它本来就是多余的：默认支的条件更弱（无 `when_prev`）、目标相同，
    #:   所以"来路=牢廊"永远得到同一个结果 ⇒ 删掉不减少任何一条原创分支。
    dict(to='ch1.card_castle.card_castle_1f', when_scene=ELEV, when_door='X',
         when_prev='ch1.card_castle.card_castle_1f',
         reason=(u'原作连接：`%s` 里 `flag[239]==1` ⇒ `room_goto(room_cc_1f)`；'
                 u'1 是"从一层（114）上来"时写的值 ⇒ 回一层。' % GML_XM),
         _original=_o(kind='delta_door_flag', table=GML_XM, via='obj_doorX_musfade',
                      marker='obj_markerX', flag=239, flag_value=1, when_prev_room=114,
                      src_room_name='room_cc_prisonelevator', dst_room_name='room_cc_1f',
                      src_room_id=109, dst_room_id=114)),
    dict(to='ch1.card_castle.card_castle_5f', when_scene=ELEV, when_door='X',
         when_prev='ch1.card_castle.card_castle_5f',
         reason=(u'原作连接：`%s` 里 `flag[239]==2` ⇒ `room_goto(room_cc_5f)`；'
                 u'2 由 `gml_Object_obj_doorw_musfade_Alarm_2` 在从 `room_cc_elevator` '
                 u'下行时写入 ⇒ 回五层。' % GML_XM),
         _original=_o(kind='delta_door_flag', table=GML_XM, via='obj_doorX_musfade',
                      marker='obj_markerX', flag=239, flag_value=2, when_prev_room=123,
                      src_room_name='room_cc_prisonelevator', dst_room_name='room_cc_5f',
                      src_room_id=109, dst_room_id=123)),
    dict(to='ch1.card_castle.card_castle_unknown', when_scene=ELEV, when_door='X',
         when_prev='ch1.card_castle.card_castle_unknown',
         reason=(u'原作连接：`%s` 里 `flag[239]==3` ⇒ `room_goto(room_cc_prison_prejoker)`；'
                 u'3 是"从 111 号？？？（prejoker）上来"时写的值 ⇒ 回原房。' % GML_XM),
         _original=_o(kind='delta_door_flag', table=GML_XM, via='obj_doorX_musfade',
                      marker='obj_markerX', flag=239, flag_value=3, when_prev_room=111,
                      src_room_name='room_cc_prisonelevator',
                      dst_room_name='room_cc_prison_prejoker',
                      src_room_id=109, dst_room_id=111)),
    # ---- 7: 默认支（`global.flag` 缺省 0）----
    dict(to='ch1.card_castle.card_castle_prison', when_scene=ELEV, when_door='X',
         reason=(u'原作连接（默认支）：`%s` 里 `flag[239]` 四支**无兜底**，但 `global.flag` '
                 u'缺省就是 0 ⇒ 从没坐过电梯（= 我们不知道来路）时落到 '
                 u'`room_cc_prison_to_elevator`（107）。' % GML_XM),
         _original=_o(kind='delta_door_flag', table=GML_XM, via='obj_doorX_musfade',
                      marker='obj_markerX', flag=239, flag_value=0, when_prev_room=None,
                      src_room_name='room_cc_prisonelevator',
                      dst_room_name='room_cc_prison_to_elevator',
                      src_room_id=109, dst_room_id=107)),
    # ---- 8: dark_chase2 滑行过场 ----
    dict(to='ch1.castle_town.castle_outskirts', when_scene='ch1.dark_world.dark_chase2',
         when_src='obj_lancerslideevent',
         reason=(u'原作连接：`%s` 在 `if (slidetimer == 540)` 时 `room_goto_next()`；'
                 u'rid 43 的下一间是 **rid 44 `room_castle_outskirts`**（42 才是 chase1）。'
                 u'过场触发器落到我们这儿等价一扇门。' % GML_SLIDE),
         _original=_o(kind='gml_room_goto_next', code=GML_SLIDE, via='obj_lancerslideevent',
                      cond='slidetimer == 540', src_room_name='room_dark_chase2',
                      dst_room_name='room_castle_outskirts',
                      src_room_id=43, dst_room_id=44)),
    # ---- 9: alphysclass 运行时 doorB ----
    dict(to='ch1.hometown.schoollobby', when_scene='ch1.hometown.alphysclass',
         when_door='B', when_src='obj_doorB',
         reason=(u'原作连接：`%s` 在 `if (global.plot >= 3)` 时 `instance_create(242, 48, obj_doorB)`；'
                 u'`obj_doorB_Alarm_2` = `room_goto_previous()` ⇒ rid 29 `room_schoollobby`'
                 u'（A 门 +1 进来、B 门 −1 出去，正好一对）。★ 这扇门原作是**运行时创建**的。'
                 % GML_CLASS),
         _original=_o(kind='runtime_door', code=GML_CLASS, via='obj_doorB',
                      marker='obj_markerB', cond='global.plot >= 3', door_x=242, door_y=48,
                      src_room_name='room_alphysclass', dst_room_name='room_schoollobby',
                      src_room_id=30, dst_room_id=29)),
    # ---- 10: cc_fountain 闭泉演出 ----
    dict(to=NEW_SID, when_scene='ch1.card_castle.cc_fountain', when_src='obj_fountainkris',
         reason=(u'原作连接：`%s` 的 `con == 12` 会 `instance_create(..., obj_darkfountain_event)`，'
                 u'那个对象的 Draw 在 `if (t >= 650)` 时 `scr_become_light()` 并 '
                 u'`room_goto(room_school_unusedroom)`（rid 33）⇒ 闭泉后回光世界。'
                 % GML_FK),
         _original=_o(kind='gml_cutscene_goto', code=GML_DFE, via='obj_fountainkris',
                      cond='obj_fountainkris.con==12 -> obj_darkfountain_event.t>=650',
                      src_room_name='room_cc_fountain',
                      dst_room_name='room_school_unusedroom',
                      src_room_id=130, dst_room_id=33)),
    # ---- 10: 新登记那间房自己的 D 门（33 − 2 = 31）----
    dict(to='ch1.hometown.schooldoor', when_scene=NEW_SID, when_door='D',
         reason=(u'原作连接：`room_school_unusedroom`（rid 33）的 D 门 = 房间数组下标 −2 '
                 u'⇒ rid 31 `room_schooldoor`；目标房含 `obj_markerD`。'),
         _original=_o(kind='delta_door_shift', via='obj_doorD', marker='obj_markerD',
                      door_letter='D', shift=-2,
                      src_room_name='room_school_unusedroom',
                      dst_room_name='room_schooldoor', src_room_id=33, dst_room_id=31)),
    # ---- 11: 回程的另一半 —— schooldoor 自己那扇 C 门（31 + 2 = 33）----
    #: ★★★ 第186轮补：`room_schooldoor`(31) 里本来就有一扇 `obj_doorC`（实例坐标
    #:   (500, 95)，见 `_zone.ch1.hometown.json`），按 C = 下标 +2 正好回到 rid 33。
    #:   本条是 check181 D1「漏加 1」逼出来的：那间房原来**没登记**，这条实例落在
    #:   "目标未登记"桶里；一旦把 33 登记成场景，它就必须真有一条边，否则就是账上缺口。
    dict(to=NEW_SID, when_scene='ch1.hometown.schooldoor', when_door='C',
         reason=(u'原作连接：`room_schooldoor`（rid 31）的 C 门 = 房间数组下标 +2 '
                 u'⇒ rid 33 `room_school_unusedroom`（与上面那条 D 门互逆，一进一出）。'
                 u'目标房含 `obj_markerC`。'),
         _original=_o(kind='delta_door_shift', via='obj_doorC', marker='obj_markerC',
                      door_letter='C', shift=2, src_room_name='room_schooldoor',
                      dst_room_name='room_school_unusedroom', src_room_id=31, dst_room_id=33)),
]

EXPECT_ROUTES = 11


# --------------------------------------------------------------------- IO
def load(path):
    """读 JSON（文本保真：不做任何替换），返回 (obj, 原始字节)。"""
    raw = io.open(path, 'rb').read()
    return json.loads(raw.decode('utf-8')), raw


def _dumps(obj, indent, level=0, inline_scalars=True):
    u"""按本目录 JSON 的**实际排版**序列化（不是 `json.dumps(indent=)` 的默认形状）。

    实测差异（第186轮，空转自证抓出来的）：
      · 字典 → 多行，每层缩 `indent` 个空格；
      · **标量数组**：分片/索引里**单行内联**（`"pos": [120, 410]`），
        但 `_routes.json` 里是**逐行**（`"how_it_works": ["1. …", "2. …"]` 被拆开）。
        两种排版在同一目录里并存 ⇒ 按文件传 `inline_scalars`；
      · 空数组 / 空字典 → `[]` / `{}` 内联；
      · 数组里含容器（`objects`）→ 多行，元素各自成块。
    """
    pad = ' ' * (indent * (level + 1))
    end = ' ' * (indent * level)
    if isinstance(obj, dict):
        if not obj:
            return '{}'
        parts = ['%s%s: %s' % (pad, json.dumps(k, ensure_ascii=False),
                               _dumps(v, indent, level + 1, inline_scalars))
                 for k, v in obj.items()]
        return '{\n' + ',\n'.join(parts) + '\n' + end + '}'
    if isinstance(obj, (list, tuple)):
        if not obj:
            return '[]'
        if inline_scalars and all(not isinstance(x, (dict, list, tuple)) for x in obj):
            return '[%s]' % ', '.join(json.dumps(x, ensure_ascii=False) for x in obj)
        parts = [pad + _dumps(x, indent, level + 1, inline_scalars) for x in obj]
        return '[\n' + ',\n'.join(parts) + '\n' + end + ']'
    return json.dumps(obj, ensure_ascii=False)


def dump(obj, trailing_newline, indent=2, inline_scalars=True):
    """把 obj 摊成该文件的**原样格式**：CRLF + `indent`（+ 可选尾换行）。

    ★ 缩进**不是全仓统一**的（实测第186轮）：
        `_index.json` / `_routes.json`   → indent=2，**尾无换行**
        `_zone.<ch>.<area>.json`         → indent=**1**，**尾有换行**
      第一版一律按 indent=2 ⇒ 分片 39,861 字节被重排成 57,186 字节，
      首个差异落在第 4 字节（`{\\r\\n "` vs `{\\r\\n  "`）—— 空转自证当场抓住。
    """
    text = _dumps(obj, indent, 0, inline_scalars)
    if trailing_newline:
        text += '\n'
    return text.replace('\n', '\r\n').encode('utf-8')


def selfcheck_format(obj, raw, trailing_newline, name, indent=2, inline_scalars=True):
    """★ 空转往返自证：不改内容 dump 一遍必须与原文**逐字节相同**。

    这条不通过就说明我的 dumper 与文件的真实格式不一致（缩进 / 行尾 / 尾换行 /
    ensure_ascii），此时**任何**写入都会把整个文件重排 —— 那种 diff 无法与
    "我真改了什么"区分开。所以宁可直接报错退出。
    """
    got = dump(obj, trailing_newline, indent, inline_scalars)
    if got != raw:
        d = 0
        for i in range(min(len(got), len(raw))):
            if got[i] != raw[i]:
                d = i
                break
        raise SystemExit(u'%s 格式往返不一致（原文 %d 字节 / 重排 %d 字节，首个差异在 %d）'
                         % (name, len(raw), len(got), d))
    return True


# ------------------------------------------------------------------ 变更
def upsert_scene(index, zone, stats):
    """把新场景登记进 `_index.json` 与区域分片。已存在则**逐字段核验后覆盖**。"""
    area = index['chapters']['ch1']['areas']['hometown']
    scenes = area['scenes']
    zscenes = zone['scenes']

    node = collections.OrderedDict(NEW_NODE)
    if NEW_SID in scenes:
        if scenes[NEW_SID] != node:
            stats['scene_index_replace'] += 1
        scenes[NEW_SID] = node
    else:
        # 按 rid 顺序插在 insidecloset(32) 之后，保持文件可读
        rebuilt = collections.OrderedDict()
        placed = False
        for k, v in scenes.items():
            rebuilt[k] = v
            if k == 'ch1.hometown.insidecloset':
                rebuilt[NEW_SID] = node
                placed = True
        if not placed:
            rebuilt[NEW_SID] = node
        area['scenes'] = rebuilt
        stats['scene_index_add'] += 1

    full = collections.OrderedDict(NEW_NODE)
    full['objects'] = [collections.OrderedDict(
        [('pos', pos), ('sprite', sp), ('src', src), ('depth', 0)])
        for pos, sp, src in NEW_OBJS]
    if NEW_SID in zscenes:
        if zscenes[NEW_SID] != full:
            stats['scene_zone_replace'] += 1
        zscenes[NEW_SID] = full
    else:
        zscenes[NEW_SID] = full
        stats['scene_zone_add'] += 1
    return stats


def add_objects(zone, sid, items, stats):
    """给既有场景补物件。判重键 = (src, pos) 全等（重复跑不会加第二份）。"""
    sc = (zone.get('scenes') or {}).get(sid)
    if sc is None:
        stats['obj_missing_scene'] += 1
        return stats
    have = set()
    for o in (sc.get('objects') or []):
        if isinstance(o, dict):
            try:
                have.add((o.get('src'), tuple(o.get('pos') or ())))
            except TypeError:
                pass
    lst = sc.setdefault('objects', [])
    for pos, sp, src in items:
        if (src, tuple(pos)) in have:
            stats['obj_dup'] += 1
            continue
        lst.append(collections.OrderedDict(
            [('pos', pos), ('sprite', sp), ('src', src), ('depth', 0)]))
        stats['obj_add'] += 1
    return stats


def _route_key(r):
    return (r.get('when_scene'), r.get('when_door'), r.get('when_src'),
            r.get('when_prev'), r.get('to'))


def upsert_routes(raw, stats):
    """11 条边入库。**先整段清空本轮的 priority 区间，再按 ROUTES 重写**。

    ★★★ 为什么不是"按键去重、缺哪条补哪条"（第一版写法，改对了数据也不收敛）：
      ① 键里含 `when_prev`，而本轮定稿**删掉了「来路=牢廊」那一条**（与默认支同门同目标）；
         按键去重只会"不再新增"，**删不掉**已经写进盘的那条 ⇒ 同门重复留在文件里；
      ② `priority = PRIO_BASE + i` 是**按 `ROUTES` 下标**算的，删除中间一条会让后面全体
         前移一位；而按键去重保留下来的老条目**不会重排** ⇒ 区间里出现空洞、兜底支不再是
         四支里最后一个 ⇒ 升序裁决（priority 小者胜）会把兜底支顶到具体支前面，
         `when_prev` 的三条分支**永远不生效**（这是最隐蔽的一种"改完还是错的"）。
      整段清空后重写，跑几次结果都完全一致（幂等），且兜底支必然落在三条之后。
    """
    routes = raw['routes']
    lo, hi = PRIO_BASE, PRIO_BASE + len(ROUTES)      # 只清自己这一段，不动 9001/9002 等历史段
    kept = [r for r in routes
            if not (isinstance(r, dict) and isinstance(r.get('priority'), int)
                    and lo <= r['priority'] < hi)]
    stats['route_purge'] += len(routes) - len(kept)
    del routes[:]
    routes.extend(kept)
    n0 = len(routes)
    for i, spec in enumerate(ROUTES):
        entry = collections.OrderedDict()
        entry['to'] = spec['to']
        entry['priority'] = PRIO_BASE + i
        entry['reason'] = spec['reason']
        entry['when_scene'] = spec['when_scene']
        if spec.get('when_door'):
            entry['when_door'] = spec['when_door']
        if spec.get('when_src'):
            entry['when_src'] = spec['when_src']
        if spec.get('when_prev'):
            entry['when_prev'] = spec['when_prev']
        entry['_original'] = spec['_original']
        routes.append(entry)
        stats['route_add'] += 1
    stats['route_delta'] = len(routes) - n0
    return stats


NOTE = (u'★ 第186轮：ch1 五间「进得去出不来」的房接上出口，新增 **11** 条（priority '
        u'9100~9110），并新登记场景 `ch1.hometown.school_unusedroom`（rid 33）。'
        u'根因不是缺边，而是"房里没有能出去的东西"或"边要的条件表达不了"：'
        u'`forest_maze_susie` 两扇 X 门靠**门自身 y**（≥340 去 savepoint_relax、<340 回 maze2，'
        u'`obj_doorX_Alarm_2`）；`cc_prisonelevator` 读 `flag[239]` = **你从哪层来** '
        u'（107→0/114→1/123→2/111→3，**无兜底**），用本轮新增的 `when_prev` 表达 1/2/3 三支，'
        u'外加一条默认支兜住 flag=0 与"来路未知"（两者落点相同，故只留一条，不造同门重复）；'
        u'`dark_chase2` 是 `slidetimer==540` 的 `room_goto_next()` '
        u'（rid 43→**44 castle_outskirts**）；`alphysclass` 的出口是 `obj_classscene_Create_0` 里 '
        u'`if (global.plot>=3) instance_create(242,48,obj_doorB)` —— **运行时创建**的门，'
        u'静态实例表里没有；`cc_fountain` 需先闭泉（`obj_fountainkris` con==12 → '
        u'`obj_darkfountain_event` t>=650）再 `room_goto(room_school_unusedroom)`。 '
        u'生成器 `code-quality-audit/第186轮-修有入无出/_tools/apply186.py`。')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true')
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args()
    write = args.write and not args.check

    stats = collections.Counter()

    index, raw_index = load(P_INDEX)
    routes, raw_routes = load(P_ROUTES)
    zone_h, raw_zh = load(P_ZONE_HOMETOWN)
    zone_d, raw_zd = load(P_ZONE_DARKWORLD)

    # ① 格式自证（四份文件，写入前先证明 dumper 与原文逐字节一致）
    selfcheck_format(index, raw_index, False, '_index.json')
    selfcheck_format(routes, raw_routes, False, '_routes.json', inline_scalars=False)
    selfcheck_format(zone_h, raw_zh, True, '_zone.ch1.hometown.json', indent=1)
    selfcheck_format(zone_d, raw_zd, True, '_zone.ch1.dark_world.json', indent=1)
    print(u'[1] 格式往返自证：4/4 逐字节一致')

    n_scene_before = sum(len(a.get('scenes') or {})
                         for c in index['chapters'].values()
                         for a in (c.get('areas') or {}).values())
    n_route_before = len(routes['routes'])
    print(u'[2] 改前：场景 %d 条 · 路由 %d 条' % (n_scene_before, n_route_before))

    # ② 场景登记
    upsert_scene(index, zone_h, stats)
    # ③ 既有场景补物件
    add_objects(zone_h, 'ch1.hometown.alphysclass',
                [(pos, sp, src) for pos, sp, src in ADD_OBJS['ch1.hometown.alphysclass']], stats)
    add_objects(zone_d, 'ch1.dark_world.dark_chase2',
                [(pos, sp, src) for pos, sp, src in ADD_OBJS['ch1.dark_world.dark_chase2']], stats)
    # ④ 路由
    upsert_routes(routes, stats)

    n_scene_after = sum(len(a.get('scenes') or {})
                        for c in index['chapters'].values()
                        for a in (c.get('areas') or {}).values())
    n_route_after = len(routes['routes'])
    print(u'[3] 改后：场景 %d 条（+%d）· 路由 %d 条（+%d）'
          % (n_scene_after, n_scene_after - n_scene_before,
             n_route_after, n_route_after - n_route_before))
    print(u'[4] 明细：%s' % dict(sorted(stats.items())))

    if n_route_after - n_route_before not in (0, EXPECT_ROUTES):
        raise SystemExit(u'新增边 %d 条 ∉ {0, %d} —— 拒绝写入'
                         % (n_route_after - n_route_before, EXPECT_ROUTES))
    #: ★ 绝对对账（不随上下文变）：改前 2,832 + 本轮 11 == 2,843。
    #:   有这一条，"整段清空再重写"就不可能悄悄多出或少掉条数（比如区间算错把 9,0xx 也清了）。
    if n_route_after != 2843:
        raise SystemExit(u'路由总数 %d ≠ 2843（2,832 + 11）—— 拒绝写入' % n_route_after)
    if n_route_after == n_route_before:
        # ★ 幂等复跑路径（第180轮铁律：**禁**"已存在就 assert 退"，也禁"重复加一遍"）。
        #   走到这里说明 11 条全在、场景也全在 ⇒ 本次就是一次 no-op，照常往下走
        #   （仍然重写文件，让"内容 == 期望"这件事被逐字节确认一次）。
        print(u'[4b] 已应用过（11 条全在 / 场景全在）⇒ 本次为 no-op，不重复添加')

    # ⑤ 自洽：每条新边的目标必须在索引里、出发场景必须在索引里
    scenes = {}
    for cid, ch in index['chapters'].items():
        for aid, ar in (ch.get('areas') or {}).items():
            for sid in (ar.get('scenes') or {}):
                scenes[sid] = (cid, aid)
    bad = []
    for spec in ROUTES:
        for k in ('when_scene', 'to'):
            if spec[k] not in scenes:
                bad.append((k, spec[k]))
    if bad:
        raise SystemExit(u'新边引用了未登记的场景：%r' % bad)
    print(u'[5] 自洽：11 条边的两端场景全部已登记（场景总数 %d）' % len(scenes))

    # ⑥ note
    if u'第186轮' not in (routes['meta'].get('note') or ''):
        routes['meta']['note'] = (routes['meta'].get('note') or '') + NOTE
        print(u'[6] meta.note 已追加第186轮说明')
    else:
        print(u'[6] meta.note 已含第186轮说明（幂等跳过）')

    if not write:
        print(u'[7] --check 模式：**未写盘**')
        return 0

    for path, obj, trail, ind, inl in (
            (P_INDEX, index, False, 2, True), (P_ROUTES, routes, False, 2, False),
            (P_ZONE_HOMETOWN, zone_h, True, 1, True),
            (P_ZONE_DARKWORLD, zone_d, True, 1, True)):
        blob = dump(obj, trail, ind, inl)
        with io.open(path, 'wb') as fh:
            fh.write(blob)
        print(u'[8] 写 %-30s %9d 字节' % (os.path.basename(path), len(blob)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
