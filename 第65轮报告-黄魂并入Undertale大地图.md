# 第65轮报告 · 黄魂并入 Undertale 大地图（数据面）

> 仓库根：`try - 副本`　|　轮次目录：`code-quality-audit/第65轮-黄魂并入Undertale大地图/`
> 授权：用户「人设我明天继续，你先干其他的就好」＋ 第64轮已拍定 **D2「黄魂的地图直接和 undertale 的整合成一个大的」**
> 范围：**只出数据/证据**，产品侧（场景系统 / 寻路器）**本轮不接线**

---

## 0. 一句话结论

把 Undertale 原版（338 间）与黄魂 / Undertale Yellow（287 间）合成了 **一张大图 `bigmap65.json`（625 节点 / 988 条已解析边）**；
**两者的房间命名空间完全不相交（交集 = 0），跨作品边 = 0**——这是**实证结论，不是"没做"**。大图因此保留为 **125 个连通分量（61 + 64）**，
并按纪律**不臆造**任何跨作品连接点，改为在 §6 列为**待裁定项**。

副产物：查清用户记忆里的两个易混来源——**《红与黄》= Undertale 本体 + mod**（不是黄魂），
它 = 原版 338 间**同序** + 追加 20 间，且用 5 个 GML 实证的连接点把新沙盒房挂回原版房。

---

## 1. 本轮定位：三个来源，别再混

| 代号 | 真实身份 | 房名体系 | 房间数 | 门对象 |
|---|---|---|---|---|
| **ut** | Undertale **原版**（`undertale.apk` → game.droid） | `room_*` | **338** | `obj_doorA~D` + `obj_door_t/u/v/w/s_musfade/ruins13/Xmusicfade` 等 |
| **uty** | **黄魂**（Undertale Yellow，独立同人前传作品） | `rm_*` | **287** | `obj_doorway` / `obj_exit` / `obj_door` + 大量房间专属门 |
| **ry** | **《红与黄》**（`红与黄.apk` → 原版 Undertale + mod） | `room_*`（同原版） | **358** | 同原版 `obj_doorA~D` 等 |

> ⚠️ 第64轮曾把「红与黄」误认为黄魂（A/B 锚点 0/3 报红）⇒ **报红先怀疑判据**：错在判据侧（对象名假设），不在提取器。
> 修正后锚点：黄魂 3/3、原版 4/4 全 PASS。

---

## 2. 关键突破：三个游戏的「门」机制（全部代码实证）

### 2.1 Undertale 原版：**结构规则（索引偏移）+ 显式逐房映射** 两套并用

结构规则（本轮**代码实证**，不再是第43轮的"照 Deltarune 类推"）：

| 对象 | GML 写法 | 规则 | 实证边数 |
|---|---|---|---|
| `obj_doorA` / `obj_doorAmusicfade` | `room_goto(room_next(room))` | **+1** | 178 |
| `obj_doorB` / `obj_doorBmusicfade` | `room_goto(room_previous(room))` | **−1** | 178 |
| `obj_doorC` / `obj_doorCmusicfade` | `room_next(room_next(room))` | **+2** | 27 |
| `obj_doorD` / `obj_doorDmusicfade` | `room_previous(room_previous(room))` | **−2** | 30 |

⇒ **第43轮（Deltarune）的 A=+1 / B=−1 / C=+2 / D=−2 规则，在 Undertale 上同样成立**。本轮从"不敢套用"升级为"代码实证"。

