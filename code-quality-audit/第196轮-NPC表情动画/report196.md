# 第196轮 · NPC 表情动画（A 案：5 类统一 + 各自用自己的帧）

> 一句话：**之前 `play_expression_anim` 对 NPC 直接 `return False`，现在 11 个角色会用自己的动画演 5 类情绪。**
> 判据：`check196` **38/38**、`mutate196` **8/8**、全量回归 **193/193 IDENTICAL · PASS=8494 · FAIL=0**。

---

## 1. 起点：我上一轮的判断是错的

第195轮我在 `check195` 的坑位里写下：

> `play_expression_anim` 里 `if char_id: return False` 是**有意为之** —— NPC 立绘只有站立帧，没有自己的动画。

用户当场纠正：

> 「**每个角色在原作可是都有自己的动画的，为啥要用ralsei的啊**」

**错在哪**：「立绘（`assets/npc/portraits/`）只有站立帧」和「原作没有该角色的动画」是**两件不相干的事**。
我把"我手上唯一的素材形态"当成了"全部素材"。这是**查得不够就下结论**。

用户随后选定 **A 案**：

> 「A」

⇒ 统一 **5 类 `happy/sad/angry/surprised/hurt`**；顺手给 Ralsei 补 `angry`；
`cry` 只有 Ralsei 有，NPC 遇 `cry` 走 `sad` 兜底 —— 照原作。

---

## 2. ★★★ 核心口径：「有动画」≠「能当表情动画用」

四轮探针逐级收紧，数据链：

| 探针 | 问题 | 结论 |
|---|---|---|
| `probe_anim_src.py` | 原作一共有多少帧、几个角色有情绪帧 | 34,520 张 PNG；18 角色里 15 个命中，共 **1,459 帧** |
| `probe_frames_size.py` | 命中的都是真的吗、尺寸一致吗 | 大量命中是 cutscene 整图；`susie`/`susiedark` 数字完全相同 |
| `probe_usable_anim.py` | 只保留"单人帧 + 同高度族 + 正面" | **六情绪齐全的角色 0 / 18** |
| `probe_walk_variant.py` | 换成"行走变体"口径 | 覆盖度大幅提升 |
| `probe_final_set.py` | 五道闸全开结算 | **11 人 / 159 帧** |

**正确做法**：原作在 overworld 表现情绪本来就是**换一整套行走图**
（`walk_down_dw_unhappy` / `laugh_dw` / `walk_left_angry`），
不是"挑一张表情脸贴上去"。

★★★ **"模板复制"的含义**：模板是**结构**（`<emotion>_<dir>_<i>` 命名与目录约定），
内容是**各自自己的帧** —— 不是重命名 Ralsei 的帧。

### ★★★ `dw/lw/rw/uw` 是"暗世界/光世界"，不是方向词

把 `dw` 当 `down` 会让 `spr_berdly_walk_left_dw_shocked` 被塞进"正面四向"；
`spr_lancer_lt_laugh` 又认不出 `left`。
⇒ `DIR_PAT` 按**整 token** 匹配（`down|dt|d`、`left|lt|l`…），且 `_d` 后跟 `w` 时不算 down。

---

## 3. 五道闸，每个阈值都有实测出处

| 闸 | 阈值 | 出处 |
|---|---|---|
| 不透明底 | `ratio ≥ 0.85` 判废 | 走路帧全在 **0.448~0.732** |
| 并排两主体 | bbox 内整列全透明的连续段 `≤ 2` | 走路帧 `gap` **全为 0** |
| 夹带道具 | 实心像素 `> 1.8×` 判废 | 抓 `spr_king_laugh_ch1_1`（举着大斧） |
| **bbox 宽度** | `0.45× ~ 1.45×` | 用**实心区宽**，不是画布宽 |
| **bbox 高度** | 容差 3px / 12% | 跪、躺会变矮 |
| 姿势词黑名单 | `POSE_BAD` | `fall/kneel/sit/sleep/ground/jump/…` |
| **配色 share** | `< 0.55` 判废 | 真帧 **0.70~0.83**，假帧 **0.00~0.41** |

★★★ **前五道几何闸全开也漏**。逐帧放大（`zoom196.py`）抓到：

