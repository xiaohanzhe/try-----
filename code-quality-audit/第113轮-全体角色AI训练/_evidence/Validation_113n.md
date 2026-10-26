# 第113轮n · 「你还记得这些地方」—— 空间认知的最后一块接上了

> 用户口径（2026-10-26 逐字，第113轮j 就引过，**这一轮才落地**）：
> 「对了，方便的话可以**训练一下他们寻路的能力**（**包括地方偏好，特定事件时去的地方**等等）」
>
> 本轮接的是上一句里的「**寻路**」—— 不是让 7B 做路径搜索，而是让 NPC **知道从这儿能走到哪**。

---

## 1. 这块为什么一直空着

`place_hint(here=, home=, near=, at_home=)` 从第113轮j 起就是三块：

| 块 | 状态 |
|---|---|
| 【你现在在哪】 | 113j 落地 |
| 【你的归属地】 | 113j 落地 |
| 【你还记得这些地方】 | **有形参、有文案、有判据（113j C5/C6 还专门测它）—— 但产品一次都没传过 `near=`** |

这正是本项目最贵的那类坑：**形状齐了、判据全绿、没人接线**。
和 106 轮「路径算出来了但没人走」、45 轮「`follow_route` 零调用」是同一类。

本轮先确认了它确实是空的：

```
$ grep -n "place_hint(" ralsei_pet/src/main.py
    ...  npc_life_mod.place_hint(here=here_txt, home=home_txt, at_home=...)
                                                          ↑ 没有 near
```

---

## 2. 真源：原作门连接图，**不按坐标算"近"**

`_room_graph.json`（第42轮反汇编取证，第105轮补 `oneshot` 章，共 **1,202 条边 / 6 章**）。

★ 为什么不用落点坐标算距离：房间坐标是**各自局部坐标系**里的值（10~300 的小数），
跨房比距离在原理上不成立 —— 第44轮已证伪，`shortest_path()` 的注释里写着。
**只能走图。**

★ 为什么只要 **1 跳**：一扇门就能到，模型说"往那边走能到教堂"是**真的**。
2 跳开始就成了"知道但没去过"，既说不清怎么走，也更容易编路线。

---

## 3. 落地（三处，都在各自唯一的出口上）

| # | 位置 | 做了什么 |
|---|---|---|
| 1 | `ralsei_pet/modules/scene_pathfind.py` | 新增纯函数 `neighbor_rooms(graph, chapter, room, limit=None)`：只取 `src==room` 且 `dst!=room`、**升序去重**（确定性）、坏输入返 `[]` 不抛 |
| 2 | `ralsei_pet/src/main.py` | 新增 `_scene_rooms()` / `_scene_by_room()`（房间下标表，和索引**共用一次解析**）、`_room_graph_edges()`（懒加载 + 缓存）、`_npc_place_near(sid, limit=3)` |
| 3 | `ralsei_pet/src/main.py` | `_npc_life_blocks` 里 `place_hint(..., near=near_txt, ...)` —— **接上了** |

`npc_life.place_hint` 的 near 文案改成：

```
【你还记得这些地方】Town Mid —— 就在这一带，走过去能到。
```

★ 补「走过去能到」这半句的理由：只说"我记得有这些地方"，模型不会拿它当**路线依据**
（而用户口径是"训练**寻路**"）。

### 3.1 名字为什么不用 `_scene_place_label()`

实测（本轮探针）：

```
ch2.hometown.town_north  ->  here='家乡'
  邻居: 家乡 / 家乡 / 家乡 / 家乡        ← 5 个邻居全叫「家乡」
```

根因：`_index.json` 里这些场景 `name_derived=true`（名字是我们**推的**），
`_scene_place_label()` 按设计把推导名当"无名"，于是只吐区名。
位置块已经说过区名了，这里要的是「**哪一间**」。

⇒ 改成**原作房间 id 整形后的英文**（`room_diner` ⇒ `Diner`，走同一条 `speakable_en`）：

```
ch1.hometown.diner       -> ['Town Mid']
ch1.hometown.town_north  -> ['Town Krisyard', 'Beach', 'Town Mid']
ch1.home.krishallway     -> ["Kris's Room", 'Torhouse']
oneshot.barrens.Bed_room -> ['Docks']
```

