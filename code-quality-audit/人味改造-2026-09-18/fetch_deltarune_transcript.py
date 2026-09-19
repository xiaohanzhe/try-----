# -*- coding: utf-8 -*-
"""下载「带说话人标注」的 Deltarune 全剧本，供 `ralsei_lora_corpus.py` 建 LoRA 语料。

为什么必须换源（不是喜好问题）
------------------------------
最先用的是 hushbugger 的文本转储。它上面 `* ` 开头的行**没有说话人字段** ——
Susie / Lancer / Ralsei / 旁白全部混排：

    * Lancer!!!              ← Susie
    * What is it this time!? ← Lancer

按它建语料 = 把别人的台词标注成 Ralsei，属于**给训练数据投毒**，
比"我自己编 Ralsei 会说什么"更糟（至少我编的东西标签是对的）。判定过程见
`_evidence/corpus_build/feasibility.txt`（三条归属策略逐一算过，含反例）。

本数据集（`Deltarunefan/Deltarune-Complete-Transcript-Cleaned`）逐行带 `speaker` 字段，
字段结构 `{context, speaker, text}`，第 1~4 章共 11,599 行，其中 Ralsei 825 行。

用法
----
    C:\\Python311\\python.exe fetch_deltarune_transcript.py [下载目录]

默认下载目录 `E:\\Download\\_tmp\\corpus\\hf`（与 `ralsei_lora_corpus.py --src` 的默认值一致）。
**原始游戏文本不入库**（第三方素材，可随时按本脚本重下）；
入库的只有构建脚本、来源 sha256 前 16 位与统计结果。
"""
import json
import os
import ssl
import sys
import traceback
import urllib.request

DEFAULT_OUTDIR = r"E:\Download\_tmp\corpus\hf"
REPO = "Deltarunefan/Deltarune-Complete-Transcript-Cleaned"

OUTDIR = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_OUTDIR
REPORT = os.path.join(os.path.dirname(OUTDIR.rstrip("\\")), "hf_fetch.txt")

lines = []


def get(url, binary=False):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    with urllib.request.urlopen(req, timeout=60, context=ctx) as r:
        data = r.read()
    return data if binary else data.decode("utf-8", "replace")


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    lines.append("proxy env: HTTP_PROXY=%s HTTPS_PROXY=%s"
                 % (os.environ.get("HTTP_PROXY"), os.environ.get("HTTPS_PROXY")))

    # 1) 仓库文件树（根 + 各子目录）
    tree = json.loads(get("https://huggingface.co/api/datasets/%s/tree/main" % REPO))
    files = [t for t in tree if t.get("type") == "file"]
    dirs = [t["path"] for t in tree if t.get("type") == "directory"]
    lines.append("")
    lines.append("== 仓库文件 ==")
    for t in files:
        lines.append("  %-46s %s bytes" % (t["path"], t.get("size")))
    for d in dirs:
        try:
            sub = json.loads(get("https://huggingface.co/api/datasets/%s/tree/main/%s" % (REPO, d)))
        except Exception as e:
            lines.append("  ERR list %s: %r" % (d, e))
            continue
        for t in sub:
            if t.get("type") == "file":
                lines.append("  %-46s %s bytes" % (t["path"], t.get("size")))
            elif t.get("type") == "directory":
                dirs.append(t["path"])

    # 2) 下载 jsonl / json
    lines.append("")
    lines.append("== 下载 ==")
    targets = []
    for t in tree:
        if t.get("type") == "file" and t["path"].lower().endswith((".jsonl", ".json")):
            targets.append(t["path"])
    for d in dirs:
        try:
            sub = json.loads(get("https://huggingface.co/api/datasets/%s/tree/main/%s" % (REPO, d)))
        except Exception:
            continue
        for t in sub:
            if t.get("type") == "file" and t["path"].lower().endswith((".jsonl", ".json")):
                targets.append(t["path"])

    for p in sorted(set(targets)):
        url = "https://huggingface.co/datasets/%s/resolve/main/%s" % (REPO, p)
        dst = os.path.join(OUTDIR, p.replace("/", "__"))
        if os.path.exists(dst) and os.path.getsize(dst) > 0:
            lines.append("  SKIP(exists) %s" % dst)
            continue
        try:
            data = get(url, binary=True)
            with open(dst, "wb") as f:
                f.write(data)
            lines.append("  OK   %s  %d bytes" % (dst, len(data)))
        except Exception as e:
            lines.append("  ERR  %s  %r" % (url, e))


try:
    main()
except Exception:
    lines.append("EXCEPTION:\n" + traceback.format_exc())

if os.path.isdir(os.path.dirname(REPORT)):
    with open(REPORT, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
print("done, %d lines" % len(lines))
