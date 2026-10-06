# 第88轮报告 — NPC 交互链（原作「Z → 射线检测 → 触发交互」的等价物）

> 用户口径（逐字，承接）
> * 「原作里该有的可以交互的东西也要有哦，也就是和原作内的效果一样」（第46轮）
> * 「把原作的世界搬到桌面上…桌面也是一个场景」（第38轮）
> * 「一切根据原作」（第38轮）
> * 本轮触发：「继续按计划推进吧」⇒ 承接第84轮清单里列为**既有实现缺口**的 I3 / I6 / I9。

---

## 0. 一句话结论

把桌宠的「按交互键 → 选中谁」从**点对点最近距离**换成**原作的四段射线**：
照抄 `obj_mainchara_Step_0` 的四个 `collision_rectangle`（**四段形状各不相同**），
接上**被交互者转向主角**（I3），Z 键按"当前操控谁"分流。
新增零依赖模块 `npc_interact.py`（486 行），`main.py` +8 方法 + Z 键分流。
判据 `check88` **41 项**（A/B 锚点法把原作式子独立重算）、鉴别力体检 **9 个变异全被抓到**。
★★ 本轮抓到一个**真判据缺陷**（`E5` 子串判据分不清分支，`M6` 变异能骗过它）⇒ 已改成 AST 断言。

---

## 1. 为什么是这三个缺口（I3 / I6 / I9）

第84轮把「原作里该有的可交互物」逐条比对，列出既有实现缺口。其中三条属于**同一个机制**：

| 编号 | 缺口 | 原作出处 |
|---|---|---|
| **I6** | 交互射线的**四段矩形** | `obj_mainchara_Step_0` 的四个 `collision_rectangle` |
| **I3** | 被交互者**转向主角** | `with (interactedobject) { facing = 3; }` |
| **I9** | NPC **待机朝向**的一半 | 同上（交互后朝向被写） |

**旧实现的问题**（第46轮 `interact_scene_prop` → `_soul_pick_prop`）：

> 点对点最近距离 ⇒ **背对着人按交互键，也会交互到他**。

原作用的是**朝向射线**：`facing == 1` 时只查**右侧**一条矩形，背对方向根本进不了候选。
这不是装饰差异 —— 它决定了"按键选中谁"这个**核心手感**。

---

## 2. ★★★ 原作式子（逐字，第84轮 UTMT 反编译取证）

物证：`code-quality-audit/第84轮-原作互动技能取证/_evidence/dr_code.json`

```
obj_mainchara_Step_0:
  if (button1_p()) {
    d = global.darkzone + 1;
    if (global.facing == 1) collision_rectangle(x+sw/2, y+6d+sh/2,
                                                x+sw+13d, y+sh, obj_interactable,...);
    if (global.facing == 3) collision_rectangle(x+sw/2, y+6d+sh/2,
                                                x-13d,    y+sh, obj_interactable,...);
    if (global.facing == 0) collision_rectangle(x+4d,   y+28d,
                                                x+sw-4d,  y+sh+15d, obj_interactable,...);
    if (global.facing == 2) collision_rectangle(x+3d,   y+sh-5d,
                                                x+sw-5d,  y+5d, obj_interactable,...);
    if (interactedobject != -4) {
        with (interactedobject) { facing = 3; }        // ★ 被交互者转向主角
        with (interactedobject) { scr_interact(); }    // ★ 触发
    }
  }
scr_interact() = { myinteract = 1; event_user(0); }
```

三个**必须照抄**的点：

1. **`d = darkzone + 1`** —— 暗世界射线**更长**（`d` 从 1 变 2，所有距离项翻倍）。
2. **四段形状各不相同**：左右段是"贴着一侧的竖条、向前延伸"；下段是"脚前方一段横向窄条、
   向下延伸"；上段是"头顶一条横条、向上延伸"。**不是"角色前方一个方块"**。
3. **朝向枚举**：`0=下 / 1=右 / 2=上 / 3=左`；`facing = 3` = 被交互者转向**左**
   （GMS 里"朝向主角"就是让被交互者面对主角来向）。

---

## 3. ★★★ 最贵的一处坑：坐标口径（A/B 锚点法当场抓到）

### 3.1 `Body.x/y` 是中心，原作 `x/y` 是 sprite 左上角

| | 语义 | 换算 |
|---|---|---|
| 本项目 `Body.x/y` | **中心** | — |
| 原作 `x/y` | **sprite 左上角** | `左 = x - hw`、`右 = x + hw`、`上 = y - hh`、`下 = y + hh` |

### 3.2 首版错在哪

首版把 `y + 28d` 直接写成 `cy + 28d`（`cy` 是中心）—— **漏了 `- hh`**。

后果：**所有涉及 `y` 的项整体偏 16px（= 一个半高）**。

### 3.3 为什么会被抓到 —— A/B 锚点法

