# 第66轮报告 · 大图连通 + mod 并入 + N4 跨作品 NPC 注册

> 仓库根：`try - 副本`　|　轮次目录：`code-quality-audit/第66轮-大图连通与mod并入/`
> 用户授权（逐字）：「跨作品连接我不管你中间怎么转，**把地图联通就好**」「黄魂和 ut 那个**全部事件你自己决定**」「**mod 房接入正典图**」「N4 素材这类的不是在我给你发过的那个文件里吗」（澄清：「就是之前那个 onnshot.world.machine 的那个文件」）「人设我待会给你，你先干别的」

---

## 0. 一句话结论

三件事全部落地：

| # | 事项 | 结果 |
|---|---|---|
| ① | **大图连通** | 645 节点的真实图原本 **129 个连通分量**（最大 225）⇒ 用 **3 个 hub 节点 + 4 条 hub 边 + 127 条合成边** 连成 **1 个分量（648 节点）**。**真实边与合成边分开存**，合成边各自带 `reason`，原始分量统计**原样保留** |
| ② | **mod 并入正典** | 《红与黄》20 间增量房按**索引对齐**无损并入 ut 命名空间（**338 → 358 间**，338/338 同名同序），合并新增 **43 条**边 |
| ③ | **N4 注册** | OneShot 21 + Undertale 14 共 **35 条跨作品 NPC 注册进 `_registry.json`**（**35 → 70 条**）。此前它们**只到人设层** —— `_personas.json` 有 50 份人设，但注册表里没人 ⇒ @点名认不出、记忆不建档，属"有设无人" |

复检：`recheck66.py` **65/65 ALL PASS**；`recheck66_n4.py` **30/30 ALL PASS**；G2 全量 **ALL IDENTICAL**。

---

## 1. 本轮做了什么（按用户四条授权逐条对账）

| 用户口径 | 落地 |
|---|---|
| 「跨作品连接我不管你中间怎么转，把地图联通就好」 | ⇒ 允许**合成边**。做法：3 个 `hub:*` 节点 + 4 条 hub 边 + 对每个非主分量补 1 条 `hub-orphan`（共 127 条）。**合成边单独成表 `synthetic_edges`，绝不混进 `edges`** |
| 「黄魂和 ut 那个全部事件你自己决定」 | ⇒ 允许自治处理 66 条 `no-rule` 对象：**读全部事件**（不只 Create/Step），逐条判「非门」并给出可复核的代码证据 |
| 「mod 房接入正典图」 | ⇒ 《红与黄》20 间增量房并进正典（不是另起一张图） |
| N4：跨作品 NPC 归属素材 | ⇒ 用用户给的 `contacts_metadata.json`（OneShot 官方数据）；Undertale 侧用户没给对应文件 ⇒ 用磁盘上已有的 `UT素材/` **文件名**取证 |

---

## 2. ① 大图连通

### 2.1 问题：真实图是碎的

`topo_build65.py` 算出的真实边（只统计**代码里真有的转场指令**）把 645 个房间分成 **129 个连通分量**：

```
真实（real）：components = 129，largest = 225
  分量大小 top: 225 / 128 / 63 / 40 / 21 / 11 / 8 / 6 / 6 / 5 / 5 / 4 …
```

这**不是 bug**，是原作事实：很多房间是**剧情/flag 门控**的死胡同，或全靠运行期生成的转场（本轮新补的载体 ④）。

### 2.2 做法：hub 节点 + 合成边（真实边不动）

```
hub:desktop ──┬── hub:ut  ── ut:0   （Undertale 开场房）
              └── hub:uty ── uty:0  （黄魂开场房）
```

- **3 个 hub 节点**：`hub:desktop`（电脑桌面）、`hub:ut`、`hub:uty`
- **4 条 hub 边**：desktop→ut、desktop→uty、ut→ut:0、uty→uty:0
  → 语义 = 「桌面上通向该世界的门户（暗之泉式）」+「该作品的开场房」
