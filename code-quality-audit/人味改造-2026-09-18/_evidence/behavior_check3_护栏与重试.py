# -*- coding: utf-8 -*-
"""第十八轮 · 行为级验证 v3（示范恢复 + 复用护栏 + 判退重采样 之后）。

v2 暴露的两个问题都在这一版验证：
  * v2 的"照抄"用例全 FAIL 是**脚本期望值匹配写错**（expect='→ None（相似度）'
    不匹配 literal '→ None'），不是护栏失效 —— v3 改成 startswith 判定。
  * v2 端到端显示"删掉完整示范 → 人味明显退化"（出现「我明白你的心情了」这类
    明令禁止的套话）。v3 恢复示范，并验证护栏能在"照抄/重复"时把回复退回**重采样**。
"""
import json
import os
import sys
import threading
import time
import urllib.request
from types import MethodType, SimpleNamespace

ROOT = r"C:\Users\23002\Desktop\项目文件夹\try - 副本"
PET = os.path.join(ROOT, "ralsei_pet")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, PET)
sys.path.insert(0, os.path.join(PET, "src"))

OUT = r"E:\Download\_tmp\behavior_check3.txt"
lines = []


def log(s=""):
    lines.append(str(s))


import main as M

R = M.RalseiPet


def make_stub(persona_override=None, **extra):
    s = SimpleNamespace()
    s.AI_REPLY_MAX_CHARS = R.AI_REPLY_MAX_CHARS
    if persona_override is None:
        s._build_persona_prompt = MethodType(R._build_persona_prompt, s)
    else:
        s._build_persona_prompt = lambda: persona_override
    for name in ("_persona_samples", "_is_recycled_reply", "_clean_ai_reply",
                 "_ai_chat_options"):
        setattr(s, name, MethodType(getattr(R, name), s))
    s.api_config = {}
    for k, v in extra.items():
        setattr(s, k, v)
    return s


log("=" * 76)
log("0) persona 采样面：示范已恢复（3 组完整问答对）+ 短片段")
log("=" * 76)
stub = make_stub()
persona = stub._build_persona_prompt()
log("persona 读取：%d 字符" % len(persona))
samples = stub._persona_samples()
for i, s_ in enumerate(samples, 1):
    log("  样本%d: %r" % (i, s_))
log("样本数=%d" % len(samples))
log()

log("=" * 76)
log("1) 护栏 _clean_ai_reply（合成 persona，机制与内容解耦）")
log("=" * 76)
SYNTH = (
    "## 示范\n"
    "主人：我好喜欢你呀\n"
    "我：诶、诶？！你突然说这个干嘛啦……我、我其实也挺喜欢主人的就是了。\n"
)
s2 = make_stub(SYNTH)
log("合成 persona 采样数=%d" % len(s2._persona_samples()))
log()

CASES = [
    ("markdown 强调标记残留", "**听到也让我心里暖暖的**。别太累了。",
     "剥掉 **", lambda g: g == "听到也让我心里暖暖的。别太累了。"),
    ("markdown 列表前缀", "- 早点休息\n- 别熬夜", "剥掉列表符号",
     lambda g: "-" not in g),
    ("自问自答续写", "嗯……被骂了啊……我先陪着你。\n主人：老板说我业绩下滑了\n你：哎呀。",
     "截到「主人：」之前", lambda g: g and "主人：" not in g and "被骂了" in g),
    ("整条都是续写", "主人：你今天怎么不说话\n你：我在想事情。", "→ None",
     lambda g: g is None),
    ("照抄示范（原文）",
     "诶、诶？！你突然说这个干嘛啦……我、我其实也挺喜欢主人的就是了。", "→ None",
     lambda g: g is None),
    ("照抄示范（改两处）", "诶、诶？！你突然说这个干嘛啦……我其实也挺喜欢主人的。",
     "→ None", lambda g: g is None),
    ("v1 漏网样本（ratio 0.74 但整段搬）",
     "诪、诪！你突然说这个干嘛啦……我、我其实也挺喜欢你的。", "→ None",
     lambda g: g is None),
    ("重复自己刚说过的话（recent 命中）", "被骂了啊……是因为什么事呢？我听着都替你委屈。",
     "→ None", lambda g: g is None),
    ("纯标点（只回一个句号）", "。", "→ None", lambda g: g is None),
    ("被引号包裹", "“今天辛苦了，早点休息哦。”", "去包裹引号",
     lambda g: g == "今天辛苦了，早点休息哦。"),
    ("正常回复（与 recent / 示范都不重合）",
     "今天风挺大的，出门记得加件外套。", "原样通过",
     lambda g: g == "今天风挺大的，出门记得加件外套。"),
    ("空串", "", "→ None", lambda g: g is None),
    ("None", None, "→ None", lambda g: g is None),
    ("非字符串数字", 12345, "→ '12345'", lambda g: g == "12345"),
]
RECENT = ["被骂了啊……是因为什么事呢？我听着都替你委屈。"]
bad = 0
for name, inp, expect, pred in CASES:
    got = s2._clean_ai_reply(inp, recent=RECENT)
    ok = bool(pred(got))
    if not ok:
        bad += 1
    g = got if got is None or len(str(got)) <= 44 else str(got)[:44] + "…"
    log("  [%s] %-34s 输出=%r  预期=%s" % ("OK  " if ok else "FAIL", name, g, expect))
