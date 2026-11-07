# 第169轮 · W 门按分支补齐

> 一句话：**第168轮那 98 条 W 边是下界，不是全集。** 根因不在门型，在
> `第42轮/_tools/conn42b.csx` 的一行 —— **每遇到一个 `Cmp` 就把 `srcRoom` 重置为 -1**。
> 这条缺陷让 ch2 有 **97 条** W 边的源房间变成 `-1`，被下游 `src >= 0` 过滤掉，
> 于是它们从来没进过场景图。本轮把源房间补回来，落 **102 条**，全表 1,828 → **1,930**。

---

## 1. 结论摘要

| 项 | 第168轮（graph 侧） | 第169轮（分支侧） |
|---|---|---|
| W 边来源 | `_room_graph.json` 的 98 条 | 反汇编 `Alarm_2` 逐分支解析 |
| ch1 / ch2 可认出的唯一边 | 60（graph 上限） | **173** |
| 落进 `_routes.json` | 88 | **+102** = 190 |
| 全表路由 | 1,828 | **1,930** |
| 桌面可达 | 220 | **220**（不变，见 §8） |

**四条独立证据说明补回来的边不是编的**：

| 检验 | 结果 |
|---|---|
| 「多出的边」落在 `conn42b` 的哪一批 | **113/113 全部**落在 `src=-1` 批里，**一处「找不到」都没有** |
| dst **多重集**是否逐值相等（防造边） | 6/6、6/6、**151/151**、13/13 全部相等 ⇒ **零造边** |
| `_room_graph` 里「graph 独有」的边 | ch1、ch2 **都是 0** ⇒ 解析结果是图谱的真超集 |
| 解析出的 `src` 是否越界 | ch1/ch2 **都是 0** |

---

## 2. 为什么要重审：一行 `srcRoom = -1`

`conn42b.csx` 第 119–131 行：

```csharp
else if (kind == "Cmp")
{
    srcRoom = -1;          // ← 任何 Cmp 都把源房间清掉
    if (pend.Count >= 2) { /* 只有当 pend 里恰好是 room 与常量时才重设 */ }
    pend.Clear();
}
```

`Call room_goto` 分支**不清** `srcRoom`。所以只要 `if (room == N)` 块里再夹一个比较，
那条 goto 的源房间就被清成 `-1`。ch2 里正是这种写法（`room_dw_mansion_east_2f_c` 等）：

```
46 PushBltn VAR=room / 47 PushI 27 / 48 Cmp / 49 Bf      ← 这里是 room==27
50 Push VAR=x / 51 PushI 290 / 52 Cmp / 53 Bf            ← 这里把 srcRoom 清成 -1
60 PushI 20 / 61 Pop entrance / 64 Call room_goto(48)    ← 这条边丢了源房间
```

对比 `conn42b` 的统计：

| 章 | code | conn42b 总条数 | `src >= 0` | `src = -1` | 解析器识别 |
|---|---|---|---|---|---|
| ch1 | `obj_doorW_Alarm_2` | 6 | 6 | 0 | 6 |
| ch1 | `obj_doorw_musfade_Alarm_2` | 6 | 4 | 2 | 5 |
| ch2 | `obj_doorW_Alarm_2` | **151** | **54** | **97** | **97** |
| ch2 | `obj_doorw_musfade_Alarm_2` | 13 | 9 | 4 | 11 |

ch2 的 `doorW` 恰好「解析 97 == `src=-1` 97」—— **一半的边丢了源房间**。

> **这不是门型问题。** 第125轮拒收 W 门用的是「落点自证率」这把尺；
> 第168轮推翻了那次拒收。本轮要推翻的是另一件事：**第168轮收的 98 条，
> 是「`conn42b` 没丢源房间的那部分」，不是「原作全部 W 边」。**

---

## 3. 顺带解出：分支 ↔ 哪一扇门（x 区间）

同一间房可以摆**多扇** `obj_doorW`（`room_dw_mansion_east_2f_c` 摆了 4 扇，
x = 0 / 360 / 1560 / 2540）。原作靠 `if (x >= lo && x <= hi)` 决定走哪扇。
GML 把它编译成：

```
Push VAR=x / PushI lo / Cmp / Bf
Push VAR=x / PushI hi / Cmp / B / PushI 0 / Bf     ← 短路
```

把区间解出来后与门实例坐标交叉验证，**多数分支的区间恰好命中一扇**：

