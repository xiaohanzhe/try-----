# 第172轮 · `obj_doorAny` 每实例目标（探针 → 落边 → 接线，**已落地**）

> 前半段是只读探针（回答"能不能静态解出"），后半段是落地（落 798 条边 + 改一处分流）。
> 落地结果：`_routes.json` **1,961 → 2,759**，G2 **170/170 IDENTICAL、7,678 PASS / 0 FAIL**。
> ★ 第 11 节如实写了一条**仍未解决**的产品侧缺口（Any 门还没在场景数据里物化）。

---

## 1. 一句话结论

**能。** 881 扇 Any 门里 **853 扇**的目标在 `data.win` 里是**字面量房名**，去重后 **812 条边、其中 798 条是产品现在没有的**；而产品现有路由只覆盖 1067 个源场景，**有 404 个场景（18.7%）现在一条出边都没有**，它们唯一的出口就是这些 Any 门。

**已落地**：798 条边进表（1,961 → **2,759**），`route_for_door` 的对象级分流 + `_pick_by_pos` 第二拍上线，
新 `check172` 33 条锁住，全量 G2 **170/170 IDENTICAL、7,678 PASS / 0 FAIL**。

**⚠️ 但**：这 798 条边**目前没有消费方** —— 我们的场景数据里 `obj_doorAny` 实例数是 **0**
（详见 §11）。所以本轮交付的是"**原作路网的完整记录 + 已备好的分流逻辑**"，
不是"玩家今天就能走通这 404 个房间"。物化 objects 属新范围，未做。

---

## 2. 三个走错又纠正的地方（本轮一半价值）

| # | 一开始的判断 | 事实 | 怎么发现的 |
|---|---|---|---|
| 1 | `instance.CreationCode` 是实例级创建代码 ⇒ 全是 `null`，以为"没有每实例数据" | 真正的字段是 **`PreCreateCode`**，`CreationCode` 恒为 null | 把一扇门的**全部属性名+值**打出来（`probe5`）才看见 |
| 2 | `Data.Macros` 空 ⇒ 以为 `ROOM_INITIALIZE` 是编译期宏 | 它是**房间资源名**（在 `scr_get_room_by_id` 的房表里，id 20011，紧邻 `room_gms_debug_failsafe`） | 扫 779 个 `GlobalInitScripts` 找它的定义处 |
| 3 | 场景索引只有 `name_raw` ⇒ 用名字对房 | 一批场景 `name_raw` 是 `null`（如 `queen_s_mansion_entrance`）⇒ 名对名会漏 | 改用 **`Data.Rooms` 下标 ↔ 产品 `original_room_id`** |

★ 第 3 条是这轮数字从"673 条边 / 167 条落空"跳到"812 条边 / 23 条落空"的唯一原因：**口径换对了，落空数掉了一个数量级**。

---

## 3. 原作怎么写的（决定性证据）

`obj_doorAny` 的代码只有 5 条（ch2）：

```gml
// PreCreate_0
event_inherited();          // 父对象为 None ⇒ 空操作
doorSpecial = "none";

// Create_0
touched = 0; init = 0; image_speed = 0;

// Step_0（只用 image_index 1~6 这一条 debug 分支）
if (init == 0) {
    switch (image_index) {
        case 1: doorRoom = room + ROOM_INITIALIZE; break;
        case 2: doorRoom = room - ROOM_INITIALIZE; break;
        ... 3~6 分别是 room_title_placeholder / room_battletest 的 ±
        default: break;
    }
    if (image_index != 0) doorEntrance = image_index;
    init = 1;
}

// Alarm_2（被 Other_19 里 alarm[2]=8 触发）
global.entrance = 1; event_user(7); instance_create(0,0,obj_persistentfadein);
room_goto(doorRoom);

// Other_19
global.interact = 3; instance_create(0,0,obj_fadeout);
if (touched == 0) { alarm[2] = 8; event_user(8); touched = 1; }
```

**目标在每实例的 `PreCreateCode` 里**，形如：

```gml
// gml_RoomCC_room_lw_police_0_PreCreate
doorRoom = room_town_south;
```

对照 `obj_doorW`：它的 892 行 `Alarm_2` 是 `room_goto(room_xxx)` **直接写死**，根本不用 `doorRoom`。⇒ 两个族**机制不同**：W 是"房间表 + 位置条件"，Any 是"每实例一个目标"。

---

## 4. 取证与 A/B 锚点