判据 `A1` **不读产品代码**，而是把原作式子**独立重算一遍**（用左上角口径
`_LX=60, _LY=80, _SW=24, _SH=32`，再把结果归一化），与产品函数（中心口径）**逐值比**：

```
down 段 y1：期望 108（= 80 + 28×1）  实得 124（= 96 + 28）
up   段 y1：期望  85（= 112 − 5×1）  实得 101（= 112 − 5 + 16 漂移）
```

⇒ 立刻报红。修法：引入 `top = cy - hh` / `bottom = cy + hh`，四段统一用它们重写；
重测**四段 × 明暗两世界 8 组逐值精确相等**。

★ 教训（本项目的 A/B 锚点铁律）：
**"提取成功" ≠ "提取正确"**。反编译出来的式子必须用**独立重算的锚点**比一遍，
否则"我照抄了原作"这句话没有任何证据。

---

## 4. 交付物

### 4.1 新模块 `ralsei_pet/modules/npc_interact.py`（486 行，零依赖）

| 函数 | 职责 |
|---|---|
| `ray_rect(x, y, facing, darkzone, half_w, half_h)` | ★★★ 原作四段射线（返回归一化矩形） |
| `rect_contains` / `rect_intersects` | 命中判定 |
| `_box_of` / `_normalize_box` | 形状约定（2 元组=点 / 4 元组=矩形 / 字典=中心+半宽） |
| `pick_nearest(candidates, rect, ax, ay)` | 命中集合里取**盒中心最近**（平手取 key 字典序最小） |
| `facing_toward(ax, ay, bx, by)` | 45° 分档朝向（**与 `npc_placement._facing_between` 等价**） |
| `face_actor(ax, ay, bx, by)` | 被交互者看向主角（I3） |
| `resolve(...)` | 一步到位：解"该跟谁交互 + 他朝哪"（恒返回 dict） |

**零依赖纪律**：顶层只 `import logging`；函数体内零 import（防初始化环，本项目已踩 4 次）。

### 4.2 `main.py` 接线

* `import modules.npc_interact as npc_interact_mod`
* `_interact_facing` 记忆字段（初始 `down`）
* **重写 `interact_scene_prop()`** —— 逐级降级：① NPC 射线 → ② 物件射线 → ③ `_soul_pick_prop` → ④ 登记顺序第一个（**每级都不静默**）
* 新增 8 方法：`_npc_interact_actor_room_xy` / `_npc_interact_facing` / `_npc_interact_darkzone` /
  `_npc_interact_candidates` / `_npc_interact_pick` / `_npc_interact_pick_prop` /
  `_npc_face_actor` / `_npc_interact_speak`
* **Z 键分流**：
  ```python
  if key == _Qt.Key_Z:
      poss_z = getattr(self, 'possession', None)
      if poss_z is not None and poss_z.is_possessing:
          self.toggle_possession()      # 已附身 ⇒ 交回灵魂（R5 契约不变）
      else:
          self.interact_scene_prop()    # 未附身 ⇒ 场景交互（第88轮 I6）
  ```
* 方向键分支记忆朝向：`if d in npc_interact_mod.FACINGS: self._interact_facing = d`

复用既有通道（**不新起生成路径**）：说话走 `npc_speak()`、展示走 `_npc_say_line()`、
明暗世界走 `scene_system.world_of_scene()`（与第85轮速度表**同源**）。

### 4.3 判据 `check88.py`（41 项）

| 段 | 内容 |
|---|---|
| **A** ★★★ | 射线几何**逐值等于**原作（A/B 锚点法 + 明暗两世界 8 组 + 鉴别力负控制） |
| **B** ★★ | 四段形状差异真在（互不相同 · 上下段"横向窄纵向延伸" · 方形射线负控制） |
| **C** ★★★ | 命中按朝向（背对不命中 · 最近优先 · 平手确定性 · 空候选不硬选 · 非法分因 · `_box_of` 约定 · 逆序归一化） |
| **D** ★★ | 转向 I3（`face_actor` 看向主角 + 与 `_facing_between` **逐例等价** + 配对负控制） |
| **E** ★★★ | 接线断言（8 方法 · 真调射线 · **AST 断言 Z 键分流** + 正负控制 · 复用 `npc_speak` · `_npc_say_line` · 转向真写 `body.facing` · 明暗同源） |
| **F** ★★ | 旧行为不回归（桌面场景不射线 · 旧降级链保留 · 零依赖） |
| **G** | 判据自身体检（几何差异真在 · 记账守恒 · 记账器鉴别力） |

---

## 5. ★★★ 本轮抓到的两个真问题（都不是报红暴露的）

### 5.1 `D1`：`facing_toward` 与 `_facing_between` 的退化阈值分歧

首版我的 `facing_toward` 用 `abs(dx) < 1e-9 and abs(dy) < 1e-9` 判退化，
而 `npc_placement._facing_between` 用 `dx == 0.0 and dy == 0.0`。

