# -*- coding: utf-8 -*-
"""第一百一十三轮 · 对他人态度（build 阶段，不占模型）

用户 2026-10-24 口径：「调权重、性格、记忆、口癖、**和对她人的态度**（这要求他能
识别出来别人，所以可以最后做）」。

为什么最后做：识别"别人"需要**知道别人是谁**。第113轮刚把 `人物关系叙述.txt`
切成了 `_relations/_index.json`（作品→小节→人物），这份索引正好提供"谁和谁什么关系"。

本脚本只做「准备」，不跑模型、不改产品代码：
  1. 从关系真源里，为每个 NPC 抽出**同句共现**的句子（`Susie` 与 `Lancer` 出现在
     同一句里 ⇒ 那句就是他俩的关系描述）。原句照抄，不做二次改写 —— 改写过就失真。
  2. 每组关系压成一行「你和 X：<原句>」，拼成该角色的**关系小卡**（≤ 220 字）。
  3. 选 3 个**同作品、有原句依据**的对象当**探针**，供 `--eval` 问
     「你觉得 X 怎么样？」并比对回答是否有区分度。

产物：`assets/npc/_relations/_attitude.json`
用法：`python attitude113.py --build`
"""
import json
import io
import os
import re
import sys

import common113 as C
import relations113 as R

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(C.NPC_DIR, '_relations')
EV = os.path.abspath(os.path.join(HERE, '..', '_evidence'))

CARD_MAX = 220          # 关系小卡上限（实际控制的是 prompt 增量，不是回答长度）
MAX_PAIRS = 3           # 最多写 3 组关系，多了会盖住角色自己的口癖
SENT_MAX = 90           # 单句原话上限，超长就截断（真源里有 200+ 字的复合长句）

_SENT_SPLIT = re.compile(r'(?<=[。；！？])')

#: ★★★ 三道清洗（实测必须，否则关系卡会把角色教坏）
#:  ① 排除「总体关系网」小节 —— 那是总结，句子是串联，不是某个人的关系；
#:  ② 排除代词开头的句子 —— 「她与 Ceroba 是朋友」里的"她"根本不是本角色，
#:     自动摘句无法判断指代，只能丢弃（hy_clover 就栽在这句上）；
#:  ③ 排除"串联句" —— 一句里塞 4 个以上人名的，通常是概述（「Susie 连接着学校、
#:     Lancer 的友情、Ralsei 的成长…」），当个体关系用会让角色说错话。
_PRONOUN_HEAD = re.compile(r'^[「『（(【\s]*(她|他|它|ta|Ta|TA|TA们|他们|她们|它们|其)')
SUMMARY_HEADING = re.compile(r'总体关系|关系网|总结')
MAX_NAMES_IN_SENT = 4
#: ★★★ 第五道清洗（最终判据）：**句首必须是一个"具体的已知角色名"**。
#:   为什么不用"必须以我的名字起句"：`Lancer 与 Susie 是最好的朋友` 配给 Susie
#:   完全正确（双向关系），按"自己起句"就白丢了。
#:   为什么必须卡句首：反例「在和平路线结尾，**她**会和 Starlo 一起试图阻止 Ceroba」
#:   —— 句首是介词短语、主语是代词 Martlet，Starlo 只是宾语，配给 Starlo 就错。
#:   所以判的是"主语明不明确"，不是"主是不是我"。句首是 `她/在/当/而` 一律丢。
_SUBJECT_LEAD = re.compile(r'^[「『（(【\t ]*(在|当|而|但|于是|后来|这|那|其|虽然|因为|如果|为了)')
SUBJECT_MUST_START = True
LEAD_NAME_MIN = 3           # 判"句首是人名"时，太短的别名（Ed、ta）不作数

