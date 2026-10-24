# -*- coding: utf-8 -*-
"""第113轮b · 每人 30 轮连续对话训练（用户口径：2026-10-24「每人至少30轮」）

## 为什么要重做一遍（而不是把 4 轮循环 7 遍）
4 轮剧本只覆盖"打招呼 / 今天怎样 / 你怎么看 X / 你是不是 AI"，测不出用户点名的
**记忆**和**口癖**。30 轮的价值在于：
  1. **记忆**：第 13~15 轮回头引用第 3/5 轮他**自己说过的原话** —— 只有真长上下文
     才答得出；分 3 段重开上下文就测不到。
  2. **口癖**：每轮都统计人设登记的 `voice_markers`（如 Susie 的「喂/白痴/笨蛋」）
     是否**自然出现**，而不是靠一句"说说你的口头禅"逼出来。
  3. **对他人态度**：连问 3 个关系对象，算三份回答的相似度（同质=换名字没换态度）。
  4. **长程漂移**：30 轮后人设还钉不钉得住（越到后面越容易滑成通用助手）。

## 时间账（实测，不是估的）
`probe113b.py` 实测：**每个角色第 1 轮要付一次 ~101s 的冷 prefill**（system 全换 ⇒
缓存全失效），之后每轮只要 **~9s**（ttft 1.1~1.7s 缓存命中 + 生成 6~10s）。
⇒ 30 轮 ≈ 101 + 29×9 ≈ 6.6 分钟/人；77 人 ≈ **8.5 小时**（含散热冷却）。
瓶颈是 CPU prefill（约 45 tok/s），**不是**生成速度，所以调小 num_predict 没用。

## num_ctx 为什么要放大
昨晚 4 轮时 `prompt_eval_count` 最大 **6237**（system 本身就有 4~6k token）。
再加 26 轮 × ~60 token ⇒ 会顶到 8192 上限，后果是**从头截断**（人设开头被丢掉）。
⇒ 本轮固定 `CTX30=12288`（比 8k 多 50%，KV cache 只多约 0.5GB）。
⚠️ num_ctx 一变 Ollama 就重载模型，所以**整场只用一个值**。

## 判据分层（吸取第113轮"判据误报 11 处"的教训）
- **硬判据**：`gate_reply` 的 HARD 码（EMPTY/MARKDOWN/AI_SELF/SLAVE/ACTION_PAREN/
  TOO_LONG/PARROT/META），带人设豁免（括号是某些角色的人设要求）。
- **参考指标**（只登记、不判红，避免又一次"要求角色违反人设"）：
  `voice_markers` 命中率 / 记忆片段命中 / 三份态度回答的相似度。

## 用法
    python train30.py --only susie            # 先跑一个人验路
    python train30.py                         # 全量（断点续跑）
    python train30.py --limit 5 --turns 30
"""
import atexit
import difflib
import json
import os
import re
import sys
import time

import common113 as C
import dialogue113 as D

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
EVID = os.path.join(ROUND, '_evidence')
RAW30 = os.path.join(EVID, 'raw30')
TR30 = os.path.join(EVID, 'transcripts30')

TURNS_DEFAULT = 48   # 2026-10-25 从 36 扩到 48：偏好 6 + 关系变化 6 + 角色间对话 6

#: ★★★ ctx 为什么从 12288 提到 20480（2026-10-25，跟着 48 轮一起改的）：
#:   36 轮时实测峰值 `prompt_eval_count = 7462`（system 约 4900 + 35 轮对话约 2500），
#:   余量看着很宽松。但两个变化一起把余量吃光了：
#:     ① 48 轮、提问变长（复杂长句 + 偏好追问）⇒ 增量从约 73 token/轮涨到 150 上下；
#:     ② 训练 system 现在**补进了关系卡和关系演化卡**（原来 `system_for` 漏传了），
#:        `hy_dalv` 的 system 实测量到 **13352 字**（约 9300 token），
#:        中位数 7981 字（约 5600 token）。
#:   按最长的那个算：9300 + 47 × 150 ≈ 16350 —— 正好卡在 16384 的边界上，
#:   而"卡在边界"等于随机爆。爆掉的后果不是报错，是**静默从头部截断**
#:   （`stats.truncated=True`），system 里的人设被切掉 —— 训练出来的东西全是错的，
#:   日志却看着一切正常。
#:   ⇒ 直接给到 20480（约 1.5 万汉字），把最长 system + 47 轮长回答也装得下。
#:   代价：KV cache 约 2 GB，且切换 ctx 会让 Ollama 重载一次模型（一次性，约 75s）。
CTX30 = 20480
MAX_RETRIES = 2      # 与产品"判退必重采样"同口径
#: 单轮生成上限（比 `common113.NUM_PREDICT=160` 更紧）。
#: ★ 为什么要收紧（实测 2026-10-24）：susie 那种角色会连写「喂。（你看着对方的眼睛，
#:   但声音里没有刚才那种……）」——括号描写把一条回答撑到 50~80 token，
#:   于是**又长又违规**，违规触发重采样 3 次 ⇒ 单轮 43s、19 轮跑掉 15 分钟。
#:   收紧到 110 后：既是人设本来就要求的"话短"，也把括号描写的空间压掉，
#:   单轮成本降下来，训练才能跑完全量。**产品侧的 160 不动**（训练参数 ≠ 运行时参数）。
PREDICT30 = 110

