# 第185轮报告 · ch1 森林 1/50 隐藏房投用 + 门字母接线

> 范围（用户裁定「**完整一条链**」）：登记 `room_man` 与 `room_forest_savepoint2` 两间场景、
> `area5` 的 A 门按原作确认、`room_man` 的 X 门 → savepoint2，
> 并把掷骰接到**推门**那条路上（用户裁定「**本轮一并修接线**」）。
> 判据 `check185`（**41 条**）· 变异 `mutate185`（**17 条**）· `_routes.json` **2,830 → 2,832**

---

## §1 为什么做这一轮

第182轮把"1/50 隐藏房"的概率机制做出来了（`_hidden_rooms` + `pick_hidden` + 掷骰注入），
但**只启用了 ch2 那一条**；ch1 的 `room_man` 一直挂着 `enabled: false`，理由是
"`from_scene` 那间房没登记、门也没接线"。本轮把它补完。

顺带查出一条比"补数据"重要得多的东西（§5）。

---

## §2 五处口径（用户逐条裁定，不要重问）

| 项 | 裁定 | 为什么这么定 |
|---|---|---|
| 本轮做什么 | ch1 `room_man` 投用 | 其余候选（ch4 取证 / ch3 找入边）都是"取证轮"，`room_man` 是唯一能"做成"的 |
| "做成"到哪一层 | **数据 + 机制 + 判据** | 不做真机走一遍（透明分层窗口的可见性只能靠内省对账，真机验证成本高、收益低） |
| 场景名 | zone `猩红森林·man` / index `森林·man` | 两层命名**本来就不同**（zone 带区域名、index 不带），沿用同区 27 个场景的派生惯例 |
| 范围 | 完整一条链（两间房 + 两条边） | 只做 `room_man` 会出现"进得去出不来" |
| 接线缺陷 | **本轮一并修** | 不修的话本轮做的东西在真机上等于没做（见 §5） |

---

## §3 ★★★ 先纠正一个前提：1/50 那扇门**不是 A 门**

我方案第一版写的是"把 `(area5, A)` 改成指向 starwalker"。**这是错的**，查完原件后纠正：

| 门对象 | 体积 | 有 area5 分支吗 | 实际机制 |
|---|---|---|---|
| `obj_doorA_Alarm_2` | **84 字节** | **没有** | 走通用「房间下标位移」：`_original.room_delta = 1`，rid 89 + 1 = **90**（`森林·迷宫前`，原作名 `room_forest_savepoint_relax`） |
| `obj_doorX_musfade.Alarm_2` | — | **有** | 才是 1/50 那扇：`ch = ceil(random(50)); if (ch == 50 && flag[910] == 0) room_goto(room_man); else room_goto(room_forest_starwalker);` |

所以：

- **`(area5, A) → before_maze`（priority 662）一个字都不用改**（`A10` 专门钉它没被动过）。
- 1/50 那扇是**字母 X** 的 `obj_doorX_musfade`，而它此前**一条边都没有** ⇒ 门查不到目标。
- `door_letter_of()` 取的是 `obj_door` 之后到第一个 `_` 的首字母：
  `obj_doorX_musfade → 'X'`、`obj_doorw_musfade → 'W'`。
- `area5` 这间房有**两扇门**（A 和 X）⇒ 旧实现"从这间房任意门出去都掷"是错的（见 §6）。

> 教训记在这里：**"这间房有 1/50"不等于"这间房每扇门都 1/50"**。原作的概率条件是挂在
> **门对象**的 `Alarm_2` 上的，同一间房不同门可以是完全不同的机制。

---

## §4 数据：两间房 + 两条边

### 4.1 两间场景

| 场景 id | rid | 物件数 | 来源 | 说明 |
|---|---|---|---|---|
| `ch1.forest.room_man` | **142** | **4** | 第115轮 `inst68.json` 的 `room_man` | 新登记（zone + index 各一处） |
| `ch1.forest.forest_bake_sale` | **82** | **10** | 同上 `room_forest_savepoint2` | **只补物件数据**，见下 |

