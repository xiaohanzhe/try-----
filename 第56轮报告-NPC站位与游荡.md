# 第56轮报告 — NPC 站位 / 游荡 / 结伴 / 桌面白名单

- 轮次：第 56 轮
- 基线：`caaf935`（第55轮：灵魂实体 + 13 份 NPC 人设 + 一人一份独立记忆 + 模型档位校正）
- 主题：给 35 个已登记 NPC 落**城堡镇初始站位**、加**自己游荡**、加**抱团与结对互动**，并给**电脑桌面**设白名单

---

## 1. 本轮指令（逐字）

> 「对于那些npc参考原作给他们设定的初始在城堡镇里的位置再加一些自己游荡的特性，就像是，主角团会总凑在一起，其他npc一部分也会有相互经常互动的情节，参考原作，其次，只有主角团最多加个lancer能来电脑桌面，其余的不能」

拆成四件事：

| # | 指令 | 落点 |
|---|---|---|
| ① | 参考原作，给 NPC 设定城堡镇里的**初始位置** | `assets/npc/_placement.json` 的 `placement`（34 条） |
| ② | 加**自己游荡**的特性 | `modules/npc_placement.py` 的 stand / patrol / pace 三模式 |
| ③ | 主角团**总凑在一起**；其他 NPC **一部分**会互相经常互动 | `groups`（1 组编队）+ `bonds`（9 条结对） |
| ④ | **只有主角团 + Lancer 能来电脑桌面** | `npc_system.DESKTOP_ALLOWED_IDS` + `world_gate` 第 0 条 |

---

## 2. 先解决"原作坐标从哪来"这件事

本轮最早卡住的**不是**写代码，而是**取证**。必须先把"原作数据"与"我编的数据"分清，否则整张表就是一张看起来很像原作的假表。

### 2.1 场景 dump 里**一个 NPC 实例都没有**

`assets/scenes/**` 的实例 dump 一共只有 **40 类**门 / 落点 / 存档点，**含 0 个 NPC 实例**。
⇒ 从场景文件里**拿不到**"Lancer 站在 (793,92)"这种事实。

### 2.2 真证据在第49轮的 UTMT 反编译 GML 里

`code-quality-audit/第49轮-NPC与球容器/_evidence/gml/` 下有 5 章逐对象的 `Create_0` / `Step_0` / `Draw_0` 脚本。本轮只把这批文件当**唯一**的"原作硬证据"来源：

| 证据文件 | 本轮从它取走什么 |
|---|---|
| `ch4.obj_room_castle_lancer_Create_0.gml` | **完整站位表**（108 行）：`lancer_npc=(793,92)`、`elegant_npc=(869,92)`、`ponman=(665,268)`、`tasque=(890,348)`、`maus=(880,188)`、`poppup=(924,297)`、`hacker=(740,254)`、`swatchling=(656,26)`、`dozer_marker=(940,47)` |
| `ch4.obj_room_castle_lancer_Step_0.gml` | **巡逻的逐字写法**：`target = (alt % 2) ? (xstart + N) : xstart` + `scr_flip("x")` + `x = scr_movetowards(x, target, speed)`；三个实数例：maus `N=180 speed=2`、poppup `N=124 speed=1`、tasque `N=130 speed=1` |
| `ch4.obj_room_castle_queen_Create_0.gml` | `instance_create(200, 150, obj_npc_room)`；同房 trashy`(315,175)`、Rouxls 台灯`(127,275)` |
| `ch4.obj_room_castle_tenna_Step_0.gml` | `x = 478; y = 376;` |
| `ch2.obj_npc_king_Step_0.gml` | **踱步**：`x < 1380` 时 hspeed 累加到 3+ 且 `y -= 4`；`x > xstart` 则 hspeed −= 1 且 `y += 4`；`x > 1455 ⇒ x = 1455` |
| `ch1.obj_npc_room_Create_0.gml` / `ch1.obj_npc_puzzlemaster2_Create_0.gml` / `ch1.obj_npc_sign_Create_0.gml` / `ch2.obj_npc_mansion_room_Create_0.gml` / `ch2.obj_npc_police_Create_0.gml` / `ch4.obj_npc_gerson_Create_0.gml` / `ch5.obj_npc_castle_cafe_Create_0.gml` | 其余 `obj_npc_*` 的**落点** |

