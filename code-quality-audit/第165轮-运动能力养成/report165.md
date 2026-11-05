# 第165轮 · 运动能力养成（练出来的能力）

> 用户口径（2026-11-06）：
> 「那就给AI加装一个学习模块，让他能够像是练习一样练出来，当然，针对不同NPC的特点，
>   运动能力肯定也不同，所以初始和进步速度都不同哦」
>
> 四问定下的细节：
> ① **练习怎么发生** → 日常动作即练习（真跳/真跑就记一笔，不新增行为）
> ② **接到哪儿** → 桌宠 + NPC 两边都真读档案（不存"写了没人读"的死数据）
> ③ **初始值真源** → 全员按原作手写
> ④ **无依据的人怎么落** → 每人落值 + 标依据等级（明证 / 推断 / 无据）

---

## 1. 结论先行

| 项 | 结果 |
|---|---|
| 新增模块 | `ralsei_pet/modules/motion_profile.py`（零依赖纯函数，227 行） |
| 新增数据 | `ralsei_pet/assets/npc/_motion_profile.json`（**96 人**，17334 字节） |
| 产品接线 | `main.py` **8 个方法 + 4 处乘法 + 4 处记账 + 1 处退出落盘** |
| 回归锁 | `check165.py`：56 处判据 / 执行 **53 条**（`run_all` 计 PASS=54，含末尾总结行） |
| 变异测试 | `mutate165.py`：**15/15 全抓**，产品文件 sha1 全程未变 |
| 核心文件复检 | `recheck165_core.py`：**92/0** |
| 全量 G2 | **PASS=7476 FAIL=0，套件 164，零 DIFF** |
| 零回归 | 旧行为**逐值不变**（倍率 1.0 时 `x * 1.0 == x` 精确成立），靠结构而非"这次跑绿了" |
| 顺带修出 | 产品 1 处真缺陷（读档单条坏值连坐整张表）+ 5 个旧套件的桩/时相量问题 |
| 仍未做 | `npc_roam` 选远场景按 `accel` 加距离惩罚（会改变 NPC 活动范围，本轮**主动放弃**） |

---

## 2. 设计：为什么"倍率制"能零回归

产品里本来就有一套**全局常量**在定义"人能做到多少"：
`JUMP_SPEED_MAX`（跳力上限 700）/ `RUNUP_SPEED_MAX`（冲刺上限 320）/ `RUNUP_ACCEL`（助跑加速度 600）。

如果档案存**绝对值**，那几十个套件里凡是断言常量的地方全都要重钉基线；而且"没档案的人物"就没有行为可依。

⇒ 档案只存**倍率**：

* `1.0` = 就是全局常量本身。没档案 / 档案坏 / 还没读盘 ⇒ 一律默认档 ⇒ **乘法恒等**。
* 浮点下 `x * 1.0 == x` **精确成立**（不是"约等于"）。
* 于是"加一个学习模块"对旧存档、旧测试、旧行为是**零改动** —— 这是本轮没动任何旧基线的**唯一**原因。

### 初始值 与 进步速度 是两个正交字段

| 字段 | 含义 | 举例 |
|---|---|---|
| `jump` / `run` / `accel` | 初始能力倍率 | 天生壮的起点就高 |
| `growth` | 进步速度倍率 | 同一套练法下，growth 大的涨得多 |

可以组合出"起点很高但练不动"（growth 0.5）与"起点低但一练就成"（growth 1.8）。

### 成长曲线（刻意简单：可解释、可断言）

```
level = exp // 240              （0 ~ 5 级）
mult  = 1 + 0.06 × growth × level
exp   = min(1200, exp + amount) （封顶、不退步）
```

* **不退步**：`apply_exp` 只做加法与钳制，全模块**没有任何减分路径** —— 用户没要求遗忘，加了就是自造需求。
* **封顶**：满级 1200 经验 ≈ **100 次成功起跳**（每次 12），不会练成超人。
* 典型量级：growth 1.0 练满 **+30%**；1.6 练满 +48%；0.5 练满 +15%。

### 记账权重（练什么给多少）

| 事件 | 经验 | 理由 |
|---|---|---|
| 起跳成功 | 12 | 主体来源 |
| 起跳失败（被闸门拒 / 半路掉下来） | 3 | 「练失败也是练」，但**远少于**成功，否则撞墙比跳成功更划算 |
| 跨场景移动走完（NPC） | 4 | 常量已定义，本轮未接线（见 §10） |
| 差事办完（NPC） | 8 | 跑腿本身就是运动 |

---

## 3. 施工清单（逐处）

### 3.1 新增模块 `modules/motion_profile.py`

