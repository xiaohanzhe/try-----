# 第114轮 · 证据：差事「世界门控 + 派发入口 + 独立落盘」

> 生成时间：2026-10-14（收尾跨到 10-15 凌晨）
> 代码：`ralsei_pet/modules/npc_system.py`（别名归一）· `ralsei_pet/src/main.py`（门控/入口/落盘）·
> `ralsei_pet/modules/dialogue_ui.py`（对话层接线）· `ralsei_pet/modules/npc_errand.py`（上一轮新增，本轮只消费）
> 判据：`_tools/check114.py`（**84 PASS / 0 FAIL**）｜变异：`_tools/mutate114.py`（**22 变异 / CAUGHT=21 / MISSED=0 / SKIP=0 / no-op=1**）
> 真机：`_tools/rec114.py`（**58 PASS / 0 FAIL ｜ PNG=6**，`QT_QPA_PLATFORM=windows`，2560×1600）
> 全量回归：G2 **PASS=5563 / FAIL=0 ｜ 104 套件 ｜ 全 IDENTICAL（零 DIFF）**

---

## 一、用户口径（逐字）

> 「**记忆改删的就删改加的就加，然后，派发入口这类的我也不懂，按照人类的逻辑来就好，然后，没有硬性对话，用AI自己生成即可，被派不可进入原本不可进入的世界，比如暗之民不能在没有球的情况下进光世界，这样的，那个落盘我也不知道啥意思，你看着办就好**」

拆成**四条裁定 + 两条授权**：

| # | 逐字片段 | 性质 | 本轮落地 |
|---|---|---|---|
| ① | 「记忆改删的就删改加的就加」 | 授权 | 详版 §114 + 速查本 §20（见"记忆三件"） |
| ② | 「派发入口这类的我也不懂，**按照人类的逻辑来就好**」 | 裁定权交我 | `handle_errand_command` 挂 `dialogue_ui.send_message` |
| ③ | 「**没有硬性对话，用AI自己生成即可**」 | 硬约束 | `_errand_ack` 全走 `chat_with_ai`，**零写死台词** |
| ④ | 「**被派不可进入原本不可进入的世界**，比如暗之民不能在没有球的情况下进光世界」 | 硬约束 | 差事**继承** `world_gate`（派发当场 + 每拍重判 + 拒即作废 + 落痕） |
| ⑤ | 「那个落盘我也不知道啥意思，**你看着办就好**」 | 授权 | 独立档 `npc_errands.json`（不蹭 `npc_plan_store` 的 `Book`） |

★ 上一轮（§113）遗留的**两条待裁定**（"被派可否跨世界"、"差事是否落盘"）在本轮被 ④⑤ 直接答掉 ⇒ **不再是待裁定项**。

---

## 二、四条裁定 → 落地位置

| 设计决定 | 落地 | 判据 |
|---|---|---|
| **差事继承世界门控**（"被派 ≠ 免检"） | `_npc_errand_gate()` 唯一真源 = `npc_system.world_gate()`；`assign_errand` **当场**判 + `_npc_errand_tick` **每拍**判 | `C1`/`C5`/`C6`（+ 负控制 `C5b`/`B12`） |
| **拒了要作废**（不是"这拍先跳过"） | `_npc_errand_gate` 不过 ⇒ `board.abort(npc_id)` | `C2` + `D2~D5`（+ 负控制 `D7`） |
| **拒了要留痕**（"办不成"也是结果） | `_npc_errand_note()` → `npc_memory.remember/save` | `C3`/`C9`（+ 负控制 `D-M13`） |
| **入口按人类逻辑**：先问路、后派人 | `handle_errand_command`：识别 → **问路** → 派 → 回应 | `H2`/`H3`/`H5` |
| **台词由模型生成**（禁写死） | `_errand_ack` → `chat_with_ai`；`_errand_show_reply` → `add_dialogue(asker_id, …)` | `H6`~`H9`（+ 负控制：`H9` 判"无写死台词"） |
| **独立落盘** | `npc_errands.json`；**写**复用 `npc_plan_store.save`、**读**自己走 `json` + `ErrandBoard.from_dict` | `C12`/`C13`/`E1`~`E7` |
| **开关继承当前**（关闸不被旧档"复活"） | `_er.enabled = RalseiPet.NPC_ERRAND_ENABLED and RalseiPet.NPC_AUTONOMOUS_MOVE` | `C8b`（+ 负控制 `C8c`） |

