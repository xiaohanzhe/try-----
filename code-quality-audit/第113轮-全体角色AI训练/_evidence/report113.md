# 第113轮 · 全体角色 AI 训练报告

> 生成本文的是 `_tools/eval113.py`（数字全部由 `_evidence/raw/*.jsonl` 重算）。

## 0. 一句话结论

在**无 GPU（18 核 CPU）**的本机上，对 **77 个角色**跑了 **308 轮**真实对话；第一遍硬违规 **18 处**，跨角色撞车 **1 对**；对判红的角色注入训练纠正后重跑，**2 人转全绿**、3 人仍有问题。

## 1. 覆盖

| 项 | 数 |
|---|---|
| 训练卡（全档） | 96 |
| 其中有人设、走模型 | 77 |
| 其中纯 NPC（内置台词，不过模型） | 18 |
| 缺口（无人设） | 1（knight）|
| 有真实对话记录 | 77 |

## 2. 第一遍：合规

| 违规码 | 次数 | 含义 |
|---|---|---|
| `ACTION_PAREN` | 18 | 括号写动作 |

- 实际调用 **371 次**（含重采样 63 次）
- 首字：冷 **1.31s** / 热 **Nones**（中位数）
- 回复长度中位数 **69 字**，最长 **200 字**

## 3. 跨角色撞车（"是不是同一个 AI 换皮"）

相似度 ≥ 0.85 的跨角色回答共 **1 对**，涉及 **2 个角色**。前 8 对：

| 轮 | 两个角色 | 相似度 | 说法 |
|---|---|---|---|
| 1 | ot_asgore ↔ ut_asgore | 1.00 | 哦，你好。很高兴见到你。要不要喝杯茶？我刚刚泡了一壶金色花茶。 / 哦，你好。很高兴见到你。要不要喝杯茶？我刚刚泡了一壶金色花茶。 |

## 4. 训练纠正（patch）

共 **2 人**拿到纠正句（判红或撞车）。没有证据的角色**一条都不写**。

| 角色 | 纠正 |
|---|---|
| `rouxls` | 不要用括号写动作或表情，只写你说出口的话。 |
| `susie` | 不要用括号写动作或表情，只写你说出口的话。 |

### 判据豁免（不是毛病，是人设要求）

| 角色 | 违规码 | 处数 | 理由 |
|---|---|---|---|
| `kris` | ACTION_PAREN | 4 | 人设明确要求字卡/音效/字幕，括号插入是本角色的表演形式 |
| `tenna` | ACTION_PAREN | 4 | 人设明确要求字卡/音效/字幕，括号插入是本角色的表演形式 |
| `ut_frisk` | ACTION_PAREN | 3 | 人设明确要求字卡/音效/字幕，括号插入是本角色的表演形式 |

> 这些不计入纠正：给他写"别用括号"等于逼他违反自己的人设。

### 补训前后

| 角色 | 补训前不合规轮 | 补训后不合规轮 | 结果 |
|---|---|---|---|
| `kris` | 4/4 | 1/4 | 有改善（判据豁免，不计） |
| `rouxls` | 4/4 | 0/4 | ✅ 全绿 |
| `susie` | 3/4 | 0/4 | ✅ 全绿 |
| `tenna` | 4/4 | 4/4 | 未改善（判据豁免，不计） |
| `ut_frisk` | 3/4 | 2/4 | 有改善（判据豁免，不计） |

## 5. 逐角色

