# 第159轮：空白名字不算一个人

> **入口**：第158轮 `report158.md §9` 结转的第 4 条里最确定、最小、可实测的一件 ——
> 第150~153轮一路结转的「**纯空格 `npc_id` 不拒**」。
> **用户口径**（逐字贯穿）：「**按照人类的逻辑来就好**」。

---

## 1. 结论

**名字是空的不算一个人；带前后空格的，也不是他。**

改前，`assign_errand('   ', …)` 能造出一条"**看不见的人**"的在办，它会写进盘、
会进 prompt、`working_positions()` 每拍还会把他往目的地压。更隐蔽的是 `' ralsei '`：
它跟注册表里的 `'ralsei'` **不是同一个键**，于是同一个人占**两个槽** —— 他一个人两条在办、
名额虚耗，而且第二次派活 `active_of('ralsei')` 取不到旧的 ⇒ 不算改派 ⇒ **旧那条永远留在外面**，
直到自己到期。

修法只有一条原则：**判据是 `strip()` 后非空，但绝不 strip 后使用 —— 宁拒不改写。**
四道口子（宿主 2 + 机制层 2）+ 一处欠账表，全部只加判据、不改任何语义。

| 项 | 数值 |
|---|---|
| 产品改动 | `src/main.py` +15 −1 行（18901 行 / 813230 字符，全 CRLF）· `modules/npc_errand.py` +30 −4 行（427 行 / 15630 字符，全 CRLF） |
| 判据 | `check159` **25/0**（A 13 真跑 / B 7 AST / C 5 自检） |
| 负控制 | `mutate159` **8/8** + Z1 收口全绿 + Z2 sha1 不变 |
| 复检 | `recheck159_core` **36/0**，另加两条对复检自身的负控制（N1/N2 都真红） |
| 探针 | `probe159` 改前 **6/6**、改后 **6/6**（成对，不是"改完才写一份"） |

---

## 2. 改前实测（`probe159 --before`，6/6 全过）

| # | 输入 | 改前实际发生了什么 |
|---|---|---|
| P1 | `assign_errand('   ', 场景, 事由)` | 派成，在办 **1 条**；`_npc_errand_save()` 落盘后盘上是 `"npc_id": "   "`，重启读回 **1 条** |
| P2 | `' ralsei '` 再 `'ralsei'` | 槽位 `[' ralsei ', 'ralsei']` —— **两个槽**（同一人两条在办） |
| P3 | `assign_errand('ralsei', '   ', 事由)` | 进得去（会去压一个不存在的场景） |
| P4 | `what='   '` | 原样存 `'   '`（界面显示"办「   」"） |
| P5 | 老档里 `npc_id: "   "` 的条目 | 读回 1 条 —— **重启后那个"人"又出门了** |
| P6 | 机制层 `ErrandBoard.assign('  ', …)` | 放行（不靠宿主兜） |

---

## 3. 改法：四处判据 + 一处归一

```python
# ① 宿主 assign_errand（main.py，排在 _npc_errand_gate **之前**）
if not isinstance(npc_id, str) or not npc_id \
        or npc_id != npc_id.strip():
    _log.info('派活被拒：npc_id 为空、全是空白、或首尾带空白（%r）', npc_id)
    return None
if not isinstance(dest_scene, str) or not dest_scene \
        or dest_scene != dest_scene.strip():
    _log.info('派活被拒：目的地为空、全是空白、或首尾带空白（%r）', dest_scene)
    return None

# ② 模块级 _errand_given_up_add（main.py）
if not isinstance(npc_id, str) or not npc_id \
        or npc_id != npc_id.strip():
    return

# ③ ErrandBoard.assign（npc_errand.py）—— id 与地点
if not isinstance(npc_id, str) or not npc_id \
        or npc_id != npc_id.strip():
    return None
if not isinstance(dest_scene, str) or not dest_scene \
        or dest_scene != dest_scene.strip():
    return None
#    事由：纯空白归一，但**活照样派**
if not isinstance(what, str):
    what = ''
elif not what.strip():
    what = ''

# ④ Errand.from_dict（npc_errand.py）—— 老档也挡
if not isinstance(npc_id, str) or not npc_id \
        or npc_id != npc_id.strip():
    return None
```

### 3.1 为什么判据是「两半」：`not x` **和** `x != x.strip()`

只写 `npc_id.strip()` 只能挡住 `'   '`。第一版补丁我就是这么写的 —— 改完 `P2` 当场仍然红：
`' ralsei '` 照样占一个独立的槽。**"全空白"只是脏输入的一半**，另一半是首尾带空白。
这一半更阴：它看起来"像个人"，界面上也显示得出来，只有在对注册表/记忆/名册做 key 查时才会露馅。

### 3.2 为什么**绝不 strip 后使用**

最省事的修法是 `npc_id = npc_id.strip()` 然后照常派。这是**静默改写**，比不改更坏：

