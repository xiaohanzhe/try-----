# -*- coding: utf-8 -*-
"""第130轮 · 探测 77 张训练卡的 patch/eval 存量（只读，决定重建时怎么保）。"""
import io
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
CARDS = os.path.join(ROOT, "ralsei_pet", "assets", "npc", "_training", "cards")

files = sorted(f for f in os.listdir(CARDS) if f.endswith(".json") and f != "_index.json")
print("卡片数 =", len(files))

n_patch = n_eval = n_eval_real = 0
rows = []
for fn in files:
    p = os.path.join(CARDS, fn)
    c = json.loads(io.open(p, "rb").read().decode("utf-8"))
    pt = (c.get("patch") or "").strip()
    ev = c.get("eval") or {}
    if pt:
        n_patch += 1
    if ev:
        n_eval += 1
        # "真评测数据"= 不只是 note 默认值
        keys = set(ev.keys()) - {"note"}
        if keys:
            n_eval_real += 1
            rows.append((fn, len(pt), sorted(keys)))

print("含非空 patch =", n_patch)
print("含非空 eval  =", n_eval, "（其中带 note 以外字段 =", n_eval_real, "）")
for r in rows[:12]:
    print("   ", r)
