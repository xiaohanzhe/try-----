# 第113轮l · 地名英文 / 口语化 / 跨区域 / 人名英文

> 2026-10-26。承接第113轮k（NPC 听懂「咱吃饭去吧」并说得出「那要不去 XXX 家餐厅」）。
> 本文只记**本轮**改了什么、抓到什么真错误、判据怎么改的。k 轮的全文在 `Validation_113k.md`。

---

## 1. 用户口径（逐字）

汇报完第113轮全部成果后，用户回了三句：

> 「那就按你的想法继续吧，对了**名字用英文**，有些地方 room 的名称并不口语化，所以你需要把他们变的口语化一些，对了，**可以跨区域哦**」

> 「**人名也要改成英文**」

拆成四条硬口径：

| # | 口径 | 落地成什么 |
|---|---|---|
| 1 | 名字用英文 | 活动/去处标签整体英文：`Hometown · Diner`（原来是 `家乡 · diner（餐厅）`） |
| 2 | room 名要口语化 | `c asgore kitchen` ⇒ `Asgore's Kitchen`；`tundra inn 2f` ⇒ `Tundra Inn Second Floor`；`Tv World` ⇒ `TV World` |
| 3 | 可以跨区域 | `_activity_places` 从"只扫本章"改成"扫全库、同章排前面" |
| 4 | 人名也要英文 | 中文人名换英文（`托丽尔` ⇒ `Toriel`）；地名里的所有格 `Asgore's` / `Noelle's` |

★ 第 4 条不是"再翻译一遍"—— 是"地名里夹着的中文名要有确定英文对应"。没有对应的一律**不猜**（见 §4 K5b）。

---

## 2. 改了什么（产品）

### 2.1 `modules/npc_life.py`（1243 → **1378** 行）

新增（全部零依赖，只 import `re` / 标准库）：

| 名字 | 作用 |
|---|---|
| `has_cjk(text)` | 这段文本里有中日韩**文字**吗（★ 刻意不含标点，见 §3.1） |
| `speakable_en(text, proper=())` | id 末段 → 能说出口的英文地名：下划线转空格 · 楼层说人话 · 逐词 Title Case（虚词除外）· 人名 + 地点词 ⇒ 所有格 |
| `de_cjk_names(text, names_en)` | 地名里夹着的中文人名换英文（长名优先，避免留半截） |
| `label_key(text)` | 地名归一键（只留字母数字），判"两个标签是不是同一个地方" |
| `PLACE_CONTAINER_IDS = {'rooms'}` | **id 形态**的容器区（`ut.rooms.*` / `uty.rooms.*`） |
| `_ABBR_EN` / `_FLOOR_EN` / `_EN_MINOR` | 已知缩写（`tv`/`ut`/`uty`/`truelab`）· 楼层（`2f` ⇒ `Second Floor`）· 虚词（`of`/`the`/`in`…） |

改：

- `place_label()` 从"中文区名 + 英文 id + 中文括注"改成**全英文**；`detail` 只有在**不含中文**且**不是区名复读**时才用；中文类型名（`place_type_name`）退到**内部去重键**，不再进 prompt。
- `activity_hint()` 加 `cross=` 参数：混了别处候选就说「有的不在你这一带 —— 提的时候把"在哪儿"也说出来；还用你自己平常的说法，别照着念」；纯同章仍说「你们这儿真有的地方」。
- `strip_room_index()` 加"去行首纯数字"（`1 library` ⇒ `library`），房号/首字母两条原有规则不动。
- `ACTIVITY_SAY['play']` 从 `出去转转` 改成 `转一圈`（模板是「要去%s」，原先把"去"叠成"要去出去转转"）。

### 2.2 `src/main.py`（16797 → **16909** 行）

- `_activity_places(kind, chapter='')`：**跨区域**。扫全库、按 `(章, 区 id, 中文类型名)` 去重、返回前**同章优先**排序。
  - ★ 缓存只存**章无关**的那一份（`(kind,)` 键），同章优先在返回时再做 —— 否则第二个章会拿到第一个章的排序，且**不报错**。
- `_activity_label()`：区名取**区 id** 整形（`hometown` ⇒ `Hometown`），不取中文区名；容器区换成**作品缩写**（`ut.rooms.*` ⇒ `UT · Water Shop`）。
- 新增 `_place_proper()`（人名集合，从 `npc_registry.ids()` 现取）与 `_place_names_en()`（中文名 ⇒ 英文名，从 `name_cn`/`name`/id 末段取）。
- `_scene_place_label()` 剥"场景名自带区名前缀"改成**大小写不敏感**（英文名常是小写 id 配 Title Case 区名）。
- `_npc_life_blocks()` 活动段：算 `_cross`（前 4 条里有没有不在本章的）传给 `activity_hint`。

