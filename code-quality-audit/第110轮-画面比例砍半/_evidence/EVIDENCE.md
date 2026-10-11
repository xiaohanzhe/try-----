# 第110轮 · 场景画面比例砍半 + 真机抓帧抓出的画布 bug

## 0. 用户口径（逐字）

- 「**别这么大啊**」
- 「**到刚才的一半才好一些**」

指第107轮那版"铺满整屏"的场景画面：2560×1600 屏上被放大到 **2133×1600**
（占屏 83%×100%），`camera.scale = 6.666` ⇒ Ralsei 行走精灵被画成约 **273px** 高。

## 1. 落地（单点真源）

| 位置 | 改动 |
|---|---|
| `ralsei_pet/modules/scene_camera.py` | 新增 `SCENE_FIT_FRACTION = 0.5`（唯一自由度）+ `fit_fraction(view_w, view_h, ratio, fraction)` 纯函数（= `fit_fullscreen` 结果矩形 × fraction，**偏移按整块屏幕**重新居中） |
| `ralsei_pet/modules/scene_controller.py` | `fit_camera_to_screen` 改调 `fit_fraction(...)`；日志加"比例 %.2f" |
| `ralsei_pet/src/main.py` | ★ **`_update_scene_layer` 调用顺序修正**（见 §3） |

**一处改、三处动**（本项目最贵的坑 = 两处各写一份真源）：
`fit_camera_to_screen` 的 `scale = out_w / scoped_w` ⇒ 砍半后 `scale` 自动减半
⇒ `main.py` 的 `_cached_scale_factor = camera.scale × pet_scale` 跟着减半
⇒ **宠物同步变小**；`ui_scale()` 由 `pet_scale` 派生（与 scale 无关）⇒ UI 不受影响。

### 为什么不改 `fit_fullscreen` 的入参

`fit_fullscreen` 是纯函数、有单测锚点（`check107 A5` 逐值钉死
`(2560,1600) → (2133,1600,214,0)`）。写成 `fit_fullscreen(sw*fr, sh*fr, ratio)`
会把**居中偏移**算成"相对半块屏" ⇒ 画面偏到左上角。
⇒ 保 `fit_fullscreen` 不动，"占多大比例"独立成具名常量，在结果矩形上缩比 + 重居中。

## 2. 数值（2560×1600 主屏，真机实测）

| | 第107轮（内接满屏） | 第110轮（×0.5） |
|---|---|---|
| 画面 | 2133×1600（占屏 83%×100%） | **1066×800**（占屏 42%×50%） |
| 偏移 | (214, 0) | **(747, 400)** |
| `camera.scale` | 6.666 | **3.331** |
| Ralsei 高 | ≈273px | **≈137px** |

**`fraction == 1.0` 时逐值等价 `fit_fullscreen`** ⇒ 本层是它的严格泛化，不是替换
（旧基线语义不会被悄悄改写）。

## 3. ★★★ 真机抓帧抓出的活 bug（第107/108/109 三轮漏网）

### 症状（`_evidence/frames110/k001_room.png` 修前）

房间画面贴在屏幕**左上角**、四周黑边**不出现** —— 黑块只有 1066×800
（实测 `x∈[0,1065], y∈[0,799]`），而屏是 2560×1600。

### 根因

`SceneCanvas.set_plan(plan, view_size)` 内部会 `resize(view_size)`，
而 `_update_scene_layer` 传的 `view = scene.plan_viewport()` 是**相机尺寸
（= 画面尺寸）**。它紧随 `canvas.resize(sw, sh)`（整屏）之后
⇒ **后写覆盖前写** ⇒ 画布实际变成"画面那么大"。
后果：`paintEvent` 的 `fillRect(self.rect(), 黑)` 只填画面那块 ⇒ 黑边消失。

### 为什么前三轮是假绿（判据缺口）

- 第107轮离屏录屏用 **800×600 屏 ⇒ 画面恰好也是 800×600**（4:3 零黑边）
  ⇒ `view == 整屏` ⇒ 覆盖后**看不出差别**（`rec107_meta.txt` S1 因此假绿）。
- 第109轮真机**已现形**（`rec109_meta.txt` 记录 `canvas=(2133,1600)` ≠ 屏 2560×1600），
  但那一轮**没断言** canvas == 屏 ⇒ 漏网。
- 第110轮画面砍半后（1066×800 vs 屏 2560×1600）差异立刻显形。

