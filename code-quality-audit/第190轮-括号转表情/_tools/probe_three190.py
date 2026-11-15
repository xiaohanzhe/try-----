# -*- coding: utf-8 -*-
u"""第190轮续二 · 三张表（场景/内在/外在）的逐条对账。

★ 每条都必须同时看**两件事**：
    · `clean`  —— 台词里还留不留这段字
    · `acts`   —— 有没有被 `_note` 记成"要表现/要说"的信号
  只看 `clean` 的话，"删了但冒出一行旁白"会被漏掉；只看 `acts` 的话，
  "留着字还播旁白"会被漏掉。两个一起看才闭合。
"""
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'ralsei_pet', 'modules'))

import event_speech as E   # noqa: E402

#: (括号内容, 期望留在台词里?, 期望进 sink(=可能要播)?, 类别说明)
CASES = [
    # ---- 内在活动：删掉、不播（用户本轮纠正的核心）
    (u'想了想',        False, False, u'内在'),
    (u'想了想，还是算了', False, False, u'内在'),
    (u'犹豫',          False, False, u'内在'),
    (u'犹豫了一下',     False, False, u'内在'),
    (u'沉思片刻',       False, False, u'内在'),
    (u'回忆',          False, False, u'内在'),
    (u'心里盘算着',     False, False, u'内在'),
    # ---- 场景交互：删掉、不播
    (u'推开门',        False, False, u'场景'),
    (u'走到窗边',       False, False, u'场景'),
    (u'拿起杯子',       False, False, u'场景'),
    # ---- 外在表现：删掉、要播
    (u'叹气',          False, True,  u'外在'),
    (u'苦笑',          False, True,  u'外在'),
    (u'蹲下身子',       False, True,  u'外在'),
    (u'叉腰',          False, True,  u'外在'),
    (u'点了点头',       False, True,  u'外在'),
    # ---- 必须原样保留（老锁钉着的负控制）
    (u'笑不出来',       True,  False, u'保留'),
    (u'我想想该怎么说',  True,  False, u'保留'),
    (u'抱歉，我不是故意的', True, False, u'保留'),
    (u'SANS! STOP BEING LAZY!', True, False, u'保留'),
]


def main():
    bad = []
    print(u'%-22s %-6s %-8s %-8s %s' % (u'括号内容', u'类别', u'留字', u'进sink', u'判定'))
    print(u'-' * 72)
    for raw, want_keep, want_sink, kind in CASES:
        line = u'（%s）后面是正文。' % raw
        acts = []
        clean = E.strip_action_parentheticals(line, sink=acts)
        kept = (raw in clean)
        sink_hit = (raw in acts) or any(raw in a for a in acts)
        ok = (kept == want_keep) and (sink_hit == want_sink)
        if not ok:
            bad.append((raw, kept, want_keep, sink_hit, want_sink, clean, acts))
        print(u'%-22s %-6s %-8s %-8s %s'
              % (raw, kind,
                 u'留' if kept else u'删',
                 u'播' if sink_hit else u'不播',
                 u'OK' if ok else u'✘'))

    print(u'')
    if bad:
        for b in bad:
            print(u'[X] %r 留字=%s(期望%s) 进sink=%s(期望%s) clean=%r acts=%r' % b)
        print(u'[结论] 不符 %d 条' % len(bad))
        return 1
    print(u'[结论] 全部符合预期（%d 条）' % len(CASES))
    return 0


if __name__ == '__main__':
    sys.exit(main())