### 2.3 主角团"总凑在一起"的原作机制

`scr_makecaterpillar`：`target = 12 + slot * 12`（**落后主角的帧数**）；`obj_caterpillarcha` 存 **25 帧**位置历史；`scr_setparty` 正好**两个队友位**。
⇒ 原作里队友是**走主角走过的路**，不是各走各的。本轮照此实现（见 §3.3）。

### 2.4 数据层把"哪条是原作、哪条是我编的"写死在条目里

`_placement.json` 每条都有 `source` ∈ `original` / `derived` / `authored`，并配 `evidence`（指向上面哪个 GML）与 `why`。
本轮实际分布：**original 17 / derived 8 / authored 9**。
另外 `how_original_works` 六条机制里，**唯独 `pace` 一条明写"这是概括、只借它的形状"**，并点出原作右行支被 `global.flag[20] == 3` 门控 —— 不假装逐帧一致。

---

## 3. 交付物

### 3.1 数据层 `ralsei_pet/assets/npc/_placement.json`（28,186 B）

顶层键：`schema_version / note / source / how_original_works / rules / hubs / groups / bonds / placement / unplaced / desktop / counts`。

`counts` 自报：`{'placed': 34, 'unplaced': 1, 'groups': 1, 'bonds': 9, 'by_source': {'original': 17, 'derived': 8, 'authored': 9}, 'desktop_allowed': 4}`。

每条站位含 `id / scene / pos / facing / mode / room_id / room_raw / source / evidence / why`，巡逻与踱步另带 `patrol{offset,speed}` / `pace{end,clamp,speed}`。例：

```json
{"id":"lancer","scene":"ch4.card_castle.cc_lancer","pos":[793,92],
 "facing":"down","mode":"stand","room_id":89,"room_raw":"room_cc_lancer",
 "source":"original","evidence":"ch4.obj_room_castle_lancer_Create_0.gml"}

{"id":"king","scene":"ch2.my_castle_town.dw_castle_dungeon","pos":[1180,380],
 "mode":"pace","pace":{"end":1380,"clamp":1455,"speed":3},
 "room_id":69,"room_raw":"room_dw_castle_dungeon","source":"original"}

{"id":"ralsei","scene":"ch2.ralsei_room.dw_ralsei_castle_front","pos":[500,620],
 "facing":"down","mode":"patrol","patrol":{"offset":180,"speed":1},
 "room_id":63,"room_raw":"room_dw_ralsei_castle_front","source":"original"}
```

`room_raw` 是**原作内部房间名**（不是我们自己的场景 id）——用来给判据当"锚"，见 §5。

`desktop` 段是**数据镜像**，`source` 明确写 `user`，并逐字抄了本轮用户原话：
`"quote": "「只有主角团最多加个lancer能来电脑桌面，其余的不能」(第56轮用户原话，逐字)"`。
**代码侧单一真源**在 `npc_system.DESKTOP_ALLOWED_IDS`，两处由判据 M1 逐字比对。

### 3.2 运动学层 `ralsei_pet/modules/npc_placement.py`（929 行）

零依赖：顶部只 `import collections / json / logging / math / os`（+ `try: from logger_utils import get_logger`），**函数体内零 import**（AST 强制）。

三模式：

- `stand` —— 不动，只按 `facing` 定朝向。
- `patrol` —— 沿 `x` 在 `[xstart, xstart+offset]` 上**精确折返**，用 `_movetowards` 一类的收敛步进，步长 `speed`。
- `pace` —— 区间 + **y 起伏**（去程上浮、回程落回）+ `clamp` 硬钳制。