- `spr_susie_mad_face_up_0` = **Kris 的背面**
- `spr_susie_walk_down_shock_*` = 深紫发 + 牛仔裤，**不是 Susie**
- `spr_noelle_surprise_left_0` = 金发黑裙红领结，**别的角色**
- `spr_susie_grabsmile_0` / `spr_susie_hurt_0` = 画布宽 43 / 实心 48，几何闸的原始漏网

⇒ 必须靠**配色一致性**兜底。**这类"素材真伪"只能看图**，纯代码判不出来。

---

## 4. 逐人明细（用户要求"精细到每个人"）

| 角色 | happy | sad | angry | surprised | hurt | 帧数 |
|---|---|---|---|---|---|---|
| **susie** | 4 向 / 8 帧 | 3 向 / 12 帧 | 2 向 / 8 帧 | 4 向 / 7 帧 | — | **35** |
| **susiedark** | 4 向 / 8 帧 | 3 向 / 12 帧 | 2 向 / 8 帧 | 4 向 / 7 帧 | — | **35** |
| **noelle** | 4 向 / 16 帧 | 3 向 / 12 帧 | down 1 帧 | 2 向 / 2 帧 | — | **31** |
| **berdly** | down 2 帧 | 3 向 / 12 帧 | — | left 4 帧 | — | **18** |
| **toriel** | down 2 帧 | 2 向 / 8 帧 | down 2 帧 | — | — | **12** |
| **lancer** | 2 向 / 4 帧 | 4 向 / 4 帧 | — | — | down 1 帧 | **9** |
| **queen** | — | 2 向 / 8 帧 | — | down 1 帧 | — | **9** |
| **asgore** | — | down 4 帧 | — | down 1 帧 | — | **5** |
| **kris** | down 2 帧 | — | — | — | — | **2** |
| **rudy** | down 2 帧 | — | — | — | — | **2** |
| **king** | — | — | — | down 1 帧 | — | **1** |
| 合计 | | | | | | **159** |

★ `susiedark` 与 `susie` 用**同一批源帧**（`spr_susie_*`）。这不是本轮引入的错：
`_npc_frames.json` 里两人的走路帧 `sha256` **逐帧相同**，是既有的贴图族复用。

### 素材来源举例（可回溯到原作文件名）

| 角色 | 情绪 | 源文件 |
|---|---|---|
| asgore | sad/down | `spr_asgore_walk_down_housekeeper_unhappy_0.png` |
| berdly | sad/left | `spr_berdly_walk_left_dw_unhappy_0.png` |
| lancer | happy/left | `spr_lancer_lt_laugh_0.png` |
| noelle | happy/right | `spr_noelle_walk_right_smile_dw_0.png` |
| susie | angry/left | `spr_susie_walk_left_angry_0.png` |

产物清单 `ralsei_pet/assets/sprites/dr/_npc_anims.json` 每条都带 `w/h/sha256/src_name`，运行时**零猜解**。

---

## 5. 另外 85 个登记角色为什么没有

登记表共 **96** 人（`assets/npc/_registry.json`），有表情帧 **11** 人。

| 分类 | 人数 | 原因 |
|---|---|---|
| **探过、零过闸** | 7 | `addison_tea` `gerson` `hammerguy` `mike` `rabbits` `rouxls` `tenna` —— 走路族找到了，但没有一帧能过五道闸（尺寸族不同 / 整图 / 姿势） |
| **未形成四向走路族** | 13 | `catti` `doubter` `police` `sign` `wrapper` `zapper` `spamton` `puzzlemaster1/2` `knight` `conbini` `dumpster` `flowery` —— 原作里就是单图 / 摆件 |
| **本体** | 1 | `ralsei` —— 走桌宠自己的贴图体系，不受本轮影响 |
| **非角色实体** | 3 | `castle_cafe` `mansion_room` `npc_room` |
| **别的作品，本轮未扫** | 61 | `ut_*` 14 · `ot_*` 11 · `hy_*` 15 · `os_*` 21（素材在 `UT素材/`、`UT原版Overworld分图/`、`xnbcli（oneshot)`，不在 `deltarune/`） |

---

## 6. `cry` 的缺口（照原作，不硬造）

全库 `cry` 帧**只存在于** ElNina / LaNino 小怪与 funnytext 的眼泪，**主角团一个都没有**。
⇒ `EMOTION_CLASS` 里 `'cry': 'sad'`，NPC 遇 `cry` 退 `sad`。
这是**照原作**，不是偷懒。Ralsei 自己有 cry（走主桌宠贴图体系），不受影响。