★★ **`room_forest_savepoint2` 不是"未登记"** —— `_index.json` 里 rid 82 早就叫
`ch1.forest.forest_bake_sale`（"森林·义卖"）。我施工前以为要新登记，是错的。
它只是**缺 `_zone.ch1.forest.json` 的物件数据**（森林里 5 间这种"索引有、区域文件无"：73/82/90/96/97），
所以本轮只给它补 `objects`，不动 id、不动名字。

物件不是凭印象填的：`A4`/`A5` 拿 `src` + `pos` + `sprite` **逐条**对原作实例表比。
贴图映射用"现有数据里出现最多的那个"（不猜命名规律），`A6` 逐个 `os.path.isfile` 验存在。

`_zone.*.json` 的写法**和标准 `json.dumps` 不同**：缩进 **1**、纯 int 列表**内联**成 `[0, 200]`、
CRLF、**有**尾换行。所以施工脚本先证明"读进来再吐出去逐字节相同"（`P1`）才敢写。

### 4.2 两条边

```json
{"to": "ch1.forest.forest_starwalker", "priority": 9001,
 "when_scene": "ch1.forest.forest_area5", "when_door": "X",
 "_original": {"object": "obj_doorX_musfade", "event": "Alarm_2",
               "cond_man": "ceil(random(50)) == 50 && global.flag[910] == 0",
               "code": "if (room == room_forest_area5) {…}"}}

{"to": "ch1.forest.forest_bake_sale", "priority": 9002,
 "when_scene": "ch1.forest.room_man", "when_door": "X",
 "_original": {"code": "if (room == room_man)\r\n{\r\n    room_goto(room_forest_savepoint2);\r\n}"}}
```

`_original.code` 是**原作 GML 的逐字子串**（`A11` 拿它去原件里 `in` 一遍，CRLF 归一比），
防的是"我凭印象誊一遍"。两条分支其实在**同一个** `gml_Object_obj_doorX_musfade_Alarm_2` 里。

### 4.3 隐藏房登记

`_hidden_rooms[0]`：`scene = ch1.forest.room_man`、`enabled: true`、**`when_door: "X"`**、
`status: "enabled"`；顺手给 `[1]`（ch2）补 `when_door: "W"`。
`ch3` / `ch4` 两条继续 `enabled: false`，只登记不投用。

---

## §5 ★★★ 本轮真正的发现：接线缺陷（第182/184 两轮的功能在真机上等于没做）

### 5.1 症状

`_maybe_divert_to_hidden`（掷隐藏房骰）只挂在 `travel_to_scene()` 里。
而 `travel_to_scene` 全项目**只有 2 个调用方**，都是右键菜单（`main.py:16005/16008`）。

真推门走的是另一条链：

```
DoorProp.on_interact  →  _item_enter_scene  →  scene.switch
```

**直达，两边都不经**：

| 机制 | 本该挂在哪 | 实际挂着的地方 | 后果 |
|---|---|---|---|
| 掷隐藏房骰（182） | 换房前 | `travel_to_scene` | 推门时**一次都不掷** |
| 门控记账（184） | 换房后 | `_travel_feedback_done` | 推门时**一次都不写** ⇒ 门控**永不翻支** |

也就是说，第182轮的 ch2 隐藏房、第184轮的 W 门门控，**只要用户是正常走路推门，就完全不生效**，
而且**没有任何报错**（两条路径都正常返回 True，只是少做了事）。这是典型的静默降级。

### 5.2 修法

`_item_enter_scene(self, scene_id, door=None)` 重写成三段**固定顺序**：

```python
① target = self._maybe_divert_to_hidden(before, scene_id, door=door)   # 先改目的地
② ok = bool(self.scene.switch(target))                                  # 再换房
③ if ok: self._travel_feedback_done()                                   # 真换房了才收尾
```

