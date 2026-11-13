# 第186轮报告 · ch1 五间「进得去出不来」的房接上出口

> 范围（用户裁定「**5 间全做（含无门的）**」）：
> `forest_maze_susie`（X 门按门自身 y 分流）· `cc_prisonelevator`（一扇门四去向，按"来路"）
> · `dark_chase2`（出口是滑行过场）· `alphysclass`（出口是**运行时创建**的门）
> · `cc_fountain`（闭泉演出才走）。
> 判据 `check186`（**33 条**）· 变异 `mutate186`（**14 条，14 报红 0 漏网**）
> · `_routes.json` **2,832 → 2,843**（+11）· `_index.json` **2,167 → 2,168**（+1）
> · 物件 **+11** · 新场景带**真背景**

---

## §1 为什么做这一轮

第185轮把 ch1 森林的 1/50 隐藏房投用后，收口时按"**每间 playable 房的出边数**"扫了一遍
全库，发现有 5 间 ch1 的房 **`out == 0`**：它们都能被走到（入边 1~3 条），但**没有任何
一条从它们出去的边** —— 真机上表现为"推门没反应 / 卡在这间房里"。

这不是"缺数据"，是**一类能力缺口**。第186轮就是把它补上。

---

## §2 三条口径（用户逐条裁定，不要重问）

| 项 | 裁定 | 为什么这么定 |
|---|---|---|
| 本轮做什么 | ch1 那 5 间「进得去出不来」 | 其余候选都是"取证轮"，这 5 间是唯一能"做成"的 |
| 范围 | **5 间全做（含无门的）** | 只做"有门的"会留下 3 间永远出不去，等于没做 |
| `cc_fountain` 落点 rid 33 未登记 | **登记成新场景再接边** | 不登记就只能接一条"去了不存在的房"的假边 |
| `cc_prisonelevator` 四分支 | **加"来路"状态，4 条全生效** | 只做兜底 1 条 = 三层楼的玩家全被送回牢廊 |

---

## §3 ★★★ 根因不是"缺边"，是两类

先把结论摆在前面，因为它决定了改哪一层：

| 类型 | 房间 | 具体表现 |
|---|---|---|
| **① 房里没有"能出去的东西"** | `dark_chase2` | 出口对象 `obj_lancerslideevent` **压根没进过 objects 表**（分类器当 cutscene 跳过） |
| | `alphysclass` | 出口 `obj_doorB` 是**运行时创建**的（`instance_create`），静态实例表里永远查不到 |
| | `cc_fountain` | 出口不是门，是**闭泉演出的收尾**（`Draw` 里 `t>=650` 才 `room_goto`） |
| **② 边要的条件我们表达不了** | `forest_maze_susie` | **同字母两扇 X 门**，靠**门自身 y** 分流 |
| | `cc_prisonelevator` | **一扇门四个去向**，靠 `flag[239]`（= 你从哪层来） |

⇒ 只有 ② 需要动**机制**（新增 `when_prev` / 用既有 `door_y`）；
① 全是**数据 + 分类**问题（登记对象、改判类别、接一条无门的路由）。

---

## §4 原作证据（反编译留档 `_evidence/codes/*.gml`，逐字）

```
obj_doorX_Alarm_2（maze_susie）
    if (y >= room_height / 2)  → room_goto(room_forest_savepoint_relax)
    else                       → room_goto(room_forest_maze2)
    房高 680 ⇒ 阈值 340；实测两扇门 y = 665 / y = 0

obj_doorX_musfade_Alarm_2（prisonelevator）★ 无兜底
    flag[239] == 0 → room_cc_prison_to_elevator (107)
    flag[239] == 1 → room_cc_1f                 (114)
    flag[239] == 2 → room_cc_5f                 (123)
    flag[239] == 3 → room_cc_prison_prejoker    (111)

obj_lancerslideevent_Step_0（dark_chase2）
    if (slidetimer == 540) room_goto_next()      ⇒ rid 43 → 44（castle_outskirts）
    ★ 42 才是 dark_chase1 —— "下一间"不是"上一间"

obj_classscene_Create_0（alphysclass）★ 逐字
    ...
    if (global.plot >= 3)
    {
        doorb = instance_create(242, 48, obj_doorB);
        ...
        instance_destroy();          // 把 obj_classscene 自己销毁
    }
obj_doorB_Alarm_2（trans_codes186.json 逐字）
    with (obj_overworldbulletparent) { active = 0; }
    global.entrance = 2;  instance_create(0, 0, obj_persistentfadein);
    room_goto_previous()             ⇒ rid 30 → 29（schoollobby）

obj_fountainkris_Step_0（cc_fountain）
    con == 12 && !instance_exists(obj_writer)
        → instance_create(..., obj_darkfountain_event)
    obj_darkfountain_event.Draw  t >= 650
        → global.entrance = 0; global.interact = 1; scr_become_light();
          snd_free_all(); instance_create(0, 0, obj_persistentfadein);
          room_goto(room_school_unusedroom)                      ⇒ rid 33
```