### 2.3 行为样例（真实输出）

NPC 在 `ch1.hometown.town_square`，用户说「咱吃饭去吧」：

```
【这会儿能张罗的事】要去吃点东西，能想到的地方：Hometown · Diner、Light World · Icee Pizza、My Castle Town · Castle Cafe、My Castle Town · Castle Restaurant。
（有的不在你这一带 —— 提的时候把"在哪儿"也说出来；还用你自己平常的说法，别照着念，别让人以为走两步就到。）
```

说「我有点累了」：

```
【这会儿能张罗的事】要去歇一会儿，能想到的地方：Cyber City · City Spamton House、Dark World · Couch、Green Room、Noelle's House。
```

★ `ch1` 的 rest / play 在**原作里本来就没有**对应房间（第113轮k 的遗留池里挂着这个疑问「没候选时要不要说一句"这附近没合适的地方"」）—— 跨区域后这个问题**自然消失**：候选从别处来，并用 `cross` 文案说清"不在你这一带"。

---

## 3. 抓到的八个真错误（都是人眼读出来的，判据当时是绿的）

按发现顺序，每条：症状 → 根因 → 修法。

| # | 症状 | 根因 | 修法 |
|---|---|---|---|
| 1 | `Rooms · Water Shop`（1251 间房全这样） | `ut.rooms.*` / `uty.rooms.*` 的 `rooms` 是我们的**房间容器**，不是地名；中文过滤（`全部房间`）管不到英文 id | `PLACE_CONTAINER_IDS` + 容器区改用**作品缩写** ⇒ `UT · Water Shop` / `UTY · Shop` |
| 2 | `要去出去转转` | `ACTIVITY_SAY['play'] = '出去转转'` 拼进「要去%s」 | 改 `转一圈` |
| 3 | `Garden · Way Home` 之外还有一条 `Garden`（丢了店名） | `name_raw` 为空 / 只存区名时 `core` 取到区名，剥前缀匹配不上 | `core` 为空或等于区名 ⇒ 用 **sid 末段**兜底 |
| 4 | 同上，修完 #3 仍只剩 `Garden` | `detail`（真名）**只是区名的复读**，被当"有细节" | `label_key(detail) == label_key(area)` ⇒ 视为无细节，退回 core |
| 5 | `Noelle's S House` | id 的 `noelle_s_house` 里 `_s_` 是**所有格分隔**，`_`→空格后 `s` 变独立词 | 单独词 `s` 并入前词：`words[-1] += "'s"` |
| 6 | `Noelle's's House` | 前词已按人名加过 `'s`，`s` 又加一次 | 前词已以 `'s` 结尾则跳过 |
| 7 | `Cyber Field · Cyber Field Arcade` | ① 剥区名前缀用 `startswith(area)`，英文大小写不一致；② core 来自 `room_word()`（**已把 `_` 转空格**），而 `area_id` 是下划线形态 ⇒ 两种写法都拼不上 | 大小写不敏感；区名前缀按 **`cyber_field` 与 `cyber field` 两种写法**各试一次 |
| 8 | `Steamworks Factory 01` / `Dunes 30 House 1` / `1 Library` / `Tv World` | `detail` 分支绕过 `strip_room_index`；行首纯数字没去；缩写被 Title Case 成 `Tv` | detail 也过 strip；加"去行首数字"；加 `_ABBR_EN`（`tv`⇒`TV`，`truelab`⇒`True Lab`） |

**★ #7 是"诊断输入造假"的教训**：我手工调 `_activity_label(sid, 'arcade', ['arcade'])` 时它是对的 —— 因为我把 `core` 写成 `arcade` 了；真调用里 `core` 是 `cyber field arcade`。**判据/诊断必须用真实输入**，否则测的是我自己想象的那条路径。

**★ #5/#6 是本项目"两处算同一件事"的又一次**：所有格由 `speakable_en` 和 id 分词**两处**决定，一边加一边不知道，就出了 `'s's`。

---

## 4. 判据改造：**被改掉的每条都写清为什么**

`check113k.py` 60 → **80** 条。口径变了，判据必须跟着变 —— 但"变松"和"变准"要分得清。

