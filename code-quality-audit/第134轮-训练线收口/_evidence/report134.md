# 第134轮报告 · 训练线收口（以及一条"登记了没人读"的新样本）

## §1 结论

| 项 | 结果 |
|---|---|
| 本套件 | `check134` **36 PASS / 0 FAIL** |
| 全量 G2 | **PASS=6387 / 133 套件 / FAIL=0 / 无 DIFF** |
| 判据自纠 | **1 处**（B5 第一版是恒真判据，见 §5） |
| 新发现的真缺口 | **1 处**：`patches["ralsei"]` 在链上零读取（见 §6，**本轮只登记、未改产品**） |
| 产品代码改动 | **零**（本轮只加回归锁） |
| 结案 | `Twinkly` 一条（理由钉在数据上，见 §7） |

一句话：**训练线的接线本身是通的**（58 条 patch / 57 条 relation / 44 条 evolution 全部逐字进 prompt），
但**没有一条判据守着它** —— 删掉 `main.py` 里那三行 `patch=…`，第113轮的 `check113` 会全绿。
本轮把这把锁补上；顺手撞出一个真缺口：主宠自己那张训练卡根本没被任何代码读过。

---

## §2 为什么单开一轮

`check113` 的 C2 段是这么验的：造一条**合成** patch 字符串，传进 `build_system_prompt`，
断言它出现在返回值里。这验的是"函数收参数就会拼"，**不验"上层有没有把参数传进来"**。

所以这段代码删掉，回归照样全绿：

```python
# main.py :: npc_system_prompt()
patch=npc_persona_mod.training_patch(npc_id),
relation=npc_persona_mod.relation_patch(npc_id),
evolution=npc_persona_mod.evolution_patch(npc_id))
```

这在本项目已经不是新坑了 —— 第45轮的 `follow_route` 零调用、第101轮的"登记了没人读"、
第113轮r 的 `bonds.familiarity` 不存在（`AttributeError` 被 `except` 吞成 0）、
第120轮的 `room.Backgrounds` 恒空，都是同一个形状：**数据在、函数在、中间那一跳没人验。**

本轮要做的就是把这一跳钉死：**A 数据面**（从磁盘数出来，跟 `_index.counts` 对账）、
**B 端到端**（真跑产品函数，一条一条核对）、**C 接线**（AST + 破坏性负控制）。

---

## §3 数据面（全部从磁盘数出来，不抄文档）

| 面 | 实测 | 自洽性 |
|---|---|---|
| registry 条目 | **96** | `_index.counts.total` = 96 ✔ |
| 档位 | main **78** / plain **18** | — |
| `persona` 字段三态 | 文件 **76** + 主宠外链 **1**（`ralsei` → `../ralsei_persona.md`）+ `None` **19** | `counts.persona` = **77** = 76 + 1（两种口径各自自洽，别混算） |
| `None` 那 19 个 | 18 个 plain + `knight` | `gaps` 恰为 `["knight"]`，`counts.gap` = 1，且其 `notes` 写着"沉默" |
| 训练卡 | **96 张**，与 registry 的 id **一一对应**（无多无少） | — |
| `patch` | **59 人**，全部 main 档、全部非空串 | — |
| `relation` | **58 人** | — |
| `evolution` | **44 人** | — |
| `_seek` | **72 人**有权重 / **24** 条未解 | 只记录分母，不判好坏 |

`patches` 的**真源是 `_training/_index.json` 的 `patches` 映射**，
不是卡片文件里的 `patches` 字段（那个字段是空的）。我一开始数成 0 就是看错了地方。

---

## §4 端到端：三类卡真的逐字进了 prompt

真跑 `npc_persona.build_system_prompt(...)`，逐个角色核对 `txt.strip() in prompt`：

```
[PASS] B0  三类卡覆盖数：patch 59 / relation 58 / evolution 44（分母非空）
[PASS] B0b 进链分母：patch 58/59、relation 57/58、evolution 44/44 进链（差的都属主宠外链）
[PASS] B1  进链的 58 条 patch 全部逐字进 prompt        58/58 缺=[]
[PASS] B2  进链的 57 条 relation 全部逐字进 prompt     缺 0 条
[PASS] B3  进链的 44 条 evolution 全部逐字进 prompt    缺 0 条
[PASS] B4  无 patch 的 18 个角色：prompt 里没有训练纠正块（负控制，分母非空）  漏进 0 个
[PASS] B5  无 relation 的 19 个角色：prompt 里没有关系块（同上，分母非空）    漏进 0 个
```

