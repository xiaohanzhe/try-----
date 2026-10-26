# -*- coding: utf-8 -*-
"""第113轮l：用**现行** `_AI_RE` 重判 `raw30` 的全部回复（"换尺子"之后到底有多少人）。

为什么需要这一步：
    `raw30` 里存的 `violations` 是**训练当时**用旧判据算的。本轮把 `_AI_RE` 放宽了
    （裸词 `AI` / `提示词` / `设定` 也算），但历史记录不会自己更新。
    ⇒ 必须拿**原始回复文本**重新判一遍，否则"有证据的人"还是旧的 22 个，
      新判红的 20 多人就永远补不上纠正句。

输出：
    ① 新旧对比（多少人、多少条）
    ② 新增判红的人（这些人的 `patches` 目前是空的）
    ③ 只统计，不写盘 —— 写盘由 `apply_aiself113l.py` 负责（单一入口，便于回滚）
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import common113 as C  # noqa: E402

RAW30 = os.path.join(C.EVID, 'raw30')
INDEX = os.path.normpath(os.path.join(
    HERE, '..', '..', '..', 'ralsei_pet', 'assets', 'npc', '_training', '_index.json'))


def main():
    old_ev, new_ev = set(), set()
    new_hits = []
    n_turn = 0
    for fn in sorted(os.listdir(RAW30)):
        if not fn.endswith('.jsonl'):
            continue
        for rec in C.read_jsonl(os.path.join(RAW30, fn)):
            nid = rec.get('id') or fn[:-6]
            for t in rec.get('turns') or []:
                n_turn += 1
                txt = t.get('final') or ''
                codes = [c for c, _ in (t.get('violations') or [])]
                if 'AI_SELF' in codes:
                    old_ev.add(nid)
                m = C._AI_RE.search(txt)
                if m:
                    new_ev.add(nid)
                    new_hits.append((nid, t.get('i'), m.group(0), txt))

    patches = (json.load(io.open(INDEX, encoding='utf-8')) or {}).get('patches') or {}
    have = {n for n, p in patches.items() if C.AI_SELF_PATCH in p}

    print('=' * 74)
    print('扫了 %d 轮回复' % n_turn)
    print('旧判据（记录里的 violations）：%d 人' % len(old_ev))
    print('新判据（现行 `_AI_RE` 重判）：%d 人 / %d 条' % (len(new_ev), len(new_hits)))
    print('已有 AI_SELF 纠正句：%d 人' % len(have))
    print('=' * 74)

    lack = sorted(new_ev - have)
    print('\n① 新判红但**没有**纠正句：%d 人' % len(lack))
    print('   ' + ', '.join(lack))

    extra = sorted(have - new_ev)
    print('\n② 有纠正句但新判据下查不到证据：%d 人' % len(extra))
    print('   ' + (', '.join(extra) or '无'))

    print('\n③ 新增样本（旧判据没抓到、新判据抓到的前 12 条）')
    shown = 0
    for nid, i, w, txt in new_hits:
        if nid in old_ev:
            continue
        print('\n  %-22s 轮%-3s [%s]' % (nid, i, w))
        print('     %s' % txt.replace('\n', ' ')[:130])
        shown += 1
        if shown >= 12:
            break

    print('\n④ 按人汇总（新口径，降序）')
    per = {}
    for nid, i, w, txt in new_hits:
        per[nid] = per.get(nid, 0) + 1
    for nid in sorted(per, key=lambda k: (-per[k], k)):
        print('   %-24s %d 条   %s' % (nid, per[nid],
                                       '有' if nid in have else '—— 缺'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
