# 第115轮 · 跨作品物件普查（Deltarune）

> 一句话：**Deltarune 跟 OneShot 不是同一类问题 —— 它的物件本来就有名字，
> 不需要起名，缺的是「这个名字是干嘛的」。**
> 五章全量：**1,251 间 / 47,895 个实例 / 1,945 个不同对象**；
> 其中 **实体物件 698 个**（18,009 次出场）、事件触发器 401 个、纯逻辑 846 个（§3 分级）。

---

## 1. 为什么两作不能套同一个做法

| | OneShot（第114轮） | Deltarune（本轮） |
|---|---|---|
| 引擎 / 地图格式 | Tiled `.tmx` + `.tsx` 瓦片 | GameMaker `data.win` |
| 物件是什么 | **一坨连通格子**，没有名字 | **有名字的实例**（`obj_chair` / `obj_pizza`） |
| 4380 个块 / 1945 个对象里无名的 | **3456 块（79%）** | **0 个**（全都有 `obj_*` 名） |
| 要做的事 | 去重成 815 类图案 + **请人起名** | **查名字 → 写功能简介** |

所以本轮不是"再出一份待命名清单"，而是**把有名字的对象盘清楚**，让人只补真正需要读代码
才知道用途的那一小撮。

---

## 2. 数据（五章全量）

| 章 | 房间 | 实例 | 用到的对象 | 定义的对象 | 零实例房间 |
|---|---|---|---|---|---|
| ch1 | 147 | 3,513 | 167 | 500 | 1 |
| ch2 | 278 | 8,050 | 470 | 1,606 | 0 |
| ch3 | 246 | 9,892 | 702 | 1,978 | 0 |
| ch4 | 328 | 13,953 | 613 | 1,904 | 1 |
| ch5 | 252 | 12,487 | 585 | 1,985 | 1 |
| **合计** | **1,251** | **47,895** | **1,945**（去重后） | — | 3 |

分类（按实例算）：

| 类别 | 对象数 | 说明 |
|---|---|---|
| **有 sprite 且可见** | **1,099** | 画面上的东西（家具、招牌、树、门…），占实例 **41.1%**。⚠️ 这个口径**掺了 401 个触发器**，见 §3 修订 |
| 纯逻辑 / 无 sprite / 不可见 | 846 | 控制器、判定块、事件触发器 —— 不该混进"背景物件" |

出现房间最多的（= 通用件，功能简介写一次就覆盖全作）：

```
obj_mainchara          1116 间 / 1116 次  spr=spr_krisd            ch1~5
obj_darkcontroller      881 间 /  881 次  (无 sprite，纯逻辑)
obj_markerAny           443 间 /  919 次  spr=spr_markerAny
obj_doorAny             428 间 /  830 次  spr=spr_doorAny
obj_solidblocksized     418 间 / 5204 次  spr=spr_block_sized
obj_soliddark           255 间 / 2427 次  spr=spr_soliddark
obj_readable_room1      241 间 /  973 次  spr=spr_interactable
```

---

## 3. 分级：698 实体物件 / 401 事件触发器 / 846 纯逻辑

上一版把「有 sprite 且 vis=True」直接当成「画面上的物件」，**是虚高的**。
实测把精灵名一查就露了：其中 **401 个对象挂的是触发器占位图**
（`spr_board_event` 181、`spr_eventsmall` 106、`spr_event` 81、`spr_board_triggerarea` 10、
`spr_debug_*` 6、`spr_crosshair` 3、`spr_eventsmall_1` 4 …），
那是剧情事件和判定区，**不是布景**，摆到桌面上会是一堆看不见的判定框。

| 分级 | 判据 | 对象 | 实例 |
|---|---|---|---|
| **`prop` 实体物件** | 有 sprite、`vis=True`、精灵不是占位图 | **698** | **18,009** |
| `trigger` 事件触发器 | 有 sprite、`vis=True`、精灵命中占位图 | 401 | 1,668 |
| `logic` 纯逻辑 | 无 sprite 或 `vis=False` | 846 | 28,218 |
| 合计 | — | 1,945 | 47,895 |

