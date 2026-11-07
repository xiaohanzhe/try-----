# 第168轮 · W 门补齐

> 一句话：**第125轮那次「W 门证据不足」的拒收不成立** —— 当年两次都量错了对象。
> 本轮按 A/B/C/D/X 用的**同一把尺**补收 **88** 条 W 门，五章边覆盖 **617 → 706 / 782 = 90.3%**。

---

## 0. 结论摘要

| 项 | 改前 | 改后 |
|---|---|---|
| `_routes.json` 路由条数 | 1,740 | **1,828**（+88） |
| 唯一边 / 合法重复 | 1,735 / 5 | **1,823 / 5** |
| W 门规则 | **0 条**（第125轮整类拒收） | **88 条**（priority 7000~7087） |
| 五章边覆盖（`_room_graph.json` 782 边） | 617（78.9%） | **706（90.3%）** |
| 五章「有出边的场景数」 | 116 / 137 / 35 / 32 / 31 | **118 / 165 / 45 / 40 / 41** |
| 桌面出发可达场景 | 215 / 2166 | **220 / 2166** |
| 文件大小 | 1,214,349 B（1740 条时约 1.15 MB） | **1,214,349 B** / 33,213 CRLF / 无尾换行 |

**这不是加功能，是把一条被误判的数据补回去。** 判据口径、准入门槛（机制 + 在场 ≈ 90% 且逐条可归因）
一条都没放宽 —— 放的是"当年量错了对象"这件事本身。

---

## 1. 为什么要重审 W 门

第125轮原文结论：

```
W **0/97**（marker 实为小写 `obj_markerw`：60.2%；`obj_markerX` 84.3%
⇒ 两套都到不了 100%，**W 仍不收**）
```

第126轮又把门槛更正为「机制 + 在场 ≈ 90% 以上，且**每一条不中都能逐条归因**」，
但 W 仍然没进表，真因写的是「两套 marker 写法归不了因」。

本轮把"归不了因"这件事查穿了：**不是数据不够，是尺子拿错了。**

---

## 2. 三处实证（都不是推测）

### ① 机制：`obj_doorW_Alarm_2` 与 X 门**逐句同形**

UTMT 反汇编（`probe168.csx` → `_evidence/probe168_ch1.txt` / `probe168_ch2.txt`）：

```
0   PushI 23  →  Pop VAR=entrance                      ← 先给出生点编号
2   PushI 145 →  … FN=gml_Script_instance_create       ← 建 persistentfadein
10  PushBltn room; PushI 13; Cmp; Bf; PushI 18; FN=room_goto
18  PushBltn room; PushI 18; Cmp; Bf; PushI 13; FN=room_goto
…                                                      ← ch1 共 6 条 if (room == N) room_goto(M)
```

骨架 = 赋 `entrance` → `instance_create` → 一串 `if (room == N) room_goto(M)`，
**与 `obj_doorX` 一模一样**。W 不是"另一种门"，就是**表驱动那一种**。

指令数也能佐证分支密度：`obj_doorW_Alarm_2` 在 ch1 是 **58** 条指令、ch2 是 **1805** 条
（`check168.E7` 钉这条，≥10 倍）。

### ② marker 对象表（UTMT `sprite=` 字段）

| 对象名 | sprite | 结论 |
|---|---|---|
| `obj_markerA`~`obj_markerF` | `spr_markerA`~`spr_markerF` | 各**专属** |
| **`obj_markerw`**（小写 w） | **`spr_markerW`** | **W 的专属**，与 A~F 同族 |
| `obj_markerX` | `spr_markerX` | **X 的专属**，不是通用兜底 |
| `obj_markerAny` | `spr_markerAny` | **真通用** |

★ 第125轮的两次测量**都量错了对象**：

* 拿 `'obj_marker' + 'W'`（大写）比 —— 产品里是**小写** `obj_markerw` ⇒ 恒 0%；
* 换 `obj_markerX` 比 —— 那是字母 X 的出生点 ⇒ 84.3% 是个混账数。

★ ch1 里 `obj_markerr/s/t/u/v` 共用 `spr_markerX`，只是那五张 sprite 当时没画
（ch2 里它们各自有 `spr_markerR..V`）——**不能**据此把 X 当占位符。`check168.E4` 钉这条。

### ③ 同一把尺重算六类门（`_room_graph.json` 同一批实例）

| 门 | 同字母 | 通用 Any | 只有 X | 别字母 | 空房 | 自证率 |
|---|---|---|---|---|---|---|
| A | 195 | 8 | 2 | 6 | 6 | 93.5% |
| B | 194 | 6 | 4 | 8 | 4 | 92.6% |
| C | 59 | 0 | 0 | 1 | 1 | 96.7% |
| D | 61 | 1 | 0 | 1 | 5 | 91.2% |
| X | 84 | 0 | 0 | 0 | 5 | 94.4% |
| **W** | **74** | **16** | 1 | 5 | 1 | **92.8%** ← 本轮 |