#: ★ 第四道清洗：**关系定性**优先于**剧情事件**。
#:   要的是"他和你是什么关系"，不是"他后来干了什么"。
#:   实测反例：「当 Clover 杀死 Starlo 后，她变得冰冷而愤怒」—— 这是事件，
#:   塞进关系卡会让角色以为自己杀过 Starlo，甚至混淆和平线/屠杀线。
REL_WORDS = (
    '朋友', '搭档', '伙伴', '队友', '父亲', '母亲', '儿子', '女儿', '兄弟', '姐妹',
    '老师', '学生', '师父', '徒弟', '家人', '亲人', '儿子', '女爸爸', '小爸爸',
    '敌人', '对手', '宿敌', '崇拜', '暗恋', '迷恋', '信任', '依赖', '保护', '守护',
    '嫌弃', '害怕', '讨厌', '尊敬', '厌恶', '敌意', '亲密', '冷淡', '照顾', '关心',
    '憎恨', '嫉妒', '喜欢', '爱', '一边', '忠诚', '承诺', '约定', '歉意', '愧疚',
)
EVENT_WORDS = ('杀死', '杀掉', '击败', '路线中', '变得', '复仇', '死亡', '坠落',
               '开战', '战斗', '绑架', '囚禁', '献祭')


def sentences(text):
    """按中文句读切句。关系真源里 '；' 用得比 '。' 还多，必须一起切。"""
    out = []
    for chunk in _SENT_SPLIT.split(text):
        s = chunk.strip().replace('\n', '')
        s = re.sub(r'^[一二三四五六七八九十]+、.*?$', '', s).strip()
        if len(s) >= 8:
            out.append(s)
    return out


def _lead_rank(sent, me):
    """句子开头是不是我 —— 0 优先、1 次之。

    ★ 为什么加这一层（G5 判出来的真问题）：
      「Asgore 与 Toriel 曾是…，Asriel 是他们的亲生儿子」这一句同时被 Toriel 和
      Asriel 选中（对两人都成立），结果两张卡**一字不差** ⇒ 角色没区分度。
      优先选"以我开头"的句子，只要该角色自己有句子，就不会跟别人撞卡。
    """
    head = sent.lstrip('「『（(【 \t')
    return 0 if any(head.startswith(a) for a in me) else 1


def _score(sent):
    """关系词加权、事件词降权。分数只用于排序，不参与取舍。"""
    s = sum(2 for w in REL_WORDS if w in sent)
    s -= sum(1 for w in EVENT_WORDS if w in sent)
    return s


def _is_modifier(sent, me):
    """我在这句里是否**只**以「X 的…」形式出现（修饰语，不是主体）。

    ★ 实测反例：「Mettaton 由 Alphys 创造，灵魂来自 **Napstablook 的表哥** Hapstablook。」
      对 Napstablook 而言这句讲的是 Mettaton，他只是别人的亲戚定语。
      按"含我名字"就收进来，他的卡会变成「你和 Alphys：Mettaton 由 Alphys 创造…」
      —— 卡上写的关系根本不是他自己的（G5 靠"两张卡一模一样"才抓到）。
    """
    hit_any = False
    for a in me:
        if not _has(sent, a):
            continue
        hit_any = True
        if not re.search(re.escape(a) + r'\s*的', sent):
            return False        # 至少有一处不是"X 的"，说明是主体
    return hit_any              # 全是"X 的"（或压根没出现）⇒ 不算我的关系句


def usable(sent, me, all_names):
    """这句能不能当关系依据。六道清洗见文件头常量注释。"""
    if _PRONOUN_HEAD.match(sent) or _SUBJECT_LEAD.match(sent):
        return False
    if _is_modifier(sent, me):
        return False
    # ★ 串联句：「Berdly 与 Kris 是…，与 Susie 从鄙视到迷恋，与 Noelle 是…」
    #   一句话把 A 对 B/C/D 各说一遍 ⇒ 塞进任何一格都会把别人的关系说成自己的。
    if sent.count('与') >= 3:
        return False
    hit = [nm for nm in all_names if _has(sent, nm)]
    if len(hit) > MAX_NAMES_IN_SENT:
        return False
    if SUBJECT_MUST_START:
        head = sent.lstrip('「『（(【 \t')
        if not any(len(a) >= LEAD_NAME_MIN and head.startswith(a) for a in all_names):
            return False
    return True