---

## 4. 实测数据（不是"应该没问题"）

| 项 | 数 | 说明 |
|---|---|---|
| 全量场景 | 2,166 | |
| **能产出邻居的** | **617**（28%） | 只有**有门图**的章才有 |
| ch1 | 117 / 128 | |
| ch2 | 183 / 236 | |
| ch3 | 46 / 187 | 图只覆盖光世界主链 |
| ch4 | 42 / 261 | 同上（圣域是剧情传送，不是门） |
| ch5 | 41 / 201 | 同上 |
| oneshot | 188 / 263 | 第105轮补的 420 条边 |
| ut / uty / outertale / desktop | 0 / 890 | **完全没有门图**（见 §7） |

★ 覆盖率判据用**只增不减**的下界（`≥ 500`），不打印实际值 ——
否则"补了素材"会变成假 DIFF。

---

## 5. 判据：`check113n` **46 条**（新套件，已进 G2）

| 组 | 守什么 | 代表判据 |
|---|---|---|
| A（7） | `neighbor_rooms` 纯函数 | 只取方向正确的边（`5→2` 不算 2 的邻居）· 自环丢掉 · **边表倒序结果不变**（确定性）· 坏输入 6 种全返 `[]` |
| B（16） | 真图 + 抽产品代码真跑 | `diner ⇒ Town Mid`（人眼核过原作）· 不含自己 · 调试/演出区被剔（`ch2.system` ⇒ 空）· 无图章节返 `[]` 不崩 · 全量零空标签 / 零内部结构 / 零重复 · 覆盖率下界 |
| C（5） | `place_hint` near 文案 | 有【你还记得这些地方】· **「走过去能到」** · near 空 ⇒ 不产块（负控制）· 空值/None 被滤 · 只有 near 也成块 |
| D（7） | AST 接线（禁纯文本扫） | `place_hint` 真带 `near=` · 值最终来自 `self._npc_place_near(...)`（**允许局部变量中转**，判一步数据流）· 链上真到 `load_room_graph()` · import 用 AST `ImportFrom` 判 |
| E（2） | 破坏性负控制 | `neighbor_rooms` 打回 `[]` ⇒ 邻居必须消失 · **只拆** near 分支（其余不动）⇒ C 组必须变红 |
| F（5） | 脚本自检 | 语法 · 无 BOM · 行尾不混 · **无恒真判据** + 正控制（扫描器能抓到夹具里的 `check("x", True)` 且不误报 `1 == 1`） |
| G（4） | **端到端** | 整段 prompt 里**真有**那块（`ch1.hometown.diner`）· `ut` 整段不含（负控制）· 打回 `[]` 后消失（破坏性） |

★ D3 的「允许局部变量中转」是**改判据**不是放水：第一版只认直接调用，
把正确写法 `near_txt = self._npc_place_near(sid)` 判红了 ——
同 107 轮变异 M13（只认直接调用会误伤）。判据也要被测。

---

## 6. 踩到的两个坑

### 6.1 桩漏一个新依赖 ⇒ 整块**静默消失**

给 `_npc_life_blocks` 加 `self._npc_place_near(...)` 之后，`check113j` 直接红了 4 条：

```
[FAIL] F1 在家（sid == home）⇒ 输出「就是这儿」且不提「想回去」
[FAIL] F2 不在家 ⇒ 输出「想回去」
[FAIL] F3 无归属地 ⇒ 只有「在哪」，不硬凑归属地
[FAIL] F4 位置块在整段 prompt 的**最前面**
```

报的是**真事实**（位置块确实没了），但根因在桩：`check113j` 的 `_Stub` 没有
`_npc_place_near`，`AttributeError` 被同一个 `try/except` 吞掉 ⇒ **整块不产**。

⇒ 结论：**给被抽取的方法加新 `self.xxx` 依赖 = 给所有挂这个桩的套件加一个破坏性变更**。
第113轮m 已经因为 `_place_proper` 崩过一次（那次是直接抛），这次更隐蔽（被吞）。
两轮连续踩，已写进记忆。