B4/B5 是**成对负控制**：没有卡的角色，连块标题都不许出现，否则就是凭空造设定。
分母打印出来（18 / 19），并且断言 `bool(_NO_PATCH)` —— 否则"空集里没有泄漏"恒真。

---

## §5 判据自纠：B5 第一版是恒真判据

第一版这么写的：

```python
_other_leak = [nid for nid in PERSONAS
               if nid not in REL and u'【你和其他人的关系' in NP.build_system_prompt(...)]
```

`REL` 是 `{i: NP.relation_patch(i) for i in BY_ID}` —— **全 96 个 id 的字典**。
所以 `nid not in REL` **永远是 False** ⇒ `_other_leak` 恒空 ⇒ 这条判据无论产品怎么坏都绿。

改成 `REL_IN`（有卡的那 57 个）之后，分母才真的是 19 个"没卡的人"。

★ 值得单独说一句：`F1`（AST 查 `check(..., True)`）**抓不到**这一类。
它只认"字面量恒真"，而这条是**表达式恒假**。两者是同一种病：**看着在守，其实没守。**
能抓到它的只有两个习惯 —— ① 写完把分母打印出来看一眼（这条现在每条负控制都打）；
② 自己问一句"这个集合凭什么可能非空"。

---

## §6 ★★ 新发现：`patches["ralsei"]` 零读取（只登记，本轮不改）

### §6.1 事实

96 张卡里有 `ralsei` 这张（`cards/ralsei.json`，`persona_rel` 指向 **`ralsei_persona.md`**，4494 字），
`_index.patches` 里他有一句 **160 字**的纠正：

> 一次最多两三句，短一点，像随口说出来的。 只认得原作里真有的名字：Kris（克里斯）、Susie（苏西）、
> Lancer、Ralsei 自己、Toriel、Asgore、Asriel、Noelle、Berdly。 不要自己造人名
> （例如「凯斯恩」这种把两个名字拼起来的说法），拿不准名字的时候就称「你」「他」「她」，不要编。

`relation` 里他还有 84 字（`evolution` 为 0）。

### §6.2 但它一次都没被读过 —— 三段证据

1. `training_patch()` 全仓**只有一个调用点**：`main.py :: npc_system_prompt()`。
2. `npc_system_prompt()` 先取 `persona = self.npc_persona_of(npc_id)`，空了就 `return ''`；
   而 `self.npc_personas = load_personas(root)` 读的是 `assets/npc/_personas.json` ——
   那是从游戏 `chars` 抽的 **76 份 NPC 人设**，**不含主宠**（主宠真源是 `assets/ralsei_persona.md`）。
3. 就算有人硬传 `npc_id='ralsei'`，`chat_with_ai()` 第一件事就是
   `_npc_id = speaker if (… and speaker != 'ralsei') else None` ⇒ `'ralsei'` 直接走老路径，
   `npc_system_prompt()` 永不服务他。

⇒ **这条纠正目前对 Ralsei 本人零生效。**

### §6.3 但这不是"数据冗余"（先排除掉这个可能，再报问题）

查过 `ralsei_persona.md` 全文：`造人名` / `凯斯恩` / `拿不准` 三个词**一次都没出现**，
`两三句` 也没有。所以 patch 不是 persona 的副本，它是**独立的一条约束**，
尤其"不要自己造人名"这条在人设里完全没有对应物。

### §6.4 为什么不本轮就改

因为改它要动**主宠的 system**，而主宠 system 是这盘棋里最敏感的部件：

- 第113轮的口径是"只发 persona，**一个字节都不变**"（前缀缓存 + 人味都挂在这句话上）；
- 第128轮（结巴节流阀）、第131轮（真机 7 题基线）、第132轮（元话语闸）、
  第133轮（事件链闸）的**全部基线**都建立在当前这段 system 上；
- 插一条纠正进去，`persona_chat` / `s8_stream` / `s7_event_speech` 三条人味锁必然要 `--update`，
  而且会改变真机输出 —— 那是**另一轮**的事，需要 A/B 实测（现在改了也只是"我觉得更好"）。

