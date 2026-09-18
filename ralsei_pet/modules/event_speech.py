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


def looks_out_of_character(text):
    """这句话是不是"从角色里掉出来了"（AI 自我指涉 / 否认自己有感觉）。"""
    if not isinstance(text, str) or not text:
        return False
    low = text.lower()
    for p in _OOC_PATTERNS:
        if p in low:
            return True
    return False


def guard_reaction(text):
    """事件台词的可用性判定：出戏 / 空 → 返回空串（调用方回落罐头）。"""
    if looks_out_of_character(text):
        return ""
    return text


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
