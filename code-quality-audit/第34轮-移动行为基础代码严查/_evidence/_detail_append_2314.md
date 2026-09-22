
---

### §23.14 第 34 轮续二：移动核心节拍缺陷 F34-1 + 三次自我推翻（2026-09-22 深夜）

用户口径（逐字）：「对了，检查一下尤其是**移动代码**，动画播放和有关楼层的代码」

#### ★ F34-1（真缺陷，已修 + 已锁）：5 秒节拍的时间戳被无条件推进

**位置**：`ralsei_pet/src/main.py` `update_movement`（L1655-2107，453 行 —— 移动核心），
原 L1690-1695。

**缺陷形态**：
```python
try:
    if not hasattr(self, '_last_desktop_elem_check') or current_time - self._last_desktop_elem_check > 5.0:
        self.check_nearby_desktop_elements()
except Exception as e:
    _log.warning(f"check_nearby_desktop_elements 异常: {e}")
self._last_desktop_elem_check = current_time      # ← 无条件执行（缺陷）
```
**机理**：时间戳每 tick（30ms）刷新 ⇒ `current_time - _last_... > 5.0` 除首次外恒假
⇒ `check_nearby_desktop_elements` **一生只跑一次**。

**最强旁证 = 同文件另两处节拍写法本就正确**：

| 位置 | 赋值位置 | 正确性 |
|---|---|---|
| `_last_env_update`（L1674-1682） | `if > 5.0:` 块内 | ✅ |
| `last_floor_check_time`（L1744-1756） | `if > interval:` 块内 | ✅ |
| `_last_desktop_elem_check`（L1691-1695） | `try` **外、无条件** | ❌ |

**注释与实现不符**（用户最在意的维度，两处）：
- L1686-1687 注释称「修复：时间戳更新放在 **try 外**」—— 意图对（防热循环），代价是**关掉功能**；
- L4158 注释称「（update_movement **每 5 秒一次**）自动触发」—— 与实现**正好相反**。

**后果链（真机可达）**：
```
check_nearby_desktop_elements()   ← 一生只跑 1 次
  → react_to_desktop_element()    ← 连带近乎从不执行
      → _note_desktop_observation()   ← 唯一调用点在此 ⇒ 从不执行
          ⇒ 「宠物凑近桌面文件/文件夹的观察」从不进入 AI 事件队列
```

**行为级铁证**（`_evidence/28_节拍时间戳失效.txt`，9/9 PASS）：

| 口径 | 20s(667 tick) | 60s(2000 tick) |
|---|---|---|
| 现写法（缺陷） | 1 次 | **1 次**（时间翻三倍、次数不变） |
| 修法 | 4 次 | 12 次（线性 = 5 秒节拍） |

探针自带**接线自证**（去节拍版 100 tick = 100 次）+ **负控制**（旧写法 60s = 1 次）。

**修法**：赋值移进 `if` 块内（与另两处同口径）。
关于"抛错防热循环"的替代：抛错 tick 不推进时间戳 ⇒ 下一 tick 重试一次；
但节拍判据要求"距上次**成功**检查满 5 秒"，最坏是持续抛错时才高频重试 ——
而 `check_nearby_desktop_elements` 内部是 `get_nearby_elements`（有缓存）+
`react_to_desktop_element`（30 秒防抖），**无热循环风险**。

**改动核验**：AST `Try 内首语句 = If` / `If 块内语句体 = [Call, Assign]` / 本级无裸赋值；
**CRLF 8967 行保持、0 单独 LF、无 BOM**。

**新回归锁 `round34b_move_beat`（13 项）**：
- A 结构：A1 本级不得有裸赋值 / A2 必须有一处在 if 体内 / **A3-A4 反向控制**（节拍判据与调用点不许被整体删掉）
- B 行为：B1 20s=4 / B2 60s=12 / B3 必须随时间增长 / **B4 接线自证** / **B5 负控制**（旧写法 60s 只 1 次）
- C 一致性：C1 `_last_env_update` / C2 `last_floor_check_time` 仍为块内赋值

**鉴别力体检**：回退修复 → **5 项报红（A1/A2/B1/B2/B3）rc=1**；还原 → 13/13 PASS rc=0。

#### ★★ 三次自我推翻（本轮最贵的产出，比修好的缺陷更有价值）

| # | 假设 | 结论 | **推翻依据（务必留存）** |
|---|---|---|---|
| 1 | `_handle_mouse_follow` 首次跟随"只加速不移动"（L2153 把 `self.move()` 包在 `_cached_screen_geom` 判空里，而该缓存**全项目只 L2005 一个写点**且在 `is_moving` 分支内） | **不成立** | `init_movement` **L1095 已置 `self.is_moving = True`** ⇒ 启动后首 tick 必进 is_moving 分支建缓存（30ms 内）⇒ "首次跟随不移动"在时钟上不可能发生。**仍记为设计脆弱点**（把"移动"耦合在"缓存可用"上） |
| 2 | `randomize_movement_pattern` 的 `is_moving=False` 分支（L1483/1492/1500/1508）未重置 `idle_timer` ⇒ 因判据 `idle_timer >= max_idle_duration` 而反复触发 | **不成立** | 调用方 `update_movement` 在 `randomize_movement_pattern()` 之后 **L2107 无条件 `self.idle_timer = 0`** ⇒ 两条路都被兜住 |
| 3 | `adjacent_lower_floor` 的 `idx < 0` 是死分支 | **成立但属防御性冗余** | `_index_of_floor` 三支返回值（`0`/`i-1`(i≥1)/`len-1`）**均 ≥0**（`26_楼户口径一致性.txt` S1a-S1h 全 PASS，含"旧写法 i-1 确为 -1"的负控制）⇒ 不可达。**按改动最小化不动** |