| 锚点 | 结果 |
|---|---|
| **ch2 两路取数**：实例属性读 vs 全量扫 `gml_RoomCC_*` | **23 = 23，双向零差** |
| **状态一致性**：脚本内解压 vs 第171轮 CLI `-c` 导出 `obj_doorAny_Alarm_2` | 4 行**逐字相同** |
| **房间映射**：`Data.Rooms` 下标 vs 产品 `original_room_id` | ch2 **26 一致 / 0 冲突**（唯一"无此 id"是 debug 房 `room_cutscene_tester`） |
| **名字副证**：`name_raw` vs 房间资源名 | **0 冲突** |
| **语义自证**：4 条"已存在边"里 `lw_police → town_south` 正是 `doorRoom = room_town_south` | 与产品既有边一致 |

`gml_RoomCC_*` 全库 ch2 共 1064 条，**解压失败 0 条**（对比：全量 6707 条代码里有 869 条解压失败，但那批不在门这条线上）。

---

## 5. 五类裁决（881 扇）

| 类别 | 扇数 | 含义 |
|---|---|---|
| `static_dst_ok` | **853** | `doorRoom = room_xxx` 字面量，目标房**是**已登记场景 ⇒ 可入边 |
| `static_dst_unmapped` | 23 | 字面量有，目标房没登记成场景（属"场景抽取"另一条线） |
| `relative_debug` | 4 | 无字面量、`image_index` 1~2 ⇒ 走 `room ± debug房`，**debug 相对跳，不落边** |
| `unknown_no_code` | 1 | 无字面量、无 `PreCreateCode`、`image_index=0` |
| `unknown_code_only` | 0 | 有代码但里面没 `doorRoom` |

另有 **10 扇的源房本身没登记成场景** ⇒ 即使目标明确也不能入边。

逐章：

| 章 | 扇数 | 可入边 | 目标未登记 | debug 相对 | 无代码 |
|---|---|---|---|---|---|
| ch1 | **0** | 0 | 0 | 0 | 0 |
| ch2 | 27 | 23 | 0 | 4 | 0 |
| ch3 | 190 | 185 | 4 | 0 | 1 |
| ch4 | 366 | 350 | 16 | 0 | 0 |
| ch5 | 298 | 295 | 3 | 0 | 0 |

★ **ch1 一扇 Any 门都没有**（`obj_doorAny` 在 ch1 的 `data.win` 里不存在）——所以第一章不是靠这个机制走路的。

---

## 6. 对产品意味着什么

- 候选边（源已登记、按 `(场景,目标)` 去重）：**812** 条
- 其中**已在表里**：14 条；**新边**：**798** 条（ch2 9 / ch3 178 / ch4 335 / ch5 276）
- 现有路由：1,961 条，覆盖 **1067** 个源场景（总场景 2166）
- **404 个场景现在没有任何出边**，Any 门是它们唯一的出口

换句话说：这不是"补几条边"，而是**把桌面世界的路网从 1067 个出口点扩到 ~1400 个**。

---

## 7. 未解 / 不猜的部分

1. **4 扇 debug 相对门**（`room_dw_cyber_intro_1`、`..._connector`、`room_dw_city_postbaseball_3` ×2）：目标写成 `room ± ROOM_INITIALIZE`，而 `ROOM_INITIALIZE` 是 debug 房 ⇒ **按"不知道"处理，不落边**。
2. **1 扇无代码门**（ch3）：只有实例没有 `PreCreateCode`。
3. **23 扇目标房未登记成场景**、**10 扇源房未登记**：属场景抽取线，本轮不碰。
4. **`image_index=0` 时 `doorRoom` 会不会被别处覆盖**：全量扫过 `doorRoom` 的 26 处引用，除 `obj_doorAny_Step_0` 外只有 `obj_doorparent_PreCreate_0`（`doorRoom = room_next(room)`，另一个族）和各 Any 门自己的 `PreCreateCode` ⇒ **不会互相覆盖**。

---

## 8. 落地（**已完成**，原"等裁定"已获批）

