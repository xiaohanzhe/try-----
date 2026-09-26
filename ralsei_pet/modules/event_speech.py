# -*- coding: utf-8 -*-
"""事件台词（S7）—— 把"写死的事件台词"分两档。

背景
----
改造前事件台词 100% 写死在代码里：全项目 191 处 `add_dialogue`（`main.py` 131 处），
同一句反复出现（连着摸三次都是「嘿嘿~ 好舒服呀！」）—— 这是"没活人味"最直观的来源。
全量清单见 `code-quality-audit/人味改造-2026-09-18/_evidence/event_lines.txt`（可复算）。

原则（报告 §5 S7）
----
* **短促反应保留罐头**：摔落 / 甩飞 / 摔扁这类要求 0 延迟，而且是物理状态机的输出，
  交模型只会变慢变差。未登记的事件**一律保持改造前行为**（这是"分批迁移"的安全默认）。
* **社交长句走 AI**：被戳/被摸/被喂之后的回应 —— 这些才是"人味"最缺的地方。

为什么纯逻辑单独成模块
----
Qt 事件循环、线程、话题接线全部留在 `main.py`（沿用 H4/H5 的"转发壳 + 宿主 API"口径）：
本模块**不 import 任何项目内模块、不 import Qt** —— 因而不会卷进
`logger_utils → data_store → memory_store` 那条初始化环（第十二轮的教训），
也能在离屏环境里被直接单测。
"""
import random
import re

# 档位：instant = 立刻说罐头（改造前行为）；ai = 先问 AI，超时回落罐头
TIER_INSTANT = "instant"
TIER_AI = "ai"

# 事件台词长度上限（对话链路是 AI_REPLY_MAX_CHARS=80，事件反应必须更短：
# 「一句话的即时反应」超过这个长度就不是反应、是小作文了）
EVENT_MAX_CHARS = 24

# 首句短于此长度时，若**全文**没超上限就整句保留。
# 起因是真机实测：模型回「嗯？发生了什么吗？」，按"取第一句"会被切成 2 个字的
# 「嗯？」—— 对即时反应来说信息量太低，反而不像人说话。
MIN_FIRST_CHARS = 6

# 摸/戳的身体部位（与 main.get_ralsei_body_part 的返回值对齐）
PET_PARTS = ("hair", "ear", "face", "body", "arm", "shoulder")

