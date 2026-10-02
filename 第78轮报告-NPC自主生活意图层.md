# 第78轮报告 —— NPC 自主生活「层1 意图层」与「人味」L1~L6 落锁

> 日期：2026-10-02
> 起点：`60671ee`（第76轮 R4）
> 本轮提交：`f49c74a`（第77轮场景迁入）→ 本报告对应提交见文末
> 回归：`code-quality-audit/regress/run_all.py` —— **PASS=3662 FAIL=0 套件=70 全 IDENTICAL**

---

## 0. 本轮要回答的用户口径（逐字）

> 「人物之间也可以自己动，也就是，**他们生活是生活，我和他们只是朋友**，而不是主导人，
> 也就是**不会因为缺少一个人哪怕是我他们就不生活了**，OK？还有，像是**去哪？找谁？干什么？
> 生活规划**这类的事也是由**各自的 AI 决定**，并且**不是一到晚上就必须回自己家**，
> 也可以选择**在朋友那睡觉**，但这也是 AI 决定，反正就是，**人味，人味，还 tm 是人味**，
> 重要的事情说三遍！」

本轮把它拆成 **L1~L6 六条硬口径**，并把 **L1~L6 全部写成回归锁**（`check78`，38 项）。

---

## 1. L1~L6 逐条落实（每条都要能"指到代码"）

| 编号 | 用户原话（关键词） | 落点 | 怎么证明（判据） |
|---|---|---|---|
| **L1** | 「他们生活是生活」 | `npc_intent.py` 整模块 = **纯函数决策层**，零依赖、可离线跑 | `check78` A：AST 顶层 import ⊆ {collections, hashlib, random}，零函数内 import，零项目内 import |
| **L2** | 「我和他们只是朋友，而不是主导人」「不会因为缺少一个人哪怕是我他们就不生活了」 | `decide()` / `choose_sleep_scene()` 的**签名里没有** `pet`/`user`/`player`/`host`/`me` | `check78` B：**结构判据**（AST 查形参名）+ 负控制（造一个带 `user` 形参的假函数必须被抓出） |
| **L3** | 「去哪？找谁？干什么？生活规划…由各自的 AI 决定」 | `Intent`（what/dest_scene/who）+ `Plan`（今日规划） | `check78` E：行为级真跑（无可达 ⇒ 只能 stay；无朋友 ⇒ 不捏造社交；找朋友时 who ∈ 名单） |
| **L4** | 「不是一到晚上就必须回自己家，也可以选择在朋友那睡觉」 | `choose_sleep_scene()`：`own_home` 与 `friend` **同量级权重**，谁赢由种子+熟络度摇 | `check78` F：两类结果都真会出现 ⇒ **是决策不是常量**；朋友家不可达 ⇒ 不出现；陌生人不给睡 |
| **L5** | 「生活规划」 | `Plan.day/intent/last_sleep_scene/wants/history`，`decide(last=...)` **读上次结果**避免原地打转 | `check78` E：L5 读上次结果会改道 |
| **L6** | 「**人味，人味，还 tm 是人味**」 | 三条机制：①每角色固定种子 ②时段只是"倾向"（权重）不是"开关" ③`jitter` 用连续时间 | `check78` C/D：见下 §3 |

---

## 2. `npc_intent.py` 设计（545 行，零依赖）

**四个问题四个答案**：

| 问题 | 字段 |
|---|---|
| 去哪 | `Intent.dest_scene` |
| 找谁 | `Intent.who` |
| 干什么 | `Intent.what` |
| 生活规划 | `Plan` |

**意图动作表**（`ACTIONS`，6 项）：`wander` / `visit_friend` / `go_home` / `visit_favorite` /
`explore_unknown` / `stay`。★ **刻意不含 `sleep_here`** —— 睡觉是"在哪过夜"（`dest_scene` 的事），
不是"干什么"，避免与 L4 混淆。

**时段**（`PHASES`）：`dawn(5-8)` / `day(8-17)` / `dusk(17-21)` / `night(21-29)`。
键名刻意用中性词，**避免"晚上 = 回家"这种默认叙事**。

**零依赖三纪律**（对齐 `companion*` / `npc_placement`）：
顶层只 `import` 标准库；**零函数内 import**；**不 import 任何项目内模块**
（连 `npc_life` 都不 import —— 熟络度**从入参拿**）。

---

## 3. ★★★ 「人味」L6 怎么落：**禁"整点必做 X"**

这是本轮技术含量最高的一条。**"人味"的反面 = 定点定事**（一到 23 点所有人同时回家、
一到 8 点所有人同时出门）—— 那是**程序**，不是**生活**。

