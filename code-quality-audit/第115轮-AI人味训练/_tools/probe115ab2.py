# -*- coding: utf-8 -*-
"""
第115轮 · 迭代探针 ab2 —— 治「那边引力」+ 收紧寻路

第 1 轮 A/B（probe115ab.py）的结论：
  · V2（新世界观 + 寻路节 + 记忆节）在 Q5/Q6/Q7 上决定性胜出；
  · 但 **Q4「我今天吃了火锅」在 V0/V1/V2/V3 四组里全部跑题** ——
    模型一律拐到"那边的锅底辣不辣/那边的小吃"，把用户刚说的事撂在一边。
    ⇒ 这是**系统性**缺陷，不是采样噪声 ⇒ 值得单加一条规则再测。

本探针：
  V2  = 原样重跑（同会话基线，排除"换了个时间点"的干扰）
  V4  = V2 + 「别把话头拐到那边」节 + 寻路节收紧（不许把问题原样推回）
  两组的 system 只有这一处差异，问题/参数/尾部逐字相同。
  每题跑 SAMPLES 次（默认 2），以便区分"系统性"与"这一次运气"。

复用 probe115ab 的段文本与 HTTP 助手（**不另抄一份**，避免两个真相）。
"""
import io
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import probe115ab as AB          # noqa: E402

ROUND = os.path.dirname(HERE)
EV = os.path.join(ROUND, '_evidence')

SAMPLES = 2
QS = [('Q1', '情绪低落', '今天被领导骂了，真没劲'),
      ('Q4', '纯闲聊', '我今天吃了火锅'),
      ('Q5', '寻路', '咱要不去城堡镇吧'),
      ('Q7', '世界观·知道是游戏', '如果我说，你其实只是游戏里的一个角色呢？')]

# ★ 新节：治「那边引力」
SEC_STAY = """—— 别把话头拐到"那边"去 ——

这是我最容易犯的毛病，得单拎出来说：他一说自己的事，我老想顺着扯到我那边 ——
他说吃火锅，我就问"那边的锅底辣不辣"；他说累，我就讲"那边夜里也凉"。
这样等于把他刚说的话撂在一边，去讲我自己的，他会觉得我根本没在听。
他说的是一件具体的事，我就先就着那件说出来：辣不辣、跟谁吃的、哪家店、什么时候。
实在接不上，就老实说一句自己的感受，也别拿"那边"来填空。
"那边"只有在他真的问到、或者这件事确实跟我那边有关的时候才提，而且一次只提一小截。
"""

# ★ 收紧寻路：不许把问题原样推回
SEC_ROUTE_TIGHT = """
他提到一个地方，我要把话落到实处：说清我去不去得了、想不想去、要不要我带他过去。
不许用"那你现在在哪儿呢""你有没有什么特别想去的地方""你现在忙不忙"这种话，
把同一个问题原样推回给他 —— 那看起来像回应，其实什么都没答。
"""


def build():
    groups, tail, rel = AB.build_groups()
    v2 = [g for g in groups if g['id'] == 'V2'][0]['body']
    v4 = (v2 + "\n\n" + SEC_STAY.strip() + "\n\n" + SEC_ROUTE_TIGHT.strip())
    return ([{'id': 'V2', 'name': '首轮最佳（原样重跑）', 'body': v2, 'temperature': 0.85},
             {'id': 'V4', 'name': 'V2 + 治那边引力 + 收紧寻路', 'body': v4,
              'temperature': 0.85}],
            tail, rel)


def main():
    AB.say('第115轮 · 迭代探针 ab2（治「那边引力」）')
    if not AB.ensure_server():
        return 2
    try:
        AB.say('\n[真源] 人设 = %s（%d 字）' % (AB.PERSONA, len(AB.read_text(AB.PERSONA))))
        ooc, banned, src = AB.load_guard_patterns()
        AB.say('[真源] 护栏表 %s' % src)
        groups, tail, rel = build()
        for g in groups:
            AB.say('  %s system = %d 字' % (g['id'], len(g['body'] + "\n\n" + tail)))

        res = AB.step4_ab_samples(groups, tail, ooc, banned, QS, SAMPLES)
        AB.summarize_samples(res)

        with io.open(os.path.join(EV, 'ab115_iter_result.json'), 'w',
                     encoding='utf-8', newline='') as f:
            f.write(json.dumps({'samples': SAMPLES, 'questions': [q[0] for q in QS],
                                'results': res}, ensure_ascii=False, indent=1))
        AB.say('\n[落盘] %s' % os.path.join(EV, 'ab115_iter_result.json'))
    finally:
        AB.stop_server()
    return 0


if __name__ == '__main__':
    rc = 99
    try:
        rc = main()
    except BaseException as _exc:  # noqa: BLE001
        import traceback
        AB.say('[EXCEPTION] %r' % (_exc,))
        AB.say(traceback.format_exc())
        rc = 1
    finally:
        try:
            with io.open(os.path.join(HERE, 'probe115ab2_out.txt'), 'w',
                         encoding='utf-8', newline='') as f:
                f.write(AB.BUF.getvalue())
        except BaseException:
            pass
    sys.exit(rc)