显式逐房映射（`obj_door_s_musfade` 等），出处文件已蒸馏进仓（见 §7）：
```
global.entrance = 19;
if (room == room_water12)   { room_goto(room_water_bird); }
if (room == room_lastruins_corridor) { room_goto(room_castle_precastle); }
if (room == room_fire_elevator)     // ← 同一个门，按 global.flag[398] 六选一
{
    if (global.flag[398] == 0) { room_goto(room_fire_elevator_l1); }
    ... == 1 → _r1 ; 2 → _r2 ; 3 → _l2 ; 4 → _l3 ; 5 → _r3
}
```
**★ 语义要点**：一个门可指向**多个**目标房（flag / 坐标条件分支）⇒ 寻路时它们是**并列可选**而非"改线"。
本轮把 6 条都如实记为 `cond` 边（这也是"344 间却 544 条边"的原因）。
另有硬编码例外 1 条：`room_castle_prebarrier` → `room_castle_trueexit`（`global.flag[7]` 门控）。

### 2.2 黄魂（UTY）：**门对象代码里几乎没有转场**，指令写在**实例创建代码**里

这是本轮最大的机制差异。黄魂的门不是"统一对象 + 条件分支"，而是**每个实例自己声明目标**：

```
// obj_doorway 的实例创建代码（CreationCode）
nextroom = 7;
xx = 160;  yy = 360;
```

⇒ **目标房索引 + 落点坐标全部显式写死**。全表统计：

- 实例原始 **1,054** → 按 (obj,x,y,cc) 去重后 **526**（csx 同时从 `room.GameObjects` 与 `layer.Instances` 取，**是同一批实例的两个视图**；不去重则边数翻倍）
- 带 `nextroom` 的实例 **946**，成功建边 **443** 条 `cc-nextroom`（同房多门合并后）

### 2.3 红与黄：与原版**完全同构**（它是 mod，不是另一个作品）

⇒ 结构规则表与原版逐项一致（`obj_doorA +1 … obj_doorDmusicfade −2`）。

---

## 3. 三份拓扑规模（逐边带出处）

| 作品 | 房间 | 边（全部） | 已解析 | 未解析 | 连通分量 | 最大分量 |
|---|---|---|---|---|---|---|
| **ut 原版** | 338 | 557 | **544** | 13 | 61 | **209** |
| **uty 黄魂** | 287 | 491 | **444** | **47** | 64 | 128 |
| **ry 红与黄** | 358 | 593 | 580 | 13 | 68 | 223 |

边来源分布（ut）：`offset=+1 178 / −1 178 / +2 27 / −2 30 / cond 126 / uncond 4 / special 1 / no-rule 13`。
边来源分布（uty）：`cc-nextroom 443 / no-rule 47 / uncond 1`。

**未解析边（`no-rule`）按纪律留空，不按几何就近凑**：
- ut 13 条（如 `obj_alabdoor_l` / `obj_chipdoor_*` / `obj_coredoor_anim` 等，门逻辑在其它事件或运行期变量里）
- uty 47 条（多是 `obj_locked_door` / `obj_*_door` 等，实例创建代码里没写 `nextroom`）⇒ **列入待人工确认项**，见 §6

### 3.1 建拓扑过程中修掉的 3 处真错误（值得记）

| # | 症状 | 根因 | 修法 |
|---|---|---|---|
| 1 | 实例数翻倍（3702 vs 1851） | `GameObjects` 与 `layer.Instances` 双视图 | 按 `(obj,x,y,cc)` 去重 |
| 2 | 587 条 `no-rule` 噪声 | `obj_marker*`（落点锚点）被当成门 | marker 单独收集为落点，**不计边** |
| 3 | 139 条假边 | `obj_doorA` 的**例外分支**（如 prebarrier）被每个含 doorA 的房间重复命中 ⇒ 典型**恒真**式假边 | 有 struct 规则或 SPECIAL 例外时**不采纳**其 `uncond` |

修后 ut 从 `edges=1131 / unresolved=587` → **`edges=557 / unresolved=13`**。

---

## 4. 大图 `bigmap65.json`：怎么合的

- **节点**：`{work}:{index}` 统一编号（`ut:0` / `uty:0`…），保留 `name / w / h` ⇒ 共 **625** 个
- **边**：统一结构，逐条带 `via / rule / evidence_kind / evidence_file / landing / source_work` ⇒ 共 **988** 条
  （只收已解析边；未解析边保留在原拓扑里，由各自 `stats.unresolved` 记账）
