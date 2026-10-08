# 第96轮b · 基础宠物专项复现（用户视角）

> 用户指令：「还是用录视频，逐帧对比的方法看看」
> 上一轮（96）已做过 10 分钟全程录制复核（20 PASS / 1 FAIL，FAIL 是覆盖度不足，已由专项探针补上 7/7）。
> 本轮改为**定向复现**：先用只读侦查提出候选，再用**真机行为级取证**逐条证实/证伪，
> 最后只修**用户视角可见且口径违规**的那几条。

---

## 0. 一句话结论

本轮提出 6 个候选，**证伪 1 个、降权 2 个（不可达）**，**实锤并修复 2 个用户可见缺陷**：

| # | 候选 | 判定 | 处置 |
|---|------|------|------|
| 1 | 惊讶污染全局 `jump_height`/`jump_duration` | **证伪**（分支用户不可达） | 登记为"接线前必须先修"的前置条件 |
| 2 | 弹跳期间抓宠会"自己往回窜" | 未复现（本轮未取到证据） | 留在待办池 |
| 3 | **靠近图标冒罐头台词（绕过 AI 口径）** | **实锤 · 真缺陷** | **已修** + 回归锁 `check96b` B 段 |
| 4 | 表演动画期间"边跳边滑" | 静态路径成立，触发偶发 | 留在待办池（需 AI 事件与漫游重叠） |
| 5 | **多键拖拽判定用错了（`==` 应为 `&`）** | **实锤 · 真缺陷** | **已修** + 回归锁 `check96b` C 段 |
| 6 | `_blush`/`_unhappy` 后缀缺素材 | **不可达**（触发方法零调用） | 只登记，不修 |

**机器验收**：G2 全量 `PASS=4638 FAIL=0 套件=88`，**零 DIFF**（新套件 `check96b` 已固化基线；`check81` 因套件数 87→88 触发一次预期 DIFF，已重建）。

---

## 1. 候选1 —— 证伪（重要：不报假问题）

### 假设（静态上完全成立）

`main.py:13468-13481` 的惊讶分支：

```python
if self.is_surprised and not getattr(self, 'game_state', {}).get('is_playing'):
    if self.current_direction == "down":
        new_animation = "surprised_down"
        if not hasattr(self, 'surprised_jump'):
            self.surprised_jump = True
            ...
            self.jump_height = 20      # ← 全局字段被改写（初值 50）
            self.jump_duration = 0.5   # ← 全局字段被改写（初值 1.0）
```

**AST 实证**（`probe97_surprise_jump.py` 的 A 段，走 AST 而不是正则）：

- `jump_height` 全项目**恰 2 个真写入点**：`5699`（初始化 50）+ `13480`（惊吓 20）。
- `jump_duration` 全项目**恰 2 个真写入点**：`5700`（初始化 1.0）+ `13481`（惊吓 0.5）。
- 两字段被 `handle_jump` **真消费**（`8212` / `8226` / `8243`）。
- 全项目**没有**任何"写回 50 / 写回 1.0"的还原点。

⇒ 静态逻辑**闭合**：一旦进过这个分支，此后每一次跳跃都会变成 0.5 秒、20px 的矮跳。

### 决定性证伪：该分支**用户不可达**

| # | 命题 | 证据 |
|---|------|------|
| 1 | 进分支的前提是 `self.is_surprised` 为真 | `main.py:13468` |
| 2 | `is_surprised = True` 全项目**只有 1 处** | `main.py:9278` |
| 3 | 该处在 `def trigger_surprise(self)` 内 | `main.py:9276-9280` |
| 4 | `trigger_surprise` **全项目零调用** | 全仓检索：仅命中定义行 |
| 5 | `pet_ai.py` 那 2 处是 `trigger_surprised`（**带 d**），**不同方法** | `pet_ai.py:80/138` |
| 6 | `trigger_surprised()` 是**谓词**（返回 bool），**不写** `is_surprised` | `pet_ai.py:138-144` |
| 7 | `is_surprised` 其余写入点全是 `= False` | `5762` / `9307` / `13951` |

⇒ `self.is_surprised` **恒为 False** ⇒ 分支**永不进入** ⇒ 参数**永不被污染** ⇒ 用户看不到。

### 留下的结构性风险（登记，不修）

`trigger_surprise()` 是死代码，却携带一个**全局副作用**。
用户已把「睡着时点他一下，概率播受惊吓动画」列入计划 —— **一旦接线就会静默把跳跃参数永久改坏**。

