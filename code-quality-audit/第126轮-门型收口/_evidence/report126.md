# 第126轮报告 · outertale 的门：244 个场景、0 条路由

> 一句话：**outertale 整个作品此前没有任何一条门路由**（`plan_route_to` 在那个作品里连一条边都拿不到）。本轮按「机制 + 在场」两条独立证据补 **209 条**，并**同时**写进 `_routes.json` 与逐门寻路图 `_room_graph.json` 的 `chapters.outertale`。

---

## 1. 缺口

| 作品 | 场景数 | 本轮前路由数 | 本轮后 |
|---|---|---|---|
| ch1~ch5 | 1,013 | 582（第125轮后） | 582 |
| oneshot | 263 | 420 | 420 |
| ut | 358 | 525 | 525 |
| **outertale** | **244** | **0** | **209** |
| uty | 287 | 0 | 0（证据不足，见 §9） |

第115轮的可达账已经写明 outertale「exact 策略 144 条边、从入口只到得了 **1** 间房」，但**没人把这些边变成产品能读的东西** —— 于是 244 个场景全部"看得到、走不通"。

## 2. 为什么以前没做（不是没数据）

第115轮已经从 `game.droid` 抽出：

- `conn_ut.json` —— **301** 条 `room_goto` 记录（`n_codes 8,374`、`n_with_room_goto 134`）
- `inst_full.tsv` —— **358** 间房、**4,600** 个实例的摆放表

缺的是"把这两份东西对起来、按产品能消费的形状落地"这一步。

## 3. 怎么验的（三条推导 + 四类拒收）

| kind | GML 写法 | 条数 | 独立证据 |
|---|---|---|---|
| `ot_door_guard` | `if (room == N) room_goto(M)` | **93** | ★ 那个门对象**真的摆在 N 这间房**的实例表里 |
| `ot_door_shift` | `room_goto_next()` | **116** | 目标 = `src + 1`；**97.9%** 的目标房也有门，且房间名成序列（`room_ruins1 → ruins2 → ruins3 …`） |

`ot_door_guard` 的"在场"判据与 Deltarune 的 `obj_marker<字母>` 等价：**守卫常量只是先验，实例表才是落点证据**。

**拒收四类**（每一类都留账，见 §5）：

1. 无条件 `room_goto(M)`（`src` 未知）—— **28 条**，不猜；
2. 守卫说源房是 N、实例表里 N **没有**这扇门 —— **24 条**，两种证据打架 ⇒ 不写；
3. 同 `(场景, 对象)` 出现多个目标（原作按 `x` 坐标分叉：旅馆大堂 `x<300`→商店 / `x>300`→新家电梯）—— **1 组**整组丢（产品一扇门一个目标）；
4. 端点未登记成场景 —— **62 条**（其中 `src` 侧多，属 outertale 房间表比场景表大：358 vs 244）。

## 4. 改了什么（两层，缺一层就是半成品）

### 4.1 `ralsei_pet/assets/scenes/_routes.json`

- 1,531 → **1,740** 条；新段 priority **6000~6208** 连续
- 每条：`when_scene` = 场景、`when_door` = **None**、`when_src` = 门对象名、`_original` 带 `chapter/kind/via/code/room_delta(仅 shift)/两端房名与下标`
- 格式：CRLF 31,541 / 裸 LF 0 / 尾 `}\r\n}` / 无 BOM / FFFD 0（`check126.G4` 锁）

### 4.2 `code-quality-audit/第42轮-原作拓扑取证/_evidence/_room_graph.json`

- 新增 `chapters.outertale`（`folder` + `n_edges 209` + `edges`），总边数 1,202 → **1,411**
- ★ 这份"证据"同时是**运行时数据**：`scene_pathfind.room_graph_path()` 把它硬编码到该路径 —— 第105轮给 OneShot 补边时踩过同一个点
- 冻结章 **ch1 238 / ch2 323 / ch3 79 / ch4 72 / ch5 70 / oneshot 420** 逐章等值（生成器内含指纹自证 + `check126.E3` 独立复核）

## 5. 账

**丢弃账（与 `check126.B5` 对账）**

