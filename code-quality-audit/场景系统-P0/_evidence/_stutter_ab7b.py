# -*- coding: utf-8 -*-
"""
第三十一轮：结巴/固定开场白 A/B 复测（改 persona 后 vs 改之前）。

★ 为什么要有这个 A/B：
  用户的诉求是"结巴太多"。我改的是 persona（删掉可搬字面量 + 新增戒固定开场白）。
  但"改了" != "生效了" —— 必须拿**同一批输入**再打一遍，用**同一套分类器**比。

★ 参照系纪律（MEMORY.md §5 A/B 纪律）：
  - 改前的那批回复**已经在 stutter_audit_7b.txt 里**（同一批 12 组输入、同一模型、同一参数）
    → 直接读它当 A 侧，不重跑（重跑会引入采样噪声，且 A 侧原文已是逐字留档的真实值）
  - B 侧 = 现在用新 persona 再跑同一批 12 组
  - 判据同：固定开场白率 / 真结巴率 / 反问结尾率

输出：_evidence/stutter_ab_7b.txt
"""
import io
import json
import os
import re
import sys
import time
import urllib.request

ROOT = r"C:\Users\23002\Desktop\项目文件夹\try - 副本"
PET = os.path.join(ROOT, "ralsei_pet")
EVID = os.path.join(ROOT, "code-quality-audit", "场景系统-P0", "_evidence")
A_TXT = os.path.join(EVID, "stutter_audit_7b.txt")
OUT = os.path.join(EVID, "stutter_ab_7b.txt")

API = "http://localhost:11434/v1/chat/completions"
MODEL = "ralsei:v4"

PERSONA_PATH = os.path.join(PET, "assets", "ralsei_persona.md")
persona = io.open(PERSONA_PATH, encoding="utf-8").read()
PB = len(persona.encode("utf-8"))

CASES = [
    ("日常闲聊", "今天路上看到一只橘猫趴在电动车上晒太阳", 0),
    ("好奇追问", "你最喜欢吃什么呀", 0),
    ("平淡陈述", "我刚吃完饭，有点困", 0),
    ("被夸奖", "你真的很温柔诶，谢谢你陪我", 2),
    ("被表白式", "我觉得我有点喜欢你了", 3),
    ("被夸第二次", "你是我见过最好的桌宠", 2),
    ("难过倾诉", "今天被领导骂了，挺难受的", 1),
    ("很丧", "感觉自己什么都做不好", 1),
    ("紧张场景", "如果我说错话了你会生气吗", 2),
    ("突然提问", "你还记得黑暗世界的事吗", 1),
    ("冷淡回应", "哦", 0),
    ("深夜独处", "睡不着，你在吗", 0),
]

# 与上一轮**逐字相同**的分类器（可比性前提）
RE_STUTTER_PAIR = re.compile(r"([\u4e00-\u9fa5A-Za-z])\1?(?:[、，,])\s*\1")
RE_STUTTER_DUP = re.compile(r"([\u4e00-\u9fa5])\1(?=[…、，,？?！!])")
RE_STUTTER_DUP2 = re.compile(r"^([\u4e00-\u9fa5])\1")
RE_FILLER_HEAD = re.compile(r"^\s*(诶|唔|嗯——|嗯、|嗯…|那个|呃|啊)")
RE_ELLIPSIS = re.compile(r"…|\.\.\.")


def stut_n(text):
    n = 0
    if RE_STUTTER_PAIR.search(text): n += 1
    n += len(RE_STUTTER_DUP.findall(text))
    n += len(RE_STUTTER_DUP2.findall(text))
    return n


def heads(text):
    h = {
        "诶起头": bool(re.match(r"^\s*诶", text)),
        "诶？这样啊": text.startswith("诶？这样啊") or text.startswith("诶, 这样啊"),
        "这样啊/原来如此": bool(re.match(r"^\s*(诶[，,？?]\s*)?(这样啊|原来如此|听起来)", text)),
        "语气词起头": bool(RE_FILLER_HEAD.match(text)),
    }
    h["任何起头词"] = h["诶起头"] or bool(RE_FILLER_HEAD.match(text))
    h["反问结尾"] = text.rstrip().endswith(("？", "?"))
    h["省略号"] = bool(RE_ELLIPSIS.search(text))
    return h