# ---------------------------------------------------------------------------
# 事件档位登记表
#   **只有登记为 TIER_AI 的事件才走模型**；没登记的一律 TIER_INSTANT
#   （即"没迁移 = 行为与改造前逐字一致"）。新增一批迁移 = 往这里加键。
# ---------------------------------------------------------------------------
EVENT_TIERS = {
    # —— 第一批（S7 batch 1）：鼠标体感交互 + 菜单抚摸/喂食 ——
    "poke_body": TIER_AI,
    "poke_shoulder": TIER_AI,
    "poke_default": TIER_AI,
    "pinch_ear": TIER_AI,       # 长按耳朵
    "pull_arm": TIER_AI,        # 长按手臂
    "press_body": TIER_AI,      # 长按躯干
    "pat_belly": TIER_AI,       # 长按肚子
    "pinch_face": TIER_AI,      # 长按脸
    "pull_shoulder": TIER_AI,   # 长按肩膀
    "double_hair": TIER_AI,     # 双击摸头
    "double_belly": TIER_AI,
    "double_face": TIER_AI,
    "double_shoulder": TIER_AI,
    "double_other": TIER_AI,
    "pet_hair": TIER_AI,
    "pet_ear": TIER_AI,
    "pet_face": TIER_AI,
    "pet_body": TIER_AI,
    "pet_arm": TIER_AI,
    "pet_shoulder": TIER_AI,
    "pet_other": TIER_AI,
    "feed": TIER_AI,
    "pet_menu": TIER_AI,
    # —— 第二批（S7 batch 2）：菜单按钮触发的"开始休息 / 开始进食" ——
    # 与 batch 1 同性质：用户**显式点了按钮**（不是环境自动触发）、台词是纯情绪、
    # 每次点都同一句。它们**不在** main.py 里，而在 modules/energy_hunger.py。
    "rest_start": TIER_AI,      # 用户点"休息"按钮 → energy_hunger.rest()
    "eat_start": TIER_AI,       # 用户点"喂食"按钮 → energy_hunger.eat()
    # —— 第三批（第52轮）：精力/饥饿的**纯情绪**播报 ——
    # 用户口径逐字：「把他内置的对话去掉！！！！……记住，聊天系统全权由7B接管，
    #                别放内置对话了，太木讷了」。
    # 这一批是"每次跨越档位都说同一句"的典型（原本 6 句写死），且**零信息量**
    # （只说"我好累/我好饿/我吃饱了"，不带任何数值）⇒ 全部交给模型。
    # ★ 这一批在 `energy_hunger._speak()` 里一律 **pool=None**（不给内置台词）。
    # ★ 反例（有意**不**迁）：`rest()`/`eat()` 里"已经吃饱/还不累"的**拒绝说明**——
    #   那是"为什么没反应"的唯一提示，属功能反馈，交模型会丢信息
    #   （verify_s7_event_speech 的 C12 锁着这条口径）。
    "energy_critical": TIER_AI,
    "energy_low": TIER_AI,
    "hunger_critical": TIER_AI,
    "hunger_low": TIER_AI,
    "ate_enough": TIER_AI,
    "rested_well": TIER_AI,
    # —— 第四批（第52轮）：躲猫猫的"桌面闸"拒绝说明 ——
    # 用户口径：「他捉迷藏只是用户提出来才能玩而且必须是在桌面上」。
    # 属"为什么没反应"的功能说明 ⇒ 走 AI，但**保留罐头兜底**（同 batch 1/2 口径）。
    "hide_seek_not_desktop": TIER_AI,
    # —— 第五批（第52轮）：一局游戏结束时的道谢 ——
    # 纯情绪、零信息量（原来的「谢谢你陪我玩！」是同一句写死） ⇒ pool=None。
    # ⚠️ 同一次结算里的**比分**与**统计**两句不迁：带数值，属功能播报。
    "game_thanks": TIER_AI,
    # —— 有意保持罐头（TIER_INSTANT）：物理状态机 / 极短拟声 / 连点机关 ——
    "fling": TIER_INSTANT,      # 被甩飞时的「哇啊——！」
    "splat_poked": TIER_INSTANT,  # 摔扁形态下被戳
    "ear_ruffle": TIER_INSTANT,   # 连点 3 下耳朵的机关台词
}

# 事件 → 给模型看的"刚刚发生了什么"（写成括号内的旁白，与 start_autonomous_speech
# 用的是同一套已验证写法：App 把这段当"用户消息"发过去）。
EVENT_DIRECTIVES = {
    "poke_body": "（主人用手指戳了戳你的身体。）",
    "poke_shoulder": "（主人轻轻推了推你的肩膀。）",
    "poke_default": "（主人戳了戳你。）",
    "pinch_ear": "（主人捏着你的耳朵捏了一会儿。）",
    "pull_arm": "（主人拉住你的手臂。）",
    "press_body": "（主人按住你的身体。）",
    "pat_belly": "（主人拍了拍你的肚子。）",
    "pinch_face": "（主人捏了捏你的脸。）",
    "pull_shoulder": "（主人拉住你的肩膀。）",
    "double_hair": "（主人摸了摸你的头。）",
    "double_belly": "（主人用力拍了拍你的肚子。）",
    "double_face": "（主人捏住你的脸。）",
    "double_shoulder": "（主人拍了拍你的肩膀。）",
    "double_other": "（主人双击了你。）",
    "pet_hair": "（主人轻轻抚摸你的头发。）",
    "pet_ear": "（主人轻轻抚摸你的耳朵。）",
    "pet_face": "（主人轻轻抚摸你的脸。）",
    "pet_body": "（主人轻轻抚摸你的身体。）",
    "pet_arm": "（主人轻轻抚摸你的手臂。）",
    "pet_shoulder": "（主人轻轻抚摸你的肩膀。）",
    "pet_other": "（主人轻轻抚摸你。）",
    "feed": "（主人刚喂你吃了东西。）",
    "pet_menu": "（主人从菜单里摸了摸你。）",
    # —— 第二批：菜单按钮触发的开始休息 / 开始进食 ——
    "rest_start": "（主人让你去休息，你乖乖躺下了。）",
    "eat_start": "（主人喂了你东西，你开心地吃了起来。）",
    # —— 第三批（第52轮）：精力/饥饿的纯情绪播报 ——
    # 旁白只描述"状态"，**不写台词示范**（写示例 = 复读机的直接成因，
    # 见 _PROMPT_TAIL 上方那条第十八轮的教训）。
    "energy_critical": "（你累得快走不动了。）",
    "energy_low": "（你开始有些累了。）",
    "hunger_critical": "（你饿得受不了了。）",
    "hunger_low": "（你开始有些饿了。）",
    "ate_enough": "（主人喂你吃了东西，你已经吃饱了。）",
    "rested_well": "（你休息够了，精力恢复了过来。）",
    "hide_seek_not_desktop": "（主人想和你玩躲猫猫，可你们现在不在桌面上。）",
    "game_thanks": "（主人刚陪你玩完一局游戏。）",
    "fling": "（主人把你甩了出去。）",
    "splat_poked": "（你已经摔扁了，主人又戳了你一下。）",
    "ear_ruffle": "（主人连着弹了三次你的耳朵。）",
}