```
301 items = 179 门类 + 122 非门
门类 179 = 150 guard + 28 uncond + 1 shift
  guard 150 → 丢 24（与实例打架）→ 126
  shift 1 项 → 展开 140 个实例房 → 126
  合计候选 266
266 → 丢 54（端点未登记）→ 212 → 丢 1 组（按坐标分叉）→ 211 → 去重 1 → 丢 1（已在产品）→ 209
```

**覆盖**：src 场景 **162** / dst 场景 **162** / 并集 **204 / 244**（**如实登记：还有 40 个场景没有出边**）

**按对象**：`obj_doorA` 116 · `obj_door_ruins13` 31 · `obj_door_t` 18 · `obj_door_s_musfade` 18 · `obj_door_u` 10 · `obj_doorW`→`obj_door_w` 6 · `obj_doorXmusicfade` 6 · `obj_door_v` 3 · `obj_demodoorA` 1

**按区**：citadel 55 · foundry 42 · starton 30 · wasteland 30 · core 22 · aerialis 20 · special 10

**密度**：outertale「有出边的场景」**0 → 162**；桌面可达仍 **215**（outertale 没有桌面门，本轮不动世界门控）

## 6. `check126` 守什么（35 条）

| 段 | 内容 |
|---|---|
| A | 209 条 · priority 6000~6208 连续 · 只落 outertale · `when_door` 全 None · `when_src` 全是门对象 |
| **B** | **独立重推**：另写一份推导（不 import 生成器）⇒ 集合相等；挖一条 / 塞一条各判一次；丢弃账与生成器一致 |
| C | guard 条**在场**互证 · shift 条 `dst == src+1` · 端点已登记 · 无自环 · 负控制：换到"没摆这扇门"的房间必红 |
| **D** | 拒收纪律**四对**（28 / 24 / 1 组 / 62 —— 每对都是"证据里真有、产品里 0 条"） |
| **E** | 图里的边 == 路由新段（**两层不许各说各的**）+ 冻结章逐章等值 |
| F | 密度只增不减，且**如实**登记并集 204 < 244 |
| G | 自检：`check` 的 `args[1]` 与 `ok` 的 `args[0]` **两套 harness 都查** + 正控制 + 编码行尾 |

## 7. 老锁同步（6 处，全部是"判据描述了过去时相"）

| 文件 | 改了什么 | 为什么 |
|---|---|---|
| `verify_scene_route_original.C3` | 新增 `_KIND_OT_GUARD/_SHIFT` + `_ot_self_ok` + C3a11/C3a12 + `_NON_LETTER_KINDS` 扩容 | 新 kind 无分支 ⇒ 209 条报"不自洽" |
| `verify_routes_order44.B6` | 对象级 `when_src` 209 → **418** | 它钉的是"有分流依据的条数" |
| `verify_pathfind45.A3/A3c/A4` | `expect_ch` 加 `outertale: 209` | 硬编码分章数 |
| `check113n.B8` | outertale 移出"无图章"名单 + 新增 **B8b 正控制** | 它现在**有图了**，判据在描述旧时相 |
| `check124.A0/D2` | 路由 1,531 → **1,740**；唯一边 1,526 → **1,735** | 计数锚点 |
| `check125.A/B` | 新段选择 `priority >= 5000` → **闭区间 [5000, 5138]** | `>=` 把 6000 段一起吞了，10 条判据同时红 |

## 8. 踩的坑（9 条）

1. **⚠️ 遗留池里那项是幻影**：第125轮我写的是"39 条 A/B/C 的 `_musfade` 变体边，89.7% 过 marker 闸，下轮可补"。实测 **84 条 musfade 全覆盖检查**（A17/B15/C7/D12/X20/W13）后发现：凡是"机制 + marker"都过的，**全部**卡在"同场景同门已有路由 ・ 该边已存在" ⇒ 一条也补不了。**先测再动手，直接省掉一整轮。**
2. **把"不知道"当"都知道"**：第一版把无条件 `room_goto(M)`（`src` 未知）展开到**该对象的全部实例房** ⇒ `obj_doorA` 一个对象炸出 140 条边，`c_archive_aerialis4` 变成"处处可达"，歧义组从 1 涨到 **196 组**。这是整轮最像"产品 bug"的一次假象 —— 根因在我的推导，不在数据。
3. **`_room_graph.json` 不在 `assets/scenes/`**：产品 `scene_pathfind.room_graph_path()` 把它硬编码到第42轮证据目录（"证据即运行时数据"）。第一版路径写错，**routes 已经写进去了才崩** ⇒ 半成品。用 `git show HEAD:<path> > <path>` 还原后重跑（**不用 `git checkout --`**，那条命令 109 轮有前科）。
   - ⚠️ 顺带发现：`git show` 出来的 blob 是 **LF**（仓库存 LF、工作区 CRLF），还原后 `git status` 会显示整文件改动 —— 只有让生成器重写一遍（它按 CRLF 落盘）才回到合同形状。**还原 ≠ 复原**。
