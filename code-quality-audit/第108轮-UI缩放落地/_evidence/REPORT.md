# 第108轮报告 · UI 缩放落地（缺口②：`ui_scale()` 零消费）

> 落点：`code-quality-audit/第108轮-UI缩放落地/`
> 工具：`_tools/check108.py`（52 PASS）· `_tools/mutate108.py`（10/10 命中）
> 产品改动：`ralsei_pet/src/main.py` · `modules/dialogue_ui.py` · `modules/item_menu_ui.py` · `modules/dr_textbox.py`

---

## §1 用户口径（逐字，第107轮，仍生效）

- 「**UI，也就是我所说的游戏中的对话框之类的也要放大**」
- 上游：「**全局都放大，也即半自动或者是手动可以调整宠物大小**」（⇒ `pet_scale` 是真源，UI 由它派生）
- 铁律：「一切根据原作」「别改我的要求啊」

## §2 缺口的确证（AST 实证，不是"看着像"）

第107轮交付时，`RalseiPet.ui_scale()`（`main.py:6923`）**有定义、零消费**：

```
ast.walk 查 Attribute(attr='ui_scale') / Name(id='ui_scale')  ⇒  两侧结果均为空
```

同时三个控件的尺寸/字号**全是硬编码**：

| 控件 | 文件 | 硬编码点数 |
|---|---|---|
| `DialogueUI` | `modules/dialogue_ui.py` | 22 个常量 |
| `ItemMenuUI` | `modules/item_menu_ui.py` | 5 个常量 |
| `DrTextboxFrame` | `modules/dr_textbox.py` | 5 个绘图常量 |

⇒ 第107轮只做了"半自动调宠物大小"，UI 一点没跟。

## §3 ★★★ 原作取证（关键：不许假装"原作也缩放"）

回查第44轮反编译产物 `_evidence/gml/`，原作 UI 尺寸**全是固定像素常量**：

- `scr_dbox`：`draw_rectangle(xxx+38, yyy+16, xxx+602, yyy+154)`
- `scr_darkbox`：`((xxx+32)-8, ...)`
- `scr_texttype`：`charline=33 / hspace=8 / vspace=18 / fnt_main em=12`
- `scr_textsetup`：只有传参，无缩放

### ⇒ 结论（必须如实写进代码注释）

**原作 UI 本身不缩放。** 原作是固定 320×240 视口，UI 就那么大；
**变的是我们的产品场景**——我们的场景等比放大铺满桌面，UI 不跟就会像"贴在放大画面上的小贴纸"。
所以「UI 随场景放大」是**我们的产品口径**（用户要求），不是"还原原作"。
⇒ 已把这段写进 `dialogue_ui.apply_ui_scale` / `item_menu_ui.apply_ui_scale` 的 docstring。

## §4 方案：基准快照 + 每次重算（幂等的唯一正解）

### 反面（会出事的写法）

在**现值**上乘：`self.BOX_INSET = int(self.BOX_INSET * s)`
⇒ `1.0 → 1.5 → 1.0` 走完，`BOX_INSET` 留在 `1.5×`，越改越大（残留）。

### 正解

控件构建完时拍一份 **`_ui_base`** 基准 dict，之后每次：
```
_i(key) = int(round(float(_ui_base[key]) * s))
```
从**基准**重算 ⇒ `f(f(x)) == f(x)`，折返必回原位。

### 倍率真源只有一处

`ui_scale() = (pet_scale / PET_SCALE_DEFAULT) ** 0.5`，钳 `[0.5, 3.0]`。
控件**不自己算倍率、也不自己存盘**（存一份 = 两份真源，本项目反复踩的裂缝）。
宿主统一算一次、统一**下发**：

```python
# main.py（新增）
def _apply_ui_scale(self):
    s = float(self.ui_scale())
    for name in ('dialogue_ui', 'item_menu_ui'):
        w = getattr(self, name, None)      # 缺一个不许全废：item_menu_ui 可能没建出来
        fn = getattr(w, 'apply_ui_scale', None)
        if callable(fn):
            fn(s)
```