- **127 条 `hub-orphan` 合成边**：每个**非主分量**补 1 条，把它挂回自己世界的 hub
- ★ **唯一豁免 = 入口房所在分量**（初版按"最大分量"豁免 ⇒ 唯一豁免的是**入口房那个分量**）

### 2.3 结果

```
with_synthetic：components = 1，largest = 648
```

⇒ **图已连通**。且三条性质都被复检钉住（见 §7）：
- **抽掉 hub + 合成边 ⇒ 回落 129 分量**（证明是它们承的重）
- **少补一条 ⇒ 破成 2 分量**（证明 127 条一条不多一条不少）
- **加冗余边 ⇒ 仍是 1 分量**（连通性对冗余不敏感）

### 2.4 新补的载体 ④：运行期动态创建门

第65轮认了三种门载体（结构偏移 / 显式逐房表 / 实例创建代码）。本轮补第 **四**种：

```gml
// 事件里**运行期**动态造一个门
var dr = instance_create(x, y, obj_doorway);
with (dr) { nextroom = 28; }
```

**代码实证 3 条**：`uty:27→28`、`uty:188→192`、`uty:201→199`。

★ 权威判据来自 UTY 的**读取端**：`obj_doorway` 碰撞时 `trn = instance_create(x,y,obj_transition); trn.newRoom = nextroom;`
⇒ **目标房只来自实例的 `nextroom`** ⇒ 图上没有 `obj_doorway` 的**来源房**不可能有 door-转场。

`by_evidence` 全表：

| 载体 | 边数 |
|---|---|
| `cc-nextroom`（实例创建代码，黄魂主机制） | 443 |
| `offset=+1` / `-1` / `+2` / `-2`（结构偏移） | 187 / 184 / 29 / 32 |
| `cond`（显式表 · 条件分支） | 145 |
| `uncond`（显式表 · 无条件） | 10 |
| `runtime-nextroom`（★本轮新补） | **3** |
| `special` | 1 |

---

## 3. ② 判非门：66 个对象「不是出口」

用户授权「全部事件你自己决定」⇒ 本轮把**所有事件**（Create/Alarm/Step/Draw/…）都扫一遍，凡**任何事件里都没有转场指令**的对象 ⇒ 不是出口，移出图并单独登记。

| 分类 | 条数 | 含义 |
|---|---|---|
| `non-door-superseded` | **57** | 同房**已有**真门（所以它是不是门不影响连通） |
| `code-not-dumped` | **6** | 转储里**没有任何事件文件** ⇒ 属**转储覆盖的真缺口**，如实登记 |
| `non-door-noexit` | **3** | 该房压根没有出口 |

`code-not-dumped` 6 个（**这条是"我们不知道"，不是"它不是门"**）：
`obj_darkruins_doorExit` / `obj_darkruins_doorLight` / `obj_market_exit` /
`obj_steamworks_03_door` / `obj_steamworks_05c_locker_door` / `obj_truelab_door`

**仍无解 4 条**（`dead-or-gated`，有转场代码但该房没有对应分支）：

| 作品 | 对象 | 房 |
|---|---|---|
| ut | `obj_door_s_musfade` | 123 |
| ut | `obj_door_t` | 297 |
| ry | `obj_door_t` | 272 |
| ry | `obj_door_t` | 297 |

---

## 4. ③ mod 并入正典（《红与黄》）

《红与黄》= **Undertale 原版 + mod**（不是黄魂 —— 第64轮曾混淆，A/B 锚点 0/3 报红，修正后黄魂 3/3、原版 4/4）。

- 原版 **338 间**与《红与黄》前 **338 间 同名同序**（`ry_base_same_order = 338`）⇒ 索引可直接对齐
- 《红与黄》另有 **20 间**增量房 ⇒ 并入 ut 命名空间：**338 → 358 间**
- 合并**新增 43 条**边（含 mod 对基础房的重路由）
- ★ 复检钉住：`ry 前 338 同名同序 = 338`（逐条比对，不是"差不多"）

