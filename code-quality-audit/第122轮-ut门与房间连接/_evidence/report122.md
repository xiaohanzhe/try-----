# 第122轮：ut 的门与房间连接

> 承接第121轮 §7 遗留第 1 条：「ut 的门（1,299 个实例）故意没写，建门要查路由，ut 段是空的」。
> 本轮把门解开：**243 条有原作出处的路由**，让 ut 里 **548/1,299** 个门实例变成真能推开的门。

---

## 1. 一句话结论

**上一轮 ut 一个门都建不出来，根因不在"没写门"，而在产品里一个 `if letter else None`。**

`item_interact.build_props` 原来的门分支是：

```python
tgt = route_for_door(routes, sid, letter) if letter else None
```

而 ut 的门对象**大多不带字母**（`obj_door_ruins13` / `obj_door_s_musfade` / `obj_door_t` …），
`door_letter_of()` 对它们一律返 `None` ⇒ **查表那一步根本没执行**，连日志都没有
（最后一个 `elif` 也要求 `letter`）。所以第121轮即使把门写进 `objects`，也是"点不动的门"。

---

## 2. ut 的门跟 Deltarune 不是一回事

| | Deltarune | ut |
|---|---|---|
| 名字 | `obj_doorA~F`，**字母即出口标识** | 两种：`obj_doorA/B/C/D`（也有字母）+ `obj_door_ruins13`/`obj_door_s_musfade`/`obj_door_t/u/v/w`/`obj_doorXmusicfade`（**不带字母**） |
| 目标怎么定 | 控制器按「房间 + 字母」算**下标位移**（A+1 / B-1 / C+2） | 写在 **GML 里**：`if (room == X) { room_goto(Y); }`，或 `room_goto_next()` |

实测 ut 侧：**34 种 door 对象 / 572 个（房间,对象）站位 / 1,299 个实例**。

---

## 3. 证据：只用可信层，一层不掺

两层证据（第115轮普查）里，**只有一层能当门的目标**：

| 层 | 条数 | 能不能用 |
|---|---|---|
| `conn115.json`（**可信层**，`code` = 反编译函数名 `gml_Object_obj_door_ruins13_Alarm_2`） | 131 | ✅ 用；最长前缀匹配取出门对象名 |
| `conn_inferred115.json`（**候选层**） | 563 | ❌ **一条不用** —— `rule` 字段自己写着「摆了该对象的房间就存在这条边 **未经验证**」，且其中 **420 条 `via=obj_mainchara`** 是"走到屏幕边缘换房"，不是门 |

可信层 131 条的**层层过滤账**（每一类丢在哪一步都记下来）：

| 步骤 | 剩余 |
|---|---|
| 原始边 | 131 |
| `code` 认不出对象名 | 0（丢 0） |
| **同 (房间,门对象) 多目标** ⇒ 条件分支，**不猜** | 129 组里丢 2 组 |
| 唯一目标 | 127 |
| **该房间没有这个门的实例** ⇒ 没有那扇门 | 丢 15 |
| 两端未登记为场景 | 丢 0 |
| **可用** | **112** |

被丢掉的两组多目标（如实留档，将来有剧情状态面再解）：

- `room_tundra_paproom` + `obj_battlerflowey` → `room_adate` / `room_papdate`
- `room_water11` + `obj_door_ruins13` → `room_water12` / `room_water_savepoint1`

另有一类走**原有字母机制**：`obj_doorA` 的 133 条候选边**全部** `off=+1` 且 `dst == src+1`
（133/133 自洽）= `room_goto_next()` 语义 ⇒ 这类本来就是字母 A，**不需要产品改动**，
但同样要求"那个房间真有 `obj_doorA` 实例"。

`obj_doorB/C/D` 与 musicfade 变体在证据里**一条边都没有** ⇒ **一条不写**（不猜）。

---

## 4. 覆盖率（两个分母，别混着算）

| 口径 | 分子 | 分母 | 比例 |
|---|---|---|---|
| **门实例**（同房多个同种门计多次） | 548 | 1,299 | **42.2%** |
| **站位**（房间,对象） | 243 | 572 | 42.5% |

两条账互相对得上：**243 条规则 → 243 个真站位（无重复、无幽灵）→ 548 个实例**。
剩下的 751 个实例是 `obj_doorB`(321) / `obj_doorBmusicfade`(113) / `obj_doorAmusicfade`(101)
/ `obj_elevatordoor`(13) 这类**证据里没有边**的门 —— 不是漏做，是**没出处**。

> ⚠️ 侦察脚本 `probe_doors122.py` 里那句「110（19.2%）」是**只算对象级**的偏小下界
> （不含 133 条字母级），已在该脚本里明确标注，不许拿来当最终覆盖率。

---

## 5. 产品改动：`when_src` 这一路，以及"两路互斥"

`_routes.json` 原有 `when_scene` / `when_door`，表达不了"这扇**不带字母**的门去哪"。
本轮新增 `when_src`（对象级路由），并**刻意**做了两个不对称决定：

1. **`route_for_door(routes, sid, letter, src=None)` 两路互斥**：
   先按 `when_src == src` 精确找；**字母那一路会跳过带 `when_src` 的条目**。
   不跳过会怎样：一条 `when_door` 为空的 ut 对象级规则会匹配**任意字母门** ⇒
   "到下一间"顶替"走 B 门" ⇒ **静默走错房间**。
2. **`scene_routing._match_one` 里，语境没给 `src` 时判不匹配**（与 `when_door` 的
   "缺席即放行"**故意相反**）：放行等于**凭空指定一扇门**。

两条都用**行为断言**钉住，不靠"代码里出现过这几个字"：

