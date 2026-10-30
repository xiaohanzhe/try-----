# 第123轮报告：ut 剩下的 751 个门实例（覆盖率 42.2% → 94.9%）

> 一句话：第122轮把「751 个实例没路由」记成**证据无出处**，这个归因是错的 ——
> 证据一直在，是**扫描器不认**：ut 的门把目标写成 `room_goto(room_previous(room))`，
> 目标是**函数调用**，而 `conn_ut.csx` 只收常量目标。
> 本轮反编译 133 条 door 事件代码 + 34 个 door 对象元数据（含 `ParentId`），按 GML 位移机制补齐 282 条。

## 1. 归因更正（本轮最重要的一条）

| 说法 | 事实 |
|---|---|
| 「`obj_doorB` 疑为 `room_goto_previous`，待验 `off=-1`」 | **已验证**：`obj_doorB_Alarm_2` 逐字就是 `room_goto(room_previous(room));` |
| 「证据无出处」 | 证据在**事件代码**里；`conn115` 的边表只投影了常量目标 ⇒ `n_nonconst_target: 30` |
| 「`obj_doorAmusicfade` 大概和 `obj_doorA` 一样」 | **对**，但机制是**父链继承**（自己没有 `Alarm_2`，`PreCreate` 只有 `event_inherited();`） |

## 2. 机制表（UTMT 反编译原文）

| 对象 | `Alarm_2` 正文 | 位移 | 实例数 |
|---|---|---|---|
| `obj_doorA` | `if (room != room_castle_prebarrier) room_goto(room_next(room)); else if (global.flag[7]==1) room_goto(room_castle_trueexit); else room_goto_next();` | **+1**（`castle_prebarrier` 排除） | 2 条新 |
| `obj_doorB` | `room_goto(room_previous(room));` | **−1** | 132 |
| `obj_doorC` | `room_goto(room_next(room_next(room)));` | **+2** | 24 |
| `obj_doorD` | `room_goto(room_previous(room_previous(room)));` | **−2** | 25 |
| `obj_doorAmusicfade` | 继承 A | +1 | 44 |
| `obj_doorBmusicfade` | 继承 B | −1 | 46 |
| `obj_doorCmusicfade` | 继承 C | +2 | 3 |
| `obj_doorDmusicfade` | 继承 D | −2 | 5 |
| `obj_papdoor` | `room_goto(room_next(room));` | **+1** | 1 |
| `obj_elevatordoor` | `event_user(0)` 开电梯 UI | **不是门位移** | 13（仍不写） |

⇒ 与 Deltarune 的「A+1 / B−1 / C+2」**同一套约定**，D 是 −2。

## 3. 产物

| 文件 | 前 | 后 |
|---|---|---|
| `ralsei_pet/assets/scenes/_routes.json` | 1,110 条（ut 243） | **1,392 条（ut 525）** |
| `ralsei_pet/assets/scenes/_zone.ut.rooms.json` | 970 条 / 227 场景 | **1,655 条 / 274 场景**（door 1,233 + 物 422） |
| 门覆盖 | 548 / 1,299（42.2%） | **1,233 / 1,299（94.9%）** |

ut 段构成：`ut_door_src` 110 ｜ `ut_door_next` 133 ｜ **`ut_door_shift` 282**（字母级 183 + 对象级 99）。
`priority` 独立段 **4000~4524 连续无洞**。

## 4. 三条纪律（都吃过亏）

1. **必须查 `ParentId`** —— 不沿父链解析会把 musicfade 变体的 **214 个实例**判成"无机制"。
2. **`Alarm_2` 里 `if (...)` 条件点名的房间不套通用位移** —— `obj_doorA` 在 `castle_prebarrier`
   走 `global.flag[7]` 分叉，第122轮已有 2 条专门规则，本轮机制不去覆盖。
3. **同场景同字母只留一条**，冲突**整键丢弃并记账**，不猜。

## 5. 判据（`check123` 23/0）

- A 规模/形状：525 条分账 · priority 连续 · 两端已登记 · 无自环 · **同场景同字母唯一** ·
  `shift` 只含 {−2,−1,1,2} 与 9 个已实证对象 · src/字母合法。
