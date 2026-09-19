# -*- coding: utf-8 -*-
"""从「带说话人标注的原作剧本」构建 Ralsei LoRA 语料（SFT 对）。

语料来源与为什么换源
--------------------
用户口径（2026-09-19）：「走原作台词语料」。
最先拿到的是 hushbugger 的文本转储（`DELTARUNE.txt`）。**它不能用**——
里面 `* ` 行**没有说话人字段**，Susie / Lancer / Ralsei / 旁白全部混排：

    * Lancer!!!              ← Susie
    * What is it this time!? ← Lancer

按它建语料 = 把别人的台词标注成 Ralsei，属于**给训练数据投毒**，
比"我自己编 Ralsei 会说什么"更糟（至少我编的东西标签是对的）。
证据见 `feasibility.txt`（策略 A 只剩 116 行且全是战斗教学；策略 C 覆盖 52% 但按"场景"不按"说话人"）。

改用 `Deltarunefan/Deltarune-Complete-Transcript-Cleaned`（HuggingFace，CC 类数据）：
每行 `{context, speaker, text}`，**speaker 是逐行标的**。
第 1~4 章共 11599 行，其中 Ralsei 825 行 → 这就是"原作台词语料"。

配对规则（不编造输入）
--------------------
游戏剧本里只有"台词序列"，没有"用户说的话"。所以**输入侧只取剧本里真实存在的前文**：
对每一句 Ralsei 台词，把它**紧邻的前 K 句台词**作为输入（带说话人标签）。
这样 (输入 → 输出) 两边都是原作原文，没有一处是我写的。
代价：语境是"游戏场景"（Kris/Susie 在场），不是"桌宠主人聊天"——这个错位如实记录在 stats 里。

⚠ 第一版的错误（已修）：遇 Ralsei 台词就把上下文清空 → Ralsei 连说 3 句时，
第 2、3 句的输入是空的，**854 对里 422 对（49%）没有前文**，
等于教模型"对着空气说话"。Ralsei 有 42% 的台词是连续串内的第 2 句以后（见 speakers_peek.txt）。
现在改成**滚动窗口**：窗口里 Ralsei 自己说过的话也算前文（标签区分），
于是连续台词变成"接着自己上一句说"的续写对 —— 这正是对话语料该有的样子。

输入侧黑名单
------------
`Player` 是菜单选项（YES / SWEETS / [PLAYER NAME]），不是台词；
`Narrator` 是旁白（描述动作/环境），桌宠不面对旁白。
两者都不进输入侧，也不作为输出。

产物
----
  <out>/ralsei_lora_corpus.jsonl       训练/验证对（含 provenance）
  <out>/ralsei_lora_corpus_stats.txt   统计与人眼复核样例
"""
import argparse
import collections
import hashlib
import json
import os
import re
import unicodedata

DEFAULT_SRC = r"E:\Download\_tmp\corpus\hf"
CHAPS = (1, 2, 3, 4)

# 输入侧最多带几句前文；超过就把更早的截掉（保持短，贴近桌宠的短输入）
MAX_CTX_LINES = 3
# 占位/噪声台词：纯符号、纯省略号等，作为输出毫无信息量
JUNK = re.compile(r"^[\s\.\-…\*\(\)\[\]!\?！？，,。、]*$")


def norm(s):
    s = unicodedata.normalize("NFKC", s or "")
    s = s.replace("\u2019", "'").replace("\u201c", '"').replace("\u201d", '"')
    return re.sub(r"\s+", " ", s).strip()