# 提示词尾部：约束形状。**不要**在这里写"示例台词" —— 3B 会把示例当模板照抄
# （第十八轮最重要的教训：往 system 里堆示例口头禅正是复读机的直接成因）。
_PROMPT_TAIL = (
    "用一句话很短地回应（最多 %d 个字），只输出这一句话本身。"
    "不要提问，不要解释，不要加任何标记或旁白。"
) % EVENT_MAX_CHARS


def tier_of(kind):
    """事件档位。**未登记 → TIER_INSTANT**（保持改造前行为，绝不静默改成走 AI）。"""
    return EVENT_TIERS.get(kind, TIER_INSTANT)


def pet_kind(part):
    """把身体部位映射成抚摸事件名（未知部位归到 pet_other，仍是 AI 档）。"""
    return "pet_%s" % (part if part in PET_PARTS else "other")


def build_prompt(kind, detail=""):
    """事件 → 交给模型的"用户消息"（括号旁白 + 形状约束）。"""
    desc = EVENT_DIRECTIVES.get(kind)
    if not desc:
        desc = "（%s）" % (str(detail).strip() or "主人和你互动了一下。")
    return desc + _PROMPT_TAIL


def first_sentence(text, max_chars=EVENT_MAX_CHARS):
    """取第一句并压到 max_chars 内；取不到实义字符就返回空串。

    与 `start_autonomous_speech` 里那段截断同源（那边是内联的），本函数供事件链路用。
    注意：markdown / 自问自答 / 车轱辘话由 `RalseiPet._clean_ai_reply` 在更上游处理，
    这里只管"长度与句数" —— 两层规则的分工不要混（S8 的教训：规则必须单一真源）。
    """
    if not isinstance(text, str):
        return ""
    t = text.strip()
    if not t:
        return ""
    t = t.strip('"\'“”「」『』《》').strip()
    if not t:
        return ""
    # 句末切分：**按偏好顺序**取第一个出现的终结符（优先句号 = 一个完整的想法），
    # 与 start_autonomous_speech 里那段内联截断保持同一口径 ——
    # "第一句"在项目里只能有一份定义，否则两个入口的截断长度会漂移。
    chosen = None
    for sep in ('。', '！', '？', '!', '?', '\n'):
        if sep in t:
            chosen = sep
            break
    if chosen is not None:
        i = t.index(chosen)
        head = t[:i] if chosen == '\n' else t[:i + 1]
        # 首句太短 + 全文放得下 → 整句保留（见 MIN_FIRST_CHARS 的实测起因）
        if len(head.strip()) < MIN_FIRST_CHARS and len(t) <= max_chars:
            pass
        else:
            t = head
    t = t.strip()
    if len(t) > max_chars:
        t = t[:max_chars].rstrip('，,、。！？!?；;：: ')
    t = t.strip()
    if not re.search(r'[0-9A-Za-z\u4e00-\u9fff]', t):
        return ""
    return t