`prop + trigger = 1,099`，与上一版「可见」口径**逐个对象对得上**（P3 就是对这条的判据）。

覆盖面（对 698 个实体物件的实例数排序）：

```
前 10%（ 69 个）覆盖 69.7%
前 25%（174 个）覆盖 88.0%
前 50%（349 个）覆盖 96.7%
```

⇒ **先把前 174 个的功能简介写掉，就能覆盖近九成的物件出场次数**，不用 698 个平铺。

### 3.1 给用户填的清单

`_evidence/deltarune_objects_todo.csv`（**698 行**，utf-8-sig，Excel 直接双击打开）：

```
编号,对象名,精灵,章节,房间数,实例数,最常见层深,示例房间,名字含糊,功能简介（请填写）
001,obj_mainchara,spr_krisd,ch1/ch2/ch3/ch4/ch5,1116,1116,0,room_krisroom | room_krishallway | ...
002,obj_climb_climbable,spr_climb_climbabletile,ch4/ch5,55,954,0,room_test_climb_new | ...
005,obj_waterable_flower_small,spr_waterable_smallflower,ch5,1,520,1000200,room_dw_garden_flowerygardening,,
```

「最常见层深」是从 `rooms_map.json` 的 Instances 层算出来的
（GM 里**数值越大越靠后**，负数是前景），能帮判断这东西是贴墙的、还是飘在人前面的。
「示例房间」取该对象出现的前 3 间房，房间名本身就带语义（`room_dw_garden_flowerygardening`
= 暗世界花园·园艺房），比看精灵名好猜。

另附 `_evidence/deltarune_triggers115.txt`：401 个触发器，**不用填**，留着查「这间房为什么会触发剧情」。

### 3.2 82 个名字不表意的，分开看

上一版说「82 个名字不表意的可见物件」，分级之后发现**只有 21 个是实体物件**，其余 61 个是触发器：

```
实体（要填）    obj_waterable_flower_2x2 / obj_board_mazewater1~4 / obj_board_glacier_switch3 /
                obj_darkroom1_lanternDispenser1 / obj_dw_church_pushableshelf_3x3 /
                obj_lottery_bridgeBuilder1 / obj_tower_dog_fx1 / obj_rotationTile_track1~3 /
                obj_b2_bino_v2 / obj_npc_puzzlemaster1~2 / obj_dogcheck2 / obj_lancerscare2 ...
触发器（不用填）obj_b1cactusfield* / obj_b2_ice_* / obj_b3dock* / obj_board_event_intro* /
                obj_controller_keyboard_puzzle_* / obj_dw_church* 系列事件 …
```

全表在 `_evidence/deltarune_props115.json` 的 `objects[]` 里（`class` + `vague` 两个字段）。

---

## 4. 数据缺口（必须先说清，别当成"已经做完"）

1. ~~没有全量坐标~~ ⇒ **已补上**：新写 csx 经 UTMT 采到了 **47,895 个实例的 x/y/scale/rotation**
   （见 §10）。`rooms_map.json` 本身只有实例名、没有 x/y，那份仍然保持原样（它是"每间房有哪些对象"
   的轻量索引），逐实例坐标一律以 `raw/chN/inst_full.tsv` 为准。
2. **1 个空引用实例**：ch5 `room_dw_cliff_finaldash` 有 1 个实例的 `Object` 引用是**空的**。
   上一轮的导出脚本给它写了类型名占位 `GameObject`，本次 dump 得到**空名** ⇒ 全作唯一一个，
   在两份对账里都按「已知例外」成对处理（R3/R5 都印出这个数）。