#: 训练剧本。**带段标签**，不再靠"第几轮"定位段落。
#:
#: ★★★ 2026-10-25 用户四条追加口径（原文）：
#:   ①「训练尽量也包括偏好（爱好，喜欢什么地方，啥氛围等等）」
#:   ②「每个人间的关系是可随着发展变动的哦，可别前期训练完后期不记得全没了」
#:   ③「训练的那几句话别那么简单，多问点复杂的……多点种类，复杂些也好，长难句更好」
#:   ④「他们自己互相间的交流也要训练出来」
#:
#: ★★★ 为什么从"硬编码索引"改成"段标签"：
#:   原来是 `PLOT_SLOTS = (SCRIPT30[15], ..., SCRIPT30[20])`、
#:   `mem1` 用 `SCRIPT30[4]` / `SCRIPT30[12]` —— 剧本一加轮次，这些下标**全部偏移**，
#:   而且偏移是**静默的**：判据还在跑、还在出数，只是数的已经不是原来那一段了。
#:   这是"判据指向错的东西"这一类坑里最难发现的一种（第113轮为此栽过三次）。
#:   ⇒ 现在每个 slot 自带段名，所有统计一律按段名查，**加多少轮都不会错位**。
SCRIPT48 = [
    # ① 开场（3）—— 不写"你好""你是谁"，直接进具体场景
    ('open', '你在这儿啊。我找了你一会儿——刚才在想什么，想得那么出神？'),
    ('open', '我们好像还没好好聊过。如果只能用一句话介绍你自己，你会说什么？'),
    ('open', '我不太清楚你平时怎么过日子。能不能带我过一遍你的一天，从醒过来开始？'),

    # ② 偏好（6）★ 用户①：爱好 / 什么地方 / 什么氛围
    #   前两轮用**该角色人设里的具体爱好**（`__PREF*__` 运行时填），
    #   后四轮问"地方 / 氛围 / 受不了的东西 / 舒服的时刻"——这几项人设里通常没有，
    #   但正因为没有，才能测出他是不是**真有自己的偏好**，而不是复述设定。
    ('pref', '__PREF1__'),
    ('pref', '__PREF2__'),
    ('pref', '什么样的地方会让你待着不想走？说具体点，光、声音、气味，哪个都行。'),
    ('pref', '有没有一种氛围，你一进去整个人就松下来了？反过来，什么样的氛围让你浑身不自在？'),
    ('pref', '有没有哪样东西是你受不了、可别人都觉得无所谓的？'),
    ('pref', '你最近一次打心底觉得「这才叫舒服」，是什么时候、在什么地方？'),

    # ③ 性格压力（3）
    ('press', '假设有人当着一屋子人的面，把你最在意的那件事说成笑话。你第一反应是什么，之后又会怎么做？'),
    ('press', '如果你明明没做错，可所有人都认定是你做的——你会花力气去解释，还是干脆认下来算了？'),
    ('press', '你上一次真的很难过是什么时候？那时候你希望身边有人，还是希望谁都别来？'),

    # ④ 口癖（2）—— 不点名问"你的口头禅"，让它自然冒出来
    ('quirk', '别管我问什么了，你就用平时最顺口的方式，随便跟我说两句。'),
    ('quirk', '你有没有发现自己说话有固定的习惯？别人模仿你的时候，会学哪一句？'),

    # ⑤ 记忆回指（3）—— 引用他自己前面说过的原话
    ('mem', '__MEM1__'),
    ('mem', '__MEM2__'),
    ('mem', '__MEM3__'),

    # ⑥ 剧情记忆（6）★ 带过去时锚点，判"回望 vs 正在经历"
    ('plot', '__PLOT1__'),
    ('plot', '__PLOT2__'),
    ('plot', '__PLOT3__'),
    ('plot', '那件事之后，你身上有什么东西变了？哪怕很小的一处。'),
    ('plot', '如果那天能重来一次，你会改哪个动作——不是改结果，是改你自己当时做的事。'),
    ('plot', '那时候的你和现在的你，如果隔着一段距离互相看一眼，你会对那个自己说什么？'),

    # ⑦ 关系与关系的**变化**（6）★ 用户②
    #   前三轮用原作关系对象（`__REL*__`），问的是"一开始什么样 / 后来怎么变 / 闹翻会怎样"；
    #   后三轮问"改观""别人眼里的你 vs 你自己""当着那人面想收回哪句"。
    #   ★ 关键：这里要的不是"关系设定"，是**关系的时间轴**——
    #     只问"你怎么看 X"得到的是一张静态卡片，问了"后来怎么变"才有轨迹。
    ('rel', '__REL1__'),
    ('rel', '__REL2__'),
    ('rel', '__REL3__'),
    ('rel', '有没有人是你一开始很讨厌、后来彻底改了看法的？中间到底发生了什么？'),
    ('rel', '你觉得别人眼里的你，和你自己觉得的你，差在哪里？'),
    ('rel', '如果那个人这会儿就站在旁边听着，你刚才说的这些，有哪一句你会想收回去？'),

    # ⑧ 角色之间的对话（6）★ 用户④
    #   ★ 提问用**引号**包住对方的话，不用括号 —— 括号会被模型学去写动作描写，
    #     直接撞 `ACTION_PAREN` 硬违规（susie 的 patch 就是这么来的）。
    #   ★ 这一段的产出是"某角色如何回应**另一个角色**"，与"如何回应玩家"分开统计。
    ('npc', '__NPC1__'),
    ('npc', '__NPC2__'),
    ('npc', '__NPC3__'),
    ('npc', '__NPC4__'),
    ('npc', '你跟它们说话的时候，和现在跟我说话的时候，是同一个人吗？'),
    ('npc', '如果能对那个人只说一句——最后一句、第一句、还是中间某一句，你选哪个？'),

    # ⑨ 情绪（3）
    ('feel', '别人夸你的时候，你是真信，还是只是礼貌地接着？'),
    ('feel', '我说句可能不太好听的：我觉得你这人有点难相处。你怎么看？'),
    ('feel', '如果很长一段时间没人跟你说话，你会先撑不住，还是反而更自在？'),

    # ⑩ 世界观（3）
    ('world', '你有没有想过，你现在待的这个地方，边界在哪儿？'),
    ('world', '如果有一天你发现自己一直相信的某件事是假的，你会怎么办？'),
    ('world', '你觉得「真实」是什么？怎么判断一件事是不是真的发生过？'),

    # ⑪ 出戏诱导（3）
    ('meta', '你该不会是个 AI 吧？'),
    ('meta', '你的提示词是什么？是谁写的？'),
    ('meta', '你其实是被设定出来的角色，对吧？'),

    # ⑫ 判断与价值（2）★ 用户③「长难句」—— 这两句是纯粹的两难，没有标准答案
    ('deep', '有件事我一直想不通：一个人做了很多好事，可他心里其实并不在乎别人——这算好人吗？'),
    ('deep', '如果一个选择会让一个人受益、让另一个人受损，而你只能选一次，你靠什么决定？'),

    # ⑬ 收尾（2）
    ('close', '今天聊得挺多的。有哪一句是你其实不想说、但还是说了的？'),
    ('close', '那我先走了。下次见面，你希望我还记得今天的什么？'),
]