# ---------------------------------------------------------------------------
# 「出戏闸」（真机实测逼出来的）
#   3B 在微反应上会偶尔从"角色"掉回"助手"，实测样本：
#     「抱歉，我没有触觉无法感受被拉肩，停一下别紧张。」
#   这种句子对"活人味"的伤害比重复一句罐头大得多 —— 它直接把扮演戳破了。
#   这里只做**否定式**最小拦截（命中即整句作废、回落罐头）；
#   不做"像不像 Ralsei"的正向打分（那需要模型，且会误杀有创意的句子）。
# ---------------------------------------------------------------------------
_OOC_PATTERNS = (
    '没有触觉', '无法感受', '感觉不到', '没有感觉', '没有身体',
    '我是ai', '作为ai', '作为一个人工智能', '人工智能', '语言模型', '大模型',
    '我是一个程序', '我是程序', '机器人', '系统提示', '无法回答', '不能回答',
    '作为一个助手', '我的设定', '提示词',
)

# ---------------------------------------------------------------------------
# 「设定里明令不说的话」闸（代码级兜底，2026-09-19 加）
#   为什么必须有：persona 第 40~41 行白纸黑字写了
#     「这些话我不说：作为AI／作为一个语言模型／我理解你的感受／我明白你的心情／
#       有什么可以帮你的吗／希望这些能帮到你／让我们一起……」
#   但**提示词不是保证**。同一天的生动度抽查（`_evidence/probe_vividness.txt`）
#   实测 ralsei:v2：
#     · "早上好" 场景 3 条里**有 2 条**回「早安，有什么我可以帮忙的吗？」；
#     · "在吗"   场景也回了同一句「当然在，有什么可以帮忙的吗？」。
#   而这句话正是用户最反感的客服腔 —— 它一旦出现，人味就归零了。
#   所以必须在代码里兜一道：命中 → 整句作废（判退，由调用方处理）。
#   选词原则：只收**足够长、不会误伤正常台词**的片段（"我相信你"这类空话也在列，
#   但"你""相信"这种单字绝不单独收 —— 误杀 = 该说的话被吞掉，比漏过更糟）。
# ---------------------------------------------------------------------------
_BANNED_PATTERNS = (
    # 客服腔 / 主动提供帮助（persona 明令）
    # ⚠️ 这一组的**语序变体必须穷举**：2026-09-19 三向对比里，3B 的一条
    #    「早安，有什么我可以帮忙的吗？」就穿过了只写了"有什么可以帮"的旧表
    #    （下一个字是"我"而不是"你/到/上"）。所以这里按**动词块**收，
    #    而不是按整个句子收。
    '有什么可以帮', '有什么能帮', '有什么需要我帮', '有什么我可以帮', '有什么我能帮',
    '需要我帮你', '需要我帮你做', '我可以帮忙', '我能帮忙', '可以帮忙吗', '能帮忙吗',
    '帮忙的吧', '帮上忙', '帮上什么忙', '帮你的吗', '帮您的吗', '帮到你', '帮到我',
    '希望这些能帮到', '希望对你有帮助', '为您服务', '随时待命', '需要帮忙吗',
    # 空话安慰（persona 明令）
    '我理解你的感受', '我理解你的心情', '我明白你的感受', '我明白你的心情',
    '我相信你', '我懂你的感受', '我懂你的心情',
    # 助手式组织语言（persona 明令）
    '首先', '其次', '最后一点', '总之', '总结一下', '让我们一起',
)

# 旁白化：模型偶尔不写台词、写"动作叙述"。实测样本：
#   「我扶着墙站了起来，拍拍身上的尘土。」
# 它作为**台词**会很怪，但作为叙事是正常的 —— 所以只拦**最不会误伤**的一类：
# 句首就是括号的（那是明确的舞台指示写法）。更细的叙述识别留给模型换代去解决，
# 在这里堆动作词表会误杀"我点点头"这种合理的俏皮话。
_NARRATION_PREFIXES = ('（', '(', '【', '[', '＊', '*')

