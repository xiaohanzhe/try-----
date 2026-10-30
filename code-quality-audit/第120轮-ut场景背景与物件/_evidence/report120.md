# 第120轮 · UT 场景的「空壳」补上画面（含一处自纠）

> 承接第115轮 §15 与第119轮 §18.7 登记的头号阻塞项：
> **ut 的 358 个场景 `objects` 全空、`bg` 全 null —— 走进去是纯黑空房间。**
> 本轮把它补上了：**338 间房按原作像素烘出背景并接进产品**，
> 并在收尾时**自己抓出并撤回**了一处「拿外传美术冒充原作」的错接（§120.6）。

---

## §120.1 空壳的根因：UT 是 GMS2 包，之前所有脚本都在读 GMS1.4 的旧槽位

一句话：**不是"没数据"，是"读错地方"。**

| 读的地方 | 结果 |
|---|---|
| `room.Backgrounds`（GMS1.4） | UT 里**恒为空** |
| `room.Tiles`（GMS1.4） | UT 里**恒为空** |
| `room.Layers`（GMS2） | 背景层 / Assets 层 / Instances 层 —— 真数据全在这 |

之前第114/115轮的普查脚本走的是前两条 ⇒ `RoomBackgrounds=0` / `TileRows=0`，
于是 `bg` 只能写 null、`objects` 只能写 `[]`。**结构自洽、跑不报错、就是全空** ——
典型的"静态自洽型"误导。

`dump_roomviz120.csx` 首跑就复现了这一点：`BG=70` 条（资源池里有 70 个背景精灵）
但 `RBG`（room→background 关联）**一行都没有**。

---

## §120.2 本轮取证（UTMT，两个包都跑了）

`_tools/dump_viz120.csx` 输出五段：`ROOM` / `LAYER` / `LBG` / `LSP` / `SPR`，
外加所有被引用精灵帧导出成 PNG。实测：

| | ut | outertale |
|---|---|---|
| `ROOM`（房间） | **338** | **358** |
| `LAYER`（层） | 2,667 | 2,798 |
| `LBG`（背景层） | 428 | 453 |
| `LSP`（legacy 精灵层） | 0 | 76 |
| `SPR`（精灵帧导出） | 481 张全成功 | 537 张全成功 |
| Assets 层资源 | 70 个 | — |
| legacy tile 素材池（单帧合计） | **261,322** 块 | — |
| 房间实摆 tile | **68,863** 块 | **69,163** 块 |
| 房间实摆实例 | 2,135 个 | 2,163 个 |
| 纯填充色兜底房间 | 336 间 | 350 间 |

证据入库：`_evidence/raw/{ut,outertale}/viz120.*.tsv`、
`visasm120.*.tsv`、`draw120.*.tsv`、`roomviz120.ut.tsv`。
（`tiles120.*.tsv` 3.9 MB **刻意不入库**，靠 `ROOM` 表 + 工具可复算。）

---

## §120.3 烘图：`bake120.py` 与它踩过的四个坑

合成顺序：`items.sort(key=lambda z: (-z[0], z[1]))` —— **GM 的 depth 大 = 更靠后 = 先画**。

四个坑，每个都真红过：

1. **★★★ 裁剪坐标系必须用 `ExportAsPNG(tp, f, null, true)`**，
   第三参 `includePadding` 必须 `true`。默认 `false` 会裁掉透明边 ⇒
   导出尺寸 ≠ `BoundingWidth/Height` ⇒ 与 tile 的 `(SourceX,SourceY,W,H)`
   **不是同一坐标系**。实测：137 张里 **44 张**尺寸不一致、**26 块** tile 越界。
2. **★★ 每块 tile 自带 `Tpag`**，就是那块子的纹理页子项 ⇒
   直接导 `Tpag` 成 PNG 就不必自己算 sprite-sheet 坐标（省掉一整层易错数学）；
   去重用 `Data.TexturePageItems.IndexOf(Tpag)`，ut 去重后 **137 张**唯一贴图。
3. **★★ 「资产 `visible`」≠「运行时可见」**。`obj_overworldcontroller` 资产 `vis=True`、
   精灵是 `spr_heartgtfo`，但它在 `Create_0` 里把自己设成不可见，且 `Draw_0` 是自绘
   （只在战斗里画）⇒ 第一版烘图**每间房左上角都多一颗红心**。
4. **★★★ 三层可见性过滤**（本轮建立）：
   - `objmap.vis`（资产级）
   - `Create_0` 里 `pushi.e 0` + `pop.v.i self.visible`（**最后一条为准**）
   - `Draw_0` 里没有 `draw_self` ⇒ 判 `custom`，**不画**（我们不复刻自绘）

   实测分布：

   | | none | self | custom | Create 隐藏 |
   |---|---|---|---|---|
   | ut | 620 | 3 | 161 | 16 |
   | outertale | 638 | 4 | 170 | 17 |

   > 反编译在 UTMT CLI 里**调不通**（`Decompiler.Decompile` 不存在、
   > `Underanalyzer.Decompiler.Decompiler` 也不存在）⇒ 改用
   > `Disassembler.Disassemble(code, Data.Variables, null, true)`。
   > `UndertaleCode` **没有** `Locals` 属性，第三参传 `null`。

