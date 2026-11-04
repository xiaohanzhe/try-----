# 第160轮：判据别绑写法，也别绑时相

> **入口**：`report159.md §9` 第 1 条 —— `recheck159_core H5g` 的"两半必须挤在同一个 `if` 里"。
> **用户口径**（逐字贯穿）：「**按照人类的逻辑来就好**」。

---

## 1. 结论

这一轮**没改产品一行代码**（`ralsei_pet/` 零改动），改的是**判据**。

`recheck159_core.py` 里有三条判据把"守卫该长什么样 / 该处于什么状态"写死了。实测三条**全会假红**：

| 判据 | 绑的是什么 | 假红症状 |
|---|---|---|
| `H5g` | `if` 的**形状**（两半必须挤在同一个 `if` 里） | 语义等价的"拆成两个连续 `if`"被判成"缺一半" |
| `H6a` | **多行文本片段**（含缩进与续行） | 同一改写一拆段就数出 0 处 |
| `H1a` | **时相**（要求两个产品文件"恰好"处于已修改状态） | 一提交就 `产品改动=[]` ⇒ 必假红 |

判据过窄 = 误报，比不写还危险：它会训练人「**改判据**」而不是「改代码」（第107轮教训同族）。

| 项 | 数值 |
|---|---|
| 产品改动 | **0 行**（`ralsei_pet/` 一个文件都没动） |
| 判据改动 | `recheck159_core.py` 三条口径 · `check159.py` 补 `B8`（25 → 26 条） |
| 新增判据 | `check160` **21/0**（A 9 / B 7 / C 5）—— 把复检里那三个判定函数**当被测物** |
| 负控制 | `mutate160` **5/5**（破坏判据本身）+ `mutate159` **9/9**（含新增的无害变异 `M9`） |
| 复检 | `recheck160_core` **23/0** |

---

## 2. 改前实测（`probe160 --before`）

把宿主 `npc_id` 闸改成**语义完全等价**的两段式：

```python
if not isinstance(npc_id, str) or not npc_id:     # 先挡空/非 str
    return None
if npc_id != npc_id.strip():                      # 再挡首尾空白
    return None
```

同一个注入，跑两个套件：

```
check159          rc=0 红：（无）
recheck159_core   rc=1 红：H1a H5g H6a
还原后 sha1 一致：True
```

其中 `H5g` / `H6a` 是**这一注入引起的假红**：

```
[FAIL] H5g 判据**两半都在**…    缺一半=['npc_id']
[FAIL] H6a `main.py` 里三处新判据各按**预期次数**出现
         不符=[('if not isinstance(npc_id, str) or not npc_id \\', 0, 1)]
```

`H1a` 与注入**无关**，是纯粹的时相问题 —— 提交之后、什么都不改，直接跑复检：

```
[FAIL] H1a 产品侧被改的**只有** `src/main.py` 与 `modules/npc_errand.py`…    产品改动=[]
recheck159_core：FAIL 1 / PASS 35
```

⇒ 上一轮收口时它 36/0，是因为那时两个文件刚好处于"已修改"状态。**判据读到了一个时相量**
（工作区当时长什么样），而不是被守的性质。

---

## 3. 三条判据各怎么了

### 3.1 `H5g`：把"两半"绑在 `if` 的形状上

原实现只认这一种写法：

```python
if isinstance(n, ast.If):
    if _vals and _strip_cmp_lines(ast.Module(body=[n], ...), _name):
        _hit = True          # ← 两半必须在同一个 If 里
```

可"挡空串"和"挡首尾空白"是**两个性质**，写在一个 `if` 里只是**一种**实现。拆成两个连续 `if`
语义完全等价（第一个 return 之后才轮到第二个），却判"缺一半"。

**改法**：分成两个找法，各自在同函数内出现即可 ——

```python
def _strip_cmp(fn, name):    # 找「name 与 name.strip() 相比」的 ast.Compare
def _not_guard(fn, name):    # 找「not name 落在 if 的 test 里」的 ast.If
...
if not _strip_cmp(_fn, _name) or not _not_guard(_fn, _name):
    _bad_half.append(_name)
```

### 3.2 `H6a`：按"多行文本片段"计数

原实现数的是这一段**文本**：

```python
u"if not isinstance(npc_id, str) or not npc_id \\\r\n"
u"                or npc_id != npc_id.strip():"
```