W 落在已收五类的**区间正中**⇒ 达到第126轮写下的门槛。

---

## 3. ★★★ 一条必须记住的坑：`entrance` 不是"每类门一个常量"

这是本轮**最容易写错判据**的地方，也是我自己一度写错又推翻的：

```
ch1  obj_doorW_Alarm_2            entrance = 23      ins =   58
ch2  obj_doorW_Alarm_2            entrance = 24      ins = 1805
ch2  obj_doorw_musfade_Alarm_2    entrance = 20      ins =  180
```

ch1 里它恰好等于字母序（W = 第 23 个字母），**于是极容易得出「W ⇒ entrance=23」这个错结论**。
ch2 直接推翻：同一扇 `obj_doorW` 给 24，它的 musfade 变体给 20。

真语义是「**新房间里第 N 个字母的出生点**」——每个 `if (room == N)` 分支各自指定。
ch2 那 145 次赋值全部落在 19~24（= S/T/U/V/W/X 的字母序）。

⇒ 可以据它说「W 与 A/B/C/D/X 同机制」；
**不可以**说「W ⇒ entrance=23」，更**不许把判据建在它的数值上**。

已写进三处：`gen_routes168.py` 的 docstring / `check125.py` / `verify_scene_route_original.py` 注释，
并由 `check168.E6`（三处不一致）与 `E7`（指令数 10 倍）用数据钉住。

---

## 4. 98 → 88 的账（一条不少地对上）

```
 98  证据里的 W 边（_room_graph.json；obj_doorW + obj_doorw_musfade）
 − 7 落点不自证（6 条"目标房只有别的字母的 marker" + 1 条"目标房零 marker"）
 = 91 可用（机制查表 98/98 全过 + 两端都已登记）
 − 1 重复实例（同一间房的门被第42轮数了两遍，逐字段一致）
 = 90 唯一边
 − 2 已由别的门提供同一 (场景, 目标)
 = 88 新增（同字母 72 + 通用 obj_markerAny 16）
```

### 拒收的 7 条（逐条留档，不为凑数放宽）

| # | 章 | 源 → 目标 | 目标房里的 marker | 拒收理由 |
|---|---|---|---|---|
| 1 | ch2 | 92 `room_dw_cyber_maze_fireworks` → 85 `room_dw_cyber_maze_virokun` | A/B/D/t/u | 落点不是 W |
| 2 | ch2 | 119 `room_dw_city_big_2` → 138 `room_dw_city_mirrorfriend` | **只有 X** | 落点不是 W |
| 3 | ch2 | 140 `room_dw_city_dog_traffic` → 123 `room_dw_city_traffic_3` | A/B/X + charm | 落点不是 W |
| 4 | ch2 | 141 `room_dw_city_man` → 123 同上 | A/B/X + charm | 落点不是 W |
| 5 | ch2 | 142 `room_dw_city_moss` → 123 同上 | A/B/X + charm | 落点不是 W |
| 6 | ch2 | 157 `room_dw_mansion_entrance` → 231 `room_shop_ch2_swatch` | **零 marker** | 商店空壳，连房都不像房 |
| 7 | ch2 | 164 `room_dw_mansion_east_1f_secret` → 169 `room_dw_mansion_b_entrance` | B/t | 落点不是 W |

★ 第 6 条是**双尾**：目标房零 marker **且**该房没登记成场景。
`check168.D3` 的负控制就是给它补一个 `obj_markerw` ⇒ 拒收 7→6，而这条边**落到下一道闸**
（"未登记"）—— 两道缺口分工明确，没有一条是被误丢。

### 那 2 条"已存在"

```
ch2.cyber_city.dw_city_traffic_4    → ch2.cyber_city.dw_city_spamton_alley   已有 A 门
ch2.cyber_city.dw_city_spamton_alley → ch2.cyber_city.dw_city_traffic_4      已有 B 门
```

同一对场景，原作里 W 门和 A/B 门都能走。产品一扇门一条规则 ⇒ 不重复写。

---

## 5. 落地

* 位置：`ralsei_pet/assets/scenes/_routes.json`，追加 88 条，priority **7000~7087**（连续无空洞）
* `kind = 'delta_door_table'`（复用第125轮那套表驱动自洽五条）
* `marker` 写**实测对象名**：`obj_markerw` 72 / `obj_markerAny` 16，**不写假的大写**
* `table` = `gml_Object_obj_doorW_Alarm_2`（79 条）/ `gml_Object_obj_doorw_musfade_Alarm_2`（9 条）
* 格式逐字节保持：`ensure_ascii=False, indent=2` + CRLF + **无尾换行**
* 生成器：`_tools/gen_routes168.py`（`EXPECT_ADD = 88` 钉死，条数不符**拒绝写入**）