编队 `PartyRig`：`lag = 12 + slot*12` 帧，按 `GAME_FPS=30` 换算成"落后 **72 / 144 px**"（`lag × 每帧位移`）。
`Trail` 是 25 帧位置历史且**采样**（不是外推）。

结对 `Bond`：`approach`（互相凑近到 `gap` 停住）与 `face`（只转向、不移动）两种。

> **自创值必须标注**：原作**没有**"两个 NPC 互相凑近"这套机制（原作只有主角团 caterpillar 跟随）。因此 `BOND_APPROACH_SPEED = 40.0` 是本项目自创量，代码注释与数据 `why` 都写明了出处，不冒充原作。

### 3.3 政策层 `ralsei_pet/modules/npc_system.py`（548 行，+60/−2）

```python
DESKTOP_SCENE = 'desktop'
DESKTOP_ALLOWED_IDS = ('ralsei', 'kris', 'susie', 'lancer')   # ★ 第56轮用户口径，代码侧单一真源
REASON_DESKTOP_FORBIDDEN = 'desktop_forbidden'
```

`world_gate` 里新增**第 0 条**规则，插在光世界分支**之前**：

```python
if scene_id == DESKTOP_SCENE or world == DESKTOP_SCENE:
    if desktop_allowed(npc):
        return GateResult(True, REASON_OK, 'desktop_allowed')
    return GateResult(False, REASON_DESKTOP_FORBIDDEN,
                      '%s 不能来电脑桌面（只有主角团和 Lancer 可以）' % npc.name_cn)
```

**为什么必须排在最前面**（三条，任一成立都不能挪）：

1. `_worlds.json` 的 `overrides.desktop == "light"` ⇒ 若先走光世界分支，**所有** NPC 都会被判"可进"；
2. 电脑桌面是 Ralsei 自己的家（`BEDTIME_HOME_SCENE == 'desktop'`）⇒ 先判光世界会让他走 `LIGHT_NEEDS_BUBBLE`，**回不了家**；
3. `verify_npc49` 的 E1~E11 **没有一条**传 `scene_id='desktop'` ⇒ 顺序改动不会翻旧契约。

### 3.4 接线层 `ralsei_pet/src/main.py`（11,641 行，+283/−8）

- 新增 `from modules import npc_placement as npc_placement_mod`
- `init_npc_systems`：装站位表 → **镜像不一致就告警** → 建 `Trail` / 编队 `rig('party')` → **开局就播种**
- `_on_scene_switched_npc`：换场景时 **先清理 → 再播种** → 最后才问"跟不跟"
- 新增一组方法：`_npc_carried_ids` / `_npc_anchor_id`（桌面=Ralsei，房间=编队 leader，缺则 Kris）/ `_npc_anchor_pos` / `_npc_scene_roster`（**站位表 ∩ 注册表 ∩ world_gate**）/ `_npc_desktop_roster` / `_npc_build_desktop_bodies` / `_npc_seed_bodies` / `npc_placement_tick(dt)`
- `update_movement` 内接一行 `self.npc_placement_tick(elapsed_time)`

**`_npc_desktop_roster` 刻意只走 `world_gate` 一条判据**（不查数据镜像）：两道判据会形成"多解闸"——将来两边不一致时，被测物到底被哪道拦住的就说不清了。判据 `T10b` 用 AST 把这条钉住（必须调 `world_gate`、**不许**调 `desktop_allowed`）。

---

## 4. 本轮顺手修掉的一个**判据缺陷**（不是产品缺陷）

第52轮的 `check52c.py` 有三条判据把 `main.py` 的**绝对字节偏移/字面量总数**打进了诊断串：

- `A3c` → `lounge=%d rand=%d`、`A3d` → `bed=%d sleep=%d`、`A8c` → `取样数=%d`

`main.py` 每轮**合法变长**，这三个数**必然漂移** ⇒ 套件每轮都报"输出与基线不一致"。断言本身没错（判的是**位置先后**与**样本非空**），错的是诊断串。
危害不止噪音：它训练出"闭眼 `--update`"的习惯，**于是一条真回归会被顺手一起吞掉**。