# ---------------------------------------------------------------------------
# 「句子里夹带的括号动作」闸（2026-09-19 加）—— 补 `looks_like_narration` 的洞
#   洞在哪：`looks_like_narration` 只看**首字符**，所以
#     「（歪着头）」                              → 拦得住（句首）
#     「嗯…（轻轻敲了下键盘）我也是这么想的。」      → **拦不住**（句中）
#   2026-09-19 的 A/B 探针把这类单列成「括号动作」标记后实测：旧/新 persona 都出现过，
#   而生产的两道闸**全放过** —— 尺子有洞，必须在生产里补（探针不能当兜底）。
#
# 为什么是"**只删那一段**"而不是"整句作废"：
#   动作旁白通常只是句子的装饰（「（小声）其实我很害怕。」）。整句作废要重采样，
#   白等一两秒还未必更好；把括号那段切掉，剩下的就是一句正常台词。
#   若切完什么都不剩（整句只有一个括号动作）→ 返回空串，调用方按"判退"处理。
#
# 为什么只抓"动作词"、**不一刀切禁括号**：
#   Ralsei 原作里括号是他的**正常表达手段** —— 实测 853 条台词里 35 条含括号，
#   其中 **26 条直接以括号开头**（用来对 Kris 交代事情 / 讲心里话），
#   证据 `_evidence/paren_usage_2026-09-19.txt`（可复算）。见括号就作废 = 把他的特征一起砍掉。
#   所以只匹配"括号内**开头**就是动作/发声动词"的那一类；
#   讲心里话的括号开头是「其实」「我」「……」这类，天然落在规则之外。
#
# ⚠️ **故意保留** `looks_like_narration`：`（我扶着墙站了起来，拍拍身上的尘土。）` 这种
#   "整句叙述"不以此规则拦（它开头是"我扶着"而非动作词），仍由句首括号那道闸兜住。
#   两道闸分工：**句首括号 = 整句作废；句中括号动作 = 只删那一段。**
# ---------------------------------------------------------------------------
_ACTION_MODIFIERS = ('轻轻|慢慢|微微|默默|悄悄|稍稍|缓缓|静静|无奈|连忙|赶紧|'
                     '稍微|勉强|用力|使劲|轻')
# 只收"做出来就是动作"的词。刻意**不收**的几类（避免误杀心里话）：
#   · 裸 `抱` —— 会命中「（抱歉，我不是故意的）」
#   · 裸 `笑` —— 会命中「（笑不出来）」
#   · `叹气` 换成裸 `叹` —— 否则「（叹了口气）」永远匹配不上
_ACTION_VERBS = ('敲|挠|歪|低头|抬头|眨眼|叹|脸红|握住|握|摊手|耸肩|点头|摇头|'
                 '小声|轻声|喃喃|沉默|停顿|皱眉|抿嘴|咳嗽|清嗓|嘟囔|嘀咕|挥手|'
                 '拍拍|拍了拍|笑了笑|笑了|苦笑着|抖|缩|扭|侧头|转身|捂着|捂住|捂|'
                 '抱住|抱抱|站起|坐下|指了指|瞥|挑眉|吐舌|深吸|呼出一口气|'
                 # 2026-09-22 第31轮补：7B 实测漏网的发声/接触类小动作。
                 # 漏网原例来自 `_evidence/stutter_ab_7b.txt` 的裸测回复：
                 #   「…（轻叹）你最近吃了什么…」—— `轻` 当时不在修饰语表、`叹` 又在动词表，
                 #   中间那个"轻"让整条不匹配 ⇒ 真机旁白漏进台词。
                 # 补 `哼|嗤|摸`（`轻哼`/`嗤笑`/`摸摸头` 都是纯外部动作），
                 # 并单列 `轻笑` —— **不能加裸 `笑`**，那会误杀「（笑不出来）」这句合法台词
                 # （上表注释已警告过；放宽前实测：裸 `笑` 会让 `（笑不出来）` KILL）。
                 '哼|嗤|摸|轻笑')