### 4.1 ★ 一个容易错的细节：`obj_doorB` 有**两个**创建点

| 出处 | 坐标 | 何时 | 我们取哪个 |
|---|---|---|---|
| `obj_classscene_Create_0` | **(242, 48)** | 进房时 `global.plot >= 3`（过场已看完） | ✅ **取这个** |
| `obj_classscene_Step_0`（`con == 57`） | (242, **51**) | 过场**刚看完**那一帧，顺手 `global.plot = 3`，下次进房才走上面那支 | 不取 |

差 3px。取 `Create_0` 的理由：**玩家能自由操作这扇门的时候，走的一定是 Create_0 那支**
（`plot >= 3` 才会留下门）；`Step_0` 那 3px 只存在于过场最后一帧。
⇒ `_original.door_y = 48`，`cond = 'global.plot >= 3'`（都是原文，不是估的）。

**`flag[239]` 的语义就是"来路"** —— 这不是我编的映射，是四个落点本身在说话：
107（回牢廊）/ 114（一层）/ 123（五层）/ 111（牢廊前厅）。原作靠 flag 记住"从哪层进的电梯"，
我们等价地记"上一个场景 id"。

---

## §5 机制：`when_prev`（新增一路）

### 5.1 三个必须同时成立的性质

1. **`when_prev` 缺席即判不匹配（fail-closed）**。
   放行等于"凭空指定一扇门" —— 不知道来路却给你选一条具体支，是编造。
2. **兜底必须由另一条不带 `when_prev` 的规则承担**。
   因为 (1)，"不知道来路"永远匹配不上任何带 `when_prev` 的规则；
   所以 `flag==0` 那条（回牢廊）只能写成**无 `when_prev` 的默认支**。
3. **兜底的 `priority` 必须比三条具体支都大**。
   `priority` 是**升序**裁决（数值小者胜、同号按声明序）——
   兜底放前面会让三条 `when_prev` 支**永远不生效**，而且**不报错**。

### 5.2 接线（三处，缺一即静默失效）

| 位置 | 改动 |
|---|---|
| `scene_routing._match_one` | 按 `route.get('when_prev')` 加分；`_prev_ok(prev, want)` |
| `item_interact.route_for_door(..., prev=)` | `_pick` 与 `_letter_ok` **都**过 `_prev_ok` |
| `item_interact.build_props(..., prev=)` | 透传给 `route_for_door` |
| `scene_controller.switch()` | 记 `pet._scene_prev = 上一个 current_scene` |
| `main.py` | ① **预声明** `self._scene_prev = None`；② `_rebuild_item_props` 传 `prev=` |

> ★ `main.py` 里那句**预声明**不是多余的：`__setattr__` 会把新属性转发到状态层，
> 不预声明就把同一个字段劈成两份（记忆 §84 的老坑）。

★ `_letter_ok` 故意**跳过**带 `when_src` 的条目 —— 所以**对象级路径不受 `when_prev` 影响**，
第122轮"对象级优先"的契约一字未动。

---

## §6 数据：11 条边（priority 9100~9110）

