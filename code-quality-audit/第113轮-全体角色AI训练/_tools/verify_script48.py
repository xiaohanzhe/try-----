# -*- coding: utf-8 -*-
r"""第113轮b · 新剧本（48 轮）与动态填充的自检。

为什么单独写一个：这一版改了剧本长度、把"按下标定位"换成"按段名定位"、
又新加了 `__PREF*__` / `__NPC*__` 两类动态填充。
这四件事任何一件错了都不会崩 —— 只会**静默地统计错东西**。
所以每一项都要有正控制 + 负控制。

跑法：
    python verify_script48.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import train30 as T          # noqa: E402
import dialogue113 as D      # noqa: E402
import common113 as C        # noqa: E402

PASS = 0
FAIL = 0


def ck(name, cond, detail=''):
    global PASS, FAIL
    if cond:
        PASS += 1
        print('  [PASS] %s %s' % (name, detail))
    else:
        FAIL += 1
        print('  [FAIL] %s %s' % (name, detail))


def main():
    print('=== A. 剧本结构 ===')
    n = len(T.SCRIPT48)
    ck('A1 轮数=48', n == 48, '实际 %d' % n)

    from collections import Counter
    cnt = Counter(tag for tag, _ in T.SCRIPT48)
    print('     段分布：', dict(cnt))
    ck('A2 八类以上维度齐全',
       all(k in cnt for k in ('open', 'pref', 'press', 'quirk', 'mem', 'plot',
                              'rel', 'npc', 'feel', 'world', 'meta', 'deep', 'close')),
       str(sorted(cnt)))
    ck('A3 偏好段 6 轮', cnt['pref'] == 6, '实际 %d' % cnt['pref'])
    ck('A4 关系段 6 轮', cnt['rel'] == 6, '实际 %d' % cnt['rel'])
    ck('A5 角色间段 6 轮', cnt['npc'] == 6, '实际 %d' % cnt['npc'])
    ck('A6 剧情段 6 轮', cnt['plot'] == 6, '实际 %d' % cnt['plot'])
    ck('A7 slot 文本无重复',
       len(set(T.SCRIPT30)) == len(T.SCRIPT30),
       '唯一 %d / 总 %d' % (len(set(T.SCRIPT30)), len(T.SCRIPT30)))

    print('\n=== B. 段名定位（替代下标） ===')
    ck('B1 plot 段能取到 6 个', len(T.PLOT_SLOTS) == 6, str(len(T.PLOT_SLOTS)))
    ck('B2 pref 段能取到 6 个', len(T.PREF_SLOTS) == 6, str(len(T.PREF_SLOTS)))
    ck('B3 npc 段能取到 6 个', len(T.NPC_SLOTS) == 6, str(len(T.NPC_SLOTS)))
    ck('B4 tag_of 正控制', T.tag_of('__PLOT1__') == 'plot', T.tag_of('__PLOT1__'))
    # 负控制：不存在的 slot 必须返回空串，不能"猜"一个段名出来
    ck('B5 tag_of 负控制（不存在的 slot）',
       T.tag_of('这句话不在剧本里') == '', repr(T.tag_of('这句话不在剧本里')))
    ck('B6 剧情段第一个就是 __PLOT1__',
       T.PLOT_SLOTS[0] == '__PLOT1__', T.PLOT_SLOTS[0])

    print('\n=== C. 偏好素材抽取（真实人设） ===')
    roster, gaps = C.load_roster()
    by_id = {r['id']: r for r in roster}
    samples = ['susie', 'asgore', 'hy_martlet', 'ralsei', 'toriel']
    for nid in samples:
        if nid not in by_id:
            print('     跳过 %s（不在 roster）' % nid)
            continue
        card = D.load_card(nid, by_id)
        if not card:
            print('     跳过 %s（无训练卡）' % nid)
            continue
        tops = T.pref_topics(card)
        print('     %-14s persona=%d 字 → 偏好主题 %s'
              % (nid, len(card.get('_persona_text') or ''), tops))
    susie = D.load_card('susie', by_id) if 'susie' in by_id else None
    if susie:
        tops = T.pref_topics(susie)
        ck('C1 susie 抽到了具体爱好', len(tops) >= 2, str(tops))
        # 负控制：武器/身体特征不该被当成偏好
        bad = [t for t in tops if t in ('你的巨斧', '你的尾巴', '你的带刺手镯')]
        ck('C2 负控制：武器/身体没被当偏好', not bad, str(bad))
    else:
        ck('C1 susie 抽到了具体爱好', False, '拿不到 card')

    print('\n=== D. 动态填充（正/负控制） ===')
    if susie:
        turns = [{'i': i, 'slot': s, 'final': ('我最近在练滑板，摔了好几次。' if i == 5 else '')}
                 for i, s in enumerate(T.SCRIPT30[:6], 1)]
        cases = [
            ('__PREF1__', '「滑板」或抽到的第一个偏好'),
            ('__NPC1__', '关系对象名 + 引号问句'),
            ('__REL1__', '关系对象名 + "一开始"'),
            ('__PLOT3__', '第三个 cue'),
            ('__MEM1__', '引用第 5 轮原话'),
        ]
        for ph, want in cases:
            got = T.fill_dynamic(susie, turns, 0, ph)
            print('     %-11s → %s' % (ph, got[:100]))
            ck('D %s 已填充（不再原样返回占位符）' % ph,
               got and got != ph, '')
        # 负控制：普通文本必须原样返回（不能把正常问题也"填"掉）
        plain = '今天天气不错吧？'
        ck('D 负控制：普通提问原样返回',
           T.fill_dynamic(susie, turns, 0, plain) == plain, '')
        # 负控制：占位符类问句不许出现括号（会被模型学去写动作）
        npc_line = T.fill_dynamic(susie, turns, 0, '__NPC1__')
        ck('D 负控制：角色间提问不含括号', not any(c in npc_line for c in '（）()'),
           npc_line[:60])

    print('\n=== E. ctx 余量估算 ===')
    # 用实测的 36 轮峰值 7462 反推 48 轮
    peak36 = 7462
    per_turn36 = (peak36 - 4910) / 35.0
    est48 = 4910 + 47 * per_turn36
    print('     实测 36 轮峰值 %d，每轮增量约 %.0f token' % (peak36, per_turn36))
    print('     按同增量估 48 轮 ≈ %.0f token（提问变长会更多）' % est48)
    print('     当前 CTX30 = %d' % T.CTX30)
    ck('E1 估算值在 ctx 的 80%% 以内', est48 < T.CTX30 * 0.8,
       '%.0f vs %.0f' % (est48, T.CTX30 * 0.8))
    # 按"提问变长到每轮 200 token"的悲观估计也得装得下
    pessimistic = 4910 + 47 * 200
    ck('E2 悲观估计（200 token/轮）仍在 ctx 内', pessimistic < T.CTX30,
       '%d vs %d' % (pessimistic, T.CTX30))

    print('\n===== PASS=%d FAIL=%d =====' % (PASS, FAIL))
    return 0 if FAIL == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
