# 第七十五轮 B3 证据：宠物手势判定「唯一真源」改造前后的差异面（2026-10-02）

> 目的：B3 不是"接线"那么简单 —— `modules/pet_interaction.py`（365 行、**零接线**）
> 与 `src/main.py` 里**手写的**手势系统（约 666 行、**在用**）功能重叠。
> 本文件把"重叠到什么程度"量化存档，供后人判断这次统一是否安全。

## 1. 接线状态（改造前，硬事实）

| 检查项 | 实测 |
|---|---|
| `main.py` 里出现 `pet_interaction` 的次数 | **0** |
| `main.py` 里出现 `PetInteractionTracker` 的次数 | **0** |
| 全仓库真正 `import pet_interaction` 的文件（AST 级） | **无** |
| 仅"字符串里出现 `pet_interaction`"的文件 | `emotion_system.py` / `pet_ai.py` / `social_growth_system.py`（那是**事件类型名**，不是模块） |

⇒ 确认：改造前**零接线**。

## 2. 两份实现的差异面

### 2.1 部位名集合

| 来源 | 部位名 |
|---|---|
| `main.py` `get_ralsei_body_part`（12 条区域） | `ear` `hair` `face` `belly` `body` `legs` `arm` `shoulder` `whole_body` |
| `pet_interaction.BodyPart`（改前，8 个） | `ear` `hair` `face` `torso` `leg` `arm` `shoulder` `whole_body` |
| **只有 main 有** | `belly` `body` `legs` |
| **只有模块有** | `leg` `torso` |
| **两边都有** | `arm` `ear` `face` `hair` `shoulder` `whole_body` |

⚠️ **两边阈值也不同**：`main` 是 ear `0/0/30/40`、hair `25/10/75/50`；
模块改前是 ear `0/0/28/38`、hair `22/5/78/42`。
⇒ 同一张精灵上，"点这里算哪个部位"取决于走哪条路径 —— 这正是重复编码的**实际危害**。

### 2.2 手势集合

| 来源 | 手势 |
|---|---|
| `pet_interaction.Gesture` | `stroke` `push` `pat` `pinch` `pull` `flick`（**显式枚举**） |
| `main.py` | **隐式**：连击 3 次=耳不楞 / 双击=摸头杀 / 长按+移动=拉 / 长按=捏 / 往返移动=抚摸 |

### 2.3 代码体量

| 段落 | 行数（约） |
|---|---|
| `get_ralsei_body_part` | 58 |
| `mousePressEvent` | 136 |
| `mouseMoveEvent` | 204 |
| `mouseReleaseEvent` | 209 |
| `mouseDoubleClickEvent` | 59 |
| **合计** | **≈666** |

`main.py` 改造前总行数 **12716**，改造后 **12576**（净减 **140** 行）。

## 3. 改造前的 22 个手势事件名（一个不多一个不少）

```
poke_body  poke_shoulder  poke_default
pinch_ear  pinch_face  press_body  pat_belly
pull_arm  pull_shoulder
double_hair  double_belly  double_face  double_shoulder  double_other
ear_ruffle
pet_hair  pet_ear  pet_face  pet_body  pet_arm  pet_shoulder  pet_other
```

★ 这 22 个同时被 `EVENT_TIERS` / `EVENT_DIRECTIVES` / `verify_s7_event_speech`
三处登记 ⇒ 统一后**只复用、不新增**（`check76` 的 A6 锁死集合相等）。

## 4. 逐分支参数（改造前，逐字摘录）

> 来源：`_tools/_probe_b3_spec.py` 对 `main.py` 的行级输出。
> 这些数**一个都没改**地搬进了 `pet_interaction.RESPONSE_SPEC`。

### 单击（PUSH）
```
body      → happy+15, curious+10, anim=look_up,  pool=["嗯？怎么啦？","诶？有什么事吗？","嘿嘿~ 你戳我啦"]
shoulder  → happy+20, curious+10, anim=look_up,  pool=["嗯？有什么事吗？"]
else      → （无情绪）,          anim=None,      pool=["嘿嘿！","你好呀！","很高兴见到你！","要一起玩吗？"]
```