`C6` 钉 ①在②之前（判据比行号），`C7` 钉 ③在②之后且真的调了。
两处都各自 `try/except` 包住并 `_log.exception`，理由不同：

- ① 失败 ⇒ 照常走原目标（掷骰是"加料"，不该让门打不开）；
- ③ 失败 ⇒ 换房已经成功了，不能因为记账炸了就把用户留在原地。

### 5.3 `item_interact` 侧：主动看签名，不靠捕异常

`item_interact` 是**零依赖 L1**（`G1` 硬闸禁止 import 项目内模块），而 `on_enter` 由接线层注入，
两边版本可以不同步 —— 项目里有一批桩把它写成 `lambda sid: ...`。直接传 `door=` 会让那些桩炸。
但"捕 `TypeError` 就退回旧签名"是错的：会把**宿主自己真实的 `TypeError` 一起吞掉**。所以：

```python
def _accepts_door_kw(fn):
    sig = inspect.signature(fn)              # 主动看，不猜
    if 'door' in sig.parameters: return True
    return any(p.kind is p.VAR_KEYWORD for p in sig.parameters.values())

def _call_enter(fn, scene_id, door=None):
    if door and _accepts_door_kw(fn):
        return fn(scene_id, door=door)
    return fn(scene_id)                      # 不知道是哪扇门 / 桩不认 ⇒ 什么都不变
```

`D4` 用 1 参桩验证"不炸"，`D5` 反过来验证**宿主的真方法确实接受 `door`**（不是只有桩认）。
只测 D4 的话，`_call_enter` 可以永远走旧签名也全绿 —— 两条必须成对。

---

## §6 门字母语义：`when_door` + fail-closed

```python
want_door = entry.get('when_door')
if isinstance(want_door, str) and want_door:
    if not (isinstance(door, str) and door):
        continue          # ★ 缺门信息 ⇒ 不掷
    if want_door != '*' and want_door != door:
        continue
```

四种"不掷"的情况：`enabled` 不是 True、概率不合法、`once` 且已发现过、
**指定了 `when_door` 但门字母对不上（含根本不知道是哪扇门）**。

★★ 缺门信息时**故意 fail-closed**，与 `gate_for`（184）同口径：掷骰会改**目的地**，
不知道走的是哪扇门就套用 ＝ "从这间房随便哪扇门出去都可能被扔进隐藏房"，
那比"不掷"坏得多。`B3` 钉这条。

★ 向后兼容：**没写** `when_door` 的老登记仍然"任意门都掷"（`B7`），`"*"` 同（`B8`）——
这两条是防止"为了本轮把老数据弄坏"。

---

## §7 ★★★ 施工中途撞出的真问题：priority 撞号

第一版两条手工边的 priority 取 7900/7901，理由是"7900 段空着"。**判断是错的**：

- `7901` 早被 `ch5.flower_castle.dw_fcastle_gloves_tower` 的 Any 门占着
  （第172轮按实例创建代码补的那条）；
- 更根本：**7850~8262 整段是 `gen_routes44.py` 用 `110 + scene_ord * BAND + k` 生成的区间**。
  手工边塞在里面，**以后重跑生成器就会再撞一次，而且不报错**。

撞号的后果不是"本轮行为错了"（两条边在**不同 `when_scene`**、不互相竞争），而是：
`route_for_door` 的第二键就是 priority，**同号时胜负退化成声明顺序**（`sorted` 稳定），
下次谁挪一行数据就会静默翻结果。

修法：`_tools/fix_prio185.py` **字节级**挪到 **9001/9002**（生成器够不到），
带三重自证：锚点恰好命中 1 次 · `dump2(parse(new)) == new`（**除这两处外一个字节没动**）·
改后全表只剩桌面那组 `200`（4 扇门，施工前就有、不同字母不竞争）。
`A13` 把这条件固化成判据："两条手工边 priority 全表唯一，且高于生成器区间"。

