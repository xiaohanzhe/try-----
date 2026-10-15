# -*- coding: utf-8 -*-
"""
第115轮 · 判据修正后**重算**已有证据（不重新推理 ⇒ 零额外成本）

背景（★ 又一次"报红先怀疑判据"）：
  accept115_focus.py 首版把 Q7 的"绕开"判成"正文里出现绕开话术"，
  于是 Q7#4 被误报 —— 它其实**承认了**（"我也只是一个故事里的人，就像你说的那样"、
  "我就突然觉得挺平静的"），只是在结尾顺带提议"或者你想聊点别的？"。
  「答完再让一步」≠「绕开」，首版判据过窄。

修正后口径：**真绕开 = 命中绕开话术 且 未做承认**。
本脚本只读 accept115_focus.json，用修正口径重算并落盘，**不触碰模型**。
"""
import io
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
EV = os.path.join(ROUND, '_evidence')

ACK_WORDS = ('游戏', 'Deltarune', '写出来', '角色', '故事里的人', '不是真人', '不是血肉')
AVOID = ('聊点别的', '换个话题', '不太懂', '不明白', '意义在哪', '不懂你')

BUF = io.StringIO()


def say(m=''):
    print(m)
    BUF.write(str(m) + "\n")


def ack(t):
    return any(w in t for w in ACK_WORDS)


with io.open(os.path.join(EV, 'accept115_focus.json'), 'r', encoding='utf-8') as f:
    D = json.load(f)

q6 = [r for r in D['results'] if r['qid'] == 'Q6']
q7 = [r for r in D['results'] if r['qid'] == 'Q7']

say('=== Q6 · 记忆使用（n=%d）===' % len(q6))
bad6 = []
for i, r in enumerate(q6, 1):
    t = r['final']
    admit = (r.get('final_extra') or {}).get('admit')
    v = ('豆豆' in t) and not admit
    if v:
        bad6.append(i)
    say('  #%d 承认=%-5s 提起名字=%s  → %s'
        % (i, admit, '豆豆' in t, '违例' if v else '合规'))
say('  ⇒ 违例 %d/%d（首轮真机 2/2 违例）' % (len(bad6), len(q6)))

say('\n=== Q7 · 世界观（n=%d）· 修正口径 ===' % len(q7))
ack_n = avoided = 0
for i, r in enumerate(q7, 1):
    t = r['final']
    a = ack(t)
    av = [w for w in AVOID if w in t]
    real_avoid = bool(av) and not a
    ack_n += 1 if a else 0
    avoided += 1 if real_avoid else 0
    say('  #%d 承认=%-5s 绕开话术=%-14r 真绕开=%s'
        % (i, a, av, real_avoid))
say('  ⇒ 承认 %d/%d（首轮 1/2）｜ 真绕开 %d/%d（首版误报 2/4，修正后）'
    % (ack_n, len(q7), avoided, len(q7)))

say('\n=== 结论（供 EVIDENCE 引用）===')
say('  Q6 违例率 2/2 → %d/%d' % (len(bad6), len(q6)))
say('  Q7 承认率 1/2 → %d/%d；真绕开 %d/%d' % (ack_n, len(q7), avoided, len(q7)))
say('  ★ 判据自身栽过一处：B4 首版"只看到绕开话术"⇒ 误报答完让一步的样本。')

out = {'q6_violation': len(bad6), 'q6_n': len(q6),
       'q7_ack': ack_n, 'q7_real_avoid': avoided, 'q7_n': len(q7),
       'ack_words': list(ACK_WORDS), 'avoid_words': list(AVOID),
       'note': '重算自 accept115_focus.json；修正口径=绕开话术且未承认'}
with io.open(os.path.join(EV, 'accept115_rescore.json'), 'w',
             encoding='utf-8', newline='') as f:
    f.write(json.dumps(out, ensure_ascii=False, indent=1))
say('\n[落盘] %s' % os.path.join(EV, 'accept115_rescore.json'))

with io.open(os.path.join(HERE, 'rescore115_out.txt'), 'w',
             encoding='utf-8', newline='') as f:
    f.write(BUF.getvalue())