两个入口都接线：
- `set_pet_scale()` 尾部 —— 用户改档（拖 spinbox）**立即**生效；
- `init_systems()` 尾部（`init_plot_mark()` 之后，排全链最末）—— 启动时用**读回的持久化倍率**发一次。
  ★ 光靠前者不够：`set_pet_scale` 只在用户改档时被调，上次设的 `2.0` 重启后 UI 不会生效。

## §5 落点清单（放大不能只放一族）

### `DialogueUI`
- 框体几何：`BOX_INSET` / `_base_width` / `_min_dialogue_h` / `_max_dialogue_h`
- 五个 `setFont`（光标 11 / 名字 12 / 正文 13 / 输入 11 / 发送 9）
- `_cursor_label` / `face_label` / `input_field` / `send_button` 的固定尺寸
- **HTML 内联字号**：`<div style="font-size:10pt">` 是**字符串字号**，`setFont` 管不到
  ⇒ 新增 `_html_pt(base_pt)`，四处拼接全改走它（不缩 = 框放大了、历史区还是小字）
- 头像贴图边长（`face_pix` 78）—— 不缩 = 框放大了、头像还是小的
- `_recalc_size_to_content` 的三个硬编码行高 `18 / 4 / 84` 改从基准派生
- 布局内缩 `setContentsMargins`
- 末尾 `_recalc_size_to_content()` + `_position_cursor_overlay()`

### `ItemMenuUI`
- `_panel_width` / `_frame.set_content_scale(s)` / 标题字号 / 提示字号
- **遍历 `self._rows` 重设已建行的字号 + `setFixedWidth`**（不重设 = 新版面 + 旧字号的拼接脸）
- 所有尺寸收口到 `_pt(key, fallback)`（唯一乘法入口，没有第二处乘法 = 没有两份真源）

### `DrTextboxFrame`（框体绘制）
- 新增 `paint_dark_box_scaled(painter, x1, y1, x2, y2, frame, scale, sprites=None)`：
  把框矩形四边按倍率换算后跑**同一套** `darkbox_blits` ⇒
  带厚 `BAND(32)×s` / 角块 `CORNER_SIZE×s` / 黑底内缩 `BLACK_INSET(14)×s` 全部自动等比
- 新增 `set_content_scale(s)` / `content_scale()`；`_content_scale = None` 时走**原路径**
- `paintEvent`：`None` 或 `1.0` ⇒ `paint_dark_box`（第44轮老行为，零回归）；否则走缩放版
- ★ 入参 `x1/y1/x2/y2` 与 `paint_dark_box` **同义（未缩放）**，缩放发生在函数内部，避免"乘两遍"

## §6 判据侧（`check108.py`，52 PASS / 0 FAIL）

结构性 8 段：A 消费点真存在 · B 下发面 · C 幂等 · D 非法输入 · E 落点齐 ·
F 框体缩放绘制 · G 零依赖+零回归 · H 判据自身体检。

**5 处"报红先怀疑判据"，全部归因到判据侧/夹具侧，无一是产品缺陷**：

| # | 症状 | 归因 | 修法 |
|---|---|---|---|
| 1 | `E1b` 残留=2 | 裸扫源码扫到 `_html_pt` docstring 里的**举例** | 只认 `f'<div style=` 的 f-string 行（**"禁某 API 出现"禁纯文本扫，第 5 次同类**） |
| 2 | `F3` 假红 | `_code_only()` 把 `getattr(self, '_content_scale', None)` 的**字符串属性名**剥了 | 改判 AST 结构（`getattr` 第二实参是 `Constant('_content_scale')`） |
| 3 | `A3c` 假红 | 控件名是**字符串字面量**，被 `_code_only` 剥掉 | 对**原文**判这两个令牌 |
| 4 | `G1` 3 处违规 | 判据范围**过宽**（判整个文件，抓到既有的 `import re`/`import html`） | 只判**本轮新增方法**（`_NEW_METHODS`） |
| 5 | `C3` 折返"残留" | **探针夹具不保真**（控件刚 new 时 `setFont` 从未被调，快照 `None`） | 基准点改在**构建完成态**（先 `apply_ui_scale(1.0)` 再取快照） |

外加：`H1` 检测器抓到我 `ok(..., True)` 恒真写法（**检测器是对的**）⇒ 改用变量 `_live`/`_dead`；
`H3b` 撤回算术恒真 ⇒ 改 `sys.stdout` 重定向的静默探针。