| # | 从 | 门 | 到 | 条件 | 原作依据 |
|---|---|---|---|---|---|
| 9100 | `forest_maze_susie` | X | `forest_before_maze` | `door_y=665` | `y >= 340` |
| 9101 | `forest_maze_susie` | X | `forest_maze2` | `door_y=0` | `y < 340` |
| 9102 | `cc_prisonelevator` | X | `card_castle_1f` | `when_prev=card_castle_1f` | `flag==1` |
| 9103 | `cc_prisonelevator` | X | `card_castle_5f` | `when_prev=card_castle_5f` | `flag==2` |
| 9104 | `cc_prisonelevator` | X | `card_castle_unknown` | `when_prev=card_castle_unknown` | `flag==3` |
| 9105 | `cc_prisonelevator` | X | `card_castle_prison` | **默认支**（无 `when_prev`） | `flag==0` |
| 9106 | `dark_chase2` | — | `castle_outskirts` | `when_src=obj_lancerslideevent` | `room_goto_next()` |
| 9107 | `alphysclass` | B | `schoollobby` | `when_src=obj_doorB` | `room_goto_previous()` |
| 9108 | `cc_fountain` | — | `school_unusedroom` | `when_src=obj_fountainkris` | `t>=650` 闭泉 |
| 9109 | `school_unusedroom` | D | `schooldoor` | 位移 **-2** | D = 下标 -2 |
| 9110 | `schooldoor` | C | `school_unusedroom` | 位移 **+2** | C = 下标 +2 |

### 6.1 ★ 定稿时**砍掉**的一条

原本还写了第 5 条电梯支（`flag==0` 显式写成 `when_prev=card_castle_prison`）。
定稿时**删掉**：它与默认支**同门同目标**，会造出一组"同门重复"，
`check124 D2` / `check171 E1` / `check172 D1` 三处一起报红。
删掉**不减任何原作分支** —— 落点完全相同（107），只是让"默认"来承担 flag==0。

### 6.2 新场景 `ch1.hometown.school_unusedroom`（rid 33）

| 字段 | 值 |
|---|---|
| 物件 | **9 个**（`obj_doorD` + `obj_markerC` + `obj_unusedclassevent` + 6 × `obj_readable_room1`） |
| 背景 | `bg/ch1_hometown_school_unusedroom.png`（**7,025 字节**，原作 `bg_unusedclass` 320×240 **原样复制、不缩放**，第39轮口径） |
| 三元组 | `bg_source=room.bg_layer` / `bg_asset=bg_unusedclass` |

★ 背景这一项**我第一版填的是 `bg=None` + `bg_source='none'`** —— 那是**谎报**
（原作 `bg_sprite = bg_unusedclass`，320×240 已满足 ≥300×200 的采集门槛），
被 `bg_round39 B1/B3` 当场抓出。证据在 `_evidence/`，改法见 §9 第 ⑤ 条。

### 6.3 两处**类别**改动（产品，不是数据）

| 对象 | 原 | 现 | 为什么 |
|---|---|---|---|
| `obj_fountainkris` | `fountain` | **`door`** | 全 147 间房只在 `cc_fountain` 出现；原作它不是"可以进去的泉"，是**闭泉触发器**。落成泉会被送去 `FOUNTAIN_TARGET`（城堡镇）—— 那是产品通用玩法，不是这一间的原作行为。★ 同房的 `obj_darkfountain` **保持 fountain** |
| `obj_lancerslideevent` | （无登记 ⇒ cutscene 被跳过） | **`door`** | 本项目的"门"= 换房入口，不区分原作叫 door 还是 event；不登记 ⇒ 那间房永远出不去 |

---

## §7 判据 `check186`（33 条）

| 段 | 条数 | 内容 |
|---|---|---|
| A 数据 | 10 | 11 条边逐条在位 / priority 段正确 / **同门重复 == 0** / **本轮 11 条各自唯一** / 新场景登记 + 真背景 |
| B 纯函数 | 8 | `_prev_ok` / `_match_one` / `_pick` / `_letter_ok` 的语义（含"缺席即不匹配"） |
| C 接线 | 6 | AST 查三处真接线 + `main.py` 预声明 |
| D 端到端 | 5 | 真跑 `build_props` + **两条负控制** |
| E 自检 | 4 | 分母闸 / AST 常量扫盘符 / 条数固定 / 打印点计数 |

### 7.1 两条负控制

- **D4**：删掉「来路=一层」那条 ⇒ 来路=一层 必须落**默认支**（牢廊）。
- **D5**：把三条 `when_prev` **全拆掉** ⇒ 来路=五层 也**拿不到**五层（塌成最小 priority 那支）。

