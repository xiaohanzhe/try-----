# 第81轮报告 · OneShot 区域层级（6 区）+ 层4 存档

**日期**：2026-10-03
**仓库根**：`C:\Users\23002\Desktop\项目文件夹\try - 副本`
**用户裁决（逐字）**：
> **「按照我之前的决策和你的建议来就好」**
> 区域口径 → **「5 区（推荐）」**
> 层4 落盘范围 → **「全量：计划+驻留+last_sleep（推荐）」**

---

## 0. 一句话

把 **OneShot 从"一个房间区"拆成 6 个区域**（按官方三源互证），并把 **NPC 自主生活的
层1/2/3 状态（意图 / 驻留 / 昨晚睡哪）第一次落盘**——桌宠重启后 NPC 不再失忆。

---

## 1. 先说一个前提修正（我上一条建议里有错）

我在上一轮建议里写「OneShot 需要**明暗表**（light/dark）」。**这是错的，已撤回。**

**取证结论**：OneShot 的房数据里**没有** light/dark 维度。

| 我原以为 | 实际（三源取证） |
|---|---|
| 需要一套 light/dark 分区 | 房数据只有 **4 个官方区域**（`map_colors.json`），**没有**第二维度 |
| `*_light` 是"光世界"标记 | `red_water_light` / `start_carpet_light` 是 **autotiles**（同一张图里 base 与 light **成对出现**，75 张图）⇒ 是**场景内美术层次**，不是两个世界 |

⇒ **`check80` E3「263 间全 unknown，一个 light/dark 都不许猜」恰好正确，无需改动。**
我把 Deltarune 的光暗概念错套到 OneShot 上了。

---

## 2. 官方区域事实源（4 份明文，三源互证）

| 文件 | 内容 | 角色 |
|---|---|---|
| `gamedata/oneshot_map_colors.json` | `{mapColors:[{name,color,maps[]}]}`，4 组（purple 69 / red 82 / green 55 / blue 35） | **分区主源** |
| `gamedata/oneshot_map_zone_names.json` | `{"Blue":"The Barrens","Green":"The Glen","Red":"The Refuge","RedGround":"The Refuge (Surface)"}` | 英文名 |
| `gamedata/oneshot_minimap_nodes.json` | `{zones:{Blue/Green/Red/RedGround}}` | **官方邻接图（最权威）** |
| `gamedata/loc/zh_cn/map_zone_name_strs.po` | 官方中文：`荒野 / 幽谷 / 城市 / 城市（地表区）` | 中文名 |

> ★ 以上 JSON 是 **RPG Maker MV 的 JS 字面量**（trailing comma），标准 `json` 解不了
> （11/18 个文件带尾逗号）。勘查脚本自带容错解析（**仅在字符串外部生效**），
> 并过了 **11 项锚点**（7 个标准文件 `strict==tolerant` 零改写 / 正负控制 / 双源键相等）。

---

## 3. 6 区方案（覆盖 263/263，两两零交集）

| 官方 key | slug | 中文 | 间数 |
|---|---|---|---|
| `Blue` | `barrens` | 荒野 | 35 |
| `Green` | `glen` | 幽谷 | 55 |
| `Red` | `refuge` | 城市 | 73 |
| `RedGround` | `refuge_ground` | 城市（地表区） | 9 |
| `Purple` | `mainline` | 主线 · 家/塔/终局 | 69 |
| `UNZONED`（汇总） | `unzoned` | 未分区（废弃/调试/演示） | 22 |
| | | **合计** | **263** |

* **优先级**：`minimap_nodes` 四区（官方邻接图）> `map_colors` > `unzoned`。
  `RedGround`(9) 是 `red` 的子集（地表层特化），minimap 优先 ⇒ Red 计 **73**（82−9）。
* **未分区 22 间的名字自带证据**：`IGNORE`(×7) / `UNUSED` / `Lobby-OLD VER` /
  `stairwell-demo` / `C1~C7` / `pshot` …… ⇒ 是废弃/调试/演示房，不是真区域。
* ★★ **区域 slug 零令牌命中**：实测 6 个 slug（barrens/glen/refuge/refuge_ground/
  mainline/unzoned）**全部不在** `npc_life.trait_hits` 的令牌表里 ⇒ 改 scene_id 前缀
  对场景特质**零影响**（逐键 diff = **0 条**，证据 `_evidence/traits81.json`）。

---

## 4. 改了哪些文件