---

## 5. ④ N4：35 条跨作品 NPC 注册

### 5.1 为什么必须做（本轮勘误）

第64轮把用户 30 万字原文里的 37 份人设抽进 `_personas.json`（**13 → 50**），但**只到了人设层**：

- `npc_persona.load_personas()` 的真源 = `_personas.json` 的 `personas[].file`
- **`_registry.json` 的 `persona` 字段没有任何运行时消费者**（只在 `to_dict` / `from_dict` 里过手）
- ⇒ 那 35 份人设"**有设无人**"：不进 `main._npc_aliases`（@点名认不出）、不进 `MiniMemory`（不建档）

### 5.2 字段取值（逐条有据，零臆造）

| 字段 | OneShot（21） | Undertale（14） |
|---|---|---|
| `id` | `_personas.json` 的 id（`os_*`） | `_personas.json` 的 id（`ut_*`） |
| `name` | contacts 的 `title` | persona 首行英文名 |
| `name_cn` | persona 首行中文括号（有才给） | 同左（UT 无括号 ⇒ = name） |
| `objects` | contacts 的 **`walkspriteId`（官方）** | `UT素材/` 文件名里的**原作 sprite 名** |
| `chapters` | `['oneshot']` | `['undertale']` |
| `home_world` | `'dark'` | `'dark'` |
| `tier` | `main`（有人设 ⇒ 走模型） | `main` |
| `needs_setting` | `False`（`persona` 非空） | `False` |

**★ `home_world` 为什么写 `dark`**：`NpcDef.__init__` 里 `home_world if home_world in ('light','dark') else 'dark'`
⇒ 写 `'oneshot'` 会被**静默改判**。本项目世界模型只有两分，两作品都归 `dark`。
**显式写 `dark`** 让读的人一眼看到真值，不靠"被静默改判"来发现（本项目最讨厌的那类惊喜）。

**★ `chapters` 为什么非空**（三条理由，缺一不可）：
① `can_follow()` = `bool(chapters)` ⇒ 空 = 不能跟随；
② `world_gate()` 暗世界分支遇空 chapters 直接 `REASON_NO_CHAPTERS` 拒绝；
③ 第49轮回归 `verify_npc49.B5` 硬断言 `all(n.chapters for n in REG.all())`。
当前**没有** `oneshot.*` / `undertale.*` 场景 ⇒ 这两个值是**未来场景前缀锚**（`scene_chapter()` 取 `split('.')[0]`）。

**净效果（复检实测）**：

| 场景 | 结果 |
|---|---|
| OneShot 角色进 `oneshot.*` | ✅ 放行 |
| OneShot / UT 角色进 `ch1~ch5.*` | ❌ 拒绝（**跨作品天然隔离**） |
| 跨作品角色上**电脑桌面** | ❌ 拒绝（不在白名单） |
| 对照 · kris 上桌面 / 进 ch3 | ✅ 放行（证明上面两条不是一刀切） |

### 5.3 OneShot 21 条（素材 = 用户给的 `contacts_metadata.json`）

26 条 profile / **21 个唯一角色**（`george1..6` 是同一角色 George 的 6 个变体）。区域分布：Barrens 4 / Glen 6 / Refuge 13 / `???` 3。