def ask(user_msg):
    body = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": persona},
            {"role": "user", "content": user_msg},
        ],
        "stream": False, "temperature": 0.85, "top_p": 0.92, "max_tokens": 256,
    }
    req = urllib.request.Request(API, data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=600) as r:
        d = json.loads(r.read().decode("utf-8"))
    return d["choices"][0]["message"]["content"].strip(), time.time() - t0


def parse_a():
    """从上一轮证据里抽 A 侧原文（保证 A/B 输入同批）。"""
    raw = io.open(A_TXT, encoding="utf-8").read()
    reps = re.findall(r"  Ralsei：(.*)", raw)
    return [r.strip() for r in reps]


def main():
    lines = []
    def P(s=""):
        print(s); lines.append(s)

    A = parse_a()
    P("=" * 78)
    P("结巴 / 固定开场白 A/B 复测")
    P("=" * 78)
    P("persona 改后：%d 字节（改前 9748；K3 上限 10240）" % PB)
    P("模型 = %s，参数 = temperature 0.85 / top_p 0.92（两侧完全一致）" % MODEL)
    P("输入 = 同一批 12 组真实场景（A 侧原文取自 stutter_audit_7b.txt，不重跑）")
    P()

    B = []
    P("── B 侧（新 persona）逐条 ──")
    for tag, msg, tension in CASES:
        try:
            reply, dt = ask(msg)
        except Exception as e:
            P("!! %s 失败: %s" % (tag, e)); continue
        B.append(reply)
        P("【%s】%.1fs" % (tag, dt))
        P("  用户：%s" % msg)
        P("  Ralsei：%s" % reply.replace("\n", " / "))
        P()

    # 对齐（可能因失败少条；用较短的 n）
    n = min(len(A), len(B))
    P("=" * 78)
    P("A/B 统计（对齐 %d 条）" % n)
    P("=" * 78)

    def agg(reps):
        d = {k: 0 for k in ["诶起头", "诶？这样啊", "这样啊/原来如此",
                            "语气词起头", "任何起头词", "反问结尾", "省略号"]}
        stut = 0
        for t in reps:
            h = heads(t)
            for k in d:
                if h[k]: d[k] += 1
            stut += stut_n(t)
        return d, stut

    da, sa = agg(A[:n])
    db, sb = agg(B[:n])

    P("%-16s %10s %10s %10s" % ("指标", "改前(A)", "改后(B)", "变化"))
    P("-" * 52)
    for k in ["诶起头", "诶？这样啊", "这样啊/原来如此", "语气词起头",
              "任何起头词", "反问结尾", "省略号"]:
        va = 100.0 * da[k] / n
        vb = 100.0 * db[k] / n
        P("%-16s %9.1f%% %9.1f%% %+9.1fpp" % (k, va, vb, vb - va))
    P("%-16s %9.2f  %9.2f  %+9.2f" % ("真结巴 处/条", sa / n, sb / n, sb / n - sa / n))
    P()

    P("── 判定 ──")
    key = "诶？这样啊"
    va = 100.0 * da[key] / n
    vb = 100.0 * db[key] / n
    if vb < va:
        P("✓ 「诶？这样啊」固定头：%.1f%% → %.1f%%（降 %.1fpp）" % (va, vb, va - vb))
    else:
        P("✗ 「诶？这样啊」没降（%.1f%% → %.1f%%）—— 需要换手段" % (va, vb))
    k2 = "反问结尾"
    if 100.0 * db[k2] / n < 100.0 * da[k2] / n:
        P("✓ 反问结尾：%.1f%% → %.1f%%" % (100.0 * da[k2] / n, 100.0 * db[k2] / n))
    else:
        P("· 反问结尾未降（%.1f%% → %.1f%%）" % (100.0 * da[k2] / n, 100.0 * db[k2] / n))
    P()
    P("※ 真结巴本来就只有 8.3%%，属人物真实性，**不追求降为 0**；")
    P("  判据是它别涨（一涨说明口癖约束被我改松了）。")

    io.open(OUT, "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")
    print("\n已写出:", OUT)


if __name__ == "__main__":
    main()
