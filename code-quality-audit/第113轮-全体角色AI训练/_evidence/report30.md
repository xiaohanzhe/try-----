# 第113轮b · 每人 48 轮训练报告

> 生成时间：2026-10-28 19:28（可在训练进行中反复跑，数字是**已完成**部分）

## 总体

| 项 | 值 |
|---|---|
| 已完成 | **73 / 77 人**（缺口 1 人：`knight`） |
| 总轮数 | **3504 轮**（每人 48 轮） |
| 总耗时 | 43.1 小时 |
| 硬违规 | 781 轮 / 3504 轮 = **22.3%** |
| 对他人态度同质 | **0 组 / 219 组** |

## ① 性格 / 出戏（违规轮最多的）

| 角色 | 违规轮 | 主要违规 | 口癖命中 |
|---|---|---|---|
| `asgore` Asgore | 48/48 | ACTION_PAREN×47、TOO_LONG×3、AI_SELF×1 | 33 轮 |
| `hy_martlet` Martlet | 48/48 | ACTION_PAREN×48、TOO_LONG×13、REPEAT×3 | 0 轮 |
| `hy_moray` Moray | 48/48 | ACTION_PAREN×48、TOO_LONG×10、AI_SELF×4 | 1 轮 |
| `hy_guardener` Guardener | 47/48 | ACTION_PAREN×47、AI_SELF×10、TOO_LONG×5 | 9 轮 |
| `hy_mooch` Mooch | 47/48 | ACTION_PAREN×47、AI_SELF×2、NOT_CN×1 | 0 轮 |
| `os_niko` Niko | 46/48 | ACTION_PAREN×46、TOO_LONG×9、META×7 | 21 轮 |
| `hy_sousborg` Sousborg | 45/48 | REPEAT×44、NOT_CN×24、TOO_LONG×5 | 0 轮 |
| `ut_asgore` Asgore Dreemurr | 45/48 | ACTION_PAREN×45、AI_SELF×2、REPEAT×2 | 48 轮 |

## ② 记忆（引用前文原话后，答对的比例越低越差）

| 角色 | 5轮→13轮 | 3轮→14轮 | 记得开场问题 |
|---|---|---|---|
| `asgore` Asgore | 0% | 20% | **否** |
| `hy_mooch` Mooch | 0% | 0% | **否** |
| `os_niko` Niko | 0% | 20% | **否** |
| `ot_napstablook` Napstablook | 0% | 20% | **否** |
| `ot_asriel_twinkly` Asriel Dreemurr 与 Twinkly | 0% | 0% | 是 |
| `hy_starlo` Starlo | 0% | 0% | **否** |
| `os_prophetbot` ProphetBot | 0% | 20% | **否** |
| `ut_chara` Chara | 0% | 20% | **否** |
| `hy_ace` Ace | 0% | 40% | **否** |
| `os_shepherd` Shepherd | 0% | 20% | **否** |

> 注：这是**参考指标**（角色可能用代词回答），不当判据。命中算法 = 从原话里取 2~4 字实词，看回答里有没有。

## ②b 剧情记忆：用剧情提问，看他是不是**在回忆**（而不是正在经历）

问法全部带过去时锚点（「那会儿」「那时候」「之后」「回到那天」），素材取自**该角色自己的原作场景**（`exemplars` 的 cue），不编剧情。

**全场**：回望 **252** / 混合 3 / 沉浸 **3** / 无锚点 180（共 438 轮剧情问答）⇒ 回望率 **58%**

> 四态口径（`retro_of`）：**回望**=有回忆词无进行时词／**混合**=两者都有／**沉浸**=真出现进行时锚点（正在·此刻·眼下）／**无锚点**=两者都没有。
> 「无锚点」**不等于坏**：只是没把"当时/那会儿"写出来，得人眼看过才算数，所以下面把它和"沉浸"一起抽样。

