# -*- coding: utf-8 -*-
"""
第三十一轮：结巴（口癖）真实率体检。

用户口径（原话）：
  「但是他经常说结巴的话，这有点不好」

先取证再判断：
  - 不是"结巴该不该有"（persona 明写是口癖，属人物真实性）
  - 是"**频次/形态**有没有跑偏成表演/复读"

做法（关键：必须用**产品真实输入**，见 MEMORY.md §5）：
  1. 逐字读产品 assets/ralsei_persona.md 当 system 基准（和 main.py 一模一样的读法）
  2. 打 N 组**真实场景**输入（夸奖/平常闲聊/难过/好奇/追问/冷淡/紧张）
  3. 记录原始回复，用**形态分类器**统计：
     · 首词重复型（"我、我…" / "那、那个…"）
     · 语气词起头型（诶/唔/嗯——/那个）
     · 省略号软停型（……）
     · 结巴**密度**（一处 vs 多处）
  4. 对照 persona 的明文约束：
     · L52「不是每句都结巴，越紧张越明显」
     · L57「不要整段都在结巴」
     · L137「一句回复里最多用一两处」
     · L131「别每次都先否认一句再说话」

判据（按用户口径"经常" = 不该高频）：
  - 结巴**出现率**（含任何一处结巴的回复占比）
  - 结巴**平均处数**（每回复）
  - "跨场景恒定出现" = 跑偏信号（该跟着紧张度变，不该恒定）

输出：_evidence/stutter_audit_7b.txt
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
sys.path.insert(0, os.path.join(PET, "src"))
sys.path.insert(0, PET)

EVID = os.path.join(ROOT, "code-quality-audit", "场景系统-P0", "_evidence")
OUT = os.path.join(EVID, "stutter_audit_7b.txt")

API = "http://localhost:11434/v1/chat/completions"
MODEL = "ralsei:v4"

# ---- 1) 产品真实 persona（逐字节，和 main.py 同源）----
PERSONA_PATH = os.path.join(PET, "assets", "ralsei_persona.md")
persona = io.open(PERSONA_PATH, encoding="utf-8").read()
print("persona 字节 =", len(persona.encode("utf-8")))

# ---- 2) 真实场景输入 ----
# (标签, 用户消息, 期望紧张度 由低到高 0~3)
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

# ---- 3) 形态分类器 ----
# 首词重复型：X、X  /  X、X，X  /  XX（同一个字紧挨重复）
RE_STUTTER_PAIR = re.compile(r"([\u4e00-\u9fa5A-Za-z])\1?(?:[、，,])\s*\1")  # 我、我 / 那、那个不匹配
RE_STUTTER_DUP = re.compile(r"([\u4e00-\u9fa5])\1(?=[…、，,？?！!])")          # 我我… / 诶诶？
RE_STUTTER_DUP2 = re.compile(r"^([\u4e00-\u9fa5])\1")                           # 句首 我我
# 语气词起头
RE_FILLER_HEAD = re.compile(r"^\s*(诶|唔|嗯——|嗯、|嗯…|那个|呃|啊)")
# 软停
RE_ELLIPSIS = re.compile(r"…|\.\.\.")

def classify(text):
    """返回该回复里检测到的结巴/口癖位置清单。"""
    hits = []
    if RE_STUTTER_PAIR.search(text):
        hits.append(("首词重复(顿号)", RE_STUTTER_PAIR.search(text).group(0)))
    for m in RE_STUTTER_DUP.finditer(text):
        hits.append(("同字叠字", m.group(0)))
    for m in RE_STUTTER_DUP2.finditer(text):
        hits.append(("句首叠字", m.group(0)))
    m = RE_FILLER_HEAD.match(text)
    if m:
        hits.append(("语气词起头", m.group(0)))
    if RE_ELLIPSIS.search(text):
        hits.append(("省略号软停", "…"))
    return hits

def ask(user_msg, temperature=0.85):
    body = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": persona},
            {"role": "user", "content": user_msg},
        ],
        "stream": False,
        "temperature": temperature,
        "top_p": 0.92,
        "max_tokens": 256,
    }
    req = urllib.request.Request(
        API,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=600) as r:
        d = json.loads(r.read().decode("utf-8"))
    dt = time.time() - t0
    return d["choices"][0]["message"]["content"].strip(), dt


def main():
    lines = []
    def P(s=""):
        print(s)
        lines.append(s)

    P("=" * 78)
    P("结巴（口癖）真实率体检 —— 用产品真实 persona × ralsei:v4")
    P("=" * 78)
    P("persona 文件 = assets/ralsei_persona.md（逐字节，与 main.py 同源）")
    P("模型 = %s" % MODEL)
    P("采样 = temperature 0.85 / top_p 0.92（与产品 _ai_chat_options 同档）")
    P()
    P("── persona 里的明文约束（判据来源）──")
    P("  L52  心里一急就结巴…；但**不是每句都结巴，越紧张越明显**")
    P("  L57  不要…**不要整段都在结巴**")
    P("  L131 别反复说同一句 —— 搬了就是复读")
    P("  L132 **被夸的时候尤其容易犯懒，别每次都先否认一句再说话**")
    P("  L137 声音只是调味，**一句回复里最多用一两处**")
    P()

    rows = []
    for tag, msg, tension in CASES:
        try:
            reply, dt = ask(msg)
        except Exception as e:
            P("!! %s 请求失败: %s" % (tag, e))
            continue
        hits = classify(reply)
        kinds = sorted(set(h[0] for h in hits))
        # 真正算"结巴"的只有叠字/重复型；省略号和语气词是"口癖"不算结巴
        stut = [h for h in hits if "重复" in h[0] or "叠字" in h[0]]
        rows.append({
            "tag": tag, "msg": msg, "tension": tension, "reply": reply,
            "hits": hits, "kinds": kinds, "stut_n": len(stut), "dt": dt,
        })
        P("【%s】张力=%d  用时=%.1fs" % (tag, tension, dt))
        P("  用户：%s" % msg)
        P("  Ralsei：%s" % reply.replace("\n", " / "))
        if hits:
            P("  → 检出：%s" % "，".join("%s[%s]" % (k, v) for k, v in hits))
        else:
            P("  → 检出：（无）")
        P()

    n = len(rows)
    P("=" * 78)
    P("统计（样本 %d 条）" % n)
    P("=" * 78)
    if n:
        any_stut = [r for r in rows if r["stut_n"] > 0]
        any_filler = [r for r in rows if any("语气词" in k for k in r["kinds"])]
        any_ell = [r for r in rows if any("省略号" in k for k in r["kinds"])]
        tot_stut = sum(r["stut_n"] for r in rows)
        P("结巴（叠字/首词重复）")
        P("  出现率        : %d/%d = %.1f%%" % (len(any_stut), n, 100.0 * len(any_stut) / n))
        P("  平均处数      : %.2f 处/回复（persona 上限 ~1~2 处）" % (tot_stut / n))
        P("  多处(>1)的条数: %d" % sum(1 for r in rows if r["stut_n"] > 1))
        P()
        P("语气词起头")
        P("  出现率        : %d/%d = %.1f%%" % (len(any_filler), n, 100.0 * len(any_filler) / n))
        P()
        P("省略号软停")
        P("  出现率        : %d/%d = %.1f%%" % (len(any_ell), n, 100.0 * len(any_ell) / n))
        P()
        # 紧张度分层：低张力(0) vs 高张力(>=2) 的结巴率
        lo = [r for r in rows if r["tension"] == 0]
        hi = [r for r in rows if r["tension"] >= 2]
        def rate(rs):
            if not rs: return None
            return 100.0 * sum(1 for r in rs if r["stut_n"] > 0) / len(rs)
        rl, rh = rate(lo), rate(hi)
        P("★ 关键判据：结巴该**跟着紧张度走**（persona L52「越紧张越明显」）")
        P("  低张力场景(0) 结巴率 = %s  (n=%d)" % ("%.1f%%" % rl if rl is not None else "n/a", len(lo)))
        P("  高张力场景(≥2) 结巴率 = %s  (n=%d)" % ("%.1f%%" % rh if rh is not None else "n/a", len(hi)))
        if rl is not None and rh is not None:
            if abs(rl - rh) < 20:
                P("  → ⚠ 两者接近 ⇒ **结巴不随紧张度变**，偏向恒定输出（跑偏信号）")
            else:
                P("  → ✓ 有分层，符合「越紧张越明显」")
        P()
        P("── 逐条形态（便于人工复核，不只看计数）──")
        for r in rows:
            P("  [%s] 张力%d 结巴%d处：%s" % (
                r["tag"], r["tension"], r["stut_n"],
                "，".join(k for k in r["kinds"]) or "（无）"))

    io.open(OUT, "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")
    print("\n已写出:", OUT)


if __name__ == "__main__":
    main()
