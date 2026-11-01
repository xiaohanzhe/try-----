# -*- coding: utf-8 -*-
"""第130轮 · 探测 NPC 人设尾块现状（只读）。"""
import io
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
NPC = os.path.join(ROOT, "ralsei_pet", "assets", "npc")
IDX = os.path.join(NPC, "_personas.json")
DIR = os.path.join(NPC, "persona")

with io.open(IDX, "r", encoding="utf-8", newline="") as fh:
    idx = json.load(fh)

print("index keys =", sorted(idx.keys())[:8], "... 共", len(idx))
tail = idx.get("tail_text") or ""
print("tail_text: chars=%d bytes=%d" % (len(tail), len(tail.encode("utf-8"))))
print("tail 前 60 字: %r" % tail[:60])
print("tail 后 80 字: %r" % tail[-80:])
print("含标记【本项目补充 =", "【本项目补充" in tail)

files = sorted(f for f in os.listdir(DIR) if f.endswith(".txt"))
print("\npersona 文件数 =", len(files))
one = os.path.join(DIR, files[0])
raw = open(one, "rb").read()
t = raw.decode("utf-8")
i = t.find("【本项目补充")
print("样本 =", files[0])
print("  bytes=%d crlf=%d lf=%d" % (len(raw), raw.count(b"\r\n"), raw.count(b"\n")))
print("  标记位置 = %d / 总长 %d" % (i, len(t)))
print("  尾块（从标记到 EOF）= %r" % t[i:i + 80])
print("  尾块 EOL: CRLF=%d LF=%d" % (t[i:].count("\r\n"), t[i:].count("\n")))

# 索引条目样本
k = [k for k in idx.keys() if k != "tail_text"][0]
print("\n条目样本 %r = %r" % (k, idx[k] if not isinstance(idx[k], dict) else
                              {kk: (str(vv)[:40]) for kk, vv in idx[k].items()}))
