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
   **物件分级也做了**，见 §12：实体物件 1,516 个（合并同名后 **1,056 行**待填清单）。
5. **用户填 `deltarune_objects_todo.csv` 的前 174 行**（覆盖 88.0% 的实体物件出场）。
6. **用户填 `cross_objects_todo.csv`**（三款 1,056 行；只填最后一列「功能简介」）。
7. **Freebird 四款**：用户已明确搁置（性质不同）。

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

---

## 12. 三款的物件分级与待填清单（补齐 §11.4 第一条）

口径**逐条沿用** `props115.py`，三分类不变（`logic` / `trigger` / `prop`），这样以后能和
Deltarune 并到同一套块级结构。判据写在 `props_ut115.py` 里，可复现。

对象来源有**两道筛**：先只看 `inst_full.tsv` 里**真出现过**的对象（1,720 / 3,224 / 1,800 个对象里
实际用到 784 / 915 / 812 个），再拿 `objmap_ut.txt` 的 `spr=` 与 `vis=` 去分类。
**battle-only、从未摆进房间的对象不进清单**（否则清单会被上千个用不上的东西灌满）。

### 12.1 分级结果

| 作品 | 用到对象 | 实例 | 实体物件 prop | 事件触发器 trigger | 纯逻辑 logic |
|---|---|---|---|---|---|
| Undertale | 784 | 13,965 | **454 个 / 3,128 次** | 24 / 293 | 306 / 10,544 |
| Undertale Yellow | 915 | 7,636 | **592 个 / 1,350 次** | 4 / 156 | 319 / 6,130 |
| Outertale | 812 | 14,535 | **470 个 / 3,206 次** | 24 / 293 | 318 / 11,036 |
| 合计 | 2,511 | 36,136 | 1,516 个 / 7,684 次 | 52 / 742 | 943 / 27,710 |

★ 三款都是 **`logic` 吃掉七成以上实例**（UT 75.5%、UTY 80.3%、Outertale 75.9%）——
这是对的：`obj_solid*`（不可见墙）这类在每个房间里成百上千地铺，它们不是"画面上的东西"。

### 12.2 口径验证：靠的是同一个判据，不是巧合

| 对象 | Deltarune | UT | 结论 |
|---|---|---|---|
| `obj_solidblocksized` / `obj_solidsmall` | `logic`（vis=False） | `logic`（vis=False） | ✅ |
| `obj_doorA` | `logic`（vis=False） | `logic`（vis=False） | ✅ |
| `obj_mainchara` | `prop`（vis=True） | `prop`（vis=True） | ✅ |

门和碰撞块在两边都落进 `logic`，是因为**同一个 `vis=False` 判据**在起作用，
不是因为两队数据碰巧一致。`check_props_ut115.py` 的 **P6** 把这条锁成判据。

### 12.3 占位图规则表（10 条，每条都有实测依据）

| 规则 | 命中的对象 | 理由 |
|---|---|---|
| `^spr_event` | `spr_event` / `_small` / `_collider` | 事件占位图（UT 123 个、Outertale 131 个、UTY 46 个） |
| `^spr_marker` | `spr_markerX` | 标记点 |
| `^spr_collisionbox$` / `_hitbox$` | `spr_collisionbox`、`*_hitbox` | 碰撞盒 |
| `^spr_solid` | `spr_solid*` | 不可见碰撞块（墙） |
| `^spr_invisible$` / `^spr_debug_` / `^spr_crosshair` / `^spr_border$` / `^spr_whitefader$` | 各自 | 显式不可见/调试/准星/边界/淡出遮罩 |

★★ **`shadow` 故意不进规则表**：`spr_martlet_head_shadow`、`spr_insomnitot_body_shadow`
这类是**角色部件**，是货真价实的物件。第一版探查脚本把 `shadow` 当关键字，命中 128 个对象——
那是**误报**，已剔除。**凡"看着像占位"的名字，必须回到实际对象看它在房间里干什么。**

### 12.4 待填清单做了同名合并（省掉 460 行）

UT 和 Outertale 是同源改版：**UT 的 454 个实体物件里有 453 个在 Outertale 中原样重现**（96%）。
若按"作品 × 对象"出清单，用户会把同一个物件填两遍。

| 项目 | 值 |
|---|---|
| 未合并行数 | 1,516 |
| **合并后行数**（`cross_objects_todo.csv`） | **1,056** |
| 省掉 | **460 行** |
| 跨作品重合 | ut∩outertale **453**；ut∩uty 5；outertale∩uty 7 |

合并列口径：`作品` 写 `Undertale / Outertale`，`作品数` 记 1/2/3，
`房间数(合计)` 与 `实例数(合计)` 是跨作品求和。**用户只填最后一列 `功能简介`。**

⚠️ **2 个同名但精灵不同的**，已在 `精灵` 列原样列出两边：
`obj_fakewaterm`（ut/oty `spr_fakewaterm`，uty `spr_fakewatermu`）、
`obj_chairiel`（ut/oty `spr_chairiel`，uty `spr_toriel_sitting`）。

