
---

## 十五、追加范围（用户第 34 轮续指令）：移动核心 `update_movement` 的节拍缺陷

> 用户口径（逐字）：「对了，检查一下尤其是**移动代码**，动画播放和有关楼层的代码」

### 15.1 结论速览

| 编号 | 结论 | 定性 | 处置 |
|---|---|---|---|
| **F34-1** | `update_movement` 里 `check_nearby_desktop_elements` 的 5 秒节拍**失效**，该检查一生只跑一次 | ★ **真缺陷**（用户可感知） | **已修 + 已锁** |
| F34-2 | `check_desktop_element_at_target` 零调用点 | 死函数（低危） | 记入 P3 待办 |
| F34-3 | `generate_new_move_target` 硬编码 `sprite_size=100`，与产品 `self.width()/height()`（实测 138×94）口径不一致 | **技术债，零可见后果**（已用穷举证明） | 记入 P3 待办 |
| — | `_handle_mouse_follow` 首次跟随不移动 / `idle_timer` 未重置导致死循环 / `adjacent_lower_floor` 的 `idx<0` 死分支 / `get_jump_destinations` 横向口径 | **三条假设全部被推翻**，一条属防御性冗余 | **不改** |

### 15.2 ★ F34-1：节拍时间戳被无条件推进 ⇒ 5 秒节拍失效（真缺陷，已修）

**缺陷形态**（改动前，`main.py` L1690-1695）：

```python
try:
    if not hasattr(self, '_last_desktop_elem_check') or current_time - self._last_desktop_elem_check > 5.0:
        self.check_nearby_desktop_elements()
except Exception as e:
    _log.warning(f"check_nearby_desktop_elements 异常: {e}")
self._last_desktop_elem_check = current_time      # ← 无条件执行（缺陷）
```

**机理**：时间戳每 tick（30 ms）都被刷新 ⇒ 下一次比较 `current_time - _last_... > 5.0` 恒为 `0.03 > 5.0` = **假** ⇒ 该检查除启动后首次外**永不触发**。

**同文件另两处节拍写法本来就正确**（这是最重要的旁证 —— 说明是疏漏而非有意设计）：

| 位置 | 时间戳赋值位置 | 正确性 |
|---|---|---|
| `_last_env_update`（L1674-1682） | `if > 5.0:` **块内** | ✅ |
| `last_floor_check_time`（L1744-1756） | `if > interval:` **块内** | ✅ |
| `_last_desktop_elem_check`（L1691-1695） | `try` **外、无条件** | ❌ **缺陷** |

**注释与实现不符**（用户最在意的维度）：
- L1686-1687 注释写「修复：时间戳更新放在 **try 外**——原来在 try 内，若 check_* 抛错则时间戳不更新，每 30ms 全量重试（性能热循环）」——**修法意图对（防热循环），代价却是彻底关掉了这个功能**；
- L4158 注释写「（update_movement **每 5 秒一次** check_nearby_desktop_elements）自动触发」——**与实际行为相反**。

**后果链（真机可达）**：

```
check_nearby_desktop_elements()   ← 一生只跑 1 次
  → react_to_desktop_element()    ← 连带近乎从不执行（其自身有 30s 防抖，非问题来源）
      → _note_desktop_observation()   ← 唯一调用点在此 ⇒ 从不执行
          ⇒ 「宠物凑近桌面文件/文件夹的观察」从不进入 AI 事件队列
```

**行为级铁证**（`_evidence/28_节拍时间戳失效.txt`，`_probe_beat_timestamp.py`，9/9 PASS）：

| 口径 | 20 秒（667 tick） | 60 秒（2000 tick） |
|---|---|---|
| **现写法**（缺陷） | 触发 **1** 次 | 触发 **1** 次 ← 时间翻三倍，次数不变 |
| **修法** | 触发 **4** 次 | 触发 **12** 次（线性，符合 5 秒节拍） |

自证与鉴别力：桩接线自证（去节拍版 100 tick = 100 次，证明桩与调用链确实是通的）；负控制（旧写法 60 秒 = 1 次）。

**修法**（最小改动，赋值移进 `if` 块，与另两处同口径）：

```python
try:
    if not hasattr(self, '_last_desktop_elem_check') or current_time - self._last_desktop_elem_check > 5.0:
        self.check_nearby_desktop_elements()
        self._last_desktop_elem_check = current_time
except Exception as e:
    _log.warning(f"check_nearby_desktop_elements 异常: {e}")
```

