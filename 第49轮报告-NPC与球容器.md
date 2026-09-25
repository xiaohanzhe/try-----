# 第49轮报告 · NPC 分层 / 世界门控 / 光世界「扭蛋球」容器

> 用户口径（本轮起点，逐字）
> 「对了，主线npc也就是非主角团的但有重大影响的人（包括toriel和asgore哦，其他的就是各个章节的boos和相对重要的那几个）可以给他们一个4B模型，当然，我也会提供对应的设定，你到时候和我说需要谁的就好，还有，纯npc，也就是没任何有重大帮助对话的人，就用4~10句内置对话就好，这个你自己写就行，对了，这些npc都可以跟着主角团走，但只有主线npc可以自己自主跟随，其他的npc需要主角同意或是要求才行，当然，这些npc都不可脱离暗世界或是进入不属于他们的暗世界，还有，ralsei也不可以脱离暗世界，除非是用，额，就第3章里出现过一很多扭蛋的那个球对吧，做一个4个方向的旋转动画然后在ralsei需要在光世界的时候让kris给他使用，然后就相当于把那个球套在了他身上，还有，球本身不可见的地方需要能遮住ralsei，所以你要做一下代码，还有，ralsei是在球里面，所以不要穿模，要时刻保持在光世界时候在球里面，所以即使是球可见度部分看到ralsei也要有那种透过塑料看人的感觉，也就是给他上一层滤镜，对了，其他主角团的人和lancer也可以进去，要求和上述一样，只不过他们可以随时脱下来（除了lancer）」

---

## 1. 需求 → 实现 → 验收