**人眼核验**（不是只看 JSON）：`room_ruins1`（Ruins 紫色大厅，Toriel 站在中央花纹前）、
`room_ruins3`（740×240 长走廊，4 个 NPC + 两座 Waterfall 水柱）、
`room_tundra1`（雪镇雪景 + 门柱）、`room_water1`、`room_fire1`（Sans 哨站含送餐台）——
全部连贯、无错位、无缺块。

---

## §120.4 接线：`apply120.py` 的三条纪律

1. **按房间名匹配，不按 `original_room_id`**。`_zone.ut.rooms.json` 里 20 个场景的
   id 是 338~357，**不是 UT 的房间下标**；按 id 接线会把图贴错房间且**不报错**。
2. **只拷真正被引用到的图**。第一版把 358 张全拷进 `bg/`，338 张成孤儿
   （白胖 2.8 MB）。重写为"先在内存定案、只拷被引用到的"。
3. **找不到对应图就保持 `bg: null`**，不猜、不留假路径。

产物：`bg/ut_*.png` **338 张 / 2.47 MB**，`_zone.ut.rooms.json` 对应写
`bg_source: "room.bake120.ut"`。幂等（连跑两次字节相同）。

`bg/` 现状：**836 张 / 17.67 MB**（ut 338 · ch1 40 · ch2 58 · ch3 38 · ch4 53 · ch5 46 · oneshot 263）。

---

## §120.5 渲染链路验证（`verify120_render.py`，11 PASS / 0 FAIL）

**不只看 JSON 字段**，走真链路：`SceneAssetCache` → `Camera` → `scene_render.plan_frame`。

判据：V0 有 bg / V4 素材可读 / V1 出 `K_BG` 指令 / V1b 指令里的 name == JSON /
V2 `native` == 图真实尺寸 / V3 `fit == cover` / V5 不存在的 bg ⇒ native 空且 fit=room /
V5b 进了 missing / V6 尺寸变了 native 跟着变（不是抄 JSON）/ V7 除负控制外没有读不出的图。

★ 这里自己栽过两次：

- 以为"读不到图就不出 `K_BG`" ⇒ 实测 n=1（`plan_frame` **设计上**退回房间矩形）；
- 改成 `not native` 仍假红 —— **`native` 读不到时是 `(None, None)`，非空 tuple ⇒ truthy**。
  最终逐值比 `tuple(nat or ()) == (None, None)`。

---

## §120.6 ★★★ 自纠：20 间 ut 场景被贴了 **outertale** 的图

### 怎么发生的

第二轮接线我跑了：

```
python apply120.py --game outertale --only-missing --source-tag ot \
                   --zone assets/scenes/_zone.ut.rooms.json ...
```

用意是"ut 这边缺图的房间，看看 outertale 有没有**同名**图"。
**这个用意本身是错的**，当时我没查就跑了。

### 查出来是什么

同一份 TSV，两侧房间集合对比：

```
ut  game.droid ROOM = 338
ot  game.droid ROOM = 358
ut ∩ ot             = 338   ← ut 的 338 间 / 全含
ut 独有             =   0
ot 独有             =  20
```

⇒ **outertale 的包 = UT 全 358 间（含 UT 全部 338）+ 自己独有 20 间**。
`_zone.ut.rooms.json` 现在是 **358** 个场景 = UT 的 338 + outertale 独有的 20。
那 20 个名字（`room_steamworks_*` / `room_newhome_*` / `room_of_bog` / `coming_soon`
/ `room_god` / `room_smile` / `room_water_yellow` / `room_fire_alley` /
`room_fire_rooftop` / `room_fire_elevator_s` / `room_modcredits` /
`room_steamworks_factory_elevator`）**在 UT 的 game.droid 里 0 命中** ——
它们是第77轮从跨作品大图 `bigmap66.json` 迁入时**混进 ut 章的**。

### 为什么必须撤

给它们贴外传的像素 = **拿外传美术冒充原作画面**，属于编造。
用户口径「一切根据原作」⇒ 宁可如实留空。

### 撤成什么

`bg: null` + `bg_source: "none"`（= `check77 F3` 的原意「没素材就如实留空」）。
**不动**这 20 个场景本身的存在与命名 —— 它们该归哪一章是另一件事（见 §120.9）。

工具：`_tools/revert120_ot.py`（幂等，连跑两次第二次输出"没有需要撤的"）。

★ 它自己也栽过一次：**首版 `refs` 是扫"磁盘上尚未写回"的 json 得到的** ⇒
那 20 个场景此刻还挂着 bg ⇒ 仍算"被引用" ⇒ 孤儿数恒为 **0** ⇒ 20 张图会留在盘上发霉。
修法：先把本轮要撤掉的引用 `refs -= reverted` 再算孤儿。**dry-run 抓到的**。

删除的 20 张图先落 sha256/尺寸清单到 `_evidence/ot20_manifest.tsv`（可随时
用 `bake120.py` 从 outertale dump 原样重现）。

---

## §120.7 回归锁与老套件的口径更新

