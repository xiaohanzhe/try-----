
---

## 第 34 轮（续二）：移动核心节拍缺陷 F34-1 —— 一条真缺陷 + 三次自我推翻

> 用户指令（逐字）：「对了，检查一下尤其是**移动代码**，动画播放和有关楼层的代码」

### 确定成果

**★ F34-1（真缺陷，已修 + 已锁）**：`main.py` `update_movement` 里
`check_nearby_desktop_elements` 的 5 秒节拍**失效**。

- 缺陷形态：时间戳 `self._last_desktop_elem_check = current_time` 写在 `try`
  **之外、无条件执行**（L1695）⇒ 每 tick（30ms）刷新 ⇒ `> 5.0` 除首次外恒假
  ⇒ 该检查**一生只跑一次**。
- 同文件另两处节拍（`_last_env_update` L1674-1682 / `last_floor_check_time`
  L1744-1756）写法**本就正确**（赋值在条件块内）⇒ 证明是疏漏。
- **注释与实现不符**（用户最在意维度）：L1686-1687 注释说"时间戳放 try 外"是修复
  （意图对：防热循环），代价却是关掉功能；L4158 注释说"每 5 秒一次"与实现相反。
- 后果链：`check_nearby_desktop_elements` → `react_to_desktop_element` →
  `_note_desktop_observation`（唯一调用点在此）⇒ **"凑近桌面文件的观察"从不入 AI 事件队列**。
- 修法：赋值移进 `if` 块内（与另两处同口径）。
- 行为级铁证：现写法 20s=1 次 / 60s=**仍 1 次**；修法 20s=4 次 / 60s=12 次（线性）。
- 新回归锁 `round34b_move_beat`（13 项）：AST 结构 A1/A2 + 反向控制 A3/A4 +
  行为 B1/B2/B3 + 接线自证 B4 + **负控制 B5**（旧写法 60s 只 1 次）+ 一致性 C1/C2。
- 鉴别力体检：回退修复 → **5 项报红 rc=1**；还原 → 13/13 PASS rc=0。

### ★★ 本轮 4 次假设检验，3 次自我推翻（核心教训）

| 假设 | 结论 | 推翻依据（比结论更有价值） |
|---|---|---|
| `_handle_mouse_follow` 首次跟随"只加速不移动" | **不成立** | `init_movement` **L1095 已置 `self.is_moving = True`** ⇒ 首 tick 必进 is_moving 分支建缓存（L2005 是唯一写点）；30ms 内缓存必存在 |
| `randomize_movement_pattern` 的 `is_moving=False` 未重置 `idle_timer` → 反复触发 | **不成立** | 调用方 `update_movement` **L2107 无条件 `self.idle_timer = 0`**，两条路都被兜住 |
| `adjacent_lower_floor` 的 `idx < 0` 是死分支 | **成立但属防御性冗余** | `_index_of_floor` 三支返回值均 ≥0（第 34 轮已修）⇒ 不可达。**按改动最小化不动** |
| `get_jump_destinations` 横向用 rect / 纵向用可见区（口径不一致） | **成立但非缺陷** | `_nearest_floor_jump` **刻意绕过**横向过滤（L2445-2453 显式补 `adjacent_lower_floor`）+ 真准入门是 `_floor_entry_plan`（可见吸附 + >200px 拒绝） |

**新增纪律**：
- **能从运行时读到的量，就不要靠推算**（F34-3 靠 100 反推会得出反向结论；真机读一次定案）。
- **零可见后果的"不一致"要显式定性为技术债，不要顺手改**（无收益 + 无谓回归风险）。
- **推翻一个假设后，把"推翻依据"本身也变成证据**。

### F34-3（技术债，零可见后果，**不修**）

`generate_new_move_target` 硬编码 `sprite_size = int(50*2.0) = 100`（单一标量同时夹 X/Y），
而全项目其余 7 处夹取一律用 `self.width()/self.height()`。

真机实测（`assets/sprites/` 仓库为空 ⇒ **必须真机**）：
```
idle 帧 69×47 → _anim_container_size (69,47) → 窗口 138×94（= 69×2 / 47×2）
_cached_scale_factor = <未设置>（全项目无赋值点 ⇒ getattr 恒取默认 2.0）
⇒ X 偏差 +38px / Y 偏差 −6px
```
**零可见后果的证明**：到达容差 30px；且**目标生成本身也用同一 `sprite_size` 夹取**
⇒ 目标被生成在 `right-100` 以内 ⇒ 走到边界时距目标必 <30px ⇒ 必判到达。
**穷举**（目标 x 1500→1920）：**"修法能到、硬编码到不了"的 x = 0 个**，38px 偏差被 30px 容差完全吸收，无临界区。
⇒ 归入 **P3 技术债（口径统一）**。

### 其他

- **F34-2**：`check_desktop_element_at_target`（L2188）**零调用点** ⇒ 死函数，记 P3。
- `initiate_auto_mouse_drag`（L2198）接了定时器但函数体 `return`（第十三轮主动禁用）⇒ **有意为之，非缺陷**。
- 全量 G2：**PASS=1440 FAIL=0，30 套件**（1427+13=1440，账目吻合）。
- 证据：`26_楼户口径一致性.txt` `27_跳跃候选分层核验.txt` `28_节拍时间戳失效.txt`
  `29_真机窗口尺寸.txt` `30_sprite_size后果验证.txt` `31_sprite_size边界精算.txt`。
- 报告：`第三十四轮移动行为基础代码严查报告_2026-09-22.md` 31308 → **38773 字符**（新增 §十五/§十六）。