### 6.2 `check107` 的 E8b 把**行号**写进了描述 —— 第 6 次

本轮只在 `main.py` 的 import 区上方加了 7 行，`check107` 就假 DIFF：

```
-[PASS] ... E8b ... `RalseiPet.__init__`(744) 与 `PerformanceMonitor.__init__`(396) ...  <- line 748 vs 396
+[PASS] ... E8b ... `RalseiPet.__init__`(744) 与 `PerformanceMonitor.__init__`(396) ...  <- line 755 vs 396
```

判据本身（两个 `__init__` 的 `lineno` 不同）没问题，坏的是**回显了随代码布局漂移的绝对值**。
⇒ 描述去掉 `(744)`/`(396)`，detail 改打布尔（`都在=True 同一行=False`）。
"判据禁回显随时相变的绝对值（含行号）"这条**已是第 6 次发作**。

---

## 7. 已知缺口（不当成绩报）

1. **`ut` / `uty` / `outertale` 没有门图**（890 个场景，41%）。这三部作品的房间切换
   没做过反汇编取证 ⇒ 里面的 NPC 拿不到邻居，块不产出（**不硬凑**）。
2. **ch3/ch4/ch5 只覆盖光世界**：暗世界的房间切换是剧情传送（`room_goto` 由脚本决定），
   不是门对象，所以第42轮的取证没进去。ch3 只有 46/187。
3. **只要 1 跳**：2 跳及以上的"知道但没去过"没做 —— 那需要另一套说法（"听说"），
   与"走过去能到"是两种语气，不能混。
4. **「地方偏好」还是没做**：用户口径里"地方偏好"指角色**偏爱**去哪（性格/习惯），
   本轮做的是**拓扑可达**（客观事实）。前者需要逐角色数据（96 张卡里没有"喜欢的地点"
   这个字段），凭空生成就是编造 ⇒ 留给有数据的时候。
5. **`Krishallway` / `Torbathroom` 这类粘连词**：原作 id 就是一个词，拆开（`Kris Hallway`）
   属于猜词，按 113l 口径不猜。

---

## 8. 改动清单

| 文件 | 变化 |
|---|---|
| `ralsei_pet/modules/scene_pathfind.py` | 733 → **775** 行（新增 `neighbor_rooms`，纯函数、零依赖） |
| `ralsei_pet/modules/npc_life.py` | 1405 → **1410** 行（near 文案补「就在这一带，走过去能到」） |
| `ralsei_pet/src/main.py` | 16920 → **17053** 行（+`scene_pathfind` import、+房间下标两张表、+`_room_graph_edges`、+`_npc_place_near`、`place_hint(near=)` 接线） |
| `.../_tools/check113n.py` | **新建**（46 条） |
| `.../_tools/check113j.py` | 桩补 `_npc_place_near()`（返回 `[]`），38 条不变 |
| `.../_tools/probe_near113n.py` | **新建**（看邻居标签长什么样：人读用） |
| `.../第107轮-全屏化与全局缩放/_tools/check107.py` | E8b 去掉写死的行号（第 6 次"回显绝对值"） |
| `code-quality-audit/regress/run_all.py` | 注册 `check113n`（110 个套件） |
| `code-quality-audit/regress/baseline.json` | 新建 `check113n`（46）；重建 `check107`（80，E8b 文案） |
| `.../_evidence/Validation_113n.md` | 新建（本文） |

### 回归

- `check113n` **46/46** · `check113j` **38/38** · `check113k` **80/80** · `check113l` **35/35**
- 全量 G2：**PASS=5688 FAIL=0 / 110 套件全部 IDENTICAL**
  （唯一 `IDENTICAL*` 是既有 `check75c` 空行噪声）
- 算术自证：上轮 5642 + `check113n` 新增 46 条 = **5688**

### 复现命令

```
cd code-quality-audit/第113轮-全体角色AI训练/_tools
python check113n.py           # 46 条判据
python probe_near113n.py 6    # 人读：每章抽 6 个房间的 1 跳邻居标签
cd ../../regress && python run_all.py
```