| id | 角色 | `objects`（官方 walkspriteId） | 区域 |
|---|---|---|---|
| `os_niko` | Niko | `niko` | ??? |
| `os_the_world_machine` | The World Machine | `en` | ??? |
| `os_the_author` | The Author | `clovers` | ??? |
| `os_prophetbot` | ProphetBot | `blue_npc_prophet` | Barrens |
| `os_silver` | Silver | `blue_npc_silver` | Barrens |
| `os_rowbot` | Rowbot | `contacts_rowbot` | Barrens |
| `os_prototype` | Prototype | `blue_npc_prototype` | Barrens |
| `os_calamus` | Calamus | `green_npc_calamus` | Glen |
| `os_alula` | Alula | `green_npc_alula` | Glen |
| `os_maize` | Maize | `contacts_maize` | Glen |
| `os_magpie` | Magpie | `green_npc_magpie` | Glen |
| `os_shepherd` | Shepherd | `contacts_shepherd` | Glen |
| `os_cedric` | Cedric | `green_npc_cedric` | Glen |
| `os_lamplighter` | Lamplighter | `red_lamplighter` | Refuge |
| `os_watcher` | Watcher | `contacts_watcher` | Refuge |
| `os_ling` | Ling | `contacts_ling` | Refuge |
| `os_mason` | Mason | `contacts_mason` | Refuge |
| `os_kelvin` | Kelvin | `contacts_kelvin` | Refuge |
| `os_kip` | Kip | `red_kip` | Refuge |
| `os_george` | George | `red_npc_george1` | Refuge |
| `os_rue` | Rue | `red_rue` | Refuge |

⚠️ 该文件是 Newtonsoft 风格序列化产物，**带尾逗号**（`,}` / `,]`）⇒ 标准 json 会解析失败，
先用 `re.sub(r',(\s*[}\]])', r'\1', raw)` 清洗。清洗后的蒸馏件在
`_evidence/oneshot_contacts66.json`。

### 5.4 Undertale 14 条（素材 = 磁盘上的 `UT素材/`）

用户**没有**给 Undertale 侧的 contacts 式文件 ⇒ 用 `UT素材/`（5,818 张 PNG / **2,213 个 sprite base**）的**文件名**取证。

| id | 角色 | `objects` | 取证方式 |
|---|---|---|---|
| `ut_toriel` | Toriel | `spr_toriel_d` | overworld 四向 |
| `ut_sans` | Sans | `spr_sans_d` | overworld 四向 |
| `ut_papyrus` | Papyrus | `spr_papyrus_d` | overworld 四向 |
| `ut_undyne` | Undyne | `spr_undyne_d` | overworld 四向 |
| `ut_alphys` | Alphys | `spr_alphys_d` | overworld 四向 |
| `ut_napstablook` | Napstablook | `spr_napstablook_d` | overworld 四向 |
| `ut_monster_kid` | Monster Kid | `spr_mkid_d` | overworld 四向（★ 原作前缀是 `spr_mkid_`） |
| `ut_asgore` | Asgore Dreemurr | `spr_asgore_d` | overworld 四向 |
| `ut_frisk` | Frisk | `spr_f_maincharad` | overworld 四向（★ 原作用的是 `spr_f_mainchara*`） |
| `ut_chara` | Chara | `spr_charad` | overworld 四向（★ 命名不带下划线分隔） |
| `ut_muffet` | Muffet | `spr_muffet_overworld` | 原作用 `overworld` 标的那一版 |
| `ut_mettaton` | Mettaton | `spr_mettatonb` | ★ **nearest_base** |
| `ut_flowey` | Flowey | `spr_floweyfly` | ★ **nearest_base** |
| `ut_gaster` | W.D. Gaster | `spr_gasterblaster` | ★ **nearest_base** |

★ 最后 3 条 **在本素材集里没有 overworld 四向图**（Mettaton / Flowey / Gaster），
取的是最接近本体的原作 sprite，并在 `notes` + `_evidence/ut_sprites66.json` 的 `how` 里
**如实标注**（`nearest_base`）—— **不假装是行走图**。

**口径说明（写进 `notes` 与 `_registry.json.source`）**：
OneShot 登记的是官方 `walkspriteId`，UT 登记的是原作 **sprite 名**（`spr_*`），
Deltarune 登记的是 GameMaker **对象名**（`obj_*`）⇒
`objects` 的语义 = **「该作品里标识这个角色的资源名」**，跨作品各自如其所是。
（UT 侧若将来补做对象名转储，可再校正为 `obj_*`。）