**修法**（只动诊断，不动断言）：A3c/A3d 改报**顺序**（`lounge→rand`）；A8c 把"正好 1519 个"改成**下限** `len(MAIN_CONSTS) >= 1000` 并只报"够不够用"。
修完单跑 `dialog_lounge52` = **82 PASS / 0 FAIL**（断言集合未变），随后重建基线。

---

## 5. 验证矩阵

| 判据 | 结果 |
|---|---|
| `code-quality-audit/第56轮-NPC站位与游荡/check56.py` | **137 PASS / 0 FAIL** |
| 鉴别力体检 `_tools/mutate56.py`（12 处定点破坏） | **12/12 命中**，逐字还原后复跑全绿 |
| 第49轮契约 `verify_npc49.py` | **83 PASS / 0 FAIL**（零回归） |
| 全量 G2 `code-quality-audit/regress/run_all.py` | **54 / 54 IDENTICAL**，PASS=**2898** FAIL=**0**，无问题段 |
| 桌面闸冒烟（手工脚本） | 白名单 4 人**全放行**；toriel / asgore / king / queen / susiedark / noelle / berdly / spamton **全拒**且原因码 `desktop_forbidden`；同一人不在桌面时放行；Ralsei 上桌面**不需球**而光世界其他场景**仍需球** |

`check56` 的九段：**A** 零依赖（AST，含用 `main.py` 做的负控制）／**D** 数据层 19 条（★`room_raw` 必须与房间几何表的真实内部名**逐字**一致、坐标与巡逻端点必须落在房间盒内、**标 `original` 的坐标必须在 GML 里逐字存在** + 负控制"一个编出来的坐标不在 GML 里"）／**M** 数据↔代码镜像／**W** 游荡三模式（含零长度段不空转、pace **第一趟就上浮**、`dt` 钳到 `MAX_DT`）／**G** 编队（**落 72/144 px**、错位在 y、不重复入队）／**B** 结对（**精确停在 `gap` 且全程不过冲**、face 只转不动含竖直方向）／**K** 桌面闸本体／**T** 产品接线（AST + 真机 `RalseiPet()`）。

### 5.1 排查过的**真缺陷**（都是本轮自己写出来的）

| 症状 | 根因 | 修法 |
|---|---|---|
| 两人竖直相对时都被判"朝下" | `_facing_for(dx)` 只吃一轴 | 新增 `_facing_between(dx, dy)`，取**占优轴**（等价 45° 分档） |
| 队友落后 132 px 而非 144 | `PartyRig.place` **无条件 push**，而调用方本来就每帧 push ⇒ 整条轨迹被挪后一帧 | 加 `Trail.head()`，`head != anchor` 才 push |
| 落后量被污染成 78 | 错位量加在 **x** 上，正好污染"落后量"这条可测量 | 错位量改加到 **y** 上 |
| 结伴在 `gap` 附近**永久抖动**（200 帧后停在 68.00 而非 72） | 两人各走"**整份**超出量"⇒ 一帧压到 gap 以下、下一帧又推开 | 每人只走 `min(step, rem * 0.5)` |
| `pace` 第一趟不上浮、第二趟起才浮 | `Body.__init__` 的 `y_target` 恒取 `ystart`，与 `_step_pace` 端点处**同一判据给出相反结论** | 统一成 `ystart - RISE if target != xstart else ystart` |
| `_step_pace` 零长度段每帧声称"动过" | `return True` 与 `_step_patrol` 口径不一致 | 改 `return False` |

另外 `check56` **首跑 10 项 FAIL**，逐条查证后其中 **8 条是判据自己写错/写窄**（例如 `B16` 期望 kris/susie 同场景，而原作 ch2 里他们分处**两间不同客房**）—— 按仓库元规则"报红先怀疑判据"，改判据并**如实登记** kris/susie 这条结对在当前站位下不生效。