三条机制：

### ① 每角色固定种子
```python
def seed_for(npc_id, salt=''):   # sha256(npc_id+salt) 每角色一个稳定种子
```
⇒ 不同人的一天**长得不一样**（`check78` D：不同人分布不同）。

### ② 时段只是"倾向"，不是"开关"（★ 核心）
```python
PHASE_WEIGHT_MUL = {
    'dawn':  {'wander': 1.1, 'stay': 1.4, 'go_home': 1.1},
    'day':   {'wander': 1.3, 'visit_friend': 1.2, 'explore_unknown': 1.2},
    'dusk':  {'visit_friend': 1.4, 'go_home': 1.2, 'visit_favorite': 1.1},
    'night': {'go_home': 1.6, 'stay': 1.2, 'visit_friend': 1.1},  # ★ visit_friend 不许归零
}
```
`action_weights()` 末尾有一道 **⑤ 下钳**：任何项都不许被乘成 0。
⇒ **夜里 `visit_friend` 仍 > 0**（"在朋友那睡"是可能的，L4）；
**白天 `go_home` 也 > 0**（不强制"白天必须在外"）。

`check78` C 是这条的**结构保障判据**：遍历全天候 × 全动作，断言权重**恒 > 0**。

### ③ `jitter()`：同一人同一时段，每次摇出来可以不同
```python
def jitter(npc_id, now, salt='', lo=0.0, hi=1.0):
    # 种子来自 (npc_id, 连续时间 now) —— ★ 不是 (seed, day, slot)
    # day/slot 会锁死 ⇒ 故意用**连续时间**
```
⇒ `check78` D 断言"同一人 40 天同一时刻出现 > 1 种决策"，
且"同刻可复现"（确定性抖动）—— **既不是死板，也不是乱跑**。

---

## 4. `check78`（38 项 / PASS=38 FAIL=0）七段结构

| 段 | 主题 | 关键判据 |
|---|---|---|
| **A** | 零依赖纪律 | AST：顶层白名单 + 零函数内 import + 零项目内 import |
| **B** | ★★ **L2 用户不是驱动源** | `decide()`/`choose_sleep_scene()` 形参不含 pet/user/player/host/me + **负控制** |
| **C** | ★★★ **L6 禁整点必做** | 任何时段 × 任何动作权重恒 > 0；夜里 visit_friend > 0；白天 go_home > 0；熟络度只加不减；非法熟络度不抛 |
| **D** | ★★ **L6 同人同刻不必同行为** | 40 天同刻 > 1 种决策；不同人分布不同；同刻可复现；jitter 随时间真变/因人而异 |
| **E** | 行为 | 无可达⇒stay；**家在可达集外一次都不许出现**（+正控制证明非空集）；无朋友⇒不捏造社交；找朋友 who ∈ 名单；L5 读上次结果会改道 |
| **F** | ★★ **L4 睡觉** | 两类结果都真出现（是决策不是常量）；朋友家不可达⇒不出现；哪都去不了⇒None；陌生人不给睡；连睡降权 |
| **G** | 判据自身体检 | AST 层数标记打印点（不吃字面量自指）；记账守恒 |

### 判据侧修了 3 个 bug（★ 值得记下来）

1. **G2 用错文件**：初版 `src.count("print('[PASS]")` 用的是**被测模块** `npc_intent.py`
   ⇒ 得 0。改 `_SELF = read(__file__)`（**必须看本文件**）。
2. **G2 自指计数**：改 `_SELF` 后 `count(...)` 得 **4** —— 因为**判据自己的字符串字面量
   也含该标记**（自指）。改 **AST 层计数**，且认三种形状
   （`Constant` / `JoinedStr` / `BinOp(%)` 左操作数是常量）。
   ★ 教训：`src.count(marker)` 这类**文本计数**在"判据自己也要打标记"时**必然虚高**。
3. **G4 记账守恒恒差 1**：`n_check_calls=38`，`PASS+FAIL=37`。
   根因 = **G4 自己也是一次 `check()`**，在比较之后才进账。
   改右边为 `n_check_calls - 1` 并注释"第一版恒差 1，是**判据自己的** bug"。

★ 另有一条**全局纪律**（第77轮血泪）：`check77`/`check78` 的**判据名与明细里不许出现
`[FAIL]`/`[PASS]` 字面量** —— 因为 `run_all.py:1795` 的 `count_results()` 是
**正则数 `[FAIL]` 字面量**，自指会污染套件 FAIL 计数。

---

## 5. 回归与数据面

### 5.1 全量回归
```
合计：PASS=3662 FAIL=0  套件=70
check78          0      38     0      IDENTICAL
```