- ★★ B **独立重算**：用**另一套实现**（手工括号配对 `_calls` / `_cond_rooms`，不用生成器的正则）
  从事件源码重推 282 条，**逐条相等**；配改目标负控制 + 原样正控制 + 非空分母闸 +
  **B5 继承链生效自证**（2 个对象真从父链解析到）+ **B6 条件房间被识别**（`obj_doorA` → `castle_prebarrier`）。
- C 与 `objects` 双向相等（1,233 组 / 1,655 条 / 274 场景）；未覆盖 66 个**全部**来自无机制门。
- D 产品行为：`obj_doorB` → `room_area1`；撤掉 `when_src` ⇒ 0 扇。
- E 防回滚 · F 自检（AST 数恒真 / 无 BOM）。

## 6. 老锁按新事实改口径（一律加严/分账，没有放宽）

| 套件 | 改法 | 性质 |
|---|---|---|
| `check_objs121` | `_routed_doors()` 旧写 `when_src or 'obj_doorA'` ⇒ 122 只有字母 A 时侥幸成立；123 补 B/C/D 后变成**纯误报**（"点不动的门 442 / 幽灵规则 66"）。改**语义重推**（字母级去实例表找该房间同字母的门对象）⇒ 525=525，dead/ghost 双 0 | **修误报** |
| `check105` | `D2e` ut 段 243 → 525 | 分母跟上事实 |
| `verify_scene_fit99` | `G24c` `sprite is None` 970 → 1655 | 同上 |
| `objects_round44` | `A2c` ut 分片 227/970 → 274/1655 | 同上 |
| `items_round48` / `items_round68` | `E3b` / `C3b` 分账 `(422,548)` → `(422,1233)` | 同上 |
| `routes_order44` | `B6` 对象级 110 → 209；`C1b` 243 → 525，**去重键升级为 (场景,目标,依据)** | **修误报** |
| `scene_route_original` | `C3` 加第四种机制 `ut_door_shift`；`C3a4` 243 → 525；新增 `C3a6` 三条负控制 | **加严** |

★ `C1b` 为什么必须换键：`room_water12` 有**两扇不同的门**指向同一间 `room_water11`
（`obj_doorDmusicfade` 的 D−2 + 第122轮那条 `obj_door_ruins13` 对象级规则）⇒ 旧的
`(场景,目标)` 键会把 525 判成 524 报红，而那是**合法并存**，不是重复条目。

## 7. 回归

全量 G2：**122 套件 / PASS 6000 / FAIL 0 / 全 IDENTICAL**。
（本轮新增 1 套 `check123`；改口径 8 套已 `--update` 重建基线。）

## 8. 没做的 66 个实例（逐类有出处）

`obj_elevatordoor`(13) 是电梯 UI ｜ `obj_door_s_musfade`(13) / `obj_doorXmusicfade`(10) /
`obj_door_ruins13`(5) / `obj_door_t`(2) 的剩余房间在可信边里查不到目标 ｜
`obj_labdoor`(3) / `obj_fakedoor`(2) 等**非位移门**。

## 9. 本轮踩的坑（都写进了复检）

1. `probe_doors123` 第一版用"房间名后固定 400 字窗口"取条件分支目标 ⇒ 把相邻分支全算进来
   （一个房间冒出 5 个目标）。改成只解析 `if (...)` 的**条件文本**，`room ==` 与 `room !=` 都收。
2. `gen_routes123` 覆盖账混账：`no_mechanism` 里 157 个实例其实是 122 的对象级已覆盖 ⇒
   循环开头先认账，账目变成 239 + 994 + 66 = 1,299。
3. `check123` 的 `%d` 放在 `check(desc, cond, detail)` 第一位（只有 detail 参与 `%`）⇒ 未替换。
4. `check123.D1/D2` 调 `build_props()` 少传 `chapter`/`world`（签名是
   `build_props(scene, chapter, world, present, ...)`）。
5. **E 盘坏盘新形态**：`UndertaleModCli.exe` 启动即 `OSError: WinError 193 不是有效的 Win32 应用程序`，
   而**同一份 exe**（sha256 逐字节相同、PE machine=0x8664、dll 齐全）从 D 盘备份起就正常
   ⇒ `CreateProcess` 读坏页。**换盘不换文件**即解决。
6. `check95 A2` 体积闸再次被顶破（10076 > 10000）：上一轮收尾写的记忆没复跑 G2。
   ⇒ 本轮按门槛处理：**先补详版 §123 → 再压速查本**（10,076 → 9,888），删掉的令牌逐个回详版 `in` 过一遍。
