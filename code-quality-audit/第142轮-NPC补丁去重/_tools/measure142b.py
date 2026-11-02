# -*- coding: utf-8 -*-
"""第142轮 · 反查：`①` 是不是"这个角色实测超长/句多"的产物？

前一步量到的事实：
  · 76 份人设的句数规格**只有一种写法**：`一次开口通常 1~2 句，最长不超过 200 字…`
  · 38 张卡的 patch 里逐字含 `一次最多两三句，短一点，像随口说出来的。`（①）
  · 三份副本（index.patches / index.cards / cards/*.json）集合完全一致

而 `common113.py` 里：
  · `TOO_LONG` 的触发是 **`len(t) > MAX_CHARS`（200 字）**，不是句数；
  · `build_patch` 按优先级取前 3 条：`MARKDOWN, AI_SELF, SLAVE, NOT_CN,
    ACTION_PAREN, META, TOO_LONG, TOO_MANY_SENTENCES, PARROT, REPEAT, ENGLISH, EMPTY`
    ⇒ ① 出现，说明这个角色**确实**踩过 TOO_LONG/TOO_MANY_SENTENCES，
    而且前面几项没把 3 个槽位占满。

**所以"38 位同型重复"可能根本不是重复，是 38 份实测诊断。**

本脚本用第113轮的原始语料（`raw30/`，每个角色 48~100 轮真机回复）**独立反推**：
  · 对每个角色算：最长回复多少字、超 200 字几条、超 3 句几条
  · 与"patch 里有没有 ①"做交叉表
预测（若 patch 确由数据生成）：**有 ① 的那批，超长/句多计数应显著高于没有的那批**；
若两批数字一样，说明 ① 是"人人一条"的模板，与数据无关 —— 那才是真正该删的重复。

★ 只读盘，不改任何产品文件。
"""
import glob
import io
import json
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
TRAIN = os.path.join(PET, 'assets', 'npc', '_training')
RAW = os.path.join(ROOT, 'code-quality-audit', '第113轮-全体角色AI训练',
                   '_evidence', 'raw30')
MAX_CHARS = 200
# ★★★ 第143轮订正：原来这行注释写的是「与 `common113._sentences` 同口径（不含 `…`）」
#   ——**与实现相反**。`_sentences` 的正则是 `[。！？!?…]+`，**含** `…`。
#   ⇒ 本文件这份 `END` **不含** `…`，切出来的段**更少** ⇒ 判出的"超 3 句"**更少** ⇒
#   这一列比产品**更宽（更宽松）**，第142轮那张表里"超句"的百分数**偏低**。
#   ⚠️ 第142轮的主结论走的是**长度**（`TOO_LONG`，247 条），不受影响；
#   "100% 有 >3 句"这种**已经到顶**的数字也不受影响（真实值只会更高）；
#   但中间的百分数以后**不许再引用**，要用就按 `_sentences` 重算。
END = u'\u3002\uff01\uff1f!?\n'      # 比 common113._sentences 宽：故意不含 `…`（见上）