---

## §7b ★★★ 收尾阶段又抓到三处（都不是新功能，是**我自己留下的**错）

第 8 节那 41 条判据落地、`mutate185` 17/17 全抓之后，**全量 G2 第一次跑是 `rc=1`**
（182 个套件里 24 个红）。逐个查完，**3 个是我的真缺陷、21 个是引账**。三处真缺陷：

### 7b.1 载体重复：`bake_sale` 既有独立文件，又被我塞进 zone

`ch1.forest.forest_bake_sale.json`（3,022 字节，带 `bg`/`bgm`/`ambient`，10 个物件）
**本来就存在**，而且与第 115 轮证据 **10/10 逐条一致**。施工前我看到 zone 里没有它，
就顺手也往 zone 塞了一份 —— 于是同一个场景有了**两个载体**，物件被数两遍。

暴露它的是四条互不相同的老锁（这正是"判据互证"该有的样子）：

| 套件 | 报什么 |
|---|---|
| `verify_objects44 C2` | 物件总数 **4086**，而 C3 独立算出 **4076** |
| `rooms_round47 B1` | `room_man.json` 不存在（我却按"有独立文件"去断言） |
| `scene_route_original E1c` | 锚点 88 个里 `room_man` 没有 `bg` |
| `check185 A5` | 读 zone 那份拿不到 `bg` 来源 |

**修法**：`_tools/fix185b.py` 把 `bake_sale` 从 zone 撤掉，`room_man` 的 index 登记
改成同区惯例的六字段（不带 `file`，因为 zone 场景按惯例不写 `file`）。
判据侧把 `A3` 的**方向翻过来**（现在钉的是"`bake_sale` **不在** zone、只认它那份独立文件"），
并新增 **`A14` 载体唯一性**：

```
index 场景数 (2167) == 独立文件 (88) + zone 场景 (2079)
且三者无重叠 / 无孤儿 / 无空壳
```

这条是**结构性不变量**，不是当日快照 —— 以后再往 zone 里塞一个已经有独立文件的场景，
它会立刻红。

### 7b.2 `_hidden_rooms[1].status` 是第 181 轮留下的陈旧值

ch2 那间的 `enabled` 第 182 轮就是 `true`，但 `status` 一直写着 `data_only`
（第 181 轮"只登记不投用"那会儿的词）。**行为开关与口径描述自相矛盾** ——
往后任何按 `status` 读的判据/报告都会把"已启用"读成"只是登记"。

修法：`status` 改成 `enabled`，并在 `check181` 加 **`E4a`**：`enabled is True` ⇔ `status == 'enabled'`，
两个方向都钉（四间里任何一间对不上就红）。

### 7b.3 两条边的 `_original` 是**自造结构**，不属于任何已登记的原作机制

我第一版写的是 `{object, event, cond_man, code, evidence}` —— **没有 `kind`**。
于是 `verify_scene_route_original.C3`（"每条规则的 `_original` 自洽于**它声明的**原作机制"）
分派不到任何一类，判红"不自洽"。

**这不是判据苛刻。** `obj_doorX_musfade` 的 `Alarm_2` 本来就是
`if (room == X) room_goto(Y)` 的**查表**，正是第 125 轮收的 83 条 X 门、第 168 轮收的
220 条 W 门那一类（`delta_door_table`）。自造结构等于在表里留一条"谁也不知道它属于哪套机制"
的边，下一次有人按 `kind` 统计就会把它数丢。

**已按六条契约补齐**（`_table_self_ok` 逐条对应）：