⇒ 在 `(1e-12, 0)` 上：**这边返 `None`、那边返 `'right'`**。

**判据 `D1` 是"逐例等价"**，它守的是"两条实现可以互相替换"——
那就不许留一条**只有一侧知道的宽容带**。

修法：把 `facing_toward` 的退化判定改成**逐位一致**的 `dx == 0.0 and dy == 0.0`，
并在注释里写清楚"首版为什么错、为什么'更稳健'反而是错的"。

★ 教训：**等价性判据守的是"算法"，不是"阈值"**。

### 5.2 `E5`：子串判据分不清分支（`M6` 变异骗过了它）

首版 `E5` 只查三个子串在文件里出现过：

```python
_z_ok = ('poss_z is not None and poss_z.is_possessing' in _src
         and 'self.toggle_possession()' in _src
         and 'self.interact_scene_prop()' in _src)
```

鉴别力体检的 `M6` 把 **Z 键的 `else` 分支也换成 `toggle_possession()`**（= Z 键彻底不分流），
结果 **`E5` 照样 PASS** —— 因为 `self.interact_scene_prop()` 在**别处**（E 键处理器）也有，
子串判据分不清"在哪个分支里"。

这正是本项目反复栽的"**判据过窄 = 会误报**"（第69/70轮同类）。

修法：改成 **AST 结构判据** `_z_branch_ok()` —— 在 `keyPressEvent` 里找到 `Key_Z` 分支，
**断言内层 `if/else` 的 if 体真调 `toggle_possession`、else 体真调 `interact_scene_prop`**；
并配 **正控制 `E5c`（正确形状必判真，防"改严了变恒假"）+ 负控制 `E5b`（两分支都 toggle 必判假）**。

★ 教训：**"子串在文件里出现"不是接线断言**。接线断言必须能回答"**在哪个分支里**"。

---

## 6. 鉴别力体检（`mutate88.py`，9 个变异全被抓到）

| 变异 | 期望被抓的判据 | 结果 |
|---|---|---|
| M1 射线系数 28→27 | A1 / A2 | ✅ FAIL=2 |
| M2 去掉矩形归一化 | C8 | ✅ FAIL=1 |
| M3 射线放大成整屏（背对也命中） | A1 / A4 / C2 | ✅ FAIL=6 |
| M4 转向方向反 | D1 / D2 | ✅ FAIL=3 |
| M5 退化阈值改宽容带 | D1 | ✅ FAIL=1 |
| M6 Z 键不分流 | **E5**（★修前 FAIL=0，修后抓到） | ✅ FAIL=1 |
| M7 说话不经 `npc_speak` | E6 | ✅ FAIL=1 |
| M8 不调射线选人 | E4 | ✅ FAIL=1 |
| M9 明暗世界另判一遍 | E10 | ✅ FAIL=1 |

★ 变异保真自检：每个变异跑完都做 `ast.parse`，语法被弄坏的直接判 `BADMUT`（不计入"抓到"）。

---

## 7. 自查（`recheck88.py`，全 PASS）

六类判据：① 可编译（AST）② 结构自检（10 个顶层函数 + `WIRING`）③ 无 BOM / 无 U+FFFD
④ 无 `check(..., True)` 恒真占位 ⑤ 逐令牌回验（9 个关键令牌 + 无 `_npc_show_line` 残留）
⑥ 零依赖（顶层只 `logging`、函数内零 import）+ 工作区状态。

---

## 8. 如实标注（本轮**没做**的）

* **I9 的完整形态**（NPC 待机朝向的**渲染层**）本轮只做了"交互后转向"这一半；
  真正的"待机时按某种规则朝向"需要渲染层配合，**本轮未做**。
* **`facing` 持久化**：原作 `global.facing` 是持久状态；本项目 `SoulState` 无此字段
  ⇒ 用宿主侧临时字段 `self._interact_facing`（方向键按下时更新）。
  **这是本项目的临时实现**，与"原作每帧都持有 facing"不完全等价。
* **NPC 挂 `Interactable`**：既有 `item_interact` 家族只挂在场景 objects 上，
  本轮 NPC 走的是**射线选人 + 直接调 `npc_speak`**，未挂 `Interactable` 协议
  （NPC 交互语义与物件不同，暂不统一）。
* **`ot_*`（Outertale）**：仍无处安家（第87轮如实挂起），本轮不涉及。

---

## 9. 回归与收尾

* 全量回归：**79 + 1 = 80 套件**（新增 `check88`）。
* 变更文件：`ralsei_pet/modules/npc_interact.py`（新）、`ralsei_pet/src/main.py`（改）、
  `code-quality-audit/第88轮-NPC交互链/_tools/{check88,mutate88,recheck88}.py`（新）、
  `code-quality-audit/regress/run_all.py`（注册）、`code-quality-audit/regress/baseline.json`（重固）。
* 真机启动验证：零异常，所有模块正常初始化，`npc_interact` 导入无环。
