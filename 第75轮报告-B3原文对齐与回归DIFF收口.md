# 第75轮报告（三）—— B3 手势判定原文对齐 + 回归 DIFF 收口

- **日期**：2026-10-02
- **范围**：第75轮最后一组遗留 —— ① B3「宠物手势判定唯一真源」的**原文对齐**；
  ② 全量回归 11 个 DIFF 的**逐个定性 + 基线重录**；③ 回归基础设施的一处**真缺陷修复**；
  ④ 顺手加强一处**过窄判据**（`check76` C5 → C5a/b/c）
- **全量回归**：修前 `PASS=3462 FAIL=4 套件=66` ⇒ 修后 **`PASS=3531 FAIL=0 套件=66`，零 DIFF**
- **配套证据**：`_evidence/diff_triage75.txt`（定性总表）· `_evidence/normalize_recheck75.txt`（复检真跑）
  · `_evidence/b3_kind_map75.txt`（22 项 kind 全矩阵）· `_evidence/logger_recheck75.txt`

---

## 一、B3：宠物手势判定的「唯一真源」必须与**原文**对齐

### 1.1 背景
第75轮把 `main.py` 里**散落四处的**手写手势判定（`mousePressEvent` / `mouseMoveEvent` /
`mouseReleaseEvent` / `mouseDoubleClickEvent` 各写一份部位识别 + 手势识别，约 666 行）
统一到 `modules/pet_interaction.py`，实现"唯一真源"。

**但收口复检发现：迁移时我"按合理重写"了内容，偏离了原文 —— 而且是静默的**
（不报错、不报红、回归也不亮）。这是本轮**最贵的一类坑**。

### 1.2 三类静默漂移（逐条回 `git show HEAD:ralsei_pet/src/main.py` 原文核对后修回）

| # | 漂移内容 | 原文实际 | 后果 |
|---|---|---|---|
| ① | `_REGIONS_PERCENT` **丢掉 `belly` 整条**，9 条数值被重调，丢 `WHOLE_BODY` 兜底 | `("belly",35,60,65,80)` 独立成条；`ear(0,0,30,40)`/`hair(25,10,75,50)` 等 12 条 | 拍肚子永不触发；部位识别边界整体偏移 |
| ② | `RESPONSE_SPEC` 的**情绪 / 动画 / 台词几乎全错**（15 条） | 逐条来自 HEAD 的 `show_emotion` / `play_animation_once` / 台词字面量 | 同一手势给错的反应 |
| ③ | `_PRESS_KINDS` **删过头** —— 漏 `body→press_body`、`belly→pat_belly` | HEAD 长按链六分支里有这两支 | 长按躯干/肚子无反应 |

### 1.3 两个**真 bug**（不是迁移漂移，是逻辑缺陷）

**(a) `kind_for` 的 PINCH / PULL 分表查 ⇒ 间歇性无反应**
```python
# 修前：各自表里查
if g == Gesture.PINCH.value: return _PRESS_KINDS[Gesture.PINCH].get(p)
if g == Gesture.PULL.value:  return _PRESS_KINDS[Gesture.PULL].get(p)
```
`GestureTracker` 会把"长按**且移动**"判成 `PULL` —— 于是用户**捏住耳朵稍微拖一下**就从
`pinch_ear` 掉进"PULL 表里没有 ear ⇒ `None`"，表现为"**捏耳朵有时有反应有时没有**"。

> ★ 依据：HEAD 原文只有**一条**"长按 ≥0.5s"的 if/elif 链，分支**只看 `clicked_part`**，
> 完全不看长按期间有没有移动。⇒ 改为**合并查两张表**。

**(b) `dialogue_ui._stream_reset` 开关关掉时**不擦半句****（由 `s8_stream` D14 抓到）
```python
# 修前：擦半句被错放进 if 分支
if AI_THINKING_PLACEHOLDER_ENABLED:
    self.typing_text = self.AI_THINKING_PLACEHOLDER
    self.typing_index = len(self.typing_text)
# 开关关掉 ⇒ 整段跳过 ⇒ typing_text 原样保留那半句
```
后果：判退重采样时屏幕上变成"**旧半句 + 新句**"黏在一起。
修法：把"擦掉"移出 `if`，两档都真的清。

### 1.4 对齐结果
- `kind_for` 全矩阵 **22/22 产出、零未登记**，`RESPONSE_SPEC` **零死项**（15 条）
- `import main` 端到端 OK（`BodyPart.BELLY` 生效、区域表 12 行、SPEC 15 项）
- 回归锁 `check76` **61/61**、`check75b` **59/59**、`s7_event_speech` **139/139**、`s8_stream` **73/73 IDENTICAL**
- 全矩阵见 `_evidence/b3_kind_map75.txt`