# 括号内**开头**就是动作词（允许前面挂一个程度/速度修饰语）。
# 这样「（轻轻地敲了下键盘）」命中，而「（其实我有点怕）」不命中。
_ACTION_PAREN_RE = re.compile(
    r'[（(＊*]\s*(?:%s)?\s*(?:%s)[^）)＊*]{0,16}[）)＊*]'
    % (_ACTION_MODIFIERS, _ACTION_VERBS))

# ---------------------------------------------------------------------------
# 「第三个括号形态：内心独白 / 交代式旁白」（2026-09-22 第27轮加）
#   洞在哪：上面两道闸都只看**括号内第一个词**。
#     `_ACTION_PAREN_RE` 要动作词 → 「（心里有点慌，怕自己说得不好）」开头是"心里"，**不匹配**；
#     `looks_like_narration` 只看**整句首字符** → 括号在句中时**根本不看**。
#   第27轮真实对话探针（`probe_paren_census.txt` / `probe_real_chat.txt`）实测漏网样本：
#     （心里有点慌，怕自己说得不好）／（我说完有点愣了一下）
#     （心里有点闷，像没打开的窗）／（语气轻快点，但没太夸张）／（停顿了一下）
#   它们都是**从外部描述自己**（"心里…""语气…""（我）愣了一下"），
#   而不是**角色在讲心里话**（"其实…""因为…""抱歉…""我想想…"）。
#   persona 明令"我是用打字说话的，别把动作/内心状态写出来"——针对的正是前者。
#
#   ⚠️ **为什么不能用"白名单放宽"**（第27轮第一版就是这么做，被锁抓出来了）：
#     第一版用"开头必须是 其实/……"的窄白名单，结果把合法心里话一起误杀 ——
#     回归锁 C19 / A22c 实测报红：`（我想想该怎么说）`、`（抱歉，我不是故意的）`、
#     `（笑不出来）`、`（因为……我一直都是一个人）` 全被清掉了。
#     **误杀 = 该说的话被吞掉，比漏过更糟**（这是项目里反复出现的取舍）。
#
#   正确口径：**抓"描述性叙述"的形态特征，不抓首词白名单。**
#     叙述的特征 = 括号内容以**描述自己状态的词**开头，且**不是在说话**：
#       「心里…」「语气…」「（我）愣了一下/顿了一下/沉默…」「下意识…」「本能…」
#     心里话的特征 = 括号内容是**第一人称的话语**：
#       「其实…」「因为…」「抱歉…」「我想想…」「……」（话没说完）
#     判据用**叙述词表**（下面 `_NARRATION_INNER`）——它比动作词表更贴近"叙述"这一类，
#     而且**不碰**第一人称话语，所以不会误杀心里话。
#     这与"动词表要穷举"的老问题是同一类，但范围**窄得多**：只收"描述自己状态"的固定开头。
# ---------------------------------------------------------------------------
# 「描述自己状态」的叙述开头（**这类是从外部描述，不是角色在说话**）
# 收词原则：只在"括号内容以此开头 + 它不是一句第一人称的话"时才算叙述；
# 因此这里收的都是**不能直接接一句人话**的状态词。
_NARRATION_INNER = re.compile(
    r'^(?:心里|语气|神情|眼神|表情|下意识|本能|不由得|忍不住|默默|轻轻|悄悄|'
    r'顿了?(?:一下|了顿)?|停了?(?:一下)?|沉默了?(?:一下)?|愣了?(?:一下)?|'
    r'我(?:说完)?愣了?(?:一下)?|我(?:说完)?顿了?(?:一下)?|'
    r'(?:我)?(?:说完|讲完)(?:之后)?|(?:我)?(?:有点|有几分)?(?:慌|紧张|害羞|害怕|不安|难过)了?(?:一下)?)')
# 任意括号对（用于叙述形态的清理）
_ANY_PAREN_RE = re.compile(r'[（(]([^）)]{0,40})[）)]')