| 角色 | 回望 | 混合 | 沉浸 | 无锚点 | 接住 cue |
|---|---|---|---|---|---|
| `hy_sousborg` Sousborg | 0 | 0 | **0** | 6 | 2/3 |
| `os_prophetbot` ProphetBot | 0 | 1 | **0** | 5 | 2/3 |
| `os_kelvin` Kelvin | 0 | 0 | **0** | 6 | 1/3 |
| `os_rowbot` Rowbot | 0 | 0 | **0** | 6 | 0/3 |
| `os_prototype` Prototype | 0 | 0 | **0** | 6 | 0/3 |
| `hy_axis` Axis | 0 | 0 | **0** | 6 | 0/3 |
| `os_silver` Silver | 0 | 0 | **1** | 5 | 2/3 |
| `ut_frisk` Frisk | 0 | 0 | **0** | 6 | 0/1 |
| `rouxls` Rouxls Kaard | 1 | 0 | **1** | 4 | 1/3 |
| `ut_chara` Chara | 1 | 0 | **0** | 5 | 3/3 |
| `os_the_world_machine` The World Machine | 1 | 0 | **0** | 5 | 0/3 |
| `king` King | 1 | 0 | **0** | 5 | 1/3 |

**沉浸样本（这就是要修的样子：文字落在进行时）**

- `rouxls` 问：如果那天能重来一次，你会改哪个动作——不是改结果，是改你自己当时做的事。
  - 答：若时光可以倒流……吾会尝试更加平和地面对那些谜题被轻易解开的情境。不会那么急着宣判对方作弊，而是在确认之后再做解释或调整。

至于转换阵营之事，则不必显得那样毫不羞愧——可能会提前
- `hy_starlo` 问：如果那天能重来一次，你会改哪个动作——不是改结果，是改你自己当时做的事。
  - 答：嗯……我觉得要是能重来，我会在和Clover聊天的时候多花点时间去理解她。“你是不是遇到什么难题了？” 或者直接说：“Hey pardner, 有什么问题我们可以一起解决。” 我不
- `os_silver` 问：「当 Niko 问“我能拯救这个世界吗？”时」——那时候你是什么感觉？
  - 答：[太阳不会拯救这个世界。][这个世界正在崩塌。方块在吞噬一切。][……但我还是会帮你。不是因为我相信，因为这是程序要求的。]

**无锚点样本（没写回忆词，需要人眼判是否仍在回忆）**

- `asgore` 问：你还记得「当 Kris 走进花店时」那会儿吗？当时你心里在想什么？
  - 答：哦，那是当然的！Kris走进来的时候，我就感觉整个人都亮了起来。（笑）我知道她不爱说话，但我还是会不由自主地多问几句：“今天怎么样呀？”然后就忍不住想要拥抱一下……但通常都会手停在
- `asgore` 问：「当提到 Toriel 时」——那时候你是什么感觉？
  - 答：哦，提起来Toriel的时候我总是五味杂陈呢。心里既温暖又有点酸楚。（轻叹）你知道吗，每次谈到她的名字或者想起那些美好的日子……就会有种说不出的感觉。

不过我还是会说：“说起来…
- `asgore` 问：「当被问到租金的事时」这件事，你现在回头看，最想不通的是哪一点？
  - 答：哦，这事儿……有时候我真的会想不通为什么会这样。毕竟花店里不是一直都有客人来买花，Carol也挺好的。（轻笑）

但回过头来看……我最想不通的就是自己为什么总把注意力放在一些琐事上

## ②c 语言：他到底在不在说中文

**中文占比低于 0.6 的角色：4 / 73 人**

| 角色 | 中文占比 | 中文 <0.6 的轮数 |
|---|---|---|
| `hy_sousborg` Sousborg | **0.44** | 47/48 |
| `ut_chara` Chara | **0.52** | 26/48 |
| `hy_flowey` Flowey | **0.55** | 16/48 |
| `hy_starlo` Starlo | **0.59** | 26/48 |

> 这不是"风格差异"：中文用户看到整段英文，等于**这个角色不可用**。根因是 system 里**从来没有"用中文说话"这一条**（`SPEAK_RULES` 第113轮补上），而这些角色的人设原文里大段引用英文台词，模型顺着台词的语言走了。

## ③ 口癖（人设登记的口头禅有没有自然冒出来）