按本项目口径「这一阶段 ok 才进下一阶段」，本轮是**收口**，不是扩功能。所以：

- 产品**一行没改**；
- 但用 **B0b / B1b / B1c / B1c2** 四条判据把这个状态**显式钉住**：
  - `B1b` 证明**卡本身没问题**（拿主宠人设去调 `build_system_prompt`，patch 逐字进 prompt，5333 字）；
  - `B1c` 证明**结构成因还在**（`chat_with_ai` 里确有"speaker == ralsei ⇒ 不走 NPC 路径"那一步）；
  - `B1c2` 是**破坏性负控制**（把文件里 17 处 `'ralsei'` 全替掉 ⇒ `B1c` 必须报红）；
  - `B0b` 把"差的那一条就是 `ralsei`"写成集合等式，不是写死数字。

⇒ **谁哪天把它接上了，`B1c` 会红**，逼人回来复审这几条，而不是悄悄多读一条卡。

### §6.5 下一轮如果要做，两条路线（代价都写清楚）

| 路线 | 做法 | 代价 |
|---|---|---|
| A 接进主宠 system | 在 `_build_ai_context` / system 装配处追加 `training_patch('ralsei')` | 动前缀（但内容是常量，缓存仍命中）；三条人味锁要 `--update`；需真机 A/B（n=10/格 起） |
| B 不接，改数据 | 把这条纠正的**有效部分**人工并进 `ralsei_persona.md`（像第130轮那样逐句过） | 人设体积涨（有体积闸）；仍是改人设，同样要真机复测；且"训练产物回灌人设"会让两条真源打架 |

我倾向 **A**（训练产物的消费方就该是 system 装配处，不该回灌人设真源），
但这需要一轮专门的 A/B，不在本轮范围。

---

## §7 `Twinkly` 结案（把理由钉在数据上，免得下轮再翻案）

`_seek.unresolved_names` 剩 **24** 条，其中 `Twinkly` 只有 1 处提到（`ot_asgore` 说的）。
它看起来"可解"（有 `ot_asriel_twinkly` 这张卡），但：

- `E2`：目标卡的登记名是 **「Asriel Dreemurr 与 Twinkly」** —— 两个人**合一**的一张卡。
  把 `Twinkly` 解过去，等于把 Asriel 和 Twinkly 当成同一个人，这比"不知道"更糟。
- `E3`：而且这张卡在 `seek` 里**已经有 5 条出边** —— 它不是"没人用的孤儿卡"，
  接它不是因为"能补一条数据"，只会污染一个已有语义。

⇒ **不接是对的。** 结案，不进下一轮的待办。

---

## §8 回归与落盘

### §8.1 全量 G2

```
合计：PASS=6387 FAIL=0  套件=133
```

第133轮是 `6351 / 132`，本轮 `+36` 条判据、`+1` 套件，**全 IDENTICAL，无 DIFF**。

★ 登记进 `SUITES` 后必须 `--only check134 --update` —— 漏了会被 `check81 G5` 抓
（那条是**真守卫**：专抓"入列 SUITES 却漏 update ⇒ 永远 BASELINE"，第133轮就红过一次）。

### §8.2 复检

- `recheck134_core.py`：语法（`ast.parse`，**不** `py_compile`，避免产 `.pyc`）/ 结构 /
  编码（BOM / U+FFFD / 行尾）/ 恒真判据（含**正控制**：塞一条假 `check(..., True)` 必须被抓到）/
  逐令牌回验 / 工作区只动该动的路径。
- `recheck134_mem.py`：体积（UTF-16 码元，`check95 A2` 硬闸 ≤10000）/ 编码 / 新增在位 /
  **删后有据**（每个删掉的令牌"速查本 or 详版"并集里必须还在）/ 日志 append-only / 守恒。

### §8.3 证据文件

- `_evidence/train134.json` —— 本套件落盘的那组计数（96 / 78 / 18 / 76 / 19 / 96 / 59 / 58 / 44 / 72 / 24 / 58）
- `_evidence/report134.md` —— 本文

### §8.4 推送

按第113轮起的口径：推 `HEAD:local-134`，**不 merge、不 force**。
（远端 `main` 停在 `c88292b`（第118轮交接单），与本地 `main` 早已分叉，`HEAD:main` 必被 `non-fast-forward` 拒。）