**真跑夹具（不靠"看代码像对的"）**：
- `_exec_methods()` 用 `ast.get_source_segment` **原样抽取产品方法体**再 `exec` 绑定到探针
  （★ **不许把产品代码抄一遍** —— 抄写 = 判据与被测物脱节）
- `F5` 等价性真跑：假画笔记录 `fillRect`/`drawPixmap` 调用序列，
  `scale == 1.0` 时缩放版与原版 **9 条绘制指令逐值相等**（零回归的算术保证）

## §7 变异测试（`mutate108.py`，10/10 命中）

每条防线逐条拆，确认**真报红且报的正是预期那条判据**：

```
[基线] 未变异 ⇒ FAIL=0（期望 0）
[HIT] M1  FAIL=1 · 命中 A2      宿主不再调 ui_scale()
[HIT] M2  FAIL=1 · 命中 B2      set_pet_scale 删下发
[HIT] M3  FAIL=1 · 命中 B2b/B3  init_systems 删下发（两判据同时报红 = 如实记录耦合）
[HIT] M4  FAIL=1 · 命中 C2      DialogueUI 不记基准
[HIT] M5  FAIL=3 · 命中 D       去掉 NaN 检查
[HIT] M6  FAIL=2 · 命中 E1      HTML 字号改回硬编码
[HIT] M7  FAIL=1 · 命中 F3      框体绘制不消费倍率
[HIT] M8  FAIL=1 · 命中 F6      不缩带厚
[HIT] M9  FAIL=1 · 命中 E7      菜单不遍历已有行
[HIT] M10 FAIL=1 · 命中 C2b     菜单 _pt 不走基准
变异测试：10/10 命中
```

### ★★★ 首跑只有 4/10 —— 其中 2 条是**真恒真判据**（比不写更危险）

| 变异体 | 症状 | 根因 | 修法 |
|---|---|---|---|
| M8 | **DEAD**（拆了不报红） | `F6` 只判源码里"**提到** `BAND` / `CORNER_SIZE`" | 改 AST：`QRect` 的宽/高实参**必须被 `_m(...)` 包裹** |
| M10 | **DEAD** | `C2b` 只判 `'_ui_base' in _menu_scale_src` | 改 AST：`_pt` 体内**真出现 `base[key]` 下标取值** |
| M4/M6/M7 | 锚点不可用 | 锚点串凭记忆写、与产品真身不符 | 换产品真身串 / `expect=2`（如实计数） |
| M3 | 命中了但不是 B2b | `init_systems` 删行后 `B3`（顺序判据）**同时**报红 | `expect` 扩为 `('B2b','B3')`，如实记录耦合 |

★ 这正是记忆里那条：**"变异测试全绿比报红更危险"** —— M8/M10 只是"提到名字就算数"，
产品真错（裸 `BAND` = 边框不缩）时判据照样绿。**加固后 M8/M10 都真报红。**

## §8 纪律遵守

- **EOL**：`main.py` 15911 CRLF / 0 bare LF，`dialogue_ui.py` 2437/2437 全 CRLF，
  两文件 Edit 后 EOL 未破坏；`dr_textbox.py` / `item_menu_ui.py` 全 LF。
- **四文件 `ast.parse` 全 OK**。
- **零依赖**：三个控件的新增方法**零函数内 import**（判据 G1 守）。
- **不写盘**：控件缩放**不自己持久化**（真源只有宿主 `pet_scale`；判据 G2 守）。
- **无倍率时逐字节等价**：`F3b` + `F5` 双保险。

## §9 全量回归

见 `code-quality-audit/regress/_out/`：`PASS / FAIL / 套件数` 见下节。

## §10 未决（下一批）

- **#35** 进入场景的原作式过渡动画（须先回原作取证：过渡形式/时长/可否跳过，**禁止自创**）
- **#36** 桌面与各作品的连接点核对
  （桌面⇄光世界小镇中心 / 桌面正下方 OneShot 暗门 / 桌面⇄UT 人类坠落处）
- `_apply_scale_to_scene()` 已确认**零调用**（现存路径走 `_refresh_pet_render_scale`）