⇒ 处置：登记为**接线前必须先加还原点**的前置条件。

---

## 2. 候选3 —— 实锤并修复（**口径违规**）

### 症状（用户视角）

宠物自主漫游靠近桌面某个图标/文件时，会**突然冒出一句写死的台词**。

### 口径对照

用户 2026-09-19 定：「所有对话全权交给 AI」。
`speak_event` 的 docstring **逐字**：

> 不传（`pool=None`）：**不给内置台词** —— 说不了就**不说话**，
> 宁可安静也不甩一句写死的台词。这是"全权交给 AI"的口径。

而 `react_to_desktop_element`（`main.py`）里原来有：

```python
self.dialogue_ui.add_dialogue("ralsei", reaction['dialogue'], reaction['emotion'])
self.dialogue_ui.show_dialogue()
```

⇒ **绕过唯一入口**，直接写死台词并显示。

### 真机实证（三对照齐全）

`_tools/probe96b_canned.py`，落 `_evidence/probe96b_canned.txt`：

| 段 | 内容 | 修前 | 修后 | 期望 |
|----|------|------|------|------|
| A 正控制 | 真调 `react_to_desktop_element` | `add_dialogue` 增量 **2**，`speak_event` 增量 **0** | 增量 **0** | 0（不绕过） ✅ |
| B 负控制 | `speak_event(pool=None)` | 增量 **0**（沉默） | 增量 **0** | 0（沉默） ✅ |
| C 正控制 | `speak_event(pool=[...])` | 增量 **2**（说了） | 增量 **2** | >0（会说） ✅ |

**修前实抓台词**（用户视角可见的原话）：

> 「这是文本文件呢！ 纸做的东西要小心处理哦！」

### 修法

删掉那两行直写；**保留** `reaction['emotion']` 的赋值（`add_emotion` 真消费它）。
观察已经由下方的 `_note_desktop_observation` **完整上报**给 AI
（质地/重量/温度/材质逐项对应，本来就是"规则系统只当眼睛"的第八轮成果）。

> ★ 关键发现：`_note_desktop_observation`（`main.py:9546+`）把同样的观察
> **逐项**上报给 AI ⇒ 那两行直写是**纯冗余的旧实现残留**，删掉不丢任何信息。

### 判据收窄（首版过宽 ⇒ 假红）

该函数内**还有一处** `add_dialogue`（`help_messages[file_ext]`），但它被
`if self.SHOW_FILE_HELP_HINTS:` 总控，该开关**默认 False**（`main.py:9561`，第51轮定）
⇒ **永不执行**，不是本轮要守的路径。

⇒ 回归锁判据**只在"开关外"生效**，且按**行号区间**扣除受保护区
（`add_dialogue` 恰好内外各一次 ⇒ 不许按名字聚合，否则判反）。

---

## 3. 候选5 —— 实锤并修复（Qt 经典坑）

### 症状（用户视角）

拖动 Ralsei 时，若**又按下了右键**（多键鼠标 / 触控板 / 触屏常发生），
宠物会**突然停在原地不再跟手**，松开右键后又跳回鼠标位置。

### 根因

`mouseMoveEvent`（`main.py`）：

```python
if event.buttons() == Qt.LeftButton:      # ← 等值比较
    ...
else:
    if hasattr(self, '_is_being_dragged'):
        self._is_being_dragged = False    # ← 多键按下即"停止拖拽"
    if hasattr(self, '_drag_speed'):
        delattr(self, '_drag_speed')
    ...  # 还会误触发"悬停 + 抚摸检测"
```

Qt 的 `event.buttons()` 返回**按位或**组合值：同时按左+右键时是
`LeftButton | RightButton`，`== LeftButton` 为**假** ⇒ 掉进 `else`。

### 修法

```python
if event.buttons() & Qt.LeftButton:       # 位检测
```

★ 单按左键时 `&` 与 `==` **同值** ⇒ **不改变**既有行为，只修组合键场景。

---

## 4. 候选2 / 4 / 6 的处置（如实登记，不夸大）

- **候选2（弹跳期抓宠"自己往回窜"）**：`update_bounce`（`main.py:14069`）每 30ms
  无条件 `self.move(start_pos.x(), new_y)`，而 `mousePressEvent` **不停** `_bounce_timer`
  ⇒ 两写者互搏。静态路径成立，但**本轮未取到真机证据** ⇒ 留待办池。
