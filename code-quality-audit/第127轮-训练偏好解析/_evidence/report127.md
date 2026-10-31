# 第127轮报告 · 训练线的「成果漏损」：4 条被误判成歧义的偏好

> 用户口径（本轮唯一一句）：「对了，别忘了其他的计划，**训练这类的也要抓一下**哦」
>
> 承接：第126轮（outertale 门型收口）已提交并推 `local-126`，全量 G2
> `PASS=6099 / FAIL=0 / 套件 125 / 全 IDENTICAL`。

---

## 1. 定位：先量接线，再决定抓哪里

「训练」这条线在本项目里指第113轮那套离线训练：`_training/_index.json`（96 张卡）、
`persona/*.txt`（76 份人设）、`patches`（59 条纠正）、`_seek.json`（72 人的「想找谁」）、
`corpus/*.jsonl`（77 份 / 3,696 行，留给 LoRA，运行时**不用**）。

我先逐环量了「训练产物 → 产品代码」的接线，**不靠印象**：

| 环节 | 接线点 | 实测 |
|---|---|---|
| 96 个角色覆盖 | `_registry.json` 的 `tier` | **main 78 / plain 18**；main = 77 有 AI 人设 + `ralsei`（走 `assets/ralsei_persona.md` 单一真源）；plain 18 = 设计上「用 4~10 句内置对话，不走模型」；`knight` 是 main 但 `persona=null`，`notes` 写明「不说话/极少说话，压迫感来自沉默」 |
| 训练纠正 | `npc_persona.training_patch()` → `main.py:3494` `build_system_prompt(patch=)` | 有 **59** 条，接线**通** |
| 关系卡 / 演化卡 | 同处 `relation=` / `evolution=` | 通 |
| 「想找谁」 | `npc_seek.load()` → `weights_of()` → `_pick_friend(seek=)` | 通，**72** 人 |
| 训练语料 | `corpus/*.jsonl` | **运行时不读**（LoRA 素材，属设计，不是缺陷） |

⇒ **覆盖不是缺口**（96/96 都有明确策略），**接线也没断**。
缺的那块在**数据被白白丢掉的那一段**。

## 2. 真缺口：`unresolved_names` 里 4 条「其实解得开」的 Asgore

`_seek.json` 的 `unresolved_names`（解析不到、按纪律丢弃的名字）里有 28 条，其中：

```
ut_toriel    → Asgore（ambiguous）
ut_undyne    → Asgore（ambiguous）
ut_frisk     → Asgore（ambiguous）
ut_flowey    → Asgore（ambiguous）
```

`ambiguous` = 「名册里有多个同名，我不猜」。这条纪律本身是对的（第113轮p 的原始教训：
猜错等于把 A 的偏好挂到 B 头上）。**但这 4 条根本不是歧义。**

### 根因

`gen_seek113p.pick_id()` 的「登记名以该名字开头」第三档，被写在 `if not cand:` 里面：

```python
if not cand:                      # ← 只有精确档**零命中**才进得来
    if len(str(nm)) >= 5:
        ...startswith 前缀档...
```

而 UT 那条 Asgore 的登记名是 **`Asgore Dreemurr`**（`_registry.json` 实测）：

```
'Asgore' 精确档 → ['asgore'(Deltarune), 'ot_asgore'(outertale)]   # 两条，非空
源 ut_toriel 的作品前缀 = 'ut_' → 同作品候选 = 空 → ambiguous（丢弃）
别名档里明明有 ut_asgore，却因为"精确档不为空"永远读不到。
```

⇒ 别名档**设计了、也实现了，但只在一半的入口上生效**。

## 3. 影响面：先量化，再动手

改解析函数是有风险的（它影响全部 477 个「名字 → 人」的解析）。所以先写探针对
`raw30` 里出现的**全部** (名字, 源) 对跑「旧逻辑 vs 新逻辑」：

```
raw30 里不同 (名字, 源) 对: 477
差异条数 = 8，其中倒退 = 0
自指（目标 == 源）条数 = 0
```

8 条差异**全部**是 `ut_*` 提 `Asgore` → `ut_asgore`
（ut_alphys / ut_chara / ut_flowey / ut_frisk / ut_gaster / ut_mettaton / ut_toriel / ut_undyne）。

零倒退、零自指 ⇒ 可以动手。

## 4. 修法

1. 把前缀档抽成 `_alias_startswith(nm, by_name, ids)`（**只一份实现**，两处复用）。
2. 在 `pick_id` 判 ambiguous **之前**、`len(same) == 1` 判据**之后**，加一次兜底：
   同作品候选为空、且源有作品前缀 ⇒ 用别名档取**同作品**那一条，恰好一个才采用。

```python
    if not same and p:
        alias = [c for c in _alias_startswith(nm, by_name, ids)
                 if split_prefix(c)[0] == p]
        if len(alias) == 1:
            return alias[0], 'ok'
```

**为什么只收同作品那一条**：`Sans` 在 ut_/ot_ 各一条、源 `toriel`（无前缀）提它，
仍然 ambiguous —— 跨作品猜错就是把偏好挂到另一个人身上。这条门没动。