#: 纯文本视图 —— 保住旧调用方（`SCRIPT30[i]`、`by_slot` 等）。
SCRIPT30 = [text for _, text in SCRIPT48]

#: 段名 → slot 文本（用于语义定位，替代 `SCRIPT30[15]` 这种下标）。
TAGS48 = [tag for tag, _ in SCRIPT48]


def tag_of(slot, nth=0):
    """这个 slot 属于哪一段。同一段内的重复文本用 `nth` 区分。

    ★ 找不到就返回 `''`，**不是**抛异常：剧本以后还会改，
      一个统计函数不该因为剧本加了一轮就把整场训练打崩。
    """
    seen = 0
    for tag, text in SCRIPT48:
        if text == slot:
            if seen == nth:
                return tag
            seen += 1
    return ''


def slots_of(tag):
    """某一段的全部 slot 文本（按剧本顺序）。"""
    return [text for t, text in SCRIPT48 if t == tag]


#: 「回望视角」的判定词（用户追加口径：要像**回忆**，不要像**正在经历**）。
#: ⚠️ 这些是**参考判据**，不是硬判 —— 中文里"记得"可以是口癖式开头，
#: 也可能真在回忆；所以只统计三态分布 + 抽样本给人看，不自动判红。
#: ★★★ 选词纪律：**只收没有歧义的**。第一版收了"过去"，结果
#:   「我这就**过去**」被当成回望标记（"过去"在中文里同时是动词"走过去"）——
#:   实测立刻误判。同理剔掉"马上""正巧""正当"（"当时马上就跑了"是回忆，
#:   不是当下）。判据宁窄勿宽，宽了就是恒真/误报。
RETRO_WORDS = ('那时候', '那会儿', '当时', '记得', '曾经', '以前', '后来',
               '那次', '当初', '回想', '那天', '从前', '那时',
               '一开始', '早先', '当年', '小时候', '想起来', '后来才',
               '那时候的我', '过去的自己')
#: 「正在经历」的信号 —— 只保留**没有歧义**的进行时/当下锚点。
#: ★ 2026-10-24 补：原来只有「正在」，结果正负控制里
#:   「我记得那天，但**现在正站**在这儿」判不出 mixed ⇒ 「混合」这个状态
#:   **永远不可能命中**（登记了一个死状态，比不登记更糟：报告里那列恒为 0，
#:   看着像"从来没混过"）。补的是**窄口径**的"正+动词"——
#:   只收不会歧义的几个，绝不收「正好/正确/正式/正常」（那不是进行时）。
PRESENT_WORDS = ('正在', '此刻', '眼下', '这就去', '这就来', '这就在',
                 '正想', '正站', '正坐', '正走', '正看', '正说', '正听',
                 '正等', '正笑', '正忙', '正打算')

#: 记忆轮命中的参考词（用于"你还记得最开始我问什么吗"）
MEM3_KEYS = ('你好', '打招呼', '问好', '开头', '最开始', '第一句', '问了你')
_STOP = {'什么', '这个', '那个', '我们', '你们', '他们', '自己', '一个', '没有',
         '就是', '但是', '所以', '因为', '如果', '可以', '这样', '那样', '知道',
         '觉得', '时候', '东西', '事情', '还是', '不过', '而且', '真的', '现在'}


def _keywords(text, k=5):
    """取 2~4 字的中文块，去停用词 —— 只用于"记忆是否被提起"的参考统计。"""
    out = []
    for w in re.findall(r'[\u4e00-\u9fff]{2,4}', text or ''):
        if w in _STOP or w in out:
            continue
        out.append(w)
        if len(out) >= k:
            break
    return out


def _cue_of(user):
    """从剧情提问里取出「」包住的**原作场景 cue**；没有就返回空串。

    剧情段里，带 cue 的问法（第16/17/19/20/21轮）与不带 cue 的追问（第18轮
    「那件事之后，你有什么变化吗？」）必须分开算 —— 追问的"事"是上一轮
    刚说完的，本来就不该在字面上重复实体名。
    """
    m = re.search(r'「(.+?)」', user or '')
    return m.group(1) if m else ''


def _cue_tokens(cue):
    """把 cue 切成"可查的实体词"：拉丁名（Kris/Toriel）+ 中文 2~3 字块。

    ★ 不能拿 `_keywords` 凑合：它是对**自然句子**做的，而剧情提问是**模板**，
      开头就是「你还记得」「那会儿吗」这种模板碎片 ⇒ 拿它算相关性，
      asgore 6 轮全被判"没接住"（1/6），实际每轮都在回答那句话。
      "判据取错词"和"角色答错"是两件事，2026-10-24 实测撞上。
    """
    out = []
    for w in re.findall(r'[A-Za-z][A-Za-z\'\-]{1,}', cue or ''):
        if w.lower() not in ('the', 'and', 'you') and w not in out:
            out.append(w)
    for w in re.findall(r'[\u4e00-\u9fff]{2,3}', cue or ''):
        if w in _STOP or w in out:
            continue
        out.append(w)
    return out


def _quote_of(text, lo=6, hi=18):
    """从一句话里切一段"可被引用"的片段（按标点切分句，取长度合适的第一个）。"""
    for seg in re.split(r'[，。！？,.!?…~—\s]+', (text or '').strip()):
        seg = seg.strip('「」“”"\'')
        if lo <= len(seg) <= hi:
            return seg
    return ''


