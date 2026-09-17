# -*- coding: utf-8 -*-
"""滑字（「诪、诪……」本该是「诶、诶？！」）成因的可证伪探针。

假说：`repeat_penalty=1.15` 会惩罚"重复同一个 token"。而 Ralsei 的招牌反应
恰好是**重复语气词**（诶、诶？！ / 我、我其实……）。惩罚把第二次「诶」推到
低概率的替代 token 上 → 采出同码位的生僻字「诪」。

为什么必须走 Ollama 原生 /api/chat：`/v1/chat/completions` **静默忽略**
`repeat_penalty` 与 `num_ctx`（实测，见诊断报告 E3），只有原生端点的 options 生效。

三组对照（同一 system / 同一问题 / 同一温度，只动一个参数）：
  A  rp=1.15 top_p=0.92   ← 当前 ralsei:v2 的实际配置
  B  rp=1.00 top_p=0.92   ← 若假说成立，滑字应消失
  C  rp=1.15 top_p=0.90   ← 对照组：只是收窄尾部采样
结论判据：A/B 谁出现叠字滑字（同一生僻字 + 「、」重复）次数多。
"""
import json
import os
import re
import urllib.request

OUT = r"E:\Download\_tmp\rp_probe.txt"
PERSONA = open(
    r"C:\Users\23002\Desktop\项目文件夹\try - 副本\ralsei_pet\assets\ralsei_persona.md",
    encoding="utf-8").read()
CFG = json.load(open(r"E:\RalseiMemory\config.json", encoding="utf-8"))
MODEL = CFG["api"]["model"]
CTX = "【此刻】现在是深夜，天气晴，心情平静，有点疲惫，主人的名字是小豆"
SYSTEM = PERSONA + "\n\n" + CTX
Q = "我好喜欢你呀"
N = 3

# 常用语气词/叠字（这些重复是**想要的**，不算滑字）
COMMON = set("诶唔咕嘟暖啊呀哦嗯呢吧呜咦嘿哈嘛啦喔哎喂嗯")


def is_slip(text):
    """滑字判据：同一个汉字被「、」连着重写 ≥2 次，且这个字不是常用语气词。"""
    for m in re.finditer(r'(.)、\1', text):
        if m.group(1) not in COMMON:
            return m.group(0)
    return None


def call(opts):
    body = {"model": MODEL,
            "messages": [{"role": "system", "content": SYSTEM},
                         {"role": "user", "content": Q}],
            "options": dict(opts, num_ctx=8192, num_predict=256),
            "stream": False}
    req = urllib.request.Request("http://localhost:11434/api/chat",
                                data=json.dumps(body).encode("utf-8"),
                                headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        d = json.loads(r.read().decode("utf-8"))
    return (d.get("message") or {}).get("content", "").strip()


ARMS = [
    ("A  rp=1.15 top_p=0.92（= 当前 ralsei:v2）",
     {"temperature": 0.85, "top_p": 0.92, "repeat_penalty": 1.15}),
    ("B  rp=1.00 top_p=0.92（假说：滑字该消失）",
     {"temperature": 0.85, "top_p": 0.92, "repeat_penalty": 1.00}),
    ("C  rp=1.15 top_p=0.90（对照：只收窄尾部）",
     {"temperature": 0.85, "top_p": 0.90, "repeat_penalty": 1.15}),
]

lines = []
lines.append("问题：%s   每题采样 %d 次" % (Q, N))
lines.append("模型：%s   判据：同一非语气词汉字被「、」重写 ≥2 次" % MODEL)
lines.append("")
tally = {}
for label, opts in ARMS:
    lines.append("=" * 76)
    lines.append(label)
    lines.append("=" * 76)
    slips = 0
    for i in range(1, N + 1):
        try:
            txt = call(opts)
        except Exception as e:
            lines.append("  #%d ERR %r" % (i, e))
            continue
        s = is_slip(txt)
        if s:
            slips += 1
        lines.append("  #%d %s %r" % (i, ("[滑字:%s]" % s) if s else "        ", txt))
    tally[label] = (slips, N)
    lines.append("  → 滑字 %d/%d" % (slips, N))
    lines.append("")

lines.append("=" * 76)
lines.append("汇总")
lines.append("=" * 76)
for k, (s, n) in tally.items():
    lines.append("  %-46s 滑字 %d/%d" % (k, s, n))

os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
open(OUT, "w", encoding="utf-8").write("\n".join(lines))
print("WROTE", OUT)