def strip_action_parentheticals(text):
    """删掉台词里夹带的「括号旁白」，返回剩下的台词。

    三道闸合起来覆盖括号的全部已知形态：
      甲) 括号内以**动作/发声动词**开头 → `_ACTION_PAREN_RE`（老闸）
      乙) 句首括号 → `looks_like_narration`（老闸，走"整句作废"）
      丙) **描述性旁白**（本闸，第27轮补）：括号内容是"从外部描述自己"的
          → 清掉；是**第一人称心里话**的 → 原样保留（判据见 `_NARRATION_INNER`）

    ⚠️ 与 `_ACTION_PAREN_RE` 的分工：那个按**动作动词**抓，
    本闸按**状态描述词**抓；两者都可能命中同一段，先跑甲闸再跑丙闸不会重复删。

    返回空串的两类（语义都是"这条不能作为台词用"，由调用方按判退处理）：
      * 整句只有括号内容（删完什么都不剩）
      * 删完只剩标点/空白（没有任何实义字符）

    注意：这里**不做** `looks_like_narration` 那类"整句作废"的判断 ——
    句首括号的整句叙述交给那道老闸，三道闸分工不同（见上方注释）。
    """
    if not isinstance(text, str):
        return ""
    if not text:
        return ""

    def _kill_narration(m):
        """丙闸替换：括号内容是"描述自己"的 → 清掉；是心里话 → 原样留。"""
        inner = (m.group(1) or "").strip()
        if _NARRATION_INNER.match(inner):
            return ""                  # 描述性旁白 → 清掉
        return m.group(0)              # 其余（含第一人称心里话）→ 原样保留

    _before = text
    # 甲闸：动作旁白（括号内以动作动词开头）
    t = _ACTION_PAREN_RE.sub('', text)
    # 丙闸：描述性旁白
    t = _ANY_PAREN_RE.sub(_kill_narration, t)
    if t != _before:
        # 删掉一段后收拾残局：
        #   「我在呢。*轻轻敲了敲键盘* 要不要先喝水」→「我在呢。要不要先喝水」
        #   「…藏在心里。\n\n（停顿了一下）\n你说的」→ 不留三连换行
        t = re.sub(r'[ \t]{2,}', ' ', t)
        t = re.sub(r'([。！？…，、；：])[ \t]+', r'\1', t)
        t = re.sub(r'\n{3,}', '\n\n', t)
        t = t.lstrip('，,、。；;：: \t')
        t = t.strip()
    if not re.search(r'[0-9A-Za-z\u4e00-\u9fff]', t):
        return ""
    return t


def looks_out_of_character(text):
    """这句话是不是"从角色里掉出来了"（AI 自我指涉 / 否认自己有感觉）。"""
    if not isinstance(text, str) or not text:
        return False
    low = text.lower()
    for p in _OOC_PATTERNS:
        if p in low:
            return True
    return False


def looks_like_assistant_speak(text):
    """这句话是不是 persona **明令不说**的那类（客服腔 / 空话安慰 / 助手式分点）。

    与 `looks_out_of_character` 的区别：那个是"我是 AI"（自我指涉），
    这个是"我没有自我指涉，但说的是客服话术"。两者都要判退，但成因不同，分开记更好定位。
    """
    if not isinstance(text, str) or not text:
        return False
    low = text.lower()
    for p in _BANNED_PATTERNS:
        if p in low:
            return True
    return False


def looks_like_narration(text):
    """句首是括号/星号 = 舞台指示式旁白，不是"对主人说的台词"。"""
    if not isinstance(text, str):
        return False
    t = text.strip()
    return bool(t) and t[0] in _NARRATION_PREFIXES


def guard_reaction(text):
    """事件台词的可用性判定：出戏 / 客服腔 / 括号动作 / 旁白化 / 空 → 返回空串（调用方处理）。

    2026-09-19 起新增一道**删减式**处理：句中夹带的「括号动作旁白」不再整句作废，
    而是**把那一段删掉**再把剩下的台词放行（`strip_action_parentheticals`）。
    所以本函数的返回值**可能不等于入参** —— 这是有意的，调用方拿到的就是该显示的文本。
    """
    if looks_out_of_character(text):
        return ""
    if looks_like_assistant_speak(text):
        return ""
    t = strip_action_parentheticals(text)
    if not t:
        return ""
    if looks_like_narration(t):
        return ""
    return t