log()
log("  护栏用例：%d 项，%d 项不符" % (len(CASES), bad))
log()

log("=" * 76)
log("2) 超长截断的**真实长度**校验")
log("=" * 76)
long_in = "唔……" + "这是一段很长的独白，用来测试超长截断。" * 12
long_out = stub._clean_ai_reply(long_in)
log("  输入=%d 字  输出=%d 字  上限=%d  末字=%r  → %s"
    % (len(long_in), len(long_out), R.AI_REPLY_MAX_CHARS,
       long_out[-1] if long_out else None,
       "OK" if long_out and len(long_out) <= R.AI_REPLY_MAX_CHARS else "FAIL"))
log()

log("=" * 76)
log("3) 判退后**重采样**：chat_with_ai 真的会重发一次、并用二次结果")
log("=" * 76)


class FakeCli:
    enabled = True

    def __init__(self, replies):
        self.replies = list(replies)
        self.seen = []

    def chat(self, prompt, system_prompt=None, **kw):
        self.seen.append((prompt, kw.get("temperature"), (system_prompt or "")[-30:]))
        return self.replies.pop(0) if self.replies else None


class FakeSig:
    def __init__(self):
        self.vals = []
        self.ev = threading.Event()

    def emit(self, val, cb):
        self.vals.append(val)
        self.ev.set()


ECHO = "诶、诶？！你突然说这个干嘛啦……我、我其实也挺喜欢主人的就是了。"
FRESH = "诶？！你、你别突然说这个啦……我耳朵都要热起来了。"
st = make_stub(api_config={"options": {"temperature": 0.85, "max_tokens": 256}})
st.api_enabled = True
st.api_client = FakeCli([ECHO, FRESH])
st._api_result = FakeSig()
st.dialogue_ui = SimpleNamespace(get_ai_history=lambda limit=0: [],
                                 get_focus_brief=lambda: "")
st._build_ai_context = lambda: ""
st.memory_system = None
R.chat_with_ai(st, "我好喜欢你呀", lambda r: None)
st._api_result.ev.wait(10)
log("  FakeCli 被调用次数 = %d（期望 2：首次判退 + 重采样）" % len(st.api_client.seen))
log("  两次温度 = %r（期望第二次更高）" % [t for _p, t, _s in st.api_client.seen])
log("  第二次 system 尾部 = %r（期望带「这一次请特别注意」）"
    % (st.api_client.seen[1][2] if len(st.api_client.seen) > 1 else None))
log("  最终 emit 值 = %r（期望 = 重采样结果）" % (st._api_result.vals,))
ok_retry = (len(st.api_client.seen) == 2
            and st._api_result.vals and st._api_result.vals[0] == FRESH)
log("  → %s" % ("OK 判退确实触发了换说法重采样" if ok_retry else "**FAIL 重采样未生效**"))
log()

st2 = make_stub(api_config={"options": {"temperature": 0.85, "max_tokens": 256}})
st2.api_enabled = True
st2.api_client = FakeCli(["   "])
st2._api_result = FakeSig()
st2.dialogue_ui = SimpleNamespace(get_ai_history=lambda limit=0: [],
                                  get_focus_brief=lambda: "")
st2._build_ai_context = lambda: ""
st2.memory_system = None
R.chat_with_ai(st2, "在吗", lambda r: None)
st2._api_result.ev.wait(10)
log("  模型主动沉默（空回复）时 FakeCli 调用次数 = %d（期望 1，不该重试）"
    % len(st2.api_client.seen))
log("  → %s" % ("OK 主动沉默不触发重试"
                if len(st2.api_client.seen) == 1 else "**FAIL 多试了一次**"))