| 文件 | 改动 |
|---|---|
| `ralsei_pet/assets/scenes/_index.json` | `chapters.oneshot.areas`：1 个 `rooms` → **6 个区域** |
| `ralsei_pet/assets/scenes/_worlds.json` | `areas.oneshot` 同步 6 键（全 `unknown`）；`rooms.oneshot` 263 间**不动** |
| `_zone.oneshot.<area>.json` ×6 | **新增** 6 个分片；旧 `_zone.oneshot.rooms.json` **已删**（备份在 `_evidence/`） |
| `ralsei_pet/modules/npc_plan_store.py` | **新增**（层4 落盘容器，零依赖） |
| `ralsei_pet/modules/npc_roam.py` | `WIRING`：清空 `not_yet` + 登记 `npc_plan_store` |
| `ralsei_pet/modules/npc_intent.py` | `WIRING`：`wired` 翻正 + 清空 `not_yet` |
| `ralsei_pet/src/main.py` | 层4 接线 7 处（见 §5） |
| 第80轮回归锁（`check80.py` / `verify_load80.py`） | **区域无关化**（13 处判据改得更严） |
| 第79轮回归锁（`check79.py`） | **I3 判据随事实改**（见 §7） |

---

## 5. 层4 存档：接线点（`main.py`）

| # | 位置 | 做了什么 |
|---|---|---|
| 1 | import 区 | `from modules import npc_plan_store as npc_plan_store_mod` |
| 2 | 类常量 | `NPC_LIFE_FILE = 'npc_life.json'` + `NPC_PLAN_SAVE_EVERY = 120.0` |
| 3 | `init_npc_systems` | 预声明 `self.npc_plan_book = Book()`（**不是 None**）+ 读回 `load()` + **驻留表灌回** |
| 4 | `_npc_roam_decide` | `plan = book.plan_of(npc_id)` → `decide(last=plan.intent)` → `plan.note(it)` |
| 5 | `_npc_roam_sleep` | `last_sleep = book.last_sleep_of(npc_id)`（调用方没给时）→ 决策后 `note_sleep()` |
| 6 | `_npc_plan_file` / `_npc_plan_save` | 路径注入（`data_store.app_file`）+ 节流落盘 + **原子写** |
| 7 | `_npc_roam_tick` 末尾 + 退出收尾 | `moved/expired` 非空 ⇒ `_npc_plan_save()`；退出时 `force=True` |

> ★★★ **纪律**：`npc_plan_store` **不 import `data_store`**（初始化环，本项目栽过 4 次）
> ⇒ 路径由 `main` **注入**（与 `_make_relationship` / `_ghost_state_path` 同规）。

### 5.1 层4 解决了什么（"函数写对了 ≠ 产品用上了"）

* 层4 **之前**：`_npc_roam_decide` 用 `last=None` **硬编码** ⇒ 决策**无记忆**；
  `choose_sleep_scene(last_sleep=...)` 的"连睡同一处 ×0.6 降权"**永远拿不到值**。
* 层4 **之后**：两处都从档案里取值 ⇒ **闭环成立**（见 §6 的 E1）。

---

## 6. 验证（全部真跑，不是推算）

| 证据 | 结果 |
|---|---|
| `_evidence/层4接线探针81.txt` | **33/33 PASS**（A 结构面 25 项 + B 行为面 8 项，真 exec 抽出的真函数体跑在假宿主上） |
| `_evidence/层4往返实测81.txt` | **26/26 PASS**（真 `save()` → `load()` → 驻留/规划/`last_sleep`/意图全还原 + 5 例容错） |
| `_evidence/check81回归锁81.txt` | **50/50 PASS**（回归锁） |

### 6.1 ★★★ 闭环证明（E1，最贵的一条）

```text
             400 天里选"自己家"的次数
无记忆（last_sleep=None）        76 次
昨睡朋友家后（last_sleep=朋友家） 104 次     ⇒ 降权真生效（朋友家被 ×0.6 削）
```

★ **负控制**：只有一个地点时（家 == 朋友家）降权**无可比较** ⇒ 两次皆 400/400（判据非恒真）。

---

## 7. 判据侧的两处修正（"判据本身也是被测物"）

> 本轮**零产物错**，但改了 2 处**判据侧**问题。这与第 62~70 轮的历史规律一致。

### 7.1 `check79` I3 —— 判据过窄（会误报）

* **旧判据**：`not_yet` 必须**非空**（第79轮时层3/层4 确实没做完，写字是对的）。
* **本轮事实**：层4 做完 ⇒ `not_yet` **真的空了** ⇒ 旧判据**过窄假红**。
* **修法**（**不弱化鉴别力**）：`wired=True` ⇒ ① `used_by` 非空；② **若 `not_yet` 为空，
  则 `wired_how` 必须写明层4 落盘接线**（`npc_plan_store`）。
  ⇒ 既证"真做完了"，又挡住"没做却偷偷清空 `not_yet`"。
* **鉴别力实测**：4 态验证 —— 现状 ✅ / 旧态 ✅ / **偷清 not_yet ❌** / **wired=False ❌**。
* 同规先例：第70轮 `check57` A9 上限随事实改 / §60.3「判据过窄 = 会误报」。

### 7.2 我自己写的探针 / 实测里的 3 处判据 bug（真跑抓出）

