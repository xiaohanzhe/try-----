# 第85轮报告：Shift 跑 + 暗世界移速 + 互动闸/缓冲 + 剧情标记（I1/I2/I4/I5/I10）

> 日期：2026-10-03
> 轮次目录：`code-quality-audit/第85轮-原作用键与移速表取证/`
> 对账文档：`code-quality-audit/第85轮-原作用键与移速表取证/原作移速与用键对账.md`

---

## 0. 一句话结论

**原作的移速不是"一个常量"，而是一张表**（光 3 / 暗 4 为基准，跑动按 `runtimer` 三段加码）。
本项目此前把它压成了 `HERO_SPEED_PX = 3.0` —— **8 格只覆盖 1 格**。
本轮用 UTMT 反编译 Deltarune ch1 逐字取证，把表**补全**，并顺带落地了原作的
**全局闸**（`global.interact`）、**输入缓冲**（`onebuffer = 5`）与**剧情标记**（I10）。

按用户口径「**别毁，就是已经过完剧情了就好**」：I10 **只记账、零销毁**；
并按后续裁定「**只要不是在剧情里死了的npc就可以出现**」——
**剧情过完 ≠ NPC 消失**，`plot_mark` **不接线**为出场门控（见 §9）。

---

## 1. 用户口径（本轮）

> 「按你的意思继续吧，对了，前一轮有计划做完了吗，记得收尾哦，
>   还有那个剧情标记自毁是啥？**别毁，就是已经过完剧情了就好**」

**（本轮后续，逐字）**

> 「**只要不是在剧情里死了的npc就可以出现。不用。ok。继续推进吧**」

三层落点：

| 用户话 | 落地 |
|---|---|
| 「按你的意思继续」 | 按我上轮建议：**I1（Shift 跑）+ I2（暗世界移速 4）优先**，I4/I5/I10 一并做 |
| 「前一轮有计划做完了吗，记得收尾哦」 | ✅ 第84轮已收尾：`39e261e` 已推送、工作区干净 |
| 「**剧情标记自毁是啥？别毁**」 | I10 原作是 `if (global.plot >= 30) { instance_destroy(); }` —— 那是**出场门控**（该 NPC 不再生成），**不是删存档**；本项目按口径**只打标记、零销毁** |
| 「**只要不是在剧情里死了的npc就可以出现**」 | ★★★ **推翻性裁定**：`plot_mark` **不接线**为出场门控 —— 剧情过完 ≠ NPC 消失；出场**只被"剧情里已死亡"挡**（见 §9） |
| 「**不用**」 | **不做** UI 显示"剧情已过" |
| 「**ok**」 | `Shift` 跑键保持不动 |
| 「**继续推进吧**」 | 测绿即连续推进（承接既有工作方式口径） |

---

## 2. 取证（新增物证）

| 项 | 值 |
|---|---|
| 数据源 | `chapter1_windows/data.win`（**14,658,588 B**） |
| 工具 | `E:\Download\UTMT_CLI_v0.9.2.0\UndertaleModCli.exe` |
| 调用形式 | `UndertaleModCli.exe load <datafile> -s <script.csx>` |
| 产物 | **70 codes / 258 globals / 7 strings** |
| 机械锚点 | `_evidence/dr85_anchors.md` —— **17/17 回验通过** |
| 蒸馏脚本 | `_tools/distill85.py`（从**产物**抽，不从"记忆里的源码"抽） |

### 2.1 逐字锚点（关键四条）

```gml
/* obj_mainchara_Create_0 —— 基准速度 */
darkmode = global.darkzone;
wspeed = 3; bwspeed = 3;
if (darkmode == 1) { bwspeed = 4; wspeed = 4; }
```

```gml
/* obj_mainchara_Step_0 —— 跑动三段 */
if (run == 1) {
    if (darkmode == 0) { wspeed = bwspeed + 1; if (runtimer > 10) {...+2} if (runtimer > 60) {...+3} }
    if (darkmode == 1) { wspeed = bwspeed + 2; if (runtimer > 10) {...+4} if (runtimer > 60) {...+5} }
}
```

