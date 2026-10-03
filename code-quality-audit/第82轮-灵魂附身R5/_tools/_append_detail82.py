# -*- coding: utf-8 -*-
"""把 §73 追加进详版（不注入的详版文件）。"""
import io
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
P = os.path.join(ROOT, '.workbuddy', 'memory', '参考-契约与历轮（详版）.md')

ADD = u'''

## §73 第82轮：R5 Z 键附身（2026-10-03）

### 73.1 用户口径（第76轮需求锁定，逐字）
> 「交互键用 Z（对 kris 和 firsk，niko 用可以在征求他们同意的情况下附身（特效用原作的），
>  也就是达到原作操控的功能）」

### 73.2 ★★★ 核心设计：附身 = 换方向键的消费方，不是新造物理
原作里「操控谁」从来就是**同一套输入**（`obj_time` 四个布尔）指向不同实体，区别只在速度：

| 文件 | 关键行 | 含义 |
|---|---|---|
| `obj_time_Create_0.gml` | `up/down/left/right = control_check(...)` | 方向布尔**只此一份** |
| `obj_mainchara_Step_0.gml` | `if (obj_time.left) x -= 3;` | 主角读它、**3 px/帧** |
| `obj_heart_Step_0.gml` | `ossafe_keyboard_check(40)` ⇒ `y += global.sp` | 灵魂读**同一组** |

⇒ 附身**没有**加速度/跟随/光效。三处特效**全部有原作出处**：
`obj_mainchara_Other_12` = `snd_play(snd_squeak)` + `control_clear(2)` + `control_check_pressed(0)`（Z = 交互/取消同一键）。
回头步 2px 出自 `if (xprevious == x∓3)`。

**★ 与原作不同的两处**（如实标注「本项目扩展」）：
① 「征求同意」原作没有（只有 Kris 一人可操控），是本项目加的三态 `ConsentState`；
② `ut_frisk` 也 DIRECT（用户口径说「对 kris 和 firsk」）。

### 73.3 交付物
- `ralsei_pet/modules/possession.py`（569 行，**零依赖**：顶层只 `logging/math`，零函数内 import）。
  常量：`CONFIRM_KEY='z'` / `HERO_SPEED_PX=3.0` / `TURN_BACK_STEP=2.0` / `FRAME_HZ=30` / `MAX_DT=0.1` /
  `MODE_FREE/ASKING/POSSESSED/REFUSED` / `POSSESSION_KINDS={'kris':direct,'ut_frisk':direct,'os_niko':consent}`。
- `main.py` 接线（+326/−10）：`:418` import、`:1257` `init_possession()`（**在 `init_npc_systems()` 之后**）、
  R5 整段（Z 主入口 `toggle_possession`）、`update_movement` 里 `_possession_tick` 紧接 `_soul_tick`（**早退分支前**）、
  `keyPressEvent` 方向键**附身优先** + `Key_Z`、`keyReleaseEvent` 对称、`focusOutEvent` `release_all()`。
- 回归锁 `check82.py`（**78 判据**：A 零依赖 / B 类别表+**B2 真机形状** / C 行为真跑 / D 接线 / E 原作对照 / F 自身体检）。

### 73.4 ★★★ 本轮三个真 bug（两个在「判据侧 / 接口侧」）
1. **真机路径拿到空表**（`build_targets` 只认 dict/list，真机是 `NpcRegistry` **对象** ⇒ 空表 ⇒ Z 永远「无目标」）。
   线索 = 启动日志打印 **「0 个」**（不是 3 个），**是我逐条核对 DIFF 时发现的，不是套件报红暴露的**。
   修法 = duck typing（`_entry_get` 吃 dict 与对象）+ main 侧传 `npc_registry`；
   防回归 = B2 段 **A/B 锚点**（对象==dict 且**必须非空**）+ 负控制。
2. **`check81` G5 自指判据每轮 `--update` 假红**：它读**磁盘旧基线**（update 要到全部跑完才落盘）⇒ 新套件入列时必红一次。
   修法（`run_all.py`）：`--update` 时**先预登记 picked 的 id 进基线键集**（值留 `PENDING_UPDATE` 哨兵），跑完被真值覆盖。
3. **真机探针判据写错**：断言 `possessed_id=='os_niko'` 于 ASKING 态 —— 但 `possessed_id` **故意**在非附身态返 `None`。
   **产品对、判据错** ⇒ 改查 `st.target.npc_id`。

### 73.5 另：`PossessionState` 方法重名（施工期血泪）
首版 `release(why)`（解除）与 `release(key)`（松键）**同名** ⇒ Python 静默覆盖 ⇒ 解除附身 `TypeError`。
⇒ 改名 `stop(why)` / `release_key(key)` / `release_all()`，并用 AST 断言「零重名」。

### 73.6 验收
- 全量回归：**PASS=3910 FAIL=0 套件=74（全 IDENTICAL）**（开工时 3831/1/73，那 1 个即 73.4-2 的假红）。
- 真机 **16/16 PASS**（`_evidence/live_r5_82.txt`）：目标 3 个 + kris 名「克里斯」/ 未附身灵魂 Δx=-120 而角色 0 /
  附身灵魂收起 / 附身后角色 Δx=**-30.00**（10帧×3px）而灵魂 0 / 再按 Z 解除 / niko 先 ASKING 后 possessed。
- 复检 67 项全 PASS（六类判据）。

### 73.7 遗留（未获放行不得抢跑）
R6 请求角色带灵魂走 / R1 每人一个家 / R7 原作菜单键位 / P3 `pet_interaction` 三选。
'''

with io.open(P, encoding='utf-8') as fh:
    old = fh.read()
if u'§73' in old:
    print('SKIP: 详版已有 §73')
else:
    with io.open(P, 'a', encoding='utf-8', newline='') as fh:
        fh.write(ADD)
    print('APPENDED')
with io.open(P, encoding='utf-8') as fh:
    s = fh.read()
print('len chars:', len(s), 'bytes:', len(s.encode('utf-8')))
print('§73 ok:', u'§73' in s, '| 73.4 ok:', u'73.4' in s)