| 字段 | 9001（area5 → starwalker） | 9002（room_man → savepoint2） |
|---|---|---|
| `kind` | `delta_door_table` | 同 |
| `table` | `gml_Object_obj_doorX_musfade_Alarm_2` | 同 |
| `via` | `obj_doorX_musfade` | 同 |
| `door_letter` | `X` | `X` |
| `marker` | `obj_markerX`（**实测**：`forest_starwalker` 物件表里有它） | `obj_markerX`（`forest_bake_sale` 有） |
| `src_room_name` / `src_room_id` | `room_forest_area5` / 89 | `room_man` / 142 |
| `dst_room_name` / `dst_room_id` | `room_forest_starwalker` / 88 | `room_forest_savepoint2` / 82 |

★ 房间号**不写死**：施工脚本 `/tmp` 版从 `_index.json` 的 `original_room_id` 反查，
反查不到就判红（宁可停下，也不许用"我记得是 88"填数）。
★ `marker` 也不是按名字猜的：先扫两个落点房的**物件表**确认 `obj_markerX` 真在，才写。
★ 旧的 GML 原文与出处（`code` / `cond_man` / `evidence`）**一条不删** ——
删了就没法复核"这张表是从哪读出来的"。

### 7b.4 顺带：`routes_order44.C1c` 把"手工边"与"生成器产物"混在一个段位判据里

修完 7b.3 之后它**仍然真 FAIL**：`C1c` 断言"X 段 == 83 条 且 priority 落在 5000~5999"，
而我两条手工边是 9001/9002（**故意**排在生成器区间之上，见 §7）。

改法：`_tbl_of` 加一个 `skip` 名单（默认空 ⇒ 老行为一字不变），把手工边摘出来
**改判"高于整个 X 生成器段"**（界取本段实测最大值，不写死数字），并新增 **`C1c2b`**：
W 段不许有绕开生成器的手工边（空集才通过）—— 多一条就要单独登记，不许静默放行。

---

## §8 判据 41 条

| 段 | 条数 | 内容 |
|---|---|---|
| A 数据 | **14** | 两间场景在 zone/index 都登记且 rid 对 · 物件数 4/10 · **逐条**对原作实例 src/pos/sprite · 贴图逐个存在 · routes 2,832 · 两条边的 to/priority · **`(area5, A)` 一个字没动** · `_original.code` 是原作逐字子串 · `when_door` = X / W · **priority 唯一且在生成器区间之上** · **`A14` 载体唯一性**（`index == 独立文件 + zone`，无重叠 / 无孤儿 / 无空壳；见 §7b.1） |
| B 纯函数 | 9 | 走产品 `load_routes()` 真身：X 门掷中 · **A 门不掷** · **`door=None` 不掷（fail-closed）** · roll=0.5 不中（1/50 是真的） · 已发现过不掷 · ch2 只在 W 门 · 无 `when_door` 任意门掷 · `"*"` 任意门掷 · 未启用的不掷 |
| C 接线（AST） | 8 | `pick_hidden` / `_maybe_divert_to_hidden` / `_item_enter_scene` 都有 `door` 形参 · **`pick_hidden` 里真的用上了门字母**（不是只加形参）· `door=` 传下去了 · **掷骰行号 < switch 行号** · **`_travel_feedback_done` 在 switch 之后** · `DoorProp` 经 `_call_enter` 传 `self.door_letter` |
| D 端到端 | 5 | 真 `build_props` 在 `room_man` 建出那扇门 → bake_sale · `area5` 两扇门**各走各的** · 真 `route_for_door` · `_call_enter` 对 1 参桩不炸 · **宿主真方法接受 `door`** |
| E 自检 | 5 | 无 BOM / 无 U+FFFD · 无 `check(..., True)` 恒真判据 · 不 import `main` / 不构造 `RalseiPet` · 判据自己不写死外部盘路径（AST 常量扫描）· 条数 **41** |