### 5.5 站位表同步

35 条新增 NPC **不属于 Deltarune 任何房间**（没有 `obj_npc_*` 站位脚本、没有原作坐标）
⇒ 如实挂进 `_placement.json` 的 `unplaced`（1 → **36** 条），**不给他编一个安身之所**。
`counts.unplaced` 同步为 36。

---

## 6. 判据修正记录（5 处 —— **既有套件**的判据，全是"判据过窄"，不是产物问题）

> 本轮另有 **2 处**判据/夹具失手出现在**新写的记忆复检脚本**里（M2 过窄、M6b 负控制夹具自踩坑），
> 见 §7.5。合计 **7 处**，**零产物错**。

| # | 位置 | 原来 | 改成 | 为什么 |
|---|---|---|---|---|
| 1 | `check55.py` R1 | `len(reg) == 35 and main == 17 and plain == 18` | `≥ 基线(35/17/15)` + **分层守恒** + **id 唯一** | 数字不是要守的东西；要守的是"没被削"+"分层没丢人"+"**加条目时没加重复**"（后者比原判据更强） |
| 2 | `check55.py` W11 | `len(pet.npc_registry) == 35` | `>= 35` | 同上 |
| 3 | `check56.py` D6 | 描述里写死"35 个" | 去掉数字（判据体未动） | 描述与事实脱节 |
| 4 | `check56.py` D7 | `_unpl_ids == {'knight'}` | 加"排除 `os_`/`ut_` 前缀"口径 ⇒ **Deltarune 侧只剩 knight**；**新增 D7b** 守"跨作品那批确实挂在 unplaced 且理由非空" | **意图一个字没动**（"不给他编安身之所"），只是名单变大 |
| 5 | `check57.py` A5 | 判据名写死"注册表 **35 条** NPC 的 model 全为 None"（实测 n=70 却照样 PASS） | "注册表**每条** NPC…" | ★ **判据名与事实脱节 = 本项目头号坑**。判据体本就只锁下限，名字里的条数拿掉 |

> 与 R6/R8 的第64轮修正记录、第49轮 B7b 是**同一套做法**：判据**形状**改，被期待的**事实锚点**随事实走。
> ★ 第 5 条特别值得记：它**不是报红暴露的**，是我逐个核对 DIFF 时发现的 —— 说明"DIFF 必看"这条纪律有用。

---

## 7. 复检结论

### 7.1 `recheck66.py` → **65 项 ALL PASS**

> ★ ① 段的"可编译"是**按 `_tools/*.py` 动态枚举**的 ⇒ 本轮新增 `recheck66_mem.py` 后由 **64 → 65**。
> （初稿正文里写死"64 项"，属**判据计数与事实脱节**的同族问题，已在同一轮改掉。）

| 组 | 内容 |
|---|---|
| ① | 全部 `.py` 可 `ast.parse`（不产 `.pyc`）+ 全部 `.json` 可 `json.load` + 负控制"坏源码必被拒" |
| ② | 无 BOM / 无 U+FFFD + 负控制"检出器可用" |
| ③ | 结构自洽：nodes 645 / edges 1034 / 边两端都在节点里 / `non-door-superseded` 全部"同房已有真门"（配负控制"能抓出伪造样本"） |
| ④ | **连通性三条**：抽掉 hub+合成边 ⇒ **回落 129 分量**；少一条 orphan ⇒ **破成 2 分量**；加冗余 ⇒ **仍 1 分量** |
| ⑤ | **逐令牌回验**：报告里每个数字 ← 产物（645 / 1034 / 129 / 548 / 338 / 66 / 57 / 6 / 4）+ 负控制"错 token(999) 必 FAIL" |
| ⑥ | **判非门判据的判别力（真实回查源码）**：★ **只读仓内蒸馏副本**（见下）+ 抽查 8 条无转场指令 + **正控制 2**（`obj_hiddenentrance_Step_0` 运行期 `nextroom = 28`；`obj_door_t_Alarm_2` 的 `room_goto` 表）+ **反向控制**（`obj_doorway` 是**读取端**，判据**不该**命中） |