```
room_town_mid   门 x = [301, 1082, 1740]
  x=[ 290,  370] -> room_lw_icee_pizza     命中 [301]
  x=[1730, 1840] -> room_alphysalley       命中 [1740]
  x=[1000, 1140] -> room_lw_conbini        命中 [1082]
```

ch2 的 164 条分支里 **52 条带 x 区间**；落地的 102 条里 **29 条**解出了「对应哪一扇门」，
写进 `_original.door_x`；其余 73 条在原作里没有位置条件（电梯、剧情开关），
或区间宽到覆盖多扇门，如实写 `door_x: null` 并把全部门坐标放进 `door_x_all`。

> ★ 解析器第一版在这里踩了坑：**每个 `Cmp` 都覆盖房间号**，把 x 比较前后的杂项常量
> （`400` / `12562` / `18113`）当成房间号 ⇒ 37 条越界。修法是「只在
> `PushBltn VAR=room` 之后紧邻的那一个 `Cmp` 才算房间守卫」。
> 修完后与第168轮的解析结果**多重集完全相等**（`(src, dst, entrance, code)`），
> 只是多了 x 区间 —— 这是「新解析没有偷偷改变旧结论」的硬证据。

---

## 4. 102 条的账（逐项点名，不许「不落就算了」）

```
176 条原始分支（ch1 12 + ch2 164）
 ├─  60  已由第168轮收（graph 侧那批）
 ├─   2  目标房**未登记成场景**：room_shop_ch2_spamton / room_shop_ch2_music
 │        （写不进表：`_routes.json` 的 `to` 必须是场景 id）
 ├─   8  已被**别的门型**覆盖同一 (场景, 目标)
 ├─   4  同一 (场景, 目标) 的重复分支（落点与 entrance 完全相同）
 └─ 102  本轮落地
```

落点分桶：

| 桶 | 条数 | 处理 |
|---|---|---|
| 目标房含对应字母的 marker | **83** | `marker` 写**真实对象名** |
| 目标房含通用 `obj_markerAny` | **15** | `marker = obj_markerAny` |
| 目标房有 marker 但没有这个字母的 | **4** | `marker: null`，**按原作照收** |
| 目标房零 marker | 0 | 那 2 条已在「未登记」被挡掉 |

> ★★ **与第168轮口径有意不同**：第168轮对「落点不自证」的 7 条是**拒收**的；
> 本轮用户口径是「**按原作，也落**」—— 那 4 条是原作 `entrance` 指向房内
> 不存在的落点（原作自己的问题），照收并在 `reason` 里写明。
> 差异单列成 `marker: null`，两个口径都能用判据分开数。

`marker` 实测分布（**真实对象名，大小写敏感**）：

```
obj_markerw 16 · obj_markert 18 · obj_markerv 11 · obj_markeru 12
obj_markerX 23 · obj_markers  3 · obj_markerAny 15 · null 4   = 102
```

---

## 5. 落地

- `ralsei_pet/assets/scenes/_routes.json`：1,828 → **1,930** 条。
  **只增不改**（`git diff --numstat` = `3151  0`）。
  用**文本插入**（锚点 `\r\n  ],\r\n  "_fallback"`）而不是整体重写 ——
  1.2 MB 的表 `json.loads`→`json.dumps` 会把全部 1,828 条的缩进重排，
  那样「改了哪几条」就再也看不出来了。
- 新条目字段：
  - `when_door: "W"`、`kind: "delta_door_table"`、`priority` **7088~7189** 连续
  - `_original.batch = 169`（分账用）
  - `_original.branch_letter` / `entrance` / `door_x` / `door_x_all` / `x_range`
  - `marker` 写真实对象名（4 条为 `null`）
  - `reason` 逐条写清「哪扇门（x 坐标）→ 哪个落点」，多出口场景注明
- 格式保持：**无 BOM / 纯 CRLF / 无尾换行**（`crlf=36364`、`bare_lf=0`、`tail='\r\n}'`）。

---

## 6. 验证

### 6.1 `check169`（18 条判据）

| 段 | 条数 | 内容 |
|---|---|---|
| A 段位与分母 | 8 | 分母 1,930 / priority 连续 / **priority 升序 == (章,源房,目标,门对象) 字典序**（保证可复现）/ 只落 ch1~ch5 / 段位字段 / marker 只用真实对象名且**大写 `obj_markerW` 一条都不许有** / 无重复 / 两端场景都在索引里 / **`table` 必须能由 `via` 推导** |
| B 独立重推 | 3 | 守恒账逐项点名 · **独立重推 == 产品段**（双向差集空）· 每条能回溯到具体一条分支的 (章,门对象,代码名,源房,目标房,entrance) |
| C 落点自证 | 3 | 落点分桶 · **`marker` 真的出现在目标房对象表里**（大小写敏感，不拼字符串）· 负控制：大写名 0 条 |
| D 关联口径 | 3 | 一房多出口 37 个场景点清数目 · 反回滚 · **第168轮那 88 条原样保留** |