- `' ralsei '` 被改成 `'ralsei'` 之后，"派活时写进来的这个人"和"注册表里那个人"看似对上了，
  但用户输入的原样已经丢了；
- 更麻烦的是**同一份输入在三个地方按不同口径解释**：记忆按 id 存、欠账按 id 去重、名册按 key 查。
  一旦有一处忘了 strip，同一个人就裂成两条记录 —— 而这正是本轮要修的病。
- ⇒ **宁拒不改写**，与 `Errand.from_dict` 的老规矩一致（那里一直是不合法就丢那一条）。

`mutate159 M6` 专门把这个反例做成负控制：把判据换成真的 `npc_id = npc_id.strip()`，
`A2`（一个人只能一个槽）与 `B6`（全仓不许有这种赋值）当场变红。

### 3.3 为什么宿主那两道闸必须排在 `_npc_errand_gate` **之前**

门控对**未知 id** 可能给出"去不了"。如果先问路再验名字，脏参数会走成这样：

```
assign_errand('   ', 'oneshot.barrens.Blue', …)
  → _npc_errand_gate('   ', …) 判"去不了"
  → _npc_errand_note('   ', '我本来要去 X，但去不了 —— …')
```

于是记忆里多一条「我本来要去 X，但去不了」的**假自述** —— 说这话的"人"根本不存在。
**参数就不是人，连问路都不该问**；同理不写欠账、不产生档。

`A5` 用"门控一次都没被调"守这一条（`gate_asked == []`），`B5` 用 AST 的 `lineno` 比大小独立守一遍。
`mutate159 M4` 是这一条的负控制：只把闸挪到门控之后（闸还在、逻辑没变），`A5`/`B5` 就红。

---

## 4. 两条"看着该红却没红"的实得（写负控制时才发现的）

这两条都不是 bug，而是**产品本来就是双层的**，值得记下来，免得下一轮误判"判据失效"：

1. **删掉宿主 `dest_scene` 闸，`A3` 仍然绿**（`M8` 只红 `B4`/`B5`）。
   因为机制层 `ErrandBoard.assign` 自己也挡地点 ⇒ 行为面被兜住了，只有 AST 能看出宿主那层少了。
2. **删掉宿主 `npc_id` 闸，`A13` 仍然绿**（`M1` 红的是 `A5`/`B4`/`B5`）。
   同理：机制层自己挡得住 `'   '`，反而是 `A5`（"门控没被问"）先红 —— 因为闸没了，
   脏参数一路走到门控门口。

⇒ 教训：**行为面的判据和 AST 判据必须两套都在**。只写行为，"某一道闸被绕过但被另一道兜住"
永远发现不了；只写 AST，"闸在、但顺序错了"也发现不了。

---

## 5. 判据（`check159` 25/0）

| 段 | 条数 | 守什么 |
|---|---|---|
| A 真跑 | 13 | 四种脏输入各拒 · **门控一次都没被问** · 不写记忆 · 不写欠账 · **不产档** · 老档幽灵丢弃而正常条目照读 · 机制层两道口子都堵 · 空白事由归一但**活照派** · 正常路照常落盘读回 |
| B AST | 7 | 四处判据都含"首尾空白" · 宿主两道在门控**之前**（`lineno` 比较）· 全仓无 `npc_id = npc_id.strip()` · `what` 归一分支在位 |
| C 自检 | 5 | 分母闸 · 判据名字面量 · 只用 `check()` · 无 BOM 全 LF · 零外部盘 |

`B` 段的关键实现（不用文本扫，第108.6）：

```python
def _has_strip_guard(fn, name):
    for n in ast.walk(fn):
        if isinstance(n, ast.Compare):
            side = [...]   # 比较两侧里的 `.strip()` 调用
            other = [...]  # 比较两侧里的同名 Name
            if side and other:
                return True
```

---

## 6. 负控制（`mutate159` 8/8 + Z1/Z2）

| # | 破坏 | 实得红点 |
|---|---|---|
| M1 | 宿主删掉 `npc_id` 闸（脏参数照进） | `A5 B4 B5` |
| M2 | 机制层 `assign` 的 id 判据**只挡全空白** | `A13 B1` |
| M3 | `Errand.from_dict` 退回"只挡空串"（老档幽灵复活） | `A10 A8 B3` |
| M4 | 宿主判据挪到**门控之后**（脏参数先问路） | `A5 B5` |
| M5 | 空白事由**不归一**（原样存 `'   '`） | `A4 B7` |
| M6 | 改成**静默改写**（`npc_id = npc_id.strip()`） | `A2 B6` |
| M7 | **一刀切**：任何非空 str 都拒 | `A11 A2 A4 B4 B5` |
| M8 | 宿主删掉 `dest_scene` 闸 | `B4 B5` |

`M4` 第一版写的是"整段删掉"，与 `M1` 同效（红点一模一样）—— 那不是独立覆盖，
而是同一个破坏做了两遍。改成真的"插一道门控在闸前面"之后，红点变成 `A5 B5`，
才真正验到了**顺序**这条。

