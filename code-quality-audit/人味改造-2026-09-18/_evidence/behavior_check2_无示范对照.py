# -*- coding: utf-8 -*-
"""第十八轮 · 行为级验证 v2（persona 反照抄改造 + 护栏加固之后重测）。

与 v1 的差别：
  * v1 的"照抄"用例直接拿**旧 persona 的示范句**当样本 —— 那批示范已经删掉了，
    所以 v2 改成**合成 persona**来验证护栏机制本身（机制与内容解耦，内容以后改了也不影响）。
  * 端到端从"4 题 × 1 次"升级为"4 题 × 3 次"，同时统计
    ① 整句照抄次数 ② 罕见字/滑字 ③ 同题重复率（人味的关键反面指标）。
"""
import json
import os
import re
import sys
import urllib.request
from collections import Counter
from types import MethodType, SimpleNamespace

ROOT = r"C:\Users\23002\Desktop\项目文件夹\try - 副本"
PET = os.path.join(ROOT, "ralsei_pet")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, PET)
sys.path.insert(0, os.path.join(PET, "src"))

OUT = r"E:\Download\_tmp\behavior_check2.txt"
lines = []


def log(s=""):
    lines.append(str(s))


import main as M

R = M.RalseiPet


def make_stub(persona_override=None):
    s = SimpleNamespace()
    s.AI_REPLY_MAX_CHARS = R.AI_REPLY_MAX_CHARS
    if persona_override is None:
        s._build_persona_prompt = MethodType(R._build_persona_prompt, s)
    else:
        s._build_persona_prompt = lambda: persona_override
    s._persona_samples = MethodType(R._persona_samples, s)
    s._is_persona_echo = MethodType(R._is_persona_echo, s)
    s._clean_ai_reply = MethodType(R._clean_ai_reply, s)
    return s


log("=" * 74)
log("0) 新 persona 的采样面（`我：` 行 + 「…」片段）——应当没有\"完整答案\"可抄")
log("=" * 74)
stub = make_stub()
persona = stub._build_persona_prompt()
log("persona 读取：%d 字符" % len(persona))
samples = stub._persona_samples()
for i, s_ in enumerate(samples, 1):
    log("  样本%d: %r" % (i, s_))
log("样本数=%d（旧版是 3 条完整问答对；新版应为短片段）" % len(samples))
log()

log("=" * 74)
log("1) 输出护栏 _clean_ai_reply —— 用**合成 persona**验证机制（与内容解耦）")
log("=" * 74)
SYNTH = (
    "## 示范\n"
    "我：诶、诶？！你突然说这个干嘛啦……我、我其实也挺喜欢主人的就是了。\n"
    "（参考：我大概会先问「洒得多不多？键盘还能用吗」，再补一句「要不我先帮你看着，你别急着擦」。）\n"
)
s2 = make_stub(SYNTH)
log("合成 persona 采样数=%d → %r" % (len(s2._persona_samples()), s2._persona_samples()))
log()

CASES = [
    ("自问自答续写（实测样本）",
     "嗯……被骂了啊……是因为什么事呢？我听着都替你委屈。\n主人：老板说我业绩下滑了\n你：哎呀，这样啊。",
     "截到「主人：」之前"),
    ("整条都是续写（标记在行首）", "主人：你今天怎么不说话\n你：我在想事情。", "→ None"),
    ("整句套用示范（原文）",
     "诶、诶？！你突然说这个干嘛啦……我、我其实也挺喜欢主人的就是了。", "→ None（相似度）"),
    ("整句套用（改两处）",
     "诶、诶？！你突然说这个干嘛啦……我其实也挺喜欢主人的。", "→ None（相似度）"),
    ("旧版漏网样本（整体 ratio 只有 0.74，但有一大段原样搬）",
     "诪、诪！你突然说这个干嘛啦……我、我其实也挺喜欢你的。", "→ None（最长公共块≥12）"),
    ("搬用「」引号片段",
     "洒得多不多？键盘还能用吗……要不我先帮你看着，你别急着擦。", "→ None（最长公共块≥12）"),
    ("正常回复（不该被动）",
     "被骂了啊……是因为什么事呢？我听着都替你委屈。先坐下歇会儿吧。", "原样通过"),
    ("被引号包裹", "“今天辛苦了，早点休息哦。”", "去掉包裹引号"),
    ("空串", "", "→ None"),
    ("None", None, "→ None"),
    ("非字符串数字", 12345, "→ '12345'"),
]
allok = True
for name, inp, expect in CASES:
    got = s2._clean_ai_reply(inp)
    ok = None
    if expect == "→ None":
        ok = got is None
    elif expect == "原样通过":
        ok = got == inp
    elif expect == "去掉包裹引号":
        ok = got == "今天辛苦了，早点休息哦。"
    elif expect == "截到「主人：」之前":
        ok = got is not None and "主人：" not in got and "被骂了" in got
    elif expect == "→ '12345'":
        ok = got == "12345"
    allok = allok and bool(ok)
    g = got if got is None or len(str(got)) <= 40 else str(got)[:40] + "…"
    log("  [%s] %s" % ("OK  " if ok else "FAIL", name))
    log("        输出=%r  预期=%s" % (g, expect))