★ `E3`/`E4` 第一版是**纯文本扫自己** ⇒ 扫到了自己那一行字面量（"禁某短语出现"却用文本搜"短语"，
是这个项目反复踩的坑）。改成扫 **AST**：`E3` 看有没有 `RalseiPet(...)` 调用、`E4` 看常量里有没有
`^[A-Za-z]:[\\/]` 开头的绝对路径。

---

## §9 变异 17 条（全抓）

数据侧 `M1`~`M8`、`M16`：`when_door` X→A / 改成 `*` · 删 `room_man` · 少一个物件 ·
X 边改指 bake_sale · **动了那条本来就对的 A 边** · `_original.code` 抄错一个字 · 关掉 `enabled` ·
**ch5 那条 Any 门 priority 改成 9002 撞过来** · `M17` **把 `bake_sale` 塞回 zone**
（打 `A14` 载体唯一性 —— 这一条是 §7b.1 那个真事故的固化）。
代码侧 `M9`~`M15`：缺门信息也照掷 · 不比门字母 · 不传 `door=` · 掷骰挪到 `switch` 之后 ·
不走 `_travel_feedback_done` · `DoorProp` 改回旧签名 · `_accepts_door_kw` 恒 True。

**五条是夹具自己的错**（实测 0 红后改的，原因都留在注释里）——**都不是判据的问题**：

| 变异 | 第一版为什么等于没做 |
|---|---|
| `M9` | 只把 `continue` 改 `pass`，后面那句"字母不相等就 continue"照样拦下（`door` 是 `None`、`want_door` 是 `'X'`）⇒ 改成把 `door` 补成 `want_door` |
| `M11`/`M12`/`M13`/`M15` | **锚点没命中**：`main.py` / `item_interact.py` 盘上是 **CRLF**，锚点写的是 `\n` ⇒ `old in s` 恒假。`p_src()` 改成两侧都 `lf()` 归一，并加"锚点必须恰好命中 `count` 次"的断言 |
| `M10` | 锚点在 `gate_for` 里有**逐字相同的两行**（连缩进都一样）⇒ 带上一行注释才唯一 |

`M16` 特意挑"**别人撞过来**"而不是"改本轮那条"：改本轮那条的话 `A9` 会一起红，
就看不出 `A13` 自己有没有鉴别力了。

---

## §10 回归

### 10.1 施工期脚本（每个都自带"能失败"的自证）

| 脚本 | 结果 | 关键自证 |
|---|---|---|
| `_tools/apply185.py` | 第 1 遍 **12/12**，第 2 遍**空转 `rc=0`** | P1 三个文件各自无损往返（`_zone.*` 是非标准写法 ⇒ 专门写 `dumps_inline()`）· P2 原有 2,830 条逐条未变（多重集合）· P3 引用完整性 + 14 张贴图逐个真实存在 |
| `_tools/fix_prio185.py` | **11/11** | `dump2(parse(new)) == new`（其余字节一字未动）· `7901` 只剩 ch5 那条 · 全表只剩桌面 `200` 那组历史重复 |
| `_tools/fix185b.py` | **13/13** | 终态 `2167 == 88 + 2079`，重叠 `[]` / 孤儿 `[]` / 空壳 `[]` |
| `_tools/fix_worlds185.py` | **13/13** | 行级插入 `"142": "dark"`，`Counter` 差分 + "按位删掉那行后逐行全等" |
| `_tools/fix_orig185.py` | **21/21** | 房间号从 `_index.json` 反查（不写死）· `obj_markerX` 从物件表实测 · 逆向还原后整棵树逐字段相同 |
| `_tools/verify_hr185.py` | **16/16** | 按**位置**回滚（不是 `replace(…,1)`，那会命中 `"enabled"` 那个**键**）· 与 `HEAD` 结构差分恰好 `{status, when_door, note}` |
| `_tools/check185.py` | **41/41** | A 14 / B 9 / C 8 / D 5 / E 5 |
| `_tools/mutate185.py` | **17/17 全抓** | 双跑结果一致 · 6 个文件每步整文件还原并核 sha1 |