### 7.2 ★ GML 蒸馏（本轮的一个**纠错**）

`recheck66.py` 的 ⑥ 段原先直接读 `E:\Download\_extract61\...`（**外部盘 + 用后即删的转储区**）
—— **违反铁律**（回归/复检不许依赖外部盘：盘一掉线，判据要么报红、要么**静默变成假绿**）。

已用 `_tools/distill_gml66.py` 把 ⑥ 段要读的 **105 个 GML** 蒸馏进
`_evidence/gml_evidence66/`（ut 23 / uty 60 / ry 22，缺 0），复检改为**只读仓内**，
并补 2 条判据：**蒸馏守恒**（仓内 105 == manifest 记的 105）+ **负控制**（目录真在仓内）。

### 7.3 `recheck66_n4.py` → **30 项 ALL PASS**

| 组 | 内容 |
|---|---|
| A | 70 条 / 分层守恒 / id 唯一 / `counts` 一致 / `source` 记明第66轮 |
| B | **反向控制**：抽掉 `os_`/`ut_` 条目 ⇒ **回到 35 条**；留下的 35 条无跨作品 id；三条 Deltarune 代理仍在（防"清空造成的假 PASS"） |
| C | OneShot 21 条**逐条**回验 `objects == contacts.walkspriteId` + `chapters` + persona 文件 |
| D | UT 14 条**逐条**回验素材文件名证据 + `how` 如实标注（10 四向 / 1 overworld_tagged / 3 nearest_base） |
| E | `world_gate` **正 / 负 / 对照成对**（6 条） |
| F | **人设贯通**：35 条的新 NPC，加载器**真能取到**人设（不再"有设无人"）；`needs_setting ⇔ persona is None` |
| G | 站位表对齐（D6 口径）+ 跨作品 36 条理由非空 + **Deltarune 侧仍只有 knight** |
| H | `home_world` 磁盘字面就是 `"dark"`（不是被静默改判） |

### 7.4 G2 全量回归

**56 套件 · ALL IDENTICAL**（失败 0）。其中 6 个套件（`npc_round49` / `soul_round55` /
`npc_persona55` / `npc_place56` / `model_conc57` / `bubble_round50`）因本轮的**有意改动**
用 `--update`（**合并模式**，只重建选中的 6 个）重建了基线；
**每个 DIFF 都逐条核对过**，全部是预期内的计数变化（35→70、17→52、未安置 1→36、别名 81→154 等）。

### 7.5 `recheck66_mem.py` → **16 项 ALL PASS**（记忆文件复检）

本轮改了速查本（§4 记自纠两例 / §10 索引加 66 / §11 N1~N4 转"已裁定" / 头部段号 §0–§62）。
按用户对记忆的门槛（**实证或被要求 + 先补详版 + 逐令牌回验 + 改动守恒**），补了这份复检。

| 组 | 内容 |
|---|---|
| M0–M3 | 三份输入齐 / `js_len = 9888 ≤ 10000`（余量 112）/ 头部段号 == 详版实际最大段号 / 详版 §62 的 62.1~62.12 全在 |
| M4–M5 | §10 索引含 66 及本轮三个数字 / §11 的 N1~N4 四条裁定都在 |
| **M6** | ★ **反向**：本轮**被删令牌 = `toks(改前) - toks(改后)`**（**自动 diff**，不是我手列）⇒ 28 个里 **22 个宽式命中详版**、**6 个走白名单**、**未处置 0** |
| M6a/M6b0/M6b | **no-op 控制**（自动命中数 > 0）+ **负控制夹具自证**（4-gram 真阴性）+ **负控制**（伪造令牌不命中） |
| M6c | 白名单**不免检**：6 条的**锚点必须真在详版**（如 `nextroom=N;xx=..;yy=..` 的锚点 = §61.2.2 的 `xx = 160`） |
| M7–M9 | 本轮新增 10 个令牌全在速查本 / 无 BOM 无 U+FFFD / 快照 LF-only |
| M10 | **改动守恒**：净增 **+114**（9774 → 9888，额度 200）+ 余量 ≥ 100 |
| M11 | **结构自检**：§0~§11 标题全在、严格递增、无粘连 |

