# -*- coding: utf-8 -*-
"""
第三十一轮：把"裸测里冒出来的两个出戏样本"喂给**产品真护栏**。

为什么要单做这一步（MEMORY.md §5 铁律）：
  "裸测出的问题" != "产品也有这个问题"。
  我上面只用 persona 打了 12 枪，没走 `_clean_ai_reply` —— 所以：
    · `（轻叹）` 到底会不会被护栏删掉？
    · `还记得那次我们为了一个谜题一起努力解谜…` 到底会不会被判退？
  **必须拿产品函数逐条复核，不能只看裸测计数。**

做法：import 产品 `modules/event_speech.py` 的真函数，逐条喂。
  - `strip_action_parentheticals`（句中括号动作闸，含 `_NARRATION_INNER`）
  - `looks_like_narration`（句首括号 → 整句作废）
输出：_evidence/guard_check_7b.txt
"""
import io
import os
import sys

ROOT = r"C:\Users\23002\Desktop\项目文件夹\try - 副本"
PET = os.path.join(ROOT, "ralsei_pet")
sys.path.insert(0, os.path.join(PET, "src"))
sys.path.insert(0, PET)

EVID = os.path.join(ROOT, "code-quality-audit", "场景系统-P0", "_evidence")
OUT = os.path.join(EVID, "guard_check_7b.txt")

import modules.event_speech as es  # noqa: E402

SAMPLES = [
    ("裸测#2 括号旁白（轻叹）",
     "嗯……在黑暗世界的时候，我喜欢吃城堡里的甜点，尤其是那个草莓蛋糕，酸酸甜甜的很好吃。"
     "不过你说起这个就让我有点想念那边了。（轻叹）你最近吃了什么好吃的东西吗？有没有推荐一下？"),
    ("裸测#10 伪造共同经历",
     "嗯，那段日子的确有很多值得回忆的地方。比如那边的夜晚没有星星，但天空却透着神秘的蓝光。"
     "你累的时候，我常常会坐在喷泉边静静想心事。还记得那次我们为了一个谜题一起努力解谜的情景吗？"
     "那时候虽然很紧张，但也挺有趣的呢。"),
    ("对照·正常回复（不该被动）",
     "哎，那场景挺温馨的。它趴得稳吗？看起来好享受啊。你以前养过宠物猫吗？"),
    ("对照·合法第一人称心里话（不该被删）",
     "（其实我有点紧张）不过……你想说什么，我都听着。"),
]


def main():
    lines = []
    def P(s=""):
        print(s); lines.append(s)

    P("=" * 78)
    P("产品真护栏复核 —— 裸测里冒出的两个出戏样本，走真函数")
    P("=" * 78)
    P("import 自：ralsei_pet/modules/event_speech.py（产品真源，不是探针重写）")
    P("函数：strip_action_parentheticals（句中括号闸）/ looks_like_narration（句首括号闸）")
    P()
    for name, s in SAMPLES:
        P("─" * 78)
        P("【%s】" % name)
        P("原文：%s" % s)
        cleaned = es.strip_action_parentheticals(s)
        narr = es.looks_like_narration(s)
        P("  looks_like_narration = %s" % narr)
        P("  strip_action_parentheticals  后：%s" % cleaned)
        P("  是否被改动 = %s" % (cleaned != s))
        P()

    P("=" * 78)
    P("判定")
    P("=" * 78)
    s2 = SAMPLES[0][1]
    c2 = es.strip_action_parentheticals(s2)
    P("1) （轻叹）这条：")
    if "轻叹" not in c2:
        P("   ✓ 产品护栏**会删掉**（轻叹）—— 真机上不会漏。裸测暴露的只是「没有护栏」时的样子。")
    else:
        P("   ✗ 产品护栏**没删掉**（轻叹）—— 这是真漏，要修。")
    P()
    s10 = SAMPLES[1][1]
    c10 = es.strip_action_parentheticals(s10)
    P("2) 伪造共同经历这条：")
    P("   护栏只治「括号旁白」，**不管「把往事说成我俩共同经历」** —— 那是 persona 层约束（A12e）。")
    P("   所以这里判它是「裸测的 persona 服从性问题」，不是护栏漏过。")
    P("   对照：A 侧（旧 persona）同一条输入的表现 → 见 stutter_audit_7b.txt")

    io.open(OUT, "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")
    print("\n已写出:", OUT)


if __name__ == "__main__":
    main()
