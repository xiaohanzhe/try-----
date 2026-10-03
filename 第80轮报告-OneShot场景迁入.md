# 第80轮报告 — OneShot 场景迁入 + 层3 就寝接线

> 轮次：第80轮 ｜ 日期：2026-10-03 ｜ 分支：`main` ｜ 仓库根：`try - 副本`
> 用户裁决（逐字）：**「废除，默认打开，我现在不方便，先跳过，要」**
> 本轮 = 收尾第79轮遗留 + 执行该裁决的 3 项（废除 / 默认打开 / 要）+ 1 项跳过（chkdsk）

---

## 0. 一页结论

| 项 | 结果 |
|---|---|
| **① Q3「废除」** | ✅ `BEDTIME_HOME_SCENE='desktop'` 旧口径**已废弃**（注释声明 + 判据钉住）；NPC 就寝改**逐人决策** |
| **② 默认打开** | ✅ `NPC_AUTONOMOUS_MOVE` 默认 **False → True** |
| **③「要」= 场景补齐接 OneShot** | ✅ **OneShot 263 场景迁入**（索引 1,659 → **1,922**） |
| **④「先跳过」** | ⏭️ `chkdsk E: /f`（需用户管理员）**未做** |
| **回归** | ✅ **PASS=3778 FAIL=0 / 72 套，全部 IDENTICAL** |
| **附带发现并修正** | ★ **4 条预留令牌转正/封禁**（`sun`/`sky` 转正；`square`/`street` 封禁）+ **OneShot 几何并入** + **`meta.unknown_rooms` 同步** |

---

## 1. 层3：NPC 就寝（裁决 ①「废除」）

### 1.1 模型变化

| | 旧（≤第79轮） | 新（第80轮） |
|---|---|---|
| 谁决定睡觉地点 | 桌宠本人 | **每个 NPC 各自决策** |
| 判据 | 常量 `BEDTIME_HOME_SCENE='desktop'` | `npc_intent.choose_sleep_scene()` |
| 是否硬性回家 | 是（回桌面） | **否**（L4：可不回家、可睡朋友家） |

### 1.2 落地物

* `modules/npc_roam.py`
  * 新常量 `SLEEP_PHASE='night'`（只认 night，21:00 起）、`SLEEP_DWELL_SECONDS=6h`。
  * 新纯函数 `decide_sleep(now, *, phase, sleep_fn, npc_id, home, friends, reachable, last_sleep, cur_scene)` → `(scene_id | None, why)`。
    * 白天 ⇒ `(None,'day')`；无 fn / fn 抛异常 ⇒ `(None,'no_fn')`；返 None ⇒ `(None,'nowhere')`；
      返 `desktop` ⇒ `(None,'desktop_blocked')`（**桌面闸**）；等于当前场景 ⇒ `(None,'already')`。
  * `step()` 扩两个形参 `sleep_fn` / `sleep_enabled`，三步逻辑：① 到期 drop → ② 意图决策 → ③ **就寝**（夜里 + 本拍没挪窝才问）。
* `src/main.py`
  * 新增 `_npc_roam_sleep()`（唯一新接点，真调 `choose_sleep_scene`；异常 ⇒ `(None,'error')`）。
  * `_npc_roam_tick` 的 `step(...)` 加 `sleep_fn=self._npc_roam_sleep`。
  * `BEDTIME_HOME_SCENE` 处补「★★★ 旧口径**废弃**声明（第80轮，用户裁决③）」——明写 **NPC 完全不适用**。
  * `BEDTIME_*` 注释块补「这一段只管**桌宠本人**；NPC 走逐人决策」；`go_to_bed()` docstring 同步。

### 1.3 零回归结构保证

`enabled=False` ⇒ `step()` **一字节不改**（就寝也含在内）。`check79` 的 B 段（最贵一条）钉死：返回空 + 状态零变化 + 负控制（打开后同调用必须真产生变化）。