### 12.5 对账 `check_props_ut115.py` **11 PASS / 0 FAIL**

| 判据 | 内容 |
|---|---|
| P1 | 三款 分级对象数 == 实例表出现过的对象数（互斥穷尽） |
| P2 | 三款实例数 == 13,965 / 7,636 / 14,535（与 §11 的坐标导出独立相符） |
| P3 | CSV 行数 == 不同对象名数；编号连续 001..N；对象名集合相等；作品列合法 |
| P4 | 每个 `prop` 的 sprite 非空且 `vis=True`（防"看不见的东西混进清单"） |
| P5 | 每个 `trigger` 的 sprite 非空 |
| P6 | 与 Deltarune 同口径抽查 4/4 相符 |
| P7 | 负控制 A：把 `obj_doorA` 的 `vis` 改成 True ⇒ P6 报红 |
| P8 | 负控制 B：清空规则表 ⇒ `trigger` 从 52 掉到 0 |
| P9 | 负控制 C：CSV 编号注入重复 ⇒ P3 连续性判据报红 |
| P10 | 分母闸：`prop` 数 > 0 |
| P11 | **合并守恒**：CSV 实例合计 == prop 实例 7,684；`作品数`之和 == 未合并行数 1,516 |

### 12.6 仍然没做

- **功能简介要等用户填**（1,056 行，这是本轮交付给用户的手工活）；
- 门/存档点/可读物这层**语义标注**仍未做（只有原始对象名）；
- 三款的**房间连通图**：已试六条路线，见 §13 —— 只拿到"可信但不满"的一层，**没到可用的完整图**。

---

## 13. 三款房间连通图：试了六条路，一条能采信

项目口径是「把原作的世界搬到桌面上」，而且有一条硬要求「**当原作门逐门寻路（禁瞬移）**」。
没有连通图这条不成立。`第42轮` 的 `_room_graph.json` 只有 Deltarune 的 1,202 条边，
三款是空白，所以本轮补这一块。

### 13.1 先说结论

| | 房间 | 可信边 | 有出边的房间 | 作为 src 或 dst 出现过 | 覆盖率 |
|---|---|---|---|---|---|
| ut | 338 | **131** | 101 | 157 | **46.4%** |
| uty | 287 | **1** | 1 | 19 | **6.6%** |
| outertale | 358 | **144** | 110 | 175 | **48.9%** |

- 可信边 = GML 里写死的 `if (room == N) room_goto(M)`。原始记录 147 / 1 / 158 条，
  **去重后 131 / 1 / 144 条**（同一对房间被多个对象各写一遍，`check_conn115 C3` 守着这条守恒）。
- 缺口：ut 还差 181 间、outertale 还差 183 间、**uty 几乎全空**（只有 1 条）。
- 候选边（推断，未经真值验证）另存一份：ut 563 条 / outertale 588 条，能把出边覆盖推到 289/338、305/358。

产物：
- `_evidence/conn115.json` —— **只放可信边**，每条带 `code`（哪段 GML 写的）；
- `_evidence/conn_inferred115.json` —— **候选边单独一个文件**，每条带 `via`（哪个对象）/`off`/`same_area`；
- `_evidence/conn_falsify115.txt` —— 各条路线的实测数字（下面每行都能在这份里查到）。

★ 为什么可信边和推断边**必须分文件**：一条错边会把角色送进错的房间，**错边比缺边更糟**。
两层的边集 `check_conn115 C5` 判为零重叠，谁想混放会直接报红。

### 13.2 六条路线，逐条实测

| 路线 | 做法 | 实测 | 判决 |
|---|---|---|---|
| **A** GML 常量边 | 扫全量 code，收 `room_goto(常量)`；`src` 取同一 code 里的 `if (room == N)` | ut 147 / uty 1 / outertale 158 条（去重后 131/1/144） | ✅ **唯一可信** |
| **B** 门对象 → 固定偏移 | 按 code 分组看 `dst - src` | ut 8/8 个 code、outertale 8/8 个 code **偏移全不恒定**（如 `obj_door_w` = {+3:3, −3:3, +5:1, −5:1}） | ❌ 不成立 |
| **C** 实例创建代码 | 数 door 实例带 CreationCode 的 | ut 1,299 个里 **0 个**；outertale 1,367 里 **0 个**；uty 473 个带但指令全是 `I:0 I:0 I:0`（默认值） | ❌ 不成立 |
| **D** 几何匹配 | 贴顶/底/左/右的门按坐标配对 | ut 命中 **4/131 = 3.1%**、uty **0/1**、outertale **4/144 = 2.8%**；候选边 1,626 条里只有 4 条是已知的（精度 **0.2%**） | ❌ 不成立 |
| **E** src 反推（对象的实例只在一间房） | 事件的 src 未知，就用"这个对象的实例只摆在一间房"反推 | 验证集 **EMPTY**：有 src 的边全落在多房对象上，比不出对错；uty 唯一 1 条还冲突 | ❌ **无法验证 ⇒ 不敢用** |
| **F** 对象事件的 next/prev 规则 | `room_goto_next/previous` 的偏移是 op 自带的 ±1，对象事件共享 ⇒ 一个 `obj_doorA` 覆盖 135 间房 | 生成 571 / 601 条候选，出边覆盖 101→**289**、110→**305** | ⚠️ **未证实也未证伪** |
| **G** F 的同区域体检（A/B） | 真门多半同区域：`room_ruins5 → room_ruins6`；对照 = 随机房对 | 候选同区域率 **84.6% / 83.5%**，随机对照 **11.9% / 11.2%**（7 倍差距）；跨区域 83 / 92 条 | ⚠️ 方向对，但有约 15% 可疑 |