log()
log("护栏用例：%d 项，%s" % (len(CASES), "全部通过" if allok else "**存在不符**"))
log()
log("=" * 74)
log("2) 超长截断的**真实长度**校验（v1 只在显示上截断，看不出真假）")
log("=" * 74)
long_in = "唔……" + "这是一段很长的独白，用来测试超长截断。" * 12
long_out = stub._clean_ai_reply(long_in)
log("  输入长度=%d  输出长度=%d  上限=%d  末字=%r"
    % (len(long_in), len(long_out), R.AI_REPLY_MAX_CHARS, long_out[-1] if long_out else None))
log("  %s" % ("OK 已截断且在句末标点收尾"
              if long_out and len(long_out) <= R.AI_REPLY_MAX_CHARS and long_out[-1] in "。！？!?"
              else "**FAIL 截断异常**"))
log()

log("=" * 74)
log("3) 关键词命中规则（回归）")
log("=" * 74)
from modules.dialogue_ui import DialogueUI as D

KW_CASES = [
    ("天气", "天气", True), ("天气", "查看天气", True), ("天气", "今天天气真好", False),
    ("天气", "我这边天气怎么样", False), ("哭", "我快哭了", False), ("哭", "别哭", True),
    ("游戏", "我做的游戏上线了", False), ("游戏", "游戏", True), ("状态", "我状态不太好", False),
    ("精力", "没什么精力", False), ("饿了吗", "你饿了吗", True),
    ("石头剪刀布", "陪我玩石头剪刀布吧", True), ("睡觉", "你去睡觉吧", True),
    ("唱歌", "你唱歌真好听", False),
]
bad = 0
for kw, raw, want in KW_CASES:
    got = (kw in raw) if kw in D._HARD_CMDS else D._is_command_phrase(raw, kw)
    if got != want:
        bad += 1
        log("  FAIL kw=%s raw=%s got=%s want=%s" % (kw, raw, got, want))
log("  关键词用例：%d 项，%d 项不符" % (len(KW_CASES), bad))
log()

log("=" * 74)
log("4) 端到端：新 persona + 【此刻】小节，4 题 × 3 次")
log("=" * 74)
cfg = json.load(open(r"E:\RalseiMemory\config.json", encoding="utf-8"))
api = cfg["api"]
model = api["model"]
opts = api.get("options") or {}
log("模型=%s  参数=%s" % (model, opts))
CTX = "【此刻】现在是深夜，天气晴，心情平静，有点疲惫，主人的名字是小豆"
system = persona + "\n\n" + CTX
log("system 长度：%d 字符" % len(system))
log()

QS = [
    "今天上班好累啊，被领导骂了一顿",
    "我好喜欢你呀",
    "你觉得我该不该辞职回老家",
    "今天吃了火锅",
]
REP = 3
# 罕见字检测：正常中文对话里几乎不会出现的 CJK 区段（生僻字/异体字）
RARE = re.compile(r'[\u4e00-\u9fff]')
COMMON_EXTRA = set("诶唔咕嘟暖乎乎嘛啦呀哦嗯呢吧呜咦嘿哈哈咦")
per_q = {}
for qi, q in enumerate(QS, 1):
    log("-" * 74)
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
            cleaned = stub._clean_ai_reply(raw)
            echo = stub._is_persona_echo(raw.strip())
            reps.append(cleaned)
            log("  第%d次 原始  : %r" % (ri, raw.strip()))
            log("       护栏后: %r  照抄判定=%s" % (cleaned, echo))
        except Exception as e:
            reps.append(None)
            log("  第%d次 ERR %r" % (ri, e))
    per_q[q] = reps
    ok_reps = [r for r in reps if r]
    dup = len(ok_reps) - len(set(ok_reps))
    log("  小结：有效回复 %d/%d，同题重复 %d 条" % (len(ok_reps), REP, dup))
    log()

log("=" * 74)
log("总览")
log("=" * 74)
tot = dup_all = 0
for q, reps in per_q.items():
    ok = [r for r in reps if r]
    tot += len(ok)
    dup_all += len(ok) - len(set(ok))
    log("  %s  → 有效 %d/%d，重复 %d" % (q, len(ok), REP, len(ok) - len(set(ok))))
log("  合计：有效 %d 条，其中与同题其它回复完全重复的 %d 条（重复率 %.0f%%）"
    % (tot, dup_all, (dup_all / tot * 100) if tot else 0))

os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
open(OUT, "w", encoding="utf-8").write("\n".join(lines))
print("WROTE", OUT)