> ★ D5 第一版是"删掉兜底那条 ⇒ 落回牢廊"，定稿砍掉第 5 条后**该断言恒假**（恒真/恒假的
> 负控制比不写更危险）。换成"拆光 `when_prev` ⇒ 具体支全失效"，靶子才落在被测分支上。

### 7.2 变异 `mutate186`（14 条，14 报红 / 0 漏网）

M01 删下门边 · M02 坐标 665→1 · M03 `when_prev` 改错 · M04 删默认支 ·
M05 拆 `_prev_ok` 的"不相等就拒" · M06 `dark_chase2` 目标改 chase1（±1 陷阱）·
M07 删运行时 B 门对象 · M08 B 门改自环 · M09 泉目标改城堡镇 · M10 删新场景登记 ·
M11 挪走 D 门坐标 · M12 删 `_scene_prev` 预声明 · M13 删 `prev=` 传参 · M14 删 `switch` 记账。

全恢复后回到 **rc=0 FAIL=0**（证明恢复干净）。

---

## §8 ★★★ 施工器 `apply186.py` 的两个自证

1. **空转往返自证**：不改内容 dump 一遍，必须与原文**逐字节相同**。
   这一步抓出了"三个 JSON 排版各不相同"：`_index`/`_routes` 是 indent=2 且**尾无换行**、
   标量数组 `_index` **内联**而 `_routes` **逐行**；`_zone.*` 是 indent=1 且**尾有换行**。
   ⇒ 用同一个 `json.dump` 一把梭会**静默改掉全部排版**（四个文件几十万行 diff）。
2. **先整段清空再重写**：按键去重删不掉"定稿时砍掉的那条"（键都不在了），
   而且会让 `priority` 出现**空洞** —— 空洞会让兜底顶到前面（§5.1 第 3 条）。
3. **绝对对账闸**：写盘后 `routes == 2843`，不等就直接 `SystemExit`。
4. **幂等**：连跑两次逐字节相同（`IDEMPOTENT-OK`）。

---

## §9 老锁加账清单（**23 个判据文件** + `run_all.py` 登记，**历史常数一字不动**）

| # | 套件 | 改动 | 为什么是加账不是放松 |
|---|---|---|---|
| ① | `check124` | `EXPECT_SCENES = 2166 + 1 + 1`；`EXPECT_UNIQUE_EDGES` 保持 2754 | **下限不跟涨** |
| ② | `check125` | `2166 + 1 + 1`；`EXPECT_UNREG_D = 9 → 8` | 33 登记后不再"端点未登记" ⇒ **账变少**，仍是 `==` 等值 |
| ③ | `check126` / `check168` / `check169` | `2166 + 1 + 1` | 场景数 |
| ④ | `check170` | `_MANUAL_ABOVE_BAND` 加 11 条；**探针候选集剔掉带 `when_prev` 的规则** | 探针不传 `prev`，而 `when_prev` 是 fail-closed ⇒ 不剔会算出产品永远给不出的答案 |
| ⑤ | `bg_round39` | 新场景补真背景（不是改判据） | 见 §6.2 |
| ⑥ | `routes_order44` | **B2c 改成段表 `_BANDS`** 驱动 + 新增 91xx 段 | 纪律不变：摘掉这一段必须**不再违例**才记账 |
| ⑦ | `scene_route_original` | 新增 `_KIND_186` 五族 + `_r186_bad()` + `C3a21`（逐族样本）+ `C3a22`（正/负控制，四种错法**各不相同**地报红） | 本轮引入 5 种新 `_original.kind` |
| ⑧ | `objects_round44` | `MAN_186 = 9 + 2` 与 `MAN_186_EXTRA = 3` **拆两个常量** | 拿 11 去补 C3 会多出 8 —— 那才是把判据调松 |
| ⑨ | `items_round48` | `light == 202 + 1` | — |
| ⑩ | `verify_scene_fit99` | `('obj_readable_room1', 921 + 2 + 6)` | 新场景 6 个 |
| ⑪ | `check176` | `EXPECT_185 = 2 + 11`；`EXPECT_SNAP_N = 3047 + 1 + 2` | `obj_lancerslideevent` **不**进这个账（不是 `obj_door*` 前缀） |
| ⑫ | `check173` / `check174` | `MAN_186 = 9 + 2` | 11 条里的 2 件 |
| ⑬ | `check175` / `check177` | `2166+1+1` / `2078+1+1` | 场景数三处 |
| ⑭ | `check181` | `_LEGACY_ALLOWED` 加 `'when_prev'` | 有产品实现作理由 |
| ⑮ | `check183` / `check184` | `_ADDED_186 = 11` | 路由数 |
| ⑯ | `check185` | `EXPECT_ROUTES_NOW = 2832 + 11`；**A13 从"max == 9002"改成"两条都 > GEN_MAX(8262)"** | 旧写法是**当日快照**，把"当日 max"换成"结构性区间" |
| ⑰ | `rooms_round47` | 见 §9.1 | 结构性后果 |
| ⑱ | `check77` / `check80` / `check99` / `第36轮` / `第44轮` | 各自加账（改动理由见各自文件内注释） | 场景数 / 路由数 / 物件数 |
| ⑲ | `run_all.py` | 新增 `check186` 条目（`offscreen: False`） | 入列 SUITES |