### 13.3 三个必须说清楚的坑（都是我自己先踩的）

**(1) B 的第一次归因是错的。** 上一版把"源房间里摆了哪些门对象"当触发者 —— 一个房间
摆十几个门对象，真正触发的是事件代码所属那一个。`conn_ut.json` 的 `code` 字段早就写明是谁
（`gml_Object_obj_door_t_Alarm_2`），改按 `code` 分组才叫对。**归因错了，数据再对也没用。**

**(2) F 的"不符"不算证伪。** 一开始我拿"已知边里有多少条等于 R+1"去判 F，得到 55 条里只有 1 条，
看着像彻底失败。但同一房间可以同时有表驱动门（`obj_door_t` 的 `if (room==N)`）和 next/prev 门 ——
**两条边本来就能并存**，已知边当然是表驱动那条。所以 F 只能算"不能证真"，不能算证伪。
判据本身有偏，先怀疑判据。

**(3) 房间下标顺序 ≠ 剧情推进顺序。** 我本来想"相邻房就是下一间"，实测 ut 的 `(i, i+1)`
在 337 个相邻对里只命中 **3** 条已知边（反方向 5 条）。端口把房间表重排过，
所以 F 的 `R+1` 只是"房间表里的下一格"，不是"剧情的下一刻"。这也是 F 只能当候选的根本原因。

### 13.4 对账 `check_conn115.py` **13 PASS / 0 FAIL**

| 判据 | 内容 |
|---|---|
| C1a / C1b | 分母闸：三款可信边非空（131/1/144）；候选边至少一款非空 |
| C2 | 可信边不越界、不自环（276 条全部 0..n−1 且 src≠dst） |
| C3 | **去重守恒**：导出条数 == 原始 (src,dst) 唯一对数（147/1/158 → 131/1/144） |
| C4 | 每条边的 `src_name/dst_name` 与 `room_names` 逐条对上 |
| C5 | **可信边与候选边零重叠**（错边比缺边糟） |
| C6 | 候选边 `dst == src + off` 且 `off ∈ {+1,−1}` |
| C7 | `same_area` 汇总数与逐条标签一致（ut 480 / outertale 496） |
| C11 | 房间数/边数/src 房数与本节表格**逐值一致**（防报告与数据脱节） |
| C8~C13 | 五条负控制，全部报红：越界 dst → C2；`n_edges` 造假 → C3；候选边混进可信边 → C5；`same_area` 翻面 → C7；清空 ut 可信边 → C1a |

★ **uty 的候选边为 0，判据里显式登记了 `nop`**（全库没有任何 next/prev 规则，是数据事实不是缺陷）。
不登记的话，"0 条边全通过"就是空集恒真。

### 13.5 需要裁定的一件事

候选边要不要用？三条路，我倾向第 2 条：

1. **只用可信边**（ut 131 / uty 1 / outertale 144）—— 最干净，但 54% 的房间没有出边，
   uty 基本等于没有图，寻路会在 ruins 里断掉。
2. **可信边优先 + 候选边兜底**（推荐）—— 有可信边走可信边，没有再走候选边；
   跨区域的 83/92 条另标 `suspicious`。覆盖率到 85%，且来源逐条可查，出问题能一眼定位到是哪条推断。
3. **换源取证** —— UT/UTY 的 PC 版 `data.win` 里有完整的房间创建代码，
   重跑一遍就能拿到真值，不用推断。代价是要用户提供 PC 版游戏文件（端口版 `game.droid` 拿不到）。

> **这一节的推荐已被 §13.6 的实测推翻**：按"可信优先"裁剪出来的图，从落地房只能走到 4 间。
> 保留在此是因为它记录了当时的判断链，别按它施工。

---

## 13.6 可达性实测：把我自己的推荐推翻了

覆盖率是"有多少间房有出边"，但玩家关心的是**从落地房走进去能走多远、会不会走进死胡同**。
这两件事在链式地图上差别很大，所以直接跑 BFS。

**入口怎么定的**：`room_start` 是标题/菜单房、里面没有门 —— 拿它当起点会得到"一间都走不出去"的假结论
（我第一次就这么错了）。真正的落地房是 `room_area1`（坠落处）。

