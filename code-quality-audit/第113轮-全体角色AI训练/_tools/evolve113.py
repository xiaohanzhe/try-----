# -*- coding: utf-8 -*-
"""第113轮b · 关系演化卡：把训练里「关系怎么变」的产出固化成运行时能读的数据。

## 为什么必须单独做一个文件
用户 2026-10-25 原话：「**每个人间的关系是可随着发展变动的哦，可别前期训练完后期
不记得全没了**」。这句话点的是两件事：

1. **关系不是静态设定**。原来注入 system 的 `_attitude.json` 是从《人物关系叙述.txt》
   摘的**原作原句**，那是一张不动的卡片（"Susie 和 Kris 是队友"）。
   但角色在对话里说出来的"我一开始很烦他，后来……"是**有时间轴的**，前者装不下后者。
2. **训练出来的东西会丢**。`raw30/*.jsonl` 一重跑就被覆盖（`--force` 追加新版，
   旧版沉在文件里但没人读），下次改个规则再跑一遍，上一版学会的关系认知就没了。

⇒ 本脚本把 `raw30` 里关系段/角色间段的问答**抽出来单独存**（`_relations/_evolution.json`），
   它不随重跑消失，运行时可以按需注入。`raw30` 是"过程"，这份是"沉淀"。

## 用法
    python evolve113.py            # 生成 _relations/_evolution.json
    python evolve113.py --report   # 只看覆盖情况，不写文件
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import common113 as C          # noqa: E402
import train30 as T            # noqa: E402

OUT = os.path.join(C.NPC_DIR, '_relations', '_evolution.json')

#: 关系段里**最能体现"变化"**的问法特征。注入时优先取这些轮。
CHANGE_HINTS = ('后来', '变化', '改观', '闹翻', '一开始', '以前', '后来才')

#: 每条回答截到多少字再进 prompt（system 已经很长，不能塞满）
MAX_ANSWER_CHARS = 90
#: 每个角色最多带几条进 prompt
MAX_PAIRS = 3


def _latest(target=None):
    """id → 该 id 最后一条 `turns_n == target` 的记录。"""
    target = target or T.TURNS_DEFAULT
    out = {}
    if not os.path.isdir(T.RAW30):
        return out
    for f in sorted(os.listdir(T.RAW30)):
        if not f.endswith('.jsonl'):
            continue
        best = None
        for r in C.read_jsonl(os.path.join(T.RAW30, f)):
            if isinstance(r, dict) and r.get('turns_n') == target:
                best = r              # 后面的覆盖前面的 ⇒ 留最新
        if best:
            out[f[:-6]] = best
    return out


def _clip(s, n=MAX_ANSWER_CHARS):
    s = (s or '').strip().replace('\n', ' ')
    return s if len(s) <= n else s[:n] + '…'


def pairs_of(rec):
    """从一条训练记录里抽关系/角色间段的问答。"""
    out = []
    for t in rec.get('turns') or []:
        slot = t.get('slot') or ''
        tag = T.tag_of(slot)
        if tag not in ('rel', 'npc'):
            continue
        a = (t.get('final') or '').strip()
        if not a:
            continue
        out.append({'tag': tag, 'i': t.get('i'),
                    'q': (t.get('user') or '')[:120],
                    'a': _clip(a)})
    return out


def build():
    rows = _latest()
    npcs = {}
    for nid, rec in sorted(rows.items()):
        ps = pairs_of(rec)
        if not ps:
            continue
        npcs[nid] = {'turns_n': rec.get('turns_n'),
                     'built_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                     'pairs': ps}
    data = {
        'schema_version': 1,
        'note': ('训练里"关系怎么变"的产出。与 `_attitude.json`（原作的静态关系）'
                 '分工不同：那份是设定，这份是角色**自己说过的**关系轨迹。'
                 '由 `_tools/evolve113.py` 从 raw30 抽取，重跑训练不会丢。'),
        'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'turns_n': T.TURNS_DEFAULT,
        'count': len(npcs),
        'npcs': npcs,
    }
    return data


def report(data):
    print('覆盖角色：%d 人' % data['count'])
    print('按轮数口径：turns_n == %d' % data['turns_n'])
    print('')
    for nid, rec in sorted(data['npcs'].items())[:12]:
        n_change = sum(1 for p in rec['pairs'] if any(h in p['q'] for h in CHANGE_HINTS))
        print('  %-22s %d 条（含"变化"追问 %d 条）' % (nid, len(rec['pairs']), n_change))
        for p in rec['pairs'][:2]:
            print('     Q: %s' % p['q'][:60])
            print('     A: %s' % p['a'][:60])
    if data['count'] > 12:
        print('  …… 其余 %d 人省略' % (data['count'] - 12))


def main(argv):
    data = build()
    if '--report' in argv:
        report(data)
        return 0
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, OUT)
    # 回读校验：写进去的东西必须能读回来、条数对得上
    with open(OUT, 'rb') as f:
        back = json.loads(f.read().decode('utf-8'))
    ok = (back.get('count') == data['count']
          and set(back.get('npcs') or {}) == set(data['npcs']))
    print('写入 %s（%d 字节）回读校验：%s'
          % (OUT, os.path.getsize(OUT), 'OK' if ok else 'FAIL'))
    report(data)
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