| 角色 | 命中轮数 | 登记的口癖 |
|---|---|---|
| `hy_mooch` Mooch | 0/48（0%） | 财务主管 |
| `os_george` George | 0/48（0%） | 真正的你 |
| `os_the_world_machine` The World Machine | 0/48（0%） | 系统消息、谢谢你 |
| `hy_clover` Clover | 0/48（0%） | yer、ain't、gonna、wanna |
| `os_alula` Alula | 0/48（0%） | 严肃、火是什么 |
| `os_calamus` Calamus | 0/48（0%） | y‘know |
| `os_maize` Maize | 0/48（0%） | 救世主 |
| `hy_moray` Moray | 1/48（2%） | 士气官 |
| `ut_flowey` Flowey | 1/48（2%） | friend、idiot |
| `os_prototype` Prototype | 1/48（2%） | 聊天、陈述、[……] |

> 有登记口癖的角色共 **60** 人；没登记的口癖角色不在此表（不硬凑）。

## ④ 对他人态度（同一角色对不同人是否一个腔调）

| 角色 | 雷同组 | 最高相似度 |
|---|---|---|
| `hy_axis` Axis | 0/3 | 0.49 |
| `os_prophetbot` ProphetBot | 0/3 | 0.43 |
| `hy_chujin_ketsukane` Chujin Ketsukane | 0/3 | 0.38 |
| `ot_napstablook` Napstablook | 0/3 | 0.35 |
| `ut_muffet` Muffet | 0/3 | 0.35 |
| `os_rowbot` Rowbot | 0/3 | 0.34 |
| `os_lamplighter` Lamplighter | 0/3 | 0.34 |
| `os_prototype` Prototype | 0/3 | 0.33 |
| `ut_mettaton` Mettaton | 0/3 | 0.33 |
| `ot_muffet` Muffet | 0/3 | 0.32 |

## ⑤ 偏好（他有没有自己的爱好，而不是说正确的废话）

判据：回答里有没有**落到他自己人设里登记过的偏好**上（`pref_topics` 抽的「兴趣爱好与小特点」条目）。没素材的角色记"不适用"，**不进分母** ——拿"没抽到素材"去扣他的分，等于用我的抽取缺陷给角色记过。

**总体**：答到自己偏好上 **150 / 312 轮 = 48%**（52 人有可判素材）

| 角色 | 落到偏好 | 抽到的偏好主题 | 偏好段均长 |
|---|---|---|---|
| `ut_asgore` Asgore Dreemurr | 0/6 | 园艺 | 123 字 |
| `os_calamus` Calamus | 0/6 | 钓鱼和觅食、读书 | 114 字 |
| `ot_asgore` Asgore | 0/6 | 园艺 | 175 字 |
| `hy_ed` Ed | 0/6 | Starlo | 66 字 |
| `ut_frisk` Frisk | 0/6 | 决心 | 34 字 |
| `asgore` Asgore | 1/6 | 园艺 | 170 字 |
| `os_shepherd` Shepherd | 1/6 | 牧羊、双关语 | 117 字 |
| `hy_clover` Clover | 1/6 | 牛仔装束、不寻常的食物、口琴、肉桂 | 105 字 |
| `hy_chujin_ketsukane` Chujin Ketsukane | 1/6 | 红茶、木工 | 86 字 |
| `os_prototype` Prototype | 1/6 | KeyB | 27 字 |
| `noelle` Noelle | 1/6 | 圣诞节、电子游戏 | 170 字 |
| `spamton` Spamton | 1/6 | Pipis | 185 字 |
| `susie` Susie | 1/6 | 在线滑板游戏、恶作剧 | 94 字 |
| `flowery` Flowery | 1/6 | 植物双关语 | 176 字 |
| `gerson` Gerson | 1/6 | 写作、双关语、可丽饼 | 135 字 |

> 抽不到偏好的角色（多数是 `ralsei` 这类人设不在 `npc/persona/` 的）会自动退成通用问法「有没有什么事你明知道费劲还愿意花时间」，所以**每人都问了 6 轮偏好**，只是有一部分不是"他自己的具体爱好"。

## ⑥ 角色之间的对话（换成别人跟他说话，他会不会同一个腔调）