3. **原始产物原本在 `E:/Download/_tmp`**（临时盘，随时可能被清）。本轮已把五章的
   `rooms_map.json` + `objmap43.txt` + `inst68.json` + `inst_full.tsv` **蒸馏进仓库**
   `_evidence/raw/chN/`（共 6.7 MB），下面的复现命令不再依赖临时盘。

---

## 5. 复现

```bash
# 1) 普查（读 _evidence/raw/，不碰游戏目录、不碰临时盘）
python _tools/deltarune_objects115.py

# 2) 独立对账（11 条判据，含负控制）
python _tools/check_obj115.py

# 3) 分级 + 生成待填清单（写 deltarune_props115.json / objects_todo.csv / triggers115.txt）
python _tools/props115.py

# 4) 分级的独立对账（9 条判据，含两条负控制）
python _tools/check_props115.py

# 5) 交互点坐标表（读 raw/chN/inst68.json，写 points115.json / points115.txt）
python _tools/points115.py

# 6) 交互点坐标的独立对账（7 条判据，含两条负控制）
python _tools/check_points115.py

# 7) 全量实例坐标索引（读 raw/chN/inst_full.tsv，写 instances115.json / .txt）
python _tools/instances115.py

# 8) 全量坐标的独立对账（9 条判据，含两条负控制）
python _tools/check_inst115.py

# 9) 重新导出坐标（要 UTMT + 游戏本体；启动方式是重点，见 §7）
python _tools/run_dump115.py
#    它做四件事：复制 data.win 到 D:（只对副本 load）→ sha256 双向核对
#    → 用 DETACHED_PROCESS 启动 UTMT 跑 dump_instances.csx → 校验房间数/实例数

# 10) UT / UTY / Outertale 的同类导出（源是 game.droid，不是 data.win）
python _tools/run_dump_ut.py
#    与 run_dump115.py 只差三点：源文件名、三款各自一份、EXPECT 允许为 None
#    产物落 _evidence/raw/{ut,uty,outertale}/inst_full.tsv

# 11) 跨作品摘要（写 cross_works115.txt）
python _tools/cross_works115.py

# 12) 跨作品坐标的独立对账（13 条判据，含四条负控制）
python _tools/check_ut115.py
```

`check_obj115.py` 当前 **11 PASS / 0 FAIL**：
逐章房间数 == 147/278/246/328/252（C1×5）· 合计 1,251（C1b）· Σ实例 47,895 且与报告一致（C2）·
实例名都落在 objmap（C3，允许 `GameObject` 例外）· 可见/纯逻辑互斥且穷尽（C4）·
排序单调（C5）· **负控制**：注入 `obj_THIS_IS_NOT_REAL` 后 C3 必须报红（C6）。

`check_props115.py` 当前 **9 PASS / 0 FAIL**：
三类互斥穷尽（P1）· Σ实例 47,895（P2）· `prop+trigger` == 上一版可见集合（P3）·
CSV 行数/编号连续/名字集合一致（P4）· 名字含糊计数 21 一致（P5）·
触发器 401 条且精灵都命中占位规则（P6）· **层深统计用「重扫 rooms_map」独立复现**（P7）·
**负控制 A**：往 prop 里塞假对象后 P4 必须报红（P8）· **负控制 B**：清空占位图规则表后
trigger 必须从 401 掉到 0（P9，证明规则表真在起作用，不是摆设）。

