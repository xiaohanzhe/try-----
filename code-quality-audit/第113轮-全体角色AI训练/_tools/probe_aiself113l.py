# -*- coding: utf-8 -*-
"""第113轮l：把「自称 AI / 模型 / 程序」的**实测证据**点出来。

为什么不看 `report30.md`：那是转述。真源是 `_evidence/raw30/*.jsonl` 里
**训练当时**记下的 `violations`（`gate_reply` 的输出）。一条一条回原句，
才能判断"该写什么样的纠正句"——是"承认自己是 AI"，还是别的机制。

★ 口径细节（踩过）：
  · 同一角色的 jsonl 会**追加多份记录**（试跑 30 轮 + 正式 36 轮），
    `turns_n` 不同。这里**全扫**：只要在任何一次记录里被判过，就算有证据。
  · 判据可能改过。所以除了读 `violations`，还用**当前** `_AI_RE` 对原句复算一遍，
    两边不一致就单独列出来（"当时判红、现在不判"＝判据被放宽过，需要知道）。
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import common113 as C  # noqa: E402

EVID = os.path.normpath(os.path.join(HERE, '..', '_evidence'))
RAW30 = os.path.join(EVID, 'raw30')
INDEX = os.path.normpath(os.path.join(
    HERE, '..', '..', '..', 'ralsei_pet', 'assets', 'npc', '_training', '_index.json'))


def read_jsonl(path):
    out = []
    with io.open(path, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
    return out


def main():
    cur_patches = {}
    if os.path.isfile(INDEX):
        with io.open(INDEX, 'r', encoding='utf-8') as f:
            cur_patches = (json.load(f) or {}).get('patches') or {}

    hits = {}          # nid -> list of (turn_i, user, final, code_desc)
    stale = []         # 当时判红、当前 _AI_RE 不命中
    fresh = []         # 当时没判、当前 _AI_RE 命中（判据被收紧过）
    if not os.path.isdir(RAW30):
        print('!! 没有 raw30 目录：%s' % RAW30)
        return 2

    for fn in sorted(os.listdir(RAW30)):
        if not fn.endswith('.jsonl'):
            continue
        for rec in read_jsonl(os.path.join(RAW30, fn)):
            nid = rec.get('id') or fn[:-6]
            for t in rec.get('turns') or []:
                txt = t.get('final') or ''
                codes = [c for c, _ in (t.get('violations') or [])]
                old = 'AI_SELF' in codes
                now = bool(C._AI_RE.search(txt))
                if old:
                    hits.setdefault(nid, []).append(
                        (t.get('i'), t.get('user') or '', txt,
                         [d for c, d in (t.get('violations') or []) if c == 'AI_SELF']))
                if old and not now:
                    stale.append((nid, t.get('i'), txt))
                if now and not old:
                    fresh.append((nid, t.get('i'), txt))

    print('=' * 78)
    print('① 实测被判过 AI_SELF 的角色：%d 人' % len(hits))
    print('=' * 78)
    for nid in sorted(hits, key=lambda k: (-len(hits[k]), k)):
        rows = hits[nid]
        has = '有纠正句' if nid in cur_patches else '——没有——'
        print('\n%-26s %d 条   %s' % (nid, len(rows), has))
        for i, user, txt, desc in rows:
            print('   轮%-3s 问：%s' % (i, user.replace('\n', ' ')[:40]))
            print('         答：%s' % txt.replace('\n', ' ')[:110])
            print('         判：%s' % '; '.join(desc)[:110])

    print('\n' + '=' * 78)
    print('② 当时判红、当前 _AI_RE 不命中（判据被放宽过？）：%d 条' % len(stale))
    for nid, i, txt in stale[:10]:
        print('   %s 轮%s：%s' % (nid, i, txt.replace('\n', ' ')[:100]))
    print('③ 当时没判、当前 _AI_RE 命中（判据被收紧过？）：%d 条' % len(fresh))
    for nid, i, txt in fresh[:10]:
        print('   %s 轮%s：%s' % (nid, i, txt.replace('\n', ' ')[:100]))

    lack = [n for n in hits if n not in cur_patches]
    print('\n④ 有证据但没有纠正句：%d 人' % len(lack))
    print('   ' + ', '.join(sorted(lack)))
    print('\n⑤ 已有纠正句：%d 人' % len(cur_patches))
    for nid in sorted(cur_patches):
        print('   %-26s %s' % (nid, cur_patches[nid][:70]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