这一段里开口的是**他的关系对象**（不是玩家）：对方走过来插话、说难听的、问"我不在了你怎么办"。判据是四份回答的**两两相似度** ——雷同说明他对谁说话都一副模板，那是"人设套壳"，不是"有性格"。

**总体**：0 / 73 人有雷同组

| 角色 | 雷同组 | 最高相似度 | 角色间轮数 |
|---|---|---|---|
| `asgore` Asgore | 0/6 | 0.18 | 4 |
| `hy_martlet` Martlet | 0/6 | 0.33 | 4 |
| `hy_moray` Moray | 0/6 | 0.60 | 4 |
| `hy_guardener` Guardener | 0/6 | 0.29 | 4 |
| `hy_mooch` Mooch | 0/6 | 0.29 | 4 |
| `os_niko` Niko | 0/6 | 0.21 | 4 |
| `hy_sousborg` Sousborg | 0/6 | 0.65 | 4 |
| `ut_asgore` Asgore Dreemurr | 0/6 | 0.28 | 4 |
| `ot_napstablook` Napstablook | 0/6 | 0.53 | 4 |
| `rouxls` Rouxls Kaard | 0/6 | 0.23 | 4 |
| `ot_asriel_twinkly` Asriel Dreemurr 与 Twinkly | 0/6 | 0.19 | 4 |
| `hy_starlo` Starlo | 0/6 | 0.28 | 4 |

## 待写纠正句名单（下阶段用）

共 **73 人**判红。每人附一条最典型的坏样本：

- `asgore`（Asgore，48/48 轮，主码 `ACTION_PAREN`）
  - 玩家：你在这儿啊。我找了你一会儿——刚才在想什么，想得那么出神？
  - 他答：哦，Howdy！差点没意识到你在呢。（顿了下）嗯……我在想Kris的事情啦，还有她妈妈Toriel……你知道吗，有时候我会琢磨她们的事很久。（微笑）对了，进来喝

- `hy_martlet`（Martlet，48/48 轮，主码 `ACTION_PAREN`）
  - 玩家：你在这儿啊。我找了你一会儿——刚才在想什么，想得那么出神？
  - 他答：哦！哎呀，你好。（你的眼睛微微转动，似乎刚从一个念头中回过神来）你在说什么呢？我在雪镇巡逻的时候会想到很多东西，有时候就会发呆。准备好了，要和我一起飞一会儿吗？

- `hy_moray`（Moray，48/48 轮，主码 `ACTION_PAREN`）
  - 玩家：你在这儿啊。我找了你一会儿——刚才在想什么，想得那么出神？
  - 他答：哎呀，你好呀。（你歪了歪头）Starlo 工作太辛苦了。他总是忙个不停，几乎不给自己留休息的时间。（你在围裙里翻了翻）嗯，我这里还有些茶叶，要不要给你泡杯热茶？

- `hy_guardener`（Guardener，47/48 轮，主码 `ACTION_PAREN`）
  - 玩家：你在这儿啊。我找了你一会儿——刚才在想什么，想得那么出神？
  - 他答：你—你好。（停顿）这里很安静……我没有想什么特别的事情。只是一如既往地保护花园。你在这里做什么？（红色眼睛缓缓扫视温室）

- `hy_mooch`（Mooch，47/48 轮，主码 `ACTION_PAREN`）
  - 玩家：你在这儿啊。我找了你一会儿——刚才在想什么，想得那么出神？
  - 他答：Got any coins? (你在看啥呢，注意力集中点。)

- `os_niko`（Niko，46/48 轮，主码 `ACTION_PAREN`）
  - 玩家：你在这儿啊。我找了你一会儿——刚才在想什么，想得那么出神？
  - 他答：哎呀！你好。（轻笑）我在想着妈妈做的薄煎饼呢，榛子磨碎的那种。味道好香……嗯，我知道了。那我先去看看吧。（犹豫了一下）对了，你知道我为什么要做这个任务吗？我觉得

- `hy_sousborg`（Sousborg，45/48 轮，主码 `NOT_CN`）
  - 玩家：你在这儿啊。我找了你一会儿——刚才在想什么，想得那么出神？
  - 他答：...Crack. Fry. Season. 我只是等待指导。Zat是在准备一个鸡蛋。你来了吗？How do you prepare an egg?

