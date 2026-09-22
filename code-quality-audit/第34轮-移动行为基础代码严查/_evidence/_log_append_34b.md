
---

## 第 34 轮（续）· 楼层实现细查 + 跳跃动画统一 jump_ball（2026-09-22 夜）

### 用户本轮两条指令（逐字）
- 「他**跳跃动画统一用 jump_ball 代替，只有摔下去的时候用原来的**」
- 「还有，**仔细检查那个楼层的实现**」

### 落地改动（F1~F7）
| 编号 | 文件 | 内容 |
|---|---|---|
| F1 | `src/main.py` | 删假 Qt 钩子 `mouseEnterEvent`/`mouseLeaveEvent` |
| F2 | `src/main.py` | 删死字段 `fall_start_time`（6 写 0 读） |
| F3 | `src/main.py` | 合并 `init_movement` 5 组重复赋值（⚠️ `max_fall_duration` 取 **2.0**，后赋值胜） |
| F4 | `src/main.py` | `start_fall` 四分支 `is_moving=False` 提到分支前 |
| F5 | `modules/logger_utils.py` | `_SafeTimedRotatingFileHandler` 兜住 rollover 失败 |
| F6 | `src/main.py` | 跳跃动画统一 `jump_ball`（3 处） |
| **F7** | **`modules/floor_manager.py`** | **`_index_of_floor` 退化分支 `i-1` → `0 if i==0 else i-1`（本轮最重发现）** |

### ★★ F7：本轮最重发现（`_index_of_floor` 返回 -1 不是安全哨兵）
- **起因**：用户指令「仔细检查那个楼层的实现」→ 通读 `floor_manager.py` 633 行 / 24 方法。
- **缺陷**：退化分支 `return i - 1` 在 `i == 0` 时返回 **-1**。
  而 `-1` 被两个消费方误读成"**比最高活楼层还高**"，不是"未找到"：
  · `get_drop_destination`：`range(-1+1, n)` = `range(0, n)` → 从**最高**活楼层起扫
    → 宠物**被"上吸"到更高的层**（实测 h=5 → h=10）；
  · `adjacent_lower_floor`：`idx < 0` → 直接 `None`，语义是"**下面没楼板了**"
    → **明明有下一层却报"到底了"**。
- **触发路径（真机可达）**：宠物站在**当前最高的窗口**上 → 用户**关掉它** →
  `current_floor` 仍持已消失窗口的旧 dict，重建后最高活楼层更低 → 按高度找 `<= cur_h` 首项即 `i == 0`。
- **与历史的关系**：`_floor_identity` docstring 里**恰好记着同型的"凭空被上吸"缺陷**（第十三轮修过）。
  那次只修了"别用 dict 内容比较"，**没修"退化成 -1"** → 这是该缺陷的遗留复现路径。
- **修复**：`return 0 if i == 0 else i - 1`（0 = 落在最高活楼层之上；
  `current_index + 1 == 1` ⇒ 向下扫从第二高开始，与"关掉最高楼板 → 掉到下一层或桌面"一致）。
- **受控取证**（关键：布局必须用**重叠窗口**，否则两种情形结果相同、**测不出差异** —— 我前两版探针都栽在这里）：
  正控制 `get_drop_destination`=h5 / 被测=h10；`adjacent_lower_floor` 正控制=h5 / 被测=None。
  修复后两项都回到 h5。证据 `_evidence/11_*.txt`（修前）、`12_*.txt`（修后）。

### ★ 探针几何选错两次（值得记的教训）
- v1/v2 探针把宠物放在"没有任何楼板覆盖"的位置（y=400 / y=850）→ 两种情形都得桌面 0，**对照不出差异**，
  而我却在注释里**写死了错误的期望值**（"应得 h=5"）→ 差点把"探针选错几何"误判成"缺陷不成立"。
- **通则**：对照实验里"看不到差异"有两种可能 —— ① 确实无差异 ② **夹具没把差异逼出来**。
  必须先把期望值算清楚，再解释结果；**不能拿"没差异"当结论**。

### ★ 楼层实现的其余结论
- **三条核心不变量经复核成立**（勿动）：`visible_subrects` 两两不重叠+并集精确（`_cut` 构造性）；
  `platform_height=(n-i)*5` 与桌面 0 的量纲自洽；`_generate_floors` 只在成立的楼层里累加遮挡者。
- **1 处口径不一致（低危，不改）**：`nearest_visible_point` / `get_jump_destinations` 用 `QRect` 闭区间
  （`right()=left+w-1`），而 `_rect_tuple` 用半开区间 ⇒ 潜在差 1px。
  **实测无危害**：产物要过 `floor_visible_contains`，而后者用同一套 `QRect.contains` ⇒ **内部自洽**，
  且 1px 与 `MIN_FLOOR_VISIBLE_AREA=1600px²` 差 3 个数量级。证据 `_evidence/13_*.txt`。

### ★ `has_ball` 是恒假字段（新发现）
- 全项目**只有 `main.py:1170` 一处赋值** `self.has_ball = False`，**永不为 True**。
- ⇒ 所有 `if has_ball → jump_ball / else → jump` 分支里 **`jump_ball` 那条是死的**，
  实际**永远走 `jump`** —— 这就是"为什么跳跃动画一直是 jump"。
- F6 因此把三处二选一直接写死为 `jump_ball`。

### 回归锁
- 新增 `round34_movement`（36 项，本轮把其中一条断言从"打印绝对行号"改为"断言相对先后"）+
  `round34_floor_manager`（15 项，全部走产品真函数 + 正负控制成对）。
- **鉴别力体检 5/5 全过**（假钩子 / 死字段 / 初值 5.0 / 裸 handler / `return i-1`，全被抓，rc=1），
  且每次体检后**逐字节核验修复文件已还原**。
- ★ **新教训：回归锁断言里不许打印绝对行号** —— `round34_movement` 原先打印 `assign@3479 < branch@3482`，
  我在 `start_fall` 上方插了注释（F4 的说明）→ 行号漂移 → **G2 报 DIFF**，
  而这次 DIFF **与判据完全无关**。⇒ 断言相对关系，消息里只打布尔结果。

### 最终 G2
`PASS=1410 FAIL=0`，**28 套件全 IDENTICAL**，rc=0。
（基线路径：26 套/1359 → 27 套/1395 → **28 套/1410**）

### 真机
- GUI 启动 **42s 存活、RSS 25.1MB、零 Traceback / 零 ERROR / 零 `Logging error`**（F5 在真机也成立）。
- 离屏驱动产品真对象验证跳跃动画：**10/10 PASS**（A 起跳帧 / B `has_ball` 对照 / C 坠落链路未被改）。
- ⚠️ 杀进程时踩到**假阳性**：我的探针脚本命令行里含 `main.py` + `ralsei` 字面量 →
  被 `psutil` 匹配成"残留桌宠"。**判据要精确**（`c.endswith('main.py')` + 有 `src` 段），否则自欺。

### 本轮遗留
- P3 技术债新增：楼层"区间口径统一"（低危）。
- 生命周期/存储/配置线（task #13）、交互线深度部分（task #14）仍未开始。