### 5.2 `round5_smoke` DIFF 定性（★ 本轮收尾的第一件事）
```diff
-待导入模块数: 63
+待导入模块数: 64
   [ OK ] memory_system
+  [ OK ] npc_intent
   [ OK ] npc_life
```
**定性：模块计数闸，属预期"数字随事实 +1"，不是缺陷。**
这是记忆里 §0 铁律记的那条：新增合法零依赖模块会撞 `round5_smoke` 的模块计数闸
（与 H4/H5 轮 `file_sheet_controller` 35→36 先例**完全同型**）。
处理：`run_all.py --update --only round5_smoke`（**合并模式**，其余 69 套基线不动）
⇒ 复跑全量 **全 IDENTICAL**。

★ **为什么不该改判据**：`round5_smoke` 的判据本就是"全模块可导入 + 记录数量"，
数量变化是事实的自然记录；判据的 `desc` 里**已经写明**
"模块数随新增模块而变，勿把具体数字写进描述"。⇒ 改判据反而是画蛇添足。

---

## 6. 交付边界（★ 先说清楚，免得把"接口就位"说成"已经能用了"）

**`WIRING` 如实登记**：
```python
WIRING = OrderedDict((
    ('wired', False),
    ('used_by', []),
    ('why', '层1 只做"决策"（纯函数，零依赖、可离线验）…'),
    ('not_yet', ['main 接线（层2）', 'BEDTIME_HOME_SCENE 替换（层3）',
                 '规划持久化（层4）']),
))
```

| 层 | 内容 | 状态 |
|---|---|---|
| **层1 决策** | `npc_intent.py` 去哪/找谁/干什么/规划/睡觉 | ✅ **本轮已完成**，38 项锁全绿 |
| **层2 移动** | `main → scene_controller.travel_to` 接线，开关 `NPC_AUTONOMOUS_MOVE` 默认 false | ⏳ 未做 |
| **层3 睡觉接线** | 把 `main.py:7956` 的 `BEDTIME_HOME_SCENE='desktop'` 换成 `choose_sleep_scene()` | ⏳ 未做（**挡在 Q3**） |
| **层4 存档** | `plan`/`intent`/`last_sleep_scene` 落 `data_store` | ⏳ 未做 |

### ★★★ 层2 的头号技术障碍（已定位，未修）
`_npc_seed_bodies()` **只在两处被调用**：
- `main.py:2182` 启动时；
- `main.py:2513` **场景切换钩子**里。

⇒ **"用户不动，世界就冻住"** —— 与 L2「不会因为缺少一个人哪怕是我他们就不生活了」**正相反**。
层2 必须解决它：NPC 移动**不能依赖宠物位置**、**不能只在切场景时重建**。

---

## 7. 待用户拍板（★ 挡着后续施工）

| # | 问题 | 影响 |
|---|---|---|
| **Q3** | `BEDTIME_HOME_SCENE = 'desktop'`（`main.py:7956`）**旧行为确认废弃？** | ★ **挡着层3**。旧口径是"所有 NPC 一律回 desktop"，新口径是 `choose_sleep_scene()` 决策。要改的是一处常量，但**行为语义变了**（NPC 可能不回桌面、而去朋友家）⇒ 需要用户确认 |
| **Q1** | 场景补齐选档（建议接 OneShot 263） | 第77轮遗留 |
| **Q2** | Outertale 只补 53 采样是否够 | 第77轮遗留 |

---

## 8. 下一步（按优先级）

1. **层2 移动**（★ 核心）：复用 `scene_controller.travel_to` + `reachable_destinations`；
   新开关 `NPC_AUTONOMOUS_MOVE` 默认 **false**；**首要**是解决"只在切场景时重建"。
2. **层3 睡觉接线**：待 Q3 确认。
3. **层4 存档**：`plan`/`intent`/`last_sleep_scene` 落 `data_store`（vault=`E:\RalseiMemory\`）。
4. U1 收尾池：A4 `chkdsk E: /f`（**需用户管理员**）、B15 素材补采、B14 瓦片、B11 修 13 套件、B6。

---

## 9. 留痕

- 新增：`ralsei_pet/modules/npc_intent.py`（545 行）、
  `code-quality-audit/第78轮-自主生活意图层/_tools/check78.py`（38 项）。
- 改动：`code-quality-audit/regress/run_all.py`（注册 `check78`）、
  `code-quality-audit/regress/baseline.json`（`round5_smoke` 与 `check78` 合并重固）。
- 回归：`PASS=3662 FAIL=0 套件=70`。