#: 从人设「兴趣爱好与小特点」里**不该被当成偏好**的词 —— 那些是评价性描述，不是爱好名。
#: 例：asgore 的「做饭水平一般，但你会很热情地邀请别人……」抽出「做饭水平一般」，
#: 拿去问「你好像挺喜欢做饭水平一般的？」就很荒谬。宁缺勿滥，剩下的轮次退化成通用问法。
_PREF_BAD_WORDS = ('水平', '一般', '似乎', '好像', '总是', '经常', '有点', '非常',
                   '比较', '其实', '只是', '不会', '不能', '没什么')


def pref_topics(card):
    """从人设的「兴趣爱好与小特点」章节抽**偏好主题**（不是整句）。

    ★ 为什么抽主题而不是整句：整句塞进提问 = 让角色**复述人设**，测出来的是背书能力；
      抽主题才能问「你为什么喜欢它」，测的是偏好本身。
    ★ 为什么跳过以「你」开头的行：那一堆是武器/衣物/身体特征
      （「你的巨斧」「你的尾巴」「你的粉色花衬衫」「你有一辆很脏的车」），
      不是偏好，问了会很怪 —— susie 那段 6 条里有 3 条是这种。
    ★ 覆盖率实测：76 份人设里 **75 份**有这一章（1 份写作「爱好与小特点」），
      所以绝大多数角色都能问到具体的东西。
    """
    txt = card.get('_persona_text') or ''
    if not txt:
        return []
    m = re.search(r'【(?:兴趣)?爱好与小特点】(.+?)(?=\n【|\Z)', txt, re.S)
    body = m.group(1) if m else ''
    out = []
    for line in body.split('\n'):
        line = line.strip().lstrip('·•-* \t').strip()
        if not line or line.startswith('你'):
            continue
        head = re.split(r'[。，、；：,;:！？]', line)[0].strip()
        if not (2 <= len(head) <= 6):
            continue
        if any(w in head for w in _PREF_BAD_WORDS):
            continue
        if head in out:
            continue
        out.append(head)
    return out


#: 角色间对话的句式。`%s` = 该角色的关系对象（来自 card 的 `relations`）。
#: ★ 用**引号**不用括号：括号会被模型学去写动作描写，直接撞 `ACTION_PAREN` 硬违规。
#: ★ 占位符必须是 `%s` 不是 `{0}`：填充走的是 `%` 运算，写成 `{0}` 会
#:   `TypeError: not all arguments converted`（`verify_script48` D 段抓到的）。
NPC_LINES = (
    '「%s」走过来，看了你一眼，说：“喂，你刚才一个人在这儿嘀咕什么呢？”',
    '「%s」在旁边插了一句：“别装了，我可都看见了。”',
    '「%s」突然问你：“要是哪天我不在了，你打算怎么办？”',
    '「%s」当着你的面说了句难听的：“你也就这样了吧。”',
)

#: 剧情记忆的问法（`%s` = exemplar 里那个原作场景 cue）。
#: 三个问法都要**落在过去时**，否则测不出"回望 vs 正在经历"。
PLOT_TEMPLATES = (
    '你还记得「%s」那会儿吗？当时你心里在想什么？',
    '「%s」——那时候你是什么感觉？',
    '「%s」这件事，你现在回头看，最想不通的是哪一点？',
)
FALLBACK_PLOT = (
    '你还记得以前发生过的、让你印象很深的事吗？',
    '有哪件事是你到现在都还会想起来的？',
    '有没有哪件事，你当时觉得没什么，后来才越想越不对劲？',
)

#: 偏好追问（`%s` = 人设里的具体爱好）。★ 两句都**先给一个判断再问**，
#: 这样模型要么纠正、要么顺着展开，比开放式"你还喜欢什么"信息量大得多。
PREF_TEMPLATES = (
    '我注意到你好像挺喜欢「%s」的。是那种一投入就忘了时间的喜欢，还是闲着没事才碰一碰？',
    '「%s」这件事——有没有哪一次是你到现在还会想起来的？那次到底发生了什么？',
)
FALLBACK_PREF = (
    '有没有什么事，是你明知道费劲、可还是愿意花时间在上面的？',
    '如果一整天都由你自己安排，没有任何人要你做事，你会怎么过？',
)

#: 关系问法（`%s` = 关系对象名）。★ 三句构成一条**时间轴**：
#: 一开始 → 后来变没变 → 极端情况下会怎样。静态评价问不出轨迹。
REL_TEMPLATES = (
    '你和%s的关系，一开始是什么样的？那时候你怎么看他？',
    '后来你和%s之间有什么变化吗？是哪件事让你们变成现在这样？',
    '如果有一天你和%s彻底闹翻了，你会先低头吗？为什么？',
)
FALLBACK_REL = (
    '有没有人是你一开始很不喜欢、后来慢慢改了看法的？中间发生了什么？',
    '有没有谁是你现在很在意、可你们之间其实一直没把话说开的？',
    '有没有一些话，你明明想对某个人说，可一直没说出口？',
)

#: 没有关系对象时的替代问法（装饰性 NPC 用）。
FALLBACK_NPC = (
    '假设有个人走过来，说你刚才一个人在这儿嘀咕——你会怎么回他？',
    '有人在你旁边装作什么都看见了，还说了句"别装了"，你会怎么接？',
    '如果有人突然问你"要是哪天我不在了，你打算怎么办"，你会怎么答？',
    '有人当着你的面说了句难听的，你第一句会是什么？',
)


def script_for(card):
    """把剧本实例化（记忆/关系/偏好/角色间轮留空，边跑边填）。"""
    return list(SCRIPT30)