- `verify_doors122.D4`：对象级规则建出来的门 `door_letter is None`
- `verify_doors122.D5`：字母查询拿到 `RIGHT_A`、对象查询拿到 `WRONG`（互不串台）
- `check122.D5` / `verify_doors122.F1~F4`：正/负控制成对（不给 `src` ⇒ 不匹配；给了对的 ⇒ score 2；给了错的 ⇒ 不匹配；普通规则照旧匹配）

---

## 6. 数据落盘

| 文件 | 变化 | 行尾口径 |
|---|---|---|
| `assets/scenes/_routes.json` | 867 → **1,110** 条（+243 ut：110 对象级 + 133 字母级） | **CRLF + 无尾换行**（19,438 行，与原件同构） |
| `assets/scenes/_zone.ut.rooms.json` | 422 → **970** 条（+548 门 / 227 场景） | **纯 LF**（第121轮口径） |

`priority` 走**独立段 4000~4242 连续无洞**，追加在声明序末尾 ⇒ `verify_routes_order44.B3`
（段内单调不减）仍成立；`R4` 的 `_original.kind` 只有 `ut_door_src` / `ut_door_next` 两种。

两个文件的**行尾故意不同**（一个是 Deltarune 原生表、一个是 ut 分片），
`recheck122 ③b/③c` 分开断言，不许"统一成一种"。

---

## 7. 判据

**新增**

- `check122.py`（进 G2）**20/0**：A 规模形状 · ★★B **独立重算**（从 `conn115` +
  `conn_inferred115` + `inst_full.tsv` 重推每条 (场景,对象)→目标，逐条相等；配改目标负控制
  + 原样正控制 + **非空分母闸**）· C 与 `objects` **双射**（点不动的门 0 / 幽灵规则 0）·
  D 产品接线（AST 判 `src` 形参与 `src=` 传递 + 行为判字母/对象互不串台）· E 防回滚 · F 自检
- `verify_doors122.py`（真链路，不进 G2）**15/0**：243 条逐条建出门、目标逐条相等、
  不给 routes ⇒ 0 门、删 ut 条目 ⇒ 门消失、`on_interact` 真调 `on_enter`、**既有 297 个
  Deltarune 门场景加不加 ut 条目门清单逐条相同**（跨作品隔离）、`_match_one` 四正两负

**老锁按新事实改口径（一处都没放宽）**

| 套件 | 改了什么 |
|---|---|
| `check_objs121` | 16 → 18 条：门单独一遍写，准入闸 = 「`_routes.json` 里有目标」，B2b 双向锁住"点不动的门"与"幽灵规则"；**门由 `build_objs121` 本体写**（保证幂等，重跑不会抹掉） |
| `verify_objects44` | A2c/A2d 分母抬到 227 / 970 |
| `verify_routes_order44` | B2 只比**字母级**（对象级无字母，`None < str` 会炸）；B6 改「字母 **或** `when_src` 二选一非空」+ B6b 正负控制；C1 排除 ut 段 + **C1b 自证**（243 条 / 两端在 ut 场景表 / 去重后仍 243） |
| `verify_scene_route_original` | C3 加第三种机制分支（纯函数 `_ut_self_ok`）+ C3a4 样本 + C3a5 正负成对；**C3b 改成"按有没有字母筛"** —— 第105轮"按 kind 排除"这次排除不完（`ut_door_next` 带字母、`ut_door_src` 不带）⇒ 混合 `None/str` 排序 `TypeError`；配 **C3b1 非空闸**（防空集恒真）+ **C3b2 负控制**（塞 `door_letter='Z'` 必须判红） |
| `check105` | `_UT` 单独抽出（`_OLD` 排除 `('oneshot','ut.')`）+ C5b/C5c/D2e/D2e2；**50/0** |
| `verify_scene_fit99` | G24c 的 `_n_none` 期望 422 → 970（门也让 `sprite=None`，报真事实）；**108/108** |
| `verify_items48` / `verify_items68` | 跨作品同名分账那条：`(物, 门) == (422, 548)` **两段分开写**（谁缩水红谁那段），不再只锁总数 970 |

---

## 8. G2

```
合计：PASS=5979 FAIL=0 套件=121   （全部 IDENTICAL，diff 文件 0 个）
基线套件数 121，含 check122 = True
```

---

## 9. 明确不做（都有理由，不是遗漏）

- **`obj_doorB/C/D` / musicfade 变体的 751 个实例**：证据里没有边。`obj_doorB` 可能是
  `room_goto_previous`（要验 `off=-1`），但**候选层不可信**，等下一次取证。
- **`obj_mainchara` 的 420 条**：走到屏幕边缘换房，属另一层机制，**不是门**。
- **`cutscene`（375 个）**：`build_props` 落 `else` 丢弃，要动产品代码才能承载。
- **那两组多目标门**（`room_paproom`/`battlerflowey`、`room_water11`/`door_ruins13`）：
  原作按 `global.flag` 分流，**没有剧情状态面就没依据**，不猜。

---

## 10. 复检

`_tools/recheck122.py` 七项，逐项 PASS 落盘：

① 语法（16 个 .py，含两个产品核心文件，`ast.parse` 不产 `.pyc`）·
② 结构（两表 + 两处接线的**形状**，AST 判形参与关键字实参，不扫字符串）·
③ 编码行尾（无 BOM / 无 U+FFFD；`_routes` CRLF 无尾换行；`_zone.ut` 纯 LF）·
④ 恒真判据（AST + 正控制）·
⑤ 令牌回验（8 个令牌逐个 `in`）+ ⑤b 报告数字与实测对账（8 个数）·
⑥ **幂等**（重跑 `gen_routes122` 后 sha256 不变）+ 两条负控制（`_sha` 差一个空格就变 / 两表 sha 不同）·
⑦ 临时产物没落进仓库（临时文件放系统 temp，**用完就删**，不碰工作区）
