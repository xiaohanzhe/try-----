# -*- coding: utf-8 -*-
u"""第90轮 · 场景 JSON 里的物件素材名 → 磁盘文件 的解析率（只读）

判据：每个出现过的 `objs/...` 名字，去 `assets/scenes/<name>` 查是否存在。
解析不到的名字在渲染时会被 plan_frame 回落成 1x1 → 画出来是个像素点。
"""
import io
import json
import os
import re

SCENES = r"C:\Users\23002\Desktop\项目文件夹\try - 副本\ralsei_pet\assets\scenes"
PAT = re.compile(r'"(objs/[^"]+)"')

names = {}
for dp, _dn, fn in os.walk(SCENES):
    for f in fn:
        if not f.endswith(".json"):
            continue
        p = os.path.join(dp, f)
        try:
            s = io.open(p, encoding="utf-8", errors="replace").read()
        except Exception:
            continue
        for m in PAT.findall(s):
            names[m] = names.get(m, 0) + 1

ok, bad = [], []
for nm, n in sorted(names.items()):
    fp = os.path.join(SCENES, *nm.split("/"))
    (ok if os.path.exists(fp) else bad).append((nm, n))

print("=" * 70)
print("场景 JSON 中 `objs/...` 素材名解析情况")
print("=" * 70)
print("  出现过的不同名字 = %d  （引用次数合计 %d）"
      % (len(names), sum(names.values())))
print("  可直接解析     = %d" % len(ok))
print("  **解析不到**   = %d   （引用次数合计 %d）"
      % (len(bad), sum(n for _nm, n in bad)))
print()
if bad:
    print("  解析不到的名单（最多 40 条）：")
    for nm, n in bad[:40]:
        print("    %-46s x%d" % (nm, n))
    print()
    # 给"猜测修复"：去掉/补上 _0 后缀能否命中
    fixed = 0
    for nm, _n in bad:
        base, ext = os.path.splitext(nm)
        cands = [base + "_0" + ext, base[:-2] + ext if base.endswith("_0") else None]
        if any(c and os.path.exists(os.path.join(SCENES, *c.split("/"))) for c in cands):
            fixed += 1
    print("  其中「补/去 _0 帧号后缀即可命中」的 = %d / %d" % (fixed, len(bad)))
print()
print("  样例（可解析，前 10 条）：")
for nm, n in ok[:10]:
    print("    %-46s x%d" % (nm, n))