| 常量 | 值 |
|---|---|
| `EFF_KEYS` | `('jump', 'run', 'accel')`（顺序固定，便于按位解包） |
| `DEFAULT_PROFILE` | 全 1.0 |
| `LIMITS` | 三项 `(0.4, 2.0)`；`growth` `(0.3, 2.5)` |
| `EVIDENCE_LEVELS` | `('明证', '推断', '无据')` |
| `LEVEL_STEP` / `MAX_LEVEL` / `GAIN_PER_LEVEL` | 240 / 5 / 0.06 |
| `MAX_EXP` | 1200 |

函数：`default_profile` / `from_dict`（**永不抛**）/ `to_dict` / `level_of` / `progress_of` /
`apply_exp`（只加不减、封顶）/ `effective` / `effective_tuple` / `validate_entry`。

**零依赖纪律**（与 `scene_walk` / `possession` / `npc_roam` 同源）：模块内**一条 import 都没有**（`recheck165_core ②` 守着）。
理由：`main.py` import 期就要建控制器，回头 import 项目内模块会把「初始化环」接上（本仓已踩 4 次）。

### 3.2 `main.py` 的八处接线

| # | 位置 | 改动 |
|---|---|---|
| 1 | import 区 | `from modules import motion_profile as motion_profile_mod` |
| 2 | 常量区 | `MOTION_PROFILE_ID = 'ralsei'` / `MOTION_PROGRESS_FILE = 'motion_progress.json'` |
| 3 | `init_movement` | 9 个状态位：`_motion_exp` / `_motion_eff_cache` / `_motion_profile_cache` / `_motion_dirty` / `_motion_exp_map` / `_motion_progress_path` / `_motion_progress_loaded` / `_motion_saved_at` |
| 4 | 新方法 | `_motion_profile_table`（读不到 ⇒ **空表**，不是"人人 1.0 一份"）/ `_motion_profile_of`（`_meta` 不是人物）/ `_motion_eff`（桌宠走缓存、NPC 现算）/ `_motion_note_practice`（30 秒落盘节流） |
| 5 | 新方法 | `_motion_progress_file` / `_motion_progress_ensure` / `_motion_progress_load` / `_motion_progress_save`（原子写 `.tmp` + `os.replace`） |
| 6 | `_jump_reach_ok` | `_limit *= self._motion_eff()['jump']` |
| 7 | `_max_run_px_s` | `_cap = RUNUP_SPEED_MAX * self._motion_eff()['run']`；**`_base` 故意不乘** |
| 8 | `_try_runup` | `_acc = RUNUP_ACCEL * self._motion_eff()['accel']` |
| 9 | `assign_errand` | `kw['travel'] = DEFAULT_TRAVEL_SECONDS / run_eff`（跑得快 ⇒ 到得早） |
| 10 | 记账 | `_start_floor_jump` 成功/失败各一笔；`_npc_errand_commit` 早退处 + `finally` 各一笔 |
| 11 | `cleanup_on_exit` | 第 0 步：`if self._motion_progress_loaded: self._motion_progress_save(force=True)` |

**为什么 `max_speed` 不乘倍率**：① 走路手感不该随练习变（用户只要求"跳得更高"）；
② `max_speed` 被 19 个套件引用，改它的语义等于全盘重钉基线。要"走得更快"是另一条改动，别混进来。

### 3.3 `assets/npc/_motion_profile.json`

96 人 × `{jump, run, accel, growth, evidence, why}` + `_meta`。真源脚本：`_tools/gen165_profiles.py`（`--check` 只校验）。

---

## 4. 96 人档案是怎么来的

| 依据等级 | 人数 | jump | run | growth |
|---|---|---|---|---|
| 明证 | 22 | 0.60 ~ 1.45 | 0.60 ~ 1.50 | 0.50 ~ 1.80 |
| 推断 | 50 | 0.60 ~ 1.45 | 0.60 ~ 1.50 | 0.50 ~ 1.80 |
| **无据** | **24** | **0.40 ~ 1.00** | **0.40 ~ 1.00** | 0.30 ~ 1.30 |

三条纪律（都写进了 `validate_entry` 与 `check165 B` 段）：

1. **基准人律**：`ralsei` 三项**必须 1.0**。全局常量本来就是照他的手感调的，
   给他 0.95 等于"加个模块顺手把桌宠跳矮 5%"。（他的"特点"体现在 `growth 1.25`，不是初始值。）
2. **「无据」不许超过默认档**：对一个没有运动描写的角色给"略高于常人"，等于**把猜测写成数据**。
   （本轮自查揪出过 `zapper` 原写 1.05 却标「无据」，已改回 1.0。）
3. **每条都要有 `why`**：只说数值不够，得说清这个值是从哪句原作描写推出来的。

极值（可见"每人不同"不是摆设）：

