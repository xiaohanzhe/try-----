# 第115轮 · 跨作品物件普查（Deltarune）

> 一句话：**Deltarune 跟 OneShot 不是同一类问题 —— 它的物件本来就有名字，
> 不需要起名，缺的是「这个名字是干嘛的」。**
> 五章全量：**1,251 间 / 47,895 个实例 / 1,945 个不同对象**，其中 **1,099 个是画面上的物件**。

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
| **有 sprite 且可见** | **1,099** | 画面上的东西（家具、招牌、树、门…），占实例 **41.1%** |
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

## 3. 需要人补的那一小撮：82 个名字不表意的可见物件

按「`obj_prop_*` / 尾部带编号 / 单字母」筛出来的，共 **82 个**（占可见物件 7.5%）。
这些名字从字面看不出用途，需要读代码或看现场。前几个例子：

```
obj_dogcheck2                     4 间  spr=spr_dogcar
obj_waterable_flower_2x2          3 间  spr=spr_waterable_flower
obj_dw_churchc_titanclimb2        3 间  spr=spr_eventsmall
obj_darkroom1_lanternDispenser1   2 间  spr=spr_darkroom1_lanternDispenser1
obj_board_mazewater1..4           1 间  spr=spr_board_mazewater / spr_board_mazewall
obj_board_glacier_switch3         1 间  spr=spr_board_b2dungeonswitch
```

全表在 `_evidence/deltarune_objects115.json` 的 `objects[]` 里（`vague: true`）。

---

## 4. 数据缺口（必须先说清，别当成"已经做完"）

1. **没有坐标**。`rooms_map.json` 只记「这间房有哪几个对象」，**没有 x/y**。
   ⇒ 现在能做「哪些对象在哪几间房」，**做不了**「这个物件在这一格」。
   要做到 OneShot 那种「块级」粒度，得**重跑 UTMT 写新 csx 采 `x/y`**（本轮没做，列待办）。
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
```

`check_obj115.py` 当前 **11 PASS / 0 FAIL**：
逐章房间数 == 147/278/246/328/252（C1×5）· 合计 1,251（C1b）· Σ实例 47,895 且与报告一致（C2）·
实例名都落在 objmap（C3，允许 `GameObject` 例外）· 可见/纯逻辑互斥且穷尽（C4）·
排序单调（C5）· **负控制**：注入 `obj_THIS_IS_NOT_REAL` 后 C3 必须报红（C6）。

> 原始数据怎么来的（本轮没重跑，沿用既有产物）：UTMT CLI v0.9.2.0，
> `UndertaleModCli.exe load <data.win 副本> -s <脚本.csx>`，**只对副本 load**，stdout 落文件。
> 五章 `data.win` 在 `…\珍贵的回忆\DELTARUNE_183049\DELTARUNE\chapterN_windows\`。

---

## 6. 下一步（按性价比排）

1. **写新 csx 采实例坐标**（x/y/scale/rotation）⇒ 才能做「哪一格是什么」；
   有了坐标，Deltarune 这一侧就能和 OneShot 的块级表并到同一套结构里。
2. **82 个不表意名字**：能靠 `obj_*` 引用次数 / 所在房间 / sprite 反推一部分，
   反推不出的再列给用户。
3. **UT / UTY / Outertale**：同为 GameMaker `data.win`，流程可复用（本轮方法直接迁移）。
4. **Freebird 四款**：用户已明确搁置（性质不同）。