| 项 | 做法 | 结果 |
|---|---|---|
| 数据 | `apply172.py` 无损往返自检 → 写 `.new` → 复读断言 → `os.replace` | **+798 条**，priority 7300~8097、`batch=172`；表 1,961 → **2,759** |
| 防重复 | 与既有 `(场景, 目标)` 完全相同的 14 条**有意不落**；批内重复 34 条只留一条 | 重复组仍是 **5**（一组合法重复都没新增） |
| 产品（一处） | `route_for_door` 的**对象级**分支先 `_pick_by_pos(pred=when_src)`，再退回老口径 | 843 个 `(场景, when_src)` 组里候选 ≥2 的 **只有 242 个、全是 `obj_doorAny`** ⇒ 既有 1,961 条**零影响** |
| 产品（补充） | `_pick_by_pos` 加**第二拍**：单轴挑不出唯一 ⇒ `(door_x, door_y)` 两个坐标一起对 | 只多认 **6 条 / 3 个房**（含 `dw_fcastle_foyer` 的 2×2 网格）；另修正 1 条第170轮遗留（同 x、只有一扇记 y） |
| 判据 | 新 `check172` **33 条 / 六段**；`mutate172` **11/11** 符合预期 | 全量 G2：170/170 IDENTICAL、**7,678 PASS / 0 FAIL** |

**落地时纠正的两个"想当然"**

1. **`axis` 口径不能按"边数"算，必须按"门实例扇数"算。** 同房同 x 的两扇若目标相同，只会留下 1 条边 ⇒ 用边数去推 `axis` 会把 4 条正确规则判成"多写了 axis"（`check172.B4` 首跑假红 4 条）。
2. **`_pick_by_pos` 的"单轴"在网格房里根本不够。** `dw_fcastle_foyer` 四扇门是 `x ∈ {-34, 954} × y ∈ {960, 1240}`，x 有两组、y 也有两组 ⇒ 任何单轴都命中 2 条 ⇒ 退回 priority 最小 ⇒ **四扇里三扇走错房间**。这是第170轮"命中 ≥2 一律退回"那条契约留下的真空，第二拍就是补它。

**"零影响"是算出来的，不是感觉出来的**

- 非 Any 的对象级分组 **418 个，没有一个候选 ≥2** ⇒ 对象级消歧对老规则**永不触发**（`check172.C5`）。
- 字母级规则传/不传坐标会改变的 **36 条，全部是有 `door_x` 的**（没有坐标的规则不可能被 `pos` 影响，`check172.C6`）。
- 第二拍对对象级的改变量：**6 条，全部 `batch=172`**；对字母级：**1 条，`batch=170`**（就是上面那条"同 x、只有一扇记 y"的遗留）。逐 batch 扫过，别的批次 **0 条**。

---

## 9. 产品侧认门**不需要**新增门类别（原判断作废）

原稿写"`door_letter_of('obj_doorAny')` 返回 `None` ⇒ Any 门在产品里根本不是门，需要新增门类别"。
**这条是错的**：`classify()` 里 `'door' in low` 已经把 `obj_doorAny` 归成 `kind='door'`；
建门分支的条件是 `elif tgt:`（有目标就建，**不要求字母**），第122轮给 ut 无字母门就是这么接的。
所以只要路由表里有目标，`build_props` 就会把 Any 门建成 `DoorProp(door_letter=None)` —— **一行分类器都不用改**。

---

## 10. 证据清单（`_evidence/`）

| 文件 | 内容 |
|---|---|
| `probe_any172.ch{1..5}.json` | 每扇 Any 门的房间/坐标/`image_index`/`PreCreateCode` 名与 GML/`doorRoom` 目标；含房间名表 |
| `probe2_172.ch2.json` | `Data` 属性清单（证明没有 `Macros`）、父链（`obj_doorAny` 无父）、祖先代码清单 |
| `probe3_172.ch2.json` | 779 个全局脚本筛选结果（`ROOM_INITIALIZE` 是房名不是宏）+ `obj_doorW` 对照代码 |
| `probe4_172.ch2.json` | 全量 6707 条代码里 26 处 `doorRoom` 引用 |
| `probe5_172.ch2.json` | Any 实例全部属性（发现 `PreCreateCode`）+ 1064 条 `gml_RoomCC_*` 清点 |
| `analyze172.json` | 881 扇逐门分类 + 812 条候选边 + 404 个"只有 Any 门能出"的场景 |

工具：`probe_any172.csx` / `probe2~5_172.csx` / `run_any172.py` / `analyze172.py`（探针与裁决）、
`apply172.py`（落盘，无损往返自检）、`check172.py`（33 条回归锁）、`mutate172.py`（11 条变异）。
判据已注册进 G2（`regress/run_all.py` 的 `check172`）。

---

## 11. ★★★ 仍未解决：Any 门在**场景数据**里一次都没被物化

落完 798 条边之后核的一件事（**必须写在最显眼处，不许含糊**）：

