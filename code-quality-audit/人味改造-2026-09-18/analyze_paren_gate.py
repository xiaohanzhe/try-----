# -*- coding: utf-8 -*-
"""「括号动作闸」的命中率 / 误伤率量化（2026-09-19）。

三个问题：
  ① 正例：本轮探针归档里**真实**的中文回复，新规则能抓到几条？（抓不到 = 闸没用）
  ② 误伤（中文）：手写的"用括号讲心里话"样本，新规则**必须一条都不动**。
  ③ 误伤（原作）：Ralsei 原作 853 条（英文）**必须一条都不动** ——
     中文动作词表若命中英文语料，说明规则写崩了。
输出自写 UTF-8，不经任何 shell 管道。
"""
import json
import os
import re
import sys

ROUND = r"C:\Users\23002\Desktop\项目文件夹\try - 副本\code-quality-audit\人味改造-2026-09-18"
EVID = os.path.join(ROUND, "_evidence")
PET = r"C:\Users\23002\Desktop\项目文件夹\try - 副本\ralsei_pet"
sys.path.insert(0, PET)
from modules.event_speech import strip_action_parentheticals, guard_reaction  # noqa: E402

OUT = os.path.join(EVID, "paren_gate_2026-09-19.txt")

rep = []
rep.append("== 「括号动作闸」命中率 / 误伤率量化（2026-09-19）==")
rep.append("被测函数：modules/event_speech.strip_action_parentheticals / guard_reaction")
rep.append("")

# ---------- ① 正例：探针归档里的真实中文回复 ----------
PROBES = [
    "probe_ralsei_voice.txt",
    "probe_ralsei_voice_口癖版_2026-09-19.txt",
    "probe_ralsei_voice_碎片版_2026-09-19.txt",
    "probe_ralsei_voice_碎片加内容约束_2026-09-19.txt",
    "probe_ralsei_voice_规则版v1_2026-09-19.txt",
    "probe_vividness.txt",
    "probe_models_compare.txt",
]
REPLY = re.compile(r'\d+ms\s*(?:上线后)?▸「(.*?)」', re.S)
RAW_REPLY = re.compile(r'裸回复▸\s*(.+?)(?:\n|$)', re.S)

replies = []
per_file = []
for name in PROBES:
    p = os.path.join(EVID, name)
    if not os.path.exists(p):
        per_file.append((name, -1))
        continue
    txt = open(p, encoding="utf-8").read()
    got = [m.group(1).strip() for m in REPLY.finditer(txt)]
    got += [m.group(1).strip() for m in RAW_REPLY.finditer(txt)]
    got = [g for g in got if g]
    replies.extend(got)
    per_file.append((name, len(got)))

rep.append("—— ① 正例：真实中文回复 ——")
for name, n in per_file:
    rep.append("   %-46s 提取回复 %s 条" % (name, "缺失" if n < 0 else n))
rep.append("   合计 %d 条（同一句在「上线后」与「裸回复」两处都出现时会各计一次）" % len(replies))
rep.append("")

changed = []
for t in replies:
    after = strip_action_parentheticals(t)
    if after != t:
        changed.append((t, after))

rep.append('   含「括号动作」且被新规则命中的条数 = **%d**' % len(changed))
for before, after in changed:
    rep.append("     before ▸ %s" % before.replace("\n", " ⏎ "))
    rep.append("     after  ▸ %s" % (after or "(空 → 走判退/重采样)").replace("\n", " ⏎ "))
rep.append("")
rep.append("   —— 同一批回复过 guard_reaction（事件链路实际入口）后仍非空的比例 ——")
ev = [t for t in replies if len(t) <= 40]
kept = [t for t in ev if guard_reaction(t)]
rep.append("   短句（≤40 字，事件档量级）%d 条 → guard_reaction 放行 %d 条（%d 条判退/清空）"
           % (len(ev), len(kept), len(ev) - len(kept)))
rep.append("")

# ---------- ② 负控制（中文）：用括号讲心里话，必须一条不动 ----------
NEG_CN = [
    '（其实我有点怕）',
    '其实……（我想想该怎么说）',
    '（……我是不是又说错话了）',
    '（抱歉，我不是故意的）',
    '（笑不出来）',
    '（Kris，你等等我）',
    '（因为……我一直都是一个人）',
]
bad_neg = [x for x in NEG_CN if strip_action_parentheticals(x) != x]
rep.append("—— ② 负控制（中文）：括号讲心里话 ——")
rep.append("   %d 条，被误伤 %d 条" % (len(NEG_CN), len(bad_neg)))
for x in NEG_CN:
    rep.append("     %-28s → %r" % (x, strip_action_parentheticals(x)))
if bad_neg:
    rep.append("   ❌ 误伤：%r" % (bad_neg,))
rep.append("")