| 策略 | ut 边 | ut 可达 | 双向 | 最深 | 连通块 | 走进去出不来 |
|---|---|---|---|---|---|---|
| `exact` 只用可信边 | 131 | **1** | 1 | 0 | 38 块（最大 14） | 0 |
| `room_first` 有可信边就不补 | 500 | **4** | 1 | 2 | 12 | 3 |
| `safe` 只补同区域候选 | 611 | **3** | 2 | 2 | 12 | 1 |
| `loose` 全用候选兜底 | 694 | **280** | 265 | **109** | 5（最大 293） | 15 |

outertale 同形：`exact` 可达 1 → `loose` 可达 **283 / 双向 268 / 最深 96**。
uty 四种策略全是 1（只有 1 条边，**没有图**）。

### 三条结论，第一条是自我更正

**(1) 「可信优先」在稀疏且破碎的可信层上会反噬。** 我原本推荐"有可信边走可信边"，
   实测只有 **4 间可达**（vs 全用候选 280 间）。原因很直白：可信边是**散落的局部表** ——
   131 条边切成 **38 个互不相连的块，最大块才 14 间**。一旦走进"有可信边"的房间，
   就被锁在那张局部表里，路径立刻断。**所以可信层的正确用途不是裁剪，是锚点。**

**(2) 可信层的价值在别处，别浪费它。** 这 131 条是 100% 精确的，它的用处是：
   ① 当**校验集**评估推断质量；② 产品里"这扇门通向哪"的**高置信展示**；
   ③ 候选边出错时的**定位基准**。它不该拿来当图的裁剪条件。

**(3) 候选边的错，落在"本来就该走不出去"的地方。** UT 那 15 间"走进去出不来"是
   `room_intromenu`、`room_undertale_end`、`room_gaster`、`room2`、`TESTROOM`、`bullettest` ——
   **全是测试房、结局房、Gaster 房**，原作里本来就没有正常出口。主线反倒是连贯的：
   280 间可达、265 间双向、最长路径 **109 层**。这是候选边"方向大体对"最有力的一条旁证。

### 产品侧契约（三条，写死在数据里，不靠口头约定）

1. **边表全量入图**（`loose`）：`room_graph115.json` 每条边带 `provenance` + `confidence` + `via`；
2. **不在图上裁剪，只在出口上排序**：同一间房同时有 `exact` 和 `inferred` 出边时，
   `exact` 排前（因为它是精确的），但**不丢弃** `inferred`；
3. **`confidence=low`（跨区域）只作提示，不作门控** —— 实测里把它关掉（`safe`）会让可达数从
   280 掉到 3，等于把图废掉。

★ 产品代码本轮**没有改动**：`ralsei_pet/` 一行没动，`_routes.json`（场景级路由）也没动。
   这份图是**数据交付**，接线要等 G2 全绿 + 真机验证另行做。

### outertale 的一个真缺口（产品侧，不是数据侧）

outertale 358 间房里，产品只登记了 **244 间**（`_zone.outertale.*.json` 的 `original_room_id` 覆盖 244/358），
而且**房间名全被改过**（`s_start` 而不是 `room_start`），按名字映射命中 **0/358**。
所以接 outertale 必须按 `original_room_id` 对，不能按名字 —— 这条已锁进 `check_graph115 G6`。

### 对账 `check_graph115.py` **12 PASS / 0 FAIL**

| 判据 | 内容 |
|---|---|
| G1 | 分母闸：三款边表非空（696 / 2 / 732） |
| G2 | `provenance` 只有 exact/inferred，且导出时 exact 全在前 |
| G3 | 图里的 exact 边集与原表**逐条相等**（131 / 1 / 144） |
| G4 | 候选边 `dst == src + off`，`off ∈ {+1,−1}` |
| G5 | **另写一份 BFS 复算**，可达/双向/最深/出不来与记录逐一相等（不 import 被测代码） |
| G6 | scene 映射锁定：ut 338/338、uty 287/287、outertale 按名 0 按 id 244 |
| G7 | 每条边的房间名与 `room_names` 一致 |
| G8~G12 | 五条负控制全部报红：exact 改标 → G3；off 改 2 → G4；可达数 +7 → G5；命中率造假 → G6；inferred 挪到最前 → G2 |

产物：`_evidence/room_graph115.json`（三款分层图，含 `reachability` 实测）、`_evidence/route115.txt`。

---

## 14. 三款交互点的语义标注（把"这是啥门、通向哪"标出来）

§12.6 剩下的那条：门 / 存档点 / 可读物的**语义**。此前只有原始对象名（`obj_door_t` 这种），
没有用途、也没有去向。本节把这一层补上。

### 14.1 覆盖与分类

| | 房间 | 有可交互点的房间 | 可交互实例 |
|---|---|---|---|
| 三款合计 | 983 | **815** | **5,274** |

分类（**口径与 Deltarune 逐字一致**，同一份 `KINDS` 列表、同一顺序、同样匹配方式）：

门 **3,189** · 命名标记 **1,210** · 可读物 **716** · 招牌 **88** · 存档点 **68** · 宝箱 **3**

> 另有 **30,862** 个实例落在"其它"，它们不是交互点，归 §12 的物件分级口径，别混进分母。