---

## 6. 复检（用户口径：改过重要核心文件必须复检）

`_tools/recheck56.py` → `_evidence/recheck56_result.txt`，六类判据逐项 PASS/FAIL 落盘，结果 **PASS=23 / FAIL=0**：

1. **可解析** —— 全部改动 `.py` 走 `ast.parse`（**不用 `py_compile`**：它会落 `.pyc`，改变被检状态）；全部改动 `.json` 可解析
2. **结构自检** —— 本报告章节 1~8 全在、无标题粘连；`_placement.json` 顶层键集合；`counts` 自洽；`placement ⊎ unplaced ==` 注册表 35 条；`baseline.json` 含 54 套件且登记了 `npc_place56`；`run_all.SUITES ==` 基线集合；三个真机套件都在 `HERMETIC_IDS`
3. **编码** —— 无 BOM、无 U+FFFD、均为合法 UTF-8
4. **恒真判据复查** —— AST 扫本轮判据脚本，抓"裸写的常量条件"；配**正控制**（合成的裸写必须被抓出）与**负控制**（`try/except` 里的真假分支属合法写法，不许误报）；另断言 6 条骨架判据仍在
5. **逐令牌回验** —— 本轮新增/保留的 **21** 个令牌逐个回原文件 `in` 一次；**外加反向**：改掉的旧诊断串（`"lounge=%d rand=%d"` 等）必须**真消失**；报告里的关键数字必须与实测一致；★ **记忆压缩**的 6 个"被移除令牌"逐个回**详版** `in` 一次；速查本体量自查 ≤ 注入上限
6. **工作区干净** —— `git status --porcelain`（无 `R`/`D` 行）+ 删除行数 < 1000 闸

### 6.1 本轮还动了**记忆文件**（属重要核心文件）

速查本 `.workbuddy/memory/MEMORY.md` 撞上注入上限：**用前 `js_len = 9988` / 10000**，加完第56轮三段后一度 **10035（超限 35）**，压后 **9994（余量 6）**。
按 `agent-memory-compaction` 铁律执行：**先补详版**（新增 §52 完整章节 266K→275K 字符）**再压速查本**，压缩动作全部是**结构性**的：

- 把「原文全文已在详版」的两段（P1 前置 → §51.10-C、资产与场景 → §51.10-A）改成**指针**；
- §10 历轮索引的「编号→主题」映射改为只留主题串（映射在详版 §14–§51 与各轮报告）；
- 合并两个"已裁定"项；去掉与 §7/§52 重复的令牌（`dump_rooms.csx` / `hubs` 未被消费 / 溯源 17/8/9）。

**判据名 / 数字 / 路径 / 代码片段一条没削**（`A12d`、`8.3%`、`AI_REPLY_MAX_CHARS=220`、`K3 < 10000 B`、`DESKTOP_ALLOWED_IDS`、`lag=12+slot*12`、`72/144px` 都留在速查本）。§5 人味线**整段未动**（它含 4 个数字/判据名，削它就要一次下沉 + 回验，本轮不动手）。
★ **下轮必须先压再加**（余量只剩 6 个 JS 字符）；§7 的「相机/换房」「房间拓扑」「自主寻路」三段都符合"原文全文已在详版"的条件，是下一批可压对象。

★ 记一笔：`recheck56` 的 **5d** 首跑报红，抓到的是**我自己**——§52.9(C) 的"原文留档"漏抄了原句的 `（§43.6/§45；细节 §51.10-A）` 前缀，于是 §52.9(E) 里"逐令牌全部命中"的说法**未经证实**。补足原文后才转绿。这正是"判据要能证伪"的价值。

---

## 7. 诚实登记（缺口 / 不一致 / 未生效项）

**这些是本轮明确**没有**做到的，不掩饰：**

