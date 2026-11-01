# 第137轮报告 · `patches["ralsei"]` 真的进主宠 system

## §1 结论

| 项 | 结果 |
|---|---|
| 修的病 | `patches["ralsei"]`（160 字）**零读取** —— 训练卡为全部 96 位角色都产出了，只有主宠那条从没进过 system（第134轮登记） |
| 补的是什么 | ②「只认原作里真有的名字」③「不要自己造人名（凯斯恩）」—— 人设正文里**一个字都没有** |
| 接法 | 新增模块级 `_with_ralsei_patch(system)`，对话与预热**各一处** |
| 本套件 | `check137` **29 PASS / 0 FAIL** |
| 判据自纠 | **3 处**（§5：桩上没有新方法 / 打桩打到第二份模块实例 / 纯文本扫被自己的引用误伤） |
| 收口复检 | `recheck137_core` **14/0**（产品侧）· `recheck137_mem` **20/0**（记忆侧） |
| 全量 G2 | **PASS=6479 / FAIL=0 / 136 套件 / 全 IDENTICAL**（§7） |

---

## §2 病是什么

`main.chat_with_ai` 的老路径（`speaker` 为 `None`/`'ralsei'`）：

```python
else:
    system = self._build_persona_prompt()      # 只读 assets/ralsei_persona.md
```

而 NPC 路径早就把训练纠正拼进去了（`npc_persona.build_system_prompt` 的第 ③ 段
`【这个角色容易犯的毛病（照着改）】`）。两条链共用同一份训练数据，只有主宠这条**不读**。

第134轮做过排除：这**不是**"数据冗余"——`ralsei_persona.md` 里
`造人名` / `凯斯恩` / `拿不准` / `两三句` 一次都不出现。所以它是真缺口。

---

## §3 这条 patch 补了什么（逐条对人设）

`assets/npc/_training/_index.json` → `patches["ralsei"]`：

```
一次最多两三句，短一点，像随口说出来的。 只认得原作里真有的名字：Kris（克里斯）、
Susie（苏西）、Lancer、Ralsei 自己、Toriel、Asgore、Asriel、Noelle、Berdly。
不要自己造人名（例如「凯斯恩」这种把两个名字拼起来的说法），拿不准名字的时候就称
「你」「他」「她」，不要编。
```

| 要求 | 人设里有吗 | 处理 |
|---|---|---|
| ① 一次最多两三句 | **有**（「我怎么说」写着"一次只说 1~3 句"） | 冗余，无害，保留 |
| ② 只认原作里真有的名字（8 人白名单） | **没有** | 本轮补上 |
| ③ 不要自己造人名（凯斯恩） | **没有** | 本轮补上 |

② ③ 是**实测观测到**的出戏（模型把两个名字拼成一个新名字），不是"我觉得该加一句"。
`npc_persona.training_patch` 的 docstring 里写死了这条纪律：
「没有实测依据的一句话会**改变**角色的说话方式（第75轮的教训），只有训练里真的复现过的毛病，才配写进来。」

→ 判据 `B` 段专门断"② ③ 确实不在人设里"。**如果哪天有人把它们并进了人设，B 会报红**，
提醒去把 patch 清掉——不然同一句话就有两处，改一处忘一处。

---

## §4 接法：为什么是模块级函数 + 两个调用点

### 4.1 不并进 `_build_persona_prompt()`

那个方法的契约是"读到的就是 persona 文件**全文**"，
`persona_chat B8` 逐字守着（`stub._build_persona_prompt().strip() == PERSONA.strip()`）。
而这条 patch 是**训练产出的增量**、来源不同（`_training/_index.json`）。混进去以后
就说不清"这句到底是有证据的纠正，还是原始设定"——那正是
`npc_persona.training_patch` 与 `relation_patch` 故意分家的同一条理由。

### 4.2 为什么是模块级函数，不是 `RalseiPet` 的方法

第一版写成了方法 `self._append_training_patch(system)`。`s7_event_speech F1` **当场崩**：

```
File "<ROOT>/ralsei_pet/src/main.py", line <LN>, in chat_with_ai
    system = self._append_training_patch(system)
AttributeError: 'types.SimpleNamespace' object has no attribute '_append_training_patch'
```

原因：回归套件在 `SimpleNamespace` 桩上直接调 `chat_with_ai`，桩只**手工绑了少数方法**
（`_build_persona_prompt` / `_clean_ai_reply` / …）。这与 `_build_persona_prompt`
docstring 里那条「只依赖类属性与局部量，以便在测试桩上直接调用」是同一条约束。
⇒ 改成模块级函数，桩上也能跑。

### 4.3 为什么预热也必须调