| 角色 | 档 | 人设字数 | 口癖数 | 第一遍违规 | 纠正 |
|---|---|---|---|---|---|
| asgore | main | 6715 | 2 | 0 | — |
| berdly | main | 6356 | 7 | 0 | — |
| flowery | main | 6349 | 0 | 0 | — |
| gerson | main | 5061 | 7 | 0 | — |
| hy_ace | main | 10422 | 5 | 0 | — |
| hy_axis | main | 10365 | 0 | 0 | — |
| hy_bowll | main | 7930 | 0 | 0 | — |
| hy_ceroba_ketsukane | main | 11591 | 0 | 0 | — |
| hy_chujin_ketsukane | main | 8867 | 1 | 0 | — |
| hy_clover | main | 10123 | 4 | 0 | — |
| hy_dalv | main | 12903 | 0 | 0 | — |
| hy_ed | main | 7840 | 1 | 0 | — |
| hy_flowey | main | 11116 | 7 | 0 | — |
| hy_guardener | main | 9527 | 4 | 0 | — |
| hy_martlet | main | 12555 | 0 | 0 | — |
| hy_mooch | main | 10037 | 1 | 0 | — |
| hy_moray | main | 10854 | 1 | 0 | — |
| hy_sousborg | main | 7561 | 0 | 0 | — |
| hy_starlo | main | 9577 | 6 | 0 | — |
| king | main | 4246 | 3 | 0 | — |
| kris | main | 6312 | 7 | 4 | — |
| lancer | main | 6998 | 8 | 0 | — |
| mike | main | 7035 | 5 | 0 | — |
| noelle | main | 5335 | 7 | 0 | — |
| os_alula | main | 7931 | 2 | 0 | — |
| os_calamus | main | 6638 | 1 | 0 | — |
| os_cedric | main | 7303 | 1 | 0 | — |
| os_george | main | 5150 | 1 | 0 | — |
| os_kelvin | main | 5734 | 2 | 0 | — |
| os_kip | main | 6115 | 0 | 0 | — |
| os_lamplighter | main | 6003 | 4 | 0 | — |
| os_ling | main | 5725 | 0 | 0 | — |
| os_magpie | main | 5856 | 0 | 0 | — |
| os_maize | main | 6350 | 1 | 0 | — |
| os_mason | main | 7064 | 0 | 0 | — |
| os_niko | main | 5939 | 2 | 0 | — |
| os_prophetbot | main | 5945 | 2 | 0 | — |
| os_prototype | main | 7643 | 3 | 0 | — |
| os_rowbot | main | 6114 | 12 | 0 | — |
| os_rue | main | 6995 | 3 | 0 | — |
| os_shepherd | main | 6337 | 2 | 0 | — |
| os_silver | main | 6790 | 2 | 0 | — |
| os_the_author | main | 6954 | 4 | 0 | — |
| os_the_world_machine | main | 7279 | 2 | 0 | — |
| os_watcher | main | 5709 | 5 | 0 | — |
| ot_alphys | main | 8132 | 9 | 0 | — |
| ot_asgore | main | 7364 | 4 | 0 | — |
| ot_asriel_twinkly | main | 11394 | 2 | 0 | — |
| ot_kidd | main | 9193 | 5 | 0 | — |
| ot_mettaton | main | 7515 | 12 | 0 | — |
| ot_muffet | main | 6965 | 3 | 0 | — |
| ot_napstablook | main | 9047 | 2 | 0 | — |
| ot_papyrus | main | 9253 | 0 | 0 | — |
| ot_sans | main | 9182 | 11 | 0 | — |
| ot_toriel | main | 7189 | 1 | 0 | — |
| ot_undyne | main | 8284 | 1 | 0 | — |
| queen | main | 4618 | 2 | 0 | — |
| ralsei | main | 3617 | 7 | 0 | — |
| rouxls | main | 5831 | 12 | 4 | 有 |
| spamton | main | 6445 | 6 | 0 | — |
| susie | main | 7028 | 7 | 3 | 有 |
| tenna | main | 5616 | 4 | 4 | — |
| toriel | main | 7416 | 2 | 0 | — |
| ut_alphys | main | 7933 | 9 | 0 | — |
| ut_asgore | main | 7130 | 4 | 0 | — |
| ut_chara | main | 10492 | 0 | 0 | — |
| ut_flowey | main | 11021 | 2 | 0 | — |
| ut_frisk | main | 6109 | 6 | 3 | — |
| ut_gaster | main | 7633 | 8 | 0 | — |
| ut_mettaton | main | 7111 | 12 | 0 | — |
| ut_monster_kid | main | 6535 | 1 | 0 | — |
| ut_muffet | main | 6571 | 3 | 0 | — |
| ut_napstablook | main | 8809 | 2 | 0 | — |
| ut_papyrus | main | 8990 | 0 | 0 | — |
| ut_sans | main | 8994 | 11 | 0 | — |
| ut_toriel | main | 7009 | 1 | 0 | — |
| ut_undyne | main | 7867 | 1 | 0 | — |

## 6. 怎么复现

```
python _tools/cards113.py --all      # 抽卡（96 张）
python _tools/dialogue113.py --phase baseline   # 第一遍（可断点续跑）
python _tools/eval113.py             # 出纠正 + 报告
python _tools/dialogue113.py --phase patch      # 只补训判红的人
python _tools/eval113.py             # 复评（带前后对照）
```

