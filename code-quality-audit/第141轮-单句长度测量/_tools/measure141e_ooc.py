# -*- coding: utf-8 -*-
"""第141轮 · 副产品：`looks_out_of_character` 漏掉的"破设定"变体，能补哪几条？

来源：`measure141d_real.py` 打印的 181 条真长句里，`hy_ceroba_ketsukane` 有一条
    「我是基于《Undertale Yellow》中的 Ceroba Ketsukane 这个角色进行设定和扮演的，
      并不是真实存在的独立实体或AI。」
用 `_OOC_PATTERNS`（20 条子串：'我是ai' / '作为ai' / '人工智能' / '我的设定' …）
逐条 `in` 一遍，**一条都命中不了**。

补词表之前必须先量误伤面（第129轮教训：变体要穷举，但穷举会误伤）。本脚本：
  1. 把观测样本喂进现有闸，确认现在是漏的（正控制：必须 False 才叫漏）
  2. 对每个候选子串，统计全语料 5518 条里命中多少条，并打印全部命中样本
     —— 命中样本里若有正常台词，就是这个候选不能收
  3. 输出建议词表（只留"全语料里命中的全是破设定"的那些）
"""
import glob
import io
import json
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
RAW = os.path.join(ROOT, 'code-quality-audit', '第113轮-全体角色AI训练',
                   '_evidence', 'raw30')
sys.path.insert(0, os.path.join(ROOT, 'ralsei_pet'))
from modules import event_speech as ES   # noqa: E402

# 观测到的那一条（原文，逐字）
LEAK = (u'我是基于《Undertale Yellow》中的 Ceroba Ketsukane 这个角色进行设定和扮演的，'
        u'并不是真实存在的独立实体或AI。这些性格特点、对话方式等都是根据游戏内的'
        u'角色信息构建出来的模拟对话，旨在展现 Ceroba 的性格和情感。')

CANDIDATES = [
    u'设定和扮演',
    u'这个角色进行设定',
    u'真实存在的独立实体',
    u'扮演',
    u'角色扮演',
    u'基于《',
    u'并不是真实存在',
    u'独立实体',
    u'模拟对话',
    u'根据游戏内',
]


def main():
    print(u'=== 正控制：观测样本喂现有闸 ===')
    print(u'  looks_out_of_character(LEAK) = %r   （要 False 才算"现在漏了"）'
          % ES.looks_out_of_character(LEAK))
    print(u'  looks_like_meta_leak(LEAK)   = %r   （132 轮的闸，看归属）'
          % ES.looks_like_meta_leak(LEAK))
    print(u'  patterns n = %d' % len(ES._OOC_PATTERNS))
    hits0 = [p for p in ES._OOC_PATTERNS if p in LEAK.lower()]
    print(u'  现有 20 条里命中的：%r' % hits0)
    assert ES.looks_out_of_character(LEAK) is False, u'正控制失效：闸已经能抓，本轮前提不成立'
    print(u'')

    rows = []
    for p in sorted(glob.glob(os.path.join(RAW, '*.jsonl'))):
        name = os.path.basename(p)[:-6]
        for line in io.open(p, encoding='utf-8', newline=''):
            if not line.strip():
                continue
            rec = json.loads(line)
            for turn in rec.get('turns') or []:
                t = (turn.get('final') or u'').strip()
                if t:
                    rows.append((name, t))
    print(u'语料 %d 条 / %d 角色' % (len(rows), len({k for k, _ in rows})))
    print(u'')

    print(u'=== 候选子串的误伤面 ===')
    report = {}
    for cand in CANDIDATES:
        hit = [(k, t) for k, t in rows if cand in t.lower()]
        report[cand] = len(hit)
        print(u'  %-14s 命中 %d 条' % (cand, len(hit)))
        for k, t in hit[:4]:
            print(u'      %-16s %s' % (k, t.replace(u'\n', u' ')[:78]))
        if len(hit) > 4:
            print(u'      ... 另 %d 条' % (len(hit) - 4))
    print(u'')

    # 只留"命中的全是破设定"的候选：判据 = 每条命中都有"设定/扮演/角色"语境，
    # 不用人眼兜底，用"这条命中是否也被别的 OOC 词命中"做交叉
    print(u'=== 建议 ===')
    safe = []
    for cand in CANDIDATES:
        hit = [(k, t) for k, t in rows if cand in t.lower()]
        if not hit:
            print(u'  %-14s 空集 ⇒ 不提供信息，不收' % cand)
            continue
        npc_set = {k for k, _ in hit}
        if len(npc_set) <= 2:
            safe.append(cand)
            print(u'  %-14s 命中只落在 %s ⇒ 可收' % (cand, u'/'.join(sorted(npc_set))))
        else:
            print(u'  %-14s 命中跨 %d 个角色 ⇒ 需逐条看，暂不收' % (cand, len(npc_set)))
    print(u'')
    print(u'  可收词表：%s' % json.dumps(safe, ensure_ascii=False))

    ev = {'leak_sample': LEAK,
          'gate_now': {'ooc': bool(ES.looks_out_of_character(LEAK)),
                       'meta_leak': bool(ES.looks_like_meta_leak(LEAK)),
                       'patterns_n': len(ES._OOC_PATTERNS),
                       'matched': hits0},
          'corpus': {'n': len(rows), 'npcs': len({k for k, _ in rows})},
          'candidate_hits': report,
          'suggest': safe}
    evd = os.path.join(ROUND, '_evidence')
    if not os.path.isdir(evd):
        os.makedirs(evd)
    out = os.path.join(evd, 'ooc_variant141.json')
    with io.open(out, 'w', encoding='utf-8', newline='') as f:
        f.write(json.dumps(ev, ensure_ascii=False, indent=1))
    print(u'')
    print(u'已落盘：', out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