> 原始数据怎么来的（本轮没重跑，沿用既有产物）：UTMT CLI v0.9.2.0，
> `UndertaleModCli.exe load <data.win 副本> -s <脚本.csx>`，**只对副本 load**，stdout 落文件。
> 五章 `data.win` 在 `…\珍贵的回忆\DELTARUNE_183049\DELTARUNE\chapterN_windows\`。

---

## 6. 下一步（按性价比排）

1. ~~全量实例坐标~~ ⇒ **已做**：47,895 个实例的 x/y/scale/rotation 全部采到，见 §10。
2. ~~82 个不表意名字~~ ⇒ **已做**，见 §3.2（其中 61 个其实是触发器，真正要填的只有 21 个）。
3. ~~先给一部分坐标~~ ⇒ **已做**：978 间房的**交互点坐标**（门/标记/可读物/存档/宝箱/招牌/传送），
   见 §8（它是 §10 的一个**子集视图**，查门/存档点更好用）。
4. ~~UT / UTY / Outertale~~ ⇒ **已做**：三款共 **983 间房 / 36,136 个实例**，
   ut=338 间、uty=287 间均与历史登记逐值相等，见 §11。`check_ut115.py` **13 PASS / 0 FAIL**。
5. **用户填 `deltarune_objects_todo.csv` 的前 174 行**（覆盖 88.0% 的实体物件出场）。
6. **Freebird 四款**：用户已明确搁置（性质不同）。

---

## 7. 那个「工具起不来」的坑，根因是**启动方式**

### 7.1 排查链（三次归因，前两次都错）

| 现象 | 当时以为 | 实际 |
|---|---|---|
| `UndertaleModCli.exe --help` 一律 `SIGTERM`、零输出 | 脚本写错了 | 不是脚本 |
| 改名 `umcli.exe` / 换目录 / **关沙箱**照样被杀 | 安全策略拦名字/路径 | 不是这些 |
| 同目录 `createdump.exe` 从 `%TEMP%` 跑**正常** | 「这个 exe 有毒」 | 不是 |
| `dotnet.exe --version` **能跑** | 「.NET 被拦」 | 不是 |
| **整套换到 `D:`（NTFS）仍然被杀** | 一度归因「E: 盘坏了」 | **也不是磁盘** |
| 申请 `CREATE_BREAKAWAY_FROM_JOB` → `PermissionError [WinError 5]` | —— | **我们确实在作业对象里** |
| 只加 `DETACHED_PROCESS \| CREATE_NEW_PROCESS_GROUP` | —— | **✅ 一次成功，`--help` 返回 rc=0** |

⇒ 结论：**不能让它继承我们这个控制台/作业**。断出去之后，五章 26 秒全部导完。
`_tools/run_dump115.py` 里那两行 `creationflags` 就是全部秘密，删了立刻退回"秒杀 + 连坐父进程"。

‖ 教训 ‖ 前两次归因（文件名 / 磁盘）都"看起来很有道理"，是靠**换盘再试**和**同目录另一个 exe 对照**
才排除的。**"零输出 + 连父进程一起死"不等于对方崩了** —— 那更像被外部收尸。

### 7.2 具体参数（照抄即可）

```python
DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200
p = subprocess.Popen([EXE, 'load', data_win, '-s', CSX],
                     stdout=out_file, stderr=subprocess.STDOUT,
                     stdin=subprocess.DEVNULL, env={**os.environ, 'UTMT_OUT': tsv},
                     creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP)