### ★★★ 「顺序即优先级」的落点（第113轮口径的延续）

```
_npc_roam_tick     先跑：他这一拍自己想去哪
_npc_errand_tick   后跑：被派出的人用 roam.put() 压过本拍的自发决策
```

⇒ 被派的人**不会**因为"这一拍他自己想逛"而跑偏。**顺序反了 = 差事被自发改写**（变异 `D-M11` 锁住）。

---

## 三、★★★ 世界门控：四条规则（**按判断顺序，不可换位**）

`npc_system.world_gate(npc, world, scene_id=None, carried=False)` → `GateResult(ok, reason, detail)`（`__bool__ == ok`）

| 序 | 规则 | 结果 |
|---|---|---|
| **0** | **电脑桌面**（`scene_id == 'desktop'` 或 `world == 'desktop'`） | 仅 `DESKTOP_ALLOWED_IDS = ('ralsei','kris','susie','lancer')` ⇒ ok；否则 `REASON_DESKTOP_FORBIDDEN`。★★★ **必须先于光世界判** —— 桌面在 `_worlds.json` 里是 `light`，若先走光世界规则，**Ralsei 无球 ⇒ 连自己家都回不去** |
| **1** | **光世界** ⇒ `light_needs_bubble(npc)` 假 | `light_free`：谁都能去、**不需球** |
| **1b** | 光世界 + `light_needs_bubble` 真（= `DARK_ONLY_IDS = ('ralsei',)` 且 `escape_via_bubble`） | `carried` ⇒ ok；否则 `REASON_LIGHT_NEEDS_BUBBLE`（"X 是暗世界居民，脱离暗世界必须被装进球"） |
| **2** | **暗世界** ⇒ `npc.roam_scope != RoamScope.HOME`（**跨作品**） | 自己作品侧 ✅｜`RoamScope.ALL`（**仅 Niko 1 人**）✅｜其余 ⇒ `REASON_FOREIGN_DARK`（"X 只能在非暗世界穿梭"） |
| **3** | 暗世界 + `chapter_matches(ch, npc.chapters)` | 不匹配 ⇒ `REASON_FOREIGN_DARK`（"ch 不属于 X"） |
| **4** | 暗世界 + `free_dark_roam(npc)`（**仅 Ralsei**） | 免章限制 |

### ★★ 本机实测放行矩阵（`probe114e.py`，注册表 96 人）

| 角色 | `roam_scope` | 能去 | 不能去 |
|---|---|---|---|
| `ralsei` | `home`（`free_dark_roam`） | `ch1.card_castle.*`（暗）· `oneshot.*` · `ut.*` · `desktop` | **光世界**（`ch1.kris_room.*` ⇒ `REASON_LIGHT_NEEDS_BUBBLE`，除非 `carried`） |
| `susie`/`kris`/`lancer` | `home` | Deltarune 光/暗侧 + `desktop` | `oneshot` / `ut`（"oneshot 不属于 苏西"） |
| `os_niko` | `all`（唯一） | 除桌面外**全通** | 桌面（不在白名单） |
| `ut_papyrus`/`ut_toriel` | `non_dark` | `ut.*` ✅（**别名归一后**）· Deltarune **光世界** ✅ | `oneshot` 与 Deltarune **暗世界** |

★ 注册表里**没有** `niko` / `hy_sans` 两个 id —— `os_niko` 才是 Niko 真身（别照字面猜）。

### ★★★ 迁入章的 `world` 判定（与 `world_of_scene` **故意不同**）

`_worlds.json` 把 `oneshot`/`outertale`/`ut`/`uty` 全部房间标 `unknown`；`scene_system.world_of_scene()` 对它们返 `None`
（服务**道具系统**："判不出 ⇒ 不触发销毁"）。差事门控需要**另一个保守侧**、且要让用户主用例（派 Ralsei 去 oneshot）跑得通：

```
① overrides（desktop → light）
② rooms[chapter][room_id] ∈ {light, dark}
③ 其余（迁入章 unknown / None / 空串）⇒ dark   ← 保守侧：宁可按"暗世界"严判，不按"光世界"放水
```