### 4.1 改掉的（每条都在代码注释里写了原判据为什么不再成立）

| 判据 | 原判 | 现判 | 为什么 |
|---|---|---|---|
| D2 | 候选带**中文类型名** | 候选**零中文** | 中文括注不进 prompt 了（口径 1） |
| D4 | 同区不许两家同类型店（看内部键） | `activity_hint` 拿到重复名字**只列一次** | 跨区域后 `ch1` 与 `ch2` 的 `Hometown · Hospital` 是两家店、两个键；合并发生在 hint 那一层。改判**行为**，不偷看内部键 |
| E4 | 判不出章 ⇒ **不产块** | 判不出章**不再阻塞**，但要换"有的不在你这一带" | 口径 3。原本的理由（"宁可不张罗也不推荐别的世界"）与新口径直接冲突，所以**改判据本身**并在注释里写明 |
| H2 | **零跨章污染** | 跨区域**不许出现裸的通用类型词**（`Diner`/`Shop`） | 跨章现在是要的。按"必须含分隔符"判会误伤 `Flower Castle`/`Green Room`/`Core`（区名==场景名时本来就只有一个词）—— 首版这么判，实测假红 |
| H4 | 四种活动**至少一种**在 ch1 有候选 | 四种**都**有 | 跨区域后不该再出现"一种都没有" |
| J4 | `ch1` 没有这类地方 ⇒ **不产块**（原判：静默是对的） | 删掉 | 跨区域后有了。这条判据守的是"别编"，现在由 `cross` 文案 + `H2` 一起守 |

### 4.2 新增的 K 组（12 条，正负成对）

`K1` Title Case · `K2/K2b` 所有格（**同输入，`proper` 有/无必须不同**）· `K3` 楼层 · `K4` 虚词 · `K5/K5b` 中文人名换英文（**无映射 ⇒ 原样返回**）· `K6/K6b` 容器区（**缩写替换不是把整区砍了**）· `K7` 真跨区域了 · `K8` 同章优先 · `K9` 全量零中文。

另加 **H5**：同一种活动里**同一个名字只出现一次**（跨章同名店合成一条）。实测 `ch1 eat` 27 条里 `Hometown · Diner` 出现 3 次（`ch1`/`ch2`/`ch3` 三个章的 `hometown.diner` 是同一家店的不同章节版本）—— `activity_hint` 最终会合并，但 `limit=4` 的名额已经被占掉，所以候选层就先去掉。

### 4.3 判据自己错的三次

| # | 判据 | 错在哪 | 怎么发现的 |
|---|---|---|---|
| 1 | `has_cjk` | 把 `、`（U+3001）和全角括号算成"中文" ⇒ `Hometown · Diner、Light World …` 被判成中文 ⇒ **4 条 J 判据恒假** | 4 条 J 同时红，但 detail 里明明全英文 ⇒ 回头看判据 |
| 2 | `H2` | "跨区域必须含 ` · `" 过窄 ⇒ 误伤 `Flower Castle`/`Green Room`/`Core` | 失败详情里是三个**完整地名**，不是裸词 |
| 3 | `recheck113k` 的 4 条 | `== 1243` / `== 16797` / `== 60` **绑死了随演进变化的绝对值** ⇒ 改码就恒红 | 本轮改完必红；铁律本来就禁"判据回显随时相变的绝对值" |

★ 第 1 条最贵：**"零中文"这种判据，判据自己必须先说清"什么叫中文"**。标点不是文字。

`recheck113l.py`（本轮新建的复检脚本）首版又栽了三处，全是"判据自己错"：

| 错在哪 | 真象 |
|---|---|
| 判"`check()` 首参是常量真" | 首参是**描述串**（永远 truthy）⇒ 恒红。必须看**第二个**参数 |
| 判"所有 .py 全 CRLF" | `check113k.py` 本来就是全 LF ⇒ 假红。产品文件才要求保 CRLF |
| 取 `baseline.json["suites"]` 当列表 | 它是 **dict**（键=suite id），`.get` 抛异常被 `except` 吞 ⇒ 0 条 ⇒ 假红 |

---

## 5. 全量数据面（不是抽样）

`_scene_label_map()` 共 **2166** 个场景 / **10** 个章。所有章 × 四种活动展开后：