| # | 需求（原话要点）| 实现 | 验收判据 |
|---|---|---|---|
| 1 | 主线 NPC 给 4B 模型 | `assets/npc/_registry.json` 里 `tier='main'` + `model='ralsei-npc:4b'` + `needs_setting=True` | B2/B6/B7 |
| 2 | 纯 NPC 用 4~10 句内置对话，我自己写 | `assets/npc/_dialogue.json`（18 组 × 4 句，本项目撰写）| C1/C2/C3 |
| 3 | 都能跟主角团走 | `npc_system.can_follow()` 对两类都返回 True | D4 |
| 4 | 只有主线 NPC 自主跟随 | `FollowPolicy.AUTONOMOUS`（`TIER_FOLLOW_POLICY[main]`）| D1/D6 |
| 5 | 其他 NPC 需主角同意/要求 | `FollowPolicy.CONSENT` + `FollowerBoard.request()→pending→respond()` | D2/D7/D8/D10 |
| 6 | 不可脱离暗世界 | `world_gate(npc,'light')` ⇒ `leave_dark_world` | E1/E2/E6 |
| 7 | 不可进入不属于他们的暗世界 | 章节门：`scene_chapter(scene_id) ∈ npc.chapters` | E3/E4/E5/E10 |
| 8 | Ralsei 不可脱离暗世界，除非用球 | `escape_via_bubble` + `world_gate(..., carried=True)` | E6/E7/E8 |
| 9 | 球：4 个方向的旋转动画 | `angle_for_direction()`：基准角 + N × **90°**（360/4 均分整圈）| G4/G5/G6 |
| 10 | Kris 给 Ralsei 使用球 ⇒ 套在身上 | `BubbleField.equip(cid, by='kris')`，`by` 必须是主角团 | F1/F2/F3 |
| 11 | 球不可见处要遮住角色 | ★ **原作做法**：球切三层，角色夹在**下半后层(2)** 与**下半前层(3)** 之间，最后盖**上罩(1)**（`DRAW_ORDER`）| F12/F13/**H1/H2/H3** |
| 12 | 不穿模，时刻保持在球里 | `Bubble.keep_inside()` / `clamp_inside()` 每帧把角色钳回球内 | F8/G1/G2 |
| 13 | 透过塑料看人的滤镜 | `filter_params()`：tint (222,231,238) / alpha 0.88 / rim 0.18 / saturate 0.92 | G8 |
| 14 | 其他主角团 + Lancer 也能进球 | `CONTAINABLE = (kris, susie, ralsei, lancer)` | F1/F2 |
| 15 | 可随时脱下，**除了 Lancer** | `ALWAYS_EJECTABLE=(kris,susie)`；`NEVER_EJECTABLE=(lancer,)`；Ralsei 光世界不可脱 | F4/F5/F6/F10/F14/F15 |

---

## 2. 关键设计决策

### 2.1 ★「遮住 / 透出」不用 mask，用**分层绘制**
用户要的是「球本身不可见的地方要能遮住 ralsei」+「可见度部分要能透过塑料看到」。
原作 `ch3.obj_tenna_board4_gacha_Draw_0.gml` 的**绘制序**直接给出了答案（逐字）：

```gml
draw_sprite_ext(spr_dw_tv_gachaball_transparent, 2, ...);   // 下半后层
draw_sprite_ext(actor_sprite, actor_target.image_index, ...);// ★ 角色
draw_sprite_ext(spr_dw_tv_gachaball_transparent, 3, ...);   // 下半前层
draw_sprite_ext(spr_dw_tv_gachaball_transparent, 1, ...);   // 上罩
```
不透明像素自然遮挡 ⇒ 不需要额外 mask。
（原作另有 `scr_draw_in_mask` / `chromakey_mask_begin,end` 的 alpha 模板法，
本轮**不需要**，已记入文档备查。）
H1/H3 就是**直接读这份 GML** 断言帧序 `[2,3,1]` 且角色确实夹在 2 与 3 之间。

### 2.2 球的身份靠**排除法**定死
用户说「第3章…很多扭蛋的那个球」。普查 ch3 全部候选后：
* `obj_ch3_ballcon`（`spr_ballcon`）＝ **对话气泡框**（corner/line/charface + obj_writer 打字机）⇒ 排除；
* `obj_ch3_gachapon` ＝ 扭蛋**机**（不是容器）；
* ★ **`obj_tenna_board4_gacha` / `obj_ch3_GSC07_gacha`** ＝ 用 `spr_dw_tv_gachaball_transparent`
  把**角色罩进球里**的对象 ⇒ **就是它**。

且原作**本来就支持三人进球**（`actor_target`：1409=Kris / 1411=Susie / 1412=Ralsei），
与用户「其他主角团的人也可以进去」完全一致。

### 2.3 「4 个方向」= 均分整圈 90°
首版我拍了 45°，被自己的鉴别力体检 P6 抓到（判据当时还是恒真的自比写法）。
改为 **360/4 = 90°**，并把判据换成行为断言：4 个朝向互不相同、相邻 90°、补满 360°。
（原作本身是固定角 `-100/-150/-180` 三种，没有"4 方向"这一层——这一层是用户加的产品需求。）

### 2.4 不可脱 / 必留球 是**两张表**，不要合并
* `NEVER_EJECTABLE = ('lancer',)` —— **永远脱不下来**；
* `must_stay_inside`：Lancer 永远、Ralsei **仅光世界**；
* Ralsei 在暗世界**可脱**（他本来就不需要球）。
体检 P3 证实：清空 `NEVER_EJECTABLE` 只影响 `must_stay_inside`
（`ejectable()` 末尾还有 `ALWAYS_EJECTABLE` 兜底）⇒ 两张表的职责是真的分开的。

### 2.5 NPC 的"自己的暗世界"复用第48轮的世界表
不新造概念：`npc.chapters` × `assets/scenes/_worlds.json`（1,014 场景 light202/dark809/unknown3）。
`scene_id` 缺失时**不做章节硬判**（E11）——不猜。

### 2.6 跟随的**轨迹数学不重写**
复用第46轮 `companion.py`（`obj_caterpillarchara` 采样轨迹 + `scr_makecaterpillar` 的 `12+slot×12`）。
本模块只管**策略与门控**，不碰跟随插值。

---

## 3. 交付物

### 新增产品代码（零依赖，模块顶部 import 白名单内）
| 文件 | 职责 |
|---|---|
| `ralsei_pet/modules/npc_system.py` | NPC 分层 / 跟随策略 / 世界门控 / `FollowerBoard` 状态机 |
| `ralsei_pet/modules/bubble_system.py` | 扭蛋球容器：绘制序 / 4 向旋转 / 钳制 / 滤镜 / 穿脱规则 |

### 新增产品数据
| 文件 | 内容 |
|---|---|
| `ralsei_pet/assets/npc/_registry.json` | 33 条 NPC（主线 15 / 纯 18）+ 分层说明 |
| `ralsei_pet/assets/npc/_dialogue.json` | 18 组内置对话（每组 4 句）|
| `ralsei_pet/assets/bubble/*.png` | **43** 帧：主球 4 帧（62×62，原点 31,31）+ 变体 + 4 角色四向行走 |

### 本轮取证与工具（`code-quality-audit/第49轮-NPC与球容器/`）
`_evidence/gml/` **381 个 .gml**（五章 NPC/跟随/球容器/遮罩 相关，UTMT 反编译）、
`_evidence/names49/*`（关键词普查 + 目标 code 清单）、`_evidence/spr49_log.txt`、
`_evidence/取证与设计49.md`；
`_tools/`：`mk_names49 / run_list49 / mk_dump49 / run_dump49 / distill_gml49 /
run_spr49 / distill_spr49 / gen_npc49 / disc_npc49`。

---

## 4. 验收证据

| 项 | 结果 |
|---|---|
| 回归锁 `verify_npc49.py` | **PASS=82 / FAIL=0**（A~H 八段）|
| G2 全量 `regress/run_all.py` | **PASS=2296 / FAIL=0 / 46 套件 / 全 IDENTICAL**（上轮 45 套 2214 + 新套 82）|
| 鉴别力体检 `_tools/disc_npc49.py` | **12/12 精确报红**，还原后内容无漂移、资产清单一致 |
| 原作锚定 | 球帧序 `[2,3,1]` 逐字取自 GML；主球 62×62 四帧来自 UTMT 导出日志 |

### 4.1 体检过程中**真修掉的两处判据缺陷**（值得复用）
1. **`G4` 曾是恒真判据**：写成 `_diffs == [SPIN_STEP_DEG]*3`，右边取自被测常量
   ⇒ 把步长改成 90° 照样绿。改成行为断言（互不相同 + 相邻 90° + 补满 360°）。
   紧接着第二版又踩到**恒假**（`angle_for_direction` 取模后永远回不到 +360）——
   正/负两侧都踩过，最终靠"字面锚点 + 结构断言"落地。
2. **`H10/H12` 曾看不到破坏**：直接 `len(os.listdir())`，把文件改名成 `xxx.png.hidden`
   后目录条目数不变、前缀也没变 ⇒ 判据失明。改成**只数真 PNG**。

### 4.2 G2 漂移处理
`round5_smoke` 因**新增 2 个零依赖模块**导致模块数变化 ⇒ 按纪律用
`--only round5_smoke --only npc_round49 --update`（**合并模式**）重建这两条基线，
其余 44 套逐字节未动（全量复跑已确认 46/46 IDENTICAL）。

---

## 5. ★ 如实登记的缺口（未完成的部分）

1. **★ 尚未接线到产品主流程。** 本轮交付的是**零依赖骨架 + 数据 + 回归锁**，
   与第46轮 companion 框架同一阶段（P0~P1）。还没做：
   * `scene_controller` / `main.py` 里挂 `NpcRegistry` / `FollowerBoard` / `BubbleField`；
   * `scene_render.py` 按 `Bubble.plan()` 真画三层球（含塑料滤镜）；
   * S 键菜单之外的**镜头跟随**与"回暗世界自动脱"的世界切换钩子。
   ⇒ 现在**玩家看不到球**，`bubble_system` 只被回归锁调用。
2. **★ 主线 NPC 的 4B 模型还没接。** `model='ralsei-npc:4b'` 目前只是登记值，
   Ollama 侧还没有这个模型（等用户给设定后一起建）。
3. **纯 NPC 对话是"通用口吻"，没有逐角色考据。** 18 组是我按各自的物件气质写的
   （锤子哥/谜题大师/告示牌/垃圾桶…），不是从原作台词里抽的。
4. **NPC 的四向行走精灵只导了 `down` 一帧用于点数**（`spr_board_*_walk_*` 两帧都在），
   实际进场后的动画名表还没接 `sprite_loader`。
5. **Lancer 的"进球"缺少专属素材**：`spr_board_lancer_*` 每向只有 **1 帧**（不是 2 帧），
   他被装进球后不会有行走动画。
6. **`escape_via_bubble` 只对 Ralsei 开了口子**；用户没提别的角色能不能靠球出暗世界，
   现行策略是"只有 Ralsei"（E8 把它钉住了）——如需放开要改这一条。
7. **球的可视层数按原作固定 3 层**（下半后层/下半前层/上罩），
   原作另有 `spr_dw_tv_gachaball`（3 帧）与 `spr_dw_gachaballhalves_horizontal`（2 帧，左右开合）
   两种变体，本轮**导出但未使用**。
8. **没有做真机视觉验收**：三层叠出来的最终观感（尤其"塑料滤镜"到底像不像）
   必须人眼看，回归锁只能保证**结构正确**，保证不了**好看**。

---

## 6. 复检表（`_tools/recheck49.py`）

| # | 项 | 结果 |
|---|---|---|
| ① | 可编译（`ast.parse`，不产 `.pyc`）| 见复检输出 |
| ② | 报告结构（7 段全在、无粘连）| 见复检输出 |
| ③ | 编码（无 BOM / 无 U+FFFD）| 见复检输出 |
| ④ | 恒真判据形状扫描 | 见复检输出 |
| ⑤ | **逐令牌回验** | 见复检输出 |
| ⑥ | 工作区清单 | 见复检输出 |

---

## 7. ★★ 需要用户提供设定的 NPC 清单（主线，14 位）

> 已登记 `objects`/`chapters`/`home_world`，等你的设定来配 4B 模型。
> **Ralsei 本人不需要**（他已有 `assets/ralsei_persona.md`）。

| # | NPC | 中文名 | 出现章 | 原作物件 | 需要你给的 |
|---|---|---|---|---|---|
| 1 | **Toriel** | 托丽尔 | ch1~ch5 | `obj_npc_toriel` | ★ 必给（五章都在，光世界母亲）|
| 2 | **Asgore** | 艾斯戈尔 | ch5 | `obj_ch5_DW30_asgore` 等 3 个 | ★ 必给 |
| 3 | **Lancer** | 兰瑟 | ch1~ch4 | `obj_darklancer` / `obj_lancerboss{,2,3}` | ★ 必给（也是唯一"进球后脱不下来"的人）|
| 4 | **King** | 黑桃王 | ch1~ch3 | `obj_king_boss` / `obj_npc_king` | ch1 Boss |
| 5 | **Queen** | 女王 | ch2、ch4 | `obj_queen_social_media` 等 | ch2 Boss |
| 6 | **Spamton** | 斯帕姆顿 | ch2 | `obj_spamton_enemy` / `obj_spamton_neo_enemy` | ch2 隐藏 Boss |
| 7 | **Berdly** | 伯德利 | ch2、ch5 | `obj_berdlyb_enemy` / `obj_town_north_berdly` | 关键角色 |
| 8 | **Noelle** | 诺艾尔 | ch2、ch4、ch5 | `obj_heronoelle` / `obj_noellehouse_noelle` | 关键角色 |
| 9 | **Tenna** | 天娜 | ch3、ch4 | `obj_actor_tenna` / `obj_tenna_enemy` | ch3 Boss |
| 10 | **Rouxls Kaard** | 鲁尔斯·卡德 | ch3 | `obj_rouxls_yarnball` | "谜题公爵" |
| 11 | **Gerson** | 格森 | ch4 | `obj_npc_gerson` / `obj_dw_church_gerson_follow` | ch4 关键 |
| 12 | **Mike** | 迈克 | ch4、ch5 | `obj_mike` / `obj_mike_battle` | ch4 对手 |
| 13 | **Roaring Knight** | 咆哮骑士 | ch3、ch4 | `obj_knight_enemy` / `obj_ch4_DCA01_roaringknight` | 主线反派 |
| 14 | **Flowey** | 小花 | ch5 | `obj_flowery_throwkris` / `obj_flowery_kristhrown` | ch5 Boss |

**建议每人给：**① 语气/口癖 ② 称呼主角团各人的叫法 ③ 与 Ralsei 的关系
④ 会不会主动跟、还是等人开口 ⑤ 绝不能说的话（禁忌）。
只给「语气 + 禁忌」我就能开工；其余的我会照原作补。

> 另外 18 位纯 NPC 的 4 句内置对话**我已经写好了**（`assets/npc/_dialogue.json`），
> 你可以直接改文字，改完 `_tools/gen_npc49.py` 不用动（数据与生成器解耦）。

---

## 8. 下一步

1. ★ **等设定** → 建 4B 模型 `ralsei-npc:4b`（Ollama），让主线 NPC 真说话。
2. ★ **接线**（缺口 1）：`scene_controller` 挂 NPC/球，`scene_render` 真画三层球。
3. 真机视觉验收（缺口 8）：球在 Ralsei 身上的观感 + 塑料滤镜 + 4 向旋转。
4. 纯 NPC 对话逐角色考据（缺口 3）——可选，等你说要不要。