`check114 A8` 是**对照判据**：断言它与 `world_of_scene` 对同一批输入**行为不同**
（迁入章 ⇒ 它是 `dark`、后者是 `None`；`desktop` ⇒ 两者都 `light`）—— 证明 A 段**不是后者的复制品**。

---

## 四、★★★ 顺带修掉的真缺口：跨作品章名**两套写法**

| 侧 | 写法 |
|---|---|
| 场景侧（`_routes.json` / 场景 id） | `ut` · `uty` |
| 角色侧（`_registry.json` / `npcs.json`） | `undertale` · `undertale_yellow` |

`chapter_matches` 原本**逐字比** ⇒ `'ut' in ['undertale']` **恒假** ⇒ **UT / UTY 全部 29 位角色连自己家都进不去**
（`ut_toriel` 想去 `ut.rooms.*` 被 `REASON_FOREIGN_DARK` 拦下）。

**修法 = 在比较处归一，两边数据都不动**：

```python
CHAPTER_ALIASES = {'ut': ('undertale',), 'uty': ('undertale_yellow',)}
# chapter_names() / same_chapter() / chapter_matches() —— 全部在比较处展开
```

★ 为什么不动数据：角色侧全名是**人设/注册表的既有口径**，场景侧短码是**场景系统的既有口径**，
两边各有 29 / 263 条记录；改任一侧 = 大面积回归风险，**归一在比较处 = 单点、可测、零数据迁移**。

`check114 B5`（放行）+ `B13`（清空别名表 ⇒ 反转成拒）+ `B14`（还回去 ⇒ 又放行，**拆干净了**）
= 正/负/复原三连；变异 `C-M8`/`C-M9`/`C-M10`（含"退回逐字比"与"另一条老写法"两条独立路径）全部 CAUGHT。

---

## 五、判据与验证（全部机器可复算）

| 项 | 结果 |
|---|---|
| `check114.py` | **84 PASS / 0 FAIL**（输出留档 `_evidence/check114_out.txt`） |
| `mutate114.py` | **22 变异 ｜ CAUGHT=21 ｜ MISSED=0 ｜ SKIP=0 ｜ no-op=1 ｜ 工作区干净**（`_evidence/mutate114_out.txt`） |
| `rec114.py`（真机 `QT_QPA_PLATFORM=windows`） | **58 PASS / 0 FAIL ｜ PNG=6**（`_evidence/rec114_out_real.txt`） |
| `rec114.py`（离屏复核） | **58 PASS / 0 FAIL**（`_evidence/rec114_out_offscreen.txt`） |
| `verify114_alias.py` | **30 PASS / 0 FAIL** |
| `verify114_eol.py` | **21 PASS / 0 FAIL** |
| `recheck114mem.py`（记忆三件复检） | **38 PASS / 0 FAIL**（`_evidence/recheck114mem.txt`） |
| G2 全量 | **PASS=5563 / FAIL=0 ｜ 104 套件 ｜ 零 DIFF** |

### 判据覆盖（A–H 八段，每类配负控制）

- **A 目的地 → 世界**：真调产品 `staticmethod` + 真数据；`A8` 与 `world_of_scene` 对照；`A9` 缓存层。
- **B 门控**：真调 + 真注册表 **96 人**；`B1`/`B2` **成对**（同一个 Ralsei：暗世界放行 / 光世界拒）；
  `B3` 是 `B2` 的**正控制**（只加 `carried` ⇒ 放行 ⇒ 证明 B2 测的是"球"而不是"一刀切"）；
  `B12`/`B13`/`B14` 三条负控制。
- **C main 接线**：AST；行号只比较、**不回显**；`C0` 是"函数解析到了"的前置（否则后面全变恒假）。
- **D `abort` 语义**：半途作废 **不进 `done`**、不留结果、之后再 `step` 不冒 finished；`D7` 负控制。
- **E 落盘**：真写盘 + 真读回；`E6` 交叉验证"`npc_plan_store.load` 读差事档 ⇒ 空书"（**注释里那句是真的**）；`E7` 负控制证明是**类型不匹配**而非 save/load 坏了。
- **G 派发入口**：真跑 `_errand_parse_intent`；`G2`/`G9` 词边界；`G8` 负控制。
- **H 对话层接线**：AST；`H9` 判"**没有**写死的对用户台词"；`H13`/`H14` **成对结构判据**。
- **F 判据自身体检**：记账 / 判据名无标记 / 无重复。

