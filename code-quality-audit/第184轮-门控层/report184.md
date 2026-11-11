# 第184轮报告 · 门控层：同一扇门随剧情状态改去向

> 范围：**只做 `ch2.cyber_city.dw_city_traffic_3` 的 W 门这一扇**（用户裁定）
> 判据 `check184`（34 条）· 变异 `mutate184`（16 条）· `_routes.json` 2,830 → 2,830（**一条边没加没删**）

---

## §1 为什么要做这一轮

第183轮删掉那条 7122 误边后，收尾打了一条 `[NOTE]`：

```
7123 → dw_city_moss 仍被 7121 无条件遮挡 ⇒ dw_city_moss 目前不可达；
表里表达不出"先 dog_traffic 后 moss"的门控。
```

根因不是边写错，而是**表达力**：一条路由规则只能写「从哪个场景的哪扇门出去 → 一个固定目标」，
而原作 `obj_doorw_musfade.Alarm_2` 是**同一扇门按剧情状态走不同分支**：

```gml
if (global.flag[917] == 0 && scr_sideb_get_phase() == 0)
    room_goto(room_dw_city_dog_traffic);
else {
    var man_room = scr_sideb_get_phase() == 0 && global.flag[917] < 2
                   && global.flag[918] == 0 && ceil(random(50)) == 50;
    if (man_room) room_goto(room_dw_city_man);
    else          room_goto(room_dw_city_moss);
}
```

三分支里 `dog_traffic` / `moss` 是**确定性的两支**，只差剧情状态（`man` 那支是 1/50，
第182轮已由 `_hidden_rooms[1]` 承担，与门控无关）。

---

## §2 三处口径（用户逐条裁定，不要重问）

| 项 | 裁定 | 为什么这么定 |
|---|---|---|
| 状态源 | **复用 `plot_mark`** | 现成设施、自带落盘、`plot:` 前缀防撞名。它此前**零调用方**（等于死设施），本轮是它的第一处真实消费 |
| 记账时机 | **真站进去才写** | 与第182轮隐藏房同口径（`cur != sid`）：`switch` 失败 / 过渡被取消都不算。按"意图"记账会让门控**提前换支**且不报错 |
| 次数精度 | **只代理"去过 / 没去过"** | 原件 `flag[917]` 是**次数**（`< 2` 才继续掷 man），布尔表达不了这层。如实写进 `_original.note`，不假装保住 |
| 永久性 | **永久切换** | 与隐藏房"进过一次就永久锁"一致。副作用：`dog_traffic` 变成"只能去一次"的房间（它本来就只有一条回边 `7192`） |

---

## §3 形状：顶层 `_gates`，一个 route 对象都没碰

```json
"_gates": [{
  "when_scene": "ch2.cyber_city.dw_city_traffic_3",
  "when_door": "W",
  "mark": "ch2.city.dog_traffic",
  "set_mark_when_arrive": "ch2.cyber_city.dw_city_dog_traffic",
  "to_when_unset": "ch2.cyber_city.dw_city_dog_traffic",
  "to_when_set":   "ch2.cyber_city.dw_city_moss",
  "_original": { "cond_unset": "...", "cond_man": "...", "cond_set": "...", "evidence": "..." }
}]
```

**为什么不塞进 route 对象**：那要给 7121/7123 各加字段，而 `check169` 的 `_original` 指纹、
`check176` 的规范化 sha1 都对 route **逐字段**敏感 ⇒ 会撞一排与本轮无关的老锁。
放顶层只影响"统计文件字节 / CRLF 数"的纯回显套件。`A7` 专门钉"带门控键的规则 0 条"。

`_original` 里的三个 `cond` 是**从第170轮 `applied170.json` 抄的原文**（不是重写的），
`A8` 拿它逐字对账 —— 这条判据防的是"我凭印象誊一遍"。

---

## §4 依赖方向：门控**不**进 `item_interact`

`item_interact` 是零依赖 L1（`G1` 硬闸禁止 import 项目内模块）。第一版我图省事在
`route_for_door` 里直接调了 `scene_routing.gate_for`，**跑起来就炸**（`NameError`），
顺势把它改成注入式：

```
main._rebuild_item_props
    └─ scene_routing.gate_overrides(gates, sid, self.is_plot_done)   → {字母: 目标}
        └─ item_interact.build_props(..., door_overrides=那张表)      → 只当纯数据用
```

- `scene_routing` 一侧全是**纯函数**（`gate_for` / `gate_target` / `gate_overrides` /
  `gate_marks_on_arrival`），`is_done` 由外面注入 ⇒ 判据能单测，不需要构造真机。
- `item_interact` 一侧只多一个可选形参，**不传 ⇒ 行为与第183轮逐字相同**（`D3` 钉住）。

