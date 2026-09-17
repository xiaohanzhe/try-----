# -*- coding: utf-8 -*-
"""第十八轮 · 端到端终验（忠实复刻 chat_with_ai 的判退→重采样流程）。

与 behavior_check3 第 5 节的区别：那一节直接调 _clean_ai_reply，**没有走重试**，
所以"判退"看起来像"成功率为 0"。这里按真实链路跑：
    raw → 护栏(recent=已说过的台词) → 判退则抬温+换说法提示重发一次 → 再护栏 → 采用
并把「同一问题连问两次」单独作为一组，验证车轱辘话护栏真的会在第二次换出新的说法。
"""
import json
import os
import sys
import urllib.request
from types import MethodType, SimpleNamespace

ROOT = r"C:\Users\23002\Desktop\项目文件夹\try - 副本"
PET = os.path.join(ROOT, "ralsei_pet")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, PET)
sys.path.insert(0, os.path.join(PET, "src"))

OUT = r"E:\Download\_tmp\e2e_final.txt"
lines = []


def log(s=""):
    lines.append(str(s))


import main as M

R = M.RalseiPet
stub = SimpleNamespace()
stub.AI_REPLY_MAX_CHARS = R.AI_REPLY_MAX_CHARS
for name in ("_build_persona_prompt", "_clean_ai_reply", "_is_repeat_of_recent"):
    setattr(stub, name, MethodType(getattr(R, name), stub))
stub._persona_cache = None

persona = stub._build_persona_prompt()
cfg = json.load(open(r"E:\RalseiMemory\config.json", encoding="utf-8"))
api = cfg["api"]
model, opts = api["model"], (api.get("options") or {})
CTX = "【此刻】现在是深夜，天气晴，心情平静，有点疲惫，主人的名字是小豆"
SYSTEM = persona + "\n\n" + CTX

log("=" * 78)
log("端到端终验 · 复刻 chat_with_ai：护栏判退 → 抬温 + 换说法 → 重采样一次")
log("=" * 78)
log("模型=%s  参数=%s" % (model, opts))
log("persona=%d 字  system=%d 字" % (len(persona), len(SYSTEM)))
log()

BANNED = ["作为AI", "作为一个语言模型", "我理解你的感受", "我明白你的心情",
          "有什么可以帮你的", "希望这些能帮到你", "让我们一起"]


def llm(q, temp, sys_prompt):
    body = {"model": model,
            "messages": [{"role": "system", "content": sys_prompt},
                         {"role": "user", "content": q}],
            "temperature": temp,
            "max_tokens": opts.get("max_tokens", 256),
            "stream": False}
    req = urllib.request.Request("http://localhost:11434/v1/chat/completions",
                                data=json.dumps(body).encode("utf-8"),
                                headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        d = json.loads(r.read().decode("utf-8"))
    return ((d.get("choices") or [{}])[0].get("message") or {}).get("content", "")


spoken = []          # Ralsei 已说出口的台词（= 真实链路里的 get_ai_history）
stats = {"calls": 0, "retries": 0, "rejects": 0, "ok": 0}
banned_hits = []
format_hits = []


def turn(q, tag=""):
    """一次完整的对话轮：raw → 护栏 → （判退则重采样）→ 采用。"""
    temp = float(opts.get("temperature", 0.85))
    stats["calls"] += 1
    raw = llm(q, temp, SYSTEM).strip()
    cleaned = stub._clean_ai_reply(raw, recent=spoken)
    reused = stub._is_repeat_of_recent(raw, spoken)
    log("  %s问题: %s" % (tag, q))
    log("    ①原始  : %r" % raw)
    log("      判重=%s" % reused)
    if cleaned is None and raw:
        stats["retries"] += 1
        stats["rejects"] += 1
        log("      → 护栏判退，抬温 %.2f→%.2f 并要求换说法重采样" % (temp, min(1.0, temp + 0.1)))
        stats["calls"] += 1
        raw2 = llm(q, min(1.0, temp + 0.1), SYSTEM + "\n\n" + R._RETRY_NUDGE).strip()
        cleaned = stub._clean_ai_reply(raw2, recent=spoken)
        log("    ②重采  : %r" % raw2)
        log("      判重=%s" % stub._is_repeat_of_recent(raw2, spoken))
    if cleaned:
        stats["ok"] += 1
        spoken.append(cleaned)
        for b in BANNED:
            if b in cleaned:
                banned_hits.append((q, b, cleaned))
        for mk in ("**", "`", "\n- ", "\n#"):
            if mk in cleaned:
                format_hits.append((q, mk, cleaned))
    log("    最终  : %r" % cleaned)
    log()
    return cleaned


log("-" * 78)
log("第一组：四道常规问题（每道一次）")
log("-" * 78)
log()
for i, q in enumerate(["今天上班好累啊，被领导骂了一顿", "我好喜欢你呀",
                       "你觉得我该不该辞职回老家", "今天吃了火锅"], 1):
    turn(q, "Q%d " % i)

log("-" * 78)
log("第二组：同一问题连问三次（车轱辘话护栏的核心场景）")
log("-" * 78)
log()
for i in range(1, 4):
    turn("我好喜欢你呀", "第%d次 " % i)

log("=" * 78)
log("总览")
log("=" * 78)
log("模型调用 %d 次（其中重采样 %d 次）" % (stats["calls"], stats["retries"]))
log("护栏判退 %d 次 → 重采样后成功 %d 次" % (stats["rejects"], stats["ok"]))
log("最终全部产出 %d 条台词" % len(spoken))
dup = len(spoken) - len(set(spoken))
log("完全重复：%d 条（重复率 %.0f%%）" % (dup, (dup / len(spoken) * 100) if spoken else 0))
log("违禁套话命中：%d 处" % len(banned_hits))
for h in banned_hits:
    log("  - %s [%s] %r" % h)
log("markdown/格式残留命中：%d 处" % len(format_hits))
for h in format_hits:
    log("  - %s [%s] %r" % h)

os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
open(OUT, "w", encoding="utf-8").write("\n".join(lines))
print("WROTE", OUT)
