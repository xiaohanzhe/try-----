# 第79轮报告 —— NPC 自主生活「层2 驻留层」接线：从「场景的装饰」到「有自己的位置」

> 日期：2026-10-02
> 起点：`5091a8c`（第78轮 层1 意图层）
> 回归：`code-quality-audit/regress/run_all.py` —— **PASS=3719 FAIL=0 套件=71**

---

## 0. 本轮回答的用户口径（逐字）

> 「人物之间也可以自己动，也就是，**他们生活是生活，我和他们只是朋友**，而不是主导人，
> 也就是**不会因为缺少一个人哪怕是我他们就不生活了**，OK？还有，像是**去哪？找谁？干什么？
> 生活规划**这类的事也是由**各自的 AI 决定**」

层1（第78轮）已经把「决策」做出来了（`npc_intent.py` 纯函数，38 项锁）。
**但层1 只是"会想"，不会"走"** —— 本轮把它接进产品，让 NPC 真的会有自己的位置。

---

## 1. ★★★ 层2 要解决的头号障碍（第78轮定位，本轮修掉）

```
_npc_seed_bodies()  只在两处被调用：
  · main.py:2182   启动时
  · main.py:2513   场景切换钩子
```

⇒ 现有模型 =「**NPC 是当前场景的装饰**」：站位表 `_placement.json` 里写死
`scene_of(npc_id)`，NPC **没有属于自己的位置状态**。
⇒ **用户不动，世界就冻住** —— 与用户口径「不会因为缺少一个人哪怕是我他们就不生活了」
**正相反**。

---

## 2. 模型升级：静态归属 → 静态归属 + 动态驻留覆盖

新增 `ralsei_pet/modules/npc_roam.py`（零依赖）：

| 层 | 是什么 | 真源 |
|---|---|---|
| **静态归属** | `_placement.json` 里"他住哪" | `npc_placement.PlacementBook.scene_of()` |
| **动态驻留** | `RoamState`：只存**偏离了默认**的人 | `npc_roam.RoamState` |

**查询规则**（`_npc_scene_roster` 里落地）：
```python
here = roam.resident_of(nid)      # ① 有覆盖 ⇒ 他自主挪到了这儿
if here is None:
    here = book.scene_of(nid)     # ② 没有 ⇒ 回落静态归属
if here != scene_id:
    continue
```

★★★ **为什么"没有覆盖"必须返回 `None`，而不是返回默认值**：
默认值的真源在 `_placement.json`，本层**不该复制一份** —— 那就是"同一份规则两处算"
（本项目最贵的坑）。返回 `None` = 明确交接。

---

## 3. ★★★ 零回归承诺（本轮最贵的一条）

`NPC_AUTONOMOUS_MOVE = False`（**默认关**）时：

- `npc_roam.step()` **立即返回、一个字节都不改**（`check79` B1）；
- ⇒ `RoamState` 恒为空表；
- ⇒ `resident_of()` 恒 `None`；
- ⇒ `_npc_scene_roster` 全走 `_placement.json`；
- ⇒ **行为与第78轮逐字相同**。

这不是"大概一样"，是**结构保证**，并有**负控制**兜底
（`check79` B2n：打开开关后同样调用**必须**真产生变化 ⇒ 证明 B1 不是恒真）。

### 回归实测佐证
接线后全量跑，6 套旧套件出现 DIFF，逐条核对后**全部定性为同一件事**：

```diff
+ <TS> [INFO] ralsei_pet.main — NPC 自主移动：关（默认；NPC 仍只在站位表里"原地生活"）
```
（`round8_anim` / `soul_round55` / `npc_persona55` / `npc_place56` / `check67` / `check73`）
外加 `npc_persona55` 的 import 列表多了 `npc_intent` / `npc_roam`（该判据本就打印列表）。

⇒ **零行为变化**：只多一行"说明关着"的日志。

---

## 4. `npc_roam.py` 设计要点

### 4.1 `RoamState`（驻留覆盖表）
```python
resident_of(npc_id)   # → scene_id | None（没覆盖 ⇒ None，不返默认值）
put(npc_id, scene, now, dwell=None, reason='')   # 驻留期 = MIN_DWELL_SECONDS（180s）
drop(npc_id)          # 撤掉覆盖 ⇒ 回落站位表
expired(now)          # 只读，不删（删由调用方决定）
```

### 4.2 `step()`（纯函数推进）
```python
step(state, now, *, decide_fn=None, roster=None, traits_of=None,
     familiar_of=None, home_of=None, reachable_of=None, friends_of=None, ...)
```
- ★★ `decide_fn` 是**注入**的（默认 `None`）⇒ 本模块**不 import** `npc_intent`，
  零依赖纪律得以保持；