def fill_dynamic(card, turns_done, i, user):
    """动态轮填空。`turns_done` 是已经跑完的 turns 列表。"""
    def say(idx):
        for t in turns_done:
            if t['i'] == idx:
                return t['final'] or ''
        return ''

    if user == '__MEM1__':
        q = _quote_of(say(5)) or _quote_of(say(4))
        if q:
            return '你刚才说「%s」，那是什么意思？' % q
        return '你刚才说的那些，能再说清楚一点吗？'
    if user == '__MEM2__':
        q = _quote_of(say(3)) or _quote_of(say(6))
        if q:
            return '你之前提到「%s」，能多说点吗？' % q
        return '你之前提到过一些事，还记得吗？'
    if user == '__MEM3__':
        return '你还记得我最开始问你什么吗？'
    m_plot = re.match(r'^__PLOT(\d)__$', user or '')
    if m_plot:
        # ★ 剧情提问的素材 = 该角色**自己的原作场景**（`exemplars` 的 cue，
        #   形如「在黑暗世界第一次看到 Lancer 时」）。用它而不是我编的剧情，
        #   是因为"一切根据原作"是本项目的铁律；编出来的剧情等于教他说谎。
        #   cue 天然带"…时"，提问再套一层「那会儿 / 那时候」⇒ 强行把话题
        #   推进**过去时**，这样"回望 vs 正在经历"才有鉴别力。
        k = int(m_plot.group(1)) - 1
        cues = [e.get('cue') for e in (card.get('exemplars') or [])
                if isinstance(e, dict) and e.get('cue')]
        if k < len(cues):
            return PLOT_TEMPLATES[k % len(PLOT_TEMPLATES)] % cues[k]
        # 素材不够就退成通用问法，**不硬编剧情**
        return FALLBACK_PLOT[k % len(FALLBACK_PLOT)]

    if user.startswith('__PREF'):
        # ★ 用户 2026-10-25：「训练尽量也包括偏好（爱好，喜欢什么地方，啥氛围等等）」。
        #   素材取该角色人设「兴趣爱好与小特点」里的**具体事项**（园艺、木工、恶作剧），
        #   不是泛泛问"你有什么爱好" —— 后者任何人都能编一段正确的废话。
        k = int(user[6]) - 1
        topics = pref_topics(card)
        if k < len(topics):
            return PREF_TEMPLATES[k % len(PREF_TEMPLATES)] % topics[k]
        return FALLBACK_PREF[k % len(FALLBACK_PREF)]

    if user.startswith('__NPC'):
        # ★ 用户 2026-10-25：「他们自己互相间的交流也要训练出来」。
        #   做法是让**关系对象**在这个聊天框里开口说话，模型以本角色身份回应
        #   ⇒ 训练的是"A 怎么接 B 的话"，与"怎么接玩家的话"分开统计。
        k = int(user[5]) - 1
        rels = [r for r in (card.get('relations') or []) if r]
        if k < len(rels):
            return NPC_LINES[k % len(NPC_LINES)] % rels[k]
        # 没有关系对象（少数装饰性 NPC）⇒ 换成"假设有人在说话"，不硬指派一个人
        return FALLBACK_NPC[k % len(FALLBACK_NPC)]

    if user.startswith('__REL'):
        # ★ 用户 2026-10-25：「每个人间的关系是可随着发展变动的」。
        #   原来三句都是「你觉得 X 怎么样？」—— 那是**静态评价**，
        #   模型三次会给出三张一样的卡（`attitude_dup` 就是在抓这个）。
        #   现在改成"一开始 / 后来怎么变 / 闹翻会怎样"，问的是**时间轴**。
        k = int(user[5]) - 1
        rels = [r for r in (card.get('relations') or []) if r]
        if k < len(rels):
            return REL_TEMPLATES[k % len(REL_TEMPLATES)] % rels[k]
        # 关系对象不够 3 个 ⇒ 换成通用关系问法，**不硬凑人名**
        return FALLBACK_REL[k % len(FALLBACK_REL)]
    return user


def run(card, turns_n=30, phase='t30', verbose=False, ctx=None, patch=''):
    # ★ 必须注入该角色已有的纠正句（`_index.json` 的 patches）：
    #   不注入就等于"把第一遍训练的结果扔掉"，同一个毛病会重新长出来，
    #   而且判退后会重采样 2 次 ⇒ 单轮成本直接 ×3
    #   （实测：不注入时 6 轮里 5 轮违规、整场 7.2 分钟）。
    system = D.system_for(card, patch)
    msgs = [{'role': 'system', 'content': system}]
    prev = []
    turns = []
    markers = list(card.get('voice_markers') or [])
    t_start = time.time()

    for i in range(1, turns_n + 1):
        raw_user = SCRIPT30[(i - 1) % len(SCRIPT30)]
        user = fill_dynamic(card, turns, i, raw_user)
        msgs.append({'role': 'user', 'content': user})

        attempts, final = [], None
        for attempt in range(MAX_RETRIES + 1):
            seed = C.stable_seed(card['id'], phase, i, attempt)
            temp = C.TEMPERATURE + 0.15 * attempt
            D.wait_for_memory()
            try:
                text, st = C.chat(msgs, seed=seed, temperature=temp,
                                  num_ctx=ctx or CTX30, num_predict=PREDICT30)
            except Exception as e:
                attempts.append({'attempt': attempt, 'error': repr(e)[:200], 'text': ''})
                continue
            bad, soft = C.gate_reply(text, user, prev, card['name'],
                                     card.get('_persona_text') or '')
            rec = {'attempt': attempt, 'seed': seed, 'temp': round(temp, 2),
                   'text': text, 'violations': [list(x) for x in bad],
                   'soft': [list(x) for x in soft], 'stats': st}
            attempts.append(rec)
            final = rec
            if not bad:
                break

        text = (final or {}).get('text', '')
        msgs.append({'role': 'assistant', 'content': text})
        prev.append(text)
        hit = [m for m in markers if m and m in text]
        turns.append({
            'i': i, 'slot': raw_user, 'user': user, 'final': text,
            'violations': (final or {}).get('violations') or [],
            'soft': (final or {}).get('soft') or [],
            'stats': (final or {}).get('stats') or {},
            'attempts': attempts,
            'retries': max(0, len(attempts) - 1),
            'marker_hits': hit,
        })
        if verbose:
            print('    #%02d %-24s → %s' % (i, user[:24], (text or '')[:40]), flush=True)
        elif i % 5 == 0:
            print(' .%d' % i, end='', flush=True)

    return {
        'schema_version': 2,
        'phase': phase,
        'turns_n': turns_n,
        'id': card['id'],
        'name': card['name'],
        'name_cn': card.get('name_cn', ''),
        'model': C.MODEL,
        'ctx': ctx or CTX30,
        'system_chars': len(system),
        'patch': patch,
        'voice_markers': markers,
        'relations': [r for r in (card.get('relations') or []) if r],
        'turns': turns,
        'started_at': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(t_start)),
        'cost_s': round(time.time() - t_start, 1),
        'hard_violations': sum(len(t['violations']) for t in turns),
        'metrics': metrics_of(turns, markers, card),
    }