---

## 7. 顺手抓到 Ralsei 侧一条死键

`dialogue_ui.EXPRESSION_ANIM` 原写 `EXPRESSION_ANIM['happy'] = 'happy'`。
但 `event_speech.ACT_EMOTION_RULES` **从不产出 `happy`** —— 大笑/狂笑/哈哈哈 全产 `laugh`。

⇒ 补 `'laugh': 'laugh'`，并补 `'angry': 'fall_mad'`（Ralsei 盘上有 `fall_mad`/`splat_mad`）。
★ **不改老路径行为**：原 `happy` 键留着，新键只是多一条命中。

---

## 8. 实现与性能（用户点名"要么来个5090都跑不动"）

| 落点 | 做法 |
|---|---|
| `npc_body_render.load_anims()` | 失败**一律返 `{}`**，绝不让素材问题把桌宠拖崩 |
| `NpcFrameBook(anim_manifest=)` | 帧**懒加载** + `_anim_pm_cache` / `_anim_scaled_cache` 按 `scale` 缓存 |
| `play_once(npc_id, emotion)` | 写 `_oneshot[nid] = {emo, start, end}`，`sync()` 里**优先取表情帧** |
| 时长 | `ANIM_FRAME_MS=120`、末帧 `ANIM_HOLD_MS=350` 停住，到点清状态回站姿 |
| 帧数上限 | `max_frames=4` 封顶（清单里实测最大就是 4） |
| **冷却按人分开记** | `main._expr_anim_at_by` —— 否则 A 说完 B 接着说会被 A 的冷却挡掉 |
| 清理 | `destroy_all()` 与 `sync()` 的隐藏分支都清 `_oneshot`，否则复现时帧错位 |

`play_expression_anim` 现在开头：`if char_id: return self._play_npc_expression_anim(emotion, char_id)`
—— **Ralsei 老路径逐字未改**。

---

## 9. 验证

| 项 | 结果 |
|---|---|
| `check196` | **38/38**（A 清单↔磁盘对账 5 · B 情绪口径 5 · C 行为 12 · D 接线 AST 9 · E 素材质量契约 4 · F 自检 3） |
| `smoke196` | 25 条，用 `_bits(win)` **比像素**而非比返回值 |
| `mutate196` | **8/8 全抓**，含 1 条无害变异必须红 0 |
| 全量回归 | **193/193 IDENTICAL · PASS=8494 · FAIL=0 · EXIT=0** |

### 本轮我自己踩的三个错

1. **判断错**：把"立绘只有站立帧"当成"NPC 没有动画"（§1）
2. **口径错**："有命中帧"当成"能用" —— 34,520 → 159
3. **`check196` F3 污染计数**：判据名里写了 `[PASS]`/`[FAIL]` 字面量，
   那条 FAIL 行本身往 stdout 多打两个标记，`run_all` 计数当场坏掉。
   修法：标记用拼接构造 `_MARK_P = '[' + 'PASS' + ']'`，改走 AST 检查 `check()` 的 args[0]/args[2]。
   ★ 这是第187轮那条规矩的**现场复发**。

---

## 10. 遗留

| 项 | 说明 |
|---|---|
| 61 个别作品角色的动画 | 需扫 `UT素材/`、`UT原版Overworld分图/`、`xnbcli（oneshot)`，做法同本轮 |
| hurt 覆盖 | 除 lancer 外全员无可用 hurt 帧；遇 hurt 目前退 `sad` |
| angry 覆盖 | 仅 noelle/susie/toriel |
| 姿势类帧（跪/躺/坐） | 本轮全被 `POSE_BAD` 排除；若将来要"倒地"演出，需另立一套不带位移的静帧规则 |

---

## 附：本轮产物

- `ralsei_pet/assets/sprites/dr/<id>/anim/*.png` —— 159 帧
- `ralsei_pet/assets/sprites/dr/_npc_anims.json` —— 独立清单（**不能并进 `_npc_frames.json`**：
  `pick196.py --write` 会整份重写它，表情帧会被静默冲掉）
- `_evidence/`：`anim_src_probe.json`、`anim_usable_probe.json`、`anim_walkvariant_probe.json`、
  `anim_final_set.json`、`sheet196*.png`、`cmp196_*.png`、`zoom196.png`