- **不做无来源的"融合边"**：每条边的出处都能指回某份拓扑的某个 GML / cc

### 4.1 跨作品连接点：**0 条，且有实证**

| 判据 | 结果 |
|---|---|
| 房名交集 `ut ∩ uty` | **0**（`room_*` vs `rm_*`，命名空间不相交） |
| 跨作品边数 | **0** |
| **分量数守恒**：`union 分量 == Σ 各作品分量` | **125 == 61 + 64** ✅ |
| 负控制 B：注入 1 条伪造跨作品边 | 分量数**恰好 125 → 124** ✅（判据真在图上跑） |
| 反向控制 C：注入 1 条同作品自环 | 分量数**不变 125** ✅ |

> ★ 守恒判据是**会说话的判据**：只要有一条跨作品边被误引入，等式立刻破——**堵死了"恒真式假绿"**。

---

## 5. 《红与黄》对账：358 = 原版 338 **同序** + 追加 20

- 逐索引比对：`ry[:338]` 与 `ut` 的房名 **338 / 338 完全相同**（**同一命名空间、索引对齐**）
- 追加 20 间（index 338–357）：
  `room_of_bog` `room_fire_elevator_s` `room_steamworks_32~36` `room_steamworks_factory_elevator`
  `room_newhome_01~04` `room_newhome_elevator` `room_modcredits` `room_smile` `room_god`
  `room_water_yellow` `coming_soon` `room_fire_alley` `room_fire_rooftop`
- 基线区（0–337）边差异：**共同 537｜仅原版有 7｜仅红与黄有 9** ⇒ mod 确实动了 16 处

### 5.1 ★ mod 的 5 个「基础房 → 新沙盒房」连接点（GML 实证，非猜测）

| 基础房 | 门对象 | → 增量房 | 分支 |
|---|---|---|---|
| `room_water_prebird` (123) | `obj_door_s_musfade` | `room_water_yellow` (354) | cond |
| `room_fire_hotelfront_2` (182) | `obj_doorXmusicfade` | `room_fire_alley` (356) | cond |
| `room_fire_hotellobby` (183) | `obj_door_s_musfade` | `room_newhome_elevator` (347) | uncond |
| `room_fire_elevator` (213) | `obj_door_s_musfade` | `room_fire_elevator_s` (339) | cond |
| `room_lastruins_corridor` (230) | `obj_door_s_musfade` | `room_newhome_elevator` (347) | cond |

⇒ 单独落 `bigmap65_ry_overlay.json`（20 增量房 / **5 连接点** / 39 条增量边），供产品侧选裁。
**注意**：这类边两端**同属原版命名空间**（都是 `room_*` 索引），证据来自 GML 分支 ——
与「黄魂↔Undertale」的**跨作品无实证边**是两回事，**不可混为一谈**。

---

## 6. 待裁定 / 遗留（★ 需用户发话）

1. ★★ **跨作品连接点怎么定？** 数据上黄魂与原版**互不相连**（命名空间不相交、0 跨作品边）。
   若产品上要"一张能走通的大图"，需**人为指定挂接点**（例如统一从"暗之泉/桌面"入口分流）。
   ⇒ 本轮**不臆造**，请用户裁定用哪种挂法（选项见 §8）。
2. **黄魂 47 条 `no-rule` 边**：门逻辑藏在实例创建代码之外（运行期变量 / 其它事件）。
   建议：下一轮针对性 dump `obj_locked_door` 等对象的**全部事件**再定。
3. **红与黄 mod 是否并入正典图**：技术上可无损合并（索引对齐），但"mod 房算不算正典"是**产品决策**。
4. **ut 13 条 `no-rule` 边**：同上。
5. 沿用第64轮遗留（人设线 N1~N4 等用户明天继续）。

---

## 7. 复检结论：**62 / 62 ALL PASS**