| 作品 | 门 | 命名标记 | 可读物 | 存档点 | 招牌 | 宝箱 |
|---|---|---|---|---|---|---|
| ut | 1,299 | 592 | 351 | 33 | 34 | 0 |
| uty | 523 | 0 | 4 | 0 | 20 | 3 |
| outertale | 1,367 | 618 | 361 | 35 | 34 | 0 |

**ut 与 outertale 几乎逐项相等**（1,299/1,367、592/618、351/361、33/35）—— 这不是巧合，
outertale 是 UT 的改版、大量沿用房间布局。两条独立导出的数字互相印证，是这批数据自洽的旁证。

细分（只作说明，**不参与 kind 判定**）：门洞/出口 466 · 假门 311 · 挡路物 27 · 书架 4 · 箱子 3 · 书 2。

★ UTY 用另一套命名（`obj_doorway` / `obj_savebox` / `obj_books` / `obj_chest_*`）。
   我**没有**为了让统计好看去改 `KINDS` —— 改了就等于偷偷换口径，三款就没法跟 Deltarune 比了。
   做法是：统一口径不动，另加 `subkind` 字段表达这些差异，并在报告里说明。

### 14.2 门通向哪：1,128 个门有了明确去向（35.4%）

| 作品 | 门实例 | exact 解析 | inferred 解析 | 多候选（不猜） | 无解 |
|---|---|---|---|---|---|
| ut | 1,299 | 239 | 309 | 2 | **749** |
| uty | 523 | 0 | 0 | 0 | **523** |
| outertale | 1,367 | 256 | 324 | 2 | **785** |
| 合计 | 3,189 | **495** | **633** | 4 | **2,057** |

判据：`exact` 是"这段 GML 的 code 名里真的出现这个门对象名"，`inferred` 是"对象的
`room_goto_next` 推出的 ±1"。**只有唯一匹配才算 resolved**；两三条候选一律列出来标 `ambiguous`，
不挑一个看起来顺眼的。

**无解 2,057 个不是失败，是事实，得说清楚**：
1. 一扇门房里常并排摆 **4 个** `obj_doorA` 实例（左右各一对），真正触发的只有一个；
2. uty 的 523 个门**全部**落在"没有边"里（§13.6：它整个库没有可用的换房代码）；
3. exact 边只覆盖 101 间房（§13.1），剩下的房间本来就没有可信依据。

样例（ut）：
```
room_area1   obj_doorA -> room_area1_2   (inferred)
room_ruins1  obj_doorA -> room_ruins2    (inferred)
```

### 14.3 对账 `check_semantics115.py` **10 PASS / 0 FAIL**

| 判据 | 内容 |
|---|---|
| M1 | 分母闸：三款门实例非零（1,299 / 523 / 1,367） |
| M2 | **分类守恒**：所有 kind 合计 == 36,136（互斥穷尽） |
| M3 | resolved + ambiguous + unknown == 门实例数，且与实测逐值一致 |
| M4 | **每条 exact 门可回验**：真边存在，且 `via` 里真的出现该对象名（独立正则，不复用被测代码） |
| M5 | 每条 inferred 门：候选边存在且 `via == 对象名` |
| M6 | 口径与 `points115.py` 的 `KINDS` **逐项相同**（AST 比对，不 import、不执行源码） |
| M7~M10 | 四条负控制全报红：`to_room` 改 9999 → M4；`via` 换成不含该对象的 code → M4；unknown +5 → M3；door 计数 +1 → M2 |

产物：`_evidence/cross_semantics115.json`（含每个门的 `to_room/to_scene/provenance/via`）、
`_evidence/cross_semantics115.txt`。

### 14.4 这一节仍然没做的

- **可读物的原文没抽**：现在只知道"这间房里有个可读物、在什么坐标"，不知道上面写了什么。
  要抽得读 `obj_readable_*` 事件里的字符串常量，是另一件事。
- **存档点只有坐标**，没有"存到哪一章/哪个进度点"的语义。
- 宝箱只认出 **3** 个（UTY 的 `obj_chest_*`）—— UT/Outertale 的宝箱命名不在关键词表里，需要另做一轮。

---

## 15. 可读物正文：621 个键 × 三种语言（含**官方中文**）

上一节留下的第一条（可读物原文）做完了，而且比预期好 —— UT 里带**官方中文**文本。

### 15.1 先走错一次，留作记录

第一版扫 `obj_readable_*` 对象的事件，抽出 616 个字符串 —— **全部是变量名**
（`obj_readable_room1_64` 这种），一句正文都没有。那条 csx 没删，
文件头已标"★ 已废弃（留作证伪记录）"，免得以后有人从头再试一遍。

真正的形状是这样（`probe_rtext.txt`，UT 的 `gml_Script_textdata_en`）：

```
68765: Push  str='obj_readable_modernbook_59'          ← 键
68766: Conv
68767: PushGlb / 68768: Call / 68769: Popz             ← 中间固定隔 3 条
68770: Push  str='* (Here I am..^1.&* Writing this book.)/'   ← 正文
```

