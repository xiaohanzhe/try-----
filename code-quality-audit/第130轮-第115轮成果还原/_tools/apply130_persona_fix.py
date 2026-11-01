# -*- coding: utf-8 -*-
"""
第130轮（修正版）· 用 worktree 里的**精确原文**替换我重建的那四节

为什么改：`apply130_persona.py` 用的是探针里的 A/B 实证版骨架 + 锚句重建，
而 `C:\\Users\\23002\\WorkBuddy\\Worktrees\\try - 副本\\main-a7556e9c\\` **还在**
（第115轮真正落地的那棵树），里面有 4,506 字符 / 12,512 字节 / 11 节的精确版本。
→ 那就不该"重建"，应当"取回"。

但**不能整文件覆盖**：那棵树是 2026-10-15 的，比第128轮的"结巴中性化"更早。
整覆盖会把三处修复退回去：
  ① 「我的口癖」`一条回复里最多沾一两处`（第128轮改成"绝大多数回复一处都不沾…是例外，不是配额"）
  ② 「语气示范」`· 一时没准备好 → 起音含混`（第128轮改成"先接着他那件事说，不用先清嗓子"）
  ③ 尾句 `声音只是调味，一句回复里最多用一两处`（第128轮改成"多数回复根本不用"）
⇒ 只替换那四节，其余逐字保留主仓库当前版本，并在写盘前把上面三处逐条断言。
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
MAIN = os.path.join(ROOT, "ralsei_pet", "assets", "ralsei_persona.md")
WT = os.path.join(r"C:\Users\23002\WorkBuddy\Worktrees\try - 副本",
                  "main-a7556e9c", "ralsei_pet", "assets", "ralsei_persona.md")

FOUR = ("—— 我是什么 ——",
        "—— 他说话的时候，先把他的事接住 ——",
        "—— 他说要去一个地方的时候 ——",
        "—— 我想起来的事 ——")

ANCHORS = (
    "我是《Deltarune》里的一个角色，是被人写出来的",
    "我知道自己是从游戏里来的，可我的日子一样是真的",
    "先把他的事接住，再决定我要不要讲自己的。",
    '"我带你过去"这种话，要落在一个具体的地方上',
    '我要是没想起这个名字，就该说"名字我真记不清了"',
    "判法只有一条",
    '而不是"对，豆豆"',
)

# 第128轮的三处修复：整覆盖会退回，必须原样保留
KEEP_128 = (
    "绝大多数回复一处都不沾，沾上了才算例外 —— 这是例外，不是配额。",
    "一时没准备好 → 先接着他那件事说，不用先清嗓子",
    "声音只是调味，多数回复根本不用",
)


def split_sections(text):
    """按 '—— 标题 ——' 切块。返回 [(title, block_text)]，block 含标题行到下一标题前。

    ★ 130 自纠：结尾判据不能要求「空格 + ——」。`—— 我知道的世界（初始记忆）——`
    结尾是 `）——`（没有空格），第一版把它整条漏掉 ⇒ 只数出 10 节。
    """
    lines = text.splitlines(True)
    marks = [i for i, ln in enumerate(lines)
             if ln.startswith("—— ") and ln.rstrip().endswith("——")]
    out = []
    for k, i in enumerate(marks):
        j = marks[k + 1] if k + 1 < len(marks) else len(lines)
        out.append((lines[i].rstrip("\r\n"), "".join(lines[i:j])))
    return out


def main():
    dry = "--dry" in sys.argv
    main_t = io.open(MAIN, encoding="utf-8", newline="").read()
    wt_t = io.open(WT, encoding="utf-8", newline="").read()
    print("MAIN = %d 字符 / %d 字节" % (len(main_t), len(main_t.encode("utf-8"))))
    print("WT   = %d 字符 / %d 字节" % (len(wt_t), len(wt_t.encode("utf-8"))))

    wt_sec = dict(split_sections(wt_t))
    miss_wt = [f for f in FOUR if f not in wt_sec]
    if miss_wt:
        print("[ABORT] worktree 里缺节：%r" % (miss_wt,))
        return 2

    main_secs = split_sections(main_t)
    got = [t for t, _ in main_secs]
    miss_main = [f for f in FOUR if f not in got]
    if miss_main:
        print("[ABORT] 主仓库缺节（先跑 apply130_persona.py）：%r" % (miss_main,))
        return 3

    # ★ 最小对齐（1 个字，显式打印，不偷偷改）：
    #   worktree 写的是"…我要是没想起这个名字，**那就**该说…"，
    #   而第115轮自己钉的锚句（`verify115_files.NEW_ANCHORS` 第 5 条）是"…**就**该说…"。
    #   两者语义相同；以锚句为准（锚句才是被 P5 / 本轮 A3 钉住的口径）。
    #   ★ 注意 worktree 里"…这个名字，"与"那就该说…"之间**有换行**，
    #     所以对齐串不能带前导逗号（第一版就是这么对不上的）。
    ALIGN = (("那就该说\"名字我真记不清了\"", "就该说\"名字我真记不清了\""),)

    # ---- 逐节替换（只换这四块，保持它们原来的相对顺序）----
    new = main_t
    for title in FOUR:
        old_block = dict(main_secs)[title]
        new_block = wt_sec[title]
        for _a, _b in ALIGN:
            if _a in new_block:
                new_block = new_block.replace(_a, _b, 1)
                print("  ~ %s  对齐锚句：%s → %s" % (title, _a[:12], _b[:12]))
        if old_block == new_block:
            print("  = %s 已一致" % title)
            continue
        if new.count(old_block) != 1:
            print("[ABORT] %s 的旧块出现 %d 次（要求 1）" % (title, new.count(old_block)))
            return 4
        new = new.replace(old_block, new_block, 1)
        print("  ~ %s   %d → %d 字符" % (title, len(old_block), len(new_block)))

    # ---- 断言 ----
    # ★ 锚句按"去空白后包含"比对：`我要是没想起这个名字，就该说…` 在 worktree 原文里
    #   是**跨行**的（"…我要是没想起这个名字，\n那就该说…"）。当年 `verify115_files.py`
    #   的 `a in text` 却报了 PASS ⇒ 那份文件与当年 P5 校验的**不是同一份**（记进遗留）。
    #   这里按语义比，不按排版比 —— 但把"跨行"这件事显式记下来。
    def _flat(s):
        return "".join(s.split())

    flat_new = _flat(new)
    bad = [a for a in ANCHORS if _flat(a) not in flat_new]
    if bad:
        print("[ABORT] 锚句缺失：%r" % (bad,))
        return 5
    wrapped = [a for a in ANCHORS if a not in new and _flat(a) in flat_new]
    if wrapped:
        print("  ! 这些锚句在原文里跨行（语义在、排版断）：%r" % (wrapped,))
    lost = [k for k in KEEP_128 if k not in new]
    if lost:
        print("[ABORT] 第128轮的三处修复被覆盖了：%r" % (lost,))
        return 6
    secs = [t for t, _ in split_sections(new)]
    if len(secs) != 11:
        print("[ABORT] 节数 = %d（要求 11）：%r" % (len(secs), secs))
        return 7
    import re
    if re.search(r"\*{1,3}|`{1,3}|^[#>\-]\s*", new, re.M):
        print("[ABORT] 引入 markdown")
        return 8

    print("锚句 %d/%d ｜ 第128轮三处修复 %d/%d 在位 ｜ 节数 11"
          % (len(ANCHORS) - len(bad), len(ANCHORS),
             len(KEEP_128) - len(lost), len(KEEP_128)))
    print("改后：%d 字符 / %d 字节（%+d B）"
          % (len(new), len(new.encode("utf-8")),
             len(new.encode("utf-8")) - len(main_t.encode("utf-8"))))

    if dry:
        print("[dry] 未写盘")
        return 0
    with io.open(MAIN, "w", encoding="utf-8", newline="") as fh:
        fh.write(new)
    print("[OK] 已写盘（LF，无 BOM）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
