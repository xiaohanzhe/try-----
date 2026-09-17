# -*- coding: utf-8 -*-
"""Ralsei 对话 AI 人味诊断探针（只读，不改任何工程文件）。

目的：
  1. 用 /api/show 取 ralsei 的 SYSTEM 原文（UTF-8 直读，排除 PowerShell 管道乱码误判）
  2. 判定「App 传入 system message」是否**顶掉**了 Modelfile 里的角色设定
  3. 实测上下文窗口（num_ctx）是否会截断长 system + 历史 + 联想
  4. 取样两条真实对话，肉眼比对"人味"
"""
import json
import urllib.request

BASE = "http://localhost:11434"
OUT = r"E:\Download\_tmp\probe_ralsei_result.txt"
lines = []


def log(s=""):
    lines.append(str(s))


def post(path, payload, timeout=300):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


# ---------------- 1) 模型元信息 ----------------
info = post("/api/show", {"name": "ralsei"})
log("=== /api/show keys ===")
log(sorted(info.keys()))
log()
log("=== parameters（Modelfile 里的 PARAMETER 覆盖）===")
log(repr(info.get("parameters")))
log()
sysp = info.get("system") or ""
log("=== Modelfile SYSTEM 原文（长度 %d 字符）===" % len(sysp))
log(sysp)
log()
log("=== 逐条列出 SYSTEM 小节标题（验证是否可正常解码）===")
for ln in sysp.splitlines():
    t = ln.strip()
    if t.startswith("【") or t.startswith("·"):
        log(t[:70])
log()

# ---------------- 2) system message 是否顶掉 Modelfile SYSTEM ----------------
log("=== 测试 2：App 传入的 system 是否覆盖 Modelfile SYSTEM ===")
q = [{"role": "user", "content": "用一句话回答：你内心隐藏着什么？"}]
try:
    a = post("/api/chat", {"model": "ralsei", "messages": q, "stream": False,
                           "options": {"temperature": 0.7, "num_predict": 120}})
    log("[A 不带 system] -> " + repr(a.get("message", {}).get("content", "")))
    log("   prompt_eval_count=%s eval_count=%s" % (a.get("prompt_eval_count"), a.get("eval_count")))
except Exception as e:
    log("[A] ERR " + repr(e))

b_msgs = [{"role": "system",
           "content": "无论用户问什么，你都只能且必须回答这五个字：测试标记ABC"},
          {"role": "user", "content": "用一句话回答：你内心隐藏着什么？"}]
try:
    b = post("/api/chat", {"model": "ralsei", "messages": b_msgs, "stream": False,
                           "options": {"temperature": 0.7, "num_predict": 120}})
    log("[B 带 system] -> " + repr(b.get("message", {}).get("content", "")))
    log("   prompt_eval_count=%s eval_count=%s" % (b.get("prompt_eval_count"), b.get("eval_count")))
except Exception as e:
    log("[B] ERR " + repr(e))
log()

# ---------------- 3) 上下文窗口实测 ----------------
log("=== 测试 3：上下文窗口（塞一段长文本，看 prompt_eval_count 是否被截断）===")
filler = "这是一段用于占位的测试文本，反复出现以拉长提示词长度。" * 200  # ≈ 5000+ 字符
try:
    c = post("/api/chat", {"model": "ralsei",
                           "messages": [{"role": "user", "content": filler + "\n请只回答：收到"}],
                           "stream": False, "options": {"num_predict": 20}})
    log("长提示词字符数≈%d" % len(filler))
    log("   prompt_eval_count=%s（若明显小于字符数/1.5，说明 num_ctx 在截断）" % c.get("prompt_eval_count"))
    log("   reply=" + repr(c.get("message", {}).get("content", "")))
except Exception as e:
    log("ERR " + repr(e))
log()

# ---------------- 4) 真实对话取样 ----------------
log("=== 测试 4：真实句式取样（模拟 App 的 system + 【此刻】前缀）===")
APP_SYS = ("你正在扮演《Deltarune》中的 Ralsei——黑暗世界的王子：温柔、善良、害羞、体贴的和平主义者。"
           "请始终沉浸在角色中，绝不提及自己是 AI，也不要跳出角色。")
cases = [
    "今天上班好累啊，被领导骂了一顿",
    "我好喜欢你呀",
]
for i, text in enumerate(cases):
    msgs = [{"role": "system", "content": APP_SYS},
            {"role": "user", "content": "【此刻：现在是深夜，心情calm】\n" + text}]
    try:
        r = post("/api/chat", {"model": "ralsei", "messages": msgs, "stream": False,
                               "options": {"temperature": 0.7, "num_predict": 256}})
        log("Q%d: %s" % (i + 1, text))
        log("A%d: %s" % (i + 1, r.get("message", {}).get("content", "")))
        log()
    except Exception as e:
        log("Q%d ERR %r" % (i + 1, e))

with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print("WROTE", OUT)