---

## 六、变异测试（22 条，覆盖 4 个文件）

| 组 | 变异 | 结果 |
|---|---|---|
| no-op | `M0` 注释级改动（**应当不报红**） | OK(no-op) |
| A | `M1` 迁入章兜底 `dark→light` · `M2` 空/非字符串早返回 `dark→light` · `M3` 忽略 `overrides` | CAUGHT ×3 |
| B | `M4` 门控**恒放行** · `M5` **恒拒绝** · `M6` 不喂 `carried` · `M7` 喂**错的世界** | CAUGHT ×4 |
| C | `M8` `chapter_matches` 退回逐字比 · `M9` 清空 `CHAPTER_ALIASES` · `M10` `home_production` 分支退回逐字比 | CAUGHT ×3 |
| D | `M11` 每拍不过门控 · `M12` 不 `abort` · `M13` 不落记忆 · `M14` 不落盘 · `M15` 读回不继承开关 · `M16` 派发当场不问路 · `M21` `abort` 空操作 | CAUGHT ×7 |
| G | `M17` 去掉"不能派自己" · `M18` 去掉地点词词边界 | CAUGHT ×2 |
| H | `M19` 入口被拒时不落记忆 · `M20` `dialogue_ui` 不再取入口 | CAUGHT ×2 |

---

## 七、真机录像（`_evidence/frames114/`，6 帧 + 1 特写）

| 帧 | 时刻 | 关键观察（内省对账） |
|---|---|---|
| `k000_boot` | 起实例 | 看板空（没派过 ⇒ 零行为变化） |
| `k001_denied` | Ralsei 无球进光世界被拒 | 看板**仍空**、位置真源**未改写**、记忆 **+1** 条"去不了" |
| `k002_dispatched` | 派 Ralsei 去 `oneshot` | 看板 **+1**（放行） |
| `k003_home_production` | 派 Papyrus 回 `ut` | 看板 **+1**（**别名归一后**才可能） |
| `k004_working` | 两人都到达 | `working_positions()` 两条、`_npc_seed_bodies` 在目标场景**含他** |
| `k005_noop` | 闲聊 / 半句话 | 看板、场景、显示**一字不动** |

★★ **画面本身没有变化** —— 这是**设计使然**（§109.5 要点 1：NPC 移动不切显示）。
⇒ 本轮的录像证据形式 = **内省状态 + 几何不变量 + 真机跑通**，而不是"画面上多了一个人"。

### ★★★ 用几何而不是肉眼（透明分层窗口的老坑）

`QScreen.grabWindow(0)` 抓不到 `WA_TranslucentBackground` 分层窗口 ⇒
"桌宠在不在"不能靠肉眼在帧里找。本轮改为**几何不变量**：

- `F5`：**每个**快照都取到了 `frameGeometry()`（防 `None` 混进集合里蒙混）；
- `F6`：**没有任何一次**快照出现"接近全屏"的窗口（阈值 `max(320, screen//2)`；实测最大边长 **144**）。

⚠️ **第一版判据写错了**：断言"六个快照几何**逐个相等**" —— 太脆。桌宠窗口按当前精灵帧**自适应宽高**
（本轮实测 `144×98`，历史跑出过 `100×100` / `39×83`）。真正要守的是"**没有窗口接近全屏**"
（= 切了场景画布），而不是"每帧一样大"。

### 图像处理**如实声明**（不是原始抓帧）

| 文件 | 处理 |
|---|---|
| `k00N_*.png` | 原始抓帧 **2560×1600** → **等比缩到宽 1280**（6.08 MB → 1.78 MB/帧） |
| `dbg114_pet_zoom.png` | 按报告里的 `pet_geo` **[2388,1379,144,98]** 外扩 → 裁 **(2338,1329,222,198)** → **×2 放大** = 444×396 |
| `contact_114.png` | 6 帧缩图拼 **3×2 联系表**（1908×864） |

★ 我**真看了**这三张（不是只读后台输出）：联系表 6 帧全是桌面壁纸、右下角是桌宠、**无场景切换、无多余窗口**；
特写里能看到 **绿袍 Ralsei + 红心灵魂**压在壁纸之上 ⇒ 我们的窗口确实在屏上、压在最上层。