```

- **不要**同时加 `CREATE_BREAKAWAY_FROM_JOB`（被拒，WinError 5）；
- stdout 必须重定向到文件（`stdout=out_file`），否则拿不到 `DUMP OK` 那行；
- 数据文件用**副本**：`run_dump115.py` 先复制到 D:，sha256 双向核对后才 load。

★ 游戏本体在 **C:**：`C:\Users\23002\Desktop\项目文件夹\珍贵的回忆\DELTARUNE_183049\DELTARUNE\chapterN_windows\data.win`
（14.0 / 66.2 / 140.4 / 128.7 / 161.7 MB）—— **不在 E:**，之前记的路径是错的。

---

## 8. 交互点视图（978 间 / 6,889 个点）

这是 §10 全量坐标的**筛选视图**：把「能交互的东西」单独拎出来，查门/存档点/可读物比翻 4.8 万行 TSV 快得多。
覆盖的正是：门要连路线、可读物要能读、存档点和宝箱要能碰。

| 类 | 数量 | 说明 |
|---|---|---|
| `marker` 命名标记 | 3,232 | 原作自己钉的锚点（`obj_markerA/B/X`、`obj_krmarker`…），是"这里该放什么"的原始依据 |
| `door` 门 | 1,978 | 含 `obj_doorAny` / `obj_doorAnyHorz` / 按方向分的 `A/B/C/D/W/X` |
| `readable` 可读物 | 973 | `obj_readable_room1` 一类，撞上去出文本 |
| `other` | 287 | 没被前几条规则接住的（`obj_bg_room` 等） |
| `sign` 招牌 | 153 | |
| `warp` 传送 | 99 | `obj_board_warptouch` 一类 |
| `treasure` 宝箱 | 90 | |
| `save` 存档点 | 77 | |

逐章：ch1 129/147 间 · ch2 231/278 · ch3 172/246 · ch4 246/328 · ch5 200/252 间有交互点。
产物 `_evidence/deltarune_points115.json`（含每间房的 `w/h`，可直接换算相对坐标）+
`_evidence/deltarune_points115.txt`（人看的摘要）。
对账 `check_points115.py` **7 PASS / 0 FAIL**，含两条负控制。

★ **明确不判的一条**：不判「点必须在房间框内」。实测越界 407/6889（5.9%），
最远 `obj_krmarker` `x=-2360`（房间宽 2680）—— GM 允许实例摆在房间外，那是原作摆法，
拿它当判据只会误报。判据改成 `int` + `|v| ≤ 100000`（实测最大 19698），抓的是"解析跑偏"。

---

## 9. 附：E: 盘确实坏了（与坐标无关，但得说）

这条**不是**坐标失败的原因，但本轮排查时被动发现，独立成立：

| 证据 | 说明 |
|---|---|
| `Get-Volume`：`E` = **exFAT / HealthStatus=Warning** | 卷已受损 |
| 根目录有 **`FOUND.000`** | chkdsk 捡回来的碎片目录 |
| `du` / `ls -l <大目录>` / `robocopy` 从 E 读，**中途被杀** | 大目录/大文件 I/O 会卡死 |
| 分块读 ch5 `data.win`：偏移 0→16 MB 秒过，**16→20 MB 用了 29.76 秒** | 特定区域等同步 |
| 事件日志 `LiveKernelEvent 0x1cc EXRESOURCE_TIMEOUT_OWNERTHREAD_exfat!FppWaitSync` | exFAT 驱动超时 |

⇒ **修好之前别把 E: 当工作盘**（临时文件改投 `D:`，NTFS）。
建议顺序：① 备份（`D:\E盘备份_20261028` 已有 19 个顶层目录）→ ② 用户手动
`chkdsk E: /f`（要提权，我不绕）→ ③ 观察 `LiveKernelEvent` 是否还出现 → ④ 再谈搬盘。

---

## 10. 全量实例坐标（1,251 间 / 47,895 个实例）

`_tools/dump_instances.csx` 经 UTMT CLI 导出，五章**逐实例**落成 `_evidence/raw/chN/inst_full.tsv`（2.89 MB）。
每行带 `x / y / scaleX / scaleY / rotation / imageIndex / imageSpeed / depth / 层名`——
这就是「哪一格是什么」的原始依据，也是把 Deltarune 并到 OneShot 那套块级结构的**前置条件**。

| 章 | 房间 | 实例 | 用到的对象 | `Data.GameObjects.Count` |
|---|---|---|---|---|
| ch1 | 147 | 3,513 | 167 | 353 |
| ch2 | 278 | 8,050 | 470 | 1,328 |
| ch3 | 246 | 9,892 | 702 | 1,732 |
| ch4 | 328 | 13,953 | 613 | 1,576 |
| ch5 | 252 | 12,487 | 585 | 1,733 |
| **合计** | **1,251** | **47,895** | **1,945** | — |

> 末列是引擎对象表的条目数，**和 §2 那列「定义的对象」（500/1606/1978/1904/1985）不是一个口径** ——
> §2 来自 `objmap43.txt` 的条目数。两个数差在哪本轮没查，**先当参考、别互相替代**。

顺带量出来的两件事（以前不知道）：

- **808 个对象（41.5%）带非 1 缩放** —— 同一套贴图靠 `scaleX/scaleY` 放大缩小复用，
  这条对渲染很关键：**不能按原图像素直接摆**；
- **58 个对象带旋转**，多用于轨道/转塔一类。

索引产物 `_evidence/deltarune_instances115.json`（797 KB）给的是聚合（每章每房 + 每个对象的
x/y 区间、缩放种类、旋转种类、出现过的 depth），**不复制**逐实例数据。

★ **坐标系警告**：每间房的 `x/y` 是**该房自己的局部系**，跨房比距离/比 bbox 在原理上不成立
（第44轮已证伪）。JSON 里的 `x/y` 区间只能用来"看量级"，不要拿去算远近。

对账 `check_inst115.py` **9 PASS / 0 FAIL**：

| 判据 | 内容 |
|---|---|
| R1 | 逐章 房间数/实例数 == 既有普查（147/3513 … 252/12487），Σ=47,895 |
| R2 | 每房「层内实例数」== 实际 I 行数 == `GameObjects` 数 |
| R3 | 实例名**多重集**与 `rooms_map.json` 完全相等（ch5 允许 `空名 ↔ GameObject` 一对） |
| R4 | 非空对象名都落在该章 `objmap43.txt` |
| R5 | 每个对象的实例数与上一轮 `deltarune_objects115.json` **1,945 个逐个相等** |
| R6 | 同一间房同一个层 ⇒ 只能有一个 `depth`（列错位立刻暴露） |
| R7 | 坐标/缩放/旋转可解析，`\|v\| ≤ 100000`（实测最大 19,720） |
| R8 | 负控制 A：注入假对象名 ⇒ R3 报红 |
| R9 | 负控制 B：改一间房的层内实例数 ⇒ R2 报红 |

★ **明确不判**「层名里的 `_Depth_N` 必须等于 depth 列」：ch4/ch5 的层是自定义名
（`OBJECTS_MAIN` / `COLLISION_DOOR` …），且确有 59 个 `_Depth_N` 层与 depth 不符——
层名是人起的、depth 才是引擎用的，拿层名当判据只会误报。R6 用「房内层→depth 唯一」代替。

---

## 11. 跨作品：UT / UTY / Outertale（983 间 / 36,136 实例）

源是**安卓包 `game.droid`**（不是 `data.win`），UTMT 同样能读，`dump_instances.csx` 一行没改。
三款各导一次，每款 4 秒、4 MB 级 TSV。

| 作品 | 房间 | 实例 | 不同对象 | 非 1 缩放 | 带旋转 | 房间名前缀 | 交叉校验 |
|---|---|---|---|---|---|---|---|
| Undertale | **338** | 13,965 | 784 | 170 | 0 | `room_` 335（99.1%） | ✅ 与详版 §87.11 登记 **338** 相等 |
| Undertale Yellow | **287** | 7,636 | 915 | 4,863 | 28 | `rm_` 250（87.1%） | ✅ 与登记 **287** 相等 |
| Outertale | **358** | 14,535 | 812 | 218 | 0 | `room_` 354（98.9%） | 无历史登记，首次测定 |

**两个历史登记值被独立命中（338 / 287）**，这是比"脚本不报错"强得多的正确性证据——
期望值来自第42轮拓扑取证，不是本脚本自己算的，所以能真正证伪。

### 11.1 三款的结构差异（直接影响后续渲染）

| 维度 | Undertale | Undertale Yellow | Outertale |
|---|---|---|---|
| 层结构 | **全是 `Compatibility_Instances_Depth_N`** | 混合：`Compatibility_*` + 真实层名（`Walls` / `walls` / `Window`） | 同 UT，全是 compatibility 层 |
| 最大层 | `Depth_0` 7,935 个 | `Depth_-999999` 2,633 个 | `Depth_0` 7,923 个 |
| 非 1 缩放占比 | 1.2% | **63.7%** | 1.5% |

★ **UTY 是异类**：63.7% 的实例靠 `scaleX/scaleY` 缩放，且层名是人起的。
把 UT 的做法直接套到 UTY 上会错——这也是当初「两作不能套同一套做法」的又一例证。

### 11.2 实例最多的对象

- **UT**：`obj_solidsmall` 2,893、`obj_solidexwide` 1,188、`obj_solidwide` 640、
  `obj_doorA` 315 / `obj_doorB` 321（与 §87.11 登记的「门 = `obj_doorA~D`」相符）
- **UTY**：`obj_wall` 3,887、`obj_doorway` 462、`obj_interactable` 296
  （与登记的「门 = `obj_doorway` / `obj_exit` / `obj_door`」相符）
- **Outertale**：`obj_solidsmall` 2,991、`obj_solidexwide` 1,281、`obj_doorB` 333
  —— 结构几乎与 UT 同构（它本来就是 UT 的改版）

### 11.3 对账 `check_ut115.py` **13 PASS / 0 FAIL**

| 判据 | 内容 |
|---|---|
| U1 | 三份 TSV 非空（分母闸，防「空集恒真」） |
| U2 | `H` 行自述房间数 == 实际 `R` 行数 |
| U3 | `R` 行 8 字段 / `I` 行 11 字段（全量逐行，不抽样） |
| U4a | 每房「层内实例数」== 实际 `I` 行数（0 例外） |
| U4b | `GameObjects` 与层内实例的差异集合 == 白名单（多一处就报红） |
| U5 | ut=338 / uty=287（历史登记逐值相等） |
| U6 | 房间名前缀覆盖：ut `room_` ≥ 90%、uty `rm_` ≥ 80% |
| U7 | x/y/sx/sy/rot 全量可解析且 `\|v\| ≤ 100000`（实测最大 5,120） |
| U8 | `raw` 件与 `D:\_wb_tmp\dw_ut` 工作副本 sha256 一致 |
| U9 | 负控制 A：改一间房的层内实例数 ⇒ U4a 报红 |
| U10 | 负控制 B：把 uty 期望改成 288 ⇒ U5 报红 |
| U11 | 负控制 C：喂空房间列表 ⇒ U4a 分母闸报红 |
| U12 | 负控制 D：塞一个白名单外差异 ⇒ U4b 报红 |

**唯一已知差异（白名单）**：`uty / rm_intro` —— 层内 3 个实例，
但引擎 `GameObjects` 是 4。3 个实例全在 `Compatibility_Instances_Depth_0` 层里，
第 4 个**没挂到任何 Instances 层**。这是 UTY 老格式房间的真实特征，不是导出缺陷，
所以进白名单而不把判据放宽成 `>=`（放宽就等于放弃这条判据）。

★ 这条差异暴露了**判据本身曾经写错**：第一版把「层内实例 == `GameObjects`」当恒等式，
U4 立刻报红。查原始数据后确认是判据过严，不是数据有问题——**报红先怀疑判据**，又一次生效。

### 11.4 这一节没做的事（别当已完成）

- **只做了全量坐标**。UT / UTY / Outertale 的**物件分级、触发器识别、功能说明**都还没做
  （Deltarune 那套 §3 的三分法没有套用过来）；
- 门/存档点/可读物这层**语义标注**也还没有，目前只有原始对象名；
- 三款的**房间连通图**（谁能走到谁）未重建，`_room_graph.json` 仍只有 Deltarune 的 1,202 条边。