`check79` 新增 **J 段（J1~J12）**：`decide_sleep` 7 变体探针（白天/夜无fn/桌面/同处/别处/异常/None）+ 长驻留 + `sleep:` 前缀 + 挪窝不被覆盖 + 产品接线（含注入 + 负控制）+ 旧口径废弃声明 + 无 pet/user/player。

---

## 2. 默认打开（裁决 ②）

`main.py:2036` `NPC_AUTONOMOUS_MOVE = False → True`，注释补「第80轮**按用户裁决改成默认 True**（用户原话逐字：「**废除，默认打开**」）」。

启动日志两分支已就位，开时记：`NPC 自主移动：**开**（驻留层已启用；他们会有自己的位置）`。

> ★ 7 套既有基线的 DIFF **全部只是这一行日志**（`关` → `开`），零行为变化 ⇒ 已 `--update --only` 合并重固。

---

## 3. OneShot 263 场景迁入（裁决 ③「要」）

### 3.1 勘查（锚点优先）

`_tools/extract_oneshot80.py`（只读）：
* OneShot 是 **MonoGame / RPG Maker MV**，房数据**明文**（非 `data.win`）：
  `gamedata/maps/map<N>.tmx`（尺寸）+ `events_map<N>.json`（门）。
* **门机制** = RPG Maker `code 201 = Transfer Player`，`parameters[0]` = 目标 map id（与 Deltarune `obj_doorA~F` 同构）。
* **5 锚点自检全 PASS**：① 名字表 263 连续 ② `map2.tmx` 头 50×30 逐字 ③ `events_map2` 可解析
  ④ 伪造路径必不存在（负控制）⑤ 真 `map1` 在盘。
* 产出：**263 节点 / 826 门边**（全部落在 1..263 内，**0 悬空**；212 出边 / 206 入边 / 40 孤立）。

### 3.2 迁入（数据面）

`_tools/build80.py`：字段集**逐字对齐** Deltarune 分片场景
（`{name, name_raw, name_derived, original_room_id, bg, bg_source, objects}`）。
* 新增章 `oneshot`：`{id:'oneshot', name:'OneShot · 世界机器版', order:102, alias:'OneShot', tint:'#2a2036'}`。
* 新增区 `rooms`（`全部房间`）。
* 写 `_zone.oneshot.rooms.json` + `_index.json`。★ **263/263 字段逐条全等**。

**索引：1,659 → 1,922（+263，增量恰好）**；既有 8 章**逐值不变**。

### 3.3 明暗表（`_worlds.json`）

`_tools/worlds80.py`：**如实标 `unknown`**（照抄 UT/黄魂 —— 本轮只采了尺寸与门，**没采明暗**，
一个 `light`/`dark` 都不许猜）⇒ 263 间全 `unknown`。

> ★★ **本轮自查抓到一个我自己的遗漏**：首版只更新了 `areas` + `rooms`，**漏了 `meta.unknown_rooms`**
> ⇒ 被 `items_round48` 的 **F4** 判据抓红（**判据对、数据缺**）。
> 教训 = 「同一份事实两处写」的老坑；已改成由 `rooms` **派生** `meta`（单一真源），
> 并在 `worlds80.py` 里补了 `_sync_meta_unknown()`，重复跑幂等。

### 3.4 几何（★ 本轮新增的实修）

OneShot 的 TMX 里**本来就有**像素尺寸（`width × tilewidth`）⇒ 我把它**并入了**
`assets/scenes/_room_geometry.json`（键 `oneshot:<map_index>`，**px 口径与既有行一致**）。
* 1896 → **2159** 间（`stats` 加 `oneshot:263`）。
* 效果：`rooms_round47` 的 **B7「几何表未命中 == 0（房内行走可算）」** 从 263 未命中 ⇒ **0**。
* ★ 这是**真修**（不是放宽判据）：OneShot 房间现在**真能算尺寸**、房内行走可算。
* `n_layers` 未采 ⇒ 如实不写（与"字段可缺"约定一致）。