| 检查 | 实测 |
|---|---|
| 425 个有 Any 边的场景，是否都登记成了场景？ | **425 / 425 都在** |
| 它们能不能 `load_scene()` 出来？ | **425 / 425 都能** |
| 里面有没有一个 `src == 'obj_doorAny'` 的 object？ | **0 个**（425 个场景的 `objects` 合计只有 **386** 个，全是存档点/可读物/门A~F/W/X/marker 等） |
| 全库 76 个 `_zone.*.json` 分片 + 88 个独立场景文件呢？ | 2,078 个场景、**12,263** 个 object 里 `obj_doorAny` **0 个** |

⇒ **表里有路，但场上没有那扇门。** `build_props` 是遍历 `scene['objects']` 建门的，
没有实例就不会调 `route_for_door`，所以这 798 条边**目前一条都没被消费**。
它们是"记录下来的原作拓扑"，不是"玩家今天就能走的路"。

**这不是本轮引入的缺陷，是本来就存在的断层**（第42~171轮的对象抽取只覆盖了
门 A~F/W/X/marker/存档点/可读物这批 `src`，Any 族从来不在白名单里）。
`obj_doorAny` 也**不在** `_obj_visible.json` 的"该画"名单里（它在 `hidden` 里，
而 `hidden` 只影响绘制、不影响交互）——所以缺的是**抽取白名单**，不是可见性。

**要真正走通，还缺一步（属新范围，需单独裁定）：**

1. 把 `inst171.ch{1..5}.json`（上一轮已采到的逐房间实例快照，含每扇 Any 门的 `x/y`）
   合并成"场景 objects 补丁"，给那 425 个场景各补上它该有的 Any 门实例
   （`pos` 直接取实例坐标；`src='obj_doorAny'`；不需要 sprite —— 它在 `hidden` 名单里，不画）。
2. 补完之后 `route_for_door(..., src='obj_doorAny', pos=[x,y])` 才会真的被调用，
   本轮那两处产品改动（对象级消歧 + 第二拍）才**从"备好"变成"在用"**。
3. 验收要新增判据：**425 个场景里 Any 门实例数 == 证据扇数**，且"按 E 真能换房间"
   的端到端用例（这条只能真机验，不能只静态断言）。

★ 一句话：**路网已经画在图上，但还没铺到地上。** 本轮把"图"补全并证明了它是对的，
"铺地"（物化 objects）没做，也不该在本轮偷偷做 —— 那会把一次"补数据"变成"改场景生成管线"。

---

## 12. 教训

1. **★★★ "没有数据" 先怀疑字段名。** `CreationCode` 是 null、`PreCreateCode` 才有货——一个字段名之差，差点得出"Any 门是 debug 垃圾"的反向结论。
2. **★★★ 名义对账不如主键对账。** 场景名对不上时先别断言"未登记"，换成两边都有的**房间下标**，落空数直接掉一个数量级。
3. **★★ A/B 要成对**：ch2 两路（属性 vs 全扫）必须逐条相等才敢用另外四章。
4. **★ 全量扫描要报分母**：6707 条扫出 26 处命中、869 条解压失败——**失败数必须写在结论旁边**，否则"26 处"是假精确。
5. **★★★ 单轴消歧在"网格房"上根本不成立。** `dw_fcastle_foyer` 四扇门 `x ∈ {-34,954} × y ∈ {960,1240}`，
   任何单轴都命中 2 条 ⇒ 一律退回 priority 最小 ⇒ 四扇里三扇走错。**"命中 ≥2 一律退回"是个安全默认，但不是一个完备方案**；
   补法不是放宽它，而是加**第二拍**（两个坐标一起对），且只在第一拍失败时启用。
6. **★★★ 统计口径要按"被测对象"数，不是按"表里剩几条"数。** `axis` 该不该写，取决于**那间房同 x 有几扇门**，
   不取决于**表里留了几条边**（同房同 x 且目标相同的两扇，只会留 1 条边）——按边数算会假红 4 条。
7. **★★ 判据／扫描器会"扫到自己"。** F4 第一版把 `E:\` 这类令牌**字面量**写进源码再全文找，那行自己就命中；
   注释里写了一遍同理。⇒ 导入用 **AST** 查，盘符/协议用**拼接**构造。这和"扫描器恒空"是同一个病的两面。
8. **★★ 先看证据的**数据结构**再写断言。** `analyze172.json` 的 `new_pairs` 是 `"a -> b"` **字符串**，
   第一版直接拿去和元组集合比 ⇒ 报了 798 条假红。一条 `split` 就解决，但如果不看就变成"数据错了"。