---

## 八、本轮修掉的真 bug：入口被拒时**一个字都不留**

**发现方式**：`rec114 B7` 实跑报红（不是靠读代码猜的）。

`handle_errand_command` 走的是"**先问路、后派人**"：

```python
ok, why = self._npc_errand_gate(target_id, dest_scene)
if not ok:
    ...      # ← 原实现只 _log.info + _errand_ack（对用户说"去不了"）
else:
    self.assign_errand(...)     # ← "去不了"那句记忆只写在 assign_errand 内部
```

⇒ 门控不合格时**根本不会**调到 `assign_errand`，而那支记忆写在其内部 ⇒
**从对话层被拒的人一个字都不留**：用户过两天问他"上次让你去的地方怎么样了"，他只会茫然
（他压根不记得有过这回事）—— 而"**办不成也要留下结果**"正是本轮口径。

**修法**（补在拒绝分支）：

```python
if not ok:
    self._npc_errand_note(target_id,
                          '我本来要去 %s，但去不了 —— %s' % (dest_scene, why))
elif self.assign_errand(target_id, dest_scene, what) is None:
    ok = False
    why = '他没能接上这趟差事'
```

★ **不会重复落两条**：走到这个分支 ⇒ `assign_errand` **没被调用过** ⇒ 它内部那支不可能已经落过
（两处**互斥**，同一件事只留一条记忆）。`H13`（结构判："`_npc_errand_note` 在 `if` 体、`assign_errand` 在 `else/elif` 体"）
+ `H14`（负控制：同一条结构判据在 `_errand_ack` 上必须为假）把这条钉死；`H-M19` 变异 CAUGHT。

---

## 九、判据自身栽过的地方（全部记录在案，**"报红先怀疑判据"** 本轮又成立五次）

1. ★★★ **`mutate114 D-M15` MISSED**（把 `_er.enabled` 写成写死 `True`，**一条判据都没报红**）
   ⇒ 说明"**读回时开关继承当前**"当时**没有任何判据在守**。
   修 = 新增 `C8b`（AST 结构判：存在 `_er.enabled = RalseiPet.A and RalseiPet.B`，且两个操作数是**当前**开关）
   + `C8c`（负控制：**同一条判据**在 `_npc_errand_tick` 上必须为假 —— 否则"换个函数也过"= 它没在守东西）。
2. ★★ **`mutate114 C-M8` SKIP**（锚点命中 0 次）：`chapter_matches` 是**模块级函数**、体缩进 **4 空格**，
   我按 8 空格写锚点 ⇒ 命中 0。修后 CAUGHT。
3. ★★★ **`check114 A0`**：本套件第一版 `import npc_system` 又加载了**第二份**模块对象，
   判据持有的是副本、产品改的是原件 ⇒ 负控制**假红**。修 = 断言"判据持有的模块与产品是同一份"。
4. ★★ **`recheck114mem` 首版 3 红，三条全是判据自己的毛病**：
   - `P2c`「详版仍在」报红 —— 我把门槛按 **UTF-8 字节**设了 90 万，
     而中文 **1 字 = 3 字节但只 1 个 JS 码元** ⇒ 详版 js_len 只有 59.5 万。改按**码元**设门槛。
   - `P5a`「无恒真判据」报红 —— 用**裸正则**扫 `check(..., True)`，
     扫到了**本文件 docstring 里写着这个词**（**本项目第五次**同型坑）⇒ 改走 **AST**，只看真调用。
   - `P4b`「逐令牌回验」报红 12 个 —— 判据**过窄**：只认"整串逐字出现"，
     而那 12 个都是**措辞被压缩、语义仍在详版**（如 `灵魂减半` ↔ 详版 `灵魂尺寸减半`）。
     ⇒ 改为 **raw / norm / sub 三级命中** + **"别名锚点"表**（每个锚点由 `P4a` **逐个回验真的在详版**
     ⇒ 详版一旦丢锚点立刻报红，**不是白名单放行**）+ **有限"合理消失"表**（3 条，逐条写理由）。
5. ★★★ **`recheck114mem P4e` 负控制自己恒绿**：我把"构造探针"**同时加进基准侧和现盘侧**
   ⇒ 相减之后归零 ⇒ 负控制永远绿（= 比没有负控制更糟）。
   修 = 探针**只加在基准侧**（模拟"它在 HEAD 里、现在被删了"）。
   ★ **教训：负控制本身也是被测物**。