- ★ 关掉开关 ⇒ 立刻返回（零副作用）。

### 4.3 ★★★ L6「禁整点必做」怎么落
```python
def leave_probability(stay, now, *, phase='day', familiar=0.0):
    frac = dwell / span
    p = LEAVE_P_MIN + (LEAVE_P_MAX - LEAVE_P_MIN) * frac ** 2   # 待越久越想走
    if phase == 'night': p *= 0.35       # 夜里更恋栈
    p *= (1.0 - 0.3 * familiar)          # 熟人越多越不想走
    return max(LEAVE_P_MIN, min(LEAVE_P_MAX, p))
```
三条保障：
1. **恒 > 0**（`LEAVE_P_MIN = 0.02`）—— "永远不动"就是另一种整点必做；
2. **单调不减**（待越久越可能走）；
3. **封顶 ≤ 0.85**（不会变成"必然走"）。

### 4.4 ★★ 桌面闸
`DESKTOP_SCENE = 'desktop'` 不许**自主**进入（那要走跟随/邀请那条路）。
与 `npc_system.DESKTOP_ALLOWED_IDS` **并列**的一道闸，不是替代。

---

## 5. 接线（★「函数写对了 ≠ 产品用上了」）

四步，全部有 AST 判据锁住（`check79` W 段）：

| # | 改动 | 位置 | 判据 |
|---|---|---|---|
| 1 | `NPC_AUTONOMOUS_MOVE = False` / `NPC_AUTONOMOUS_TICK = 30.0` | `main.py` 常量区 | W2（默认必须 False） |
| 2 | `import npc_intent as npc_intent_mod` / `import npc_roam as npc_roam_mod` | `main.py:465` 附近 | W3 |
| 3 | `init_npc_systems` 建 `self.npc_roam` | `main.py:~2190` | — |
| 4 | ★★★ **`_npc_scene_roster` 真读 `resident_of()`** | `main.py:~2710` | **W5**（否则层2 = 死代码） |
| 5 | ★★ **`_npc_roam_tick`**（30s 节拍调 `step()`） | `main.py:~3080` | W6 / W8 |
| 6 | ★★ 挂进 `update_movement`，**排在所有早退分支之前** | `main.py:~5027` | W7 / W7b |

★ W7b 判据值得单说：用 **AST 行号**断言 `_npc_roam_tick` 的调用点**早于**该函数里
**第一个 `return`** —— 保证「宠物睡着时世界照样转」（与灵魂/站位/幽灵/自由生活同一位置）。

### 新增七个方法
`_npc_roam_tick` / `_npc_roam_reachable` / `_npc_roam_traits` / `_npc_roam_familiar` /
`_npc_roam_friends` / `_npc_roam_scene_of` / `_npc_roam_decide`

★ `_npc_roam_reachable` 复用 `scene_controller.reachable_destinations()`（单一真源）；
★ `_npc_roam_decide` 只负责"把宿主的事实喂进 `npc_intent.decide()`"；
★ `_npc_roam_familiar` 如实返回 **0.0**（`npc_bonds` 是 NPC↔NPC，没有"NPC↔用户"这一维 ⇒ **不编**）。

---

## 6. `check79`（56 项 / PASS=56 FAIL=0）

九段 A~I、W：

| 段 | 主题 | 关键判据 |
|---|---|---|
| **A** | 零依赖纪律 | AST：顶层白名单 + 零函数内 import + 零项目内 import |
| **B** | ★★★ **零回归** | `enabled=False` ⇒ 零变化 + 负控制 |
| **C** | 驻留语义 | 空表 ⇒ `None`；drop 回落；snapshot 形状 |
| **D** | 不与用户耦合 | `step`/`leave_probability` 形参 + 负控制 |
| **E** | ★★★ **L6** | 概率恒 > 0；单调不减；序列非常量；夜里更恋栈；封顶；非法输入不抛 |
| **F** | 桌面闸 | 拒 desktop + 正控制（不是"什么都不记"） |
| **G** | 时段同源 | 24 整点逐时与 `npc_intent.phase_of` 同值 + 负控制 |
| **H** | 行为 | 真能移动（134 次）；可复现；换 salt 摇号真变；驻留期；到期；容错 |
| **W** | ★★★ **产品接线** | 见 §5 六项，含 W5「`resident_of` 真被调」 |
| **I** | 序列化 + 自身体检 | 标记打印点 == 1 + 负控制；`CALLS == PASS+FAIL` + 漏记负控制 |