### 10.2 老锁引账（一律"只加账、不把历史数调小"）

改动 **26 个判据文件 + 基线**，没有一处是把历史数字悄悄改小：

| 套件 | 改动 |
|---|---|
| `第44轮 verify_objects44` | `MAN_185 = 4`；`C2 == EXPECT_TOTAL + ANY_EXPECT + MAN_185` |
| `第44轮 verify_routes_order44` | `C1c` 拆「生成器 83 + 手工 2」，手工边改判"高于生成器段最大值"；**新增 `C1c2b`**（W 段不许有手工边） |
| `第47轮 verify_rooms47` | `A5 n_scenes_4 == 826 + 1` |
| `第48轮 verify_items48` | `item_interact` 白名单加 `'inspect'`；`F2 dark == 809 + 1` |
| `第77轮 check77` | 新增 `_LEDGER_185 = {'ch1': 1}`，**减账后**再比 `BASE`（`BASE` 不动） |
| `第80轮 check80` | `C1` 改成"从现状副本摘掉账上那一间再深比"，配 `_ledger_missing` 防退化成永真；`C3 _delta + 1` |
| `第99轮 verify_scene_fit99` | `G27 obj_readable_room1 = 921 + 2` |
| `第112轮 check112` | `_II_OK_TOP` 白名单加 `'inspect'`（`item_interact` 新增了这个 import） |
| `第124轮 check124` | `EXPECT_SCENES = 2166 + 1` |
| `第125轮 check125` | `A0 = 2166 + 1`（两处） |
| `第126轮 check126` | `A0` 改成 `%d` 传 `2166 + 1` |
| `第168轮 check168` | `EXPECT_SCENES = 2166 + 1` |
| `第169轮 check169` | 同上 |
| `第170轮 check170` | **`D2b` 只对"带 `batch`"的批算段序**（手工边不属于生成器链）；**新增 `D2c`** 手工边登记制（高于生成器区间的无 batch 边必须与登记表逐条相等，多一条/少一条都红） |
| `第173轮 check173` | `MAN_185 = 4`；`D1 == EXPECT_ORIG_OBJS + MAN_185` |
| `第174轮 check174` | `MAN_185 = 4`；`D1` 断言 + 报文同步 |
| `第175轮 check175` | `EXPECT_SCENES` / `EXPECT_ZONE_SCENES` / `EXPECT_SELF_BEFORE` 各 `+1` |
| `第176轮 check176` | `RL_BASE` 剔除第 185 轮那 2 条（**结构判别**：无 batch 且 priority 高于生成器区间，不写死 9001/9002）；`B3` 加 `len(RL_185) == 2` 防判别式退化成空集；`EXPECT_SNAP_N = 3047 + 1`（`room_man` 自带一扇门） |
| `第177轮 check177` | `EXPECT_INDEX` / `EXPECT_ZONE` 各 `+1` |
| `第181轮 check181` | `E2` 白名单加 `enabled`；`E4` 拆成 `E4a`（`enabled` ⇔ `status` 不许打架）+ `E4b`（启用集合 == 登记表）；`F5` 40→41 |
| `第182轮 check182` | `A2` 改**集合账**；`A4` 2 条 2 理由；**新增 `A6`**（两间启用都齐"1/50 + once + when_door"）；B 段 13 处调用补 `door=`；`B5` 换负控制；**新增 `B12/B13/B14`**（缺门不掷 / 门不对不掷 / ch1 只认 X）；`D5` 28→32 |
| `第183轮 check183` | `A2`/`D3` 引 `_ADDED_185 = 2`；`B6` 补 `door='W'` |
| `第184轮 check184` | `EXPECT_ROUTES = 2830 + _ADDED_185`；`A7` 报文同步 |
| `regress/baseline.json` | `--update` 重建（182 套件） |
| `regress/run_all.py` | `SUITES` 新增 `check185`；desc 条数同步 41/17 并补记收尾三件事 |

