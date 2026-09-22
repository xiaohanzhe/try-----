
---

## 十一、★ 第 34 轮追加：楼层实现细查（用户指令「仔细检查那个楼层的实现」）

**对象**：`ralsei_pet/modules/floor_manager.py`（27 969 B / 633 行 / `FloorManager` 24 方法，全文通读）
**关联**：`desktop_interaction.py`（窗口枚举）＋ `main.py` 的接入点
（`check_window_movement` / `_start_climb_transition` / `start_jump` / `handle_jump` /
`_follow_floor_move` / `_sync_window_cache_from_floor`）

### 11.1 结论速览

**查出 1 个真缺陷（已修，F7）＋ 1 处口径不一致（低危，不改）＋ 三条核心不变量经复核成立。**

### 11.2 ★ F7：`_index_of_floor` 退化分支返回 `-1` 不是安全哨兵（真缺陷，已修）

**源码**（`floor_manager.py` L477-494，修复前）：

```python
for i, floor in enumerate(all_floors):
    if floor['platform_height'] <= cur_h:
        return i - 1          # ← i == 0 时返回 -1
return len(all_floors) - 1
```

**判据错在哪**：`i - 1` 在本函数语境里表示「**当前楼层高于第 i 层**」。
但 `i == 0` 时它返回 **-1**，而 **两个消费方都不把 -1 当"未找到"**，
而是当成"**比最高的活楼层还高**"：

| 消费方 | `idx = -1` 的实际效果 | 正确语义 |
|---|---|---|
| `get_drop_destination`（L506 `range(current_index+1, n)`） | `range(0, n)` ⇒ 从**最高**活楼层起向下扫 ⇒ 第一块能接住的就是最高的那块 ⇒ **宠物被"上吸"到更高的层** | 落到**下方第一块**能接住的板 |
| `adjacent_lower_floor`（L570 `if idx < 0: return None`） | 直接 `None` ⇒ 语义是"**已在最底层、下面没楼板了**"，可桌面明明在下面 ⇒ **有下层却报"到底了"** | 返回相邻的下一层 |

> 注：`_floor_identity` 的 docstring 里**恰好记着同型的"凭空被上吸"历史缺陷**（第十三轮修过一次）。
> 本缺陷是那条的历史遗留复现路径 —— 那次只修了"用 dict 内容比较"，没修"退化成 -1"。

**触发条件（真机可达）**：宠物站在**当前最高的那个窗口**上 → 用户把这个窗口**关掉** →
`self.current_floor` 仍持有那只已消失窗口的旧 dict（`window_hwnd` 已不在 `underlying_windows` 里），
而 `update_floors()` 重建后「最高活楼层」比它低 ⇒ 按高度找"`<= cur_h`"的第一项就是 `i == 0` ⇒ 返回 -1。

**受控取证（正控制 vs 被测，只改 `current_floor` 的取值）** ——
布局刻意用**重叠窗口**（真实桌面常态）：`h=10` 占 y300..699、`h=5` 占 y500..899，宠物 (200,600) 同落两块板内。

| | 正控制（`current_floor` = 活楼层 h=10） | 被测（`current_floor` = 已消失的 h=15） |
|---|---|---|
| `_index_of_floor` | 0 | **-1** |
| `get_drop_destination` | **h=5** ✅（下面第一块） | **h=10** ❌（被"上吸"一层） |
| `adjacent_lower_floor` | **h=5** ✅ | **None** ❌（谎报"下面没楼板"） |

证据：`_evidence/11_floor_index_受控取证v4.txt`（修复前）、`12_floor_index_修复后复验.txt`（修复后 → 两项都回到 h=5）。

**修复**（保持 `i >= 1` 的原语义，只规范 `i == 0` 这一支）：

```python
return 0 if i == 0 else i - 1
```

**为什么是 0 而不是别的**：0 = 「落在最高活楼层**之上**」，
于是 `current_index + 1 == 1` ⇒ 向下扫时从**第二高**的活楼层开始，
正好对应"关掉最高的楼板 → 掉到下一个活楼层或桌面"的既有口径（§4.9 第十四/十七轮）。

**回归锁**：新套件 `round34_floor_manager`（15 项），**全部调用产品真函数**，正负控制成对
（[A] 退化分支 + [B] 落点单调性 + [C] 相邻下层 + [D] 正常路径 `i>=1` 不许被改坏 + [E] 桌面口径）。
**鉴别力体检**：把修复行回退成 `return i - 1` → **6 项报红（rc=1）**；还原后**逐字节核验一致**、15/15 全绿。
证据：`_evidence/14_鉴别力体检_floor.txt`。

### 11.3 ⚠️ 口径不一致（低危，**本轮不改**）

`_rect_tuple` / `_cut` / `visible_subrects` 全程用**半开区间**（`right = left + width`），
而 `nearest_visible_point` 与 `get_jump_destinations` 用 **`QRect.right()` / `.bottom()`**（= `left + w - 1`，**闭区间**）⇒ 潜在差 1px。

**实测影响面（`_evidence/13_闭区间混用影响面核验.txt`）**：**可忽略**。原因：
`nearest_visible_point` 的输出随后要过 `floor_visible_contains`，而后者用的是**同一套 `QRect.contains`**（也是闭区间）
⇒ **内部自洽**，吸附结果永远落在"它自己认为可见"的区域里，不存在"吸到区域外"。