> ★ 两个**可复跑**设计，直接对应本项目踩过的坑：
> ① 改前版本**不能用 `git show HEAD:`** 现算 —— 本轮一 commit，HEAD 就变成"改后"、diff 变空、
>   判据**静默失效**（恒真判据的另一种形态）⇒ 改成**快照入库** `_evidence/mem_quick_before66.md`；
> ② 反向判据**不能手列令牌**（第一版手列 16 个，把"轮次标签"也列进去了 —— 那 6 个
>   `相机+换房`/`道具背包`/… **本来就还在速查本 §10**，前提就错）⇒ 改成**自动 diff**。

**本轮判据侧第 6~7 处失手（都在这份新脚本里，同一轮修掉）**：

| # | 表象 | 真凶 | 处置 |
|---|---|---|---|
| 6 | M2 报 `头部 §0–§62 但详版 max = 56` | 判据**过窄**：详版标题两种写法混用（`## §57 …` 与 `## 56. …`），正则 `^##\s+(\d+)` **吃不到 `§` 前缀** | 改 `^#{2,3}\s*§?(\d+)` |
| 7 | M6b 负控制报红（`cjk=subphrase:在详版里`） | **夹具自己踩坑**：伪造串里含 `在详版里` —— 这是**文档本身的高频措辞**，必然命中 | 换**生僻字**（`彘鬻鱻麤龘靐齉爩虪黐`）+ 新增 **M6b0 夹具自证**（先证明夹具是真阴性再用） |

> 第 7 条与第64轮 `W22`、本轮 §6 的第 5 条同源：**「判据/夹具本身也是被测物」**。


---

## 8. 产物清单

