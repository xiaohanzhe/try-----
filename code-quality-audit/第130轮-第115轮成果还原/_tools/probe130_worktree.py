# -*- coding: utf-8 -*-
"""读当年那棵 worktree 里的人设（只读），并与主仓库的 7/11 节对比。"""
import io
import os

WT = r"C:\Users\23002\WorkBuddy\Worktrees\try - 副本\main-a7556e9c\ralsei_pet\assets\ralsei_persona.md"
MAIN = r"C:\Users\23002\Desktop\项目文件夹\try - 副本\ralsei_pet\assets\ralsei_persona.md"

for tag, p in (("WORKTREE", WT), ("MAIN(now)", MAIN)):
    print("=" * 20, tag)
    if not os.path.isfile(p):
        print("  不存在：", p)
        continue
    raw = open(p, "rb").read()
    t = raw.decode("utf-8")
    print("  bytes=%d chars=%d crlf=%d bom=%s" % (len(raw), len(t),
                                                  raw.count(b"\r\n"),
                                                  raw.startswith(b"\xef\xbb\xbf")))
    secs = [l for l in t.splitlines() if l.startswith("——")]
    print("  节数 = %d" % len(secs))
    for s in secs:
        print("     ", s)