关于原注释担心的"抛错则每 tick 全量重试"：改为块内赋值后，抛错那一 tick 不推进时间戳，下一 tick 会重试一次；但**节拍判据本身**要求"距上次**成功**检查满 5 秒"，所以最坏情形是每秒 33 次重试仅在**持续抛错**时发生 —— 而 `check_nearby_desktop_elements` 内部是 `get_nearby_elements`（有缓存）+ `react_to_desktop_element`（有 30 秒防抖），无热循环风险。

**改动核验**：AST 确认 `Try 内首语句 = If`、`If 块内语句体 = [Call, Assign]`、本级无裸赋值；**CRLF 8967 行保持、0 单独 LF、无 BOM**。

### 15.3 回归锁 `round34b_move_beat`（13 项）

`code-quality-audit/第34轮-移动行为基础代码严查/verify_round34b_move_beat.py`

判据纪律：**AST 判结构（不断言写法）** + **逐字抽取该片段用最小 self 桩跑**。

| 组 | 断言 |
|---|---|
| A 结构 | A1 本级不得有裸赋值；A2 必须有一处落在 if 体内；A3/A4 **反向控制**（节拍判据与调用点不许被整体删掉） |
| B 行为 | B1 20s 触发 4 次；B2 60s 触发 12 次；B3 次数必须随时间增长；B4 **接线自证**（无节拍版 100 tick = 100 次）；B5 **负控制**（旧写法 60s 只 1 次） |
| C 一致性 | C1/C2 `_last_env_update` / `last_floor_check_time` 仍为块内赋值（防"修一处、改坏另两处"） |

**鉴别力体检**：把修复回退成缺陷写法 → **5 项报红**（A1/A2/B1/B2/B3）、rc=1；还原 → **13/13 PASS、rc=0**。

### 15.4 ⚠️ 本轮"查过但**不成立**"的四条（重要，防后续误改）

> 本轮共做 **4 次假设检验，3 次自我推翻**。教训与 §14.2 同源：**先怀疑判据，再怀疑被测物**。

**(1) `_handle_mouse_follow` 首次跟随"只加速不移动"？→ 不成立**

疑点：L2153 `if getattr(self, '_cached_screen_geom', None) is not None:` 把 `self.move()` 包在缓存判空里，而 `_cached_screen_geom` **全项目只有 L2005 一个写入点**（且位于 `is_moving` 分支）。
推翻依据：`init_movement` L1095 设 `self.is_moving = True` ⇒ 启动后第一次 `update_movement` 必定进 `is_moving` 分支并建立缓存 ⇒ 30 ms 内缓存必然存在。**"首次跟随不移动"在时钟上不可能发生。**
※ 仍记录为**设计脆弱点**（把"移动"耦合在"夹取缓存可用"上），但不构成缺陷，本轮不动。

**(2) `randomize_movement_pattern` 的 `is_moving = False` 分支未重置 `idle_timer` → 反复触发？→ 不成立**

疑点：L1483/1492/1500/1508 设 `is_moving = False` 时**没有** `idle_timer = 0`，而 `idle_timer` 判据是 `>= max_idle_duration`。
推翻依据：`idle_timer` 的调用方 `update_movement` 在 `randomize_movement_pattern()` 之后 **L2107 无条件 `self.idle_timer = 0`** ⇒ 两条路（`generate_new_move_target` / 休息分支）都被兜住。

**(3) `adjacent_lower_floor` 的 `idx < 0` 分支是死分支？→ 成立，但属防御性冗余，不改**

`_index_of_floor` 经第 34 轮修复后，三支返回值（`0` / `i-1`(i≥1) / `len-1`）**均 ≥ 0**（`_evidence/26_楼户口径一致性.txt`，S1a-S1h 全 PASS，含"旧写法 `i-1` 在此场景确为 -1"的负控制）。
结论：`idx < 0` 是**不可达的防御分支**。留着无害、删了要动第 34 轮刚锁定的函数 ⇒ 按"改动最小化"，**不动**。

**(4) `get_jump_destinations` 横向用 `rect`、纵向用可见区（口径不一致）→ 成立，但产品路径不依赖，非缺陷**

`_evidence/27_跳跃候选分层核验.txt`（11/11 PASS）证明：`_nearest_floor_jump`（L2427-2467）**刻意绕过** `get_jump_destinations` 的横向过滤 ——
- L2445-2453 显式补 `adjacent_lower_floor`（注释明确写"贴边时 x 已出范围，会被漏掉"）；
- 每个候选都要过 `_floor_entry_plan`（L2362-2425）这道**真正的准入门**：`nearest_visible_point` 可见吸附 + 吸附距离 > 200 px 直接拒绝。

⇒ `get_jump_destinations` 的候选只是**种子集**，横向判据偏宽不会导致"跳错地方"，最坏是"少给一个候选"，而该候选本就会被 `_floor_entry_plan` 拒掉。**这是"函数写得不够齐，但产品路径不依赖它"** —— 与第 34 轮"函数写对了 ≠ 产品用上了"互为镜像，同样值得记录。