拆成两段，这段文本就不存在了 ⇒ 数出 0 处。**它数的是排版，不是判据。**

**改法**：数 `ast.Compare` 节点（`_strip_cmp` 的长度），并保留精确次数：

```python
_n_main_id   = len(_strip_cmp(_ASSIGN, 'npc_id')) + len(_strip_cmp(_GIVEN_UP, 'npc_id'))
_n_main_dest = len(_strip_cmp(_ASSIGN, 'dest_scene'))
# 期望：2 / 1
```

`H6b` 同理：机制层 id、地点各 2 处，`what` 归一 2 处（新增 `_what_norm` 数"`not what.strip()` +
`what = ''`"这种 `if`）。

### 3.3 `H1a`：绑了时相

原实现：

```python
_prod == ['ralsei_pet/modules/npc_errand.py', 'ralsei_pet/src/main.py']
```

这要求"**恰好**这两个文件处于已修改状态"。提交之后工作区干净 ⇒ `_prod == []` ⇒ 必红。
**它读的是"现在几点"，不是"改了哪些东西"。**

**改法**：改成子集判（问"有没有第三个文件"）：

```python
_ALLOWED = ('ralsei_pet/modules/npc_errand.py', 'ralsei_pet/src/main.py')
_extra = [p for p in _prod if p not in _ALLOWED]
check(u'H1a 产品侧**没有第三个文件**被改（只可能是这两个；已提交时为空也算过）',
      not _extra, ...)
```

真守卫没丢：多出**第三个**产品文件照样红（`check160 B6` 用行为模拟把这条钉住）。

---

## 4. `check160`：把判定函数当被测物（21/0）

这轮最需要防的是"**我改判据，改成了另一种写法绑定**"。所以 `check160` 不测产品，
它把 `recheck159_core.py` 里那三个函数**取出来当被测物**（`ast.get_source_segment` + `exec`），
喂 **8 个独立构造的样本**（不经产品源码）：

| # | 样本 | 期望 |
|---|---|---|
| A1 | 两半在**同一个 `if`** | strip=1 not=1 |
| A2 | **两个连续 `if`**（语义等价） | strip=1 not=1 |
| A3 | 只有 `not` 半 | strip=0 |
| A4 | `if not npc_id.strip():`（**不是比较**） | strip=0（它挡不住 `' ralsei '`，反而全拒） |
| A5 | 只有 strip 半 | not=0 |
| A6 | `what` 归一在位 | 1 处 |
| A7 | `what` 归一被换成 `elif False` | 0 处（A6 的负控制） |
| A8 | `strip()` 只出现在**语句**里 | 两半都不算（防"提到就算"的恒真） |

`B` 段专守时相：`H1a` 不许拿列表做相等比较、必须问"多出来的文件"，外加"已提交 / 两个文件 /
多第三个文件"三种时相的**行为模拟**（正/负成对），最后从**真代码**里把 `_ALLOWED` 读出来对一遍
—— 防"模拟绿、真判据已经恒真"。

---

## 5. 负控制（`mutate160` 5/5 · `mutate159` 9/9）

这轮的负控制换靶子：**破坏判据本身**。

| # | 破坏 | 实得红点 |
|---|---|---|
| M1 | `_strip_cmp` 退化成"只要有 `.strip()` 调用就算" | `A4 A8` |
| M2 | `_not_guard` 退化成"只要提到这个名字就算" | `A5 A8` |
| M3 | `_what_norm` 的 test 判据写成 `has_test = True` | `A6 A7` |
| M4 | 白名单 `_ALLOWED` 清空 | `B7` |
| M5 | `H1a` 退回相等比较 | `B2 B3` |

`M3` 实得比预期多一条（`A6`）—— 不是判据坏：退化成"见到 `what` 赋值就算"之后，
样本里**两个分支**都被算进来，A6（在位样本数到 2）与 A7（死分支也被认）一起红，
是**同一条判据的两个观测面**。

### 5.1 `mutate159` 新增 `M9`：**无害变异**

负控制历来只问"破坏会不会红"。这一轮补上另一半：**没破坏时会不会假红**。

`M9` 就是把宿主闸拆成两个连续 `if`（上面 §2 那段），`expect` 写成**空 tuple**，
框架的断言随之反过来：

```python
if not expect:
    ok = (rc == 0) and not reds        # 一条都不许红
```