`_prewarm_ai_cache` 只发 persona、`max_tokens=1`，目的是**把 KV 前缀喂进缓存**。
如果对话发 `persona+patch` 而预热只发 `persona`，前缀**仍然命中**（persona 是前缀），
但每次都要多 prefill 那 160 字 —— 预热等于白做一半。
⇒ 两处必须逐字同源，判据 `D2`/`D3` 钉死"各一处、都在 `_build_persona_prompt()` 之后"。

### 4.4 尾块标题用第一人称

NPC 那边是`【这个角色容易犯的毛病（照着改）】`。Ralsei 的人设通篇第一人称，
混一句第三人称标题会让模型把"这个角色"当成别人来演（第75轮：一句措辞就能改掉说话方式）。
⇒ 用 `【我容易犯的毛病（照着改）】`（`PATCH_HEADER_RALSEI`），判据 `C3` 钉住。

---

## §5 判据自己翻的车（2 处）

### 5.1 桩上没有新方法（产品侧的自纠）

见 §4.2。这是**产品**写法错了，判据（s7 的既有锁）抓到的。

### 5.2 打桩打到了**第二份模块实例**（判据侧的自纠）

`check137 C6`（负控制：让 `training_patch` 返回空 ⇒ 尾块必须消失）第一版报红：
`len 4671 → 4671`，纹丝不动。

根因：`main.py` 里是 `from modules import npc_persona as npc_persona_mod`（`modules/` 是个包），
而我在判据里写 `import npc_persona`（把 `modules` 塞进了 `sys.path`）——
Python 于是**又造了一个模块实例**，连 `_PATCH_CACHE` 都是两份。
打桩打的是那份没人用的，产品调的是另一份。

⇒ 改 `NP = M.npc_persona_mod`，并加一条判据 `C8`：
「打桩打的正是产品用的那个模块实例」——以后谁再写成 `import npc_persona`，C8 先报红。

★ 通用形状：**在桩上打补丁之前，先证明你拿到的是产品那一个对象**。
同族的坑：`mutate85`「夹具不保真 ⇒ 报假问题」、第129轮「判据互证≠独立验证」。

### 5.3 复检抓出两处**过时的假断言**（收口前，我自己写的文案）

改完代码后跑 `recheck137_core.py`，`E1` 报红：`一个字节都不变` 还在 `main.py` 里。
三处命中，逐条看：

| 位置 | 是什么 | 处理 |
|---|---|---|
| `chat_with_ai` docstring（14098） | 「`None`/`'ralsei'` ⇒ 老路径，**一个字节都不变**」—— 现在多了 160 字，**假了** | 改成「persona 全文 + 训练纠正尾块…其余照旧」 |
| `_prewarm_ai_cache` docstring（14770） | 「只发 persona，一个字节都不变」—— 现在发 persona+patch，**假了** | 同上 |
| lean 分支注释（14234） | 「（本次改动之前这里写的是"一个字节都不变"）」—— 这是**引用**，不是断言 | 保留 |

★★★ 顺带记一条：**这条判据第一版就是纯文本扫**（`u'一个字节都不变' not in src`），
于是被自己那行引用**当场误伤**。这已是"禁某短语出现"类判据禁纯文本扫的**第 7 次**发作。
⇒ 改成**按行判**：只有带「之前这里写的」标记的**引用行**才允许出现该短语，
并补一条正控制（把旧断言原文喂同一个谓词，必须判坏）。

这条的本体价值：**改完代码，同一件事的"说法"也得跟着改** ——
两处 docstring 在说谎，而它们正是下一个人读的"事实来源"。

---

## §6 本套件守什么（`check137`，29 项）

| 段 | 内容 |
|---|---|
| A 数据面 | patch 在 / 非空 / 三条要求在 / 带实测例「凯斯恩」 |
| B 人设面 | 「造人名」「凯斯恩」「名字白名单」三样**都不在** persona（否则这轮是自欺）；①"两三句"故意不断（本就重复） |
| C 行为面 | 以 persona 原文开头 / patch 逐字在 / 排在正文之后 / 第一人称标题 / 空串与 None 不抛 / **破坏性负控制**（`training_patch` 返回空 ⇒ 尾块整个消失）/ 恢复自证 / C8 打桩对象正确 |
| D 接线（AST） | `chat_with_ai` 与 `_prewarm_ai_cache` **各 1 处**、都排在 `_build_persona_prompt()` 之后、`_build_persona_prompt` 自己不碰 `training_patch` |
| E 契约不破 | 桩上真跑：`_build_persona_prompt()` 仍逐字等于 persona 文件，且不含 patch |
| F 自检 | 无恒真判据 / 无 BOM / 零外部盘 / 判据不自己拼尾块（单一真源） |

---

## §7 全量 G2

```
cd code-quality-audit/regress && python run_all.py
合计：PASS=6479 FAIL=0  套件=136
```

**全部 136 套 `IDENTICAL`**（基准逐条比对）。两条最相关的既有锁单独复核：