**为什么这不是「猜」**：源 `ut_toriel` 提 `Asgore`，UT 的 Asgore 只有一位，且登记名
只差一个后缀。`why` 原句本身也是证据（见下表）。

## 5. 结果

`_seek.json`：条目 **189 → 193**（+4），角色数仍 **72**，`formula` / `method` / `about` /
`schema` **一字未改**，既有 189 条**逐字段一字未改**（对账 16/16 PASS）。

新增 4 条的 `why` 原句（全部是 UT 剧情，不是 Deltarune 的 Asgore）：

| 源 | w | 原句 |
|---|---|---|
| ut_toriel | 1.24 | 「比如 Asgore 站在那里时的那种气氛，总会让我变得严肃起来」 |
| ut_undyne | 1.06 | 「吃完饭就继续训练，直到 Asgore 叫我去瀑布抓人类为止」 |
| ut_flowey | 1.06 | 「如果我和 Asgore 彻底闹翻了，我大概不会选择低头吧」 |
| ut_frisk | 1.06 | 「面对 Asgore 战斗时害怕」 |

——「瀑布」「闹翻」只可能出现在 UT。这是「同作品优先」正确性的直接证据。

`unresolved_names` 少 4 条；仍保留 `Sans（ambiguous）`×2、`Undyne（ambiguous）`、
`Twinkie`/`Grillby`/`Kanako`/`人类`/`厨房` 等 24 条（拒猜纪律不变）。

## 6. 判据（`check127.py`，24 条）

| 段 | 守什么 |
|---|---|
| A 现场 | 8 个 `ut_*` 源真跑 `pick_id` ⇒ 必须 `ut_asgore`；根因可复述（登记名是 `Asgore Dreemurr`；精确档确实只有两条） |
| B 拒猜纪律 | 跨作品同名（`Sans`/`Undyne`）仍 ambiguous；名册外（`Grillby`/`Kanako`）仍 unknown；非人条目（`人类`/`厨房`）仍丢弃 |
| C 数据面 | 4 条真在；`why` 原句真的提到 `Asgore`；`unresolved` 不再有该条；仍被拒的 3 条还在；无自指；条目数下界 193 |
| **D 破坏性负控制** | 把别名兜底**拆掉**重算（`pick_old`）⇒ 同 4 个源**全部解不出**（证明 A 的绿来自修复，不是恒真）；`ot_toriel` 换一部作品也成立（排除硬编码 ut）；生成器里别名档**只有一份实现** |
| E 自检 | AST 查恒真（有分母：函数 ≥5）；本脚本与 `_seek.json` 无 BOM / 无 U+FFFD |

**B1 首跑报红，红的是我的断言**：我写的是「无前缀源提 `Asgore` 仍判 ambiguous」，
实测 `('asgore','ok')` —— 无前缀源 + 无前缀候选恰好一个，**本来就该解析**。
改成真正该守的那条：「**不许**被别名兜底带到 `ot_asgore`/`ut_asgore`」。

## 7. 验证

- `check127` **24/0**
- `check113p`（第113轮p 老锁，守偏好层）**54/0**
- `_seek.json` 逐字段对账（HEAD vs 工作区）**16/16**：顶层字段未改 · 角色集合未改 ·
  既有条目零消失零改值 · 新增恰好 4 条且全是 `ut_asgore` · 减少的未解析恰好 4 条且全是
  `Asgore（ambiguous）` · 自指零
- 全量 G2：见 §8

## 8. 踩坑

1. **首跑 `check127.B1` 报红** —— 又是「红的是判据不是产品」。无前缀源的同作品解析
   本来就是 `ok`，我按"歧义"写死了期望。
2. **PowerShell 管道编码**：`python ... *>` 落的是 UTF-16LE，Read 打不开；
   改用 `2>&1 | Out-File -Encoding utf8` 才可读。**控制台里的中文乱码不代表数据错**。
3. **`ConvertFrom-Json` 把 JSON 数组当对象**：`$j.npcs.catti` 返回的是数组的方法集合，
   看起来像"字段全 None"。**统计类必须用 Python 解析**，别用 PowerShell 猜结构。

## 9. 遗留（训练线）

- `unresolved_names` 剩 **24** 条：`Kanako`(×3) / `Grillby` / `Annoying Dog` /
  `Feisty Five` / `母亲` / `萤火虫` / `时间` / `钟楼` / `玩家` / `人类`(×2) 等 ——
  绝大多数是**名册外或非人**，按纪律丢弃是对的；`Twinkly` 一条**可解**
  （`ot_asriel_twinkly` 的登记名是 `Asriel Dreemurr 与 Twinkly`，属"后缀"匹配，
  需另立规则且风险高于收益）⇒ 本轮**不做**，登记在此。
- `corpus` 77 份 / 3,696 行**未用于运行时**（LoRA 素材，属设计）。
- `patches` 59 / 96（37 个角色训练 0 违规，无需纠正）。
- 第126轮遗留照旧：uty 287 场景零边 · outertale 40 场景无出边 · ch2~ch5 桌面不可达等。