| 项 | 值 |
|---|---|
| 章 × 活动展开条目 | **640** |
| **唯一标签** | **64** |
| 含中文标签 | **0** |
| 含 id 形态（`rm `/`dw `/`lw `/`room_`） | **0** |
| 空标签 | **0** |
| 调试区泄漏（`PLACE_SKIP_AREA_IDS`：`system`/`unzoned`/`test`/`debug`/`tmp`） | **0** |
| 容器名泄漏（`Rooms`） | **0** |
| 跨章条目 | **576**（口径 3 的预期结果） |

64 条全部人眼过了一遍（清单见 §6 的复现命令）。要点：

- 所有格 3 处全对：`Citadel · Asgore's Kitchen` / `Wastelands · Toriel's Kitchen` / `Noelle's House`
- 缩写 4 处全对：`TV World · B3bs Shop` / `UT · Truelab Bedroom`（`True Lab`）/ `UTY · Shop`
- 仍是英文 id 但**不算错**的：`Second Sanctuary · Churchb Library`（原作 `dw_churchb_library`，"churchb" 到底是 church B 还是别的我判不准 ⇒ **不猜**）、`Glen · House`（原作 `House_1___stew`，`stew` 在名里但场景名未登记 ⇒ 只给 `House`）

---

## 6. 验证

| 项 | 结果 |
|---|---|
| `check113k` | **80 / 80 PASS**（60 → 80 条） |
| 全量 G2 | **PASS=5597 FAIL=0 / 108 套件，EXIT=0** |
| 基线 | 只有 `check113k` 重建（`--only check113k --update`）；其余 107 个套件**全部 IDENTICAL** |
| 算术自证 | 旧 5577 = 5517 + 60；新 5597 = 5517 + 80 ✓ |
| 唯一 `IDENTICAL*` | `check75c`（既有空行噪声，未刷基线） |
| `recheck113k` | **66 / 66**（改掉 4 条绑绝对值的判据后） |
| `recheck113l` | **78 / 78**（语法 / 结构 / 编码 / 恒真判据 / 逐令牌 / 回归） |

复现命令（都在 `code-quality-audit/第113轮-全体角色AI训练/_tools/`）：

```
python check113k.py          # 80 条判据
python recheck113k.py        # 语法/结构/编码/恒真判据/逐令牌/回归
python survey_act113k_labels.py   # 全部章 × 四种活动，人读
cd ../../regress && python run_all.py
```

---

## 7. 已知缺口（不当成绩报）

1. **位置块仍是原始小写**：`【你现在在哪】town square。` —— 活动块是 Title Case，位置块沿用 113j 的输出（只改了"英文前缀剥除"的大小写）。要不要统一成 `Town Square`，等一句确认。
2. **`Bed` 而不是 `Bedroom`**：`oneshot.barrens.Bed_room` 被 `trim_core_at_type` 截到类型词 `bed`。`Barrens · Bed` 能读，但不如 `Bedroom`。
3. **`Glen · House` 丢了 `stew`**：该场景 `name` 未登记，只能给到 `House`。要补名字得改索引（本轮不做）。
4. **中间编号保留**：`UTY · Dunes 30 House` —— `30` 是黄魂的房间序号（门牌），我没删（删了就是编造）。
5. **跨区域的"远"没有量化**：只说"不在你这一带"，没有距离/楼层概念。真要做需要 `_room_graph.json` 的边权（第105轮已有 1,202 边）。
6. 第113轮k 遗留的其余项（全量 77 人 ×48 轮、`evolve113.py`、`cards113.py` 误删、合流第118轮）**原样未动**。

---

## 8. 改动清单

| 文件 | 变化 |
|---|---|
| `ralsei_pet/modules/npc_life.py` | 1243 → **1378** 行（+135） |
| `ralsei_pet/src/main.py` | 16797 → **16909** 行（+112） |
| `.../_tools/check113k.py` | 60 → **80** 条判据；头 docstring 换新口径 |
| `.../_tools/recheck113k.py` | 4 条绑绝对值的判据改成**只增不减** |
| `.../_tools/recheck113l.py` | **新建**（78 条复检：语法/结构/编码/恒真判据/逐令牌/回归） |
| `.../_tools/survey_act113k_labels.py` | 输出英文标签（人读用） |
| `code-quality-audit/regress/run_all.py` | `check113k` 的 `desc` 更新到 k/l 双口径 |
| `code-quality-audit/regress/baseline.json` | 重建 `check113k`（80 条） |
| `.../_evidence/Validation_113l.md` | 新建（本文） |
