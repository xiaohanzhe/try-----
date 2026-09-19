# -*- coding: utf-8 -*-
"""量化 Ralsei 原作台词里的括号用法 —— 决定「括号动作闸」该有多紧。

要回答三个问题：
  1) 原作台词里有**多少条**用了括号？（这是"不能一刀切禁括号"的量级）
  2) 其中多少条是**句首**括号？（现有 looks_like_narration 会整句作废 → 现网已被误杀的量）
  3) 括号里是"动作旁白"vs"心里话"各占多少？（新规则会不会误伤他心里话）
输出自写 UTF-8，不经任何 shell 管道。
"""
import json
import os
import re

BASE = r"C:\Users\23002\Desktop\项目文件夹\try - 副本\code-quality-audit\人味改造-2026-09-18"
SRC = os.path.join(BASE, "_evidence", "ralsei_lora_corpus.jsonl")
OUT = os.path.join(BASE, "_evidence", "paren_usage_2026-09-19.txt")

# 候选规则（待评估）：括号内**开头**就是动作/发声词 → 判为动作旁白
_MODS = ('轻轻', '慢慢', '微微', '默默', '悄悄', '稍稍', '缓缓', '静静', '无奈',
         '苦笑', '连忙', '赶紧', '稍微', '勉强', '用力', '使劲')
_VERBS = ('敲', '挠', '歪', '低头', '抬头', '眨眼', '叹气', '脸红', '握', '摊手',
          '耸肩', '点头', '摇头', '小声', '轻声', '喃喃', '沉默', '停顿', '皱眉',
          '抿嘴', '咳嗽', '清嗓', '嘟囔', '嘀咕', '挥手', '拍拍', '笑了笑', '笑了',
          '笑', '抖', '缩', '扭', '侧头', '转身', '捂', '抱', '站起', '坐下',
          '指了指', '看着他', '看了', '瞥', '挑眉', '吐舌', '吸气', '呼气')
_ACT_START = re.compile(r'^[（(＊*]\s*(?:%s)?\s*(?:%s)' % ('|'.join(_MODS), '|'.join(_VERBS)))

lines = []
with open(SRC, encoding="utf-8") as f:
    for ln in f:
        ln = ln.strip()
        if not ln:
            continue
        try:
            obj = json.loads(ln)
        except Exception:
            continue
        # 语料是 {"messages":[{"role":..,"content":..},...]} 或 {"prompt":..,"completion":..}
        if "messages" in obj:
            for m in obj["messages"]:
                if m.get("role") == "assistant":
                    lines.append(m.get("content", ""))
        else:
            for k in ("completion", "assistant", "response", "output"):
                if isinstance(obj.get(k), str):
                    lines.append(obj[k])
                    break

lines = [x for x in lines if isinstance(x, str) and x.strip()]

def has_open(t):
    return any(c in t for c in "（(＊*")
def starts_open(t):
    return t.lstrip()[:1] in ("（", "(", "＊", "*")

with_paren = [t for t in lines if has_open(t)]
start_paren = [t for t in lines if starts_open(t)]
act_start = [t for t in start_paren if _ACT_START.match(t.lstrip())]
inner_start = [t for t in start_paren if not _ACT_START.match(t.lstrip())]

rep = []
rep.append("== Ralsei 原作台词 · 括号用法量化（%s）==" % os.path.basename(SRC))
rep.append("样本条数 = %d" % len(lines))
rep.append("")
rep.append("含括号/星号的条数          = %d  (%.1f%%)" % (len(with_paren), 100.0 * len(with_paren) / max(1, len(lines))))
rep.append("其中**句首**就是括号的条数  = %d  (%.1f%%)   <- 现有 looks_like_narration 会整句作废" % (len(start_paren), 100.0 * len(start_paren) / max(1, len(lines))))
rep.append("   · 句首括号 + 括号内开头是动作词 = %d   <- 新规则会判为旁白（期望）" % len(act_start))
rep.append("   · 句首括号 + 不是动作词         = %d   <- **这些是他的心里话**，新规则应放行" % len(inner_start))
rep.append("")
rep.append("—— 句首括号但**不是**动作词的样本（新规则必须放行的那一批，最多列 25 条）——")
for t in inner_start[:25]:
    rep.append("    %s" % t.replace("\n", " "))
rep.append("")
rep.append("—— 句首括号且开头是动作词的样本（新规则会拦，最多列 25 条）——")
for t in act_start[:25]:
    rep.append("    %s" % t.replace("\n", " "))
rep.append("")
rep.append("—— 括语出现在**句中**的样本（现有闸抓不到；新闸要处理的那一类，最多列 25 条）——")
mid = [t for t in with_paren if not starts_open(t)]
for t in mid[:25]:
    rep.append("    %s" % t.replace("\n", " "))
rep.append("")
# 新规则对"整句只有括号动作"的处理结果统计
only_act = [t for t in act_start if re.fullmatch(r'[（(＊*][^）)＊*]*[）)＊*]', t.strip())]
rep.append("整句**只有**一个括号动作的条数 = %d（删掉后会变空 → 走判退）" % len(only_act))
rep.append("")
rep.append("计数说明：以上是**语料条数**（已按说话人切分），不是原作全部行数；")
rep.append("          「含括号」包含 Ralsei 用括号讲心里话的正常用法 —— 这正是不能用一刀切的原因。")

open(OUT, "w", encoding="utf-8").write("\n".join(rep) + "\n")
print("WROTE", OUT)
print("lines=%d with_paren=%d start_paren=%d act=%d inner=%d" %
      (len(lines), len(with_paren), len(start_paren), len(act_start), len(inner_start)))
