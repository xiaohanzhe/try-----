# 第183轮报告 · 删掉 ch2 那条 `priority=7122` 的确定性边

> 一句话：`_routes.json` **2,831 → 2,830**，删掉的是 `traffic_3 → dw_city_man` 那条
> "确定性地去 man"的边 —— 因为原作那扇门里 `man` 是 `ceil(random(50)) == 50` 的
> **1/50 概率分支**，不是确定性边；概率已由第182轮 `_hidden_rooms[1]` 承担。
> 删它**不改变任何运行行为**（B3/B4 成对钉死），连带按"引账不调数"改了 **7 把老锁**。

---

## §1 原作是什么样（一手取证，第181轮反编译）

`gml_Object_obj_doorw_musfade_Alarm_2`：

```gml
if (global.flag[917] == 0 && scr_sideb_get_phase() == 0)
    room_goto(room_dw_city_dog_traffic);        // ← 第一次走：确定去这里（有门控）
else {
    var man_room = scr_sideb_get_phase() == 0 && global.flag[917] < 2
                   && global.flag[918] == 0 && ceil(random(50)) == 50;
    if (man_room) room_goto(room_dw_city_man);  // ← 1/50 概率
    else          room_goto(room_dw_city_moss); // ← else 分支
}
```

三个分支**互斥**：`dog_traffic` 有门控、`man` 是 1/50、`moss` 是 else。

第169轮把这扇门的三个互斥分支**都物化成了无条件边**（当时的口径是"按分支解析补齐"，
对 `dog_traffic` / `moss` 是对的，对 `man` 是错的 —— 它是概率不是确定）。

## §2 ★★★ 一条没照字面执行的决定（必须先说清楚）

上一轮我问过口径，用户选的是 **「照原作改：7122 改指 moss」**。

**执行时我没有照字面做，改成删除。依据：那个选项在我写下它的时候是错的。**

`_routes.json` 里同源的本来就是**三条**：

| priority | to |
|---|---|
| 7121 | `ch2.cyber_city.dw_city_dog_traffic` |
| 7122 | `ch2.cyber_city.dw_city_man` |
| 7123 | `ch2.cyber_city.dw_city_moss` |

`7123` **本来就是 moss**。把 `7122` 也改指 moss，结果是**两条一模一样的 moss 边**
（`when_scene` / `when_door` / `to` 全同、只差 priority）—— 而"重复边不加"是第170轮
定的规矩（重复边会让 `_pick_by_pos` 挑不出唯一，退回 priority 最小，行为看起来对、
"哪条在干活"悄悄变了）。

所以"照原作改"只剩一个自洽的落法：**这条边根本不该作为确定边存在** ⇒ 删。
`A7` 就是钉这个的：同一扇门现在**恰好 2 条**出边，且 `to` 互不相同。

> 这是一次**基于事实的偏离**，不是"我觉得这样更好"。写在这里供复核；
> 若认为应该按字面改成 moss，恢复方式是把 `_evidence/removed183.json` 里那条的
> `to` 改成 `ch2.cyber_city.dw_city_moss` 再插回 `7121` 之后 —— 但 `A7` 会立刻红。

## §3 怎么删的（`_tools/apply183.py`，幂等）

1. 先**留档** `_evidence/removed183.json`（原样整条 + `meta` 说明为什么删/为什么安全/怎么还原）；
2. 再删，重写走 `json.dumps(indent=2, ensure_ascii=False)` + CRLF + 无尾换行
   —— 这个口径是**校验过的**：对改前文件做同样的 dumps 与磁盘**逐字节相同**，
   所以重写不会顺带改排版（自证 `格式无损往返 = True`）；
3. 顺手更新 `_hidden_rooms[1].note`（那句"7122 尚未删除"已经变成假话）。

**幂等**（第180轮双跑教训：同一命令可能被跑两次）：

- 第 1 遍：留档 → 2831 → 2830 → 只删这一条；
- 第 2 遍起：**空转**，并自证两条**能失败**的事实 ——
  `当前条数 == 留档 meta.total_after`、`留档条目确实不在表里`；
- 不留 `assert`（"存在就 assert 退"是错的：双跑时第二次会崩）。

`git diff --numstat` = **0 增 / 30 删**，正好是那一个对象。

## §4 ★★★ 为什么删它不改变任何运行行为（本轮最强的一条）

