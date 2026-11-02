# -*- coding: utf-8 -*-
"""第142轮 · 先量：38 位 NPC 的 patch 复述的到底是同一句吗？

背景（第139轮登记）：76 份 `assets/npc/persona/*.txt` 里写着「一次开口通常 1~2 句」，
其中 38 位的训练卡 `patch` 里又复述了一遍句数规格（`check139 E1` 守着 `38/76`）。
第139轮只处理了主宠 `ralsei`：它的 patch 开头是
    「一次最多两三句，短一点，像随口说出来的。 」（简称 ①，31 字）
删掉后 56 条真机 A/B **无差别**。

本轮**先量再决定**，四个问题：

  Q1 这 38 条的 ① 是不是**逐字相同**？（相同 ⇒ 一次模板生成的，可批量处理）
  Q2 ① 是不是都在 patch **开头**？
  Q3 ① 与人设里的句数规格**一致**吗？（人设是 1~2 句，① 说"最多两三句" ⇒ **相冲突**，
     删 ① 等于把人设收紧到 1~2，那是行为改变，不是"去重"）
  Q4 ① 占 patch 多大比例？删掉会不会把 patch 掏空？

★ 判据只读盘，不改任何产品文件。
"""
import io
import json
import os
import re
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
TRAIN = os.path.join(PET, 'assets', 'npc', '_training')
CARDS_DIR = os.path.join(TRAIN, 'cards')
INDEX_JSON = os.path.join(TRAIN, '_index.json')
PERSONA_DIR = os.path.join(PET, 'assets', 'npc', 'persona')

MARKS = (u'两三句', u'随口说')
#: 人设里那句句数规格的锚点
SPEC_ANCHOR = u'一次开口通常'