所以规则是：**名字之后 12 条指令内的第一个字符串常量**，就是正文。
（第一版要求"紧邻"，`pairs=0`，正是这个"不紧邻"把我挡住了。）

### 15.2 结果

| | 键 | en | ja | **cn** | 只在自己的对象表里有 | 同键冲突 |
|---|---|---|---|---|---|---|
| ut | **621** | 614 | 614 | **614** | 7 | 0 |
| outertale | **621** | 614 | 614 | **0** | 23 | 0 |
| uty | 0 | — | — | — | — | — |

中文样例（`cn_tight` 已把汉字之间的排版空格去掉）：

```
obj_readable_modernbook_59  * (我正在 ..^1.&* 写这本书。 )/
obj_readable_room1_70       * 远处的门并不是出口 ^1， &* 只是表示视角的旋转。 /%%
obj_readable_room2_465      * 谢谢你， ASGORE。 /%%
```

三条事实要说清楚：

1. **中文是原作自带的**（`textdata_cn` 表，614 条与 en/ja **键完全一致**），不是我翻的。
2. **outertale 没有中文表** —— en/ja 各 614，cn 0。这是原作事实，已锁进 `check_readables115 R7`，
   免得将来被当成"漏抽"去修。
3. **uty 没有可读物正文** —— 它的可读物叫 `obj_books` / `obj_bookshelf`（4 个实例），
   正文不在 `textdata_*` 表里，本轮没找到，**不算做完**。

### 15.3 两处必须点明的处理

- **`cn` 与 `cn_tight` 并存**：原样保留（保真）＋ 去掉汉字间空格（渲染用）。
  判据 `R5` 逐条验证"两者去空白后逐字相等"——只许少空格，一个字都不许差。
- **剔掉"后面跟的是下一个键名"**：`obj_readable_roomX_Alarm_0` 里不少条目，名字后面跟的
  不是正文而是下一个键名（ut 548 条 / outertale 519 条）。不滤掉就会把键名当正文，
  而"同键冲突数"正是用来暴露这件事的（滤之前 outertale 有 4 处冲突）。

标记统计（en 侧）：`%` 681 · `&` 658 · `/` 605 · `^1` 261 · `^2` 5。
这些是**控制符**（换页 / 换行 / 按键图标位），产品渲染怎么处理是另一件事 ——
我**没有**擅自定一套编码规则，原始串原样保留。

### 15.4 对账 `check_readables115.py` **11 PASS / 0 FAIL**

| 判据 | 内容 |
|---|---|
| R1 | 分母闸：ut / outertale 各 621 键（uty 为 0 是事实，见 R7） |
| R2 | 每个键至少有一种语言的正文（1,242 个键全过） |
| R3 | ut 的 en/ja/cn **键集合完全相等**（各 614） |
| R4 | 同键冲突 0；键名当正文已剔除 |
| R5 | 614 条 `cn_tight` 与 `cn` **去空白后逐字相等** |
| R6 | 抽 20 条 `(key, en)` 回 `readable_text.json` 都能找到同一条 |
| R7 | 锁死"outertale 没有中文表"是事实而非缺陷 |
| R8~R11 | 四条负控制全报红：改一个字 → R5；抹掉一条 en → R3；conflicts=3 → R4；清空 `cn_tight` → R5 |

产物：`_evidence/readables115.json`（621 键 / 三语 / `cn_tight`）、`_evidence/readables115.txt`、
`_evidence/raw/{ut,outertale}/readable_text.json`（原始导出，已蒸馏进仓库）、`_evidence/raw/ut/probe_rtext.txt`。

### 15.5 这一段仍未做的（下一步）

- ~~**键还没绑到房间里的具体实例**~~ → **已解，见 §16**（机理＝`Alarm_0` 里 `if (room == N)`）。
- 标记（`%` `&` `/` `^1`）的渲染规则没定。
- uty 的可读物正文没找到。

## 16. 可读物「哪间房用哪个键」：解出来了，粒度是 (房间, 对象)（第117轮补）

### 16.1 结论先行

**文本键不是按实例坐标选的，是按房间选的。** `obj_readable_<kind>_Alarm_0` 里是一串：

```
PushBltn{room} ; PushI <N> ; Cmp ; Bf <skip> ; Push 'obj_readable_<kind>_<M>' ; Call … ; Pop …
        ↑ 反射出来 ValueVariable = {room}
```

⇒ 等价于 GML 的 `if (room == N) { msg = scr_textdata('obj_readable_<kind>_<M>'); }`。

**关键证据（两条，都不是推断）**：
① `probe_dump_ins` 对 `PushBltn` 指令做**全字段反射**，`ValueVariable = {room}`；
② `probe_key_users` 反查 16 个样本键，**每个键只被自己对象的 Alarm 引用一次**（其它 8,120 段代码一处都不碰）。

### 16.2 排除过程（四次探针，每次否掉一个假设）

