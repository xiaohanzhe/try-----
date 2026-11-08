# 第174轮 · `obj_doorAnyHorz` / `obj_doorAnyVert` 物化 + 落边

> 一句话：**doorany 家族剩下那两个变体补上了（51 条边 + 51 个物件）**，
> 顺带挖出第172轮一个「数据里说假话」的缺陷并留档。
> 判据 39 条全绿、变异 8/8 全抓、三把老锁连带改对。

---

## 1. 先纠正上一轮的一个判断错误

我在第173轮收尾时说过「`obj_doorAnyHorz/Vert` 没有任何既有取证，需要先跑 UTMT」。
**这句话是错的。**

第172轮探针 `probe_any172.csx` 的对象过滤是**子串**：

```csharp
if (on.ToLowerInvariant().IndexOf("doorany") < 0) continue;
```

`obj_doorAnyHorz` / `obj_doorAnyVert` / `obj_doorAnyModespecific` 的名字里**都含**
`doorany` ⇒ 四个变体的实例**全部**被录进了 `probe_any172.ch5.json`，每条都带自己的
`creation_gml`（= `gml_RoomCC_<房>_<n>_PreCreate` 的反编译结果）。

`analyze172.json` 里 `via` 全为 `None`、`src_room_name` 全 `False`，**不是探针没采到**，
而是分析脚本 `analyze172.py` 没把 `obj` 字段带进 `rows`：

```
rows 881 = obj_doorAny 830 + obj_doorAnyHorz 42 + obj_doorAnyVert 9   ← 一条不少
```

**结论：本轮不需要重跑 UTMT。** 唯一新增的产物是 `analyze174.py` 把 51 条捡出来。

---

## 2. A/B 双盲（两条独立读取路径互证）

| 变体 | A：csx 探针（UTMT 对象模型） | B：第42轮 CLI 普查 | 差异 |
|---|---|---|---|
| `obj_doorAnyHorz` | 42 | 42 | `IDENTICAL` |
| `obj_doorAnyVert` | 9 | 9 | `IDENTICAL` |

比的是**逐实例的 `{(room_index, x, y)}` 集合**，不是条数 —— 条数对上但坐标错位在这里
是抓不到的，集合相等才说明两条链读到的是同一批实例。

`analyze174.py` 跑完打印 `→ 不一致的变体数 = 0`，`check174 A1` 再独立重算一遍。

---

## 3. 分类结果：51 扇全部可落边

```
ch1  inst=0    ch2  inst=0    ch3  inst=0    ch4  inst=0
ch5  inst=51   ok=51   unmapped=0  debug_rel=0  unk(code)=0  unk(nocode)=0  src_unmapped=0
```

- **51/51** 都在自己的**实例创建代码**里写死了 `doorRoom = room_xxx`；
- **51/51** 的目标房都登记成了场景；
- **51/51** 的源房都登记成了场景（不需要"硬塞到别的载体"）；
- 去重后落在 **29 个「章:房间」键**上。

---

## 4. ★★★ 挖出第172轮的数据缺陷：42 条边的 `via` 说假话

`analyze172.py` 只按"这条实例的 `kind` 是不是 `static_dst_ok`"筛边，**没有按 `obj` 过滤**
⇒ 变体实例也被当成 `obj_doorAny` 处理，`via` / `when_src` 硬写成 `obj_doorAny`。

用 `precreate` 名字反查探针里的**真实实例**（代码名是机械生成的
`gml_RoomCC_<房>_<实例号>_PreCreate`，编不出来）即可证伪：

```
batch=172 的边 798 条
  via 真身 = obj_doorAny      756
  via 真身 = obj_doorAnyHorz   36   ← 标错了
  via 真身 = obj_doorAnyVert    6   ← 标错了
  查不到                       0
```

**后果**：那 42 条边的目标是查得到的，但**没有任何 `obj_doorAny` 物件在那些房间**
（例：`room_dw_garden_aquahole` 里一个 `obj_doorAny` 都没有，只有 3 个 `obj_doorAnyHorz`）
⇒ 它们是**死边**：路网画在表上，地上没有门。