结果：**PASS=18 FAIL=0**。

### 6.2 `mutate169`（11 个变异，全部符合预期）

| 变异 | 期望红 | 说明 |
|---|---|---|
| M1 priority 挪出 7088 段 | A1 A1b | |
| M2 marker 写成大写 `obj_markerW` | A4 C2 C3 | 第125轮那把错尺，三个判据同时抓 |
| M3 `when_door` 改成 X | A3 | |
| M4 `table` 换成另一个门对象（`via` 不动） | A7 B2 | ★ 见 §9 第①条 |
| M5 目标换成另一间房 | B1 B2 | |
| M6 复制一条（同门同目标） | A0 A1 A1b A4 A5 | |
| M7 抹掉一条的 `batch` 标记 | A1 A4 B0 C1 D1 D2 D3 | 会被算成第168轮的老条 |
| M8 把有落点的改成 `None` | A4 | |
| **M9 无害：只改一句中文说明** | **（一条都不红）** | 判据不扫文本 |
| M10 交换两条 priority（段位仍连续） | A1b | 专抓「priority 对但顺序乱」 |
| M11 源房号改成 999 | A1b B2 | |

字节级还原：`sha1` 不变（`f658c5bbe41f`），真表复跑 **18/0**。

### 6.3 全量 G2

```
合计：PASS=7592 FAIL=0  套件=167
```

**167 个套件全部 IDENTICAL**（无【问题】段）。为此重建了 9 个基线：
`check169`（新）· `check168` · `check126` · `check125` · `check124` ·
`scene_route_original` · `routes_order44` · `check_r0_76` · `check105`。

---

## 7. 连带改的老判据（**都是新数据顶到旧账面，不是放宽**）

| 文件 | 改动 | 原因 |
|---|---|---|
| `第168轮/_tools/check168.py` | `W_RULES` 过滤加 `not _o.get('batch')`；`EXPECT_ROUTES` 1828→**1930** | 分账：168 只数它自己那 88 条，历史结论一字不动 |
| `第168轮/_tools/verify_branch168.py` | `ANY` 改成**后缀集**；删死代码 `elif L=='x'` | ★ 两个判据缺陷，见 §9 第③条 |
| `第126轮/_tools/check126.py` | 分母 1828→**1930**（两处） | 路由总数 |
| `第125轮/_tools/check125.py` | `EXPECT_W_IN_PROD` 88→**190** | W 段 = 168 的 88 + 169 的 102 |
| `第124轮/_tools/check124.py` | `EXPECT_UNIQUE_EDGES` 1823→**1925** | 唯一边（1,930 − 5 组合法重复） |
| `第44轮/verify_routes_order44.py` | `C1c2` 88→**190** | W 段合计 |
| `第36轮/verify_scene_route_original.py` | `_table_self_ok` 改用 `branch_letter` 校验 marker | ★★ 见 §9 第②条 |
| `regress/run_all.py` | 新增 `check169` 条目 | |

---

## 8. 桌面可达为什么没变

`check124` 的「桌面可达并集」算的是**从 desktop 出发能走到的场景数**。
本轮 102 条边的源场景全部是 ch1/ch2 里的**战内房间**，它们本身已经在可达集里
（或本来就不在），补边不会新增「从桌面能到达的场景」。

⇒ 覆盖 `706/782 = 90.3%` 这个数**也不会动**。这一点必须说清楚：

> **90.3% 这个 KPI 是双盲的。** 它的分母 `_room_graph` 只收了 **98** 条 W 边
> （而且全是 `obj_doorW` 的单分支边），本轮补的 102 条**大部分不在图里**。
> 补进去分子分母都不动 ⇒ 真实连通性提升了，指标一点感觉都没有。
> 它衡量的是「图里的边有没有被 routes 覆盖」，**不是「原作连通的还原度」**。

---

## 9. 本轮踩的坑（六个）

### ① 变异 M4 抓到一个真缺口：`table` 没人校验

把某条规则的 `_original.table` 改成**另一个门对象**的 `Alarm_2`（`via` 不动），
**一条判据都不红** —— 因为 `A3` 只查 `via`、`B2` 只比 `via`。
而「这条边是从哪段代码读出来的」已经错了。