* jump 最高：`ut_papyrus` / `ot_papyrus` 1.45（原作里真的能跳很高）
* run 最高：`ut_undyne` / `ot_undyne` 1.50
* growth 最高：`ut_papyrus` / `ot_papyrus` 1.80（练得最快）
* 三项全 1.0 的 10 人：`ralsei` / `mike` / `doubter` / `zapper` / `os_cedric` / `os_ling` / `os_kelvin` / `os_george` / `hy_bowll` / `hy_moray`

---

## 5. 判据与变异

### 5.1 `check165.py`（56 处调用 / 执行 53 条）

| 段 | 条数 | 守什么 |
|---|---|---|
| A 纯函数 | 16 | 默认档恒等 + **正控制**证它不恒真 / 坏值不抛 / 越界钳回 / 等级边界 / 只加不减 / 封顶 / 单调 / growth 真影响涨幅 / 天顶不越界 / 进度 / 校验器"该报的报、不该报的一条不许报" |
| B 96 人数据 | 7 | 与注册表一一对应 / 全员过校验 / 三档都有 / 基准人 1.0 / 「无据」不超默认档 / 生成表与磁盘逐字一致 |
| C 桌宠接线 | 18 | 未练恒等 / 满级变强 / 陌生 id 1.0 / 真读到别人的档 / 闸门按 jump 倍率放行（1.0 拒、1.25 放、1.4 放）/ 走路不吃倍率 / 冲刺上限 = 320×run 逐值 / 只抬上限不伪造实测 / 记账 12:3 / NPC 分账 / **练到升级缓存当场失效** / 落盘 round-trip / 坏档不抛 / 缺档当 0 |
| D 零回归结构 | 8 | 基准人 id / 档名 / AST 定位 `_limit`·`_cap`·`_acc`·**`_base` 不许含倍率** / 两处记账点都接上 |
| E 自检 | 5 | 无 BOM / 行尾不混 / 只用一套 harness / 判据名不带计数标记 / 分母闸 |

### 5.2 `mutate165.py`（15/15 全抓）

模块侧 8 个：默认档抬 1.05 / 负数给减 / 去掉封顶 / growth 变摆设 / 越界不钳 / 等级阈值翻倍 / 不查 why / 不查 evidence。
产品侧 7 个：闸门不乘 jump / 上限不乘 run / 走路也乘 run / 成功按失败记账 / 缓存不失效 / 落盘不写 NPC / 读档不读 NPC。

每个变异体都断言"**红了**且**红的是预期那几条**"；跑完用 sha1 校产品文件字节未变。
隔离方式：`CQ_SRC_DIR` + `CQ_MOD_DIR` 喂副本，且 `PYTHONDONTWRITEBYTECODE=1`
（同秒同长度的变异体会命中旧 `.pyc`，现象是"变异没生效 ⇒ 判据全绿"）。

---

## 6. 本轮判据自己踩的五个坑（都写进了套件注释）

1. **E4/E5 借错了 AST**：扫的是 D 段那棵 **main.py 的树**，`_names` 恒空 ⇒ E5「实得 0 条」恒假、
   E4「无坏名」恒真。**一条恒假配一条恒真，正好互相掩护**（第134/136轮同族）。
2. **E3 扫描器把自己的字符串当证据**：判据写成 `'def ok(' not in 文本`，
   而**判据自己那一行就含这串字** ⇒ 自己把自己打红。改成 AST 取顶层函数名。
3. **C4 要了不需要的东西**：`QPoint` 是纯值类型，**不需要 QApplication**；
   原写法"没 app 就判 FAIL"在沙箱里恒红，失败原因与被测逻辑无关。
4. **C5b 夹具不保真**：沿用 `max_speed=15` ⇒ `_base`≈454px/s 已高过 `RUNUP_SPEED_MAX`(320)，
   倍率把上限抬到 448 也**看不见**（被 `_base` 压住）⇒ 判据变成空转。
   改用文档实测值 5px/帧（151px/s）后才看得见 320→448。
5. **C7/C8/C9 打桩没打全**：`_motion_progress_load()` 里路径是**它自己算**的
   （`path = self._motion_progress_file()` 再回写 `_motion_progress_path`），
   只设 `_motion_progress_path` 会被当场覆盖成真实 vault 路径 —— 判据读的是用户的真档。

---

## 7. 顺带修出的产品缺陷（D165-1）

`_motion_progress_load` 原写法：

```python
self._motion_exp = max(0.0, float(raw.get('self', 0.0) or 0.0))
```

`self` 被写坏（手工改档 / 断电写半截）⇒ `float()` 抛 `ValueError` ⇒ 走到外层 `except`
⇒ **同一次读里 `npcs` 那 96 人的经验一起丢**。一条坏值毁全表。