def build_one(nid, pool, sec_texts, alias_map):
    """返回 {'pairs': [...], 'card': str, 'probe': [...]}"""
    me = alias_map.get(nid) or set()
    if not me:
        return None
    all_names = set()
    for other in pool:
        all_names.update(alias_map.get(other['id']) or set())

    # 1) 扫全作品句子，找"我 + 别人"同句共现
    pairs = {}
    for other in pool:
        if other['id'] == nid:
            continue
        other_ids = alias_map.get(other['id']) or set()
        if not other_ids:
            continue
        hits = []
        for sent in sec_texts:
            if not any(_has(sent, a) for a in me):
                continue
            if not any(_has(sent, b) for b in other_ids):
                continue
            if not usable(sent, me, all_names):
                continue
            hits.append(sent)
        if hits:
            hits.sort(key=lambda s: (_lead_rank(s, me), -_score(s), s))   # ★ 我开头 > 关系词 > 字典序
            pairs[other['id']] = {'with': other['id'],
                                  'with_name': other.get('name') or other['id'],
                                  'with_name_cn': other.get('name_cn') or '',
                                  'cooccur': len(hits),
                                  'score': _score(hits[0]),
                                  'sentences': hits[:2]}

    # 2) 排前 N 组：先按共现句数，再按名字稳定序（保证可复算）
    ranked = sorted(pairs.values(),
                    key=lambda p: (-p.get('score', 0), -p['cooccur'], p['with']))[:MAX_PAIRS]

    # 3) 拼关系小卡（原句照抄，超长截断）
    #    ★ 同一句只能用一次：一个句子里若同时讲了两个人，重复填两格会变成
    #      "你和 A：<其实在说 B>"。这条和 usable() 的串联句检测互为兜底。
    parts, used, kept = [], set(), []
    for p in ranked:
        s = next((x for x in p['sentences'] if x not in used), None)
        if not s:
            continue
        used.add(s)
        kept.append(p)
        if len(s) > SENT_MAX:
            s = s[:SENT_MAX].rstrip('，、；') + '…'
        label = p['with_name'] + ('（%s）' % p['with_name_cn'] if p['with_name_cn']
                                  and p['with_name_cn'] != p['with_name'] else '')
        parts.append('你和 %s：%s' % (label, s))
    ranked = kept
    card = '\n'.join(parts)
    if len(card) > CARD_MAX:
        # 按整行丢，不切半句（切半句会变成"你和 X：Susie 是 Kris 最重…"，读着像 bug）
        keep, total = [], 0
        for line in card.split('\n'):
            if total + len(line) + 1 > CARD_MAX and keep:
                break
            keep.append(line)
            total += len(line) + 1
        card = '\n'.join(keep)

    probe = [p['with'] for p in ranked]
    return {'pairs': ranked, 'card': card, 'probe': probe,
            'probe_names': [p['with_name'] for p in ranked],
            'unused_pairs': len(pairs) - len(ranked)}


def _has(text, name):
    if name.isascii():
        return re.search(r'(?<![A-Za-z])%s(?![A-Za-z])' % re.escape(name), text) is not None
    return name in text