def _read(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def _json(p):
    return json.loads(_read(p))


def _has_lead(t):
    return any(m in (t or u'') for m in (u'两三句', u'随口说'))


def n_sent(t):
    n, buf = 0, []
    for ch in t:
        buf.append(ch)
        if ch in END:
            if any(not c.isspace() and c not in END for c in buf):
                n += 1
            buf = []
    if any(not c.isspace() for c in buf):
        n += 1
    return n


def main():
    idx = _json(os.path.join(TRAIN, '_index.json'))
    cards = idx.get('cards') or {}

    # 每个角色的原始回复
    per = {}
    for p in sorted(glob.glob(os.path.join(RAW, '*.jsonl'))):
        name = os.path.basename(p)[:-6]
        texts = []
        for line in io.open(p, encoding='utf-8', newline=''):
            if not line.strip():
                continue
            rec = json.loads(line)
            for turn in rec.get('turns') or []:
                t = (turn.get('final') or u'').strip()
                if t:
                    texts.append(t)
        if texts:
            per[name] = texts

    print(u'语料：%d 个角色（raw30）· 卡片 %d 张' % (len(per), len(cards)))
    print(u'')

    rows = []
    for name, v in sorted(cards.items()):
        lead = _has_lead((v or {}).get('patch'))
        ts = per.get(name) or []
        if not ts:
            rows.append({'id': name, 'lead': lead, 'n': 0, 'max': 0,
                         'over200': 0, 'over3s': 0, 'mean': 0.0, 'norec': True})
            continue
        lens = [len(t) for t in ts]
        rows.append({
            'id': name, 'lead': lead, 'n': len(ts),
            'max': max(lens),
            'over200': sum(1 for x in lens if x > MAX_CHARS),
            'over3s': sum(1 for t in ts if n_sent(t) > 3),
            'mean': round(sum(lens) / float(len(lens)), 1),
            'norec': False,
        })

    have = [r for r in rows if r['lead']]
    lack = [r for r in rows if not r['lead']]
    print(u'有 ①：%d 人 · 无 ①：%d 人' % (len(have), len(lack)))
    norec = [r['id'] for r in rows if r['norec']]
    if norec:
        print(u'  ⚠ 无原始语料的：%s' % u' '.join(norec))
    print(u'')

    def agg(rs, label):
        rs = [r for r in rs if not r['norec']]
        if not rs:
            return None
        n = len(rs)
        over = sum(1 for r in rs if r['over200'] > 0)
        over3 = sum(1 for r in rs if r['over3s'] > 0)
        tot200 = sum(r['over200'] for r in rs)
        tot3s = sum(r['over3s'] for r in rs)
        mx = max(r['max'] for r in rs)
        print(u'  %-8s n=%-3d 至少 1 条超200字 %d 人(%.1f%%) · 至少 1 条超3句 %d 人(%.1f%%) '
              u'· 超200字共 %d 条 · 超3句共 %d 条 · 最长 %d 字'
              % (label, n, over, 100.0 * over / n, over3, 100.0 * over3 / n,
                 tot200, tot3s, mx))
        return {'n': n, 'over200_ids': over, 'over3s_ids': over3,
                'tot200': tot200, 'tot3s': tot3s, 'max': mx}

    print(u'=== 交叉表：patch 里有没有 ① × 实测长度 ===')
    a_have = agg(have, u'有①')
    a_lack = agg(lack, u'无①')
    print(u'')

    # 关键判据：那 38 人里有多少"确实超长"
    h_ids = [r for r in have if not r['norec']]
    h_over = [r for r in h_ids if r['over200'] > 0]
    h_over3 = [r for r in h_ids if r['over3s'] > 0]
    print(u'有 ① 的 %d 人里：实测超过 200 字 %d 人（%.1f%%）· 实测超过 3 句 %d 人（%.1f%%）'
          % (len(h_ids), len(h_over), 100.0 * len(h_over) / max(1, len(h_ids)),
             len(h_over3), 100.0 * len(h_over3) / max(1, len(h_ids))))
    clean = [r['id'] for r in h_ids if r['over200'] == 0 and r['over3s'] == 0]
    print(u'  「既没超长也没超句」却有 ① 的：%d 人 %s'
          % (len(clean), (u' '.join(clean[:12]) + (u' …' if len(clean) > 12 else u''))))
    print(u'')

    # 反向：没 ① 的那批里，有多少其实也超长？（说明被"前 3 槽位"挤掉了）
    l_ids = [r for r in lack if not r['norec']]
    l_over = [r['id'] for r in l_ids if r['over200'] > 0]
    print(u'无 ① 的 %d 人里，实测也超长过的：%d 人' % (len(l_ids), len(l_over)))
    if l_over:
        print(u'  %s' % (u' '.join(l_over[:15]) + (u' …' if len(l_over) > 15 else u'')))
        print(u'  ⇒ 这些是"优先级被更高违规占满 3 槽"而没拿到 ① 的，不是没违规')
    print(u'')

    print(u'--- 有 ① 且实测最长的前 10 人 ---')
    for r in sorted(h_ids, key=lambda x: -x['max'])[:10]:
        print(u'  %-22s 最长 %-4d 字 · 超200 %-2d 条 · 超3句 %-2d 条 · 均 %s 字'
              % (r['id'], r['max'], r['over200'], r['over3s'], r['mean']))
    print(u'')
    print(u'--- 无 ① 且实测最长的前 8 人（对照）---')
    for r in sorted(l_ids, key=lambda x: -x['max'])[:8]:
        print(u'  %-22s 最长 %-4d 字 · 超200 %-2d 条 · 超3句 %-2d 条 · 均 %s 字'
              % (r['id'], r['max'], r['over200'], r['over3s'], r['mean']))

    ev = {
        'cards': len(cards), 'raw_npcs': len(per),
        'have_lead': len(have), 'lack_lead': len(lack),
        'norec': norec,
        'agg_have': a_have, 'agg_lack': a_lack,
        'have_over200_ids': len(h_over), 'have_over3s_ids': len(h_over3),
        'have_but_clean': clean,
        'lack_but_over200': l_over,
        'rows': rows,
    }
    evd = os.path.join(ROUND, '_evidence')
    if not os.path.isdir(evd):
        os.makedirs(evd)
    out = os.path.join(evd, 'lead142b.json')
    with io.open(out, 'w', encoding='utf-8', newline='') as f:
        f.write(json.dumps(ev, ensure_ascii=False, indent=1))
    print(u'')
    print(u'已落盘：', out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