| 探针 | 症状 | 根因 | 修法 |
|---|---|---|---|
| `probe81_layer4` A17 | 恒假 | `kw_present()` 查的是**调用侧 keywords**，我却拿它查 `def` 的**形参** | 改查 `node.args.args` |
| `probe81_layer4` B 段 | `NameError` | 两个方法**各编译一份 globals** ⇒ `npc_intent_mod` 只塞进去一半 | 共用一份 globals（与真模块同语义） |
| `roundtrip81` 第 3 项 | 方向写反 | 我把"降权后自己家更常被选"的**方向**写成了 `<` | 改成 `hits['none'] < hits['friend']` |

★ 三处**都不是报红暴露的**（A17 是报红、另两处是报红/静默），全靠**真跑一次数输出**抓到
——印证「判据真跑一次比推算可靠」。

---

## 8. 区域改造的后置影响（已全部处理）

| 受影响处 | 处理 |
|---|---|
| 第80轮 `check80.py`（8 处） | 改**区域无关**（`_all_scenes_of` / `_area_ids_of`），E1 由"== `{rooms}`"改**集合相等**（更严）⇒ **35/35 PASS** |
| 第80轮 `verify_load80.py`（5 处） | 同上 + S11 改"6 个分片全在位" / S11b"旧分片已退场" ⇒ **17/17 PASS** |
| `objects_round44` A2 | 分片数 61 → **69**（+6 OneShot 新分片 +2 UT/黄ty）⇒ 判据早已是**下界**，只 DIFF 不 FAIL，属事实变化 |
| `check73` C1/C1b/C2 | 松口径 id 键 **1963 → 1969**（+6 区域名）；真场景口径 1922 与全部分布**逐值不变** |

★ 两处 DIFF **不是报红暴露的**，是逐条核对 DIFF 文件时确认的（DIFF 必看）。

---

## 8b. 收尾：7 个 DIFF 定性 + 一处"静默不比对"真隐患

### 8b.1 7 个 DIFF 全部定性为「事实变化」，零真回归

| 套件 | DIFF 内容 | 定性 |
|---|---|---|
| `round5_smoke` | 待导入模块数 65 → 66；多一行 `[ OK ] npc_plan_store` | 新模块入列（count-agnostic，仅记录） |
| `round8_anim` | 多一行日志 `NPC 生活档案：…` | 层4 新增日志 |
| `soul_round55` | 同上 | 同上 |
| `npc_persona55` | ① W1 import 列表多 `modules.npc_plan_store`；② 同上日志 | 同上 |
| `npc_place56` | 同上日志 | 同上 |
| `check67` | 同上日志 | 同上 |
| `check78` | G3 被测文件体积 21236 B → 21634 B | `check78.py` 自身被改过 |

★ 顺手抓到产品文案缺陷：新日志原文多一个右括号（`内存态（不落盘））`）
⇒ 已修 `main.py:2264` 为 `内存态-不落盘`。**这条是读 DIFF 原文才看见的**，
不是报红暴露的 —— 再次印证「DIFF 必看」。

### 8b.2 ★★★ 抓到一处"静默不比对"（本轮最值钱的一条）

* **现象**：单跑 `--only check80` 却打印 `BASELINE`（既非 `IDENTICAL` 也非 `DIFF`）。
* **根因**：`run_all.py:2143` 的比对分支是
  `if args.update or old is None: cmp_txt = 'BASELINE'`。
  `check80` 上段已入列 `SUITES`，**却从未 `--update` 固基线** ⇒ `old is None`
  ⇒ **永远打印 `BASELINE`**。它看起来完全正常，**实际根本没在比对**。
* **实证**：`baseline.json` 只有 **72** 条，`SUITES` 有 **73** 个 —— 差的就是 `check80`。
* **修法**：① `--update --only check80` 补固（基线 72 → 73）；
  ② 在 `check81` 加**常驻锁 G5/G5n**：断言
  `基线套件集合 == SUITES 的 id 集合`（AST 取 id，不吃字符串自指），
  配负控制「摘掉一个真 id 后缺集必须非空」。
  ⇒ `check81` 50 → **52 PASS**。
* **同规先例**：`run_all.py:2044` 自己的注释就在讲这个坑
  （「……`BASELINE`（无从比对），而输出看起来一切正常」）。

---

## 9. 待办（未获放行、不得抢跑）

* **Q2**：Outertale 53 采样是否够 / Outertale 场景迁入 / 跨作品贴图（`sprites/` 只有 `ghost/`）
* **R5 / R6 / R1 / R7**：Z 键附身 / 带灵魂走 / 每人一个家 / 原作菜单键位
* **B6 / B8 / B11 / B14 / B15**：主线 NPC 自主开口 / 预热 / 修 13 套件 / 瓦片 / 素材补采
* **待用户裁决**：A1「留了两个任务在等待发送里」/ A2 黄魂 `黄魂：` 标题后 12 行归属 /
  A3 黄魂缺 Toriel 是否补 `hy_toriel`