工具 `_tools/recheck65.py`（**只 `ast.parse`，不产 `.pyc`；不改变被测状态**），五组判据每组配负控制：

| 组 | 内容 | 结果 |
|---|---|---|
| ① 可编译 | 7 个 `.py` 全 `ast.parse` 通过 ＋ 负控制（坏源码必被拒） | PASS |
| ② JSON / 结构 | 5 份 JSON 可载入；`room_count == len(rooms)`；节点带 `work` 标签 | PASS |
| ③ 编码 | **无 BOM、无 U+FFFD**（含负控制：检出器可用） | PASS |
| ④ 恒真判据复查 | 分量守恒、跨作品边=0、负控制（伪造跨作品边被数出来） | PASS |
| ⑤ 逐令牌回验 | **30 个报告数字 ← 产物**（338/287/358/625/988/125/209/128/443/20/5/39…）＋ 负控制 | PASS |
| ⑥ 端到端 | `merge_bigmap65.py` 重跑退出码 0 | PASS |

**证据蒸馏**：把边引用到的 GML 出处文件拷进仓库 `_evidence/gml_evidence65/{ut,uty,ry}/`（**19 个**，77 KB，含 `_manifest.json`），
使仓内读者**不依赖 E 盘**即可自证每条 `explicit/cond` 边。
其中 `obj_doorA_Alarm_2` 是 SPECIAL 边的**代码位置标签**（非文件），已在 manifest 里标明。

**未跑 G2 回归的理由**：本轮**没有改动 `ralsei_pet/` 任何源码**（`git status` 仅新增本轮目录），G2 无对应增量。

---

## 8. 交付物清单

```
code-quality-audit/第65轮-黄魂并入Undertale大地图/
├─ _tools/
│   ├─ dump_uty65.csx / dump_utdoors65.csx   # UTMT 转储（黄魂 / 原版，含 A/B 锚点自动判定）
│   ├─ run_dump65.py                         # UTMT 驱动（stdout 落文件）
│   ├─ mk_utdoors65.py                       # 程序化生成原版脚本（避免复制漂移）
│   ├─ topo_build65.py                       # 通用拓扑构建器（房间+实例+gml → 边）
│   ├─ merge_bigmap65.py                     # ★ 大图合并 + 守恒判据 + 正/负/反向控制
│   ├─ distill_gml65.py                      # GML 出处蒸馏进仓
│   ├─ recheck65.py                          # ★ 交付前复检 62 项
│   ├─ build_topo65.py / _patch65.py         # 早轮构建与补丁（留痕）
├─ _evidence/
│   ├─ ut_topology65.json    (338 间 / 557 边)     178 KB
│   ├─ uty_topology65.json   (287 间 / 491 边)     162 KB
│   ├─ ry_topology65.json    (358 间 / 593 边)     169 KB
│   ├─ bigmap65.json         (★ 625 节点 / 988 边) 391 KB
│   ├─ bigmap65_ry_overlay.json (mod 增量房 + 5 连接点) 10 KB
│   └─ gml_evidence65/       (19 个 GML 出处 + manifest) 77 KB
└─ 第65轮报告-黄魂并入Undertale大地图.md            （项目根）
```

---

## 9. 口径修正建议（提请用户确认）

第64轮记下的 D2 是「**黄魂的地图直接和 undertale 的整合成一个大的**」。据本轮实证，建议把口径精确化为：

> 「**把 Undertale 原版(338)、黄魂(287)、以及《红与黄》mod 的 20 间增量房，整合进同一份大图数据结构；
> 三者按命名空间分治，跨作品连接点由产品侧显式指定，不由数据层臆造。**」

理由：① 黄魂与原版命名空间不相交，**游戏内本来就不通**；②《红与黄》是原版的 **mod（同命名空间）**，与黄魂不是一回事。

---

_报告完毕。本轮产物提交前已跑复检 **62/62**；提交与远端双向核验见 `.workbuddy/memory/MEMORY.md` §10 索引行。_