### 3.5 真装载验证

`_tools/verify_load80.py`（16 项）：走产品**唯一入口** `load_index()` + `load_scene(sid, entry=)`。
* ★ 关键坑：第一版 `load_scene(sid)` 得 **263 全 `None`** ⇒ 真因 = **分片场景必须给 `entry`（索引登记行）**，
  不给就只认独立文件。改 `load_scene(sid, entry=flat[sid])` ⇒ **PASS=16 / FAIL=0**。
* 真名（`Start` 等）、`original_room_id` 真带上。

---

## 4. ★ 附带发现：4 条预留令牌转正/封禁（判据随事实加强）

迁入 OneShot 后，`check73` D2 / `check77` D4 报红 —— 断言「预留令牌现网必须 0 命中」被打破。
**逐条核实**（`_evidence/probe80_tokens.json`）：

| 令牌 | 特质 | 命中 | 例 | 裁决 |
|---|---|---|---|---|
| `sun` | bright | 3 | `Sunroom` / `basement_after_sun` | ✅ **转正**（真有阳光） |
| `sky` | cosmic | 2 | `Red_sky` / `POSTGAME_RED_SKY` | ✅ **转正**（天空/空旷感） |
| `square` | crowded | 2 | `House 4 - squares`（**几何方形**）/ `SQUARES BE GONE`（**谜题名**） | ❌ **封禁**（`OMITTED`） |
| `street` | crowded | 5 | `Elevator Street` / `Vendor Street`（**街名**） | ❌ **封禁**（`OMITTED`） |

**口径**：与第73轮 `room`/`light` **同款判法** —— 词本身能命中但**语义错位** ⇒ `OMITTED`，
靠「不在任何令牌表里」挡；**不许为了让判据变绿硬塞进本位表**（那才是真"虚假宣传"）。

**副产品**：★ `cosmic` 特质**首次有了真实命中**（`Red_sky`）—— 用户点名的「破败这类词要有能力识别」
在 bright/cosmic 两个方向也**兑现了一部分**。

### 4.1 判据加强（不是放宽）

| 判据 | 旧 | 新（**更严**） |
|---|---|---|
| `check73` C2b | `bright`/`cosmic` **必须零命中** | **必须 > 0**（能力真到位） |
| `check73` C2b2（新） | — | 能力**只由转正令牌**兑现，预留槽**不许偷偷命中** |
| `check73` D2 | 预留令牌 0 命中（含禁词） | 0 命中，**先排除已扬弃禁词** |
| `check73` D3c（新） | — | `OMITTED` 禁词**运行期硬过滤**（不依赖人自觉） |
| `check77` D4/D5 | 同 C2b/D2 | 同款加强 |

★ `npc_life._match_terms` 新增**运行期闸**：`OMITTED` 禁词即使被误写进表也**进不了匹配**。

---

## 5. 回归收尾（7 套 DIFF 定性）

| 套件 | 现象 | 定性 | 处置 |
|---|---|---|---|
| `bg_round39` | A2b FAIL | 无溯源章写死 `['ut','uty']`+645 | 改**逐章事实对齐**（不写死章名/数字） |
| `rooms_round47` | B7 FAIL，263 未命中 | **真缺口** | **并入 OneShot 几何**（真修） |
| `items_round48` | F2/F4 FAIL | 写死 645/649 | 改"非 Deltarune 五章"派生 + **补 `meta.unknown_rooms`** |
| `check73` | D2 FAIL | 预留令牌转正事实 | 判据随事实加强 + 契约补 `round80_update` |
| `check77` | D4 FAIL | 同上 | 同款加强 |
| `objects_round44` | 分片 63→64 | ✅ 事实 | 重固基线 |
| `pathfind_round45` | 1,659→1,922 | ✅ 事实 | 重固基线 |