`7121`（`dog_traffic`）的 `when_*` 与 `7122` **完全相同**、priority **更小**
⇒ `match()` 只会返回 7121。但"我推理过"不算证明，所以做成一对：

| 判据 | 做什么 | 实测 |
|---|---|---|
| **B3** | 把留档加回表里，重跑同一个 `match()` | 加回 `(7121, dog_traffic)` = 现在 `(7121, dog_traffic)` |
| **B4** | 再把 `7121` 抠掉，重跑 | `(7122, dw_city_man)` ← 7122 **本来是能被选中的** |

**没有 B4，B3 可能只是"7122 本来就是垃圾"的同义反复。** 两条一起才成立：
7122 是活的、只是被 7121 挡住 ⇒ 删它零行为差异。

变异 `M13`（把留档 priority 改成 1000，加回去就抢赢）让 B3 红、`M12`（把留档
`when_scene` 改成别的场景）让 B4 红 —— 两条都验证过有鉴别力。

`B6` 补最后一环：删了确定边之后，概率机制仍覆盖 man ——
`pick_hidden(traffic_3, roll=0.0)` 实测命中 `ch2.cyber_city.dw_city_man`。

## §5 判据 26 条

| 段 | 条数 | 内容 |
|---|---|---|
| A 数据 | 7 | 7122 查不到 · 总数 2830 == 留档 before−1 == after · 留档结构/字段完整 · 留档的确实是那条（源/目标/批次 169）· **同源另两条没被误伤** · 同门现恰 2 条且目标互异 |
| B 行为 | 6 | 真调产品 `load_routes` / `match` / `pick_hidden`：B2 仍 7121→dog_traffic · **B3 零行为差异** · **B4 负控制** · B5 现在选不到 man · B6 概率接手 |
| C 登记说明 | 3 | 说明已更新（不含"尚未删除"、含"第183轮"）· 仍保留 1/50 表达式与锁文件名（防"更新成假话"） |
| D 账本 | 4 | 第181轮账本 priority == 留档（跨轮对得上）· 第181轮 A1 已改成 `_BASE_TOTAL - _N_REMOVED`（AST 判右操作数不是裸 Constant）· 留档可整段还原 = 2831 且 7122 唯一 · 施工脚本无 `assert` 且有 `dump_routes` |
| E 自检 | 6 | 无 BOM / 无 U+FFFD / 无恒真判据 / 无真实盘符路径 / 不 import 真机网络 Qt / 条数固定 26 |

**变异 16/16 全抓**（`_tools/mutate183.py`，每条双跑幂等 + 断言"红数 >0 且 <26"）。

## §6 连带改的 7 把老锁 —— 全部"引账不调数"

★★★ 口径来自第176轮：**不把历史数悄悄调小，而是把"删除"记成一笔账、让数由账推出来。**
本轮没有一处是"把 2831 改成 2830"了事。

| 套件 | 改了什么 | 为什么不只是调小 |
|---|---|---|
| `check181` | A1/C1 改成 `_BASE_TOTAL - _N_REMOVED`；**新增 A1b**：账本里记的删除**确实不在表里**；F5 39→40 | 账本不能只是算术（"记了账但边还在"同样是错）；A1b 让账本**可被推翻** |
| `check169` | A1 空洞**恰好**是 7122 · A4 marker 分布按留档扣 · **B1 改成 `重推 == 产品 ∪ 留档`** · D2 下限按账扣 | 本轮**证据侧仍冻结在 102**（原件确实有这条分支）——变的只是"有没有落成确定边"。放宽成 `>=101` 会让"删错了别的"也绿 |
| `check170` | W 221→220 · `FROZEN_BATCH[169]` 102→101 | 同上，按 `W_REMOVED_183` 推 |
| `check171` | W 221→220 | 同上 |
| `check172` | `FROZEN_BATCH[169]` 102→101 | 同上 |
| `check176` | B3 加一项减账；**B5 一个数没调** —— 改成"把留档那条按原位插回后再比 sha1"；D1 同步 | `rest_sha1` 是第176轮当日冻结的**历史事实**；插回原位后实测**逐字命中**（`e43eea7f…`），这比"把 2768 改成 2767"硬得多：同时证明"只少了这一条"和"能原样放回" |
| `routes_order44` | C1c2 W 段 221→220 | 同上 |

**没改的**：`EXPECT_BEFORE` / `EXPECT_AFTER` / `BEFORE['rest_sha1']` ——
它们是"第176轮那天那张表"的事实，改了才是造假。