两处失败口径**故意相反**，各有理由：

| 位置 | 失败时 | 理由 |
|---|---|---|
| `item_interact`（宿主没给表 / 求值抛异常） | **fail-open**（当没门控） | 行为退回第183轮，可观测；反向会让门悄悄改道 |
| `gate_for`（没给门字母） | **fail-closed**（不套门控） | 门控会改**目的地**，不知道是哪扇门就套用 ＝ "随便哪个门出门都去 moss" |

---

## §5 记账

`_travel_feedback_done`（换房的**唯一收尾点**）里，紧跟在 `_commit_hidden_seen()` 之后
调用 `_commit_gate_marks()`：

1. 取 `current_scene`（**事实**），不是"刚走过哪扇门"（**意图**）；
2. `gate_marks_on_arrival(routes.gates, sid)` 查出"到这个场景该记哪笔账"（表驱动，
   不在 `main` 里写 `if sid == '...dog_traffic'`）；
3. 已经记过就跳过（`is_plot_done`），否则 `mark_plot_done`。

★ 第 3 步不只是省一次写盘：`plot_mark.mark_done` 是**整体覆盖**记录，
重复写会丢掉首次的 `note`（实测：`mark_done(m1, key)` 与 `m1` 不相等）。跳过之后 note 保得住。

---

## §6 判据 34 条

| 段 | 条数 | 内容 |
|---|---|---|
| A 数据 | 8 | `_gates` 存在且恰 1 条 · 七个必备键 · 值对 · 记账点 == 未记支目的地 · 两个目标**本来就有边** · 两个目标都在 `_index.json` 登记 · **带门控键的 route 0 条**（routes 仍 2,830）· `_original` 三 cond 与第170轮留档**逐字相同** |
| B 纯函数 | 10 | 走产品 `load_routes()` 真身：命中 · 换场景不命中 · 换扇门不命中 · **没给门字母不套用** · 未记/已记两支**必须不同** · 查账抛异常当没记 · `is_done=None` 当没记 · `gate_marks_on_arrival` 只认目的地 · `gate_overrides` 打成 `{字母:目标}` |
| C 接线（AST） | 7 | `build_props` 有 `door_overrides` 形参 · **读了表并且 `tgt = _ov` 用上** · `item_interact` 不 import `scene_routing`/`plot_mark` · 宿主 `gate_overrides(...)` + 关键字传参 · 两处记账顺序 · 记账读 `current_scene` · **`mark_plot_done` 有真实调用方** |
| D 端到端 | 4 | 真 `build_props`：未记 → dog · 已记 → **moss** · 不给表 → 与第183轮逐字相同 · 覆盖表塞无关字母不影响 |
| E 自检 | 5 | 无 BOM / 无 U+FFFD · 无恒真判据 · 不 import main / 不构造 `RalseiPet` · 判据自己不写死外部盘路径 · 条数 34 |

---

## §7 变异 16 条（全抓）

数据侧 `M1`~`M7`：删 `_gates` · `to_when_set` 改指 man · 记账点改成出发房 · `mark` 改名 ·
`cond_set` 抄错一个空格 · 偷偷给 route 加 `when_gate` · 门控挂错门字母。
纯函数侧 `M8`/`M9`/`M16`：缺门信息也套门控 · fail-open 翻 fail-closed · 记账不看目的地。
接线侧 `M10`~`M15`：漏传关键字 · 门分支不应用覆盖表 · 记账改看"刚走过哪扇门" ·
两处记账顺序倒过来 · 不再写账 · 破零依赖。

**四条是夹具自己的错**（实测 0 红后改的，都留在注释里）：

| 变异 | 第一版为什么等于没做 |
|---|---|
| `M7` | 文本替换 `"when_door": "W"` 命中的是**第一条 route**，不是 `_gates` 那条 ⇒ 改整表改写 |
| `M8` | 只把 `continue` 改 `pass`，后面那句"字母不相等就 continue"照样拦下 ⇒ 改成把 door 补成门控要求的字母 |
| `M12` | 替换的是 `main.py` 里**第一处** `current_scene`，根本不在记账函数里 ⇒ 改用四行唯一锚 |
| `M13` | 两个 `try` 块中间夹着注释，"拼成一串"找不到锚 ⇒ 打占位符对调 |

**两条是我把期望值猜错了**（按实测改期望、不改判据）：

- `M9`（fail-closed）—— 除了 `B7/B8`，还会把 `B6/B10/D1` 一起打红，因为"未记"这条
  分支整条失效了。这是对的，期望漏写了。
- `M11`（`if False and ...`）—— 只有 `D2` 能抓；`C2` 是**结构**判据（只看有没有读表、
  有没有 `tgt = _ov`），走不到的分支它看不见。这也对。

---