```gml
/* obj_mainchara_Step_0 —— 全局闸 */
if (global.interact == 0) { ...整段移动代码... }
```

```gml
/* obj_interactablesolid_Step_0 —— 输入缓冲 */
global.interact = 0; myinteract = 0;
with (obj_mainchara) { onebuffer = 5; }
```

### 2.2 ★★★ 两处**刻意的不等差**（不许"顺手规范化"）

| 世界 | 走 | 跑段1（timer ≤ 10） | 跑段2（10 < timer ≤ 60） | 跑段3（timer > 60） |
|---|---|---|---|---|
| 光 | 3 | 4 | 5 | 6 |
| 暗 | 4 | **6**（+2，不是 +1） | 8 | **9**（+5，不是 +4） |

⇒ 代码里写成**显式三条**，**不是**"基准 + 等差"的公式（公式会把 `+2/+5` 抹平）。

### 2.3 阈值是**严格大于**

`if (runtimer > 10)` / `if (runtimer > 60)` ⇒ `== 10` 仍在段1、`== 60` 仍在段2（差一就与原作不符）。
30 fps 下 = 0.33 s / 2.0 s。

---

## 3. 落地（改了什么）

### 3.1 `modules/possession.py`（829 → 935 行）

**新增常量**：`BASE_SPEED_LIGHT = 3.0` / `BASE_SPEED_DARK = 4.0`；
`RUN_SPEED_TABLE = {'light': (4,5,6), 'dark': (6,8,9)}`；`RUN_SEG2_AFTER = 10` / `RUN_SEG3_AFTER = 60`；
`WORLD_LIGHT/WORLD_DARK`；`INTERACT_FREE/DIALOG/MENU = 0/1/5`；`INPUT_BUFFER_FRAMES = 5`。
`HERO_SPEED_PX` 降级为**兼容别名**。

**新增纯函数**：`normalize_world(world)`（认不出 ⇒ `None`，**不猜**）、
`run_segment(run_timer)`、`speed_for(world, running, run_timer)`（世界判不出 ⇒ `None`）、
`advance_run_timer(run_timer, running, moved)`。

**`PossessionState`** 新增：`world` / `_running` / `_run_timer` / `_last_speed` / `_interact` /
`_confirm_buffer` 六个槽位；`set_running` / `is_running` / `run_timer` / `current_speed` /
`set_world` / `set_interact` / `interact` / `is_gated` / `arm_confirm_buffer` / `accept_confirm` /
`tick_buffer` / `confirm_buffer` 十二个接口。

**`drive()` 重写**：先 `tick_buffer()`（**在所有早退之前**）；`is_gated` ⇒ 零位移；
`px_speed = self.current_speed()`（`None` ⇒ 回落 `HERO_SPEED_PX`）；结尾推进跑表。

### 3.2 `modules/plot_mark.py`（**新建**，零依赖 / 只记不毁）

`SCHEMA_VERSION` / `PLOT_PREFIX = 'plot:'` / `PLOT_THRESHOLDS = (30, 120, 150, 245)`；
`mark_key` / `mark_done`（**纯函数，返回新 dict**）/ `is_done` / `done_keys` /
`plot_threshold_reached`（纯比较，**不接线、且永不用于出场判定**）/ `as_dict` / `load_dict`。

模块头**逐字引用**了原作的 `if (global.plot >= 30) { instance_destroy(); }` 并说明"**为什么不做它**"，
并写明**用户裁定**：「剧情过完 ≠ NPC 消失；出场只被"剧情里已死亡"挡」+「不做 UI 显示」。

### 3.3 `src/main.py`（14,032 → 14,169 行，9 处接线）

1. `from modules import plot_mark as plot_mark_mod`
2. `init_possession()` 末尾 `self._possession_sync_world()`
3. 新增 `_possession_sync_world()` —— 走**唯一来源** `scene_system.world_of_scene()`
4. `keyPressEvent` 的 Shift 跑键分支（**左 `Key_Shift` + 右 `0x01000021` 都认**）
5. `keyReleaseEvent` 对称的放开
6. `travel_to_scene()` 换场景后 `_possession_sync_world()`
7. `toggle_possession()` 开头加 I5 缓冲闸（**解除附身不吃缓冲**）
8. 新增 `_interact_level()`（唯一取值口）+ `_possession_tick()` 每帧派发
9. `PLOT_MARK_ENABLED` / `init_plot_mark` / `mark_plot_done` / `is_plot_done` / `_plot_marks_save`