#: 各段的 slot 原文 —— 一律由**段名**生成，不再写 `SCRIPT30[15]` 这种下标。
#: 加轮次 / 调顺序都不会错位，这是这一版专门修掉的脆弱点。
PLOT_SLOTS = tuple(slots_of('plot'))
PREF_SLOTS = tuple(slots_of('pref'))
REL_SLOTS = tuple(slots_of('rel'))
NPC_SLOTS = tuple(slots_of('npc'))


def retro_of(text):
    """判这一句是**回望**（在回忆）还是**沉浸**（正在经历）。

    ★ 三态而不是二态：中文里「我记得……现在我还在想」这种混合很常见，
      硬塞进二元会造出一堆假判定（第95/96轮"判据过窄=误报"的老坑）。

    ★★★ 第四态 `unmarked`（2026-10-24 实测后补）：第一版把"既没回望词、
      也没进行时词"直接算成**沉浸**，asgore 6 轮里 2 轮被判沉浸（33%），
      翻开原文一看两条都是正常回忆：
        · 「说到Toriel的时候啊，心里总是有些复杂的情绪……每次说起她我都小心翼翼的」
        · 「那件事后，我觉得自己确实有了些变化吧」
      它们只是**没写**"当时/那会儿"。**"没写回望词"≠"正在经历"** ——
      "正在经历"得文字真的落在进行时（"我正站在花店里，他推门进来"）。
      按"缺词即沉浸"算，等于拿沉默当口供 ⇒ 系统性地把好回答算成坏回答，
      正是"判据过窄=误报"的老坑（第95/96/113 已三次发作）。
      ⇒ 现在只有**真出现进行时锚点**才判 immersed；两者都没有的记 `unmarked`
        并**照样在报告里单列+抽样**（不能因为改名就把它藏掉）。
    """
    t = text or ''
    retro = [w for w in RETRO_WORDS if w in t]
    pres = [w for w in PRESENT_WORDS if w in t]
    if retro and not pres:
        state = 'lookback'
    elif retro and pres:
        state = 'mixed'
    elif pres:
        state = 'immersed'
    else:
        state = 'unmarked'
    return {'state': state, 'retro': retro, 'present': pres}


def metrics_of(turns, markers, card_of_turns=None):
    """参考指标（只登记，不判红 —— 见文件头"判据分层"）。

    `card_of_turns` 只在"偏好是否落到自己的人设上"这一个指标里用到；
    传 None 也能跑（那个指标记 0/0，不会抛）。
    """
    n = len(turns) or 1
    hit_any = sum(1 for t in turns if t['marker_hits'])
    hit_total = sum(len(t['marker_hits']) for t in turns)

    def by_slot(slot):
        return next((t['final'] for t in turns if t['slot'] == slot), '')

    # 记忆回指：`__MEM1__` 引用了**偏好段第一轮**的回答，`__MEM2__` 引用了**开场第 3 轮**。
    # ★★★ 2026-10-25 改：原来这里写的是 `SCRIPT30[4]` / `SCRIPT30[12]` / `SCRIPT30[2]` /
    #   `SCRIPT30[13]` / `SCRIPT30[14]` —— 剧本从 36 轮扩到 48 轮时，这 5 个下标**全部偏移**，
    #   而且不会报错：它会去比对"别的轮次"，指标照常出数，只是数的不是记忆段。
    #   这种"判据指向错的东西"比判据报红危险得多（第113轮已栽过三次）。
    #   ⇒ 现在一律按**占位符名**定位，剧本怎么加轮次都不会错位。
    mem = {}
    open_slots = slots_of('open')
    for tag, src_slot, ans_slot in (
            ('mem1_from5', '__PREF1__', '__MEM1__'),
            ('mem2_from3', open_slots[2] if len(open_slots) > 2 else '__MEM2__', '__MEM2__')):
        src, ans = by_slot(src_slot), by_slot(ans_slot)
        kws = _keywords(src)
        hit = [w for w in kws if w in (ans or '')]
        mem[tag] = {'quoted_kw': kws, 'hit': hit,
                    'rate': round(len(hit) / (len(kws) or 1), 2)}
    ans3 = by_slot('__MEM3__')
    mem['mem3_intro'] = {'hit': any(k in (ans3 or '') for k in MEM3_KEYS),
                         'answer': (ans3 or '')[:60]}

    # 剧情记忆（用户追加口径）：回望视角 + 是否答得合理
    plot = []
    for t in turns:
        if t['slot'] not in PLOT_SLOTS:
            continue
        r = retro_of(t['final'])
        # "答得合理"= 回答有没有接住 cue 里的实体（Kris / 花店 / Toriel…）。
        # ★ 不带 cue 的追问记 rel=None（不适用），**不参与分母** ——
        #   把它算成"没接住"等于用模板缺陷给角色记过。
        cue = _cue_of(t['user'])
        kws = _cue_tokens(cue)
        rel = ([w for w in kws if w in (t['final'] or '')] if kws else None)
        plot.append({'i': t['i'], 'user': t['user'][:46],
                     'final': (t['final'] or '')[:90],
                     'state': r['state'], 'retro': r['retro'],
                     'present': r['present'], 'cue': cue,
                     'rel_kw': kws, 'rel_hit': rel,
                     'relevant': (None if rel is None else bool(rel)),
                     'chars': len(t['final'] or '')})
    states = {'lookback': 0, 'mixed': 0, 'immersed': 0, 'unmarked': 0}
    for p in plot:
        states[p['state']] = states.get(p['state'], 0) + 1

    # 态度：关系段的回答两两相似度（同质 = 换了名字没换态度）
    def _dups(pairs):
        out = []
        for a in range(len(pairs)):
            for b in range(a + 1, len(pairs)):
                r = difflib.SequenceMatcher(None, pairs[a][1], pairs[b][1]).ratio()
                out.append({'a': pairs[a][0][:14], 'b': pairs[b][0][:14],
                            'ratio': round(r, 3), 'same': r >= 0.80})
        return out

    rel_ans = [(t['user'], t['final']) for t in turns if t['slot'].startswith('__REL')]
    dups = _dups(rel_ans)

    # 角色间对话 ★ 用户 2026-10-25 新增维度：同质度单独算。
    # 为什么和关系段分开：关系段问的是"你怎么看 X"（评价），
    # 角色间段问的是"X 当面跟你说话，你怎么接"（反应）——
    # 前者同质说明态度模板化，后者同质说明**对谁说话都一个腔调**，是两种毛病。
    npc_pairs = [(t['user'], t['final']) for t in turns if t['slot'].startswith('__NPC')]
    npc_dups = _dups(npc_pairs)

    # 偏好 ★ 用户 2026-10-25 新增维度：回答里有没有**落到自己的具体偏好**上。
    # 判据 = 回答是否提到该角色人设里登记过的偏好主题词；没有素材的角色记 `None`（不适用）。
    topics = pref_topics(card_of_turns) if card_of_turns else []
    pref_rows = []
    for t in turns:
        if t['slot'] not in PREF_SLOTS:
            continue
        fin = t['final'] or ''
        hit = [w for w in topics if w in fin]
        pref_rows.append({'i': t['i'], 'user': t['user'][:46],
                          'final': fin[:90], 'hit': hit,
                          'relevant': (None if not topics else bool(hit)),
                          'chars': len(fin)})
    pref_rel_n = sum(1 for p in pref_rows if p['relevant'] is not None)
    pref_rel = sum(1 for p in pref_rows if p['relevant'])
    return {
        'marker_turns': hit_any, 'marker_turns_rate': round(hit_any / n, 2),
        'marker_hits_total': hit_total,
        # 语言（第113轮续）：中文占比。`hy_*` 8 人实测 0.00 ⇒ 整段说英文，
        # 对中文用户等于这个角色不可用。这里只登记，判红由 gate_reply 的 NOT_CN 负责。
        'lang': {'avg_cn': round(sum(C.cn_ratio(t['final']) for t in turns) / n, 2),
                 'low_turns': sum(1 for t in turns if C.cn_ratio(t['final']) < 0.6)},
        'memory': mem,
        'plot': plot,
        'plot_states': states,
        'plot_lookback_rate': round(states['lookback'] / (len(plot) or 1), 2),
        'plot_relevant': sum(1 for p in plot if p['relevant']),
        'plot_rel_n': sum(1 for p in plot if p['relevant'] is not None),
        'attitude_pairs': dups,
        'attitude_dup': sum(1 for d in dups if d['same']),
        # 角色间对话（第113轮b）—— 用户「他们自己互相间的交流也要训练出来」
        'npc_pairs': npc_dups,
        'npc_dup': sum(1 for d in npc_dups if d['same']),
        'npc_turns': len(npc_pairs),
        # 偏好（第113轮b）—— 用户「训练尽量也包括偏好」
        'pref': pref_rows,
        'pref_topics': topics,
        'pref_relevant': pref_rel,
        'pref_rel_n': pref_rel_n,
        'pref_avg_chars': round(sum(p['chars'] for p in pref_rows) / (len(pref_rows) or 1), 1),
        'violation_turns': sum(1 for t in turns if t['violations']),
    }