1. **★ 渲染缺口（最重要）**：`assets/sprites/` 里**一个 NPC 帧都没有**（第49轮只导出了扭蛋球 + 四个可进球角色）。本轮 `_placement.json` 的 34 条站位/游荡是**位置层**，逐场景又只见到门口 27 个门精灵 ⇒ **关掉 `SCENE_LAYER_ENABLED` 后，屏幕上看不到任何一个 NPC**。
   待补：`spr_npc_*` 精灵帧。原料齐全（`E:\Download\_tmp\drw\chapter{1..5}_windows\data.win` 与 UTMT CLI 都在）；
   可作抓手：`spr_npc_*` 的来源可从第49轮 GML 的 `sprite_index` 抓。
2. `rouxls` 注册表 `chapters` 只写 ch3，实际横跨 ch4/ch5 —— **数据不一致，未修**。
3. **9 条 `authored`**：`gerson` / `flowery` / `hammerguy` / `dumpster` / `addison_tea` / `rabbits` / `wrapper` / `doubter` / `susiedark` —— 原作没有给落点脚本，位置由我按场景语义安排，已逐条登记，**不冒充原作**。
4. `toriel` / `asgore` / `berdly` / `noelle` 按原作放在**光世界**（教室 / 家乡北街 / 学校），因此他们在城堡镇站位表中**不在场**。
5. **9 条结对里只有 `berdly↔noelle` 是同场景**（可生效）；其余 8 条跨场景。其中 `toriel↔asgore`、`kris↔susie` 在**当前站位下永不生效**（分处换章 / 两间客房），`note` 已写明"保留是为了将来同场景时自动成立"。
6. `knight` 列在 `unplaced`：「不是城堡镇居民，也没有任何 `obj_npc_*` 站位脚本 ⇒ 不给他编安身之所」。
7. `mike` / `knight` / `spamton` **仍未装人设**（等用户给设定），因此本轮他们只有站位、没有台词。
8. **`scenes/*` 里零 NPC 实例**这个事实本身决定了：本轮**不可能**做到"NPC 会随时间走动/离场"。原作那些行为写在 `Step_0` 里（如 king 的 `flag[20] == 3` 分支），本轮只搬了**形状**，没有搬**门控条件**。

---

## 8. 遗留与待裁定

**本轮遗留（下轮可直接拣）**

- 补采 `spr_npc_*` 精灵帧，让 §7.1 的"位置层"真正看得见。
- `kris↔susie` / `toriel↔asgore` 两条结对的"同场景才成立"目前只是 `note`，可考虑改成运行时**显式 no-op + 日志**，避免读表的人误以为它在工作。
- 表驱动的 `hub`（区域）概念已进数据(`hubs`)，运行时**尚未消费**。
- ★ **记忆容量**：速查本余量只剩 **6** 个 JS 字符 ⇒ 下轮往速查本加东西前**必须先压**（§7 的「相机/换房」「房间拓扑」「自主寻路」三段都符合"原文全文已在详版"的条件，是下一批可压对象）。

**等用户发话**

- `mike` / `knight` / `spamton` 的设定（人设 + 是否允许上桌面）。
- 第55轮遗留："NPC 画进场景走动"需 UTMT 补采 `obj_herokris` / `obj_herosusie` 实例。
- 第49/50轮遗留：`toggle_bubble` 仍无交互入口；球每帧 offset 未导出；实机目视验收未做。

---

## 附：本轮改动集合（`git diff --numstat`）

```
283    8   ralsei_pet/src/main.py
 60    2   ralsei_pet/modules/npc_system.py
 23    0   code-quality-audit/regress/run_all.py
 18    3   code-quality-audit/第52轮-对话与人味收口/_tools/check52c.py
 12    6   code-quality-audit/regress/baseline.json
新增：ralsei_pet/modules/npc_placement.py（929 行）
新增：ralsei_pet/assets/npc/_placement.json（28,186 B）
新增：code-quality-audit/第56轮-NPC站位与游荡/（check56.py 730 行 + _tools/mutate56.py 151 行）
```

暂存区删除行数 **19 行**（守卫阈值 1000），无 `R`/`D` 行。
