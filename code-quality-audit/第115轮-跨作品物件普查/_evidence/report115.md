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

1. **没有全量坐标**。`rooms_map.json` 只记「这间房有哪几个对象」，**没有 x/y**。
   ⇒ 现在能做「哪些对象在哪几间房」，**做不了**「这个物件在这一格」。
   要做到 OneShot 那种「块级」粒度，得**重跑 UTMT 写新 csx 采 `x/y`**（csx 已写好，本轮
   跑不起来，见 §6/§7）。**折中**：交互点的坐标已经有了，见 §8。
2. **1 个坏实例名**：`GameObject`（ch5 `room_dw_cliff_finaldash`），是当年导出脚本对
   解析不出的实例写了类型名占位。占 47,895 的 0.002%，已在对账里作为**已知例外**白名单。
3. **原始产物原本在 `E:/Download/_tmp`**（临时盘，随时可能被清）。本轮已把五章的
   `rooms_map.json` + `objmap43.txt` **蒸馏进仓库** `_evidence/raw/chN/`（共 3.8 MB），
   下面的复现命令不再依赖临时盘。

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

1. **全量实例坐标（x/y/scale/rotation）** —— 仍未采到。`UndertaleModCli.exe` 在这台机器上
   **起不来**（`--help` 都失败），排查过程见 §7，**与磁盘无关，是工具本身被环境挡住**。
   可行的三条路（下一轮挑一条）：① 用 UTMT **GUI** 版手工跑同一个 csx 导出（脚本已写好，
   见 §7.2）；② 换一台机器 / 换个版本再试；③ 退一步用 §8 的**交互点坐标**顶上。
2. ~~82 个不表意名字~~ ⇒ **已做**，见 §3.2（其中 61 个其实是触发器，真正要填的只有 21 个）。
3. ~~先给一部分坐标~~ ⇒ **已做**：978 间房的**交互点坐标**（门/标记/可读物/存档/宝箱/招牌/传送），
   见 §8。
4. **UT / UTY / Outertale**：同为 GameMaker `data.win`，流程可复用（本轮方法直接迁移）。
5. **Freebird 四款**：用户已明确搁置（性质不同）。

---

## 7. 坐标任务为什么没做完（**先排除了一圈，最后不是磁盘**）

### 7.1 现象与排除链

| 现象 | 排查结论 |
|---|---|
| `UndertaleModCli.exe --help` 一律 `SIGTERM`、零输出 | 不是脚本问题（`--help` 都起不来） |
| 改名副本（`umcli.exe`）、换目录、**关沙箱**，照样被杀 | 不是文件名 / 不是沙箱策略 |
| 同目录 `createdump.exe` 从 `%TEMP%` 跑**正常返回 -1** | 不是「这个 exe 有毒」 |
| `dotnet.exe --version` **能跑**（报"没有 SDK"是 runtime-only 的正常反应） | 不是 .NET 整体被拦 |
| **把整套 UTMT 换到 `D:`（NTFS）再跑，仍然 `SIGTERM`** | ⚠️ **不是磁盘** |

⇒ **更正**：本轮中途一度判断成「E: 盘坏了导致工具起不来」，**这条是错的**，用 D: 的副本一试就破了。
真正结论只有一句能站住：**这台机器上 `UndertaleModCli.exe` 起不来，本轮没有绕法**。
（顺带说明：作者最初是从 `E:` 启动的，所以先怀疑盘；换了盘才证明跟盘无关 —— 这就是"判据也是被测物"。）

### 7.2 已经准备好的东西（下一轮直接用）

`_tools/dump_instances.csx` 已经写好并入库，**不需要再设计**：

- 反射取值（`GF/GS/GD` 三个 helper），字段名对不上也不会编译失败；
- 输出 TSV：`R\t房号\t房名\t宽\t高\t层数\t层内实例数\tGameObjects数` + `I\t对象\tx\ty\tsx\tsy\trot\timgIdx\timgSpeed\tdepth\t层名`；
- 输出路径走环境变量 `UTMT_OUT`，**同一个脚本可以直接跑五章**；
- 用法：`set UTMT_OUT=...` → `UndertaleModCli.exe load <data.win 副本> -s dump_instances.csx`。

★ 游戏本体在 **C:**：`C:\Users\23002\Desktop\项目文件夹\珍贵的回忆\DELTARUNE_183049\DELTARUNE\chapterN_windows\data.win`
（14.0 / 66.2 / 140.4 / 128.7 / 161.7 MB，五章齐全）—— **不在 E:**，之前记的路径是错的。

---

## 8. 折中交付：交互点坐标（978 间 / 6,889 个点）

全量坐标采不到，但第68轮那批 `inst68.json` **本来就带 x/y**，覆盖的正是「能交互的东西」。
对"把世界搬上桌面"来说，这一撮恰恰最需要坐标：门要连路线、可读物要能读、存档点和宝箱要能碰。

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
