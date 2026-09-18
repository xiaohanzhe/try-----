# -*- coding: utf-8 -*-
"""决定实现方式：requests 的三种读法，谁的"首字延迟"最低。

背景：urllib 的 `for line in resp`（= BufferedReader.readline）实测 0.23s 首字。
但项目里统一用 requests，需要确认 requests 侧不引入额外缓冲延迟。
"""
import json
import time

import requests

URL = "http://localhost:11434/v1/chat/completions"
OUT = r"E:\Download\_tmp\s8_latency_probe.txt"
SYS = "你是 Ralsei，一只住在电脑桌面上的温柔小羊。说话口语化，1~3 句。"
Q = "今天上班好累啊，被领导骂了一顿"

lines = []


def body():
    return {
        "model": "ralsei:v2",
        "messages": [{"role": "system", "content": SYS},
                     {"role": "user", "content": Q}],
        "temperature": 0.85,
        "max_tokens": 256,
        "stream": True,
    }


def t_run(name, reader):
    """reader(resp) -> (first_delta_seconds, text, n_parts)"""
    t0 = time.time()
    resp = requests.post(URL, json=body(),
                         headers={"Content-Type": "application/json"},
                         timeout=60, stream=True)
    try:
        return reader(resp, t0)
    finally:
        try:
            resp.close()
        except Exception:
            pass


def _piece(payload):
    try:
        obj = json.loads(payload)
    except Exception:
        return ""
    ch = obj.get("choices") or []
    if not ch:
        return ""
    return (ch[0].get("delta") or {}).get("content") or ""


def r_iter_lines_default(resp, t0):
    first, parts = None, []
    for raw in resp.iter_lines():
        s = (raw or b"").decode("utf-8", "replace").strip()
        if not s.startswith("data:"):
            continue
        p = s[5:].strip()
        if p == "[DONE]":
            break
        pc = _piece(p)
        if pc:
            if first is None:
                first = time.time() - t0
            parts.append(pc)
    return first, "".join(parts), len(parts)


def r_iter_lines_1(resp, t0):
    first, parts = None, []
    for raw in resp.iter_lines(chunk_size=1):
        s = (raw or b"").decode("utf-8", "replace").strip()
        if not s.startswith("data:"):
            continue
        p = s[5:].strip()
        if p == "[DONE]":
            break
        pc = _piece(p)
        if pc:
            if first is None:
                first = time.time() - t0
            parts.append(pc)
    return first, "".join(parts), len(parts)


def r_raw_readline(resp, t0):
    first, parts = None, []
    while True:
        raw = resp.raw.readline()
        if not raw:
            break
        s = raw.decode("utf-8", "replace").strip()
        if not s.startswith("data:"):
            continue
        p = s[5:].strip()
        if p == "[DONE]":
            break
        pc = _piece(p)
        if pc:
            if first is None:
                first = time.time() - t0
            parts.append(pc)
    return first, "".join(parts), len(parts)


for name, fn in (("iter_lines(默认)", r_iter_lines_default),
                 ("iter_lines(chunk_size=1)", r_iter_lines_1),
                 ("resp.raw.readline()", r_raw_readline)):
    try:
        first, text, n = t_run(name, fn)
        lines.append("%-26s 首字=%s  分片=%d  文本=%s" % (
            name, ("%.2fs" % first) if first else "N/A", n, text[:40]))
    except Exception as e:
        lines.append("%-26s 异常: %r" % (name, e))

open(OUT, "w", encoding="utf-8").write("\n".join(lines))
print("done")