---

## 二、★★★ 两条"**判据自己会说谎**"的教训（本轮第 62~70 轮同型的第 N 次）

第62~70 轮每轮都栽在**判据侧**、零产物错。本轮又添两条，且**都是"读错了文件"**：

### 2.1 `_out/*.diff.txt` **是陈旧文件，绝不能当证据**
`write_diff()` 只在 **DIFF 时**重写，套件恢复正常（IDENTICAL）后**旧文件原地留着不删**。
实测：`round12_store.diff.txt` 时间戳 `10-01 10:45`，而同名 `.txt` 是 `10-02 13:08`。
⇒ 我一度"看到 19 个 DIFF"，**其中一半是几天前的陈旧文件**。

**真判据（唯一）**：拿**当前** `normalize()` 重算 sha256，与 `baseline.json` 的 `sha256` **逐条比**。

### 2.2 `_out/*.baseline.txt` **不是**基线快照
实测 `companion_round46.baseline.txt` 用当前 `normalize()` 算 `c6b88edc`，
而 `baseline.json` 里是 `c1bb4d72` —— **对不上**。它可能是上一次 `--update` 的残留，也可能是某次运行的 raw 副本。
⇒ 要复现基线只能用 `--show-diff <id>` 或**重跑 + 比 sha**。

> 两条都已写进 `run_all.py` 的 `write_diff()` docstring（防下次再被骗）。

---

## 三、修的一处**回归基础设施真缺陷**：`normalize()` 漏了 traceback 行号

### 3.1 现象
`companion_round46` / `items_round48` 变成假 DIFF，**diff 内容除 `line NNN` 外逐字相同**
（`RuntimeError: 故意炸`、断言行全一致）。根因：本轮在 5 个被 traceback 引用的模块
**靠前位置**插了注释 ⇒ 下游行号整体 **+28**。

### 3.2 为什么必须修
行号是**纯脆性信息**：任何人在任一被 traceback 引用的文件上方插一行，
**几十个套件就集体假红**（而且 PASS/FAIL 计数一条不变 —— 最容易骗过人）。

### 3.3 改法（`run_all.py`）
1. 新增 `_TRACEBACK_LN = re.compile(r'(,\s*line\s+)\d+(,\s*in\s)')`，在 `normalize()` 里抹平。
2. `_ENV_NOISE` 补三类**环境状态**：
   - `global_hotkey` 的**成功与失败两种终态行**（★ 必须都排，否则基线录到"成功"、下次跑到"失败"就是假 DIFF）
   - **旧形态裸文本** `RegisterHotKey 失败 …`（logger 修复前的写法，基线里存的是它）
   - `item_menu` 的 `菜单页面未启用：X（nodata）`

### 3.4 ★★ 判定"环境 vs 行为"的**铁证**
`check73` 与 `check67` 是**同一份基线、相邻两次运行**：
- `check73`：`全局热键已注册：ctrl+alt+S/E/H（id=0x1000~1002）`
- `check67`：`RegisterHotKey 失败 key=ctrl+alt+S/E/H …`

**同一份代码两次运行互斥出现** ⇒ 唯一变量 = 本机这三个热键有没有被别的程序占用
⇒ **环境状态，不是被测行为**。

### 3.5 代价（如实登记，写进代码注释）
- 抹平行号后，「同一异常**换位置**抛」看不见 —— 但那**不是**套件该守的东西
  （套件守"异常被兜住 + 状态回滚"）。
- 排除热键行后，「热键功能**整个挂掉**」看不见 —— 真守它的是紧随其后的
  「全局热键未装上：… ⇒ 仍可用"宠物窗口有焦点时按 S / E"」**兜底路径**（代码自己拼的，不随环境变）。

---

## 四、十一个 DIFF 的定性（逐个，**非批量 `--update`**）

| 类 | 数 | 套件 | 根因 |
|---|---|---|---|
| **A** logger 修复预期效果 | 5 | `check67` `round8_anim` `soul_round55` `npc_persona55` `npc_place56` | 裸文本 → 带 logger 前缀；`item_menu` INFO 行重新出现 |
| **B** 判据变更（我改的） | 3 | `check76`(59→61) `check75b`(58→59) `s7_event_speech`(137→139) | A5a/A5c 新增、C1 改 AST、C1n 新增、期望集加 `ear_ruffle` |
| **C** traceback 行号漂移 | 2 | `companion_round46` `items_round48` | 行号 +28（零行为变化，见 §3.1） |
| **D** 转正 | 1 | `check75c` | 已注册但 `baseline.json` **原先无此条目**（**不是 `None`**，上轮记录有误） |