### 9.1 `rooms_round47`：rid 33 **通了**之后必然要动的 6 条

| 判据 | 原来 | 现在 | 性质 |
|---|---|---|---|
| A5 | 四章 `826 + 1` | `826 + 1 + 1` | +1 新场景 |
| A6 | 覆盖 812 / 未覆盖 41 | `812 + 1` / `41 - 1` | **总数 853 不动**，内部搬运 |
| A7 | 真缺口 == 10 间 | == `10 - 1` | **不删** `REAL_GAPS_4`（那是第47轮的取证结论），另立 `COVERED_186` 差分表 |
| A8 | `len(real)==10` | `len(real)==len(EXPECT_REAL)` | 负控制仍在 |
| B8 | `ch1: 40`，合计 836 | `40 + 1`，合计 837 | 新场景**带真背景** |
| C1 | `maybe 9 / nonscene 1` | `maybe 9 - 1 / nonscene 1` | 仍是**等值**断言，不是 `<=` |

★ 关键设计：`REAL_GAPS_4` **一个字都没改**，`COVERED_186 = {('ch1', 33)}` 单独成表。
这样"这一项是被**解决**掉的"可单独审计；若哪天 rid 33 又退回未覆盖，
`EXPECT_REAL` 里没有它 ⇒ A7 立刻报红。

---

## §10 全量 G2

```
合计：PASS=8137  FAIL=0  套件=183
比对：全部 IDENTICAL（无一行 DIFF 提示）
```

全程 **13 个套件**因本轮改动被碰到（其中 8 个一度报红：`scene_route_original` / `bg_round39` /
`routes_order44` / `objects_round44` / `rooms_round47` / `items_round48` / `check81` /
`verify_scene_fit99`），逐个修完并复跑转绿：
`scene_route_original` 66/0 · `bg_round39` 34/0 · `routes_order44` 26/0 ·
`objects_round44` 20/0 · `items_round48` 54/0 · `verify_scene_fit99` 108/0 ·
`check170` 26/0 · `check181` 41/0 · `check183` 26/0 · `check184` 34/0 ·
`check185` 41/0 · `rooms_round47` 23/0 · `check81` 52/0。

★ `check81 G5` 报"缺 `check186`"不是缺陷 —— 它是**专门设计来抓"入列 SUITES 却漏 `--update`"** 的闸。
先 `--only check186 --update` 固化基线，G5 自己就绿了（负控制 `G5n` 仍绿）。

### 10.1 未改过却 DIFF 的 12 个套件（逐条核过，都不是回归）

| 套件 | DIFF 内容 | 判定 |
|---|---|---|
| `pathfind_round45` / `check73` / `items_round68` / `check105` / `check_r0_76` / `check171` / `check172` | 2,167→2,168 / 2,832→2,843 / readable 923→929 | 数据量漂移 |
| `check_readable_wire117` / `check122` | kwargs / 形参列表里多了 `prev` | 新增形参在 AST 里露面 |
| `check182` | main.py 行号整体后移（7823→7835 等） | 行号漂移 |
| `soul_round55` | `暗之泉(obj_fountainkris)` → `门(obj_fountainkris)` | §6.3 **刻意**改判 |
| `check113k` | `Hometown · Town School` → `Hometown · School` | 新场景 sid 排在同类型房之前，去重键 `(章, 区, 类型)` 只留代表 ⇒ **条数仍 4**，能力未减 |