---

## 4. 验证（三层）

| 脚本 | 作用 | 结果 |
|---|---|---|
| `_tools/check85.py` | 回归锁（A~H 八段 + **F2 出场门控禁用**） | **PASS=99 FAIL=0** |
| `_tools/mutate85.py` | **鉴别力体检**（8 处定点破坏） | **PASS=25 FAIL=0** |
| `_tools/recheck85.py` | 核心文件复检（六类判据） | **PASS=41 FAIL=0** |

**行为级实测**：光跑 90 帧 **468 px** > 光走 270 px；暗跑 90 帧 **727 px**；
暗跑/光跑 **> 1.5**；闸关 ⇒ **整帧零位移**；缓冲期内 `accept_confirm()` False、5 帧后 True。

**鉴别力体检 8 条**：跑表段3 `+5→+4` / 暗基准 `4→3` / 阈值严格大于→大于等于 /
未知世界→默认 light / 跑表归零→只不加 / 缓冲 `5→0` / 闸恒 False / 混入真销毁
—— **全部报红、全部可归因**，还原后零 FAIL，无害改动不报红。

---

## 5. ★★★ 本轮抓到的两个真问题（都不是"报红"暴露的）

### ① `PossessionState.drive` 被定义了**两次**（前者静默覆盖后者）

- 症状：所有跑动验证**恒等**（30.0 / 30.0 / 30.0 …）——"看起来跑起来了"，其实跑的是旧版。
- 定位：AST 查方法表 ⇒ `DUP ['drive']`。
- 教训：**"函数写对了 ≠ 产品用上了"的变体 —— 写了两遍，后写的静默覆盖前写的。**
- 已加进 `recheck85.py` ② 段，**同类事故以后必被挡住**。

### ② `mutate85.py` 第一版「夹具不保真」⇒ 所有破坏都报 `FAIL=0`（**全绿**）

- 根因：`subprocess.run([PY, CHECK], cwd=case_root)` —— `cwd` 改了，
  但**脚本路径是工作区那份**；`HERE = dirname(__file__)` 仍指工作区 ⇒ 读的是**没被破坏**的原文件。
- **症状是全绿**，比报红危险得多。
- 修法：跑 case_root 里那份；加"临时区无破坏 ⇒ 仍全绿"正控制；逐条要求"破坏 ⇒ 必报红 + 可归因"。

---

## 6. ⚠️ 一处**差点改错**的更正（诚实记录）

我一度认为第 82 轮 `TURN_BACK_STEP` 那条"照抄 `xprevious == (x ∓ 3)`"的注释**无物证**
（第 85 轮 70 codes 的 dump 里查无 `xprevious`），并已把它改成"本项目取值"。

**复核后推翻**：第 82 轮的 `_evidence/obj_mainchara_Step_0.gml`
第 **54** 行 `if (xprevious == (x + 3))`、第 **129** 行 `if (xprevious == (x - 3))`
**真的存在且在 git 里**。

⇒ 根因是**取证范围不同**（第 85 轮抽的不是同一个对象集）。
注释**原本是对的**，已改回并补注「**取证范围不同 ≠ 事实不存在**」。

---

## 7. 全量回归（`run_all.py`）

`check85` 已注册（`id=check85`，`offscreen=True`）；基线**合并模式**固化：

```
合计：PASS=4193 FAIL=0  套件=77
```

初始 10 个 `DIFF` —— **逐份核对后全部为合法漂移，无一条真回归**：

| 套件 | diff 内容 | 判定 |
|---|---|---|
| `round5_smoke` | 模块数 68 → **69**（新增 `plot_mark`） | 本轮既定事实 |
| `round8_anim` / `soul_round55` / `npc_persona55` / `npc_place56` / `check67` / `check73` | 启动日志多一行「剧情标记就绪：已记录 0 条（无）」 | 新接线的日志 |
| `check79` / `check82` / `check84` | **行号位移**（`main.py` 变长） | 纯脆性信息 |

