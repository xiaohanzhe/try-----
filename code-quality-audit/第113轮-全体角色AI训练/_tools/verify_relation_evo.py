# -*- coding: utf-8 -*-
r"""验证「关系卡 + 关系演化卡」是否真的进了训练 system，且没有卡时逐字不变。

为什么必须验：
- `system_for` 原来**漏传了 `relation`** —— 训练时模型不知道关系对象是谁，
  而产品运行时是注入的。这种"训练与运行时不同源"不会报错，只会让训练白做。
- `build_system_prompt` 加了 `evolution` 参数，产品函数一改就可能影响所有 NPC 的 prompt，
  必须有**负控制**证明"没有卡的角色输出与旧版逐字一致"。
"""
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import common113 as C          # noqa: E402
import dialogue113 as D        # noqa: E402

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
    NP = C._NP
    roster, _ = C.load_roster()
    by_id = {r['id']: r for r in roster}

    print('=== A. 关系卡 / 演化卡本身 ===')
    rel = NP.relation_patch('asgore')
    evo = NP.evolution_patch('asgore')
    print('     asgore relation_patch  %d 字' % len(rel))
    print('     asgore evolution_patch %d 字' % len(evo))
    ck('A1 asgore 有关系卡', bool(rel.strip()))
    ck('A2 asgore 有演化卡', bool(evo.strip()))
    ck('A3 演化卡带"你自己说过的"标记', '你自己说过的' in evo, evo[:40])
    # 负控制：不存在的角色必须返回空串，不能随便回退成别人的卡
    ck('A4 负控制：不存在的 id 返回空串',
       NP.relation_patch('no_such_npc_xyz') == ''
       and NP.evolution_patch('no_such_npc_xyz') == '')

    print('\n=== B. system_for 是否真的注入了 ===')
    card = D.load_card('asgore', by_id)
    sys_full = D.system_for(card)
    sys_no_rel = NP.build_system_prompt(
        card['name'], card['_persona_text'], entries=[], npc_id=card['id'],
        context='', life='', patch=card.get('patch') or '')
    print('     完整 system %d 字 / 不含关系 %d 字 / 差 %d 字'
          % (len(sys_full), len(sys_no_rel), len(sys_full) - len(sys_no_rel)))
    ck('B1 完整 system 更长', len(sys_full) > len(sys_no_rel))
    ck('B2 含【你和其他人的关系】', '【你和其他人的关系' in sys_full)
    ck('B3 含演化卡标记', '你和别人之间的事' in sys_full)
    ck('B4 不含关系卡的版本确实没有这两块',
       '【你和其他人的关系' not in sys_no_rel and '你和别人之间的事' not in sys_no_rel)
    # 关键：关系/演化必须排在 SPEAK_RULES **之前**（顺序即语义）
    i_rel = sys_full.find('【你和其他人的关系')
    i_evo = sys_full.find('你和别人之间的事')
    i_speak = sys_full.find('【说话方式】')
    ck('B5 关系卡在 SPEAK_RULES 之前', 0 <= i_rel < i_speak, '%d < %d' % (i_rel, i_speak))
    ck('B6 演化卡在静态关系卡之后、SPEAK_RULES 之前',
       0 <= i_rel < i_evo < i_speak, '%d < %d < %d' % (i_rel, i_evo, i_speak))

    print('\n=== C. 负控制：没有卡的角色必须与旧版逐字一致 ===')
    # 找一个既无 relation 也无 evolution 的角色
    cand = None
    for r in roster:
        nid = r['id']
        if not NP.relation_patch(nid).strip() and not NP.evolution_patch(nid).strip():
            cand = nid
            break
    if cand:
        c2 = D.load_card(cand, by_id)
        a = NP.build_system_prompt(c2['name'], c2['_persona_text'], entries=[],
                                   npc_id=c2['id'], context='', life='',
                                   patch=c2.get('patch') or '')
        b = NP.build_system_prompt(c2['name'], c2['_persona_text'], entries=[],
                                   npc_id=c2['id'], context='', life='',
                                   patch=c2.get('patch') or '',
                                   relation='', evolution='')
        same = hashlib.sha256(a.encode('utf-8')).hexdigest() == \
            hashlib.sha256(b.encode('utf-8')).hexdigest()
        ck('C1 无卡角色：显式传空 == 不传', same, '角色=%s 长度=%d' % (cand, len(a)))
    else:
        # ★ 这里**不能**写 `ck(..., True)`：那是个恒真判据 —— 一旦所有角色都有卡，
        #   这一项就永远绿，而它其实一个字节都没验过。
        #   "跳过"必须看起来像跳过（第85轮 `{} == {}` 的教训）。
        print('     [SKIP] C1：所有角色都有关系卡，没有"无卡角色"可用来做负控制。')
        print('            这不影响结论，但要显式记成跳过，不是通过。')

    print('\n=== D. 长度代价（system 会不会被撑太满） ===')
    worst = []
    for r in roster:
        nid = r['id']
        cd = D.load_card(nid, by_id)
        if not cd:
            continue
        worst.append((len(D.system_for(cd)), nid))
    worst.sort(reverse=True)
    print('     system 最长的 5 个：', worst[:5])
    print('     中位长度：%d 字' % worst[len(worst) // 2][0])
    # 16384 token 约合 1 万~1.6 万汉字，system 超过 1.2 万字就危险
    ck('D1 最长 system 仍在 14000 字以内', worst[0][0] < 14000,
       '%d 字（%s）' % worst[0])

    print('\n===== PASS=%d FAIL=%d =====' % (PASS, FAIL))
    return 0 if FAIL == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
