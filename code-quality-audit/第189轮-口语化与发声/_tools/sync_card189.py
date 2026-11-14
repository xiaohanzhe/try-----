# -*- coding: utf-8 -*-
"""第189轮 · 只重建 `asgore` 一张训练卡（人设改过），且**不许冲掉训练结果**。

为什么不是 `cards113.py --all`
------------------------------
`--all` 会把 77 张卡全部重写：
  · `patch` / `eval` 被清空（第189轮实测 59+61 张，四把老锁同时红）——
    已在 `cards113.py` 加 `carry_trained()` 修掉；
  · `voice_markers` 被重新抽取，把第113轮r 手工剔掉的灌水项塞回去
    （`kris` 的 `想` / `……` 等 10 张）—— 只在**人设 sha256 没变**时可拦，
    asgore 恰好变了，所以那层拦不住；
  · 62 张 CRLF 卡被 `write_text` 统一成 LF，制造大片无意义 diff。
本轮只有 asgore 的人设真变了 ⇒ **只重建它**，其余 95 张一个字节不动。

口径
----
* 走产品自己的抽取函数 `cards113.build_card()`（不另写一套，免得两份口径漂）。
* 走 `cards113.carry_trained()` 保住 `patch` / `eval`。
* 行尾沿用**这个文件原本的**行尾（asgore.json 是 CRLF），不做全库统一。
* 幂等：重建两遍字节相同。

用法
----
    python sync_card189.py            # 只预览差异
    python sync_card189.py --write    # 写盘
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

TARGET = 'asgore'
CARD = os.path.join(C.TRAIN_DIR, 'cards', TARGET + '.json')


def render(card):
    """按文件既有行尾渲染（CRLF 文件仍然 CRLF），末尾一个换行。"""
    raw = open(CARD, 'rb').read()
    crlf = b'\r\n' in raw
    txt = json.dumps(card, ensure_ascii=False, indent=1)
    if crlf:
        txt = txt.replace('\r\n', '\n').replace('\n', '\r\n')
    return (txt + ('\r\n' if crlf else '\n')).encode('utf-8')


def sync_index(card, dry=True):
    """把 `_index.json` 里这张卡的派生记账跟着改（只动这一条）。

    `cards113.py --all` 会整表重写索引；本轮不跑它（那会重排 96 张卡的 JSON 缩进），
    所以这里只把 `persona_chars` / `markers` / `patch` 三项对齐到卡片。
    写盘体例与 `cards113.py` 一致（indent=1 / 不转义中文 / 末尾一个 LF）。
    ★ `dry=True` 时**只算不写**（预览模式不许改盘）。
    """
    path = os.path.join(C.TRAIN_DIR, '_index.json')
    idx = C.load_json(path) or {}
    rec = (idx.get('cards') or {}).get(TARGET)
    if rec is None:
        print('[跳过] 索引里没有 %s' % TARGET)
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
    roster, _gaps = C.load_roster()
    item = next((x for x in roster if x['id'] == TARGET), None)
    assert item, '名单里没有 %s' % TARGET

    old = C.load_json(CARD) or {}
    card = cards113.carry_trained(cards113.build_card(item), CARD)
    payload = render(card)

    print('人设：%d 字  sha256=%s' % (len(item['persona']), item['persona_sha256'][:12]))
    changed = [k for k in set(old) | set(card) if old.get(k) != card.get(k)]
    print('相对磁盘旧卡的改动键：%r' % changed)
    for k in ('patch', 'eval'):
        print('  %-6s 旧 %d 字 → 新 %d 字' % (k, len(json.dumps(old.get(k), ensure_ascii=False)),
                                            len(json.dumps(card.get(k), ensure_ascii=False))))
    assert card.get('patch') == old.get('patch'), 'patch 被改了（carry_trained 失效）'
    assert card.get('eval') == old.get('eval'), 'eval 被改了（carry_trained 失效）'

    cur = open(CARD, 'rb').read()
    idx_changed = sync_index(card, dry=not do_write)
    if cur == payload and not idx_changed:
        print('磁盘已是目标内容（幂等，不写盘）')
        return 0
    if not do_write:
        print('（dry：卡片 %d B → %d B；索引需同步 %r，加 --write 执行）'
              % (len(cur), len(payload), idx_changed))
        return 0
    tmp = CARD + '.tmp'
    with io.open(tmp, 'wb') as fh:
        fh.write(payload)
    os.replace(tmp, CARD)
    assert open(CARD, 'rb').read() == payload, '写后回读不一致'
    print('[写入] %s  %d B' % (CARD, len(payload)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