def _read(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def _json(p):
    return json.loads(_read(p))


def _has_mark(t):
    return any(m in (t or u'') for m in MARKS)


def main():
    idx = _json(INDEX_JSON)
    cards = idx.get('cards') or {}
    patches = idx.get('patches') or {}

    # ---- 人设侧：哪些写着句数规格，写的是什么 ----
    spec = {}
    for fn in sorted(os.listdir(PERSONA_DIR)):
        if not fn.endswith('.txt'):
            continue
        t = _read(os.path.join(PERSONA_DIR, fn))
        for line in t.split(u'\n'):
            if SPEC_ANCHOR in line:
                spec[fn[:-4]] = line.strip()
                break
    print(u'人设里写「%s」的：%d 份' % (SPEC_ANCHOR, len(spec)))
    variants_spec = {}
    for k, v in spec.items():
        variants_spec.setdefault(v, []).append(k)
    print(u'  这些人设句子共有 %d 种写法：' % len(variants_spec))
    for v, ks in sorted(variants_spec.items(), key=lambda kv: -len(kv[1])):
        print(u'    [%d 人] %s' % (len(ks), v[:110]))
    print(u'')

    # ---- 卡片侧：patch 里带 ① 的 ----
    lead_ids = []
    for k, v in sorted(cards.items()):
        if _has_mark((v or {}).get('patch')):
            lead_ids.append(k)
    # 三份副本一致性（先证明"改一处够不够"）
    p_idx = sorted(k for k, v in patches.items() if _has_mark(v))
    cf = []
    for fn in sorted(os.listdir(CARDS_DIR)):
        if fn.endswith('.json'):
            d = _json(os.path.join(CARDS_DIR, fn))
            if _has_mark(d.get('patch')):
                cf.append(fn[:-5])
    print(u'带 ① 的角色：index.cards %d · index.patches %d · cards/*.json %d'
          % (len(lead_ids), len(p_idx), len(cf)))
    print(u'  三份集合一致？%s' % (lead_ids == p_idx == sorted(cf)))
    print(u'')

    # ---- Q1/Q2：把 ① 摘出来，看有几种写法、在不在开头 ----
    frag = {}
    at_head = 0
    for k in lead_ids:
        p = (cards[k] or {}).get('patch') or u''
        m = re.search(u'[^。！？]*?(?:两三句|随口说)[^。！？]*?[。！？]?\\s*', p)
        s = m.group(0) if m else u''
        frag.setdefault(s.strip(), []).append(k)
        if p.strip().startswith(s.strip()):
            at_head += 1
    print(u'Q1 ① 的写法共 %d 种：' % len(frag))
    for s, ks in sorted(frag.items(), key=lambda kv: -len(kv[1])):
        print(u'  [%d 人 / %d 字] %r' % (len(ks), len(s), s))
        print(u'        %s' % u' '.join(ks[:8]) + (u' …' if len(ks) > 8 else u''))
    print(u'Q2 在 patch 开头（strip 后 startswith）的：%d / %d' % (at_head, len(lead_ids)))
    print(u'')

    # ---- Q3：① 与人设规格是否一致 ----
    print(u'Q3 ① 与人设规格的对照（关键）')
    pairs = {}
    for k in lead_ids:
        p = (cards[k] or {}).get('patch') or u''
        m = re.search(u'[^。！？]*?(?:两三句|随口说)[^。！？]*?[。！？]?\\s*', p)
        s = (m.group(0) if m else u'').strip()
        pairs.setdefault(s, set()).add(spec.get(k, u'（人设无此句）'))
    for s, sp in sorted(pairs.items(), key=lambda kv: -len(kv[1])):
        print(u'  ① = %r' % s)
        for x in sorted(sp):
            print(u'      人设 = %s' % x[:110])
    print(u'')

    # ---- Q4：占比 ----
    tot = 0
    shares = []
    for k in lead_ids:
        p = (cards[k] or {}).get('patch') or u''
        m = re.search(u'[^。！？]*?(?:两三句|随口说)[^。！？]*?[。！？]?\\s*', p)
        s = (m.group(0) if m else u'')
        tot += len(p)
        if s:
            shares.append((len(s), len(p), k))
    print(u'Q4 patch 体量：38 条合计 %d 字，平均 %d 字' % (tot, tot // max(1, len(lead_ids))))
    if shares:
        shares.sort(reverse=True)
        print(u'  ① 最长 %d 字 / patch %d 字（%s）· 最短 %d 字 / patch %d 字（%s）'
              % (shares[0][0], shares[0][1], shares[0][2],
                 shares[-1][0], shares[-1][1], shares[-1][2]))
        ratio = [float(a) / max(1, b) for a, b, _ in shares]
        print(u'  ① 占 patch 比例：中位 %.1f%% · max %.1f%%'
              % (sorted(ratio)[len(ratio) // 2] * 100, max(ratio) * 100))

    # ---- 样本：挑三条不同角色看全文 ----
    print(u'')
    print(u'--- 样本（三条，看 ① 之后接的是什么）---')
    for k in lead_ids[:3]:
        print(u'[%s]' % k)
        print(u'  %s' % ((cards[k] or {}).get('patch') or u'')[:300])
        print(u'')

    ev = {
        'persona_spec_n': len(spec),
        'persona_spec_variants': {k: v for k, v in variants_spec.items()},
        'lead_n': {'index_cards': len(lead_ids), 'index_patches': len(p_idx),
                   'card_files': len(cf), 'all_same': lead_ids == p_idx == sorted(cf)},
        'lead_variants': [{'text': s, 'n': len(ks), 'ids': ks} for s, ks in frag.items()],
        'at_head': at_head,
        'patch_total_chars': tot,
        'patch_mean_chars': tot // max(1, len(lead_ids)),
    }
    evd = os.path.join(ROUND, '_evidence')
    if not os.path.isdir(evd):
        os.makedirs(evd)
    out = os.path.join(evd, 'lead142.json')
    with io.open(out, 'w', encoding='utf-8', newline='') as f:
        f.write(json.dumps(ev, ensure_ascii=False, indent=1))
    print(u'已落盘：', out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