**本轮怎么处理**：**只留档，不修。**

理由不是"怕麻烦"，是**改标签会动两套别人的账**：

- `check172` 的 `EXPECT_N=798`、以及它对 `via` / `label` 的一致性断言；
- `第36轮 verify_scene_route_original.py` 的 `_ANY_VIA = 'obj_doorAny'`、
  `_ANY_TABLE`、以及 `C3a13 _n_any >= 798`。

在**同一轮**里既改数据又改两套历史判据，等于把"发现缺陷"和"重写历史"混在一起，
将来没人分得清哪条红是真回归。所以：

- `check174 B6`：钉住第172轮那 798 条 **一条都不许动**（含"不许被改标签"）；
- `check174 B7`：钉住"42 条误标"这个事实仍然成立（`precreate` 反查）；
- 报告即凭据；修正留待**单独一轮**裁定。

---

## 5. 落库

### 5.1 路由：51 条边（`priority` 8100~8150，`batch=174`）

`_routes.json` **2,759 → 2,810**。

**★ 为什么"一条实例一条边"而不是"一对一条"**：去重后只有 **42 对**，按对落边会吞掉
**9 扇**。同房多扇、目标两两不同的场景里，`_pick_by_pos` 靠 `door_x/door_y` **逐扇**
对坐标；第二扇的坐标在表里没有对应条目 ⇒ 挑不出唯一 ⇒ 退回 `priority` 最小
⇒ **静默走错房间**。

字段口径（与第172轮同构，但 `table` 如实写）：

```json
{
  "when_scene": "<场景>", "when_door": null,
  "when_src": "obj_doorAnyHorz",
  "to": "<目标场景>", "priority": 8100,
  "_original": {
    "chapter": "ch5", "kind": "delta_door_any_variant",
    "table": "gml_Object_obj_doorAny_Alarm_2",
    "own_event": "Step_1",
    "via": "obj_doorAnyHorz",
    "precreate": "gml_RoomCC_<房>_<n>_PreCreate",
    "src_room_name": "...", "dst_room_name": "...",
    "src_room_id": 141, "dst_room_id": 142,
    "door_x": -34, "door_y": 1480, "door_x_all": [...], "batch": 174
  }
}
```

**`table` 为什么写父对象**：`obj_doorAnyHorz/Vert` **自身没有 `Alarm_2`**。
它们真正的换房链路是：

```
继承来的 Other_19（碰到玩家）→ alarm[2] = 8
        ↓
父对象 gml_Object_obj_doorAny_Alarm_2 → room_goto(doorRoom)
```

另外它们各有一个自己的 `Step_1`：玩家在平台上（`i_ex(obj_plat_player)`）时把
`x`（Horz）/ `y`（Vert）相对 `xstart`/`ystart` 挪 **±40**，按房间的左右/上下半区决定方向。

> **对我们的产品意味着什么**：产品里没有 `obj_plat_player`（grep 全仓 0 命中）
> ⇒ `plat_adjusted` 恒为 false ⇒ 位置恒为 `xstart/ystart` 原值
> ⇒ **本轮记的静态坐标就是产品该用的坐标**，不需要模拟那 ±40。
> 速度交接（`global.plat_hspeed/vspeed`）在产品里没有对应物，如实不做。

### 5.2 物件：51 个（`{pos, src}`，**无 sprite**）

| 载体 | 条数 |
|---|---|
| `_zone.ch5.cliffs.json` | 18 |
| `_zone.ch5.flower_castle.json` | 17 |
| `_zone.ch5.garden.json` | 13 |
| `ch5.garden.garden_shrine.json`（独立文件） | 3 |

- 分片 **3 个文件 / 28 个场景** + 独立文件 **1 个 / 1 个场景**，两路都写到了；
- **故意不写 `sprite`**：两个变体都是 `visible=false` 的触发器（`_obj_visible.json` 的
  hidden 名单里有），`is_drawable_object()` 会滤掉 ⇒ 永不绘制。`objs/` 里也**没有**
  `spr_doorAny_0.png` —— 这正是生成器当初把这批实例静默跳过的原因。