## §8 本轮踩的坑

1. **`item_interact` 里直接调 `scene_routing`** ⇒ `NameError`（违反零依赖 L1）⇒ 改注入式。
2. **`_index.json` 是三层嵌套**（章 → 区域 → 场景），第一版按 `INDEX['scenes']` 取，
   取到空表 ⇒ `A6` 报"两个目标都没登记"。改成**按形状摊平**（key 含 ≥2 个点、value 是 dict），
   将来多包一层也不会变成假绿。
3. **`_travel_commit` 不是收尾点** —— 记账调用实际在 `_travel_feedback_done` 里。
   第一版 `C5` 扫错函数，报"两处调用为空"。
4. **`current_scene` 是字符串字面量不是属性** —— `C6` 第一版扫 `ast.Attribute`，恒空。
   "扫描器恒空"是"判据恒真"的反面。
5. **`py_compile` 把已跟踪的 `.pyc` 改脏了**（`src/__pycache__/main.cpython-311.pyc`）。
   按 HEAD 版本拷回，`git status` 才只剩 4 个源文件 + 新轮次目录。
6. **回归跑到一半我在改文件** —— 那次"基线"里 `items_round48` 崩了（`NameError` 抓到的
   正是第 1 条那个中间版本）。教训：**全量回归期间不许动源码**，否则跑出来的东西既不是
   改前也不是改后。

---

## §9 回归

- `check184`：**34/34**
- 变异：**16/16**（双跑幂等 + 每步四文件 sha1 还原）
- 全量 G2（`--update` 之后复跑）：**181 套件 / PASS=8054 / FAIL=0 / 181 条全 IDENTICAL**
  （第183轮 180 / 8020 ⇒ +34 恰好是本轮新增）

### 被撞的 7 个套件 —— 全部是纯回显

| 套件 | diff 里唯一的差异 | PASS/FAIL |
|---|---|---|
| `check_readable_wire117` | `E1` 回显的 kwargs 多了 `door_overrides`（判据判的是"`readables=` 在不在"，仍在） | 36 → 36 |
| `check125` | `G2` CRLF `60240 → 60260` | 30 → 30 |
| `check126` | `G4` CRLF `60240 → 60260` | 35 → 35 |
| `check168` | `F7` CRLF `60240 → 60260` | 42 → 42 |
| `check172` | `D2` 文件字节 `2,440,496 → 2,441,765`、`D3` CRLF 计数 | 34 → 34 |
| `check176` | `E1` CRLF 计数、`E2` 无损往返长度 `2,209,959 → 2,211,030` | 32 → 32 |
| `check182` | `C1/C2` 回显的 `main.py` **行号**（多了 23 行，整体后移） | 28 → 28 |

逐条核过"PASS/FAIL 条数一字未变、没有新增 `[FAIL]`"才 `--update`。
**没有一条判据的阈值被改动** —— 撞的全是"统计文件字节 / 行号"这类回显。

---

## §10 本轮**没做**的（如实记录）

- 其余 **11 条惰性规则**、另外 **3 间隐藏房**（ch1 `room_man` / ch3 `dw_ch3_man` /
  ch4 `dw_churchb_man`）继续 `gate_unresolved`，只登记不投用。
- **不给 `match()` 加门控**：它至今零调用方，加了碰不到真实路径，还会破坏被 20+ 判据依赖的
  "完全确定性"。
- **不加手动重置开关**：标记一旦写入就是永久的（与隐藏房同口径），要重来只能删
  `data_store` 里的剧情标记文件 —— 本轮故意不提供这条口子。
- **`flag[917] < 2` 的次数精度**没代理（见 §2）。真要保住，得把 `plot_mark` 的布尔换成计数，
  那是另一个数据结构的事。

---

## §11 记忆复检（详版 §186.11）

- 详版追加 `§186`（11 小节）；速查本加 `184` 条目、§10 索引推到 `168~184`。
- **体积**：先把 `js_len` 从 **9979 压到 9857**（11 处冗词，全是近义词重复／历史别名），
  再塞进 110 字符新条目（含换行 +112）⇒ **9969**，余量 **+31**。
  `check95` 单跑 **43/43 IDENTICAL**（A2 体积硬闸 `js_len ≤ 10000`）。
- **逐令牌回验**：对 `git HEAD` 版做真 diff（CRLF 归一），1,173 个去重令牌，**27 个丢失**，
  逐条判定后全部是刻意压缩、**0 真丢失**；守卫 `_tools/slim184_mem.py` **36/36**
  （S1 体积 · S2 去处逐条举证 · S3 铁律仍在 · **S4 逐令牌真 diff**）。
- S4 特意加了「**白名单不多于实测丢失数**」—— 防止以后靠往白名单里加一串字来"合法削语义"。