### 修法

`set_plan` 之后**再 `resize` 一次到整屏尺寸**：

```python
canvas.set_plan(behind, view)
canvas.resize(int(sw), int(sh))     # ★ 必须最后铺整屏（set_plan 会按画面尺寸覆盖）
self._place_scene_layer()
```

## 4. 判据

### 4a. 改判（旧判据被新自由度误伤 ⇒ AST 化，**不许弱化**）

| 旧 | 新 | 理由 |
|---|---|---|
| `check107 B3` `'frac' not in _fcs_code`（纯文本扫） | **AST 判形参**：`fit_camera_to_screen` 签名里无 `frac`/`fraction` | `SCENE_FIT_FRACTION` / `fit_fraction` 含子串 "frac" ⇒ 误伤。守的真东西 =「比例是**内读常量**，不由调用方传」 |
| `check107 B4` `'fit_fullscreen' in _fcs_code` | `'fit_fraction' in _fcs_code` + **B4b**：`fit_fraction` 内部委托 `fit_fullscreen` | 几何仍走纯函数，只是多一层委托 ⇒ 守"委托链不断" |
| `check106 B5 / B5b` 同上两条 | 同上 | 同步 |

### 4b. 新增

- `check107 A11~A14`：常量存在且 == 0.5 · **正控制** scale 6.666→3.331 ·
  **负控制** `fraction=1.0` 逐值等价 · 不变量（在屏内 + 4:3 + 偏移真居中，5 组屏）
- `check107 C13~C15b`：★ **AST 调用序** —— `set_plan` 真被调 · `resize` 在 `set_plan`
  **之后** · `set_plan` 之后仍以 `_primary_screen_size()` 铺整屏 · **负控制**（顺序对调必判假）
- `check107 B3`（AST 形参）· `B4b`（委托链）· `check106 B5/B5b` 定向更新

### 4c. 变异验证（破坏必报红）

把 `main.py` 的 `resize` 挪回 `set_plan` 之前 ⇒ `check107 C14` **报红**
（`set_plan@26 resize@25`）；还原后全绿。

## 5. 回归

- **全量 G2：PASS=5202 FAIL=0，100 套件全 IDENTICAL（0 DIFF）**
- 受影响并 `--update` 的套件（10 个）：`check106` / `check107` / `check89` / `check99` /
  `round8_anim` / `soul_round55` / `npc_persona55` / `npc_place56` / `check67` / `check73`
  —— 逐条确认成因**只有一条**几何日志行
  （`画面 800x600 … scale=2.500` → `画面 400x300 … 比例 0.50 … scale=1.250`；
  `check73` 为真机 2560×1600：`2133x1600/6.666` → `1066x800/3.331`）或由它派生的绝对坐标。

## 6. 录屏自检（真机，`rec110.py`）

**PASS=11 FAIL=0**

| 判据 | 实测 |
|---|---|
| G1 相机尺寸 == 现推 | `(1066,800)` ✅ |
| G2 scale == 现推 | `3.3312`（内接 6.666 的一半）✅ |
| G3 偏移真居中 | `(747,400)` ✅ |
| G4/G4b 桌面透明 · 房间不透明（成对） | `True` / `False` ✅ |
| G5 宠物倍率 == camera.scale × pet_scale | `3.3312 == 3.3312` ✅ |
| **G5b 画布 == 主屏物理尺寸** | `(2560,1600)` ✅ **（第110轮修正点）** |
| G6/G6b 负控制：1.0 等价内接 · 砍半≠内接 | ✅ |

### 人眼逐帧复核（`_evidence/frames110/`）

- `k000_desktop.png`：桌面场景 —— 壁纸透出（透明 ✅）+ 4 扇桌面门贴边框。
- `k001_room.png` / `k002_room2.png`：第一章房间 —— **整屏不透明黑** ✅ +
  4:3 房间画面**居中**、左右黑边**对称** ✅ + 画面约占 42% 宽（砍半 ✅）。
  房间内容正确（床 / 带三角符文的地毯 / 下方门）；Ralsei 与对话框在右下角
  （UI 未受砍半影响 ✅）。

## 7. 复检

- 语法 AST-OK；EOL 保持（`main.py` = CRLF，`scene_camera.py` = LF，其余按原样）
- 无 BOM / 无 U+FFFD
- 逐令牌回验
- 工作区干净