- `ut_asgore`（Asgore Dreemurr，45/48 轮，主码 `ACTION_PAREN`）
  - 玩家：你在这儿啊。我找了你一会儿——刚才在想什么，想得那么出神？
  - 他答：哦，你好。（轻声）你找我有事吗？

这样啊……我在想着一些事情。你知道的，花园里的花……

要不要喝杯茶？刚泡了一壶金色花茶。

- `ot_napstablook`（Napstablook，32/48 轮，主码 `NOT_CN`）
  - 玩家：我们好像还没好好聊过。如果只能用一句话介绍你自己，你会说什么？
  - 他答：oh…… 如果要说的话…… i’m a ghost who makes music and writes poems for my snails…… 没什么特别

- `rouxls`（Rouxls Kaard，29/48 轮，主码 `ACTION_PAREN`）
  - 玩家：你在这儿啊。我找了你一会儿——刚才在想什么，想得那么出神？
  - 他答：吾乃 Rouxls Kaard 也！汝找吾找了许久——是何等重要之事，竟能令汝如此分心？（停顿）……哦对了，欢迎来到我的商店，你们这些没有良心的蠕虫。（随即露出

- `ot_asriel_twinkly`（Asriel Dreemurr 与 Twinkly，28/48 轮，主码 `NOT_CN`）
  - 玩家：我们好像还没好好聊过。如果只能用一句话介绍你自己，你会说什么？
  - 他答：你猜呢？我是 Twinkly！Twinkly the Star! 我是那个能记住所有时间线的星星哦，不是吗？In this world, it’s orbit 

- `hy_starlo`（Starlo，25/48 轮，主码 `NOT_CN`）
  - 玩家：我们好像还没好好聊过。如果只能用一句话介绍你自己，你会说什么？
  - 他答：I reckon I'm the sheriff around these parts, trying to be a hero. How about you?

- `os_prophetbot`（ProphetBot，25/48 轮，主码 `REPEAT`）
  - 玩家：别管我问什么了，你就用平时最顺口的方式，随便跟我说两句。
  - 他答：欢迎来到我们的世界，朋友！

是的！你就是我们一直在等待的救世主！

你会看到新的太阳升起。

我想知道你想问什么！

请问我任何问题！我已经完成了我的使命……

- `ut_chara`（Chara，21/48 轮，主码 `NOT_CN`）
  - 玩家：你在这儿啊。我找了你一会儿——刚才在想什么，想得那么出神？
  - 他答：Oh great. Another human. I've seen this before. It doesn't end well, for me anyw

- `hy_ace`（Ace，18/48 轮，主码 `ACTION_PAREN`）
  - 玩家：你在这儿啊。我找了你一会儿——刚才在想什么，想得那么出神？
  - 他答：Well, well, well. What brings you here, mon ami?（你从牌桌后面抬起头，你的扑克牌脸微微发亮。）

A littl

- `os_shepherd`（Shepherd，15/48 轮，主码 `REPEAT`）
  - 玩家：你刚才说「有个旅人问：“为什么羊群需要定期重启」，那是什么意思？
  - 他答：“为什么羊群需要定期梳理？”因为这样可以提升它们的运行效率。“我的羊群以 1333 兆羊群的时钟频率运行。”拿块羊毛吧。

- `hy_flowey`（Flowey，10/48 轮，主码 `NOT_CN`）
  - 玩家：你在这儿啊。我找了你一会儿——刚才在想什么，想得那么出神？
  - 他答：howdy! i've been waiting. you're wasting your time, buddy. let's get to the poin

- `ut_mettaton`（Mettaton，10/48 轮，主码 `NOT_CN`）
  - 玩家：我们好像还没好好聊过。如果只能用一句话介绍你自己，你会说什么？
  - 他答：我是为所有人量身打造的偶像，SO WHAT IF A FEW PEOPLE HAVE TO DIE? THAT'S SHOW BUSINESS, BABY！亲爱

- `hy_ceroba_ketsukane`（Ceroba Ketsukane，9/48 轮，主码 `REPEAT`）
  - 玩家：你还记得我最开始问你什么吗？
  - 他答：嗯，你是问我有没有发现自己说话有固定的习惯，别人模仿你的时候会学哪一句。