★ **没有一个是真回归**。全部明细见 `_evidence/diff_triage75.txt`。

### ★★★ "DIFF 必看"这次真抓到了东西
`npc_place56` 的 diff 里除 logger 行外，T1 判据打印的 import 列表也变了
（出现 `adopt_module_logger`、`EntertainmentSystem` 被挤出）。
**单独核实**：两者**全在 `main.py` 里**，差异来自 **T1 判据的 AST 扫描窗口截断**
⇒ **PASS 计数不变**，不阻塞。
> 技术债记一笔：`npc_place56` T1 的 import 断言应改成**集合相等**而非打印字符串比对。

---

## 五、`main.py` 改动复核（属"改到重要核心文件"）

`git diff --stat` = **−347 / +264**（净 −83 行）。两处实质改动：

1. **真 bug 修复 —— 25 个模块的日志曾全丢**
   `except ImportError` 降级路径原先 `def get_logger(name): return logging.getLogger(name)`
   ⇒ 拿到**裸名**（`modules.xxx`），既**不在 `ralsei_pet` 树下**（没有文件 handler），
   有效级别又退回 WARNING ⇒ **INFO 级日志全部丢失**。这正是"程序坏了但日志里查不到"的根因。
   现改为三层降级兜底挂到 `ralsei_pet.*` 树下。
2. **B3 接线**：`from modules.pet_interaction import (...)`，手写判定 666 行删除。

---

## 六、顺手加强一处**过窄判据**（`check76` C5 → C5a/b/c）

### 6.1 问题
`C5` 原判据：`_sync_pet_tracker_sprite` 真被调用且**同步点 >= 2 处**。

看着合理，但它守不住最常见的退化：**新增第三个 `sprite_label.setPixmap(...)` 却忘了同步**
⇒ 同步点数仍是 2，判据照样 PASS，而部位识别会在那个新路径上按旧尺寸算、整体偏移。
（这正是 docstring 自己警告的那件事，判据却没守住。）

### 6.2 改法（配对判据 + 双向控制）
- `C5a`：对**每一个** `setPixmap` 调用点，断言它**之后**存在同步点，且两者之间不夹别的 `setPixmap`。
- `C5b` **正控制**：合成"3 处 `setPixmap`、只有 2 处同步"的源码走**同一套**配对逻辑，必须判出 1 个坏点
  （实测 `坏点=[9]` ⇒ 判据有鉴别力）。
- `C5c` **负控制**：全配对的合成源码不许被判缺。

### 6.3 实测
```
[PASS] C5  _sync_pet_tracker_sprite 真被调用（2 处，换帧都要同步）
[PASS] C5a 每个 setPixmap 之后都有同步（2 处 setPixmap / 2 处同步；未配对=无）
[PASS] C5b 正控制：合成的"3 换帧 2 同步"必须被判缺（坏点=[9]）
[PASS] C5c 负控制：全配对的合成源码不许被判缺（坏点=无）
```
`check76` 61 → **64** 项。

> ★ 通用形状：**凡"数量 >= N"的判据，先问一句「N 不变、但结构退化」时它还守得住吗？**

### 6.4 ★★ 连"篡改自证工具"自己都会漏检（第三层）
`tamper76.py`（mutate-and-revert 自证）原本打 **"8/10 命中"、退出码 0**，
但其中 **⑨⑩ 两个用例 `SKIP`**（夹具串找不到）——**最有价值的两个**（`BELLY` 优先级、
事件名登记）**根本没跑**，而总结把它们混在分母里、**静默通过**。

**根因（连着踩了三层）**：
1. ⑨ 的夹具写的是 `(BodyPart.BELLY,   35.0, 60.0, 65.0, 80.0),`（`65.0` 前 1 空格 + 行尾注释），
   而实现为视觉对齐写的是 **2 个空格、无注释** ⇒ 逐字匹配失败。
2. ⑩ 的夹具写 `_PUSH_DEFAULT = "poke_default"` —— 那是**初版**的常量名，
   回原文对齐后实现里**已不存在** ⇒ 恒找不到。
