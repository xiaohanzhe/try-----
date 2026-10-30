# 第121轮：让 ut 的房间**点得动**（场景 `objects` 接线）

> 一句话：第120轮给了 ut 画面，但 `objects` 还是空表 ⇒ 走进 ut 的房间什么都点不了。
> 本轮写进 **422 条可交互物 / 136 个场景**，门票是"只写现在真能用的 6 类"。

---

## 1. 问题是什么（链路取证）

产品侧的可交互物**只有一个入口**：

```
item_interact.build_props(scene, chapter, world, routes=…, readables=…)
   ↑ 遍历 scene['objects']
```

- `readable` / `sign` / `savepoint` / `pickup` / `fountain` / `interactable` 分别落到对应分支；
- `door` 分支要 `routes` 表（`door_letter_of` + `route_for_door`），没路由就建不出门；
- **`cutscene` 落 `else` 被直接丢弃**。

而第120轮结束时 ut 的 358 个场景**全是** `"objects": []` ⇒ `build_props` 返回空列表
⇒ 原文可读物、存档点、告示牌**全部哑掉**。这是 §120.9 登记的第 3 条"下一层"。

## 2. 三条口径（每条都有取证，不是为了填数字）

### ① 只写**现在真能用**的 6 类

ut 的可交互实例全量 **2,096** 个，按 `item_interact.classify` 分：

| kind | 实例数 | 本轮写？ | 理由 |
|---|---:|:--:|---|
| `door` | 1,299 | ✗ | 建门必须有 `routes`；ut 侧**还没有** `_routes.json` 条目（第109轮只做了桌面 4 门）。没有目标就建门 = 推不开的门。 |
| `cutscene` | 375 | ✗ | `build_props` 落 `else` 丢弃 ⇒ 写了是纯噪音。要承载必须改产品代码。 |
| `readable` | 350 | ✓ | 正文走 `_readable_text.json` 的 `by_scene`（第117轮已备好 ut 90 个场景） |
| `sign` | 34 | ✓ | |
| `savepoint` | 33 | ✓ | |
| `pickup` | 3 | ✓ | |
| `fountain` | 1 | ✓ | |
| `interactable` | 1 | ✓ | |

⇒ 写入 **422 条**。

### ② `sprite` **一律 `null`**（不是省略键）

- ut 的画面已在第120轮烘进背景图，再画一遍就是**重复绘制**；
- 走"并进隐形名单"这条路会**跨作品污染**：`_obj_visible.json` 的 `hidden` 是**全局扁平**
  名单（901 条，来自 Deltarune 转储），ut 的可交互名 90 个里与"Deltarune 要画的 src"
  冲突**只有 1 个**：`obj_savepoint`（Deltarune 要画、ut 已烘进背景）。
- 所以走 `sprite=None` 这条**不依赖名单**的路：`scene_render` 对它的处理是
  `name=None` → `scene_canvas._paint_obj` 第 375~376 行
  `pm = assets.get(name) if name else None` ⇒ **不落笔、不崩**（已逐行核过）。

条目语义因此是：**"这里有个可交互物，画面已在背景里"** —— 与"能不能画"刻意脱钩。

> **别把 422 误读成"能画 422 个"**。按"有 sprite + `vis=True` + 非自绘 + 非 Create 隐藏"
> 三层过滤，**能画的只有 78 个**（`probe_props121.py` 实测），其中还有 13 个是门（本轮不写）。
> 那 1,973 个 `vis=False` 不是坏数据 —— 原作里它们本来就是"看不见但能碰"的触发器。

### ③ `pos` 用**左上角**语义 `[x-ox, y-oy]`

- `scene_render` 的 rect 就是左上角；
- 烘图 `bake120` 画实例用的**正是** `(x-ox, y-oy)`（`paste(canvas, img, p['x']-ox, p['y']-oy)`）
  ⇒ 两者同一坐标系，交互判定框与背景像素能对上。
- ⚠️ **既有欠账（本轮只登记、不动）**：Deltarune 侧 `gen_objects44` 写的是 `[x, y]`
  （**没减原点**），涉及 10,608 条。改了会动一大批既有锁的锚点值，留待专门一轮。

## 3. 数量账（可复算）

| 项 | 值 |
|---|---:|
| ut 场景总数 | 358 |
| 有实例表的房间 | 338 |
| 无实例（那 20 个"名字不在 UT 房间表里"的附加场景，第120轮已如实留空 bg） | 20 |
| 可交互实例（8 类） | 2,096 |
| **写入 `objects` 的条目** | **422** |
| **有物件的场景** | **136** |
| 按 kind | readable 350 / sign 34 / savepoint 33 / pickup 3 / fountain 1 / interactable 1 |
| 幂等 sha256（连跑两次） | `728e8e3db8e8a202` |

## 4. 验证（三层，全绿）