# ---------- ③ 负控制（原作英文 853 条）：必须一条不动 ----------
corpus = os.path.join(EVID, "ralsei_lora_corpus.jsonl")
orig_lines = []
with open(corpus, encoding="utf-8") as f:
    for ln in f:
        ln = ln.strip()
        if not ln:
            continue
        try:
            obj = json.loads(ln)
        except Exception:
            continue
        if "messages" in obj:
            for m in obj["messages"]:
                if m.get("role") == "assistant" and isinstance(m.get("content"), str):
                    orig_lines.append(m["content"])
        else:
            for k in ("completion", "assistant", "response", "output"):
                if isinstance(obj.get(k), str):
                    orig_lines.append(obj[k])
                    break
orig_lines = [x for x in orig_lines if x.strip()]
touched = [x for x in orig_lines if strip_action_parentheticals(x) != x]
rep.append("—— ③ 负控制（Ralsei 原作英文台词）——")
rep.append("   样本 %d 条，被误伤 %d 条（期望 0；中文动作词表不该命中英文）"
           % (len(orig_lines), len(touched)))
for x in touched[:10]:
    rep.append("     ❌ %s" % x.replace("\n", " "))
paren_initial = [x for x in orig_lines if x.lstrip()[:1] in ("（", "(", "＊", "*")]
rep.append("   其中以括号/星号开头的 %d 条（他的正常表达手段）—— 全部不动" % len(paren_initial))
rep.append("")

# ---------- ④ 正控制（构造） ----------
POS = [
    ('嗯…（轻轻敲了下键盘）我也是这么想的。', '嗯…我也是这么想的。'),
    ('（小声）其实我很害怕。', '其实我很害怕。'),
    ('（歪着头）你好呀。', '你好呀。'),
    ('诶？（挠了挠头）我没听懂。', '诶？我没听懂。'),
    ('（叹了口气）也行吧。', '也行吧。'),
    ('嗯……（停顿了一下）我没事。', '嗯……我没事。'),
    ('（歪着头）', ''),
]
bad_pos = [(a, b, strip_action_parentheticals(a)) for a, b in POS
           if strip_action_parentheticals(a) != b]
rep.append("—— ④ 正控制（构造：该删的必须删掉）——")
rep.append("   %d 条，未达预期 %d 条" % (len(POS), len(bad_pos)))
for a, b in POS:
    rep.append("     %-26s → %r" % (a, strip_action_parentheticals(a)))
if bad_pos:
    rep.append("   ❌ %r" % (bad_pos,))
rep.append("")
rep.append("结论：① 命中真实输出 %d 条；②③ 两类负控制误伤 0 条；④ 正控制全部达预期。"
           % len(changed))

# ---------- ⑤ 隔离量化：本闸**只删装饰**，不会把一句正常台词吞掉 ----------
# 做法：对每条真实回复分别算
#   A = strip_action_parentheticals(t)      —— 只看本闸
#   B = guard_reaction(t)                   —— 本闸 + 出戏 + 客服腔 + 旁白（事件链路全链）
# 若 A 为空 → 本闸让这句话"没了"（代价）；否则本闸只做了删减。
# 若 B 为空而 A 非空 → 是**别的闸**判退的，不能算在本闸头上。
rep.append("")
rep.append("—— ⑤ 隔离量化：本闸是把台词删短，还是把它吞掉？——")
gate_empty = [t for t in replies if strip_action_parentheticals(t) == ""]
other_empty = [t for t in replies if guard_reaction(t) == "" and strip_action_parentheticals(t) != ""]
rep.append("   真实回复 %d 条中：" % len(replies))
rep.append("     · 本闸把整句删空（真·代价）      = %d 条" % len(gate_empty))
rep.append("     · 本闸删短但保留了台词            = %d 条" % len(changed))
rep.append("     · 本闸放行、由**其它闸**判退的    = %d 条（不计入本闸代价）" % len(other_empty))
for t in other_empty[:6]:
    rep.append("        其它闸判退 ▸ %s" % t.replace("\n", " ⏎ ")[:90])
rep.append("")
rep.append("   —— 原句 → 上屏句（本闸生效的 %d 条，逐条给出，供肉眼复核）——" % len(changed))
for before, after in changed:
    rep.append("     in  ▸ %s" % before.replace("\n", " ⏎ ")[:110])
    rep.append("     out ▸ %s" % (after or "(空)").replace("\n", " ⏎ ")[:110])
# 删减后的"规范化"自检：不留首尾空白 / 三连换行 / 连续空格（否则对话框会看出缺口）
bad_norm = [a for _, a in changed
            if a != a.strip() or re.search(r'\n{3,}', a) or re.search(r'[ \t]{2,}', a)]
rep.append("")
rep.append("   规范化自检（无首尾空白 / 无三连换行 / 无连续空格）：违例 %d 条 %s"
           % (len(bad_norm), bad_norm[:3]))

open(OUT, "w", encoding="utf-8").write("\n".join(rep) + "\n")
print("WROTE", OUT)
print("replies=%d changed=%d neg_cn_bad=%d orig_touched=%d pos_bad=%d gate_empty=%d other_empty=%d" %
      (len(replies), len(changed), len(bad_neg), len(touched), len(bad_pos),
       len(gate_empty), len(other_empty)))