⇒ 同步基线后复核，**`DIFF` 归零**。

---

## 8. 判据侧的自我修正（"报红先怀疑判据"）

| 现象 | 真相 | 修法 |
|---|---|---|
| F 段"文本里零销毁字面量"报红 | `plot_mark` 的 **docstring 里如实引了** `instance_destroy`（是"如实标注"不是违规）⇒ **判据过窄** | 拆成 **AST 调用名** + **AST 剥字符串后的代码层** 双查；补负控制 |
| F 段出现 `check('…原表仍空', {} == {}, star=True)` | **恒真判据**（`{} == {}` 永远真）—— **自查抓到的死判据** | 删除；改由 `_orig == {}` + 新负控制来守 |
| `recheck85` ② 「粘连」误报 11 处 | `@property` / `@staticmethod` / `return x` 后接 `def` 是**合法风格** | 加装饰器 / 语句结尾豁免 + 正负控制 |
| `recheck85` ⑥ 工作区判据假红 | git 对**中文路径**输出八进制转义 | 判据同时认两种形态 |

---

## 9. 用户裁定结果（原"待裁定"三条 —— 已全部答复）

| # | 原问题 | 用户裁定（逐字） | 落地 |
|---|---|---|---|
| 1 | I10 标记要不要门控出场？ | 「**只要不是在剧情里死了的npc就可以出现**」 | **不门控**：出场只被"剧情里已死亡"挡；`plot` 阈值**永不**用于出场判定 |
| 2 | 要不要在 UI 显示"剧情已过"？ | 「**不用**」 | **不做** |
| 3 | `Shift` 作为跑键？ | 「**ok**」 | 保持（左/右 Shift 都认） |

★★★ **第 1 条是推翻性的**：原作拿 `global.plot >= 30` 当**出场门控**
（`obj_npc_susiedark` 的 `instance_destroy()`），本项目**明确不采用** ——
「**剧情过完 ≠ NPC 消失**」。语义上把它拆成两件事：

| 语义 | 真源 | 用途 |
|---|---|---|
| 「这段**剧情**过完了」 | `plot_mark`（本轮新建） | **只记录**，不挡任何人 |
| 「这个 **NPC** 在剧情里死了」 | **尚无**（待后续轮次建立） | **唯一的出场门控依据** |

两者**不同源、不许互相替代** —— 防"同一份规则两处算"。

### 9.1 本轮因此新增的守卫（防回退）

`check85` **F2 段**（6 条，全部带负控制）：

| 判据 | 守什么 |
|---|---|
| 模块头写明"剧情过完 ≠ NPC 消失" / 出场只被"剧情里已死亡"挡 / 不做 UI 显示 | 口径落在文档里 |
| 代码层 `instance_destroy` 零出现 | 真去实现出场门控 ⇒ 报红 |
| `plot_mark` 不暴露 `should_spawn` / `can_appear` / `is_culled` … | 别把门控塞进标记模块 |
| **全仓** `plot_threshold_reached` 零调用 | 别的模块也不许拿进度阈值挡出场 |
| 三条负控制 | 证明上面每条**都不是恒真** |

⇒ 三层验证复跑：`check85` **99/0**（原 91/0）、`mutate85` **25/0**、`recheck85` **41/0**。

---

## 10. 遗留（未获放行，不抢跑）

R1 每人一个家 / R7 原作菜单键位 / P3 `pet_interaction` 三选 / Q2 Outertale 采样 /
跨作品贴图 / B6 自主开口 / B8 预热 / B11 修 13 套件 / B14 瓦片 / B15 素材补采 /
R6 的 `ESCORT_WIRING.wired=False`；**I3 / I6 / I7 / I8 / I9**（本轮未获授权）。

★ **新增待办**（由本轮裁定派生）：**"剧情里已死亡"标记语义尚未建立** ——
它现在是唯一的出场门控依据，需要时**单开一份**（与 `plot` 明确分离），
**不塞进 `plot_mark`**。