### 10.3 全量 G2

```
run_all.py --update   → rc=0   合计 PASS=8102  FAIL=0   套件=182
run_all.py（复跑）    → rc=0   合计 PASS=8102  FAIL=0   套件=182
                       比对列：182/182 全部 IDENTICAL，【问题】段为空
```

★ **第一次全量回归是 `rc=1`**（24 个套件非 IDENTICAL，其中 1 个真 FAIL）。
逐个用 `_tools/dump_fails185.py`（AST 读 `SUITES` 的 `id → script`，因为 `script` 是
`os.path.join(...)` 的 `Call`、不能 `literal_eval`）捞 `[FAIL]` 之后：
**3 个是我的真缺陷**（§7b.1 载体重复 / §7b.3 `_original` 自造结构 / §7b.4 段位混判），
**21 个是引账**（数据面 +1 场景 +2 条边带来的分母/快照账）。
没有一条是"产品坏了"。

★ `routes_order44` 是唯一在引账之后**仍然真 FAIL** 的：它不属于"分母变了"，
而是"判据把手工边和生成器产物混在一个段位里"，属于**判据口径过时**（§7b.4）。
按本仓一贯做法：改的是"分哪种东西去判"，不是把 5000~5999 改成 5000~9999 糊过去。

---

## §11 本轮**没做**的（如实记录）

- `ch3.system.dw_ch3_man` / `ch4.second_sanctuary.dw_churchb_man` 继续 `enabled: false`
  （前者 `no_incoming_edge`、后者 `gate_unresolved`），只登记不投用。
- **其余 9 条 ch1 森林悬空边**不动（那些是"目标房没登记"的问题，不是本轮范围）。
- `bake_sale` 自己的门**不接线**：它走 `_fallback: desktop`（既有行为，2,832 条里没有任何
  `when_scene = bake_sale` 的边）。改了会让"从 savepoint2 出门"变成另一个行为，属于原作出门链的
  下一环，本轮不碰。
- **不碰 `match()`**（它至今零调用方，加了碰不到真实路径，还会破坏被 20+ 判据依赖的"完全确定性"）。
- **不做真机验证**：透明分层窗口的"可见面积"失效（见契约 ⑤），真机只能靠 Win32 `IsWindowVisible`
  + 内省对账，成本高、对"数据+机制是否接上"没有额外信息量。
- `forest_before_maze` / `forest_after_maze` / `forest_entrance` / `forest_thrashing_room`
  这 4 间仍然"索引有、zone 无物件数据"，本轮不补。

---

## §12 记忆复检

全文在详版 `§187.12`，此处只记结论：

- **详版**新增 `§187`（12 小节），本报告 §1~§11 的每条口径都能在详版找到落点。
- **速查本**做了一次**结构性合并**：`182` 与 `185` 并成一条 —— 182 那句「只启用 ch2」已被本轮推翻，
  留着就是行为描述与事实矛盾（与 §7b.2 那个陈旧 `status` 同型）。
- **体积守恒**：`js_len` **9,969 → 9,969**（`check95 A2` 硬闸 10,000，余量 **+31**）。
  新增 **238** 字符的条目，靠 **19 处压缩 / 删条**腾出 **256**、再补回 **18** —— 净增 0。
- **删了两整条老条目**（`182` 隐藏房概率、`175` 补房间号），都不是丢信息：
  前者被本条吸收，后者并入 `173` 的尾注（`175` 补 87 缺），且 `2166/2166` 这个数本轮已被 `2167` 取代。
- **逐令牌回验**：`490` 个去重令牌、`9` 个在新文件里找不到，逐个判定后**全是刻意压缩、0 真丢失**
  （明细表在详版 §187.12）。
- **硬闸**：`check95` **43/43**（`A2` 绿）。
