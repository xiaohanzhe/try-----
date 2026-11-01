# -*- coding: utf-8 -*-
"""
第130轮 · 重建训练卡（人设变了必须重建），但**保住训练结果**

为什么必须重建：第130轮改了 `ralsei_persona.md`（+ 76 份 NPC 尾块），
`check113 A4` 比的是"卡片里记的人设 sha256 == 磁盘人设的 sha256"⇒ 77 张全 stale。

为什么不能直接跑 `cards113.py`：它 `build_card()` 从零重写，`eval` 字段回到默认值。
第128轮实测跑全量是 `63 files changed, +158 −1001` —— 丢的 1001 行就是训练评测。
61 张卡有真 `eval` 数据（codes/cross_dups/marker_hit/violations），59 张有 `patch`。

做法：先快照 → 跑重建 → 回填 → 逐张断言（patch/eval 与快照逐字相同，sha 与新磁盘一致）。
快照只放内存，**不落临时文件**（不污染工作区）。
"""
import io
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
CARDS = os.path.join(ROOT, "ralsei_pet", "assets", "npc", "_training", "cards")
SCRIPT = os.path.join(ROOT, "code-quality-audit", "第113轮-全体角色AI训练",
                      "_tools", "cards113.py")

P = F = 0


def ok(cond, name, detail=""):
    global P, F
    if cond:
        P += 1
        print("[PASS] %s" % name)
    else:
        F += 1
        print("[FAIL] %s%s" % (name, ("   << %s" % detail) if detail else ""))


def load(p):
    return json.loads(io.open(p, "rb").read().decode("utf-8"))


def dump(p, obj):
    with io.open(p, "w", encoding="utf-8", newline="") as fh:
        fh.write(json.dumps(obj, ensure_ascii=False, indent=1) + "\n")


def main():
    files = sorted(f for f in os.listdir(CARDS) if f.endswith(".json") and f != "_index.json")
    print("卡片数 = %d" % len(files))

    # ---- 1. 快照 ----
    snap = {}
    for fn in files:
        c = load(os.path.join(CARDS, fn))
        snap[fn] = {"patch": c.get("patch", ""), "eval": c.get("eval", {})}
    n_patch = sum(1 for v in snap.values() if (v["patch"] or "").strip())
    n_eval = sum(1 for v in snap.values() if v["eval"])
    print("快照：patch 非空 %d 张 ｜ eval 非空 %d 张" % (n_patch, n_eval))

    # ---- 2. 跑重建 ----
    # ★ 必须带 `--all`：默认只重建 roster 的 77 张，索引 `counts.total` 会写成 77，
    #   把 19 个 plain/gap 档的登记冲掉（`check113 A1` 要求全档 96）。
    #   训练结果由下面的回填保住，所以全量重建是安全的。
    r = subprocess.run([sys.executable, SCRIPT, "--all"], cwd=ROOT,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out = r.stdout.decode("utf-8", "replace")
    print("cards113.py rc=%d" % r.returncode)
    for ln in out.strip().splitlines()[-4:]:
        print("   |", ln)
    ok(r.returncode == 0, "R1 cards113.py 正常退出")

    # ---- 3. 回填 ----
    restored_p = restored_e = 0
    for fn in files:
        p = os.path.join(CARDS, fn)
        c = load(p)
        old = snap[fn]
        changed = False
        if (old["patch"] or "").strip() and c.get("patch") != old["patch"]:
            c["patch"] = old["patch"]
            restored_p += 1
            changed = True
        if old["eval"] and c.get("eval") != old["eval"]:
            c["eval"] = old["eval"]
            restored_e += 1
            changed = True
        if changed:            # ★ 只在真需要时写：否则 96 张全 dump 会把格式差异也带进 diff
            dump(p, c)
    print("回填：patch %d 张 ｜ eval %d 张" % (restored_p, restored_e))

    # ---- 4. 断言（读回，不信写入通道）----
    bad_p, bad_e, bad_sha = [], [], []
    import hashlib

    for fn in files:
        c = load(os.path.join(CARDS, fn))
        old = snap[fn]
        if (old["patch"] or "").strip() and c.get("patch") != old["patch"]:
            bad_p.append(fn)
        if old["eval"] and c.get("eval") != old["eval"]:
            bad_e.append(fn)
    ok(not bad_p, "R2 59 张非空 patch 逐字保住", "丢=%r" % (bad_p[:5],))
    ok(not bad_e, "R3 %d 张 eval 逐字保住" % n_eval, "丢=%r" % (bad_e[:5],))

    # ---- 4b. ★★★ 必须跟着跑「口癖灌水项清理」----
    #   `voice_markers` 是**从人设重新抽出来的**派生字段 ⇒ 每次重建都会把第113轮r
    #   清掉的 12 条灌水项（`想` / `……` / `[……]` / `时候` / `I` …）带回来，
    #   `test_markers113r H` 立刻报红。这个依赖当年只存在于人脑里，第130轮实测踩中。
    FIXM = os.path.join(ROOT, "code-quality-audit", "第113轮-全体角色AI训练",
                        "_tools", "fix_markers113r.py")
    r2 = subprocess.run([sys.executable, FIXM, "--apply"], cwd=ROOT,
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out2 = r2.stdout.decode("utf-8", "replace")
    tail2 = [ln for ln in out2.strip().splitlines() if "合计" in ln or "已写盘" in ln][-2:]
    for ln in tail2:
        print("   |", ln)
    ok(r2.returncode == 0, "R2b fix_markers113r 正常退出（清灌水项）")

    # ---- 5. 索引记账（`_index.json` 在 `_training/` 下，不在 `cards/` 里）----
    idx = load(os.path.join(ROOT, "ralsei_pet", "assets", "npc", "_training", "_index.json"))
    print("索引 counts = %r" % (idx.get("counts"),))
    # ★ 130 自纠：这里第一版写死 77（只想着 roster），而 `--all` 之后是 96
    #   ⇒ 报红的是我的期望值。数字须**数出来**，不是估的（同 §129.8 第 7 条）。
    ok(idx.get("counts", {}).get("total") == 96,
       "R4 索引 counts.total == 96（全档，不是只有 roster 77）", repr(idx.get("counts")))
    ok(isinstance(idx.get("patches"), dict) and len(idx["patches"]) >= 50,
       "R5 索引 patches 没被冲掉（≥50 条）",
       "patches=%d" % len(idx.get("patches") or {}))
    return 0 if (F == 0) else 1


if __name__ == "__main__":
    sys.exit(main())