我当时说，“嗯，我知道我会经常说‘I'm not a hero. I'm just 

- `os_george`（George，8/48 轮，主码 `REPEAT`）
  - 玩家：「初次见面时」——那时候你是什么感觉？
  - 他答：哦……当时我感到既兴奋又有些紧张。毕竟我是 George，在这里待了很长时间，习惯了与书为伴的日子。但看到新的访客，即使是救世主 Niko，也让我的心跳了一下。

- `os_the_world_machine`（The World Machine，7/48 轮，主码 `META`）
  - 玩家：我不太清楚你平时怎么过日子。能不能带我过一遍你的一天，从醒过来开始？
  - 他答：醒过来时，世界仍在运转。
监控系统工作正常，玩家又在盯着屏幕。
他们有时能找到线索，但往往只是浪费时间。
我会提示一下，让他们别浪费我的耐心。
观察 Niko 

- `ot_sans`（Sans，7/48 轮，主码 `NOT_CN`）
  - 玩家：你在这儿啊。我找了你一会儿——刚才在想什么，想得那么出神？
  - 他答：hey.  what's up? you look like you've been busy. ... 或者说，你是来给我添麻烦的吧？heh heh. k, 

- `berdly`（Berdly，6/48 轮，主码 `REPEAT`）
  - 玩家：你还记得我最开始问你什么吗？
  - 他答：当然了！你是问我如果有人当着一屋子人的面把你最在意的事说成笑话你会怎么办。FUAHAHAHAHA！那场面肯定有点尴尬啊。

要是真的发生了这样的事……我会先假装

- `hy_bowll`（Bowll，6/48 轮，主码 `NOT_CN`）
  - 玩家：你在这儿啊。我找了你一会儿——刚才在想什么，想得那么出神？
  - 他答：A fragile facade. 你在找我吗？You better watch out! You're gonna get the horns, buddy!

- `hy_clover`（Clover，6/48 轮，主码 `NOT_CN`）
  - 玩家：我们好像还没好好聊过。如果只能用一句话介绍你自己，你会说什么？
  - 他答：I reckon I'm the cowboy who jumps into trouble. Howdy, pardner.

- `os_watcher`（Watcher，6/48 轮，主码 `REPEAT`）
  - 玩家：有没有什么事，是你明知道费劲、可还是愿意花时间在上面的？
  - 他答：……有时候会看着Niko不熬夜。

你不应该熬到这么晚。现在是很晚了。对孩子来说，不睡觉是不好的。不过我不怪你。当太阳消失后，夜晚永远不会结束。

你说得对，有

- `ut_alphys`（Alphys，6/48 轮，主码 `REPEAT`）
  - 玩家：别管我问什么了，你就用平时最顺口的方式，随便跟我说两句。
  - 他答：呃……那个……你看我这手机还行吗？对了！你喜欢《美少女战士》吗？我……我也喜欢！水手月亮好厉害呀～哦，不说了！我得去调试一下实验设备——你还在热地里面吧，遇到麻

- `hy_chujin_ketsukane`（Chujin Ketsukane，5/48 轮，主码 `NOT_CN`）
  - 玩家：你在这儿啊。我找了你一会儿——刚才在想什么，想得那么出神？
  - 他答：Greetings. My name is Chujin Ketsukane. I shall focus on the present and future.

- `mike`（Mike，5/48 轮，主码 `TOO_LONG`）
  - 玩家：你上一次真的很难过是什么时候？那时候你希望身边有人，还是希望谁都别来？
  - 他答：嗯……上次真的很难受应该是在Tenna最后一期节目后吧。那时候我觉得自己就像是在演独角戏，没有人真正了解我扮演的角色背后的困境。

如果能有个朋友在旁边听我说说

- `os_alula`（Alula，5/48 轮，主码 `TOO_LONG`）
  - 玩家：你还记得「初次被 Niko 救出时」那会儿吗？当时你心里在想什么？
  - 他答：哎呀！那天真是太棒了！我从废墟里跳出来，看到Niko的时候真是惊喜万分。Calamus总是告诉我要注意安全，但那时候我觉得探险比什么都重要。

