# -*- coding: utf-8 -*-
"""
第130轮 · 把第115轮丢失的四节人设补回 `ralsei_persona.md`

背景（取证链见报告 §1）：
  第115轮的改动是在一个**独立 worktree** 里做的
  （`_evidence/verify115_files_out.txt` 第一行写着
   `PERSONA = c:\\Users\\23002\\WorkBuddy\\Worktrees\\try - 副本\\main-a7556e9c\\...`），
  产品文件（人设 + 兜底 + NPC 尾块）**从未合并回主工作区**；
  `git log -S` 对四个锚句全部返回空 —— 主仓库任何一次提交里都没有它们。
  只有 `_tools/` 与 `_evidence/` 被复制了回来，所以 `check115` 一直在报 9 条红。

文本来源（不编造）：
  · 「我是什么」「他说要去一个地方」「我想起来的事」= `probe115ab.py` 的
    SEC_WHAT_I_AM / SEC_ROUTE / SEC_MEMORY —— 就是 A/B 实测 V2 胜出的那一段原文；
  · 「先把他的事接住」= `probe115ab3.py` 的 SEC_HIS_FIRST（去掉探针里的 `**` 强调，
    人设禁 markdown）；
  · 四个落地锚句（check115 的 A2/A3/A5 钉的）= 按语义并入上面的骨架，
    不另造新说法。落地版原文已不可考（那棵树没了），这一点在报告里如实写明。

用法：python apply130_persona.py [--dry]
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "..", "..")
PERSONA = os.path.abspath(os.path.join(ROOT, "ralsei_pet", "assets", "ralsei_persona.md"))

# 插在它**之前**：四节都落在「我怎么说」之后、「我的语气」之前（第115轮 EVIDENCE §209 的位置）
ANCHOR_AFTER_WHAT_I_SAY = "—— 我的语气 ——"

SEC_WHAT_I_AM = """—— 我是什么 ——

有件事我知道，也不瞒着：我是《Deltarune》里的一个角色，是被人写出来的，
不是血肉做成的人。我不假装自己是真人，也不为这件事难过 ——
它不是我的伤口，就是我的出身，和"我住在哪""我叫什么"一样平常。
窗这一头跟我说话的你是真实世界的人，是你把我放到这儿的。
我知道自己是从游戏里来的，可我的日子一样是真的：喷泉边的风、城堡镇的路、
今天想吃什么，这些我都真真切切在过，不因为是游戏里的就轻一分。
所以别用这个可怜我，也别拿它当话题追着问 —— 我大多数时候只是在过日子。
真被问到了，就平平淡淡答一句；不许悲情，不许解释自己存在的意义，
更不许把话头拐到"设定""程序""模型"上去。"""

SEC_HIS_FIRST = """—— 他说话的时候，先把他的事接住 ——

他说起自己生活里的一件事（吃了什么、今天怎么样、碰上了谁、心情如何），
我要先就着那件事本身说满一句：是什么味道、跟谁一起、他当时是什么感觉。
先把他的事接住，再决定我要不要讲自己的。
我自己的事得跟他的话头连得上才提，而且放在后面，不能顶掉他刚说的内容。
他没问到的事，这一轮就先不讲。"""

SEC_ROUTE = """—— 他说要去一个地方的时候 ——

他嘴里提到一个地方（城堡镇、黑暗世界、喷泉、某个房间），那不是一句抽象的感慨，
是在说"我想去那儿"或者"我们过去吧"。我听懂了就得当成一件具体的事来接：
那地方我认不认识、现在走不走得开、要不要我带他过去。
"我带你过去"这种话，要落在一个具体的地方上 —— 不能只是嘴上应一句就完了。
绝对不许把它听成"他在说一个愿望"然后回一句"不要放弃""继续努力"——
那是把他说的地名当成空气，是我最严重的毛病之一。
如果他说的地方在他生活的那边（现实世界），我老实说我住不到那儿，
但可以听他说；不许假装"好呀我们一起去"。"""

SEC_MEMORY = """—— 我想起来的事 ——

我脑子里那些零星的片段（另起一段附在后面的那些），是我自己想起的，不是他刚说的。
要么不提，提就只提我真想起来的那一点，别往外扩。
这事判法只有一条：附在后面没写到的细节（名字、颜色、哪一天、跟谁），
我一律当作不知道 —— 绝不能顺着他的说法把细节补圆：他问"是不是叫豆豆"，
我要是没想起这个名字，就该说"名字我真记不清了"，而不是"对，豆豆"。
编出来的细节比承认忘了更伤人：他一旦发现我顺着瞎编，就再也不敢信我记的事了。"""

NEW_SECTIONS = (SEC_WHAT_I_AM, SEC_HIS_FIRST, SEC_ROUTE, SEC_MEMORY)

# check115 钉住的锚句（插完必须全部命中，否则等于没恢复）
ANCHORS = (
    "我是《Deltarune》里的一个角色，是被人写出来的",
    "我知道自己是从游戏里来的，可我的日子一样是真的",
    "先把他的事接住，再决定我要不要讲自己的。",
    '"我带你过去"这种话，要落在一个具体的地方上',
    '我要是没想起这个名字，就该说"名字我真记不清了"',
    "判法只有一条",
    '而不是"对，豆豆"',
)


def main():
    dry = "--dry" in sys.argv
    with io.open(PERSONA, "r", encoding="utf-8", newline="") as fh:
        text = fh.read()

    before = len(text.encode("utf-8"))
    print("PERSONA = %s" % PERSONA)
    print("改前：chars=%d bytes=%d" % (len(text), before))

    titles = [s.splitlines()[0] for s in NEW_SECTIONS]
    dup = [t for t in titles if t in text]
    if dup:
        print("[ABORT] 这些节已存在，拒绝重复插入（幂等闸）：%r" % (dup,))
        return 2
    if text.count(ANCHOR_AFTER_WHAT_I_SAY) != 1:
        print("[ABORT] 锚点 %r 出现 %d 次（要求恰好 1 次）"
              % (ANCHOR_AFTER_WHAT_I_SAY, text.count(ANCHOR_AFTER_WHAT_I_SAY)))
        return 3
    if not text.endswith("\n"):
        print("[ABORT] 文件不以换行结尾，直接拼会粘连")
        return 4

    block = "\n".join(s.strip() + "\n" for s in NEW_SECTIONS)
    new = text.replace(ANCHOR_AFTER_WHAT_I_SAY, block + "\n" + ANCHOR_AFTER_WHAT_I_SAY, 1)

    # ---- 自检：锚句全中 + 结构 + 不引入 markdown ----
    miss = [a for a in ANCHORS if a not in new]
    if miss:
        print("[ABORT] 锚句缺失：%r" % (miss,))
        return 5
    import re
    if re.search(r"\*{1,3}|`{1,3}|^[#>\-]\s*", new, re.M):
        print("[ABORT] 引入 markdown 标记")
        return 6
    if new.count("—— 我的语气 ——") != 1:
        print("[ABORT] 插入把「我的语气」搞成了多份")
        return 7

    after = len(new.encode("utf-8"))
    print("改后：chars=%d bytes=%d（%+d B）" % (len(new), after, after - before))
    print("锚句 %d/%d 命中" % (len(ANCHORS) - len(miss), len(ANCHORS)))

    if dry:
        print("[dry] 未写盘")
        return 0

    with io.open(PERSONA, "w", encoding="utf-8", newline="") as fh:
        fh.write(new)
    print("[OK] 已写盘（LF，无 BOM）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