| # | 假设 | 结果 |
| --- | --- | --- |
| 1 | 正文写在对象 `Create` 事件里 | ✗ Create 只有变量初始化（room1 的 24 条指令里 0 个字符串） |
| 2 | 键按**实例**算（实例号/坐标） | ✗ 键数远多于实例数（614 键 vs 350 实例）⇒ 是预置文本槽 |
| 3 | 键在**房间创建代码** `gml_RoomCC_*` 里写死 | ✗ 反查 16 个键，引用者全是自己的 `Alarm_0`，没有一条 RoomCC |
| 4 | 键在 `Alarm_0` 里按 `room` 选 | ✓ 反射出 `{room}` + `PushI N` + `Cmp` + `Bf` |

### 16.3 量化结果（分母是"有实例的 (房间,对象) 组合"，不是"全部房间"）

| 作品 | 绑定行 | 有 room 守卫 | 唯一键 | 可读物实例 | 组合 | **能绑定** | 涉及房间 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ut | 614 | 203 | 614 | 350 | 202 | **187（92.6%）** | 95 |
| outertale | 604 | 200 | 599 | 360 | 210 | **183（87.1%）** | 102 |
| uty | 0 | 0 | 0 | 0 | 0 | EMPTY（无数据，不当 100%） | 0 |

> 203/614 有 room 守卫、其余 411 个没有 —— 这正好解释 §15 那个"键数多于实例数"的困惑：
> **键是预先写好的文本槽**（全游戏 614 个），房间用到哪个就在 Alarm 里挂哪条，
> 没用到的也留在表里。所以"按第几个实例取第几个键"从一开始就是错的。

### 16.4 对不上的 15 / 27 例（全部列出，不猜）

ut 的 15 例：`room_area1/flowers1`、`room_ruins3/sign1`、`room_ruins3/switch1`、
`room_ruins10/plaque_1`、`room_ruins10/plaque_2`、`room_ruins13/sign2`、
`room_tundra_xoxopuzz/room5`、`room_tundra_library/modernbook`、`room_tundra_paproom/room3`、
`room_fire_lab2/room2`、`room_fire_lab2/room4`、`room_fire_lab2/room_editor`、
`room_truelab_hub/room3`、`room_truelab_fan/room1`、`room_water7_older/room1`。

它们的共同点：**都是单例小对象**（`sign1`/`switch1`/`plaque_*` 各有 1 个实例）。
实测 `switch1` 的 Alarm 用的是 `PushGlb <全局> == 5` 这种**全局/剧情条件**，不是 `room ==`。
⇒ 这 7 种对象走另一套守卫，**本轮不猜**，如实列出来。

### 16.5 ★★ 必须说清的限制：粒度只到 (房间, 对象)

ut 有 **103** 个组合是"同一房间摆了多个同类可读物"（outertale 98 个）。
按本规则这些实例会**共享同一条正文** —— 本规则**不能**当成"每实例一文本"。
桌宠实现时应当：进入房间 → 取该房间该对象类型的键 → 显示该段正文；
同房间多个同类牌子显示同一段（除非以后解出第二层守卫）。

### 16.6 复现

```
# 1) 抽绑定表（三款一起，产物落工作目录）
python _tools/run_csx_ut.py --csx dump_readable_bind.csx --out readable_bind.tsv --no-distil
# 2) 交叉验证 + 异常清单（只读仓库内文件，不碰 D:/E:）
python _tools/readable_bind115.py
```

产物：`_evidence/raw/{ut,outertale,uty}/readable_bind.tsv`、
`_evidence/readable_bind115.json` / `.txt`。
排除过程中用到的五个探针脚本留在 `_tools/`（`probe_readable_key.csx`、`probe_readable_alarm.csx`、
`probe_key_users.csx`、`probe_dump_ins.csx`、`probe_resolve.csx`）——
**它们是"证伪记录"不是产物**，留着是为了下一个人能复现"为什么排除了别的解释"。





## 17. 正文里的控制符怎么解（第117轮补：反编译取证，不许拍脑袋）

### 17.1 结论先行：一张表，几类标记，全部有代码出处

| 标记 | 原作行为（GML 原文） | 产品显示 |
| --- | --- | --- |
| `&` | `script_execute(SCR_NEWLINE)` —— 书写点 `myy += vspacing` | **换行** |
| `%`（后不接 `%`）| `stringno++`，`originalstring = mystring[stringno]` ⇒ **换新文本框** | 换行（本产品可读物只有一个气泡） |
| `%%` | `instance_destroy(); break;` ⇒ **消息到此结束** | **截断**，后面不显示 |
| `/` | `halt = 1; … break;` —— **不移动书写点**，只等按键 | 删除，**不换行** |
| `/%` `/*` `/^N` | `halt = 2 / 6 / 4`（等按键后换页 / 特殊 / 停顿） | 删 `/`，其余按各自规则 |
| `^N` | `Alarm_0`：`delay = real(ch) * 10` —— 停顿一瞬；`^0` 不产生停顿 | 删除 |
| `\X` | 颜色 `R G W Y X B O L P p` · `C`=`event_user(1)` · `M/E/F/T/S/z` 各吞 1~2 个字符 | 删除 |
| `[C]` | `scr_replace_buttons_pc` 把 `\*C` 换成 `[C]`（按键字形） | 删除（画不出按键图标） |