⇒ 补 **`A7`：`table` 必须能由 `via` 推导**（`gml_Object_<门对象>_Alarm_2`），
并把 `table` 并进 `B2` 的回溯元组。

### ② `C3` 拿门字母去校验落点 —— 分支级规则必然失败

`第36轮` 的 `_table_self_ok` 用 `_marker_ok(marker, door_letter)` 校验。
第168轮的 88 条恰好「门 W → 落点 w」所以一直绿；本轮的分支级规则**门是 W、
落点可能是 S/T/U/V/X**（这正是 `entrance` 的真语义）⇒ **71 条正确的规则被判「不自洽」**。

⇒ 改成：`batch=169` 的规则用 `branch_letter` 校验；`marker is None`（目标房
没有这个字母的落点）的存在性自证交给 `check169.C1/C2`。

### ③ `verify_branch168.py` 自己有两个判据缺陷

- `ANY = ('obj_markerany', 'obj_markerany40px')` 拿**完整对象名**去比 `ds`
  （`ds` 存的是**后缀** `'any'`）⇒ 求交**恒为空**，29 条通用 Any 落点被误判 MISS，
  ch2 命中率假跌到 **73.2%**。改成后缀集后 **90.9%**。
- `elif L and ('x' == L) and 'x' in ds` 是死代码（上面的 `L in ds` 已覆盖）。

### ④ 变异 M4 第一次「没红」是**夹具自己的错**

`_mine[0]` 的 `via` 本来就是 `obj_doorw_musfade`，改成 musfade = **没改**。
「夹具不保真 = 报假问题」—— 必须挑 `via=obj_doorW` 的那条来改。

### ⑤ CRLF 锚点

改 `verify_routes_order44.py` 时锚点 `\n` 对不上 `\r\n`（读文件用了 `newline=''`）。
必须先归一化再匹配、写回时还原。

### ⑥ 解析器第一版把杂项常量当房间号

见 §3 末。37 条越界（`src=400` / `12562` / `18113`）。

---

## 10. 复现

```bat
cd /d "C:\Users\23002\Desktop\项目文件夹\try - 副本"
set PY=C:\Python311\python.exe

:: 1) 分支级解析（含 x 区间）—— 产出 _evidence/branch_x169.json
%PY% code-quality-audit\第169轮-W门按分支补齐\_tools\branch_x169.py

:: 2) 生成 102 条（不写产品表）—— 产出 _evidence/w_rules169.json
%PY% code-quality-audit\第169轮-W门按分支补齐\_tools\gen_routes169.py

:: 3) 文本插入产品表（幂等：已含 batch=169 则拒绝执行）
%PY% code-quality-audit\第169轮-W门按分支补齐\_tools\apply_routes169.py

:: 4) 判据 18 条
%PY% code-quality-audit\第169轮-W门按分支补齐\_tools\check169.py

:: 5) 变异 11 个（字节级还原 + 真表复跑）
%PY% code-quality-audit\第169轮-W门按分支补齐\_tools\mutate169.py

:: 6) 全量回归
%PY% code-quality-audit\regress\run_all.py
```

全量结论行：`合计：PASS=7592 FAIL=0  套件=167`（全部 IDENTICAL）。

---

## 11. 遗留（本轮不做，已留档）

1. **37 个场景是一房多出口**，而产品侧 `route_for_door(sid, letter)` 每个
   (场景, 门字母) 只返回**一个**目标 ⇒ 运行时每场景只生效一条。
   本轮按「按原作」把多条都写进去了（数据完整），但运行时会取其中一条。
   **根治要「位置级落点」**（用 `door_x` / 玩家 x 选门）＝加功能，本轮不做。
2. `conn42b.csx` 的那行 `srcRoom = -1` **没修**（改了要重跑 UTMT 并重生成
   ch1~ch5 全部 `conn42b`，会波及第125/126/168 轮的证据基准）。本轮用
   `branch_x169.py` 单开一份解析绕开它。
3. `_room_graph.json` 的 W 边仍是 98 条（**下界**）。改它＝改第42轮的取证文件，
   本轮不动。
4. 2 条边（`room_shop_ch2_spamton` / `room_shop_ch2_music`）因为目标房**没登记成场景**
   写不进表 —— 要落得先给那两间房建场景记录。
5. `room_dw_mansion_east_2f_c` 这类房间的「分支 ↔ 哪一扇门」仍有 73 条未解出
   （原作按剧情标志分流，不是位置）。