- **9 扇没有路由的也物化了**：原作里它们确实存在；`build_props` 查不到目标就**不建门**，
  所以多这 9 个物件零行为变化，但数据不说谎。

### 5.3 端到端（真跑 `build_props`，不是查源码猜）

```
变体物件 51 → 建出 DoorProp 51 → 全部解析出目标 0 条失败
42 个「场景→目标」对不同目标；11 个场景同房多扇分流到不同目标
```

`ch5.garden.garden_shrine`（原作房间 `room_dw_garden_aquahole`）本轮之前
**只有 1 个存档点、没有任何门**；现在：

```
SavePointProp  obj_savepoint      -> None
DoorProp       obj_doorAnyHorz    -> ch5.garden.dw_garden_aquashrine
DoorProp       obj_doorAnyHorz    -> ch5.garden.dw_garden_aquahole_left
DoorProp       obj_doorAnyHorz    -> ch5.garden.dw_garden_aquahole_left
```

### 5.4 ★ 可达图没变（这条必须说清）

42 个 `(源场景, 目标场景)` 对，在**不含本轮 51 条边**的旧表里**就已经全部存在**
（第172轮落的那批）。

⇒ 本轮**没有新增任何一条通路**，效果是**把原本无人消费的死边变成了真能走过去的门**。
`check174 C7` 独立重算这句话，防止"补了 51 条边"被误读成"新增 51 条路"。

---

## 6. 为什么不补 `obj_doorAnyModespecific`

| 事实 | 值 |
|---|---|
| 对象表里登记 | **有**（`objmap43` ch5） |
| 五章实例数 | **0** |
| `sprite` | `spr_doorAny`、`visible=False` |
| `classify()` | `kind='door'`、`letter=None` |
| 自己的代码 | 有（`Create_0` / `Alarm_2` / `Step_0` / `Other_19` / `PreCreate_0`） |

**有代码、有登记、零实例** ⇒ 补不了（没有坐标可补）。本轮 `A6` 把这条钉成判据，
免得下一轮又有人来问"是不是漏了"。

---

## 7. 判据与变异

### `check174.py` — 39 条，五段

| 段 | 内容 |
|---|---|
| A | 取证账：数量 / **逐变体 A/B 双盲** / 逐章 / 分类 / 两房都登记 / 零实例变体 / **为什么按实例落边** |
| B | 路由对账：51 条与取证**一一对应** / 目标真实 / priority 段无空洞 / 字段自洽 / **`precreate` 与源房对得上** / 负控制编造名 / **172 那 798 条一条没动** + **42 条误标留档** |
| C | **端到端**：51/51 解析出目标 / 目标真实 / 11 个场景分流 / **负控制"摘掉本轮边 ⇒ 51→0"** / 不给 `pos` 退回 priority / **可达图不变** |
| D | 不造 + 反回滚：条数 floor / 既有 3197 物件没动 / 形状 / 查重 / **载体两路** / 未登记泄漏 / 可见性 |
| E | 自检：单一 harness / AST 查恒真 / 条数下限 / 零外部盘 / 不起真机 / 零网络 |

### 变异 8/8

| 编号 | 改什么 | 期望报红 | 实际 |
|---|---|---|---|
| M1 | 删一条变体边 | B0 | `B0 B1 B3 D0` ✅ |
| M2 | `door_x` 挪 1px | B1 | `B1` ✅ |
| M3 | 变体边改标成 `obj_doorAny` | B6 | `B0 B1 B3 B6` ✅ |
| M4 | priority 挪到段外 | B3 | `B3` ✅ |
| M5 | `_original.via` 改假名 | B4 | `B4` ✅ |
| M6 | 删一个变体物件 | C1 | `C1 C2 C3 C4` ✅ |
| M7 | 给变体物件加 sprite | D2 | `D2` ✅ |
| M8 | 塞进 `desktop.json` | D4 | `C1 C2 D1 D4 D5` ✅ |

---