---

## 十、G2 全量（104 套件）

| 轮 | 套件 | PASS | FAIL | DIFF |
|---|---|---|---|---|
| 改码前（基线） | 103 | 5479 | 0 | — |
| 本轮 | **104** | **5563** | **0** | **0（零 DIFF）** |

本轮先出现 **3 个 DIFF**，逐条分诊（**没有一条是"改基线糊过去"**）：

| 套件 | 现象 | 处置 |
|---|---|---|
| `check81 G5` | `缺=['check114']` | **这正是该守卫在干活**（"新套件必须已固化进基线"）⇒ `--update` |
| `model_conc57 B6` | `chat_with_ai` 调用点 5 → 6 | 新增 `_errand_ack` 是**真的多了一处**（预期产品变化）⇒ `--update` |
| `check72 B5` | 回显 `roam@3370 chapters@3883` | **判据本身的缺陷**：回显**绝对字符偏移** ⇒ 源码任意增删即假 DIFF，违反铁律「判据禁回显随相变绝对值」⇒ **改判据**，不回显偏移 |

---

## 十、记忆三件（用户的 ① 授权「记忆改删的就删改加的就加」）

★ 先满足**两道门槛**：**(a) 代码实证会被截断** —— 改前速查本 `js_len = 9991`，
**只余 9 个码元**（`check95 A2` 硬闸 `≤ 10000`），加任何内容都被截断砍尾；
**(b) 用户明确授权**（本轮 ① ）。

顺序按 skill `agent-memory-compaction` 的铁律：**先补详版、再压速查本**。

| 件 | 动作 |
|---|---|
| 详版 `参考-契约与历轮（详版）.md` | **追加 `## §114`**（口径逐字 / 门控四规则 / 迁入章判定 / 别名缺口 / 接线 / 入口 / 落盘 / 判据 / 录像铁律 / 剩余令牌） |
| 速查本 `MEMORY.md` | **新增 §20（3 条）**；**压** §19 / §10 / §11 / §16 —— 被删内容**全部先落到详版**，速查本只留指针 |
| 当日日志 `2026-10-14.md` | **append** 本轮小节（append-only，不改历史行） |

**复检**（`_tools/recheck114mem.py` → `_evidence/recheck114mem.txt`）：**38 PASS / 0 FAIL**
- P1 结构（§114 恰一处、排在 §113 之后、四个小节都在、标题无粘连/无重复）
- P2 体积：速查本 **JS 长度 9956 ≤ 10000**（余量 44）；详版 594,886 码元（未被压）
- P3 编码：两文件 **无 BOM / 无 U+FFFD / 全 LF**
- P4 ★★★ **逐令牌回验**：从 HEAD 版速查本删掉 **77 个**令牌 ⇒ 归宿 = raw 57 / norm 3 / **别名锚点 14** /
  **合理消失 3** / **缺 0**。★ 14 个"别名锚点"由 `P4a` **逐个回验真的在详版**（锚点腐烂 ⇒ 立刻报红）；
  ★ 负控制（详版没有的令牌被删 ⇒ 必报出）+ 正控制（详版有的令牌被删 ⇒ 不误报）成对。
- P5 恒真判据复查：**AST** 查本文件，`check(名字, True)` 恒真调用 = **0**；判据名无重复。
- P6 判据自身体检：提取器四类都能提、`hits()` 在"有/无"两份文本上结论相反（有鉴别力）。

★ 复检自己栽的几处见 §九（**全部是判据的毛病，不是记忆文件的问题**）。

---

## 十一、明文遗留（未做 / 待裁定）

1. ★ **办完是 `drop`（回落静态归属 = 回家），不恢复"派出前那次自主驻留"**。
   理由：差事是"出门办事"，办完回家是自然的。**若用户希望"办完回原处"，改一处即可**。**（仍待裁定）**
2. **进 OneShot 后向导机器人固定对话 + Niko「.............」**（详版 §109.2(c) 登记）—— 下一批。
3. **所有世界角色加「通关后」背景设定** —— 已登记，下一批。
4. `blend_type=2` / `character_hue` / `step_anime` / `move_route` 等原作保真缺口属 §104 范围，不在本轮。