| 层 | 脚本 | 结果 | 守什么 |
|---|---|---|---|
| 离屏**真链路** | `_tools/verify_objs121.py` | **14 PASS / 0 FAIL** | `SceneState.from_dict` → `II.build_props` → `scene_render.plan_frame` 真跑；含"给表用原作正文逐字 `* 顺着路走。`"、"不给表回落兜底台词且两者**必须不同**"、清空 objects ⇒ 0、假 src ⇒ 0、K_OBJ 的 name 全为 None（不重复绘制）、塞真 sprite ⇒ name 非 None（正控制） |
| **静态锁**（进 G2） | `_tools/check_objs121.py` | **16 PASS / 0 FAIL** | ★★ 位置**全量复算**：`inst_full.tsv` + `objmap_ut.txt` + `viz120.ut.tsv` 的 `SPR` 原点段重算 `pos`，358 个场景**逐条相等**；配 1 像素负控制 + 原样正控制；分布逐值钉死；`door`/`cutscene` 一个都不许出现 |
| **全量回归** | `regress/run_all.py` | **PASS=5947 / FAIL=0 / 套件 120 / 全部 IDENTICAL** | 老锁一条没放宽（见 §5） |
| 复检 | `_tools/recheck121.py` | **9 PASS / 0 FAIL** | 语法 / 结构 / 编码行尾 / 恒真判据（AST+正控制）/ 令牌回验 / 幂等 / 无临时产物 |

## 5. 四套老锁报红 —— 都是**真事实**，改的是口径不是门槛

| 套件 | 红在哪 | 客观事实 | 怎么改 |
|---|---|---|---|
| `objects_round44` | A3 形状坏 422 / C1 752≠616 / C2 3623≠3201 / C3 同上 | 本锁的种群是 **Deltarune 命名空间**，A4「sprite 指向 `objs/` 真实文件」与 C2/C3「对着第68轮 Deltarune 普查守恒」都装不下 `sprite=None` | 与 OneShot 同样**剔除** `_zone.ut.*`，并新增 **A2c**（被排除分片自证：1 个 / 358 场景 / 136 有物件 / 422 条 / sprite 非 None 的 0）+ **A2d** 正负控制（`RE_UT_ZONE` 认 `_zone.ut.rooms.json`、**不认** `_zone.uty.rooms.json` —— 否则连黄魂一起静默剔除）。守恒数字回到 616 / 3201 |
| `items_round48` | E3「缺口却有实例 1 个」 | `obj_interactable` 在 **ut** 有 1 个实例，而 `data_gaps()` 说的是**第68轮对 Deltarune 五章**的普查（gap 文案写着 `objmap43` / `ch1~5`） | `_product_src_hist(skip_ut=True)` 分账 + 新增 **E3b**：ut 分片 422 条、落在缺口名单里的**只有** `{'obj_interactable': 1}`、Deltarune 侧仍 0 ⇒ 缺口声明成立（**不是**把声明改小去迎合事实） |
| `items_round68` | C3 同上 | 同上 | `_src_hist(skip_ut=True)` + 新增 **C3b**（同 E3b 口径） |
| `verify_scene_fit99` | G24c「出现第三种前缀 `(无前缀)` 422」/ G27 `obj_readable_room1` 921→1047 | 422 个条目 `sprite=None` 被并进了 `(无前缀)` 桶；其中 126 条 `obj_readable_room1` 被计入"被隐形名单过滤"——而它们**压根没贴图**，不是被名单拦下 | G24c：`(sprite=None)` **单独立桶**（不把 `(无前缀)` 整体放行 —— 那个桶是真会出问题的"漏目录前缀"），钉死 422 条 + **只许出现在 ut 场景**（`none_sids - ut_ids` 必须为空）；G27：只数**有贴图**的物件，语义钉回"隐形名单的杀伤面" = 921 |

> ★ 三轮踩过的同一个坑：**分母换了物种**（第103轮 OneShot 7,804 条把过滤率从 85.5% 拉到 24.9%）。
> 这次是 ut 422 条。处理方式一致：**分账**，而不是放宽判据。

## 6. 一个决定性对照实验（反证第120轮"没漏画"）

给 `bake120.py` 加 `--include-invisible`（默认关，产品行为一字不变），对 `room_area1`
烘两张图对比：含 `vis=False` 的那张多出**蓝色箭头与黑色圆点**（`obj_sdl` / `obj_solidsmall`
等**碰撞体调试精灵**），差异 4,227 / 176,800 = 2.39%。

⇒ `vis=False ⇒ 不画` 是**对的**，第120轮不是漏画。这个开关留作将来的对照工具，
**不是产品口径**。

## 7. 遗留（按优先级）

1. **ut 的门（1,299 个实例）**：要先建 ut 侧 `_routes.json`（`build_props` 的 `door` 分支
   需要 `door_letter_of` + `route_for_door`），否则只能建出"推不开的门"。
2. **`cutscene`（375）**：`build_props` 落 `else` 丢弃，**必须改产品代码**才能承载
   （建议另开一层，不要塞进现有 kind 分支）。
3. **Deltarune 侧 `pos` 未减原点**（10,608 条）：既有欠账，改动面大，单独一轮。
4. **那 20 个 ut 章场景归属哪一章**：不动会牵连 2,166 场景数与多套分母。
5. `_zone.outertale.*.json` 244 场景仍接不了线（`original_room_id` 是自编号，0/244）；
   新线索：ot 358 间里 338 间名字与 UT 相同（第120轮取证）。

## 8. 复现

```bash
cd code-quality-audit/第121轮-ut可交互物/_tools
python build_objs121.py --dry-run     # 看账，不写盘
python build_objs121.py               # 写回（幂等）
python verify_objs121.py              # 真链路 14/0
python check_objs121.py               # 静态锁 16/0
python recheck121.py                  # 复检 9/0
cd ../../regress && python run_all.py  # 全量 5947/0
```