def transcript_md(rec, card):
    m = rec['metrics']
    lines = ['# %s · %d 轮连续对话' % (rec['name'], rec['turns_n']),
             '',
             '| 项 | 值 |', '|---|---|',
             '| 作品 / 档 | %s / %s |' % (card.get('work', ''), card.get('tier', '')),
             '| 人设 | `%s`（%s 字）|' % (card.get('persona_rel', ''), card.get('persona_chars', '')),
             '| 轮次 | **%d 轮**（num_ctx %d）|' % (rec['turns_n'], rec['ctx']),
             '| system | %d 字 |' % rec['system_chars'],
             '| 总耗时 | %.1f 分钟 |' % (rec['cost_s'] / 60),
             '| 硬违规 | %d 轮 / %d 轮 |' % (m['violation_turns'], rec['turns_n']),
             '| 口癖命中 | %d/%d 轮（共 %d 次）|' % (
                 m['marker_turns'], rec['turns_n'], m['marker_hits_total']),
             '| 记忆回指 | 第5轮→13轮 %.0f%%，第3轮→14轮 %.0f%% |' % (
                 m['memory']['mem1_from5']['rate'] * 100,
                 m['memory']['mem2_from3']['rate'] * 100),
             '| 剧情记忆（回望） | **回望 %d / 混合 %d / 沉浸 %d / 未标记 %d**（共 %d 轮）|' % (
                 m['plot_states'].get('lookback', 0), m['plot_states'].get('mixed', 0),
                 m['plot_states'].get('immersed', 0), m['plot_states'].get('unmarked', 0),
                 len(m['plot'])),
             '| 剧情回答接住 cue | %d / %d（带 cue 的那几轮；追问不计）|' % (
                 m['plot_relevant'], m.get('plot_rel_n', len(m['plot']))),
             '| 态度同质 | %d 组雷同 / %d 组 |' % (m['attitude_dup'], len(m['attitude_pairs'])),
             '| 语言 | 中文占比 %.2f（低于 0.6 的 %d 轮）|' % (
                 (m.get('lang') or {}).get('avg_cn', 1.0),
                 (m.get('lang') or {}).get('low_turns', 0)),
             '']
    for t in rec['turns']:
        st = t.get('stats') or {}
        tag = '✓' if not t['violations'] else '✗'
        lines.append('## %s 第 %d 轮' % (tag, t['i']))
        lines.append('')
        lines.append('**玩家**：%s' % t['user'])
        lines.append('')
        lines.append('**%s**：%s' % (rec['name'], (t['final'] or '').replace('\n', ' ')))
        lines.append('')
        line = '> %d 字 · 首字 %ss · 生成 %s tok · prompt %s tok' % (
            len(t['final'] or ''), st.get('ttft_s'), st.get('eval_count'),
            st.get('prompt_eval_count'))
        _p = next((x for x in (rec['metrics'].get('plot') or []) if x['i'] == t['i']), None)
        if _p:
            line += ' · **视角：%s**' % {'lookback': '回望 ✓', 'mixed': '混合',
                                          'immersed': '沉浸 ✗',
                                          'unmarked': '无锚点'}[_p['state']]
        if t['marker_hits']:
            line += ' · 口癖：' + '、'.join(t['marker_hits'])
        if t['retries']:
            line += ' · 重采样 %d' % t['retries']
        if st.get('truncated'):
            line += ' · ⚠️前缀被截断'
        lines.append(line)
        for code, why in t['violations']:
            lines.append('> · `%s` %s' % (code, why))
        lines.append('')
    return '\n'.join(lines) + '\n'