#### `get_jump_destinations` 口径不一致 → 成立但**产品路径不依赖**，非缺陷

`_evidence/27_跳跃候选分层核验.txt`（11/11 PASS）：
`_nearest_floor_jump`（L2427-2467）**刻意绕过**横向过滤 ——
- L2445-2453 显式补 `adjacent_lower_floor`（注释明写"贴边时 x 已出范围，会被漏掉"）；
- 候选一律过 `_floor_entry_plan`（L2362-2425）这道**真准入门**：`nearest_visible_point`
  可见吸附 + 吸附 >200px 拒绝。

⇒ `get_jump_destinations` 只是**种子集**，横向判据偏宽最坏是"少给一个候选"，
而该候选本就会被 `_floor_entry_plan` 拒掉。
**与"函数写对了 ≠ 产品用上了"互为镜像**：这条是"**函数写得不够齐，但产品不依赖它**"。

#### F34-3（技术债，零可见后果，**不修**）：`sprite_size = 100` vs 真实窗口 138×94

**静态事实**：全项目 8 处夹取，**只有 1 处**用硬编码标量：
| 位置 | 夹取量 |
|---|---|
| `generate_new_move_target` L1612/1620/1635/1636 | `sprite_size = int(50*2.0)` = **100**（单一标量，同时夹 X/Y） |
| `update_movement` L2009-2010 / `_handle_mouse_follow` L2155-2156 | `self.width()`/`self.height()` |
| `start_jump` L2793/2812/2818 / `_move_away_from_recycle_bin` L8521 / `_clamp_pos_to_desktop` L8613 | `self.width()` |

**真机取证**（`_evidence/29_真机窗口尺寸.txt`，`_probe_realwin.py`）：
⚠️ **`assets/sprites/` 在仓库里为空**（精灵图属用户本地资源）⇒ 帧尺寸**只能真机读**：
```
idle 帧 69×47（5 帧全同）→ _anim_container_size (69,47) → 窗口 138×94（= 69×2 / 47×2）
_cached_scale_factor = <未设置>（全项目**无任何赋值点** ⇒ getattr 恒取默认 2.0）
⇒ X 偏差 +38px（目标可越出可视区右侧 38px）/ Y 偏差 −6px（保守，无害）
```

**零可见后果的证明**（`30`+`31` 两步都做了）：
1. 到达判据 `distance_sq <= max((speed*3)^2, 30^2)` = **30px 容差**；
2. **目标生成本身也用同一个 `sprite_size` 夹取**（L1635/1636）⇒ 目标被生成在 `right-100` 以内；
3. 走到该边界时距目标必然 <30px ⇒ **必判到达**；
4. **穷举**（目标 x 1500→1920）：**"修法能到、硬编码到不了"的 x = 0 个**
   ⇒ 38px 偏差被 30px 容差**完全吸收**，**不存在临界区**。

⇒ 归入 **P3 技术债（口径统一）**。理由：改要动 4 行、收益为零；真正该统一的是
"所有夹取量都走 `self.width()/self.height()`"这条口径，适合与 P3 其他项一并做。

#### F34-2 / 其他

- **F34-2**：`check_desktop_element_at_target`（L2188）**零调用点** ⇒ 死函数，记 P3。
- `initiate_auto_mouse_drag`（L2198）接了定时器（L987）但函数体直接 `return`
  —— 第十三轮**主动禁用**（"宠物不该抢用户的鼠标"）⇒ **有意为之，非缺陷**。

#### 本轮新增的两条操作纪律

- **纪律 A：能从运行时读到的量，就不要靠推算。**
  F34-3 若靠 `int(50*2.0)=100` 反推，会得出"窗口就是 100×100、sprite_size 正确"的**反向结论**。
  真机读属性 30 秒定案 —— 而"`assets/sprites/` 为空"这个事实本身就已说明必须真机。
- **纪律 B：零可见后果的"不一致"要显式定性为技术债，不要顺手改。**
  F34-3 与 §23.9.2 的口径不一致都是真事实，但顺手"统一"= 无收益改动 + 无谓回归风险。
  正确做法：写清事实 → 量清后果（本次做了穷举） → **归入 P3**。
- **纪律 C（§23.12.1 的延伸）：推翻一个假设后，把"推翻依据"本身也变成证据。**
  本轮的"L1095 已置 is_moving"、"L2107 无条件清零 idle_timer"、"`_nearest_floor_jump`
  刻意绕过横向过滤"这三条，比"我查过了"有价值得多 —— 后人才不会重走。

#### G2 终态（第 34 轮续二）

**PASS=1440 FAIL=0，30 套件**（原 29 套件全 IDENTICAL + 新套件 `round34b_move_beat` 13 项；
1427+13=1440 账目吻合）。工作区无 `.pyc` 污染。

证据：`26_楼户口径一致性.txt`、`27_跳跃候选分层核验.txt`、`28_节拍时间戳失效.txt`、
`29_真机窗口尺寸.txt`、`30_sprite_size后果验证.txt`、`31_sprite_size边界精算.txt`。
报告：`第三十四轮移动行为基础代码严查报告_2026-09-22.md` 31308 → **38773 字符**（新增 §十五/§十六）。