已改成**单条兜底**：`self` 坏值 / NaN / 负数 ⇒ 按 0，`npcs` 照读（每条也各自 try）。
`check165 C8` 守这条（坏 `self` + 坏条目 + 好条目 ⇒ 好的那条必须留下）。

---

## 8. 全量 G2 与"五个套件同时变红"的归因

第一次全量跑出 **5 个套件红**，全部是**我在 ④⑤ 阶段接线时引入的**（当时只抽查了 6 个套件，
没跑全量 —— 这是本轮最该记的教训）。

| 套件 | 症状 | 真因 |
|---|---|---|
| `round14_move` | 输出从 58 行塌到 24 行、exit=1 | 桩缺 `_motion_note_practice` ⇒ `_start_floor_jump` 中途 `AttributeError`，**这一跳根本没发生** |
| `round18_climb` | 74 行塌到 27 行 | 同上 |
| `check151` | A11 红 | 桩缺该方法 ⇒ `_npc_errand_commit` 抛 ⇒ tick 的 `except` 吞掉 ⇒ `finished` 那段**整段没执行** |
| `check153` | A1/A1b/A5 红（`实得=['drop','commit']`） | 同上（`report` 那步永远到不了） |
| `check158` | A7 红（在办=1 已办=0） | 同上（办完那拍没落盘） |
| `npc_place56` | T1 整行 DIFF（判据仍 PASS） | extra 回显了"顶部 import 了哪些 modules"= **规模量 + 时相量**，加了 `modules.motion_profile` 就变 |

处理：
* 5 处补桩（都写了注释说明"桩不跟装会被 `except` 吞掉，症状不是报错而是整段没执行"）。
* `npc_place56` 的 extra 改成布尔（判据一字未动），随后 `--only npc_place56 --update` 重钉基线。
* 重跑：**PASS=7476 FAIL=0，套件 164，零 DIFF**。

**结构性提醒**：`tick` 里 `drop → commit → report` 是定死顺序，而 `commit` 那一步
**没有隔离**（不 try）。以后任何往 `commit` 里加的东西都必须自己"绝不抛"
（`_motion_note_practice` 内部有 try，所以本轮是安全的；但这条约束值得写下来）。

---

## 9. 复现方法

```bat
:: 回归锁
python code-quality-audit\第165轮-运动能力养成\_tools\check165.py

:: 变异测试（15 个变异体，改完字节还原并校 sha1）
python code-quality-audit\第165轮-运动能力养成\_tools\mutate165.py

:: 核心文件复检（七段 92 条）
python code-quality-audit\第165轮-运动能力养成\_tools\recheck165_core.py

:: 档案生成 / 校验
python code-quality-audit\第165轮-运动能力养成\_tools\gen165_profiles.py --check

:: 全量 G2
python code-quality-audit\regress\run_all.py
```

---

## 10. 本轮不做的事 & 待用户划线

### 主动放弃（已写进提交信息）

* **`npc_roam` 选远场景按 `accel` 加距离惩罚**：会改变 NPC 的活动范围（行为口径变更），
  本轮只做"能力"，不动"去哪"。已登记为下一轮候选。
* **`move_ok`（跨场景移动 4 点）没接线**：常量留着，但现在没有任何地方产生这个事件 ——
  硬加会变成"凭空多一条记账路径"，等真有独立的"走一段路"事件再接。

### 待裁定（沿用第164轮，仍未划线）

* **R1**：第十八轮"勿把跨层拆成逐层小跳"（`main.py:11113~11125`）的前提在 2.5D 下不成立
  （正确做法是先走到中间层正下方再跳 = 助跑的意义）。**须用户批准才能改。**
* **R2**：「下楼也用跳不用掉落」（`11106`）vs 「从平台边缘走出去＝掉下去」，**须用户划线**。
* **D1**（第164轮遗留）：`main.py:12058` 仍是 `vx = delta_x / jump_duration`，未修。
  准确的收口状态是「D5/D4/D3 已修、R1 已落地、D2 撤销、**只剩 D1**」。

### 本轮新发现的一条观察（不改，只登记）

`_max_run_px_s()` 里 `_base = max_speed / dt`。默认配置 `max_speed=15` ⇒ `_base ≈ 454px/s`，
而 `RUNUP_SPEED_MAX = 320` ⇒ **`max(_base, min(_cap, _meas))` 恒取 `_base`**，
也就是说在默认配置下"助跑上限"其实是**惰性**的（`run` 倍率要 >1.42 才开始起作用）。
它不算错（闸门更保守，物理上跳远失败会自己掉下来），但会让"助跑解锁冲刺"这个设计
在默认配置下失效。**要不要把 `_base` 改用当前 `speed` 而非常量 `max_speed`，请用户划线** ——
这属于第164轮契约（`check164 B` 段钉着 `v_max` 的算法），我不擅自动。