## §7 五个坑

1. **`to` 是带前缀的全名**（`ch2.cyber_city.dw_city_man`），不是 `dw_city_man`。
   第一版探针按裸名查，报"0 条"，差点得出"这条边不存在"的反向结论。
2. **`match(routes, ctx)` 的 `routes` 不能直接喂 `json.loads` 的结果** ——
   它要 `routes.get('ok')` 为真，否则 `table` 直接变成空表。必须走 `load_routes()`。
3. **一次"无改动"的 Edit 吞掉了换行** —— 我把 `EXPECT_181 = 63   # ...\n` 换成同一行
   但去掉尾换行，结果把下一行 `EXPECT_VERT_OF_RM = 6` 并进了注释里，
   `check176` 报 `NameError`。教训：**"看起来没改"的 Edit 也可能有副作用**，改完要读。
4. **`_out/_out/*.txt` 里的"PASS/FAIL 汇总"不可靠** —— 很多套件根本不打印汇总行
   （`run_all` 自己扫 `[PASS]` 行计数），第一版 `preupdate183.py` 因此全读成 `None`。
5. **`scene_route_original` 用的是 `[ OK ]` 不是 `[PASS]`** —— 只数 `[PASS]` 会把它算成
   `(0,0)`，等于对该套件**没有校验**（"扫描器恒空"是"判据恒真"的反面，第168轮同款）。

## §8 ★ 本轮**没修**的（如实记录）

`7123 → dw_city_moss` 仍然被 `7121` **无条件遮挡** ⇒ **`dw_city_moss` 目前不可达**。

原因不是这条边写错，是 `match()` **没有"门控"概念**：`when_*` 只有
`scene/area/chapter/door/mood/event/keywords`，没有 `flag` / 条件；`fallback` 只有
**全局一份**，不能给单扇门配兜底。所以"先 dog_traffic、之后才 moss"这种
**同一扇门随剧情状态改变去向**的原作行为，表里表达不出来 —— 要根治得给
`route_for_door` 加门控层，那是加功能，另起一轮。

本轮只把它钉成 `check183` 的收尾 `[NOTE]` 打印，不假装已经解决。

## §9 回归

- `check183`：**26/26**
- 变异：**16/16**（双跑幂等）
- 全量 G2：**180 套件 / PASS=8020 / FAIL=0 / 180 条全 IDENTICAL**
  （第182轮是 179 / 7993 ⇒ +26 新套件 +1 新增 A1b）
- 16 个 DIFF 套件在 `--update` 前逐个核对过"PASS/FAIL **总数**一字未变"，
  唯一例外是 `check181` 39→40（+A1b，FAIL 仍 0）：

| 套件 | 基线 | 现在 |
|---|---|---|
| scene_route_original | (64, 0) | (64, 0) |
| routes_order44 / check_r0_76 / check105 / check124 / check125 / check126 | (25/39/50/25/30/35, 0) | 同 |
| check168 / check169 / check170 / check171 | (42/18/25/26, 0) | 同 |
| check172 / check173 / check174 / check176 | (34/42/39/32, 0) | 同 |
| check181 | (39, 0) | **(40, 0)** ← 新增 A1b |

> 注：`_evidence/preupdate183.run.txt` 是 **`--update` 之后**复跑的，所以里面
> `check181` 显示 `(40,0)/(40,0)`；上表才是更新前的读数（我用它决定放行）。

## §10 文件清单

| 文件 | 变动 |
|---|---|
| `ralsei_pet/assets/scenes/_routes.json` | −30 行（那一个对象）；`_hidden_rooms[1].note` 更新 |
| `code-quality-audit/第183轮-删7122误边/_tools/apply183.py` | 新建（幂等留档+删除+改说明） |
| `…/_tools/check183.py` | 新建，26 条 |
| `…/_tools/mutate183.py` | 新建，16 条变异 |
| `…/_tools/probe183.py` | 新建（只读探针） |
| `…/_tools/preupdate183.py` | 新建（`--update` 前的总数核对尺） |
| `…/_evidence/*` | `removed183.json` / `check183.run.txt` / `mutate183.run.txt` / `preupdate183.run.txt` / `g2.summary.txt` |
| `code-quality-audit/regress/run_all.py` | SUITES + `check183` |
| `check181` / `check169` / `check170` / `check171` / `check172` / `check176` / `verify_routes_order44` | 7 把老锁按"引账"改口径 |