`M6` 第一版是 `if False` 死代码（Python 不产 `ast.Assign` 就抓不到 `B6`），改成真的
`npc_id = npc_id.strip()` 才成立。

---

## 7. 复检（`recheck159_core` 36/0）

本轮改了**两个**产品文件（上轮只改 `main.py`），所以复检面比上轮宽：

| 段 | 守什么 |
|---|---|
| H1 | 产品侧只该动那两个文件；未跟踪项全在本轮目录内 |
| H2 | 两个文件**都没缩水**（与 `HEAD` 比，反回滚闸）；净增有上限；删除行 ≤ 8 |
| H3 | 两个产品文件 + 四个工具脚本都能 `ast.parse`（不用 `py_compile`，别产 `.pyc`） |
| H4 | 全 CRLF、裸 LF = 0、无 BOM、无 U+FFFD；工具脚本全 LF |
| H5 | 四处判据都在、**两半都在**、宿主两道在门控**之前**（与 `check159` B 段独立实现） |
| H6 | 令牌**按预期次数**回验：`main.py` 三处、`npc_errand.py` 三处、旧写法残留 0 |
| H7 | 判据名是字面量 · 不用 `ok()` · 8 处破坏都有期望 · 探针挂产品函数 |
| H8 | 四件齐 · 基线已登记 · `SUITES` 已登记 · 没碰 `.pyc` · 不依赖外部盘 |

### 7.1 复检自己也要做负控制

"复检脚本自己也会说谎"（第21轮起的老教训）。这轮给复检加了两条外部负控制
（`D:` 临时区跑完即删，不进仓库）：

| 破坏 | 复检的反应 |
|---|---|
| N1 宿主 `npc_id` 闸**只留半条**（拆掉 `or npc_id != npc_id.strip()`） | `H5a H5c H5g H6a` 红 |
| N2 闸**挪到门控之后**（闸还在、逻辑没变） | `H5c` 红 |

还原后 `sha1` 与开工前一致（`True`）。两条都真红 ⇒ `H5`/`H6` 不是恒真。

---

## 8. 回归

### 8.1 G2 全量（机器统计列，不靠 grep）

```
套件行数 = 158      比对分布 = {'IDENTICAL': 158}
PASS 合计 = 7254    FAIL 合计 = 0
非零 exit = []      非 IDENTICAL = []
尾行：合计：PASS=7254 FAIL=0  套件=158
```

上轮 7229/0/157 ⇒ 本轮 +25 = `check159`（25 条），**其余 157 个套件一个数都没动**。

★ 记忆三层改完**又补跑一遍**（`check95 A2` 是硬闸）：第二次同样
`PASS=7254 FAIL=0 / 158 套件全 IDENTICAL`。

★ 统计用"列形状"认行（`parts[1..3]` 都是数字且 `parts[4]` 是比对词），
第一版按套件名前缀过滤漏了 30 行（`persona_chat` / `s8_stream` / `scene_p0` 这类不以
`check` 开头）—— 差点把 158 读成 128。这与"desc 正文里带 DIFF 字样导致 `grep -c` 误报"
是同一个坑的两面：**不许用文本搜索代替列解析**。

---

## 9. 遗留（下一轮的入口）

1. **`H5g` 的"两半"判据只看三个函数里的 `if`** —— 目前覆盖到七处（宿主 2 / 机制层 4 / 欠账 1），
   但它验的是"同一个 `if` 里既有 `not x` 又有 strip 比较"。若哪天有人把它拆成两个连续的
   `if`（语义等价、写法不同），会**假红**。属**判据过窄**，不是产品问题，等真发生再改。
2. **`ErrandBoard.assign` 的 `what` 归一与 `from_dict` 的归一现在有两份**（两处 `elif not what.strip()`）。
   §5 的 `B7` 与 `H6b` 都按"恰好 2 处"记着 —— 以后真要合并成一个小函数，**必须同时改这两条**，
   否则改对了也会红。
3. 第156~157轮结转仍未做：三条 ack 的"用户不在场也照样发起"、地点别名只到作品级前缀、
   否定闸整句从严、`_item_enter_scene` 无内部调用者、`current_scene` 双语义、
   `max_sentences` 读了不用（有意不执行）。

---

## 10. 证据（都在本轮目录）

```
第159轮-空白名字不算人/
├── report159.md                  本文件
└── _tools/
    ├── probe159.py               改前/改后成对探针（6/6 · 6/6）
    ├── check159.py               回归锁（25/0）
    ├── mutate159.py              8 处破坏 + 字节级还原（8/8 · Z1 · Z2）
    └── recheck159_core.py        核心文件复检（36/0）
```

`SUITES` 已登记（排在 `check158` 之后）· `baseline.json` 已按 `--only check159 --update` 建基线
（PASS=25 / FAIL=0 / BASELINE）。