log()

log("=" * 76)
log("4) 关键词命中规则（回归）")
log("=" * 76)
from modules.dialogue_ui import DialogueUI as D

KW_CASES = [
    ("天气", "天气", True), ("天气", "查看天气", True), ("天气", "今天天气真好", False),
    ("天气", "我这边天气怎么样", False), ("哭", "我快哭了", False), ("哭", "别哭", True),
    ("游戏", "我做的游戏上线了", False), ("游戏", "游戏", True), ("状态", "我状态不太好", False),
    ("精力", "没什么精力", False), ("饿了吗", "你饿了吗", True),
    ("石头剪刀布", "陪我玩石头剪刀布吧", True), ("睡觉", "你去睡觉吧", True),
    ("唱歌", "你唱歌真好听", False),
]
kbad = 0
for kw, raw, want in KW_CASES:
    got = (kw in raw) if kw in D._HARD_CMDS else D._is_command_phrase(raw, kw)
    if got != want:
        kbad += 1
        log("  FAIL kw=%s raw=%s got=%s want=%s" % (kw, raw, got, want))
log("  关键词用例：%d 项，%d 项不符" % (len(KW_CASES), kbad))
log()

log("=" * 76)
log("5) 端到端：恢复示范后的 persona，4 题 × 3 次（含违禁套话扫描）")
log("=" * 76)
cfg = json.load(open(r"E:\RalseiMemory\config.json", encoding="utf-8"))
api = cfg["api"]
model = api["model"]
opts = api.get("options") or {}
log("模型=%s  参数=%s" % (model, opts))
CTX = "【此刻】现在是深夜，天气晴，心情平静，有点疲惫，主人的名字是小豆"
system = persona + "\n\n" + CTX
log("system 长度：%d 字符" % len(system))
log()

BANNED = ["作为AI", "作为一个语言模型", "我理解你的感受", "有什么可以帮你的",
          "希望这些能帮到你", "让我们一起", "我明白你的心情"]
QS = ["今天上班好累啊，被领导骂了一顿", "我好喜欢你呀",
      "你觉得我该不该辞职回老家", "今天吃了火锅"]
REP = 3
per_q = {}
hits = []
for qi, q in enumerate(QS, 1):
    log("-" * 76)
    log("Q%d: %s" % (qi, q))
    reps = []
    for ri in range(1, REP + 1):
        body = {"model": model,
                "messages": [{"role": "system", "content": system},
                             {"role": "user", "content": q}],
                "temperature": opts.get("temperature", 0.85),
                "max_tokens": opts.get("max_tokens", 256),
                "stream": False}
        req = urllib.request.Request(
            "http://localhost:11434/v1/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                d = json.loads(r.read().decode("utf-8"))
            raw = ((d.get("choices") or [{}])[0].get("message") or {}).get("content", "")
            cleaned = stub._clean_ai_reply(raw, recent=reps[-1:])
            recycled = stub._is_recycled_reply(raw.strip(), reps[-1:])
            for b in BANNED:
                if b in (cleaned or ""):
                    hits.append((q, ri, b, cleaned))
            for mark in ("**", "`", "\n- "):
                if mark in (cleaned or ""):
                    hits.append((q, ri, "格式残留:" + mark, cleaned))
            reps.append(cleaned)
            log("  第%d次 原始  : %r" % (ri, raw.strip()))
            log("       护栏后: %r  复用判定=%s" % (cleaned, recycled))
        except Exception as e:
            reps.append(None)
            log("  第%d次 ERR %r" % (ri, e))
    per_q[q] = reps
    ok = [r for r in reps if r]
    log("  小结：有效 %d/%d，同题重复 %d 条" % (len(ok), REP, len(ok) - len(set(ok))))
    log()

log("=" * 76)
log("总览")
log("=" * 76)
tot = dup = 0
for q, reps in per_q.items():
    ok = [r for r in reps if r]
    tot += len(ok)
    dup += len(ok) - len(set(ok))
    log("  %s → 有效 %d/%d，重复 %d" % (q, len(ok), REP, len(ok) - len(set(ok))))
log("  合计：有效 %d 条，完全重复 %d 条（重复率 %.0f%%）"
    % (tot, dup, (dup / tot * 100) if tot else 0))
log("  违禁套话/格式残留命中：%d 处" % len(hits))
for h in hits:
    log("    - %s 第%d次 [%s] %r" % h)

os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
open(OUT, "w", encoding="utf-8").write("\n".join(lines))
print("WROTE", OUT)