def load_chapter(src, ch):
    p = os.path.join(src, "data__chap%d_dataset.jsonl" % ch)
    if not os.path.exists(p):
        raise SystemExit("缺少 %s —— 先跑同目录的 fetch_deltarune_transcript.py" % p)
    rows = []
    with open(p, encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if ln:
                rows.append(json.loads(ln))
    return p, rows


def sha8(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()[:16]


def build(src):
    pairs = []
    drop = collections.Counter()
    prov = {}

    for ch in CHAPS:
        path, rows = load_chapter(src, ch)
        prov["chap%d" % ch] = {"file": os.path.basename(path),
                               "rows": len(rows), "sha256_16": sha8(path)}

        # 按场景切段，段内保序；buf = 滚动窗口（含 Ralsei 自己说过的话）
        scene = None
        buf = []
        for r in rows:
            ctx = norm(r.get("context"))
            spk = norm(r.get("speaker"))
            txt = norm(r.get("text"))
            if ctx != scene:                    # 换场景 → 清空，不跨场景借前文
                scene, buf = ctx, []
                continue
            if not txt:
                drop["空台词"] += 1
                continue
            if spk == "Player":
                drop["菜单选项（Player，非台词）"] += 1
                continue
            if spk == "Narrator":
                drop["旁白（不入输入侧，也不产出）"] += 1
                continue
            if spk.startswith("Ralsei"):
                if JUNK.match(txt):
                    drop["Ralsei 纯省略号/符号"] += 1
                    continue
                win = buf[-MAX_CTX_LINES:]
                pairs.append({
                    "chapter": ch,
                    "scene": scene,
                    "input": "\n".join("%s：%s" % (a, b) for a, b in win),
                    "output": txt,
                    "ctx_speakers": [a for a, _ in win],
                    "has_ctx": bool(win),
                    "self_ctx": any(a.startswith("Ralsei") for a, _ in win),
                    "inner": txt.startswith("(") and txt.endswith(")"),
                })
                # 自己这句也要进窗口 —— 下一句就变成"接着自己说"
                buf.append(("Ralsei", txt))
            else:
                buf.append((spk, txt))
    return pairs, drop, prov


def split(pairs, val_ratio=0.12):
    """按场景切分验证集 —— 同一场景的行不能同时出现在两边（否则是泄漏）。"""
    scenes = sorted({(p["chapter"], p["scene"]) for p in pairs})
    # 稳定：按场景名哈希排序后取前 val_ratio
    scenes.sort(key=lambda t: hashlib.md5(("%d|%s" % t).encode("utf-8")).hexdigest())
    n_val = max(1, int(len(scenes) * val_ratio))
    val_scenes = set(scenes[:n_val])
    tr = [p for p in pairs if (p["chapter"], p["scene"]) not in val_scenes]
    va = [p for p in pairs if (p["chapter"], p["scene"]) in val_scenes]
    return tr, va, len(scenes), len(val_scenes)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=DEFAULT_SRC)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    pairs, drop, prov = build(a.src)
    tr, va, n_sc, n_val_sc = split(pairs)

    os.makedirs(a.out, exist_ok=True)
    jl = os.path.join(a.out, "ralsei_lora_corpus.jsonl")
    with open(jl, "w", encoding="utf-8", newline="\n") as f:
        for i, p in enumerate(pairs):
            is_val = (p["chapter"], p["scene"]) in {(x["chapter"], x["scene"]) for x in va}
            rec = {
                "id": "ralsei-%04d" % i,
                "split": "val" if is_val else "train",
                "source": "Deltarunefan/Deltarune-Complete-Transcript-Cleaned",
                "chapter": p["chapter"],
                "scene": p["scene"],
                "input": p["input"],
                "output": p["output"],
                "meta": {"ctx_speakers": p["ctx_speakers"],
                         "has_ctx": p["has_ctx"],
                         "inner_thought": p["inner"]},
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # ---------------- 统计
    L = []
    L.append("Ralsei LoRA 语料构建报告")
    L.append("=" * 70)
    L.append("来源仓库 : Deltarunefan/Deltarune-Complete-Transcript-Cleaned（HuggingFace）")
    L.append("来源说明 : 逐行标注 speaker 的完整剧本；**不是** hushbugger 的无标注转储")
    for k in sorted(prov):
        v = prov[k]
        L.append("  %s  %s  rows=%d  sha256_16=%s" % (k, v["file"], v["rows"], v["sha256_16"]))
    L.append("")
    L.append("-- 产出 --")
    L.append("配对总数      : %d" % len(pairs))
    L.append("  训练 / 验证 : %d / %d" % (len(tr), len(va)))
    L.append("  场景总数    : %d（验证集占 %d 个场景，按场景切分避免泄漏）" % (n_sc, n_val_sc))
    L.append("")
    L.append("-- 输入侧构成 --")
    has = sum(1 for p in pairs if p["has_ctx"])
    slf = sum(1 for p in pairs if p["self_ctx"])
    L.append("  带前文（>=1 句台词）      : %d (%.0f%%)" % (has, 100.0 * has / len(pairs)))
    L.append("  其中前文含 Ralsei 自己    : %d (%.0f%%)" % (slf, 100.0 * slf / len(pairs)))
    L.append("  无前文（场景第一句）      : %d" % (len(pairs) - has))
    cs = collections.Counter(s for p in pairs for s in p["ctx_speakers"])
    L.append("  前文说话人分布（前 10）   : %s" % dict(cs.most_common(10)))
    L.append("")
    L.append("-- 输出侧构成 --")
    ln = [len(p["output"]) for p in pairs]
    L.append("  字符数 min/均值/中位/max  : %d / %.1f / %d / %d"
             % (min(ln), sum(ln) / len(ln), sorted(ln)[len(ln) // 2], max(ln)))
    L.append("  总字符                    : %d" % sum(ln))
    L.append("  内心独白型（整体括号）    : %d" % sum(1 for p in pairs if p["inner"]))
    L.append("  最长/最短样例             : %r / %r"
             % (max(pairs, key=lambda p: len(p["output"]))["output"][:60],
                min(pairs, key=lambda p: len(p["output"]))["output"][:60]))
    L.append("")
    L.append("-- 丢弃计数 --")
    for k, v in drop.most_common():
        L.append("  %-28s %d" % (k, v))
    L.append("")
    L.append("-- 人眼复核：随机 25 对（seed 固定）--")
    import random
    rnd = random.Random(20260919)
    for p in rnd.sample(pairs, min(25, len(pairs))):
        L.append("")
        L.append("  [%s] %s" % (p["scene"][:40], " 带前文" if p["has_ctx"] else " 无前文"))
        if p["input"]:
            for x in p["input"].split("\n"):
                L.append("      IN  %s" % x[:96])
        L.append("      OUT %s" % p["output"][:96])
    L.append("")
    L.append("-- 已知错位（必须写进结论，不能藏）--")
    L.append("  1) 语言：全英文。桌宠说中文 → 直接用会诱导英文输出，需翻译层（= 引入我的转写）。")
    L.append("  2) 语境：输入是 Kris/Susie 在剧情里的话，不是桌宠主人的闲聊。")
    L.append("  3) 量级：%d 对 / %d 字符，对 4B 模型 LoRA 属于偏小，需靠早停与低 rank 控过拟合。"
             % (len(pairs), sum(ln)))
    L.append("  4) 覆盖面：只到第 4 章（第 5 章官方文本未收录进该数据集）。")

    st = os.path.join(a.out, "ralsei_lora_corpus_stats.txt")
    with open(st, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(L) + "\n")
    print("wrote %s\nwrote %s\npairs=%d train=%d val=%d"
          % (jl, st, len(pairs), len(tr), len(va)))


if __name__ == "__main__":
    main()