### 15.5 ★ F34-3：`sprite_size=100` 与真实窗口 138×94 口径不一致（技术债，零可见后果）

**静态事实**（全项目 8 处夹取，**只有 1 处**用硬编码标量）：

| 位置 | 夹取量 |
|---|---|
| `generate_new_move_target` L1612/1620/1635/1636 | `sprite_size = int(50 * 2.0)` = **100**（单一标量，同时用于 X/Y） |
| `update_movement` L2009-2010 | `self.width()` / `self.height()` |
| `_handle_mouse_follow` L2155-2156 | `self.width()` / `self.height()` |
| `start_jump` L2793/2812/2818 | `self.width()` |
| `_move_away_from_recycle_bin` L8521 / `_clamp_pos_to_desktop` L8613 | `self.width()` |

**真机取证**（`_evidence/29_真机窗口尺寸.txt`，`_probe_realwin.py`；`assets/sprites/` 在仓库里为空，精灵图属用户本地资源 ⇒ **必须真机**）：

```
idle 帧原始尺寸        = 69 × 47（5 帧全同）
_anim_container_size   = (69, 47)
_cached_scale_factor   = <未设置>（⇒ getattr 恒取默认 2.0；且全项目无任何赋值点）
实际窗口 self.width()/height() = 138 × 94   ← 恰为 69×2 / 47×2
硬编码 sprite_size     = 100
⇒ X 偏差 +38 px（目标可越出可视区右侧 38 px）
⇒ Y 偏差 −6 px（保守，无害）
```

**为什么零可见后果**（`_evidence/30` 与 `31`，两步都做了）：

1. 到达判据是 `distance_sq <= max((speed*3)^2, 30^2)` = **30 px 容差**；
2. **目标生成本身也用同一个 `sprite_size` 夹取**（L1635/1636）⇒ 目标被生成在 `screen.right() - 100` 以内；
3. 宠物走到该边界时距目标必然 < 30 px ⇒ **一定判到达**。

**穷举验证**（`31_sprite_size边界精算.txt`）：目标 x 从 1500 到 1920 全枚举，**"修法能到、硬编码到不了"的 x 个数 = 0**。38 px 偏差被 30 px 容差**完全吸收**，**不存在临界区**。

⇒ **处置：不修，记入 P3 技术债（口径统一）**。理由：改它要动 4 行且收益为零；真正该统一的是"所有夹取量都走 `self.width()/self.height()`"这条口径，适合与"楼层区间口径统一"等 P3 项一并做。

### 15.6 本线 G2 / 工作区

- 全量 G2（新增套件后）：**PASS=1440 FAIL=0，30 套件**（原 29 套件全 IDENTICAL + 新套件 `round34b_move_beat` 13 项）；
- 工作区无 `.pyc` 污染（G2 的 `compileall` 产物已被 `git checkout --` 处理）；
- 证据：`26_楼户口径一致性.txt`、`27_跳跃候选分层核验.txt`、`28_节拍时间戳失效.txt`、`29_真机窗口尺寸.txt`、`30_sprite_size后果验证.txt`、`31_sprite_size边界精算.txt`。

---

## 十六、第 34 轮续 · 方法论追加（第 4 次自我推翻记录）

本文 §6 立过"探针误报率 55%"这条。本轮追加范围（§14-§15）**再添 4 个案例，3 个被推翻**，累计误报率维持高位。归纳新增的两条操作纪律：

**纪律 A：能从运行时读到的量，就不要靠推算。**
F34-3 的"138×94"如果靠 `int(50*2.0)=100` 反推，会得出"窗口就是 100×100、sprite_size 正确"的**反向结论**。真机读属性 30 秒就能定案 —— 而仓库里 `assets/sprites/` 为空这个事实本身，就已经说明"必须真机"。

**纪律 B：零可见后果的"不一致"要显式定性为技术债，不要顺手改。**
F34-3 与 §11.3 的口径不一致都是真事实，但如果顺手"统一"了，就产生了**无收益的改动 + 无谓的回归风险**。正确做法是：写清事实、量清后果（本次做了穷举证明"0 个卡住点"）、**归入 P3**。

**纪律 C（复用 §14.2 的延伸）：推翻一个假设后，要顺手把"推翻依据"本身也变成证据。**
本轮的"`init_movement` L1095 已置 `is_moving=True`"、"L2107 无条件清零 `idle_timer`"、"`_nearest_floor_jump` 刻意绕过横向过滤"这三条，都是**推翻依据**。它们比"我查过了"有价值得多 —— 后人才不会重走一遍。