---

## 6. 验证

### `check168.py` —— 41 条判据，41/0

| 段 | 内容 |
|---|---|
| A 7 条 | 88 条 / priority 7000~7087 连续 / 只落 ch1~ch5 / **marker 只用实测名、大写 `obj_markerW` 一条都不许有** / `(场景,目标)` 无重复 / `table` 与 `via` 对得上 |
| B 8 条 | **另写一份推导**（不 import 生成器）重推 → 机制 98/98 一致 · 落点自证 · **与产品段集合相等** · 守恒账 · **两条负控制**（换回第125轮那把尺 ⇒ 两边都不等，多认 4 / 少认 28；大小写敏感找大写 ⇒ 恒 0，正是当年那个 0%） · 正控制（两类落点都认） |
| C 6 条 | 两端 `original_room_id` / **用规则自己声明的 `table`** 查表 / **目标房真摆着那个 marker** / 章前缀 / 声明序 / `reason` 文案不许造假 |
| D 5 条 | 7 条拒收**逐条留档**（6 + 1，成对）；负控制补 marker ⇒ 拒收 7→6 且落到"未登记"闸；未登记桶必须为空 |
| E 7 条 | 直接读 `doors168.json` 把 A 段的**依据事实**也锁住（三项 sprite 归属 / ch1 共用 X 只是没画 / **`entrance` 三处不一致** / 指令数 1805 vs 58） |
| F 8 条 | AST 查恒真 / 单一 harness / 判据名不带计数 / 文件格式 / 分母闸 / 零外部盘 / 生成器在盘 |

### `mutate168.py` —— 12 项全抓

| 变异 | 红了 |
|---|---|
| M1 priority 挪出 7000 段 | `A1 C5` |
| M2 marker 写成大写 `obj_markerW` | `A4 B7 C3 C6` |
| M3 `when_door` 改成 X | `A3` |
| M4 `table` 换成 X 门那段 | `A6 C2` |
| M5 目标换成另一间房 | `B3 C1` |
| M6 复制一条（同门同目标） | `A0 A1 A4 A5 B7 C5` |
| M7 `reason` 里 marker 改成大写 | `C6` |
| M8 证据里 `obj_markerw` 的 sprite 改掉 | `E1` |
| **M9 无害变异**（只改一句中文说明） | **一条都不红**（考"会不会假红"） |
| M10 判据自己的 `_desc_of` 退回只认裸字面量 | `F5`（分母闸兜住"扫描器恒空"） |
| Z1 / Z2 | 字节级还原 sha1 未变 / 收口复跑全绿 |

★ 有几条红了不止一个，是**正常的**：A4 守"marker 是不是实测名"、B7 守"两类落点各多少条"、
C3 守"目标房真有它"、C6 守"文案没造假"，改一个 marker 名会同时踩到四处 —— 分工重叠但不等价。
真正要防的是"改了却一条都不红"。

### 全量回归（G2）

```
合计：PASS=7574  FAIL=0  套件=166     ← 全部 IDENTICAL
```

---

## 7. 连带改的老判据（5 处，都为"账要跟着事实走"）

### ① `verify_routes_order44.py`：B2 收窄到**同段内** + 新增 B2c + C1c 拆两段

**为什么必须改**：W 落地后，字母序里 W=23 介于 D=4 与 X=24 之间，而段位上
5000（D/X）< 7000（W）⇒ **同一场景里「字母升」与「priority 升」无法同时成立**
（实测 3 个场景含 D、6 个含 X）。**段位放哪儿都救不了 —— 它是两个不同维度。**

改法（**分账，不是放宽**）：

* `B2` 从"全局字母序 == priority 序"改成"**同段内**"（按 `priority // 1000` 分组），段内仍逐条升序；
* 新增 `B2c`：**跨段违例必须恰好等于**「同场景同时含 W 与 D/X」的场景集，多一个都红（实测 0 个例外）；
* `C1c` 拆成 `C1c`（X，5000~5999，83 条）+ **`C1c2`**（W，7000~7999，88 条）——同一个 `kind`
  现在装两段，不许混在一起数。

### ② `verify_scene_route_original.py`：`C3a7` 描述改成"表驱动门（X + W）"

`kind=delta_door_table` 现在装 83 + 88 = 171 条，描述原来只写"X 门"，**改成两类分开报数**
（`X 83 / W 88`），并断言 X 那类非空。`C3a9` 的 `W 门（证据不足）判红` 改成
`W 门写成位移边判红（W 是表驱动，没有位移可言）` —— **断言一字未动，只改措辞**：
W 不再是"证据不足"，它在这里被判红的理由是**机制不同**（与 X 门同一条理由）。