**最终：`PASS=3778 FAIL=0 / 72 套，全部 IDENTICAL`**（`check80` 35 PASS 首次入列）。

---

## 6. 判据侧 bug（本轮抓到 2 个）

1. **`check77` D2 含 `or True`** ⇒ **恒真判据**（看着在守其实没守）。已删除，改成真判据。
2. **`check73` D3c 第一版判错层** —— 写的是 `_token_hits('square', ...)`（纯匹配函数，无禁词逻辑 ⇒ 恒真）；
   真闸在 `_match_terms`。已改断言在**正确的缝**上（`_match_terms`/`trait_hits`）。

> 这两处**都不是报红暴露的**，是逐条核对时发现的 —— 印证「判据本身也是被测物」。

---

## 7. 交付物

### 7.1 代码
* `ralsei_pet/modules/npc_roam.py`（层3 就寝）
* `ralsei_pet/modules/npc_life.py`（令牌转正/封禁 + `_match_terms` 运行期闸）
* `ralsei_pet/src/main.py`（`NPC_AUTONOMOUS_MOVE=True`、`_npc_roam_sleep`、废弃声明）

### 7.2 数据
* `ralsei_pet/assets/scenes/_index.json`（+`oneshot` 章 263 场景）
* `ralsei_pet/assets/scenes/_zone.oneshot.rooms.json`（新建）
* `ralsei_pet/assets/scenes/_worlds.json`（areas + rooms + **meta.unknown_rooms**）
* `ralsei_pet/assets/scenes/_room_geometry.json`（+263 间）
* `ralsei_pet/assets/npc/_crossworld.json`（`round80_update`）

### 7.3 工具与证据（`code-quality-audit/第80轮-OneShot场景迁入/`）
* `_tools/`：`extract_oneshot80.py` / `build80.py` / `worlds80.py` / `verify_load80.py` / `check80.py`
* `_evidence/`：`oneshot80.json` / `build80.json` / `index_before80.json` / `worlds_before80.json`
  / `geometry_before80.json` / `worlds_before_meta80.json` / `probe80_tokens.json`

### 7.4 回归
* `regress/run_all.py`（注册 `check80`；更新 `check73`/`check77` 描述）
* `regress/baseline.json`（合并重固 14 套：层3 的 7 套 + 本轮 7 套）

---

## 8. 遗留（未做 / 待裁定）

| # | 项 | 状态 |
|---|---|---|
| A4 | `chkdsk E: /f` | ⏭️ **用户明确跳过**（"我现在不方便"） |
| — | 层4 存档（`plan`/`intent`/`RoamState` 落 `data_store`） | 待排期 |
| — | OneShot 区域层级（map name 无 `" - "` 前缀） | 待补 |
| — | OneShot 明暗表 | 待建（现全 `unknown`） |
| — | `Outertale` 场景迁入 | 未做（预留令牌仍 0 命中） |
| — | 跨作品贴图（`sprites/` 只有 `ghost/`） | 未抽 ⇒ 跨作品 NPC 画不出来 |
| B15/B14/B11/B8/B6 | 素材补采 / 瓦片 / 修 13 套件 / 预热 / 主线 NPC 自主开口 | 遗留池 |
| R5/R6/R1/R7 | Z 键附身 / 带灵魂走 / 每人一个家 / 原作菜单键位 | 遗留池 |

---

## 9. 收尾清单

* [x] 层3 就寝（废除旧口径）
* [x] `NPC_AUTONOMOUS_MOVE` 默认 True
* [x] OneShot 263 迁入（索引/明暗/几何/真装载）
* [x] 预留令牌 4 条转正/封禁
* [x] 7 套 DIFF 逐个定性 + 判据加强
* [x] 全量回归 72 套全绿
* [x] `check80` 35 项
* [ ] 记忆 / 待阅清单更新
* [ ] `gitpush.py` 推送