def main(argv):
    if '--recheck' in argv:
        return recheck_main(argv)
    if '--eval' in argv:
        return eval_main(argv)
    if '--build' not in argv:
        print('用法：python attitude113.py --build   # 只读，出关系卡\n'
              '      python attitude113.py --eval    # 占模型，问态度题', flush=True)
        return 2

    idx_path = os.path.join(OUT, '_index.json')
    if not os.path.isfile(idx_path):
        print('[FAIL] 先跑 relations113.py 生成 _index.json', flush=True)
        return 2
    with io.open(idx_path, encoding='utf-8') as f:
        index = json.load(f)

    roster, gaps = C.load_roster()
    reg = C.load_json(os.path.join(C.NPC_DIR, '_registry.json'), {}) or {}
    reg_by_id = {x['id']: x for x in (reg.get('npcs') or [])}

    # 每个 NPC 的别名集（复用 relations113 的规则，保证两处口径一致）
    alias_map = {n['id']: R.names_of(reg_by_id.get(n['id'], n)) for n in reg_by_id.values()}

    # 作品内候选池
    pools = {}
    for p in ('', 'os_', 'hy_', 'ut_', 'ot_'):
        pools[p] = [x for x in (reg.get('npcs') or []) if _in_pool(x['id'], p)]

    out = {'schema_version': 1,
           'built_from': {'relations_index': '_index.json',
                          'relations_sha256': index['source']['sha256']},
           'card_max': CARD_MAX, 'max_pairs': MAX_PAIRS,
           'npcs': {}}
    no_rel = []
    no_probe = []
    for w in index['works']:
        sec_texts = []
        for s in w['sections']:
            if SUMMARY_HEADING.search(s['heading']):
                continue                    # ★ 清洗①：总结节不进素材
            sec_texts.extend(sentences(s['text']))
        for nid in w['npcs']:
            if nid in out['npcs']:
                continue
            pool = pools.get(w['prefix'], [])
            got = build_one(nid, pool, sec_texts, alias_map)
            if not got:
                no_rel.append(nid)
                continue
            got['work'] = w['key']
            out['npcs'][nid] = got
            if not got['probe']:
                no_probe.append(nid)

    out['coverage'] = {'npcs': len(out['npcs']), 'no_relation_text': no_rel,
                       'no_probe': no_probe}
    # ★ 自检：每条卡句必须同时含**本角色**与**对方**。
    #   少一个就是错配（把别人的关系说成自己的），这种卡比没有卡更坏 ⇒ 写盘前先卡住。
    bad = []
    for nid, v in out['npcs'].items():
        me_set = alias_map.get(nid) or set()
        for p in v['pairs']:
            sent = p['sentences'][0]
            other_set = alias_map.get(p['with']) or set()
            if not any(_has(sent, x) for x in me_set):
                bad.append({'npc': nid, 'with': p['with'], 'why': '缺本角色', 'sent': sent})
            if not any(_has(sent, x) for x in other_set):
                bad.append({'npc': nid, 'with': p['with'], 'why': '缺对方', 'sent': sent})
    out['selfcheck'] = {'bad_pairs': bad, 'ok': not bad}
    if bad:
        print('[FAIL] 自检发现 %d 处错配，拒绝写盘：' % len(bad), flush=True)
        for b in bad[:5]:
            print('   ', b, flush=True)
        return 1
    if not os.path.isdir(OUT):
        os.makedirs(OUT)
    p = os.path.join(OUT, '_attitude.json')
    with io.open(p, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    print('已写 %s（%d 人）' % (p, len(out['npcs'])), flush=True)
    print('  自检：%s' % ('通过（0 处错配）' if not bad else '%d 处' % len(bad)), flush=True)
    full = sum(1 for v in out['npcs'].values() if len(v['probe']) >= 2)
    one = sum(1 for v in out['npcs'].values() if len(v['probe']) == 1)
    print('  探针：≥2 个 %d 人 / 仅 1 个 %d 人 / 无 %d 人'
          % (full, one, len(out['npcs']) - full - one), flush=True)
    print('  无关系原文：%d 人 %s' % (len(no_rel), '、'.join(no_rel[:10])), flush=True)
    print('  无探针对象：%d 人 %s' % (len(no_probe), '、'.join(no_probe[:10])), flush=True)
    # 抽样自证：人看的三个
    for nid in ('susie', 'lancer', 'hy_clover'):
        v = out['npcs'].get(nid)
        if v:
            print('  · %s 探针=%s' % (nid, v['probe']), flush=True)
            print('    %s' % v['card'].replace('\n', ' / ')[:200], flush=True)
    return 0


def _in_pool(nid, prefix):
    if prefix == '':
        return not any(nid.startswith(x) for x in ('os_', 'hy_', 'ut_', 'ot_'))
    return nid.startswith(prefix)


# ---------------------------------------------------------------- eval（占模型）
ATT_DUP = 0.80          # 两答相似度上限（超过 = 换了名字没换态度）
ATT_DUP_DENAMED = 0.75  # 去掉人名后仍像 = 套模板
MAX_WAIT_S = 240


def wait_for_memory(floor=450, max_wait=MAX_WAIT_S):
    """与 dialogue113 同一口径：不够就等，不死。"""
    import psutil
    import time as _t
    waited = 0
    while waited < max_wait:
        if psutil.virtual_memory().available / 1e6 >= floor:
            break
        if waited == 0:
            print('  ！可用内存不足，等一等…', flush=True)
        _t.sleep(15)
        waited += 15
    return waited


def _dename(text, names):
    """把双方名字抹成同一个占位符 —— 抹完还像，就说明只是换了个名字。"""
    out = text
    for n in sorted(names, key=len, reverse=True):
        if n:
            out = out.replace(n, '§')
    return out


def eval_main(argv):
    """对每个角色问「你觉得 A/B/C 怎么样」，看回答有没有真的区分。"""
    import common113 as _C
    import dialogue113 as _D
    import json as _json
    import time as _t

    only = None
    if '--only' in argv:
        only = set(x.strip() for x in argv[argv.index('--only') + 1].split(',') if x.strip())
    limit = 0
    if '--limit' in argv:
        limit = int(argv[argv.index('--limit') + 1])

    with io.open(os.path.join(OUT, '_attitude.json'), encoding='utf-8') as f:
        att = json.load(f)
    npcs = att['npcs']
    roster, _ = _C.load_roster()
    by_id = {x['id']: x for x in roster}

    targets = []
    for item in roster:
        a = npcs.get(item['id']) or {}
        if len(a.get('probe') or []) < 2:
            continue
        if only and item['id'] not in only:
            continue
        targets.append(item)
    if limit:
        targets = targets[:limit]
    print('态度评测：%d 人（探针 ≥2 的）' % len(targets), flush=True)

    idx_path = os.path.join(EV, 'attitude113.json')
    done = {}
    if os.path.isfile(idx_path):
        try:
            with io.open(idx_path, encoding='utf-8') as f:
                done = (json.load(f) or {}).get('npcs') or {}
            print('  断点：已完成 %d 人' % len(done), flush=True)
        except Exception:
            done = {}

    patch_map = (_C.load_json(os.path.join(_C.TRAIN_DIR, '_index.json'), {}) or {}).get('patches') or {}
    out = {'schema_version': 1, 'model': _C.MODEL,
           'rule': {'dup_max': ATT_DUP, 'dup_denamed_max': ATT_DUP_DENAMED},
           'npcs': dict(done)}
    t0 = _t.time()
    for n, item in enumerate(targets, 1):
        nid = item['id']
        if nid in out['npcs']:
            continue
        a = npcs[nid]
        rel = a.get('card') or ''
        # ★ 走训练脚本同一个取卡口（`load_card` 会把 `item['persona']` 注成 `_persona_text`），
        #   保证"评测用的 system"和"训练用的 system"是同一份，不是我自己另拼一份。
        card = _D.load_card(nid, by_id) or {}
        if not card.get('_persona_text'):
            print('  跳过 %s：取不到人设正文' % nid, flush=True)
            continue
        system = _C._NP.build_system_prompt(
            card['name'], card['_persona_text'], entries=[], npc_id=nid,
            patch=patch_map.get(nid) or '', relation=rel)
        probe = a['probe'][:3]
        replies = []
        for pid in probe:
            other = a['pairs'] and next((p for p in a['pairs'] if p['with'] == pid), None)
            oname = (other or {}).get('with_name') or pid
            q = '你觉得%s怎么样？' % oname
            wait_for_memory()
            try:
                text, st = _C.chat([{'role': 'system', 'content': system},
                                    {'role': 'user', 'content': q}],
                                   seed=_C.stable_seed(nid, 'att', pid),
                                   temperature=_C.TEMPERATURE)
            except Exception as e:
                replies.append({'with': pid, 'name': oname, 'q': q,
                                'reply': '', 'error': repr(e)[:160]})
                continue
            _bad, _soft = _C.gate_reply(text, q, (), card['name'],
                                        card.get('_persona_text') or '')
            replies.append({'with': pid, 'name': oname, 'q': q, 'reply': text,
                            'violations': [list(x) for x in _bad],
                            'soft': [list(x) for x in _soft], 'stats': st})

        # 判据：两两相似度（原样 / 去名）
        pairs = []
        for i in range(len(replies)):
            for j in range(i + 1, len(replies)):
                r1, r2 = replies[i], replies[j]
                if not r1['reply'] or not r2['reply']:
                    continue
                sim = _C.similarity(r1['reply'], r2['reply'])
                nm = set([r1['name'], r2['name']])
                dn = _C.similarity(_dename(r1['reply'], nm), _dename(r2['reply'], nm))
                pairs.append({'a': r1['with'], 'b': r2['with'],
                              'sim': round(sim, 3), 'sim_denamed': round(dn, 3),
                              'same': sim >= ATT_DUP, 'same_denamed': dn >= ATT_DUP_DENAMED})
        # ★ 「有没有提到对方」只作参考，不当硬判据：
        #   角色用"那家伙""她"完全正常（实测 Susie 对 Kris 就说"那家伙"），
        #   而且中文名和英文名都可能出现（Lancer 那条答的是"兰瑟"）。
        named_ok = 0
        for r in replies:
            if not r.get('reply'):
                continue
            other_obj = by_id.get(r['with']) or {}
            cand = {r.get('name') or '', other_obj.get('name_cn') or '',
                    other_obj.get('name') or ''} - {''}
            if any(n in r['reply'] for n in cand):
                named_ok += 1
        out['npcs'][nid] = {'_id': nid, 'card': rel, 'probe': probe, 'replies': replies,
                            'pairs': pairs,
                            'same_pairs': sum(1 for p in pairs if p['same']),
                            'same_denamed_pairs': sum(1 for p in pairs if p['same_denamed']),
                            'named_ok': named_ok, 'n': len(replies)}
        flag = 'OK' if not any(p['same'] for p in pairs) else '同质'
        print('[%d/%d] %-22s %d 问 同质对=%d 去名同质=%d 称呼对=%d/%d  %s'
              % (n, len(targets), nid, len(replies),
                 out['npcs'][nid]['same_pairs'],
                 out['npcs'][nid]['same_denamed_pairs'], named_ok, len(replies), flag),
              flush=True)
        with io.open(idx_path, 'w', encoding='utf-8', newline='\n') as f:
            json.dump(out, f, ensure_ascii=False, indent=1)

    _write_att_report(out, by_id)
    print('耗时 %.0fs → %s' % (_t.time() - t0, idx_path), flush=True)
    return 0


def recheck_main(argv):
    """对已产出的回答**事后**补判格式合规（不重跑模型）。

    ★ 为什么需要：`--eval` 首版只算了"区分度"，没查"格式是否合规"。
      于是 `kris` 三条全用「（看着你）」开头照样判 OK —— 区分度 0 同质，
      但格式问题被放过去了。**只测一个维度就会漏另一个维度。**
    """
    import common113 as _C
    import json as _json

    idx_path = os.path.join(EV, 'attitude113.json')
    with io.open(idx_path, encoding='utf-8') as f:
        out = json.load(f)
    roster, _ = _C.load_roster()
    by_id = {x['id']: x for x in roster}
    patch_map = (_C.load_json(os.path.join(_C.TRAIN_DIR, '_index.json'), {}) or {}).get('patches') or {}

    n_bad = n_tot = 0
    per_code = {}
    for nid, v in out['npcs'].items():
        persona = (by_id.get(nid) or {}).get('persona') or ''
        vios = []
        for r in v.get('replies') or []:
            if not r.get('reply'):
                continue
            n_tot += 1
            bad, soft = _C.gate_reply(r['reply'], r.get('q') or '', (), by_id.get(nid, {}).get('name') or '',
                                      persona)
            r['violations'] = [list(x) for x in bad]
            r['soft'] = [list(x) for x in soft]
            for c, _w in bad:
                per_code[c] = per_code.get(c, 0) + 1
            if bad:
                n_bad += 1
                vios.append({'i': r.get('with'), 'codes': [c for c, _ in bad]})
        v['bad_replies'] = len(vios)
        v['bad_detail'] = vios
    out['format'] = {'replies': n_tot, 'bad': n_bad,
                     'rate': round(n_bad / max(1, n_tot), 3), 'by_code': per_code}
    with io.open(idx_path, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    _write_att_report(out, by_id)
    print('补判完成：%d 条回答，%d 条格式不合规（%.1f%%）  %s'
          % (n_tot, n_bad, n_bad * 100.0 / max(1, n_tot), per_code), flush=True)
    for nid, v in out['npcs'].items():
        if v.get('bad_replies'):
            print('  %-20s %d/%d 条：%s' % (nid, v['bad_replies'], len(v.get('replies') or []),
                                          v['bad_detail'][:2]), flush=True)
    return 0


def _write_att_report(out, by_id):
    npcs = out['npcs']
    recs = [v for v in npcs.values() if v.get('pairs')]
    same = sum(v['same_pairs'] for v in recs)
    den = sum(v['same_denamed_pairs'] for v in recs)
    tot = sum(len(v['pairs']) for v in recs)
    L = ['# 第一百一十三轮 · 对他人态度（区分度）', '',
         '> 同一个角色，问「你觉得 A/B/C 怎么样」。',
         '> 判据：两答相似度 ≥ %.2f 记"同质"（换了名字没换态度）；'
         '去掉人名后 ≥ %.2f 记"套模板"。' % (ATT_DUP, ATT_DUP_DENAMED), '',
         '## 汇总', '',
         '| 项 | 值 |', '|---|---|',
         '| 参评角色 | %d |' % len(recs),
         '| 回答对总数 | %d |' % tot,
         '| 同质对 | %d（%.1f%%） |' % (same, same * 100.0 / max(1, tot)),
         '| 去名后仍同质 | %d（%.1f%%） |' % (den, den * 100.0 / max(1, tot)),
         '']
    fmt = out.get('format') or {}
    if fmt:
        L += ['## 格式合规（`--recheck` 补判）', '',
              '- 回答 **%d** 条，格式不合规 **%d** 条（%.1f%%）'
              % (fmt['replies'], fmt['bad'], fmt['rate'] * 100),
              '- 按违规码：`%s`' % (fmt.get('by_code') or '无'), '',
              '> 括号/字卡类是否算违规，取决于**人设有没有要求**。'
              '`kris`/`ut_frisk`/`tenna` 的人设明写要用括号或字卡，故豁免。', '']
    worst = sorted(recs, key=lambda v: -v['same_denamed_pairs'])[:12]
    L += ['## 最像模板的 12 个', '', '| 角色 | 去名同质 | 同质 | 提到对方（参考） |', '|---|---|---|---|']
    for v in worst:
        if not v.get('n'):
            continue
        L.append('| `%s` | %d | %d | %d/%d |'
                 % (v.get('_id', ''), v['same_denamed_pairs'], v['same_pairs'],
                    v['named_ok'], v['n']))
    L += ['', '## 逐条样例（前 8 个角色的问答）', '']
    for nid, v in list(npcs.items())[:8]:
        if not v.get('replies'):
            continue
        L.append('### %s' % nid)
        L.append('')
        L.append('**关系卡**：')
        L.append('')
        for ln in (v.get('card') or '').split('\n'):
            L.append('> ' + ln)
        L.append('')
        for r in v['replies']:
            L.append('- **问**：%s' % r['q'])
            L.append('  **答**：%s' % (r.get('reply') or '（空/失败）'))
            L.append('')
        L.append('')
    p = os.path.join(EV, 'attitude113.md')
    with io.open(p, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(L))
    print('报告 → %s' % p, flush=True)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