---

## §11 踩到的坑（写给下一轮）

1. **★★★ `priority` 升序 + `when_prev` fail-closed 的交互**：删掉一条中间规则后若按"键去重"
   保留老条目，`priority` 会出现空洞、兜底顶到前面 ⇒ 三条 `when_prev` **永远不生效且不报错**。
   修法是施工器"**先整段清空区间再重写**"，不是去重。
2. **★★★ `mutate186` 的两条铁律级坑**：
   - **CRLF 锚点**：产品源码是 CRLF，而变异锚点按 LF 写 ⇒ **多行锚点 `count()` 恒为 0**。
     单行锚点不受影响 ⇒ 前 11 个全绿、第 12 个才崩。修法：**只把锚点归一成文件自身 EOL**，
     绝不把整文件换成 LF。
   - **假幂等**：`backup_all(); restore_all()` 看着像自愈，实则**只自愈一次** ——
     崩过一次之后会把"被改坏的现状"当成"原样"备份。必须 **先恢复、后备份**，
     并在基准不绿时明确提示"备份本身已被污染，先删备份目录"。
3. **★★★ 恒真/恒假的负控制比不写更危险**：D5 在删掉一条边后变恒假，必须换靶。
4. **★★ 同门重复 == 0 是"过宽"判据**：全表本来就有 7 组合法的同门重复（ch5 的
   `obj_doorAnyHorz/Vert` 多实例去同一目标，第174轮裁定合法）⇒ 只能断言"**本轮 11 条各自唯一**"。
5. **★★ 谎报背景会被抓**：新场景填 `bg=None` 是省事，但那是假话；`bg_round39` 的两条判据
   就是干这个的。
6. **★★ 老锁改法＝引账不调数**：`REAL_GAPS_4` 一个字节都不改，另立 `COVERED_186`。
   历史取证结论是**事实**，不因为"今天情况变了"就该被改写。

---

## §12 遗留 / 下一轮候选

| 项 | 说明 |
|---|---|
| ch1/2/4/5 仍剩 **9 间真缺口** | `ch1:133,134` / `ch2:54,229,230,231` / `ch4:60` / `ch5:49,79`（第38轮 cls：maybe 8 / nonscene 1，至今没裁） |
| 31 间孤立房 | 原作门图里 in=0 且 out=0，**不是"没做"，是原作就没有路** |
| `flag[239]` 的"来路"语义 | 我们用 `when_prev` 等价表达；若将来要支持"跨多次换房记忆来路"，现有实现只记**上一层** |
| `obj_fountainkris` 改判的连带 | 它在别章有 `_ch2_sideb` 兄弟（仍是 fountain），两章行为**故意不同**，别再"统一"掉 |

---

## §13 证据索引

| 文件 | 内容 |
|---|---|
| `_tools/apply186.py` | 数据侧施工器（含空转自证 / 幂等 / 绝对对账闸） |
| `_tools/check186.py` | 33 条判据 |
| `_tools/mutate186.py` | 14 条变异 |
| `_tools/probe186.py` / `probe186b.py` | 实例表探针（找 `obj_doorB` 的运行时创建、`obj_lancerslideevent` 的 rid） |
| `_tools/dump_*.csx` | UTMT 导出脚本（`exit186` / `inst186` / `trans186` / `allrooms186`） |
| `_evidence/codes/*.gml` | 9 段原作 GML 逐字留档（`obj_doorX_Alarm_2` / `obj_doorX_musfade_Alarm_2` / `obj_lancerslideevent_Step_0` / `obj_fountainkris_Step_0` / `obj_classscene_Step_0` 等） |
| `_evidence/exit_codes186.json` | 含 `obj_classscene_Create_0`（`(242,48)` 那一支）与 `obj_darkfountain_event` 的 `t>=650` 原文 |
| `_evidence/trans_codes186.json` | 含 `obj_doorB_Alarm_2`（`room_goto_previous()`）原文 |
| `_evidence/rooms_inst186.json` / `all_rooms186.json` | 实例表全量（找 rid 33 的 9 个物件、确认 `obj_doorB` 不在静态实例里） |
| `ralsei_pet/assets/scenes/bg/ch1_hometown_school_unusedroom.png` | 新场景真背景（7,025 字节） |