```
code-quality-audit/第66轮-大图连通与mod并入/
├─ _tools/
│   ├─ build66.py            主构建器：补载体4 + 判非门 + hub/合成边 + mod 并入
│   ├─ probe_norule66.py     诊断：66 条 no-rule 对象的分类（★依赖转储，一次性）
│   ├─ probe_norule_deep66.py 诊断：逐对象读全部事件
│   ├─ recheck66.py          ★复检 65 项（① 段按 `_tools/*.py` 动态枚举；只读仓内 GML）
│   ├─ distill_gml66.py      ★把 ⑥ 段要读的 105 个 GML 蒸馏进仓
│   ├─ collect_n4_66.py      ★N4 取证：OneShot contacts 蒸馏 + UT sprite 取证
│   ├─ reg_npcs66.py         ★N4 注册器（含**等价性锚点**：dumps 必须逐字节重现原文件）
│   ├─ recheck66_n4.py       ★N4 复检 30 项
│   └─ recheck66_mem.py      ★记忆文件复检 16 项（速查本 vs 详版，含自动 diff + 负控制）
└─ _evidence/
    ├─ bigmap66.json                  645 节点 / 1034 边 / 真实 129 分量 → 1 分量
    ├─ norule_probe66.json            66 条判非门（分类+证据）
    ├─ norule_deep66.json             逐对象全部事件的扫描明细
    ├─ oneshot_contacts66.json        ★OneShot 官方 contacts 蒸馏（26 profile）
    ├─ ut_sprites66.json              ★UT 14 角色 sprite 取证（含 evidence 文件名）
    ├─ mem_quick_before66.md          ★改前的速查本全文（记忆复检的可复跑基线）
    └─ gml_evidence66/                ★105 个 GML + _manifest.json
```

产品侧改动（**只有数据，零代码改动**）：
- `ralsei_pet/assets/npc/_registry.json`（35 → 70 条；`counts` / `source` 同步）
- `ralsei_pet/assets/npc/_placement.json`（`unplaced` 1 → 36；`counts.unplaced` 同步）

回归侧改动（判据修正，见 §6）：`check55.py` / `check56.py` / `check57.py` / `regress/run_all.py` + `baseline.json`

记忆侧改动（受 `recheck66_mem.py` 16 项复检约束，见 §7.5）：
- `.workbuddy/memory/MEMORY.md`（速查本）：§4 +2 条自纠 / §10 索引 65→66 / §11 N1~N4 转"已裁定" / 头部段号 §0–§62
- `.workbuddy/memory/参考-契约与历轮（详版）.md`：新增 **§62**（62.1~62.12）

---

## 9. 遗留 / 待裁定

| # | 事项 | 状态 |
|---|---|---|
| 1 | **N1** 幽灵亮暗的「决心」当量 | ★ 用户已给口径 = **「和 Kris 等人接触的时间」**（此前建议是"Ralsei↔用户信任度"，**用户改口径**）。`relationship.py` 已有接触时长可复用 ⇒ **待落地** |
| 2 | **N2** 幽灵 alpha | ★ 用户已给口径 = **定点距离式**（采纳建议，**照抄原作** `min(10/(dist+1), 0.9)`）⇒ **待落地** |
| 3 | **N3** `sprites/ghost/` 接线时机 | ★ 用户「你来看就好」⇒ **我定：等 N1/N2 一起做**（素材先放着） |
| 4 | **UT 侧 `objects` 口径** | 现在是 **sprite 名**（`spr_*`）。若将来补做 UT 的 `obj_*` 对象名转储，可校正为与 Deltarune 同体系 |
| 5 | `code-not-dumped` 6 个对象 | 转储里**没有任何事件文件** ⇒ 属转储覆盖的真缺口（要重跑 UTMT 才能判） |
| 6 | 仍无解 4 条（`dead-or-gated`） | 有转场代码但该房无对应分支 ⇒ 已如实登记，不再臆造 |
| 7 | 人设原文 | 用户「待会给你」 |
| 8 | 既有遗留 | `ralsei_pet/` 真机实测（#63/#64）、扩展前技术债（#114）等 |

---

## 10. 一句话收尾

本轮把「**地图联通**」这条硬要求做实了（129 → 1 分量，且真实边/合成边分开存、三条连通性性质可复现），
把《红与黄》并回正典（338 → 358），并把 **35 条跨作品 NPC 从"有设无人"变成真注册**
（35 → 70，且 `world_gate` 的正/负/对照全部实测过）。
过程中**纠了自己两个错**：① `recheck66.py` 依赖 E 盘转储（违反铁律）⇒ 蒸馏 105 个 GML 进仓；
② `check57.py` A5 的判据名写死"35 条"（判据名与事实脱节）⇒ 改掉。
两者都不是产物错，但都属于"**判据/证据链**"这一层，按纪律同一轮修掉。

收尾时给**记忆文件**也补了一份复检（`recheck66_mem.py`，16 项 ALL PASS）。它自己又暴露了
**两处判据侧失手**：③ 头部段号判据的正则吃不到详版标题的 `§` 前缀（**判据过窄**）；
④ 负控制的伪造串里混进了 `在详版里`（**夹具自己踩坑**，必然命中）⇒ 换生僻字 + 加"夹具自证"。
⇒ 本轮累计 **4 处判据/夹具侧失手，零产物错**，与第 62/63/64 轮的规律一致：
**出问题的地方几乎总是在"判据"这一侧，而不在被测的东西上。**