4. **`>=` 段位口径太宽**：`check125` 用 `priority >= 5000` 选新段 ⇒ 6000 段的 209 条被吞进来，A1/A2/A3/A4/B2/B3/B4 一起红。改成闭区间才对；**不能改成"按场景前缀筛"** —— 那会让 A2「只落 ch1~ch5」变成恒真判据（自己筛自己）。
5. **判据在描述过去的时相**：`check113n.B8` 把 outertale 归到"无图章 ⇒ 返 `[]`"。它现在有图了 ⇒ 必须**翻面**，并且要新增正控制（有图 ⇒ 必须真有邻居），否则把名单改了也没人证明它真的生效。
6. **`scene_route_original.C3` 的位移域**：`guard` 的落点由守卫常量决定，**不保证任何差值**。第一版若照 ut 的写法断言 `dst == src + off`，209 条里 93 条 guard 会全红。⇒ `_ot_self_ok` **只对 shift 断言位移**。
7. **`obj_mainchara` 必须排除**：它出现在 **297** 间房，`goto`/`next`/`prev` 都有，是"走到屏幕边缘换房"的另一层机制（第122轮已裁定不写）。混进来会让每条走廊都多出十几条假边。
8. **`conn_ut.json` 的 `goto` 不全是门**：144 条里 6 个对象是非门（`obj_battlerflowey` 战斗触发、`obj_wanderparent` 演出移动、`obj_readable_room_editor`…）。按 `obj_door*` / `obj_demodoor*` 前缀筛，并把 `obj_mainchara` 单独排掉。
9. **方法学更正（对第125轮的措辞）**：本轮顺带实测了已收字母门的 marker 命中率 —— **A 184/204 = 90.2% ・ B 189/210 = 90.0% ・ C 52/54 = 96.3%**，都**不是** 100%。所以第125轮"必须 100% 才收"这句话把门槛说高了：真正的判据是「机制 + 在场 ≈ 90% 以上，且**每一条不中都能逐条归因**」，W 门之所以仍不收，是因为它两套 marker 写法（60.2% / 84.3%）**归不了因**，不是因为它不到 100%。

## 9. 回归

- `check126` **35/0**（新锁）
- 全量 G2：**见下**（本轮收口时实测）
- 老锁同步后逐套件：`scene_route_original` 58/0 · `routes_order44` 23/0 · `pathfind_round45` 37/0 · `check113n` 47/0 · `check124` 25/0 · `check125` 28/0

## 10. 遗留

- **uty 287 个场景仍 0 边**：第115轮 `conn115.json` 里 uty 只有 **1** 条可信边，`conn_ut.json` 侧的 `room_goto` 也基本是 `room_goto_next` 且对象是 `obj_flowey_world_controller` 这类，**没有门对象语义** ⇒ 证据不足，本轮不写（要写就得先反编译 uty 的门对象，属于新取证）。
- **outertale 还有 40 个场景没有出边**：其中 62 条证据边因为端点未登记而丢。要补得先把缺的房间登记成场景（房间表 358 vs 场景表 244）。
- `goto_const_nosrc` 的 **28 条**：知道目标、不知道从哪触发。若日后能确认"哪段 Alarm 在哪间房跑"，可回收。
- **39 条 A/B/C musfade 变体**：本轮证伪为"已覆盖"，**不要再当遗留项**。
- 老池子：ch2~ch5 从桌面不可达 · 66 门实例里 10 个可补 + 2 组冲突 · cutscene 375 · `chapters.ut` 为 null · Deltarune `pos` 未减原点 10,608。