### 新增 `check_bg120`（23 条，已进 G2）

A 接线三面对得上（场景名 ↔ 图名 ↔ `bg_source` 前缀）· A0b **338 有 / 20 留空，
且留空的正是"名字不在 UT 房间表里"的那批** · A0c 有图的 338 间名字全在 UT 表里 ·
B 图尺寸 == 原作 w×h（抽样 14）+ 颜色种类 > 2（抽样 40）·
**B1b 留空的 20 间必须"∈OT 且 ∉UT"（撤线理由成立）** ·
C1/C2 **双向全称**：非 UT 房 ⇒ 留空；UT 房 ⇒ 不许留空 · C3 四条合成样本正负控制 ·
D 无孤儿 / 图数 == 引用数 == 338 / 无残留外传图 ·
E 防回滚 338 间 + ≥ 2 MB · F 自检（**AST** 数恒真判据——扫注释会被文案误报）。

### 三套老套件的报红 + 处置

三套都是**报真事实**（本轮改了产品数据），所以改断言、**不放宽**：

| 套件 | 原判据 | 处置 |
|---|---|---|
| `bg_round39` E1 | 新增场景只许 `none`/`C.REAL_HOWS` | 单列 `BAKED_HOWS = ('room.bake120.ut',)`。**不能**塞进 `C.REAL_HOWS` —— B1/B3 是"据第37轮溯源表**重算** how 再比对"，塞进去会让 ut 场景被拿去和 Deltarune 的溯源表比 ⇒ 恒红。另配 **E5**（338 个都有图·在盘·是 PNG）+ **E1b/E6** 负控制 |
| `rooms_round47` B8 | 背景覆盖 == 498（= 235 + 263） | 改**逐章钉死** `{ch1:40, ch2:58, ch3:38, ch4:53, ch5:46, oneshot:263, ut:338}` + **禁止出现未登记的章**。比原来"总数 - oneshot == stock"两段相减更严（后者允许"ch1 掉1、ch5 补1"抵掉） |
| `check77` F3 | 迁入场景 `bg` 全为 None 且 `bg_source == "none"` | 拆两路：`none` ⇒ 必须留空（20 间）／`room.bake120.ut` ⇒ 必须有真图（338 间）／**第三种来源一律报红**；另配 F3b 正负控制 |

`check81 G5`（基线套件集合 == SUITES 集合）在 `--update` 后自然转绿。

### 结果

```
合计：PASS=5927  FAIL=0  套件=119
```

`check_bg120` 23 条已固化进基线。

---

## §120.8 本轮新增/修改文件

**新增**
- `_tools/{probe_types120,probe_tex120,probe_legacy120,dump_layers120,dump_roomviz120,dump_tiles120,dump_viz120,probe_visasm120,probe_draw120,probe_visible120,probe_api120,probe_api120b}.csx`
- `_tools/{run120,bake120,apply120,revert120_ot,verify120_render,check_bg120}.py`
- `_evidence/raw/{ut,outertale}/*.tsv`、`_evidence/ot20_manifest.tsv`
- `ralsei_pet/assets/scenes/bg/ut_*.png`（338 张）

**修改**
- `ralsei_pet/assets/scenes/_zone.ut.rooms.json` —— 338 间接 `room.bake120.ut`；
  20 间 `bg: null` / `bg_source: "none"`
- `code-quality-audit/regress/run_all.py` —— 新增 `check_bg120` 条目 + 三套 desc 口径同步
- `第39轮/verify_bg_round39.py`、`第47轮/verify_rooms47.py`、`第77轮/_tools/check77.py`

---

## §120.9 遗留（如实登记，本轮不做）

1. **★ 那 20 个场景该归哪一章，是待裁定项。** 取证已定：它们不是 UT 的房间。
   最干净的处置是移出 ut 章（改归 outertale 章或删除），但那会动**场景总数 2166**
   与多套老判据的分母（`rooms47 A5` / `check77 E1` / `bg_round39 A1`…）⇒
   需要单独一轮做，且要先向用户确认「ut 章要不要保留这 20 间」。
2. **`_zone.outertale.*.json` 的 244 个场景仍无法接线**：它们的 `original_room_id`
   是本项目自编号（第99轮 note 明写），与本轮 outertale game.droid 的房间名
   **0/244** 命中。没有对照表就不接线。★ 现在多了一条线索：
   outertale 的 358 间里 338 间名字与 UT **完全相同** ⇒ 若 outertale 场景的
   `name` 字段可用，可以按**名字**接，但要先核那 244 个 `name` 到底是原名还是自命名。
3. **ut/outertale 的 `objects` 仍全空**（本轮只补了 `bg`）。可交互物
   （可读物 / 门）还没摆 —— 这是下一层，数据已在 TSV 里（`SPR`/实例段）。
4. **tile 越界 26/27 块**（ut/outertale）：`(SourceX,SourceY,W,H)` 超出贴图边界的
   tile 被跳过，未逐块归因。数量极小（68,863 分之 26）。
5. `apply120.py` 的第二条用法示例已加 ⛔ 警示，但**没删** —— 保留是为说清
   "当时为什么这么跑、错在哪"。