| 套件 | 结果 | 说明 |
|---|---|---|
| `persona_chat` | 156 / 0 | `B8` 逐字守着 `_build_persona_prompt()`，本轮没动它 ⇒ 一字不变 |
| `s7_event_speech` | 139 / 0 | 第一版写成方法时它当场崩（§4.2），改模块级后全绿 |

### 7.1 四个 DIFF 逐条归因（**无一条盲更新**）

`run_all.py` 第一次跑出 4 条 DIFF，每条都先查清"变的是什么"再 `--update`：

| 套件·判据 | 变化 | 归因 |
|---|---|---|
| `check134 B1c2` | `'ralsei'` 字面量 **17 → 19** | 我新加了两个调用点（对话 + 预热），各一个 `'ralsei'` —— 纯**计数回显**，不是行为变化 |
| `check129 D5` | `main` 体积 **744500 → 746780** | 新增函数 + 两处调用 + 注释 ≈ 2.3 KB，体积回显 |
| `check132 D3/D4` | 行号 **15130 → 15183** | 行号回显（模块级函数插在 `prewarm_order()` 之后，把后面整体推了 ~53 行） |
| `check135 F1` | 行号 **12395 → 12438** | 同上 |

★★ `check134 B1c2` 是**它的设计目的达成了**：第134轮写这条判据时就写明"谁哪天接上了会红，逼人回来复审"。
⇒ 我按它的要求回来复审，并把缺口的"下半句"写进 `check134.py` 的注释：

> `training_patch('ralsei')` **零读取**这句话**已经过时**，别照着它再做一次"补接线"。

（判据本身一条没删 —— B0b/B1b/B1c 仍在守"主宠不走 NPC 那条 `build_system_prompt` 链"这个**至今仍然成立**的事实。）

### 7.2 反回滚

`git status --porcelain` = **4 改 + 1 新增目录**，`git diff HEAD --numstat` 逐条：

| 文件 | 增 / 删 | 为什么改 |
|---|---|---|
| `ralsei_pet/src/main.py` | +56 / −3 | 新增 `_with_ralsei_patch` + 两个调用点 + 注释改正 |
| `code-quality-audit/regress/run_all.py` | +35 / −0 | `SUITES` 加 `check137`、`check136`/`round6_verify` 的 desc 同步 |
| `code-quality-audit/regress/baseline.json` | +10 / −4 | 四套件的基线行替换 |
| `.../第134轮-训练线收口/_tools/check134.py` | +8 / −0 | 只加注释（缺口的"下半句"），**判据一条没删** |
| `第137轮-主宠训练补丁/` | 新目录 | `check137.py` + 本报告 |

`main.py` 行数 **17280 → 17333**（+53 = 56−3），**没有缩水**；
`check134.py` 是纯增 8 行 ⇒ 符合"登记过时断言"而不是"删守卫"。

★ 产品行为面没有"只靠 git 不报错"的静默回滚空间：`persona_chat B8` 与
`s7_event_speech` 两条既有锁都在动 `main.py`，任何一个函数被换回旧版都会当场报红。

### 7.3 第二次 DIFF：收口前改文案又推了一次行号

§5.3 修掉两处 docstring 假断言（`main.py` 14098 附近 +4 行、14770 附近 +1 行），
于是同一批回显判据**又红了一次**：

| 判据 | 第一次 | 第二次 | 是什么 |
|---|---|---|---|
| `check129 D5` | 744500 → 746780 | → **747019** | 体积回显（文案加长 239 B） |
| `check132 D3/D4` | 15130 → 15183 | → **15187** | 行号回显（+4 行） |
| `check137 D1/D2/D3` | — | 14231→**14234** / 14802→**14806** | 行号回显（新套件自己的基线也跟着移） |

三条计数与判定**全是 PASS**，只有末尾那几个数字变。`--only check129 check132 check137 --update`
（合计 82/0）后重跑全量：**PASS=6479 / FAIL=0 / 136 套件 / 全 IDENTICAL**。

★★ **这条脆性在本轮之内咬了两次**（第132/135 轮各咬一次，本轮两咬）。
它不是"改判据的时机到了"，而是**下一个明确的活儿**：把"回显行号 / 体积 / 字面量计数"这三类
换成**结构性判据**（AST 定位 + 语义断言），否则每改一行注释都要人工归因四个 DIFF。

---

## §8 遗留

1. **patch ① 与人设重复**（"两三句" vs "1~3 句"）：冗余但无害，本轮不清。
   真要去重得先决定"以哪个为准"，且要重跑训练卡（`cards113.py --all` 会重抽
   `voice_markers`，第130轮记录过"重建冲掉 12 条手补"的坑）。
2. 第136轮遗留：第三条截断链（`_clean_ai_reply` 220 字）未统一；
   `check132`/`check135` 的**行号回显**脆性未清。
3. 第135轮遗留：第一句本身超 24 字仍会硬截。