⇒ 差 1px 与 `MIN_FLOOR_VISIBLE_AREA = 40*40 = 1600 px²` 的判据尺度相差 3 个数量级，
**不可能改变任何"站得住 / 站不住"的结论**。**故只记录、不动**（改动会引入无收益的风险面）。

### 11.4 经复核**成立**的核心不变量（勿动）

| 不变量 | 复核结论 |
|---|---|
| `visible_subrects(target, blockers)` 两两不重叠 + 并集精确 | ✅ `_cut` **构造性**保证 ⇒ **可见面积可直接求和**（`MIN_FLOOR_VISIBLE_AREA` 判据因此才成立） |
| `platform_height = (n - i) * 5`，桌面恒 0 | ✅ 窗口最低层 = 5，**桌面 0 = 唯一最大层高差基准** ⇒ 与"下跳显式 `adjacent_lower_floor`、桌面返回 None（不穿透）"自洽 |
| `_generate_floors` 只在**成立的楼层**里累加遮挡者 | ✅ 可见面积跌破阈值 ⇒ 该层"暂时不存在"且**不再遮挡更低窗口** —— 与 §4.9 口径完全一致 |

### 11.5 楼层线遗留（并入 P3 技术债）

| # | 位置 | 事项 | 判定 |
|---|---|---|---|
| 1 | `get_floors_above` / `get_jump_destinations` | 闭区间 vs 半开区间口径统一 | 低危（实测无危害），**建议与 P3 同批处理** |
| 2 | `_index_of_floor` | ~~退化分支返回 -1~~ | ✅ **本轮已修（F7）** |
| 3 | `_index_of_floor` | 依赖调用方自律的隐式契约（已加 docstring 说明） | 记录，暂不动 |

---

## 十二、第 34 轮追加：跳跃动画统一 `jump_ball`（用户口径）

### 12.1 用户口径（逐字）

> 「他**跳跃动画统一用 jump_ball 代替，只有摔下去的时候用原来的**」

### 12.2 ★ 关键发现：`has_ball` 是**恒假字段**

全项目**只有 `main.py:1170` 一处赋值**：`self.has_ball = False` —— **永远不为 True**。

后果：所有 `if self.has_ball: "jump_ball" elif: "jump"` 分支里，
**`jump_ball` 那条是死的**，实际**永远走 `jump`**。这解释了"为什么跳跃动画一直是 `jump`"。

### 12.3 改动点（3 处，均在 `main.py`）

| # | 位置 | 改前 | 改后 |
|---|---|---|---|
| 1 | `start_jump` 起跳准备帧 | `jump_ready` | **`jump_ball`** |
| 2 | `handle_jump`（L3049 附近） | `if has_ball → jump_ball / else → jump` | **写死 `jump_ball`** |
| 3 | `update_animation` 的 `jump_phase` 推进 | `ready`→`jump_ready`、`jumping`→`jump` | 两阶段都 → **`jump_ball`** |

⚠️ **不受影响**：`_jump_anim_override`（"跨度大"选型，`climb_*` 攀爬素材）**优先于**上述默认值 —— 那是独立机制的选型。
⚠️ **未改**：`L919-921` 帧率表、`L236 / L6278 / L6357 / L6399 / L7738` 动画名清单（字典键 / 注册，不能动）。

> **决策留痕**：`jump_ready` → `jump_ball` 是**我按"统一"字面口径做的判断**
> （原文只点名 `jump_ball`，没说 `ready` 帧怎么办）。理由是"整个跳跃过程只有一种素材"最贴合"统一"。
> **用户可一句话推翻**（改回一行即可）。

### 12.4 真机（离屏）验证 —— 走**产品真对象**

证据：`_evidence/15_跳跃动画真机离屏验证.txt`，**10/10 PASS**。

```
[A] start_jump 起跳准备帧
  [PASS] start_jump 期间切到过 jump_ball（实测序列 ['jump_ball']）
  [PASS] start_jump 期间**不再**切 jump_ready（实测 ['jump_ball']）
[B] has_ball 开关不再影响跳跃选型（对照组应一致）
  [PASS] has_ball=False 与 True 的跳跃动画序列一致（['jump_ball'] vs ['jump_ball']）
[C] 坠落链路（"摔下去"）仍用原来的素材
  [PASS] start_falling(reason=None)           → ['fall']      （非 jump_ball）
  [PASS] start_falling(reason='floor_removed')→ ['fall_mad']  （非 jump_ball）
```

**B 组的意义**：把 `has_ball` 分别置 False / True，跳跃动画序列**完全一致** ⇒
证明"恒假条件已被去掉"，不再存在"分支永远走另一条"的隐蔽性。
**C 组的意义**：用户要求的例外（「只有摔下去的时候用原来的」）**被真正保住** ——
常规坠落 `fall`、用户抽楼板 `fall_mad`，两者都没有被改成 `jump_ball`。

### 12.5 素材侧核验

- `assets/animations.json` 中 `jump_ball` 已注册：**4 帧**（`spr_ralsei_jump_ball_0..3.png`），`climb_front/left/right` 亦在册；
- 素材文件实际存在于仓根 `deltarune_ralsei/`（非 `assets/sprites/`，该目录为空）；
- 真机启动日志：`已从 animations.json 加载 112 组动画（legacy 28 组，schema=1）`，
  且收尾行 `本轮运行未出现未命中的动画名（已加载 493 组）` ⇒ **`jump_ball` 无 miss**。