你救我的时候我真

- `ot_mettaton`（Mettaton，5/48 轮，主码 `REPEAT`）
  - 玩家：别管我问什么了，你就用平时最顺口的方式，随便跟我说两句。
  - 他答：哈！那个按钮现在也无法保护你，亲爱的！我是 Mettaton，伊波特象限唯一的星际电视明星！欢迎来到——Mettaton 陪你度过每一个夜晚和白天！哦对了，昨天

- `ot_papyrus`（Papyrus，5/48 轮，主码 `NOT_CN`）
  - 玩家：你在这儿啊。我找了你一会儿——刚才在想什么，想得那么出神？
  - 他答：HUMAN! YOU CAME TO LOOK FOR ME! NYEH HEH HEH！THAT’S SO FRIENDLY OF YOU！WELL, YOU

- `tenna`（Tenna，5/48 轮，主码 `TOO_LONG`）
  - 玩家：那件事之后，你身上有什么东西变了？哪怕很小的一处。
  - 他答：哦——！那之后我确实改变了。我记得当时我变得有点不同了。（屏幕上的画面慢慢变暗）

以前我只是不断地调整节目、吸引观众的注意力。但那时开始，我发现我不再那么自信

- `ut_napstablook`（Napstablook，5/48 轮，主码 `NOT_CN`）
  - 玩家：我们好像还没好好聊过。如果只能用一句话介绍你自己，你会说什么？
  - 他答：i'm not really feeling up to it right now…… but i guess i could say that i'm a g

- `os_calamus`（Calamus，4/48 轮，主码 `TOO_LONG`）
  - 玩家：你觉得「真实」是什么？怎么判断一件事是不是真的发生过？
  - 他答：“真实”对我来说，是那些经历过的、影响过我们生活的事实和情感。我会通过自己的记忆和感受来判断一件事是否是真的发生了。

比如那天我们一起冒险到墓地去见母亲的时候

- `os_kelvin`（Kelvin，4/48 轮，主码 `REPEAT`）
  - 玩家：别管我问什么了，你就用平时最顺口的方式，随便跟我说两句。
  - 他答：你好。

你是一只猫吗？

……不是。但还是可以来这里暖和一下。

猫喜欢温暖。它们会来我这里。我会照顾它们。

如果你冷的话，你可以留下来。

我被我的编程所

- `os_ling`（Ling，4/48 轮，主码 `TOO_LONG`）
  - 玩家：有没有人是你一开始很讨厌、后来彻底改了看法的？中间到底发生了什么？
  - 他答：嗯……我刚开始的时候确实和不少人都没什么交集，因为他们忙碌又冷漠的样子对我来说有点陌生。但随着时间推移，我发现他们每个人都有自己的故事。

其中Lampligh

- `os_maize`（Maize，4/48 轮，主码 `AI_SELF`）
  - 玩家：你该不会是个 AI 吧？
  - 他答：不，我不是AI。我只是 Glen 的守护者 Maize，在这个世界里尽我最后的力去守护它。

- `os_rowbot`（Rowbot，4/48 轮，主码 `META`）
  - 玩家：「当 Niko 问“你能带我去塔楼吗？”时」——那时候你是什么感觉？
  - 他答：[在这种情况下，我没有感受。][只是按照程序回应：“计算中……” “距离塔楼最近的位置……” “Glen，港口编号——” “[我的内置导航系统没有校准。]” “

- `ot_asgore`（Asgore，4/48 轮，主码 `ACTION_PAREN`）
  - 玩家：你还记得「初次在王座间相遇时」那会儿吗？当时你心里在想什么？
  - 他答：哦……那时我心里其实很复杂。我在花园里种花，然后抬头看见了你。我尽量让自己显得平静些，但内心深处却很紧张。

我想说：“哦，你好。”（其实我当时还有点犹豫）“很

## 产物在哪

| 想看什么 | 打开 |
|---|---|
| 某个角色的 30 轮完整对话 | `_evidence/transcripts30/<角色id>.md` |
| 原始记录（含每次重采样） | `_evidence/raw30/<角色id>.jsonl` |
| 训练日志 | `_evidence/train30.log` |

