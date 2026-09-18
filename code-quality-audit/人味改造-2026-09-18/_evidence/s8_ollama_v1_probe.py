# -*- coding: utf-8 -*-
"""S8 前置探针：验证 Ollama /v1/chat/completions 的流式行为。

必须实测，不能凭直觉：本项目已两次被 "/v1 端点静默忽略参数" 咬过
（num_ctx / repeat_penalty）。所以先看原始 SSE 报文长什么样，
再量首字延迟，最后确认分片拼接 == 完整回复。
"""
import json
import time
import urllib.request

URL = "http://localhost:11434/v1/chat/completions"
OUT = r"E:\Download\_tmp\s8_stream_probe.txt"
lines = []


def log(s):
    lines.append(str(s))


SYS = "你是 Ralsei，一只住在电脑桌面上的温柔小羊。说话口语化，1~3 句，不要分点。"
Q = "今天上班好累啊，被领导骂了一顿"

# ---------------- ① 非流式（对照） ----------------
body = {
    "model": "ralsei:v2",
    "messages": [{"role": "system", "content": SYS}, {"role": "user", "content": Q}],
    "temperature": 0.85,
    "max_tokens": 256,
    "stream": False,
}
req = urllib.request.Request(
    URL, data=json.dumps(body).encode("utf-8"),
    headers={"Content-Type": "application/json"})
log("=== ① 非流式（对照）===")
t0 = time.time()
with urllib.request.urlopen(req, timeout=60) as r:
    d = json.load(r)
t_all = time.time() - t0
full = d["choices"][0]["message"]["content"]
log("首字节=全文到达: %.2fs" % t_all)
log("内容: %s" % full)

# ---------------- ② 流式 ----------------
body["stream"] = True
req = urllib.request.Request(
    URL, data=json.dumps(body).encode("utf-8"),
    headers={"Content-Type": "application/json"})
log("")
log("=== ② 流式（stream=true）===")
t0 = time.time()
first = None
chunks = []
raw_head = []
status = None
ctype = None
try:
    with urllib.request.urlopen(req, timeout=60) as r:
        status = r.status
        ctype = r.headers.get("Content-Type")
        for raw in r:
            raw = raw.decode("utf-8", "replace")
            if len(raw_head) < 12:
                raw_head.append(raw.rstrip("\n"))
            s = raw.strip()
            if not s.startswith("data:"):
                continue
            payload = s[5:].strip()
            if payload == "[DONE]":
                break
            try:
                obj = json.loads(payload)
            except Exception:
                continue
            delta = (obj.get("choices") or [{}])[0].get("delta") or {}
            piece = delta.get("content")
            if piece:
                if first is None:
                    first = time.time() - t0
                chunks.append(piece)
except Exception as e:
    log("流式异常: %r" % (e,))

t_all2 = time.time() - t0
log("HTTP status=%s  Content-Type=%s" % (status, ctype))
log("首字延迟(first delta) = %s s" % ("%.2f" % first if first is not None else "N/A"))
log("全文耗时 = %.2fs" % t_all2)
log("分片数 = %d" % len(chunks))
joined = "".join(chunks)
log("拼接结果: %s" % joined)
log("拼接长度 = %d" % len(joined))
log("")
log("=== ③ 原始 SSE 前 12 行 ===")
for x in raw_head:
    log(repr(x))

open(OUT, "w", encoding="utf-8").write("\n".join(lines))
print("done")