### ③ `check126.A0` 路由条数 1740 → 1828
### ④ `check124` `EXPECT_ROUTES 1740 → 1828`、`EXPECT_UNIQUE_EDGES 1735 → 1823`
### ⑤ `check125`：D 段从「W 门一条都不许进表」改成「W 门的账」

* `D1` 改成"**恰好 88 条**"（原口径"一条都没有"已作废），新增 `D1b`（只落 ch1~ch5）；
* ★ 踩坑修正：`D1` 去重键必须是 **(场景, 目标)** 而不是 `(目标)` —— 88 条只落在 **55** 个不同目标上，
  不同场景的两扇 W 门去同一处是**原作事实**（同第125轮报告 §5 第 4 条那个坑）；
* `D2` 保留证据侧 98 条，注释改成 `98 = 88 收 + 7 拒收 + 1 重复 + 2 已存在`。

### 基线：9 个套件重建（`--update` 合并模式）
`check168` `check124` `check125` `check126` `scene_route_original` `routes_order44` `check_r0_76` `check89` `check105`

★ `check89` 的那条 DIFF 是**好消息**：原来会打一行
`门 obj_doorW（字母 W）在场景 ch1.hometown.town_mid 查不到路由 ⇒ 不建（不造假门）`，
现在这行**不再出现** —— W 门真有路由了，产品不用再"故意不建"。

---

## 8. 遗留（登记，不在本轮做）

1. **7 条落点不自证**：6 条"目标房只有别的字母的 marker"是**原作事实**（那些房确实没有 W 出生点），
   补齐要靠"房间内坐标级落点"，不是补 marker；1 条商店空壳房连场景都没登记。
2. **ch1 的 r/s/t/u/v 共用 `spr_markerX`**：那五张图 ch1 没画。若将来要按 sprite 反查字母，
   ch1 会误判 —— 记着用**对象名**判，不用 sprite。
3. **`entrance` 的正确用法**：本轮只把它当"同机制"的旁证。真要按它推落点字母，
   需要**按分支解析**（本轮 `branch168.py` 已能做到，但 `verify_branch168.py` 实测它比
   `conn42b` 多识别分支 ⇒ **不能直接当判据**，要先把差异逐条归因）。
4. **W 的覆盖仍是 90.3%**（706/782）。剩下的 76 条不是 W 的问题，见第125轮报告 §7 那批老缺口。

---

## 9. 复现

```bash
# 取证（需要 UTMT；stdin 必须接 DEVNULL，否则挂死）
UndertaleModCli.exe load ch1_data.win -s _tools/probe168.csx > _evidence/probe168_ch1.txt 2>&1 < /dev/null
UndertaleModCli.exe load ch2_data.win -s _tools/probe168.csx > _evidence/probe168_ch2.txt 2>&1 < /dev/null

python _tools/make_evidence168.py      # → _evidence/doors168.json
python _tools/gen_routes168.py         # → 追加 88 条（条数不符会拒绝写入）
python _tools/check168.py              # → 41/0
python _tools/mutate168.py             # → 12/0

cd ../.. && python regress/run_all.py  # → 全量 IDENTICAL
```

---

## 10. 本轮踩到的坑（留给自己和下一轮）

1. **`stdin` 不接 DEVNULL，UTMT 直接挂死**：CPU 累计 0.06 秒、日志 0 字节、进程常驻 25 MB。
   只重定向 stdout/stderr 不够 —— `.NET 10` 的 `ConsolePal.GetCursorPosition()` 会挂住。
2. **`entrance` 被当成字母常量**（见 §3）—— 是本轮最贵的错误，靠 ch2 的数据才推翻。
3. **判据名是 `BinOp` 时，只认 `ast.Constant` 的扫描器会恒空**：`_desc_of` 第一版只数出 21 条
   （真实 41），`F4` 照样绿（扫不到就"没违规"），靠 `F5` 分母闸兜住。
   **"扫描器恒空"是"判据恒真"的反面，一样在假装守。**
4. **判据名里用「共」当计数标记会误伤「共用」**：判据过窄=误报，第107/160轮同族。
5. **变异体放 temp 目录时，判据自己按 `__file__` 推的路径全错** → 看起来像"判据不灵"，
   实际是"跑都跑不起来"。四个口子（`CQ_PKG168` / `CQ_ROUTES168` / `CQ_EV42` / `CQ_DOORS168` / `CQ_GEN168`）都指回真文件才测得准。
6. **`C2` 第一版用 `via` 重新拼 code 去查表** ⇒ 把 `table` 改错照样绿。
   正解：**用规则自己声明的 `table`**——判据要问"你报的那张表里有没有这条边"，不是"我替你算一遍"。