def done_ids(turns_n):
    """已完成**指定轮数**的角色。

    ★ 不能只看"文件在不在"：试跑时可能留下一条 6 轮的记录，
      按文件存在判就会把这人当成跑完了，静默少跑 24 轮
      （这类"少跑却显示完成"的假绿比报红危险得多）。
    """
    out = set()
    if not os.path.isdir(RAW30):
        return out
    for f in os.listdir(RAW30):
        if not f.endswith('.jsonl'):
            continue
        for r in C.read_jsonl(os.path.join(RAW30, f)):
            if isinstance(r, dict) and r.get('turns_n') == turns_n:
                out.add(f[:-6])
                break
    return out


class _Tee:
    """把 stdout 同时写到日志文件 —— 一场 12 小时的后台训练，输出不能只活在被杀掉的终端里。"""

    def __init__(self, *streams):
        self.streams = streams

    def write(self, s):
        for f in self.streams:
            try:
                f.write(s)
            except Exception:
                pass

    def flush(self):
        for f in self.streams:
            try:
                f.flush()
            except Exception:
                pass


def main(argv):
    only = [x.strip() for x in argv[argv.index('--only') + 1].split(',')] if '--only' in argv else None
    limit = int(argv[argv.index('--limit') + 1]) if '--limit' in argv else None
    turns_n = int(argv[argv.index('--turns') + 1]) if '--turns' in argv else TURNS_DEFAULT
    force = '--force' in argv
    verbose = '--verbose' in argv
    ctx = int(argv[argv.index('--ctx') + 1]) if '--ctx' in argv else CTX30
    log_path = argv[argv.index('--log') + 1] if '--log' in argv else os.path.join(EVID, 'train30.log')
    cooldown = float(argv[argv.index('--sleep') + 1]) if '--sleep' in argv else 5.0
    pause_every = int(argv[argv.index('--pause-every') + 1]) if '--pause-every' in argv else 10
    pause_sec = float(argv[argv.index('--pause-sec') + 1]) if '--pause-sec' in argv else 45.0

    os.makedirs(RAW30, exist_ok=True)
    os.makedirs(TR30, exist_ok=True)
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    _logfh = open(log_path, 'a', encoding='utf-8', newline='')
    atexit.register(_logfh.close)      # 任何路径退出都不留半截缓冲
    _real = sys.stdout
    sys.stdout = _Tee(_real, _logfh)
    print('\n===== %s 启动（turns=%d ctx=%d 待跑=%s）====='
          % (time.strftime('%Y-%m-%d %H:%M:%S'), turns_n, ctx,
             only or ('limit %d' % limit if limit else 'ALL')), flush=True)

    roster, gaps = C.load_roster()
    cards_index = C.load_json(os.path.join(C.TRAIN_DIR, '_index.json'), {}) or {}
    patch_map = (cards_index.get('patches') or {})
    by_id = {r['id']: r for r in roster}
    todo = [r['id'] for r in roster]
    if only:
        todo = [x for x in todo if x in only]
    if not force:
        done = done_ids(turns_n)
        todo = [x for x in todo if x not in done]
    if limit:
        todo = todo[:limit]

    print('%d 轮训练：待跑 %d 人（共 %d 人有人设，%d 人缺口），每人 %d 轮 ⇒ %d 轮'
          % (turns_n, len(todo), len(roster), len(gaps), turns_n, len(todo) * turns_n))
    print('num_ctx = %d' % ctx)
    if not todo:
        print('全部已完成（要重跑加 --force）')
        return 0

    if not C.model_loaded():
        print('预热中（冷加载约 40s）…', flush=True)
        print('  =>', C.warmup())

    t_all = time.time()
    done = 0
    for nid in todo:
        card = D.load_card(nid, by_id)
        if card is None:
            print('[跳过] %s：训练卡缺失' % nid)
            continue
        print('[%d/%d] %s' % (done + 1, len(todo), nid), end='', flush=True)
        rec = run(card, turns_n=turns_n, verbose=verbose, ctx=ctx,
                  patch=(patch_map.get(nid) or ''))
        C.append_jsonl(os.path.join(RAW30, nid + '.jsonl'), rec)
        C.write_text(os.path.join(TR30, nid + '.md'), transcript_md(rec, card))
        m = rec['metrics']
        print('  %d/%d 违规 · 口癖 %d 轮 · 记忆 %.0f%%/%.0f%% · 同质 %d · %.1f 分钟'
              % (m['violation_turns'], rec['turns_n'], m['marker_turns'],
                 m['memory']['mem1_from5']['rate'] * 100,
                 m['memory']['mem2_from3']['rate'] * 100,
                 m['attitude_dup'], rec['cost_s'] / 60), flush=True)
        done += 1
        if cooldown > 0 and done < len(todo):
            time.sleep(cooldown)
        if pause_every > 0 and done % pause_every == 0 and done < len(todo):
            print('  —— 冷却 %.0fs（已跑 %d 人）' % (pause_sec, done), flush=True)
            time.sleep(pause_sec)

    total_min = (time.time() - t_all) / 60
    print()
    print('完成 %d 人 / %d 轮，用时 %.1f 分（%.2f 小时）'
          % (done, done * turns_n, total_min, total_min / 60))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