### 判据侧修了 4 个 bug（★ 全是"判据自己的错"）
1. **`B2n` 逻辑自相矛盾**：断言写成 `bool(moved) and resident_of('a') is None` —— 动了就不该是 None。改为只看 `moved`。
2. **`H3n` 恒真**：我写了 `... or True` —— 典型恒真判据。改为**真判据**：换 salt 后 `_unit()` 摇号值必须变。
3. **`I5n` 恒真**：同样写了 `or True`。改为真造一个 **no-op 记账口**喂同一输入，必须判否。
4. **`I6` 记账守恒恒差**：我用 AST 数 `check(...)` 调用点 = 42，而运行时是 43 ——
   因为 **D 段有 for 循环**（源码 1 个调用点、实际执行 4 次）。
   ★ 这一版**不再数 AST**，改为在 `check()` 入口加**独立计数器 `CALLS`**，
   断言 `CALLS == PASS + FAIL`（抓漏记/错记）+ **漏记负控制**。
5. **`I4n` 夹具与真源码不同量级**：夹具只放 1 处标记 ⇒ 数出 1 而非 >1（判据看着像恒真）。改为放**两处**。

★ 教训再次印证：**"判据本身也是被测物"** —— 本轮 5 个 bug 全在判据侧，产品零错。

---

## 7. 回归与数据面

```
合计：PASS=3719 FAIL=0  套件=71
check79  0  56  0  IDENTICAL
```

### 本轮涉及的重固（全部合并模式，逐条定性后）
| 套件 | DIFF 内容 | 定性 |
|---|---|---|
| `round5_smoke` | 模块数 64 → 65（+`npc_roam`） | ★ 事实 +1（同第78轮先例） |
| `check78` | 新套件注册 | 基线 |
| `check79` | 新套件（含 W 段） | 基线 |
| `round8_anim` / `soul_round55` / `npc_persona55` / `npc_place56` / `check67` / `check73` | 多一行「NPC 自主移动：关」启动日志 | ★ 零行为变化，如实反映"默认关" |

---

## 8. 交付边界（★ 先说清楚）

| 层 | 内容 | 状态 |
|---|---|---|
| **层1 决策** | `npc_intent.py`（去哪/找谁/干什么/规划/睡觉） | ✅ 第78轮 |
| **层2 驻留 + 接线** | `npc_roam.py` + `main` 六处接线 | ✅ **本轮完成**（56 项锁） |
| **层3 睡觉接线** | `BEDTIME_HOME_SCENE → choose_sleep_scene()` | ⏳ **挡在 Q3** |
| **层4 存档** | `plan`/`intent`/驻留表落 `data_store` | ⏳ 未做 |

★ `WIRING.wired` 本轮从 `False` 改成 **`True`**（`used_by` 三项、`wired_how` 说明开关语义）——
因为层2 现在**真被产品调用**了（`_npc_scene_roster` 真读 `resident_of`，AST 可证）。

★ 用户若要**现在就看见效果**：把 `main.py` 的 `NPC_AUTONOMOUS_MOVE` 改成 `True` 即可
（默认 `False` 是刻意保守，保证零回归）。**这一步是否改默认值，我建议等 Q3 一起定** ——
因为它与层3（睡觉）合在一起才是完整的"过日子"。

---

## 9. 下一步

1. **层3 睡觉接线**（待 Q3）：`BEDTIME_HOME_SCENE = 'desktop'` → `choose_sleep_scene()`；
   ★ 旧行为须**显式标注"旧口径已废弃"**。
2. **层4 存档**：`plan` / `intent` / `RoamState` 落 `data_store`（vault=`E:\RalseiMemory\`）。
3. U1 收尾池：A4 `chkdsk E: /f`（**需用户管理员**）、B15 素材补采、B14 瓦片、B11 修 13 套件、B6。
4. R5 Z 键附身 / R6 带灵魂走 / R1 每人一个家 / R7 原作菜单键位（上一段遗留，继续生效）。

---

## 10. 留痕

- 新增：`ralsei_pet/modules/npc_roam.py`（零依赖）、
  `code-quality-audit/第79轮-自主生活驻留层/_tools/check79.py`（56 项）。
- 改动：`ralsei_pet/src/main.py`（常量 ×2 / import ×2 / `npc_roam` 建立 /
  `_npc_scene_roster` 读驻留表 / `_npc_roam_tick` 等 7 方法 / `update_movement` 挂载）、
  `code-quality-audit/regress/run_all.py`（注册 `check79`）、
  `code-quality-audit/regress/baseline.json`（9 套合并重固）。
- 回归：`PASS=3719 FAIL=0 套件=71`。
