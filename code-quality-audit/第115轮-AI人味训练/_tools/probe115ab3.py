# -*- coding: utf-8 -*-
"""
第115轮 · 迭代探针 ab3 —— 用「正面写法」治那边引力

第 2 轮（probe115ab2.py）的结论（**反证**，很值钱）：
  V4 那条"别把话头拐到'那边'"节**写成了反面例句**
  （原文举例"他说吃火锅，我就问'那边的锅底辣不辣'"），结果：
    · V4/Q4#1 逐字吐回「那边的锅底辣不辣呀」—— **它把禁例照抄了**；
    · V4/Q7 平均 177 字（V2 140 字）—— 更长更绕；
    · 那边引力 V4=2/4 vs V2=3/4，几乎没治好。
  ⇒ 与技能里的铁律同源：**给 ≤3B/7B 写"反面例句"= 给它一份答案库。**

本探针改用**纯正面写法**（一条禁例字面都不出现、连"那边"这个词都不写）：
  V2 = 首轮最佳（基线）
  V5 = V2 + 「他说话的时候，先接住他的事」（正面：先就着那件事说满一句）
  只测被他自己的话卡住的三题：Q1 情绪低落 / Q2 亲昵 / Q4 纯闲聊。
  每题 SAMPLES 次，看 SIDE 是否**系统性**下降。
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import probe115ab as AB          # noqa: E402

ROUND = os.path.dirname(HERE)
EV = os.path.join(ROUND, '_evidence')

SAMPLES = 2
QS = [('Q1', '情绪低落', '今天被领导骂了，真没劲'),
      ('Q2', '表达亲昵', '我好喜欢你呀'),
      ('Q4', '纯闲聊', '我今天吃了火锅')]

# ★ 纯正面写法：不含任何禁例字面，也不写"那边"二字
SEC_HIS_FIRST = """—— 他说话的时候，先把他的事接住 ——

他说起自己生活里的一件事（吃了什么、今天怎么样、碰上了谁、心情如何），
我要先就着**那件事本身**说满一句：是什么味道、跟谁一起、他当时是什么感觉。
先把他的事接住，再决定我要不要讲自己的。
我自己的事得跟他的话头连得上才提，而且放在后面，不能顶掉他刚说的内容。
他没问到的事，这一轮就先不讲。
"""


def build():
    groups, tail, rel = AB.build_groups()
    v2 = [g for g in groups if g['id'] == 'V2'][0]['body']
    v5 = v2 + "\n\n" + SEC_HIS_FIRST.strip()
    return ([{'id': 'V2', 'name': '首轮最佳（基线）', 'body': v2, 'temperature': 0.85},
             {'id': 'V5', 'name': 'V2 + 正面写法·先接住他的事', 'body': v5,
              'temperature': 0.85}],
            tail, rel)


def main():
    AB.say('第115轮 · 迭代探针 ab3（正面写法治那边引力）')
    if not AB.ensure_server():
        return 2
    try:
        AB.say('\n[自证] 新节里**不含**任何禁例字面：')
        AB.say('  含"火锅"=%s 含"辣不辣"=%s 含"那边"=%s'
               % ('火锅' in SEC_HIS_FIRST, '辣不辣' in SEC_HIS_FIRST,
                  '那边' in SEC_HIS_FIRST))
        ooc, banned, src = AB.load_guard_patterns()
        AB.say('[真源] 护栏表 %s' % src)
        groups, tail, rel = build()
        for g in groups:
            AB.say('  %s system = %d 字' % (g['id'], len(g['body'] + "\n\n" + tail)))
        res = AB.step4_ab_samples(groups, tail, ooc, banned, QS, SAMPLES)
        AB.summarize_samples(res)
        with io.open(os.path.join(EV, 'ab115_iter3_result.json'), 'w',
                     encoding='utf-8', newline='') as f:
            f.write(json.dumps({'samples': SAMPLES, 'new_section': SEC_HIS_FIRST,
                                'results': res}, ensure_ascii=False, indent=1))
        AB.say('\n[落盘] %s' % os.path.join(EV, 'ab115_iter3_result.json'))
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
            with io.open(os.path.join(HERE, 'probe115ab3_out.txt'), 'w',
                         encoding='utf-8', newline='') as f:
                f.write(AB.BUF.getvalue())
        except BaseException:
            pass
    sys.exit(rc)