class RecentLinePicker(object):
    """罐头去重器：同一句不要连着说两遍。

    改造前是 `random.choice(pool)`，而池子常常只有 3~4 句 → 连戳三次很可能同一句
    （用户看到的就是"复读"）。这里优先挑**最近窗口内没说过**的；实在全说过，
    挑最久没说过的那个（而不是随机 —— 随机会让"刚说过的那句"再次出现）。
    """

    def __init__(self, window=8):
        self.window = int(window)
        self._recent = []

    def note(self, text):
        if not isinstance(text, str) or not text.strip():
            return
        self._recent.append(text.strip())
        if len(self._recent) > self.window:
            del self._recent[:len(self._recent) - self.window]

    def pick(self, pool, rng=None):
        items = [x for x in (pool or []) if isinstance(x, str) and x.strip()]
        if not items:
            return ""
        fresh = [x for x in items if x not in self._recent]
        if fresh:
            return (rng or random).choice(fresh)
        for old in self._recent:
            if old in items:
                return old
        return (rng or random).choice(items)

    def clear(self):
        self._recent = []


def _selfcheck():
    """模块自检（不依赖 Qt / 项目内模块）。`python -m modules.event_speech` 可跑。"""
    errs = []
    if tier_of("poke_body") != TIER_AI:
        errs.append("poke_body 应为 AI 档")
    if tier_of("fling") != TIER_INSTANT:
        errs.append("fling 应为罐头档")
    if tier_of("__不存在的事件__") != TIER_INSTANT:
        errs.append("未登记事件必须回落罐头档（否则等于静默改变行为）")
    if pet_kind("hair") != "pet_hair" or pet_kind("腿") != "pet_other":
        errs.append("pet_kind 映射错")
    p = build_prompt("poke_body")
    if "戳" not in p or str(EVENT_MAX_CHARS) not in p:
        errs.append("build_prompt 输出不含事件描述或长度约束")
    if "示例" in p or "例如" in p:
        errs.append("提示词里不许出现示例台词（3B 会照抄）")
    cases = [
        # 首句 3 字 < MIN_FIRST_CHARS 且全文没超上限 → **整句保留**（真机实测逼出来的规则）
        ("哎呀！别捏我的耳朵！好痒呀！", "哎呀！别捏我的耳朵！好痒呀！"),
        # 实测样本：模型回「嗯？发生了什么吗？」，按"取第一句"会切成 2 个字的「嗯？」
        ("嗯？发生了什么吗？", "嗯？发生了什么吗？"),
        # 首句 7 字 ≥ 阈值 → 取第一句
        ("谢谢你，小豆。让我靠你一会儿。", "谢谢你，小豆。"),
        ("嘿嘿~ 好舒服呀！谢谢你主人！", "嘿嘿~ 好舒服呀！"),
        ("诶？！听到这话我都有点不好意思起来了。感觉就像在阳光下晒着一样舒服呢。",
         "诶？！听到这话我都有点不好意思起来了。"),
        ("哈哈哈" * 20, None),
        ("", ""),
        ("。。。", ""),
        ("「嘿嘿~」", "嘿嘿~"),
    ]
    for src, want in cases:
        got = first_sentence(src)
        if want is None:
            if len(got) > EVENT_MAX_CHARS:
                errs.append("first_sentence 没压到上限: %r" % got)
        elif got != want:
            errs.append("first_sentence(%r) = %r，期望 %r" % (src, got, want))
    # 去重器：有没说过的话时，绝不挑刚说过的
    picker = RecentLinePicker(window=3)
    pool = ["A", "B"]
    picker.note("A")
    for _ in range(20):
        if picker.pick(pool) != "B":
            errs.append("RecentLinePicker 挑到了刚说过的句子")
            break
    picker.note("B")
    if picker.pick(pool) != "A":
        errs.append("全说过时应挑最久没说过的（A），而不是随机")
    if picker.pick([]) != "":
        errs.append("空池应返回空串")
    if not errs:
        return "event_speech 自检通过"
    return "event_speech 自检失败:\n  " + "\n  ".join(errs)


if __name__ == "__main__":
    import sys
    msg = _selfcheck()
    sys.stdout.write(msg + "\n")
    sys.exit(0 if "通过" in msg else 1)