3. ★★ **修 ⑨ 时我又踩了一个更隐蔽的**：把夹具改成逐字两行后**仍 SKIP** ——
   因为源码里 BELLY 行与 TORSO 行**中间隔着 `# 躯干区域` 这行注释**。
   （症状极难查：`A in src` 真、`B in src` 真，但 `A\nB in src` 假。）

**修法（三次都对，第三次才彻底）**：
- ⑨⑩ 夹具改为**从当前源码逐字拷出**（连注释行一起）；
- `SKIP` 改为**显式计数并导致退出码非 0**（不许静默混过）；
- ★ 中途我曾试图"把匹配器改成行内空白不敏感"来一劳永逸 —— **结果把原本正确的 ①~⑧
  全部弄坏**（`\s+` 跨行贪婪 ⇒ 替换后源码语法坏 ⇒ 被测脚本崩 ⇒ `FAIL=-1` 假 MISS）。
  **已整体回退**，只在 `case()` docstring 里记下这条："**夹具就该逐字，别自作聪明**"。

**最终**：`10/10 命中、0 SKIP、退出码 0`，还原后 `PASS=64 FAIL=0`。

> ★★ 教训：**自证工具的"通过"必须包含"每个用例都真的跑了"**。
> `SKIP` 是一种**假通过** —— 比 MISS 更危险，因为它看起来像没事。

---

## 七、验收与自证

| 项 | 结果 |
|---|---|
| 全量回归 | **`PASS=3531 FAIL=0 套件=66`，尾部逐条 `IDENTICAL`（零 DIFF）** |
| 一致性 | `SUITES=66` == `baseline 条目=66`，无重复 / 无缺失 / 无 `None` |
| `run_all.py` 六类复检 | **14/14 PASS**（含正负控制：新 ENV 三支 4/4 命中、兜底路径 0/2 误吞、`_TRACEBACK_LN` 归一 + 非数字行号不动） |
| 逐令牌回验 | **30/30 PASS** |
| `check76` 判据加强 | 61 → **64**，含 C5b 正控制真抓漏同步 |
| `tamper76` 自证 | **10/10 命中、0 SKIP、退出码 0**（修前 8/10 且 2 个 SKIP 静默混过）|
| 改注释后复跑 | 仍零 FAIL、零 DIFF |
| 暂存区 `--numstat` | 插入 5159 / 删除 513（**< 1000 停手线**）；唯一大额删除 = `main.py` 已复核 |

---

## 八、方法论沉淀（供后续轮次直接引用）

1. **"删干净"校验不报错 ≠ 没问题** —— 迁移类改动必须**逐条回原文**（本轮三类静默漂移全靠人眼对原文抓到）。
2. **不报红时也要逐条核对 DIFF** —— 漂移类问题不报错、不报红。
3. **判据报红先怀疑判据** —— 本轮 4 个 FAIL 里 **2 个**（`check75b` C1、`s7` C1）根因在判据侧。
4. **能上 AST 就上 AST** —— `check75b` C1 用子串匹配被自己 docstring 误伤；改 AST 后配正控制。
5. **正则/判据"只认一种写法"会把整条事实丢掉** —— `s7` C1 三连坑（漏注释行 / 只认双引号 / `": ("` vs `_spec(`）。
6. **改归一化器 ⇒ 全部基线必须按新尺子重录**（这是 `--update` 的标准场景，与"掩盖 DIFF"无关）；
   但重录前必须**逐类定性**、**不许裸跑 `--update`**。
7. **环境状态与行为变化必须分开** —— 判据要能说清"这行的**内容变了**（改进，该进基线）"vs
   "这行**这次出现了**（环境，该排除）"。
8. **凡"数量 >= N"的判据，先问「N 不变、但结构退化」时它还守得住吗** —— 守不住就是过窄
   （本轮 `check76` C5 就是这样被加强成 C5a/b/c 配对判据）。
9. **"看回归结果"这个动作本身会骗人** —— `_out/*.diff.txt` 是陈旧的、`*.baseline.txt` 不是基线；
   **唯一真判据 = 拿当前归一化函数重算哈希与基线逐条比**。
10. **改了归一化器 ⇒ 用旧尺子做双尺对照**（动态加载改动前的备份），先把"真实行为变化"隔离出来，
    再逐类定性、分批 `--update`。

---

## 附：本轮沉淀进 skill

以上 §2（判据宽窄偏差）· §2.1/2.2（回归工具假证据）· §3（改归一化器纪律）· §7.1（迁移必回原文）
四条已写进用户级 skill `pyqt-code-audit` 的「验证脚本自身的坑」一节（14732 字节，结构复检通过）。