### 长按（PINCH / PULL）
```
ear       → happy+35, shy+25, anim=surprised, kind=pinch_ear,      pool=["哎呀！别捏我的耳朵！好痒呀！"]
arm       → happy+30,         anim=wave,      kind=pull_arm,       pool=["嘿嘿~ 别拉我的手臂啦！"]
body      → happy+25, shy+20, anim=happy,     kind=press_body,     pool=["嗯~ 好舒服！"]
belly     → happy+40, excited+20, anim=laugh, kind=pat_belly,      pool=["嘿嘿~ 我的肚子很软哦！"]
face      → happy+30, shy+30, anim=surprised, kind=pinch_face,     pool=["哎呀~ 别捏我的脸！"]
shoulder  → happy+25, shy+15, anim=pose,      kind=pull_shoulder,  pool=["谢谢你拉我的肩膀！"]
```

### 双击（PAT）
```
hair      → happy+50, shy+35,     anim=pose,      kind=double_hair
belly     → happy+45, excited+25, anim=laugh,     kind=double_belly
face      → happy+40, shy+40,     anim=surprised, kind=double_face
shoulder  → happy+35, caring+20,  anim=wave,      kind=double_shoulder
else      → happy+20, shy+10,     anim=happy,     kind=double_other   ★ 兜底不是静默
```

### 抚摸（STROKE）
```
情绪（所有部位共用）: happy+30, shy+15
台词按部位: hair / ear / face / body / arm / shoulder（body 即躯干）
```

## 5. 改造后新增/变化（诚实登记）

1. **`BELly` 补进模块的区域表**（必须先于 `TORSO`）。
   不补的话 `double_belly` / `pat_belly` 永不触发（它们原本靠 main 的 belly 区）。
2. **点击反馈时机**：改造前 PUSH 在 `mousePressEvent` 里**按下即播**；
   改造后统一在 `mouseReleaseEvent` 结算（`handle_release`）。
   理由：按下就说话与"按住拖着走"冲突；且三个手势本就需要"时长/位移"才能区分。
3. **alpha 遮罩生效**：模块会先查透明像素 ⇒ 点在角色图的透明空隙（如两耳之间）
   不再算"点在身上"。这是 `pet_interaction` 存在的价值，但确属可见变化。
4. **抚摸参数**：改前 main 是 `history≥5 / changes≥2 / 步长 3~50`，
   模块是 `history 30 / changes≥3 / 步长 3~40` ⇒ 模块更严（更少误触）。
5. **区域阈值**：统一采用模块的数值（ear `0/0/30/40`、hair `25/10/75/50` 等，
   与 main 的 12 条对齐，见 `_REGIONS_PERCENT`）。

## 6. 判据侧踩的四个坑（写套件时暴露的，**零产品错**）

| # | 症状 | 真因 | 修法 |
|---|---|---|---|
| 1 | `B11p` 恒假 | 夹具用了 `(50,50)`，但无 pixmap 时退化矩形是 `0<=x<=0` | 改用 `(0,0)` 并补反向对照 |
| 2 | `C7p` 命中 0 条 | 判据要求"行尾是 `)`"，实际列表项行尾是 `),` | 正则改 `\)\s*,?\s*$` |
| 3 | `C3` 过宽 → 加严后恒假 | 首版只查"方法名出现"（哨兵调用也算）；二版要求实参**直接**是 `_pet_rel_pos(...)`，但产品是 `rel=…; handle(rel)` | 三版＝反例排除：至少一处实参**不是字面量** |
| 4 | `case②` 篡改后仍全绿 | `-1.0` 在 AST 里是 `UnaryOp(USub, Constant)`，**不是** `Constant` ⇒ 哨兵被误判成"非字面量" | 加 `_is_literal()` 递归处理 `UnaryOp` |

★ 另：`tamper76.py` 首版 10 个 case 全 **SKIP** —— 因为仓库文件是 **CRLF** 而夹具串写 `\n`。
修法是"两边归一成 `\n` 匹配、写回时保持原 EOL 风格"。

## 7. 验收

| 项 | 结果 |
|---|---|
| `check76.py` | **59 PASS / 0 FAIL** |
| `tamper76.py` | **10/10 命中**，还原后 sha256 一致、check76 仍全绿 |
| 全量 G2 | 见第75轮报告 §B3 |
| 真机启动 | 全系统就绪（NPC 96 / 人设 76 / 道具 / 灵魂 / 幽灵），无 import 期崩溃 |