实得 `M9 ⇒ 红：无`（`[PASS]`）。它同时把 `check159 B8` 的两个方向都钉住：
**破坏时红**（`M1`/`M2`/`M3`/`M7`/`M8` 都让 `B8` 红）、**等价改写时不红**（`M9`）。

---

## 6. 复检（`recheck160_core` 23/0）与它自己踩的一脚

复检换了口径（产品零改动）：

| 段 | 守什么 |
|---|---|
| H1 | `ralsei_pet/` **一个文件都没改**（本轮的边界）· 未跟踪项全在 `code-quality-audit/` |
| H2 | 判据脚本**规模没缩水**：`check159` 26 · `recheck159_core` 静态 30 · `mutate159` 9 · `mutate160` 5 · `check160` 21 |
| H3/H4 | 七个脚本语法 ok、全 LF、无 BOM、无 U+FFFD |
| H5 | 基线有 `check160` · `SUITES` 有 `check160` · 两条 desc 都改了 |
| H6 | `check160` 判据名字面量、不用 `ok()` · `mutate160` 每处都有期望 |
| H7 | 四件齐 · 没碰 `.pyc` · 不依赖外部盘 |

★ **它自己先踩了一脚"绑写法"**：`_n_mutations` 第一版只认 `len(elts) == 6`，而 `mutate160` 的条目是
**5 元组**（目标文件固定，不需要"target"那一位）⇒ 数出 0 处 ⇒ `H2d`/`H6c` 假红。
改成 `len(x.elts) in (5, 6)` 才对。**同一轮里，同一个病，犯在"检查别人有没有犯这个病"的脚本上。**

★ 另一条：`H2b` 一开始写"`recheck159_core` 仍有 36 条" —— 而那是**运行期**条数（有几条在 `for` 里
按文件展开），**静态**只有 30。两个数都不能当对方的证明，改成静态 `>= 30` 并在 desc 里写明。

---

## 7. 回归

### 7.1 G2 全量（机器统计列）

```
套件行数 = 159      比对分布 = {'IDENTICAL': 159}
PASS 合计 = 7276    FAIL 合计 = 0
非零 exit = []      非 IDENTICAL = []
尾行：合计：PASS=7276 FAIL=0  套件=159
```

上轮 7254/0/158 ⇒ **+22** = `check159` 多一条（`B8`，25→26）+ `check160` 新增 21 条。
其余 157 个套件一个数都没动。

★ 记忆三层改完**又补跑一遍**（`check95 A2` 是硬闸）：第二次同样
`PASS=7276 FAIL=0 / 159 套件全 IDENTICAL`。

★ 统计仍按"列形状"认行（`parts[1..4]`），不用文本搜索 —— desc 正文里也带 `DIFF`/`IDENTICAL` 字样。

---

## 8. 遗留

1. **`H5g`/`B8` 现在只问"同函数内两半都在"** —— 若有人把 `not x` 判据挪到**另一个函数**（比如
   抽个 `_valid_id()` 出来），仍然会红。那时该改的是"跟着调用图看"，代价大于收益 ⇒ **等真发生再改**。
2. `check160` 用 `ast.get_source_segment` + `exec` 取出判定函数 ⇒ 若 `recheck159_core` 把那三个函数
   **改名/搬进类里**，`A0` 会红（提示同步）。这是**有意**的耦合，别为了"耐用"改成模糊匹配。
3. 第156~157轮结转仍未做：三条 ack 的"用户不在场也照样发起"、地点别名只到作品级前缀、
   否定闸整句从严、`_item_enter_scene` 无内部调用者、`current_scene` 双语义、
   `max_sentences` 读了不用（有意不执行）。

---

## 9. 证据（都在本轮目录）

```
第160轮-判据别绑写法/
├── report160.md                  本文件
└── _tools/
    ├── probe160.py               同一注入、改判据前后各跑一次（--before 红 → 改后全绿）
    ├── check160.py               把三个判定函数当被测物（21/0）
    ├── mutate160.py              破坏判据本身（5/5 · Z1 · Z2）
    └── recheck160_core.py        本轮复检（23/0）
```

被改的上一轮工具：`第159轮-空白名字不算人/_tools/` 下的
`recheck159_core.py`（三条口径）、`check159.py`（补 `B8`）、`mutate159.py`（`M9` + 空期望语义）。