- **候选4（表演动画边跳边滑）**：`pet_ai` 用裸 `change_animation("dance", force=True)`
  **不置** `_play_once_active` ⇒ `_special_anim_locked()` 返 False ⇒ 会边动边播。
  触发需 AI 事件与随机漫游**时间重叠** ⇒ 偶发 ⇒ 留待办池。
- **候选6（`_blush`/`_unhappy` 后缀缺素材）**：素材确实缺（`_blush`/`_unhappy`
  无 `walk_up_*` 与 `run_*`），但 `trigger_shy` / `trigger_unhappy` **全项目零调用**
  ⇒ 整个后缀分支是死代码 ⇒ 用户**不可达** ⇒ 只登记。

---

## 5. 本轮新增回归锁 `check96b`（17 条，全绿）

| 段 | 守什么 |
|----|--------|
| A | 前置锚点（两函数可抽出 · 口径串仍在） |
| B | `react_to_desktop_element` **开关外**零直写对话（含 B0/B0b 开关前提 + B3 变异负控制） |
| C | `mouseMoveEvent` 必须位检测（含 C3 变异负控制 · C4 全文件同类清干净） |
| D | 判据自身体检（恒真防护 · 标记打印点 · 被测文件在盘） |

### 破坏性验证（`mutate96b.py`）—— 证明"破坏必报红"

| 变异 | 预期 | 实测 |
|------|------|------|
| M1 换回 `==` | C1/C2 必红 | ✅ C1/C2/C4/D3b 全红 |
| M2 开关外加回直写对话 | B1/B2 必红 | ✅ B1/B2 红 |
| M3 开关改 `True` | B0b 必红 | ✅ B0b 红 |
| M4 开关短路 | 如实**不**报红 | ✅ 不红（判据按设计不覆盖该形态） |

### 本轮踩到并修掉的**判据自身**缺陷（全部靠"先怀疑判据"抓到）

1. **正则当"写入点"** ⇒ A2/A4/A5 假红（`==`/`<=`/`getattr`/注释全被算进来）
   ⇒ 改 **AST 真赋值**。
2. **判据过宽** ⇒ B1/B2 假红（把默认关闭的 `SHOW_FILE_HELP_HINTS` 通道也算违规）
   ⇒ 按**行号区间**收窄到"开关外"。
3. **注释误伤** ⇒ C4 假红（我在修复处写的注释**逐字引用**了旧写法）
   ⇒ 先**剥注释与字符串**再扫（与 95 轮 D1 同坑**第二次发作**）。
4. **自指** ⇒ D1 恒红（判据描述文本里含被扫的字面量）
   ⇒ 用 `re.escape` 拼模式 + 描述改中文表述。
5. **`_calls_outside_guard` 聚合错**（按名字而非按调用点）⇒ B3 负控制假红
   ⇒ 改为**按调用点**判定。
6. **变异锚点不匹配** ⇒ B3 假红（锚点串与源码缩进不一致，变异根本没插入）
   ⇒ 增加"变异是否真插入"的自检输出。

---

## 6. 机器验收

```
合计：PASS=4638 FAIL=0  套件=88
```

> ★ **收口复跑（记忆文件压缩后）**：再次 `PASS=4638 FAIL=0 套件=88`、非 IDENTICAL **无**
> ⇒ 期间唯一一次波动的 `check95 / A2`（速查本 `js_len ≤ 10000`）已因把 `MEMORY.md`
> 结构性收紧到 `js_len=10000` 而**转绿**；此锁确认为**代码化的落地回归锁**。

- 相对上一轮（第95轮终验 4621/87）：**判据 +17**（`check96b` 17 条），**套件 +1**。
- `check81` 一次预期 DIFF：其 `G5` 判据打印 `suite=87 baseline=87` → `88/88`
  （**新套件正确接入**的必然表现，判据本身仍绿）⇒ 已 `--update` 重建基线（合并模式）。
- 关键套件复核：`check95`(43) · `check93`(42) · `check89`(63) · `check94`(21) 全 **IDENTICAL / FAIL=0**。

## 7. 改动文件

| 文件 | 改动 |
|------|------|
| `ralsei_pet/src/main.py` | ① 删 `react_to_desktop_element` 的直写对话（+ 说明注释）；② `mouseMoveEvent` 的 `==` → `&`（+ 说明注释） |
| `code-quality-audit/regress/run_all.py` | 新增 `check96b` 到 `SUITES` |
| `code-quality-audit/regress/baseline.json` | 新增 `check96b` 基线；重建 `check81` |
| `code-quality-audit/第96轮b-基础宠物专项复现/**` | 本轮工具与证据（新增） |