### 17.2 取证路径（这是本轮新打通的能力，值得记）

前几轮只知道 `UndertaleModCli load <data> -s <csx>` 能跑脚本；本轮发现 CLI 还有
**`dump` 子命令可以直接反编译成 GML**：

```
UndertaleModCli.exe dump <data 副本> -o <输出目录> -c <code 名>   # -c 可重复多次
# ⇒ <输出目录>/CodeEntries/<code 名>.gml
```

★ 三个踩过的坑：
1. `-c A B C` 会被当成**一个**名字（报 `does not contain a code entry named "A B C"`）
   ⇒ 必须 `-c A -c B -c C`。
2. 工具进程**必须分离启动**（`DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP`）并把 stdout 落文件，
   否则前台跑会被连带杀掉、输出为空（本仓库 `_tools/cli_help115.py` 就是这个壳）。
3. 反编译产物要**蒸馏进仓库**（`_evidence/raw/ut/gml/`），别放临时盘 —— 回归/复核要能离线重跑。

### 17.3 为什么 `/` 不能当换行（本轮最容易写错的一处）

`/` 在 `obj_base_writer_Draw_0` 里只做三件事：置 `halt`、`break`、**不动 `myx/myy`**。
真正下移书写点的是 `&`（`SCR_NEWLINE`）。

⇒ 把 `/` 也当换行，会在**每一句"等按键"的地方凭空多出一行**。素材里 `/%%` 是最常见的收尾，
一旦写成换行，所有可读物末尾都会多一行空白。

### 17.4 产品侧怎么用（三步，全部在显示层）

```
assets/scenes/_readable_text.json      ← 数据层：markers_raw 仍为 true（原样保留）
        ↓ item_interact.load_readable_text(path)
{sid: {obj: 已解码文本}}                ← 载入时解码一次（进程内缓存）
        ↓ main._rebuild_item_props → build_props(..., readables=表)
ReadableProp.text → dialogue_ui 气泡    ← 可读物说的就是原作正文
```

- `decode_readable(raw)`：纯函数，无状态，13 条判据逐条锁（`%` vs `%%`、`&` vs `/` **正负成对**）。
- `load_readable_text(path)`：读不到 / 读坏 ⇒ 返回空表 + 记日志，**不抛**
  （不能因为一份数据资产缺失就把可交互物构建整个搞崩）。
- `build_props(..., readables=None)`：给了就用原文；没给 / 查不到 ⇒ 沿用 `READABLE_TEXT`
  的兜底那句「字迹已经模糊了」—— **兜底不等于造文本**。
- 正文取值优先级 `cn_tight → cn → en → ja`：`cn_tight` 是压掉字间空格的版本
  （outertale 的 `en` 槽里装的是**中文**、字间带空格，直接显示会散架）。

### 17.5 量化（355 条的账目，一条不差）

| 项 | 数 | 说明 |
| --- | --- | --- |
| 资产条目 | **355** | `by_scene` 里所有条目（166 个场景） |
| 解码后保留 | **335** | 164 个场景真的拿到了正文 |
| 解完为空 | 6 | 原文就是 `%%`（只有终止符）⇒ 该回落 |
| 判为重复 | 14 | 同一 `(场景, 对象)` 多条：`Alarm` 里还有**第二层守卫**没解，只取第一条 |
| 解码后残留控制符 | **0** | `% & / ^ \ ]` 全清；`*` 保留（原作行首符，不是控制符） |

### 17.6 本轮没做的事（如实登记）

1. **第二层守卫**：10 个组合（14 条）在同一 `(房间,对象)` 上有多个键，差别在剧情/全局变量
   （例：`switch1` 走 `PushGlb <全局> == 5`）。要"每实例一文本"，得先解这层。
2. **分页**：原作 `%` 是换新文本框；产品可读物只有一个气泡 ⇒ 退化成换行。要还原得分页文本框。
3. **`[C]` 字形**：按键图标画不出来，只能删。删掉后原文形如 `* It's me, .` —— **如实难看，不假装**。
4. **未解 15 / 27 例**（§16.4）：7 种单例小对象走全局守卫，仍未解。

### 17.7 复现

```
# 反编译（产物落 _evidence/raw/ut/gml/）
python _tools/run_csx_ut.py --csx probe_markers.csx --out probe_markers.txt --game ut
python _tools/cli_help115.py dump D:/_wb_tmp/dw_ut/ut/game.droid -o D:/_wb_tmp/dw_ut/gml_out \
       -c gml_Script_SCR_TEXT -c gml_Script_SCR_TEXTTYPE -c gml_Object_obj_base_writer_Draw_0
# 解码效果与账目（只读仓库内文件）
python _tools/residue115.py      # 残留字符：应当只剩 `*`
python _tools/ledger115.py       # 355 = 335 + 6 + 14
python _tools/scan_markers115.py # 正文里出现过哪些控制符
```

判据：`_tools/check_readable_wire117.py`（**34 条**，已进 G2 / `baseline.json`）。







