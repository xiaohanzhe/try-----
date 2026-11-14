# -*- coding: utf-8 -*-
"""第189轮 · 只重建**指定角色**的训练卡（人设改过），且不许冲掉训练结果。

为什么不是 `cards113.py --all`
------------------------------
`--all` 会把 77 张卡全部重写：`patch`/`eval` 曾因此被清空（第189轮实证 59+61 张，
四把老锁同时红，修法见 `cards113.carry_trained`）、`voice_markers` 会被重新抽取
（第113轮r 的手工剔词只有"人设 sha256 没变"时才拦得住）、62 张 CRLF 卡会被统一成 LF。
⇒ 只重建**人设真变过**的那几张，其余一个字节不动。

口径
----
* 走产品自己的抽取函数 `cards113.build_card()`（不另写一套，免得两份口径漂）。
* 走 `cards113.carry_trained()` 保住 `patch` / `eval`（以及人设未变时的 `voice_markers`）。
* 行尾沿用**该卡原本的**行尾（有的卡是 CRLF、有的是 LF），不做全库统一。
* 索引 `_index.json` 只改这张卡的三个派生记账（`persona_chars` / `markers` / `patch`）。
* 幂等：重建两遍字节相同。

用法
----
    python sync_card189.py                          # 默认只重建 asgore，dry
    python sync_card189.py --ids ot_kidd,lancer     # 指定名单
    python sync_card189.py --ids a,b --write        # 写盘
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
# `common113` / `cards113` 都在第113轮工具目录里 —— 直接复用产品口径，不另写一套
sys.path.insert(0, os.path.join(ROOT, 'code-quality-audit', '第113轮-全体角色AI训练', '_tools'))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import common113 as C          # noqa: E402
import cards113                # noqa: E402


def render(card, path):
    """按该卡既有行尾渲染（CRLF 卡仍然 CRLF），末尾一个换行。"""
    raw = open(path, 'rb').read()
    crlf = b'\r\n' in raw
    txt = json.dumps(card, ensure_ascii=False, indent=1)
    if crlf:
        txt = txt.replace('\r\n', '\n').replace('\n', '\r\n')
    return (txt + ('\r\n' if crlf else '\n')).encode('utf-8')


def sync_index(tid, card, dry=True):
    """把 `_index.json` 里这张卡的派生记账跟着改（只动这一条）。"""
    path = os.path.join(C.TRAIN_DIR, '_index.json')
    idx = C.load_json(path) or {}
    rec = (idx.get('cards') or {}).get(tid)
    if rec is None:
        print('  [跳过] 索引里没有 %s' % tid)
        return []
    want = {'persona_chars': card.get('persona_chars', 0),
            'markers': len(card.get('voice_markers') or []),
            'patch': card.get('patch') or ''}
    diff = [k for k, v in want.items() if rec.get(k) != v]
    if diff and not dry:
        for k, v in want.items():
            rec[k] = v
        C.write_text(path, json.dumps(idx, ensure_ascii=False, indent=1) + '\n')
    return diff


def main():
    do_write = '--write' in sys.argv
    ids = ['asgore']
    if '--ids' in sys.argv:
        ids = [x.strip() for x in sys.argv[sys.argv.index('--ids') + 1].split(',') if x.strip()]

    roster, _gaps = C.load_roster()
    by_id = {x['id']: x for x in roster}
    todo, missing = [], []
    for tid in ids:
        item = by_id.get(tid)
        if not item:
            missing.append(tid)
            continue
        path = os.path.join(C.TRAIN_DIR, 'cards', tid + '.json')
        if not os.path.isfile(path):
            missing.append(tid + '(无卡)')
            continue
        todo.append((tid, item, path))
    if missing:
        print('[跳过] 名单里没有或没卡：%r' % missing)

    n_changed = 0
    for tid, item, path in todo:
        old = C.load_json(path) or {}
        card = cards113.carry_trained(cards113.build_card(item), path)
        payload = render(card, path)
        changed = sorted(k for k in set(old) | set(card) if old.get(k) != card.get(k))
        assert card.get('patch') == old.get('patch'), '%s patch 被改了' % tid
        assert card.get('eval') == old.get('eval'), '%s eval 被改了' % tid
        cur = open(path, 'rb').read()
        idx_diff = sync_index(tid, card, dry=not do_write)
        print('  %-16s 人设 %d 字 sha=%s  改动键=%r  索引=%r'
              % (tid, len(item['persona']), item['persona_sha256'][:8], changed, idx_diff))
        if cur == payload and not idx_diff:
            print('    └ 已是目标内容（跳过）')
            continue
        n_changed += 1
        if do_write:
            tmp = path + '.tmp'
            with io.open(tmp, 'wb') as fh:
                fh.write(payload)
            os.replace(tmp, path)
            assert open(path, 'rb').read() == payload, '%s 写后回读不一致' % tid
            print('    └ [写入] %d → %d B' % (len(cur), len(payload)))

    print('\n共 %d 张需更新%s' % (n_changed, '，已写盘' if do_write else '（dry，加 --write 执行）'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
