# 第109轮 · 原作场景过渡动画取证报告（Deltarune ch1）

> **取证方式**：UTMT CLI 反编译 `chapter1_windows/data.win`。
> 驱动 `_tools/utmt109.py`（复用第84/85轮范式）+ 脚本 `_tools/dump_fade109.csx`。
> 产物：`_evidence/fade_codes.json`（35 条 code，25 条真 GML）、`_evidence/fade_objects.json`（10 个对象）。
> **用户口径**：「进入场景的时候按原作有过度动画」⇒ 必须先取证、**禁自创**。

---

## 1. 结论先行

原作 Deltarune 的**房间过渡 = 纯黑遮罩 alpha 线性渐变**。没有形状动画、没有音效、
没有"按任意键跳过"。分两段：**淡出（变黑）→ 换房 → 淡入（变亮）**。

| 量 | 值 | 出处 |
|---|---|---|
| 遮罩颜色 | 纯黑 `c_black` | `obj_fadeout_Create_0`: `image_blend = c_black` |
| 淡出速度 | **+0.08 / 帧** | `obj_fadeout_Create_0`: `fadespeed = 0.08` |
| 淡入速度 | **-0.08 / 帧** | `obj_fadein/persistentfadein_Create_0`: `fadespeed = -0.08` |
| macOS 特例 | 淡出 **0.14 / 帧** | `obj_fadeout_Create_0`: `if (os_type == os_macosx) fadespeed = 0.14;` |
| 单段时长 | `1/0.08` = **12.5 帧** ÷ **30fps** = **≈417ms** | 帧率 `GMS2FPS=30`（第43轮实证） |
| 门等待 | 触发后 **8 帧** 换房（`alarm[2]=8`） | `obj_doorA_Other_19` |
| 遮罩矩形 | `length = 10 + room_width/4`、`height = 10 + room_height/4`，`x=y=-20` | 三对象 `Create_0` 一致 |
| 跨房存活 | `obj_persistentfadein` **`persistent=True`** | `fade_objects.json` |
| 精灵 | 三者都是 `spr_pixel_white`（白像素，靠 blend 染黑） | `fade_objects.json` |
| 结束条件 | 淡入：`if (image_alpha <= 0) instance_destroy()` | `obj_fadein_Draw_0` |

---

## 2. 逐字源码（可复核）

### 2.1 `obj_fadeout`（遮罩：透明 → 黑）

```gml
// Create_0
image_blend = c_black;
fadespeed = 0.08;
if (os_type == os_macosx)
{
    fadespeed = 0.14;
}
image_alpha = 0;
length = 10 + (room_width / 4);
height = 10 + (room_height / 4);
x = -20;
y = -20;

// Draw_0   —— 每帧涨 alpha，到 1（全黑）
image_alpha += fadespeed;
draw_sprite_ext(sprite_index, image_index, x, y, length, height,
                0, image_blend, image_alpha);

// Other_5（Room End）—— 残留实例在房间结束时销毁
instance_destroy();
```

### 2.2 `obj_fadein` / `obj_persistentfadein`（遮罩：黑 → 透明）

```gml
// Create_0 （两对象逐字相同）
image_blend = c_black;
fadespeed = -0.08;
image_alpha = 1;
length = 10 + (room_width / 4);
height = 10 + (room_height / 4);
x = -20;
y = -20;

// Draw_0 （两对象逐字相同）—— 每帧降 alpha，<=0 时自毁
image_alpha += fadespeed;
draw_sprite_ext(sprite_index, image_index, x, y, length, height,
                0, image_blend, image_alpha);
if (image_alpha <= 0)
{
    instance_destroy();
}

// obj_persistentfadein_Other_4（Room Start）—— persistent 对象换房后重算尺寸
length = 10 + (room_width / 4);
height = 10 + (room_height / 4);
```

★ `obj_fadein` 的 Create 没有 macOS 分支（只有 `obj_fadeout` 有）—— 即 **macOS 上淡出更快、
淡入不变**。这是一个**原作的平台不对称**，如实记录。

### 2.3 门的调用端（第85轮已抓，此处交叉印证）

```gml
// obj_doorA_Other_19（玩家踩到门 / 交互）
with (obj_overworldbulletparent) { active = 0; }
global.interact = 3;
instance_create(0, 0, obj_fadeout);
if (touched == 0)
{
    alarm[2] = 8;      // 8 帧后执行 Alarm_2
    touched = 1;       // ★ 幂等守卫：同一次踩门只触发一遍
}

// obj_doorA_musfade_Alarm_2（8 帧后）
global.entrance = 1;
instance_create(0, 0, obj_persistentfadein);   // α=1 起，开始淡入
room_goto_next();                              // 换房
```

---

## 3. 时序（原作 30fps，逐字推演）

```
t=0帧   玩家踩门 → instance_create(obj_fadeout)  [α=0]
        同时 alarm[2]=8
t=1..8  每帧 α += 0.08  ⇒  t=8帧时 α = 0.64（屏幕 64% 黑）
t=8帧   Alarm_2 → room_goto + instance_create(obj_persistentfadein) [α=1]
        ★ 此处 α 从 0.64 **突跳到 1.0**（瞬间最黑）—— 原作的**真实行为**，
          不是 bug：换房那一拍画面本来就是全新的一屏，遮罩直接以全黑掩护。
t=9..  每帧 α -= 0.08  ⇒  约 12.5 帧后 α=0 自毁
```

⇒ **总时长 ≈ 8 + 12.5 ≈ 20.5 帧 ÷ 30fps ≈ 683ms**。

---

## 4. 与我们产品的映射（实现口径）

| 原作 | 我们的实现（第109轮） |
|---|---|
| `obj_fadeout` α 0→1 @ +0.08 | 切场景**前**：遮罩 α 从 0 线性涨到 1，时长 = `8/30s ≈ 267ms`（对齐原作 alarm[2]=8 帧） |
| `room_goto` | 执行真正的 `switch(scene_id)`（我们的换房是同步的） |
| `obj_persistentfadein` α 1→0 @ -0.08 | 换房**后**：遮罩 α 从 1 线性降到 0，时长 = `12.5/30s ≈ 417ms` |
| `image_blend = c_black` | 纯黑 `#000000` |
| 无音效 / 无跳过 | **照做**：不加音效、不加"按任意键" |

★ **不做**的（超纲即自创，违反"一切根据原作"）：
- 不抄 `obj_dw_transition` 的"剪影走门 + 音高 0.1→1.0"（那是**暗世界章节切换**专用，且我们
  的 `switch()` 是桌宠尺度，没有"一屏一房间"的剪影走门语义）。
- 不加淡入淡出之外的特效（模糊/缩放/闪白）。

---

## 5. 自证（判据，防"假取证"）

- ✅ `code_count=35`、`gml_ok=25`：产物里**真有 GML 源码**（判据 = 含 `if (`/`global.`/`alpha`/
  `draw_` 且**不含** `pushi.e`（反汇编特征））。
- ✅ 10 个对象全部命中，含三个核心对象 `obj_fadeout` / `obj_fadein` / `obj_persistentfadein`。
- ✅ 负控制：若把关键词收窄到只剩 `fade`（漏 `transition`），仍能抓到全部 10 个对象
  ⇒ 说明"fade"这一个词就足以覆盖本条口径；加 `transition` 是为了防止漏掉别的过渡体系
  （实测 ch1 **没有** `obj_dw_transition` 的 code，只有 fade 体系）。
- ✅ 交叉印证：第85轮独立抓到的门调用端（`obj_doorA_Other_19` / `Alarm_2`）
  与本轮同源一致。