## 8. 连带改的老锁（**7 把**，全是判据口径跟着数据扩，不是放宽）

| 文件 | 改什么 | 为什么 |
|---|---|---|
| `check173` | `D0` 路由条数 `==` → **`>=` floor**；`D1` 的"非本轮对象"从 `!= obj_doorAny` 扩到 **整个家族** | 否则 174 一加边/一加物件，173 的守卫就自己红了 —— 守卫口径必须跟数据一起扩，否则它守的不是"没被改"而是"没被新轮次改" |
| `verify_objects44` | 不可见豁免白名单 `[obj_doorAny]` → **`ANY_FAMILY`（逐个列名）**；`_count_any_expected` 同步；`A3b` 820 → **871**；`A3c` 加两个正控制 + 一个负控制（零实例的 `Modespecific` **不在**白名单） | 51 条新物件"没 sprite"是**合法**的，但豁免必须**记账**，否则白名单就是黑布 |
| `verify_scene_fit99` | `G24c` 的 `None` 条数 2475 → **2526**、`_n_any_none` 扩到家族；`G25` 过滤面 47 → **49** | 同上；`_none_other` 仍然要求"除 ut 与 doorany 家族外一个都不许有" |
| `check124` | `_door_id` 从 `when_door or when_src` 扩成 **`…@door_x,door_y`**（有坐标时）；`D2` 的重复条数改成 **`5 + 变体边数`** | ① 同一对象的**多扇实例**（同坐标不同目标 / 同目标不同坐标）不再被误判成"同门重复"；② 重复数改成结构化期望，**别的来源**冒出重复照样红 |
| `check171` | `E1` 的 `dup == 5` → **`5 + 变体边数`** | 同上 |
| `check172` | `A5` 重复组 `== 5` → **`5 + 变体边覆盖的组数`**；`C5`"非 Any 的对象级分组零多候选" → **排除整个 doorany 家族**；`E2`"死胡同场景本轮之前确实 0 条边" → 口径改成**除 doorany 家族以外**的出边 | ① 变体边**有意**与既有 (场景,目标) 重复；② 变体本来就靠多候选 + 坐标消歧（11 个场景真在分流），把它算进"零影响"就会把本轮有意引入的消歧当成回归 |
| `第36轮 verify_scene_route_original` | `C3` 的分派加 `delta_door_any_variant` 分支；`_any_self_ok` 的 `via`/`when_src` 从常量扩成**家族集合**；新增 `_n_any_var` 计数 | 否则这 51 条会落到"位移门"分支被逐条判红（首跑 51 条不自洽）。`table` 仍要求**父对象**的 `Alarm_2` —— 变体自己没有 `Alarm_2`，写别的就是编的 |

外加 `regress/run_all.py` 登记 `check174`（含长 desc），并 `--update` 基线。

> 共同口径：**放宽必须配账**。每一处放宽的同时都把"账"钉死
> （条数 / 集合 / 排除后仍要求"一个都不许有"），任何一边多出来都报红。

---

## 9. 遗留

1. **第172轮那 42 条误标边**（`via` 说假话）—— 见 §4，留待单独一轮。
   修它要同时动 `check172` 与 `第36轮 verify_scene_route_original.py` 两套账。
2. **平台速度交接**（`global.plat_hspeed/vspeed`）产品无对应物 ⇒ 不做。
3. **`obj_doorAnyHorz/Vert` 的 ±40 位移**：产品无 `obj_plat_player` ⇒ 恒用原值，不做。

---

## 10. 命令留档

```text
python code-quality-audit/第174轮-Any门变体/_tools/analyze174.py     # 取证分类 + A/B
python code-quality-audit/第174轮-Any门变体/_tools/apply174.py       # 落 51 条边（幂等）
python code-quality-audit/第174轮-Any门变体/_tools/inject174.py --apply  # 物化 51 个物件
python code-quality-audit/第174轮-Any门变体/_tools/check174.py       # 39 条判据
python code-quality-audit/第174轮-Any门变体/_tools/mutate174.py      # 变异 8/8
```
